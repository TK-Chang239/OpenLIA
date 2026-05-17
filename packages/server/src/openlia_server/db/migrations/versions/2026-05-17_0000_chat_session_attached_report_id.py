"""Add attached_report_id column to chat_sessions table.

Stores the report bound to a session at creation time, used by
"Ask in Secretary" handoffs from report viewers.

Revision ID: 20260517_0000_chat_session_attached_report_id
Revises: 20260516_0000_reports_expired_at
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0000_chat_session_attached_report_id"
down_revision: str | Sequence[str] | None = "20260516_0000_reports_expired_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.add_column(
            sa.Column(
                "attached_report_id",
                sa.String(36),
                sa.ForeignKey("reports.id", ondelete="SET NULL", use_alter=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_column("attached_report_id")
