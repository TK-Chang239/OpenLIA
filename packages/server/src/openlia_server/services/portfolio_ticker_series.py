"""Per-ticker sparkline series for the bottom-picker chart timeframe.

For ``timeframe == "1d"`` we draw from ``portfolio_quote_intraday`` (scheduler
tick points). For longer ranges we draw from ``portfolio_quote_daily``.

Returned shape mirrors the design spec's response contract for
``GET /portfolio/ticker-series``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import (
    PortfolioHolding,
    PortfolioQuoteDaily,
    PortfolioQuoteIntraday,
)
from openlia_server.services.market_hours import Market, classify_market
from openlia_server.services.portfolio_value_series import resolve_window

_GROUPS_META_TICKER = "__GROUPS__"


@dataclass(frozen=True)
class TickerSeriesPoint:
    ts: str  # ISO datetime (intraday) or ISO date (daily)
    close: Decimal


@dataclass(frozen=True)
class TickerSeries:
    timeframe: str
    series: dict[str, list[TickerSeriesPoint]]
    period_change_pct: dict[str, Decimal | None]


def _user_tickers(session: Session, user_id: str, *, market: Market | None = None) -> list[str]:
    rows = (
        session.execute(
            select(PortfolioHolding.ticker).where(
                PortfolioHolding.user_id == user_id,
                PortfolioHolding.ticker != _GROUPS_META_TICKER,
            )
        )
        .scalars()
        .all()
    )
    tickers = {t.upper() for t in rows if t}
    if market is not None:
        tickers = {t for t in tickers if classify_market(t) == market}
    return sorted(tickers)


def compute_ticker_series(
    session: Session,
    *,
    user_id: str,
    timeframe: str,
    today: date,
    market: Market | None = None,
) -> TickerSeries:
    tickers = _user_tickers(session, user_id, market=market)
    if not tickers:
        return TickerSeries(timeframe=timeframe, series={}, period_change_pct={})

    series: dict[str, list[TickerSeriesPoint]] = {t: [] for t in tickers}

    if timeframe.lower() == "1d":
        cutoff = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
        rows = session.execute(
            select(
                PortfolioQuoteIntraday.ticker,
                PortfolioQuoteIntraday.ts,
                PortfolioQuoteIntraday.close,
            )
            .where(
                PortfolioQuoteIntraday.ticker.in_(tickers),
                PortfolioQuoteIntraday.ts >= cutoff,
            )
            .order_by(PortfolioQuoteIntraday.ts.asc())
        ).all()
        for ticker, ts, close in rows:
            series[ticker].append(TickerSeriesPoint(ts=ts.isoformat(), close=close))
    else:
        start = resolve_window(timeframe, today)
        rows = session.execute(
            select(
                PortfolioQuoteDaily.ticker,
                PortfolioQuoteDaily.trade_date,
                PortfolioQuoteDaily.close,
            )
            .where(
                PortfolioQuoteDaily.ticker.in_(tickers),
                PortfolioQuoteDaily.trade_date >= start,
                PortfolioQuoteDaily.trade_date <= today,
            )
            .order_by(PortfolioQuoteDaily.trade_date.asc())
        ).all()
        for ticker, d, close in rows:
            series[ticker].append(TickerSeriesPoint(ts=d.isoformat(), close=close))

    period_change: dict[str, Decimal | None] = {}
    for ticker, points in series.items():
        if len(points) < 2:
            period_change[ticker] = None
            continue
        first = points[0].close
        last = points[-1].close
        if first == 0:
            period_change[ticker] = None
        else:
            period_change[ticker] = ((last - first) / first).quantize(Decimal("0.0001"))

    return TickerSeries(timeframe=timeframe, series=series, period_change_pct=period_change)
