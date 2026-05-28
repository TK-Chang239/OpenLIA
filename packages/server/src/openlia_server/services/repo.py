"""CRUD + filtered list + facets for repo_items — saved reports, per user."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openlia_server.db.models.content import RepoItem, Report
from openlia_server.db.models.pipeline_runs import PipelineRun
from openlia_server.db.models.report_v3 import ReportV3

SortKey = Literal[
    "saved_desc",
    "saved_asc",
    "generated_desc",
    "generated_asc",
    "department_asc",
    "filename_asc",
]

VALID_SORTS: frozenset[str] = frozenset(
    {
        "saved_desc",
        "saved_asc",
        "generated_desc",
        "generated_asc",
        "department_asc",
        "filename_asc",
    }
)


@dataclass(frozen=True)
class RepoRow:
    item: RepoItem
    report: Report


def save_to_repo(db: Session, *, user_id: str, report_id: str) -> RepoItem:
    existing = db.execute(
        select(RepoItem).where(RepoItem.user_id == user_id, RepoItem.report_id == report_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    if db.get(Report, report_id) is None:
        raise LookupError(f"report {report_id} not found")
    item = RepoItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        report_id=report_id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.execute(
            select(RepoItem).where(RepoItem.user_id == user_id, RepoItem.report_id == report_id)
        ).scalar_one()
    db.refresh(item)
    return item


def unsave_from_repo(db: Session, *, user_id: str, report_id: str) -> None:
    db.query(RepoItem).filter(RepoItem.user_id == user_id, RepoItem.report_id == report_id).delete()
    db.commit()


# ---------------------------------------------------------------------------
# v2.2 pipeline-run repo support — polymorphic mirror of the v1 helpers.
# ---------------------------------------------------------------------------


def save_v2_run_to_repo(
    db: Session, *, user_id: str, pipeline_run_id: str
) -> RepoItem:
    """Save a v2.2 pipeline_run to the user's repo. Idempotent."""
    existing = db.execute(
        select(RepoItem).where(
            RepoItem.user_id == user_id,
            RepoItem.pipeline_run_id == pipeline_run_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    run = db.get(PipelineRun, pipeline_run_id)
    if run is None or run.user_id != user_id:
        raise LookupError(f"pipeline_run {pipeline_run_id} not found")
    if run.deleted_at is not None:
        raise LookupError(f"pipeline_run {pipeline_run_id} has been deleted")
    item = RepoItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        report_id=None,
        pipeline_run_id=pipeline_run_id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.execute(
            select(RepoItem).where(
                RepoItem.user_id == user_id,
                RepoItem.pipeline_run_id == pipeline_run_id,
            )
        ).scalar_one()
    db.refresh(item)
    return item


def unsave_v2_run_from_repo(
    db: Session, *, user_id: str, pipeline_run_id: str
) -> None:
    db.query(RepoItem).filter(
        RepoItem.user_id == user_id,
        RepoItem.pipeline_run_id == pipeline_run_id,
    ).delete()
    db.commit()


def is_v2_run_saved(
    db: Session, *, user_id: str, pipeline_run_id: str
) -> bool:
    return (
        db.execute(
            select(RepoItem.id).where(
                RepoItem.user_id == user_id,
                RepoItem.pipeline_run_id == pipeline_run_id,
            )
        ).first()
        is not None
    )


# ---------------------------------------------------------------------------
# v3 equity-research report repo support — third polymorphic target.
# ---------------------------------------------------------------------------


def save_v3_report_to_repo(
    db: Session, *, user_id: str, v3_report_id: str
) -> RepoItem:
    """Save a v3 report to the user's repo. Idempotent."""
    existing = db.execute(
        select(RepoItem).where(
            RepoItem.user_id == user_id,
            RepoItem.v3_report_id == v3_report_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    report = db.get(ReportV3, v3_report_id)
    if report is None or report.user_id != user_id:
        raise LookupError(f"v3 report {v3_report_id} not found")
    item = RepoItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        report_id=None,
        pipeline_run_id=None,
        v3_report_id=v3_report_id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.execute(
            select(RepoItem).where(
                RepoItem.user_id == user_id,
                RepoItem.v3_report_id == v3_report_id,
            )
        ).scalar_one()
    db.refresh(item)
    return item


def unsave_v3_report_from_repo(
    db: Session, *, user_id: str, v3_report_id: str
) -> None:
    db.query(RepoItem).filter(
        RepoItem.user_id == user_id,
        RepoItem.v3_report_id == v3_report_id,
    ).delete()
    db.commit()


def is_v3_report_saved(
    db: Session, *, user_id: str, v3_report_id: str
) -> bool:
    return (
        db.execute(
            select(RepoItem.id).where(
                RepoItem.user_id == user_id,
                RepoItem.v3_report_id == v3_report_id,
            )
        ).first()
        is not None
    )


def list_items(db: Session, *, user_id: str) -> list[RepoItem]:
    stmt = select(RepoItem).where(RepoItem.user_id == user_id).order_by(RepoItem.created_at.desc())
    return list(db.execute(stmt).scalars())


def _start_of_day_utc(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


def _end_of_day_utc(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=UTC)


def list_items_filtered(
    db: Session,
    *,
    user_id: str,
    q: str | None = None,
    departments: list[str] | None = None,
    generated_from: date | None = None,
    generated_to: date | None = None,
    saved_from: date | None = None,
    saved_to: date | None = None,
    sort: SortKey = "saved_desc",
    page: int = 1,
    page_size: int = 50,
) -> list[RepoRow]:
    if sort not in VALID_SORTS:
        raise ValueError(f"invalid sort: {sort!r}")
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 200:
        raise ValueError("page_size must be in [1, 200]")

    stmt = (
        select(RepoItem, Report)
        .join(Report, RepoItem.report_id == Report.id)
        .where(RepoItem.user_id == user_id, Report.expired_at.is_(None))
    )
    if q:
        stmt = stmt.where(func.lower(Report.title).like(f"%{q.lower()}%"))
    if departments:
        stmt = stmt.where(Report.department.in_(departments))
    if generated_from:
        stmt = stmt.where(Report.created_at >= _start_of_day_utc(generated_from))
    if generated_to:
        stmt = stmt.where(Report.created_at <= _end_of_day_utc(generated_to))
    if saved_from:
        stmt = stmt.where(RepoItem.created_at >= _start_of_day_utc(saved_from))
    if saved_to:
        stmt = stmt.where(RepoItem.created_at <= _end_of_day_utc(saved_to))

    if sort == "saved_desc":
        stmt = stmt.order_by(RepoItem.created_at.desc(), RepoItem.id.asc())
    elif sort == "saved_asc":
        stmt = stmt.order_by(RepoItem.created_at.asc(), RepoItem.id.asc())
    elif sort == "generated_desc":
        stmt = stmt.order_by(Report.created_at.desc(), RepoItem.id.asc())
    elif sort == "generated_asc":
        stmt = stmt.order_by(Report.created_at.asc(), RepoItem.id.asc())
    elif sort == "department_asc":
        stmt = stmt.order_by(Report.department.asc(), Report.title.asc())
    elif sort == "filename_asc":
        stmt = stmt.order_by(Report.title.asc())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = db.execute(stmt).all()
    return [RepoRow(item=item, report=report) for item, report in rows]


def facets(db: Session, *, user_id: str) -> dict:
    stmt = (
        select(Report.department, func.count(RepoItem.id))
        .join(Report, RepoItem.report_id == Report.id)
        .where(RepoItem.user_id == user_id, Report.expired_at.is_(None))
        .group_by(Report.department)
        .order_by(Report.department.asc())
    )
    rows = db.execute(stmt).all()
    departments = [{"slug": dep, "count": int(count)} for dep, count in rows]
    total = sum(d["count"] for d in departments)
    return {"departments": departments, "total": total}
