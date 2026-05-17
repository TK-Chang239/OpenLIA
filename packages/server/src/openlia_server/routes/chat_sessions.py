"""Routes for chat session CRUD and message listing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatAttachment, ChatMessage, Report
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import chat_sessions as svc


def _attach_report_as_context(
    db: Session, *, session_id: str, user_id: str, report_id: str
) -> None:
    """Insert a ``user``-role chat message containing the report's title +
    structured payload as JSON. The Secretary LLM sees this as the first
    message in the conversation and can ground follow-ups against it.

    Silently no-ops when the report is missing or owned by a different user
    so a malformed handoff URL doesn't fail session creation.
    """
    report = db.get(Report, report_id)
    if report is None or report.user_id != user_id:
        return
    payload: dict = {
        "type": "attached_report",
        "report_id": report.id,
        "department": report.department,
        "title": report.title,
        "schema": report.content_structured,
    }
    body = (
        f"[Report attached: {report.title}]\n"
        f"The user has attached a report from {report.department}. "
        "Use it as the primary reference when answering follow-up questions.\n\n"
        f"```json\n{json.dumps(payload)}\n```"
    )
    db.add(
        ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content=body,
        )
    )
    db.flush()


class SessionOut(BaseModel):
    id: str
    department: str
    title: str
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    model_id: str | None = None
    disabled_connector_ids: list[str] = Field(default_factory=list)
    disabled_skill_ids: list[str] = Field(default_factory=list)
    response_length: str | None = None


class SessionListOut(BaseModel):
    items: list[SessionOut]


_DEPARTMENT_PATTERN = (
    r"^(secretary|equity_research|earnings_update|morning_briefing"
    r"|retail_sentiment|macro_research|panic_thermometer)$"
)


class SessionCreateIn(BaseModel):
    department: str = Field(..., pattern=_DEPARTMENT_PATTERN)
    title: str = Field(..., min_length=1, max_length=200)
    # Optional report to attach to the new session. When set, the server
    # injects a system-role message containing the report's structured
    # JSON so the assistant has the report content as conversational
    # context. Used by "Ask in Secretary →" handoffs from report viewers.
    attached_report_id: str | None = None


class DepartmentIn(BaseModel):
    department: str = Field(..., pattern=_DEPARTMENT_PATTERN)


class SessionPatchIn(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None
    disabled_connector_ids: list[str] | None = None
    disabled_skill_ids: list[str] | None = None
    # Composer response-length picker. ``None`` (key omitted) leaves the
    # current value unchanged. To explicitly clear, send ``"normal"`` —
    # the service treats ``"normal"`` and unset identically (no length
    # directive injected into the system prompt).
    response_length: str | None = None


class SessionModelIn(BaseModel):
    """``model_id=null`` clears the override and reverts to slot-based resolution."""

    model_id: str | None = None


class AttachmentOut(BaseModel):
    filename: str
    size_bytes: int


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: list[dict] | None = None
    model_ref: str | None = None
    token_usage: dict | None = None
    created_at: datetime
    stopped_at: datetime | None = None
    attachments: list[AttachmentOut] = Field(default_factory=list)


class MessageListOut(BaseModel):
    items: list[MessageOut]


def build_chat_sessions_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("", response_model=SessionListOut)
    def list_sessions_ep(
        include_archived: bool = False,
        department: str | None = None,
        q: str | None = None,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionListOut:
        rows = svc.list_sessions(
            db,
            user_id=user.id,
            include_archived=include_archived,
            department=department,
            q=q,
        )
        return SessionListOut(
            items=[SessionOut.model_validate(r, from_attributes=True) for r in rows]
        )

    @router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
    def create_session_ep(
        body: SessionCreateIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionOut:
        row = svc.create_session(db, user_id=user.id, department=body.department, title=body.title)
        if body.attached_report_id:
            _attach_report_as_context(
                db, session_id=row.id, user_id=user.id, report_id=body.attached_report_id
            )
        return SessionOut.model_validate(row, from_attributes=True)

    @router.get("/by-department/{department}", response_model=SessionOut)
    def get_or_create_by_department_ep(
        department: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionOut:
        try:
            DepartmentIn(department=department)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "invalid_department", "message": str(exc)}
            ) from exc
        row = svc.get_or_create_default_session(db, user_id=user.id, department=department)
        return SessionOut.model_validate(row, from_attributes=True)

    @router.get("/{session_id}", response_model=SessionOut)
    def get_session_ep(
        session_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> SessionOut:
        try:
            row = svc.get_session(db, session_id=session_id, user_id=user.id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        return SessionOut.model_validate(row, from_attributes=True)

    @router.patch("/{session_id}")
    def patch_session_ep(
        session_id: str,
        body: SessionPatchIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        try:
            if body.title is not None:
                svc.rename_session(db, session_id=session_id, user_id=user.id, new_title=body.title)
            if body.pinned is not None:
                svc.set_pinned(db, session_id=session_id, user_id=user.id, pinned=body.pinned)
            if body.archived is True:
                svc.archive_session(db, session_id=session_id, user_id=user.id)
            if body.archived is False:
                svc.unarchive_session(db, session_id=session_id, user_id=user.id)
            if body.disabled_connector_ids is not None or body.disabled_skill_ids is not None:
                svc.set_session_disabled_lists(
                    db,
                    session_id=session_id,
                    user_id=user.id,
                    disabled_connector_ids=body.disabled_connector_ids,
                    disabled_skill_ids=body.disabled_skill_ids,
                )
            if body.response_length is not None:
                svc.set_session_response_length(
                    db,
                    session_id=session_id,
                    user_id=user.id,
                    response_length=body.response_length,
                )
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "invalid", "message": str(exc)}
            ) from exc
        return {"ok": True}

    @router.put("/{session_id}/model")
    def put_session_model_ep(
        session_id: str,
        body: SessionModelIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        if body.model_id is not None:
            from openlia_server.db.models.config import LLMModel

            model = db.get(LLMModel, body.model_id)
            if model is None or not model.is_enabled:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "model_not_found", "message": "Model id not in roster."},
                )
        try:
            svc.set_session_model(
                db, session_id=session_id, user_id=user.id, model_id=body.model_id
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        return {"ok": True}

    @router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_session_ep(
        session_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        try:
            svc.delete_session(db, session_id=session_id, user_id=user.id)
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc

    @router.get("/{session_id}/messages", response_model=MessageListOut)
    def list_messages_ep(
        session_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> MessageListOut:
        try:
            rows = svc.list_messages(db, session_id=session_id, user_id=user.id)
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail={"code": "forbidden", "message": str(exc)}
            ) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": str(exc)}
            ) from exc
        message_ids = [r.id for r in rows]
        attachments_by_message: dict[str, list[AttachmentOut]] = {}
        if message_ids:
            att_stmt = (
                select(ChatAttachment)
                .where(ChatAttachment.message_id.in_(message_ids))
                .order_by(ChatAttachment.created_at.asc(), ChatAttachment.id.asc())
            )
            for a in db.execute(att_stmt).scalars():
                attachments_by_message.setdefault(a.message_id, []).append(
                    AttachmentOut(filename=a.filename, size_bytes=a.size_bytes)
                )
        return MessageListOut(
            items=[
                MessageOut(
                    id=r.id,
                    role=r.role,
                    content=r.content,
                    tool_calls=r.tool_calls,
                    model_ref=r.model_ref,
                    token_usage=r.token_usage,
                    created_at=r.created_at,
                    stopped_at=r.stopped_at,
                    attachments=attachments_by_message.get(r.id, []),
                )
                for r in rows
            ]
        )

    return router
