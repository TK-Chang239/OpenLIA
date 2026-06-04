"""rs_dashboard_cache table

Adds ``rs_dashboard_cache``: one row per (user, ticker) storing the
latest typed payload produced by the ``report_dash_rs`` engine. The route
reads this row for instant dashboard delivery without re-running the engine.

Per-user so that portfolio-dependent dashboards remain isolated per user.

Revision ID: rs_dashboard_cache
Revises: drop_mr_assessment_cache
Create Date: 2026-06-04 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "rs_dashboard_cache"
down_revision: str | Sequence[str] | None = "drop_mr_assessment_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rs_dashboard_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False, server_default=sa.text("'live'")),
        sa.Column("model_ref", sa.String(128), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_rs_dashboard_cache"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_rs_dashboard_cache_user_ticker"),
    )
    op.create_index(
        "ix_rs_dashboard_cache_user_ticker",
        "rs_dashboard_cache",
        ["user_id", "ticker"],
    )


def downgrade() -> None:
    op.drop_index("ix_rs_dashboard_cache_user_ticker", table_name="rs_dashboard_cache")
    op.drop_table("rs_dashboard_cache")
