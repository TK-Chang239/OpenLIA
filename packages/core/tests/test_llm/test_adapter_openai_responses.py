"""Phase 3a: OpenAIResponsesAdapter — targets the OpenAI Responses API
(`/v1/responses`) so we can opt into the native `{"type":"web_search"}`
tool. The existing OpenAIAdapter (Chat Completions) stays untouched.
Per-turn routing between the two lands in Phase 3b via OpenAIRouter.
"""

from __future__ import annotations

import json

import httpx
import respx
from openlia.llm.adapters.openai_responses import OpenAIResponsesAdapter
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
    ToolCall,
    ToolSchema,
)


def _adapter(model: str = "gpt-5.4") -> OpenAIResponsesAdapter:
    return OpenAIResponsesAdapter(
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


def _assistant_ok() -> list[dict]:
    """One assistant message item with a single 'ok' output_text part."""
    return [
        {
            "role": "assistant",
            "type": "message",
            "content": [{"type": "output_text", "text": "ok"}],
        }
    ]


def _ok_response(output: list[dict], status: str = "completed") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "resp_test",
            "status": status,
            "output": output,
            "usage": {"input_tokens": 5, "output_tokens": 7},
        },
    )


# ---------- Request shape ----------


async def test_generate_targets_responses_endpoint() -> None:
    """Adapter targets `/v1/responses`, not `/v1/chat/completions`."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["path"] = request.url.path
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert captured["path"] == "/v1/responses"


async def test_generate_appends_native_web_search_tool() -> None:
    """When `web_search` is in native_tools, the Responses request
    includes `{"type":"web_search_preview"}` in its tools array.

    Note the wire-level type is `web_search_preview`, not `web_search` —
    that's the spec gpt-5.4 needs to actually emit url_citation
    annotations. The internal capability name we advertise (and the
    native_tools entry callers pass) stays `web_search`."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    assert {"type": "web_search_preview"} in captured["body"]["tools"]


async def test_generate_translates_chat_completions_tool_choice_to_responses_shape() -> None:
    """The runtime emits chat-completions-shape tool_choice for openai
    provider_kind: `{"type":"function","function":{"name":"X"}}`. The
    Responses API rejects the nested `function` object — it expects the
    flat shape `{"type":"function","name":"X"}`. The adapter must
    translate verbatim chat-shape into Responses-shape before POSTing,
    so the runtime doesn't need to know which inner endpoint the router
    will pick for this turn."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tools=[
                    ToolSchema(
                        name="submit_report",
                        description="submit",
                        parameters={"type": "object"},
                    ),
                ],
                tool_choice={
                    "type": "function",
                    "function": {"name": "submit_report"},
                },
            )
        )
    sent = captured["body"]["tool_choice"]
    assert sent == {"type": "function", "name": "submit_report"}, sent


async def test_generate_passes_string_tool_choice_through_unchanged() -> None:
    """String-form tool_choice values ("auto", "none", "required") are
    valid on both APIs and must not be mangled by the translation."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tool_choice="required",
            )
        )
    assert captured["body"]["tool_choice"] == "required"


async def test_generate_passes_already_flat_tool_choice_through_unchanged() -> None:
    """If a caller (or future runtime version) already emits the flat
    Responses-API shape, the adapter must leave it alone."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tool_choice={"type": "function", "name": "submit_report"},
            )
        )
    assert captured["body"]["tool_choice"] == {
        "type": "function",
        "name": "submit_report",
    }


async def test_generate_renders_function_tools_in_responses_shape() -> None:
    """Function-tool ToolSchema entries render as Responses-shape
    `{"type":"function","name":...,"parameters":...}` (top-level fields,
    NOT wrapped under `function`). And the generic `web_search`
    ToolSchema is dropped when native is on (G-6 defensive)."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tools=[
                    ToolSchema(
                        name="submit_report",
                        description="submit",
                        parameters={"type": "object"},
                    ),
                    ToolSchema(
                        name="web_search",  # leaked — should be dropped
                        description="generic",
                        parameters={"type": "object"},
                    ),
                ],
                native_tools=("web_search",),
            )
        )
    tools = captured["body"]["tools"]
    fn_entries = [t for t in tools if t.get("type") == "function"]
    assert len(fn_entries) == 1
    assert fn_entries[0]["name"] == "submit_report"
    assert "parameters" in fn_entries[0]
    web = [t for t in tools if t.get("type") == "web_search_preview"]
    assert len(web) == 1


