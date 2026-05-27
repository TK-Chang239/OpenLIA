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

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ...types import Message, ToolCall, ToolSchema
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
from .ledger import CitationLedger
from .prompts import build_system_prompt
from .schemas import RunRequest, RunResult
from .session import LLMSession
from .tools import (
    WEB_SEARCH_TOOL_NAME,
    ToolCatalog,
    build_catalog,
)
from .tools.web_search import ingest_web_citations
from .workspace import RunWorkspace

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
    max_wall_time_seconds: int = 15 * 60
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
    ) -> RunResult:
        """Execute a v3 run for the given request.

        Pass ``session`` to use a pre-built session (tests inject a
        fake adapter via ``LLMSession.attach_adapter``). When omitted
        a fresh session is created — which runs the capability gate
        and resolves credentials from env on the first generate().
        """
        if session is None:
            session = LLMSession.create(
                provider_kind=request.provider_kind,
                model=request.model,
            )

        ledger = CitationLedger()
        workspace = RunWorkspace(
            template=request.template,
            ledger=ledger,
            subject=request.subject,
        )
        transports = self.transports_factory()
        catalog = build_catalog(
            ledger=ledger,
            workspace=workspace,
            fundamentals=transports.fundamentals,
            prices=transports.prices,
            news=transports.news,
        )

        system_prompt = build_system_prompt(request=request, catalog=catalog)
        tool_schemas = _catalog_to_tool_schemas(catalog)
        messages: list[Message] = [_initial_user_turn(request)]

        deadline = time.monotonic() + self.max_wall_time_seconds
        tools_by_name = catalog.by_name()

        for turn in range(self.max_turns):
            if time.monotonic() > deadline:
                return workspace.to_result(
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
            )

            ingest_web_citations(response.citations, ledger)

            assistant_message = Message(
                role="assistant",
                content=response.text or "",
                tool_calls=tuple(response.tool_calls),
            )
            messages.append(assistant_message)

            if not response.tool_calls:
                if workspace.finalized:
                    return workspace.to_result(status="completed")
                return workspace.to_result(
                    status="failed",
                    message=(
                        "Model ended turn without calling any tool and "
                        "without calling finalize(). Likely the run was "
                        "truncated or the prompt was misunderstood."
                    ),
                )

            for call in response.tool_calls:
                result_message = _dispatch_one(call, tools_by_name)
                messages.append(result_message)

            if workspace.finalized:
                return workspace.to_result(status="completed")

        return workspace.to_result(
            status="failed",
            message=(
                f"v3 run hit hard limit of {self.max_turns} model turns "
                f"without calling finalize(). Partial work preserved."
            ),
        )


def _initial_user_turn(request: RunRequest) -> Message:
    return Message(
        role="user",
        content=(
            f"Produce the report for {request.subject!r}. Follow the "
            f"template described in the system prompt. Use the tools "
            f"provided to research, compute, chart, and write. Call "
            f"`finalize` only after every required section is written."
        ),
    )


def _catalog_to_tool_schemas(catalog: ToolCatalog) -> list[ToolSchema]:
    """Convert dispatched-tool descriptors into LLMRequest tool schemas.

    web_search is omitted — the adapter wires it via native_tools.
    """
    schemas: list[ToolSchema] = []
    for tool in catalog.dispatched_tools:
        d = tool.descriptor
        if d.name == WEB_SEARCH_TOOL_NAME:
            continue
        schemas.append(
            ToolSchema(name=d.name, description=d.description, parameters=d.parameters)
        )
    return schemas


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
                    f"Valid tools: {sorted(tools_by_name)}"
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


def _serialize_result(result: ToolResult) -> str:
    try:
        return json.dumps(result.payload, default=str)
    except TypeError:
        return json.dumps({"summary": result.summary, "payload": str(result.payload)})
