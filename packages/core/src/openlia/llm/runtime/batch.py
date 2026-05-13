"""BatchRunner — bounded-concurrency structured classification.

Non-streaming. No tool calls. One LLM call per item. `asyncio.Semaphore`
bounds in-flight calls. Per-item exceptions are captured and surfaced
as BatchResult(ok=False, error=...) — the batch always completes.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError, ModelNotConfiguredError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.cancellation import CancellationToken, await_with_grace
from openlia.llm.runtime.messages import BatchItem, BatchResult
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ResponseFormat,
)

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


class BatchRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
    ) -> None:
        self._prompts = prompts
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory

    async def run(
        self,
        *,
        department_id: str,
        task: str,
        items: list[BatchItem],
        schema: type[BaseModel],
        concurrency: int = 8,
        user_id: str | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> list[BatchResult]:
        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
            )
        except (LLMProviderError, ModelNotConfiguredError) as exc:
            msg = f"{type(exc).__name__}: {exc!s}"
            return [BatchResult(id=it.id, ok=False, data=None, error=msg) for it in items]

        provider = self._provider_factory(resolved)
        system = self._prompts.render(department_id, f"batch.{task}.system")
        user_slot = f"batch.{task}.user"
        response_format = ResponseFormat(kind="json_schema", json_schema=schema.model_json_schema())
        sema = asyncio.Semaphore(concurrency)

        async def _one(item: BatchItem) -> BatchResult:
            async with sema:
                user = self._prompts.render(department_id, user_slot, **item.context)
                try:
                    awaitable = provider.generate(
                        LLMRequest(
                            messages=[Message(role="user", content=user)],
                            system=system,
                            response_format=response_format,
                            max_tokens=1024,
                        )
                    )
                    if cancel_token is None:
                        response = await awaitable
                    else:
                        response = await await_with_grace(awaitable, token=cancel_token)
                except asyncio.CancelledError:
                    return BatchResult(id=item.id, ok=False, data=None, error="cancelled")
                except LLMProviderError as exc:
                    return BatchResult(
                        id=item.id,
                        ok=False,
                        data=None,
                        error=f"{type(exc).__name__}: {exc!s}",
                    )
                try:
                    raw = json.loads(response.text or "{}")
                except json.JSONDecodeError as exc:
                    return BatchResult(
                        id=item.id, ok=False, data=None, error=f"JSON parse: {exc!s}"
                    )
                try:
                    validated = schema.model_validate(raw).model_dump()
                except ValidationError as exc:
                    return BatchResult(
                        id=item.id,
                        ok=False,
                        data=None,
                        error=f"schema validation: {exc!s}",
                    )
                return BatchResult(id=item.id, ok=True, data=validated, error=None)

        return list(await asyncio.gather(*(_one(item) for item in items)))
