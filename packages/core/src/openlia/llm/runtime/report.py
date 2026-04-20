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

import copy
import json
import uuid
from collections.abc import AsyncIterator, Callable
from importlib import resources
from pathlib import Path
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.resolver import ModelRegistry
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    ReportToolCall,
    SseEvent,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ResponseFormat,
)

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
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: ModelRegistry,
        provider_factory: ProviderFactory,
        frameworks_root: Path | None = None,
        report_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
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
        )

        conversation = [Message(role="user", content=user_msg)]
        tools = await self._tools.build(department_id, has_web_search=True)

        yield ReportPhase(report_id=report_id, phase="fetching_data")

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
                yield ReportError(
                    report_id=report_id,
                    error_class=type(exc).__name__,
                    message=str(exc),
                )
                return
            if not response.tool_calls:
                break
            results = await self._tools.dispatch_many(
                department_id=department_id, calls=response.tool_calls
            )
            for r in results:
                yield ReportToolCall(
                    report_id=report_id,
                    tool_name=_tool_name_for_result(response, r.call_id),
                    summary=r.summary,
                )
                conversation.append(Message(role="tool", content=json.dumps(r.payload)))
            if cancel_token is not None and cancel_token.is_cancelled:
                return
            tools = await self._tools.build(department_id, has_web_search=True)

        yield ReportPhase(report_id=report_id, phase="writing")
        if cancel_token is not None and cancel_token.is_cancelled:
            return

        try:
            final = await provider.generate(
                LLMRequest(
                    messages=conversation,
                    system=system,
                    response_format=ResponseFormat(kind="json_schema", json_schema=framework),
                    max_tokens=4096,
                )
            )
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

        yield ReportComplete(report_id=report_id, schema=schema_payload)
