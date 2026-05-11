"""Scheduler tick body for portfolio quote refresh.

Pure, synchronous, DB-bound — keeps the APScheduler executor thin and lets
the wake-up sweep on server start reuse the same code path. The provider
protocol is a single ``fetch_quote(ticker) -> dict | None`` call so the
production wiring (over ``app.state.financial_adapter``) can be substituted
with a recording fake in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.config import UserPrefs
from openlia_server.db.models.content import (
    PortfolioHolding,
    PortfolioQuoteDaily,
    PortfolioQuoteIntraday,
)
from openlia_server.services import portfolio_quotes as quotes_svc
from openlia_server.services.market_hours import is_market_open
from openlia_server.services.portfolio_prefs import cadence_seconds

log = logging.getLogger(__name__)

# Mirror the sentinel in services/portfolio.py without importing it (avoids a
# circular dep at import time).
_GROUPS_META_TICKER = "__GROUPS__"

# How long since a fetch counts as "fresh enough" to skip even when the
# market is closed. 72h covers a normal Friday-close-through-Sunday gap
# with margin; longer outages still trigger a refetch on next market day.
_CLOSED_MARKET_GRACE = timedelta(hours=72)


class QuoteProvider(Protocol):
    """Synchronous wrapper around the financial adapter's ``stock_quote`` call."""

    def fetch_quote(self, ticker: str) -> dict | None:
        """Return a dict with keys matching ``upsert_quote`` kwargs, or ``None``
        on provider failure / unavailable data. The implementor is responsible
        for setting ``source`` so the upsert row records the connector id."""


@dataclass(frozen=True)
class RefreshResult:
    fetched: int
    skipped_fresh: int
    skipped_market_closed: int
    failed: int


def union_of_tracked_tickers(session: Session) -> list[str]:
    """Distinct, upper-cased tickers across every user's holdings.

    The hidden ``__GROUPS__`` pseudo-row used to persist group ordering is
    excluded. Returned in sorted order for deterministic test output.
    """
    rows = (
        session.execute(
            select(PortfolioHolding.ticker)
            .where(PortfolioHolding.ticker != _GROUPS_META_TICKER)
            .distinct()
        )
        .scalars()
        .all()
    )
    return sorted({t.upper() for t in rows if t})


def scheduler_union(session: Session) -> list[tuple[str, int]]:
    """Return ``[(ticker, min_cadence_s), ...]`` for every ticker held by at
    least one user with a polling cadence.

    Floor semantics: a ticker held by users with cadences (weekly, hourly)
    contributes one row with ``min_cadence_s = 3600`` (the hourly user's
    floor). Tickers held only by ``manual`` users are excluded — the
    manual-refresh button is their only fetch path.
    """
    rows = session.execute(
        select(PortfolioHolding.user_id, PortfolioHolding.ticker).where(
            PortfolioHolding.ticker != _GROUPS_META_TICKER
        )
    ).all()
    if not rows:
        return []

    user_ids = {uid for uid, _ in rows}
    prefs_rows = (
        session.execute(select(UserPrefs).where(UserPrefs.user_id.in_(user_ids))).scalars().all()
    )
    cadence_by_user = {p.user_id: p.portfolio_refresh_cadence for p in prefs_rows}

    # Per ticker, take the smallest non-None cadence across its holders.
    floor_by_ticker: dict[str, int] = {}
    for uid, ticker in rows:
        if not ticker:
            continue
        cadence = cadence_by_user.get(uid, "daily")
        secs = cadence_seconds(cadence)
        if secs is None:
            continue  # manual user contributes nothing to the polling union
        t_upper = ticker.upper()
        existing = floor_by_ticker.get(t_upper)
        if existing is None or secs < existing:
            floor_by_ticker[t_upper] = secs

    return sorted(floor_by_ticker.items())


