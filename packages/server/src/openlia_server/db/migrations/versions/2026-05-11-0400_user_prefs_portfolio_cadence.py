"""Add portfolio_refresh_cadence to user_prefs.

Phase 2 of the portfolio live-data design — per-user freshness floor used by
the scheduler to dedupe quote fetches across users.

Revision ID: 20260511_0400_user_prefs_portfolio_cadence
Revises: 20260511_0300_portfolio_quotes
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0400_user_prefs_portfolio_cadence"
down_revision: str | Sequence[str] | None = "20260511_0300_portfolio_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.add_column(
            sa.Column(
                "portfolio_refresh_cadence",
                sa.String(length=16),
                nullable=False,
                server_default="daily",
            )
        )
        batch.create_check_constraint(
            "ck_user_prefs_portfolio_cadence",
            "portfolio_refresh_cadence IN ('hourly','daily','weekly','manual')",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_constraint("ck_user_prefs_portfolio_cadence", type_="check")
        batch.drop_column("portfolio_refresh_cadence")
