"""Tests that adapters handle the cache-breakpoint marker correctly.

Uses respx HTTP mocking to capture the actual outbound payload, matching
the convention used in the other test_adapter_* files.

Anthropic: emits system as a two-block list with cache_control on the
static block. OpenAI / Gemini / Ollama / OpenRouter / openai_compat:
strip the marker so it never reaches the model.
"""

from __future__ import annotations

import json

import respx
from openlia.llm.adapters._content import CACHE_BREAKPOINT_MARKER
from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.adapters.gemini import GeminiAdapter
from openlia.llm.adapters.ollama import OllamaAdapter
from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.adapters.openai_compat import OpenAICompatAdapter
from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)

SYS_WITH_MARKER = f"STATIC PREFIX\n\n{CACHE_BREAKPOINT_MARKER}\n\nDYNAMIC SUFFIX"

SAMPLE_REQUEST = LLMRequest(
    messages=[Message(role="user", content="hi")],
    system=SYS_WITH_MARKER,
    max_tokens=10,
    temperature=0.0,
)

_ANTHROPIC_OK = {
    "id": "msg_x",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": "ok"}],
    "model": "claude-sonnet-4-6",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 5, "output_tokens": 1},
}

_OPENAI_OK = {
    "id": "x",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "ok"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
}

_GEMINI_OK = {
    "candidates": [
        {
            "content": {"parts": [{"text": "ok"}], "role": "model"},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 1, "totalTokenCount": 6},
}

_OLLAMA_OK = {
    "model": "llama3",
    "message": {"role": "assistant", "content": "ok"},
    "done": True,
    "done_reason": "stop",
    "prompt_eval_count": 5,
    "eval_count": 1,
}


def _creds(api_key: str = "k") -> ProviderCredentials:
    return ProviderCredentials(api_key=api_key, base_url=None)


# ---- Anthropic: splits + cache_control ------------------------------------


async def test_anthropic_payload_splits_at_marker() -> None:
    adapter = AnthropicAdapter(
        credentials=_creds("sk-ant"), model="claude-sonnet-4-6", capabilities=Capabilities()
    )
    with respx.mock() as mock:
        route = mock.post("https://api.anthropic.com/v1/messages").respond(200, json=_ANTHROPIC_OK)
        await adapter.generate(SAMPLE_REQUEST)
    sent = json.loads(route.calls.last.request.content)
    sys = sent["system"]
    assert isinstance(sys, list), "system must be a list of blocks when marker present"
    assert len(sys) == 2
    assert sys[0]["text"].strip() == "STATIC PREFIX"
    assert sys[0]["cache_control"] == {"type": "ephemeral"}
    assert sys[1]["text"].strip() == "DYNAMIC SUFFIX"
    assert "cache_control" not in sys[1]


async def test_anthropic_payload_passes_string_when_no_marker() -> None:
    adapter = AnthropicAdapter(
        credentials=_creds("sk-ant"), model="claude-sonnet-4-6", capabilities=Capabilities()
    )
    req = LLMRequest(
        messages=[Message(role="user", content="hi")],
        system="plain system",
        max_tokens=10,
        temperature=0.0,
    )
    with respx.mock() as mock:
        route = mock.post("https://api.anthropic.com/v1/messages").respond(200, json=_ANTHROPIC_OK)
        await adapter.generate(req)
    sent = json.loads(route.calls.last.request.content)
    assert sent["system"] == "plain system"


# ---- Non-Anthropic adapters: strip the marker -----------------------------


async def test_openai_strips_marker() -> None:
    adapter = OpenAIAdapter(credentials=_creds("sk-x"), model="gpt-4o", capabilities=Capabilities())
    with respx.mock() as mock:
        route = mock.post("https://api.openai.com/v1/chat/completions").respond(
            200, json=_OPENAI_OK
        )
        await adapter.generate(SAMPLE_REQUEST)
    sent = json.loads(route.calls.last.request.content)
    sys_msg = next(m for m in sent["messages"] if m["role"] == "system")
    assert CACHE_BREAKPOINT_MARKER not in sys_msg["content"]
    assert "STATIC PREFIX" in sys_msg["content"]
    assert "DYNAMIC SUFFIX" in sys_msg["content"]


async def test_openai_compat_strips_marker() -> None:
    adapter = OpenAICompatAdapter(
        credentials=ProviderCredentials(api_key="k", base_url="https://example.test/v1"),
        model="any",
        capabilities=Capabilities(),
    )
    with respx.mock() as mock:
        route = mock.post("https://example.test/v1/chat/completions").respond(200, json=_OPENAI_OK)
        await adapter.generate(SAMPLE_REQUEST)
    sent = json.loads(route.calls.last.request.content)
    sys_msg = next(m for m in sent["messages"] if m["role"] == "system")
    assert CACHE_BREAKPOINT_MARKER not in sys_msg["content"]


async def test_openrouter_strips_marker() -> None:
    adapter = OpenRouterAdapter(
        credentials=_creds("or"), model="anthropic/claude-3-haiku", capabilities=Capabilities()
    )
    with respx.mock() as mock:
        route = mock.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200, json=_OPENAI_OK
        )
        await adapter.generate(SAMPLE_REQUEST)
    sent = json.loads(route.calls.last.request.content)
    sys_msg = next(m for m in sent["messages"] if m["role"] == "system")
    assert CACHE_BREAKPOINT_MARKER not in sys_msg["content"]


async def test_ollama_strips_marker() -> None:
    adapter = OllamaAdapter(
        credentials=ProviderCredentials(api_key=None, base_url="http://localhost:11434"),
        model="llama3",
        capabilities=Capabilities(),
    )
    with respx.mock() as mock:
        route = mock.post("http://localhost:11434/api/chat").respond(200, json=_OLLAMA_OK)
        await adapter.generate(SAMPLE_REQUEST)
    sent = json.loads(route.calls.last.request.content)
    sys_msg = next(m for m in sent["messages"] if m["role"] == "system")
    assert CACHE_BREAKPOINT_MARKER not in sys_msg["content"]


async def test_gemini_strips_marker() -> None:
    adapter = GeminiAdapter(
        credentials=_creds("gem"), model="gemini-1.5-flash", capabilities=Capabilities()
    )
    with respx.mock() as mock:
        route = mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        ).respond(200, json=_GEMINI_OK)
        await adapter.generate(SAMPLE_REQUEST)
    sent = json.loads(route.calls.last.request.content)
    sys_text = sent["systemInstruction"]["parts"][0]["text"]
    assert CACHE_BREAKPOINT_MARKER not in sys_text
    assert "STATIC PREFIX" in sys_text and "DYNAMIC SUFFIX" in sys_text
