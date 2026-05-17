"""add attached_report_id to chat_sessions

Revision ID: 83062e1da1ec
Revises: 20260516_0000_reports_expired_at
Create Date: 2026-05-17 15:54:36.531540+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83062e1da1ec"
down_revision: str | Sequence[str] | None = "20260516_0000_reports_expired_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("attached_report_id", sa.String(), nullable=True, server_default=None)
        )
    op.create_index(
        "idx_chat_sessions_attached_report_id",
        "chat_sessions",
        ["attached_report_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_chat_sessions_attached_report_id", table_name="chat_sessions")
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_column("attached_report_id")
