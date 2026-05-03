"""GET /api/admin/guardrail-events — paginated, filterable audit reader."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.guardrail_log import list_events, wipe_all


def build_guardrail_events_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/admin/guardrail-events", tags=["guardrail"])

    @router.get("")
    def get_events(
        since_days: int = Query(7, ge=1, le=365),
        category: str | None = None,
        department_id: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, object]:
        rows = list_events(
            db,
            since_days=since_days,
            category=category,
            department_id=department_id,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [
                {
                    "id": r.id,
                    "created_at": r.created_at.isoformat(),
                    "session_id": r.session_id,
                    "user_id": r.user_id,
                    "department_id": r.department_id,
                    "event_type": r.event_type,
                    "category": r.category,
                    "action_taken": r.action_taken,
                    "tripwire_pattern": r.tripwire_pattern,
                    "response_excerpt": r.response_excerpt,
                    "model_ref": r.model_ref,
                }
                for r in rows
            ],
        }

    @router.delete("")
    def wipe(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, int]:
        n = wipe_all(db)
        db.commit()
        return {"deleted": n}

    return router
