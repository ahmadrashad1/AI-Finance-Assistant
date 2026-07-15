"""create company policy tables

Company policies are structured, queryable data -- never prompt text
(PRD Ch.19, Company Policies). Business rules that apply them live in
services.

Revision ID: c3e4f5a60033
Revises: b2d3e4f50022
Create Date: 2026-07-15

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c3e4f5a60033'
down_revision: str | Sequence[str] | None = 'b2d3e4f50022'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "expense_limit_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("grade", sa.String(length=20), nullable=False),
        sa.Column("per_claim_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("category", "grade", name="uq_expense_limit_policies_category_grade"),
        schema="finance",
    )

    op.create_table(
        "approval_threshold_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject", sa.String(length=30), unique=True, nullable=False),
        sa.Column("threshold_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "subject IN ('payment', 'purchase_requisition', 'expense_claim')",
            name="ck_approval_threshold_policies_subject",
        ),
        schema="finance",
    )

    op.create_table(
        "expense_submission_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("receipt_required_above", sa.Numeric(12, 2), nullable=False),
        sa.Column("submission_deadline_days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="finance",
    )

    op.create_table(
        "depreciation_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_class", sa.String(length=30), unique=True, nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("useful_life_months", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "method IN ('straight_line', 'declining_balance')",
            name="ck_depreciation_policies_method",
        ),
        schema="finance",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("depreciation_policies", schema="finance")
    op.drop_table("expense_submission_policies", schema="finance")
    op.drop_table("approval_threshold_policies", schema="finance")
    op.drop_table("expense_limit_policies", schema="finance")
