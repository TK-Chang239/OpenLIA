"""User notification endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.scheduler.services import notifications as notif_service


class UnreadOut(BaseModel):
    by_department: dict[str, int]
    total: int


class MarkReadIn(BaseModel):
    department: str = Field(min_length=1)


class MarkReadOut(BaseModel):
    marked_read: int


def build_notifications_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    """Factory for /notifications/*. Binds the real auth dependency for the given mode."""
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/notifications", tags=["notifications"])

    @router.get("/unread", response_model=UnreadOut)
    def get_unread(
        request: Request,
        user: User = require_auth,
    ) -> UnreadOut:
        svc = request.app.state.scheduler
        with svc.session_factory() as session:
            by_dept = notif_service.unread_counts_by_department(session=session, user_id=user.id)
            total = notif_service.unread_total(session=session, user_id=user.id)
        return UnreadOut(by_department=by_dept, total=total)

    @router.post("/read", response_model=MarkReadOut)
    def mark_read(
        body: MarkReadIn,
        request: Request,
        user: User = require_auth,
    ) -> MarkReadOut:
        svc = request.app.state.scheduler
        with svc.session_factory() as session:
            count = notif_service.mark_department_read(
                session=session,
                user_id=user.id,
                department=body.department,
            )
            # mark_department_read does not commit; callers own transaction boundaries.
            session.commit()
        return MarkReadOut(marked_read=count)

    return router
