from __future__ import annotations

import httpx
import respx
from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(model: str = "anthropic/claude-sonnet-4-6") -> OpenRouterAdapter:
    return OpenRouterAdapter(
        credentials=ProviderCredentials(api_key="or-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_not_used_returns_empty_list() -> None:
    adapter = _adapter()
    models = await adapter.list_models()
    assert models == []


async def test_generate_uses_openai_compat_endpoint() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.text == "ok"
    assert resp.input_tokens == 3


async def test_generate_includes_bearer_token() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert captured["headers"]["authorization"] == "Bearer or-test"


async def test_generate_wraps_ssl_error_as_transient_transport_error() -> None:
    """Mid-stream TLS faults (e.g. SSLV3_ALERT_BAD_RECORD_MAC from a corrupted
    keepalive connection) escape httpx as raw ssl.SSLError. The adapter must
    convert those to TransportError so with_retries treats them as transient
    and a single network blip doesn't abort a long agentic resolve."""
    import ssl

    from openlia.llm.exceptions import TransportError

    adapter = _adapter()

    def _raise_ssl(_request):
        raise ssl.SSLError("SSLV3_ALERT_BAD_RECORD_MAC")

    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_raise_ssl)
        try:
            await adapter.generate(
                LLMRequest(
                    messages=[Message(role="user", content="hi")],
                    max_tokens=8,
                    temperature=0.0,
                )
            )
        except TransportError:
            pass
        else:
            raise AssertionError("expected TransportError after retry exhaustion")


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        tr = await adapter.test_connection(model="anthropic/claude-sonnet-4-6")
    assert tr.ok is True
