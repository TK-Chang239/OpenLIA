from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from openlia.llm.adapters._content import render_gemini_contents, strip_cache_breakpoint
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
    ServerToolEvent,
    TestResult,
)

_BASE_URL = "https://generativelanguage.googleapis.com"

# Gemini's native Grounding with Google Search tool. Documented at
# https://ai.google.dev/gemini-api/docs/grounding. Activated by adding
# `{"google_search": {}}` to the request's `tools` array; the response
# returns search results under `candidates[0].groundingMetadata`.
_GOOGLE_SEARCH_TOOL = {"google_search": {}}


def _build_gemini_tools(request: LLMRequest) -> list[dict] | None:
    """Render request.tools into Gemini's `tools` array. Function tools
    pack into a single `{"functionDeclarations": [...]}` entry; native
    search adds a sibling `{"google_search": {}}` entry."""
    tools: list[dict] = []
    if request.tools:
        tools.append(
            {
                "functionDeclarations": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    }
                    for t in request.tools
                ]
            }
        )
    if "web_search" in request.native_tools:
        tools.append(_GOOGLE_SEARCH_TOOL)
    return tools or None


def _parse_gemini_grounding(grounding_metadata: dict | None) -> tuple[Citation, ...]:
    """Walk `candidates[0].groundingMetadata` into Citations.

    For each `groundingChunks[i].web` chunk we emit one "bare" Citation
    carrying the URL/title with no segment offsets. For each
    `groundingSupports[s]` we additionally emit one "segmented"
    Citation per `groundingChunkIndices[i]`, copying the same URL/title
    but populating `segment_start`/`segment_end` from the support's
    `segment.startIndex`/`segment.endIndex`. This lets downstream
    renderers place inline `[N]` markers at exact char offsets while
    bare Citations still serve the side-panel chip list.
    """
    if not grounding_metadata:
        return ()
    chunks = grounding_metadata.get("groundingChunks") or []
    supports = grounding_metadata.get("groundingSupports") or []

    chunk_meta: list[dict[str, str | None]] = []
    citations: list[Citation] = []
    for i, chunk in enumerate(chunks):
        web = chunk.get("web") or {}
        url = web.get("uri")
        title = web.get("title")
        chunk_meta.append({"url": url, "title": title})
        citations.append(
            Citation(
                id=f"c{i + 1}",
                kind="web",
                url=url,
                title=title,
                source="Google Search",
            )
        )

    seg_seq = 0
    for support in supports:
        segment = support.get("segment") or {}
        start = segment.get("startIndex")
        end = segment.get("endIndex")
        for idx in support.get("groundingChunkIndices") or []:
            if not (0 <= idx < len(chunk_meta)):
                continue
            seg_seq += 1
            meta = chunk_meta[idx]
            citations.append(
                Citation(
                    id=f"cs{seg_seq}",
                    kind="web",
                    url=meta["url"],
                    title=meta["title"],
                    source="Google Search",
                    segment_start=start,
                    segment_end=end,
                )
            )
    return tuple(citations)


