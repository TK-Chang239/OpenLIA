"""build_batch_transport — maps provider_kind to a concrete transport."""

from __future__ import annotations

from openlia.llm.adapters.anthropic_batch import AnthropicBatchTransport
from openlia.llm.adapters.openai_batch import OpenAIBatchTransport
from openlia.llm.batch_factory import build_batch_transport
from openlia.llm.types import ProviderCredentials

_CREDS = ProviderCredentials(api_key="k", base_url=None)


def test_openai_builds_responses_batch_transport():
    t = build_batch_transport(provider_kind="openai", credentials=_CREDS, model="gpt-5.4")
    assert isinstance(t, OpenAIBatchTransport)


def test_anthropic_builds_message_batch_transport():
    t = build_batch_transport(
        provider_kind="anthropic", credentials=_CREDS, model="claude-sonnet-4-6"
    )
    assert isinstance(t, AnthropicBatchTransport)


def test_unsupported_providers_return_none():
    for kind in ("openrouter", "ollama", "gemini", "openai_responses", "unknown"):
        assert build_batch_transport(provider_kind=kind, credentials=_CREDS, model="m") is None
