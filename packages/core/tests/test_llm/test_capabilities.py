from __future__ import annotations

from openlia.llm.capabilities import capabilities_for


def test_unknown_provider_returns_sane_default() -> None:
    caps = capabilities_for(provider_kind="unknown", model="anything")
    assert caps.streaming is True
    assert caps.tool_calling is False
    assert caps.structured_output is False
    assert caps.max_context_tokens == 8192


def test_anthropic_opus_family_matches() -> None:
    caps = capabilities_for(provider_kind="anthropic", model="claude-opus-4-6-20260101")
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.web_search_native is True
    assert caps.max_context_tokens >= 200_000


def test_anthropic_haiku_matches() -> None:
    caps = capabilities_for(provider_kind="anthropic", model="claude-haiku-4-5")
    assert caps.tool_calling is True


def test_openai_gpt_5_4_matches() -> None:
    caps = capabilities_for(provider_kind="openai", model="gpt-5.4-pro")
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.web_search_native is True


def test_gemini_3_1_matches() -> None:
    caps = capabilities_for(provider_kind="gemini", model="gemini-3.1-pro")
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.web_search_native is True


def test_openrouter_inherits_upstream() -> None:
    caps = capabilities_for(provider_kind="openrouter", model="anthropic/claude-sonnet-4-6")
    assert caps.tool_calling is True


def test_openrouter_tilde_provider_alias_resolves() -> None:
    """OpenRouter routes like ``~anthropic/claude-sonnet-latest`` use the
    tilde to mark a floating-version alias. The tilde must be ignored when
    resolving capabilities so the upstream's real cap is used (otherwise
    we fall back to the 2048 default and report writing trips
    OutputLimitReached on every run)."""
    caps = capabilities_for(provider_kind="openrouter", model="~anthropic/claude-sonnet-latest")
    assert caps.tool_calling is True
    assert caps.max_output_tokens >= 8_192


def test_openrouter_anthropic_latest_aliases_resolve() -> None:
    sonnet = capabilities_for(provider_kind="openrouter", model="anthropic/claude-sonnet-latest")
    opus = capabilities_for(provider_kind="openrouter", model="anthropic/claude-opus-latest")
    haiku = capabilities_for(provider_kind="openrouter", model="anthropic/claude-haiku-latest")
    assert sonnet.max_output_tokens >= 8_192
    assert opus.max_output_tokens >= 8_192
    assert haiku.max_output_tokens >= 4_096


def test_ollama_llama31_has_tools() -> None:
    caps = capabilities_for(provider_kind="ollama", model="llama3.1:8b")
    assert caps.tool_calling is True


def test_ollama_llama2_no_tools() -> None:
    caps = capabilities_for(provider_kind="ollama", model="llama2:7b")
    assert caps.tool_calling is False


def test_openai_compat_defaults_to_generic_modern() -> None:
    caps = capabilities_for(provider_kind="openai_compat", model="anything")
    assert caps.streaming is True
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.vision is False


def test_override_applies() -> None:
    override = {"tool_calling": False, "max_context_tokens": 16000}
    caps = capabilities_for(provider_kind="anthropic", model="claude-opus-4-6", override=override)
    assert caps.tool_calling is False
    assert caps.max_context_tokens == 16000
    assert caps.structured_output is True
