"""AI review orchestrator — calls Quick-tier LLM + parses JSON response."""
from __future__ import annotations

import json
from typing import Any, Protocol

from openlia_server.ai_review.prompt import build_review_prompt
from openlia_server.ai_review.schema import ReviewResult
from openlia_server.ai_review.store import ReviewStore


class _LLMProtocol(Protocol):
    async def generate(self, *, prompt: str, max_tokens: int) -> Any: ...


async def run_review(
    *,
    review_id: str,
    db: Any,
    llm: _LLMProtocol,
    departments: list[tuple[str, list[str]]],
    providers: list[dict[str, object]],
    store: ReviewStore,
) -> None:
    try:
        prompt = build_review_prompt(departments, providers)
        response = await llm.generate(prompt=prompt, max_tokens=4096)
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            store.update(review_id, state="failed", error=f"parse error: {exc}")
            return
        result = ReviewResult.model_validate(payload)
        store.update(review_id, state="complete", progress=100, result=result.model_dump())
    except Exception as exc:  # noqa: BLE001
        store.update(review_id, state="failed", error=str(exc))
