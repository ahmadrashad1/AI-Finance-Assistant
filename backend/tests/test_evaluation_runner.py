from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.evaluation.case_schema import EvalCase
from ai_platform.evaluation.cassette import load_cassette, save_cassette
from ai_platform.evaluation.runner import CaseStale, run_case
from ai_platform.evaluation.scoring import score_case
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.tools.get_current_date import GET_CURRENT_DATE_TOOL
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
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


def _followup_registry() -> ToolRegistry:
    registry = _registry()
    registry.register(GET_CUSTOMER_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    return registry


class _FakeRealLLMService:
    def __init__(self, plan_response: str, response_text: str) -> None:
        self._plan_response = plan_response
        self._response_text = response_text

    async def complete(self, system: str, history: list[dict[str, str]], message: str) -> str:
        return self._plan_response

    async def stream_reply(self, system: str, history: list[dict[str, str]], message: str):
        yield self._response_text


@pytest.mark.asyncio
async def test_run_case_live_mode_with_record_writes_a_replayable_cassette(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    case = _current_date_case("current_date_record_roundtrip")
    fake_real_service = _FakeRealLLMService(
        plan_response='{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}',
        response_text="Today is Tuesday, July 14, 2026.",
    )

    live_outcome = await run_case(
        db_session, _registry(), case, mode="live", record=True,
        real_llm_service=fake_real_service, cassettes_root=tmp_path,
    )
    await db_session.commit()

    assert [tc.tool for tc in live_outcome.tool_calls] == ["get_current_date"]

    cassette = load_cassette(case.id, 0, cassettes_root=tmp_path)
    assert cassette is not None
    expected_plan = '{"tool_calls": [{"tool": "get_current_date", "parameters": {}}]}'
    assert cassette["plan_response"] == expected_plan
    assert cassette["response_text"] == "Today is Tuesday, July 14, 2026."

    replayed_outcome = await run_case(
        db_session, _registry(), case, mode="recorded", cassettes_root=tmp_path,
    )
    await db_session.commit()
    assert replayed_outcome.response_text == live_outcome.response_text
    replayed_tools = [tc.tool for tc in replayed_outcome.tool_calls]
    live_tools = [tc.tool for tc in live_outcome.tool_calls]
    assert replayed_tools == live_tools


@pytest.mark.asyncio
async def test_run_case_replays_a_two_turn_piped_follow_up_case(
    clean_db: None, db_session: AsyncSession, tmp_path: Path
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-9001", company_name="Anchor Components", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-9001", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("6534.00"), tax=Decimal("0"), total=Decimal("6534.00"),
    )
    await db_session.commit()

    case = EvalCase.model_validate(
        {
            "id": "followup_replay_test", "category": "follow_up", "tests_memory": True,
            "conversation_setup": [{"user_message": "Show overdue invoices"}],
            "user_message": "Which of those belong to Anchor Components?",
            "expectations": {
                "expected_tools": [
                    {"tool": "get_customer", "parameters": {"customer_name": "Anchor Components"}},
                    {"tool": "get_overdue_invoices", "parameters": {"customer_id": "<piped>"}},
                ],
                "required_facts": ["6534.00"],
            },
        }
    )
    save_cassette(
        case.id, 0,
        plan_response='{"tool_calls": [{"tool": "get_overdue_invoices", "parameters": {}}]}',
        response_text="Here are the overdue invoices.",
        cassettes_root=tmp_path,
    )
    save_cassette(
        case.id, 1,
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_customer", "parameters": {"customer_name": "Anchor Components"}}, '
            '{"tool": "get_overdue_invoices", '
            '"parameters": {"customer_id": "$step0.customer_code"}}'
            ']}'
        ),
        response_text="Anchor Components has one overdue invoice for $6,534.00.",
        cassettes_root=tmp_path,
    )

    outcome = await run_case(
        db_session, _followup_registry(), case, mode="recorded", cassettes_root=tmp_path,
    )
    await db_session.commit()

    assert [tc.tool for tc in outcome.tool_calls] == ["get_customer", "get_overdue_invoices"]
    assert outcome.tool_calls[1].parameters["customer_id"] == "CUST-9001"

    score = score_case(case, outcome)
    assert score.passed is True
