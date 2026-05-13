"""ChatRunner — multi-turn chat with tool calls and token streaming.

Loop contract:
  - chat.start
  - while True:
      request the model; if it returns tool calls, emit tool events,
      dispatch, append tool-result messages, loop.
      if it returns text, stream tokens and emit chat.done.
  - chat.error on any LLMProviderError or ModelNotConfiguredError.

Cancellation: poll cancel_token between yields; stop yielding with no
terminal event when flipped.

When constructed with a v2 connector `dispatcher` plus a `router_llm_client`,
the runner additionally performs spec-§8 routing: it asks a small router
LLM to pick a tool subset from the dispatcher's `candidate_tools()`, places
a cache breakpoint marker before that subset in the system prompt, and
exposes the `request_additional_tools` escalation tool. Without those
constructor args the runner falls back to the legacy ToolDispatcher path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from openlia.connectors.dispatch import MissingRequiredArgumentError
from openlia.connectors.serialization import to_jsonable
from openlia.departments import get_department
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError, ModelNotConfiguredError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.attachments import (
    AttachmentNotSupportedError,
    materialize_for_model,
)
from openlia.llm.runtime.cancellation import CancellationToken, await_with_grace
from openlia.llm.runtime.escalation import (
    ESCALATION_TOOL_DEFINITION,
    ESCALATION_TOOL_NAME,
    merge_escalation,
    summarize_added,
)
from openlia.llm.runtime.events import (
    ChatDone,
    ChatError,
    ChatSkillLoaded,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
    SseEvent,
)
from openlia.llm.runtime.messages import Attachment, ChatMessage, ContentBlock
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.recall_artifacts import (
    RECALL_ARTIFACTS_SCHEMA,
    RECALL_ARTIFACTS_TOOL_NAME,
    RecallArtifactsHandler,
    dispatch_recall_artifacts,
)
from openlia.llm.runtime.router import LlmClient as RouterLlmClient
from openlia.llm.runtime.router import route_tools
from openlia.llm.runtime.tools import (
    LOAD_SKILL_SCHEMA,
    MAX_TOOL_TURNS,
    ToolCallResult,
    ToolDispatcher,
    dispatch_load_skill,
)
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ToolCall,
    ToolSchema,
)
from openlia.safety.input_wrapper import wrap_user_input
from openlia.skills import SkillRegistry

logger = logging.getLogger(__name__)

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]

# Marker emitted in the system prompt where an Anthropic prompt-cache
# breakpoint should be placed (spec §8.6). Provider adapters that
# support cache_control can split on this token; adapters that don't
# simply strip it and treat the prompt as plain text.
CACHE_BREAKPOINT_MARKER = "<<<openlia:cache_breakpoint>>>"


# Issue #99: tools whose semantics overlap with "extract text from a file the
# user attached." When the runtime has already inlined the file's text into
# the user message, exposing these to the model invites it to call them on
# the filename and ignore the inline content.
_DOC_PARSER_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "firecrawl__parse",
    }
)


def _has_inline_attachment(blocks: tuple[ContentBlock, ...]) -> bool:
    """True when any materialized block carries inline file payload (text,
    image, or native document) that the model should read directly."""
    return len(blocks) > 0


def _filter_doc_parsers(
    candidate_tools: list[dict[str, Any]],
    *,
    blocks: tuple[ContentBlock, ...],
) -> list[dict[str, Any]]:
    if not _has_inline_attachment(blocks):
        return candidate_tools
    return [t for t in candidate_tools if t.get("name") not in _DOC_PARSER_TOOL_NAMES]


def wrap_last_user_message(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Return a new list where the LAST role='user' message has its content
    wrapped in <user_input>...</user_input>. Earlier user messages are left
    untouched (they were already wrapped in their own turn). System and
    assistant messages are never wrapped."""
    out = list(messages)
    for i in range(len(out) - 1, -1, -1):
        if out[i].role == "user":
            out[i] = ChatMessage(
                role="user",
                content=wrap_user_input(out[i].content),
            )
            break
    return out


