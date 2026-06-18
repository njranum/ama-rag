"""Network-free tests for the embed/store stage (M1.5-01). Pinecone is not called here."""

from __future__ import annotations

from pathlib import Path

from ingest.chunker import Chunk
from ingest.embed_store import _chunk_id, _chunk_metadata, get_collection, store_chunks


def test_chunk_id_format() -> None:
    assert _chunk_id(Chunk("p1", "T", "t", 2, "hello")) == "p1:2"


def test_chunk_metadata_has_no_none_values() -> None:
    md = _chunk_metadata(Chunk("p1", "Title", "2026-06-18T00:00:00.000Z", 0, "x"))
    assert md == {
        "page_id": "p1",
        "title": "Title",
        "last_edited_time": "2026-06-18T00:00:00.000Z",
        "chunk_position": 0,
    }
    assert all(v is not None for v in md.values())  # Chroma rejects None metadata values


def test_store_empty_is_a_noop(tmp_path: Path) -> None:
    col = get_collection(path=str(tmp_path), name="empty")
    assert store_chunks([], [], collection=col) == 0
    assert col.count() == 0


def test_store_and_query_roundtrip(tmp_path: Path) -> None:
    col = get_collection(path=str(tmp_path), name="test")
    chunks = [Chunk("p1", "A", "t", 0, "alpha text"), Chunk("p1", "A", "t", 1, "beta text")]
    vectors = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]

    assert store_chunks(chunks, vectors, collection=col) == 2
    assert col.count() == 2

    res = col.query(query_embeddings=[[1.0, 0.0, 0.0, 0.0]], n_results=1)
    assert res["ids"][0][0] == "p1:0"
    assert res["documents"][0][0] == "alpha text"
    assert res["metadatas"][0][0]["chunk_position"] == 0
