"""Network-free tests for incremental sync + mark-and-sweep reconcile (M1.6).

A fake embedder stands in for Pinecone, so these exercise the destructive paths (re-chunk,
delete-before-upsert, removal sweep) deterministically against a real local Chroma store.
"""

from __future__ import annotations

from pathlib import Path

from ingest.chunker import Chunk
from ingest.embed_store import get_collection, store_chunks
from ingest.notion_fetch import PageRecord
from ingest.sync import reconcile_and_sync


def _fake_embed(chunks: list[Chunk]) -> list[list[float]]:
    # Deterministic 4-dim vectors; value varies a little per chunk so they aren't identical.
    return [[float(len(c.text) % 5), 1.0, 0.0, 0.0] for c in chunks]


def _seed(collection: object, record: PageRecord) -> None:
    """Embed + store a record's chunks via the fake embedder (initial store state)."""
    from ingest.chunker import chunk_page

    chunks = chunk_page(record)
    store_chunks(chunks, _fake_embed(chunks), collection=collection)


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


def test_unchanged_page_is_skipped_without_re_embedding(tmp_path: Path) -> None:
    col = get_collection(path=str(tmp_path), name="skip")
    rec = PageRecord("p1", "A", "t1", _words(100))
    _seed(col, rec)
    before = col.count()

    calls: list[int] = []

    def counting_embed(chunks: list[Chunk]) -> list[list[float]]:
        calls.append(len(chunks))
        return _fake_embed(chunks)

    report = reconcile_and_sync([rec], collection=col, embed_fn=counting_embed)

    assert report.skipped == ["p1"]
    assert report.changed == []
    assert calls == []  # embedder never invoked for an unchanged page
    assert col.count() == before


def test_changed_page_re_chunks_to_fewer_with_no_orphans(tmp_path: Path) -> None:
    col = get_collection(path=str(tmp_path), name="reembed")
    # Seed a long page (~900 words -> multiple chunks) at t1.
    _seed(col, PageRecord("p1", "A", "t1", _words(900)))
    seeded = col.count()
    assert seeded > 1

    # Same page, edited (t2), now short -> exactly one chunk.
    report = reconcile_and_sync(
        [PageRecord("p1", "A", "t2", _words(20))], collection=col, embed_fn=_fake_embed
    )

    assert report.changed == ["p1"]
    got = col.get(where={"page_id": "p1"})
    assert len(got["ids"]) == 1  # old tail chunks deleted, no orphans
    assert col.count() == 1


def test_removed_page_is_swept(tmp_path: Path) -> None:
    col = get_collection(path=str(tmp_path), name="sweep")
    _seed(col, PageRecord("p1", "A", "t1", _words(50)))
    _seed(col, PageRecord("p2", "B", "t1", _words(50)))

    # p2 no longer in the desired set.
    report = reconcile_and_sync(
        [PageRecord("p1", "A", "t1", _words(50))], collection=col, embed_fn=_fake_embed
    )

    assert report.removed == ["p2"]
    assert report.skipped == ["p1"]
    assert col.get(where={"page_id": "p2"})["ids"] == []


def test_new_page_is_added(tmp_path: Path) -> None:
    col = get_collection(path=str(tmp_path), name="add")
    _seed(col, PageRecord("p1", "A", "t1", _words(50)))

    report = reconcile_and_sync(
        [PageRecord("p1", "A", "t1", _words(50)), PageRecord("p2", "B", "t1", _words(50))],
        collection=col,
        embed_fn=_fake_embed,
    )

    assert report.changed == ["p2"]
    assert report.skipped == ["p1"]
    assert col.get(where={"page_id": "p2"})["ids"] != []
