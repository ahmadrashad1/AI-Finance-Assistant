from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.repository import EvaluationRepository


@pytest.mark.asyncio
async def test_upsert_case_creates_then_updates(clean_db: None, db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    created = await repo.upsert_case(
        case_id="case-1", category="unpaid_invoices", suite="core",
        definition={"user_message": "Show unpaid invoices"},
    )
    await db_session.commit()

    updated = await repo.upsert_case(
        case_id="case-1", category="unpaid_invoices", suite="core",
        definition={"user_message": "Show me unpaid invoices please"},
    )
    await db_session.commit()

    assert updated.id == created.id
    assert updated.definition == {"user_message": "Show me unpaid invoices please"}


@pytest.mark.asyncio
async def test_create_run_defaults_to_zero_totals(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = EvaluationRepository(db_session)
    run = await repo.create_run(
        suite="core", mode="recorded",
        planning_prompt_version="1.3.0", system_prompt_version="1.4.0",
    )
    await db_session.commit()

    assert run.total_cases == 0
    assert run.passed_cases == 0
    assert run.overall_score == Decimal("0")
    assert run.finished_at is None


@pytest.mark.asyncio
async def test_record_result_and_finish_run(clean_db: None, db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    case = await repo.upsert_case(
        case_id="case-2", category="hallucination", suite="core", definition={},
    )
    run = await repo.create_run(
        suite="core", mode="recorded",
        planning_prompt_version="1.3.0", system_prompt_version="1.4.0",
    )
    await db_session.commit()

    result = await repo.record_result(
        run_id=run.id, case_id=case.id,
        expected={"expected_tools": [{"tool": "search_invoices", "parameters": {}}]},
        actual={"tool_calls": [{"tool": "search_invoices", "parameters": {}}]},
        passed=True, score=1.0,
        metrics={"tool_selection_correct": True},
        failure_reason=None,
    )
    await repo.finish_run(
        run_id=run.id, total_cases=1, passed_cases=1,
        overall_score=Decimal("1.0000"),
        metrics={"tool_selection_accuracy": 1.0},
    )
    await db_session.commit()

    assert result.passed is True
    assert result.score == Decimal("1.0000")

    refreshed = await db_session.get(type(run), run.id)
    assert refreshed is not None
    assert refreshed.total_cases == 1
    assert refreshed.passed_cases == 1
    assert refreshed.finished_at is not None


@pytest.mark.asyncio
async def test_finish_run_raises_for_unknown_run_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = EvaluationRepository(db_session)
    with pytest.raises(ValueError, match="does not exist"):
        await repo.finish_run(
            run_id=uuid.uuid4(), total_cases=0, passed_cases=0,
            overall_score=Decimal("0"), metrics={},
        )
