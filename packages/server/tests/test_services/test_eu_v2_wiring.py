# packages/server/tests/test_services/test_eu_v2_wiring.py
from __future__ import annotations

import sys
import types

from openlia_server.services.eu_v2_wiring import build_eu_v2_transports


def test_none_when_no_key(monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    assert build_eu_v2_transports() is None


def _install_fake_eodhd(monkeypatch) -> None:
    fake = types.ModuleType("eodhd")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def get_fundamentals_data(self, ticker: str) -> dict:
            return {"General": {"Sector": "Tech"}}

        def get_eod_historical_stock_market_data(self, **kwargs) -> list:
            return []

        def financial_news(self, s: str, limit: int) -> list:
            return []

    fake.APIClient = FakeClient
    monkeypatch.setitem(sys.modules, "eodhd", fake)


def test_bundle_when_key_set(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    _install_fake_eodhd(monkeypatch)
    t = build_eu_v2_transports()
    assert t is not None
    assert callable(t.fundamentals)
    assert callable(t.earnings_calendar)
