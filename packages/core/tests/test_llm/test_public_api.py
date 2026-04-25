"""NEW-4-21: openlia.llm public API surface."""

from __future__ import annotations


def test_public_api_imports() -> None:
    from openlia.llm import (  # noqa: F401
        ADAPTERS,
        DEPARTMENT_DEFAULT_TIERS,
        DEPARTMENT_REQUIREMENTS,
        DEPARTMENT_TIER_REASONS,
        SHIPPED_TIER_DEFAULTS,
        AnthropicAdapter,
        AuthError,
        Capabilities,
        Capability,
        CapabilityError,
        CapabilityReport,
        ContextLengthError,
        DepartmentRequirements,
        GeminiAdapter,
        LLMChunk,
        LLMProvider,
        LLMProviderError,
        LLMRequest,
        LLMResponse,
        Message,
        ModelInfo,
        ModelNotFoundError,
        ModelRegistry,
        ModelTier,
        OllamaAdapter,
        OpenAIAdapter,
        OpenAICompatAdapter,
        OpenRouterAdapter,
        ProviderCredentials,
        ProviderOutageError,
        RateLimitError,
        ResolvedModel,
        ResolvedModelRow,
        ResponseFormat,
        TestResult,
        TierNotConfiguredError,
        ToolCall,
        ToolSchema,
        TransportError,
        build_adapter,
        capabilities_for,
        evaluate_requirements,
        is_transient,
        requirements_for,
        resolve,
        resolve_tier,
        with_retries,
    )


def test_public_api_constants_have_expected_keys() -> None:
    from openlia.llm import DEPARTMENT_DEFAULT_TIERS, DEPARTMENT_REQUIREMENTS

    expected = {
        "secretary",
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "retail_sentiment",
        "macro_research",
        "panic_thermometer",
    }
    assert expected.issubset(DEPARTMENT_DEFAULT_TIERS.keys())
    assert expected.issubset(DEPARTMENT_REQUIREMENTS.keys())
