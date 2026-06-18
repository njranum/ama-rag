"""Layer 1, Stage 2 — split page text into overlapping chunks.

Splits each page's text into ~500-token windows with ~50-token overlap, carrying a
`chunk_position` ordinal plus the page metadata from Stage 1 (M1.3). Chunk text is kept verbatim:
it is stored alongside the vector and returned to the widget as the source snippet.

Tokeniser note: `llama-text-embed-v2` is hosted (no local torch/transformers), so its exact
tokeniser isn't available in-process. Tokens are approximated by whitespace words (~0.75
words/token). Exact counting isn't load-bearing — the model's 2048-token cap is ~4x the
~500-token target, so the approximation stays well within range. See the "Chunking" decision in
docs/L1_Ingestion.md.

Run from the repo root:  python -m ingest.chunker
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from ingest.notion_fetch import PageRecord

DEFAULT_CHUNK_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 50
# English averages ~1.3 tokens/word; ~0.75 words/token converts a token budget to a word budget.
_WORDS_PER_TOKEN = 0.75


@dataclass(frozen=True)
class Chunk:
    page_id: str
    title: str
    last_edited_time: str
    chunk_position: int
    text: str
    url: str | None = None
    anchor: str | None = None


def estimate_tokens(text: str) -> int:
    """Approximate token count of text (word count / words-per-token)."""
    return round(len(text.split()) / _WORDS_PER_TOKEN)


def chunk_text(
    text: str,
    *,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    """Split text into overlapping word windows (~chunk_tokens each, ~overlap_tokens overlap)."""
    words = text.split()
    if not words:
        return []
    size = max(1, round(chunk_tokens * _WORDS_PER_TOKEN))
    overlap = min(max(0, round(overlap_tokens * _WORDS_PER_TOKEN)), size - 1)
    step = size - overlap

    chunks: list[str] = []
    start = 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
        start += step
    return chunks


def chunk_page(
    record: PageRecord,
    *,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Chunk one page record, carrying its metadata + a 0-based chunk_position per chunk."""
    pieces = chunk_text(record.text, chunk_tokens=chunk_tokens, overlap_tokens=overlap_tokens)
    return [
        Chunk(
            page_id=record.id,
            title=record.title,
            last_edited_time=record.last_edited_time,
            chunk_position=pos,
            text=piece,
        )
        for pos, piece in enumerate(pieces)
    ]


def chunk_pages(records: list[PageRecord]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for record in records:
        chunks.extend(chunk_page(record))
    return chunks


def main() -> int:
    from ingest.notion_fetch import fetch_portfolio_pages

    try:
        records = fetch_portfolio_pages()
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    chunks = chunk_pages(records)
    print(
        f"{len(records)} pages -> {len(chunks)} chunks "
        f"(~{DEFAULT_CHUNK_TOKENS} tok/chunk, ~{DEFAULT_OVERLAP_TOKENS} overlap)\n"
    )
    for record in sorted(records, key=lambda r: r.title):
        n = sum(1 for c in chunks if c.page_id == record.id)
        print(f"  - {record.title:<48} ~{estimate_tokens(record.text):>4} tok -> {n} chunk(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
