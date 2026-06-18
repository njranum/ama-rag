"""Deterministic unit tests for the Stage-2 chunker (M1.4-01)."""

from __future__ import annotations

from ingest.chunker import Chunk, chunk_page, chunk_pages, chunk_text, estimate_tokens
from ingest.notion_fetch import PageRecord

_WORDS_PER_TOKEN = 0.75


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_is_a_single_chunk() -> None:
    assert chunk_text("one two three") == ["one two three"]


def test_estimate_tokens_scales_with_words() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a b c") == round(3 / _WORDS_PER_TOKEN)


def test_windows_overlap_by_expected_words() -> None:
    text = " ".join(f"w{i}" for i in range(1000))
    chunks = chunk_text(text, chunk_tokens=100, overlap_tokens=20)

    size = round(100 * _WORDS_PER_TOKEN)  # 75 words
    overlap = round(20 * _WORDS_PER_TOKEN)  # 15 words

    assert len(chunks) > 1
    first, second = chunks[0].split(), chunks[1].split()
    assert len(first) == size
    # last `overlap` words of chunk 0 == first `overlap` words of chunk 1
    assert first[-overlap:] == second[:overlap]


def test_chunk_page_carries_metadata_and_ordinal_position() -> None:
    rec = PageRecord(
        id="p1",
        title="Title",
        last_edited_time="2026-06-18T00:00:00.000Z",
        text=" ".join(f"w{i}" for i in range(200)),
    )
    chunks = chunk_page(rec, chunk_tokens=100, overlap_tokens=20)

    assert all(isinstance(c, Chunk) for c in chunks)
    assert [c.chunk_position for c in chunks] == list(range(len(chunks)))
    assert all(c.page_id == "p1" and c.title == "Title" for c in chunks)


def test_chunk_pages_flattens_across_records() -> None:
    recs = [
        PageRecord("p1", "A", "t", " ".join(f"x{i}" for i in range(200))),
        PageRecord("p2", "B", "t", "short text"),
    ]
    out = chunk_pages(recs)
    assert {c.page_id for c in out} == {"p1", "p2"}
