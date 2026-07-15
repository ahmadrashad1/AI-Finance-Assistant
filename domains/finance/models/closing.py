from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class ClosePeriodModel(Base):
    __tablename__ = "close_periods"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'closed')", name="ck_close_periods_status"
        ),
        Index("ix_close_periods_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period: Mapped[date] = mapped_column(Date, unique=True, nullable=False)  # month start
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    opened_date: Mapped[date] = mapped_column(Date, nullable=False)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CloseTaskModel(Base):
    __tablename__ = "close_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'blocked', 'completed')",
            name="ck_close_tasks_status",
        ),
        Index("ix_close_tasks_close_period_id", "close_period_id"),
        Index("ix_close_tasks_status", "status"),
        Index("ix_close_tasks_owner_employee_id", "owner_employee_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    close_period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.close_periods.id"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
