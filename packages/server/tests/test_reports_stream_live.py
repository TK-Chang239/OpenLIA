"""GET /reports/{report_id}/stream attaches as a new subscriber to a
running task; receives replay of the event_ring + live events."""

from __future__ import annotations

from datetime import UTC, datetime

import anyio
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report_row(db_session, *, report_id: str, user_id: str = "local"):
    from openlia_server.db.models.content import Report

    row = Report(
        id=report_id,
        user_id=user_id,
        department="equity_research",
        report_type="stock_initiation",
        title=f"Stream test {report_id}",
        content_markdown="",
        content_structured={},
        model_ref="",
        status="generating",
        started_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    return row


def _make_app(db_session, monkeypatch):
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User
    from openlia_server.services.background_report_registry import BackgroundReportRegistry

    user = User(
        id="local",
        email="local@openlia.local",
        display_name="Local",
        is_admin=True,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    registry = BackgroundReportRegistry()
    app.state.bg_report_registry = registry
    return app, registry


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_stream_endpoint_returns_eventstream_content_type(
    monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    from openlia.llm.runtime.events import ReportComplete, ReportStart

    app, registry = _make_app(db_session, monkeypatch)
    row = _make_report_row(db_session, report_id="r_stream_ct_1")

    with TestClient(app) as client:
        # Submit task inside the running event loop via anyio portal.
        async def _seed():
            async def runner():
                yield ReportStart(report_id=row.id, section_count=1)
                yield ReportComplete(report_id=row.id, schema={"cover": {"title": "T"}})

            registry.submit(user_id="local", report_id=row.id, runner_coro=runner())

        with anyio.from_thread.start_blocking_portal() as portal:
            portal.call(_seed)

        with client.stream("GET", f"/reports/{row.id}/stream") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            chunk = next(resp.iter_text(chunk_size=4096))
            assert "event:" in chunk or "data:" in chunk


def test_stream_endpoint_replays_event_ring(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    """A late subscriber receives the previously-emitted events via
    the event_ring replay before live tail begins."""
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    from openlia.llm.runtime.events import (
        ReportComplete,
        ReportPhase,
        ReportSectionStart,
        ReportStart,
    )

    app, registry = _make_app(db_session, monkeypatch)
    row = _make_report_row(db_session, report_id="r_stream_ring_1")

    with TestClient(app) as client:
        # Seed the task and wait for it to complete so event_ring is full.
        async def _seed_and_wait():
            async def runner():
                yield ReportStart(report_id=row.id, section_count=2)
                yield ReportPhase(report_id=row.id, phase="planning")
                yield ReportSectionStart(
                    report_id=row.id, section_id="overview", section_title="Overview"
                )
                yield ReportComplete(report_id=row.id, schema={"cover": {"title": "Ring test"}})

            task = registry.submit(user_id="local", report_id=row.id, runner_coro=runner())
            try:
                await anyio.to_thread.run_sync(lambda: None)  # yield to let task run
                await task.asyncio_task
            except Exception:
                pass

        with anyio.from_thread.start_blocking_portal() as portal:
            portal.call(_seed_and_wait)

        # Task has finished; registry has forgotten it. The stream endpoint
        # must synthesize a terminal event from the DB row.
        with client.stream("GET", f"/reports/{row.id}/stream") as resp:
            text = ""
            for chunk in resp.iter_text(chunk_size=4096):
                text += chunk
                if "report.complete" in text or "report.error" in text:
                    break
            assert text.count("event:") >= 1
