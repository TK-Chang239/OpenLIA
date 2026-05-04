from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from openlia.skills import LayeredSkillStore, SkillRegistry
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.safety import LiaGuardrailEvent
from openlia_server.middleware.auth import build_require_auth

_SKILL_EVENT_TYPES = (
    "skill_installed",
    "skill_uninstalled",
    "skill_enabled",
    "skill_disabled",
    "skill_loaded",
)


def build_admin_skills_router(
    *,
    db_session_factory: Callable[[], DBSession],
    store: LayeredSkillStore,
    registry: SkillRegistry,
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/admin/skills", tags=["skills-admin"])

    def _admin_only(user: User) -> User:
        if not getattr(user, "is_admin", False):
            raise HTTPException(403, "admin only")
        return user

    @router.get("")
    async def list_all(user: User = require_auth):
        _admin_only(user)
        sys_skills = await store.system.list(scope="system", user_id=None)
        return {
            "items": [
                {
                    "skill_id": s.manifest.name,
                    "scope": s.scope,
                    "user_id": s.user_id,
                    "version": s.manifest.version,
                    "enabled": s.enabled,
                    "installed_at": s.installed_at.isoformat(),
                }
                for s in sys_skills
            ]
        }

    @router.get("/audit")
    def audit(
        since_days: int = Query(7, ge=1, le=365),
        skill_id: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ):
        _admin_only(user)
        cutoff = datetime.now(UTC) - timedelta(days=since_days)
        stmt = (
            select(LiaGuardrailEvent)
            .where(LiaGuardrailEvent.event_type.in_(_SKILL_EVENT_TYPES))
            .where(LiaGuardrailEvent.created_at >= cutoff)
            .order_by(LiaGuardrailEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if skill_id:
            stmt = stmt.where(LiaGuardrailEvent.category == skill_id)
        rows = db.execute(stmt).scalars().all()
        return {
            "items": [
                {
                    "id": r.id,
                    "created_at": r.created_at.isoformat(),
                    "user_id": r.user_id,
                    "session_id": r.session_id,
                    "department_id": r.department_id,
                    "event_type": r.event_type,
                    "skill_id": r.category,
                    "payload": r.payload_json,
                }
                for r in rows
            ]
        }

    return router
