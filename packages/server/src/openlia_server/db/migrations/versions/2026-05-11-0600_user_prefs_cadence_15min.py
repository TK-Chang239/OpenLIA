"""Allow '15min' as a portfolio_refresh_cadence value.

Matches the */15 intraday cron so a user opting in gets a stored quote on
every sub-hour fire during market hours.

Revision ID: 20260511_0600_user_prefs_cadence_15min
Revises: 20260511_0500_user_prefs_display_currency
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260511_0600_user_prefs_cadence_15min"
down_revision: str | Sequence[str] | None = "20260511_0500_user_prefs_display_currency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_constraint("ck_user_prefs_portfolio_cadence", type_="check")
        batch.create_check_constraint(
            "ck_user_prefs_portfolio_cadence",
            "portfolio_refresh_cadence IN ('15min','hourly','daily','weekly','manual')",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_constraint("ck_user_prefs_portfolio_cadence", type_="check")
        batch.create_check_constraint(
            "ck_user_prefs_portfolio_cadence",
            "portfolio_refresh_cadence IN ('hourly','daily','weekly','manual')",
        )
