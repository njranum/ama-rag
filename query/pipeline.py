"""Layer 2 — query pipeline orchestration: retrieve -> gate -> decline-or-generate.

Shared by the CLI and the FastAPI route (M2.4). Returns the retrieved sources (None when the gate
declines — a gate decline shows NO sources) plus an iterator of answer tokens.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import chain

from query.gate import DECLINE_MESSAGE, is_relevant
from query.generate import stream_answer
from query.retrieval import RetrievedChunk, retrieve


def run_pipeline(question: str) -> tuple[list[RetrievedChunk] | None, Iterator[str]]:
    """Retrieve + gate; return (sources, token_iter). `sources` is None on a gate decline."""
    results = retrieve(question)
    if not is_relevant(results):
        return None, iter([DECLINE_MESSAGE])
    return results, stream_answer(question, results)


def resolve_sources(
    sources: list[RetrievedChunk] | None,
    tokens: Iterator[str],
    *,
    decline_message: str = DECLINE_MESSAGE,
) -> tuple[list[RetrievedChunk] | None, Iterator[str]]:
    """Suppress sources on a *prompt-side* decline so it looks like a gate decline to the widget.

    The gate declines with `sources=None` up front, but the gate can pass (sources retrieved) while
    the model still declines to answer from them. Because the SSE contract streams `sources` before
    the answer, we can't know that in advance — so we peek the token stream just far enough to tell
    a real answer from the canned decline: as soon as the accumulated text stops being a prefix of
    `decline_message` it's a real answer (sources kept, peeked tokens replayed with no delay); if
    the stream ends having produced exactly the decline, we drop the sources. Only the exact canned
    wording is suppressed — anything else keeps its sources.
    """
    if sources is None:
        return None, tokens  # gate decline — already sourceless

    peeked: list[str] = []
    buffer = ""
    for token in tokens:
        peeked.append(token)
        buffer += token
        if not decline_message.startswith(buffer):
            return sources, chain(peeked, tokens)  # diverged — a real, grounded answer
    # Stream exhausted: sources stay only if the whole answer wasn't the decline.
    return (None if buffer == decline_message else sources), iter(peeked)
