"""EODHD data-transport wiring for the v3 engine.

The v3 runner's data tools (``get_fundamentals`` / ``get_historical_prices``
/ ``get_company_news``) call transport callables the wiring layer
supplies. Keeping the ``eodhd`` SDK import here keeps the core package
free of it.

``build_v3_transports`` reads ``EODHD_API_KEY`` and returns a
``DataTransports`` bundle, or ``None`` when the key is unset. The routes
pass ``None`` straight through to the runner, which falls back to
NullToolExecutor transports — the model still sees the data tools but
every call returns a clear "not configured" error instead of silently
missing the capability.

Fundamentals payloads are trimmed via the v2.3 helper so the model
isn't billed for the full multi-year EODHD dump on every call.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openlia.llm.runtime.report_v3 import DataTransports

from .eodhd_payload import trim_eodhd_fundamentals

log = logging.getLogger(__name__)


def build_v3_transports() -> DataTransports | None:
    """Build EODHD-backed transports for the v3 runner.

    Returns ``None`` when ``EODHD_API_KEY`` is unset so the runner uses
    its loud null fallback.
    """
    api_key = os.getenv("EODHD_API_KEY")
    if not api_key:
        log.info("EODHD_API_KEY unset; v3 data tools will return a not-configured error.")
        return None

    from eodhd import APIClient

    client = APIClient(api_key=api_key)

    def fundamentals(ticker: str) -> dict[str, Any]:
        raw = client.get_fundamentals_data(ticker)
        if isinstance(raw, dict):
            payload = raw
        elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
            payload = raw[0]
        else:
            return {"value": raw}
        return trim_eodhd_fundamentals(payload)

    def prices(ticker: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
        rows = client.get_eod_historical_stock_market_data(
            symbol=ticker, period="d", from_date=from_date, to_date=to_date
        )
        return list(rows) if rows else []

    def news(ticker: str, limit: int) -> list[dict[str, Any]]:
        rows = client.financial_news(s=ticker, limit=limit)
        return list(rows) if rows else []

    return DataTransports(fundamentals=fundamentals, prices=prices, news=news)


__all__ = ["build_v3_transports"]
