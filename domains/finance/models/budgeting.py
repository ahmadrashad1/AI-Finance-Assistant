from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class BudgetModel(Base):
    """A budgeted amount for one department, category, and month.

    Actual spend is never stored -- it is always computed from the real
    transactions (expense claims, purchase orders, payroll), so variance can
    never drift out of sync with reality (PRD Ch.20 Phase B).
    """

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint(
            "department_id", "category", "period", name="uq_budgets_department_category_period"
        ),
        Index("ix_budgets_department_id", "department_id"),
        Index("ix_budgets_category", "category"),
        Index("ix_budgets_period", "period"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.departments.id"), nullable=False
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)  # first day of the month
    budgeted_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
