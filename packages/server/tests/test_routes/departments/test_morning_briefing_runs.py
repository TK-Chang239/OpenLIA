"""Route tests for the Morning Briefing run lifecycle (report_mb shape).

Self-contained ``create_app`` + temp SQLite DB + authenticated local user
(personal mode), mirroring ``test_earnings_update_v2_routes.py``.

``run_svc.start_run_async`` is monkeypatched so ``POST /runs/start`` does
not spawn the real engine (which would build an ``LLMSession`` from env);
the patch inserts the ``report_mb`` running row via the real
``insert_report_row`` and returns its id, so the row-creation + listing +
detail + delete + download paths exercise the real persistence layer.

The ``/events`` SSE route is asserted via ``app.routes`` (do NOT consume
the live stream — it hangs the suite).
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
from openlia_server.db.models.report_mb import ReportMb, ReportMbSection, ReportMbTemplate

_BASE = "/api/departments/morning-briefing"


class _FakeScheduler:
    def __init__(self) -> None:
        self.added: list = []

    async def add_schedule(self, schedule) -> None:
        self.added.append(schedule)

    async def modify_schedule(self, schedule) -> None:
        pass

    async def remove_schedule(self, *, job_type, user_id, schedule_id=None) -> None:
        pass


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


def _patch_start_run_async(monkeypatch) -> None:
    """Replace the engine spawn with a synchronous running-row insert.

    Mirrors the real ``start_run_async`` contract (insert the row, register
    a cancel token, return the id) without scheduling a background task.
    """
    from openlia_server.services import mb_v2_run_service as run_svc

    def _fake_start(
        db,
        *,
        user_id,
        request,
        broker,
        cancel_registry,
        session_factory,
        trigger_kind="on_demand",
        schedule_id=None,
        instructions_id=None,
        transports=None,
        session=None,
    ):
        report_id = run_svc.insert_report_row(
            db,
            user_id=user_id,
            request=request,
            trigger_kind=trigger_kind,
            schedule_id=schedule_id,
            instructions_id=instructions_id,
        )
        from openlia.llm.runtime.report_mb import CancelToken

        cancel_registry[report_id] = CancelToken()
        return report_id

    monkeypatch.setattr(run_svc, "start_run_async", _fake_start)


def _build_app(tmp_path, monkeypatch):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/mb_runs.db")
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    session_mod.configure_engine(f"sqlite:///{tmp_path}/mb_runs.db")
    Base.metadata.create_all(session_mod.get_engine())

    _seed_local_user()
    _seed_mb_default()
    _patch_start_run_async(monkeypatch)

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


def _create_schedule(client) -> str:
    payload = {
        "time": "07:00",
        "timezone": "America/New_York",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "label": "US Pre-Market",
        "template_id": "mb_default",
        "enabled_connectors": {"provider_ids": ["eodhd"], "web_search": False},
        "provider_kind": "anthropic",
        "model": "claude-sonnet-4-6",
        "language": "en",
        "length": "concise",
    }
    r = client.post(f"{_BASE}/schedules", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _seed_completed_run(report_id: str = "rep-1") -> str:
    now = datetime.now(UTC)
    with session_mod.SessionLocal() as s:
        s.add(
            ReportMb(
                id=report_id,
                user_id="local",
                subject="Morning Briefing - 2026-06-02",
                trigger_kind="on_demand",
                schedule_id=None,
                template_id="mb_default",
                instructions_id=None,
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
            ReportMbSection(
                report_id=report_id,
                section_id="macro",
                section_index=0,
                title="Global Macro",
                markdown="Rates held steady overnight.",
                version=1,
            )
        )
        s.commit()
    return report_id


# ----- Run lifecycle -----


def test_runs_list_empty(client):
    r = client.get(f"{_BASE}/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_start_run_with_schedule_creates_running_row(client):
    sid = _create_schedule(client)
    r = client.post(f"{_BASE}/runs/start", json={"schedule_id": sid})
    assert r.status_code == 200, r.text
    report_id = r.json()["report_id"]
    assert report_id

    # listed, newest-first, status running, schedule_id pinned
    rows = client.get(f"{_BASE}/runs").json()
    assert len(rows) == 1
    assert rows[0]["report_id"] == report_id
    assert rows[0]["status"] == "running"
    assert rows[0]["schedule_id"] == sid
    assert rows[0]["template_id"] == "mb_default"


def test_start_run_adhoc_config(client):
    r = client.post(
        f"{_BASE}/runs/start",
        json={
            "template_id": "mb_default",
            "provider_kind": "anthropic",
            "model": "claude-sonnet-4-6",
            "language": "en",
            "length": "normal",
            "enabled_connectors": {"provider_ids": [], "web_search": False},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["report_id"]


def test_start_run_freeform_without_instructions_400(client):
    r = client.post(
        f"{_BASE}/runs/start",
        json={"template_id": "freeform", "instructions_id": None},
    )
    assert r.status_code == 400, r.text


def test_start_run_unknown_schedule_404(client):
    r = client.post(f"{_BASE}/runs/start", json={"schedule_id": "nope"})
    assert r.status_code == 404


def test_get_run_detail(client):
    rid = _seed_completed_run("rep-detail")
    r = client.get(f"{_BASE}/runs/{rid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report"]["report_id"] == rid
    assert body["report"]["status"] == "completed"
    assert [s["title"] for s in body["sections"]] == ["Global Macro"]


def test_get_unknown_run_404(client):
    r = client.get(f"{_BASE}/runs/nope")
    assert r.status_code == 404


def test_delete_run(client):
    rid = _seed_completed_run("rep-del")
    assert client.delete(f"{_BASE}/runs/{rid}").status_code == 204
    assert client.get(f"{_BASE}/runs/{rid}").status_code == 404


def test_delete_unknown_run_404(client):
    r = client.delete(f"{_BASE}/runs/nope")
    assert r.status_code == 404


def test_cancel_unknown_run_404(client):
    r = client.post(f"{_BASE}/runs/nope/cancel")
    assert r.status_code == 404


# ----- Downloads -----


def test_export_html_ok(client):
    rid = _seed_completed_run("rep-html")
    r = client.get(f"{_BASE}/runs/{rid}/html")
    assert r.status_code == 200, r.text
    assert ".html" in r.headers["content-disposition"]
    assert "Global Macro" in r.text


def test_export_docx_ok(client):
    rid = _seed_completed_run("rep-docx")
    r = client.get(f"{_BASE}/runs/{rid}/docx")
    assert r.status_code == 200, r.text
    assert (
        r.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ".docx" in r.headers["content-disposition"]


def test_export_html_unknown_run_404(client):
    r = client.get(f"{_BASE}/runs/nope/html")
    assert r.status_code == 404


def test_export_pdf_503_without_launcher(client):
    rid = _seed_completed_run("rep-pdf")
    r = client.get(f"{_BASE}/runs/{rid}/pdf")
    assert r.status_code == 503


# ----- SSE route registration (do NOT consume the live stream) -----


def test_events_route_registered(client):
    paths = {getattr(r, "path", None) for r in client.app.routes}
    assert "/departments/morning-briefing/runs/{report_id}/events" in paths


def test_run_start_handler_is_async():
    import inspect

    from openlia_server.routes.departments import morning_briefing as mod

    assert any(
        inspect.iscoroutinefunction(getattr(mod, n, None)) for n in dir(mod) if "start" in n.lower()
    )
