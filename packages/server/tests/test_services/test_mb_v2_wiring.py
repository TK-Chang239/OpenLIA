# packages/server/tests/test_services/test_mb_v2_wiring.py
from __future__ import annotations

import sys
import types

from openlia_server.services.mb_v2_wiring import build_mb_transports


def test_none_when_no_key(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    assert build_mb_transports() is None


def _install_fake_eodhd(monkeypatch, calls: dict) -> None:
    """Fake eodhd whose five MB endpoints record their kwargs and return rows."""
    fake = types.ModuleType("eodhd")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def get_live_stock_prices(self, ticker, s=None, **kwargs) -> list:
            calls["quotes_ticker"] = ticker
            calls["quotes_s"] = s
            return [{"code": ticker, "close": 1.0}]

        def get_eod_historical_stock_market_data(
            self, symbol, period="d", from_date=None, to_date=None, order=None
        ) -> list:
            calls["prices_symbol"] = symbol
            calls["prices_from"] = from_date
            calls["prices_to"] = to_date
            return [{"date": "2026-06-01", "close": 2.0}]

        def financial_news(self, s=None, t=None, limit=None, **kwargs) -> list:
            calls["news_s"] = s
            calls["news_limit"] = limit
            return [{"title": "headline", "symbols": [s] if s else []}]

        def get_economic_events_data(self, date_from=None, date_to=None, **kwargs) -> list:
            calls["econ_from"] = date_from
            calls["econ_to"] = date_to
            return [{"type": "CPI", "date": date_from}]

        def get_macro_indicators_data(self, country, indicator=None) -> list:
            calls.setdefault("macro_calls", []).append((country, indicator))
            return [{"CountryCode": country, "Indicator": indicator, "Value": 3.0}]

    fake.APIClient = FakeClient
    monkeypatch.setitem(sys.modules, "eodhd", fake)


def test_bundle_when_key_set(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    _install_fake_eodhd(monkeypatch, {})
    t = build_mb_transports()
    assert t is not None
    assert callable(t.quotes)
    assert callable(t.prices)
    assert callable(t.news)
    assert callable(t.economic_calendar)
    assert callable(t.macro_indicators)


def test_build_transports_uses_explicit_api_key(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    _install_fake_eodhd(monkeypatch, {})
    assert build_mb_transports(api_key="explicit") is not None


def test_quotes_routes_to_live_prices(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_fake_eodhd(monkeypatch, calls)
    t = build_mb_transports(api_key="x")
    rows = t.quotes(["SPY.US", "QQQ.US"])
    # Multi-ticker quotes: the secondary tickers ride the ``s`` param.
    assert calls["quotes_ticker"] == "SPY.US"
    assert "QQQ.US" in (calls["quotes_s"] or "")
    assert rows and isinstance(rows, list)


def test_quotes_single_ticker(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_fake_eodhd(monkeypatch, calls)
    rows = build_mb_transports(api_key="x").quotes(["AAPL.US"])
    assert calls["quotes_ticker"] == "AAPL.US"
    assert rows[0]["code"] == "AAPL.US"


def test_prices_maps_range_to_date_window(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_fake_eodhd(monkeypatch, calls)
    rows = build_mb_transports(api_key="x").prices("SPY.US", "1mo")
    assert calls["prices_symbol"] == "SPY.US"
    # A range token resolves to a from/to ISO date window.
    assert calls["prices_from"] is not None
    assert calls["prices_to"] is not None
    assert calls["prices_from"] <= calls["prices_to"]
    assert rows[0]["close"] == 2.0


def test_news_market_wide_when_symbol_omitted(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_fake_eodhd(monkeypatch, calls)
    rows = build_mb_transports(api_key="x").news()
    assert calls["news_s"] is None
    assert isinstance(rows, list)


def test_news_symbol_specific(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_fake_eodhd(monkeypatch, calls)
    rows = build_mb_transports(api_key="x").news(symbol="AAPL.US")
    assert calls["news_s"] == "AAPL.US"
    assert isinstance(rows, list)


def test_economic_calendar_maps_window_to_dates(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_fake_eodhd(monkeypatch, calls)
    rows = build_mb_transports(api_key="x").economic_calendar("today")
    assert calls["econ_from"] is not None
    assert calls["econ_to"] is not None
    assert calls["econ_from"] <= calls["econ_to"]
    assert rows[0]["type"] == "CPI"


def test_economic_calendar_this_week_wider_window(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    today_calls: dict = {}
    _install_fake_eodhd(monkeypatch, today_calls)
    build_mb_transports(api_key="x").economic_calendar("today")
    week_calls: dict = {}
    _install_fake_eodhd(monkeypatch, week_calls)
    build_mb_transports(api_key="x").economic_calendar("this_week")
    # 'this_week' spans at least as far forward as 'today'.
    assert week_calls["econ_to"] >= today_calls["econ_to"]


def test_macro_indicators_returns_keyed_dict(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_fake_eodhd(monkeypatch, calls)
    readings = build_mb_transports(api_key="x").macro_indicators(["us_10y", "vix"])
    assert isinstance(readings, dict)
    assert set(readings) == {"us_10y", "vix"}
