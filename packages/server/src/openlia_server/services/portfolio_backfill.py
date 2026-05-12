"""Backfill ``portfolio_quote_daily`` from the financial adapter.

Triggered async on ``POST /portfolio/holdings`` (5-year window) so newly
added tickers have enough daily history to power the portfolio value chart
and the per-ticker chart timeframes (1D through 5Y).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import PortfolioQuoteDaily

log = logging.getLogger(__name__)


class DailyHistoryProvider(Protocol):
    def fetch_daily_history(self, ticker: str, *, years: int) -> list[dict]:
        """Return a list of ``{date, open, high, low, close, volume}`` rows."""


def backfill_daily_history(
    session: Session,
    *,
    ticker: str,
    provider: DailyHistoryProvider,
    years: int = 5,
) -> int:
    """Fetch ``years`` of EOD history for ``ticker`` and upsert any missing
    rows into ``portfolio_quote_daily``.

    Idempotent: existing rows for a (ticker, trade_date) pair are left
    untouched. Returns the number of newly inserted rows.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        return 0

    try:
        rows = provider.fetch_daily_history(ticker, years=years)
    except Exception as exc:
        log.warning("portfolio backfill failed for %s: %s", ticker, exc)
        return 0

    if not rows:
        return 0

    existing = {
        d
        for (d,) in session.execute(
            select(PortfolioQuoteDaily.trade_date).where(
                PortfolioQuoteDaily.ticker == ticker
            )
        ).all()
    }

    inserted = 0
    for row in rows:
        trade_date = row.get("date")
        if trade_date is None or trade_date in existing:
            continue
        close = row.get("close")
        if close is None:
            continue
        session.add(
            PortfolioQuoteDaily(
                ticker=ticker,
                trade_date=trade_date,
                open=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=close,
                volume=row.get("volume"),
            )
        )
        inserted += 1

    if inserted > 0:
        session.commit()
    return inserted


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None or value == "" or value == "NA":
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "" or value == "NA":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


class AdapterDailyHistoryProvider:
    """Bridge a Plan 3 financial adapter ``eod_history`` capability to the
    sync DailyHistoryProvider contract used by :func:`backfill_daily_history`.
    """

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    def fetch_daily_history(self, ticker: str, *, years: int) -> list[dict]:
        import asyncio

        if self._adapter is None:
            return []
        from_date = (datetime.now(UTC).date() - timedelta(days=int(365 * years)))
        try:
            result = asyncio.run(
                self._adapter.fetch(
                    "eod_history",
                    {"symbol": ticker.upper(), "from": from_date.isoformat()},
                )
            )
        except Exception as exc:
            log.warning("eod_history fetch failed for %s: %s", ticker, exc)
            return []

        payload = getattr(result, "payload", None)
        if payload is None:
            return []
        if isinstance(payload, dict):
            payload = payload.get("series") or payload.get("data") or []
        if not isinstance(payload, list):
            return []

        out: list[dict] = []
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            d = raw.get("date")
            if isinstance(d, str):
                try:
                    d_parsed = date.fromisoformat(d)
                except ValueError:
                    continue
            elif isinstance(d, date):
                d_parsed = d
            else:
                continue
            close = _coerce_decimal(raw.get("close") or raw.get("adjusted_close"))
            if close is None:
                continue
            out.append(
                {
                    "date": d_parsed,
                    "open": _coerce_decimal(raw.get("open")),
                    "high": _coerce_decimal(raw.get("high")),
                    "low": _coerce_decimal(raw.get("low")),
                    "close": close,
                    "volume": _coerce_int(raw.get("volume")),
                }
            )
        return out
