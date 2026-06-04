"""Top-level runner for Retail Sentiment dashboard runs.

One LLM session. One tool-use loop. One final emit. The loop:

  1. Build system prompt + initial user turn from the request.
  2. Call ``session.generate`` with the catalog's function tools and the
     catalog's native tools (``("web_search",)`` only when the web-search
     connector is enabled).
  3. For each tool_call in the response, dispatch via the catalog and
     append the result as a tool message.
  4. When web search is enabled, ingest any web citations the adapter
     returned into the ledger.
  5. Repeat until the workspace is finalized OR a hard limit trips.
     The loop ends when the model calls ``emit_dashboard`` (which
     finalizes the workspace).

Forked from report_dash_mr: a fixed connector-gated catalog of
retail-sentiment tools, no revise pass, and no batch mode.
Persistence and rendering live in a later phase; this module owns the
in-memory flow that produces a populated ``RunResult``.
"""

from __future__ import annotations

import contextlib
import inspect
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from ...types import Message, ToolCall
from ..report_dash_mr.events import CancelToken, EventEmitter, NullEmitter
from ..report_dash_mr.ledger import CitationLedger
from ..report_dash_mr.session import LLMSession
from ..report_dash_mr.tools.web_search import format_web_citation_notice, ingest_web_citations
from ..report_dash_mr.transports import MbDataTransports
from ..report_dash_mr.workspace import RunWorkspace
from ..report_v2_3.research import (
    ResearchTool,
    ToolExecutionError,
    ToolResult,
)
from .prompts import ConnectorPromptInfo, build_system_prompt
from .schemas import RunRequest, RunResult
from .tools import build_catalog

log = logging.getLogger(__name__)


