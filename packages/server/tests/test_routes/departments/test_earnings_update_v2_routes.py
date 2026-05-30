"""Route tests for the Earnings Update v2 HTTP router.

Mirrors the v3 route-test app-construction pattern: a real ``create_app``
with a temp SQLite DB + an authenticated local user (personal mode). The
EU v2 broker / cancel registry are wired onto ``app.state`` by the test
fixture (the app-factory wiring lands in Task 17), mirroring how the v3
SSE infra is read off ``app.state`` at request time.
"""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.report_eu import EventBroker
from openlia.llm.runtime.report_eu.default_template import build_default_template
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_eu import ReportEuTemplate

_BASE = "/api/departments/earnings-update/v2"


def _seed_local_user() -> None:
    with session_mod.SessionLocal() as s:
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()


def _seed_eu_default() -> None:
    spec = build_default_template()
    now = datetime.now(UTC)
    with session_mod.SessionLocal() as s:
        s.add(
            ReportEuTemplate(
                id=spec.template_id,
                user_id=None,
                name=spec.name,
                is_builtin=True,
                template_spec_json=json.loads(spec.model_dump_json()),
                source_markdown=None,
                source_doc_blob=None,
                source_doc_mime=None,
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        s.commit()


def _build_app(tmp_path, monkeypatch, *, enabled: bool):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app
    from openlia_server.routes.departments.earnings_update_v2 import (
        build_earnings_update_v2_router,
    )

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/eu_v2.db")
    if enabled:
        monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    else:
        monkeypatch.delenv("EARNINGS_ENGINE_VERSION", raising=False)
    session_mod.configure_engine(f"sqlite:///{tmp_path}/eu_v2.db")
    Base.metadata.create_all(session_mod.get_engine())

    _seed_local_user()
    _seed_eu_default()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    # Mount the EU v2 router here: the app-factory mount lands in Task 17.
    # Routers mount with NO prefix — ``_StripApiPrefixMiddleware`` rewrites
    # incoming ``/api/...`` paths to the bare router prefix at runtime.
    app.include_router(
        build_earnings_update_v2_router(
            db_session_factory=session_mod.SessionLocal, mode="personal"
        )
    )
    # Task 17 wires these in the app factory; the route reads them off
    # app.state at request time the same way the v3 router does.
    app.state.eu_v2_event_broker = EventBroker()
    app.state.eu_v2_cancel_registry = {}
    return app


@pytest.fixture
def client_eu_v2(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, enabled=True)
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


@pytest.fixture
def client_eu_v2_disabled(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, enabled=False)
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


def test_routes_503_when_disabled(client_eu_v2_disabled):
    r = client_eu_v2_disabled.get(f"{_BASE}/settings")
    assert r.status_code == 503


def test_settings_get_returns_defaults(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["financial_enabled"] is True
    assert body["calendar_enabled"] is True
    assert body["web_search_enabled"] is False


def test_settings_put_roundtrip(client_eu_v2):
    r = client_eu_v2.put(
        f"{_BASE}/settings",
        json={
            "provider_kind": "anthropic",
            "model": "claude-sonnet-4-6",
            "template_id": "eu_default",
            "language": "en",
            "length": "concise",
            "reasoning_effort": "high",
            "financial_enabled": False,
            "calendar_enabled": False,
            "web_search_enabled": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["length"] == "concise"
    assert body["web_search_enabled"] is True
    assert body["financial_enabled"] is False


def test_watchlist_add_list_delete(client_eu_v2):
    r = client_eu_v2.post(f"{_BASE}/watchlist", json={"ticker": "MSFT.US"})
    assert r.status_code == 201, r.text
    entry_id = r.json()["id"]
    assert r.json()["ticker"] == "MSFT.US"

    r = client_eu_v2.get(f"{_BASE}/watchlist")
    assert r.status_code == 200
    assert [e["ticker"] for e in r.json()["entries"]] == ["MSFT.US"]

    r = client_eu_v2.delete(f"{_BASE}/watchlist/{entry_id}")
    assert r.status_code == 204
    assert client_eu_v2.get(f"{_BASE}/watchlist").json()["entries"] == []


def test_watchlist_add_duplicate_conflict(client_eu_v2):
    assert client_eu_v2.post(f"{_BASE}/watchlist", json={"ticker": "AAPL.US"}).status_code == 201
    r = client_eu_v2.post(f"{_BASE}/watchlist", json={"ticker": "AAPL.US"})
    assert r.status_code == 409


def test_watchlist_sync_no_transports_returns_zero(client_eu_v2):
    # No EODHD_API_KEY -> transports None -> a clean {synced: 0}.
    r = client_eu_v2.post(f"{_BASE}/watchlist/sync")
    assert r.status_code == 200
    assert r.json()["synced"] == 0


def test_templates_list_has_builtin(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/templates")
    assert r.status_code == 200
    assert any(t["id"] == "eu_default" for t in r.json()["templates"])


def test_template_upload_and_delete(client_eu_v2):
    md = "# Overview\nIntent: summarise the quarter.\n\n# Outlook\nIntent: guidance read.\n"
    r = client_eu_v2.post(
        f"{_BASE}/templates",
        json={"name": "My EU template", "source_markdown": md},
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["is_builtin"] is False

    r = client_eu_v2.delete(f"{_BASE}/templates/{tid}")
    assert r.status_code == 204


def test_schedule_empty(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/schedule")
    assert r.status_code == 200
    assert r.json()["schedule"] == []


def test_runs_list_empty(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_get_unknown_run_404(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/runs/nope")
    assert r.status_code == 404


def test_events_late_subscriber_gets_snapshot(client_eu_v2):
    # Seed a finished run directly, then connect to the SSE endpoint: a
    # late subscriber must get a single run.snapshot frame and close.
    from openlia_server.db.models.report_eu import ReportEu

    with session_mod.SessionLocal() as s:
        s.add(
            ReportEu(
                id="rep-1",
                user_id="local",
                subject="AAPL.US earnings",
                ticker="AAPL.US",
                trigger_kind="on_demand",
                fiscal_date=None,
                template_id="eu_default",
                language="en",
                length="normal",
                provider_kind="anthropic",
                model="claude-sonnet-4-6",
                status="completed",
                error_message=None,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                cover_json=None,
                reasoning_effort=None,
            )
        )
        s.commit()

    with client_eu_v2.stream("GET", f"{_BASE}/runs/rep-1/events") as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "event: run.snapshot" in body
    assert '"status": "completed"' in body


def test_events_unknown_run_404(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/runs/nope/events")
    assert r.status_code == 404


def test_cancel_unknown_run_404(client_eu_v2):
    r = client_eu_v2.post(f"{_BASE}/runs/nope/cancel")
    assert r.status_code == 404


def test_run_start_handler_is_async():
    from openlia_server.routes.departments import earnings_update_v2 as mod

    assert any(
        inspect.iscoroutinefunction(getattr(mod, n, None)) for n in dir(mod) if "start" in n.lower()
    )
