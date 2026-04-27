"""ReportRunner — single-pass structured report generation.

Flow per run():
  report.start
  → report.phase("fetching_data")
    → tool loop until the LLM returns no more tool calls
      (emit report.tool_call per dispatched tool)
  → report.phase("writing")
    → one structured-output turn (response_format=json_schema)
  → report.phase("finalizing")
  → report.complete(schema=parsed_json)

On LLMProviderError: report.error, stop.
On cancellation: stop yielding, no terminal event.
"""

from __future__ import annotations

import asyncio
import copy
import json
import uuid
from collections.abc import AsyncIterator, Callable
from importlib import resources
from pathlib import Path
from typing import Any

from openlia.connectors.dispatch import Dispatcher
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.cancellation import CancellationToken, await_with_grace
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportSectionComplete,
    ReportSectionStart,
    ReportStart,
    ReportToolCall,
    ReportToolCallStart,
    SseEvent,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.runtime_dispatch import (
    ToolCallRequest,
    ToolCallResult,
    dispatch_many,
    tools_for_run,
)
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ResponseFormat,
)

# Outer runaway guard for the report tool loop. Matches the legacy
# `MAX_TOOL_TURNS` constant from `openlia.llm.runtime.tools` so the cap is
# unchanged post-cutover. The connector dispatcher has no built-in
# expansion budget; the loop terminates when the model returns no more
# tool_use blocks or when this cap is reached.
MAX_TOOL_TURNS = 32


def _unicode_safe_truncate(s: str, *, max_len: int = 120) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len]


ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _default_frameworks_root() -> Path:
    return Path(str(resources.files("openlia.reports.frameworks")))


def _load_framework(frameworks_root: Path, mode: str) -> dict[str, Any]:
    path = frameworks_root / f"{mode}.json"
    return json.loads(path.read_text())


def _load_style_guide(frameworks_root: Path, mode: str) -> str:
    path = frameworks_root / f"{mode}_style_guide.md"
    return path.read_text() if path.exists() else ""


def _customize_framework(framework: dict[str, Any], request: ReportRequest) -> dict[str, Any]:
    fw = copy.deepcopy(framework)
    sections = fw.get("sections", [])
    if request.enabled_sections:
        wanted = set(request.enabled_sections)
        sections = [s for s in sections if s.get("id") in wanted]
    for custom in request.custom_sections:
        sections.append(dict(custom))
    fw["sections"] = sections
    fw["length_preference"] = request.length
    return fw


def _section_titles(framework: dict[str, Any]) -> list[str]:
    return [s.get("title", s.get("id", "Section")) for s in framework.get("sections", [])]


def _tool_name_for_result(response: Any, call_id: str) -> str:
    for call in response.tool_calls:
        if call.id == call_id:
            return call.name
    return "unknown"


class ReportRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        dispatcher: Dispatcher,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
        frameworks_root: Path | None = None,
        report_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._prompts = prompts
        self._dispatcher = dispatcher
        self._resolve = resolve
        self._registry = registry
        self._provider_factory = provider_factory
        self._frameworks_root = (
            frameworks_root if frameworks_root is not None else _default_frameworks_root()
        )
        self._report_id_factory = report_id_factory or (lambda: f"r_{uuid.uuid4().hex[:12]}")

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
        cancel_token: CancellationToken | None = None,
        max_expansions: int | None = None,
    ) -> AsyncIterator[SseEvent]:
        report_id = self._report_id_factory()

        framework_raw = _load_framework(self._frameworks_root, request.mode)
        framework = _customize_framework(framework_raw, request)
        style_guide = _load_style_guide(self._frameworks_root, request.mode)

        yield ReportStart(
            report_id=report_id,
            department=department_id,
            mode=request.mode,
            section_titles=_section_titles(framework),
        )

        try:
            resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
            )
        except LLMProviderError as exc:
            yield ReportError(
                report_id=report_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        provider = self._provider_factory(resolved)

        system = self._prompts.render(department_id, "report.system", style_guide=style_guide)
        user_msg = self._prompts.render(
            department_id,
            f"report.{request.mode}.user",
            user_input=request.user_input,
            framework=framework,
            length=request.length,
            enabled_sections=request.enabled_sections,
            custom_sections=request.custom_sections,
            section_topics=request.section_topics,
            reference_portfolio=request.reference_portfolio,
        )

        conversation = [Message(role="user", content=user_msg)]
        tools = tools_for_run(self._dispatcher, department_id, has_web_search=True)

        yield ReportPhase(report_id=report_id, phase="fetching_data")

        # Tool-expansion loop. The legacy ToolDispatcher carried a
        # `max_expansions` budget for its `find_more_data` rounds; with the
        # connector Dispatcher that concept moves into the runner as an
        # outer cap. `max_expansions=None` means "use the runaway guard
        # only" (MAX_TOOL_TURNS). The loop also terminates whenever the
        # model returns no tool_use blocks.
        loop_cap = MAX_TOOL_TURNS if max_expansions is None else min(MAX_TOOL_TURNS, max_expansions)
        for _ in range(loop_cap) if tools else range(0):
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
                yield ReportError(
                    report_id=report_id,
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
                yield ReportToolCallStart(
                    report_id=report_id,
                    call_id=call.id,
                    tool_name=call.name,
                    args_preview=args_preview,
                )
            requests = [
                ToolCallRequest(
                    prefixed_name=call.name,
                    arguments=call.arguments,
                    call_id=call.id,
                )
                for call in response.tool_calls
            ]
            try:
                results: list[ToolCallResult] = await self._await(
                    dispatch_many(self._dispatcher, requests),
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                return
            for r in results:
                yield ReportToolCall(
                    report_id=report_id,
                    tool_name=_tool_name_for_result(response, r.call_id),
                    summary=r.summary,
                    call_id=r.call_id,
                )
                conversation.append(Message(role="tool", content=json.dumps(r.payload)))
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            tools = tools_for_run(self._dispatcher, department_id, has_web_search=True)

        yield ReportPhase(report_id=report_id, phase="writing")
        if cancel_token is not None and cancel_token.is_cancelled:
            return

        sections_meta = framework.get("sections", []) or []
        total_sections = len(sections_meta)
        for idx, section in enumerate(sections_meta):
            yield ReportSectionStart(
                report_id=report_id,
                section_id=str(section.get("id", "")),
                title=str(section.get("title", section.get("id", "Section"))),
                idx=idx,
                total=total_sections,
            )

        try:
            final = await self._await(
                provider.generate(
                    LLMRequest(
                        messages=conversation,
                        system=system,
                        response_format=ResponseFormat(kind="json_schema", json_schema=framework),
                        max_tokens=4096,
                    )
                ),
                cancel_token=cancel_token,
            )
        except asyncio.CancelledError:
            return
        except LLMProviderError as exc:
            yield ReportError(
                report_id=report_id,
                error_class=type(exc).__name__,
                message=str(exc),
            )
            return

        yield ReportPhase(report_id=report_id, phase="finalizing")
        if cancel_token is not None and cancel_token.is_cancelled:
            return

        try:
            schema_payload = json.loads(final.text) if final.text else {}
        except json.JSONDecodeError as exc:
            yield ReportError(
                report_id=report_id,
                error_class="RuntimeError",
                message=f"LLM returned non-JSON response: {exc!s}",
            )
            return

        for section in schema_payload.get("sections", []) or []:
            yield ReportSectionComplete(
                report_id=report_id,
                section_id=str(section.get("id", "")),
                blocks=list(section.get("blocks", []) or []),
            )

        yield ReportComplete(report_id=report_id, schema=schema_payload)

    @staticmethod
    async def _await(awaitable, *, cancel_token: CancellationToken | None):
        if cancel_token is None:
            return await awaitable
        return await await_with_grace(awaitable, token=cancel_token)
