"""TTL-cached intraday price fetcher for Portfolio analytics + refresh.

The provider is a callable `PortfolioPriceProvider` that returns
``Decimal | None`` for a ticker (``None`` means "not available"); cache is
process-local and opt-in. Restarting drops the cache — that's intentional.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol


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
