"""Network-free tests for query retrieval (M2.1-01): score normalisation + nullable metadata.

Also covers the Pinecone store path + its parity with Chroma (M4.2-01).
"""

from __future__ import annotations

from typing import Any

import pytest

import config
from query.retrieval import retrieve


class _Emb:
    def __init__(self, values: list[float]) -> None:
        self.values = values


class _Inference:
    def embed(self, **_: Any) -> list[_Emb]:
        return [_Emb([0.1, 0.2, 0.3, 0.4])]


class _StubPC:
    def __init__(self) -> None:
        self.inference = _Inference()


class _StubCollection:
    def query(self, **_: Any) -> dict[str, Any]:
        return {
            "documents": [["doc A", "doc B"]],
            "metadatas": [
                [
                    {"title": "A", "page_id": "p1", "chunk_position": 0, "url": "", "anchor": ""},
                    {
                        "title": "B",
                        "page_id": "p2",
                        "chunk_position": 1,
                        "url": "https://x",
                        "anchor": "",
                    },
                ]
            ],
            "distances": [[0.2, 0.6]],
        }


def test_distance_is_normalised_to_cosine_similarity() -> None:
    results = retrieve("q", collection=_StubCollection(), client=_StubPC())
    assert [round(r.similarity, 3) for r in results] == [0.8, 0.4]  # 1 - distance


def test_empty_string_metadata_reads_back_as_none() -> None:
    results = retrieve("q", collection=_StubCollection(), client=_StubPC())
    assert results[0].url is None and results[0].anchor is None
    assert results[1].url == "https://x"


def test_metadata_carried_through() -> None:
    results = retrieve("q", collection=_StubCollection(), client=_StubPC())
    assert results[0].title == "A" and results[0].page_id == "p1"
    assert results[0].chunk_position == 0


# --- Pinecone store path (M4.2-01) ----------------------------------------------------


class _StubIndex:
    """Mirrors a Pinecone query response: matches carry .score + .metadata (text rides in meta)."""

    def query(self, **_: Any) -> dict[str, Any]:
        return {
            "matches": [
                {
                    "score": 0.83,
                    "metadata": {
                        "text": "doc A",
                        "title": "A",
                        "page_id": "p1",
                        "chunk_position": 0,
                        "url": "",
                        "anchor": "",
                    },
                },
                {
                    "score": 0.41,
                    "metadata": {
                        "text": "doc B",
                        "title": "B",
                        "page_id": "p2",
                        "chunk_position": 1,
                        "url": "https://x",
                        "anchor": "",
                    },
                },
            ]
        }


def test_pinecone_score_used_directly_as_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pinecone cosine metric already returns similarity (higher=better) — NOT a distance to invert.
    monkeypatch.setattr(config, "VECTOR_STORE", "pinecone")
    results = retrieve("q", index=_StubIndex(), client=_StubPC())
    assert [round(r.similarity, 3) for r in results] == [0.83, 0.41]


def test_pinecone_text_from_metadata_and_nullable_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "VECTOR_STORE", "pinecone")
    results = retrieve("q", index=_StubIndex(), client=_StubPC())
    assert results[0].text == "doc A"  # Pinecone carries chunk text in metadata
    assert results[0].url is None and results[0].anchor is None  # "" reads back as None
    assert results[1].url == "https://x"
    assert results[0].title == "A" and results[0].page_id == "p1" and results[0].chunk_position == 0
