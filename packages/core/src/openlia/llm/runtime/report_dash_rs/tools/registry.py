"""Per-request tool catalog assembly for report_dash_rs.

RS omits the curated EODHD data_tools branch (MR's data_tools build
curated quotes/prices/news tools; RS doesn't need them — optional
connector data arrives via dispatcher tools).
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
from .web_search import WEB_SEARCH_TOOL_NAME, build_web_search_descriptor

if TYPE_CHECKING:
    from ...report_dash_mr import MbDataTransports
    from ...report_dash_mr.ledger import CitationLedger
    from ...report_dash_mr.workspace import RunWorkspace


@dataclass(frozen=True)
class ToolCatalog:
    """Per-run tool catalog the runner dispatches against."""

    core_tools: list[ResearchTool]
    native_tools: tuple[str, ...]
    descriptors: list = field(default_factory=list)

    def by_name(self) -> dict[str, ResearchTool]:
        return {tool.descriptor.name: tool for tool in self.core_tools}

    def core_schemas(self) -> list[ToolSchema]:
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
    transports: MbDataTransports,  # accepted for parity, unused — see docstring
    enabled_connectors: EnabledConnectors,
    dashboard_slug: str,
    dispatcher: object | None = None,
) -> ToolCatalog:
    """Assemble the RS dashboard engine's hybrid catalog from connector toggles.

    Always includes emit_dashboard + classify_retail_sentiment.
    Dispatcher tools are added for every enabled non-EODHD connector.
    Native web search is gated by enabled_connectors.web_search.
    The curated EODHD data_tools branch is intentionally omitted for RS.

    ``transports`` is accepted for call-signature parity with the sibling MR
    engine (whose runner shares the catalog-build call shape) but is unused
    here precisely because RS omits that curated EODHD branch. It stays in the
    signature so the shared runner keeps passing it by keyword.
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

    if dispatcher is not None:
        from ...report_dash_mr.tools.dispatcher_tools import build_dispatcher_tools

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
