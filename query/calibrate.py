"""Layer 2 — Phase-1 threshold calibration (M2.2-02).

Runs the M2.1 retrieval over the eval set (M2.2-01), records each question's top similarity, and
sets the relevance-gate threshold at the BOTTOM of the should-answer range (just below the lowest
should-answer score) — so genuine questions are almost never hard-rejected, while clear garbage is
caught. Also reports overlap (should-refuse leaking past the threshold) and the weak-but-cleared
middle that the prompt-side decline (M2.3-01) must backstop.

The threshold is empirical and content-specific; on the synthetic corpus it is a provisional
working choice, re-locked on real content at M4.2-03. See docs/L2_Query_Pipeline.md (calibration).

Run from the repo root:  python -m query.calibrate
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from pinecone import Pinecone

import config
from ingest.embed_store import get_collection
from query.eval_set import EVAL_SET, EvalQuestion
from query.retrieval import retrieve


@dataclass(frozen=True)
class CalibrationReport:
    lowest_answer: float
    highest_refuse: float
    threshold: float
    clean_gap: bool
    refuse_leaks: int
    margin: float


def calibrate(
    answer_scores: list[float], refuse_scores: list[float], *, margin: float = 0.01
) -> CalibrationReport:
    """Set the threshold just below the lowest should-answer score (the bottom of the gap)."""
    lowest_answer = min(answer_scores)
    highest_refuse = max(refuse_scores)
    threshold = round(lowest_answer - margin, 4)
    return CalibrationReport(
        lowest_answer=lowest_answer,
        highest_refuse=highest_refuse,
        threshold=threshold,
        clean_gap=highest_refuse < lowest_answer,
        refuse_leaks=sum(1 for s in refuse_scores if s >= threshold),
        margin=margin,
    )


def score_questions(
    questions: list[EvalQuestion], *, client: Any, collection: Any
) -> list[tuple[EvalQuestion, float]]:
    scored: list[tuple[EvalQuestion, float]] = []
    for eq in questions:
        chunks = retrieve(eq.question, collection=collection, client=client)
        scored.append((eq, chunks[0].similarity if chunks else float("-inf")))
    return scored


def main() -> int:
    if not config.PINECONE_API_KEY:
        print("PINECONE_API_KEY not set — check .env.", file=sys.stderr)
        return 1
    pc: Any = Pinecone(api_key=config.PINECONE_API_KEY)
    collection: Any = get_collection()

    scored = score_questions(EVAL_SET, client=pc, collection=collection)
    answers = [(eq, s) for eq, s in scored if eq.expect == "answer"]
    refuses = [(eq, s) for eq, s in scored if eq.expect == "refuse"]
    report = calibrate([s for _, s in answers], [s for _, s in refuses])

    print("=== should-answer (low to high) ===")
    for eq, s in sorted(answers, key=lambda r: r[1]):
        print(f"  {s:5.3f}  {eq.question}")
    print("\n=== should-refuse (high to low) ===")
    for eq, s in sorted(refuses, key=lambda r: r[1], reverse=True):
        print(f"  {s:5.3f}  {eq.question}")

    print("\n=== calibration ===")
    print(f"lowest should-answer : {report.lowest_answer:.3f}")
    print(f"highest should-refuse: {report.highest_refuse:.3f}")
    print(f"clean gap?           : {report.clean_gap}")
    print(f"recommended threshold: {report.threshold:.3f}  (lowest_answer - {report.margin})")
    print(f"should-refuse leaking past threshold: {report.refuse_leaks}")

    weak = [(eq, s) for eq, s in answers if s < report.highest_refuse]
    print(f"\nweak-but-cleared (should-answer below the worst off-topic score): {len(weak)}")
    for eq, s in sorted(weak, key=lambda r: r[1]):
        print(f"  {s:5.3f}  {eq.question}")
    print("\n  -> the prompt-side decline (M2.3-01) backstops these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
