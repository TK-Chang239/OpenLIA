"""Per-request tool catalog assembly.

The runner calls ``build_catalog`` once per run to assemble the tools
the model can invoke. The catalog binds tools to the per-run
``CitationLedger`` and ``RunWorkspace`` so the runner doesn't need to
plumb those through every tool call.

EU v2 has no tool discovery and no extended/valuation tools — the
catalog is a fixed set gated by the user's connector toggles. Output
tools (``write_section``, ``set_cover``, ``emit_chart``, ``finalize``)
are always present; data tools, the earnings-calendar tool, and native
web search are each included only when their connector is enabled.

Data tool transports (EODHD callables) arrive via the ``EuDataTransports``
bundle passed in by the wiring layer — same dependency-injection shape
v2.3 uses, so the core layer stays free of EODHD SDK imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ....types import ToolSchema
from ...report_v2_3.research import ResearchTool
from ..schemas import EnabledConnectors
from .data_tools import build_data_tools, build_earnings_calendar_tool
from .output_tools import build_output_tools
from .web_search import WEB_SEARCH_TOOL_NAME, build_web_search_descriptor

if TYPE_CHECKING:
    from .. import EuDataTransports
    from ..ledger import CitationLedger
    from ..workspace import RunWorkspace


@dataclass(frozen=True)
class ToolCatalog:
    """The per-run tool catalog the runner dispatches against.

    ``core_tools`` are the function tools present in the request this
    run (output tools always; data + earnings-calendar tools when their
    connector is on). ``native_tools`` is the tuple fed into
    ``LLMRequest.native_tools`` for the adapter to wire up provider-side
    (``("web_search",)`` when web search is enabled, else empty).
    ``descriptors`` is the set the system prompt enumerates — core
    dispatched plus the native web-search descriptor when present.
    """

    core_tools: list[ResearchTool]
    native_tools: tuple[str, ...]
    descriptors: list = field(default_factory=list)

    def by_name(self) -> dict[str, ResearchTool]:
        """Core tools keyed by name."""
        return {tool.descriptor.name: tool for tool in self.core_tools}

    def core_schemas(self) -> list[ToolSchema]:
        """Request schemas for the dispatched core tools.

        ``web_search`` is omitted — the adapter wires it via native_tools.
        """
        schemas: list[ToolSchema] = []
        for tool in self.core_tools:
            d = tool.descriptor
            if d.name == WEB_SEARCH_TOOL_NAME:
                continue
            schemas.append(
                ToolSchema(name=d.name, description=d.description, parameters=d.parameters)
            )
        return schemas


def build_catalog(
    *,
    ledger: CitationLedger,
    workspace: RunWorkspace,
    transports: EuDataTransports,
    enabled_connectors: EnabledConnectors,
) -> ToolCatalog:
    """Assemble the EU v2 catalog from the user's connector toggles.

    Output tools (write_section, set_cover, emit_chart, finalize) are
    always present. The EODHD data tools plus the earnings-calendar tool
    are gated by ``enabled_connectors.eodhd``; native web search is
    gated by ``enabled_connectors.web_search``.
    """
    output = build_output_tools(workspace=workspace)
    core: list[ResearchTool] = [*output]

    if enabled_connectors.eodhd:
        core.extend(
            build_data_tools(
                ledger=ledger,
                fundamentals=transports.fundamentals,
                prices=transports.prices,
                news=transports.news,
            )
        )
        core.append(
            build_earnings_calendar_tool(
                ledger=ledger,
                earnings_calendar=transports.earnings_calendar,
            )
        )

    native: tuple[str, ...] = (WEB_SEARCH_TOOL_NAME,) if enabled_connectors.web_search else ()

    descriptors = [tool.descriptor for tool in core]
    if enabled_connectors.web_search:
        descriptors.append(build_web_search_descriptor())

    return ToolCatalog(
        core_tools=core,
        native_tools=native,
        descriptors=descriptors,
    )
