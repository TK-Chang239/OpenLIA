"""Routes for the wizard-time adapter proposed-specs flow.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.

Endpoints (mounted under `/api/connectors`):

- `GET    /{connector_id}/proposed-specs`         — list cached drafts.
- `POST   /{connector_id}/proposed-specs/resolve` — re-run resolver + canary.
- `POST   /{connector_id}/proposed-specs/approve` — persist a draft.

NOTE (Phase 6): The proposal generator is gated on Phase 8 dept artifacts;
until those land the resolve endpoint returns an empty list. The caller
must inject an `LlmClient` (Phase 9 wires the real provider).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.connectors.adapter import LlmClient
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.services import runner_specs_service
from openlia_server.services.adapter_llm_client import AdapterLlmNotConfigured


class ApprovalIn(BaseModel):
    department_id: str
    need_id: str


class DeptApprovalIn(BaseModel):
    need_id: str


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
    """Assemble the proposed-specs router.

    `llm_client_factory` is invoked per resolve call so callers can inject a
    fresh LLM client (e.g. with request-scoped headers) — Phase 9 wires a
    real OpenRouter quick-tier client; Phase 6 tests pass in a stub.
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
        proposals = await runner_specs_service.propose_specs(
            db,
            connector_id=connector_id,
            llm_client=llm_client,
        )
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
    llm_client_factory: Callable[[], LlmClient],
) -> APIRouter:
    """Per-department resolve endpoints (Phase B step 3).

    Aggregates inventory across every validated connector whose category
    overlaps the department's required ∪ optional categories and runs the
    resolver per (department, need). Cached results live in
    `runner_specs_service._DEPT_PROPOSALS`.
    """
    router = APIRouter(prefix="/departments", tags=["departments-specs"])
    session_dep = make_session_dependency(db_session_factory)

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
        "/{department_id}/proposed-specs/resolve",
        response_model=list[ProposedSpecOut],
    )
    async def resolve_dept_proposed_specs(
        department_id: str,
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
        proposals = await runner_specs_service.propose_specs_for_department(
            db,
            department_id=department_id,
            llm_client=llm_client,
        )
        return [ProposedSpecOut(**runner_specs_service.proposal_to_dict(p)) for p in proposals]

    return router


def build_runner_specs_list_router(
    *, db_session_factory: Callable[[], DBSession]
) -> APIRouter:
    """Mounts `GET /api/runner-specs?department_id=...` for the admin panel."""
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

    return router
