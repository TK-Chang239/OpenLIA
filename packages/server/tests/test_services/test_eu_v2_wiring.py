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
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.setenv("EODHD_API_KEY", "env-key")
    assert resolve_eodhd_api_key(db_session) == "env-key"


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
