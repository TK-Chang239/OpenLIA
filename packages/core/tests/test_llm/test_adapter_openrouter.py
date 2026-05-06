from __future__ import annotations

import json

import httpx
import respx
from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
    ToolSchema,
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


async def test_generate_forwards_tool_choice_when_set() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": ""},
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tools=[
                    ToolSchema(
                        name="submit_report",
                        description="Submit the final report.",
                        parameters={"type": "object", "properties": {}},
                    )
                ],
                tool_choice={"type": "function", "function": {"name": "submit_report"}},
            )
        )
    body = json.loads(captured["payload"])
    assert body["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_report"},
    }


async def test_generate_omits_tool_choice_when_unset() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
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
    body = json.loads(captured["payload"])
    assert "tool_choice" not in body


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


async def test_stream_yields_delta_chunks() -> None:
    """Single SSE data frame with a content delta yields one LLMChunk."""
    adapter = _adapter()
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"hi"},"finish_reason":null}]}\n\ndata: [DONE]\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            content=sse_body,
            headers={"content-type": "text/event-stream"},
        )
        chunks = []
        async for c in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert [c.delta for c in chunks] == ["hi"]


async def test_stream_yields_chunks_in_order_across_frames() -> None:
    adapter = _adapter()
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"a"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"b"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"c"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            content=sse_body,
            headers={"content-type": "text/event-stream"},
        )
        chunks = []
        async for c in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert "".join(c.delta for c in chunks) == "abc"


async def test_stream_emits_finish_reason_on_terminal_chunk() -> None:
    adapter = _adapter()
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"hi"},"finish_reason":null}]}\n\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            content=sse_body,
            headers={"content-type": "text/event-stream"},
        )
        chunks = []
        async for c in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert chunks[-1].finish_reason == "stop"


async def test_stream_sends_stream_true_in_payload() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            content=b"data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_capture)
        async for _ in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            pass
    assert captured["body"]["stream"] is True


async def test_stream_raises_auth_error_on_401() -> None:
    from openlia.llm.exceptions import AuthError

    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").respond(401, text="bad key")
        try:
            async for _ in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
                pass
        except AuthError:
            return
    raise AssertionError("expected AuthError on 401")


async def test_stream_includes_bearer_token_header() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            content=b"data: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    with respx.mock() as mock:
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=_capture)
        async for _ in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            pass
    assert captured["headers"]["authorization"] == "Bearer or-test"


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
