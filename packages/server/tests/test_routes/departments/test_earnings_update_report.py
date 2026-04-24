"""HTTP tests for POST /departments/earnings-update/report (SSE) and
GET /departments/earnings-update/reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from openlia.llm.runtime.events import ReportComplete, ReportStart


MINIMAL_SCHEMA = {
    "schema_version": "1.0",
    "department": "earnings_update",
    "generated_at": "2026-04-23T00:00:00Z",
    "cover": {"title": "AAPL Q1 FY2026", "subtitle": "", "tagline": ""},
    "sections": [],
    "title": "AAPL Q1 FY2026",
}


class _ScriptedRunner:
    def __init__(self, events: list) -> None:
        self._events = events
        self.received: list = []

    async def run(self, *, department_id: str, user_id: str, request):
        self.received.append((department_id, user_id, request))
        for e in self._events:
            yield e


@dataclass
class _FakeStore:
    saved: list[dict] = field(default_factory=list)

    def save_from_event(self, *, user_id, department, report_type, event):
        rid = event.report_id
        self.saved.append(
            {
                "user_id": user_id,
                "report_id": rid,
                "department": department,
                "report_type": report_type,
            }
        )
        return rid


def _consume_sse(iter_lines):
    events = []
    current = []
    for raw in iter_lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line == "":
            if current:
                events.append(json.loads("".join(current)))
                current = []
            continue
        if line.startswith("data:"):
            current.append(line[5:].lstrip())
    if current:
        events.append(json.loads("".join(current)))
    return events


def test_report_streams_events_and_persists(company_client, auth_user):
    runner = _ScriptedRunner(
        events=[
            ReportStart(
                report_id="r_1",
                department="earnings_update",
                mode="earnings_analysis",
                section_titles=["Quick Take"],
            ),
            ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA),
        ]
    )
    store = _FakeStore()
    company_client.app.state.report_runner = runner
    company_client.app.state.report_store = store

    r = company_client.post(
        "/departments/earnings-update/report",
        json={"ticker": "AAPL"},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = _consume_sse(r.iter_lines())
    types = [e["type"] for e in events]
    assert "report.start" in types
    assert "report.complete" in types
    assert store.saved[0]["report_id"] == "r_1"
    assert store.saved[0]["department"] == "earnings_update"
    # Runner receives uppercased ticker and earnings_analysis mode.
    dept_id, _uid, req = runner.received[0]
    assert dept_id == "earnings_update"
    assert "AAPL" in req.user_input
    assert req.mode == "earnings_analysis"


def test_report_uppercases_ticker(company_client, auth_user):
    runner = _ScriptedRunner(
        events=[ReportComplete(report_id="r_2", schema=MINIMAL_SCHEMA)]
    )
    store = _FakeStore()
    company_client.app.state.report_runner = runner
    company_client.app.state.report_store = store

    r = company_client.post(
        "/departments/earnings-update/report", json={"ticker": "tsla"}
    )
    assert r.status_code == 200
    _consume_sse(r.iter_lines())
    _dept, _uid, req = runner.received[0]
    assert "TSLA" in req.user_input


def test_report_maps_length_from_user_config(company_client, auth_user):
    company_client.put(
        "/departments/earnings-update/config",
        json={
            "report_length": "elaborative",
            "enabled_section_ids": ["quick_take"],
            "custom_sections": [],
        },
    )
    runner = _ScriptedRunner(
        events=[ReportComplete(report_id="r_3", schema=MINIMAL_SCHEMA)]
    )
    store = _FakeStore()
    company_client.app.state.report_runner = runner
    company_client.app.state.report_store = store

    r = company_client.post(
        "/departments/earnings-update/report", json={"ticker": "AAPL"}
    )
    assert r.status_code == 200
    _consume_sse(r.iter_lines())
    _dept, _uid, req = runner.received[0]
    assert req.length == "long"
    assert req.enabled_sections == ["quick_take"]


def test_report_rejects_empty_ticker(company_client, auth_user):
    # Wire minimal runner/store so the 500 path (missing wiring) isn't hit;
    # empty ticker must be rejected by pydantic min_length.
    company_client.app.state.report_runner = _ScriptedRunner(events=[])
    company_client.app.state.report_store = _FakeStore()
    r = company_client.post(
        "/departments/earnings-update/report", json={"ticker": ""}
    )
    assert r.status_code == 422


def test_report_requires_auth(company_client_anon):
    r = company_client_anon.post(
        "/departments/earnings-update/report", json={"ticker": "AAPL"}
    )
    assert r.status_code == 401


def test_list_recent_reports_scoped_to_earnings_update(
    company_client, auth_user, db_session
):
    from openlia_server.db.models.content import Report

    def _mk(user_id: str, department: str, title: str) -> Report:
        r = Report(
            id=str(uuid4()),
            user_id=user_id,
            department=department,
            report_type="earnings_update" if department == "earnings_update" else "other",
            title=title,
            content_markdown="# x",
            content_structured={},
            model_ref="gpt-4",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(r)
        db_session.commit()
        return r

    _mk(auth_user.id, "earnings_update", "EU report one")
    _mk(auth_user.id, "equity_research", "ER report")

    r = company_client.get("/departments/earnings-update/reports")
    assert r.status_code == 200
    body = r.json()
    titles = [row["title"] for row in body["reports"]]
    assert titles == ["EU report one"]


def test_list_recent_reports_respects_limit(company_client, auth_user, db_session):
    from openlia_server.db.models.content import Report

    for i in range(3):
        db_session.add(
            Report(
                id=str(uuid4()),
                user_id=auth_user.id,
                department="earnings_update",
                report_type="earnings_update",
                title=f"R{i}",
                content_markdown="# x",
                content_structured={},
                model_ref="gpt-4",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    db_session.commit()

    r = company_client.get("/departments/earnings-update/reports?limit=2")
    assert r.status_code == 200
    assert len(r.json()["reports"]) == 2
