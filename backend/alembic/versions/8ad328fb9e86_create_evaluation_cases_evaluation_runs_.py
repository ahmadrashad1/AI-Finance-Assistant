"""create evaluation_cases evaluation_runs evaluation_results tables

Revision ID: 8ad328fb9e86
Revises: 948c5fd90c8b
Create Date: 2026-07-13 07:39:06.796715

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '8ad328fb9e86'
down_revision: str | Sequence[str] | None = '948c5fd90c8b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "evaluation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", sa.String(length=200), nullable=False, unique=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("suite", sa.String(length=100), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="evaluation",
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("planning_prompt_version", sa.String(length=20), nullable=False),
        sa.Column("system_prompt_version", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="evaluation",
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation.evaluation_runs.id"), nullable=False,
        ),
        sa.Column(
            "case_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation.evaluation_cases.id"), nullable=False,
        ),
        sa.Column("expected", postgresql.JSONB(), nullable=False),
        sa.Column("actual", postgresql.JSONB(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Index("ix_evaluation_results_run_id", "run_id"),
        schema="evaluation",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("evaluation_results", schema="evaluation")
    op.drop_table("evaluation_runs", schema="evaluation")
    op.drop_table("evaluation_cases", schema="evaluation")
