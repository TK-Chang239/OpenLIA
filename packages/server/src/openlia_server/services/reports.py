"""Report store service — canonical Phase-13 implementation.

Validates `ReportSchema` payloads from `ReportRunner` (Phase 13 Task 3) and
persists them in the `reports` table. Also exposes:

- `ReportStoreImpl` — Protocol adapter used by the scheduler executors so a
  finished background-job report payload can be written via `save()`.
- `get_report` / `create_report` — primary read/write API used by routes.
- `get_report_for_user` / `save_report` — alternate-shape helpers used by
  HTTP-driven flows (return the ORM row directly without revalidation).

Transaction ownership stays with the caller (route session dependency or
scheduler executor); this module never commits.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import RepoItem, Report, ReportVersion
from openlia_server.db.models.graph import GraphArtifactSummary


class ReportNotFoundError(LookupError):
    pass


class InvalidReportSchemaError(ValueError):
    """Raised when a payload fails canonical `ReportSchema` validation."""


_EARNINGS_PERIOD_RE = re.compile(r"Q[1-4]\s*F?Y\s*\d{2,4}", re.IGNORECASE)


def derive_report_title(mode: str, schema: ReportSchema) -> str | None:
    """Build a distinguishing repo-list title from cover fields.

    Returns ``None`` when the relevant cover fields are missing so callers
    can fall back to ``cover.title``. Keeps the on-page H1 (``cover.title``,
    e.g. "Stock Initiation Report") untouched — only the persisted DB title
    used in repo lists, file viewer, and PDF filename changes.
    """
    cover = schema.cover
    ticker = (cover.ticker or "").strip()
    subtitle = (cover.subtitle or "").strip()
    eyebrow = (cover.eyebrow or "").strip()

    if mode == "stock_initiation":
        return f"{ticker} — Initiation" if ticker else None
    if mode == "stock_update":
        return f"{ticker} — Update" if ticker else None
    if mode == "sector_research":
        return f"{subtitle} — Sector Research" if subtitle else None
    if mode in ("earnings_analysis", "earnings_update"):
        if not ticker:
            return None
        period_match = _EARNINGS_PERIOD_RE.search(eyebrow)
        if period_match:
            period = re.sub(r"\s+", " ", period_match.group(0)).upper().replace("FY ", "FY")
            return f"{ticker} {period} Earnings"
        return f"{ticker} Earnings"
    return None


def validate_report_schema(payload: Any) -> ReportSchema:
    """Validate `payload` against the canonical `ReportSchema`.

    Returns the parsed `ReportSchema`. Raises `InvalidReportSchemaError`
    on any pydantic validation failure so callers can render a uniform
    400-style error.
    """
    try:
        return validate_report_payload(payload)
    except Exception as exc:
        raise InvalidReportSchemaError(str(exc)) from exc


class ReportStoreImpl:
    """Adapter that fulfils the scheduler `ReportStore` Protocol by
    persisting completed background-job reports through `create_report`.

    The scheduler hands the executor a finished report payload (a dict
    matching ReportSchema). We validate and write a fresh `reports` row.
    """

    def save(
        self,
        *,
        session: Session,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str:
        schema = validate_report_payload(payload)
        return create_report(
            session,
            user_id=user_id,
            department=department,
            mode="background",
            schema=schema,
        )


def get_report(session: Session, *, report_id: str, user_id: str) -> ReportSchema:
    row = session.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        raise ReportNotFoundError(report_id)
    return validate_report_payload(row.content_structured)


def create_report(
    session: Session,
    *,
    user_id: str,
    department: str,
    mode: str,
    schema: ReportSchema,
    model_ref: str = "",
    subject: str | None = None,
    title: str | None = None,
    source_session_id: str | None = None,
) -> str:
    report_id = str(uuid.uuid4())
    resolved_title = title or derive_report_title(mode, schema) or schema.cover.title
    row = Report(
        id=report_id,
        user_id=user_id,
        department=department,
        report_type=mode,
        title=resolved_title,
        subject=subject,
        # content_markdown column kept on the model (non-null) but no longer
        # populated — PDF/DOCX exports replaced the markdown download path.
        content_markdown="",
        content_structured=schema.model_dump(mode="json"),
        source_session_id=source_session_id,
        model_ref=model_ref,
        status="complete",
    )
    session.add(row)
    session.flush()
    from openlia_server.services import graph_indexing

    graph_indexing.index_report(session, row)
    return report_id


def save_report(
    db: Session,
    *,
    user_id: str,
    department: str,
    report_type: str,
    title: str,
    subject: str | None,
    content_markdown: str,
    content_structured: dict,
    model_ref: str,
    source_session_id: str | None = None,
    token_usage: dict | None = None,
    generation_duration_ms: int | None = None,
) -> Report:
    """Validate `content_structured` against canonical `ReportSchema` and
    insert a fresh `Report` row. Does not commit. Used by HTTP-driven
    flows that want the ORM row back; scheduler executors should prefer
    `ReportStoreImpl.save` / `create_report`.
    """
    validate_report_schema(content_structured)
    report = Report(
        id=str(uuid.uuid4()),
        user_id=user_id,
        department=department,
        report_type=report_type,
        title=title,
        subject=subject,
        content_markdown=content_markdown,
        content_structured=content_structured,
        source_session_id=source_session_id,
        model_ref=model_ref,
        token_usage=token_usage,
        generation_duration_ms=generation_duration_ms,
        status="complete",
    )
    db.add(report)
    db.flush()
    # Cross-session memory graph (slice 4): emit mentions edges from any
    # ticker/theme carried in the report's structured fields. Local import
    # keeps the dependency direction one-way and avoids a circular import
    # with services that read reports.
    from openlia_server.services import graph_indexing

    graph_indexing.index_report(db, report)
    return report


def get_report_for_user(db: Session, *, user_id: str, report_id: str) -> Report | None:
    """Return the report iff it exists and `user_id` is the owner."""
    stmt = select(Report).where(Report.id == report_id).where(Report.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def tombstone_report(db: Session, *, report_id: str) -> bool:
    """Tombstone a report. Returns True if state changed, False otherwise.

    Single canonical write that produces a tombstoned report: body fields
    blanked, ``report_versions`` / ``repo_items`` / ``graph_artifact_summaries``
    deleted, ``expired_at`` stamped. Both ``DELETE /reports/{id}`` and the
    nightly maintenance sweep invoke this so there is one end state.

    Idempotent: returns False if the report is missing or already
    tombstoned. The caller commits.
    """
    report = db.get(Report, report_id)
    if report is None:
        return False
    if report.expired_at is not None:
        return False

    db.execute(delete(ReportVersion).where(ReportVersion.report_id == report_id))
    db.execute(delete(RepoItem).where(RepoItem.report_id == report_id))
    db.execute(
        delete(GraphArtifactSummary).where(
            GraphArtifactSummary.artifact_kind == "report",
            GraphArtifactSummary.artifact_id == report_id,
        )
    )

    report.content_markdown = ""
    report.content_structured = {}
    report.expired_at = datetime.now(UTC)
    db.add(report)
    return True
