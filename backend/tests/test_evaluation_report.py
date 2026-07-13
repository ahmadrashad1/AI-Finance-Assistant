from __future__ import annotations

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.report import render_scorecard
from ai_platform.evaluation.scoring import CaseScore


def _case(case_id: str, category: str) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": case_id, "category": category, "user_message": "x",
            "expectations": {"expected_tools": [{"tool": "get_current_date", "parameters": {}}]},
        }
    )


def _score(passed: bool, reason: str | None = None) -> CaseScore:
    return CaseScore(
        passed=passed, score=1.0 if passed else 0.0,
        metrics={
            "tool_selection_correct": passed, "parameters_correct": True,
            "clarification_correct": True, "hallucinated": False,
            "required_facts_present": True,
        },
        parameter_pairs_matched=0, parameter_pairs_total=0, failure_reason=reason,
    )


def test_scorecard_includes_suite_mode_categories_and_totals() -> None:
    cases = [_case("case-1", "unpaid_invoices"), _case("case-2", "unpaid_invoices")]
    scores = [_score(True), _score(False, "expected get_current_date, got get_unpaid_invoices")]
    metrics = {
        "tool_selection_accuracy": 0.5, "parameter_accuracy": 1.0,
        "memory_usage_accuracy": 1.0, "hallucination_rate": 0.0,
    }

    report = render_scorecard(
        suite="core", mode="recorded", cases=cases, scores=scores, metrics=metrics,
        stale_case_ids=[],
    )

    assert "core" in report
    assert "recorded" in report
    assert "unpaid_invoices" in report
    assert "case-1" in report and "PASS" in report
    assert "case-2" in report and "FAIL" in report
    assert "expected get_current_date, got get_unpaid_invoices" in report
    assert "1/2 passed" in report
    assert "Tool-selection accuracy: 50.0%" in report


def test_scorecard_lists_stale_cases() -> None:
    report = render_scorecard(
        suite="core", mode="recorded", cases=[], scores=[],
        metrics={
            "tool_selection_accuracy": 1.0, "parameter_accuracy": 1.0,
            "memory_usage_accuracy": 1.0, "hallucination_rate": 0.0,
        },
        stale_case_ids=["current_date_basic"],
    )
    assert "STALE" in report
    assert "current_date_basic" in report
    assert "--record" in report


def test_scorecard_with_no_stale_cases_omits_the_stale_section() -> None:
    report = render_scorecard(
        suite="core", mode="recorded", cases=[], scores=[],
        metrics={
            "tool_selection_accuracy": 1.0, "parameter_accuracy": 1.0,
            "memory_usage_accuracy": 1.0, "hallucination_rate": 0.0,
        },
        stale_case_ids=[],
    )
    assert "STALE" not in report
