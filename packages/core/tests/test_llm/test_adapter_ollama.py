from __future__ import annotations

import httpx
import pytest
import respx
from openlia.llm.adapters.ollama import OllamaAdapter
from openlia.llm.exceptions import ModelNotFoundError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(
    *,
    base_url: str = "http://localhost:11434",
    model: str = "llama3.1:8b",
) -> OllamaAdapter:
    return OllamaAdapter(
        credentials=ProviderCredentials(api_key=None, base_url=base_url),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_returns_empty_list() -> None:
    adapter = _adapter()
    models = await adapter.list_models()
    assert models == []


async def test_generate_uses_chat_endpoint() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("http://localhost:11434/api/chat").respond(
            200,
            json={
                "message": {"role": "assistant", "content": "hello"},
                "done_reason": "stop",
                "prompt_eval_count": 3,
                "eval_count": 1,
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.text == "hello"
    assert resp.finish_reason == "stop"
    assert resp.input_tokens == 3
    assert resp.output_tokens == 1


async def test_generate_disables_streaming_on_payload() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        import json

        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "ok"},
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            },
        )

    with respx.mock() as mock:
        mock.post("http://localhost:11434/api/chat").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert captured["body"]["stream"] is False
    assert captured["body"]["model"] == "llama3.1:8b"


async def test_generate_model_not_found() -> None:
    adapter = _adapter(model="ghost")
    with respx.mock() as mock:
        mock.post("http://localhost:11434/api/chat").respond(404, text="model not found")
        with pytest.raises(ModelNotFoundError):
            await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("http://localhost:11434/api/chat").respond(
            200,
            json={
                "message": {"role": "assistant", "content": "x"},
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            },
        )
        tr = await adapter.test_connection(model="llama3.1:8b")
    assert tr.ok is True


async def test_test_connection_outage_reported_as_transport() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("http://localhost:11434/api/chat").respond(503, text="overloaded")
        tr = await adapter.test_connection(model="llama3.1:8b")
    assert tr.ok is False
    assert tr.error_class == "ProviderOutageError"


async def test_stream_yields_ndjson_chunks_and_terminal_done_reason() -> None:
    adapter = _adapter()
    ndjson_body = (
        b'{"message":{"role":"assistant","content":"Hi"},"done":false}\n'
        b'{"message":{"role":"assistant","content":" there"},"done":false}\n'
        b'{"done":true,"done_reason":"stop"}\n'
    )
    with respx.mock() as mock:
        mock.post("http://localhost:11434/api/chat").respond(
            200, content=ndjson_body, headers={"content-type": "application/x-ndjson"}
        )
        chunks = []
        async for c in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert "".join(c.delta for c in chunks) == "Hi there"
    assert chunks[-1].finish_reason == "stop"
