"""Compute the portfolio value time series for the top-of-page chart.

For each day ``t`` in ``[max(picker_start, earliest_holding.added_at), today]``,
``value(t) = sum_i(sharesᵢ_current * closeᵢ(t))`` over holdings whose
``added_at <= t``. See ``planning/specs/systems/portfolio-live-data-design.md``
§8 for the full math + honest-within-data-model limitations.

Single-currency only in v1 (Phase 5 will layer FX on top). When holdings
span multiple currencies we still sum naively here; the route layer is
responsible for detecting that and either applying current spot FX or
falling back to per-currency display.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import (
    PortfolioHolding,
    PortfolioQuoteDaily,
    PortfolioQuoteIntraday,
)
from openlia_server.services.market_hours import Market, classify_market

_GROUPS_META_TICKER = "__GROUPS__"


@dataclass(frozen=True)
class ValuePoint:
    date: date
    value: Decimal
    ts: datetime | None = None


@dataclass(frozen=True)
class ActualSpan:
    start: date
    end: date


@dataclass(frozen=True)
class ValueSeries:
    timeframe: str
    actual_span: ActualSpan | None
    points: list[ValuePoint]
    period_return_abs: Decimal | None
    period_return_pct: Decimal | None


def resolve_window(timeframe: str, today: date) -> date:
    """Map a timeframe string to the requested start date (un-clamped).

    Recognises ``1d, 1w, 1m, 3m, 6m, ytd, 1y, 5y``. Unknown values fall
    back to 1m so the route never 5xx's on an unexpected query param.
    """
    tf = timeframe.lower()
    if tf == "1d":
        return today - timedelta(days=1)
    if tf == "1w":
        return today - timedelta(days=7)
    if tf == "1m":
        return today - timedelta(days=30)
    if tf == "3m":
        return today - timedelta(days=90)
    if tf == "6m":
        return today - timedelta(days=180)
    if tf == "ytd":
        return date(today.year, 1, 1)
    if tf == "1y":
        return today - timedelta(days=365)
    if tf == "5y":
        return today - timedelta(days=365 * 5)
    return today - timedelta(days=30)


def _holdings_for_user(
    session: Session, user_id: str, market: Market | None = None
) -> list[PortfolioHolding]:
    rows = (
        session.execute(
            select(PortfolioHolding)
            .where(
                PortfolioHolding.user_id == user_id,
                PortfolioHolding.ticker != _GROUPS_META_TICKER,
            )
            .order_by(PortfolioHolding.ticker)
        )
        .scalars()
        .all()
    )
    # Only holdings with a share count contribute to the value chart.
    contributing = [h for h in rows if h.shares is not None]
    if market is None:
        return contributing
    return [h for h in contributing if classify_market(h.ticker) == market]


def compute_value_series(
    session: Session,
    *,
    user_id: str,
    timeframe: str,
    today: date,
    market: Market | None = None,
) -> ValueSeries:
    holdings = _holdings_for_user(session, user_id, market=market)
    if not holdings:
        return ValueSeries(
            timeframe=timeframe,
            actual_span=None,
            points=[],
            period_return_abs=None,
            period_return_pct=None,
        )

    requested_start = resolve_window(timeframe, today)
    inception = min(h.added_at.date() for h in holdings)
    actual_start = max(requested_start, inception)
    actual_end = today
    if actual_end < actual_start:
        actual_end = actual_start
    span = ActualSpan(start=actual_start, end=actual_end)

    tickers = [h.ticker for h in holdings]
    daily_rows = session.execute(
        select(
            PortfolioQuoteDaily.ticker,
            PortfolioQuoteDaily.trade_date,
            PortfolioQuoteDaily.close,
        ).where(
            PortfolioQuoteDaily.ticker.in_(tickers),
            PortfolioQuoteDaily.trade_date >= actual_start,
            PortfolioQuoteDaily.trade_date <= actual_end,
        )
    ).all()

    # date -> ticker -> close
    closes: dict[date, dict[str, Decimal]] = {}
    all_dates: set[date] = set()
    for ticker, d, close in daily_rows:
        closes.setdefault(d, {})[ticker] = close
        all_dates.add(d)

    points: list[ValuePoint] = []
    for d in sorted(all_dates):
        value = Decimal("0")
        for h in holdings:
            if h.added_at.date() > d:
                continue
            close = closes.get(d, {}).get(h.ticker)
            if close is None or h.shares is None:
                continue
            value += h.shares * close
        points.append(ValuePoint(date=d, value=value))

    period_return_abs: Decimal | None = None
    period_return_pct: Decimal | None = None
    if len(points) >= 2:
        start_val = points[0].value
        end_val = points[-1].value
        period_return_abs = end_val - start_val
        if start_val != 0:
            period_return_pct = (period_return_abs / start_val).quantize(Decimal("0.0001"))

    return ValueSeries(
        timeframe=timeframe,
        actual_span=span,
        points=points,
        period_return_abs=period_return_abs,
        period_return_pct=period_return_pct,
    )


_INTRADAY_FALLBACK_LIMIT_DAYS = 14


def compute_value_series_intraday(
    session: Session,
    *,
    user_id: str,
    today: date,
    market: Market | None = None,
) -> ValueSeries:
    """Build a one-day intraday value series.

    Finds the most recent UTC date with any intraday rows for the user's
    tickers (up to ``_INTRADAY_FALLBACK_LIMIT_DAYS`` back), then emits one
    point per unique tick timestamp. Each point sums
    ``shares_i * last-known-price_i`` over holdings whose ``added_at <= ts``.

    Returns an empty series if no eligible intraday data exists.
    """
    holdings = _holdings_for_user(session, user_id, market=market)
    if not holdings:
        return ValueSeries(
            timeframe="1d",
            actual_span=None,
            points=[],
            period_return_abs=None,
            period_return_pct=None,
        )

    tickers = [h.ticker for h in holdings]
    earliest = today - timedelta(days=_INTRADAY_FALLBACK_LIMIT_DAYS)
    rows = session.execute(
        select(
            PortfolioQuoteIntraday.ticker,
            PortfolioQuoteIntraday.ts,
            PortfolioQuoteIntraday.close,
        )
        .where(
            PortfolioQuoteIntraday.ticker.in_(tickers),
            PortfolioQuoteIntraday.ts
            >= datetime(earliest.year, earliest.month, earliest.day, tzinfo=UTC),
        )
        .order_by(PortfolioQuoteIntraday.ts)
    ).all()
    if not rows:
        return ValueSeries(
            timeframe="1d",
            actual_span=None,
            points=[],
            period_return_abs=None,
            period_return_pct=None,
        )

    # Pick most recent UTC date with any row (data-driven trading day).
    most_recent = max(r.ts.date() for r in rows)
    day_rows = [r for r in rows if r.ts.date() == most_recent]

    # Build per-ticker price-walk: at each unique ts, use latest known price.
    unique_ts = sorted({r.ts for r in day_rows})
    by_ticker: dict[str, list[tuple[datetime, Decimal]]] = {}
    for r in day_rows:
        by_ticker.setdefault(r.ticker, []).append((r.ts, r.close))

    def latest_price_at(ticker: str, at: datetime) -> Decimal | None:
        series = by_ticker.get(ticker)
        if not series:
            return None
        last: Decimal | None = None
        for ts, close in series:
            if ts > at:
                break
            last = close
        return last

    points: list[ValuePoint] = []
    for ts in unique_ts:
        value = Decimal("0")
        contributed = False
        for h in holdings:
            if h.added_at > ts:
                continue
            price = latest_price_at(h.ticker, ts)
            if price is None or h.shares is None:
                continue
            value += h.shares * price
            contributed = True
        if contributed:
            points.append(ValuePoint(date=ts.date(), value=value, ts=ts))

    period_return_abs: Decimal | None = None
    period_return_pct: Decimal | None = None
    if len(points) >= 2:
        start_val = points[0].value
        end_val = points[-1].value
        period_return_abs = end_val - start_val
        if start_val != 0:
            period_return_pct = (period_return_abs / start_val).quantize(Decimal("0.0001"))

    return ValueSeries(
        timeframe="1d",
        actual_span=ActualSpan(start=most_recent, end=most_recent),
        points=points,
        period_return_abs=period_return_abs,
        period_return_pct=period_return_pct,
    )
