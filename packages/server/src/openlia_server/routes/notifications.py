"""User notification endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from openlia_server.auth.deps import get_current_user
from openlia_server.db.models.auth import User
from openlia_server.scheduler.services import notifications as notif_service


router = APIRouter(prefix="/notifications", tags=["notifications"])


class UnreadOut(BaseModel):
    by_department: dict[str, int]
    total: int


class MarkReadIn(BaseModel):
    department: str = Field(min_length=1)


class MarkReadOut(BaseModel):
    marked_read: int


@router.get("/unread", response_model=UnreadOut)
def get_unread(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> UnreadOut:
    svc = request.app.state.scheduler
    with svc.session_factory() as session:
        by_dept = notif_service.unread_counts_by_department(
            session=session, user_id=user.id
        )
        total = notif_service.unread_total(session=session, user_id=user.id)
    return UnreadOut(by_department=by_dept, total=total)


@router.post("/read", response_model=MarkReadOut)
def mark_read(
    body: MarkReadIn,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
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
