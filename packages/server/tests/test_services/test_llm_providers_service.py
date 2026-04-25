from __future__ import annotations

import pytest
from openlia_server.db.models.config import LLMModel, LLMProvider, UserLLMPreference
from openlia_server.services import llm_providers as svc


@pytest.fixture
def _env_secret(monkeypatch):
    key = "0" * 43 + "="  # 32-byte base64
    monkeypatch.setenv("OPENLIA_SECRET_KEY", key)


def test_create_provider_encrypts_api_key(_env_secret, db_session) -> None:
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
    assert row.api_key_encrypted is not None
    assert "sk-plain-xyz" not in row.api_key_encrypted


def test_create_provider_with_env_var_does_not_encrypt(_env_secret, db_session) -> None:
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
    assert row.api_key_encrypted is None
    assert row.env_var_name == "MY_OPENAI_KEY"


def test_get_provider_api_key_prefers_env(_env_secret, db_session, monkeypatch) -> None:
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


def test_get_provider_api_key_falls_back_to_decrypted(_env_secret, db_session) -> None:
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


def test_update_provider_rewrites_encryption_when_api_key_changes(_env_secret, db_session) -> None:
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


def test_delete_provider_blocks_when_models_exist(_env_secret, db_session) -> None:
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
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="GPT 5.4 Pro",
        is_tier_default=True,
    )
    with pytest.raises(svc.ProviderHasModelsError):
        svc.delete_provider(db_session, provider.id)


def test_create_model_enforces_single_tier_default(_env_secret, db_session) -> None:
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
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="Pro",
        is_tier_default=True,
    )
    svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="thinking",
        model_ref="gpt-other",
        display_name="Other",
        is_tier_default=True,
    )
    defaults = [
        m
        for m in db_session.query(LLMModel).filter(LLMModel.tier == "thinking").all()
        if m.is_tier_default
    ]
    assert len(defaults) == 1
    assert defaults[0].model_ref == "gpt-other"


def test_set_user_preference_upserts(_env_secret, db_session) -> None:
    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    model = svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="everyday",
        model_ref="gpt-5.4",
        display_name="GPT",
        is_tier_default=True,
    )
    svc.set_user_preference(db_session, user_id="u-1", tier="everyday", model_id=model.id)
    row = db_session.query(UserLLMPreference).filter_by(user_id="u-1", tier="everyday").one()
    assert row.model_id == model.id
    model2 = svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="everyday",
        model_ref="gpt-other",
        display_name="Other",
        is_tier_default=False,
    )
    svc.set_user_preference(db_session, user_id="u-1", tier="everyday", model_id=model2.id)
    rows = db_session.query(UserLLMPreference).filter_by(user_id="u-1", tier="everyday").all()
    assert len(rows) == 1
    assert rows[0].model_id == model2.id


def test_capability_override_roundtrip(_env_secret, db_session) -> None:
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


def test_department_tier_override_roundtrip(_env_secret, db_session) -> None:
    svc.set_department_tier_override(db_session, "equity_research", "quick")
    assert svc.get_department_tier_override(db_session, "equity_research") == "quick"
    svc.clear_department_tier_override(db_session, "equity_research")
    assert svc.get_department_tier_override(db_session, "equity_research") is None


def test_decrypt_failure_raises_auth_error(_env_secret, db_session) -> None:
    """NEW-4-26: DecryptError on decrypt_for_row -> AuthError, not 500."""
    from openlia.llm.exceptions import AuthError

    p = svc.create_provider(db_session, kind="openai", label="OAI", api_key="sk-real")
    db_session.commit()

    row = db_session.get(LLMProvider, p.id)
    assert row.api_key_encrypted is not None
    row.api_key_encrypted = "corrupted-base64"
    db_session.commit()

    try:
        svc.get_provider_api_key(db_session, p.id)
        raise AssertionError("expected AuthError")
    except AuthError:
        pass


def test_update_provider_clears_api_key_with_explicit_none(_env_secret, db_session) -> None:
    """NEW-4-34: update_provider(api_key=None) clears the encrypted column."""
    p = svc.create_provider(db_session, kind="openai", label="OAI", api_key="sk-real")
    db_session.commit()
    assert db_session.get(LLMProvider, p.id).api_key_encrypted is not None

    svc.update_provider(db_session, p.id, api_key=None)
    db_session.commit()

    assert db_session.get(LLMProvider, p.id).api_key_encrypted is None


def test_update_provider_clears_env_var_name_with_explicit_none(
    _env_secret, db_session
) -> None:
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


def test_update_provider_unchanged_keeps_existing_values(_env_secret, db_session) -> None:
    p = svc.create_provider(
        db_session, kind="openai", label="OAI", api_key="sk-real"
    )
    db_session.commit()
    svc.update_provider(db_session, p.id, label="Renamed")
    db_session.commit()

    row = db_session.get(LLMProvider, p.id)
    assert row.label == "Renamed"
    assert row.api_key_encrypted is not None  # api_key was UNCHANGED
