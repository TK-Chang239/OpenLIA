"""HTTP tests for POST /departments/equity-research/report SSE route."""

from __future__ import annotations

import json

from openlia.llm.runtime.events import ReportComplete, ReportStart

MINIMAL_SCHEMA = {
    "schema_version": "2.0",
    "department": "equity_research",
    "generated_at": "2026-04-23T00:00:00Z",
    "cover": {
        "title": "AAPL Update",
        "subtitle": "",
        "tagline": "",
    },
    "sections": [],
}


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


class _FakeInner:
    def __init__(self, queue):
        self._queue = queue

    async def run(self, **kwargs):
        for e in self._queue:
            yield e


def test_report_route_streams_start_complete_saved(company_client, auth_user):
    queue = [
        ReportStart(
            report_id="r_1",
            department="equity_research",
            mode="stock_update",
            section_titles=["t"],
        ),
        ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA),
    ]
    company_client.app.state.equity_research_inner_factory = lambda: _FakeInner(queue)

    r = company_client.post(
        "/departments/equity-research/report",
        json={"mode": "stock_update", "user_input": "AAPL event"},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = _consume_sse(r.iter_lines())
    types = [e["type"] for e in events]
    assert "report.start" in types
    assert "report.complete" in types
    assert "report.saved" in types  # explicit assertion for the saved frame
    assert types[-1] == "report.saved"
    assert events[-1]["report_id"]


def test_report_route_rejects_invalid_mode(company_client, auth_user):
    r = company_client.post(
        "/departments/equity-research/report",
        json={"mode": "bogus", "user_input": "x"},
    )
    assert r.status_code == 400


def test_report_route_requires_auth(company_client_anon):
    r = company_client_anon.post(
        "/departments/equity-research/report",
        json={"mode": "stock_update", "user_input": "x"},
    )
    assert r.status_code == 401


class _AttachmentCapturingInner:
    def __init__(self, queue):
        self._queue = queue
        self.last_kwargs = None

    async def run(self, **kwargs):
        self.last_kwargs = kwargs
        for e in self._queue:
            yield e


def test_report_route_accepts_multipart_with_files(company_client, auth_user, db_session):
    from openlia_server.services import chat_sessions as chat_sessions_svc

    queue = [ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA)]
    inner = _AttachmentCapturingInner(queue)
    company_client.app.state.equity_research_inner_factory = lambda: inner

    sess = chat_sessions_svc.create_session(
        db_session, user_id=auth_user.id, department="equity_research", title="t"
    )
    r = company_client.post(
        "/departments/equity-research/report",
        data={"mode": "stock_update", "user_input": "AAPL Q4", "session_id": sess.id},
        files=[("files", ("note.txt", b"company-supplied note", "text/plain"))],
    )
    assert r.status_code == 200
    list(r.iter_lines())
    assert inner.last_kwargs is not None
    attachments = inner.last_kwargs.get("attachments")
    assert attachments is not None and len(attachments) == 1
    assert attachments[0].filename == "note.txt"


def test_report_route_rejects_multipart_without_session(company_client, auth_user):
    company_client.app.state.equity_research_inner_factory = lambda: _AttachmentCapturingInner([])
    r = company_client.post(
        "/departments/equity-research/report",
        data={"mode": "stock_update", "user_input": "x"},
        files=[("files", ("a.txt", b"abc", "text/plain"))],
    )
    assert r.status_code == 400


def test_report_route_threads_session_disabled_lists(company_client, auth_user, db_session):
    """The report path must honor the session row's disabled_connector_ids and
    disabled_skill_ids (parity with chat). Without this, the LLM still has
    access to tools the user toggled off in the UI."""
    from openlia_server.services import chat_sessions as chat_sessions_svc

    queue = [ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA)]
    inner = _AttachmentCapturingInner(queue)
    company_client.app.state.equity_research_inner_factory = lambda: inner

    sess = chat_sessions_svc.create_session(
        db_session, user_id=auth_user.id, department="equity_research", title="t"
    )
    sess.disabled_connector_ids = ["financial:fmp"]
    sess.disabled_skill_ids = ["macro_outlook"]
    db_session.commit()

    r = company_client.post(
        "/departments/equity-research/report",
        json={"mode": "stock_update", "user_input": "AAPL", "session_id": sess.id},
    )
    assert r.status_code == 200
    list(r.iter_lines())
    assert inner.last_kwargs is not None
    assert inner.last_kwargs.get("disabled_connector_ids") == ("financial:fmp",)
    assert inner.last_kwargs.get("disabled_skill_ids") == ("macro_outlook",)
