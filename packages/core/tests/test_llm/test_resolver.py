from __future__ import annotations

from dataclasses import dataclass

import pytest
from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.resolver import (
    ResolvedModelRow,
    resolve,
    resolve_tier,
)
from openlia.llm.types import (
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
)


@dataclass
class _FakeRegistry:
    dept_tier_override: ModelTier | None = None
    user_pref: dict[tuple[str, ModelTier], ResolvedModelRow] | None = None
    tier_default: dict[ModelTier, ResolvedModelRow] | None = None
    any_in_tier: dict[ModelTier, ResolvedModelRow] | None = None
    by_id: dict[str, ResolvedModelRow] | None = None
    user_preferred: dict[str, ResolvedModelRow] | None = None

    def get_department_tier_override(self, department_id: str) -> ModelTier | None:
        return self.dept_tier_override

    def get_user_preference(self, user_id: str, tier: ModelTier) -> ResolvedModelRow | None:
        if not self.user_pref:
            return None
        return self.user_pref.get((user_id, tier))

    def get_tier_default(self, tier: ModelTier) -> ResolvedModelRow | None:
        if not self.tier_default:
            return None
        return self.tier_default.get(tier)

    def get_any_in_tier(self, tier: ModelTier) -> ResolvedModelRow | None:
        if not self.any_in_tier:
            return None
        return self.any_in_tier.get(tier)

    def get_by_id(self, model_id: str) -> ResolvedModelRow | None:
        if not self.by_id:
            return None
        return self.by_id.get(model_id)

    def get_user_preferred_model(self, user_id: str) -> ResolvedModelRow | None:
        if not self.user_preferred:
            return None
        return self.user_preferred.get(user_id)


def _row(kind: str = "openai", tier: ModelTier = ModelTier.EVERYDAY) -> ResolvedModelRow:
    return ResolvedModelRow(
        model_id="m-1",
        model_ref="gpt-5.4",
        tier=tier,
        overrides={},
        provider_id="p-1",
        provider_kind=kind,
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        capability_override=None,
    )


def test_resolve_tier_prefers_override() -> None:
    reg = _FakeRegistry(dept_tier_override=ModelTier.QUICK)
    assert resolve_tier("equity_research", ModelTier.THINKING, reg) is ModelTier.THINKING


def test_resolve_tier_falls_back_to_dept_override_then_shipped() -> None:
    reg = _FakeRegistry(dept_tier_override=ModelTier.QUICK)
    assert resolve_tier("equity_research", None, reg) is ModelTier.QUICK

    reg_no_override = _FakeRegistry()
    assert resolve_tier("equity_research", None, reg_no_override) is ModelTier.THINKING


def test_resolve_tier_unknown_department_defaults_to_everyday() -> None:
    reg = _FakeRegistry()
    assert resolve_tier("made_up", None, reg) is ModelTier.EVERYDAY


def test_resolve_uses_user_preference_first() -> None:
    reg = _FakeRegistry(
        user_pref={("u-1", ModelTier.EVERYDAY): _row()},
        tier_default={ModelTier.EVERYDAY: _row(kind="anthropic")},
    )
    result = resolve(department_id="secretary", registry=reg, user_id="u-1")
    assert result.provider_kind == "openai"


def test_resolve_falls_back_to_tier_default() -> None:
    reg = _FakeRegistry(tier_default={ModelTier.EVERYDAY: _row(kind="anthropic")})
    result = resolve(department_id="secretary", registry=reg, user_id="u-1")
    assert result.provider_kind == "anthropic"


def test_resolve_falls_back_to_any_in_tier() -> None:
    reg = _FakeRegistry(any_in_tier={ModelTier.EVERYDAY: _row(kind="gemini")})
    result = resolve(department_id="secretary", registry=reg, user_id=None)
    assert result.provider_kind == "gemini"


def test_resolve_raises_when_tier_empty() -> None:
    reg = _FakeRegistry()
    with pytest.raises(TierNotConfiguredError) as excinfo:
        resolve(department_id="secretary", registry=reg, user_id=None)
    assert excinfo.value.tier == "everyday"


def test_resolve_applies_capability_override() -> None:
    row = _row()
    row = ResolvedModelRow(
        **{
            **row.__dict__,
            "capability_override": {"tool_calling": False},
        }
    )
    reg = _FakeRegistry(tier_default={ModelTier.EVERYDAY: row})
    result = resolve(department_id="secretary", registry=reg, user_id=None)
    assert result.capabilities.tool_calling is False


def test_resolve_returns_resolved_model() -> None:
    reg = _FakeRegistry(tier_default={ModelTier.THINKING: _row(tier=ModelTier.THINKING)})
    result = resolve(department_id="equity_research", registry=reg, user_id=None)
    assert isinstance(result, ResolvedModel)
    assert result.tier is ModelTier.THINKING
    assert result.model_ref == "gpt-5.4"
    assert result.credentials.api_key == "sk-test"


def test_tier_override_arg_trumps_everything() -> None:
    reg = _FakeRegistry(
        dept_tier_override=ModelTier.EVERYDAY,
        tier_default={ModelTier.QUICK: _row(tier=ModelTier.QUICK)},
    )
    result = resolve(
        department_id="equity_research",
        registry=reg,
        user_id=None,
        tier_override=ModelTier.QUICK,
    )
    assert result.tier is ModelTier.QUICK


def test_resolve_uses_user_preferred_model_before_tier() -> None:
    """User-level preferred model wins over both user-tier-pref and tier
    default. Cross-cuts every department for the user."""
    preferred = ResolvedModelRow(
        model_id="user-pick",
        model_ref="claude-special",
        tier=ModelTier.QUICK,
        overrides={},
        provider_id="p-1",
        provider_kind="anthropic",
        credentials=ProviderCredentials(api_key="sk", base_url=None),
        capability_override=None,
    )
    reg = _FakeRegistry(
        user_preferred={"u-1": preferred},
        user_pref={("u-1", ModelTier.EVERYDAY): _row()},
        tier_default={ModelTier.EVERYDAY: _row(kind="other")},
    )
    result = resolve(department_id="secretary", registry=reg, user_id="u-1")
    assert result.model_id == "user-pick"
    assert result.tier is ModelTier.QUICK


def test_resolve_falls_through_when_user_preferred_missing() -> None:
    reg = _FakeRegistry(
        user_pref={("u-1", ModelTier.EVERYDAY): _row()},
        tier_default={ModelTier.EVERYDAY: _row(kind="other")},
    )
    result = resolve(department_id="secretary", registry=reg, user_id="u-1")
    # Falls through to user-tier-pref since user_preferred is empty.
    assert result.model_id == "m-1"
