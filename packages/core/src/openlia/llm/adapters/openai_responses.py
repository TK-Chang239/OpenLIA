"""OpenAI Responses API adapter.

Targets POST /v1/responses so we can opt into the native server-side
`{"type":"web_search"}` tool. The existing OpenAIAdapter (Chat
Completions) handles everything else; OpenAIRouter (Phase 3b) routes
between the two per-turn based on `LLMRequest.native_tools`.

The Responses API is OpenAI-compatible across providers — xAI's `/v1/
responses` accepts the same wire shape. This adapter is `base_url`-
parameterized so the same class serves both providers once xAI lands.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from openlia.llm.adapters._content import strip_cache_breakpoint
from openlia.llm.adapters._http import (
    TRANSIENT_NETWORK_ERRORS,
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.retry import with_retries
from openlia.llm.types import (
    Capabilities,
    Citation,
    FailedSearch,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    ProviderCredentials,
    ServerToolCall,
    ServerToolEvent,
    TestResult,
    ToolCall,
)

_DEFAULT_BASE_URL = "https://api.openai.com"
# OpenAI's Responses API has two web-search tool shapes:
#   - "web_search"          — performs search but does NOT emit
#                             url_citation annotations for gpt-5.4
#                             (observed empirically — search runs but 0
#                             citations come back).
#   - "web_search_preview"  — the newer spec gpt-5.4 needs to emit
#                             url_citation annotations inline with the
#                             response text. This is what the runtime
#                             actually wants: the citations are the
#                             whole point of native web search.
# The internal name we advertise stays "web_search" (Capabilities.web_search_native,
# request.native_tools); only the wire-level type sent to OpenAI changes.
_WEB_SEARCH_NATIVE_TYPE = "web_search_preview"


def _normalize_tool_choice(tc: object) -> object:
    """Translate chat-completions-shape tool_choice into Responses shape.

    The runtime emits the chat-completions form for OpenAI:
    `{"type":"function","function":{"name":"X"}}`. The Responses API
    rejects the nested `function` object with "Unknown parameter:
    'tool_choice.function'" and expects the flat form
    `{"type":"function","name":"X"}` instead. String forms ("auto",
    "none", "required") and already-flat dicts pass through unchanged.
    """
    if (
        isinstance(tc, dict)
        and tc.get("type") == "function"
        and isinstance(tc.get("function"), dict)
        and tc["function"].get("name")
    ):
        return {"type": "function", "name": tc["function"]["name"]}
    return tc


def _build_responses_tools(request: LLMRequest) -> list[dict] | None:
    """Render request.tools into Responses-shape tools array.

    Function tools render as top-level `{"type":"function","name":...,
    "parameters":...}` (Responses API does NOT wrap function tools
    under a `function` key the way Chat Completions does). When
    `web_search` is in `native_tools`, drop any function-tool entry of
    the same name (G-6 defensive) and append `{"type":"web_search"}`.
    """
    native = "web_search" in request.native_tools
    function_tools = request.tools or []
    if native:
        # Defensive: when native web_search is enabled, drop any
        # function-tool named "web_search" (the canonical name we
        # advertise) so it doesn't double up with the native tool.
        function_tools = [t for t in function_tools if t.name != "web_search"]

    tools: list[dict] = [
        {
            "type": "function",
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        for t in function_tools
    ]
    if native:
        tools.append({"type": _WEB_SEARCH_NATIVE_TYPE})
    return tools or None


def _to_responses_input(messages: list[Message]) -> list[dict]:
    """Translate canonical Message list into Responses API input items.

    `user` and `assistant` text messages render as `{role, content:
    [{type: input_text|output_text, text}]}`. Assistant tool calls
    render as one `{type: function_call, call_id, name, arguments}`
    item per ToolCall, AFTER the assistant message item (when content
    is non-empty). Tool results render as `{type:
    function_call_output, call_id, output}`.
    """
    items: list[dict] = []
    for m in messages:
        if m.role == "user":
            items.append({"role": "user", "content": [{"type": "input_text", "text": m.content}]})
        elif m.role == "assistant":
            if m.content:
                items.append(
                    {
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": m.content}],
                    }
                )
            for tc in m.tool_calls:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": tc.id,
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    }
                )
        elif m.role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": m.tool_call_id or "",
                    "output": m.content,
                }
            )
    return items


def _parse_responses_output(
    output: list[dict],
) -> tuple[
    list[str],
    list[ToolCall],
    tuple[ServerToolCall, ...],
    tuple[Citation, ...],
    tuple[FailedSearch, ...],
]:
    """Walk a Responses output array into the five canonical channels."""
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    server_tool_calls: list[ServerToolCall] = []
    citations: list[Citation] = []
    failures: list[FailedSearch] = []
    cit_counter = 0

    for item in output:
        itype = item.get("type")
        if itype == "message":
            for part in item.get("content") or []:
                if part.get("type") != "output_text":
                    continue
                text_parts.append(part.get("text", ""))
                for ann in part.get("annotations") or []:
                    if ann.get("type") != "url_citation":
                        continue
                    cit_counter += 1
                    citations.append(
                        Citation(
                            id=f"c{cit_counter}",
                            kind="web",
                            url=ann.get("url"),
                            title=ann.get("title"),
                            source="OpenAI Web Search",
                            segment_start=ann.get("start_index"),
                            segment_end=ann.get("end_index"),
                        )
                    )
        elif itype == "function_call":
            try:
                args = json.loads(item.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=item.get("call_id", ""),
                    name=item.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        elif itype == "web_search_call":
            action = item.get("action") or {}
            query = str(action.get("query", ""))
            status = item.get("status", "completed")
            if status == "failed":
                err = item.get("error") or {}
                error_code = str(err.get("code", "failed")) if isinstance(err, dict) else "failed"
                failures.append(
                    FailedSearch(
                        query=query,
                        error_kind="server_error",
                        error_message=error_code,
                        turn_idx=0,
                    )
                )
            else:
                server_tool_calls.append(
                    ServerToolCall(
                        name="web_search",
                        arguments={"query": query},
                        turn_idx=0,
                    )
                )
        # Unknown item types ignored — forward-compatible with future
        # OpenAI Responses additions.
    return text_parts, tool_calls, tuple(server_tool_calls), tuple(citations), tuple(failures)


class OpenAIResponsesAdapter(LLMProvider):
    kind = "openai_responses"

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        capabilities: Capabilities,
        base_url: str | None = None,
    ) -> None:
        super().__init__(credentials=credentials, model=model, capabilities=capabilities)
        self._base_url = base_url or credentials.base_url or _DEFAULT_BASE_URL

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.credentials.api_key}",
            "content-type": "application/json",
        }

    async def list_models(self) -> list[ModelInfo]:
        """Reuse the standard `/v1/models` endpoint — Responses uses
        the same model IDs as Chat Completions."""

        async def _call() -> list[ModelInfo]:
            async with make_client(base_url=self._base_url, headers=self._headers()) as client:
                try:
                    resp = await client.get("/v1/models")
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                data = resp.json()
                return [ModelInfo(id=m["id"], display_name=m["id"]) for m in data.get("data", [])]

        return await with_retries(_call)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "input": _to_responses_input(list(request.messages)),
        }
        if request.system:
            payload["instructions"] = strip_cache_breakpoint(request.system)
        if request.max_tokens:
            payload["max_output_tokens"] = request.max_tokens
        tools = _build_responses_tools(request)
        if tools is not None:
            payload["tools"] = tools
        if request.tool_choice is not None:
            payload["tool_choice"] = _normalize_tool_choice(request.tool_choice)
        # Responses API takes reasoning as a nested object. The model
        # silently ignores it when not a reasoning model, but only when
        # absent — sending `{"effort": "high"}` against gpt-4o returns
        # 400. Caller is responsible for guarding by model when needed
        # (v2_3_wiring scopes this to PLAN + SYNTHESIZE on gpt-5.4).
        if request.reasoning_effort is not None:
            payload["reasoning"] = {"effort": request.reasoning_effort.value}

        async def _post() -> dict:
            async with make_client(base_url=self._base_url, headers=self._headers()) as client:
                try:
                    resp = await client.post("/v1/responses", json=payload)
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                return resp.json()

        body = await with_retries(_post)

        (
            text_parts,
            tool_calls,
            server_tool_calls,
            citations,
            failures,
        ) = _parse_responses_output(body.get("output", []))
        usage = body.get("usage") or {}
        cached_tokens = int((usage.get("input_tokens_details") or {}).get("cached_tokens", 0))
        reasoning_tokens = int(
            (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
        )
        return LLMResponse(
            text="".join(text_parts),
            finish_reason=body.get("status", "completed"),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cached_input_tokens=cached_tokens,
            reasoning_output_tokens=reasoning_tokens,
            tool_calls=tool_calls,
            citations=citations,
            server_tool_calls=server_tool_calls,
            server_tool_failures=failures,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        """Real Responses-API SSE parsing.

        Recognized events:
          * `response.output_text.delta`      → text chunk
          * `response.web_search_call.in_progress` → ServerToolEvent("invoked")
          * `response.web_search_call.completed`   → ServerToolEvent("completed")
          * `response.completed`              → terminal chunk with finish_reason

        Unknown event types are ignored, keeping the adapter forward-
        compatible with future SSE additions from OpenAI.
        """
        payload: dict = {
            "model": self.model,
            "input": _to_responses_input(list(request.messages)),
            "stream": True,
        }
        if request.system:
            payload["instructions"] = strip_cache_breakpoint(request.system)
        if request.max_tokens:
            payload["max_output_tokens"] = request.max_tokens
        tools = _build_responses_tools(request)
        if tools is not None:
            payload["tools"] = tools
        if request.tool_choice is not None:
            payload["tool_choice"] = _normalize_tool_choice(request.tool_choice)
        if request.reasoning_effort is not None:
            payload["reasoning"] = {"effort": request.reasoning_effort.value}

        async with make_client(base_url=self._base_url, headers=self._headers()) as client:
            try:
                async with client.stream("POST", "/v1/responses", json=payload) as resp:
                    if resp.status_code != 200:
                        body_bytes = await resp.aread()
                        status_to_exception(
                            status_code=resp.status_code,
                            body_text=body_bytes.decode("utf-8", errors="replace"),
                            headers=dict(resp.headers),
                        )
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            continue
                        try:
                            evt = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        etype = evt.get("type")
                        if etype == "response.output_text.delta":
                            text = evt.get("delta") or ""
                            if text:
                                yield LLMChunk(delta=text)
                        elif etype == "response.web_search_call.in_progress":
                            item = evt.get("item") or {}
                            action = item.get("action") or {}
                            yield LLMChunk(
                                delta="",
                                server_tool_event=ServerToolEvent(
                                    kind="invoked",
                                    provider="openai",
                                    query=str(action.get("query", "")),
                                ),
                            )
                        elif etype == "response.web_search_call.completed":
                            yield LLMChunk(
                                delta="",
                                server_tool_event=ServerToolEvent(
                                    kind="completed",
                                    provider="openai",
                                ),
                            )
                        elif etype == "response.completed":
                            response_obj = evt.get("response") or {}
                            yield LLMChunk(
                                delta="",
                                finish_reason=response_obj.get("status", "completed"),
                            )
            except TRANSIENT_NETWORK_ERRORS as exc:
                raise wrap_httpx_error(exc) from exc

    async def test_connection(self, model: str) -> TestResult:
        t0 = time.monotonic()
        try:
            await self.generate(
                LLMRequest(
                    messages=[Message(role="user", content="ping")],
                    max_tokens=1,
                )
            )
        except Exception as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.monotonic() - t0) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.monotonic() - t0) * 1000),
            error_class=None,
            error_msg=None,
        )
