"""Tests for the EODHD-backed quotes service used by the Overview overlay."""

from __future__ import annotations

from openlia.retail_sentiment import quotes as quotes_module
from openlia.retail_sentiment.quotes import QuoteBar, fetch_quotes


def test_returns_empty_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    assert fetch_quotes(ticker="TSM") == []


def test_normalizes_bare_ticker_to_us_exchange(monkeypatch):
    captured: dict[str, str] = {}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def get_eod_historical_stock_market_data(self, *, symbol, period, order):
            captured["symbol"] = symbol
            captured["period"] = period
            captured["order"] = order
            return [
                {"date": "2026-04-01", "adjusted_close": 100.0},
                {"date": "2026-04-02", "adjusted_close": 101.0},
            ]

    monkeypatch.setenv("EODHD_API_KEY", "test")
    monkeypatch.setattr(quotes_module, "ExtendedAPIClient", FakeClient, raising=False)
    # Ensure the lazy import inside fetch_quotes resolves to our fake.
    import sys

    fake_mod = type(sys)("openlia.data.eodhd_extended")
    fake_mod.ExtendedAPIClient = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openlia.data.eodhd_extended", fake_mod)

    bars = fetch_quotes(ticker="TSM", days=30)

    assert captured["symbol"] == "TSM.US"
    assert captured["period"] == "d"
    assert captured["order"] == "a"
    assert len(bars) == 2
    assert bars[0] == QuoteBar(
        date="2026-04-01", close=100.0, daily_change_pct=0.0, cumulative_pct=0.0
    )
    assert bars[1].cumulative_pct == 1.0
    assert bars[1].daily_change_pct == 1.0


def test_keeps_explicit_exchange_suffix(monkeypatch):
    captured: dict[str, str] = {}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def get_eod_historical_stock_market_data(self, *, symbol, period, order):
            captured["symbol"] = symbol
            return []

    monkeypatch.setenv("EODHD_API_KEY", "test")
    import sys

    fake_mod = type(sys)("openlia.data.eodhd_extended")
    fake_mod.ExtendedAPIClient = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openlia.data.eodhd_extended", fake_mod)

    fetch_quotes(ticker="2330.TW", days=30)
    assert captured["symbol"] == "2330.TW"


def test_returns_empty_on_upstream_error(monkeypatch):
    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def get_eod_historical_stock_market_data(self, **_: object):
            raise RuntimeError("upstream 500")

    monkeypatch.setenv("EODHD_API_KEY", "test")
    import sys

    fake_mod = type(sys)("openlia.data.eodhd_extended")
    fake_mod.ExtendedAPIClient = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openlia.data.eodhd_extended", fake_mod)

    assert fetch_quotes(ticker="TSM") == []
