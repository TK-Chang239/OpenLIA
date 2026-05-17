"""Per-task wrapper coroutine: drives the runner, persists status
transitions, and fans completion/failure/cancellation notifications
to the user's presence channel."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.llm.runtime.events import ReportComplete, ReportError


class _PresenceLike(Protocol):
    def fanout(self, user_id: str, event: dict) -> None: ...


async def run_wrapped_report(
    *,
    runner_coro: AsyncIterator[Any],
    report_id: str,
    user_id: str,
    db_session_factory,
    presence: _PresenceLike,
    registry,
) -> None:
    """Run the report generator to completion; persist status and
    notify on terminal events. Caller is expected to schedule this on
    the event loop via ``BackgroundReportRegistry.submit`` (which
    handles fan-out to subscriber queues; this wrapper handles
    persistence and notifications only)."""
    try:
        async for event in runner_coro:
            if isinstance(event, ReportComplete):
                _persist_complete(db_session_factory, report_id, event.schema)
                presence.fanout(
                    user_id,
                    {
                        "type": "report.complete",
                        "report_id": report_id,
                        "title": (event.schema.get("cover", {}) or {}).get("title", ""),
                    },
                )
            elif isinstance(event, ReportError):
                _persist_failed(db_session_factory, report_id, event.message)
                presence.fanout(
                    user_id,
                    {
                        "type": "report.failed",
                        "report_id": report_id,
                        "failure_reason": event.message,
                    },
                )
    except asyncio.CancelledError:
        _persist_cancelled(db_session_factory, report_id, "user_cancelled")
        presence.fanout(user_id, {"type": "report.cancelled", "report_id": report_id})
        raise


def _persist_complete(db_session_factory, report_id: str, schema: dict) -> None:
    from openlia_server.db.models.content import Report

    with db_session_factory() as session:
        row = session.get(Report, report_id)
        if row is None:
            return
        row.status = "complete"
        row.completed_at = datetime.now(UTC) if hasattr(row, "completed_at") else None
        row.report_schema_json = json.dumps(schema, default=str)
        session.commit()


def _persist_failed(db_session_factory, report_id: str, message: str) -> None:
    from openlia_server.db.models.content import Report

    with db_session_factory() as session:
        row = session.get(Report, report_id)
        if row is None:
            return
        row.status = "failed"
        row.failure_reason = (message or "")[:500]
        session.commit()


def _persist_cancelled(db_session_factory, report_id: str, reason: str) -> None:
    from openlia_server.db.models.content import Report

    with db_session_factory() as session:
        row = session.get(Report, report_id)
        if row is None:
            return
        row.status = "cancelled"
        row.failure_reason = reason
        session.commit()
