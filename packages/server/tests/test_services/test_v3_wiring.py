"""Tests for v3 EODHD transport wiring.

The v3 routes call ``build_v3_transports`` and pass the result into the
runner so the data tools (get_fundamentals / get_historical_prices /
get_company_news) actually work. These tests guard the two outcomes:
no key -> None (loud null fallback in the runner); key present ->
working transports backed by a (faked) EODHD client, with fundamentals
trimmed.
"""

from __future__ import annotations

import sys
import types

from openlia.llm.runtime.report_v3 import DataTransports
from openlia_server.services.v3_wiring import build_v3_transports


def test_build_v3_transports_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    assert build_v3_transports() is None


def _install_fake_eodhd(monkeypatch) -> None:
    fake = types.ModuleType("eodhd")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def get_fundamentals_data(self, ticker: str) -> dict:
            return {
                "General": {"Sector": "Tech", "Description": "long prose to drop"},
                # Holders is in the drop set -> trimming must remove it.
                "Holders": {"big": "blob"},
            }

        def get_eod_historical_stock_market_data(self, **kwargs) -> list:
            return [{"date": "2024-01-02", "close": 100.0}]

        def financial_news(self, s: str, limit: int) -> list:
            return [{"title": "headline", "link": "https://x.test"}][:limit]

    fake.APIClient = FakeClient
    monkeypatch.setitem(sys.modules, "eodhd", fake)


def test_build_v3_transports_wires_working_callables(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "fake-key")
    _install_fake_eodhd(monkeypatch)

    transports = build_v3_transports()
    assert isinstance(transports, DataTransports)

    fundamentals = transports.fundamentals("NVDA.US")
    assert fundamentals["General"]["Sector"] == "Tech"
    # Trimming ran: dropped section + prose field are gone.
    assert "Holders" not in fundamentals
    assert "Description" not in fundamentals["General"]

    prices = transports.prices("NVDA.US", "2024-01-01", "2024-02-01")
    assert prices == [{"date": "2024-01-02", "close": 100.0}]

    news = transports.news("NVDA.US", 5)
    assert news and news[0]["title"] == "headline"


def test_build_v3_transports_respects_news_limit(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "fake-key")
    _install_fake_eodhd(monkeypatch)
    transports = build_v3_transports()
    assert transports is not None
    assert transports.news("NVDA.US", 1)  # fake returns up to `limit`
