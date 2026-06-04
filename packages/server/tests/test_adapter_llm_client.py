"""Tests for the adapter LLM JSON client and its factory.

1. `AdapterLlmJsonClient` adapts an `LLMProvider.generate(...)` to the
   `LlmClient.generate_json(prompt=...)` Protocol expected by
   `resolve_callable_spec`. Must parse JSON and tolerate markdown fences.
2. The factory resolves a model from `SQLModelRegistry` per call. If no
   model can be resolved it must raise `AdapterLlmNotConfigured` so the
   route can surface a clean 422 instead of a 500.
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
from openlia_server.services.adapter_llm_client import (
    AdapterLlmJsonClient,
    AdapterLlmNotConfigured,
    make_adapter_llm_client_factory,
)


class _StubProvider:
    """Minimal LLMProvider — just records the request and returns text."""

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


# ---------------------------------------------------------------------------
# AdapterLlmJsonClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_json_parses_plain_object() -> None:
    provider = _StubProvider(text='{"tool_name":"get_quote","constants":{}}')
    client = AdapterLlmJsonClient(provider=provider)

    out = await client.generate_json(prompt="resolve this")

    assert out == {"tool_name": "get_quote", "constants": {}}
    # Prompt forwarded as a user message.
    assert provider.last_request is not None
    assert provider.last_request.messages[0].content == "resolve this"


@pytest.mark.asyncio
async def test_generate_json_strips_markdown_fence() -> None:
    fenced = '```json\n{"tool_name":"x","method":null}\n```'
    provider = _StubProvider(text=fenced)
    client = AdapterLlmJsonClient(provider=provider)

    out = await client.generate_json(prompt="x")

    assert out == {"tool_name": "x", "method": None}


@pytest.mark.asyncio
async def test_generate_json_strips_bare_fence() -> None:
    provider = _StubProvider(text='```\n{"a": 1}\n```')
    client = AdapterLlmJsonClient(provider=provider)

    out = await client.generate_json(prompt="x")

    assert out == {"a": 1}


@pytest.mark.asyncio
async def test_generate_json_raises_on_non_json() -> None:
    """Garbled output must surface as ResolverError so the resolve loop can
    record a per-need failure rather than crash."""
    from openlia.connectors.adapter import ResolverError

    provider = _StubProvider(text="not json")
    client = AdapterLlmJsonClient(provider=provider)

    with pytest.raises(ResolverError):
        await client.generate_json(prompt="x")


@pytest.mark.asyncio
async def test_generate_json_raises_when_response_is_not_object() -> None:
    from openlia.connectors.adapter import ResolverError

    provider = _StubProvider(text="[1, 2, 3]")
    client = AdapterLlmJsonClient(provider=provider)

    with pytest.raises(ResolverError):
        await client.generate_json(prompt="x")


# ---------------------------------------------------------------------------
# make_adapter_llm_client_factory
# ---------------------------------------------------------------------------


def test_factory_raises_when_no_model_configured(db_session_factory) -> None:
    """Empty `llm_models` table -> factory raises a typed exception so the
    route can return 422 (instead of 500 from the underlying
    TierNotConfiguredError)."""
    factory = make_adapter_llm_client_factory(db_session_factory)
    with pytest.raises(AdapterLlmNotConfigured):
        factory()


def test_factory_builds_client_when_model_configured(db_session_factory, db_session) -> None:
    """Seed a provider+model+slot default and confirm the factory yields a working client."""
    from openlia_server.db.models.config import LLMModel, LLMProvider, LLMSlotDefault

    provider_row = LLMProvider(
        id="p-1",
        kind="openai_compat",
        label="Stub",
        base_url="http://localhost",
        api_key=None,
        is_enabled=True,
    )
    model_row = LLMModel(
        id="m-1",
        provider_id="p-1",
        model_ref="stub-model",
        display_name="Stub Model",
        is_enabled=True,
    )
    db_session.add_all([provider_row, model_row])
    db_session.flush()
    slot_row = LLMSlotDefault(
        slot_kind="system_role",
        slot_id="connector_spec_adapter",
        model_id="m-1",
    )
    db_session.add(slot_row)
    db_session.commit()

    factory = make_adapter_llm_client_factory(db_session_factory)
    client = factory()

    # Returned object must satisfy the Protocol used by resolve_callable_spec.
    assert hasattr(client, "generate_json")
