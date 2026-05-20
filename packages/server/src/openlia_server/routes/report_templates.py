"""REST endpoints for user-uploaded report templates (PR 9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_templates import ReportTemplate
from openlia_server.middleware.auth import build_require_auth


class ReportTemplateIn(BaseModel):
    name: str
    template_spec: dict[str, Any]
    source_markdown: str | None = None


class ReportTemplateOut(BaseModel):
    id: str
    name: str
    template_spec: dict[str, Any]
    source_markdown: str | None
    created_at: datetime
    updated_at: datetime


class ReportTemplateListOut(BaseModel):
    items: list[ReportTemplateOut]


def build_report_templates_router(
    *,
    db_session_factory: Any,
    mode: str,
) -> APIRouter:
    """Mount the report-templates CRUD endpoints under /api/report-templates."""
    router = APIRouter(prefix="/report-templates", tags=["report-templates"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    def _to_out(row: ReportTemplate) -> ReportTemplateOut:
        return ReportTemplateOut(
            id=row.id,
            name=row.name,
            template_spec=row.template_spec_json,
            source_markdown=row.source_markdown,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @router.get("", response_model=ReportTemplateListOut)
    def list_templates(
        session: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> ReportTemplateListOut:
        rows = (
            session.query(ReportTemplate)
            .filter(ReportTemplate.user_id == user.id)
            .order_by(ReportTemplate.created_at.desc())
            .all()
        )
        return ReportTemplateListOut(items=[_to_out(r) for r in rows])

    @router.post("", response_model=ReportTemplateOut, status_code=status.HTTP_201_CREATED)
    def create_template(
        payload: ReportTemplateIn,
        session: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> ReportTemplateOut:
        row = ReportTemplate(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name=payload.name,
            template_spec_json=payload.template_spec,
            source_markdown=payload.source_markdown,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_out(row)

    @router.get("/{template_id}", response_model=ReportTemplateOut)
    def get_template(
        template_id: str,
        session: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> ReportTemplateOut:
        row = session.get(ReportTemplate, template_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(status_code=404, detail="template not found")
        return _to_out(row)

    @router.put("/{template_id}", response_model=ReportTemplateOut)
    def update_template(
        template_id: str,
        payload: ReportTemplateIn,
        session: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> ReportTemplateOut:
        row = session.get(ReportTemplate, template_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(status_code=404, detail="template not found")
        row.name = payload.name
        row.template_spec_json = payload.template_spec
        row.source_markdown = payload.source_markdown
        session.commit()
        session.refresh(row)
        return _to_out(row)

    @router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_template(
        template_id: str,
        session: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        row = session.get(ReportTemplate, template_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(status_code=404, detail="template not found")
        session.delete(row)
        session.commit()

    return router
