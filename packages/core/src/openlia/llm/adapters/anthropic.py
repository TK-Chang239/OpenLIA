from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator

from openlia.llm.adapters._content import (
    apply_message_cache_breakpoint,
    render_anthropic_messages,
    split_at_cache_breakpoint,
)
from openlia.llm.adapters._http import (
    TRANSIENT_NETWORK_ERRORS,
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.retry import with_retries
from openlia.llm.types import (
    Citation,
    FailedSearch,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    ReasoningEffort,
    ServerToolCall,
    ServerToolEvent,
    TestResult,
    ToolCall,
)

# Models that accept the `thinking={"type":"enabled","budget_tokens":N}`
# directive. Sending the directive to any other model returns 400, so we
# guard at the adapter — the v2.3 wiring layer also gates on stage
# (PLAN + SYNTHESIZE only), but the guard here keeps the adapter usable
# from non-v2.3 callers without relying on caller discipline.
_THINKING_MODELS_RE = re.compile(r"claude-(opus|sonnet|haiku)-4|claude-3-7-sonnet")


def _supports_thinking(model: str) -> bool:
    return bool(_THINKING_MODELS_RE.search(model.lower()))


# Effort -> budget_tokens for the Anthropic thinking directive. These are
# placeholders mirroring the v2.3 _REASONING_OVERHEAD table; the eventual
# sized-from-data pass will replace them once we see real reasoning_tokens
# in production logs.
_REASONING_BUDGET_BY_EFFORT: dict[ReasoningEffort, int] = {
    ReasoningEffort.MEDIUM: 8192,
    ReasoningEffort.HIGH: 32768,
}

# Anthropic's native server-side web search tool. Documented at
# https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
_WEB_SEARCH_NATIVE_TYPE = "web_search_20250305"
_WEB_SEARCH_NATIVE_NAME = "web_search"
_WEB_SEARCH_DEFAULT_MAX_USES = 5

# Maps Anthropic's `web_search_tool_result_error.error_code` values onto
# the runtime's canonical `FailedSearch.error_kind`. `max_uses_exceeded`
# is intentionally excluded: it signals the budget the runtime set was
# reached server-side, not a failure, and should NOT trigger I-a rescue.
_WEB_SEARCH_ERROR_KIND: dict[str, str] = {
    "too_many_requests": "rate_limit",
    "unavailable": "server_error",
    "invalid_input": "unknown",
}


def _build_anthropic_tools(request: LLMRequest) -> list[dict] | None:
    """Render request.tools into Anthropic's tools array. When
    `web_search` is in `request.native_tools`, drop any function-tool
    entry with the same name (guardrail G-6 defensive) and append the
    native server-side block instead."""
    native_web_search = "web_search" in request.native_tools
    function_tools = request.tools or []
    if native_web_search:
        function_tools = [t for t in function_tools if t.name != _WEB_SEARCH_NATIVE_NAME]

    payload_tools: list[dict] = [
        {"name": t.name, "description": t.description, "input_schema": t.parameters}
        for t in function_tools
    ]
    if native_web_search:
        max_uses = request.web_search_max_uses or _WEB_SEARCH_DEFAULT_MAX_USES
        payload_tools.append(
            {"type": _WEB_SEARCH_NATIVE_TYPE, "name": _WEB_SEARCH_NATIVE_NAME, "max_uses": max_uses}
        )
    if not payload_tools:
        return None
    if request.cache_conversation:
        # Cache the (static, per-run) tools block: one breakpoint on the
        # last entry caches the whole array as a prefix every turn reuses.
        payload_tools[-1] = {**payload_tools[-1], "cache_control": {"type": "ephemeral"}}
    return payload_tools


def _parse_anthropic_content(
    content: list[dict],
) -> tuple[
    list[str],
    list[ToolCall],
    tuple[ServerToolCall, ...],
    tuple[Citation, ...],
    tuple[FailedSearch, ...],
]:
    """Walk a `/v1/messages` response's content blocks and split into
    the five output channels:
      * `text_parts`             plain text deltas, concatenated upstream
      * `tool_calls`             standard function-tool invocations
      * `server_tool_calls`      native server-side tool uses (telemetry only)
      * `citations`              web_search_result blocks → Citation
      * `server_tool_failures`   web_search_tool_result_error → FailedSearch

    Pairs each `web_search_tool_result` (or its error) with the
    `server_tool_use` block by `tool_use_id` so the failure's `query`
    field can be reconstructed from the original input.
    """
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    server_tool_calls: list[ServerToolCall] = []
    citations: list[Citation] = []
    failures: list[FailedSearch] = []
    # Pair-table: server_tool_use id → original input dict (carries `query`).
    server_use_by_id: dict[str, dict] = {}
    cit_counter = 0

    for block in content:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    arguments=block.get("input") or {},
                )
            )
        elif btype == "server_tool_use":
            server_input = block.get("input") or {}
            server_use_by_id[block.get("id", "")] = server_input
            server_tool_calls.append(
                ServerToolCall(
                    name=block.get("name", ""),
                    arguments=server_input,
                    turn_idx=0,
                )
            )
        elif btype == "web_search_tool_result":
            result_content = block.get("content")
            paired_input = server_use_by_id.get(block.get("tool_use_id", ""), {})
            if isinstance(result_content, dict) and (
                result_content.get("type") == "web_search_tool_result_error"
            ):
                error_code = str(result_content.get("error_code", ""))
                if error_code == "max_uses_exceeded":
                    # Budget signal, not a failure. Don't rescue.
                    continue
                failures.append(
                    FailedSearch(
                        query=str(paired_input.get("query", "")),
                        error_kind=_WEB_SEARCH_ERROR_KIND.get(error_code, "unknown"),
                        error_message=error_code,
                        turn_idx=0,
                    )
                )
            elif isinstance(result_content, list):
                for r in result_content:
                    if r.get("type") != "web_search_result":
                        continue
                    cit_counter += 1
                    citations.append(
                        Citation(
                            id=f"c{cit_counter}",
                            kind="web",
                            url=r.get("url"),
                            title=r.get("title"),
                            source="Anthropic Web Search",
                            date=r.get("page_age"),
                            snippet=r.get("encrypted_content"),
                        )
                    )
        # Unknown block types are ignored — forward-compatible with
        # future Anthropic content block additions.
    return text_parts, tool_calls, tuple(server_tool_calls), tuple(citations), tuple(failures)


