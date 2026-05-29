"""Per-request tool catalog assembly.

The runner calls ``build_catalog`` once per run to assemble the tools
the model can invoke. The catalog binds tools to the per-run
``CitationLedger`` and ``RunWorkspace`` so the runner doesn't need to
plumb those through every tool call.

Two tiers:

  - **Core** tools (data + valuation + output + web_search + find_tools)
    are always in the model's request. Small set -> sharp tool selection.
  - **Extended** tools (the long-tail helper catalog) are NOT in the
    request up front. The model calls ``find_tools`` to discover them;
    the runner then injects the discovered schemas into subsequent turns
    via ``active_schemas`` / ``active_tools_by_name``.

Data tool transports (EODHD callables) are passed in by the wiring
layer — same dependency-injection shape v2.3 uses, so the core layer
stays free of EODHD SDK imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ....types import ToolSchema
from ...report_v2_3.research import ResearchTool
from ...report_v2_3.research.registry import (
    FundamentalsTransport,
    NewsTransport,
    PricesTransport,
)
from ..ledger import CitationLedger
from ..workspace import RunWorkspace
from .data_tools import build_data_tools
from .extended_tools import CATEGORY_INDEX, ExtendedTool, build_extended_tools
from .find_tools import ToolDiscoveryState, build_find_tools_tool
from .output_tools import build_output_tools
from .valuation_tools import build_valuation_tools
from .web_search import WEB_SEARCH_TOOL_NAME, build_web_search_descriptor


@dataclass(frozen=True)
class ToolCatalog:
    """The per-run tool catalog the runner dispatches against.

    ``core_tools`` are the function tools always present in the request
    (data, valuation, output, find_tools). ``native_tools`` is the tuple
    fed into ``LLMRequest.native_tools`` for the adapter to wire up
    provider-side (currently just ``("web_search",)``). ``descriptors``
    is the core set the system prompt enumerates — core dispatched +
    native, in registration order.

    ``discovery`` holds the extended (discoverable) registry plus the
    set the model has activated this run via ``find_tools``. The runner
    asks for ``active_schemas`` / ``active_tools_by_name`` each turn so
    discovered tools join the request and become dispatchable.

    ``category_index`` is the Layer-1 capability map the prompt renders.
    """

    core_tools: list[ResearchTool]
    native_tools: tuple[str, ...]
    discovery: ToolDiscoveryState
    category_index: dict[str, str]
    descriptors: list = field(default=None)  # type: ignore[assignment]

    def by_name(self) -> dict[str, ResearchTool]:
        """Core tools keyed by name."""
        return {tool.descriptor.name: tool for tool in self.core_tools}

    def core_schemas(self) -> list[ToolSchema]:
        """Request schemas for the always-on core tools.

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

    def active_schemas(self) -> list[ToolSchema]:
        """Core schemas plus any extended tools the model has discovered."""
        schemas = self.core_schemas()
        for entry in self.discovery.active_tools():
            d = entry.tool.descriptor
            schemas.append(
                ToolSchema(name=d.name, description=d.description, parameters=d.parameters)
            )
        return schemas

    def active_tools_by_name(self) -> dict[str, ResearchTool]:
        """Dispatchable tools: core plus discovered extended tools."""
        merged = self.by_name()
        for entry in self.discovery.active_tools():
            merged[entry.name] = entry.tool
        return merged


def build_catalog(
    *,
    ledger: CitationLedger,
    workspace: RunWorkspace,
    fundamentals: FundamentalsTransport,
    prices: PricesTransport,
    news: NewsTransport,
) -> ToolCatalog:
    """Assemble the full v3 catalog for a single run."""
    data = build_data_tools(
        ledger=ledger,
        fundamentals=fundamentals,
        prices=prices,
        news=news,
    )
    valuation = build_valuation_tools(ledger=ledger)
    output = build_output_tools(workspace=workspace)

    extended: dict[str, ExtendedTool] = build_extended_tools(ledger=ledger)
    discovery = ToolDiscoveryState(extended=extended)
    find_tools = build_find_tools_tool(discovery)

    core = [*data, *valuation, *output, find_tools]

    descriptors = [tool.descriptor for tool in core]
    descriptors.append(build_web_search_descriptor())

    return ToolCatalog(
        core_tools=core,
        native_tools=(WEB_SEARCH_TOOL_NAME,),
        discovery=discovery,
        category_index=dict(CATEGORY_INDEX),
        descriptors=descriptors,
    )
