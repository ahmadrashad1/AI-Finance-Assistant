"""create turn_summaries table

Revision ID: 948c5fd90c8b
Revises: 4ab4ac1573db
Create Date: 2026-07-12 18:59:36.247903

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '948c5fd90c8b'
down_revision: str | Sequence[str] | None = '4ab4ac1573db'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "turn_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application.conversations.id"), nullable=False,
        ),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=False),
        sa.Column("entities", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Index("ix_turn_summaries_conversation_id", "conversation_id"),
        schema="application",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("turn_summaries", schema="application")
