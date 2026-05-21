"""v2.2 equity research routes — SSE start + resume (Steps 3 and 4).

Two endpoints:

- ``POST /api/departments/equity-research/v2/report``: start a v2 run.
  Streams ``RunnerV2`` events as named SSE frames.
- ``POST /api/departments/equity-research/v2/runs/{run_id}/resume``: take
  user clarifier answers and re-stream the continued run.

Stage factory is injected via ``app.state.v2_runner_stage_factory``.
The factory accepts the request context (db session, user, template,
composer inputs) and returns a fully constructed ``RunnerV2``. Until
production LLM wiring lands the factory will be absent and the routes
respond with 503 — the route shapes and SSE event format are still
exercisable from tests by setting the factory on a TestClient app.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.report_v2.runner_v2 import (
    ClarifierPaused,
    Completed,
    Failed,
    ResumeState,
    RunnerV2,
    StageCompleted,
    StageStarted,
)
from openlia.llm.runtime.report_v2.schemas.clarifier import ClarifierOutput
from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import pipeline_run_service as svc

log = logging.getLogger(__name__)


class V2ReportPayload(BaseModel):
    user_input: str
    session_id: str | None = None
    report_template_id: str
    composer_inputs: dict[str, Any] = {}


class V2ResumePayload(BaseModel):
    warning_actions: dict[str, str] = {}
    clarifications: dict[str, str] = {}
    question_answers: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Stage factory contract
# ---------------------------------------------------------------------------


class StageFactoryContext(BaseModel):
    """Subset of request context passed to the stage factory."""

    user_id: str
    department: str
    composer_inputs: dict[str, Any]
    template_raw: str
    template_format: str

    model_config = {"arbitrary_types_allowed": True}


StageFactory = Callable[[StageFactoryContext], RunnerV2]


# ---------------------------------------------------------------------------
# SSE frame helpers
# ---------------------------------------------------------------------------


def _frame(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


def _stage_started_frame(stage: str) -> bytes:
    return _frame("stage.started", {"stage": stage})


def _stage_completed_frame(stage: str) -> bytes:
    return _frame("stage.completed", {"stage": stage})


def _clarifier_pause_frame(
    run_id: str, round_num: int, output: ClarifierOutput
) -> bytes:
    return _frame(
        "clarifier.pause",
        {
            "run_id": run_id,
            "round": round_num,
            "output": output.model_dump(mode="json"),
        },
    )


def _completed_frame(run_id: str, html: str) -> bytes:
    return _frame("completed", {"run_id": run_id, "html": html})


def _failed_frame(run_id: str, stage: str, reason: str) -> bytes:
    return _frame(
        "failed", {"run_id": run_id, "stage": stage, "reason": reason}
    )


# ---------------------------------------------------------------------------
# Event-stream driver — shared by start + resume
# ---------------------------------------------------------------------------


async def _drive_run(
    *,
    runner: RunnerV2,
    composer_inputs: dict[str, Any],
    template_spec: Any,
    run_id: str,
    db_session_factory: Callable[[], DBSession],
    resume_state: ResumeState | None,
) -> AsyncIterator[bytes]:
    """Pull events off the synchronous RunnerV2 generator and yield SSE frames.

    Persistence-mutating events (pause, complete, fail) open a short-lived
    session so the SSE connection itself never holds a DB transaction open.
    """
    try:
        for event in runner.execute(
            composer_inputs, template_spec, resume_state=resume_state
        ):
            if isinstance(event, StageStarted):
                yield _stage_started_frame(event.stage.value)
            elif isinstance(event, StageCompleted):
                yield _stage_completed_frame(event.stage.value)
            elif isinstance(event, ClarifierPaused):
                with db_session_factory() as s:
                    svc.mark_paused(
                        s,
                        run_id,
                        stage="clarify",
                        clarifier_output=event.output.model_dump(mode="json"),
                        clarifier_round=event.round,
                        clarification_history=[
                            c.model_dump(mode="json")
                            for c in event.clarification_history
                        ],
                    )
                    s.commit()
                yield _clarifier_pause_frame(run_id, event.round, event.output)
                return
            elif isinstance(event, Completed):
                with db_session_factory() as s:
                    svc.mark_completed(s, run_id)
                    s.commit()
                yield _completed_frame(run_id, event.html)
                return
            elif isinstance(event, Failed):
                with db_session_factory() as s:
                    svc.mark_failed(s, run_id, reason=event.reason)
                    s.commit()
                yield _failed_frame(run_id, event.stage.value, event.reason)
                return
    except Exception as exc:  # defensive: orchestrator itself raised
        log.exception("v2 runner exited unexpectedly for run %s", run_id)
        with db_session_factory() as s:
            try:
                svc.mark_failed(s, run_id, reason=str(exc))
                s.commit()
            except Exception:
                log.exception("failed to mark run %s as failed", run_id)
        yield _failed_frame(run_id, "unknown", str(exc))


def _get_factory(request: Request) -> StageFactory:
    factory = getattr(request.app.state, "v2_runner_stage_factory", None)
    if factory is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "v2_engine_unavailable",
                "message": (
                    "v2.2 pipeline factory is not wired on this deployment."
                ),
            },
        )
    return factory


# ---------------------------------------------------------------------------
# Router builder
# ---------------------------------------------------------------------------


def build_equity_research_v2_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(
        db_session_factory=db_session_factory, mode=mode
    )
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/departments/equity-research/v2", tags=["equity-research-v2"]
    )

    @router.post("/report")
    async def start_v2_report(
        payload: V2ReportPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        factory = _get_factory(request)

        # Load and validate the template before persisting the run row.
        try:
            template_spec, _notices = load_template_v2(
                _resolve_template_raw(db, payload.report_template_id),
                fmt="yaml",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_template",
                    "message": str(exc),
                },
            ) from exc

        composer_inputs = {**payload.composer_inputs, "prompt": payload.user_input}
        template_raw = _resolve_template_raw(db, payload.report_template_id)

        row = svc.create_run(
            db,
            user_id=user.id,
            session_id=payload.session_id,
            department="equity_research",
            template_id=payload.report_template_id,
            template_raw=template_raw,
            template_format="yaml",
            composer_inputs=composer_inputs,
        )
        db.commit()

        ctx = StageFactoryContext(
            user_id=user.id,
            department="equity_research",
            composer_inputs=composer_inputs,
            template_raw=template_raw,
            template_format="yaml",
        )
        runner = factory(ctx)

        return StreamingResponse(
            _drive_run(
                runner=runner,
                composer_inputs=composer_inputs,
                template_spec=template_spec,
                run_id=row.id,
                db_session_factory=db_session_factory,
                resume_state=None,
            ),
            media_type="text/event-stream",
            headers={"X-Run-Id": row.id},
        )

    @router.post("/runs/{run_id}/resume")
    async def resume_v2_report(
        run_id: str,
        payload: V2ResumePayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        factory = _get_factory(request)

        row = svc.get_run(db, run_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "run not found"},
            )
        if row.state != "CLARIFY_AWAITING_USER":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "not_paused",
                    "message": f"run is in state {row.state!r}, not paused",
                },
            )

        # Hydrate template + clarification history from the row.
        try:
            template_spec, _notices = load_template_v2(
                row.template_raw, fmt=row.template_format
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={"code": "invalid_persisted_template", "message": str(exc)},
            ) from exc

        clarification_history = [
            ClarifierOutput.model_validate(c) for c in (row.clarification_history or [])
        ]
        resume_state = ResumeState(
            clarification_history=clarification_history,
            answers={
                "warning_actions": dict(payload.warning_actions),
                "clarifications": dict(payload.clarifications),
                "question_answers": dict(payload.question_answers),
            },
        )

        svc.mark_running(db, run_id)
        db.commit()

        ctx = StageFactoryContext(
            user_id=user.id,
            department="equity_research",
            composer_inputs=dict(row.composer_inputs or {}),
            template_raw=row.template_raw,
            template_format=row.template_format,
        )
        runner = factory(ctx)

        return StreamingResponse(
            _drive_run(
                runner=runner,
                composer_inputs=dict(row.composer_inputs or {}),
                template_spec=template_spec,
                run_id=row.id,
                db_session_factory=db_session_factory,
                resume_state=resume_state,
            ),
            media_type="text/event-stream",
            headers={"X-Run-Id": row.id},
        )

    return router


# ---------------------------------------------------------------------------
# Template loading helper (decoupled so tests can override)
# ---------------------------------------------------------------------------


def _resolve_template_raw(db: DBSession, report_template_id: str) -> str:
    """Read raw template YAML from the bundled v2.2 set or the custom store.

    For the moment we support the three bundled v2.2 templates by id; custom
    templates would require a separate lookup against the report_templates
    table. That lookup is left out of step 3 — production wiring lands when
    the orchestrator picks up its real LLM dependencies.
    """
    from pathlib import Path

    bundled_dir = (
        Path(__file__).resolve().parents[5]
        / "core"
        / "src"
        / "openlia"
        / "llm"
        / "runtime"
        / "report_v2"
        / "templates"
    )
    candidate = bundled_dir / f"{report_template_id}.yaml"
    if candidate.exists():
        return candidate.read_text()
    raise FileNotFoundError(
        f"v2 template {report_template_id!r} not found in bundled set "
        f"({bundled_dir})"
    )
