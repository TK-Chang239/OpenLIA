from __future__ import annotations

import json

import httpx
import respx
from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
    ToolSchema,
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


def _sse_from_events(events: list[dict]) -> bytes:
    """Render a list of SSE event dicts into an Anthropic `data:`-line body."""
    return b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events)


def _sse_from_message(
    content: list[dict],
    *,
    stop_reason: str = "end_turn",
    usage: dict | None = None,
) -> bytes:
    """Render a full logical message (content blocks + stop_reason + usage)
    into the Anthropic SSE event stream the streaming endpoint emits, so a
    `generate` call reassembles it back into the same logical message."""
    usage = usage or {"input_tokens": 1, "output_tokens": 1}
    events: list[dict] = [
        {
            "type": "message_start",
            "message": {
                "usage": {
                    "input_tokens": usage.get("input_tokens", 0),
                    "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                }
            },
        }
    ]
    for idx, block in enumerate(content):
        btype = block.get("type")
        if btype == "text":
            events.append(
                {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {"type": "text", "text": ""},
                }
            )
            events.append(
                {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {"type": "text_delta", "text": block.get("text", "")},
                }
            )
        elif btype in ("tool_use", "server_tool_use"):
            events.append(
                {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {
                        "type": btype,
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "input": {},
                    },
                }
            )
            events.append(
                {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(block.get("input") or {}),
                    },
                }
            )
        else:
            events.append(
                {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": block,
                }
            )
        events.append({"type": "content_block_stop", "index": idx})
    events.append(
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason},
            "usage": {"output_tokens": usage.get("output_tokens", 0)},
        }
    )
    events.append({"type": "message_stop"})
    return _sse_from_events(events)


_SSE_HEADERS = {"content-type": "text/event-stream"}


async def test_generate_streams_and_reassembles_text_and_tool_use() -> None:
    """`generate` fetches via the streaming endpoint and reassembles the
    same logical message (text + tool_use + stop_reason + usage) the
    non-streaming endpoint would have returned."""
    adapter = _adapter()
    sse = _sse_from_events(
        [
            {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "Hello "},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "write_section",
                    "input": {},
                },
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": '{"section_id":"overview",'},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": '"markdown":"x"}'},
            },
            {"type": "content_block_stop", "index": 1},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "tool_use"},
                "usage": {"output_tokens": 5},
            },
            {"type": "message_stop"},
        ]
    )
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            200, content=sse, headers={"content-type": "text/event-stream"}
        )
        resp = await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.text == "Hello "
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "write_section"
    assert resp.tool_calls[0].arguments == {"section_id": "overview", "markdown": "x"}
    assert resp.tool_calls[0].id == "t1"
    assert resp.finish_reason == "tool_use"
    assert resp.input_tokens == 10
    assert resp.output_tokens == 5


async def test_generate_happy_path_separates_system_from_messages() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return httpx.Response(
            200,
            content=_sse_from_message(
                [{"type": "text", "text": "hello"}],
                usage={"input_tokens": 5, "output_tokens": 2},
            ),
            headers=_SSE_HEADERS,
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


async def test_generate_forwards_tool_choice_when_set() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return httpx.Response(
            200,
            content=_sse_from_message(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "submit_report",
                        "input": {"ok": True},
                    }
                ],
                stop_reason="tool_use",
            ),
            headers=_SSE_HEADERS,
        )

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tools=[
                    ToolSchema(
                        name="submit_report",
                        description="Submit the final report.",
                        parameters={"type": "object", "properties": {}},
                    )
                ],
                tool_choice={"type": "tool", "name": "submit_report"},
            )
        )
    body = json.loads(captured["payload"])
    assert body["tool_choice"] == {"type": "tool", "name": "submit_report"}


async def test_generate_omits_tool_choice_when_unset() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return httpx.Response(
            200,
            content=_sse_from_message([{"type": "text", "text": "ok"}]),
            headers=_SSE_HEADERS,
        )

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    body = json.loads(captured["payload"])
    assert "tool_choice" not in body


async def test_generate_includes_api_key_header() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            content=_sse_from_message([{"type": "text", "text": "ok"}]),
            headers=_SSE_HEADERS,
        )

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
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


