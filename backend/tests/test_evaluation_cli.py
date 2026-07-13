from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.cassette import save_cassette
from ai_platform.evaluation.models import EvaluationResultModel, EvaluationRunModel
from ai_platform.evaluation.run import run_suite
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL


def _write_suite(evals_root: Path, suite: str, case_id: str) -> None:
    suite_dir = evals_root / suite
    suite_dir.mkdir(parents=True)
    (suite_dir / f"{case_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": case_id, "category": "current_date", "user_message": "What's today's date?",
                "expectations": {
                    "expected_tools": [{"tool": "get_current_date", "parameters": {}}]
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_run_suite_passes_persists_results_and_reports_pass(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    evals_root = tmp_path / "evals"
    cassettes_root = tmp_path / "cassettes"
    _write_suite(evals_root, "smoke", "current_date_cli_case")
    save_cassette(
        "current_date_cli_case", 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
        cassettes_root=cassettes_root,
    )

    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)

    report, all_passed = await run_suite(
        suite="smoke", mode="recorded", record=False, case_filter=None,
        registry=registry, real_llm_service=None,
        evals_root=evals_root, cassettes_root=cassettes_root,
    )

    assert all_passed is True
    assert "PASS" in report
    assert "current_date_cli_case" in report
    assert "Total: 1/1 passed" in report

    runs = (await db_session.execute(select(EvaluationRunModel))).scalars().all()
    assert len(runs) == 1
    assert runs[0].total_cases == 1
    assert runs[0].passed_cases == 1

    results = (await db_session.execute(select(EvaluationResultModel))).scalars().all()
    assert len(results) == 1
    assert results[0].passed is True


@pytest.mark.asyncio
async def test_run_suite_reports_failure_when_cassette_is_stale(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    evals_root = tmp_path / "evals"
    cassettes_root = tmp_path / "cassettes"
    _write_suite(evals_root, "smoke", "current_date_stale_case")
    # deliberately no cassette written

    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)

    report, all_passed = await run_suite(
        suite="smoke", mode="recorded", record=False, case_filter=None,
        registry=registry, real_llm_service=None,
        evals_root=evals_root, cassettes_root=cassettes_root,
    )

    assert all_passed is False
    assert "STALE" in report
    assert "current_date_stale_case" in report


@pytest.mark.asyncio
async def test_run_suite_recovers_from_unhandled_exception_in_one_case(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    """A case whose run_case call raises an unhandled exception (e.g. AIError from
    Planner.create_plan on malformed model output) must be recorded as a failed case
    and must not crash the rest of the suite - this is the Task 21 regression: one
    case's malformed-JSON cassette used to propagate out of run_suite and kill the
    entire run instead of being scored as a single failure.
    """
    evals_root = tmp_path / "evals"
    cassettes_root = tmp_path / "cassettes"
    suite_dir = evals_root / "smoke"

    # Case 1: a healthy case that must still run and pass despite case 2's failure.
    # `_write_suite` creates the suite directory.
    _write_suite(evals_root, "smoke", "current_date_cli_case")
    save_cassette(
        "current_date_cli_case", 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
        cassettes_root=cassettes_root,
    )

    # Case 2: malformed plan_response - Planner.create_plan will raise AIError
    # when json.loads() fails on it, exactly like the real bug.
    (suite_dir / "malformed_json_case.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "malformed_json_case", "category": "current_date",
                "user_message": "What's today's date?",
                "expectations": {
                    "expected_tools": [{"tool": "get_current_date", "parameters": {}}]
                },
            }
        ),
        encoding="utf-8",
    )
    save_cassette(
        "malformed_json_case", 0,
        plan_response="not valid json {",
        response_text="Today is Tuesday.",
        cassettes_root=cassettes_root,
    )

    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)

    report, all_passed = await run_suite(
        suite="smoke", mode="recorded", record=False, case_filter=None,
        registry=registry, real_llm_service=None,
        evals_root=evals_root, cassettes_root=cassettes_root,
    )

    assert all_passed is False
    assert "FAIL" in report
    assert "malformed_json_case" in report
    assert "unhandled exception" in report
    assert "PASS" in report
    assert "current_date_cli_case" in report
    assert "Total: 1/2 passed" in report

    runs = (await db_session.execute(select(EvaluationRunModel))).scalars().all()
    assert len(runs) == 1
    assert runs[0].total_cases == 2
    assert runs[0].passed_cases == 1

    results = (await db_session.execute(select(EvaluationResultModel))).scalars().all()
    assert len(results) == 2
    results_by_passed = {r.passed: r for r in results}
    failed_result = results_by_passed[False]
    assert failed_result.failure_reason is not None
    assert "unhandled exception" in failed_result.failure_reason
    assert results_by_passed[True].passed is True


@pytest.mark.asyncio
async def test_run_suite_case_filter_runs_only_that_case(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    evals_root = tmp_path / "evals"
    cassettes_root = tmp_path / "cassettes"
    _write_suite(evals_root, "smoke", "current_date_cli_case")
    save_cassette(
        "current_date_cli_case", 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
        cassettes_root=cassettes_root,
    )

    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)

    with pytest.raises(ValueError, match="No case 'missing-case'"):
        await run_suite(
            suite="smoke", mode="recorded", record=False, case_filter="missing-case",
            registry=registry, real_llm_service=None,
            evals_root=evals_root, cassettes_root=cassettes_root,
        )
