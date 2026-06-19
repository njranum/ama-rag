"""Tests for the hybrid relevance gate (M2.1-02)."""

from __future__ import annotations

from query.gate import DECLINE_MESSAGE, is_relevant
from query.retrieval import RetrievedChunk


def _chunk(similarity: float) -> RetrievedChunk:
    return RetrievedChunk("text", similarity, "Title", "p1", 0, None, None)


def test_empty_results_are_not_relevant() -> None:
    assert is_relevant([]) is False


def test_above_threshold_passes() -> None:
    assert is_relevant([_chunk(0.9)], threshold=0.5) is True


def test_below_threshold_declines() -> None:
    assert is_relevant([_chunk(0.1)], threshold=0.5) is False


def test_threshold_boundary_is_inclusive() -> None:
    assert is_relevant([_chunk(0.5)], threshold=0.5) is True


def test_decline_wording_is_exact() -> None:
    assert DECLINE_MESSAGE == "Sorry, I don't have information about that."
