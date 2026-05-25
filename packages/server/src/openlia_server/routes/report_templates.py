"""REST endpoints for user-uploaded report templates (PR 9)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from openlia.llm.runtime.report_v2.template_v2.conversion_prompt import (
    build_conversion_prompt,
)
from openlia.llm.runtime.report_v2_3.templates import TemplateSpec as V23TemplateSpec
from openlia.llm.runtime.report_v2_3.templates.builtins import BUILTIN_TEMPLATES
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_templates import ReportTemplate
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.template_compile import compile_template_spec
from openlia_server.services.template_compile_v23 import compile_v23_spec
from openlia_server.services.template_ingest import (
    UnsupportedDocumentError,
    ingest_document,
)
from openlia_server.services.template_parser import parse_template


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


class IngestOut(BaseModel):
    markdown: str


class ParseIn(BaseModel):
    markdown: str
    name: str = "Untitled template"


class ParsedSectionOut(BaseModel):
    id: str
    title: str
    brief: str
    frontmatter: dict[str, Any]


class ParseOut(BaseModel):
    global_preface: str
    document_frontmatter: dict[str, Any]
    sections: list[ParsedSectionOut]
    template_spec: dict[str, Any]


class ConversionPromptOut(BaseModel):
    prompt: str


class V23ParseIn(BaseModel):
    markdown: str
    name: str = "Untitled template"


class V23ParseOut(BaseModel):
    template_spec: dict[str, Any]
    validation_errors: list[str]


class V23ValidateIn(BaseModel):
    template_spec: dict[str, Any]


class V23BuiltinOut(BaseModel):
    report_type: str
    template_spec: dict[str, Any]


class V23BuiltinListOut(BaseModel):
    items: list[V23BuiltinOut]


def build_report_templates_router(
    *,
    db_session_factory: Any,
    mode: str,
) -> APIRouter:
    """Mount the report-templates CRUD endpoints under /api/report-templates."""
    router = APIRouter(prefix="/report-templates", tags=["report-templates"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/conversion_prompt", response_model=ConversionPromptOut)
    def get_conversion_prompt() -> ConversionPromptOut:
        return ConversionPromptOut(prompt=build_conversion_prompt())

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

    @router.post("/ingest", response_model=IngestOut)
    async def ingest_upload(
        file: UploadFile,
        _user: User = require_auth,
    ) -> IngestOut:
        blob = await file.read()
        mime = file.content_type or "application/octet-stream"
        # Fall back on filename suffix when the browser sends a generic mime
        # (Safari + .md uploads commonly arrive as application/octet-stream).
        if mime not in (
            "text/markdown",
            "text/x-markdown",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            lower = (file.filename or "").lower()
            if lower.endswith(".md") or lower.endswith(".markdown"):
                mime = "text/markdown"
            elif lower.endswith(".txt"):
                mime = "text/plain"
            elif lower.endswith(".docx"):
                mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        try:
            markdown = ingest_document(blob, mime)
        except UnsupportedDocumentError as err:
            raise HTTPException(status_code=415, detail=str(err)) from err
        return IngestOut(markdown=markdown)

    @router.post("/parse", response_model=ParseOut)
    def parse_markdown(
        payload: ParseIn,
        _user: User = require_auth,
    ) -> ParseOut:
        parsed = parse_template(payload.markdown)
        spec = compile_template_spec(parsed, name=payload.name)
        return ParseOut(
            global_preface=parsed.global_preface,
            document_frontmatter=parsed.document_frontmatter,
            sections=[
                ParsedSectionOut(
                    id=s.id,
                    title=s.title,
                    brief=s.brief,
                    frontmatter=s.frontmatter,
                )
                for s in parsed.sections
            ],
            template_spec=spec,
        )

    @router.get("/v23/builtins", response_model=V23BuiltinListOut)
    def v23_builtins(_user: User = require_auth) -> V23BuiltinListOut:
        """Return the five built-in v2.3 TemplateSpecs paired with their
        ReportType key. The pill renders these as flat siblings of the
        user's uploaded templates so morning_brief / earnings_review are
        first-class instead of hidden behind v2.2's three-mode UI."""
        items = [
            V23BuiltinOut(
                report_type=rt.value,
                template_spec=spec.model_dump(mode="json"),
            )
            for rt, spec in BUILTIN_TEMPLATES.items()
        ]
        return V23BuiltinListOut(items=items)

    @router.post("/v23/validate", response_model=V23ParseOut)
    def v23_validate(
        payload: V23ValidateIn,
        _user: User = require_auth,
    ) -> V23ParseOut:
        """Validate a pre-built v2.3 TemplateSpec dict (e.g. uploaded .json)
        without going through the markdown parse path. Same envelope as
        /v23/parse so the upload UI can render errors inline."""
        errors: list[str] = []
        try:
            spec = V23TemplateSpec.model_validate(payload.template_spec)
        except ValidationError as err:
            return V23ParseOut(
                template_spec={},
                validation_errors=[
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()
                ],
            )
        return V23ParseOut(
            template_spec=spec.model_dump(mode="json"),
            validation_errors=errors,
        )

    @router.post("/v23/parse", response_model=V23ParseOut)
    def v23_parse(
        payload: V23ParseIn,
        _user: User = require_auth,
    ) -> V23ParseOut:
        """Parse markdown into a v2.3 TemplateSpec dict for preview.

        The endpoint always returns 200 — schema validation errors come
        back in `validation_errors` so the upload UI can render them
        inline next to the parsed structure rather than as an HTTP error."""
        parsed = parse_template(payload.markdown)
        try:
            spec_dict = compile_v23_spec(parsed, fallback_name=payload.name)
        except ValueError as err:
            return V23ParseOut(template_spec={}, validation_errors=[str(err)])
        errors: list[str] = []
        try:
            V23TemplateSpec.model_validate(spec_dict)
        except ValidationError as err:
            errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()]
        return V23ParseOut(template_spec=spec_dict, validation_errors=errors)

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
