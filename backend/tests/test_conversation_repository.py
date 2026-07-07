from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.repository import ConversationRepository


@pytest.mark.asyncio
async def test_get_or_create_session_is_idempotent(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    first = await repo.get_or_create_session("session-1")
    second = await repo.get_or_create_session("session-1")
    await db_session.commit()
    assert first.id == second.id == "session-1"


@pytest.mark.asyncio
async def test_create_conversation_and_list_by_session(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-2")
    conversation = await repo.create_conversation("session-2")
    await db_session.commit()

    conversations = await repo.list_conversations("session-2")
    assert [c.id for c in conversations] == [conversation.id]


@pytest.mark.asyncio
async def test_add_message_sets_title_from_first_user_message(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-3")
    conversation = await repo.create_conversation("session-3")
    await repo.add_message(conversation.id, "user", "What invoices are overdue?")
    await db_session.commit()

    reloaded = await repo.get_conversation(conversation.id)
    assert reloaded is not None
    assert reloaded.title == "What invoices are overdue?"


@pytest.mark.asyncio
async def test_add_message_truncates_long_title(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-4")
    conversation = await repo.create_conversation("session-4")
    long_message = "x" * 80
    await repo.add_message(conversation.id, "user", long_message)
    await db_session.commit()

    reloaded = await repo.get_conversation(conversation.id)
    assert reloaded is not None
    assert reloaded.title == "x" * 50 + "…"


@pytest.mark.asyncio
async def test_get_messages_returns_oldest_first(
    clean_db: None, db_session: AsyncSession
) -> None:
    repo = ConversationRepository(db_session)
    await repo.get_or_create_session("session-5")
    conversation = await repo.create_conversation("session-5")
    await repo.add_message(conversation.id, "user", "first")
    await repo.add_message(conversation.id, "assistant", "second")
    await db_session.commit()

    messages = await repo.get_messages(conversation.id)
    assert [m.content for m in messages] == ["first", "second"]
