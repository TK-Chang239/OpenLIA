"""portfolio_quotes + portfolio_quote_intraday + portfolio_quote_daily.

Three tables that back the server-scheduled portfolio price refresh
system (see ``planning/specs/systems/portfolio-live-data-design.md``):

- ``portfolio_quotes``: one row per ticker, upserted by the scheduler
  and the manual refresh route. Replaces the in-memory PriceCache as
  the source of truth for /analytics.
- ``portfolio_quote_intraday``: scheduler tick points used for sparklines.
- ``portfolio_quote_daily``: official OHLCV close series populated by the
  post-close fire and the 5Y backfill on holding add.

Revision ID: 20260511_0300_portfolio_quotes
Revises: 20260511_0200_graph_artifact_summaries_fts
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0300_portfolio_quotes"
down_revision: str | Sequence[str] | None = "20260511_0200_graph_artifact_summaries_fts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_quotes",
        sa.Column("ticker", sa.String(length=32), primary_key=True),
        sa.Column("last_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("previous_close", sa.Numeric(20, 6), nullable=True),
        sa.Column("day_open", sa.Numeric(20, 6), nullable=True),
        sa.Column("day_high", sa.Numeric(20, 6), nullable=True),
        sa.Column("day_low", sa.Numeric(20, 6), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("quote_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
    )

    op.create_table(
        "portfolio_quote_intraday",
        sa.Column("ticker", sa.String(length=32), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
    )
    op.create_index(
        "ix_portfolio_quote_intraday_ticker_ts",
        "portfolio_quote_intraday",
        ["ticker", "ts"],
        unique=False,
    )

    op.create_table(
        "portfolio_quote_daily",
        sa.Column("ticker", sa.String(length=32), primary_key=True),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(20, 6), nullable=True),
        sa.Column("high", sa.Numeric(20, 6), nullable=True),
        sa.Column("low", sa.Numeric(20, 6), nullable=True),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_portfolio_quote_daily_ticker_date",
        "portfolio_quote_daily",
        ["ticker", "trade_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_quote_daily_ticker_date", table_name="portfolio_quote_daily"
    )
    op.drop_table("portfolio_quote_daily")
    op.drop_index(
        "ix_portfolio_quote_intraday_ticker_ts", table_name="portfolio_quote_intraday"
    )
    op.drop_table("portfolio_quote_intraday")
    op.drop_table("portfolio_quotes")