async def test_stream_yields_text_deltas_and_terminal_stop_reason() -> None:
    adapter = _adapter()
    sse_body = (
        b"event: content_block_delta\n"
        b'data: {"type":"content_block_delta","index":0,'
        b'"delta":{"type":"text_delta","text":"Hello"}}\n\n'
        b"event: content_block_delta\n"
        b'data: {"type":"content_block_delta","index":0,'
        b'"delta":{"type":"text_delta","text":" world"}}\n\n'
        b"event: message_delta\n"
        b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n'
        b"event: message_stop\n"
        b'data: {"type":"message_stop"}\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            200, content=sse_body, headers={"content-type": "text/event-stream"}
        )
        chunks = []
        async for c in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert "".join(c.delta for c in chunks) == "Hello world"
    assert chunks[-1].finish_reason == "end_turn"


async def test_stream_sends_stream_true_in_payload() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            content=b'event: message_stop\ndata: {"type":"message_stop"}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        async for _ in adapter.stream(LLMRequest(messages=[Message(role="user", content="x")])):
            pass
    assert captured["body"]["stream"] is True


# ---------- Phase 1: native web_search (server-side tool) ----------


def _ok_response(content: list[dict], stop_reason: str = "end_turn") -> httpx.Response:
    return httpx.Response(
        200,
        content=_sse_from_message(content, stop_reason=stop_reason),
        headers=_SSE_HEADERS,
    )


async def test_generate_appends_native_web_search_tool_block() -> None:
    """When LLMRequest.native_tools contains 'web_search', the adapter
    appends Anthropic's native server-side tool block alongside any
    function-tools. The `max_uses` field carries the per-run budget
    from the runtime."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return _ok_response([{"type": "text", "text": "ok"}])

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="recent NVDA news")],
                native_tools=("web_search",),
                web_search_max_uses=7,
            )
        )
    body = json.loads(captured["payload"])
    assert body["tools"] == [{"type": "web_search_20250305", "name": "web_search", "max_uses": 7}]


async def test_generate_uses_default_max_uses_when_unspecified() -> None:
    """`web_search_max_uses=None` defaults to 5 on the native block.
    Conservative default keeps server-side cost bounded when the
    runtime omits the budget."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return _ok_response([{"type": "text", "text": "ok"}])

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    body = json.loads(captured["payload"])
    assert body["tools"][0]["max_uses"] == 5


async def test_generate_omits_generic_web_search_envelope_when_native() -> None:
    """Defensive: even if a ToolSchema named 'web_search' leaks into
    request.tools, the adapter drops it and ships only the native form.
    Guardrail G-6 at adapter level."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return _ok_response([{"type": "text", "text": "ok"}])

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tools=[
                    ToolSchema(
                        name="web_search",
                        description="generic",
                        parameters={"type": "object"},
                    ),
                    ToolSchema(
                        name="submit_report",
                        description="submit",
                        parameters={"type": "object"},
                    ),
                ],
                native_tools=("web_search",),
            )
        )
    body = json.loads(captured["payload"])
    names = [t.get("name") for t in body["tools"]]
    # Only one entry named web_search, and it's the native form.
    assert names.count("web_search") == 1
    web_search_entry = next(t for t in body["tools"] if t["name"] == "web_search")
    assert web_search_entry.get("type") == "web_search_20250305"
    assert "submit_report" in names


async def test_generate_records_server_tool_use_separately_from_tool_calls() -> None:
    """server_tool_use blocks (Anthropic's marker for native search
    invocations) populate LLMResponse.server_tool_calls. Regular
    function tool_use blocks still flow through tool_calls. The two
    never mix."""
    adapter = _adapter()
    content = [
        {
            "type": "server_tool_use",
            "id": "srvtoolu_01",
            "name": "web_search",
            "input": {"query": "NVDA recent news"},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": "srvtoolu_01",
            "content": [
                {
                    "type": "web_search_result",
                    "url": "https://reuters.com/nvda",
                    "title": "NVDA jumps on AI capex",
                    "page_age": "2 days",
                }
            ],
        },
        {"type": "text", "text": "NVDA rallied this week."},
        {
            "type": "tool_use",
            "id": "toolu_99",
            "name": "submit_report",
            "input": {"ok": True},
        },
    ]
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=_ok_response(content, stop_reason="tool_use")
        )
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    assert [c.name for c in resp.tool_calls] == ["submit_report"]
    assert len(resp.server_tool_calls) == 1
    assert resp.server_tool_calls[0].name == "web_search"
    assert resp.server_tool_calls[0].arguments == {"query": "NVDA recent news"}


async def test_generate_extracts_citations_from_web_search_results() -> None:
    """Each web_search_result inside web_search_tool_result.content
    becomes a Citation(kind="web", source="Anthropic Web Search") on
    LLMResponse.citations. Available downstream for the report
    schema's citations slot."""
    adapter = _adapter()
    content = [
        {
            "type": "server_tool_use",
            "id": "srv1",
            "name": "web_search",
            "input": {"query": "q"},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": "srv1",
            "content": [
                {
                    "type": "web_search_result",
                    "url": "https://reuters.com/a",
                    "title": "Reuters article",
                    "page_age": "1 day",
                },
                {
                    "type": "web_search_result",
                    "url": "https://ft.com/b",
                    "title": "FT report",
                    "page_age": "3 days",
                },
            ],
        },
        {"type": "text", "text": "Two findings."},
    ]
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(return_value=_ok_response(content))
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    urls = [c.url for c in resp.citations]
    assert "https://reuters.com/a" in urls
    assert "https://ft.com/b" in urls
    assert all(c.kind == "web" for c in resp.citations)
    assert all(c.source == "Anthropic Web Search" for c in resp.citations)


