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
from openlia_server.db.models.report_eu import ReportEu
from openlia_server.db.models.report_v3 import ReportV3
from openlia_server.services.eu_v2_filename import (
    build_download_filename as build_eu_download_filename,
)
from openlia_server.services.v3_filename import build_download_filename

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

Engine = Literal["v1", "v2", "v3", "eu_v2"]


@dataclass(frozen=True)
class RepoRow:
    """Flat, engine-agnostic shape returned by ``list_items_filtered``.

    ``engine`` distinguishes which source table the row was joined
    from. ``target_id`` is the id within that engine's namespace (v1:
    ``reports.id``; v2: ``pipeline_runs.id``; v3: ``report_v3.id``;
    eu_v2: ``report_eu.id``). The route layer maps this directly to
    ``RepoRowOut``; the frontend branches on ``engine`` to choose the
    right FileViewer source + delete path.
    """

    id: str  # repo_items.id
    engine: Engine
    target_id: str
    department: str
    title: str
    filename: str
    generated_at: datetime
    saved_at: datetime


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


def save_v2_run_to_repo(db: Session, *, user_id: str, pipeline_run_id: str) -> RepoItem:
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


def unsave_v2_run_from_repo(db: Session, *, user_id: str, pipeline_run_id: str) -> None:
    db.query(RepoItem).filter(
        RepoItem.user_id == user_id,
        RepoItem.pipeline_run_id == pipeline_run_id,
    ).delete()
    db.commit()


def is_v2_run_saved(db: Session, *, user_id: str, pipeline_run_id: str) -> bool:
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


def save_v3_report_to_repo(db: Session, *, user_id: str, v3_report_id: str) -> RepoItem:
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


def unsave_v3_report_from_repo(db: Session, *, user_id: str, v3_report_id: str) -> None:
    db.query(RepoItem).filter(
        RepoItem.user_id == user_id,
        RepoItem.v3_report_id == v3_report_id,
    ).delete()
    db.commit()


def is_v3_report_saved(db: Session, *, user_id: str, v3_report_id: str) -> bool:
    return (
        db.execute(
            select(RepoItem.id).where(
                RepoItem.user_id == user_id,
                RepoItem.v3_report_id == v3_report_id,
            )
        ).first()
        is not None
    )


# ---------------------------------------------------------------------------
# EU v2 earnings-update report repo support — fourth polymorphic target.
# ---------------------------------------------------------------------------


