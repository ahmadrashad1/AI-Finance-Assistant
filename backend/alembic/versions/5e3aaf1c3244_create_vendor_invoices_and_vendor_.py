"""create vendor_invoices and vendor_payments tables

Revision ID: 5e3aaf1c3244
Revises: 51417db8e8b6
Create Date: 2026-07-12 01:59:57.829591

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '5e3aaf1c3244'
down_revision: str | Sequence[str] | None = '51417db8e8b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "vendor_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vendor_invoice_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.vendors.id"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_orders.id"), nullable=True,
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled')",
            name="ck_vendor_invoices_status",
        ),
        sa.Index("ix_vendor_invoices_vendor_id", "vendor_id"),
        sa.Index("ix_vendor_invoices_due_date", "due_date"),
        sa.Index("ix_vendor_invoices_status", "status"),
        schema="finance",
    )

    op.create_table(
        "vendor_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.vendor_invoices.id"), nullable=False,
        ),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("reference_number", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "payment_method IN ('bank_transfer', 'check', 'credit_card', 'cash')",
            name="ck_vendor_payments_payment_method",
        ),
        sa.Index("ix_vendor_payments_vendor_invoice_id", "vendor_invoice_id"),
        schema="finance",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("vendor_payments", schema="finance")
    op.drop_table("vendor_invoices", schema="finance")
