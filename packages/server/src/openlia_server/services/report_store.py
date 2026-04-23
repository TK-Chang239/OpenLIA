from __future__ import annotations

import uuid

from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report


class ReportNotFoundError(LookupError):
    pass


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
) -> str:
    report_id = str(uuid.uuid4())
    row = Report(
        id=report_id,
        user_id=user_id,
        department=department,
        report_type=mode,
        title=schema.cover.title,
        content_markdown=content_markdown,
        content_structured=schema.model_dump(mode="json"),
        model_ref=model_ref,
    )
    session.add(row)
    session.flush()
    return report_id
