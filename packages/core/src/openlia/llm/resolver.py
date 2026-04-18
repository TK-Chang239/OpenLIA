from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openlia.llm.capabilities import capabilities_for
from openlia.llm.department_defaults import DEPARTMENT_DEFAULT_TIERS
from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.types import (
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
)


@dataclass(frozen=True)
class ResolvedModelRow:
    model_id: str
    model_ref: str
    tier: ModelTier
    overrides: dict

    provider_id: str
    provider_kind: str
    credentials: ProviderCredentials

    capability_override: dict | None


class ModelRegistry(Protocol):
    def get_department_tier_override(self, department_id: str) -> ModelTier | None: ...

    def get_user_preference(self, user_id: str, tier: ModelTier) -> ResolvedModelRow | None: ...

    def get_tier_default(self, tier: ModelTier) -> ResolvedModelRow | None: ...

    def get_any_in_tier(self, tier: ModelTier) -> ResolvedModelRow | None: ...


def resolve_tier(
    department_id: str,
    tier_override: ModelTier | None,
    registry: ModelRegistry,
) -> ModelTier:
    if tier_override is not None:
        return tier_override
    dept_override = registry.get_department_tier_override(department_id)
    if dept_override is not None:
        return dept_override
    return DEPARTMENT_DEFAULT_TIERS.get(department_id, ModelTier.EVERYDAY)


def _to_resolved(row: ResolvedModelRow) -> ResolvedModel:
    caps = capabilities_for(
        provider_kind=row.provider_kind,
        model=row.model_ref,
        override=row.capability_override,
    )
    return ResolvedModel(
        provider_kind=row.provider_kind,
        provider_id=row.provider_id,
        model_id=row.model_id,
        model_ref=row.model_ref,
        tier=row.tier,
        credentials=row.credentials,
        capabilities=caps,
        overrides=row.overrides or {},
    )


def resolve(
    *,
    department_id: str,
    registry: ModelRegistry,
    user_id: str | None,
    tier_override: ModelTier | None = None,
) -> ResolvedModel:
    tier = resolve_tier(department_id, tier_override, registry)

    if user_id is not None:
        pref = registry.get_user_preference(user_id, tier)
        if pref is not None:
            return _to_resolved(pref)

    tier_default = registry.get_tier_default(tier)
    if tier_default is not None:
        return _to_resolved(tier_default)

    any_row = registry.get_any_in_tier(tier)
    if any_row is not None:
        return _to_resolved(any_row)

    raise TierNotConfiguredError(tier.value)
