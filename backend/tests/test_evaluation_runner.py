from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.cassette import save_cassette
from ai_platform.evaluation.runner import CaseStale, run_case
from ai_platform.evaluation.scoring import score_case
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.tools.get_unpaid_invoices import GET_UNPAID_INVOICES_TOOL


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GET_CURRENT_DATE_TOOL)
    registry.register(GET_UNPAID_INVOICES_TOOL)
    return registry


def _current_date_case(case_id: str) -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": case_id,
            "category": "current_date",
            "user_message": "What's today's date?",
            "expectations": {
                "expected_tools": [{"tool": "get_current_date", "parameters": {}}],
                "required_facts": ["Tuesday"],
            },
        }
    )


@pytest.mark.asyncio
async def test_run_case_drives_the_real_pipeline_in_recorded_mode(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    case = _current_date_case("current_date_integration")
    save_cassette(
        case.id, 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday, July 14, 2026.",
        cassettes_root=tmp_path,
    )

    outcome = await run_case(
        db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path,
    )
    await db_session.commit()

    assert [tc.tool for tc in outcome.tool_calls] == ["get_current_date"]
    assert outcome.tool_calls[0].parameters == {}
    assert outcome.response_text == "Today is Tuesday, July 14, 2026."
    assert outcome.clarification is None

    score = score_case(case, outcome)
    assert score.passed is True


@pytest.mark.asyncio
async def test_run_case_raises_case_stale_when_cassette_is_missing(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    case = _current_date_case("current_date_no_cassette")

    with pytest.raises(CaseStale, match="current_date_no_cassette"):
        await run_case(db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path)


@pytest.mark.asyncio
async def test_run_case_result_fails_a_deliberately_wrong_expectation(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    """Negative control: proves score_case + run_case together produce a
    genuine failure, not a scorer that's silently always green."""
    case = EvalCase.model_validate(
        {
            "id": "wrong-expectation-case", "category": "current_date",
            "user_message": "What's today's date?",
            "expectations": {
                "expected_tools": [{"tool": "get_unpaid_invoices", "parameters": {}}]
            },
        }
    )
    save_cassette(
        case.id, 0,
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday.",
        cassettes_root=tmp_path,
    )

    outcome = await run_case(
        db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path
    )
    await db_session.commit()

    score = score_case(case, outcome)
    assert score.passed is False
    assert score.metrics["tool_selection_correct"] is False
    assert "get_unpaid_invoices" in (score.failure_reason or "")
    assert "get_current_date" in (score.failure_reason or "")
