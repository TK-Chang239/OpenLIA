"""Report store service.

Validates completed report schemas emitted by `ReportRunner` and persists
them into the `reports` table. Transaction ownership stays with the caller
(route session dependency) — nothing here commits.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report


class InvalidReportSchemaError(ValueError):
    """Raised when a report schema does not match the runtime contract."""


def validate_report_schema(schema: Any) -> None:
    """Require `title: str` and `sections: list[{heading: str, content: str}]`."""
    if not isinstance(schema, dict):
        raise InvalidReportSchemaError("schema must be a dict")
    title = schema.get("title")
    if not isinstance(title, str) or not title:
        raise InvalidReportSchemaError("schema.title must be a non-empty str")
    sections = schema.get("sections")
    if not isinstance(sections, list):
        raise InvalidReportSchemaError("schema.sections must be a list")
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise InvalidReportSchemaError(f"schema.sections[{i}] must be a dict")
        heading = section.get("heading")
        if not isinstance(heading, str):
            raise InvalidReportSchemaError(
                f"schema.sections[{i}].heading must be a str"
            )
        content = section.get("content")
        if not isinstance(content, str):
            raise InvalidReportSchemaError(
                f"schema.sections[{i}].content must be a str"
            )


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
    """Validate schema, build `Report`, flush, return. Does not commit."""
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


def get_report_for_user(
    db: Session, *, user_id: str, report_id: str
) -> Report | None:
    """Return the report iff it exists and `user_id` is the owner."""
    stmt = select(Report).where(Report.id == report_id).where(Report.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()
