"""Add user_prefs table (Plan 11 Task 1).

Revision ID: b3d8f5a0e192
Revises: 9a4b7c2e6f01
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b3d8f5a0e192"
down_revision: str = "9a4b7c2e6f01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_prefs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("theme", sa.String(length=16), nullable=False, server_default="system"),
        sa.Column("notify_inapp", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("display_language", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("response_language", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("report_language", sa.String(length=8), nullable=False, server_default="en"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint("theme IN ('system','light','dark')", name="ck_user_prefs_theme"),
        sa.CheckConstraint(
            "display_language IN ('en','zh-TW') "
            "AND response_language IN ('en','zh-TW') "
            "AND report_language IN ('en','zh-TW','both')",
            name="ck_user_prefs_language",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_prefs")
