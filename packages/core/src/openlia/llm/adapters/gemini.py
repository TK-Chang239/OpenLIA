from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from openlia.llm.adapters._content import render_gemini_contents
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
)

_BASE_URL = "https://generativelanguage.googleapis.com"


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
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop
        if request.tools:
            payload["tools"] = [
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
            ]
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
        return LLMResponse(
            text=text,
            finish_reason=candidate.get("finishReason", "STOP"),
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
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
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop
        if request.tools:
            payload["tools"] = [
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
            ]
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
