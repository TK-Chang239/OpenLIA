"""Routes for cross-session graph memory: proposals + user constructs (slice 8).

Thin HTTP wrappers over ``services.graph_extraction`` and
``services.user_constructs``. All endpoints require auth and scope to
``user.id``. Service-layer functions return ``None`` on cross-tenant
access or stale state; the routes translate those into 404/409 so the
frontend can distinguish "gone" from "already resolved".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.graph import (
    GraphExtractionProposal,
    GraphUserConstruct,
)
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import graph_extraction


class ProposalOut(BaseModel):
    id: str
    kind: str
    payload: dict[str, Any]
    status: str
    created_at: datetime


class ProposalListOut(BaseModel):
    items: list[ProposalOut]


class ConstructOut(BaseModel):
    id: str
    kind: str
    status: str
    statement: str
    entity_id: str
    created_at: datetime
    updated_at: datetime


class ConstructListOut(BaseModel):
    items: list[ConstructOut]


_VALID_PROPOSAL_STATUSES: frozenset[str] = frozenset({"pending", "accepted", "dismissed"})


def build_graph_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/graph", tags=["graph"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/proposals", response_model=ProposalListOut)
    def list_proposals_ep(
        status: str = "pending",
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> ProposalListOut:
        if status not in _VALID_PROPOSAL_STATUSES:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_status", "message": f"unknown status: {status!r}"},
            )
        rows = list(
            db.execute(
                select(GraphExtractionProposal)
                .where(
                    GraphExtractionProposal.user_id == user.id,
                    GraphExtractionProposal.status == status,
                )
                .order_by(GraphExtractionProposal.created_at.desc())
            ).scalars()
        )
        return ProposalListOut(
            items=[
                ProposalOut(
                    id=r.id,
                    kind=r.kind,
                    payload=r.payload,
                    status=r.status,
                    created_at=r.created_at,
                )
                for r in rows
            ]
        )

    @router.post("/proposals/{proposal_id}/accept")
    def accept_proposal_ep(
        proposal_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, Any] | None:
        p = db.get(GraphExtractionProposal, proposal_id)
        if p is None or p.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail={"code": "proposal_not_found", "message": "Proposal not found."},
            )
        if p.status != "pending":
            raise HTTPException(
                status_code=409,
                detail={"code": "proposal_not_pending", "message": "Proposal already resolved."},
            )
        construct = graph_extraction.accept_proposal(
            db, proposal_id=proposal_id, user_id=user.id
        )
        if construct is None:
            return None
        return {
            "id": construct.id,
            "kind": construct.kind,
            "status": construct.status,
            "statement": construct.statement,
            "entity_id": construct.entity_id,
            "created_at": construct.created_at.isoformat(),
            "updated_at": construct.updated_at.isoformat(),
        }

    @router.post("/proposals/{proposal_id}/dismiss")
    def dismiss_proposal_ep(
        proposal_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        p = db.get(GraphExtractionProposal, proposal_id)
        if p is None or p.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail={"code": "proposal_not_found", "message": "Proposal not found."},
            )
        if p.status != "pending":
            raise HTTPException(
                status_code=409,
                detail={"code": "proposal_not_pending", "message": "Proposal already resolved."},
            )
        graph_extraction.dismiss_proposal(db, proposal_id=proposal_id, user_id=user.id)
        return {"ok": True}

    @router.get("/constructs", response_model=ConstructListOut)
    def list_constructs_ep(
        entity_id: str | None = None,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> ConstructListOut:
        stmt = (
            select(GraphUserConstruct)
            .where(
                GraphUserConstruct.user_id == user.id,
                GraphUserConstruct.status == "confirmed",
            )
            .order_by(GraphUserConstruct.updated_at.desc())
        )
        if entity_id is not None:
            stmt = stmt.where(GraphUserConstruct.entity_id == entity_id)
        rows = list(db.execute(stmt).scalars())
        return ConstructListOut(
            items=[
                ConstructOut(
                    id=r.id,
                    kind=r.kind,
                    status=r.status,
                    statement=r.statement,
                    entity_id=r.entity_id,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]
        )

    @router.delete("/constructs/{construct_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_construct_ep(
        construct_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        row = db.get(GraphUserConstruct, construct_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail={"code": "construct_not_found", "message": "Construct not found."},
            )
        row.status = "rejected"
        db.flush()

    return router