# ---------- Conversation translation ----------


async def test_input_user_message_renders_as_input_text_part() -> None:
    """`Message(role="user", content="hi")` translates to
    `{"role":"user","content":[{"type":"input_text","text":"hi"}]}`."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert captured["body"]["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "hi"}]}
    ]


async def test_input_assistant_with_tool_calls_emits_function_call_items() -> None:
    """An assistant Message with tool_calls translates to a message
    item (when content is non-empty) followed by one `function_call`
    item per ToolCall, keyed by `call_id`."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[
                    Message(role="user", content="run X"),
                    Message(
                        role="assistant",
                        content="thinking...",
                        tool_calls=(
                            ToolCall(id="call_42", name="get_quote", arguments={"sym": "NVDA"}),
                        ),
                    ),
                ]
            )
        )
    items = captured["body"]["input"]
    # The user message; then the assistant message item; then the function_call.
    assert items[0]["role"] == "user"
    assert items[1] == {
        "role": "assistant",
        "content": [{"type": "output_text", "text": "thinking..."}],
    }
    assert items[2] == {
        "type": "function_call",
        "call_id": "call_42",
        "name": "get_quote",
        "arguments": json.dumps({"sym": "NVDA"}),
    }


async def test_openai_responses_conversation_translation_drops_prior_web_search_items() -> None:
    """Conversation replay across Responses turns must NOT carry prior
    `web_search_call` items into the next request's `input`. The
    canonical Message list carries assistant `content` (where the
    model has already integrated search results into output_text) and
    `tool_calls`; native server-side search items are dropped on
    translation (citations surface separately on LLMResponse)."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[
                    Message(role="user", content="What's new with NVDA?"),
                    # Prior assistant turn — its web_search produced citations
                    # that the model already wove into output_text. The
                    # canonical Message carries only `content`; no
                    # web_search_call item exists.
                    Message(
                        role="assistant",
                        content="Nvidia announced H300 [Reuters].",
                    ),
                    Message(role="user", content="follow-up: timeline?"),
                ]
            )
        )
    items = captured["body"]["input"]
    types = [it.get("type") for it in items]
    assert "web_search_call" not in types
    assert all(it.get("type") != "web_search_call" for it in items)
    # Prior assistant text is replayed as output_text.
    assistant_items = [it for it in items if it.get("role") == "assistant"]
    assert len(assistant_items) == 1
    assert assistant_items[0]["content"][0]["type"] == "output_text"
    assert "H300" in assistant_items[0]["content"][0]["text"]


async def test_input_tool_result_emits_function_call_output() -> None:
    """A `role="tool"` Message translates to a `function_call_output`
    input item paired by `call_id`."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[
                    Message(role="tool", content="result-json", tool_call_id="call_42"),
                ]
            )
        )
    assert captured["body"]["input"] == [
        {"type": "function_call_output", "call_id": "call_42", "output": "result-json"}
    ]


# ---------- Response parsing ----------


async def test_generate_concatenates_output_text_parts() -> None:
    output = [
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "output_text", "text": "Hello "},
                {"type": "output_text", "text": "world."},
            ],
        }
    ]
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(return_value=_ok_response(output))
        resp = await _adapter().generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.text == "Hello world."


