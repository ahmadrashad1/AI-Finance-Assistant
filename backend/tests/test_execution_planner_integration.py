from __future__ import annotations

import json as json_module
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatEvent, ChatRequest, ChatWorkflow
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_customer import GET_CUSTOMER_TOOL
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
    registry.register(GET_CUSTOMER_TOOL)
    registry.register(GET_OVERDUE_INVOICES_TOOL)
    execution_repository = ToolExecutionRepository(db_session)
    tool_executor = ToolExecutor(registry, execution_repository, db_session)
    prompt_builder = PromptBuilder()
    return ChatWorkflow(
        repository=repository,
        memory=ConversationMemory(repository),
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        planner=Planner(llm_service, registry, prompt_builder),
        execution_planner=ExecutionPlanner(),
        tool_executor=tool_executor,
        request_id="piping-test-req",
    )


@pytest.mark.asyncio
async def test_dependent_two_step_plan_pipes_the_resolved_customer_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-7701", company_name="ABC Industries", industry="Manufacturing",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7701", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    llm_service = FakeLLMService(
        tokens=["Here you go."],
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_customer", "parameters": {"customer_name": "ABC Industries"}}, '
            '{"tool": "get_overdue_invoices", '
            '"parameters": {"customer_id": "$step0.customer_code"}}'
            ']}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events: list[ChatEvent] = [
        e
        async for e in workflow.run(
            ChatRequest(session_id="piping-session", message="ABC Industries' overdue invoices")
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_customer", "get_overdue_invoices"]

    assert llm_service.last_message is not None
    payload_json = llm_service.last_message.split("\n\n[Tool results — use only this data]\n")[1]

    payload = json_module.loads(payload_json)
    assert payload[0]["status"] == "success"
    assert payload[1]["status"] == "success"
    assert payload[1]["result"]["invoices"][0]["invoice_number"] == "INV-7701"


@pytest.mark.asyncio
async def test_unresolvable_reference_degrades_gracefully_without_aborting_the_plan(
    clean_db: None, db_session: AsyncSession
) -> None:
    llm_service = FakeLLMService(
        tokens=["Here you go."],
        plan_response=(
            '{"tool_calls": ['
            '{"tool": "get_customer", "parameters": {"customer_name": "Nonexistent Corp"}}, '
            '{"tool": "get_overdue_invoices", '
            '"parameters": {"customer_id": "$step0.customer_code"}}'
            ']}'
        ),
    )
    workflow = _make_workflow(db_session, llm_service)

    events: list[ChatEvent] = [
        e
        async for e in workflow.run(
            ChatRequest(
                session_id="piping-session-2",
                message="Nonexistent Corp's overdue invoices",
            )
        )
    ]
    await db_session.commit()

    tool_call_events = [e for e in events if e.type == "tool_call"]
    assert [e.tool for e in tool_call_events] == ["get_customer", "get_overdue_invoices"]

    assert llm_service.last_message is not None
    payload_json = llm_service.last_message.split("\n\n[Tool results — use only this data]\n")[1]

    payload = json_module.loads(payload_json)
    assert payload[0]["status"] == "error"
    assert payload[1]["status"] == "error"
    assert "did not succeed" in payload[1]["error"]
