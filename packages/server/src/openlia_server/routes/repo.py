"""Routes for repo items (saved reports)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import repo as svc


class RepoSaveIn(BaseModel):
    report_id: str


class RepoItemOut(BaseModel):
    id: str
    report_id: str
    created_at: datetime


class RepoListOut(BaseModel):
    items: list[RepoItemOut]


def build_repo_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/repo", tags=["repo"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/items", response_model=RepoListOut)
    def list_items_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoListOut:
        rows = svc.list_items(db, user_id=user.id)
        return RepoListOut(
            items=[RepoItemOut.model_validate(r, from_attributes=True) for r in rows]
        )

    @router.post("/items", response_model=RepoItemOut, status_code=status.HTTP_201_CREATED)
    def save_ep(
        body: RepoSaveIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoItemOut:
        try:
            item = svc.save_to_repo(db, user_id=user.id, report_id=body.report_id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "report_not_found", "message": str(exc)},
            ) from exc
        return RepoItemOut.model_validate(item, from_attributes=True)

    @router.delete("/items", status_code=status.HTTP_204_NO_CONTENT)
    def delete_ep(
        report_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        svc.unsave_from_repo(db, user_id=user.id, report_id=report_id)

    return router
