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
import sys
import types
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
    assert body["enabled_provider_ids"] == ["eodhd"]
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
            "enabled_provider_ids": [],
            "web_search_enabled": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["length"] == "concise"
    assert body["web_search_enabled"] is True
    assert body["enabled_provider_ids"] == []


def test_settings_get_defaults_batch_disabled(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/settings")
    assert r.status_code == 200
    assert r.json()["batch_enabled"] is False


def test_settings_put_roundtrip_batch_enabled(client_eu_v2):
    r = client_eu_v2.put(
        f"{_BASE}/settings",
        json={
            "provider_kind": "openai",
            "model": "gpt-5.4-2026-03-05",
            "template_id": "eu_default",
            "language": "en",
            "length": "normal",
            "reasoning_effort": None,
            "enabled_provider_ids": ["eodhd"],
            "web_search_enabled": False,
            "batch_enabled": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["batch_enabled"] is True
    g = client_eu_v2.get(f"{_BASE}/settings")
    assert g.json()["batch_enabled"] is True


def test_settings_put_freeform_without_instructions_rejected(client_eu_v2):
    r = client_eu_v2.put(
        f"{_BASE}/settings",
        json={
            "provider_kind": "anthropic",
            "model": "claude-sonnet-4-6",
            "template_id": "freeform",
            "language": "en",
            "length": "normal",
            "reasoning_effort": None,
            "enabled_provider_ids": ["eodhd"],
            "web_search_enabled": False,
            "instructions_id": None,
        },
    )
    assert r.status_code == 400, r.text


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


def _install_fake_eodhd_calendar(monkeypatch) -> None:
    """Fake eodhd whose upcoming-earnings call returns the real dict shape.

    EODHD returns ``{"type", "description", "symbols", "earnings": [...]}`` --
    the event dicts are nested under ``earnings``, not at the top level.
    """
    fake = types.ModuleType("eodhd")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def get_upcoming_earnings_data(
            self, from_date=None, to_date=None, symbols=None
        ) -> dict:
            return {
                "type": "Earnings",
                "description": "Historical and upcoming Earnings",
                "symbols": symbols,
                "earnings": [
                    {
                        "code": symbols,
                        "report_date": "2026-07-30",
                        "before_after_market": "AfterMarket",
                        "estimate": 1.9,
                    }
                ],
            }

    fake.APIClient = FakeClient
    monkeypatch.setitem(sys.modules, "eodhd", fake)


def test_watchlist_sync_with_eodhd_populates_schedule(client_eu_v2, monkeypatch):
    # Regression: the manual sync endpoint 500'd because the EODHD transport
    # returned ``list(result)`` (the dict's keys) instead of the nested event
    # list, so sync_user_watchlist called ``str.get`` and crashed. With a
    # configured transport the endpoint must return 200 and schedule the row.
    monkeypatch.setenv("EODHD_API_KEY", "k")
    _install_fake_eodhd_calendar(monkeypatch)

    assert (
        client_eu_v2.post(f"{_BASE}/watchlist", json={"ticker": "AAPL"}).status_code
        == 201
    )

    r = client_eu_v2.post(f"{_BASE}/watchlist/sync")
    assert r.status_code == 200
    assert r.json()["synced"] == 1

    schedule = client_eu_v2.get(f"{_BASE}/schedule").json()["schedule"]
    assert any(
        row["ticker"] == "AAPL" and row["fiscal_date"] == "2026-07-30"
        for row in schedule
    )


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


def test_data_sources_503_when_disabled(client_eu_v2_disabled):
    r = client_eu_v2_disabled.get(f"{_BASE}/data-sources")
    assert r.status_code == 503


def _ds_by_key(body):
    return {s["key"]: s for s in body["sources"]}


def test_data_sources_eodhd_unavailable_without_eodhd(client_eu_v2, monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    r = client_eu_v2.get(f"{_BASE}/data-sources")
    assert r.status_code == 200, r.text
    by_key = _ds_by_key(r.json())
    eodhd = by_key["eodhd"]
    assert eodhd["available"] is False
    assert eodhd["routing"] == "curated"
    assert eodhd["unavailable_reason"] == "eodhd_unconfigured"
    assert "model_web_search" in by_key


def test_data_sources_eodhd_available_with_env(client_eu_v2, monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "k")
    r = client_eu_v2.get(f"{_BASE}/data-sources")
    eodhd = _ds_by_key(r.json())["eodhd"]
    assert eodhd["available"] is True
    assert eodhd["display_name"] == "EODHD"


def test_data_sources_lists_validated_connectors(client_eu_v2, monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    from openlia_server.db.models.connectors import Connector

    with session_mod.SessionLocal() as s:
        s.add(
            Connector(
                id="c-news",
                provider_id="newsapi_ai",
                source="built_in",
                category="news",
                launch={},
                secrets={},
                status="validated",
                display_name="News API",
            )
        )
        s.commit()
    r = client_eu_v2.get(f"{_BASE}/data-sources")
    by_key = _ds_by_key(r.json())
    assert "newsapi_ai" in by_key
    assert by_key["newsapi_ai"]["routing"] == "dispatcher"
    assert by_key["newsapi_ai"]["display_name"] == "News API"


def test_data_sources_web_search_query_override(client_eu_v2, monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    r = client_eu_v2.get(
        f"{_BASE}/data-sources",
        params={"provider_kind": "anthropic", "model": "claude-sonnet-4-6"},
    )
    ws = _ds_by_key(r.json())["model_web_search"]
    assert ws["available"] is True
    assert ws["routing"] == "model_native"


def _seed_completed_run(report_id: str = "rep-export") -> str:
    """Seed a completed report_eu row with one section for render tests."""
    from openlia_server.db.models.report_eu import ReportEu, ReportEuSection

    now = datetime.now(UTC)
    with session_mod.SessionLocal() as s:
        s.add(
            ReportEu(
                id=report_id,
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
                created_at=now,
                completed_at=now,
                cover_json=None,
                reasoning_effort=None,
            )
        )
        s.add(
            ReportEuSection(
                report_id=report_id,
                section_id="overview",
                section_index=0,
                title="Quarter Overview",
                markdown="Revenue beat expectations this quarter.",
                version=1,
            )
        )
        s.commit()
    return report_id


def test_export_html_ok(client_eu_v2):
    rid = _seed_completed_run("rep-html")
    r = client_eu_v2.get(f"{_BASE}/runs/{rid}/html")
    assert r.status_code == 200, r.text
    assert ".html" in r.headers["content-disposition"]
    assert "Quarter Overview" in r.text


def test_export_docx_ok(client_eu_v2):
    rid = _seed_completed_run("rep-docx")
    r = client_eu_v2.get(f"{_BASE}/runs/{rid}/docx")
    assert r.status_code == 200, r.text
    assert (
        r.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ".docx" in r.headers["content-disposition"]


def test_export_html_unknown_run_404(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/runs/nope/html")
    assert r.status_code == 404


def test_export_docx_unknown_run_404(client_eu_v2):
    r = client_eu_v2.get(f"{_BASE}/runs/nope/docx")
    assert r.status_code == 404


def test_export_pdf_503_without_launcher(client_eu_v2):
    # The test app has no browser_launcher on app.state, so the PDF
    # endpoint must refuse with 503 (mirrors the v3 route behaviour).
    rid = _seed_completed_run("rep-pdf")
    r = client_eu_v2.get(f"{_BASE}/runs/{rid}/pdf")
    assert r.status_code == 503


def test_resolve_eu_transports_bridges_connector_key(client_eu_v2, monkeypatch):
    # The route module's transport resolver must honor an installed EODHD
    # connector's stored key (bridge), not only the env var.
    import openlia_server.routes.departments.earnings_update_v2 as eu_routes
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.connectors import Connector

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    # Install a fake eodhd SDK so build_eu_v2_transports can construct a client.
    import sys
    import types

    fake = types.ModuleType("eodhd")

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

    fake.APIClient = _FakeClient
    monkeypatch.setitem(sys.modules, "eodhd", fake)

    with session_mod.SessionLocal() as s:
        s.add(
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
        s.commit()

    with session_mod.SessionLocal() as s:
        transports = eu_routes._resolve_eu_transports(s)
    assert transports is not None
