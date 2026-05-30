"""EODHD data-transport wiring for the EU v2 engine.

Mirrors ``v3_wiring.py`` but returns an ``EuDataTransports`` bundle that
includes the additional ``earnings_calendar`` callable. The earnings-calendar
transport calls the v2.2 ``eodhd_upcoming_earnings`` helper so the core
package stays free of the EODHD SDK.

``build_eu_v2_transports`` reads ``EODHD_API_KEY`` and returns an
``EuDataTransports`` bundle, or ``None`` when the key is unset.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openlia.llm.runtime.report_eu import EuDataTransports

from .v2_3_wiring import _trim_eodhd_fundamentals

log = logging.getLogger(__name__)


def build_eu_v2_transports() -> EuDataTransports | None:
    """Build EODHD-backed transports for the EU v2 runner.

    Returns ``None`` when ``EODHD_API_KEY`` is unset so the runner uses
    its loud null fallback.
    """
    api_key = os.getenv("EODHD_API_KEY")
    if not api_key:
        log.info("EODHD_API_KEY unset; EU v2 data tools will return a not-configured error.")
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
        return _trim_eodhd_fundamentals(payload)

    def prices(ticker: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
        rows = client.get_eod_historical_stock_market_data(
            symbol=ticker, period="d", from_date=from_date, to_date=to_date
        )
        return list(rows) if rows else []

    def news(ticker: str, limit: int) -> list[dict[str, Any]]:
        rows = client.financial_news(s=ticker, limit=limit)
        return list(rows) if rows else []

    def earnings_calendar(ticker: str) -> list[dict[str, Any]]:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers.eodhd import (
            eodhd_upcoming_earnings,
        )

        payload = eodhd_upcoming_earnings.execute(ticker)
        return list(payload.get("upcoming_earnings", []))

    return EuDataTransports(
        fundamentals=fundamentals,
        prices=prices,
        news=news,
        earnings_calendar=earnings_calendar,
    )


__all__ = ["build_eu_v2_transports"]
