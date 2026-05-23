"""v2.3 equity-research run-lifecycle routes.

Plain JSON endpoints (SSE companion lives in equity_research_v2_3_sse.py):

- ``POST   /api/departments/equity-research/v2.3/runs``
    Start a new v2.3 run; returns the resulting (possibly suspended) state.
- ``POST   /api/departments/equity-research/v2.3/runs/{run_id}/answer``
    Resume a suspended run with the user's clarifier answers.
- ``GET    /api/departments/equity-research/v2.3/runs/{run_id}``
    Read the persisted state.
- ``GET    /api/departments/equity-research/v2.3/runs``
    List the caller's runs (newest first). Optional ``status`` filter.
- ``DELETE /api/departments/equity-research/v2.3/runs/{run_id}``
    Drop a run from persistence.
- ``GET    /api/departments/equity-research/v2.3/runs/{run_id}/docx``
    Render the completed run as a Word document and stream it back.
- ``GET    /api/departments/equity-research/v2.3/runs/{run_id}/payload``
    Return the run's structured payload (resolved report + charts + minimal
    bundle facts) so the React renderer can produce the on-screen view.
    The docx and the browser view both consume this payload — one source
    of truth, two renderers.

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
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
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
from openlia_server.services.v2_3_docx import render_docx
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


class RunSummaryOut(BaseModel):
    run_id: str
    status: str
    tickers: list[str]
    raw_prompt: str
    report_type: str
    language: str
    created_at: datetime
    updated_at: datetime


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


class PayloadBundleSeriesPoint(BaseModel):
    period: str
    value: float


class PayloadBundleFact(BaseModel):
    """Bundle fact projected for the browser renderer.

    Carries only the fields the React side needs to plot a chart or
    look up a value — `Provenance` is intentionally dropped because the
    footnote text already encodes the resolved citation.
    """

    id: str
    label: str
    value: float | str | list[PayloadBundleSeriesPoint]
    unit: str | None = None
    ticker: str | None = None


class PayloadChartSeries(BaseModel):
    name: str
    value_fact_ids: list[str]


class PayloadChartSpec(BaseModel):
    id: str
    section_id: str
    claim: str
    chart_type: str
    title: str
    category_labels: list[str]
    series: list[PayloadChartSeries]
    x_axis_label: str | None = None
    y_axis_label: str | None = None


class PayloadCanonicalFigure(BaseModel):
    fact_id: str
    display: str


class PayloadOutlineSection(BaseModel):
    id: str
    title: str


class PayloadThesis(BaseModel):
    language: str
    central_argument: str
    key_takeaways: list[str]
    valuation_stance: str
    canonical_figures: list[PayloadCanonicalFigure]


class RunPayloadOut(BaseModel):
    """JSON shape consumed by ``<V23ReportView>`` in the frontend.

    Fields:
    - ``run_id`` / ``tickers`` / ``report_type`` / ``language`` — cover-page
      metadata.
    - ``thesis`` — central argument, takeaways, canonical figures.
    - ``sections`` — ordered (id, title) pairs so the renderer keeps the
      outline's section order.
    - ``section_bodies`` — resolved prose; still carries ``[^N]`` footnote
      markers and ``{{FIG:id}}`` chart placeholders for the renderer to
      transform inline.
    - ``footnotes`` — index N -> the resolved citation text the marker
      points at.
    - ``charts`` — ChartSpecs assigned to sections, keyed by id.
    - ``figure_labels`` — chart id -> 1-based figure number (the renderer
      shows "Figure N: …" in captions).
    - ``bundle_facts`` — minimal projection of facts the charts reference,
      so the React chart components can plot real numbers instead of
      placeholders.
    """

    run_id: str
    tickers: list[str]
    report_type: str
    language: str
    thesis: PayloadThesis
    sections: list[PayloadOutlineSection]
    section_bodies: dict[str, str]
    footnotes: list[str]
    charts: list[PayloadChartSpec]
    figure_labels: dict[str, int]
    bundle_facts: dict[str, PayloadBundleFact]


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

    @router.get("/runs", response_model=list[RunSummaryOut])
    def list_runs(
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> list[RunSummaryOut]:
        rows = svc.list_runs(db=db, user_id=user.id, status=status, limit=limit)
        return [
            RunSummaryOut(
                run_id=r.run_id,
                status=r.status,
                tickers=r.tickers,
                raw_prompt=r.raw_prompt,
                report_type=r.report_type,
                language=r.language,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    @router.delete("/runs/{run_id}", status_code=204)
    def delete_run(
        run_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        try:
            svc.delete_run(db=db, user_id=user.id, run_id=run_id)
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
        return Response(status_code=204)

    @router.get("/runs/{run_id}/docx")
    def download_docx(
        run_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
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
        if state.status != RunStatus.COMPLETE or state.resolved is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "run_not_complete",
                    "message": (
                        "docx export is only available for completed runs; "
                        f"current status is {state.status.value}."
                    ),
                },
            )
        try:
            blob = render_docx(state)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=500,
                detail={"code": "render_failed", "message": str(exc)},
            ) from None
        ticker_part = "_".join(state.tickers) if state.tickers else "report"
        filename = f"v2.3_{ticker_part}_{state.run_id[:8]}.docx"
        return Response(
            content=blob,
            media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/runs/{run_id}/payload", response_model=RunPayloadOut)
    def get_run_payload(
        run_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunPayloadOut:
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
        if (
            state.status != RunStatus.COMPLETE
            or state.resolved is None
            or state.thesis is None
            or state.outline is None
            or state.bundle is None
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "run_not_complete",
                    "message": (
                        "payload export is only available for completed runs; "
                        f"current status is {state.status.value}."
                    ),
                },
            )
        return _project_payload(state)

    return router


def _project_payload(state: ReportState) -> RunPayloadOut:
    """Project a completed ``ReportState`` into the JSON shape the React
    renderer consumes. Strips ``Provenance`` (encoded into footnotes already)
    and narrows ``BundleFact.value`` to the renderable subset.
    """
    assert state.resolved is not None
    assert state.thesis is not None
    assert state.outline is not None
    assert state.bundle is not None

    charts_payload = [
        PayloadChartSpec(
            id=c.id,
            section_id=c.section_id,
            claim=c.claim,
            chart_type=c.chart_type.value,
            title=c.title,
            category_labels=list(c.category_labels),
            series=[
                PayloadChartSeries(name=s.name, value_fact_ids=list(s.value_fact_ids))
                for s in c.series
            ],
            x_axis_label=c.x_axis_label,
            y_axis_label=c.y_axis_label,
        )
        for c in state.thesis.charts
    ]

    bundle_facts: dict[str, PayloadBundleFact] = {}
    for fid, fact in state.bundle.facts.items():
        value: float | str | list[PayloadBundleSeriesPoint]
        raw = fact.value
        if isinstance(raw, (int, float, str)):
            value = raw if isinstance(raw, str) else float(raw)
        else:
            value = [PayloadBundleSeriesPoint(period=p.period, value=p.value) for p in raw.points]
        bundle_facts[fid] = PayloadBundleFact(
            id=fact.id,
            label=fact.label,
            value=value,
            unit=fact.unit,
            ticker=fact.ticker,
        )

    return RunPayloadOut(
        run_id=state.run_id,
        tickers=list(state.tickers),
        report_type=state.report_type.value,
        language=state.language.value,
        thesis=PayloadThesis(
            language=state.thesis.language.value,
            central_argument=state.thesis.central_argument,
            key_takeaways=list(state.thesis.key_takeaways),
            valuation_stance=state.thesis.valuation_stance,
            canonical_figures=[
                PayloadCanonicalFigure(fact_id=cf.fact_id, display=cf.display)
                for cf in state.thesis.canonical_figures
            ],
        ),
        sections=[PayloadOutlineSection(id=s.id, title=s.title) for s in state.outline.sections],
        section_bodies=dict(state.resolved.section_bodies),
        footnotes=list(state.resolved.footnotes),
        charts=charts_payload,
        figure_labels=dict(state.resolved.figure_labels),
        bundle_facts=bundle_facts,
    )


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
