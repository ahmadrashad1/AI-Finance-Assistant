"""create request_traces table

Revision ID: 5fbe2d93a633
Revises: 8ad328fb9e86
Create Date: 2026-07-14 00:55:43.288689

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '5fbe2d93a633'
down_revision: str | Sequence[str] | None = '8ad328fb9e86'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "request_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "conversation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application.conversations.id"), nullable=False,
        ),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("planning_prompt_version", sa.String(length=20), nullable=False),
        sa.Column("system_prompt_version", sa.String(length=20), nullable=False),
        sa.Column("total_duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Index("ix_request_traces_conversation_id", "conversation_id"),
        schema="application",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("request_traces", schema="application")
