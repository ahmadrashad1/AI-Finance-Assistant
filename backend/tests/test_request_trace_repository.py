from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository


@pytest.mark.asyncio
async def test_create_then_get_request_trace(clean_db: None, db_session: AsyncSession) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-trace-1")
    conversation = await repo.create_conversation("session-trace-1")
    await db_session.commit()

    created = await repo.create_request_trace(
        conversation.id, request_id="req-trace-1",
        plan={"tool_calls": [{"tool": "get_unpaid_invoices", "parameters": {}}]},
        planning_prompt_version="1.4.0", system_prompt_version="1.5.0",
    )
    await db_session.commit()

    fetched = await repo.get_request_trace("req-trace-1")
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.plan == {"tool_calls": [{"tool": "get_unpaid_invoices", "parameters": {}}]}
    assert fetched.planning_prompt_version == "1.4.0"
    assert fetched.system_prompt_version == "1.5.0"
    assert fetched.total_duration_ms is None


@pytest.mark.asyncio
async def test_finish_request_trace_sets_duration(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-trace-2")
    conversation = await repo.create_conversation("session-trace-2")
    await db_session.commit()

    await repo.create_request_trace(
        conversation.id, request_id="req-trace-2", plan={"direct_answer": True},
        planning_prompt_version="1.4.0", system_prompt_version="1.5.0",
    )
    await db_session.commit()

    await repo.finish_request_trace("req-trace-2", total_duration_ms=842)
    await db_session.commit()

    fetched = await repo.get_request_trace("req-trace-2")
    assert fetched is not None
    assert fetched.total_duration_ms == 842


@pytest.mark.asyncio
async def test_get_request_trace_returns_none_for_unknown_request_id(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    assert await repo.get_request_trace("no-such-request-id") is None
