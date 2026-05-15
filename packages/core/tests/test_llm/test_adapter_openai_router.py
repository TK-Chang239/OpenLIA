"""Phase 3b: OpenAIRouter multiplexer.

Routes LLMRequests per-turn:
- `"web_search" in native_tools` → OpenAIResponsesAdapter (/v1/responses)
- otherwise → OpenAIAdapter (/v1/chat/completions)

The router is transparent to callers: `build_adapter(kind="openai",
...)` returns a router that behaves identically to the chat adapter
for non-search workloads (latency + cost benefit per spec B2), and
opts into Responses only when the runtime explicitly asks for native
web search.
"""

from __future__ import annotations

import httpx
import respx
from openlia.llm.adapters.openai_router import OpenAIRouter
from openlia.llm.types import Capabilities, LLMRequest, Message, ProviderCredentials


def _router(model: str = "gpt-5.4") -> OpenAIRouter:
    return OpenAIRouter(
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


_CHAT_OK = httpx.Response(
    200,
    json={
        "choices": [
            {"message": {"role": "assistant", "content": "chat-path"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    },
)

_RESPONSES_OK = httpx.Response(
    200,
    json={
        "id": "resp_x",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "responses-path"}],
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 1},
    },
)


async def test_router_routes_to_chat_completions_when_no_native_tools() -> None:
    """Default behavior: requests without native_tools go to the Chat
    Completions adapter. Spec B2: non-search workloads pay zero
    latency/cost penalty from the Responses API."""
    router = _router()
    with respx.mock(assert_all_called=False) as mock:
        chat_route = mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=_CHAT_OK
        )
        responses_route = mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_RESPONSES_OK
        )
        resp = await router.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert chat_route.called is True
    assert responses_route.called is False
    assert resp.text == "chat-path"


async def test_router_routes_to_responses_when_native_web_search() -> None:
    """When `web_search` is in native_tools, the router targets the
    Responses adapter — which is where the native server-side search
    tool is supported."""
    router = _router()
    with respx.mock(assert_all_called=False) as mock:
        chat_route = mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=_CHAT_OK
        )
        responses_route = mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_RESPONSES_OK
        )
        resp = await router.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    assert responses_route.called is True
    assert chat_route.called is False
    assert resp.text == "responses-path"


async def test_router_stream_routes_to_chat_by_default() -> None:
    """Streaming follows the same per-turn routing rule. Default →
    Chat Completions."""
    router = _router()
    chat_sse = b"data: {\"choices\":[{\"delta\":{\"content\":\"hi\"},\"finish_reason\":null}]}\n\n"
    with respx.mock(assert_all_called=False) as mock:
        chat_route = mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200, content=chat_sse, headers={"content-type": "text/event-stream"}
            )
        )
        responses_route = mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_RESPONSES_OK
        )
        async for _ in router.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            pass
    assert chat_route.called is True
    assert responses_route.called is False


async def test_router_stream_routes_to_responses_when_native() -> None:
    """Streaming with native_tools goes to the Responses adapter (which
    falls back to generate() in Phase 3a; that still proves routing)."""
    router = _router()
    with respx.mock(assert_all_called=False) as mock:
        chat_route = mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=_CHAT_OK
        )
        responses_route = mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_RESPONSES_OK
        )
        async for _ in router.stream(
            LLMRequest(
                messages=[Message(role="user", content="x")],
                native_tools=("web_search",),
            )
        ):
            pass
    assert responses_route.called is True
    assert chat_route.called is False


async def test_router_kind_is_openai_for_transparency() -> None:
    """build_adapter(kind="openai", ...) must return a provider that
    self-reports as "openai" so downstream code (capability lookup,
    error mapping, telemetry) keeps working unchanged."""
    router = _router()
    assert router.kind == "openai"
