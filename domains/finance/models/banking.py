from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "finance"

BANK_TRANSACTION_TYPES = (
    "customer_receipt",
    "vendor_payment",
    "payroll",
    "expense_reimbursement",
    "bank_fee",
    "interest",
    "transfer",
    "tax_payment",
    "unknown",
)


class BankTransactionModel(Base):
    """One bank-statement line.

    This is the *bank's* view of the world, distinct from the internal cash
    ledger (finance.cash_transactions). Match columns record the seeded truth;
    the reconciliation service must be able to recompute matches
    deterministically (PRD Ch.20 Phase B).
    """

    __tablename__ = "bank_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('customer_receipt', 'vendor_payment', 'payroll', "
            "'expense_reimbursement', 'bank_fee', 'interest', 'transfer', 'tax_payment', "
            "'unknown')",
            name="ck_bank_transactions_type",
        ),
        CheckConstraint(
            "match_status IN ('matched', 'unmatched', 'internal')",
            name="ck_bank_transactions_match_status",
        ),
        Index("ix_bank_transactions_bank_account_id", "bank_account_id"),
        Index("ix_bank_transactions_transaction_date", "transaction_date"),
        Index("ix_bank_transactions_transaction_type", "transaction_type"),
        Index("ix_bank_transactions_match_status", "match_status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.bank_accounts.id"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # signed
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    matched_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.payments.id"), nullable=True
    )
    matched_vendor_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.vendor_payments.id"), nullable=True
    )
    matched_payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.payroll_runs.id"), nullable=True
    )
    matched_expense_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.expense_claims.id"), nullable=True
    )
    match_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
