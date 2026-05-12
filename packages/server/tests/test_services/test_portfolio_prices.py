"""Tests for PriceCache + AdapterPriceProvider — TTL, cooldown, invalidate, dispatch."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from openlia_server.services.portfolio_prices import (
    AdapterPriceProvider,
    PriceCache,
    _coerce_price,
)


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

    second = cache.fetch_many(provider, ["AAPL"])
    assert second == {"AAPL": Decimal("150")}
    assert provider.calls == 1


def test_fetch_many_handles_provider_exception() -> None:
    cache = PriceCache()
    result = cache.fetch_many(_RaisingProvider(), ["AAPL"])
    assert result == {"AAPL": None}


def test_invalidate_drops_only_named_tickers() -> None:
    cache = PriceCache()
    cache.set("AAPL", Decimal("150"))
    cache.set("MSFT", Decimal("400"))
    cache.invalidate(["AAPL"])
    assert cache.get_cached("AAPL") is None
    assert cache.get_cached("MSFT") == Decimal("400")


def test_cooldown_tracks_per_user() -> None:
    cache = PriceCache(cooldown_seconds=30)
    assert cache.refresh_cooldown_remaining("u1") == 0.0
    cache.mark_refresh("u1")
    assert cache.refresh_cooldown_remaining("u1") > 0
    assert cache.refresh_cooldown_remaining("u2") == 0.0


# ---------- AdapterPriceProvider --------------------------------------------


class _ToolResult:
    def __init__(self, payload: Any) -> None:
        self.payload = payload


class _FakeAdapter:
    def __init__(self, payloads: dict[str, Any]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict]] = []

    async def fetch(self, capability: str, params: dict) -> _ToolResult:
        self.calls.append((capability, params))
        symbol = params["ticker"]
        return _ToolResult(self.payloads[symbol])


class _RaisingAdapter:
    async def fetch(self, capability: str, params: dict) -> _ToolResult:
        raise RuntimeError("data unavailable")


def test_adapter_provider_dispatches_stock_quote() -> None:
    adapter = _FakeAdapter({"AAPL": {"close": "150.0"}})
    provider = AdapterPriceProvider(adapter)
    assert provider.get_price("aapl") == Decimal("150.0")
    assert adapter.calls == [("stock_quote", {"ticker": "AAPL"})]


def test_adapter_provider_returns_none_on_error() -> None:
    provider = AdapterPriceProvider(_RaisingAdapter())
    assert provider.get_price("AAPL") is None


def test_adapter_provider_handles_list_payload() -> None:
    adapter = _FakeAdapter({"MSFT": [{"close": 400}]})
    provider = AdapterPriceProvider(adapter)
    assert provider.get_price("MSFT") == Decimal("400")


def test_adapter_provider_returns_none_for_na_sentinel() -> None:
    adapter = _FakeAdapter({"ZZZ": {"close": "NA"}})
    provider = AdapterPriceProvider(adapter)
    assert provider.get_price("ZZZ") is None


@pytest.mark.parametrize(
    "payload,expected",
    [
        (None, None),
        ("", None),
        ("NA", None),
        ({"close": "150.5"}, Decimal("150.5")),
        ({"last": 200}, Decimal("200")),
        ({"price": "300.25"}, Decimal("300.25")),
        ([{"close": 100}], Decimal("100")),
        ([], None),
        ({}, None),
        ({"unknown": 5}, None),
    ],
)
def test_coerce_price(payload: Any, expected: Decimal | None) -> None:
    assert _coerce_price(payload) == expected


def test_cache_dispatches_to_adapter_provider() -> None:
    """End-to-end: PriceCache.fetch_many over AdapterPriceProvider."""
    adapter = _FakeAdapter({"AAPL": {"close": "150.0"}})
    provider = AdapterPriceProvider(adapter)
    cache = PriceCache()
    out = cache.fetch_many(provider, ["AAPL"])
    assert out == {"AAPL": Decimal("150.0")}
    # Cache hit on second call — adapter not re-invoked.
    cache.fetch_many(provider, ["AAPL"])
    assert len(adapter.calls) == 1
