"""LLM client for the chat-runtime tool router.

`openlia.llm.runtime.router.route_tools` calls `generate_json(*, prompt)`
and accepts either a JSON array of tool names or a `{"tools": [...]}`
object (per `_coerce_to_name_list`). The wizard's `AdapterLlmJsonClient`
enforces a `dict` return, which would silently coerce array responses
into router failures and an empty routed set. This client is the same
shape but allows arrays.
"""

from __future__ import annotations

import json
import re
from typing import Any

from openlia.connectors.adapter import LlmClient
from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message, ResponseFormat

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _strip_fence(text: str) -> str:
    match = _FENCE_RE.match(text.strip())
    if match is None:
        return text
    return match.group(1).strip()


class RouterLlmJsonClient(LlmClient):
    """Wraps an `LLMProvider` so it satisfies the router's `LlmClient` Protocol.

    The router prompt asks the model to return a JSON array of tool names
    but tolerates `{"tools": [...]}` too. Either is returned as-is; the
    router's `_coerce_to_name_list` then normalizes.
    """

    def __init__(self, *, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate_json(self, *, prompt: str) -> Any:
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            system="Return ONLY a JSON value. No prose, no fences.",
            response_format=ResponseFormat(kind="json_object"),
            max_tokens=512,
            temperature=0.0,
        )
        response = await self._provider.generate(request)
        text = _strip_fence((response.text or "").strip())
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"router LLM returned non-JSON: {exc}") from exc


__all__ = ["RouterLlmJsonClient"]
