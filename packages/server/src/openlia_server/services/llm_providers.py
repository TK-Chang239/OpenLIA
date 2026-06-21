"""Service layer for LLM provider and model CRUD, API-key storage, and config overrides.

Bridges the database models in `openlia_server.db.models.config` and
`openlia_server.db.models.infrastructure` with call sites (routes, setup wizard).

API keys are stored as plaintext in the `api_key` column under the
admin-hosted single-tenant threat model (spec §3.2). Providers may also
reference an environment variable via `env_var_name` (takes precedence over the
stored value in `get_provider_api_key`).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.config import LLMModel, LLMProvider
from openlia_server.db.models.infrastructure import ConfigStore


class _Unchanged:
    """Sentinel marking a service-call argument as 'leave the field as-is'.

    Distinguishes 'caller did not pass a value' from 'caller passed None to clear'.
    """

    _instance: _Unchanged | None = None

    def __new__(cls) -> _Unchanged:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover
        return "UNCHANGED"


UNCHANGED = _Unchanged()

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProviderHasModelsError(RuntimeError):
    """Raised when attempting to delete an LLMProvider that still has LLMModel rows."""


class ModelNotFoundInDBError(LookupError):
    """Raised when a model lookup by id yields no row."""


class ProviderNotFoundError(LookupError):
    """Raised when a provider lookup by id yields no row."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ProviderCreated:
    id: str


@dataclass(slots=True)
class ModelCreated:
    id: str


# ---------------------------------------------------------------------------
# Provider CRUD
# ---------------------------------------------------------------------------


def create_provider(
    session: Session,
    *,
    kind: str,
    label: str,
    api_key: str | None = None,
    base_url: str | None = None,
    env_var_name: str | None = None,
    extra_config: dict | None = None,
    is_enabled: bool = True,
    created_by_user_id: str | None = None,
) -> ProviderCreated:
    new_id = str(uuid.uuid4())
    row = LLMProvider(
        id=new_id,
        kind=kind,
        label=label,
        api_key=api_key,
        env_var_name=env_var_name,
        base_url=base_url,
        extra_config=extra_config or None,
        is_enabled=is_enabled,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    session.flush()
    return ProviderCreated(id=new_id)


def get_provider(session: Session, provider_id: str) -> LLMProvider:
    row = session.get(LLMProvider, provider_id)
    if row is None:
        raise ProviderNotFoundError(provider_id)
    return row


def list_providers(session: Session) -> list[LLMProvider]:
    return list(session.scalars(select(LLMProvider)).all())


def update_provider(
    session: Session,
    provider_id: str,
    *,
    label: str | None | _Unchanged = UNCHANGED,
    api_key: str | None | _Unchanged = UNCHANGED,
    env_var_name: str | None | _Unchanged = UNCHANGED,
    base_url: str | None | _Unchanged = UNCHANGED,
    extra_config: dict | None | _Unchanged = UNCHANGED,
    is_enabled: bool | _Unchanged = UNCHANGED,
) -> None:
    row = get_provider(session, provider_id)
    if not isinstance(label, _Unchanged) and label is not None:
        row.label = label
    if not isinstance(api_key, _Unchanged):
        row.api_key = api_key
    if not isinstance(env_var_name, _Unchanged):
        row.env_var_name = env_var_name
    if not isinstance(base_url, _Unchanged):
        row.base_url = base_url
    if not isinstance(extra_config, _Unchanged):
        row.extra_config = extra_config
    if not isinstance(is_enabled, _Unchanged) and is_enabled is not None:
        row.is_enabled = is_enabled
    session.flush()


def delete_provider(session: Session, provider_id: str) -> None:
    row = get_provider(session, provider_id)
    model_count = session.query(LLMModel).filter_by(provider_id=provider_id).count()
    if model_count > 0:
        raise ProviderHasModelsError(
            f"Provider {provider_id!r} has {model_count} model(s); delete them first."
        )
    session.delete(row)
    session.flush()


def get_provider_api_key(session: Session, provider_id: str) -> str | None:
    """Return the API key for a provider.

    Preference order:
    1. Environment variable named by ``env_var_name`` (if set and present in env).
    2. Plaintext value from ``api_key`` column.
    """
    row = get_provider(session, provider_id)
    if row.env_var_name:
        env_val = os.environ.get(row.env_var_name)
        if env_val is not None:
            return env_val
    return row.api_key


# ---------------------------------------------------------------------------
# Model CRUD
# ---------------------------------------------------------------------------


def create_model(
    session: Session,
    *,
    provider_id: str,
    model_ref: str,
    display_name: str,
    is_enabled: bool = True,
    overrides: dict | None = None,
) -> ModelCreated:
    new_id = str(uuid.uuid4())
    row = LLMModel(
        id=new_id,
        provider_id=provider_id,
        model_ref=model_ref,
        display_name=display_name,
        is_enabled=is_enabled,
        overrides=overrides or None,
    )
    session.add(row)
    session.flush()
    return ModelCreated(id=new_id)


def get_model(session: Session, model_id: str) -> LLMModel:
    row = session.get(LLMModel, model_id)
    if row is None:
        raise ModelNotFoundInDBError(model_id)
    return row


def list_models_for_provider(session: Session, provider_id: str) -> list[LLMModel]:
    return list(session.scalars(select(LLMModel).where(LLMModel.provider_id == provider_id)).all())


def update_model(
    session: Session,
    model_id: str,
    *,
    provider_id: str | None = None,
    model_ref: str | None = None,
    display_name: str | None = None,
    is_enabled: bool | None = None,
    overrides: dict | None = None,
) -> None:
    row = get_model(session, model_id)
    if provider_id is not None:
        row.provider_id = provider_id
    if model_ref is not None:
        row.model_ref = model_ref
    if display_name is not None:
        row.display_name = display_name
    if is_enabled is not None:
        row.is_enabled = is_enabled
    if overrides is not None:
        row.overrides = overrides
    session.flush()


def delete_model(session: Session, model_id: str) -> None:
    row = get_model(session, model_id)
    session.delete(row)
    session.flush()


# ---------------------------------------------------------------------------
# ConfigStore helpers — capability overrides
# ---------------------------------------------------------------------------

_CAP_KEY_PREFIX = "llm.capability_override"


def _cap_key(provider_kind: str, model: str) -> str:
    return f"{_CAP_KEY_PREFIX}.{provider_kind}.{model}"


def _config_set(session: Session, key: str, value: object) -> None:
    row = session.get(ConfigStore, key)
    if row is None:
        row = ConfigStore(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.flush()


def _config_get(session: Session, key: str) -> object | None:
    row = session.get(ConfigStore, key)
    return row.value if row is not None else None


def _config_delete(session: Session, key: str) -> None:
    row = session.get(ConfigStore, key)
    if row is not None:
        session.delete(row)
        session.flush()


def set_capability_override(
    session: Session,
    *,
    provider_kind: str,
    model: str,
    override: dict,
) -> None:
    _config_set(session, _cap_key(provider_kind, model), override)


def get_capability_override(
    session: Session,
    *,
    provider_kind: str,
    model: str,
) -> dict | None:
    val = _config_get(session, _cap_key(provider_kind, model))
    return val if isinstance(val, dict) else None


def clear_capability_override(
    session: Session,
    *,
    provider_kind: str,
    model: str,
) -> None:
    _config_delete(session, _cap_key(provider_kind, model))
