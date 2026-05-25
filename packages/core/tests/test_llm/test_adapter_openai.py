from __future__ import annotations

import json

import pytest
import respx
from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.exceptions import AuthError, ModelNotFoundError, RateLimitError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
    ToolSchema,
)


def _adapter(model: str = "gpt-5.4") -> OpenAIAdapter:
    return OpenAIAdapter(
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_parses_response() -> None:
    adapter = _adapter()
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://api.openai.com/v1/models").respond(
            200,
            json={
                "data": [
                    {"id": "gpt-5.4", "object": "model"},
                    {"id": "gpt-5.4-mini", "object": "model"},
                ]
            },
        )
        models = await adapter.list_models()
    assert {m.id for m in models} == {"gpt-5.4", "gpt-5.4-mini"}


async def test_list_models_auth_error() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.get("https://api.openai.com/v1/models").respond(
            401, json={"error": {"message": "bad key"}}
        )
        with pytest.raises(AuthError):
            await adapter.list_models()


async def test_generate_happy_path() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.text == "hello"
    assert resp.finish_reason == "stop"
    assert resp.input_tokens == 5
    assert resp.output_tokens == 2


async def test_generate_forwards_tool_choice_when_set() -> None:
    adapter = _adapter()
    submit_tool = ToolSchema(
        name="submit_report",
        description="Submit the final report.",
        parameters={"type": "object", "properties": {}},
    )
    with respx.mock() as mock:
        route = mock.post("https://api.openai.com/v1/chat/completions").respond(
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
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tools=[submit_tool],
                tool_choice={"type": "function", "function": {"name": "submit_report"}},
            )
        )
    body = json.loads(route.calls[0].request.content)
    assert body.get("tool_choice") == {
        "type": "function",
        "function": {"name": "submit_report"},
    }


async def test_generate_omits_tool_choice_when_unset() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        route = mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hi"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    body = json.loads(route.calls[0].request.content)
    assert "tool_choice" not in body


async def test_generate_rate_limit_extracts_retry_after() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            429, json={"error": {"message": "slow"}}, headers={"retry-after": "9"}
        )
        with pytest.raises(RateLimitError) as excinfo:
            await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
        assert excinfo.value.retry_after_seconds == 9


async def test_generate_model_not_found() -> None:
    adapter = _adapter(model="ghost-model")
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            404, json={"error": {"message": "model not found"}}
        )
        with pytest.raises(ModelNotFoundError):
            await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
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
        tr = await adapter.test_connection(model="gpt-5.4")
    assert tr.ok is True
    assert tr.error_class is None


async def test_test_connection_returns_structured_failure_on_auth() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            401, json={"error": {"message": "bad key"}}
        )
        tr = await adapter.test_connection(model="gpt-5.4")
    assert tr.ok is False
    assert tr.error_class == "AuthError"


async def test_generate_preserves_system_prefix_across_calls() -> None:
    """Two sequential generate() calls with the same system prompt must
    produce a byte-identical system message in the wire payload, so
    OpenAI's auto prompt cache can hit on the static prefix."""
    adapter = _adapter()
    captured: list[dict] = []

    def _capture(request):
        captured.append(json.loads(request.read()))
        import httpx as _httpx

        return _httpx.Response(
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

    system = "static prefix\n<!-- OPENLIA_CACHE_BREAKPOINT -->\ndynamic suffix"
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").mock(side_effect=_capture)
        for _ in range(2):
            await adapter.generate(
                LLMRequest(system=system, messages=[Message(role="user", content="hi")])
            )
    assert captured[0]["messages"][0] == captured[1]["messages"][0]
    # The static prefix must remain in the rendered system content.
    assert "static prefix" in captured[0]["messages"][0]["content"]


async def test_generate_surfaces_cached_input_tokens() -> None:
    """OpenAI Chat Completions returns cached prefix counts under
    `usage.prompt_tokens_details.cached_tokens`. The adapter must expose
    that value on LLMResponse so the runtime can measure cache hit rate."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hi"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 50_000,
                    "completion_tokens": 100,
                    "prompt_tokens_details": {"cached_tokens": 47_500},
                },
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.input_tokens == 50_000
    assert resp.cached_input_tokens == 47_500


async def test_generate_sends_reasoning_effort_when_set_on_reasoning_model() -> None:
    """gpt-5 / o-series accept `reasoning_effort` on Chat Completions.
    When LLMRequest.reasoning_effort is set the adapter must surface it.
    Non-reasoning models reject the field, so this is guarded by
    _is_reasoning_model — covered separately below."""
    from openlia.llm.types import ReasoningEffort

    adapter = _adapter(model="gpt-5.4")
    captured: dict = {}

    def _capture(request):  # respx Route callback
        captured.update(json.loads(request.content))
        from httpx import Response

        return Response(
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
        mock.post("https://api.openai.com/v1/chat/completions").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )
    assert captured.get("reasoning_effort") == "high"


async def test_generate_omits_reasoning_effort_when_none() -> None:
    """Default request (reasoning_effort=None) must NOT send the field —
    OpenAI applies the model default and adding the key would override."""
    adapter = _adapter(model="gpt-5.4")
    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        from httpx import Response

        return Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert "reasoning_effort" not in captured


async def test_generate_omits_reasoning_effort_on_non_reasoning_model() -> None:
    """Non-reasoning models (e.g. gpt-4o) reject the reasoning_effort field
    with a 400. The guard around _is_reasoning_model must drop it even
    when the caller passed one."""
    from openlia.llm.types import ReasoningEffort

    adapter = _adapter(model="gpt-4o")
    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        from httpx import Response

        return Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )
    assert "reasoning_effort" not in captured


async def test_generate_surfaces_reasoning_output_tokens_from_usage() -> None:
    """The reasoning-token count lives under
    `usage.completion_tokens_details.reasoning_tokens` on reasoning models.
    Must surface as LLMResponse.reasoning_output_tokens for downstream
    sized-from-data ceiling work."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 500,
                    "completion_tokens_details": {"reasoning_tokens": 420},
                },
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.output_tokens == 500
    assert resp.reasoning_output_tokens == 420


async def test_generate_defaults_reasoning_output_tokens_to_zero_when_absent() -> None:
    """Non-reasoning models don't report completion_tokens_details. Field
    must default to 0 so consumers can always read it."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.reasoning_output_tokens == 0


async def test_generate_defaults_cached_input_tokens_to_zero_when_absent() -> None:
    """When the provider response does not report cache details, the field
    falls back to 0 so downstream consumers can always read it."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hi"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 1},
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.cached_input_tokens == 0


async def test_stream_yields_delta_chunks_with_finish_reason() -> None:
    adapter = _adapter()
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"hello"},"finish_reason":null}]}\n\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200, content=sse_body, headers={"content-type": "text/event-stream"}
        )
        chunks = []
        async for c in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert "".join(c.delta for c in chunks) == "hello"
    assert chunks[-1].finish_reason == "stop"
