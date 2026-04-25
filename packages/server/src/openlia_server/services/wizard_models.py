"""Setup-wizard Step 3 (Models) helpers.

Wraps `services.llm_providers` so /setup/models can:
  - upsert provider rows + tiered models in one shot;
  - replace prior wizard-staged models on a second POST (idempotent);
  - leave tier-default uniqueness intact via the existing
    `uq_llm_models_tier_default` constraint.

A "wizard-staged" model is any LLMModel created before the wizard's
`wizard.completed` config flag flips true. We use that as the deletion
filter — once the wizard is done, this code never runs again because the
410-gate above the route blocks it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from openlia_server.db.models.config import LLMModel, LLMProvider
from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.services import llm_providers as llm_svc


def _is_wizard_completed(db: Session) -> bool:
    row = db.get(ConfigStore, "wizard.completed")
    if row is None:
        return False
    v = row.value
    if isinstance(v, bool):
        return v
    return (v or "").lower() == "true"


def _wipe_existing_models_and_providers(db: Session) -> None:
    """Idempotency: clear all LLM models + providers before re-staging.

    Called only when the wizard is still in progress. Once the wizard is
    completed, the 410 gate prevents this code path entirely.
    """
    db.query(LLMModel).delete()
    db.flush()
    db.query(LLMProvider).delete()
    db.flush()


_KNOWN_LLM_KINDS = {"openai", "anthropic", "gemini", "openrouter", "openai_compat", "ollama"}


class UnknownLLMKindError(ValueError):
    """Raised when a wizard payload references an unknown LLM provider kind."""


def save_models(db: Session, payload: Any) -> dict[str, bool]:
    """Persist tiered models for the wizard.

    `payload` is a Pydantic model with `.thinking`, `.everyday`, `.quick`
    lists of entries; each entry has `provider`, `model`, `api_key`,
    `base_url`, `env_var_name`, `capabilities`, `is_tier_default`.

    Idempotent — a second POST replaces any wizard-staged providers/models.
    Refuses to delete anything if the wizard has already completed.
    """
    if _is_wizard_completed(db):
        # Caller (route) is already 410-gated; this is defensive.
        raise RuntimeError("wizard already completed; refusing to mutate llm models")

    # Validate kinds up-front so a partial write doesn't end with a half-staged DB.
    for tier_name in ("thinking", "everyday", "quick"):
        for entry in getattr(payload, tier_name):
            if entry.provider not in _KNOWN_LLM_KINDS:
                raise UnknownLLMKindError(
                    f"unknown LLM provider kind {entry.provider!r}; "
                    f"known: {sorted(_KNOWN_LLM_KINDS)}"
                )

    _wipe_existing_models_and_providers(db)

    for tier_name in ("thinking", "everyday", "quick"):
        entries = getattr(payload, tier_name)
        for entry in entries:
            created = llm_svc.create_provider(
                db,
                kind=entry.provider,
                label=f"{entry.provider} ({tier_name})",
                api_key=entry.api_key,
                base_url=entry.base_url,
                env_var_name=entry.env_var_name,
            )
            llm_svc.create_model(
                db,
                provider_id=created.id,
                tier=tier_name,
                model_ref=entry.model,
                display_name=entry.model,
                is_tier_default=bool(entry.is_tier_default),
            )
            if entry.provider == "openai_compat" and entry.capabilities:
                llm_svc.set_capability_override(
                    db,
                    provider_kind="openai_compat",
                    model=entry.model,
                    override=entry.capabilities,
                )
    return {"ok": True}
