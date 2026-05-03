"""GET /api/disclaimer, GET /api/disclaimer/status, POST /api/disclaimer/accept."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from openlia.safety.disclaimer import DISCLAIMER_TEXT, DISCLAIMER_VERSION
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import disclaimer as svc


class AcceptRequest(BaseModel):
    version: str


def build_disclaimer_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/disclaimer", tags=["disclaimer"])

    @router.get("")
    def get_disclaimer() -> dict[str, str]:
        return {"text": DISCLAIMER_TEXT, "version": DISCLAIMER_VERSION}

    @router.get("/status")
    def get_status(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, object]:
        accepted = svc.has_accepted(db, user_id=user.id, version=DISCLAIMER_VERSION)
        return {
            "current_version": DISCLAIMER_VERSION,
            "accepted": accepted,
            "accepted_version": DISCLAIMER_VERSION if accepted else None,
        }

    @router.post("/accept")
    def post_accept(
        body: AcceptRequest,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, str]:
        if body.version != DISCLAIMER_VERSION:
            raise HTTPException(
                status_code=400,
                detail={"code": "stale_version", "current_version": DISCLAIMER_VERSION},
            )
        svc.record_acceptance(db, user_id=user.id, version=body.version)
        db.commit()
        return {"status": "accepted", "version": body.version}

    return router
