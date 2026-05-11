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
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import (
    PortfolioHolding,
    PortfolioQuoteDaily,
)

_GROUPS_META_TICKER = "__GROUPS__"


@dataclass(frozen=True)
class ValuePoint:
    date: date
    value: Decimal


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
    session: Session, user_id: str
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
    return [h for h in rows if h.shares is not None]


def compute_value_series(
    session: Session,
    *,
    user_id: str,
    timeframe: str,
    today: date,
) -> ValueSeries:
    holdings = _holdings_for_user(session, user_id)
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
    daily_rows = (
        session.execute(
            select(
                PortfolioQuoteDaily.ticker,
                PortfolioQuoteDaily.trade_date,
                PortfolioQuoteDaily.close,
            ).where(
                PortfolioQuoteDaily.ticker.in_(tickers),
                PortfolioQuoteDaily.trade_date >= actual_start,
                PortfolioQuoteDaily.trade_date <= actual_end,
            )
        )
        .all()
    )

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
            period_return_pct = (period_return_abs / start_val).quantize(
                Decimal("0.0001")
            )

    return ValueSeries(
        timeframe=timeframe,
        actual_span=span,
        points=points,
        period_return_abs=period_return_abs,
        period_return_pct=period_return_pct,
    )
