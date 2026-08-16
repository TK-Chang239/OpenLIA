"""Portfolio quote storage — DB-backed, replacing the in-memory PriceCache.

A single :class:`PortfolioQuote` row exists per ticker (uppercased) and is
upserted by the scheduler's ``JobType.PORTFOLIO_PRICE_REFRESH`` executor
and the manual ``/portfolio/refresh-prices`` route. Read paths (``/analytics``
and the time-series endpoints) consult this table directly.

See ``planning/specs/systems/portfolio-live-data-design.md`` for the full
design.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import PortfolioQuote

# Sentinel distinguishing "field not supplied — preserve existing value" from an
# explicit ``None`` ("no data"). The manual /refresh-prices route only has a live
# last_price and must NOT clobber the scheduler-populated previous_close / OHLC /
# volume; it omits those args so they default to _KEEP.
_KEEP: Any = object()


def upsert_quote(
    session: Session,
    *,
    ticker: str,
    last_price: Decimal | None,
    previous_close: Decimal | None = _KEEP,
    day_open: Decimal | None = _KEEP,
    day_high: Decimal | None = _KEEP,
    day_low: Decimal | None = _KEEP,
    volume: int | None = _KEEP,
    currency: str | None,
    quote_at: datetime | None,
    fetched_at: datetime,
    source: str,
) -> PortfolioQuote:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    row = session.get(PortfolioQuote, ticker)
    if row is None:
        row = PortfolioQuote(ticker=ticker, fetched_at=fetched_at, source=source)
        session.add(row)
    row.last_price = last_price
    if previous_close is not _KEEP:
        row.previous_close = previous_close
    if day_open is not _KEEP:
        row.day_open = day_open
    if day_high is not _KEEP:
        row.day_high = day_high
    if day_low is not _KEEP:
        row.day_low = day_low
    if volume is not _KEEP:
        row.volume = volume
    row.currency = currency
    row.quote_at = quote_at
    row.fetched_at = fetched_at
    row.source = source
    session.commit()
    return row


def get_quote(session: Session, *, ticker: str) -> PortfolioQuote | None:
    return session.get(PortfolioQuote, ticker.strip().upper())


def get_quotes_bulk(session: Session, *, tickers: list[str]) -> dict[str, PortfolioQuote]:
    """Return a map of upper-cased ticker -> row for the rows that exist.

    Missing tickers are absent from the result (not present with a ``None``
    value) so callers can distinguish "no quote yet" from "row exists with
    null price".
    """
    if not tickers:
        return {}
    cleaned = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not cleaned:
        return {}
    rows = (
        session.execute(select(PortfolioQuote).where(PortfolioQuote.ticker.in_(cleaned)))
        .scalars()
        .all()
    )
    return {r.ticker: r for r in rows}
