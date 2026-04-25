"""Phase 18 — pt_trigger_events composite-level transition log.

Revision ID: 20260425_1400_pt_triggers
Revises: 20260425_0100_chat_stopped_at
Create Date: 2026-04-25 14:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260425_1400_pt_triggers"
down_revision: str | Sequence[str] | None = "20260425_0100_chat_stopped_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pt_trigger_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("level_from", sa.String(16), nullable=True),
        sa.Column("level_to", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "payload_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_pt_trigger_events_user_occurred",
        "pt_trigger_events",
        ["user_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pt_trigger_events_user_occurred", table_name="pt_trigger_events")
    op.drop_table("pt_trigger_events")
