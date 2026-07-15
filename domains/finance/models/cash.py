from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"


class BankAccountModel(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_number_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    opening_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CashTransactionModel(Base):
    __tablename__ = "cash_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('customer_payment', 'vendor_payment')",
            name="ck_cash_transactions_type",
        ),
        CheckConstraint(
            "(transaction_type = 'customer_payment' AND payment_id IS NOT NULL "
            "AND vendor_payment_id IS NULL) OR "
            "(transaction_type = 'vendor_payment' AND vendor_payment_id IS NOT NULL "
            "AND payment_id IS NULL)",
            name="ck_cash_transactions_reference_matches_type",
        ),
        Index("ix_cash_transactions_bank_account_id", "bank_account_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.bank_accounts.id"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.payments.id"), nullable=True
    )
    vendor_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.vendor_payments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
