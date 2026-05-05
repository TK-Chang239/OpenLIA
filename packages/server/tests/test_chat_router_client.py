"""Tests for the chat-runtime router LLM client.

The router (openlia.llm.runtime.router.route_tools) prompts the model to
return a JSON array of tool names. AdapterLlmJsonClient enforces
``dict`` returns, so the router client must accept arrays too.
"""

from __future__ import annotations

import pytest
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    TestResult,
)
from openlia_server.services.chat_router_client import RouterLlmJsonClient


class _StubProvider:
    kind = "stub"

    def __init__(self, *, text: str) -> None:
        self._text = text
        self.last_request: LLMRequest | None = None
        self.credentials = ProviderCredentials(api_key=None, base_url=None)
        self.model = "stub-model"
        self.capabilities = Capabilities()

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        return LLMResponse(text=self._text, finish_reason="stop", input_tokens=0, output_tokens=0)

    async def list_models(self) -> list[ModelInfo]:
        return []

    async def stream(self, request: LLMRequest):  # pragma: no cover - unused
        yield  # type: ignore[misc]

    async def test_connection(self, model: str) -> TestResult:
        return TestResult(ok=True, latency_ms=0)


@pytest.mark.asyncio
async def test_returns_array_when_model_emits_array() -> None:
    provider = _StubProvider(text='["eodhd__get_quote", "newsapi_ai__search"]')
    client = RouterLlmJsonClient(provider=provider)
    out = await client.generate_json(prompt="pick tools")
    assert out == ["eodhd__get_quote", "newsapi_ai__search"]


@pytest.mark.asyncio
async def test_returns_dict_when_model_emits_object() -> None:
    provider = _StubProvider(text='{"tools": ["eodhd__get_quote"]}')
    client = RouterLlmJsonClient(provider=provider)
    out = await client.generate_json(prompt="pick tools")
    assert out == {"tools": ["eodhd__get_quote"]}


@pytest.mark.asyncio
async def test_strips_markdown_fence() -> None:
    provider = _StubProvider(text='```json\n["a", "b"]\n```')
    client = RouterLlmJsonClient(provider=provider)
    out = await client.generate_json(prompt="pick tools")
    assert out == ["a", "b"]


@pytest.mark.asyncio
async def test_raises_on_non_json() -> None:
    provider = _StubProvider(text="sorry, I can't")
    client = RouterLlmJsonClient(provider=provider)
    with pytest.raises(ValueError):
        await client.generate_json(prompt="pick tools")
