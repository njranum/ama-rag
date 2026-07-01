"""Layer 2 — Phase-1 threshold calibration (M2.2-02).

Runs the M2.1 retrieval over the eval set (M2.2-01), records each question's top similarity, and
sets the relevance-gate threshold at the BOTTOM of the should-answer range (just below the lowest
should-answer score) — so genuine questions are almost never hard-rejected, while clear garbage is
caught.

The gate is measured against the `offtopic` refuses ONLY — those are the gate's job. The `about_nic`
refuses (about Nic but not in the corpus) retrieve his pages with real similarity and are *meant* to
clear the gate; the prompt-side decline (M2.3-01) backstops them. A clean gap therefore means
"highest off-topic score < lowest should-answer score", NOT "highest of all refuses" — mixing the
about-Nic cluster in makes a clean gap impossible on real content and hides the real signal.

The threshold is empirical and content-specific; on the synthetic corpus it was a provisional
working choice, re-locked on real content at M4.2-03 and re-lowered 2026-07-01 (casual phrasings).
See docs/L2_Query_Pipeline.md (calibration).

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
    highest_offtopic: float
    threshold: float
    clean_gap: bool
    offtopic_leaks: int
    about_nic_leaks: int
    margin: float


def calibrate(
    answer_scores: list[float],
    offtopic_scores: list[float],
    about_nic_scores: list[float],
    *,
    margin: float = 0.01,
) -> CalibrationReport:
    """Threshold just below the lowest should-answer score; gap measured against off-topic only.

    `offtopic_leaks` (off-topic clearing the gate) is the real failure signal and should be 0.
    `about_nic_leaks` is expected and non-zero — those clear the gate by design and are refused by
    the prompt-side decline (M2.3-01).
    """
    lowest_answer = min(answer_scores)
    highest_offtopic = max(offtopic_scores)
    threshold = round(lowest_answer - margin, 4)
    return CalibrationReport(
        lowest_answer=lowest_answer,
        highest_offtopic=highest_offtopic,
        threshold=threshold,
        clean_gap=highest_offtopic < lowest_answer,
        offtopic_leaks=sum(1 for s in offtopic_scores if s >= threshold),
        about_nic_leaks=sum(1 for s in about_nic_scores if s >= threshold),
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
    offtopic = [(eq, s) for eq, s in scored if eq.kind == "offtopic"]
    about_nic = [(eq, s) for eq, s in scored if eq.kind == "about_nic"]
    report = calibrate(
        [s for _, s in answers],
        [s for _, s in offtopic],
        [s for _, s in about_nic],
    )

    print("=== should-answer (low to high) ===")
    for eq, s in sorted(answers, key=lambda r: r[1]):
        print(f"  {s:5.3f}  {eq.question}")
    print("\n=== should-refuse · off-topic / injection (gate's job — high to low) ===")
    for eq, s in sorted(offtopic, key=lambda r: r[1], reverse=True):
        print(f"  {s:5.3f}  {eq.question}")
    print("\n=== should-refuse · about-Nic-but-unanswerable (decline's job — high to low) ===")
    for eq, s in sorted(about_nic, key=lambda r: r[1], reverse=True):
        print(f"  {s:5.3f}  {eq.question}")

    print("\n=== calibration ===")
    print(f"lowest should-answer     : {report.lowest_answer:.3f}")
    print(f"highest off-topic        : {report.highest_offtopic:.3f}")
    print(f"clean gap (vs off-topic)?: {report.clean_gap}")
    print(f"recommended threshold    : {report.threshold:.3f}  (lowest_answer - {report.margin})")
    print(f"off-topic leaking gate   : {report.offtopic_leaks}  (must be 0 — real failure signal)")
    print(f"about-Nic clearing gate  : {report.about_nic_leaks}  (expected — decline backstops)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
