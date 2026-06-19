"""Layer 2 — Phase-1 query CLI (M2.1).

Usage:  python -m query.cli "Your question here"

Embeds the question, retrieves top-k chunks from Chroma, applies the relevance gate, and prints
either the canned decline (gate failed — no LLM call) or the ranked source chunks. This is Stages
1-2 of the online pipeline, proven on the terminal before the FastAPI/SSE layer (M2.4).
"""

from __future__ import annotations

import sys

import config
from query.gate import DECLINE_MESSAGE, is_relevant
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
    for i, r in enumerate(results, 1):
        snippet = " ".join(r.text.split())[:160]
        print(f"{i}. {r.title}  (sim={r.similarity:.3f}, chunk {r.chunk_position})")
        print(f"   {snippet}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
