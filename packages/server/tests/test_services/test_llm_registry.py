from __future__ import annotations

import pytest
from openlia.llm.resolver import resolve
from openlia.llm.types import ModelTier
from openlia_server.services import llm_providers as svc
from openlia_server.services.llm_registry import SQLModelRegistry


@pytest.fixture
def _env_secret(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")


def _seed_openai(db_session) -> tuple[str, str]:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    m = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="Pro",
        is_tier_default=True,
    )
    return p.id, m.id


def test_get_user_preference_joins_provider_and_decrypts(
    _env_secret, db_session, make_user
) -> None:
    user = make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    _, model_id = _seed_openai(db_session)
    svc.set_user_preference(db_session, user_id=user.id, tier="thinking", model_id=model_id)
    reg = SQLModelRegistry(db_session)
    row = reg.get_user_preference(user.id, ModelTier.THINKING)
    assert row is not None
    assert row.provider_kind == "openai"
    assert row.model_ref == "gpt-5.4-pro"
    assert row.credentials.api_key == "sk-test"


def test_get_tier_default_returns_the_flagged_model(_env_secret, db_session) -> None:
    _seed_openai(db_session)
    reg = SQLModelRegistry(db_session)
    row = reg.get_tier_default(ModelTier.THINKING)
    assert row is not None
    assert row.model_ref == "gpt-5.4-pro"


def test_get_tier_default_none_when_absent(_env_secret, db_session) -> None:
    reg = SQLModelRegistry(db_session)
    assert reg.get_tier_default(ModelTier.QUICK) is None


def test_get_any_in_tier_returns_oldest_created(_env_secret, db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    first = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="first",
        display_name="First",
        is_tier_default=False,
    )
    svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="second",
        display_name="Second",
        is_tier_default=False,
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_any_in_tier(ModelTier.QUICK)
    assert row is not None
    assert row.model_id == first.id


def test_get_any_in_tier_skips_disabled(_env_secret, db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    disabled = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="off",
        display_name="Off",
        is_tier_default=False,
    )
    svc.update_model(db_session, disabled.id, is_enabled=False)
    enabled = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="on",
        display_name="On",
        is_tier_default=False,
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_any_in_tier(ModelTier.QUICK)
    assert row is not None
    assert row.model_id == enabled.id


def test_get_department_tier_override_reads_config_store(_env_secret, db_session) -> None:
    svc.set_department_tier_override(db_session, "equity_research", "quick")
    reg = SQLModelRegistry(db_session)
    assert reg.get_department_tier_override("equity_research") is ModelTier.QUICK


def test_resolve_end_to_end_through_sql_registry(_env_secret, db_session) -> None:
    _seed_openai(db_session)
    reg = SQLModelRegistry(db_session)
    resolved = resolve(
        department_id="equity_research",  # shipped default is THINKING
        registry=reg,
        user_id=None,
    )
    assert resolved.provider_kind == "openai"
    assert resolved.tier is ModelTier.THINKING
    assert resolved.credentials.api_key == "sk-test"


def test_capability_override_is_applied_via_resolver(_env_secret, db_session) -> None:
    _seed_openai(db_session)
    svc.set_capability_override(
        db_session,
        provider_kind="openai",
        model="gpt-5.4-pro",
        override={"tool_calling": False},
    )
    reg = SQLModelRegistry(db_session)
    resolved = resolve(department_id="equity_research", registry=reg, user_id=None)
    assert resolved.capabilities.tool_calling is False


def test_get_tier_default_skips_disabled_provider(_env_secret, db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=p.id,
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="Pro",
        is_tier_default=True,
    )
    svc.update_provider(db_session, p.id, is_enabled=False)
    reg = SQLModelRegistry(db_session)
    assert reg.get_tier_default(ModelTier.THINKING) is None


def test_get_any_in_tier_skips_disabled_provider(_env_secret, db_session) -> None:
    p1 = svc.create_provider(
        db_session,
        kind="openai",
        label="p1",
        api_key="k1",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=p1.id,
        tier="quick",
        model_ref="fast-1",
        display_name="Fast1",
        is_tier_default=False,
    )
    svc.update_provider(db_session, p1.id, is_enabled=False)

    p2 = svc.create_provider(
        db_session,
        kind="anthropic",
        label="p2",
        api_key="k2",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    enabled = svc.create_model(
        db_session,
        provider_id=p2.id,
        tier="quick",
        model_ref="fast-2",
        display_name="Fast2",
        is_tier_default=False,
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_any_in_tier(ModelTier.QUICK)
    assert row is not None
    assert row.model_id == enabled.id


def test_user_preference_with_disabled_provider_returns_none(
    _env_secret, db_session, make_user
) -> None:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    m = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="Pro",
        is_tier_default=True,
    )
    user = make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    svc.set_user_preference(db_session, user_id=user.id, tier="thinking", model_id=m.id)
    svc.update_provider(db_session, p.id, is_enabled=False)
    reg = SQLModelRegistry(db_session)
    assert reg.get_user_preference(user.id, ModelTier.THINKING) is None


def test_resolve_raises_tier_not_configured_when_all_disabled(_env_secret, db_session) -> None:
    from openlia.llm.exceptions import TierNotConfiguredError
    from openlia.llm.resolver import resolve

    p = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    m = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="Pro",
        is_tier_default=True,
    )
    svc.update_model(db_session, m.id, is_enabled=False)
    reg = SQLModelRegistry(db_session)
    with pytest.raises(TierNotConfiguredError):
        resolve(department_id="equity_research", registry=reg, user_id=None)
