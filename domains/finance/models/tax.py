from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class TaxRateModel(Base):
    __tablename__ = "tax_rates"
    __table_args__ = (
        Index("ix_tax_rates_jurisdiction_category", "jurisdiction", "category"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TaxPeriodModel(Base):
    """A tax filing period. Positions (collected, paid, net payable) are always
    computed from invoices and vendor payments by a service -- never stored
    (PRD Ch.20 Phase C)."""

    __tablename__ = "tax_periods"
    __table_args__ = (
        CheckConstraint("status IN ('filed', 'open', 'overdue')", name="ck_tax_periods_status"),
        UniqueConstraint("jurisdiction", "period", name="uq_tax_periods_jurisdiction_period"),
        Index("ix_tax_periods_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # e.g. "2026-Q1"
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    filing_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    filed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
