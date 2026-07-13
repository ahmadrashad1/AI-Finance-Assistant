from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory
from ai_platform.memory.repository import ConversationRepository
from ai_platform.orchestration.chat_workflow import ChatRequest, ChatWorkflow
from ai_platform.orchestration.execution_planner import ExecutionPlanner
from ai_platform.orchestration.planner import Planner
from ai_platform.orchestration.prompt_builder import PromptBuilder
from ai_platform.tool_registry.executor import ToolExecutor
from ai_platform.tool_registry.registry import ToolRegistry
from ai_platform.tool_registry.repository import ToolExecutionRepository
from domains.finance.repositories.customer_repository import CustomerRepository
from domains.finance.repositories.invoice_repository import InvoiceRepository
from domains.finance.tools.get_overdue_invoices import GET_OVERDUE_INVOICES_TOOL
from tests.fakes import FakeLLMService


def _make_workflow(db_session: AsyncSession, llm_service: FakeLLMService) -> ChatWorkflow:
    repository = ConversationRepository(db_session)
    registry = ToolRegistry()
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
        # Unique per workflow, mirroring production where RequestContextMiddleware
        # issues a fresh uuid per HTTP request - request_traces.request_id is unique.
        request_id=f"turn-summary-test-req-{uuid.uuid4()}",
    )


@pytest.mark.asyncio
async def test_second_turns_planning_prompt_sees_the_first_turns_tool_activity(
    clean_db: None, db_session: AsyncSession
) -> None:
    customer_repo = CustomerRepository(db_session)
    customer = await customer_repo.create(
        customer_code="CUST-7801", company_name="Crestline Holdings", industry="Retail",
        contact_name="A", contact_email="a@example.com", payment_terms="net_30",
        credit_limit=Decimal("50000.00"),
    )
    invoice_repo = InvoiceRepository(db_session)
    await invoice_repo.create(
        invoice_number="INV-7801", customer_id=customer.id, purchase_order_id=None,
        issue_date=date(2026, 1, 1), due_date=date(2026, 2, 1), status="overdue",
        subtotal=Decimal("500"), tax=Decimal("0"), total=Decimal("500"),
    )
    await db_session.commit()

    llm_service = FakeLLMService(
        tokens=["Here are the overdue invoices."],
        plan_response='{"tool_calls": [{"tool": "get_overdue_invoices", "parameters": {}}]}',
    )
    workflow = _make_workflow(db_session, llm_service)

    conversation_id: str | None = None
    async for event in workflow.run(
        ChatRequest(session_id="turn-summary-session", message="Show overdue invoices")
    ):
        if event.type == "done":
            conversation_id = event.conversation_id
    await db_session.commit()
    assert conversation_id is not None

    llm_service_2 = FakeLLMService(
        tokens=["Just that one."],
        plan_response='{"direct_answer": true}',
    )
    workflow_2 = _make_workflow(db_session, llm_service_2)
    async for _ in workflow_2.run(
        ChatRequest(
            session_id="turn-summary-session",
            message="Which of those belong to Crestline Holdings?",
            conversation_id=conversation_id,
        )
    ):
        pass
    await db_session.commit()

    assert llm_service_2.last_complete_system is not None
    assert "get_overdue_invoices" in llm_service_2.last_complete_system
    assert "Crestline Holdings" in llm_service_2.last_complete_system
    assert "INV-7801" in llm_service_2.last_complete_system
