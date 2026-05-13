"""Phase 3: backfill_daily_history — populate portfolio_quote_daily.

Triggered async on POST /portfolio/holdings. Idempotent — re-running on the
same ticker doesn't double-write rows for dates already present.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session


class _FakeDailyProvider:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.called: list[tuple[str, int]] = []

    def fetch_daily_history(self, ticker: str, *, years: int) -> list[dict]:
        self.called.append((ticker.upper(), years))
        return self.rows


def test_backfill_inserts_all_rows(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.content import PortfolioQuoteDaily
    from openlia_server.services.portfolio_backfill import backfill_daily_history

    provider = _FakeDailyProvider(
        [
            {
                "date": date(2026, 5, 1),
                "open": Decimal("100"),
                "high": Decimal("102"),
                "low": Decimal("99"),
                "close": Decimal("101"),
                "volume": 1_000_000,
            },
            {
                "date": date(2026, 5, 2),
                "open": Decimal("101"),
                "high": Decimal("105"),
                "low": Decimal("100"),
                "close": Decimal("104"),
                "volume": 1_200_000,
            },
        ]
    )
    inserted = backfill_daily_history(db_session, ticker="aapl", provider=provider, years=5)

    rows = (
        db_session.execute(select(PortfolioQuoteDaily).order_by(PortfolioQuoteDaily.trade_date))
        .scalars()
        .all()
    )
    assert inserted == 2
    assert len(rows) == 2
    assert rows[0].ticker == "AAPL"
    assert rows[0].trade_date == date(2026, 5, 1)
    assert rows[0].close == Decimal("101")
    assert rows[1].volume == 1_200_000


def test_backfill_is_idempotent(create_tables, db_session: Session) -> None:
    from openlia_server.services.portfolio_backfill import backfill_daily_history

    provider = _FakeDailyProvider(
        [
            {
                "date": date(2026, 5, 1),
                "open": None,
                "high": None,
                "low": None,
                "close": Decimal("101"),
                "volume": None,
            },
        ]
    )
    inserted_first = backfill_daily_history(db_session, ticker="AAPL", provider=provider, years=5)
    inserted_second = backfill_daily_history(db_session, ticker="AAPL", provider=provider, years=5)

    assert inserted_first == 1
    assert inserted_second == 0


def test_backfill_passes_years_to_provider(create_tables, db_session: Session) -> None:
    from openlia_server.services.portfolio_backfill import backfill_daily_history

    provider = _FakeDailyProvider([])
    backfill_daily_history(db_session, ticker="AAPL", provider=provider, years=5)
    assert provider.called == [("AAPL", 5)]