_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"


def _build_system_with_cache_control(system: str) -> str | list[dict]:
    """Return Anthropic ``system`` payload, splitting at the cache breakpoint.

    When the rendered system prompt embeds the cache-breakpoint marker, return
    a two-block list with ``cache_control: {"type": "ephemeral"}`` on the
    static prefix so Anthropic caches everything up through that block across
    the 5-minute TTL. Otherwise return the original string unchanged so the
    payload stays backward-compatible.
    """
    static, dynamic = split_at_cache_breakpoint(system)
    if dynamic is None:
        return system
    return [
        {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic},
    ]


class AnthropicAdapter(LLMProvider):
    kind = "anthropic"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.credentials.api_key or "",
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }

    async def list_models(self) -> list[ModelInfo]:
        async def _call() -> list[ModelInfo]:
            async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
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
                return [
                    ModelInfo(
                        id=item["id"],
                        display_name=item.get("display_name") or item["id"],
                        context_window=item.get("context_window"),
                    )
                    for item in data.get("data", [])
                ]

        return await with_retries(_call)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": render_anthropic_messages(request.messages),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.cache_conversation:
            apply_message_cache_breakpoint(payload["messages"])
        if request.system:
            payload["system"] = _build_system_with_cache_control(request.system)
        if request.stop:
            payload["stop_sequences"] = request.stop
        anthropic_tools = _build_anthropic_tools(request)
        if anthropic_tools is not None:
            payload["tools"] = anthropic_tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        # Extended thinking: only emit on models that support it (non-
        # supporting models return 400). Anthropic *requires* temperature=1.0
        # when thinking is enabled and *requires* max_tokens > budget_tokens
        # — the v2_3 wiring grows max_tokens to base+overhead so the
        # inequality holds.
        if request.reasoning_effort is not None and _supports_thinking(self.model):
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": _REASONING_BUDGET_BY_EFFORT[request.reasoning_effort],
            }
            payload["temperature"] = 1.0
        # Stream the completion and reassemble the same `body` dict the
        # non-streaming endpoint would have returned. Streaming keeps bytes
        # flowing so long completions (big context + reasoning) don't hit a
        # mid-completion connection reset (httpx ReadError).
        payload["stream"] = True

        async def _stream_and_assemble() -> dict:
            content_by_index: dict[int, dict] = {}
            partial_json: dict[int, str] = {}
            input_tokens = 0
            output_tokens = 0
            cache_read_input_tokens = 0
            stop_reason: str | None = None

            async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
                try:
                    async with client.stream("POST", "/v1/messages", json=payload) as resp:
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
                            try:
                                evt = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            etype = evt.get("type")
                            if etype == "message_start":
                                usage = (evt.get("message") or {}).get("usage") or {}
                                input_tokens = int(usage.get("input_tokens", 0))
                                cache_read_input_tokens = int(
                                    usage.get("cache_read_input_tokens", 0)
                                )
                            elif etype == "content_block_start":
                                idx = evt.get("index", -1)
                                block = evt.get("content_block") or {}
                                btype = block.get("type")
                                if btype == "text":
                                    content_by_index[idx] = {
                                        "type": "text",
                                        "text": "",
                                        "citations": [],
                                    }
                                elif btype in ("tool_use", "server_tool_use"):
                                    content_by_index[idx] = {
                                        "type": btype,
                                        "id": block.get("id", ""),
                                        "name": block.get("name", ""),
                                        "input": {},
                                    }
                                    partial_json[idx] = ""
                                elif btype == "web_search_tool_result":
                                    content_by_index[idx] = {
                                        "type": "web_search_tool_result",
                                        "tool_use_id": block.get("tool_use_id", ""),
                                        "content": block.get("content"),
                                    }
                                elif btype in ("thinking", "redacted_thinking"):
                                    content_by_index[idx] = {"type": btype, "thinking": ""}
                                else:
                                    content_by_index[idx] = dict(block)
                            elif etype == "content_block_delta":
                                idx = evt.get("index", -1)
                                delta = evt.get("delta") or {}
                                dtype = delta.get("type")
                                if dtype == "text_delta":
                                    blk = content_by_index.get(idx)
                                    if blk is not None:
                                        blk["text"] = blk.get("text", "") + (
                                            delta.get("text") or ""
                                        )
                                elif dtype == "input_json_delta":
                                    if idx in partial_json:
                                        partial_json[idx] += delta.get("partial_json", "")
                                elif dtype == "thinking_delta":
                                    blk = content_by_index.get(idx)
                                    if blk is not None:
                                        blk["thinking"] = blk.get("thinking", "") + (
                                            delta.get("thinking") or ""
                                        )
                                elif dtype == "citations_delta":
                                    blk = content_by_index.get(idx)
                                    if blk is not None:
                                        blk.setdefault("citations", []).append(
                                            delta.get("citation")
                                        )
                            elif etype == "content_block_stop":
                                idx = evt.get("index", -1)
                                if idx in partial_json:
                                    raw = partial_json.pop(idx)
                                    try:
                                        parsed = json.loads(raw) if raw else {}
                                    except json.JSONDecodeError:
                                        parsed = {}
                                    if not isinstance(parsed, dict):
                                        parsed = {}
                                    blk = content_by_index.get(idx)
                                    if blk is not None:
                                        blk["input"] = parsed
                            elif etype == "message_delta":
                                stop = (evt.get("delta") or {}).get("stop_reason")
                                if stop:
                                    stop_reason = stop
                                usage = evt.get("usage") or {}
                                if "output_tokens" in usage:
                                    output_tokens = int(usage.get("output_tokens", 0))
                            elif etype == "message_stop":
                                break
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc

            return {
                "content": [content_by_index[i] for i in sorted(content_by_index)],
                "stop_reason": stop_reason or "end_turn",
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_read_input_tokens": cache_read_input_tokens,
                },
            }

        body = await with_retries(_stream_and_assemble)

        (
            text_parts,
            tool_calls,
            server_tool_calls,
            citations,
            server_tool_failures,
        ) = _parse_anthropic_content(body.get("content", []))
        usage = body.get("usage") or {}
        return LLMResponse(
            text="".join(text_parts),
            finish_reason=body.get("stop_reason", "end_turn"),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cached_input_tokens=int(usage.get("cache_read_input_tokens", 0)),
            tool_calls=tool_calls,
            citations=citations,
            server_tool_calls=server_tool_calls,
            server_tool_failures=server_tool_failures,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        payload: dict = {
            "model": self.model,
            "messages": render_anthropic_messages(request.messages),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }
        if request.cache_conversation:
            apply_message_cache_breakpoint(payload["messages"])
        if request.system:
            payload["system"] = _build_system_with_cache_control(request.system)
        if request.stop:
            payload["stop_sequences"] = request.stop
        anthropic_tools = _build_anthropic_tools(request)
        if anthropic_tools is not None:
            payload["tools"] = anthropic_tools
        if request.reasoning_effort is not None and _supports_thinking(self.model):
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": _REASONING_BUDGET_BY_EFFORT[request.reasoning_effort],
            }
            payload["temperature"] = 1.0

        async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
            try:
                async with client.stream("POST", "/v1/messages", json=payload) as resp:
                    if resp.status_code != 200:
                        body_bytes = await resp.aread()
                        status_to_exception(
                            status_code=resp.status_code,
                            body_text=body_bytes.decode("utf-8", errors="replace"),
                            headers=dict(resp.headers),
                        )
                    # Server-side tool blocks (`server_tool_use`) carry
                    # their arguments via `input_json_delta` between
                    # content_block_start and content_block_stop. We
                    # buffer the partial JSON per block index and emit
                    # ServerToolEvent("invoked") at block_stop.
                    server_use_buf: dict[int, str] = {}
                    server_use_names: dict[int, str] = {}
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        try:
                            evt = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        etype = evt.get("type")
                        if etype == "content_block_start":
                            block = evt.get("content_block") or {}
                            btype = block.get("type")
                            idx = evt.get("index", -1)
                            if btype == "server_tool_use":
                                server_use_buf[idx] = ""
                                server_use_names[idx] = block.get("name", "")
                            elif btype == "web_search_tool_result":
                                result_content = block.get("content")
                                if isinstance(result_content, list):
                                    urls = tuple(
                                        r.get("url", "")
                                        for r in result_content
                                        if r.get("type") == "web_search_result"
                                    )
                                    yield LLMChunk(
                                        delta="",
                                        server_tool_event=ServerToolEvent(
                                            kind="completed",
                                            provider="anthropic",
                                            urls=urls,
                                            n_results=len(urls),
                                        ),
                                    )
                        elif etype == "content_block_delta":
                            delta = evt.get("delta") or {}
                            dtype = delta.get("type")
                            if dtype == "text_delta":
                                text = delta.get("text") or ""
                                if text:
                                    yield LLMChunk(delta=text)
                            elif dtype == "input_json_delta":
                                idx = evt.get("index", -1)
                                if idx in server_use_buf:
                                    server_use_buf[idx] += delta.get("partial_json", "")
                        elif etype == "content_block_stop":
                            idx = evt.get("index", -1)
                            if idx in server_use_buf:
                                raw = server_use_buf.pop(idx)
                                server_use_names.pop(idx, None)
                                query = ""
                                try:
                                    parsed = json.loads(raw) if raw else {}
                                    if isinstance(parsed, dict):
                                        query = str(parsed.get("query", ""))
                                except json.JSONDecodeError:
                                    pass
                                yield LLMChunk(
                                    delta="",
                                    server_tool_event=ServerToolEvent(
                                        kind="invoked",
                                        provider="anthropic",
                                        query=query,
                                    ),
                                )
                        elif etype == "message_delta":
                            stop_reason = (evt.get("delta") or {}).get("stop_reason")
                            if stop_reason:
                                yield LLMChunk(delta="", finish_reason=stop_reason)
            except TRANSIENT_NETWORK_ERRORS as exc:
                raise wrap_httpx_error(exc) from exc

    async def test_connection(self, model: str) -> TestResult:
        probe = AnthropicAdapter(
            credentials=self.credentials,
            model=model,
            capabilities=self.capabilities,
        )
        start = time.perf_counter()
        try:
            await probe.generate(
                LLMRequest(
                    messages=[Message(role="user", content="ping")],
                    max_tokens=16,
                    temperature=0.0,
                )
            )
        except LLMProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_class=None,
            error_msg=None,
        )
