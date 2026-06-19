"""Layer 2 — query pipeline orchestration: retrieve -> gate -> decline-or-generate.

Shared by the CLI and the FastAPI route (M2.4). Returns the retrieved sources (None when the gate
declines — a gate decline shows NO sources) plus an iterator of answer tokens.
"""

from __future__ import annotations

from collections.abc import Iterator

from query.gate import DECLINE_MESSAGE, is_relevant
from query.generate import stream_answer
from query.retrieval import RetrievedChunk, retrieve


def run_pipeline(question: str) -> tuple[list[RetrievedChunk] | None, Iterator[str]]:
    """Retrieve + gate; return (sources, token_iter). `sources` is None on a gate decline."""
    results = retrieve(question)
    if not is_relevant(results):
        return None, iter([DECLINE_MESSAGE])
    return results, stream_answer(question, results)
