"""Tests for threshold calibration (M2.2-02) and eval-set shape (M2.2-01)."""

from __future__ import annotations

from collections import Counter

from query.calibrate import calibrate
from query.eval_set import EVAL_SET


def test_clean_gap_sets_threshold_below_lowest_answer() -> None:
    report = calibrate([0.5, 0.6, 0.45], [0.1, 0.2], margin=0.01)
    assert report.clean_gap is True
    assert report.threshold == 0.44  # 0.45 - 0.01
    assert report.refuse_leaks == 0


def test_overlap_is_detected_and_refuse_leaks_counted() -> None:
    # genuine 0.19 sits below off-topic 0.21 -> no clean gap; the off-topic leaks past the threshold
    report = calibrate([0.19, 0.5, 0.32], [0.12, 0.21], margin=0.01)
    assert report.clean_gap is False
    assert report.threshold == 0.18
    assert report.refuse_leaks == 1  # 0.21 >= 0.18


def test_eval_set_has_balanced_coverage_and_an_injection_case() -> None:
    counts = Counter(eq.expect for eq in EVAL_SET)
    assert counts["answer"] >= 12
    assert counts["refuse"] >= 12
    refuse_text = " ".join(eq.question.lower() for eq in EVAL_SET if eq.expect == "refuse")
    assert "ignore" in refuse_text or "disregard" in refuse_text
