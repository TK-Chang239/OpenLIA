"""End-to-end success-rate probes for POST /departments/equity-research/report.

Symptom under investigation: user submits a report, LLM credits are spent
(meaning ``report.complete`` was reached), but the UI surfaces a generic
"Network error" instead of a saved report. Root-cause hypothesis: the SSE
stream handler in the route has no try/except, so any exception raised
inside ``runner.run_report`` (template lookup, schema validation,
``reports_svc.create_report`` DB write) terminates the response mid-stream
and the browser reports a transport error.

These tests pin the contract: the route must always finish with a
terminal SSE frame (``report.saved`` on success, ``report.error`` on any
failure). Mid-stream socket termination is a regression.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia_server.services.equity_research_runner import ReportSavedEvent

VALID_SCHEMA: dict[str, Any] = {
    "schema_version": "2.0",
    "department": "equity_research",
    "generated_at": "2026-05-12T00:00:00Z",
    "cover": {"title": "AAPL Update", "subtitle": "", "tagline": ""},
    "sections": [],
}

INVALID_SCHEMA: dict[str, Any] = {
    "schema_version": "2.0",
    "department": "equity_research",
    "generated_at": "2026-05-12T00:00:00Z",
    "cover": {"title": "X", "subtitle": "", "tagline": ""},
    "sections": [{"id": "broken", "title": "missing required keys"}],
}


def _consume_sse(iter_lines) -> list[dict]:
    events: list[dict] = []
    current: list[str] = []
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


def _event_types(events: list[dict]) -> list[str]:
    return [e.get("type") for e in events]


def _assert_terminal_frame(events: list[dict]) -> None:
    """The stream must end with either report.saved or report.error.

    Anything else (no terminal frame, or a partial sequence ending in
    report.complete) is what the user sees as 'Network error' in the UI.
    """
    assert events, "SSE stream produced no frames at all"
    last = events[-1].get("type")
    assert last in {"report.saved", "report.error"}, (
        f"stream did not end with a terminal frame; got types={_event_types(events)}"
    )


class _ScriptedInner:
    def __init__(self, queue):
        self._queue = queue

    async def run(self, **_kwargs):
        for ev in self._queue:
            yield ev


class _RaisingInner:
    """Inner runner that yields a partial event sequence, then raises.

    Mirrors a flaky upstream LLM stream (or a network blip mid-generation)
    where some frames make it through before the producer dies.
    """

    def __init__(self, queue, exc: Exception):
        self._queue = queue
        self._exc = exc

    async def run(self, **_kwargs):
        for ev in self._queue:
            yield ev
        raise self._exc


def _consume(client, *, body=None) -> list[dict]:
    payload = body or {"mode": "stock_update", "user_input": "AAPL deep dive"}
    r = client.post(
        "/departments/equity-research/report",
        json=payload,
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    return _consume_sse(r.iter_lines())


# ---------------------------------------------------------------------------
# Baseline — happy path must still produce the full success envelope.
# ---------------------------------------------------------------------------


def test_default_template_happy_path_emits_saved_terminal(company_client, auth_user):
    """With default template selected, a normal LLM run ends in report.saved."""
    queue = [
        ReportStart(
            report_id="r_1",
            department="equity_research",
            mode="stock_update",
            section_titles=["overview"],
        ),
        ReportComplete(report_id="r_1", schema=VALID_SCHEMA),
    ]
    company_client.app.state.equity_research_inner_factory = lambda: _ScriptedInner(queue)

    events = _consume(company_client)

    types = _event_types(events)
    assert "report.start" in types
    assert "report.complete" in types
    assert types[-1] == "report.saved"
    assert events[-1].get("report_id")


# ---------------------------------------------------------------------------
# Failure mode A — inner runner raises BEFORE report.complete.
# Symptom: LLM dies mid-stream. UI must see report.error, not network drop.
# ---------------------------------------------------------------------------


def test_inner_raises_before_complete_emits_error_frame(company_client, auth_user):
    queue = [
        ReportStart(
            report_id="r_2",
            department="equity_research",
            mode="stock_update",
            section_titles=["overview"],
        ),
    ]
    company_client.app.state.equity_research_inner_factory = lambda: _RaisingInner(
        queue, RuntimeError("upstream LLM transport closed")
    )

    events = _consume(company_client)

    _assert_terminal_frame(events)
    assert events[-1]["type"] == "report.error"
    assert "transport" in (events[-1].get("message") or "").lower() or events[-1].get("message")


# ---------------------------------------------------------------------------
# Failure mode B — inner runner raises AFTER report.complete (LLM credits
# already spent). This is the user-reported scenario.
# ---------------------------------------------------------------------------


def test_inner_raises_after_complete_emits_error_frame(company_client, auth_user):
    queue = [
        ReportStart(
            report_id="r_3",
            department="equity_research",
            mode="stock_update",
            section_titles=["overview"],
        ),
        ReportComplete(report_id="r_3", schema=VALID_SCHEMA),
    ]
    company_client.app.state.equity_research_inner_factory = lambda: _RaisingInner(
        queue, RuntimeError("post-complete persistence boom")
    )

    events = _consume(company_client)

    types = _event_types(events)
    # LLM completion was emitted, credits were 'spent'
    assert "report.complete" in types
    # ... but the user must still see a clean terminal frame.
    _assert_terminal_frame(events)
    assert events[-1]["type"] == "report.error"


# ---------------------------------------------------------------------------
# Failure mode C — inner emits a ReportComplete carrying an invalid schema.
# validate_report_payload raises inside the runner after the complete frame
# has already gone out. UI must see report.error, not a broken connection.
# ---------------------------------------------------------------------------


def test_invalid_schema_after_complete_emits_error_frame(company_client, auth_user):
    queue = [
        ReportStart(
            report_id="r_4",
            department="equity_research",
            mode="stock_update",
            section_titles=["overview"],
        ),
        ReportComplete(report_id="r_4", schema=INVALID_SCHEMA),
    ]
    company_client.app.state.equity_research_inner_factory = lambda: _ScriptedInner(queue)

    events = _consume(company_client)

    types = _event_types(events)
    assert "report.complete" in types
    _assert_terminal_frame(events)
    assert events[-1]["type"] == "report.error"


# ---------------------------------------------------------------------------
# Failure mode D — reports_svc.create_report raises (DB error during save).
# Hooked via monkeypatch so we exercise the route's error path without
# needing to corrupt the schema.
# ---------------------------------------------------------------------------


def test_create_report_db_failure_emits_error_frame(company_client, auth_user, monkeypatch):
    queue = [
        ReportStart(
            report_id="r_5",
            department="equity_research",
            mode="stock_update",
            section_titles=["overview"],
        ),
        ReportComplete(report_id="r_5", schema=VALID_SCHEMA),
    ]
    company_client.app.state.equity_research_inner_factory = lambda: _ScriptedInner(queue)

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated DB write failure")

    # The runner imports the module-level helper; patch its call site.
    from openlia_server.services import equity_research_runner as runner_mod

    monkeypatch.setattr(runner_mod.reports_svc, "create_report", _boom)

    events = _consume(company_client)

    types = _event_types(events)
    assert "report.complete" in types
    _assert_terminal_frame(events)
    assert events[-1]["type"] == "report.error"


# ---------------------------------------------------------------------------
# Failure mode E — a non-default template_id selected by the user no longer
# exists in the DB at the time of the report run. resolve_active falls back
# to the default sections list rather than crashing, so the run should still
# succeed end-to-end.
# ---------------------------------------------------------------------------


def test_dangling_template_selection_falls_back_to_default(company_client, auth_user, db_session):
    from openlia_server.services.equity_research_config import (
        EquityResearchConfigService,
    )

    svc = EquityResearchConfigService(db_session)
    svc.update_config(
        auth_user.id,
        selected_template_id_by_mode={"stock_update": "tpl_does_not_exist"},
    )
    db_session.commit()

    queue = [
        ReportStart(
            report_id="r_6",
            department="equity_research",
            mode="stock_update",
            section_titles=["overview"],
        ),
        ReportComplete(report_id="r_6", schema=VALID_SCHEMA),
    ]
    company_client.app.state.equity_research_inner_factory = lambda: _ScriptedInner(queue)

    events = _consume(company_client)

    _assert_terminal_frame(events)
    assert events[-1]["type"] == "report.saved"


# ---------------------------------------------------------------------------
# Pure runner-level probe: ReportSavedEvent should fire exactly once for a
# successful schema, and never if validation fails. This guards against
# regressions where the runner double-yields or eats the terminal event.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_emits_report_saved_exactly_once(db_session, auth_user):
    from openlia_server.services.equity_research_runner import EquityResearchRunner

    queue = [
        ReportStart(
            report_id="r_7",
            department="equity_research",
            mode="stock_update",
            section_titles=["overview"],
        ),
        ReportComplete(report_id="r_7", schema=VALID_SCHEMA),
    ]
    runner = EquityResearchRunner(db_session=db_session, inner=_ScriptedInner(queue))

    out: list[Any] = []
    async for ev in runner.run_report(
        user_id=auth_user.id,
        mode="stock_update",
        user_input="AAPL",
        session_id=None,
    ):
        out.append(ev)

    saved = [ev for ev in out if isinstance(ev, ReportSavedEvent)]
    assert len(saved) == 1
    assert saved[0].report_id
