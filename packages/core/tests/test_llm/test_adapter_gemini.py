from __future__ import annotations

import json

import httpx
import pytest
import respx
from openlia.llm.adapters.gemini import GeminiAdapter
from openlia.llm.exceptions import AuthError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(model: str = "gemini-3-flash") -> GeminiAdapter:
    return GeminiAdapter(
        credentials=ProviderCredentials(api_key="gk-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_parses_response() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.get("https://generativelanguage.googleapis.com/v1beta/models").respond(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-3.1-pro",
                        "displayName": "Gemini 3.1 Pro",
                        "inputTokenLimit": 1_000_000,
                    },
                    {
                        "name": "models/gemini-3-flash",
                        "displayName": "Gemini 3 Flash",
                        "inputTokenLimit": 1_000_000,
                    },
                ]
            },
        )
        models = await adapter.list_models()
    assert {m.id for m in models} == {"gemini-3.1-pro", "gemini-3-flash"}


async def test_generate_happy_path_uses_key_query_param() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "hello"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 4,
                    "candidatesTokenCount": 2,
                },
            },
        )

    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(side_effect=_capture)
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                system="be nice",
            )
        )
    assert "key=gk-test" in captured["url"]
    assert captured["body"]["systemInstruction"]["parts"][0]["text"] == "be nice"
    assert resp.text == "hello"
    assert resp.finish_reason == "STOP"
    assert resp.input_tokens == 4
    assert resp.output_tokens == 2


async def test_generate_auth_error() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).respond(403, json={"error": {"message": "forbidden"}})
        with pytest.raises(AuthError):
            await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).respond(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "x"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 1,
                    "candidatesTokenCount": 1,
                },
            },
        )
        tr = await adapter.test_connection(model="gemini-3-flash")
    assert tr.ok is True


async def test_stream_yields_text_deltas_and_terminal_finish_reason() -> None:
    adapter = _adapter()
    sse_body = (
        b'data: {"candidates":[{"content":{"parts":[{"text":"Hi"}],"role":"model"},'
        b'"finishReason":null,"index":0}]}\n\n'
        b'data: {"candidates":[{"content":{"parts":[{"text":"!"}],"role":"model"},'
        b'"finishReason":"STOP","index":0}]}\n\n'
    )
    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-3-flash:streamGenerateContent"
        ).respond(200, content=sse_body, headers={"content-type": "text/event-stream"})
        chunks = []
        async for c in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert "".join(c.delta for c in chunks) == "Hi!"
    assert chunks[-1].finish_reason == "STOP"
