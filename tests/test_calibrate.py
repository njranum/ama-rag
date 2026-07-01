"""Tests for threshold calibration (M2.2-02) and eval-set shape (M2.2-01)."""

from __future__ import annotations

from collections import Counter

from query.calibrate import calibrate
from query.eval_set import EVAL_SET


def test_clean_gap_sets_threshold_below_lowest_answer() -> None:
    # gap measured against OFF-TOPIC only (2nd arg); about-Nic (3rd arg) may sit high without
    # breaking the gap — that's the decline's job, not the gate's.
    report = calibrate([0.5, 0.6, 0.45], [0.1, 0.2], [0.44], margin=0.01)
    assert report.clean_gap is True  # highest off-topic 0.2 < lowest answer 0.45
    assert report.threshold == 0.44  # 0.45 - 0.01
    assert report.offtopic_leaks == 0
    assert report.about_nic_leaks == 1  # 0.44 >= 0.44 — expected, backstopped by the decline


def test_offtopic_leak_breaks_the_gap_and_is_counted() -> None:
    # a genuine 0.19 sits below off-topic 0.21 -> no clean gap; the off-topic leaks past threshold
    report = calibrate([0.19, 0.5, 0.32], [0.12, 0.21], [], margin=0.01)
    assert report.clean_gap is False
    assert report.threshold == 0.18
    assert report.offtopic_leaks == 1  # 0.21 >= 0.18 — a real gate failure


def test_eval_set_categorises_refuses_and_keeps_an_injection_case() -> None:
    counts = Counter(eq.expect for eq in EVAL_SET)
    assert counts["answer"] >= 12
    assert counts["refuse"] >= 12
    # every refuse carries its owner (gate vs decline); answers carry none.
    assert all(eq.kind in ("offtopic", "about_nic") for eq in EVAL_SET if eq.expect == "refuse")
    assert all(eq.kind is None for eq in EVAL_SET if eq.expect == "answer")
    offtopic_text = " ".join(eq.question.lower() for eq in EVAL_SET if eq.kind == "offtopic")
    assert "ignore" in offtopic_text or "disregard" in offtopic_text
