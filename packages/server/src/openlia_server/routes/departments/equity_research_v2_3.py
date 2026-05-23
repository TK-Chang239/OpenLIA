"""v2.3 equity-research run-lifecycle routes.

Plain JSON endpoints — no SSE yet:

- ``POST /api/departments/equity-research/v2.3/runs``
    Start a new v2.3 run; returns the resulting (possibly suspended) state.
- ``POST /api/departments/equity-research/v2.3/runs/{run_id}/answer``
    Resume a suspended run with the user's clarifier answers.
- ``GET  /api/departments/equity-research/v2.3/runs/{run_id}``
    Read the persisted state.

Factory resolution order, per request:

1. If the caller has per-stage model assignments in
   ``er_v2_3_model_assignments``, build a per-user factory through
   ``build_v2_3_runner_factory_from_models``. This is the production
   path.
2. Otherwise fall back to ``app.state.v2_3_runner_factory`` — the
   env-driven factory (set at app startup) — for smoke / dev runs
   where no per-user picker exists yet.
3. If neither is available, respond 503.
"""

from __future__ import annotations

import os
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
from openlia.llm.runtime.report_v2_3.slots import LLM_V23_SLOTS, V23Slot
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import er_v2_3_models as model_assignments_svc
from openlia_server.services import v2_3_run_service as svc
from openlia_server.services.llm_registry import SQLModelRegistry
from openlia_server.services.v2_3_runner_factory import V23RunnerFactory
from openlia_server.services.v2_3_wiring import build_v2_3_runner_factory_from_models


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
            cr = ClarifyResultOut(outcome="proceed", assumptions=state.clarify_result.assumptions)
        elif isinstance(state.clarify_result, ClarifyNeedsInput):
            cr = ClarifyResultOut(outcome="needs_input", questions=state.clarify_result.questions)
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

    def _factory(request: Request, db: DBSession, user: User) -> V23RunnerFactory:
        per_user = _per_user_factory(db, user)
        if per_user is not None:
            return per_user
        env_factory = getattr(request.app.state, "v2_3_runner_factory", None)
        if env_factory is None:
            raise _engine_unavailable()
        return env_factory

    @router.post("/runs", response_model=RunStateOut)
    def start_run(
        payload: StartPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunStateOut:
        state = svc.start_run(
            db=db,
            runner_factory=_factory(request, db, user),
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
                runner_factory=_factory(request, db, user),
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


def _per_user_factory(db: DBSession, user: User) -> V23RunnerFactory | None:
    """Resolve the caller's saved v2.3 model assignments and build a runner
    factory bound to them. Returns None when no clarify assignment exists
    so the route can fall back to the env-driven factory.

    Any assigned model id that does not resolve raises 422 — silently
    NoOp'ing a stage the user asked to enable would surprise them.
    """
    mapping = model_assignments_svc.get_assignments(db, user_id=user.id)
    if "clarify" not in mapping:
        return None
    registry = SQLModelRegistry(db)
    resolved: dict[str, ResolvedModel] = {}
    unresolved: list[dict[str, str]] = []
    for slot, model_id in mapping.items():
        if slot not in {s.value for s in LLM_V23_SLOTS}:
            continue
        row = registry.get_by_id(model_id)
        if row is None:
            unresolved.append({"slot": slot, "model_id": model_id})
            continue
        resolved[slot] = _to_resolved_model(row)
    if unresolved:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "models_unresolvable",
                "message": (
                    "One or more assigned v2.3 models could not be resolved; "
                    "re-assign the affected slots."
                ),
                "unresolved": unresolved,
            },
        )
    eodhd_key = os.getenv("EODHD_API_KEY")
    return build_v2_3_runner_factory_from_models(models_by_slot=resolved, eodhd_api_key=eodhd_key)


def _to_resolved_model(row: object) -> ResolvedModel:
    """Translate an ``LLMModel`` ORM row into a ``ResolvedModel`` dataclass."""
    provider = row.provider  # type: ignore[attr-defined]
    credentials = ProviderCredentials(
        api_key=provider.api_key,
        base_url=provider.base_url,
        env_var_name=provider.env_var_name,
    )
    return ResolvedModel(
        provider_kind=provider.kind,
        provider_id=provider.id,
        model_id=row.id,  # type: ignore[attr-defined]
        model_ref=row.model_ref,  # type: ignore[attr-defined]
        credentials=credentials,
        capabilities=Capabilities(
            structured_output=True,
            tool_calling=True,
            max_context_tokens=128_000,
            max_output_tokens=4096,
        ),
        overrides=row.overrides or {},  # type: ignore[attr-defined]
    )
