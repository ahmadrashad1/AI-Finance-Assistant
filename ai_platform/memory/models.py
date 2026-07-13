from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "application"


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationModel(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_session_id", "session_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(f"{SCHEMA}.sessions.id"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TurnSummaryModel(Base):
    __tablename__ = "turn_summaries"
    __table_args__ = (
        Index("ix_turn_summaries_conversation_id", "conversation_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id"), nullable=False
    )
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    entities: Mapped[dict[str, list[str]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class RequestTraceModel(Base):
    __tablename__ = "request_traces"
    __table_args__ = (
        Index("ix_request_traces_conversation_id", "conversation_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id"), nullable=False
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    planning_prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    system_prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    total_duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
