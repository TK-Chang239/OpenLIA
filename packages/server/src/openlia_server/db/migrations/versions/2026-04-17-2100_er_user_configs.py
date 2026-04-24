"""Create er_user_configs table for Equity Research per-user settings.

Revision ID: 2026_04_17_2100_er
Revises: c1f4e2d7a931
Create Date: 2026-04-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2026_04_17_2100_er"
down_revision: str | Sequence[str] | None = "c1f4e2d7a931"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "er_user_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("report_mode", sa.String(length=32), nullable=False),
        sa.Column("report_length", sa.String(length=16), nullable=False),
        sa.Column("sections_by_mode", sa.JSON(), nullable=False),
        sa.Column("custom_sections_by_mode", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "report_mode IN ('stock_initiation','stock_update','sector_research')",
            name="ck_er_user_configs_report_mode",
        ),
        sa.CheckConstraint(
            "report_length IN ('concise','normal','elaborative')",
            name="ck_er_user_configs_report_length",
        ),
    )
    op.create_index("ix_er_user_configs_user_id", "er_user_configs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_er_user_configs_user_id", table_name="er_user_configs")
    op.drop_table("er_user_configs")
