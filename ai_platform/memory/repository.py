from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform.memory.models import (
    ConversationModel,
    MessageModel,
    SessionModel,
    TurnSummaryModel,
)

TITLE_MAX_LENGTH = 50


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create_session(self, session_id: str) -> SessionModel:
        existing = await self._db.get(SessionModel, session_id)
        if existing is not None:
            return existing
        session = SessionModel(id=session_id)
        self._db.add(session)
        await self._db.flush()
        return session

    async def create_conversation(self, session_id: str) -> ConversationModel:
        conversation = ConversationModel(id=uuid.uuid4(), session_id=session_id)
        self._db.add(conversation)
        await self._db.flush()
        return conversation

    async def list_conversations(self, session_id: str) -> list[ConversationModel]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.session_id == session_id)
            .order_by(ConversationModel.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_conversation(self, conversation_id: uuid.UUID) -> ConversationModel | None:
        return await self._db.get(ConversationModel, conversation_id)

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: str
    ) -> MessageModel:
        conversation = await self._db.get(ConversationModel, conversation_id)
        if conversation is not None and conversation.title is None and role == "user":
            if len(content) > TITLE_MAX_LENGTH:
                conversation.title = content[:TITLE_MAX_LENGTH] + "…"
            else:
                conversation.title = content
        message = MessageModel(
            id=uuid.uuid4(), conversation_id=conversation_id, role=role, content=content
        )
        self._db.add(message)
        await self._db.flush()
        return message

    async def get_messages(self, conversation_id: uuid.UUID) -> list[MessageModel]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def record_turn_summary(
        self,
        conversation_id: uuid.UUID,
        *,
        tool_calls: list[dict[str, Any]],
        entities: dict[str, list[str]],
    ) -> TurnSummaryModel:
        summary = TurnSummaryModel(
            id=uuid.uuid4(), conversation_id=conversation_id,
            tool_calls=tool_calls, entities=entities,
        )
        self._db.add(summary)
        await self._db.flush()
        await self._db.refresh(summary)
        return summary

    async def list_recent_turn_summaries(
        self, conversation_id: uuid.UUID, limit: int = 2
    ) -> list[TurnSummaryModel]:
        stmt = (
            select(TurnSummaryModel)
            .where(TurnSummaryModel.conversation_id == conversation_id)
            .order_by(TurnSummaryModel.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
