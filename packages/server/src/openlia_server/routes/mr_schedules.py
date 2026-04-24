"""MR schedule CRUD — singleton per user."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth


class ScheduleUpsert(BaseModel):
    cron_expression: str


def build_mr_schedule_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
    mr_schedule_service: Any,
    require_auth_override: Callable[..., Any] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/departments/macro_research/schedule", tags=["macro_research"])
    if require_auth_override is not None:
        require_auth = Depends(require_auth_override)
    else:
        require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)

    @router.get("")
    def get_schedule(user: User = require_auth) -> dict[str, Any]:
        row = mr_schedule_service.get(user_id=user.id)
        if row is None or row.assessment_schedule is None:
            return {"cron_expression": None, "last_assessment_at": None}
        return {
            "cron_expression": row.assessment_schedule,
            "last_assessment_at": (
                row.last_assessment_at.isoformat() if row.last_assessment_at else None
            ),
        }

    @router.put("")
    async def put_schedule(body: ScheduleUpsert, user: User = require_auth) -> dict[str, Any]:
        if not body.cron_expression.strip():
            raise HTTPException(status_code=400, detail="cron_expression required")
        row = await mr_schedule_service.upsert(
            user_id=user.id, cron_expression=body.cron_expression
        )
        return {"cron_expression": row.assessment_schedule}

    @router.delete("", status_code=204)
    async def delete_schedule(user: User = require_auth) -> Response:
        await mr_schedule_service.delete(user_id=user.id)
        return Response(status_code=204)

    return router
