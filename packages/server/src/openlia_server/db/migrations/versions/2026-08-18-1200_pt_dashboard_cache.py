"""Add pt_dashboard_cache: latest computed PT dashboard payload per user.

The Panic Thermometer dashboard recomputed ~12 upstream EODHD calls on
every GET (~14-30s). This table lets the route serve the last computed
payload instantly (with a freshness TTL) and lets a scheduled job keep
it warm across restarts.

Revision ID: pt_dashboard_cache
Revises: drop_mr_dash_config_cols
Create Date: 2026-08-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "pt_dashboard_cache"
down_revision: str = "drop_mr_dash_config_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pt_dashboard_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_pt_dashboard_cache"),
        sa.UniqueConstraint("user_id", name="uq_pt_dashboard_cache_user"),
    )
    op.create_index("ix_pt_dashboard_cache_user", "pt_dashboard_cache", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_pt_dashboard_cache_user", table_name="pt_dashboard_cache")
    op.drop_table("pt_dashboard_cache")
