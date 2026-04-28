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


class ApprovalIn(BaseModel):
    department_id: str
    need_id: str


class ProposedSpecOut(BaseModel):
    department_id: str
    need_id: str
    proposed_spec: dict[str, Any]
    canary_value: Any | None
    canary_ok: bool
    shape_match: bool
    error: str | None


class ApprovalOut(BaseModel):
    id: str
    department_id: str
    need_id: str
    connector_id: str
    access_mode: str


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
        proposals = await runner_specs_service.propose_specs(
            db,
            connector_id=connector_id,
            llm_client=llm_client_factory(),
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
