from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._http import (
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


def _to_openai_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": req.system})
    for m in req.messages:
        out.append({"role": m.role, "content": m.content})
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
                except httpx.HTTPError as exc:
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
        if request.response_format and request.response_format.kind == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.response_format.json_schema,
            }

        async def _post() -> dict:
            async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
                try:
                    resp = await client.post("/v1/chat/completions", json=payload)
                except httpx.HTTPError as exc:
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
        raise NotImplementedError("OpenAIAdapter.stream is implemented in Plan 5")
        yield  # pragma: no cover

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
                    max_tokens=1,
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
