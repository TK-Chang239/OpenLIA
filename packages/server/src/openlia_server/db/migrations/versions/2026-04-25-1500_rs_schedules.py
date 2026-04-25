"""rs_schedules per-user RS snapshot schedule

Revision ID: 20260425_1500_rs_sched
Revises: 20260425_1400_pt_triggers
Create Date: 2026-04-25 15:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260425_1500_rs_sched"
down_revision: str | Sequence[str] | None = "20260425_1400_pt_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rs_schedules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("time", sa.String(length=5), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("days_of_week", sa.Text(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rs_schedules_user", "rs_schedules", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_rs_schedules_user", table_name="rs_schedules")
    op.drop_table("rs_schedules")
