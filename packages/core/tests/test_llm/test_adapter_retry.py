"""NEW-4-20: each adapter wraps generate() through with_retries.

Asserts the spec's 3x-attempt policy on transient errors and the explicit
no-retry on AuthError.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from openlia.llm.adapters import build_adapter
from openlia.llm.exceptions import AuthError, LLMProviderError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip exponential backoff so the 3x retries finish in ~0s."""
    import openlia.llm.retry as retry_mod

    async def _instant(_):
        return None

    monkeypatch.setattr(retry_mod.asyncio, "sleep", _instant)


@pytest.mark.asyncio
@respx.mock
async def test_openai_adapter_retries_on_provider_outage_three_times() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(503, text="upstream down")
    )
    adapter = build_adapter(
        kind="openai",
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        model="gpt-5.4",
        capabilities=Capabilities(),
    )
    with pytest.raises(LLMProviderError):
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")], max_tokens=8)
        )
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_adapter_retries_on_provider_outage_three_times() -> None:
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(502, text="upstream gateway")
    )
    adapter = build_adapter(
        kind="anthropic",
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        model="claude-sonnet-4",
        capabilities=Capabilities(),
    )
    with pytest.raises(LLMProviderError):
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")], max_tokens=8)
        )
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_openai_adapter_does_not_retry_on_auth_error() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(401, text="invalid key")
    )
    adapter = build_adapter(
        kind="openai",
        credentials=ProviderCredentials(api_key="sk-bad", base_url=None),
        model="gpt-5.4",
        capabilities=Capabilities(),
    )
    with pytest.raises(AuthError):
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")], max_tokens=8)
        )
    assert route.call_count == 1
