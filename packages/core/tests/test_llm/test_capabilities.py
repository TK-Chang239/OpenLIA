from __future__ import annotations

import logging

from openlia.llm.capabilities import capabilities_for, is_known_model


def test_unknown_provider_returns_sane_default() -> None:
    caps = capabilities_for(provider_kind="unknown", model="anything")
    assert caps.streaming is True
    assert caps.tool_calling is False
    assert caps.structured_output is False
    assert caps.max_context_tokens == 8192


def test_is_known_model_distinguishes_registered_from_unknown() -> None:
    assert is_known_model(provider_kind="openai", model="gpt-5.4") is True
    assert is_known_model(provider_kind="anthropic", model="claude-sonnet-4-6") is True
    assert is_known_model(provider_kind="openai", model="gpt-9.9-ultra") is False
    # openai_compat / openrouter resolve structurally, so count as known.
    assert is_known_model(provider_kind="openai_compat", model="anything") is True


def test_capabilities_for_warns_on_unknown_model(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="openlia.llm.capabilities"):
        capabilities_for(provider_kind="openai", model="gpt-9.9-ultra")
    assert "gpt-9.9-ultra" in caplog.text
    assert "capability override" in caplog.text.lower()


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


def test_openai_gpt_5_5_matches() -> None:
    # gpt-5.5 must resolve to the gpt-5.4 capability profile (native web search,
    # large context/output) instead of falling through to the conservative
    # _DEFAULT (no web search, 8K/2K) — which the v3 web-search gate rejects.
    for model in ("gpt-5.5", "gpt-5.5-2026-03-05", "gpt-5.5-pro"):
        caps = capabilities_for(provider_kind="openai", model=model)
        assert caps.web_search_native is True, model
        assert caps.max_output_tokens >= 16_000, model
    # The mini tier mirrors gpt-5.4-mini: no native web search.
    mini = capabilities_for(provider_kind="openai", model="gpt-5.5-mini")
    assert mini.web_search_native is False


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
