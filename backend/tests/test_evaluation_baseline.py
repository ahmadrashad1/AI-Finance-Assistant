from __future__ import annotations

from ai_platform.evaluation.run import compare_to_baseline


def test_identical_results_have_no_drift() -> None:
    baseline = {"case_a": True, "case_b": False}
    current = {"case_a": True, "case_b": False}
    assert compare_to_baseline(current, baseline) == []


def test_detects_a_regression() -> None:
    baseline = {"case_a": True, "case_b": False}
    current = {"case_a": False, "case_b": False}
    drift = compare_to_baseline(current, baseline)
    assert len(drift) == 1
    assert "case_a" in drift[0]
    assert "REGRESSION" in drift[0]


def test_detects_an_unexpected_improvement() -> None:
    baseline = {"case_a": True, "case_b": False}
    current = {"case_a": True, "case_b": True}
    drift = compare_to_baseline(current, baseline)
    assert len(drift) == 1
    assert "case_b" in drift[0]
    assert "unexpected improvement" in drift[0]


def test_detects_a_case_missing_from_the_current_run() -> None:
    baseline = {"case_a": True, "case_b": False}
    current = {"case_a": True}
    drift = compare_to_baseline(current, baseline)
    assert len(drift) == 1
    assert "case_b" in drift[0]
    assert "missing from this run" in drift[0]


def test_flags_a_case_not_in_the_baseline() -> None:
    baseline = {"case_a": True}
    current = {"case_a": True, "case_c": True}
    drift = compare_to_baseline(current, baseline)
    assert len(drift) == 1
    assert "case_c" in drift[0]
    assert "not in baseline" in drift[0]
