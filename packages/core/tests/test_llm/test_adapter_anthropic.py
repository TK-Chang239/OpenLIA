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


async def test_generate_forwards_tool_choice_when_set() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "submit_report",
                        "input": {"ok": True},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
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
            json={
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
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
            json={
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
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
        json={
            "content": content,
            "stop_reason": stop_reason,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
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
    assert body["tools"] == [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": 7}
    ]


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
        mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=_ok_response(content)
        )
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
        mock.post("https://api.anthropic.com/v1/messages").mock(
            return_value=_ok_response(content)
        )
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
