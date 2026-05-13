from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openlia.llm.capabilities import capabilities_for
from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.types import ProviderCredentials, ResolvedModel


@dataclass(frozen=True)
class ResolvedModelRow:
    model_id: str
    model_ref: str
    overrides: dict
    provider_id: str
    provider_kind: str
    credentials: ProviderCredentials
    capability_override: dict | None


class ModelRegistry(Protocol):
    def get_by_id(self, model_id: str) -> ResolvedModelRow | None: ...

    def get_department_user_override(
        self, user_id: str, department_id: str
    ) -> ResolvedModelRow | None: ...

    def get_department_slot_default(
        self, department_id: str
    ) -> ResolvedModelRow | None: ...

    def get_system_role_default(self, role_id: str) -> ResolvedModelRow | None: ...


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
        credentials=row.credentials,
        capabilities=caps,
        overrides=row.overrides or {},
    )


def resolve(
    *,
    department_id: str,
    registry: ModelRegistry,
    user_id: str | None,
    model_id_override: str | None = None,
) -> ResolvedModel:
    """Department-scoped resolution chain:
    explicit model_id_override -> per-user-per-department pref -> admin
    slot default for the department. Raises `ModelNotConfiguredError`
    when nothing matches.
    """
    if model_id_override is not None:
        row = registry.get_by_id(model_id_override)
        if row is not None:
            return _to_resolved(row)

    if user_id is not None:
        over = registry.get_department_user_override(user_id, department_id)
        if over is not None:
            return _to_resolved(over)

    slot = registry.get_department_slot_default(department_id)
    if slot is not None:
        return _to_resolved(slot)

    raise ModelNotConfiguredError(slot_kind="department", slot_id=department_id)


def resolve_system_role(
    *, role_id: str, registry: ModelRegistry
) -> ResolvedModel:
    """System-role resolution: no user override, direct slot lookup."""
    row = registry.get_system_role_default(role_id)
    if row is None:
        raise ModelNotConfiguredError(slot_kind="system_role", slot_id=role_id)
    return _to_resolved(row)
