from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "evaluation"


class EvaluationCaseModel(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    suite: Mapped[str] = mapped_column(String(100), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    planning_prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    system_prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0")
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )


class EvaluationResultModel(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.evaluation_runs.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.evaluation_cases.id"), nullable=False
    )
    expected: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    actual: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
