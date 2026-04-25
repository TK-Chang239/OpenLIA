"""Routes for per-user LLM tier preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.config import LLMModel, UserLLMPreference
from openlia_server.middleware.auth import build_require_active_user


class PreferenceIn(BaseModel):
    tier: str = Field(pattern=r"^(thinking|everyday|quick)$")
    model_id: str


class PreferenceListOut(BaseModel):
    preferences: dict[str, str]


def build_settings_models_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/settings/admin/llm", tags=["settings"])
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/preferences", response_model=PreferenceListOut)
    def list_preferences(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> PreferenceListOut:
        rows = db.query(UserLLMPreference).filter_by(user_id=user.id).all()
        return PreferenceListOut(preferences={row.tier: row.model_id for row in rows})

    @router.put("/preferences")
    def put_preference(
        payload: PreferenceIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        model = db.query(LLMModel).filter_by(id=payload.model_id).first()
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "model_not_found", "message": "Model id not in roster."},
            )
        if model.tier != payload.tier:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "tier_mismatch",
                    "message": f"Model is tier {model.tier}, not {payload.tier}.",
                },
            )
        existing = (
            db.query(UserLLMPreference).filter_by(user_id=user.id, tier=payload.tier).one_or_none()
        )
        if existing is None:
            db.add(UserLLMPreference(user_id=user.id, tier=payload.tier, model_id=payload.model_id))
        else:
            existing.model_id = payload.model_id
        db.flush()
        return {"ok": True}

    @router.delete("/preferences/{tier}")
    def delete_preference(
        tier: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        db.query(UserLLMPreference).filter_by(user_id=user.id, tier=tier).delete()
        db.flush()
        return {"ok": True}

    return router
