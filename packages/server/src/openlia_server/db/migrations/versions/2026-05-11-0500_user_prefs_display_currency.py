"""Add portfolio_display_currency to user_prefs.

Phase 5 of the portfolio live-data design — per-user display currency used
to aggregate multi-currency portfolios via current-spot FX.

Revision ID: 20260511_0500_user_prefs_display_currency
Revises: 20260511_0400_user_prefs_portfolio_cadence
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0500_user_prefs_display_currency"
down_revision: str | Sequence[str] | None = "20260511_0400_user_prefs_portfolio_cadence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.add_column(
            sa.Column(
                "portfolio_display_currency",
                sa.String(length=8),
                nullable=False,
                server_default="USD",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_column("portfolio_display_currency")
