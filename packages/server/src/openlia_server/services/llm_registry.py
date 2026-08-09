from __future__ import annotations

from openlia.llm.resolver import ModelRegistry, ResolvedModelRow
from openlia.llm.types import ProviderCredentials
from sqlalchemy.orm import Session

from openlia_server.db.models.config import LLMModel, LLMProvider, LLMSlotDefault
from openlia_server.services import llm_providers as svc


class SQLModelRegistry(ModelRegistry):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, model_id: str) -> ResolvedModelRow | None:
        return self._load_row(model_id)

    def get_department_user_override(
        self, user_id: str, department_id: str
    ) -> ResolvedModelRow | None:
        from openlia_server.db.models.config import UserDepartmentModelPref

        pref = self._db.get(UserDepartmentModelPref, (user_id, department_id))
        if pref is None:
            return None
        return self._load_row(pref.model_id)

    def get_department_slot_default(self, department_id: str) -> ResolvedModelRow | None:
        row = self._db.get(LLMSlotDefault, ("department", department_id))
        if row is None:
            return None
        return self._load_row(row.model_id)

    def get_user_preferred_model(self, user_id: str) -> ResolvedModelRow | None:
        from openlia_server.db.models.config import UserPrefs

        prefs = self._db.get(UserPrefs, user_id)
        if prefs is None or prefs.preferred_model_id is None:
            return None
        return self._load_row(prefs.preferred_model_id)

    def get_system_role_default(self, role_id: str) -> ResolvedModelRow | None:
        row = self._db.get(LLMSlotDefault, ("system_role", role_id))
        if row is None:
            return None
        return self._load_row(row.model_id)

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
            overrides=model.overrides or {},
            provider_id=provider.id,
            provider_kind=provider.kind,
            credentials=ProviderCredentials(api_key=api_key, base_url=provider.base_url),
            capability_override=override,
        )
