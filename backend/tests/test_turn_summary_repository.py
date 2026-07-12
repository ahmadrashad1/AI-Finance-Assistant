from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository


@pytest.mark.asyncio
async def test_record_turn_summary_and_list_recent(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-turn-1")
    conversation = await repo.create_conversation("session-turn-1")

    await repo.record_turn_summary(
        conversation.id,
        tool_calls=[{"tool": "get_overdue_invoices", "parameters": {}}],
        entities={"customer_name": ["Crestline Holdings"], "invoice_number": ["INV-7002"]},
    )
    await db_session.commit()

    summaries = await repo.list_recent_turn_summaries(conversation.id)
    assert len(summaries) == 1
    assert summaries[0].tool_calls == [{"tool": "get_overdue_invoices", "parameters": {}}]
    assert summaries[0].entities["customer_name"] == ["Crestline Holdings"]


@pytest.mark.asyncio
async def test_list_recent_turn_summaries_returns_most_recent_first_and_respects_limit(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-turn-2")
    conversation = await repo.create_conversation("session-turn-2")

    for i in range(4):
        await repo.record_turn_summary(
            conversation.id,
            tool_calls=[{"tool": f"tool_{i}", "parameters": {}}],
            entities={},
        )
    await db_session.commit()

    summaries = await repo.list_recent_turn_summaries(conversation.id, limit=2)
    assert [s.tool_calls[0]["tool"] for s in summaries] == ["tool_3", "tool_2"]


@pytest.mark.asyncio
async def test_list_recent_turn_summaries_returns_empty_for_a_fresh_conversation(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-turn-3")
    conversation = await repo.create_conversation("session-turn-3")
    await db_session.commit()

    assert await repo.list_recent_turn_summaries(conversation.id) == []
