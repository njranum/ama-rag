"""Unit tests for query.pipeline.resolve_sources — prompt-side decline suppresses sources."""

from __future__ import annotations

from query import pipeline
from query.gate import DECLINE_MESSAGE
from query.retrieval import RetrievedChunk

_SOURCE = RetrievedChunk("alpha text", 0.9, "A", "p1", 0, None, None)


def test_gate_decline_passes_through_sourceless() -> None:
    sources, tokens = pipeline.resolve_sources(None, iter([DECLINE_MESSAGE]))
    assert sources is None
    assert "".join(tokens) == DECLINE_MESSAGE


def test_prompt_side_decline_drops_sources() -> None:
    # Gate passed (sources present) but the model streams exactly the canned decline, token-split.
    tokens = iter(["Sorry, I don't ", "have information ", "about that."])
    sources, out = pipeline.resolve_sources([_SOURCE], tokens)
    assert sources is None
    assert "".join(out) == DECLINE_MESSAGE


def test_real_answer_keeps_sources_and_replays_all_tokens() -> None:
    tokens = iter(["Nic ", "works ", "at Acme."])
    sources, out = pipeline.resolve_sources([_SOURCE], tokens)
    assert sources == [_SOURCE]
    assert "".join(out) == "Nic works at Acme."


def test_answer_that_starts_like_the_decline_keeps_sources() -> None:
    # Shares a prefix ("Sorry, I don't ") then diverges — a real answer, so sources stay.
    tokens = iter(["Sorry, I don't ", "think that's right — Nic uses AWS."])
    sources, out = pipeline.resolve_sources([_SOURCE], tokens)
    assert sources == [_SOURCE]
    assert "".join(out) == "Sorry, I don't think that's right — Nic uses AWS."


def test_decline_with_trailing_answer_keeps_sources() -> None:
    # Exact decline text but the model kept going — no longer a bare decline, so sources stay.
    tokens = iter([DECLINE_MESSAGE, " However, Nic knows Python."])
    sources, out = pipeline.resolve_sources([_SOURCE], tokens)
    assert sources == [_SOURCE]
    assert "".join(out) == DECLINE_MESSAGE + " However, Nic knows Python."
