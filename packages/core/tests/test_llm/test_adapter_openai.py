from __future__ import annotations

import pytest
import respx
from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.exceptions import AuthError, ModelNotFoundError, RateLimitError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
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
