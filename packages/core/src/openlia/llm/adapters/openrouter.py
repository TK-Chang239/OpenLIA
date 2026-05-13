from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from openlia.llm.adapters._content import render_openai_messages
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
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    TestResult,
    ToolCall,
)

_BASE_URL = "https://openrouter.ai/api"


def _to_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": req.system})
    # Pre-render user/system/assistant-without-tool-calls via the shared
    # OpenAI-style renderer so user messages with materialized
    # content_blocks emit as the chat-completions "parts" array
    # (image_url, multi-text). Tool results and assistant tool-call turns
    # need OpenRouter-specific shapes and are still handled below.
    rendered_by_idx = {
        i: dict_msg for i, dict_msg in enumerate(render_openai_messages(list(req.messages)))
    }
    for i, m in enumerate(req.messages):
        if m.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id or "",
                    "content": m.content,
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in m.tool_calls
                    ],
                }
            )
            continue
        out.append(rendered_by_idx[i])
    return out


class OpenRouterAdapter(LLMProvider):
    kind = "openrouter"

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.credentials.api_key}",
            "content-type": "application/json",
            "HTTP-Referer": "https://openlia.app",
            "X-Title": "OpenLIA",
        }

    async def list_models(self) -> list[ModelInfo]:
        return []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": _to_messages(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        async def _post() -> dict:
            async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
                try:
                    resp = await client.post("/v1/chat/completions", json=payload)
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

        choice = body["choices"][0]
        message = choice.get("message", {})
        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc["function"]["name"],
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        usage = body.get("usage") or {}
        return LLMResponse(
            text=message.get("content") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            tool_calls=tool_calls,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        payload: dict = {
            "model": self.model,
            "messages": _to_messages(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]

        async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
            try:
                async with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
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
                            return
                        try:
                            payload_chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = payload_chunk.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta_obj = choice.get("delta") or {}
                        delta_text = delta_obj.get("content") or ""
                        finish = choice.get("finish_reason")
                        if delta_text or finish:
                            yield LLMChunk(delta=delta_text, finish_reason=finish)
            except TRANSIENT_NETWORK_ERRORS as exc:
                raise wrap_httpx_error(exc) from exc

    async def test_connection(self, model: str) -> TestResult:
        probe = OpenRouterAdapter(
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