@dataclass
class Runner:
    """Executes one Retail Sentiment dashboard run end-to-end.

    Construct with the run's ``request`` and an ``MbDataTransports``
    bundle (the EODHD callables the data tools dispatch against). The
    tuning knobs (``max_turns``, ``max_wall_time_seconds``) hang here so
    callers don't need to wire them through ``run``.
    """

    request: RunRequest
    transports: MbDataTransports
    max_turns: int = 60
    # 30 min default: a briefing with web search can take 20-30 turns at
    # 30-90s each (web search + long-context latency compound).
    max_wall_time_seconds: int = 30 * 60
    # Optional connector dispatcher. Duck-typed: when set, must expose an
    # async ``in_department(department)`` context manager. The runner runs
    # its whole tool loop inside that context so connector tools resolve
    # the right per-department credentials. None => no context wrapping.
    dispatcher: Any = None

    async def run(
        self,
        *,
        session: LLMSession | None = None,
        emitter: EventEmitter | None = None,
        cancel_token: CancelToken | None = None,
    ) -> RunResult:
        """Execute the Retail Sentiment dashboard run.

        Pass ``session`` to use a pre-built session (tests inject a fake
        adapter via ``LLMSession.attach_adapter``). When omitted a fresh
        session is created — which resolves credentials from env on the
        first generate().

        ``emitter`` receives progress events (run.started, tool.called,
        tool.completed, section.written, chart.emitted, run.completed /
        run.failed / run.cancelled). Defaults to a no-op emitter.

        ``cancel_token`` is checked between turns. Cancellation is
        cooperative — the runner exits at the next safe point with
        status='failed' and a clear message; partial work persists.
        The loop ends when the model calls ``emit_dashboard`` (which
        finalizes the workspace).
        """
        request = self.request
        if session is None:
            session = LLMSession.create(
                provider_kind=request.provider_kind,
                model=request.model,
            )
        emitter = emitter or NullEmitter()
        cancel_token = cancel_token or CancelToken()

        ledger = CitationLedger()
        workspace = RunWorkspace(
            template=request.template,
            ledger=ledger,
            subject=request.subject,
            dashboard_slug=request.dashboard_slug,
        )

        catalog = build_catalog(
            ledger=ledger,
            workspace=workspace,
            transports=self.transports,
            enabled_connectors=request.enabled_connectors,
            dashboard_slug=request.dashboard_slug,
            dispatcher=self.dispatcher,
        )

        emitter.emit(
            "run.started",
            {
                "subject": request.subject,
                "template_id": (
                    request.template.template_id
                    if request.template is not None
                    else request.dashboard_slug
                ),
                "language": request.language.value,
                "provider_kind": request.provider_kind,
                "model": request.model,
            },
        )

        connector_tools = _connector_prompt_info(catalog)
        system_prompt = build_system_prompt(request, connector_tools=connector_tools)
        tool_schemas = catalog.core_schemas()
        tools_by_name = catalog.by_name()

        messages: list[Message] = [_initial_user_turn(request)]

        deadline = time.monotonic() + self.max_wall_time_seconds

        if self.dispatcher is not None:
            ctx = self.dispatcher.in_department("retail_sentiment")
        else:
            ctx = contextlib.nullcontext()

        async with ctx:
            return await self._run_turn_loop(
                session=session,
                emitter=emitter,
                cancel_token=cancel_token,
                workspace=workspace,
                ledger=ledger,
                tool_schemas=tool_schemas,
                tools_by_name=tools_by_name,
                native_tools=catalog.native_tools,
                system_prompt=system_prompt,
                messages=messages,
                deadline=deadline,
            )

    async def _run_turn_loop(
        self,
        *,
        session: LLMSession,
        emitter: EventEmitter,
        cancel_token: CancelToken,
        workspace: RunWorkspace,
        ledger: CitationLedger,
        tool_schemas: list,
        tools_by_name: dict[str, ResearchTool],
        native_tools: tuple[str, ...],
        system_prompt: str,
        messages: list[Message],
        deadline: float,
    ) -> RunResult:
        request = self.request

        for turn in range(self.max_turns):
            if cancel_token.cancelled:
                return _finish(
                    workspace,
                    emitter,
                    status="failed",
                    message=(
                        f"Retail Sentiment dashboard run cancelled at turn {turn}."
                        " Partial work preserved."
                    ),
                    event_type="run.cancelled",
                )
            if time.monotonic() > deadline:
                return _finish(
                    workspace,
                    emitter,
                    status="failed",
                    message=(
                        f"Retail Sentiment dashboard run exceeded "
                        f"{self.max_wall_time_seconds}s wall "
                        f"time after {turn} turns. Partial work preserved."
                    ),
                )

            response = await session.generate(
                messages=messages,
                system=system_prompt,
                tools=tool_schemas,
                native_tools=native_tools,
                reasoning_effort=request.reasoning_effort,
            )

            web_citation_rewrites: dict[str, str] = {}
            if request.enabled_connectors.web_search:
                web_citation_rewrites = ingest_web_citations(response.citations, ledger)

            assistant_message = Message(
                role="assistant",
                content=response.text or "",
                tool_calls=tuple(response.tool_calls),
            )
            messages.append(assistant_message)

            if not response.tool_calls:
                if workspace.finalized:
                    return _finish(workspace, emitter, status="completed")
                return _finish(
                    workspace,
                    emitter,
                    status="failed",
                    message=(
                        "Model ended turn without calling any tool and "
                        "without calling emit_dashboard(). Likely the run was "
                        "truncated or the prompt was misunderstood."
                    ),
                )

            for call in response.tool_calls:
                emitter.emit(
                    "tool.called",
                    {
                        "turn": turn,
                        "tool_name": call.name,
                        "args_summary": _summarize_args(call.arguments),
                    },
                )
                result_message = await _dispatch_one(call, tools_by_name)
                messages.append(result_message)
                _emit_tool_completion(
                    emitter,
                    turn=turn,
                    call=call,
                    result_message=result_message,
                )

            if workspace.finalized:
                return _finish(workspace, emitter, status="completed")

            # Teach the model the web_N source_ids for results this turn's
            # native web search returned, so it cites [^web_N] instead of
            # the provider's native markers. Appended only when web search
            # is enabled and the loop continues.
            if request.enabled_connectors.web_search:
                notice = format_web_citation_notice(response.citations, web_citation_rewrites)
                if notice is not None:
                    messages.append(Message(role="user", content=notice))

        return _finish(
            workspace,
            emitter,
            status="failed",
            message=(
                f"Retail Sentiment dashboard run hit hard limit of {self.max_turns} model turns "
                f"without calling emit_dashboard(). Partial work preserved."
            ),
        )


