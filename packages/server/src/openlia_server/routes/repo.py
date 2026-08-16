"""Routes for repo items (saved reports)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import repo as svc


class RepoSaveIn(BaseModel):
    report_id: str


class RepoSaveV2In(BaseModel):
    pipeline_run_id: str


class RepoSaveV3In(BaseModel):
    v3_report_id: str


class RepoSaveEuIn(BaseModel):
    eu_v2_report_id: str


class RepoSaveMbIn(BaseModel):
    mb_v2_report_id: str


class RepoItemOut(BaseModel):
    id: str
    report_id: str | None = None
    pipeline_run_id: str | None = None
    v3_report_id: str | None = None
    eu_v2_report_id: str | None = None
    mb_v2_report_id: str | None = None
    created_at: datetime


class RepoV2SavedListOut(BaseModel):
    """Lightweight saved-state list — just the pipeline_run ids the user has
    bookmarked. Frontend's SavedReportsContext uses this for the v2
    ReportCard's `initialSaved` prop on page load.
    """

    saved_run_ids: list[str]


class RepoV3SavedListOut(BaseModel):
    """v3 mirror of RepoV2SavedListOut — the v3_report ids the user
    has bookmarked, used for the V3ReportCard's `initialSaved` prop
    on page load.
    """

    saved_report_ids: list[str]


class RepoEuSavedListOut(BaseModel):
    """EU v2 mirror of RepoV2SavedListOut — the eu_v2_report ids the user
    has bookmarked, used for the EU report card's `initialSaved` prop
    on page load.
    """

    saved_report_ids: list[str]


class RepoMbSavedListOut(BaseModel):
    """Morning Briefing v2 mirror of RepoV2SavedListOut — the mb_v2_report
    ids the user has bookmarked, used for the MB report card's `initialSaved`
    prop on page load.
    """

    saved_report_ids: list[str]


class RepoRowOut(BaseModel):
    id: str
    # Which engine wrote the report. v1 is the legacy report stack;
    # v3 is the new equity-research engine. Frontend branches on
    # this to open the right side-viewer source kind and choose the
    # correct delete path. Defaults to "v1" so older callers keep
    # working.
    engine: str = "v1"
    # Id of the target row in its engine's namespace. For v1 this is
    # ``reports.id``; for v3 this is ``report_v3.id``. Field is
    # named ``report_id`` for back-compat with the v1 frontend code
    # that already reads ``row.report_id``; new callers should
    # branch on ``engine`` to know which table to deref against.
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
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
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
                id=r.id,
                engine=r.engine,
                report_id=r.target_id,
                department=r.department,
                title=r.title,
                filename=r.filename,
                generated_at=r.generated_at,
                saved_at=r.saved_at,
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

    # --- v2.2 pipeline-run mirrors ---------------------------------------

    @router.post(
        "/v2-runs",
        response_model=RepoItemOut,
        status_code=status.HTTP_201_CREATED,
    )
    def save_v2_ep(
        body: RepoSaveV2In,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoItemOut:
        try:
            item = svc.save_v2_run_to_repo(
                db, user_id=user.id, pipeline_run_id=body.pipeline_run_id
            )
        except LookupError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "pipeline_run_not_found", "message": str(exc)},
            ) from exc
        return RepoItemOut.model_validate(item, from_attributes=True)

    @router.delete("/v2-runs", status_code=status.HTTP_204_NO_CONTENT)
    def unsave_v2_ep(
        pipeline_run_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        svc.unsave_v2_run_from_repo(db, user_id=user.id, pipeline_run_id=pipeline_run_id)

    @router.get("/v2-runs", response_model=RepoV2SavedListOut)
    def list_v2_saved_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoV2SavedListOut:
        rows = svc.list_items(db, user_id=user.id)
        ids = [r.pipeline_run_id for r in rows if r.pipeline_run_id is not None]
        return RepoV2SavedListOut(saved_run_ids=ids)

    # ----- v3 equity-research repo endpoints -----

    @router.post(
        "/v3-runs",
        response_model=RepoItemOut,
        status_code=status.HTTP_201_CREATED,
    )
    def save_v3_ep(
        body: RepoSaveV3In,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoItemOut:
        try:
            item = svc.save_v3_report_to_repo(db, user_id=user.id, v3_report_id=body.v3_report_id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "v3_report_not_found", "message": str(exc)},
            ) from exc
        return RepoItemOut.model_validate(item, from_attributes=True)

    @router.delete("/v3-runs", status_code=status.HTTP_204_NO_CONTENT)
    def unsave_v3_ep(
        v3_report_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        svc.unsave_v3_report_from_repo(db, user_id=user.id, v3_report_id=v3_report_id)

    @router.get("/v3-runs", response_model=RepoV3SavedListOut)
    def list_v3_saved_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoV3SavedListOut:
        rows = svc.list_items(db, user_id=user.id)
        ids = [r.v3_report_id for r in rows if r.v3_report_id is not None]
        return RepoV3SavedListOut(saved_report_ids=ids)

    # ----- Earnings Update v2 repo endpoints -----

    @router.post(
        "/eu-runs",
        response_model=RepoItemOut,
        status_code=status.HTTP_201_CREATED,
    )
    def save_eu_ep(
        body: RepoSaveEuIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoItemOut:
        try:
            item = svc.save_eu_report_to_repo(
                db, user_id=user.id, eu_report_id=body.eu_v2_report_id
            )
        except LookupError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "eu_report_not_found", "message": str(exc)},
            ) from exc
        return RepoItemOut.model_validate(item, from_attributes=True)

    @router.delete("/eu-runs", status_code=status.HTTP_204_NO_CONTENT)
    def unsave_eu_ep(
        eu_v2_report_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        svc.unsave_eu_report_from_repo(db, user_id=user.id, eu_report_id=eu_v2_report_id)

    @router.get("/eu-runs", response_model=RepoEuSavedListOut)
    def list_eu_saved_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoEuSavedListOut:
        rows = svc.list_items(db, user_id=user.id)
        ids = [r.eu_v2_report_id for r in rows if r.eu_v2_report_id is not None]
        return RepoEuSavedListOut(saved_report_ids=ids)

    # ----- Morning Briefing v2 repo endpoints -----

    @router.post(
        "/mb-runs",
        response_model=RepoItemOut,
        status_code=status.HTTP_201_CREATED,
    )
    def save_mb_ep(
        body: RepoSaveMbIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoItemOut:
        try:
            item = svc.save_mb_report_to_repo(
                db, user_id=user.id, mb_report_id=body.mb_v2_report_id
            )
        except LookupError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "mb_report_not_found", "message": str(exc)},
            ) from exc
        return RepoItemOut.model_validate(item, from_attributes=True)

    @router.delete("/mb-runs", status_code=status.HTTP_204_NO_CONTENT)
    def unsave_mb_ep(
        mb_v2_report_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        svc.unsave_mb_report_from_repo(db, user_id=user.id, mb_report_id=mb_v2_report_id)

    @router.get("/mb-runs", response_model=RepoMbSavedListOut)
    def list_mb_saved_ep(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> RepoMbSavedListOut:
        rows = svc.list_items(db, user_id=user.id)
        ids = [r.mb_v2_report_id for r in rows if r.mb_v2_report_id is not None]
        return RepoMbSavedListOut(saved_report_ids=ids)

    return router
