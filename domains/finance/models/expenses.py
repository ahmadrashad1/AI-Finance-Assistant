from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class ExpenseClaimModel(Base):
    __tablename__ = "expense_claims"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'approved', 'rejected', 'reimbursed')",
            name="ck_expense_claims_status",
        ),
        Index("ix_expense_claims_department_id", "department_id"),
        Index("ix_expense_claims_approver_id", "approver_id"),
        Index("ix_expense_claims_status", "status"),
        Index("ix_expense_claims_category", "category"),
        Index("ix_expense_claims_expense_date", "expense_date"),
        Index("ix_expense_claims_submitted_date", "submitted_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=False, index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.departments.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expense_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    submitted_date: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_attached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted")
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=True
    )
    approved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Seeded truth of planted policy violations (codes: over_limit, missing_receipt,
    # late_submission). Services recompute violations from the policy tables; this
    # column exists so the consistency check can prove the recomputation agrees.
    policy_violations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
