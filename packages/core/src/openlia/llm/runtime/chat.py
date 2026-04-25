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

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable

from openlia.departments import get_department
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.cancellation import CancellationToken, await_with_grace
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
from openlia.llm.runtime.tools import MAX_TOOL_TURNS, ToolCallResult, ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
)

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _unicode_safe_truncate(s: str, *, max_len: int = 120) -> str:
    """Truncate `s` at a codepoint boundary so the result never cuts a
    multi-byte UTF-8 character (str slicing is codepoint-safe in Python,
    but we expose a named helper to make the intent explicit and keep the
    truncation behavior tested + reusable)."""
    if len(s) <= max_len:
        return s
    return s[:max_len]


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
        dept = get_department(department_id)
        extra_tool_specs = dept.extra_tools if dept is not None else ()
        extra_tool_names = frozenset(spec["name"] for spec in extra_tool_specs)
        tools = await self._tools.build(
            department_id, has_web_search=True, extra_tools=extra_tool_specs
        )

        conversation = [Message(role=m.role, content=m.content) for m in messages]

        # Tool loop — bounded by MAX_TOOL_TURNS (32) as an outer runaway guard.
        # Per the spec, Secretary (chat) is unlimited on `find_more_data`
        # expansions; the budget arg is None here so only the outer cap fires.
        # Only runs when tools are configured; otherwise falls through to streaming.
        for _ in range(MAX_TOOL_TURNS) if tools else range(0):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            try:
                response = await self._await(
                    provider.generate(
                        LLMRequest(
                            messages=conversation,
                            system=system,
                            tools=tools or None,
                            max_tokens=2048,
                        )
                    ),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return
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
                args_preview = _unicode_safe_truncate(
                    json.dumps(call.arguments, separators=(",", ":"), ensure_ascii=False),
                    max_len=120,
                )
                yield ChatToolCallStart(
                    message_id=message_id,
                    call_id=call.id,
                    tool_name=call.name,
                    args_preview=args_preview,
                )
            try:
                results: list[ToolCallResult] = await self._await(
                    self._tools.dispatch_many(
                        department_id=department_id,
                        calls=response.tool_calls,
                        extra_tool_names=extra_tool_names,
                        max_expansions=None,  # Secretary: unlimited.
                    ),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return
            for r in results:
                yield ChatToolCallResult(
                    message_id=message_id,
                    call_id=r.call_id,
                    ok=r.ok,
                    summary=r.summary,
                    structured=r.structured,
                )
            for r in results:
                conversation.append(Message(role="tool", content=json.dumps(r.payload)))
            tools = await self._tools.build(
                department_id, has_web_search=True, extra_tools=extra_tool_specs
            )

        # Final text turn — stream tokens.
        if cancel_token is not None and cancel_token.is_cancelled:
            return
        try:
            stream_iter = provider.stream(
                LLMRequest(
                    messages=conversation,
                    system=system,
                    max_tokens=2048,
                )
            ).__aiter__()
            while True:
                if cancel_token is not None and cancel_token.is_cancelled:
                    return
                try:
                    chunk = await self._await(
                        stream_iter.__anext__(),
                        cancel_token=cancel_token,
                    )
                except StopAsyncIteration:
                    break
                except asyncio.CancelledError:
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

    @staticmethod
    async def _await(awaitable, *, cancel_token: CancellationToken | None):
        """Wrap an awaitable in `await_with_grace` when a token is provided.

        A `None` token short-circuits to direct `await` (no grace path).
        """
        if cancel_token is None:
            return await awaitable
        return await await_with_grace(awaitable, token=cancel_token)
