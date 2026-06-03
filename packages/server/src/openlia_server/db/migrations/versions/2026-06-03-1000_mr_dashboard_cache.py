"""mr_dashboard_cache table

Adds ``mr_dashboard_cache``: one row per (user, dashboard) storing the
latest typed payload produced by the ``report_dash_mr`` engine. The route
reads this row for instant dashboard delivery without re-running the engine.

Per-user (not global) so that portfolio-dependent dashboards (e.g.
All-Weather) remain isolated per user; the contract is uniform across all
dashboard types.

Revision ID: mr_dashboard_cache
Revises: drop_mb_user_configs
Create Date: 2026-06-03 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "mr_dashboard_cache"
down_revision: str | Sequence[str] | None = "drop_mb_user_configs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mr_dashboard_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dashboard", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False, server_default=sa.text("'live'")),
        sa.Column("model_ref", sa.String(128), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_mr_dashboard_cache"),
        sa.UniqueConstraint("user_id", "dashboard", name="uq_mr_dashboard_cache_user_dashboard"),
    )
    op.create_index(
        "ix_mr_dashboard_cache_user_dashboard",
        "mr_dashboard_cache",
        ["user_id", "dashboard"],
    )


def downgrade() -> None:
    op.drop_index("ix_mr_dashboard_cache_user_dashboard", table_name="mr_dashboard_cache")
    op.drop_table("mr_dashboard_cache")
