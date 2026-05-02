"""Routes for chat session CRUD and message listing."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import chat_sessions as svc


class SessionOut(BaseModel):
    id: str
    department: str
    title: str
    is_pinned: bool
    is_archived: bool
    created_at: datetime


class SessionListOut(BaseModel):
    items: list[SessionOut]


_DEPARTMENT_PATTERN = (
    r"^(secretary|equity_research|earnings_update|morning_briefing"
    r"|retail_sentiment|macro_research|panic_thermometer)$"
)


class SessionCreateIn(BaseModel):
    department: str = Field(..., pattern=_DEPARTMENT_PATTERN)
    title: str = Field(..., min_length=1, max_length=200)


class DepartmentIn(BaseModel):
    department: str = Field(..., pattern=_DEPARTMENT_PATTERN)


class SessionPatchIn(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: list[dict] | None = None
    model_ref: str | None = None
    token_usage: dict | None = None
    created_at: datetime
    stopped_at: datetime | None = None


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
                )
                for r in rows
            ]
        )

    return router
