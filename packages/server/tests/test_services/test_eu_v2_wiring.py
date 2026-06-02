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


def test_resolve_eodhd_api_key_prefers_env(monkeypatch, db_session):
    from openlia_server.db.models.connectors import Connector
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.setenv("EODHD_API_KEY", "env-key")
    db_session.add(
        Connector(
            id="c-eodhd",
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={},
            secrets={"EODHD_API_KEY": "db-key"},
            status="validated",
        )
    )
    db_session.commit()
    assert resolve_eodhd_api_key(db_session) == "env-key"  # env wins over connector


def test_resolve_eodhd_api_key_falls_back_to_validated_connector(monkeypatch, db_session):
    from openlia_server.db.models.connectors import Connector
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add(
        Connector(
            id="c-eodhd",
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={},
            secrets={"EODHD_API_KEY": "db-key"},
            status="validated",
        )
    )
    db_session.commit()
    assert resolve_eodhd_api_key(db_session) == "db-key"


def test_resolve_eodhd_api_key_ignores_unvalidated_connector(monkeypatch, db_session):
    from openlia_server.db.models.connectors import Connector
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add(
        Connector(
            id="c-eodhd-pending",
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={},
            secrets={"EODHD_API_KEY": "db-key"},
            status="pending",
        )
    )
    db_session.commit()
    assert resolve_eodhd_api_key(db_session) is None


def test_resolve_eodhd_api_key_none_when_nothing(monkeypatch, db_session):
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    assert resolve_eodhd_api_key(db_session) is None


def test_build_transports_uses_explicit_api_key(monkeypatch):
    from openlia_server.services.eu_v2_wiring import build_eu_v2_transports

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    _install_fake_eodhd(monkeypatch)
    # With no env key but an explicit key, transports build (non-None).
    assert build_eu_v2_transports(api_key="explicit") is not None


def _install_calendar_eodhd(monkeypatch, event: dict, calls: dict) -> None:
    """Fake eodhd whose upcoming-earnings call returns the real dict shape.

    EODHD's ``get_upcoming_earnings_data`` returns a dict
    ``{"type", "description", "symbols", "earnings": [...]}`` -- NOT a bare
    list. Records the kwargs it was called with into ``calls``.
    """
    fake = types.ModuleType("eodhd")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def get_upcoming_earnings_data(self, from_date=None, to_date=None, symbols=None) -> dict:
            calls["from_date"] = from_date
            calls["to_date"] = to_date
            calls["symbols"] = symbols
            return {
                "type": "Earnings",
                "description": "Historical and upcoming Earnings",
                "symbols": symbols,
                "earnings": [event] if event is not None else [],
            }

    fake.APIClient = FakeClient
    monkeypatch.setitem(sys.modules, "eodhd", fake)


def test_earnings_calendar_extracts_event_list_from_dict(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    event = {
        "code": "AAPL.US",
        "report_date": "2026-07-30",
        "before_after_market": "AfterMarket",
        "estimate": 1.9,
    }
    calls: dict = {}
    _install_calendar_eodhd(monkeypatch, event, calls)

    transports = build_eu_v2_transports(api_key="x")
    rows = transports.earnings_calendar("AAPL")

    # Returns the list of event dicts (rows["earnings"]), not the dict's keys.
    assert rows == [event]
    assert rows[0].get("report_date") == "2026-07-30"


def test_earnings_calendar_normalizes_symbol_and_passes_date_window(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_calendar_eodhd(monkeypatch, {"report_date": "2026-07-30"}, calls)

    build_eu_v2_transports(api_key="x").earnings_calendar("AAPL")

    # ``.US`` suffix appended, and a forward date window is supplied so EODHD
    # returns earnings beyond its narrow default window.
    assert calls["symbols"] == "AAPL.US"
    assert calls["from_date"] is not None
    assert calls["to_date"] is not None
    assert calls["from_date"] <= calls["to_date"]


def test_earnings_calendar_empty_when_no_events(monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "x")
    calls: dict = {}
    _install_calendar_eodhd(monkeypatch, None, calls)

    assert build_eu_v2_transports(api_key="x").earnings_calendar("AAPL") == []