async def test_generate_detects_web_search_tool_result_error_as_failed_search() -> None:
    """A web_search_tool_result whose content is a
    web_search_tool_result_error becomes a FailedSearch on
    LLMResponse.server_tool_failures. The runtime's I-a rescue path
    (Phase 0) consumes this to re-route to the configured adapter."""
    adapter = _adapter()
    content = [
        {
            "type": "server_tool_use",
            "id": "srv1",
            "name": "web_search",
            "input": {"query": "blocked query"},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": "srv1",
            "content": {
                "type": "web_search_tool_result_error",
                "error_code": "too_many_requests",
            },
        },
    ]
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(return_value=_ok_response(content))
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    assert len(resp.server_tool_failures) == 1
    f = resp.server_tool_failures[0]
    assert f.query == "blocked query"
    assert f.error_kind == "rate_limit"


# ---------- Unified streaming: ServerToolEvent ----------


async def test_stream_emits_server_tool_invoked_with_query() -> None:
    """When a `server_tool_use` content block streams in via
    content_block_start + input_json_delta(s) + content_block_stop,
    the adapter emits one ServerToolEvent(kind="invoked", provider=
    "anthropic", query=<accumulated>) on the LLMChunk that
    coincides with the closing content_block_stop."""
    sse = (
        b'data: {"type":"content_block_start","index":1,'
        b'"content_block":{"type":"server_tool_use","id":"srvtoolu_01",'
        b'"name":"web_search","input":{}}}\n\n'
        b'data: {"type":"content_block_delta","index":1,'
        b'"delta":{"type":"input_json_delta","partial_json":"{\\"query\\":\\""}}\n\n'
        b'data: {"type":"content_block_delta","index":1,'
        b'"delta":{"type":"input_json_delta","partial_json":"NVDA earnings\\"}"}}\n\n'
        b'data: {"type":"content_block_stop","index":1}\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            200, content=sse, headers={"content-type": "text/event-stream"}
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
    assert e.provider == "anthropic"
    assert e.query == "NVDA earnings"


async def test_stream_emits_server_tool_completed_with_urls() -> None:
    """When a `web_search_tool_result` content block arrives, the
    adapter emits one ServerToolEvent(kind="completed", urls=<...>,
    n_results=<len>) on a chunk."""
    sse = (
        b'data: {"type":"content_block_start","index":2,'
        b'"content_block":{"type":"web_search_tool_result",'
        b'"tool_use_id":"srvtoolu_01","content":['
        b'{"type":"web_search_result","url":"https://reuters.com/a","title":"R"},'
        b'{"type":"web_search_result","url":"https://ft.com/b","title":"F"}'
        b"]}}\n\n"
    )
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            200, content=sse, headers={"content-type": "text/event-stream"}
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
    e = completed[0].server_tool_event
    assert e.provider == "anthropic"
    assert e.n_results == 2
    assert e.urls == ("https://reuters.com/a", "https://ft.com/b")


async def test_generate_surfaces_cached_input_tokens() -> None:
    """Anthropic returns cache-read counts under
    `usage.cache_read_input_tokens`. Surface them on LLMResponse."""
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            200,
            content=_sse_from_message(
                [{"type": "text", "text": "hi"}],
                usage={
                    "input_tokens": 5_000,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 4_800,
                },
            ),
            headers=_SSE_HEADERS,
        )
        resp = await _adapter().generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.cached_input_tokens == 4_800


