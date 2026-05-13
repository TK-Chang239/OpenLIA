from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._content import render_openai_messages, strip_cache_breakpoint
from openlia.llm.adapters._http import (
    TRANSIENT_NETWORK_ERRORS,
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import CapabilityError, LLMProviderError
from openlia.llm.retry import with_retries
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    ProviderCredentials,
    TestResult,
    ToolCall,
)


def _to_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": strip_cache_breakpoint(req.system)})
    # Use the shared OpenAI-style renderer so user messages with
    # materialized content_blocks emit as the chat-completions parts
    # array (image_url + multi-text); collapses to legacy {role, content}
    # when no blocks are present.
    out.extend(render_openai_messages(list(req.messages)))
    return out


class OpenAICompatAdapter(LLMProvider):
    kind = "openai_compat"

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        capabilities: Capabilities,
    ) -> None:
        if not credentials.base_url:
            raise CapabilityError("OpenAICompatAdapter requires a base_url in credentials")
        super().__init__(credentials=credentials, model=model, capabilities=capabilities)

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.credentials.api_key:
            headers["authorization"] = f"Bearer {self.credentials.api_key}"
        return headers

    async def list_models(self) -> list[ModelInfo]:
        base = (self.credentials.base_url or "").rstrip("/")
        async with make_client(base_url=base, headers=self._headers()) as client:
            try:
                resp = await client.get("/models")
            except httpx.HTTPError:
                return []
            if resp.status_code == 404:
                return []
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
                    context_window=item.get("context_length"),
                )
                for item in data.get("data", [])
            ]

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

        base = (self.credentials.base_url or "").rstrip("/")

        async def _post() -> dict:
            async with make_client(base_url=base, headers=self._headers()) as client:
                try:
                    resp = await client.post("/chat/completions", json=payload)
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

        base = (self.credentials.base_url or "").rstrip("/")

        async with make_client(base_url=base, headers=self._headers()) as client:
            try:
                async with client.stream("POST", "/chat/completions", json=payload) as resp:
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
        probe = OpenAICompatAdapter(
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
