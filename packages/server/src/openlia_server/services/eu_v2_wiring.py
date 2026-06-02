"""EODHD data-transport wiring for the EU v2 engine.

Mirrors ``v3_wiring.py`` but returns an ``EuDataTransports`` bundle that
includes the additional ``earnings_calendar`` callable, backed by the EODHD
SDK's upcoming-earnings endpoint.

``build_eu_v2_transports`` reads ``EODHD_API_KEY`` and returns an
``EuDataTransports`` bundle, or ``None`` when the key is unset.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from openlia.connectors.types import ConnectorStatus
from openlia.llm.runtime.report_eu import EuDataTransports
from sqlalchemy.orm import Session

from .eodhd_payload import trim_eodhd_fundamentals

log = logging.getLogger(__name__)

# EODHD's upcoming-earnings endpoint defaults to a narrow ~7-day window when
# no dates are given, so a ticker reporting later returns no events. Query a
# forward quarter to reliably capture each watchlist ticker's next release.
_EARNINGS_LOOKAHEAD_DAYS = 90


def build_eu_v2_transports(api_key: str | None = None) -> EuDataTransports | None:
    """Build EODHD-backed transports for the EU v2 runner.

    Uses ``api_key`` when provided (e.g. resolved from an installed
    connector), else falls back to ``EODHD_API_KEY``. Returns ``None``
    when neither yields a key so the runner uses its loud null fallback.
    """
    key = api_key or os.getenv("EODHD_API_KEY")
    if not key:
        log.info("EODHD_API_KEY unset; EU v2 data tools will return a not-configured error.")
        return None

    from eodhd import APIClient

    client = APIClient(api_key=key)

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

    def earnings_calendar(ticker: str) -> list[dict[str, Any]]:
        symbol = ticker if "." in ticker else f"{ticker}.US"
        today = datetime.now(UTC).date()
        result = client.get_upcoming_earnings_data(
            from_date=today.isoformat(),
            to_date=(today + timedelta(days=_EARNINGS_LOOKAHEAD_DAYS)).isoformat(),
            symbols=symbol,
        )
        # EODHD returns {"type", "description", "symbols", "earnings": [...]};
        # the event dicts live under "earnings", not at the top level.
        events = result.get("earnings", []) if isinstance(result, dict) else []
        return list(events)

    return EuDataTransports(
        fundamentals=fundamentals,
        prices=prices,
        news=news,
        earnings_calendar=earnings_calendar,
    )


def resolve_eodhd_api_key(db: Session) -> str | None:
    """Resolve the EODHD key from env first, then an installed connector.

    Falls back to the ``secrets["EODHD_API_KEY"]`` of the first
    ``validated`` connector with ``provider_id == "eodhd"`` so an
    EODHD connector installed through the Connectors UI is usable by
    the report engine (whose transports otherwise read env only).
    """
    env = os.getenv("EODHD_API_KEY")
    if env:
        return env
    from openlia_server.services import connectors_service

    for connector in connectors_service.list_connectors(db):
        if connector.provider_id == "eodhd" and connector.status == ConnectorStatus.VALIDATED.value:
            key = (connector.secrets or {}).get("EODHD_API_KEY")
            if key:
                return key
    return None


__all__ = ["build_eu_v2_transports", "resolve_eodhd_api_key"]
