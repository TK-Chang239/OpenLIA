"""The ``find_tools`` discovery tool — Layer 2 of the v3 tool model.

The model calls ``find_tools(query=..., category=...)`` mid-run to
discover specialized tools that are not loaded up front. Matched tools
are recorded in a shared ``ToolDiscoveryState`` so the runner can
inject their schemas into the next request; from then on the model can
call them like any core tool.

This replaces the old planner-driven static selection: discovery is
dynamic and model-driven (it happens when the model realizes it needs
a tool), not frozen before the loop starts.

``find_tools`` itself does NOT append to the citation ledger — it is a
meta-tool, not a source. Its result lists the matched tools' names,
categories, summaries, and full parameter schemas so the model can
call them directly on the following turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
)
from ...report_v2_3.schemas import ComputedSource
from .extended_tools import CATEGORY_INDEX, ExtendedTool, match_extended_tools

FIND_TOOLS_NAME = "find_tools"

_MATCH_LIMIT = 8


@dataclass(slots=True)
class ToolDiscoveryState:
    """Shared, mutable discovery state threaded between find_tools and the runner.

    ``extended`` is the full discoverable registry (name -> ExtendedTool).
    ``activated`` accumulates the names the model has discovered this run;
    the runner reads it each turn to decide which extended schemas to add
    to the request and which tools to make dispatchable. Activation is
    sticky — once discovered, a tool stays callable for the rest of the run.
    """

    extended: dict[str, ExtendedTool]
    activated: set[str] = field(default_factory=set)

    def activate(self, names: list[str]) -> None:
        for name in names:
            if name in self.extended:
                self.activated.add(name)

    def active_tools(self) -> list[ExtendedTool]:
        return [self.extended[n] for n in self.activated if n in self.extended]


def build_find_tools_tool(state: ToolDiscoveryState) -> ResearchTool:
    """Build the ``find_tools`` meta-tool bound to the discovery state."""

    def _execute(args: dict[str, Any]) -> ToolResult:
        query = args.get("query")
        category = args.get("category")
        if not _nonempty(query) and not _nonempty(category):
            raise ToolExecutionError(
                "find_tools requires at least one of `query` or `category`. "
                f"Valid categories: {sorted(CATEGORY_INDEX)}."
            )
        if _nonempty(category) and category.strip().lower() not in CATEGORY_INDEX:
            raise ToolExecutionError(
                f"Unknown category {category!r}. Valid categories: {sorted(CATEGORY_INDEX)}."
            )

        matched, total = match_extended_tools(
            state.extended,
            query=query if _nonempty(query) else None,
            category=category if _nonempty(category) else None,
            limit=_MATCH_LIMIT,
        )
        state.activate([e.name for e in matched])

        tools_payload = [
            {
                "name": e.name,
                "category": e.category,
                "summary": e.summary,
                "description": e.tool.descriptor.description,
                "parameters": e.tool.descriptor.parameters,
            }
            for e in matched
        ]
        payload: dict[str, Any] = {
            "matched_tools": tools_payload,
            "total_matched": total,
            "note": (
                "These tools are now available to call directly. "
                "Cite their results by the source_id each returns."
            ),
        }
        if total > len(matched):
            payload["truncated"] = (
                f"{total} tools matched; showing {len(matched)}. Narrow your query for the rest."
            )
        return ToolResult(
            payload=payload,
            # Discovery is not a citable source; provenance is recorded
            # only to satisfy the ToolResult contract.
            provenance=ComputedSource(method="find_tools", derived_from=["(discovery)"]),
            summary=f"find_tools matched {len(matched)} of {total} tool(s).",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name=FIND_TOOLS_NAME,
            description=(
                "Discover specialized analysis tools that are not loaded by "
                "default (forensic and business-quality scores such as "
                "Piotroski F, Beneish M, and ROIC panels). Pass a `category` "
                "from the capability index and/or a free-text `query` describing "
                "what you need; the matched tools become callable immediately. "
                "Call this whenever the subject needs analysis the core tools "
                "don't cover."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Free-text description of the analysis you need "
                            "(e.g. 'earnings manipulation risk', 'return on "
                            "incremental capital')."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "enum": sorted(CATEGORY_INDEX),
                        "description": "Restrict the search to one capability category.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


__all__ = [
    "FIND_TOOLS_NAME",
    "ToolDiscoveryState",
    "build_find_tools_tool",
]
