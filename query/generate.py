"""Layer 2, Stage 4 — generation (M2.3-02).

Sends the assembled prompt to Claude Haiku 4.5 via the Anthropic Messages API, streamed
token-by-token at low temperature with a capped output. Any error (timeout, API failure) is caught
and surfaced as a graceful, widget-facing fallback string — never a raw traceback. In Phase 1 the
CLI just prints the streamed tokens; the SSE relay comes in M2.4-02.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Any

import anthropic

import config
from query.prompt import build_messages
from query.retrieval import RetrievedChunk

# Widget-facing fallback on any generation error (becomes the SSE `error` event in M2.4-02).
FALLBACK_MESSAGE = "Sorry, something went wrong generating an answer. Please try again."


def stream_answer(
    question: str, chunks: list[RetrievedChunk], *, client: Any = None
) -> Iterator[str]:
    """Yield the grounded answer token-by-token; on any error, yield the fallback (keep-partial)."""
    system, messages = build_messages(question, chunks)
    api: Any = client or anthropic.Anthropic(
        api_key=config.ANTHROPIC_API_KEY, timeout=config.GEN_TIMEOUT_S
    )
    streamed = False
    try:
        with api.messages.stream(
            model=config.GEN_MODEL,
            max_tokens=config.GEN_MAX_TOKENS,
            temperature=config.GEN_TEMPERATURE,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                streamed = True
                yield text
    except Exception as exc:  # never surface a raw trace to the widget
        print(f"generation failed: {exc}", file=sys.stderr)
        # If nothing streamed, the fallback is the whole answer; mid-stream, append after a break.
        yield ("\n\n" if streamed else "") + FALLBACK_MESSAGE
