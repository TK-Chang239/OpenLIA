"""eu_watchlist + eu_user_configs

Revision ID: 20260417_2200_eu
Revises: 2026_04_17_2100_er
Create Date: 2026-04-17 22:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260417_2200_eu"
down_revision: str | Sequence[str] | None = "2026_04_17_2100_er"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eu_watchlist",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.String(length=256), nullable=False),
        sa.Column("next_earnings_date", sa.Date(), nullable=True),
        sa.Column("release_timing", sa.String(length=16), nullable=True),
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
        sa.UniqueConstraint("user_id", "ticker", name="uq_eu_watchlist_user_ticker"),
        sa.CheckConstraint(
            "release_timing IS NULL OR release_timing IN ('pre_market', 'post_market')",
            name="ck_eu_watchlist_release_timing",
        ),
    )
    op.create_index("ix_eu_watchlist_user", "eu_watchlist", ["user_id"], unique=False)

    op.create_table(
        "eu_user_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "report_length",
            sa.String(length=16),
            nullable=False,
            server_default="normal",
        ),
        sa.Column(
            "enabled_section_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "custom_sections",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
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
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_eu_user_configs_length",
        ),
    )


def downgrade() -> None:
    op.drop_table("eu_user_configs")
    op.drop_index("ix_eu_watchlist_user", table_name="eu_watchlist")
    op.drop_table("eu_watchlist")
