"""GET /reports/{id} — owner-scoped report read."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services.reports import get_report_for_user


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    department: str
    report_type: str
    title: str
    subject: str | None
    content_markdown: str
    content_structured: dict
    model_ref: str
    created_at: datetime
    updated_at: datetime


def build_reports_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/reports", tags=["reports"])

    @router.get("/{report_id}", response_model=ReportResponse)
    def get_report(
        report_id: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> ReportResponse:
        report = get_report_for_user(db, user_id=user.id, report_id=report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return ReportResponse.model_validate(report)

    return router
