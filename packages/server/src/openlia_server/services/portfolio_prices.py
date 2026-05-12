"""TTL-cached intraday price fetcher for Portfolio analytics + refresh.

The provider is a callable `PortfolioPriceProvider` that returns
``Decimal | None`` for a ticker (``None`` means "not available"); cache is
process-local and opt-in. Restarting drops the cache — that's intentional.

Production wiring: ``app.py`` builds an :class:`AdapterPriceProvider` from
``app.state.financial_adapter`` (a configured Plan 3 :class:`ProviderAdapter`
exposing ``stock_quote``). When no adapter is registered the factory falls
back to :class:`_NoopPriceProvider` with a warning log so the page degrades
gracefully (sparkline ``—``, price ``—``) rather than 5xx-ing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PortfolioPriceProvider(Protocol):
    def get_price(self, ticker: str) -> Decimal | None: ...


@dataclass
class _CachedQuote:
    price: Decimal | None
    fetched_at: float


@dataclass
class PriceCache:
    ttl_seconds: float = 60.0
    cooldown_seconds: float = 30.0
    _cache: dict[str, _CachedQuote] = field(default_factory=dict)
    _last_refresh_by_user: dict[str, float] = field(default_factory=dict)

    def _now(self) -> float:
        return time.monotonic()

    def get_cached(self, ticker: str) -> Decimal | None:
        ticker = ticker.upper()
        entry = self._cache.get(ticker)
        if entry is None:
            return None
        if self._now() - entry.fetched_at > self.ttl_seconds:
            return None
        return entry.price

    def set(self, ticker: str, price: Decimal | None) -> None:
        self._cache[ticker.upper()] = _CachedQuote(price=price, fetched_at=self._now())

    def invalidate(self, tickers: Iterable[str]) -> None:
        """Public force-refresh hook — drop cached entries for the given tickers."""
        for raw in tickers:
            self._cache.pop(raw.upper(), None)

    def refresh_cooldown_remaining(self, user_id: str) -> float:
        last = self._last_refresh_by_user.get(user_id)
        if last is None:
            return 0.0
        elapsed = self._now() - last
        return max(0.0, self.cooldown_seconds - elapsed)

    def mark_refresh(self, user_id: str) -> None:
        self._last_refresh_by_user[user_id] = self._now()

    def fetch_many(
        self,
        provider: PortfolioPriceProvider,
        tickers: list[str],
    ) -> dict[str, Decimal | None]:
        """Return a ticker -> price map, consulting the cache then the provider.

        Provider exceptions are treated as "price unavailable" (None).
        """
        result: dict[str, Decimal | None] = {}
        for raw in tickers:
            t = raw.upper()
            cached = self.get_cached(t)
            if cached is not None:
                result[t] = cached
                continue
            try:
                price = provider.get_price(t)
            except Exception:
                price = None
            self.set(t, price)
            result[t] = price
        return result


_GLOBAL_CACHE = PriceCache()


def get_default_cache() -> PriceCache:
    return _GLOBAL_CACHE


class _NoopPriceProvider:
    def get_price(self, ticker: str) -> Decimal | None:
        return None


def get_default_provider() -> PortfolioPriceProvider:
    return _NoopPriceProvider()


def _coerce_price(payload: Any) -> Decimal | None:
    """Best-effort extraction of a last-price scalar from a stock_quote payload.

    EODHD's `/real-time/{ticker}` returns a dict with a numeric `close`.
    We tolerate dict / list / scalar shapes and ignore the EODHD `"NA"` sentinel.
    """
    if payload is None:
        return None
    if isinstance(payload, list):
        if not payload:
            return None
        payload = payload[0]
    if isinstance(payload, dict):
        for key in ("close", "last", "price", "regularMarketPrice"):
            if key in payload:
                payload = payload[key]
                break
        else:
            return None
    if payload is None or payload == "" or payload == "NA":
        return None
    try:
        return Decimal(str(payload))
    except (InvalidOperation, ValueError, TypeError):
        return None


class AdapterPriceProvider:
    """Bridge a Plan 3 async ProviderAdapter into the sync get_price contract.

    Used as the production factory when ``app.state.financial_adapter`` is
    set. ``DataNotAvailable`` and any other adapter error degrades to ``None``
    so the cache stores the sentinel and the route returns 200 with null
    prices rather than 5xx.

    The ``source_id`` attribute reflects the connector that fulfilled the
    request and is recorded in the ``portfolio_quotes.source`` column.
    """

    source_id: str = "eodhd"

    def __init__(self, adapter: Any, *, source_id: str | None = None) -> None:
        self._adapter = adapter
        if source_id is not None:
            self.source_id = source_id

    def get_price(self, ticker: str) -> Decimal | None:
        try:
            result = asyncio.run(self._adapter.fetch("stock_quote", {"ticker": ticker.upper()}))
        except Exception as exc:
            logger.debug("portfolio price fetch failed for %s: %s", ticker, exc)
            return None
        payload = getattr(result, "payload", None)
        return _coerce_price(payload)