async def test_generate_parses_function_call_items_into_tool_calls() -> None:
    output = [
        {
            "type": "function_call",
            "call_id": "call_abc",
            "name": "submit_report",
            "arguments": json.dumps({"ok": True}),
        }
    ]
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(return_value=_ok_response(output))
        resp = await _adapter().generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].id == "call_abc"
    assert resp.tool_calls[0].name == "submit_report"
    assert resp.tool_calls[0].arguments == {"ok": True}


async def test_generate_records_web_search_call_as_server_tool_call() -> None:
    """`web_search_call` output items populate server_tool_calls; NEVER
    enter LLMResponse.tool_calls (the runtime would try to dispatch
    them, which is wrong — Responses runs the search server-side)."""
    output = [
        {"type": "web_search_call", "id": "ws_01", "status": "completed"},
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "found it"}],
        },
    ]
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(return_value=_ok_response(output))
        resp = await _adapter().generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    assert resp.tool_calls == []
    assert len(resp.server_tool_calls) == 1
    assert resp.server_tool_calls[0].name == "web_search"


async def test_generate_parses_url_citation_annotations() -> None:
    """`url_citation` annotations on output_text parts become Citation
    entries with kind="web", source="OpenAI Web Search", and
    segment_start/end from start_index/end_index."""
    output = [
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": "NVDA rallied this week per recent reports.",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "start_index": 0,
                            "end_index": 12,
                            "url": "https://reuters.com/nvda",
                            "title": "Reuters",
                        },
                        {
                            "type": "url_citation",
                            "start_index": 28,
                            "end_index": 42,
                            "url": "https://ft.com/nvda",
                            "title": "FT",
                        },
                    ],
                }
            ],
        }
    ]
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(return_value=_ok_response(output))
        resp = await _adapter().generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    triples = [(c.url, c.segment_start, c.segment_end) for c in resp.citations]
    assert ("https://reuters.com/nvda", 0, 12) in triples
    assert ("https://ft.com/nvda", 28, 42) in triples
    assert all(c.kind == "web" for c in resp.citations)
    assert all(c.source == "OpenAI Web Search" for c in resp.citations)


async def test_generate_detects_failed_web_search_call() -> None:
    """A `web_search_call` with `status: "failed"` produces a
    FailedSearch on server_tool_failures. The runtime's I-a rescue
    consumes these to route to the configured adapter."""
    output = [
        {
            "type": "web_search_call",
            "id": "ws_99",
            "status": "failed",
            "action": {"query": "blocked query"},
        }
    ]
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(return_value=_ok_response(output))
        resp = await _adapter().generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    assert len(resp.server_tool_failures) == 1
    f = resp.server_tool_failures[0]
    assert f.query == "blocked query"
    assert f.error_kind in {"server_error", "unknown"}


# ---------- Unified streaming: real Responses SSE ----------


import httpx as _httpx  # noqa: E402


async def test_stream_yields_text_deltas_from_response_output_text_delta() -> None:
    """The Responses SSE stream emits `response.output_text.delta` frames
    whose `delta` field carries the next text chunk. Concatenated they
    rebuild the assistant message."""
    sse = (
        b'data: {"type":"response.output_text.delta","delta":"Hello "}\n\n'
        b'data: {"type":"response.output_text.delta","delta":"world"}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_httpx.Response(
                200, content=sse, headers={"content-type": "text/event-stream"}
            )
        )
        chunks = []
        async for c in _adapter().stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert "".join(c.delta for c in chunks) == "Hello world"


