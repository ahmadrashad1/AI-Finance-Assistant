"""create tool_executions table

Revision ID: 7d249154768c
Revises: daf36d10940a
Create Date: 2026-07-07 22:05:11.169664

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7d249154768c"
down_revision: str | Sequence[str] | None = "daf36d10940a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tool_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("application.conversations.id"),
            nullable=False,
        ),
        sa.Column("tool", sa.String(length=100), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="application",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tool_executions", schema="application")
