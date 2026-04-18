"""Service layer for LLM provider and model CRUD, API-key crypto, and config overrides.

Bridges the database models in `openlia_server.db.models.config` and
`openlia_server.db.models.infrastructure` with call sites (routes, setup wizard).

Encryption: `api_key` (when provided) is AES-256-GCM encrypted via
`openlia_server.db.crypto.encrypt_for_row` with the provider row's `id` as AAD.
On read, `decrypt_for_row` is called with the same AAD. Providers may also
reference an environment variable via `env_var_name` (takes precedence over the
encrypted column in `get_provider_api_key`).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.crypto import decrypt_for_row, encrypt_for_row
from openlia_server.db.models.config import LLMModel, LLMProvider, UserLLMPreference
from openlia_server.db.models.infrastructure import ConfigStore

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
        api_key_encrypted=(
            encrypt_for_row(row_id=new_id, plaintext=api_key) if api_key is not None else None
        ),
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
    label: str | None = None,
    api_key: str | None = None,
    env_var_name: str | None = None,
    base_url: str | None = None,
    extra_config: dict | None = None,
    is_enabled: bool | None = None,
) -> None:
    row = get_provider(session, provider_id)
    if label is not None:
        row.label = label
    if api_key is not None:
        row.api_key_encrypted = encrypt_for_row(row_id=provider_id, plaintext=api_key)
    if env_var_name is not None:
        row.env_var_name = env_var_name
    if base_url is not None:
        row.base_url = base_url
    if extra_config is not None:
        row.extra_config = extra_config
    if is_enabled is not None:
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
    2. Decrypted value from ``api_key_encrypted`` column.
    """
    row = get_provider(session, provider_id)
    if row.env_var_name:
        env_val = os.environ.get(row.env_var_name)
        if env_val is not None:
            return env_val
    if row.api_key_encrypted:
        return decrypt_for_row(row_id=row.id, token=row.api_key_encrypted)
    return None


# ---------------------------------------------------------------------------
# Model CRUD
# ---------------------------------------------------------------------------


def create_model(
    session: Session,
    *,
    provider_id: str,
    tier: str,
    model_ref: str,
    display_name: str,
    is_tier_default: bool = False,
    is_enabled: bool = True,
    overrides: dict | None = None,
) -> ModelCreated:
    if is_tier_default:
        # Clear existing tier default for this tier before setting the new one.
        session.query(LLMModel).filter(
            LLMModel.tier == tier, LLMModel.is_tier_default.is_(True)
        ).update({"is_tier_default": False}, synchronize_session="fetch")

    new_id = str(uuid.uuid4())
    row = LLMModel(
        id=new_id,
        provider_id=provider_id,
        tier=tier,
        model_ref=model_ref,
        display_name=display_name,
        is_tier_default=is_tier_default,
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


def list_all_models(session: Session) -> list[LLMModel]:
    return list(session.scalars(select(LLMModel)).all())


def update_model(
    session: Session,
    model_id: str,
    *,
    display_name: str | None = None,
    is_tier_default: bool | None = None,
    is_enabled: bool | None = None,
    overrides: dict | None = None,
) -> None:
    row = get_model(session, model_id)
    if display_name is not None:
        row.display_name = display_name
    if is_tier_default is not None:
        if is_tier_default:
            session.query(LLMModel).filter(
                LLMModel.tier == row.tier,
                LLMModel.id != model_id,
                LLMModel.is_tier_default.is_(True),
            ).update({"is_tier_default": False}, synchronize_session="fetch")
        row.is_tier_default = is_tier_default
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
# User preferences
# ---------------------------------------------------------------------------


def set_user_preference(
    session: Session,
    *,
    user_id: str,
    tier: str,
    model_id: str,
) -> None:
    """Upsert a user's preferred model for a given tier."""
    row = session.get(UserLLMPreference, (user_id, tier))
    if row is None:
        row = UserLLMPreference(user_id=user_id, tier=tier, model_id=model_id)
        session.add(row)
    else:
        row.model_id = model_id
    session.flush()


def get_user_preference(session: Session, user_id: str, tier: str) -> UserLLMPreference | None:
    return session.get(UserLLMPreference, (user_id, tier))


def list_user_preferences(session: Session, user_id: str) -> list[UserLLMPreference]:
    return list(
        session.scalars(select(UserLLMPreference).where(UserLLMPreference.user_id == user_id)).all()
    )


def clear_user_preference(session: Session, user_id: str, tier: str) -> None:
    row = session.get(UserLLMPreference, (user_id, tier))
    if row is not None:
        session.delete(row)
        session.flush()


# ---------------------------------------------------------------------------
# ConfigStore helpers — capability overrides
# ---------------------------------------------------------------------------

_CAP_KEY_PREFIX = "llm.capability_override"
_DEPT_KEY_PREFIX = "llm.department"


def _cap_key(provider_kind: str, model: str) -> str:
    return f"{_CAP_KEY_PREFIX}.{provider_kind}.{model}"


def _dept_key(department: str) -> str:
    return f"{_DEPT_KEY_PREFIX}.{department}.tier"


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


def set_department_tier_override(session: Session, department: str, tier: str) -> None:
    _config_set(session, _dept_key(department), tier)


def get_department_tier_override(session: Session, department: str) -> str | None:
    val = _config_get(session, _dept_key(department))
    return val if isinstance(val, str) else None


def clear_department_tier_override(session: Session, department: str) -> None:
    _config_delete(session, _dept_key(department))