def _connector_prompt_info(catalog: Any) -> tuple[ConnectorPromptInfo, ...]:
    """Derive per-connector prompt info from the catalog's dispatcher tools.

    Dispatcher tools have ``<provider>__<tool>`` names; curated EODHD tools
    have plain names and are skipped (the EODHD block covers them). Tools
    are grouped by provider prefix into one ``ConnectorPromptInfo`` each,
    preserving first-seen provider order.
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    for descriptor in catalog.descriptors:
        name = descriptor.name
        if "__" not in name:
            continue
        provider = name.split("__", 1)[0]
        grouped.setdefault(provider, []).append((name, descriptor.description))
    return tuple(
        ConnectorPromptInfo(label=provider, tools=tuple(tools))
        for provider, tools in grouped.items()
    )


def _initial_user_turn(request: RunRequest) -> Message:
    return Message(
        role="user",
        content=(
            f"Produce the {request.dashboard_slug} Retail Sentiment dashboard"
            f" for {request.subject}. "
            f"Gather the required inputs with the enabled tools, call "
            f"`classify_retail_sentiment` with the counts of bullish / bearish / neutral items "
            f"and your buzz_level assessment, then "
            f"call `emit_dashboard` once with the complete payload matching "
            f"the schema in the system prompt."
        ),
    )


async def _dispatch_one(call: ToolCall, tools_by_name: dict[str, ResearchTool]) -> Message:
    """Execute one tool call and produce the matching tool message.

    Errors from the tool are returned as tool messages too — the model
    sees the structured error and can correct itself or try a different
    tool. The loop never crashes on a single bad tool call.

    A tool's ``execute`` may be sync (curated EODHD + output tools) or a
    coroutine (connector tools). When it returns an awaitable the result
    is awaited here, inside the same try/except so a raise from either
    the sync call or the awaited coroutine surfaces as a structured error.
    """
    tool = tools_by_name.get(call.name)
    if tool is None:
        body = json.dumps(
            {
                "error": (
                    f"Unknown tool {call.name!r}. "
                    f"Valid tools: {sorted(tools_by_name)}. "
                    f"Only the enabled tools are available this run."
                )
            }
        )
        return Message(role="tool", content=body, tool_call_id=call.id)

    try:
        result = tool.execute(call.arguments)
        if inspect.isawaitable(result):
            result = await result
    except ToolExecutionError as exc:
        body = json.dumps({"error": str(exc)})
        return Message(role="tool", content=body, tool_call_id=call.id)
    except Exception as exc:
        log.exception("Retail Sentiment dashboard tool %s raised unexpectedly", call.name)
        body = json.dumps({"error": f"unexpected: {exc}"})
        return Message(role="tool", content=body, tool_call_id=call.id)

    return Message(role="tool", content=_serialize_result(result), tool_call_id=call.id)


def _serialize_result(result: ToolResult) -> str:
    try:
        return json.dumps(result.payload, default=str)
    except TypeError:
        return json.dumps({"summary": result.summary, "payload": str(result.payload)})


def _finish(
    workspace: RunWorkspace,
    emitter: EventEmitter,
    *,
    status: str,
    message: str = "",
    event_type: str | None = None,
) -> RunResult:
    """Build the RunResult, emit the terminal event, return it.

    ``event_type`` defaults to the matching terminal event for the
    status (run.completed / run.failed). Callers pass an explicit
    event_type for ``run.cancelled`` since cancel status still maps to
    'failed' on the result row but should be distinguishable in the
    event stream.
    """
    result = workspace.to_result(status=status, message=message)
    if event_type is None:
        event_type = "run.completed" if status == "completed" else "run.failed"
    emitter.emit(
        event_type,
        {
            "status": status,
            "section_count": len(result.sections),
            "chart_count": len(result.charts),
            "citation_count": len(result.citations),
            "message": message,
        },
    )
    return result


def _emit_tool_completion(
    emitter: EventEmitter,
    *,
    turn: int,
    call: ToolCall,
    result_message: Message,
) -> None:
    """Translate one tool dispatch into a tool.completed event.

    Promotes ``write_section`` and ``emit_chart`` to their own dedicated
    event types so frontends can update the section / chart lists
    incrementally without parsing the generic tool.completed payload.
    """
    parsed = _safe_json(result_message.content)
    ok = isinstance(parsed, dict) and not parsed.get("error")
    source_id = parsed.get("source_id") if isinstance(parsed, dict) else None

    emitter.emit(
        "tool.completed",
        {
            "turn": turn,
            "tool_name": call.name,
            "ok": bool(ok),
            "source_id": source_id,
            "error": parsed.get("error") if isinstance(parsed, dict) else None,
        },
    )

    if not ok:
        return

    if call.name == "write_section":
        emitter.emit(
            "section.written",
            {
                "section_id": call.arguments.get("section_id"),
                "char_count": parsed.get("char_count") if isinstance(parsed, dict) else None,
                "missing_sections": (
                    parsed.get("missing_sections") if isinstance(parsed, dict) else None
                ),
            },
        )
    elif call.name == "emit_chart":
        emitter.emit(
            "chart.emitted",
            {
                "chart_id": call.arguments.get("chart_id"),
                "chart_type": call.arguments.get("chart_type"),
                "title": call.arguments.get("title"),
            },
        )


def _summarize_args(args: dict) -> dict:
    """Compact arg view for events — drop large blobs (markdown, data arrays)."""
    summary: dict = {}
    for key, value in args.items():
        if isinstance(value, str) and len(value) > 120:
            summary[key] = value[:117] + "..."
        elif isinstance(value, list) and len(value) > 5:
            summary[key] = f"<list len={len(value)}>"
        elif isinstance(value, dict) and len(value) > 5:
            summary[key] = f"<dict keys={len(value)}>"
        else:
            summary[key] = value
    return summary


def _safe_json(text: str) -> object:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