async def test_generate_defaults_cached_input_tokens_to_zero_when_absent() -> None:
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            200,
            content=_sse_from_message(
                [{"type": "text", "text": "hi"}],
                usage={"input_tokens": 5, "output_tokens": 2},
            ),
            headers=_SSE_HEADERS,
        )
        resp = await _adapter().generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert resp.cached_input_tokens == 0


def _msg_response() -> httpx.Response:
    return httpx.Response(
        200,
        content=_sse_from_message([{"type": "text", "text": "ok"}]),
        headers=_SSE_HEADERS,
    )


async def test_generate_emits_thinking_block_on_supported_model() -> None:
    """Claude 4.x models accept `thinking={"type":"enabled","budget_tokens":N}`.
    medium → 8192, high → 32768 per the adapter's effort-to-budget map."""
    from openlia.llm.types import ReasoningEffort

    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        return _msg_response()

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await _adapter(model="claude-sonnet-4-6").generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )
    assert captured.get("thinking") == {"type": "enabled", "budget_tokens": 32768}
    # Anthropic requires temperature=1.0 with thinking enabled — adapter
    # must override whatever the caller set.
    assert captured.get("temperature") == 1.0


async def test_generate_thinking_block_medium_uses_8192_budget() -> None:
    from openlia.llm.types import ReasoningEffort

    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        return _msg_response()

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await _adapter(model="claude-opus-4-1").generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                reasoning_effort=ReasoningEffort.MEDIUM,
            )
        )
    assert captured["thinking"] == {"type": "enabled", "budget_tokens": 8192}


async def test_generate_omits_thinking_block_when_effort_none() -> None:
    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        return _msg_response()

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await _adapter(model="claude-sonnet-4-6").generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert "thinking" not in captured


async def test_generate_omits_thinking_block_on_unsupported_model() -> None:
    """Claude 3.5 sonnet (and earlier) don't accept the thinking directive —
    sending it returns 400. Adapter must drop the field on unsupported
    models even when the caller passed one."""
    from openlia.llm.types import ReasoningEffort

    captured: dict = {}

    def _capture(request):
        captured.update(json.loads(request.content))
        return _msg_response()

    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await _adapter(model="claude-3-5-sonnet-20241022").generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )
    assert "thinking" not in captured


async def test_stream_text_chunks_have_no_server_tool_event() -> None:
    """Plain text deltas must NOT set server_tool_event; otherwise the
    runtime would emit spurious ChatWebSearchInvoked events."""
    sse = (
        b'data: {"type":"content_block_delta","index":0,'
        b'"delta":{"type":"text_delta","text":"Hi"}}\n\n'
    )
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            200, content=sse, headers={"content-type": "text/event-stream"}
        )
        chunks = []
        async for c in _adapter().stream(LLMRequest(messages=[Message(role="user", content="x")])):
            chunks.append(c)
    assert all(c.server_tool_event is None for c in chunks)
    assert "".join(c.delta for c in chunks) == "Hi"


async def test_generate_retries_on_midstream_read_error() -> None:
    """A transient ReadError (connection reset) on the streaming call is
    the failure this whole change fixes. with_retries must retry with a
    fresh accumulator; the second attempt succeeds and returns the
    reassembled response — not the stale/partial first attempt."""
    adapter = _adapter()
    ok = httpx.Response(
        200,
        content=_sse_from_message([{"type": "text", "text": "recovered"}]),
        headers=_SSE_HEADERS,
    )
    with respx.mock() as mock:
        route = mock.post("https://api.anthropic.com/v1/messages")
        route.side_effect = [httpx.ReadError("connection reset mid-stream"), ok]
        resp = await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert resp.text == "recovered"
    assert route.call_count == 2
