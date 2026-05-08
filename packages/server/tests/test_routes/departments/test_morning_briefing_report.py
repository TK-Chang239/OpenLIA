"""HTTP tests for POST /departments/morning-briefing/report (SSE)."""

from __future__ import annotations

import json

from openlia.llm.runtime.events import ReportComplete, ReportPhase, ReportStart

MINIMAL_SCHEMA = {
    "schema_version": "2.0",
    "department": "morning_briefing",
    "generated_at": "2026-04-23T00:00:00Z",
    "cover": {
        "title": "Morning Briefing 2026-04-23",
        "subtitle": "",
        "tagline": "",
    },
    "sections": [],
}


class _ScriptedRunner:
    def __init__(self, events: list) -> None:
        self._events = events
        self.received: list = []

    async def run(self, *, department_id: str, user_id: str, request, cancel_token=None):
        self.received.append((department_id, user_id, request))
        for e in self._events:
            yield e


def _consume_sse(iter_lines):
    """Return list of (event_name, parsed_data) pairs."""
    events = []
    current_event: str | None = None
    current_data: list[str] = []
    for raw in iter_lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line == "":
            if current_data:
                events.append((current_event, json.loads("".join(current_data))))
                current_event = None
                current_data = []
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            current_data.append(line[5:].lstrip())
    if current_data:
        events.append((current_event, json.loads("".join(current_data))))
    return events


def test_report_streams_named_events_and_persists(company_client, auth_user, db_session):
    from openlia_server.db.models.content import Report

    runner = _ScriptedRunner(
        events=[
            ReportStart(
                report_id="r_1",
                department="morning_briefing",
                mode="morning_briefing",
                section_titles=["Executive Summary"],
            ),
            ReportPhase(report_id="r_1", phase="writing"),
            ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA),
        ]
    )
    company_client.app.state.report_runner = runner

    r = company_client.post(
        "/departments/morning-briefing/report",
        json={},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = _consume_sse(r.iter_lines())
    names = [name for name, _ in events]
    assert "report.start" in names
    assert "report.phase" in names
    assert "report.complete" in names
    assert "report.saved" in names

    saved = db_session.query(Report).filter_by(user_id=auth_user.id).all()
    assert len(saved) == 1
    assert saved[0].department == "morning_briefing"
    assert saved[0].report_type == "morning_briefing"

    dept_id, _uid, req = runner.received[0]
    assert dept_id == "morning_briefing"
    assert req.mode == "morning_briefing"


def test_report_uses_user_config_for_length_and_sections(company_client, auth_user):
    company_client.put(
        "/departments/morning-briefing/config",
        json={
            "report_length": "elaborative",
            "enabled_section_ids": ["executive_summary"],
            "section_topics": {},
            "custom_sections": [],
            "reference_portfolio": False,
        },
    )
    runner = _ScriptedRunner(events=[ReportComplete(report_id="r_2", schema=MINIMAL_SCHEMA)])
    company_client.app.state.report_runner = runner

    r = company_client.post("/departments/morning-briefing/report", json={})
    assert r.status_code == 200
    _consume_sse(r.iter_lines())
    _dept, _uid, req = runner.received[0]
    assert req.length == "long"
    assert req.enabled_sections == ["executive_summary"]


def test_report_requires_auth(company_client_anon):
    r = company_client_anon.post("/departments/morning-briefing/report", json={})
    assert r.status_code == 401
