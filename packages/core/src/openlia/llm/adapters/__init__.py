from __future__ import annotations

from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.adapters.gemini import GeminiAdapter
from openlia.llm.adapters.ollama import OllamaAdapter
from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.adapters.openai_compat import OpenAICompatAdapter
from openlia.llm.adapters.openai_responses import OpenAIResponsesAdapter
from openlia.llm.adapters.openai_router import OpenAIRouter
from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.base import LLMProvider
from openlia.llm.types import Capabilities, ProviderCredentials

# `kind="openai"` resolves to OpenAIRouter, which transparently
# multiplexes Chat Completions and Responses API per-turn based on
# `LLMRequest.native_tools`. Behavior is identical to OpenAIAdapter
# for non-search workloads — see openai_router.py for the routing
# rule and rationale (spec B2).
ADAPTERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIRouter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "openrouter": OpenRouterAdapter,
    "openai_compat": OpenAICompatAdapter,
    "ollama": OllamaAdapter,
}


def build_adapter(
    *,
    kind: str,
    credentials: ProviderCredentials,
    model: str,
    capabilities: Capabilities,
) -> LLMProvider:
    cls = ADAPTERS[kind]
    return cls(credentials=credentials, model=model, capabilities=capabilities)


__all__ = [
    "ADAPTERS",
    "AnthropicAdapter",
    "GeminiAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "OpenAICompatAdapter",
    "OpenAIResponsesAdapter",
    "OpenAIRouter",
    "OpenRouterAdapter",
    "build_adapter",
]
