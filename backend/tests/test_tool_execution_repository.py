from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository
from ai_platform.tool_registry.repository import ToolExecutionRepository


@pytest.mark.asyncio
async def test_record_execution_and_list_for_conversation(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_repo = ConversationRepository(db_session)
    await conversation_repo.get_or_create_session("session-tool-1")
    conversation = await conversation_repo.create_conversation("session-tool-1")
    await db_session.commit()

    repo = ToolExecutionRepository(db_session)
    execution = await repo.record_execution(
        request_id="req-1",
        conversation_id=conversation.id,
        tool="get_current_date",
        parameters={},
        result={"date": "2026-07-07", "day_of_week": "Tuesday"},
        duration_ms=5,
        status="success",
        error_message=None,
    )
    await db_session.commit()

    executions = await repo.list_for_conversation(conversation.id)
    assert [e.id for e in executions] == [execution.id]
    assert executions[0].tool == "get_current_date"
    assert executions[0].status == "success"
    assert executions[0].result == {"date": "2026-07-07", "day_of_week": "Tuesday"}


@pytest.mark.asyncio
async def test_record_execution_stores_error_state(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_repo = ConversationRepository(db_session)
    await conversation_repo.get_or_create_session("session-tool-2")
    conversation = await conversation_repo.create_conversation("session-tool-2")
    await db_session.commit()

    repo = ToolExecutionRepository(db_session)
    await repo.record_execution(
        request_id="req-2",
        conversation_id=conversation.id,
        tool="unknown_tool",
        parameters={},
        result=None,
        duration_ms=1,
        status="error",
        error_message="Unknown tool: unknown_tool",
    )
    await db_session.commit()

    executions = await repo.list_for_conversation(conversation.id)
    assert executions[0].status == "error"
    assert executions[0].result is None
    assert executions[0].error_message == "Unknown tool: unknown_tool"


@pytest.mark.asyncio
async def test_list_by_request_id_returns_only_that_requests_executions_in_order(
    clean_db: None, db_session: AsyncSession
) -> None:
    conversation_repo = ConversationRepository(db_session)
    await conversation_repo.get_or_create_session("session-tool-2")
    conversation = await conversation_repo.create_conversation("session-tool-2")
    await db_session.commit()

    repo = ToolExecutionRepository(db_session)
    await repo.record_execution(
        request_id="req-a", conversation_id=conversation.id, tool="get_customer",
        parameters={"customer_name": "Acme"}, result={"customer_code": "CUST-0001"},
        duration_ms=3, status="success", error_message=None,
    )
    await repo.record_execution(
        request_id="req-a", conversation_id=conversation.id, tool="get_overdue_invoices",
        parameters={"customer_id": "CUST-0001"}, result={"invoices": [], "summary": {}},
        duration_ms=4, status="success", error_message=None,
    )
    await repo.record_execution(
        request_id="req-b", conversation_id=conversation.id, tool="get_current_date",
        parameters={}, result={"date": "2026-07-13"}, duration_ms=1, status="success",
        error_message=None,
    )
    await db_session.commit()

    executions = await repo.list_by_request_id("req-a")
    assert [e.tool for e in executions] == ["get_customer", "get_overdue_invoices"]
