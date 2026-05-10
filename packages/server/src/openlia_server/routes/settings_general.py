"""Routes for GET/PATCH /settings/prefs — display name, notifications, theme, language."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import user_prefs as svc

_UNSET = "__unset__"


class PrefsOut(BaseModel):
    display_name: str
    theme: str
    notify_inapp: bool
    notify_email: bool
    display_language: str
    response_language: str
    report_language: str
    preferred_model_id: str | None = None
    timezone: str
    timezone_source: str
    graph_extraction_time: str


class TimezoneIn(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)
    source: str = Field(pattern=r"^(auto|manual)$")


class GraphExtractionTimeIn(BaseModel):
    time: str = Field(min_length=1, max_length=5)


class PrefsPatchIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    theme: str | None = Field(default=None, pattern=r"^(system|light|dark)$")
    notify_inapp: bool | None = None
    notify_email: bool | None = None
    display_language: str | None = Field(default=None, pattern=r"^(en|zh-TW)$")
    response_language: str | None = Field(default=None, pattern=r"^(en|zh-TW)$")
    report_language: str | None = Field(default=None, pattern=r"^(en|zh-TW|both)$")
    # Sentinel default so we can distinguish "not sent" from "sent as null"
    # (null clears the global model preference).
    preferred_model_id: str | None = Field(default=_UNSET)  # type: ignore[arg-type]


def _to_out(user: User, prefs) -> PrefsOut:
    return PrefsOut(
        display_name=user.display_name,
        theme=prefs.theme,
        notify_inapp=prefs.notify_inapp,
        notify_email=prefs.notify_email,
        display_language=prefs.display_language,
        response_language=prefs.response_language,
        report_language=prefs.report_language,
        preferred_model_id=prefs.preferred_model_id,
        timezone=prefs.timezone,
        timezone_source=prefs.timezone_source,
        graph_extraction_time=prefs.graph_extraction_time,
    )


def build_settings_general_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
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
        update_kwargs: dict[str, object] = dict(
            user_id=user.id,
            theme=payload.theme,
            notify_inapp=payload.notify_inapp,
            notify_email=payload.notify_email,
            display_language=payload.display_language,
            response_language=payload.response_language,
            report_language=payload.report_language,
        )
        if payload.preferred_model_id != _UNSET:
            if payload.preferred_model_id is not None:
                from openlia_server.db.models.config import LLMModel

                model = db.get(LLMModel, payload.preferred_model_id)
                if model is None or not model.is_enabled:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={
                            "code": "model_not_found",
                            "message": "Model id not in roster.",
                        },
                    )
            update_kwargs["preferred_model_id"] = payload.preferred_model_id
        try:
            prefs = svc.update(db, **update_kwargs)  # type: ignore[arg-type]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_pref", "message": str(exc)},
            ) from exc
        return _to_out(user, prefs)

    @router.put("/timezone", response_model=PrefsOut)
    def put_timezone(
        payload: TimezoneIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> PrefsOut:
        try:
            prefs = svc.set_timezone(
                db,
                user_id=user.id,
                timezone=payload.timezone,
                source=payload.source,  # type: ignore[arg-type]
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_pref", "message": str(exc)},
            ) from exc
        return _to_out(user, prefs)

    @router.put("/graph-extraction-time", response_model=PrefsOut)
    def put_graph_extraction_time(
        payload: GraphExtractionTimeIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> PrefsOut:
        try:
            prefs = svc.set_graph_extraction_time(
                db, user_id=user.id, time=payload.time
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_pref", "message": str(exc)},
            ) from exc
        return _to_out(user, prefs)

    return router
