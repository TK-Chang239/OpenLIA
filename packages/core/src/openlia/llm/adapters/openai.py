from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from openlia.llm.adapters._content import render_openai_messages, strip_cache_breakpoint
from openlia.llm.adapters._http import (
    TRANSIENT_NETWORK_ERRORS,
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.capabilities import capabilities_for
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

_BASE_URL = "https://api.openai.com"


def _is_reasoning_model(model: str) -> bool:
    m = model.lower()
    return m.startswith(("o1", "o3", "o4", "gpt-5"))


def _to_openai_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": strip_cache_breakpoint(req.system)})
    # Use the shared renderer for the role+content shape so user messages
    # with materialized content_blocks (images, extracted-text PDFs, …)
    # are emitted as the OpenAI "parts" array. Tool-call plumbing is
    # OpenAI-specific and merged onto the rendered dict afterwards.
    rendered = render_openai_messages(list(req.messages))
    for m, msg in zip(req.messages, rendered, strict=True):
        if m.role == "assistant" and m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ]
        if m.role == "tool" and m.tool_call_id is not None:
            msg["tool_call_id"] = m.tool_call_id
        out.append(msg)
    return out


def _parse_arguments(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class OpenAIAdapter(LLMProvider):
    kind = "openai"

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.credentials.api_key}",
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
                        display_name=item["id"],
                        context_window=item.get("context_length")
                        or capabilities_for(
                            provider_kind="openai", model=item["id"]
                        ).max_context_tokens,
                    )
                    for item in data.get("data", [])
                ]

        return await with_retries(_call)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": _to_openai_messages(request),
        }
        if _is_reasoning_model(self.model):
            payload["max_completion_tokens"] = request.max_tokens
        else:
            payload["max_tokens"] = request.max_tokens
            payload["temperature"] = request.temperature
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
        if request.response_format and request.response_format.kind == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.response_format.json_schema,
            }
        elif request.response_format and request.response_format.kind == "json_object":
            payload["response_format"] = {"type": "json_object"}
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
        tool_calls = [
            ToolCall(
                id=tc.get("id", ""),
                name=tc["function"]["name"],
                arguments=_parse_arguments(tc["function"].get("arguments", "{}")),
            )
            for tc in message.get("tool_calls") or []
        ]
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
            "messages": _to_openai_messages(request),
            "stream": True,
        }
        if _is_reasoning_model(self.model):
            payload["max_completion_tokens"] = request.max_tokens
        else:
            payload["max_tokens"] = request.max_tokens
            payload["temperature"] = request.temperature
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
        if request.response_format and request.response_format.kind == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.response_format.json_schema,
            }
        elif request.response_format and request.response_format.kind == "json_object":
            payload["response_format"] = {"type": "json_object"}

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
        probe = OpenAIAdapter(
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
