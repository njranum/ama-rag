"""Layer 1, Stage 1 — enumerate the Portfolio subtree from the Notion API.

Recurses the full subtree under `PORTFOLIO_PARENT_PAGE_ID`, extracting each page's plain text
and metadata (`id`, `title`, `last_edited_time`). The parent page itself is the boundary
container and is not emitted as a record. Output feeds the chunker (M1.4) and provides the
"desired set" of page ids for the mark-and-sweep reconcile (M1.6-02).

Run from the repo root:  python -m ingest.notion_fetch
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from notion_client import Client

import config


@dataclass(frozen=True)
class PageRecord:
    id: str
    title: str
    last_edited_time: str
    text: str


def _rich_text_to_plain(rich: list[dict[str, Any]]) -> str:
    return "".join(seg.get("plain_text", "") for seg in rich)


def _block_text(block: dict[str, Any]) -> str | None:
    """Plain text of a single block if it carries `rich_text`; else None."""
    data = block.get(block["type"], {})
    rich = data.get("rich_text") if isinstance(data, dict) else None
    if isinstance(rich, list) and rich:
        return _rich_text_to_plain(rich)
    return None


def _iter_children(client: Any, block_id: str) -> Iterator[dict[str, Any]]:
    """Yield every child block of a block/page, following pagination."""
    cursor: str | None = None
    while True:
        kwargs: dict[str, object] = {"block_id": block_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.blocks.children.list(**kwargs)
        yield from resp.get("results", [])
        if not resp.get("has_more"):
            return
        cursor = resp.get("next_cursor")


def _walk_blocks(client: Any, block_id: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Collect (text fragments, child-page (id, title) refs) under a block, recursively.

    `child_page` blocks are subtree boundaries: recorded as refs, not descended here for text.
    """
    texts: list[str] = []
    child_pages: list[tuple[str, str]] = []
    for block in _iter_children(client, block_id):
        btype = block["type"]
        if btype == "child_page":
            child_pages.append((block["id"], block["child_page"]["title"]))
            continue
        if btype == "child_database":
            continue
        fragment = _block_text(block)
        if fragment:
            texts.append(fragment)
        if block.get("has_children"):
            sub_texts, sub_children = _walk_blocks(client, block["id"])
            texts.extend(sub_texts)
            child_pages.extend(sub_children)
    return texts, child_pages


def fetch_portfolio_pages(
    parent_page_id: str | None = None, token: str | None = None
) -> list[PageRecord]:
    """Enumerate every page in the Portfolio subtree (excluding the parent container)."""
    parent_page_id = parent_page_id or config.PORTFOLIO_PARENT_PAGE_ID
    token = token or config.NOTION_TOKEN
    if not parent_page_id or not token:
        raise RuntimeError("PORTFOLIO_PARENT_PAGE_ID and NOTION_TOKEN must both be set (.env).")

    client: Any = Client(auth=token)
    _, top_level = _walk_blocks(client, parent_page_id)

    records: list[PageRecord] = []
    seen: set[str] = set()
    stack: list[tuple[str, str]] = list(top_level)
    while stack:
        page_id, title = stack.pop()
        if page_id in seen:
            continue
        seen.add(page_id)
        page = client.pages.retrieve(page_id=page_id)
        texts, child_pages = _walk_blocks(client, page_id)
        records.append(
            PageRecord(
                id=page_id,
                title=title,
                last_edited_time=page["last_edited_time"],
                text="\n\n".join(texts),
            )
        )
        stack.extend(child_pages)
    return records


def main() -> int:
    try:
        records = fetch_portfolio_pages()
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        print(
            "  → if this is a 404/401, share the Notion integration with the Portfolio page "
            "(manual step M0.1).",
            file=sys.stderr,
        )
        return 1

    print(f"Enumerated {len(records)} page(s) under the Portfolio subtree:\n")
    for r in sorted(records, key=lambda rec: rec.title):
        print(f"  - {r.title:<48} {len(r.text):>5} chars   edited {r.last_edited_time}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
