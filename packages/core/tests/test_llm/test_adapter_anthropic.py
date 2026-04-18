from __future__ import annotations

import json

import httpx
import pytest
import respx

from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.exceptions import AuthError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(model: str = "claude-sonnet-4-6") -> AnthropicAdapter:
    return AnthropicAdapter(
        credentials=ProviderCredentials(api_key="sk-ant", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_parses_response() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.get("https://api.anthropic.com/v1/models").respond(
            200,
            json={
                "data": [
                    {"id": "claude-opus-4-6", "display_name": "Claude Opus 4.6"},
                    {"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6"},
                ]
            },
        )
        models = await adapter.list_models()
    assert {m.id for m in models} == {"claude-opus-4-6", "claude-sonnet-4-6"}
    assert any(m.display_name == "Claude Sonnet 4.6" for m in models)


async def test_generate_happy_path_separates_system_from_messages() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 5, "output_tokens": 2},
            },
        )

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                system="be nice",
            )
        )
    assert resp.text == "hello"
    assert resp.finish_reason == "end_turn"
    assert resp.input_tokens == 5
    assert resp.output_tokens == 2
    body = json.loads(captured["payload"])
    assert body["system"] == "be nice"
    assert all(m["role"] != "system" for m in body["messages"])


async def test_generate_includes_api_key_header() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert captured["headers"]["x-api-key"] == "sk-ant"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"


async def test_test_connection_failure_returns_structured_error() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            403, json={"error": {"message": "forbidden"}}
        )
        tr = await adapter.test_connection(model="claude-sonnet-4-6")
    assert tr.ok is False
    assert tr.error_class == "AuthError"
