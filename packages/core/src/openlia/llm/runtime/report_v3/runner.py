"""Top-level runner for v3 equity-research runs.

One LLM session. One tool-use loop. One final emit. The loop:

  1. Build system prompt + initial user turn from the request.
  2. Call ``session.generate`` with the catalog's function tools and
     ``native_tools=("web_search",)``.
  3. For each tool_call in the response, dispatch via the catalog and
     append the result as a tool message.
  4. Ingest any web citations the adapter returned into the ledger.
  5. Repeat until the workspace is finalized OR a hard limit trips.

The runner deliberately stays close to the LLM loop. Persistence and
rendering live in Phase 2; this module only owns the in-memory flow
that produces a populated ``RunResult``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ...types import Message, ToolCall
from ..attachments import AttachmentNotSupportedError, materialize_for_model
from ..messages import ContentBlock
from ..report_v2_3.research import (
    NullToolExecutor,
    ResearchTool,
    ToolExecutionError,
    ToolResult,
)
from ..report_v2_3.research.registry import (
    FundamentalsTransport,
    NewsTransport,
    PricesTransport,
)
from .events import CancelToken, EventEmitter, NullEmitter
from .ledger import CitationLedger
from .prompts import build_revise_system_prompt, build_system_prompt
from .schemas import ReviseContext, RunRequest, RunResult
from .session import LLMSession
from .tools import (
    FIND_TOOLS_NAME,
    build_catalog,
)
from .tools.web_search import format_web_citation_notice, ingest_web_citations
from .workspace import RunWorkspace, WrittenSection

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataTransports:
    """Bundle of EODHD transport callables the runner needs.

    Provided by the wiring layer (the server constructs real EODHD
    SDK calls); the core layer stays free of SDK imports.
    """

    fundamentals: FundamentalsTransport
    prices: PricesTransport
    news: NewsTransport


def _null_transports(reason: str) -> DataTransports:
    """Fallback transports that fail loudly when called.

    Used when no EODHD credentials are configured. The model still
    sees the EODHD tools in its catalog but every call returns a
    clear "not configured" message it can react to.
    """
    fn = NullToolExecutor(reason)
    return DataTransports(fundamentals=fn, prices=fn, news=fn)


@dataclass
class Runner:
    """Executes one v3 run end-to-end.

    Instances are stateless across runs — configuration knobs
    (``max_turns``, ``max_wall_time_seconds``) hang here so callers
    don't need to wire them through ``run``.
    """

    max_turns: int = 60
    # 30 min default: equity research with web search routinely takes
    # 20-30 turns at 30-90s each (web search latency + long-context
    # model latency compound). Override via env in
    # ``v3_run_service._default_runner`` when ops needs more headroom.
    max_wall_time_seconds: int = 30 * 60
    # Per-tool-call cap. Tools run a synchronous SDK (the EODHD client
    # issues un-timed HTTP); a single hung call would otherwise block
    # the event loop and stall the run past the wall-time guard, which
    # only checks between turns. 120s is generous for one EODHD GET.
    # Override via env in ``v3_run_service._default_runner``.
    tool_timeout_seconds: float = 120.0
    transports_factory: Callable[[], DataTransports] = field(
        default=lambda: _null_transports(
            "EODHD transports not wired — set EODHD_API_KEY and rebuild the runner."
        )
    )

    async def run(
        self,
        request: RunRequest,
        *,
        session: LLMSession | None = None,
        emitter: EventEmitter | None = None,
        cancel_token: CancelToken | None = None,
        revise: ReviseContext | None = None,
        capability_override: dict | None = None,
        api_key: str | None = None,
    ) -> RunResult:
        """Execute a v3 run for the given request.

        Pass ``session`` to use a pre-built session (tests inject a
        fake adapter via ``LLMSession.attach_adapter``). When omitted
        a fresh session is created — which runs the capability gate
        and resolves credentials from env on the first generate().

        ``emitter`` receives progress events (run.started, tool.called,
        tool.completed, section.written, chart.emitted, run.completed
        / run.failed / run.cancelled). Defaults to a no-op emitter so
        callers that don't care don't have to wire anything.

        ``cancel_token`` is checked between turns and before each
        tool dispatch. Cancellation is cooperative — the runner exits
        at the next safe point with status='failed' and a clear
        ``run cancelled`` message; partial sections + charts persist.

        ``revise`` switches the runner into revision mode: the
        workspace is pre-loaded with the prior sections + charts,
        the ledger seeded with prior citations, and the system prompt
        + initial user turn are reshaped around the user's revision
        instruction. write_section allows section ids beyond the
        template, and finalize accepts partial completion.
        """
        if session is None:
            session = LLMSession.create(
                provider_kind=request.provider_kind,
                model=request.model,
                capability_override=capability_override,
                api_key=api_key,
            )
        emitter = emitter or NullEmitter()
        cancel_token = cancel_token or CancelToken()

        ledger = CitationLedger()
        if revise is not None:
            ledger.seed(
                [
                    {
                        "source_id": c.source_id,
                        "tool_name": c.tool_name,
                        "provenance": c.provenance,
                    }
                    for c in revise.prior_citations
                ]
            )
        workspace = RunWorkspace(
            template=request.template,
            ledger=ledger,
            subject=request.subject,
            revision_mode=revise is not None,
        )
        if revise is not None:
            # Pre-load prior sections so the workspace can render the
            # full report mid-revision and write_section's chart-ref
            # validation can see prior charts. ``sections_written_this_run``
            # stays empty so the persistence layer only versions the
            # sections this revision actually touched.
            for prior in revise.prior_sections:
                workspace.sections[prior.section_id] = WrittenSection(
                    section_id=prior.section_id,
                    title=prior.title,
                    markdown=prior.markdown,
                )
                if prior.section_id not in workspace.section_order:
                    workspace.section_order.append(prior.section_id)
            for chart in revise.prior_charts:
                workspace.charts[chart.chart_id] = chart

        transports = self.transports_factory()
        catalog = build_catalog(
            ledger=ledger,
            workspace=workspace,
            fundamentals=transports.fundamentals,
            prices=transports.prices,
            news=transports.news,
        )

        emitter.emit(
            "run.started",
            {
                "subject": request.subject,
                "template_id": request.template.template_id,
                "language": request.language.value,
                "provider_kind": request.provider_kind,
                "model": request.model,
                "mode": "revise" if revise is not None else "fresh",
            },
        )

        system_prompt = (
            build_revise_system_prompt(request=request, catalog=catalog, revise=revise)
            if revise is not None
            else build_system_prompt(request=request, catalog=catalog)
        )
        try:
            attachment_blocks = _materialize_attachments(request, session, emitter)
        except AttachmentNotSupportedError as exc:
            return _finish(
                workspace,
                emitter,
                status="failed",
                message=f"Attachment cannot be used: {exc}",
            )

        messages: list[Message] = [
            _initial_user_turn(request, revise=revise, attachment_blocks=attachment_blocks)
        ]

        deadline = time.monotonic() + self.max_wall_time_seconds

        for turn in range(self.max_turns):
            # Rebuild each turn so tools the model discovered via
            # find_tools on a prior turn join the request + dispatch set.
            tool_schemas = catalog.active_schemas()
            tools_by_name = catalog.active_tools_by_name()
            if cancel_token.cancelled:
                return _finish(
                    workspace,
                    emitter,
                    status="failed",
                    message=f"v3 run cancelled at turn {turn}. Partial work preserved.",
                    event_type="run.cancelled",
                )
            if time.monotonic() > deadline:
                return _finish(
                    workspace,
                    emitter,
                    status="failed",
                    message=(
                        f"v3 run exceeded {self.max_wall_time_seconds}s wall "
                        f"time after {turn} turns. Partial work preserved."
                    ),
                )

            response = await session.generate(
                messages=messages,
                system=system_prompt,
                tools=tool_schemas,
                native_tools=catalog.native_tools,
                reasoning_effort=request.reasoning_effort,
            )

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
                        "without calling finalize(). Likely the run was "
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
                result_message = await _dispatch_one_async(
                    call, tools_by_name, timeout_seconds=self.tool_timeout_seconds
                )
                messages.append(result_message)
                _emit_tool_completion(
                    emitter,
                    turn=turn,
                    call=call,
                    result_message=result_message,
                )
                # find_tools activates extended tools synchronously; refresh
                # so a discovered tool called later in this same response
                # (parallel tool calls) resolves instead of erroring.
                if call.name == FIND_TOOLS_NAME:
                    tools_by_name = catalog.active_tools_by_name()

            if workspace.finalized:
                return _finish(workspace, emitter, status="completed")

            # Teach the model the web_N source_ids for the results this
            # turn's native web search returned, so it cites [^web_N]
            # instead of the provider's native citation markers (which
            # don't resolve to the bibliography). Appended only when the
            # loop continues — a finalized run has no next turn to cite on.
            notice = format_web_citation_notice(response.citations, web_citation_rewrites)
            if notice is not None:
                messages.append(Message(role="user", content=notice))

        return _finish(
            workspace,
            emitter,
            status="failed",
            message=(
                f"v3 run hit hard limit of {self.max_turns} model turns "
                f"without calling finalize(). Partial work preserved."
            ),
        )


def _materialize_attachments(
    request: RunRequest,
    session: LLMSession,
    emitter: EventEmitter,
) -> tuple[ContentBlock, ...]:
    """Turn user-uploaded source documents into provider-neutral content
    blocks for the first turn.

    Multimodal-capable models receive native document/image blocks;
    others fall back to server-extracted text. Raises
    ``AttachmentNotSupportedError`` for hard-incompatible files (e.g. an
    image on a non-vision model) so the caller can fail the run with a
    clear message. Soft issues (skipped/truncated files) surface as
    ``attachment.warning`` events."""
    if not request.attachments:
        return ()
    caps = session.capabilities
    budget = max(1, caps.max_context_tokens - caps.max_output_tokens - 4_000)
    result = materialize_for_model(
        request.attachments,
        capabilities=caps,
        available_token_budget=budget,
    )
    for warning in result.warnings:
        emitter.emit("attachment.warning", {"message": warning})
    return tuple(result.blocks)


def _initial_user_turn(
    request: RunRequest,
    *,
    revise: ReviseContext | None = None,
    attachment_blocks: tuple[ContentBlock, ...] = (),
) -> Message:
    if revise is not None:
        return Message(
            role="user",
            content=(
                f"Revise the report for {request.subject!r} per the "
                f"instruction above. The prior report is loaded into "
                f"context; use the tools to research, compute, or "
                f"chart any new material, then call `write_section` "
                f"for each section you change (and `finalize` when "
                f"done)."
            ),
            content_blocks=attachment_blocks,
        )
    attachment_note = (
        " The user attached source document(s) — read them and use them "
        "as primary evidence, citing facts as usual."
        if attachment_blocks
        else ""
    )
    return Message(
        role="user",
        content=(
            f"Produce the report for {request.subject!r}. Follow the "
            f"template described in the system prompt. Use the tools "
            f"provided to research, compute, chart, and write. Call "
            f"`finalize` only after every required section is written."
            f"{attachment_note}"
        ),
        content_blocks=attachment_blocks,
    )


def _dispatch_one(call: ToolCall, tools_by_name: dict[str, ResearchTool]) -> Message:
    """Execute one tool call and produce the matching tool message.

    Errors from the tool are returned as tool messages too — the model
    sees the structured error and can correct itself or try a different
    tool. The loop never crashes on a single bad tool call.
    """
    tool = tools_by_name.get(call.name)
    if tool is None:
        body = json.dumps(
            {
                "error": (
                    f"Unknown tool {call.name!r}. "
                    f"Valid tools: {sorted(tools_by_name)}. "
                    f"If you need a specialized tool, call {FIND_TOOLS_NAME!r} "
                    f"first to discover and load it."
                )
            }
        )
        return Message(role="tool", content=body, tool_call_id=call.id)

    try:
        result = tool.execute(call.arguments)
    except ToolExecutionError as exc:
        body = json.dumps({"error": str(exc)})
        return Message(role="tool", content=body, tool_call_id=call.id)
    except Exception as exc:
        log.exception("v3 tool %s raised unexpectedly", call.name)
        body = json.dumps({"error": f"unexpected: {exc}"})
        return Message(role="tool", content=body, tool_call_id=call.id)

    return Message(role="tool", content=_serialize_result(result), tool_call_id=call.id)


async def _dispatch_one_async(
    call: ToolCall,
    tools_by_name: dict[str, ResearchTool],
    *,
    timeout_seconds: float,
) -> Message:
    """Run one tool off the event loop, bounded by a timeout.

    Tools execute a synchronous SDK (the EODHD client issues blocking,
    un-timed HTTP). Calling it inline would freeze the whole asyncio
    worker and let a single hung request hang the run indefinitely. We
    run each tool in a worker thread and cap it: a tool that overruns
    surfaces a structured timeout error to the model, exactly like any
    other tool failure, so the loop continues instead of stalling.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_dispatch_one, call, tools_by_name),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        log.warning(
            "v3 tool %s exceeded %.0fs cap; surfacing as a tool error",
            call.name,
            timeout_seconds,
        )
        body = json.dumps(
            {
                "error": (
                    f"Tool {call.name!r} timed out after {timeout_seconds:.0f}s. "
                    f"The data source may be slow or unreachable; try a "
                    f"different tool or proceed without this data."
                )
            }
        )
        return Message(role="tool", content=body, tool_call_id=call.id)


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
    event_type for ``run.cancelled`` since cancel status still maps
    to 'failed' on the result row but should be distinguishable in
    the event stream.
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

    Promotes ``write_section`` and ``emit_chart`` to their own
    dedicated event types so frontends can update the section /
    chart lists incrementally without parsing the generic
    tool.completed payload.
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