def save_eu_report_to_repo(db: Session, *, user_id: str, eu_report_id: str) -> RepoItem:
    """Save an EU v2 report to the user's repo. Idempotent."""
    existing = db.execute(
        select(RepoItem).where(
            RepoItem.user_id == user_id,
            RepoItem.eu_v2_report_id == eu_report_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    report = db.get(ReportEu, eu_report_id)
    if report is None or report.user_id != user_id:
        raise LookupError(f"EU report {eu_report_id} not found")
    item = RepoItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        report_id=None,
        pipeline_run_id=None,
        v3_report_id=None,
        eu_v2_report_id=eu_report_id,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.execute(
            select(RepoItem).where(
                RepoItem.user_id == user_id,
                RepoItem.eu_v2_report_id == eu_report_id,
            )
        ).scalar_one()
    db.refresh(item)
    return item


def unsave_eu_report_from_repo(db: Session, *, user_id: str, eu_report_id: str) -> None:
    db.query(RepoItem).filter(
        RepoItem.user_id == user_id,
        RepoItem.eu_v2_report_id == eu_report_id,
    ).delete()
    db.commit()


def is_eu_report_saved(db: Session, *, user_id: str, eu_report_id: str) -> bool:
    return (
        db.execute(
            select(RepoItem.id).where(
                RepoItem.user_id == user_id,
                RepoItem.eu_v2_report_id == eu_report_id,
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


_V3_DEPARTMENT = "equity_research"
_EU_DEPARTMENT = "earnings_update"


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
    """Fan out to every engine's source table, merge into one ordered
    list of ``RepoRow``, then slice for pagination.

    Each engine's helper applies the filters it can express server-
    side (department + date ranges + ``q`` text search). The merge
    step sorts the unified set by the chosen sort key and slices for
    pagination, which means pagination is O(total saved rows). That's
    fine in practice — a user with thousands of saves is rare and the
    queries are well-indexed. Move to a UNION-driven offset/limit if
    that ever stops being true.

    v2.2 pipeline runs are still skipped here pending a follow-up;
    they remain visible via ``GET /api/repo/v2-runs``.
    """
    if sort not in VALID_SORTS:
        raise ValueError(f"invalid sort: {sort!r}")
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 200:
        raise ValueError("page_size must be in [1, 200]")

    rows: list[RepoRow] = []
    # Department filter is engine-agnostic: skip an engine's fanout
    # when the filter narrows to departments that engine never owns.
    department_filter = departments or None
    if department_filter is None or any(
        d == _V3_DEPARTMENT or _is_v1_department(d) for d in department_filter
    ):
        # v1 owns all department slugs; let its query do the filter.
        rows.extend(
            _list_v1_rows(
                db,
                user_id=user_id,
                q=q,
                departments=department_filter,
                generated_from=generated_from,
                generated_to=generated_to,
                saved_from=saved_from,
                saved_to=saved_to,
            )
        )
    if department_filter is None or _V3_DEPARTMENT in department_filter:
        rows.extend(
            _list_v3_rows(
                db,
                user_id=user_id,
                q=q,
                generated_from=generated_from,
                generated_to=generated_to,
                saved_from=saved_from,
                saved_to=saved_to,
            )
        )
    if department_filter is None or _EU_DEPARTMENT in department_filter:
        rows.extend(
            _list_eu_rows(
                db,
                user_id=user_id,
                q=q,
                generated_from=generated_from,
                generated_to=generated_to,
                saved_from=saved_from,
                saved_to=saved_to,
            )
        )

    rows = _sort_rows(rows, sort)
    offset = (page - 1) * page_size
    return rows[offset : offset + page_size]


def _is_v1_department(slug: str) -> bool:
    """v1 reports cover every department the legacy stack supports.
    Today that's effectively any slug — kept as a function to make the
    intent explicit at the call-site and to leave room for future
    per-engine department namespaces."""
    return True


def _list_v1_rows(
    db: Session,
    *,
    user_id: str,
    q: str | None,
    departments: list[str] | None,
    generated_from: date | None,
    generated_to: date | None,
    saved_from: date | None,
    saved_to: date | None,
) -> list[RepoRow]:
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

    out: list[RepoRow] = []
    for item, report in db.execute(stmt).all():
        out.append(
            RepoRow(
                id=item.id,
                engine="v1",
                target_id=report.id,
                department=report.department,
                title=report.title,
                filename=f"{report.title}.pdf",
                generated_at=report.created_at,
                saved_at=item.created_at,
            )
        )
    return out


def _list_v3_rows(
    db: Session,
    *,
    user_id: str,
    q: str | None,
    generated_from: date | None,
    generated_to: date | None,
    saved_from: date | None,
    saved_to: date | None,
) -> list[RepoRow]:
    stmt = (
        select(RepoItem, ReportV3)
        .join(ReportV3, RepoItem.v3_report_id == ReportV3.id)
        .where(RepoItem.user_id == user_id)
    )
    if q:
        stmt = stmt.where(func.lower(ReportV3.subject).like(f"%{q.lower()}%"))
    if generated_from:
        stmt = stmt.where(ReportV3.created_at >= _start_of_day_utc(generated_from))
    if generated_to:
        stmt = stmt.where(ReportV3.created_at <= _end_of_day_utc(generated_to))
    if saved_from:
        stmt = stmt.where(RepoItem.created_at >= _start_of_day_utc(saved_from))
    if saved_to:
        stmt = stmt.where(RepoItem.created_at <= _end_of_day_utc(saved_to))

    out: list[RepoRow] = []
    for item, report in db.execute(stmt).all():
        filename = build_download_filename(row=report, ext="pdf")
        out.append(
            RepoRow(
                id=item.id,
                engine="v3",
                target_id=report.id,
                department=_V3_DEPARTMENT,
                title=report.subject,
                filename=filename,
                generated_at=report.created_at,
                saved_at=item.created_at,
            )
        )
    return out


def _list_eu_rows(
    db: Session,
    *,
    user_id: str,
    q: str | None,
    generated_from: date | None,
    generated_to: date | None,
    saved_from: date | None,
    saved_to: date | None,
) -> list[RepoRow]:
    stmt = (
        select(RepoItem, ReportEu)
        .join(ReportEu, RepoItem.eu_v2_report_id == ReportEu.id)
        .where(RepoItem.user_id == user_id)
    )
    if q:
        stmt = stmt.where(func.lower(ReportEu.subject).like(f"%{q.lower()}%"))
    if generated_from:
        stmt = stmt.where(ReportEu.created_at >= _start_of_day_utc(generated_from))
    if generated_to:
        stmt = stmt.where(ReportEu.created_at <= _end_of_day_utc(generated_to))
    if saved_from:
        stmt = stmt.where(RepoItem.created_at >= _start_of_day_utc(saved_from))
    if saved_to:
        stmt = stmt.where(RepoItem.created_at <= _end_of_day_utc(saved_to))

    out: list[RepoRow] = []
    for item, report in db.execute(stmt).all():
        filename = build_eu_download_filename(row=report, ext="pdf")
        out.append(
            RepoRow(
                id=item.id,
                engine="eu_v2",
                target_id=report.id,
                department=_EU_DEPARTMENT,
                title=report.subject,
                filename=filename,
                generated_at=report.created_at,
                saved_at=item.created_at,
            )
        )
    return out


def _sort_rows(rows: list[RepoRow], sort: SortKey) -> list[RepoRow]:
    if sort == "saved_desc":
        return sorted(rows, key=lambda r: (r.saved_at, r.id), reverse=True)
    if sort == "saved_asc":
        return sorted(rows, key=lambda r: (r.saved_at, r.id))
    if sort == "generated_desc":
        return sorted(rows, key=lambda r: (r.generated_at, r.id), reverse=True)
    if sort == "generated_asc":
        return sorted(rows, key=lambda r: (r.generated_at, r.id))
    if sort == "department_asc":
        return sorted(rows, key=lambda r: (r.department, r.title))
    if sort == "filename_asc":
        # Binary sort to match the SQL ORDER BY semantics the existing
        # tests assert against (uppercase ASCII sorts before lowercase).
        return sorted(rows, key=lambda r: r.title)
    return rows


def facets(db: Session, *, user_id: str) -> dict:
    """Aggregate saved-item counts per department across all engines.

    v1: groups on ``Report.department`` (covers every non-equity slug
    plus older v1 equity-research rows). v3: every saved row counts
    as one ``equity_research`` entry. eu_v2: every saved row counts as
    one ``earnings_update`` entry. v2 still pending.
    """
    counts: dict[str, int] = {}

    v1_stmt = (
        select(Report.department, func.count(RepoItem.id))
        .join(Report, RepoItem.report_id == Report.id)
        .where(RepoItem.user_id == user_id, Report.expired_at.is_(None))
        .group_by(Report.department)
    )
    for dep, count in db.execute(v1_stmt).all():
        counts[dep] = counts.get(dep, 0) + int(count)

    v3_stmt = (
        select(func.count(RepoItem.id))
        .join(ReportV3, RepoItem.v3_report_id == ReportV3.id)
        .where(RepoItem.user_id == user_id)
    )
    v3_count = int(db.execute(v3_stmt).scalar() or 0)
    if v3_count:
        counts[_V3_DEPARTMENT] = counts.get(_V3_DEPARTMENT, 0) + v3_count

    eu_stmt = (
        select(func.count(RepoItem.id))
        .join(ReportEu, RepoItem.eu_v2_report_id == ReportEu.id)
        .where(RepoItem.user_id == user_id)
    )
    eu_count = int(db.execute(eu_stmt).scalar() or 0)
    if eu_count:
        counts[_EU_DEPARTMENT] = counts.get(_EU_DEPARTMENT, 0) + eu_count

    departments = [{"slug": dep, "count": counts[dep]} for dep in sorted(counts.keys())]
    total = sum(d["count"] for d in departments)
    return {"departments": departments, "total": total}
