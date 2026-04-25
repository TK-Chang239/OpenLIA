"""User-facing LLM model routes mounted at /settings/models.

Surface (per llm-provider-design.md §API Surface — User-facing):
    GET    /settings/models                    -> tier roster
    GET    /settings/models/preferences        -> current user's tier preferences
    PUT    /settings/models/preferences/{tier} -> set preference
    DELETE /settings/models/preferences/{tier} -> clear preference
    GET    /settings/models/effective/{department_id} -> resolved model for current user
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.resolver import resolve as resolve_model
from openlia.llm.types import ModelTier
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.config import LLMModel, LLMProvider, UserLLMPreference
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services.llm_registry import SQLModelRegistry

_TIERS = ("thinking", "everyday", "quick")


class _ModelEntry(BaseModel):
    id: str
    model_ref: str
    display_name: str
    provider_id: str
    provider_kind: str
    is_tier_default: bool
    is_enabled: bool


class _RosterOut(BaseModel):
    thinking: list[_ModelEntry]
    everyday: list[_ModelEntry]
    quick: list[_ModelEntry]


class _PreferencesOut(BaseModel):
    preferences: dict[str, str]


class _PreferenceIn(BaseModel):
    model_id: str


class _EffectiveOut(BaseModel):
    model_ref: str
    provider_kind: str
    tier: str
    model_id: str
    provider_id: str


def build_llm_user_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/settings/models", tags=["settings"])
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("", response_model=_RosterOut)
    def get_roster(
        db: Session = Depends(session_dep),
        _: User = require_auth,
    ) -> _RosterOut:
        models = (
            db.query(LLMModel, LLMProvider)
            .join(LLMProvider, LLMProvider.id == LLMModel.provider_id)
            .all()
        )
        buckets: dict[str, list[_ModelEntry]] = {t: [] for t in _TIERS}
        for model, provider in models:
            if model.tier not in buckets:
                continue
            buckets[model.tier].append(
                _ModelEntry(
                    id=model.id,
                    model_ref=model.model_ref,
                    display_name=model.display_name,
                    provider_id=provider.id,
                    provider_kind=provider.kind,
                    is_tier_default=bool(model.is_tier_default),
                    is_enabled=bool(model.is_enabled and provider.is_enabled),
                )
            )
        return _RosterOut(
            thinking=buckets["thinking"],
            everyday=buckets["everyday"],
            quick=buckets["quick"],
        )

    @router.get("/preferences", response_model=_PreferencesOut)
    def list_preferences(
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> _PreferencesOut:
        rows = db.query(UserLLMPreference).filter_by(user_id=user.id).all()
        return _PreferencesOut(preferences={row.tier: row.model_id for row in rows})

    @router.put("/preferences/{tier}")
    def put_preference(
        tier: str,
        payload: _PreferenceIn,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        if tier not in _TIERS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_tier", "message": f"Unknown tier {tier!r}"},
            )
        model = db.query(LLMModel).filter_by(id=payload.model_id).first()
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "model_not_found", "message": "Model id not in roster."},
            )
        if not model.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "model_disabled", "message": "Model is disabled."},
            )
        if model.tier != tier:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "tier_mismatch",
                    "message": f"Model is tier {model.tier}, not {tier}.",
                },
            )
        existing = (
            db.query(UserLLMPreference).filter_by(user_id=user.id, tier=tier).one_or_none()
        )
        if existing is None:
            db.add(UserLLMPreference(user_id=user.id, tier=tier, model_id=payload.model_id))
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

    @router.get("/effective/{department_id}", response_model=_EffectiveOut)
    def get_effective(
        department_id: str,
        db: Session = Depends(session_dep),
        user: User = require_auth,
    ) -> _EffectiveOut:
        registry = SQLModelRegistry(db)
        try:
            resolved = resolve_model(
                department_id=department_id,
                registry=registry,
                user_id=user.id,
            )
        except TierNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "tier_not_configured", "message": str(exc)},
            ) from exc
        tier_value = (
            resolved.tier.value if isinstance(resolved.tier, ModelTier) else str(resolved.tier)
        )
        return _EffectiveOut(
            model_ref=resolved.model_ref,
            provider_kind=resolved.provider_kind,
            tier=tier_value,
            model_id=resolved.model_id,
            provider_id=resolved.provider_id,
        )

    return router
