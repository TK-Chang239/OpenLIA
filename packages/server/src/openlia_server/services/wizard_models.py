"""Setup-wizard Step 3 (Models) helpers.

Persists the wizard's models step under the slot-defaults model:
  - Upsert one LLMProvider per (kind, api_key, base_url, env_var_name).
  - Upsert one LLMModel per (provider_id, model_ref).
  - Write department + system-role slot defaults.

Idempotent on replay — re-POSTing the same payload upserts in place
instead of duplicating rows.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.models.config import LLMModel, LLMProvider
from openlia_server.services.slot_defaults import set_slot_default


class RegisterModelInput(BaseModel):
    provider_kind: str
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None
    model_ref: str
    display_name: str


class WizardModelsPayload(BaseModel):
    models: list[RegisterModelInput]
    department_defaults: dict[str, str]  # dept_id -> model_ref
    system_role_defaults: dict[str, str]  # role_id -> model_ref


class UnknownModelRefError(ValueError):
    """Raised when a slot default points at a model_ref not in `models`."""


def _upsert_provider(db: Session, entry: RegisterModelInput) -> LLMProvider:
    row = (
        db.query(LLMProvider)
        .filter(
            LLMProvider.kind == entry.provider_kind,
            LLMProvider.api_key.is_(entry.api_key)
            if entry.api_key is None
            else LLMProvider.api_key == entry.api_key,
            LLMProvider.base_url.is_(entry.base_url)
            if entry.base_url is None
            else LLMProvider.base_url == entry.base_url,
            LLMProvider.env_var_name.is_(entry.env_var_name)
            if entry.env_var_name is None
            else LLMProvider.env_var_name == entry.env_var_name,
        )
        .one_or_none()
    )
    if row is not None:
        return row
    hint = entry.api_key[:4] + "..." if entry.api_key else entry.env_var_name or "no-key"
    row = LLMProvider(
        id=str(uuid.uuid4()),
        kind=entry.provider_kind,
        label=f"{entry.provider_kind} ({hint})",
        api_key=entry.api_key,
        base_url=entry.base_url,
        env_var_name=entry.env_var_name,
        is_enabled=True,
    )
    db.add(row)
    db.flush()
    return row


def _upsert_model(db: Session, provider_id: str, entry: RegisterModelInput) -> LLMModel:
    row = (
        db.query(LLMModel)
        .filter(LLMModel.provider_id == provider_id, LLMModel.model_ref == entry.model_ref)
        .one_or_none()
    )
    if row is not None:
        if row.display_name != entry.display_name:
            row.display_name = entry.display_name
            db.flush()
        return row
    row = LLMModel(
        id=str(uuid.uuid4()),
        provider_id=provider_id,
        model_ref=entry.model_ref,
        display_name=entry.display_name,
        is_enabled=True,
    )
    db.add(row)
    db.flush()
    return row


def save_wizard_models(db: Session, payload: WizardModelsPayload) -> None:
    """Persist the wizard's models step.

    - Upsert one LLMProvider per (provider_kind, api_key, base_url, env_var_name).
    - Upsert one LLMModel per (provider, model_ref) with display_name.
    - For each department_defaults entry, set slot_default('department', dept_id, model_id).
    - For each system_role_defaults entry, set slot_default('system_role', role_id, model_id).
    """
    ref_to_model_id: dict[str, str] = {}
    for entry in payload.models:
        provider = _upsert_provider(db, entry)
        model = _upsert_model(db, provider.id, entry)
        ref_to_model_id[entry.model_ref] = model.id

    for dept_id, model_ref in payload.department_defaults.items():
        model_id = ref_to_model_id.get(model_ref)
        if model_id is None:
            raise UnknownModelRefError(
                f"department_defaults references unknown model_ref {model_ref!r}"
            )
        set_slot_default(db, slot_kind="department", slot_id=dept_id, model_id=model_id)

    for role_id, model_ref in payload.system_role_defaults.items():
        model_id = ref_to_model_id.get(model_ref)
        if model_id is None:
            raise UnknownModelRefError(
                f"system_role_defaults references unknown model_ref {model_ref!r}"
            )
        set_slot_default(db, slot_kind="system_role", slot_id=role_id, model_id=model_id)
