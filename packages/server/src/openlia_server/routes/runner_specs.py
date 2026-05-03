"""Routes for the wizard-time adapter proposed-specs flow.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.
Plan: docs/superpowers/plans/2026-04-30-adapter-resolver-grounding.md.

Per-connector endpoints (legacy, mounted under `/api/connectors`):
- `GET    /{connector_id}/proposed-specs`         — list cached drafts.
- `POST   /{connector_id}/proposed-specs/resolve` — re-run resolver + canary.
- `POST   /{connector_id}/proposed-specs/approve` — persist a draft.

Per-department endpoints (current, mounted under `/api/departments`):
- `GET    /{department_id}/proposed-specs`                — list cached drafts.
- `GET    /{department_id}/proposed-specs/events`         — live tool-call log.
- `POST   /{department_id}/proposed-specs/resolve`        — resolve all needs.
- `POST   /{department_id}/proposed-specs/{need_id}/resolve` — re-resolve one
   need, optionally with `{exclude_connector_ids: [...]}`.
- `POST   /{department_id}/proposed-specs/approve`        — persist a draft
   using the connector_id chosen during resolve.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.connectors.adapter import LlmClient
from openlia.llm.exceptions import (
    AuthError,
    LLMProviderError,
    ProviderOutageError,
    RateLimitError,
    TransportError,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.services import runner_specs_service
from openlia_server.services.adapter_llm_client import AdapterLlmNotConfigured


def _llm_error_to_http(exc: LLMProviderError) -> HTTPException:
    """Map provider-layer LLM errors to actionable HTTP responses.

    Without this, transient rate-limits and TLS faults during resolve bubble
    up as opaque 500s. The frontend wizard relies on the structured `code`
    field to render the right "retry / fix your key / contact admin" hint.
    """
    if isinstance(exc, RateLimitError):
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "llm_rate_limited", "message": str(exc)},
            headers=headers,
        )
    if isinstance(exc, AuthError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "llm_auth_failed", "message": str(exc)},
        )
    if isinstance(exc, (TransportError, ProviderOutageError)):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "llm_upstream_unavailable", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": "llm_provider_error", "message": str(exc)},
    )


class ApprovalIn(BaseModel):
    department_id: str
    need_id: str


class DeptApprovalIn(BaseModel):
    need_id: str
    connector_id: str | None = None


class DeptResolveNeedIn(BaseModel):
    exclude_connector_ids: list[str] = []


class ProposedSpecOut(BaseModel):
    department_id: str
    need_id: str
    proposed_spec: dict[str, Any]
    canary_value: Any | None
    canary_ok: bool
    shape_match: bool
    error: str | None
    connector_id: str | None = None
    unsatisfiable: bool = False
    reason: str | None = None


class ApprovalOut(BaseModel):
    id: str
    department_id: str
    need_id: str
    connector_id: str
    access_mode: str


class RunnerSpecRow(BaseModel):
    id: str
    department_id: str
    need_id: str
    connector_id: str
    access_mode: str
    spec: dict[str, Any]
    canary_value: dict[str, Any] | None
    canary_at: str | None
    created_at: str | None
    updated_at: str | None


def build_runner_specs_router(
    *,
    db_session_factory: Callable[[], DBSession],
    llm_client_factory: Callable[[], LlmClient],
) -> APIRouter:
    """Assemble the per-connector proposed-specs router.

    `llm_client_factory` is invoked per resolve call so callers can inject a
    fresh LLM client (e.g. with request-scoped headers); production wires
    `make_adapter_llm_client_factory`, tests pass in a stub.
    """
    router = APIRouter(prefix="/connectors", tags=["connectors-specs"])
    session_dep = make_session_dependency(db_session_factory)

    @router.get(
        "/{connector_id}/proposed-specs",
        response_model=list[ProposedSpecOut],
    )
    def list_proposed_specs(connector_id: str) -> list[ProposedSpecOut]:
        proposals = runner_specs_service.get_proposed_specs(connector_id)
        return [ProposedSpecOut(**runner_specs_service.proposal_to_dict(p)) for p in proposals]

    @router.post(
        "/{connector_id}/proposed-specs/resolve",
        response_model=list[ProposedSpecOut],
    )
    async def resolve_proposed_specs(
        connector_id: str,
        db: DBSession = Depends(session_dep),
    ) -> list[ProposedSpecOut]:
        try:
            llm_client = llm_client_factory()
        except AdapterLlmNotConfigured as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "adapter_llm_not_configured",
                    "message": str(exc),
                },
            ) from exc
        try:
            proposals = await runner_specs_service.propose_specs(
                db,
                connector_id=connector_id,
                llm_client=llm_client,
            )
        except LLMProviderError as exc:
            raise _llm_error_to_http(exc) from exc
        return [ProposedSpecOut(**runner_specs_service.proposal_to_dict(p)) for p in proposals]

    @router.post(
        "/{connector_id}/proposed-specs/approve",
        response_model=ApprovalOut,
        status_code=status.HTTP_201_CREATED,
    )
    def approve(
        connector_id: str,
        body: ApprovalIn,
        db: DBSession = Depends(session_dep),
    ) -> ApprovalOut:
        try:
            row = runner_specs_service.approve_spec(
                db,
                connector_id=connector_id,
                department_id=body.department_id,
                need_id=body.need_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApprovalOut(
            id=row.id,
            department_id=row.department_id,
            need_id=row.need_id,
            connector_id=row.connector_id,
            access_mode=row.access_mode,
        )

    return router


def build_dept_proposed_specs_router(
    *,
    db_session_factory: Callable[[], DBSession],
    llm_client_factory: Callable[[], LlmClient] | None = None,
    agentic_factory: Callable[[Any], LlmClient] | None = None,
) -> APIRouter:
    """Per-department resolve endpoints.

    Aggregates inventory across every validated connector whose category
    overlaps the department's required-or-optional categories and runs the
    resolver per (department, need). Cached results live in
    `runner_specs_service._DEPT_PROPOSALS`; live tool-call events live in
    `runner_specs_service._RESOLVE_EVENTS`. Production wires `agentic_factory`
    (multi-turn tool-use against the connector's grounding clone); the
    legacy `llm_client_factory` mode is retained for tests.
    """
    router = APIRouter(prefix="/departments", tags=["departments-specs"])
    session_dep = make_session_dependency(db_session_factory)

    @router.get(
        "/{department_id}/proposed-specs/events",
        response_model=list[dict[str, Any]],
    )
    def list_resolve_events(department_id: str) -> list[dict[str, Any]]:
        """Live tool-call log for an in-flight (or just-completed) resolve.

        The frontend polls this while the spinner is up so the user can
        watch which files the agentic LLM is reading instead of staring
        at a generic loading state.
        """
        return runner_specs_service.get_resolve_events(department_id)

    @router.get(
        "/{department_id}/proposed-specs",
        response_model=list[ProposedSpecOut],
    )
    def list_dept_proposed_specs(department_id: str) -> list[ProposedSpecOut]:
        proposals = runner_specs_service.get_dept_proposed_specs(department_id)
        return [ProposedSpecOut(**runner_specs_service.proposal_to_dict(p)) for p in proposals]

    @router.post(
        "/{department_id}/proposed-specs/approve",
        response_model=ApprovalOut,
        status_code=status.HTTP_201_CREATED,
    )
    def approve_dept(
        department_id: str,
        body: DeptApprovalIn,
        db: DBSession = Depends(session_dep),
    ) -> ApprovalOut:
        try:
            row = runner_specs_service.approve_dept_spec(
                db,
                department_id=department_id,
                need_id=body.need_id,
                connector_id=body.connector_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApprovalOut(
            id=row.id,
            department_id=row.department_id,
            need_id=row.need_id,
            connector_id=row.connector_id,
            access_mode=row.access_mode,
        )

    @router.post(
        "/{department_id}/proposed-specs/{need_id}/resolve",
        response_model=list[ProposedSpecOut],
    )
    async def resolve_single_need(
        department_id: str,
        need_id: str,
        body: DeptResolveNeedIn | None = None,
        db: DBSession = Depends(session_dep),
    ) -> list[ProposedSpecOut]:
        excluded = set(body.exclude_connector_ids) if body else set()
        try:
            if agentic_factory is not None:
                proposals = await runner_specs_service.propose_spec_for_need(
                    db,
                    department_id=department_id,
                    need_id=need_id,
                    llm_client_factory=agentic_factory,
                    exclude_connector_ids=excluded,
                )
            else:
                assert llm_client_factory is not None
                llm_client = llm_client_factory()
                proposals = await runner_specs_service.propose_spec_for_need(
                    db,
                    department_id=department_id,
                    need_id=need_id,
                    llm_client=llm_client,
                    exclude_connector_ids=excluded,
                )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LLMProviderError as exc:
            raise _llm_error_to_http(exc) from exc
        except AdapterLlmNotConfigured as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "adapter_llm_not_configured",
                    "message": str(exc),
                },
            ) from exc
        return [ProposedSpecOut(**runner_specs_service.proposal_to_dict(p)) for p in proposals]

    @router.post(
        "/{department_id}/proposed-specs/resolve",
        response_model=list[ProposedSpecOut],
    )
    async def resolve_dept_proposed_specs(
        department_id: str,
        db: DBSession = Depends(session_dep),
    ) -> list[ProposedSpecOut]:
        try:
            if agentic_factory is not None:
                proposals = await runner_specs_service.propose_specs_for_department(
                    db,
                    department_id=department_id,
                    llm_client_factory=agentic_factory,
                )
            else:
                assert llm_client_factory is not None
                llm_client = llm_client_factory()
                proposals = await runner_specs_service.propose_specs_for_department(
                    db,
                    department_id=department_id,
                    llm_client=llm_client,
                )
        except LLMProviderError as exc:
            raise _llm_error_to_http(exc) from exc
        except AdapterLlmNotConfigured as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "adapter_llm_not_configured",
                    "message": str(exc),
                },
            ) from exc
        return [ProposedSpecOut(**runner_specs_service.proposal_to_dict(p)) for p in proposals]

    return router


class ResolveSaveIn(BaseModel):
    department_id: str
    need_id: str
    connector_id: str
    resolution_mode: str  # "manual_endpoint" | "websearch"
    user_picked_endpoint: str
    user_hint: str | None = None
    websearch_url: str | None = None
    manually_overridden: bool = False


class SmokeFailureOut(BaseModel):
    status: str
    attempts: int
    error_class: str | None
    error_message: str | None
    response_excerpt: str | None


class ResolveSaveSuccess(BaseModel):
    ok: bool = True
    spec: RunnerSpecRow
    warning: str | None


class ResolveSaveFailure(BaseModel):
    ok: bool = False
    failure: SmokeFailureOut
    warning: str | None


class HistoryEntryOut(BaseModel):
    kind: str
    status: str
    error_class: str | None
    error_message: str | None
    created_at: str | None
    attempt: int | None = None


def build_runner_specs_list_router(
    *,
    db_session_factory: Callable[[], DBSession],
    llm_client_factory: Callable[[], LlmClient] | None = None,
    transport_factory: (Callable[[Any], Any] | None) = None,
) -> APIRouter:
    """Mounts:
    - GET /api/runner-specs[?department_id=...]
    - POST /api/runner-specs/resolve  (manual-pick save flow)
    - GET /api/runner-specs/{id}/history  (audit log entries)
    """
    router = APIRouter(prefix="/runner-specs", tags=["runner-specs"])
    session_dep = make_session_dependency(db_session_factory)

    @router.get("", response_model=list[RunnerSpecRow])
    def list_runner_specs(
        department_id: str | None = None,
        db: DBSession = Depends(session_dep),
    ) -> list[RunnerSpecRow]:
        rows = runner_specs_service.list_runner_specs(db, department_id=department_id)
        return [
            RunnerSpecRow(
                id=r.id,
                department_id=r.department_id,
                need_id=r.need_id,
                connector_id=r.connector_id,
                access_mode=r.access_mode,
                spec=r.spec,
                canary_value=r.canary_value,
                canary_at=r.canary_at.isoformat() if r.canary_at else None,
                created_at=r.created_at.isoformat() if r.created_at else None,
                updated_at=r.updated_at.isoformat() if r.updated_at else None,
            )
            for r in rows
        ]

    @router.post("/resolve")
    async def resolve_and_save(
        body: ResolveSaveIn,
        db: DBSession = Depends(session_dep),
    ) -> dict[str, Any]:
        from openlia_server.db.models.connectors import Connector
        from openlia_server.services.resolver_save_flow import (
            SaveFlowFailure,
            save_user_picked_spec,
        )

        if llm_client_factory is None or transport_factory is None:
            raise HTTPException(
                status_code=500,
                detail="resolve endpoint not configured",
            )
        connector = db.get(Connector, body.connector_id)
        if connector is None:
            raise HTTPException(status_code=404, detail="connector not found")

        try:
            llm_client = llm_client_factory()
        except AdapterLlmNotConfigured as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "adapter_llm_not_configured",
                    "message": str(exc),
                },
            ) from exc

        result = await save_user_picked_spec(
            session=db,
            connector=connector,
            department_id=body.department_id,
            need_id=body.need_id,
            resolution_mode=body.resolution_mode,  # type: ignore[arg-type]
            user_picked_endpoint=body.user_picked_endpoint,
            user_hint=body.user_hint,
            websearch_url=body.websearch_url,
            manually_overridden=body.manually_overridden,
            llm_client=llm_client,
            transport_factory=transport_factory,
        )
        if isinstance(result, SaveFlowFailure):
            return {
                "ok": False,
                "warning": result.warning,
                "failure": {
                    "status": result.failure.status,
                    "attempts": result.failure.attempts,
                    "error_class": result.failure.error_class,
                    "error_message": result.failure.error_message,
                    "response_excerpt": result.failure.response_excerpt,
                },
            }
        spec = result.spec
        return {
            "ok": True,
            "warning": result.warning,
            "spec": {
                "id": spec.id,
                "department_id": spec.department_id,
                "need_id": spec.need_id,
                "connector_id": spec.connector_id,
                "access_mode": spec.access_mode,
                "spec": spec.spec,
                "canary_value": spec.canary_value,
                "canary_at": spec.canary_at.isoformat() if spec.canary_at else None,
                "created_at": spec.created_at.isoformat() if spec.created_at else None,
                "updated_at": spec.updated_at.isoformat() if spec.updated_at else None,
                "resolution_mode": spec.resolution_mode,
                "manually_overridden": spec.manually_overridden,
                "last_smoke_at": (spec.last_smoke_at.isoformat() if spec.last_smoke_at else None),
                "llm_warning": spec.llm_warning,
            },
        }

    @router.get("/{spec_id}/history", response_model=list[HistoryEntryOut])
    def get_history(
        spec_id: str,
        db: DBSession = Depends(session_dep),
    ) -> list[HistoryEntryOut]:
        from openlia_server.services.resolver_save_flow import (
            get_history as svc_get_history,
        )

        rows = svc_get_history(db, spec_id=spec_id)
        return [HistoryEntryOut(**r) for r in rows]

    return router
