"""v2.2 equity research routes — SSE start + resume (Steps 3 and 4).

Two endpoints:

- ``POST /api/departments/equity-research/v2/report``: start a v2 run.
  Streams ``RunnerV2`` events as named SSE frames.
- ``POST /api/departments/equity-research/v2/runs/{run_id}/resume``: take
  user clarifier answers and re-stream the continued run.

Stage factory is injected via ``app.state.v2_runner_stage_factory``.
The factory accepts the request context (department, composer inputs,
raw template, etc.) and returns a fully constructed ``RunnerV2``. The
default factory lives in ``services.v2_stage_factory`` and builds
LLM-backed stages from env-resolved credentials; if the factory raises
during construction the routes respond with 503 carrying
``code=v2_engine_unavailable``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from openlia.llm.resolver import _to_resolved
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
from openlia.llm.runtime.report_v2.slots import REQUIRED_V2_SLOTS
from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import er_v2_models as model_assignments_svc
from openlia_server.services import pipeline_run_service as svc
from openlia_server.services.llm_registry import SQLModelRegistry
from openlia_server.services.report_docx import assemble_docx
from openlia_server.services.report_export import (
    capture_chart_pngs,
    export_report_pdf,
)

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
    # Pre-resolved per-slot models. Keys are V2Slot string values; all eight
    # required slots MUST be present. The route layer enforces this before
    # constructing the factory context.
    models_by_slot: dict[str, Any] = {}

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


def _clarifier_pause_frame(run_id: str, round_num: int, output: ClarifierOutput) -> bytes:
    return _frame(
        "clarifier.pause",
        {
            "run_id": run_id,
            "round": round_num,
            "output": output.model_dump(mode="json"),
        },
    )


def _completed_frame(run_id: str, report: dict[str, Any]) -> bytes:
    return _frame("completed", {"run_id": run_id, "report": report})


def _failed_frame(run_id: str, stage: str, reason: str) -> bytes:
    return _frame("failed", {"run_id": run_id, "stage": stage, "reason": reason})


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
        for event in runner.execute(composer_inputs, template_spec, resume_state=resume_state):
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
                            c.model_dump(mode="json") for c in event.clarification_history
                        ],
                    )
                    s.commit()
                yield _clarifier_pause_frame(run_id, event.round, event.output)
                return
            elif isinstance(event, Completed):
                report_dict = event.report.model_dump(mode="json")
                with db_session_factory() as s:
                    svc.mark_completed(s, run_id, final_report=report_dict)
                    s.commit()
                yield _completed_frame(run_id, report_dict)
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
                "message": ("v2.2 pipeline factory is not wired on this deployment."),
            },
        )
    return factory


def _forward_session_cookie_for_render(
    request: Request, base_url: str
) -> list[dict[str, Any]] | None:
    """Build a Playwright cookies list so the print-mode SPA can fetch the
    v2 report payload from `/api/.../runs/{run_id}/report` against the
    protected backend. Returns None when no session cookie is present.
    """
    from urllib.parse import urlparse

    session_cookie = request.cookies.get("openlia_session") or request.cookies.get(
        "session"
    )
    if not session_cookie:
        return None
    parsed = urlparse(base_url)
    return [
        {
            "name": "openlia_session",
            "value": session_cookie,
            "domain": parsed.hostname or "127.0.0.1",
            "path": "/",
        }
    ]


def _sanitize_filename_v2(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name).strip("_")
    return safe or "report"


async def _export_v2_run(
    *,
    run_id: str,
    request: Request,
    db: DBSession,
    user: User,
    fmt: str,
) -> Response:
    """Shared PDF/DOCX export driver for v2.2 pipeline_runs.

    Mirrors the v1 export pattern: ensure browser launcher + render base
    URL are configured, build the bundle URL for the v2 print page,
    invoke the same Playwright pipeline. The v2 print page (route
    /reports/v2/{runId}/render) fetches the ReportV2 JSON, runs the
    v2→v1 block adapter, and renders through v1's ReportRenderer — so
    the export output uses identical chrome to v1 reports.
    """
    row = svc.get_run(db, run_id)
    if (
        row is None
        or row.user_id != user.id
        or row.deleted_at is not None
        or row.expired_at is not None
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "run not found"},
        )
    if not row.final_report_json:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "report_not_ready",
                "message": f"run is in state {row.state!r}; nothing to export",
            },
        )

    launcher = getattr(request.app.state, "browser_launcher", None)
    if launcher is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "export_unavailable",
                "message": f"{fmt.upper()} export unavailable (browser launcher not configured)",
            },
        )
    resolver = getattr(request.app.state, "render_base_url_resolver", None)
    base_url = resolver.resolve() if resolver else None
    if base_url is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "render_base_url_missing",
                "message": (
                    "Report rendering requires a built frontend or running "
                    "Vite dev server. Set OPENLIA_REPORT_RENDER_BASE_URL to override."
                ),
            },
        )

    bundle_url = f"{base_url.rstrip('/')}/reports/v2/{run_id}/render"
    cookies = _forward_session_cookie_for_render(request, base_url)
    payload = row.final_report_json or {}
    cover = payload.get("cover") or {}
    title = str(cover.get("title") or cover.get("ticker") or "report")
    filename = _sanitize_filename_v2(f"{title}.{fmt}")

    from urllib.parse import quote as urlquote

    if fmt == "pdf":
        try:
            data = await export_report_pdf(
                launcher,
                bundle_url=bundle_url,
                cookies=cookies,
            )
        except HTTPException:
            raise
        except Exception as exc:
            if resolver is not None:
                resolver.invalidate()
            raise HTTPException(
                status_code=503,
                detail={"code": "pdf_render_failed", "message": str(exc)},
            ) from exc
        media_type = "application/pdf"
    else:
        # DOCX path: screenshot every chart block, then stitch via the
        # shared report_docx assembler. The v2 schema adapter on the
        # frontend produces v1-shape blocks, so assemble_docx works
        # against them without modification.
        try:
            chart_pngs = await capture_chart_pngs(
                launcher, bundle_url=bundle_url, cookies=cookies
            )
        except HTTPException:
            raise
        except Exception as exc:
            if resolver is not None:
                resolver.invalidate()
            raise HTTPException(
                status_code=503,
                detail={"code": "docx_chart_capture_failed", "message": str(exc)},
            ) from exc
        # assemble_docx wants the v1 ReportSchema shape. Run a thin
        # adapter inline rather than importing the frontend's — the
        # block types match because we've kept the v2 vocabulary close
        # to v1 throughout the assembler refactor.
        v1_payload = _v2_payload_to_v1_for_docx(payload)
        data = assemble_docx(v1_payload, chart_pngs=chart_pngs, header_text=title)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    return Response(
        content=data,
        media_type=media_type,
        headers={
            "content-disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{urlquote(filename)}"
            )
        },
    )


def _v2_payload_to_v1_for_docx(v2: dict[str, Any]) -> dict[str, Any]:
    """Minimal server-side mirror of the frontend's v2→v1 block adapter,
    just enough for assemble_docx (which reads cover/sections/blocks +
    chart `data-block-path` for image stitching). Section blocks are
    passed through with light type renaming; charts keep their
    chart_image type so assemble_docx skips them (the chart_pngs map
    fills them in via path lookup).
    """
    sections_in = v2.get("sections") or []
    sections_out = []
    for sec in sections_in:
        sections_out.append(
            {
                "id": sec.get("id"),
                "title": sec.get("name"),
                "blocks": list(sec.get("blocks") or []),
            }
        )
    cover = v2.get("cover") or {}
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "cover": {
            "title": cover.get("title") or "Report",
            "subtitle": cover.get("subtitle") or "",
            "eyebrow": cover.get("eyebrow"),
            "ticker": cover.get("ticker"),
            "tagline": cover.get("tagline") or "",
        },
        "sections": sections_out,
        "citations": v2.get("citations") or [],
    }


def _resolve_models_by_slot_for_user(db: DBSession, user_id: str) -> dict[str, Any]:
    """Load the caller's per-slot model assignments, validate completeness,
    and resolve each model_id into a `ResolvedModel`. Raises HTTPException
    422 when any required slot is unassigned or any model_id is missing.
    """
    mapping = model_assignments_svc.get_assignments(db, user_id=user_id)
    missing = model_assignments_svc.missing_slots(mapping)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "models_unassigned",
                "message": (
                    "v2.2 engine requires a model for every slot before a run "
                    "can be dispatched. Open the engine-models picker and "
                    "choose a model for each listed slot."
                ),
                "missing": missing,
                "slots": [s.value for s in REQUIRED_V2_SLOTS],
            },
        )
    registry = SQLModelRegistry(db)
    resolved: dict[str, Any] = {}
    unresolved: list[dict[str, str]] = []
    for slot, model_id in mapping.items():
        row = registry.get_by_id(model_id)
        if row is None:
            unresolved.append({"slot": slot, "model_id": model_id})
            continue
        resolved[slot] = _to_resolved(row)
    if unresolved:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "models_unresolvable",
                "message": (
                    "One or more assigned models could not be resolved; the "
                    "model or its provider may have been disabled. Re-assign "
                    "the affected slots."
                ),
                "unresolved": unresolved,
            },
        )
    return resolved


# ---------------------------------------------------------------------------
# Router builder
# ---------------------------------------------------------------------------


def build_equity_research_v2_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/departments/equity-research/v2", tags=["equity-research-v2"])

    @router.post("/report")
    async def start_v2_report(
        payload: V2ReportPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        factory = _get_factory(request)
        # Resolve every required slot BEFORE we mutate the DB. A 422 here is
        # the expected pre-flight failure mode when the user hasn't picked
        # models yet — the frontend surfaces the {missing} list directly.
        models_by_slot = _resolve_models_by_slot_for_user(db, user.id)

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

        # Frontend may send a structured composer_inputs with explicit `ticker`
        # and `prompt` keys (post-composer-redesign). Older clients sent only
        # `user_input` (= ticker). Honour the new shape; fall back to filling
        # missing keys from user_input so legacy clients still work.
        composer_inputs = dict(payload.composer_inputs or {})
        if "ticker" not in composer_inputs and payload.user_input:
            composer_inputs["ticker"] = payload.user_input.strip().upper()
        if "prompt" not in composer_inputs:
            composer_inputs["prompt"] = payload.user_input
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
            models_by_slot=models_by_slot,
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
        models_by_slot = _resolve_models_by_slot_for_user(db, user.id)

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
            template_spec, _notices = load_template_v2(row.template_raw, fmt=row.template_format)
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
            models_by_slot=models_by_slot,
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

    @router.get("/runs/{run_id}/report")
    def get_run_report(
        run_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> JSONResponse:
        """Return the persisted ReportV2 JSON for a completed v2 run.

        The frontend's V2ReportRenderer fetches this on FileViewer open
        and hands it to v1's ReportRenderer through the v2→v1 block
        adapter, so v2 reports render with the same chrome (cover, TOC,
        citations rail) as v1. Returns 404 on deleted/expired runs so
        the v2 ReportCard can render the tombstone state via /meta.
        """
        row = svc.get_run(db, run_id)
        if (
            row is None
            or row.user_id != user.id
            or row.deleted_at is not None
            or row.expired_at is not None
        ):
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "run not found"},
            )
        if not row.final_report_json:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "report_not_ready",
                    "message": f"run is in state {row.state!r}; no report payload yet",
                },
            )
        return JSONResponse(content=row.final_report_json)

    @router.get("/runs/{run_id}/meta")
    def get_run_meta(
        run_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, Any]:
        """Lifecycle metadata for a v2 run — used by the v2 ReportCard's
        reload-restore effect to decide between rendering the live card,
        the tombstone variant (when expired_at is set), or hiding it
        (when deleted_at is set). Cheaper than fetching the full report
        payload just to check liveness.
        """
        row = svc.get_run(db, run_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "run not found"},
            )
        cover = (row.final_report_json or {}).get("cover") or {}
        return {
            "id": row.id,
            "state": row.state,
            "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
            "expired_at": row.expired_at.isoformat() if row.expired_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "has_report": bool(row.final_report_json),
            "title": cover.get("title"),
            "ticker": cover.get("ticker"),
        }

    @router.get("/runs/{run_id}/export.pdf")
    async def export_run_pdf(
        run_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        return await _export_v2_run(
            run_id=run_id,
            request=request,
            db=db,
            user=user,
            fmt="pdf",
        )

    @router.get("/runs/{run_id}/export.docx")
    async def export_run_docx(
        run_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        return await _export_v2_run(
            run_id=run_id,
            request=request,
            db=db,
            user=user,
            fmt="docx",
        )

    @router.delete("/runs/{run_id}", status_code=204)
    def delete_run(
        run_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        """Soft-delete a v2.2 run. The row stays for audit/retention;
        subsequent GET /report and FileViewer fetches 404. Any repo_items
        bookmarking the run cascade away via the FK so the bookmark
        listing stops including it immediately.
        """
        row = svc.get_run(db, run_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "run not found"},
            )
        svc.soft_delete_run(db, run_id)
        db.commit()

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
        f"v2 template {report_template_id!r} not found in bundled set ({bundled_dir})"
    )