async def test_stream_emits_server_tool_invoked_on_web_search_in_progress() -> None:
    """A `response.web_search_call.in_progress` event yields a
    ServerToolEvent(kind="invoked", provider="openai"). Query is
    pulled from the item's `action.query` when present."""
    sse = (
        b'data: {"type":"response.web_search_call.in_progress",'
        b'"item":{"action":{"query":"NVDA earnings"}}}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_httpx.Response(
                200, content=sse, headers={"content-type": "text/event-stream"}
            )
        )
        chunks = []
        async for c in _adapter().stream(
            LLMRequest(
                messages=[Message(role="user", content="x")],
                native_tools=("web_search",),
            )
        ):
            chunks.append(c)
    invoked = [c for c in chunks if c.server_tool_event and c.server_tool_event.kind == "invoked"]
    assert len(invoked) == 1
    e = invoked[0].server_tool_event
    assert e.provider == "openai"
    assert e.query == "NVDA earnings"


async def test_stream_emits_server_tool_completed_on_web_search_completed() -> None:
    """A `response.web_search_call.completed` event yields a
    ServerToolEvent(kind="completed", provider="openai"). Result urls
    are not in this event — they arrive later as url_citation
    annotations — so urls=() and n_results is omitted/None."""
    sse = (
        b'data: {"type":"response.web_search_call.in_progress",'
        b'"item":{"action":{"query":"q"}}}\n\n'
        b'data: {"type":"response.web_search_call.completed",'
        b'"item":{"status":"completed"}}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_httpx.Response(
                200, content=sse, headers={"content-type": "text/event-stream"}
            )
        )
        chunks = []
        async for c in _adapter().stream(
            LLMRequest(
                messages=[Message(role="user", content="x")],
                native_tools=("web_search",),
            )
        ):
            chunks.append(c)
    completed = [
        c for c in chunks if c.server_tool_event and c.server_tool_event.kind == "completed"
    ]
    assert len(completed) == 1
    assert completed[0].server_tool_event.provider == "openai"


async def test_stream_terminal_chunk_carries_finish_reason() -> None:
    """`response.completed` ends the stream; the adapter emits a
    terminal LLMChunk with `finish_reason` set so callers see EOS."""
    sse = (
        b'data: {"type":"response.output_text.delta","delta":"x"}\n\n'
        b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(
            return_value=_httpx.Response(
                200, content=sse, headers={"content-type": "text/event-stream"}
            )
        )
        chunks = []
        async for c in _adapter().stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert chunks[-1].finish_reason == "completed"


async def test_stream_targets_responses_endpoint_with_stream_true() -> None:
    """Streaming POSTs `/v1/responses` with `"stream": true` in the body."""
    captured: dict = {}

    def _capture(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.read())
        return _httpx.Response(
            200,
            content=b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        async for _ in _adapter().stream(LLMRequest(messages=[Message(role="user", content="x")])):
            pass
    assert captured["path"] == "/v1/responses"
    assert captured["body"]["stream"] is True


async def test_generate_preserves_instructions_across_calls() -> None:
    """Two sequential generate() calls with the same system prompt must
    produce a byte-identical `instructions` field, so the Responses API
    auto-cache can hit on the static prefix."""
    adapter = _adapter()
    captured: list[dict] = []

    def _capture(request):
        captured.append(json.loads(request.read()))
        return _ok_response(_assistant_ok())

    system = "static prefix\n<!-- OPENLIA_CACHE_BREAKPOINT -->\ndynamic suffix"
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        for _ in range(2):
            await adapter.generate(
                LLMRequest(system=system, messages=[Message(role="user", content="hi")])
            )
    assert captured[0]["instructions"] == captured[1]["instructions"]
    assert "static prefix" in captured[0]["instructions"]


async def test_generate_surfaces_cached_input_tokens() -> None:
    """OpenAI Responses returns cached prefix counts under
    `usage.input_tokens_details.cached_tokens`. The adapter must expose
    that value on LLMResponse so the runtime can record cache hits."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").respond(
            200,
            json={
                "id": "resp_test",
                "status": "completed",
                "output": _assistant_ok(),
                "usage": {
                    "input_tokens": 80_000,
                    "output_tokens": 200,
                    "input_tokens_details": {"cached_tokens": 76_000},
                },
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.input_tokens == 80_000
    assert resp.cached_input_tokens == 76_000


async def test_generate_defaults_cached_input_tokens_to_zero_when_absent() -> None:
    """When the provider response does not report cache details, the
    field falls back to 0 so downstream consumers can always read it."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(
            side_effect=lambda r: _ok_response(_assistant_ok())
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.cached_input_tokens == 0


async def test_generate_sends_reasoning_effort_as_nested_object() -> None:
    """Responses API takes reasoning as `{"effort": "<value>"}`, not the
    flat `reasoning_effort` field used by Chat Completions."""
    from openlia.llm.types import ReasoningEffort

    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )
    assert captured.get("reasoning") == {"effort": "high"}


async def test_generate_omits_reasoning_block_when_effort_none() -> None:
    """Default (reasoning_effort=None) must NOT emit the reasoning block —
    sending it against a non-reasoning model returns 400."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        return _ok_response(_assistant_ok())

    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert "reasoning" not in captured


async def test_generate_surfaces_reasoning_output_tokens_from_usage() -> None:
    """Responses API exposes reasoning-token count at
    `usage.output_tokens_details.reasoning_tokens`. Must surface as
    LLMResponse.reasoning_output_tokens for the sized-from-data pass."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").respond(
            200,
            json={
                "id": "resp_test",
                "status": "completed",
                "output": _assistant_ok(),
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 800,
                    "output_tokens_details": {"reasoning_tokens": 650},
                },
            },
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.output_tokens == 800
    assert resp.reasoning_output_tokens == 650


