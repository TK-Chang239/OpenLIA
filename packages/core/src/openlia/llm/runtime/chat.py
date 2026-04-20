"""ChatRunner — multi-turn chat with tool calls and token streaming.

Loop contract:
  - chat.start
  - while True:
      request the model; if it returns tool calls, emit tool events,
      dispatch, append tool-result messages, loop.
      if it returns text, stream tokens and emit chat.done.
  - chat.error on any LLMProviderError (including TierNotConfiguredError).

Cancellation: poll cancel_token between yields; stop yielding with no
terminal event when flipped.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable

from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
    SseEvent,
)
from openlia.llm.runtime.messages import Attachment, ChatMessage
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolCallResult, ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
)

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


class ChatRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
        message_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory
        self._message_id_factory = message_id_factory or (lambda: f"m_{uuid.uuid4().hex[:12]}")

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages: list[ChatMessage],
        attachments: list[Attachment] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> AsyncIterator[SseEvent]:
        message_id = self._message_id_factory()
        yield ChatStart(message_id=message_id)

        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
            )
        except LLMProviderError as exc:
            yield ChatError(
                message_id=message_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        provider = self._provider_factory(resolved)
        system = self._prompts.render(department_id, "chat.system")
        tools = await self._tools.build(department_id, has_web_search=True)

        conversation = [Message(role=m.role, content=m.content) for m in messages]

        # Tool loop — up to 10 rounds to stop runaway expansions.
        # Only runs when tools are configured; otherwise falls through to streaming.
        for _ in range(10) if tools else range(0):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            try:
                response = await provider.generate(
                    LLMRequest(
                        messages=conversation,
                        system=system,
                        tools=tools or None,
                        max_tokens=2048,
                    )
                )
            except LLMProviderError as exc:
                yield ChatError(
                    message_id=message_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return

            if not response.tool_calls:
                break

            for call in response.tool_calls:
                yield ChatToolCallStart(
                    message_id=message_id,
                    call_id=call.id,
                    tool_name=call.name,
                    args_preview=json.dumps(call.arguments, separators=(",", ":"))[:120],
                )
            results: list[ToolCallResult] = await self._tools.dispatch_many(
                department_id=department_id, calls=response.tool_calls
            )
            for r in results:
                yield ChatToolCallResult(
                    message_id=message_id,
                    call_id=r.call_id,
                    ok=r.ok,
                    summary=r.summary,
                )
            for r in results:
                conversation.append(Message(role="tool", content=json.dumps(r.payload)))
            tools = await self._tools.build(department_id, has_web_search=True)

        # Final text turn — stream tokens.
        if cancel_token is not None and cancel_token.is_cancelled:
            return
        try:
            async for chunk in provider.stream(
                LLMRequest(
                    messages=conversation,
                    system=system,
                    max_tokens=2048,
                )
            ):
                if cancel_token is not None and cancel_token.is_cancelled:
                    return
                if chunk.delta:
                    yield ChatToken(message_id=message_id, text=chunk.delta)
        except LLMProviderError as exc:
            yield ChatError(
                message_id=message_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        if cancel_token is not None and cancel_token.is_cancelled:
            return
        yield ChatDone(message_id=message_id, stop_reason="complete")
