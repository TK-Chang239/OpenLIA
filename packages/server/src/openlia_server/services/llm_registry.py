from __future__ import annotations

import os

from openlia.llm.resolver import ModelRegistry, ResolvedModelRow
from openlia.llm.types import ModelTier, ProviderCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.config import LLMModel, LLMProvider
from openlia_server.services import llm_providers as svc


def _env_var_for_department(department_id: str) -> str:
    return f"OPENLIA_LLM_DEPARTMENT_{department_id.upper()}_TIER"


def department_tier_from_env(department_id: str) -> ModelTier | None:
    """Return the env-supplied tier override for the given department, or None."""
    raw = os.environ.get(_env_var_for_department(department_id))
    if not raw:
        return None
    try:
        return ModelTier(raw.lower())
    except ValueError:
        return None


class SQLModelRegistry(ModelRegistry):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_department_tier_override(self, department_id: str) -> ModelTier | None:
        env_override = department_tier_from_env(department_id)
        if env_override is not None:
            return env_override
        raw = svc.get_department_tier_override(self._db, department_id)
        if raw is None:
            return None
        try:
            return ModelTier(raw)
        except ValueError:
            return None

    def get_user_preference(self, user_id: str, tier: ModelTier) -> ResolvedModelRow | None:
        pref = svc.get_user_preference(self._db, user_id=user_id, tier=tier.value)
        if pref is None:
            return None
        return self._load_row(pref.model_id)

    def get_tier_default(self, tier: ModelTier) -> ResolvedModelRow | None:
        stmt = (
            select(LLMModel)
            .join(LLMProvider, LLMProvider.id == LLMModel.provider_id)
            .where(LLMModel.tier == tier.value)
            .where(LLMModel.is_tier_default.is_(True))
            .where(LLMModel.is_enabled.is_(True))
            .where(LLMProvider.is_enabled.is_(True))
            .limit(1)
        )
        model = self._db.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return self._build_row(model)

    def get_any_in_tier(self, tier: ModelTier) -> ResolvedModelRow | None:
        stmt = (
            select(LLMModel)
            .join(LLMProvider, LLMProvider.id == LLMModel.provider_id)
            .where(LLMModel.tier == tier.value)
            .where(LLMModel.is_enabled.is_(True))
            .where(LLMProvider.is_enabled.is_(True))
            .order_by(LLMModel.created_at.asc())
            .limit(1)
        )
        model = self._db.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return self._build_row(model)

    def _load_row(self, model_id: str) -> ResolvedModelRow | None:
        model = self._db.get(LLMModel, model_id)
        if model is None or not model.is_enabled:
            return None
        provider = self._db.get(LLMProvider, model.provider_id)
        if provider is None or not provider.is_enabled:
            return None
        return self._build_row(model)

    def _build_row(self, model: LLMModel) -> ResolvedModelRow:
        provider = self._db.get(LLMProvider, model.provider_id)
        if provider is None:
            raise RuntimeError(f"llm_models.{model.id} references missing provider")
        api_key = svc.get_provider_api_key(self._db, provider.id)
        override = svc.get_capability_override(
            self._db, provider_kind=provider.kind, model=model.model_ref
        )
        return ResolvedModelRow(
            model_id=model.id,
            model_ref=model.model_ref,
            tier=ModelTier(model.tier),
            overrides=model.overrides or {},
            provider_id=provider.id,
            provider_kind=provider.kind,
            credentials=ProviderCredentials(api_key=api_key, base_url=provider.base_url),
            capability_override=override,
        )
