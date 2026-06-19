"""Tests for prompt construction (M2.3-01)."""

from __future__ import annotations

from query.prompt import SYSTEM_PROMPT, build_messages, build_user_message
from query.retrieval import RetrievedChunk


def _chunk(title: str, text: str, sim: float) -> RetrievedChunk:
    return RetrievedChunk(text, sim, title, "p", 0, None, None)


def test_user_message_tags_sources_best_first_without_scores() -> None:
    chunks = [_chunk("A", "alpha", 0.9), _chunk("B", "beta", 0.4)]
    msg = build_user_message("What does Nic do?", chunks)
    assert msg.index('<source title="A">alpha</source>') < msg.index(
        '<source title="B">beta</source>'
    )
    assert msg.endswith("Question: What does Nic do?")
    assert "0.9" not in msg and "0.4" not in msg  # similarity scores never reach the model


def test_build_messages_sends_system_verbatim_single_turn() -> None:
    system, messages = build_messages("Q", [_chunk("A", "alpha", 0.5)])
    assert system == SYSTEM_PROMPT
    assert "third person" in system  # the approved persona rule is present
    assert len(messages) == 1 and messages[0]["role"] == "user"
