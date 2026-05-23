"""er_v2_3_run_state

Adds the suspended-run persistence table for the v2.3 equity-research
pipeline. Each row stores one ReportRunner ReportState payload so a
WAITING_ON_USER suspend can resume in a later request.

Revision ID: a9b1c2d4e5f6
Revises: f7a9b1c2d4e5
Create Date: 2026-05-22 23:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b1c2d4e5f6"
down_revision: str | Sequence[str] | None = "f7a9b1c2d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "er_v2_3_run_state",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_er_v2_3_run_state_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_er_v2_3_run_state"),
    )
    op.create_index(
        "ix_er_v2_3_run_state_user_id_status",
        "er_v2_3_run_state",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_er_v2_3_run_state_user_id_status",
        table_name="er_v2_3_run_state",
    )
    op.drop_table("er_v2_3_run_state")
