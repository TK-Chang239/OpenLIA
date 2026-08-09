"""EODHD-backed data dispatcher for the Panic Thermometer department.

``PtRunner`` drives each panel by asking a ``DataDispatcher`` to ``fetch`` a
named *requirement* (``historical_prices``, ``stock_quote``,
``economic_events``, ``company_news``). Until now the app installed a no-op
dispatcher, so every panel computed from empty payloads. This module wires a
real dispatcher onto the same EODHD client the Morning Briefing and Earnings
Update engines already use.

Design notes:
- The key is resolved *lazily* on each fetch (env first, then an installed
  EODHD connector) so a key added through the Connectors UI takes effect
  without a restart — the dashboard endpoint is request-scoped, unlike the
  scheduler-driven engines that resolve once per run.
- Every requirement normalizes EODHD's raw field names into the shapes the
  core panels consume (``price``/``previous_close``, ``event_name``,
  ``headline``/``summary``). See ``packages/core/.../panic_thermometer/panels``.
- A missing key or any fetch error returns ``None`` so panels degrade to a
  warning rather than raising.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from .eu_v2_wiring import resolve_eodhd_api_key

log = logging.getLogger(__name__)

# Price history lookback when a panel does not specify one, in months.
_PRICE_LOOKBACK_DEFAULT_MONTHS = 6
# Economic-calendar history window. EODHD caps the endpoint at 1000 rows
# ordered oldest-first, so a wide window silently truncates the *recent*
# releases the panels need. ~70 days of US events stays under the cap while
# still covering the latest monthly prints (Michigan survey, AHE) and the
# last FOMC meeting. The wage panel's longer history is reduced accordingly.
_ECON_EVENTS_LOOKBACK_DAYS = 70
_ECON_EVENTS_LIMIT = 1000
_NEWS_LIMIT_DEFAULT = 50
# News tag used when a panel supplies no ``news_search_tags`` (e.g. the
# diplomacy panel), so its keyword scanner still has a relevant pool.
_DEFAULT_NEWS_TAG = "geopolitics"
_EODHD_NEWS_URL = "https://eodhd.com/api/news"
_NEWS_TIMEOUT_SECONDS = 20.0


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ticker_from_params(params: dict[str, Any]) -> str | None:
    """Oil configs carry ``ticker``; inflation configs carry ``primary_ticker``."""
    return params.get("ticker") or params.get("primary_ticker")


def _source_from_link(link: str | None) -> str:
    if not link:
        return ""
    try:
        return urlparse(link).netloc
    except Exception:
        return ""


def _default_client_factory(api_key: str) -> Any:
    from eodhd import APIClient

    return APIClient(api_key=api_key)


def _default_news_fetcher(api_key: str, tag: str, limit: int) -> list[dict[str, Any]]:
    """Fetch EODHD news for a topic ``tag`` via the REST endpoint.

    The bundled ``eodhd`` SDK only permits a fixed whitelist of corporate
    finance tags, so it cannot fetch the policy/geopolitics topics the PT news
    panels need. The REST endpoint accepts arbitrary tags, so call it directly
    with an explicit timeout.
    """
    import requests

    resp = requests.get(
        _EODHD_NEWS_URL,
        params={"api_token": api_key, "t": tag, "limit": limit, "fmt": "json"},
        timeout=_NEWS_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    return list(data) if isinstance(data, list) else []


class EodhdPtDispatcher:
    """Panic Thermometer ``DataDispatcher`` backed by EODHD.

    Satisfies the ``DataDispatcher`` protocol in ``services.pt_runner``:
    ``fetch(*, requirement, panel_id, params) -> Any``.
    """

    def __init__(
        self,
        *,
        key_resolver: Callable[[], str | None],
        client_factory: Callable[[str], Any] = _default_client_factory,
        news_fetcher: Callable[[str, str, int], list[dict[str, Any]]] = _default_news_fetcher,
    ) -> None:
        self._key_resolver = key_resolver
        self._client_factory = client_factory
        self._news_fetcher = news_fetcher
        self._cached_key: str | None = None
        self._cached_client: Any = None

    def _client(self) -> Any | None:
        key = self._key_resolver()
        if not key:
            return None
        if key != self._cached_key:
            self._cached_client = self._client_factory(key)
            self._cached_key = key
        return self._cached_client

    def fetch(self, *, requirement: str, panel_id: str, params: dict[str, Any]) -> Any:
        client = self._client()
        if client is None:
            return None
        params = params or {}
        try:
            if requirement == "historical_prices":
                return self._historical_prices(client, params)
            if requirement == "stock_quote":
                return self._stock_quote(client, params)
            if requirement == "economic_events":
                return self._economic_events(client)
            if requirement == "company_news":
                return self._company_news(params)
        except Exception as exc:  # degrade to a panel warning rather than raising
            log.warning("PT EODHD fetch failed (%s/%s): %s", panel_id, requirement, exc)
            return None
        log.debug("PT dispatcher: unhandled requirement %r for panel %s", requirement, panel_id)
        return None

    def _historical_prices(self, client: Any, params: dict[str, Any]) -> list[dict[str, Any]]:
        ticker = _ticker_from_params(params)
        if not ticker:
            return []
        months = int(
            params.get("history_lookback_months")
            or params.get("tip_lookback_months")
            or _PRICE_LOOKBACK_DEFAULT_MONTHS
        )
        today = datetime.now(UTC).date()
        rows = client.get_eod_historical_stock_market_data(
            symbol=ticker,
            period="d",
            from_date=(today - timedelta(days=months * 31)).isoformat(),
            to_date=today.isoformat(),
        )
        return list(rows) if rows else []

    def _stock_quote(self, client: Any, params: dict[str, Any]) -> dict[str, Any] | None:
        ticker = _ticker_from_params(params)
        if not ticker:
            return None
        raw = client.get_live_stock_prices(ticker=ticker)
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if not isinstance(raw, dict):
            return None
        return {
            "price": _to_float(raw.get("close")),
            "previous_close": _to_float(raw.get("previousClose")),
            "high": _to_float(raw.get("high")),
            "low": _to_float(raw.get("low")),
        }

    def _economic_events(self, client: Any) -> list[dict[str, Any]]:
        today = datetime.now(UTC).date()
        rows = client.get_economic_events_data(
            date_from=(today - timedelta(days=_ECON_EVENTS_LOOKBACK_DAYS)).isoformat(),
            date_to=today.isoformat(),
            country="US",
            limit=_ECON_EVENTS_LIMIT,
        )
        out: list[dict[str, Any]] = []
        for row in rows or []:
            out.append(
                {
                    "event_name": row.get("type"),
                    "date": row.get("date"),
                    "actual": _to_float(row.get("actual")),
                    "previous": _to_float(row.get("previous")),
                    "estimate": _to_float(row.get("estimate")),
                    # ``comparison`` (mom/yoy) disambiguates same-named releases
                    # that publish both a month-over-month and year-over-year
                    # figure (e.g. Average Hourly Earnings).
                    "comparison": row.get("comparison"),
                    "period": row.get("period"),
                    "country": row.get("country"),
                }
            )
        return out

    def _company_news(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        key = self._cached_key
        if not key:
            return []
        tags_raw = params.get("news_search_tags") or ""
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] or [_DEFAULT_NEWS_TAG]
        limit = int(params.get("news_limit", _NEWS_LIMIT_DEFAULT))
        collected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tag in tags:
            try:
                rows = self._news_fetcher(key, tag, limit)
            except Exception as exc:  # a bad tag must not kill the whole panel
                log.debug("PT news tag %r failed: %s", tag, exc)
                continue
            for row in rows or []:
                title = row.get("title") or ""
                if title in seen:
                    continue
                seen.add(title)
                collected.append(
                    {
                        "headline": title,
                        "summary": row.get("content") or "",
                        "date": row.get("date"),
                        "source": _source_from_link(row.get("link")),
                        "link": row.get("link"),
                    }
                )
        return collected


def build_pt_dispatcher(session_factory: Callable[[], Any]) -> EodhdPtDispatcher:
    """Build the EODHD-backed PT dispatcher with connector-aware key resolution."""

    def _resolve() -> str | None:
        db = session_factory()
        try:
            return resolve_eodhd_api_key(db)
        finally:
            close = getattr(db, "close", None)
            if callable(close):
                close()

    return EodhdPtDispatcher(key_resolver=_resolve)


__all__ = ["EodhdPtDispatcher", "build_pt_dispatcher"]
