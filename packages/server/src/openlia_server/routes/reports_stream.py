"""GET /reports/{report_id}/stream — SSE subscription to a background
report task. Supports both live tasks (replay ring + tail) and finished
tasks (synthetic terminal event from the persisted row)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    SseEvent,
)
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.background_report_registry import BackgroundReportRegistry


def _to_sse_frame(event: SseEvent) -> bytes:
    """Serialize an SseEvent dataclass into an SSE named-event frame."""
    event_name = getattr(event, "TYPE", type(event).__name__.lower())
    from dataclasses import asdict

    payload = asdict(event)
    return f"event: {event_name}\ndata: {json.dumps(payload, default=str)}\n\n".encode()


def _frame_for_terminal(row: Report) -> bytes:
    """Synthesize a terminal SSE frame from a finished/failed Report row."""
    if row.status == "complete":
        schema = row.content_structured or {}
        return _to_sse_frame(ReportComplete(report_id=row.id, schema=schema))
    if row.status == "cancelled":
        return _to_sse_frame(
            ReportError(
                report_id=row.id,
                error_class="cancelled",
                message="Cancelled",
            )
        )
    return _to_sse_frame(
        ReportError(
            report_id=row.id,
            error_class="failed",
            message="Generation failed",
        )
    )


def build_reports_stream_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    router = APIRouter(tags=["reports"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/reports/{report_id}/stream")
    async def stream_report(
        report_id: str,
        request: Request,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> StreamingResponse:
        row = db.execute(
            select(Report).where(Report.id == report_id, Report.user_id == user.id)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "report not found")

        registry: BackgroundReportRegistry | None = getattr(
            request.app.state, "bg_report_registry", None
        )
        task = registry.get(report_id) if registry is not None else None

        async def event_generator() -> AsyncIterator[bytes]:
            if task is None:
                yield _frame_for_terminal(row)
                return
            queue: asyncio.Queue = asyncio.Queue(maxsize=512)
            task.subscriber_queues.add(queue)
            try:
                for ev in list(task.event_ring):
                    yield _to_sse_frame(ev)
                while True:
                    ev = await queue.get()
                    yield _to_sse_frame(ev)
                    if isinstance(ev, (ReportComplete, ReportError)):
                        return
            finally:
                task.subscriber_queues.discard(queue)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return router
