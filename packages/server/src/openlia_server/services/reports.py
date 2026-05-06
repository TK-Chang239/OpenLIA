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

import uuid
from typing import Any

from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report


class ReportNotFoundError(LookupError):
    pass


class InvalidReportSchemaError(ValueError):
    """Raised when a payload fails canonical `ReportSchema` validation."""


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
    content_markdown: str = "",
    subject: str | None = None,
    title: str | None = None,
) -> str:
    report_id = str(uuid.uuid4())
    row = Report(
        id=report_id,
        user_id=user_id,
        department=department,
        report_type=mode,
        title=title or schema.cover.title,
        subject=subject,
        content_markdown=content_markdown,
        content_structured=schema.model_dump(mode="json"),
        model_ref=model_ref,
    )
    session.add(row)
    session.flush()
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
    )
    db.add(report)
    db.flush()
    return report


def get_report_for_user(db: Session, *, user_id: str, report_id: str) -> Report | None:
    """Return the report iff it exists and `user_id` is the owner."""
    stmt = select(Report).where(Report.id == report_id).where(Report.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()