def refresh_due_quotes(
    session: Session,
    *,
    provider: QuoteProvider,
    now_utc: datetime,
    min_cadence_seconds: int | None = None,
) -> RefreshResult:
    """Fetch and upsert quotes for any ticker that has aged past its cadence.

    Each ticker's cadence is the *floor* across all polling users holding it
    (see :func:`scheduler_union`). When ``min_cadence_seconds`` is supplied,
    it overrides the per-ticker cadence for every ticker — this exists for
    targeted tests; production callers should leave it None.

    Skips:
      - tickers fresher than their cadence floor (cache-hit)
      - tickers whose home market is closed AND whose existing quote is
        younger than 72h (covers normal weekends)

    Provider errors degrade per-ticker without aborting the rest of the tick.
    """
    union = scheduler_union(session)
    cached = quotes_svc.get_quotes_bulk(session, tickers=[t for t, _ in union])

    fetched = 0
    skipped_fresh = 0
    skipped_market_closed = 0
    failed = 0

    for ticker, ticker_cadence_s in union:
        effective_cadence = (
            min_cadence_seconds if min_cadence_seconds is not None else ticker_cadence_s
        )
        row = cached.get(ticker)
        age = now_utc - row.fetched_at if row is not None else None

        if age is not None and age.total_seconds() < effective_cadence:
            skipped_fresh += 1
            continue

        market_open = is_market_open(ticker, now_utc)
        if not market_open and age is not None and age < _CLOSED_MARKET_GRACE:
            skipped_market_closed += 1
            continue

        try:
            payload = provider.fetch_quote(ticker)
        except Exception as exc:
            log.warning("portfolio quote fetch failed for %s: %s", ticker, exc)
            failed += 1
            continue

        if payload is None:
            failed += 1
            continue

        quotes_svc.upsert_quote(
            session,
            ticker=ticker,
            last_price=payload.get("last_price"),
            previous_close=payload.get("previous_close"),
            day_open=payload.get("day_open"),
            day_high=payload.get("day_high"),
            day_low=payload.get("day_low"),
            volume=payload.get("volume"),
            currency=payload.get("currency"),
            quote_at=payload.get("quote_at"),
            fetched_at=payload.get("fetched_at") or now_utc,
            source=payload.get("source", "unknown"),
        )
        # Append today's daily row if missing. Post-close fires overwrite
        # the close with the canonical value; intra-session fires leave any
        # existing canonical row untouched.
        last_price = payload.get("last_price")
        if last_price is not None:
            _upsert_today_daily(
                session,
                ticker=ticker,
                today=now_utc.date(),
                close=last_price,
                day_open=payload.get("day_open"),
                day_high=payload.get("day_high"),
                day_low=payload.get("day_low"),
                volume=payload.get("volume"),
            )
            # Scheduler-tick-as-points: one row per refresh into the
            # intraday table. Resolution scales with the user's cadence
            # (Hourly → ~7 points/session; Weekly → ~0-1).
            session.add(PortfolioQuoteIntraday(ticker=ticker, ts=now_utc, close=last_price))
            session.commit()
        fetched += 1

    return RefreshResult(
        fetched=fetched,
        skipped_fresh=skipped_fresh,
        skipped_market_closed=skipped_market_closed,
        failed=failed,
    )


def _upsert_today_daily(
    session: Session,
    *,
    ticker: str,
    today,  # date
    close: Decimal,
    day_open: Decimal | None,
    day_high: Decimal | None,
    day_low: Decimal | None,
    volume: int | None,
) -> None:
    """Idempotent: insert a daily row for ``today`` if missing, else update
    the high/low/close from the latest tick (intraday updates extend the
    range)."""
    row = session.get(PortfolioQuoteDaily, (ticker, today))
    if row is None:
        session.add(
            PortfolioQuoteDaily(
                ticker=ticker,
                trade_date=today,
                open=day_open,
                high=day_high,
                low=day_low,
                close=close,
                volume=volume,
            )
        )
    else:
        # Update close to the latest known print; widen high/low if needed.
        row.close = close
        if day_high is not None and (row.high is None or day_high > row.high):
            row.high = day_high
        if day_low is not None and (row.low is None or day_low < row.low):
            row.low = day_low
        if volume is not None:
            row.volume = volume
    session.commit()


def _coerce_price(payload: object) -> Decimal | None:
    """Mirror of services/portfolio_prices._coerce_price for callers that
    have a raw provider payload but no quote dict yet. Used by the production
    QuoteProvider wrapper in app.py."""
    from openlia_server.services.portfolio_prices import _coerce_price as _impl

    return _impl(payload)
