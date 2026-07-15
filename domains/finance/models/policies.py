from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class ExpenseLimitPolicyModel(Base):
    """Per-claim expense limit for one category and employee grade.

    Policies are data, never prompt text (PRD Ch.19, Company Policies).
    Business rules that apply them live in services.
    """

    __tablename__ = "expense_limit_policies"
    __table_args__ = (
        UniqueConstraint("category", "grade", name="uq_expense_limit_policies_category_grade"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    per_claim_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ApprovalThresholdPolicyModel(Base):
    """Amount above which a transaction of the given kind requires an approver."""

    __tablename__ = "approval_threshold_policies"
    __table_args__ = (
        CheckConstraint(
            "subject IN ('payment', 'purchase_requisition', 'expense_claim')",
            name="ck_approval_threshold_policies_subject",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    threshold_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExpenseSubmissionPolicyModel(Base):
    """Company-wide expense submission rules (single row)."""

    __tablename__ = "expense_submission_policies"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_required_above: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    submission_deadline_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DepreciationPolicyModel(Base):
    """Depreciation method and useful life by asset class."""

    __tablename__ = "depreciation_policies"
    __table_args__ = (
        CheckConstraint(
            "method IN ('straight_line', 'declining_balance')",
            name="ck_depreciation_policies_method",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_class: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    useful_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
