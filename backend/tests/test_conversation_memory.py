from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.conversation_memory import ConversationMemory, HistoryMessage
from ai_platform.memory.repository import ConversationRepository


@pytest.mark.asyncio
async def test_empty_conversation_returns_empty_window(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-mem-1")
    conversation = await repo.create_conversation("session-mem-1")
    await db_session.commit()

    memory = ConversationMemory(repo)
    window = await memory.get_context_window(conversation.id)
    assert window == []


@pytest.mark.asyncio
async def test_window_is_bounded_to_last_ten_messages(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-mem-2")
    conversation = await repo.create_conversation("session-mem-2")
    for i in range(12):
        role = "user" if i % 2 == 0 else "assistant"
        await repo.add_message(conversation.id, role, f"message-{i}")
    await db_session.commit()

    memory = ConversationMemory(repo)
    window = await memory.get_context_window(conversation.id)

    assert len(window) == 10
    assert window[0] == HistoryMessage(role="user", content="message-2")
    assert window[-1] == HistoryMessage(role="assistant", content="message-11")
