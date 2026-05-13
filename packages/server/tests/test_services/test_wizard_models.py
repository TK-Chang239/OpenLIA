from __future__ import annotations

import pytest
from openlia_server.db.models.config import LLMModel, LLMProvider
from openlia_server.services.slot_defaults import (
    InvalidSlotError,
    get_slot_default_model_id,
)
from openlia_server.services.wizard_models import (
    RegisterModelInput,
    WizardModelsPayload,
    save_wizard_models,
)


def test_wizard_models_persists_providers_models_and_slots(db_session) -> None:
    payload = WizardModelsPayload(
        models=[
            RegisterModelInput(
                provider_kind="openai",
                api_key="k",
                base_url=None,
                env_var_name=None,
                model_ref="gpt-x",
                display_name="GPT X",
            )
        ],
        department_defaults={"secretary": "gpt-x"},
        system_role_defaults={"ai_review": "gpt-x"},
    )
    save_wizard_models(db_session, payload)

    providers = db_session.query(LLMProvider).filter_by(kind="openai").all()
    assert len(providers) == 1

    models = db_session.query(LLMModel).filter_by(model_ref="gpt-x").all()
    assert len(models) == 1

    secretary_id = get_slot_default_model_id(db_session, "department", "secretary")
    ai_review_id = get_slot_default_model_id(db_session, "system_role", "ai_review")
    assert secretary_id == models[0].id
    assert ai_review_id == models[0].id


def test_wizard_models_idempotent_on_replay(db_session) -> None:
    payload = WizardModelsPayload(
        models=[
            RegisterModelInput(
                provider_kind="anthropic",
                api_key="kk",
                base_url=None,
                env_var_name=None,
                model_ref="claude-x",
                display_name="Claude X",
            )
        ],
        department_defaults={"secretary": "claude-x"},
        system_role_defaults={},
    )
    save_wizard_models(db_session, payload)
    save_wizard_models(db_session, payload)

    providers = db_session.query(LLMProvider).filter_by(kind="anthropic").all()
    assert len(providers) == 1
    models = db_session.query(LLMModel).filter_by(model_ref="claude-x").all()
    assert len(models) == 1


def test_wizard_models_validates_unknown_department(db_session) -> None:
    payload = WizardModelsPayload(
        models=[
            RegisterModelInput(
                provider_kind="openai",
                api_key="k",
                base_url=None,
                env_var_name=None,
                model_ref="gpt-x",
                display_name="GPT X",
            )
        ],
        department_defaults={"ghost_dept": "gpt-x"},
        system_role_defaults={},
    )
    with pytest.raises(InvalidSlotError):
        save_wizard_models(db_session, payload)
