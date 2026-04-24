"""Tests for PriceCache — TTL + cooldown + error fallback."""

from __future__ import annotations

from decimal import Decimal

from openlia_server.services.portfolio_prices import PriceCache


class _FakeProvider:
    def __init__(self, prices: dict[str, Decimal | None]) -> None:
        self.prices = prices
        self.calls = 0

    def get_price(self, ticker: str) -> Decimal | None:
        self.calls += 1
        return self.prices.get(ticker.upper())


class _RaisingProvider:
    def get_price(self, ticker: str) -> Decimal | None:
        raise RuntimeError("boom")


def test_fetch_many_returns_prices_and_caches() -> None:
    cache = PriceCache()
    provider = _FakeProvider({"AAPL": Decimal("150")})
    first = cache.fetch_many(provider, ["AAPL"])
    assert first == {"AAPL": Decimal("150")}
    assert provider.calls == 1

    # Second call hits cache
    second = cache.fetch_many(provider, ["AAPL"])
    assert second == {"AAPL": Decimal("150")}
    assert provider.calls == 1


def test_fetch_many_handles_provider_exception() -> None:
    cache = PriceCache()
    result = cache.fetch_many(_RaisingProvider(), ["AAPL"])
    assert result == {"AAPL": None}


def test_cooldown_tracks_per_user() -> None:
    cache = PriceCache(cooldown_seconds=30)
    assert cache.refresh_cooldown_remaining("u1") == 0.0
    cache.mark_refresh("u1")
    assert cache.refresh_cooldown_remaining("u1") > 0
    assert cache.refresh_cooldown_remaining("u2") == 0.0
