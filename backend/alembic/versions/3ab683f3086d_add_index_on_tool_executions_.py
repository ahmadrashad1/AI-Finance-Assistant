"""add index on tool_executions conversation_id

Revision ID: 3ab683f3086d
Revises: 7d249154768c
Create Date: 2026-07-08 02:51:12.191794

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ab683f3086d"
down_revision: str | Sequence[str] | None = "7d249154768c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_tool_executions_conversation_id",
        "tool_executions",
        ["conversation_id"],
        schema="application",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tool_executions_conversation_id",
        table_name="tool_executions",
        schema="application",
    )
