"""Per-request tool catalog assembly.

The runner calls ``build_catalog`` once per run to assemble the tools
the model can invoke. The catalog binds tools to the per-run
``CitationLedger`` and ``RunWorkspace`` so the runner doesn't need to
plumb those through every tool call.

Data tool transports (EODHD callables) are passed in by the wiring
layer — same dependency-injection shape v2.3 uses, so the core layer
stays free of EODHD SDK imports.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...report_v2_3.research import ResearchTool
from ...report_v2_3.research.registry import (
    FundamentalsTransport,
    NewsTransport,
    PricesTransport,
)
from ..ledger import CitationLedger
from ..workspace import RunWorkspace
from .data_tools import build_data_tools
from .output_tools import build_output_tools
from .valuation_tools import build_valuation_tools
from .web_search import WEB_SEARCH_TOOL_NAME, build_web_search_descriptor


@dataclass(frozen=True)
class ToolCatalog:
    """The per-run tool catalog the runner dispatches against.

    ``dispatched_tools`` are the function tools the runner executes
    locally (data, valuation, output). ``native_tools`` is the tuple
    fed into ``LLMRequest.native_tools`` for the adapter to wire up
    provider-side (currently just ``("web_search",)``). ``descriptors``
    is the full set the system prompt enumerates — dispatched +
    native, in registration order.
    """

    dispatched_tools: list[ResearchTool]
    native_tools: tuple[str, ...]
    descriptors: list = None  # type: ignore[assignment]

    def by_name(self) -> dict[str, ResearchTool]:
        return {tool.descriptor.name: tool for tool in self.dispatched_tools}


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
    dispatched = [*data, *valuation, *output]

    descriptors = [tool.descriptor for tool in dispatched]
    descriptors.append(build_web_search_descriptor())

    return ToolCatalog(
        dispatched_tools=dispatched,
        native_tools=(WEB_SEARCH_TOOL_NAME,),
        descriptors=descriptors,
    )
