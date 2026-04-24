"""Routes for repo items (saved reports)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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


class RepoRowOut(BaseModel):
    id: str
    report_id: str
    department: str
    title: str
    filename: str
    generated_at: datetime
    saved_at: datetime


class RepoListOut(BaseModel):
    items: list[RepoItemOut]


class RepoFilteredListOut(BaseModel):
    items: list[RepoRowOut]
    page: int
    page_size: int
    has_more: bool


class FacetDepartment(BaseModel):
    slug: str
    count: int


class RepoFacetsOut(BaseModel):
    departments: list[FacetDepartment]
    total: int


def _split_csv(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    out: list[str] = []
    for v in values:
        out.extend([part.strip() for part in v.split(",") if part.strip()])
    return out or None


def build_repo_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/repo", tags=["repo"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/items")
    def list_items_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
        q: str | None = None,
        department: Annotated[list[str] | None, Query()] = None,
        generated_from: date | None = None,
        generated_to: date | None = None,
        saved_from: date | None = None,
        saved_to: date | None = None,
        sort: str = "saved_desc",
        page: int = 1,
        page_size: int = 50,
        filtered: bool = False,
    ) -> RepoListOut | RepoFilteredListOut:
        # Back-compat: when no filter/sort/pagination args and not filtered,
        # return legacy flat shape used by Plan 12 callers.
        if (
            not filtered
            and q is None
            and not department
            and generated_from is None
            and generated_to is None
            and saved_from is None
            and saved_to is None
            and sort == "saved_desc"
            and page == 1
            and page_size == 50
        ):
            rows = svc.list_items(db, user_id=user.id)
            return RepoListOut(
                items=[RepoItemOut.model_validate(r, from_attributes=True) for r in rows]
            )
        try:
            repo_rows = svc.list_items_filtered(
                db,
                user_id=user.id,
                q=q,
                departments=_split_csv(department),
                generated_from=generated_from,
                generated_to=generated_to,
                saved_from=saved_from,
                saved_to=saved_to,
                sort=sort,  # type: ignore[arg-type]
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc

        out_rows = [
            RepoRowOut(
                id=r.item.id,
                report_id=r.report.id,
                department=r.report.department,
                title=r.report.title,
                filename=f"{r.report.title}.pdf",
                generated_at=r.report.created_at,
                saved_at=r.item.created_at,
            )
            for r in repo_rows
        ]
        return RepoFilteredListOut(
            items=out_rows,
            page=page,
            page_size=page_size,
            has_more=len(out_rows) == page_size,
        )

    @router.get("/facets", response_model=RepoFacetsOut)
    def facets_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoFacetsOut:
        f = svc.facets(db, user_id=user.id)
        return RepoFacetsOut(
            departments=[FacetDepartment(**d) for d in f["departments"]],
            total=f["total"],
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
