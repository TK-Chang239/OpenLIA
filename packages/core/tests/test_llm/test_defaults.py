from __future__ import annotations

from openlia.llm.department_defaults import DEPARTMENT_DEFAULT_TIERS
from openlia.llm.model_defaults import SHIPPED_TIER_DEFAULTS
from openlia.llm.types import ModelTier


def test_shipped_tier_defaults_has_six_named_providers() -> None:
    assert set(SHIPPED_TIER_DEFAULTS.keys()) == {
        "openai",
        "anthropic",
        "gemini",
        "openrouter",
        "openai_compat",
        "ollama",
    }


def test_openai_tier_defaults_populated() -> None:
    d = SHIPPED_TIER_DEFAULTS["openai"]
    assert d[ModelTier.THINKING] == "gpt-5.4-pro"
    assert d[ModelTier.EVERYDAY] == "gpt-5.4"
    assert d[ModelTier.QUICK] == "gpt-5.4-mini"


def test_anthropic_tier_defaults_populated() -> None:
    d = SHIPPED_TIER_DEFAULTS["anthropic"]
    assert d[ModelTier.THINKING] == "claude-opus-4-6"
    assert d[ModelTier.EVERYDAY] == "claude-sonnet-4-6"
    assert d[ModelTier.QUICK] == "claude-haiku-4-5"


def test_gemini_tier_defaults_populated() -> None:
    d = SHIPPED_TIER_DEFAULTS["gemini"]
    assert d[ModelTier.THINKING] == "gemini-3.1-pro"
    assert d[ModelTier.EVERYDAY] == "gemini-3-flash"
    assert d[ModelTier.QUICK] == "gemini-3.1-flash-lite"


def test_byo_providers_have_none_defaults() -> None:
    for kind in ("openrouter", "openai_compat", "ollama"):
        d = SHIPPED_TIER_DEFAULTS[kind]
        assert d[ModelTier.THINKING] is None
        assert d[ModelTier.EVERYDAY] is None
        assert d[ModelTier.QUICK] is None


def test_department_defaults_cover_all_shipped_departments() -> None:
    expected = {
        "secretary": ModelTier.EVERYDAY,
        "equity_research": ModelTier.THINKING,
        "earnings_update": ModelTier.EVERYDAY,
        "morning_briefing": ModelTier.EVERYDAY,
        "retail_sentiment": ModelTier.QUICK,
        "macro_research": ModelTier.THINKING,
        "panic_thermometer": ModelTier.QUICK,
    }
    assert DEPARTMENT_DEFAULT_TIERS == expected
