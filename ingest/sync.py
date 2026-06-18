"""Layer 1 — incremental sync + mark-and-sweep reconcile (M1.6).

One sync run, in order:
  1. Mark-and-sweep (M1.6-02): delete chunks of any stored page no longer in the Portfolio
     subtree (moved out / deleted) — closes the removal hole in the curation boundary.
  2. Incremental embed (M1.6-01): for pages whose last_edited_time changed (or are new),
     delete-before-upsert their chunks; skip unchanged pages (no re-embed).

The store is its own sync state — last_edited_time is read back from chunk metadata, so no
separate timestamp file is needed (matters for the stateless Phase-3 Lambda). See
docs/L1_Ingestion.md (Sync strategy).

Run from the repo root:  python -m ingest.sync
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import config
from ingest.chunker import chunk_page
from ingest.embed_store import (
    delete_page,
    embed_chunks,
    get_collection,
    store_chunks,
    stored_page_state,
)
from ingest.notion_fetch import PageRecord, fetch_portfolio_pages

# Embeds a batch of chunks -> one vector each. Default hits Pinecone; tests inject a fake.
EmbedFn = Callable[..., list[list[float]]]


@dataclass
class SyncReport:
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"removed {len(self.removed)}, changed {len(self.changed)}, skipped {len(self.skipped)}"
        )


def reconcile_and_sync(
    records: list[PageRecord], *, collection: Any, embed_fn: EmbedFn = embed_chunks
) -> SyncReport:
    """Sweep removed pages, then incrementally embed new/changed pages (skip unchanged)."""
    desired_ids = {r.id for r in records}
    stored = stored_page_state(collection)
    report = SyncReport()

    # 1. Mark-and-sweep: drop pages no longer in the desired set (M1.6-02).
    for page_id in stored:
        if page_id not in desired_ids:
            delete_page(collection, page_id)
            report.removed.append(page_id)

    # 2. Incremental embed for new/changed pages; skip unchanged (M1.6-01).
    for record in records:
        if stored.get(record.id) == record.last_edited_time:
            report.skipped.append(record.id)
            continue
        if record.id in stored:
            delete_page(collection, record.id)  # delete-before-upsert: no orphaned tail chunks
        chunks = chunk_page(record)
        if chunks:
            store_chunks(chunks, embed_fn(chunks), collection=collection)
        report.changed.append(record.id)

    return report


def main() -> int:
    try:
        records = fetch_portfolio_pages()
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    collection = get_collection()
    before = collection.count()
    report = reconcile_and_sync(records, collection=collection)
    print(
        f"sync: {report.summary()} | "
        f"Chroma {config.CHROMA_COLLECTION!r} count {before} -> {collection.count()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
