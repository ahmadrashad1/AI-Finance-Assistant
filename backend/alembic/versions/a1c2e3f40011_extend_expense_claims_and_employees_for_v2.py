"""extend expense_claims and employees for simulator v2

Revision ID: a1c2e3f40011
Revises: ea525685b6ed
Create Date: 2026-07-15

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1c2e3f40011'
down_revision: str | Sequence[str] | None = 'ea525685b6ed'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "expense_claims",
        sa.Column(
            "department_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.departments.id"), nullable=True,
        ),
        schema="finance",
    )
    op.add_column(
        "expense_claims", sa.Column("expense_date", sa.Date(), nullable=True), schema="finance"
    )
    op.add_column(
        "expense_claims",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        schema="finance",
    )
    op.add_column(
        "expense_claims",
        sa.Column("receipt_attached", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="finance",
    )
    op.add_column(
        "expense_claims",
        sa.Column(
            "approver_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.employees.id"), nullable=True,
        ),
        schema="finance",
    )
    op.add_column(
        "expense_claims", sa.Column("approved_date", sa.Date(), nullable=True), schema="finance"
    )
    op.add_column(
        "expense_claims",
        sa.Column(
            "policy_violations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")
        ),
        schema="finance",
    )
    op.create_index(
        "ix_expense_claims_department_id", "expense_claims", ["department_id"], schema="finance"
    )
    op.create_index(
        "ix_expense_claims_approver_id", "expense_claims", ["approver_id"], schema="finance"
    )
    op.create_index("ix_expense_claims_status", "expense_claims", ["status"], schema="finance")
    op.create_index("ix_expense_claims_category", "expense_claims", ["category"], schema="finance")
    op.create_index(
        "ix_expense_claims_expense_date", "expense_claims", ["expense_date"], schema="finance"
    )
    op.create_index(
        "ix_expense_claims_submitted_date", "expense_claims", ["submitted_date"], schema="finance"
    )

    op.add_column(
        "employees", sa.Column("grade", sa.String(length=20), nullable=True), schema="finance"
    )
    op.add_column(
        "employees", sa.Column("salary", sa.Numeric(12, 2), nullable=True), schema="finance"
    )
    op.add_column("employees", sa.Column("hire_date", sa.Date(), nullable=True), schema="finance")
    op.add_column(
        "employees", sa.Column("termination_date", sa.Date(), nullable=True), schema="finance"
    )
    op.add_column(
        "employees",
        sa.Column(
            "manager_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("finance.employees.id"), nullable=True,
        ),
        schema="finance",
    )
    op.create_check_constraint(
        "ck_employees_grade",
        "employees",
        "grade IS NULL OR grade IN ('junior', 'senior', 'manager', 'director')",
        schema="finance",
    )
    op.create_index("ix_employees_department_id", "employees", ["department_id"], schema="finance")
    op.create_index("ix_employees_status", "employees", ["status"], schema="finance")
    op.create_index("ix_employees_grade", "employees", ["grade"], schema="finance")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_employees_grade", table_name="employees", schema="finance")
    op.drop_index("ix_employees_status", table_name="employees", schema="finance")
    op.drop_index("ix_employees_department_id", table_name="employees", schema="finance")
    op.drop_constraint("ck_employees_grade", "employees", schema="finance")
    op.drop_column("employees", "manager_id", schema="finance")
    op.drop_column("employees", "termination_date", schema="finance")
    op.drop_column("employees", "hire_date", schema="finance")
    op.drop_column("employees", "salary", schema="finance")
    op.drop_column("employees", "grade", schema="finance")

    op.drop_index("ix_expense_claims_submitted_date", table_name="expense_claims", schema="finance")
    op.drop_index("ix_expense_claims_expense_date", table_name="expense_claims", schema="finance")
    op.drop_index("ix_expense_claims_category", table_name="expense_claims", schema="finance")
    op.drop_index("ix_expense_claims_status", table_name="expense_claims", schema="finance")
    op.drop_index("ix_expense_claims_approver_id", table_name="expense_claims", schema="finance")
    op.drop_index("ix_expense_claims_department_id", table_name="expense_claims", schema="finance")
    op.drop_column("expense_claims", "policy_violations", schema="finance")
    op.drop_column("expense_claims", "approved_date", schema="finance")
    op.drop_column("expense_claims", "approver_id", schema="finance")
    op.drop_column("expense_claims", "receipt_attached", schema="finance")
    op.drop_column("expense_claims", "currency", schema="finance")
    op.drop_column("expense_claims", "expense_date", schema="finance")
    op.drop_column("expense_claims", "department_id", schema="finance")
