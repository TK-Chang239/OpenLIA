"""Incremental conversation caching (LLMRequest.cache_conversation).

Two layers:
  - the ``apply_message_cache_breakpoint`` helper stamps the tail of the
    rendered message list with an ephemeral cache breakpoint;
  - the Anthropic adapter applies it (plus a tools-block breakpoint) only
    when ``cache_conversation`` is set, and leaves one-shot callers alone.
"""

from __future__ import annotations

import json

import respx
from openlia.llm.adapters._content import apply_message_cache_breakpoint
from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
    ToolSchema,
)

_EPHEMERAL = {"type": "ephemeral"}

_ANTHROPIC_OK = {
    "id": "msg_x",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": "ok"}],
    "model": "claude-sonnet-4-6",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 5, "output_tokens": 1},
}


def _creds() -> ProviderCredentials:
    return ProviderCredentials(api_key="sk-ant", base_url=None)


def _tool() -> ToolSchema:
    return ToolSchema(
        name="get_x",
        description="d",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    )


# ---- helper ---------------------------------------------------------------


def test_breakpoint_converts_string_content_to_a_cached_block() -> None:
    rendered = [{"role": "user", "content": "hello"}]
    apply_message_cache_breakpoint(rendered)
    assert rendered[-1]["content"] == [
        {"type": "text", "text": "hello", "cache_control": _EPHEMERAL}
    ]


def test_breakpoint_stamps_only_the_last_block_of_a_block_list() -> None:
    rendered = [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "a"},
                {"type": "tool_result", "tool_use_id": "t2", "content": "b"},
            ],
        }
    ]
    apply_message_cache_breakpoint(rendered)
    blocks = rendered[-1]["content"]
    assert "cache_control" not in blocks[0]
    assert blocks[1]["cache_control"] == _EPHEMERAL


def test_breakpoint_touches_only_the_last_message() -> None:
    rendered = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "mid"},
        {"role": "user", "content": "last"},
    ]
    apply_message_cache_breakpoint(rendered)
    assert rendered[0]["content"] == "first"
    assert rendered[1]["content"] == "mid"
    assert rendered[-1]["content"][-1]["cache_control"] == _EPHEMERAL


def test_breakpoint_is_a_noop_on_empty_list() -> None:
    rendered: list[dict] = []
    apply_message_cache_breakpoint(rendered)
    assert rendered == []


# ---- adapter wiring -------------------------------------------------------


async def test_anthropic_caches_tools_and_message_tail_when_enabled() -> None:
    adapter = AnthropicAdapter(
        credentials=_creds(), model="claude-sonnet-4-6", capabilities=Capabilities()
    )
    request = LLMRequest(
        messages=[Message(role="user", content="hi")],
        system="plain system",
        tools=[_tool()],
        max_tokens=10,
        temperature=0.0,
        cache_conversation=True,
    )
    with respx.mock() as mock:
        route = mock.post("https://api.anthropic.com/v1/messages").respond(200, json=_ANTHROPIC_OK)
        await adapter.generate(request)
    sent = json.loads(route.calls.last.request.content)
    assert sent["tools"][-1]["cache_control"] == _EPHEMERAL
    assert sent["messages"][-1]["content"][-1]["cache_control"] == _EPHEMERAL


async def test_anthropic_skips_cache_when_flag_default_off() -> None:
    adapter = AnthropicAdapter(
        credentials=_creds(), model="claude-sonnet-4-6", capabilities=Capabilities()
    )
    request = LLMRequest(
        messages=[Message(role="user", content="hi")],
        system="plain system",
        tools=[_tool()],
        max_tokens=10,
        temperature=0.0,
    )
    with respx.mock() as mock:
        route = mock.post("https://api.anthropic.com/v1/messages").respond(200, json=_ANTHROPIC_OK)
        await adapter.generate(request)
    sent = json.loads(route.calls.last.request.content)
    assert "cache_control" not in sent["tools"][-1]
    # One-shot caller's message is left as a plain string — untouched.
    assert sent["messages"][-1]["content"] == "hi"
