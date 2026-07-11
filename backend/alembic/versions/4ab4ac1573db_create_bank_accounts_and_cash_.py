"""create bank_accounts and cash_transactions tables

Revision ID: 4ab4ac1573db
Revises: 5e3aaf1c3244
Create Date: 2026-07-12 02:08:42.767668

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '4ab4ac1573db'
down_revision: str | Sequence[str] | None = '5e3aaf1c3244'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_name", sa.String(length=100), nullable=False),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("opening_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="finance",
    )

    op.create_table(
        "cash_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bank_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.bank_accounts.id"), nullable=False,
        ),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column(
            "payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.payments.id"),
            nullable=True,
        ),
        sa.Column(
            "vendor_payment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.vendor_payments.id"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "transaction_type IN ('customer_payment', 'vendor_payment')",
            name="ck_cash_transactions_type",
        ),
        sa.CheckConstraint(
            "(transaction_type = 'customer_payment' AND payment_id IS NOT NULL "
            "AND vendor_payment_id IS NULL) OR "
            "(transaction_type = 'vendor_payment' AND vendor_payment_id IS NOT NULL "
            "AND payment_id IS NULL)",
            name="ck_cash_transactions_reference_matches_type",
        ),
        sa.Index("ix_cash_transactions_bank_account_id", "bank_account_id"),
        schema="finance",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("cash_transactions", schema="finance")
    op.drop_table("bank_accounts", schema="finance")
