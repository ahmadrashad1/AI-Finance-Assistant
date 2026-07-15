from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class PurchaseRequisitionModel(Base):
    __tablename__ = "purchase_requisitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'rejected', 'converted')",
            name="ck_purchase_requisitions_status",
        ),
        Index("ix_purchase_requisitions_status", "status"),
        Index("ix_purchase_requisitions_department_id", "department_id"),
        Index("ix_purchase_requisitions_requester_employee_id", "requester_employee_id"),
        Index("ix_purchase_requisitions_requested_date", "requested_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requisition_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    requester_employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.departments.id"), nullable=False
    )
    requested_date: Mapped[date] = mapped_column(Date, nullable=False)
    needed_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=True
    )
    approved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RequisitionItemModel(Base):
    __tablename__ = "requisition_items"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requisition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.purchase_requisitions.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
