from __future__ import annotations

import httpx
import pytest
import respx

from openlia.llm.adapters.openai_compat import OpenAICompatAdapter
from openlia.llm.exceptions import CapabilityError, ModelNotFoundError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(
    *,
    base_url: str = "https://deepseek.example.com/v1",
    api_key: str | None = "dsk-test",
    model: str = "deepseek-chat",
) -> OpenAICompatAdapter:
    return OpenAICompatAdapter(
        credentials=ProviderCredentials(api_key=api_key, base_url=base_url),
        model=model,
        capabilities=Capabilities(),
    )


def test_missing_base_url_raises() -> None:
    with pytest.raises(CapabilityError):
        OpenAICompatAdapter(
            credentials=ProviderCredentials(api_key="x", base_url=None),
            model="x",
            capabilities=Capabilities(),
        )


async def test_list_models_hits_user_base_url() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.get("https://deepseek.example.com/v1/models").respond(
            200, json={"data": [{"id": "deepseek-chat"}]}
        )
        models = await adapter.list_models()
    assert [m.id for m in models] == ["deepseek-chat"]


async def test_list_models_404_returns_empty_for_fallback() -> None:
    adapter = _adapter()
    with respx.mock() as mock:
        mock.get("https://deepseek.example.com/v1/models").respond(404)
        models = await adapter.list_models()
    assert models == []


async def test_generate_includes_auth_header() -> None:
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
        mock.post("https://deepseek.example.com/v1/chat/completions").mock(
            side_effect=_capture
        )
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert captured["headers"]["authorization"] == "Bearer dsk-test"


async def test_generate_omits_auth_if_no_key() -> None:
    adapter = _adapter(api_key=None)
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
        mock.post("https://deepseek.example.com/v1/chat/completions").mock(
            side_effect=_capture
        )
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert "authorization" not in captured["headers"]


async def test_generate_model_not_found() -> None:
    adapter = _adapter(model="ghost")
    with respx.mock() as mock:
        mock.post("https://deepseek.example.com/v1/chat/completions").respond(
            404, json={"error": {"message": "not found"}}
        )
        with pytest.raises(ModelNotFoundError):
            await adapter.generate(
                LLMRequest(messages=[Message(role="user", content="hi")])
            )
