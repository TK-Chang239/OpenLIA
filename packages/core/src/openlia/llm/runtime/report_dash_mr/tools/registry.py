"""Per-request tool catalog assembly.

The runner calls ``build_catalog`` once per run to assemble the tools
the model can invoke. The catalog binds tools to the per-run
``CitationLedger`` and ``RunWorkspace`` so the runner doesn't need to
plumb those through every tool call.

The engine has no tool discovery and no extended/valuation tools — the
catalog is a fixed set gated by the user's connector toggles. The
catalog always includes ``emit_dashboard`` (validates and emits the
typed dashboard payload for the requested ``dashboard_slug``) and the
deterministic ``classify_debt_cycle`` quant tool. The curated
market-data tools and native web search are gated by connector toggles
as before.

Data tool transports (EODHD callables) arrive via the ``MbDataTransports``
bundle passed in by the wiring layer — same dependency-injection shape
v2.3 uses, so the core layer stays free of EODHD SDK imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ....types import ToolSchema
from ...report_v2_3.research import ResearchTool
from ..schemas import EnabledConnectors
from .dashboard_tools import (
    CLASSIFY_TOOL_BY_SLUG,
    PAYLOAD_MODEL_BY_SLUG,
    build_emit_dashboard_tool,
)
from .data_tools import build_data_tools
from .web_search import WEB_SEARCH_TOOL_NAME, build_web_search_descriptor

if TYPE_CHECKING:
    from .. import MbDataTransports
    from ..ledger import CitationLedger
    from ..workspace import RunWorkspace


@dataclass(frozen=True)
class ToolCatalog:
    """The per-run tool catalog the runner dispatches against.

    ``core_tools`` are the function tools present in the request this
    run (output tools always; the curated market data tools when their
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
    transports: MbDataTransports,
    enabled_connectors: EnabledConnectors,
    dashboard_slug: str,
    dispatcher: object | None = None,
) -> ToolCatalog:
    """Assemble the dashboard engine's hybrid catalog from connector toggles.

    The output path is the dashboard pair (``emit_dashboard`` +
    ``classify_debt_cycle``) — no write_section / emit_chart / finalize.
    ``emit_dashboard`` is bound to the typed payload model for
    ``dashboard_slug``. The curated market data tools (quotes, historical
    prices, news, economic calendar, macro indicators) are gated by
    ``enabled_connectors.eodhd``. Every other enabled connector is routed
    through ``dispatcher`` (when provided) as dispatcher-backed tools.
    Native web search is gated by ``enabled_connectors.web_search``.
    """
    payload_model = PAYLOAD_MODEL_BY_SLUG.get(dashboard_slug)
    if payload_model is None:
        raise ValueError(
            f"Unknown dashboard_slug {dashboard_slug!r}. "
            f"Known dashboards: {sorted(PAYLOAD_MODEL_BY_SLUG)}."
        )
    core: list[ResearchTool] = [build_emit_dashboard_tool(workspace, payload_model)]
    for classify_builder in CLASSIFY_TOOL_BY_SLUG.get(dashboard_slug, []):
        core.append(classify_builder())

    if enabled_connectors.eodhd:
        core.extend(
            build_data_tools(
                ledger=ledger,
                quotes=transports.quotes,
                prices=transports.prices,
                news=transports.news,
                economic_calendar=transports.economic_calendar,
                macro_indicators=transports.macro_indicators,
            )
        )

    if dispatcher is not None:
        from .dispatcher_tools import build_dispatcher_tools

        core.extend(
            build_dispatcher_tools(
                ledger=ledger,
                dispatcher=dispatcher,
                enabled_provider_ids=enabled_connectors.provider_ids,
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
