"""Layer 2 — Phase-1 query CLI (M2.1).

Usage:  python -m query.cli "Your question here"

Embeds the question, retrieves top-k chunks from Chroma, applies the relevance gate, and prints
either the canned decline (gate failed — no LLM call) or a streamed, grounded answer from Claude
Haiku 4.5 (gate passed). Stages 1-4 of the online pipeline, proven on the terminal before M2.4.
"""

from __future__ import annotations

import sys

import config
from query.gate import DECLINE_MESSAGE, is_relevant
from query.generate import stream_answer
from query.retrieval import retrieve


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print('usage: python -m query.cli "your question"', file=sys.stderr)
        return 2
    question = " ".join(args)

    try:
        results = retrieve(question)
    except Exception as exc:
        print(f"retrieval failed: {exc}", file=sys.stderr)
        return 1

    if not is_relevant(results):
        top = results[0].similarity if results else float("nan")
        reason = f"top sim {top:.3f} < {config.RELEVANCE_THRESHOLD}"
        print(f"[relevance gate tripped: {reason}] — no LLM call", file=sys.stderr)
        print(DECLINE_MESSAGE)
        return 0

    print(f"Q: {question}\n")
    for token in stream_answer(question, results):
        print(token, end="", flush=True)
    print("\n\nsources:")
    for r in results:
        print(f"  - {r.title}  (sim={r.similarity:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
