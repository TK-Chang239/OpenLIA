"""Routes for GET/PATCH /settings/prefs — display name, notifications, theme, language."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import user_prefs as svc


class PrefsOut(BaseModel):
    display_name: str
    theme: str
    notify_inapp: bool
    notify_email: bool
    display_language: str
    response_language: str
    report_language: str


class PrefsPatchIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    theme: str | None = Field(default=None, pattern=r"^(system|light|dark)$")
    notify_inapp: bool | None = None
    notify_email: bool | None = None
    display_language: str | None = Field(default=None, pattern=r"^(en|zh-TW)$")
    response_language: str | None = Field(default=None, pattern=r"^(en|zh-TW)$")
    report_language: str | None = Field(default=None, pattern=r"^(en|zh-TW|both)$")


def _to_out(user: User, prefs) -> PrefsOut:
    return PrefsOut(
        display_name=user.display_name,
        theme=prefs.theme,
        notify_inapp=prefs.notify_inapp,
        notify_email=prefs.notify_email,
        display_language=prefs.display_language,
        response_language=prefs.response_language,
        report_language=prefs.report_language,
    )


def build_settings_general_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/prefs", response_model=PrefsOut)
    def get_prefs(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> PrefsOut:
        prefs = svc.get_or_create(db, user_id=user.id)
        return _to_out(user, prefs)

    @router.patch("/prefs", response_model=PrefsOut)
    def patch_prefs(
        payload: PrefsPatchIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> PrefsOut:
        if payload.display_name is not None:
            user.display_name = payload.display_name
            db.flush()
        try:
            prefs = svc.update(
                db,
                user_id=user.id,
                theme=payload.theme,
                notify_inapp=payload.notify_inapp,
                notify_email=payload.notify_email,
                display_language=payload.display_language,
                response_language=payload.response_language,
                report_language=payload.report_language,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_pref", "message": str(exc)},
            ) from exc
        return _to_out(user, prefs)

    return router
