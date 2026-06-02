"""EODHD market-data transport wiring for the Morning Briefing engine.

Mirrors ``eu_v2_wiring.py`` but returns an ``MbDataTransports`` bundle:
the Morning Briefing tools are market-wide rather than single-ticker, so
the five callables back the multi-ticker quotes, historical prices,
market/symbol news, economic calendar, and macro-indicator tools.

``build_mb_transports`` reads ``EODHD_API_KEY`` (or an explicit key
resolved from an installed connector) and returns an ``MbDataTransports``
bundle, or ``None`` when no key is available so the runner uses its loud
null fallback.

The EODHD-key resolution itself is shared with the EU engine: this module
re-exports ``resolve_eodhd_api_key`` from ``eu_v2_wiring`` rather than
duplicating it.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from openlia.llm.runtime.report_mb import MbDataTransports

from .eu_v2_wiring import resolve_eodhd_api_key

log = logging.getLogger(__name__)

# Default country (Alpha-3 ISO) for EODHD's sovereign macro-indicators
# endpoint. The MB macro tool keys are passed through as the EODHD
# ``indicator`` name (e.g. ``inflation_consumer_prices_annual``); a key
# of the form ``XXX:indicator`` overrides the country for that reading.
_DEFAULT_MACRO_COUNTRY = "USA"

# How many EOD bars a price-range token resolves to. Daily bars only, so
# these are trading-day-agnostic calendar-day lookbacks (slightly long on
# purpose — EODHD simply returns the bars that exist in the window).
_RANGE_LOOKBACK_DAYS: dict[str, int] = {
    "5d": 7,
    "1w": 7,
    "1mo": 31,
    "1m": 31,
    "3mo": 93,
    "3m": 93,
    "6mo": 186,
    "6m": 186,
    "1y": 366,
    "ytd": 366,
    "2y": 731,
    "5y": 1827,
}
_DEFAULT_RANGE_DAYS = 31

# Economic-calendar window tokens -> forward lookahead in days from today.
_CALENDAR_WINDOW_DAYS: dict[str, int] = {
    "today": 0,
    "tomorrow": 1,
    "this_week": 7,
    "week": 7,
    "next_week": 14,
    "this_month": 31,
    "month": 31,
}
_DEFAULT_CALENDAR_DAYS = 7


def build_mb_transports(api_key: str | None = None) -> MbDataTransports | None:
    """Build EODHD-backed transports for the Morning Briefing runner.

    Uses ``api_key`` when provided (e.g. resolved from an installed
    connector), else falls back to ``EODHD_API_KEY``. Returns ``None``
    when neither yields a key so the runner uses its loud null fallback.
    """
    key = api_key or os.getenv("EODHD_API_KEY")
    if not key:
        log.info("EODHD_API_KEY unset; MB data tools will return a not-configured error.")
        return None

    from eodhd import APIClient

    client = APIClient(api_key=key)

    def quotes(tickers: list[str]) -> list[dict[str, Any]]:
        if not tickers:
            return []
        # EODHD's real-time endpoint takes one primary ``ticker`` plus a
        # comma-joined ``s`` list of secondaries; a single ticker yields a
        # dict, a multi-ticker call yields a list.
        primary, *rest = tickers
        secondaries = ",".join(rest) if rest else None
        raw = client.get_live_stock_prices(ticker=primary, s=secondaries)
        if isinstance(raw, list):
            return list(raw)
        if isinstance(raw, dict):
            return [raw]
        return []

    def prices(ticker: str, price_range: str) -> list[dict[str, Any]]:
        days = _RANGE_LOOKBACK_DAYS.get(price_range.strip().lower(), _DEFAULT_RANGE_DAYS)
        today = datetime.now(UTC).date()
        rows = client.get_eod_historical_stock_market_data(
            symbol=ticker,
            period="d",
            from_date=(today - timedelta(days=days)).isoformat(),
            to_date=today.isoformat(),
        )
        return list(rows) if rows else []

    def news(symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        rows = client.financial_news(s=symbol, limit=limit)
        return list(rows) if rows else []

    def economic_calendar(window: str) -> list[dict[str, Any]]:
        days = _CALENDAR_WINDOW_DAYS.get(window.strip().lower(), _DEFAULT_CALENDAR_DAYS)
        today = datetime.now(UTC).date()
        rows = client.get_economic_events_data(
            date_from=today.isoformat(),
            date_to=(today + timedelta(days=days)).isoformat(),
        )
        return list(rows) if rows else []

    def macro_indicators(keys: list[str]) -> dict[str, Any]:
        # EODHD's macro endpoint serves sovereign macroeconomic series
        # keyed by country (ISO-3) + indicator name. Each requested key is
        # passed through as the EODHD ``indicator`` (optionally prefixed
        # ``COUNTRY:indicator``); the reading is filed back under the
        # original key so the model can cite what it asked for.
        out: dict[str, Any] = {}
        for key in keys:
            country, _, indicator = key.partition(":")
            if indicator:
                country = country.strip().upper() or _DEFAULT_MACRO_COUNTRY
            else:
                indicator = country
                country = _DEFAULT_MACRO_COUNTRY
            rows = client.get_macro_indicators_data(
                country=country, indicator=indicator.strip() or None
            )
            out[key] = list(rows) if rows else []
        return out

    return MbDataTransports(
        quotes=quotes,
        prices=prices,
        news=news,
        economic_calendar=economic_calendar,
        macro_indicators=macro_indicators,
    )


__all__ = ["build_mb_transports", "resolve_eodhd_api_key"]
