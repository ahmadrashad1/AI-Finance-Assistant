"""index tool_executions request_id

Revision ID: ea525685b6ed
Revises: 5fbe2d93a633
Create Date: 2026-07-14 01:16:08.431269

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'ea525685b6ed'
down_revision: str | Sequence[str] | None = '5fbe2d93a633'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_tool_executions_request_id",
        "tool_executions",
        ["request_id"],
        schema="application",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tool_executions_request_id", table_name="tool_executions", schema="application"
    )
