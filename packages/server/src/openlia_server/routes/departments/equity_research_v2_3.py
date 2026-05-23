"""v2.3 equity-research run-lifecycle routes (PR3 scope).

Plain JSON endpoints — no SSE yet:

- ``POST /api/departments/equity-research/v2.3/runs``
    Start a new v2.3 run; returns the resulting (possibly suspended) state.
- ``POST /api/departments/equity-research/v2.3/runs/{run_id}/answer``
    Resume a suspended run with the user's clarifier answers.
- ``GET  /api/departments/equity-research/v2.3/runs/{run_id}``
    Read the persisted state.

The runner factory is injected via ``app.state.v2_3_runner_factory``; if it
is unset (no clarifier client available in this deployment) the routes
respond 503 with ``code=v2_3_engine_unavailable``.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from openlia.llm.runtime.report_v2_3.persistence import StateNotFoundError
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyAnswers,
    ClarifyNeedsInput,
    ClarifyProceed,
    ClarifyQuestion,
    Language,
    ReportType,
    RunStatus,
)
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.state import ReportState
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import v2_3_run_service as svc
from openlia_server.services.v2_3_runner_factory import V23RunnerFactory


class StartPayload(BaseModel):
    raw_prompt: str
    language: Language = Language.EN
    report_type: ReportType = ReportType.INITIATION
    tickers: list[str] = Field(..., min_length=1)


class AnswerPayload(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class ClarifyResultOut(BaseModel):
    outcome: str
    assumptions: list[str] = Field(default_factory=list)
    questions: list[ClarifyQuestion] = Field(default_factory=list)


class RunStateOut(BaseModel):
    run_id: str
    status: RunStatus
    current_stage: V23Slot | None
    pending_questions: list[ClarifyQuestion]
    clarify_result: ClarifyResultOut | None
    last_error: str | None
    retry_count: int

    @classmethod
    def from_state(cls, state: ReportState) -> RunStateOut:
        cr: ClarifyResultOut | None = None
        if isinstance(state.clarify_result, ClarifyProceed):
            cr = ClarifyResultOut(
                outcome="proceed", assumptions=state.clarify_result.assumptions
            )
        elif isinstance(state.clarify_result, ClarifyNeedsInput):
            cr = ClarifyResultOut(
                outcome="needs_input", questions=state.clarify_result.questions
            )
        return cls(
            run_id=state.run_id,
            status=state.status,
            current_stage=state.current_stage,
            pending_questions=list(state.pending_questions),
            clarify_result=cr,
            last_error=state.last_error,
            retry_count=state.retry_count,
        )


def _engine_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "v2_3_engine_unavailable",
            "message": "v2.3 runner factory is not wired on this deployment.",
        },
    )


def build_equity_research_v2_3_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/departments/equity-research/v2.3",
        tags=["equity-research-v2.3"],
    )

    def _factory(request: Request) -> V23RunnerFactory:
        factory = getattr(request.app.state, "v2_3_runner_factory", None)
        if factory is None:
            raise _engine_unavailable()
        return factory

    @router.post("/runs", response_model=RunStateOut)
    def start_run(
        payload: StartPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunStateOut:
        state = svc.start_run(
            db=db,
            runner_factory=_factory(request),
            user_id=user.id,
            raw_prompt=payload.raw_prompt,
            language=payload.language,
            report_type=payload.report_type,
            tickers=payload.tickers,
        )
        return RunStateOut.from_state(state)

    @router.post("/runs/{run_id}/answer", response_model=RunStateOut)
    def answer_run(
        run_id: str,
        payload: AnswerPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunStateOut:
        try:
            state = svc.answer_run(
                db=db,
                runner_factory=_factory(request),
                user_id=user.id,
                run_id=run_id,
                answers=ClarifyAnswers(answers=payload.answers),
            )
        except StateNotFoundError:
            raise HTTPException(
                status_code=404,
                detail={"code": "run_not_found", "message": f"run {run_id} not found"},
            ) from None
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail={"code": "run_not_yours", "message": "run belongs to another user"},
            ) from None
        except ValueError as exc:
            # e.g. resume() called on a run that is not WAITING_ON_USER.
            raise HTTPException(
                status_code=409,
                detail={"code": "invalid_run_state", "message": str(exc)},
            ) from None
        return RunStateOut.from_state(state)

    @router.get("/runs/{run_id}", response_model=RunStateOut)
    def get_run(
        run_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunStateOut:
        try:
            state = svc.get_run(db=db, user_id=user.id, run_id=run_id)
        except StateNotFoundError:
            raise HTTPException(
                status_code=404,
                detail={"code": "run_not_found", "message": f"run {run_id} not found"},
            ) from None
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail={"code": "run_not_yours", "message": "run belongs to another user"},
            ) from None
        return RunStateOut.from_state(state)

    return router
