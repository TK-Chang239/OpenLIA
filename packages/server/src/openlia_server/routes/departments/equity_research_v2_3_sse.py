"""SSE routes for the v2.3 equity-research pipeline.

Two endpoints, both Server-Sent Events streams:

- ``POST /api/departments/equity-research/v2.3/runs/stream``
    Start a new v2.3 run; stream stage events live as the runner walks
    the pipeline. Closes with a ``state`` frame carrying the final
    persisted ``ReportState`` (or the suspended one if CLARIFY paused).

- ``POST /api/departments/equity-research/v2.3/runs/{run_id}/answer/stream``
    Resume a suspended run with the user's clarify answers. Same event
    stream shape.

Because ``ReportRunner`` is a synchronous, non-generator state machine,
the route runs it in a worker thread and pushes ``RunnerEvent`` items
into an ``asyncio.Queue`` via an observer. The SSE generator awaits
queue items and serializes each as an SSE frame. The worker thread
opens its own DB session (SQLAlchemy sessions are not thread-safe), so
the route's request-scoped session is never shared across threads.

Frame shapes:

  event: stage_started
  data: {"slot": "clarify"}

  event: stage_completed
  data: {"slot": "clarify", "retry_count": 0}

  event: suspended
  data: {"slot": "clarify", "questions": [...], "state": {...}}

  event: failed
  data: {"slot": "clarify", "error": "...", "state": {...}}

  event: completed
  data: {"state": {...}}

The trailing ``state`` payload on terminal frames lets the client
update its UI without an extra GET round-trip.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.report_v2_3.events import (
    Completed,
    Failed,
    RunnerEvent,
    StageCompleted,
    StageStarted,
    Suspended,
)
from openlia.llm.runtime.report_v2_3.persistence import StateNotFoundError
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyAnswers,
    Language,
    ReportLength,
    ReportType,
)
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.types import ReasoningEffort
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.routes.departments.equity_research_v2_3 import (
    RunStateOut,
    _engine_unavailable,
    _per_user_factory,
    _read_persisted_reasoning_effort,
)
from openlia_server.services import v2_3_run_service as svc

log = logging.getLogger(__name__)


class StartStreamPayload(BaseModel):
    raw_prompt: str
    language: Language = Language.EN
    report_type: ReportType = ReportType.INITIATION
    length: ReportLength = ReportLength.NORMAL
    # See StartPayload in equity_research_v2_3.py for semantics.
    template_id: str | None = None
    # Optional — empty list means "let CLARIFY infer the subject
    # ticker from raw_prompt".
    tickers: list[str] = Field(default_factory=list)
    # User-selected extended-thinking effort (3-state pill on the report
    # settings modal: off / medium / high). ``None`` = off; the runtime
    # only applies the directive to PLAN + SYNTHESIZE stages.
    reasoning_effort: ReasoningEffort | None = None


class AnswerStreamPayload(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


def build_equity_research_v2_3_sse_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/departments/equity-research/v2.3",
        tags=["equity-research-v2.3-sse"],
    )

    def _resolve_factory(
        request: Request,
        db: DBSession,
        user: User,
        *,
        reasoning_effort: ReasoningEffort | None = None,
    ):
        per_user = _per_user_factory(db, user, reasoning_effort=reasoning_effort)
        if per_user is not None:
            return per_user
        # Env-driven fallback factory was built once at startup with no
        # reasoning_effort. The per-user path is what production users
        # exercise; the env path is a dev convenience and stays flat.
        env_factory = getattr(request.app.state, "v2_3_runner_factory", None)
        if env_factory is None:
            raise _engine_unavailable()
        return env_factory

    @router.post("/runs/stream")
    async def start_run_stream(
        payload: StartStreamPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        runner_factory = _resolve_factory(
            request, db, user, reasoning_effort=payload.reasoning_effort
        )

        def _worker(observer):
            with db_session_factory() as worker_db:
                return svc.start_run(
                    db=worker_db,
                    runner_factory=runner_factory,
                    user_id=user.id,
                    raw_prompt=payload.raw_prompt,
                    language=payload.language,
                    report_type=payload.report_type,
                    length=payload.length,
                    template_id=payload.template_id,
                    tickers=payload.tickers,
                    reasoning_effort=payload.reasoning_effort,
                    observer=observer,
                )

        return StreamingResponse(
            _drive_run(_worker),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    @router.post("/runs/{run_id}/answer/stream")
    async def answer_run_stream(
        run_id: str,
        payload: AnswerStreamPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        # Resume must use the same reasoning_effort the original start
        # picked, so PLAN + SYNTHESIZE get the same ceiling growth. Read
        # it off the persisted state (set on start_run) before building
        # the factory — falls back to None for runs created before this
        # field existed.
        persisted_effort = _read_persisted_reasoning_effort(db, run_id)
        runner_factory = _resolve_factory(request, db, user, reasoning_effort=persisted_effort)
        answers = ClarifyAnswers(answers=payload.answers)

        def _worker(observer):
            with db_session_factory() as worker_db:
                return svc.answer_run(
                    db=worker_db,
                    runner_factory=runner_factory,
                    user_id=user.id,
                    run_id=run_id,
                    answers=answers,
                    observer=observer,
                )

        return StreamingResponse(
            _drive_run(_worker, run_id=run_id),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    return router


# ---------------------------------------------------------------------------
# Worker driver
# ---------------------------------------------------------------------------


_SENTINEL = object()


async def _drive_run(
    worker: Callable[[Any], ReportState], *, run_id: str | None = None
) -> AsyncIterator[bytes]:
    """Run ``worker`` in a background thread; yield SSE frames per event.

    ``worker`` receives a synchronous observer callable; it should invoke
    the run service (which forwards the observer to the runner). When
    the run completes we read the final state via the worker's return
    value and emit it on a terminal frame.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Any] = asyncio.Queue()

    def _observer(event: RunnerEvent) -> None:
        # Pushed from the worker thread; hop back to the loop thread.
        loop.call_soon_threadsafe(queue.put_nowait, event)

    final_state: dict[str, Any] = {}
    error: dict[str, Any] = {}

    def _run_worker() -> None:
        try:
            state = worker(_observer)
            final_state["state"] = state
        except StateNotFoundError as exc:
            error["kind"] = "not_found"
            error["message"] = str(exc)
        except PermissionError as exc:
            error["kind"] = "forbidden"
            error["message"] = str(exc)
        except ValueError as exc:
            # e.g. resume() called when not WAITING_ON_USER
            error["kind"] = "invalid_state"
            error["message"] = str(exc)
        except Exception as exc:
            log.exception("v2.3 SSE worker raised for run %s", run_id)
            error["kind"] = "worker_error"
            error["message"] = str(exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

    thread = threading.Thread(target=_run_worker, daemon=True)
    thread.start()

    saw_terminal = False
    try:
        while True:
            event = await queue.get()
            if event is _SENTINEL:
                break
            if isinstance(event, StageStarted):
                yield _frame("stage_started", {"slot": event.slot.value})
            elif isinstance(event, StageCompleted):
                yield _frame(
                    "stage_completed",
                    {"slot": event.slot.value, "retry_count": event.retry_count},
                )
            elif isinstance(event, Suspended):
                saw_terminal = True
                payload = {
                    "slot": event.slot.value,
                    "questions": [q.model_dump(mode="json") for q in event.questions],
                }
                # State + suspended frame emitted at end of worker.
                yield _frame("suspended", payload)
            elif isinstance(event, Failed):
                saw_terminal = True
                yield _frame(
                    "failed",
                    {
                        "slot": event.slot.value if event.slot is not None else None,
                        "error": event.error,
                    },
                )
            elif isinstance(event, Completed):
                saw_terminal = True
                yield _frame("completed", {})
    finally:
        # Wait for the worker to finish so its DB commit lands before we
        # read state out. Bound the wait to avoid hanging on a stuck
        # worker; in practice the queue sentinel is the last thing the
        # worker emits, so this is fast.
        await asyncio.get_running_loop().run_in_executor(None, thread.join, 30.0)

    if error:
        kind = error.get("kind", "worker_error")
        status_code = {
            "not_found": 404,
            "forbidden": 403,
            "invalid_state": 409,
        }.get(kind)
        # SSE has already started — we can't change the HTTP status. Emit
        # a final error frame so the client can present the failure.
        yield _frame(
            "failed",
            {"slot": None, "error": error.get("message", "unknown"), "status": status_code},
        )
        return

    state = final_state.get("state")
    if state is not None:
        out = RunStateOut.from_state(state).model_dump(mode="json")
        if not saw_terminal:
            # Defensive: a synchronous path that returns without any
            # terminal event still needs a frame the client can act on.
            yield _frame("state", out)
        else:
            yield _frame("state", out)


def _frame(event: str, payload: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()
