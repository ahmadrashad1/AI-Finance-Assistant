"""create simulator v2 entity groups

Requisitions, budgets, fixed assets, payroll, bank transactions, financial
close, and tax (PRD Ch.20 Phases B and C), plus creation/approval metadata on
the existing transactional tables (segregation-of-duties analysis).

Revision ID: b2d3e4f50022
Revises: a1c2e3f40011
Create Date: 2026-07-15

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b2d3e4f50022'
down_revision: str | Sequence[str] | None = 'a1c2e3f40011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "purchase_requisitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requisition_number", sa.String(length=20), unique=True, nullable=False),
        sa.Column(
            "requester_employee_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.employees.id"), nullable=False,
        ),
        sa.Column(
            "department_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.departments.id"), nullable=False,
        ),
        sa.Column("requested_date", sa.Date(), nullable=False),
        sa.Column("needed_by_date", sa.Date(), nullable=True),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("estimated_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "approver_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.employees.id"), nullable=True,
        ),
        sa.Column("approved_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'rejected', 'converted')",
            name="ck_purchase_requisitions_status",
        ),
        sa.Index("ix_purchase_requisitions_status", "status"),
        sa.Index("ix_purchase_requisitions_department_id", "department_id"),
        sa.Index("ix_purchase_requisitions_requester_employee_id", "requester_employee_id"),
        sa.Index("ix_purchase_requisitions_requested_date", "requested_date"),
        schema="finance",
    )

    op.create_table(
        "requisition_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "requisition_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_requisitions.id"), nullable=False,
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.products.id"), nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("estimated_unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Index("ix_requisition_items_requisition_id", "requisition_id"),
        schema="finance",
    )

    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "department_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.departments.id"), nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("budgeted_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "department_id", "category", "period", name="uq_budgets_department_category_period"
        ),
        sa.Index("ix_budgets_department_id", "department_id"),
        sa.Index("ix_budgets_category", "category"),
        sa.Index("ix_budgets_period", "period"),
        schema="finance",
    )

    op.create_table(
        "fixed_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_tag", sa.String(length=20), unique=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("asset_class", sa.String(length=30), nullable=False),
        sa.Column(
            "department_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.departments.id"), nullable=False,
        ),
        sa.Column(
            "vendor_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.vendors.id"), nullable=True,
        ),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("purchase_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", sa.String(length=20), nullable=False),
        sa.Column("salvage_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("disposal_date", sa.Date(), nullable=True),
        sa.Column("disposal_proceeds", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "asset_class IN ('machinery', 'vehicle', 'it_equipment', 'office_furniture')",
            name="ck_fixed_assets_asset_class",
        ),
        sa.CheckConstraint(
            "depreciation_method IN ('straight_line', 'declining_balance')",
            name="ck_fixed_assets_depreciation_method",
        ),
        sa.CheckConstraint(
            "status IN ('in_use', 'in_storage', 'disposed')", name="ck_fixed_assets_status"
        ),
        sa.Index("ix_fixed_assets_asset_class", "asset_class"),
        sa.Index("ix_fixed_assets_department_id", "department_id"),
        sa.Index("ix_fixed_assets_status", "status"),
        sa.Index("ix_fixed_assets_purchase_date", "purchase_date"),
        schema="finance",
    )

    op.create_table(
        "payroll_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("period", sa.Date(), unique=True, nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("total_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_net", sa.Numeric(14, 2), nullable=False),
        sa.Column("bank_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('completed', 'pending')", name="ck_payroll_runs_status"),
        sa.Index("ix_payroll_runs_status", "status"),
        schema="finance",
    )

    op.create_table(
        "payroll_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "payroll_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.payroll_runs.id"), nullable=False,
        ),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.employees.id"), nullable=False,
        ),
        sa.Column("base_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("overtime", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("bonus", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_withheld", sa.Numeric(12, 2), nullable=False),
        sa.Column("other_deductions", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_pay", sa.Numeric(12, 2), nullable=False),
        sa.Index("ix_payroll_lines_payroll_run_id", "payroll_run_id"),
        sa.Index("ix_payroll_lines_employee_id", "employee_id"),
        schema="finance",
    )

    op.create_table(
        "bank_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bank_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.bank_accounts.id"), nullable=False,
        ),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("reference", sa.String(length=50), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("transaction_type", sa.String(length=30), nullable=False),
        sa.Column(
            "matched_payment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.payments.id"), nullable=True,
        ),
        sa.Column(
            "matched_vendor_payment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.vendor_payments.id"), nullable=True,
        ),
        sa.Column(
            "matched_payroll_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.payroll_runs.id"), nullable=True,
        ),
        sa.Column(
            "matched_expense_claim_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.expense_claims.id"), nullable=True,
        ),
        sa.Column("match_status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "transaction_type IN ('customer_receipt', 'vendor_payment', 'payroll', "
            "'expense_reimbursement', 'bank_fee', 'interest', 'transfer', 'tax_payment', "
            "'unknown')",
            name="ck_bank_transactions_type",
        ),
        sa.CheckConstraint(
            "match_status IN ('matched', 'unmatched', 'internal')",
            name="ck_bank_transactions_match_status",
        ),
        sa.Index("ix_bank_transactions_bank_account_id", "bank_account_id"),
        sa.Index("ix_bank_transactions_transaction_date", "transaction_date"),
        sa.Index("ix_bank_transactions_transaction_type", "transaction_type"),
        sa.Index("ix_bank_transactions_match_status", "match_status"),
        schema="finance",
    )

    # payroll_runs <-> bank_transactions reference each other; the second FK
    # is added only after both tables exist.
    op.create_foreign_key(
        "fk_payroll_runs_bank_transaction_id",
        "payroll_runs",
        "bank_transactions",
        ["bank_transaction_id"],
        ["id"],
        source_schema="finance",
        referent_schema="finance",
    )

    op.create_table(
        "close_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("period", sa.Date(), unique=True, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("opened_date", sa.Date(), nullable=False),
        sa.Column("closed_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'closed')", name="ck_close_periods_status"
        ),
        sa.Index("ix_close_periods_status", "status"),
        schema="finance",
    )

    op.create_table(
        "close_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "close_period_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.close_periods.id"), nullable=False,
        ),
        sa.Column("task_name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column(
            "owner_employee_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.employees.id"), nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("blocking_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'blocked', 'completed')",
            name="ck_close_tasks_status",
        ),
        sa.Index("ix_close_tasks_close_period_id", "close_period_id"),
        sa.Index("ix_close_tasks_status", "status"),
        sa.Index("ix_close_tasks_owner_employee_id", "owner_employee_id"),
        schema="finance",
    )

    op.create_table(
        "tax_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("jurisdiction", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Index("ix_tax_rates_jurisdiction_category", "jurisdiction", "category"),
        schema="finance",
    )

    op.create_table(
        "tax_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("jurisdiction", sa.String(length=50), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("filing_due_date", sa.Date(), nullable=False),
        sa.Column("filed_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('filed', 'open', 'overdue')", name="ck_tax_periods_status"),
        sa.UniqueConstraint("jurisdiction", "period", name="uq_tax_periods_jurisdiction_period"),
        sa.Index("ix_tax_periods_status", "status"),
        schema="finance",
    )

    # --- extensions to existing tables -----------------------------------
    op.add_column(
        "bank_accounts",
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        schema="finance",
    )
    op.add_column(
        "bank_accounts",
        sa.Column("account_number_masked", sa.String(length=20), nullable=True),
        schema="finance",
    )
    op.add_column(
        "bank_accounts",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        schema="finance",
    )

    op.alter_column(
        "purchase_orders", "approved_by", new_column_name="approved_by_employee_id",
        schema="finance",
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "requisition_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.purchase_requisitions.id"), nullable=True,
        ),
        schema="finance",
    )
    op.add_column(
        "purchase_orders",
        sa.Column(
            "created_by_employee_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.employees.id"), nullable=True,
        ),
        schema="finance",
    )
    op.create_index(
        "ix_purchase_orders_status", "purchase_orders", ["status"], schema="finance"
    )
    op.create_index(
        "ix_purchase_orders_order_date", "purchase_orders", ["order_date"], schema="finance"
    )
    op.create_index(
        "ix_purchase_orders_requisition_id", "purchase_orders", ["requisition_id"],
        schema="finance",
    )

    for table in ("invoices", "payments", "vendor_payments"):
        op.add_column(
            table,
            sa.Column(
                "created_by_employee_id", postgresql.UUID(as_uuid=True),
                sa.ForeignKey("finance.employees.id"), nullable=True,
            ),
            schema="finance",
        )
        op.add_column(
            table,
            sa.Column(
                "approved_by_employee_id", postgresql.UUID(as_uuid=True),
                sa.ForeignKey("finance.employees.id"), nullable=True,
            ),
            schema="finance",
        )
    op.create_index("ix_payments_payment_date", "payments", ["payment_date"], schema="finance")
    op.create_index(
        "ix_vendor_payments_payment_date", "vendor_payments", ["payment_date"], schema="finance"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_vendor_payments_payment_date", table_name="vendor_payments", schema="finance")
    op.drop_index("ix_payments_payment_date", table_name="payments", schema="finance")
    for table in ("vendor_payments", "payments", "invoices"):
        op.drop_column(table, "approved_by_employee_id", schema="finance")
        op.drop_column(table, "created_by_employee_id", schema="finance")

    op.drop_index(
        "ix_purchase_orders_requisition_id", table_name="purchase_orders", schema="finance"
    )
    op.drop_index("ix_purchase_orders_order_date", table_name="purchase_orders", schema="finance")
    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders", schema="finance")
    op.drop_column("purchase_orders", "created_by_employee_id", schema="finance")
    op.drop_column("purchase_orders", "requisition_id", schema="finance")
    op.alter_column(
        "purchase_orders", "approved_by_employee_id", new_column_name="approved_by",
        schema="finance",
    )

    op.drop_column("bank_accounts", "currency", schema="finance")
    op.drop_column("bank_accounts", "account_number_masked", schema="finance")
    op.drop_column("bank_accounts", "bank_name", schema="finance")

    op.drop_table("tax_periods", schema="finance")
    op.drop_table("tax_rates", schema="finance")
    op.drop_table("close_tasks", schema="finance")
    op.drop_table("close_periods", schema="finance")
    op.drop_constraint(
        "fk_payroll_runs_bank_transaction_id", "payroll_runs", schema="finance"
    )
    op.drop_table("bank_transactions", schema="finance")
    op.drop_table("payroll_lines", schema="finance")
    op.drop_table("payroll_runs", schema="finance")
    op.drop_table("fixed_assets", schema="finance")
    op.drop_table("budgets", schema="finance")
    op.drop_table("requisition_items", schema="finance")
    op.drop_table("purchase_requisitions", schema="finance")
