from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class PayrollRunModel(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        CheckConstraint("status IN ('completed', 'pending')", name="ck_payroll_runs_status"),
        Index("ix_payroll_runs_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period: Mapped[date] = mapped_column(Date, unique=True, nullable=False)  # month start
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    total_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # FK to finance.bank_transactions is added by migration after both tables
    # exist (the two tables reference each other).
    bank_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PayrollLineModel(Base):
    __tablename__ = "payroll_lines"
    __table_args__ = (
        Index("ix_payroll_lines_payroll_run_id", "payroll_run_id"),
        Index("ix_payroll_lines_employee_id", "employee_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.payroll_runs.id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.employees.id"), nullable=False
    )
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    overtime: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_withheld: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
