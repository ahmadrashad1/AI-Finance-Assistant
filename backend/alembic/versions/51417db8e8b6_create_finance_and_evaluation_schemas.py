"""create finance and evaluation schemas

Revision ID: 51417db8e8b6
Revises: 3ab683f3086d
Create Date: 2026-07-08 18:41:00.619012

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '51417db8e8b6'
down_revision: str | Sequence[str] | None = '3ab683f3086d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS finance")
    op.execute("CREATE SCHEMA IF NOT EXISTS evaluation")

    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="finance",
    )

    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=False),
        sa.Column("contact_name", sa.String(length=150), nullable=False),
        sa.Column("contact_email", sa.String(length=200), nullable=False),
        sa.Column("payment_terms", sa.String(length=20), nullable=False),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "payment_terms IN ('net_15', 'net_30', 'net_45', 'net_60')",
            name="ck_customers_payment_terms",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_customers_status"),
        schema="finance",
    )

    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vendor_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("contact_name", sa.String(length=150), nullable=False),
        sa.Column("contact_email", sa.String(length=200), nullable=False),
        sa.Column("payment_terms", sa.String(length=20), nullable=False),
        sa.Column("preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "payment_terms IN ('net_15', 'net_30', 'net_45', 'net_60')",
            name="ck_vendors_payment_terms",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_vendors_status"),
        schema="finance",
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku", sa.String(length=30), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="finance",
    )

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.departments.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_employees_status"),
        schema="finance",
    )

    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("po_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.vendors.id"),
            nullable=False,
        ),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column(
            "approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.employees.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'received', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
        sa.Index("ix_purchase_orders_vendor_id", "vendor_id"),
        schema="finance",
    )

    op.create_table(
        "purchase_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_orders.id"), nullable=False,
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.products.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Index("ix_purchase_order_items_purchase_order_id", "purchase_order_id"),
        schema="finance",
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.customers.id"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_orders.id"), nullable=True,
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
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
            name="ck_invoices_status",
        ),
        sa.Index("ix_invoices_customer_id", "customer_id"),
        sa.Index("ix_invoices_due_date", "due_date"),
        sa.Index("ix_invoices_status", "status"),
        schema="finance",
    )

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.invoices.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.products.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Index("ix_invoice_items_invoice_id", "invoice_id"),
        schema="finance",
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.invoices.id"),
            nullable=False,
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
            name="ck_payments_payment_method",
        ),
        sa.Index("ix_payments_invoice_id", "invoice_id"),
        schema="finance",
    )

    op.create_table(
        "expense_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_number", sa.String(length=20), nullable=False, unique=True),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finance.employees.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("submitted_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'approved', 'rejected', 'reimbursed')",
            name="ck_expense_claims_status",
        ),
        sa.Index("ix_expense_claims_employee_id", "employee_id"),
        schema="finance",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("expense_claims", schema="finance")
    op.drop_table("payments", schema="finance")
    op.drop_table("invoice_items", schema="finance")
    op.drop_table("invoices", schema="finance")
    op.drop_table("purchase_order_items", schema="finance")
    op.drop_table("purchase_orders", schema="finance")
    op.drop_table("employees", schema="finance")
    op.drop_table("products", schema="finance")
    op.drop_table("vendors", schema="finance")
    op.drop_table("customers", schema="finance")
    op.drop_table("departments", schema="finance")
    op.execute("DROP SCHEMA IF EXISTS evaluation CASCADE")
    op.execute("DROP SCHEMA IF EXISTS finance CASCADE")