async def test_generate_defaults_reasoning_output_tokens_to_zero_when_absent() -> None:
    """When the response omits output_tokens_details, the field defaults
    to 0 so consumers can always read it."""
    adapter = _adapter()
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(
            side_effect=lambda r: _ok_response(_assistant_ok())
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.reasoning_output_tokens == 0


async def test_multi_turn_cache_hit_rate_at_least_fifty_percent_from_turn_two() -> None:
    """Replay-style assertion: across a 3-turn report-style run where the
    provider auto-caches the static prefix, cumulative cached_input_tokens
    starting from turn 2 must be at least 50% of cumulative input_tokens.

    The mock simulates realistic numbers — 0% cache on turn 0 (first call
    warms the cache), then >=90% cache on turns 1 and 2 once the prefix
    is established. The test guards the wire path adapter→LLMResponse so
    a regression that drops cache details would surface here too."""
    adapter = _adapter()
    turn_responses = [
        # Turn 0: cold prefix, no cache.
        {"input_tokens": 80_000, "output_tokens": 200, "cached": 0},
        # Turn 1: prefix now cacheable; suffix added by tool result.
        {"input_tokens": 95_000, "output_tokens": 300, "cached": 75_000},
        # Turn 2: same stable prefix; new suffix.
        {"input_tokens": 100_000, "output_tokens": 250, "cached": 80_000},
    ]
    iter_responses = iter(turn_responses)

    def _serve(request):
        u = next(iter_responses)
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "status": "completed",
                "output": _assistant_ok(),
                "usage": {
                    "input_tokens": u["input_tokens"],
                    "output_tokens": u["output_tokens"],
                    "input_tokens_details": {"cached_tokens": u["cached"]},
                },
            },
        )

    collected: list = []
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/responses").mock(side_effect=_serve)
        for _ in range(3):
            collected.append(
                await adapter.generate(LLMRequest(messages=[Message(role="user", content="x")]))
            )

    # Per-turn surface assertions.
    assert [r.cached_input_tokens for r in collected] == [0, 75_000, 80_000]

    # Cumulative hit rate from turn 2 onward (turns 1..2 in zero-indexed).
    total_input_after_turn_one = sum(r.input_tokens for r in collected[1:])
    total_cached_after_turn_one = sum(r.cached_input_tokens for r in collected[1:])
    assert total_cached_after_turn_one / total_input_after_turn_one >= 0.5
