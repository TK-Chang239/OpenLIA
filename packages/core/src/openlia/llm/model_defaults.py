from __future__ import annotations

from openlia.llm.types import ModelTier

SHIPPED_TIER_DEFAULTS: dict[str, dict[ModelTier, str | None]] = {
    "openai": {
        ModelTier.THINKING: "gpt-5.4-pro",
        ModelTier.EVERYDAY: "gpt-5.4",
        ModelTier.QUICK: "gpt-5.4-mini",
    },
    "anthropic": {
        ModelTier.THINKING: "claude-opus-4-6",
        ModelTier.EVERYDAY: "claude-sonnet-4-6",
        ModelTier.QUICK: "claude-haiku-4-5",
    },
    "gemini": {
        ModelTier.THINKING: "gemini-3.1-pro",
        ModelTier.EVERYDAY: "gemini-3-flash",
        ModelTier.QUICK: "gemini-3.1-flash-lite",
    },
    "openrouter": {
        ModelTier.THINKING: None,
        ModelTier.EVERYDAY: None,
        ModelTier.QUICK: None,
    },
    "openai_compat": {
        ModelTier.THINKING: None,
        ModelTier.EVERYDAY: None,
        ModelTier.QUICK: None,
    },
    "ollama": {
        ModelTier.THINKING: None,
        ModelTier.EVERYDAY: None,
        ModelTier.QUICK: None,
    },
}