class GeminiAdapter(LLMProvider):
    kind = "gemini"

    def _query(self) -> dict[str, str]:
        return {"key": self.credentials.api_key or ""}

    async def list_models(self) -> list[ModelInfo]:
        async def _call() -> list[ModelInfo]:
            async with make_client(base_url=_BASE_URL) as client:
                try:
                    resp = await client.get("/v1beta/models", params=self._query())
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                data = resp.json()
                out: list[ModelInfo] = []
                for item in data.get("models", []):
                    name = item.get("name", "")
                    short_id = name.split("/", 1)[1] if "/" in name else name
                    out.append(
                        ModelInfo(
                            id=short_id,
                            display_name=item.get("displayName") or short_id,
                            context_window=item.get("inputTokenLimit"),
                        )
                    )
                return out

        return await with_retries(_call)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "contents": render_gemini_contents(list(request.messages)),
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        if request.system:
            payload["systemInstruction"] = {
                "parts": [{"text": strip_cache_breakpoint(request.system)}]
            }
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop
        gemini_tools = _build_gemini_tools(request)
        if gemini_tools is not None:
            payload["tools"] = gemini_tools
        if request.tool_choice is not None:
            payload["toolConfig"] = request.tool_choice

        path = f"/v1beta/models/{self.model}:generateContent"

        async def _post() -> dict:
            async with make_client(base_url=_BASE_URL) as client:
                try:
                    resp = await client.post(path, params=self._query(), json=payload)
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

        candidate = (body.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if "text" in p)
        usage = body.get("usageMetadata") or {}
        gmd = candidate.get("groundingMetadata")
        citations = _parse_gemini_grounding(gmd)
        failures: tuple[FailedSearch, ...] = ()
        if "web_search" in request.native_tools:
            chunks = (gmd or {}).get("groundingChunks") or []
            queries = (gmd or {}).get("webSearchQueries") or []
            # Native was requested but the model returned no grounding
            # — either the search was blocked, returned nothing, or
            # the model abstained. Surface as FailedSearch so the
            # runtime can route to the configured fallback (I-a).
            if gmd is not None and not chunks and not queries:
                failures = (
                    FailedSearch(
                        query="",
                        error_kind="unknown",
                        error_message="gemini grounding empty",
                        turn_idx=0,
                    ),
                )
        return LLMResponse(
            text=text,
            finish_reason=candidate.get("finishReason", "STOP"),
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
            citations=citations,
            server_tool_failures=failures,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        payload: dict = {
            "contents": render_gemini_contents(list(request.messages)),
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        if request.system:
            payload["systemInstruction"] = {
                "parts": [{"text": strip_cache_breakpoint(request.system)}]
            }
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop
        gemini_tools = _build_gemini_tools(request)
        if gemini_tools is not None:
            payload["tools"] = gemini_tools
        if request.tool_choice is not None:
            payload["toolConfig"] = request.tool_choice

        path = f"/v1beta/models/{self.model}:streamGenerateContent"
        params = {**self._query(), "alt": "sse"}

        async with make_client(base_url=_BASE_URL) as client:
            try:
                async with client.stream("POST", path, params=params, json=payload) as resp:
                    if resp.status_code != 200:
                        body_bytes = await resp.aread()
                        status_to_exception(
                            status_code=resp.status_code,
                            body_text=body_bytes.decode("utf-8", errors="replace"),
                            headers=dict(resp.headers),
                        )
                    # Gemini streams text deltas and surfaces native
                    # search via `groundingMetadata` on a candidate.
                    # The wire format has no separate "invoked"/"completed"
                    # markers, so we synthesize one ServerToolEvent pair
                    # at the first chunk that carries groundingMetadata.
                    grounding_emitted = False
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        try:
                            evt = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        candidate = (evt.get("candidates") or [{}])[0]
                        parts = (candidate.get("content") or {}).get("parts") or []
                        text = "".join(p.get("text", "") for p in parts if "text" in p)
                        finish = candidate.get("finishReason")
                        gmd = candidate.get("groundingMetadata")
                        if gmd and not grounding_emitted:
                            grounding_emitted = True
                            queries = gmd.get("webSearchQueries") or []
                            first_query = str(queries[0]) if queries else ""
                            yield LLMChunk(
                                delta="",
                                server_tool_event=ServerToolEvent(
                                    kind="invoked",
                                    provider="gemini",
                                    query=first_query,
                                ),
                            )
                            chunks_list = gmd.get("groundingChunks") or []
                            urls = tuple((c.get("web") or {}).get("uri", "") for c in chunks_list)
                            yield LLMChunk(
                                delta="",
                                server_tool_event=ServerToolEvent(
                                    kind="completed",
                                    provider="gemini",
                                    urls=urls,
                                    n_results=len(urls),
                                ),
                            )
                        if text or finish:
                            yield LLMChunk(delta=text, finish_reason=finish)
            except TRANSIENT_NETWORK_ERRORS as exc:
                raise wrap_httpx_error(exc) from exc

    async def test_connection(self, model: str) -> TestResult:
        probe = GeminiAdapter(
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
