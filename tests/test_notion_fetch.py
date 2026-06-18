"""Network-free unit tests for the Portfolio subtree walker (M1.3-01)."""

from __future__ import annotations

from typing import Any

from ingest.notion_fetch import _block_text, _rich_text_to_plain, _walk_blocks


def _para(text: str, *, block_id: str = "b", has_children: bool = False) -> dict[str, Any]:
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": text}]},
        "id": block_id,
        "has_children": has_children,
    }


class _StubClient:
    """Minimal stand-in for notion_client.Client.blocks.children.list (no pagination)."""

    def __init__(self, children: dict[str, list[dict[str, Any]]]) -> None:
        self._children = children
        self.blocks = self
        self.children = self

    def list(self, *, block_id: str, page_size: int, start_cursor: str | None = None) -> Any:
        return {
            "results": self._children.get(block_id, []),
            "has_more": False,
            "next_cursor": None,
        }


def test_rich_text_to_plain_concatenates_segments() -> None:
    segments = [{"plain_text": "Hello, "}, {"plain_text": "world"}]
    assert _rich_text_to_plain(segments) == "Hello, world"


def test_block_text_returns_none_for_child_page() -> None:
    assert _block_text(_para("hi")) == "hi"
    assert _block_text({"type": "child_page", "child_page": {"title": "Sub"}}) is None


def test_walk_collects_nested_text_and_treats_child_pages_as_boundaries() -> None:
    toggle = {
        "type": "toggle",
        "toggle": {"rich_text": [{"plain_text": "Toggle head"}]},
        "id": "tog",
        "has_children": True,
    }
    child_page = {
        "type": "child_page",
        "child_page": {"title": "Sub"},
        "id": "pageX",
        "has_children": True,
    }
    client = _StubClient(
        {
            "root": [_para("para1", block_id="p1"), toggle, child_page],
            "tog": [_para("inside toggle", block_id="p2")],
        }
    )

    texts, child_pages = _walk_blocks(client, "root")

    assert texts == ["para1", "Toggle head", "inside toggle"]
    # child_page is recorded as a boundary ref, not descended for text here.
    assert child_pages == [("pageX", "Sub")]
