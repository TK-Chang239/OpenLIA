from __future__ import annotations

import pytest
from openlia_server.db.models.config import LLMProvider
from openlia_server.services import llm_providers as svc


def test_create_provider_stores_plaintext_api_key(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="Main OpenAI",
        api_key="sk-plain-xyz",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    row = db_session.get(LLMProvider, created.id)
    assert row is not None
    assert row.api_key == "sk-plain-xyz"


def test_create_provider_with_env_var_only(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="via env",
        api_key=None,
        base_url=None,
        env_var_name="MY_OPENAI_KEY",
        extra_config=None,
    )
    row = db_session.get(LLMProvider, created.id)
    assert row.api_key is None
    assert row.env_var_name == "MY_OPENAI_KEY"


def test_get_provider_api_key_prefers_env(db_session, monkeypatch) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="hybrid",
        api_key="sk-db",
        base_url=None,
        env_var_name="OPENLIA_TEST_KEY",
        extra_config=None,
    )
    monkeypatch.setenv("OPENLIA_TEST_KEY", "sk-env")
    key = svc.get_provider_api_key(db_session, created.id)
    assert key == "sk-env"


def test_get_provider_api_key_falls_back_to_stored(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="db only",
        api_key="sk-db",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    key = svc.get_provider_api_key(db_session, created.id)
    assert key == "sk-db"


def test_update_provider_overwrites_api_key(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="old",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.update_provider(db_session, created.id, api_key="new")
    assert svc.get_provider_api_key(db_session, created.id) == "new"


def test_delete_provider_blocks_when_models_exist(db_session) -> None:
    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=provider.id,
        model_ref="gpt-5.4-pro",
        display_name="GPT 5.4 Pro",
    )
    with pytest.raises(svc.ProviderHasModelsError):
        svc.delete_provider(db_session, provider.id)


def test_resolve_provider_api_key_matches_model_under_kind(db_session) -> None:
    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="Main OpenAI",
        api_key="sk-db",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=provider.id,
        model_ref="gpt-5.5",
        display_name="GPT 5.5",
    )
    db_session.commit()
    key = svc.resolve_provider_api_key(db_session, provider_kind="openai", model="gpt-5.5")
    assert key == "sk-db"


def test_resolve_provider_api_key_none_when_no_provider(db_session) -> None:
    assert svc.resolve_provider_api_key(db_session, provider_kind="openai", model="gpt-5.5") is None


def test_capability_override_roundtrip(db_session) -> None:
    svc.set_capability_override(
        db_session,
        provider_kind="anthropic",
        model="claude-opus-4-6",
        override={"tool_calling": False},
    )
    got = svc.get_capability_override(
        db_session, provider_kind="anthropic", model="claude-opus-4-6"
    )
    assert got == {"tool_calling": False}
    svc.clear_capability_override(db_session, provider_kind="anthropic", model="claude-opus-4-6")
    assert (
        svc.get_capability_override(db_session, provider_kind="anthropic", model="claude-opus-4-6")
        is None
    )


def test_update_provider_clears_api_key_with_explicit_none(db_session) -> None:
    p = svc.create_provider(db_session, kind="openai", label="OAI", api_key="sk-real")
    db_session.commit()
    assert db_session.get(LLMProvider, p.id).api_key is not None

    svc.update_provider(db_session, p.id, api_key=None)
    db_session.commit()

    assert db_session.get(LLMProvider, p.id).api_key is None


def test_update_provider_clears_env_var_name_with_explicit_none(db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="OAI",
        env_var_name="OPENLIA_OPENAI_KEY",
    )
    db_session.commit()
    assert db_session.get(LLMProvider, p.id).env_var_name == "OPENLIA_OPENAI_KEY"

    svc.update_provider(db_session, p.id, env_var_name=None)
    db_session.commit()
    assert db_session.get(LLMProvider, p.id).env_var_name is None


def test_update_provider_unchanged_keeps_existing_values(db_session) -> None:
    p = svc.create_provider(db_session, kind="openai", label="OAI", api_key="sk-real")
    db_session.commit()
    svc.update_provider(db_session, p.id, label="Renamed")
    db_session.commit()

    row = db_session.get(LLMProvider, p.id)
    assert row.label == "Renamed"
    assert row.api_key == "sk-real"
