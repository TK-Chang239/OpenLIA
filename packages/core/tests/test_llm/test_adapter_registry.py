from __future__ import annotations

import pytest
from openlia.llm.adapters import ADAPTERS, build_adapter
from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.adapters.gemini import GeminiAdapter
from openlia.llm.adapters.ollama import OllamaAdapter
from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.adapters.openai_compat import OpenAICompatAdapter
from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.base import LLMProvider
from openlia.llm.types import Capabilities, ProviderCredentials


def test_registry_covers_six_kinds() -> None:
    assert set(ADAPTERS.keys()) == {
        "openai",
        "anthropic",
        "gemini",
        "openrouter",
        "openai_compat",
        "ollama",
    }


def test_registry_values_are_concrete_subclasses() -> None:
    assert ADAPTERS["openai"] is OpenAIAdapter
    assert ADAPTERS["anthropic"] is AnthropicAdapter
    assert ADAPTERS["gemini"] is GeminiAdapter
    assert ADAPTERS["openrouter"] is OpenRouterAdapter
    assert ADAPTERS["openai_compat"] is OpenAICompatAdapter
    assert ADAPTERS["ollama"] is OllamaAdapter
    for cls in ADAPTERS.values():
        assert issubclass(cls, LLMProvider)


def test_build_adapter_returns_matching_instance() -> None:
    adapter = build_adapter(
        kind="openai",
        credentials=ProviderCredentials(api_key="sk-x", base_url=None),
        model="gpt-5.4",
        capabilities=Capabilities(),
    )
    assert isinstance(adapter, OpenAIAdapter)
    assert adapter.model == "gpt-5.4"


def test_build_adapter_unknown_kind_raises() -> None:
    with pytest.raises(KeyError):
        build_adapter(
            kind="nope",
            credentials=ProviderCredentials(api_key="x", base_url=None),
            model="x",
            capabilities=Capabilities(),
        )
