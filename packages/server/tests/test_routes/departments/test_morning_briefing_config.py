"""Route tests for the Morning Briefing config endpoints (report_mb shape).

Self-contained ``create_app`` + temp SQLite DB + authenticated local user
(personal mode), mirroring ``test_earnings_update_v2_routes.py``. The MB v2
broker / cancel registry are wired onto ``app.state`` by ``create_app``'s
include-router guard; a fake APScheduler control is injected so the schedule
endpoints round-trip without a live scheduler.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.report_mb.default_template import build_default_template
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_mb import ReportMbTemplate

_BASE = "/api/departments/morning-briefing"


class _FakeScheduler:
    """No-op SchedulerControl stand-in for the route's hot-reload calls."""

    def __init__(self) -> None:
        self.added: list = []
        self.modified: list = []
        self.removed: list = []

    async def add_schedule(self, schedule) -> None:
        self.added.append(schedule)

    async def modify_schedule(self, schedule) -> None:
        self.modified.append(schedule)

    async def remove_schedule(self, *, job_type, user_id, schedule_id=None) -> None:
        self.removed.append((job_type, user_id, schedule_id))


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


def _seed_mb_default() -> None:
    spec = build_default_template()
    now = datetime.now(UTC)
    with session_mod.SessionLocal() as s:
        s.add(
            ReportMbTemplate(
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


def _build_app(tmp_path, monkeypatch):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/mb_v2.db")
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    session_mod.configure_engine(f"sqlite:///{tmp_path}/mb_v2.db")
    Base.metadata.create_all(session_mod.get_engine())

    _seed_local_user()
    _seed_mb_default()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.scheduler = _FakeScheduler()
    return app


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


# ----- Schedules -----


def test_schedules_empty(client):
    r = client.get(f"{_BASE}/schedules")
    assert r.status_code == 200
    assert r.json() == []


def test_schedule_crud_roundtrip_echoes_binding(client):
    payload = {
        "time": "07:00",
        "timezone": "America/New_York",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "label": "US Pre-Market",
        "template_id": "mb_default",
        "instructions_id": None,
        "enabled_connectors": {"provider_ids": ["eodhd"], "web_search": True},
        "provider_kind": "anthropic",
        "model": "claude-sonnet-4-6",
        "language": "en",
        "length": "concise",
        "reasoning_effort": "high",
    }
    r = client.post(f"{_BASE}/schedules", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    sid = body["id"]
    assert body["label"] == "US Pre-Market"
    assert body["template_id"] == "mb_default"
    assert body["enabled_connectors"] == {"provider_ids": ["eodhd"], "web_search": True}
    assert body["provider_kind"] == "anthropic"
    assert body["model"] == "claude-sonnet-4-6"
    assert body["length"] == "concise"
    assert body["reasoning_effort"] == "high"
    assert body["web_search"] is True
    assert body["is_enabled"] is True

    # list reflects it
    r = client.get(f"{_BASE}/schedules")
    assert [row["id"] for row in r.json()] == [sid]

    # patch the binding
    patch = dict(payload)
    patch["time"] = "18:00"
    patch["label"] = "Asia Close"
    patch["length"] = "elaborative"
    patch["enabled_connectors"] = {"provider_ids": [], "web_search": False}
    r = client.patch(f"{_BASE}/schedules/{sid}", json=patch)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["time"] == "18:00"
    assert body["label"] == "Asia Close"
    assert body["length"] == "elaborative"
    assert body["web_search"] is False
    assert body["enabled_connectors"] == {"provider_ids": [], "web_search": False}

    # delete
    r = client.delete(f"{_BASE}/schedules/{sid}")
    assert r.status_code == 204
    assert client.get(f"{_BASE}/schedules").json() == []


def test_schedule_rejects_invalid_time(client):
    r = client.post(
        f"{_BASE}/schedules",
        json={
            "time": "25:99",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "bad",
        },
    )
    assert r.status_code == 422


def test_schedule_rejects_invalid_template(client):
    r = client.post(
        f"{_BASE}/schedules",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "bad-binding",
            "template_id": "does-not-exist",
        },
    )
    assert r.status_code == 422


def test_patch_unknown_schedule_404(client):
    r = client.patch(
        f"{_BASE}/schedules/nope",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon"],
            "label": "x",
        },
    )
    assert r.status_code == 404


def test_delete_unknown_schedule_404(client):
    r = client.delete(f"{_BASE}/schedules/nope")
    assert r.status_code == 404


# ----- Templates -----


def test_templates_list_has_builtin(client):
    r = client.get(f"{_BASE}/templates")
    assert r.status_code == 200
    assert any(t["id"] == "mb_default" for t in r.json()["templates"])


def test_template_upload_markdown_and_delete(client):
    md = "# Macro\nIntent: scan global macro.\n\n# Equities\nIntent: index moves.\n"
    r = client.post(
        f"{_BASE}/templates",
        json={"name": "My MB template", "source_markdown": md},
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["is_builtin"] is False

    assert tid in [t["id"] for t in client.get(f"{_BASE}/templates").json()["templates"]]

    r = client.delete(f"{_BASE}/templates/{tid}")
    assert r.status_code == 204


def test_template_upload_document(client):
    r = client.post(
        f"{_BASE}/templates",
        data={"name": "Doc template"},
        files={
            "file": (
                "tpl.md",
                b"# Overview\nIntent: summary.\n\n# Risks\nIntent: risk read.\n",
                "text/markdown",
            )
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_builtin"] is False


# ----- Instructions -----


def test_instructions_crud_roundtrip(client):
    r = client.post(
        f"{_BASE}/instructions",
        data={"name": "Macro bias"},
        files={"file": ("methodology.txt", b"Favor macro themes.", "text/plain")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    iid = body["id"]
    assert body["name"] == "Macro bias"
    assert body["is_builtin"] is False

    r = client.get(f"{_BASE}/instructions")
    assert r.status_code == 200
    assert iid in [row["id"] for row in r.json()]

    r = client.delete(f"{_BASE}/instructions/{iid}")
    assert r.status_code == 204


# ----- Data sources -----


def test_data_sources_returns_list(client):
    r = client.get(f"{_BASE}/data-sources")
    assert r.status_code == 200, r.text
    by_key = {s["key"]: s for s in r.json()["sources"]}
    assert "eodhd" in by_key
    assert by_key["eodhd"]["routing"] == "curated"
    assert by_key["eodhd"]["available"] is False
    assert by_key["eodhd"]["unavailable_reason"] == "eodhd_unconfigured"
    assert "model_web_search" in by_key


def test_data_sources_eodhd_available_with_env(client, monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "k")
    r = client.get(f"{_BASE}/data-sources")
    assert r.json()["sources"][0]["key"] == "eodhd"
    eodhd = {s["key"]: s for s in r.json()["sources"]}["eodhd"]
    assert eodhd["available"] is True


def test_data_sources_from_schedule_binding(client):
    payload = {
        "time": "07:00",
        "timezone": "UTC",
        "days_of_week": ["mon"],
        "label": "WS on",
        "template_id": "mb_default",
        "enabled_connectors": {"provider_ids": ["eodhd"], "web_search": True},
        "provider_kind": "anthropic",
        "model": "claude-sonnet-4-6",
    }
    sid = client.post(f"{_BASE}/schedules", json=payload).json()["id"]
    r = client.get(f"{_BASE}/data-sources", params={"schedule_id": sid})
    assert r.status_code == 200, r.text
    by_key = {s["key"]: s for s in r.json()["sources"]}
    assert by_key["eodhd"]["enabled"] is True
    assert by_key["model_web_search"]["enabled"] is True


def test_data_sources_unknown_schedule_404(client):
    r = client.get(f"{_BASE}/data-sources", params={"schedule_id": "nope"})
    assert r.status_code == 404


def test_config_requires_auth(tmp_path, monkeypatch):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/mb_auth.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/mb_auth.db")
    Base.metadata.create_all(session_mod.get_engine())
    app = create_app(db_session_factory=session_mod.SessionLocal)
    try:
        c = TestClient(app)
        r = c.get(f"{_BASE}/schedules")
        assert r.status_code == 401
    finally:
        session_mod.dispose_engine()
