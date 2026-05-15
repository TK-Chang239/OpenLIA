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
    ToolSchema,
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


async def test_generate_forwards_tool_choice_as_tool_config() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "submit_report",
                                        "args": {"ok": True},
                                    }
                                }
                            ]
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(side_effect=_capture)
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
                tool_choice={
                    "function_calling_config": {
                        "mode": "ANY",
                        "allowed_function_names": ["submit_report"],
                    }
                },
            )
        )
    assert captured["body"]["toolConfig"] == {
        "function_calling_config": {
            "mode": "ANY",
            "allowed_function_names": ["submit_report"],
        }
    }


async def test_generate_omits_tool_config_when_unset() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "hi"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert "toolConfig" not in captured["body"]


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


# ---------- Phase 2: native Grounding with Google Search ----------


def _gemini_ok(content_text: str, *, grounding_metadata: dict | None = None) -> httpx.Response:
    candidate: dict = {
        "content": {"parts": [{"text": content_text}]},
        "finishReason": "STOP",
    }
    if grounding_metadata is not None:
        candidate["groundingMetadata"] = grounding_metadata
    return httpx.Response(
        200,
        json={
            "candidates": [candidate],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
        },
    )


async def test_generate_appends_google_search_tool_when_native() -> None:
    """When LLMRequest.native_tools contains 'web_search', Gemini's
    native grounding tool `{"google_search": {}}` is appended to
    `tools`. Function tools and the native tool live in the same
    array (Gemini packs both under the single Tool union)."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _gemini_ok("ok")

    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="recent NVDA news")],
                native_tools=("web_search",),
            )
        )
    assert {"google_search": {}} in captured["body"]["tools"]


async def test_generate_combines_function_tools_with_google_search() -> None:
    """Function tools (rendered as a `functionDeclarations` entry) and
    the native `google_search` tool coexist in the same `tools` array.
    Gemini's API tolerates both styles in one request."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _gemini_ok("ok")

    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                tools=[
                    ToolSchema(
                        name="get_stock_quote",
                        description="quote",
                        parameters={"type": "object"},
                    ),
                ],
                native_tools=("web_search",),
            )
        )
    tools = captured["body"]["tools"]
    assert {"google_search": {}} in tools
    fn_decls = next(t["functionDeclarations"] for t in tools if "functionDeclarations" in t)
    assert any(d["name"] == "get_stock_quote" for d in fn_decls)


async def test_generate_omits_google_search_when_no_native_tools() -> None:
    """Regression guard: without native_tools, the payload never
    contains `{"google_search": {}}`. Today's behavior, pinned to
    catch future changes that flip the default."""
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        return _gemini_ok("ok")

    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(side_effect=_capture)
        await adapter.generate(LLMRequest(messages=[Message(role="user", content="hi")]))
    assert "tools" not in captured["body"] or all(
        "google_search" not in t for t in captured["body"]["tools"]
    )


async def test_generate_parses_grounding_chunks_into_citations() -> None:
    """`candidates[0].groundingMetadata.groundingChunks[i].web` becomes
    Citation(kind="web", source="Google Search", url=uri, title=title)
    on LLMResponse.citations."""
    adapter = _adapter()
    grounding = {
        "webSearchQueries": ["NVDA recent news"],
        "groundingChunks": [
            {"web": {"uri": "https://reuters.com/a", "title": "Reuters"}},
            {"web": {"uri": "https://ft.com/b", "title": "FT"}},
        ],
        "groundingSupports": [],
    }
    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(return_value=_gemini_ok("NVDA news.", grounding_metadata=grounding))
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
    assert all(c.source == "Google Search" for c in resp.citations)


async def test_generate_segments_citations_via_grounding_supports() -> None:
    """`groundingSupports[i]` ties a text segment to one or more chunk
    indices. The adapter expands each (support, chunk_idx) pair into a
    distinct Citation with `segment_start`/`segment_end` populated, so
    downstream renderers can place inline `[N]` markers at the right
    char offsets."""
    adapter = _adapter()
    grounding = {
        "webSearchQueries": ["q"],
        "groundingChunks": [
            {"web": {"uri": "https://a", "title": "A"}},
            {"web": {"uri": "https://b", "title": "B"}},
        ],
        "groundingSupports": [
            {
                "segment": {"startIndex": 0, "endIndex": 10, "text": "Span one"},
                "groundingChunkIndices": [0, 1],
            },
            {
                "segment": {"startIndex": 11, "endIndex": 20, "text": "Span two"},
                "groundingChunkIndices": [1],
            },
        ],
    }
    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(return_value=_gemini_ok("Span one and Span two", grounding_metadata=grounding))
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                native_tools=("web_search",),
            )
        )
    # 2 chunks always present as bare Citations (chunk-only). 2 supports x
    # (2+1) = 3 segmented Citations on top. The adapter is free to
    # consolidate or duplicate; we assert the segmented ones exist with
    # the right (url, segment_start, segment_end) triplets.
    segmented = [
        (c.url, c.segment_start, c.segment_end)
        for c in resp.citations
        if c.segment_start is not None
    ]
    assert ("https://a", 0, 10) in segmented
    assert ("https://b", 0, 10) in segmented
    assert ("https://b", 11, 20) in segmented