def _build_conversation(
    wrapped_messages: list[ChatMessage],
    materialized_blocks: tuple[ContentBlock, ...],
) -> list[Message]:
    """Project wrapped ChatMessages into LLM Messages. The last user message
    inherits any materialized attachment blocks; earlier user messages keep
    empty content_blocks."""
    out: list[Message] = []
    last_user_idx = -1
    for i in range(len(wrapped_messages) - 1, -1, -1):
        if wrapped_messages[i].role == "user":
            last_user_idx = i
            break
    for i, m in enumerate(wrapped_messages):
        blocks = materialized_blocks if i == last_user_idx else ()
        out.append(Message(role=m.role, content=m.content, content_blocks=blocks))
    return out


def _unicode_safe_truncate(s: str, *, max_len: int = 120) -> str:
    """Truncate `s` at a codepoint boundary so the result never cuts a
    multi-byte UTF-8 character (str slicing is codepoint-safe in Python,
    but we expose a named helper to make the intent explicit and keep the
    truncation behavior tested + reusable)."""
    if len(s) <= max_len:
        return s
    return s[:max_len]


def build_chat_system_prompt(
    *,
    department_id: str,
    user_id: str | None,
    registry: SkillRegistry,
    loader: PromptLoader | None = None,
    disabled_skill_ids: frozenset[str] = frozenset(),
    response_length: str | None = None,
    memory_block: str | None = None,
    selected_exemplars: list[str] | None = None,
    market_basket: dict[str, list[str]] | None = None,
) -> str:
    """Render the chat.system slot with the user's visible skills menu.

    `disabled_skill_ids` is the per-session opt-out set from the chat
    input "Tools" dropdown. Disabled skills are dropped before
    `skills_menu` is rendered so the model never knows they exist.

    `response_length` is the per-session composer choice; ``"concise"`` or
    ``"detailed"`` injects an explicit length directive into the system
    prompt, ``None``/``"normal"`` leaves the default discipline alone.

    `memory_block` is a pre-rendered cross-session memory snippet
    (slice 13). Server callers compute it via
    ``graph_retrieval.retrieve_memory_block`` from the live user
    message; ``None`` emits nothing so per-turn token cost stays zero
    when nothing is relevant.
    """
    loader = loader or PromptLoader()
    visible = registry.visible(
        department_id=department_id,
        user_id=user_id,
        disabled_skill_ids=disabled_skill_ids,
    )
    skills_menu = [
        {
            "id": s.manifest.name,
            "description": s.manifest.description,
            "tools": [
                f"skill__{s.manifest.name.replace('-', '_')}__{t['name']}"
                for t in (s.manifest.tools or [])
            ],
        }
        for s in visible
    ]
    return loader.render(
        department_id,
        "chat.system",
        skills_menu=skills_menu,
        response_length=response_length,
        memory_block=memory_block,
        selected_exemplars=list(selected_exemplars) if selected_exemplars else [],
        market_basket=market_basket,
    )


TraceRecorder = Callable[[str, str, dict[str, Any] | None], None]


def _no_trace(_category: str, _message: str, _payload: dict[str, Any] | None) -> None:
    return None


class ChatRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
        skill_registry: SkillRegistry,
        message_id_factory: Callable[[], str] | None = None,
        dispatcher: Any | None = None,
        router_llm_client: RouterLlmClient | None = None,
        routing_context_loader: Callable[[str], str] | None = None,
        trace: TraceRecorder | None = None,
        recall_artifacts: RecallArtifactsHandler | None = None,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory
        self._skill_registry = skill_registry
        self._message_id_factory = message_id_factory or (lambda: f"m_{uuid.uuid4().hex[:12]}")
        # Phase 9: v2 connector dispatcher + router LLM client. When all
        # three are present the runner uses the spec §8 routing flow;
        # otherwise it falls through to the legacy ToolDispatcher path.
        self._dispatcher = dispatcher
        self._router_llm = router_llm_client
        self._routing_context_loader = routing_context_loader
        # Optional dev-mode hook so the server can mirror per-LLM-call
        # detail (system prompt, tools, model_ref) into its event panel.
        self._trace: TraceRecorder = trace or _no_trace
        # Slice 12: cross-session report recall. When wired, the runner
        # exposes ``recall_artifacts`` to the model and intercepts the
        # tool call to invoke this server-side handler. The handler
        # itself owns DB + embedding-provider dependencies; the runner
        # only threads ``user_id`` from its request context (never from
        # LLM-supplied args — that would be a tenant-isolation hole).
        self._recall_artifacts = recall_artifacts

    def _v2_routing_enabled(self) -> bool:
        return (
            self._dispatcher is not None
            and self._router_llm is not None
            and self._routing_context_loader is not None
        )

    def _maybe_with_skill_tool(
        self,
        tools: list[ToolSchema],
        *,
        department_id: str,
        user_id: str | None,
        disabled_skill_ids: frozenset[str] = frozenset(),
    ) -> list[ToolSchema]:
        if (
            len(
                self._skill_registry.visible(
                    department_id=department_id,
                    user_id=user_id,
                    disabled_skill_ids=disabled_skill_ids,
                )
            )
            > 0
        ):
            return [*tools, LOAD_SKILL_SCHEMA]
        return tools

    def _maybe_with_recall_tool(self, tools: list[ToolSchema]) -> list[ToolSchema]:
        if self._recall_artifacts is None:
            return tools
        return [*tools, RECALL_ARTIFACTS_SCHEMA]

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages: list[ChatMessage],
        attachments: list[Attachment] | None = None,
        cancel_token: CancellationToken | None = None,
        session_id: str | None = None,
        model_id_override: str | None = None,
        disabled_skill_ids: frozenset[str] = frozenset(),
        response_length: str | None = None,
        memory_block: str | None = None,
        selected_exemplars: list[str] | None = None,
        market_basket: dict[str, list[str]] | None = None,
    ) -> AsyncIterator[SseEvent]:
        # `session_id` is currently informational — runtime does not branch
        # on it but routes thread it for telemetry / persistence parity.
        del session_id
        message_id = self._message_id_factory()
        yield ChatStart(message_id=message_id)

        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
                model_id_override=model_id_override,
            )
        except (LLMProviderError, ModelNotConfiguredError) as exc:
            yield ChatError(
                message_id=message_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        provider = self._provider_factory(resolved)

        # Materialize attachments into provider-neutral content blocks. The
        # blocks ride alongside the last user message so adapters can render
        # them as multi-modal content. See composer-attachments-design.md.
        try:
            materialized = materialize_for_model(
                attachments or (),
                capabilities=resolved.capabilities,
                available_token_budget=max(
                    1,
                    resolved.capabilities.max_context_tokens
                    - resolved.capabilities.max_output_tokens
                    - 4_000,  # rough headroom for system prompt + tool schemas
                ),
            )
        except AttachmentNotSupportedError as exc:
            yield ChatError(
                message_id=message_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return
        materialized_blocks: tuple[ContentBlock, ...] = tuple(materialized.blocks)
        for warning in materialized.warnings:
            self._trace("attachment.warning", warning, None)

        system = build_chat_system_prompt(
            department_id=department_id,
            user_id=user_id,
            registry=self._skill_registry,
            loader=self._prompts,
            disabled_skill_ids=disabled_skill_ids,
            response_length=response_length,
            memory_block=memory_block,
            selected_exemplars=selected_exemplars,
            market_basket=market_basket,
        )
        self._trace(
            "llm.resolved",
            f"{resolved.provider_kind}:{resolved.model_ref}",
            {
                "department_id": department_id,
                "model_id": resolved.model_id,
                "model_ref": resolved.model_ref,
                "provider_kind": resolved.provider_kind,
                "system_prompt_chars": len(system),
                "system_prompt_excerpt": system[:400],
            },
        )
        dept = get_department(department_id)
        extra_tool_specs = dept.extra_tools if dept is not None else ()
        extra_tool_names = frozenset(spec["name"] for spec in extra_tool_specs)

        # Phase 9 / spec §8: when a v2 dispatcher and router are wired,
        # route through the connector subsystem and yield from the v2
        # implementation. The legacy ToolDispatcher path remains for
        # tests and pre-v2 wiring.
        if self._v2_routing_enabled():
            async for event in self._run_v2_routed(
                provider=provider,
                system=system,
                department_id=department_id,
                dept=dept,
                resolved=resolved,
                messages=messages,
                materialized_blocks=materialized_blocks,
                cancel_token=cancel_token,
                message_id=message_id,
                extra_tool_specs=extra_tool_specs,
                user_id=user_id,
            ):
                yield event
            return

        tools = self._maybe_with_recall_tool(
            self._maybe_with_skill_tool(
                await self._tools.build(
                    department_id, has_web_search=True, extra_tools=extra_tool_specs
                ),
                department_id=department_id,
                user_id=user_id,
                disabled_skill_ids=disabled_skill_ids,
            )
        )

        wrapped_messages = wrap_last_user_message(messages)
        conversation = _build_conversation(wrapped_messages, materialized_blocks)

        # Tool loop — bounded by MAX_TOOL_TURNS (32) as an outer runaway guard.
        # Chat exposes the same `request_additional_tools` escalation as the
        # expansions; the budget arg is None here so only the outer cap fires.
        # Only runs when tools are configured; otherwise falls through to streaming.
        for _ in range(MAX_TOOL_TURNS) if tools else range(0):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            tool_names_v1 = [t.name for t in (tools or [])]
            summary_v1 = (
                f"{resolved.provider_kind}:{resolved.model_ref} "
                f"({len(conversation)} msgs, {len(tool_names_v1)} tools)"
            )
            self._trace(
                "llm.call.start",
                summary_v1,
                {
                    "model_ref": resolved.model_ref,
                    "provider_kind": resolved.provider_kind,
                    "messages": [{"role": m.role, "chars": len(m.content)} for m in conversation],
                    "tool_names": tool_names_v1,
                    "system_prompt_chars": len(system),
                    "max_tokens": 2048,
                },
            )
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
                self._trace(
                    "llm.call.error",
                    f"{type(exc).__name__}: {exc}",
                    {"model_ref": resolved.model_ref},
                )
                yield ChatError(
                    message_id=message_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return
            self._trace(
                "llm.call.done",
                f"{len(response.tool_calls)} tool_calls, {len(response.text or '')} chars",
                {
                    "model_ref": resolved.model_ref,
                    "tool_calls": [{"name": c.name, "id": c.id} for c in response.tool_calls],
                    "text_chars": len(response.text or ""),
                },
            )

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

            # Split load_skill / recall_artifacts calls from other calls
            # — both are dispatched directly through injected handlers,
            # not through the ToolDispatcher (which only knows about
            # connector / web-search tools).
            load_skill_calls: list[ToolCall] = []
            recall_calls: list[ToolCall] = []
            other_calls: list[ToolCall] = []
            for c in response.tool_calls:
                if c.name == "load_skill":
                    load_skill_calls.append(c)
                elif c.name == RECALL_ARTIFACTS_TOOL_NAME and self._recall_artifacts is not None:
                    recall_calls.append(c)
                else:
                    other_calls.append(c)

            # Dispatch load_skill calls directly (registry, not ToolDispatcher).
            load_skill_results: list[ToolCallResult] = []
            try:
                for c in load_skill_calls:
                    args = c.arguments if isinstance(c.arguments, dict) else json.loads(c.arguments)
                    r = await dispatch_load_skill(
                        self._skill_registry,
                        user_id=user_id,
                        skill_id=args["skill_id"],
                        call_id=c.id,
                    )
                    load_skill_results.append(r)
            except asyncio.CancelledError:
                return

            # Dispatch recall_artifacts calls via the injected handler.
            # user_id is taken from the runtime context — the LLM cannot
            # supply it.
            recall_results: list[ToolCallResult] = []
            try:
                for c in recall_calls:
                    args = c.arguments if isinstance(c.arguments, dict) else json.loads(c.arguments)
                    assert self._recall_artifacts is not None
                    r = await dispatch_recall_artifacts(
                        self._recall_artifacts,
                        user_id=user_id,
                        arguments=args,
                        call_id=c.id,
                    )
                    recall_results.append(r)
            except asyncio.CancelledError:
                return

            # Dispatch all other calls through ToolDispatcher.
            other_results: list[ToolCallResult] = []
            if other_calls:
                try:
                    other_results = await self._await(
                        self._tools.dispatch_many(
                            department_id=department_id,
                            calls=other_calls,
                            extra_tool_names=extra_tool_names,
                        ),
                        cancel_token=cancel_token,
                    )
                except asyncio.CancelledError:
                    return

            results: list[ToolCallResult] = load_skill_results + recall_results + other_results

            for r in results:
                yield ChatToolCallResult(
                    message_id=message_id,
                    call_id=r.call_id,
                    ok=r.ok,
                    summary=r.summary,
                    structured=r.structured,
                )

            # Emit ChatSkillLoaded for successful load_skill results.
            for r in load_skill_results:
                if r.ok and r.structured:
                    yield ChatSkillLoaded(
                        message_id=message_id,
                        skill_id=r.structured["skill_id"],
                        display_name=r.structured["display_name"],
                    )

            for r in results:
                conversation.append(Message(role="tool", content=json.dumps(r.payload)))
            tools = self._maybe_with_recall_tool(
                self._maybe_with_skill_tool(
                    await self._tools.build(
                        department_id, has_web_search=True, extra_tools=extra_tool_specs
                    ),
                    department_id=department_id,
                    user_id=user_id,
                    disabled_skill_ids=disabled_skill_ids,
                )
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

    # ---- Phase 9: v2 routed chat path (spec §8) ----

    async def _run_v2_routed(
        self,
        *,
        provider: LLMProvider,
        system: str,
        department_id: str,
        dept: Any,
        resolved: ResolvedModel,
        messages: list[ChatMessage],
        materialized_blocks: tuple[ContentBlock, ...] = (),
        cancel_token: CancellationToken | None,
        message_id: str,
        extra_tool_specs: tuple[dict[str, Any], ...] = (),
        user_id: str | None = None,
    ) -> AsyncIterator[SseEvent]:
        """Route + escalate per spec §8.

        - Build candidate pool from dispatcher.candidate_tools().
        - If `dept.disable_runtime_routing` is False, invoke the router
          LLM once on conversation start to pick a subset; otherwise
          expose the full pool with no escalation tool.
        - Place a cache-breakpoint marker before the routed-tools section
          in the system prompt so escalations only invalidate the suffix.
        - On `request_additional_tools` tool_use, re-invoke the router
          and continue with the merged set.
        """
        assert self._dispatcher is not None
        assert self._router_llm is not None
        assert self._routing_context_loader is not None

        candidate_tools: list[dict[str, Any]] = self._dispatcher.candidate_tools()
        candidate_tools = _filter_doc_parsers(candidate_tools, blocks=materialized_blocks)

        disable_routing = bool(getattr(dept, "disable_runtime_routing", False))

        if disable_routing:
            routed_names = [t["name"] for t in candidate_tools]
            include_escalation = False
        else:
            user_first = next(
                (m.content for m in messages if m.role == "user"),
                "",
            )
            try:
                routing_context = self._routing_context_loader(department_id)
            except FileNotFoundError as exc:
                logger.warning(
                    "routing_context missing for dept %s; skipping router: %s",
                    department_id,
                    exc,
                )
                routing_context = ""
            routed_names = await route_tools(
                department_id=department_id,
                routing_context=routing_context,
                user_prompt=user_first,
                candidate_tools=candidate_tools,
                llm_client=self._router_llm,
            )
            include_escalation = True

        candidate_by_name = {t["name"]: t for t in candidate_tools}

        async with self._dispatcher.in_department(department_id):
            async for event in self._v2_loop(
                provider=provider,
                system=system,
                department_id=department_id,
                resolved=resolved,
                routing_context_loader=self._routing_context_loader,
                candidate_by_name=candidate_by_name,
                routed_names=list(routed_names),
                include_escalation=include_escalation,
                messages=messages,
                materialized_blocks=materialized_blocks,
                cancel_token=cancel_token,
                message_id=message_id,
                disable_routing=disable_routing,
                extra_tool_specs=extra_tool_specs,
                user_id=user_id,
            ):
                yield event

    async def _v2_loop(
        self,
        *,
        provider: LLMProvider,
        system: str,
        department_id: str,
        resolved: ResolvedModel,
        routing_context_loader: Callable[[str], str],
        candidate_by_name: dict[str, dict[str, Any]],
        routed_names: list[str],
        include_escalation: bool,
        messages: list[ChatMessage],
        materialized_blocks: tuple[ContentBlock, ...],
        cancel_token: CancellationToken | None,
        message_id: str,
        disable_routing: bool,
        extra_tool_specs: tuple[dict[str, Any], ...] = (),
        user_id: str | None = None,
    ) -> AsyncIterator[SseEvent]:
        assert self._dispatcher is not None
        wrapped_messages = wrap_last_user_message(messages)
        conversation = _build_conversation(wrapped_messages, materialized_blocks)

        candidate_list = list(candidate_by_name.values())

        extra_tool_names: frozenset[str] = frozenset(spec["name"] for spec in extra_tool_specs)

        def _build_main_tools(names: list[str]) -> list[ToolSchema]:
            schemas: list[ToolSchema] = []
            for name in names:
                td = candidate_by_name.get(name)
                if td is None:
                    continue
                schemas.append(
                    ToolSchema(
                        name=td["name"],
                        description=td.get("description", ""),
                        parameters=td.get("input_schema", {"type": "object", "properties": {}}),
                    )
                )
            if include_escalation:
                schemas.append(
                    ToolSchema(
                        name=ESCALATION_TOOL_DEFINITION["name"],
                        description=ESCALATION_TOOL_DEFINITION["description"],
                        parameters=ESCALATION_TOOL_DEFINITION["input_schema"],
                    )
                )
            for spec in extra_tool_specs:
                schemas.append(
                    ToolSchema(
                        name=spec["name"],
                        description=spec.get("description", ""),
                        parameters=spec.get("parameters", {"type": "object", "properties": {}}),
                    )
                )
            # Slice 12: expose recall_artifacts to chat-style depts when
            # a handler has been wired by the server.
            if self._recall_artifacts is not None:
                schemas.append(RECALL_ARTIFACTS_SCHEMA)
            return schemas

        def _build_system(names: list[str]) -> str:
            # Spec §8.6: cache breakpoint sits BEFORE the routed-tools
            # description so an escalation only invalidates the suffix.
            tool_section_lines = ["", "## Available tools (routed)"]
            for name in names:
                td = candidate_by_name.get(name)
                if td is None:
                    continue
                tool_section_lines.append(f"- {td['name']}: {td.get('description', '')}")
            tool_section = "\n".join(tool_section_lines)
            return f"{system}\n{CACHE_BREAKPOINT_MARKER}{tool_section}"

        tools = _build_main_tools(routed_names)
        system_prompt = _build_system(routed_names)

        for _ in range(MAX_TOOL_TURNS):
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            tool_names_v2 = [t.name for t in (tools or [])]
            summary_v2 = (
                f"{resolved.provider_kind}:{resolved.model_ref} "
                f"(v2 routed, {len(conversation)} msgs, {len(tool_names_v2)} tools)"
            )
            self._trace(
                "llm.call.start",
                summary_v2,
                {
                    "model_ref": resolved.model_ref,
                    "provider_kind": resolved.provider_kind,
                    "messages": [{"role": m.role, "chars": len(m.content)} for m in conversation],
                    "tool_names": tool_names_v2,
                    "system_prompt_chars": len(system_prompt),
                    "max_tokens": 2048,
                    "routed": True,
                },
            )
            try:
                response = await self._await(
                    provider.generate(
                        LLMRequest(
                            messages=conversation,
                            system=system_prompt,
                            tools=tools or None,
                            max_tokens=2048,
                        )
                    ),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return
            except LLMProviderError as exc:
                self._trace(
                    "llm.call.error",
                    f"{type(exc).__name__}: {exc}",
                    {"model_ref": resolved.model_ref},
                )
                yield ChatError(
                    message_id=message_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return
            self._trace(
                "llm.call.done",
                f"{len(response.tool_calls)} tool_calls, {len(response.text or '')} chars",
                {
                    "model_ref": resolved.model_ref,
                    "tool_calls": [{"name": c.name, "id": c.id} for c in response.tool_calls],
                    "text_chars": len(response.text or ""),
                    "routed": True,
                },
            )

            if not response.tool_calls:
                break

            # Replay the assistant turn that requested the tools. Required
            # by OpenAI/OpenRouter/Anthropic — every `tool` message must
            # pair with a prior assistant `tool_calls` block carrying the
            # same id, otherwise the next request 400s.
            conversation.append(
                Message(
                    role="assistant",
                    content=response.text or "",
                    tool_calls=tuple(response.tool_calls),
                )
            )

            # Emit start events for every call before dispatching.
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

            # Dispatch each call: escalation -> re-route + summarize;
            # otherwise -> dispatcher.dispatch_tool_use.
            for call in response.tool_calls:
                if call.name == ESCALATION_TOOL_NAME and include_escalation:
                    before = list(routed_names)
                    try:
                        routing_context = routing_context_loader(department_id)
                    except FileNotFoundError:
                        routing_context = ""
                    routed_names = await merge_escalation(
                        department_id=department_id,
                        routing_context=routing_context,
                        current_tools=routed_names,
                        escalation_arguments=call.arguments,
                        candidate_tools=candidate_list,
                        llm_client=self._router_llm,  # type: ignore[arg-type]
                    )
                    summary = summarize_added(before, routed_names)
                    yield ChatToolCallResult(
                        message_id=message_id,
                        call_id=call.id,
                        ok=True,
                        summary=summary,
                        structured=None,
                    )
                    conversation.append(
                        Message(
                            role="tool",
                            content=json.dumps({"summary": summary}),
                            tool_call_id=call.id,
                        )
                    )
                    # Rebuild tool list and system prompt with the
                    # expanded routed set; the cache breakpoint stays
                    # in the same place so the prefix remains hot.
                    tools = _build_main_tools(routed_names)
                    system_prompt = _build_system(routed_names)
                    continue

                if call.name in extra_tool_names:
                    args = dict(call.arguments)
                    yield ChatToolCallResult(
                        message_id=message_id,
                        call_id=call.id,
                        ok=True,
                        summary=f"{call.name} suggested",
                        structured=args,
                    )
                    conversation.append(
                        Message(
                            role="tool",
                            content=json.dumps({"ack": True}),
                            tool_call_id=call.id,
                        )
                    )
                    continue

                if call.name == RECALL_ARTIFACTS_TOOL_NAME and self._recall_artifacts is not None:
                    raw_args = (
                        call.arguments
                        if isinstance(call.arguments, dict)
                        else json.loads(call.arguments)
                    )
                    recall_result = await dispatch_recall_artifacts(
                        self._recall_artifacts,
                        user_id=user_id,
                        arguments=raw_args,
                        call_id=call.id,
                    )
                    yield ChatToolCallResult(
                        message_id=message_id,
                        call_id=call.id,
                        ok=recall_result.ok,
                        summary=recall_result.summary,
                        structured=None,
                    )
                    conversation.append(
                        Message(
                            role="tool",
                            content=json.dumps(recall_result.payload),
                            tool_call_id=call.id,
                        )
                    )
                    continue

                payload, ok, summary_text = await self._dispatch_v2_call(call)
                yield ChatToolCallResult(
                    message_id=message_id,
                    call_id=call.id,
                    ok=ok,
                    summary=summary_text,
                    structured=None,
                )
                conversation.append(
                    Message(
                        role="tool",
                        content=json.dumps(payload),
                        tool_call_id=call.id,
                    )
                )

        # Final streaming turn — same shape as the legacy path.
        del disable_routing  # currently unused after build; reserved for telemetry
        if cancel_token is not None and cancel_token.is_cancelled:
            return
        try:
            stream_iter = provider.stream(
                LLMRequest(
                    messages=conversation,
                    system=system_prompt,
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

    async def _dispatch_v2_call(self, call: ToolCall) -> tuple[dict[str, Any], bool, str]:
        """Dispatch a v2 prefixed tool_use through the connector dispatcher.

        Coerces the raw return through `to_jsonable` so non-JSON-native SDK
        return types (firecrawl-py SearchData, pydantic models, dataclasses,
        datetimes) round-trip through `json.dumps` without raising.
        """
        assert self._dispatcher is not None
        try:
            raw = await self._dispatcher.dispatch_tool_use(call.name, call.arguments)
        except MissingRequiredArgumentError as exc:
            return (
                {
                    "error": str(exc),
                    "missing": list(exc.missing),
                    "hint": ("Retry the call with one of the listed arguments set (non-empty)."),
                },
                False,
                f"{call.name} missing required argument: {' or '.join(exc.missing)}",
            )
        except Exception as exc:
            return ({"error": str(exc)}, False, f"{call.name} failed: {exc!s}")
        coerced = to_jsonable(raw)
        if isinstance(coerced, dict):
            payload = coerced
        else:
            payload = {"value": coerced}
        return (payload, True, f"Called {call.name}")
