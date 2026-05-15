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
    includes `{"type":"web_search"}` in its tools array."""
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
    assert {"type": "web_search"} in captured["body"]["tools"]


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
    web = [t for t in tools if t.get("type") == "web_search"]
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
