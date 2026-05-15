"""Bridge that lets the report runner consume the v2 connector dispatcher.

The runtime ToolDispatcher (in core/llm/runtime/tools.py) was designed
against a v1 DataProviderDispatcher Protocol. The chat path uses the v2
Dispatcher directly. This bridge plugs the v2 Dispatcher into the v1
Protocol.

Phase B simplification: empty starter pack — `list_requirement_tools`
returns []. The LLM escalates via `request_additional_tools` for every
data tool it needs. `dispatch_requirement` is a thin pass-through.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from openlia.connectors.dispatch import Dispatcher
from openlia.connectors.serialization import to_jsonable
from openlia.llm.runtime.expand_ranking import rank_candidates

log = logging.getLogger(__name__)


@dataclass
class ReportDispatcherBridge:
    """Implements DataProviderDispatcher for the report runner."""

    dispatcher: Dispatcher
    department_id: str

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        """Empty starter pack — the LLM escalates for every data tool."""
        if department_id != self.department_id:
            raise RuntimeError(
                f"bridge pinned to {self.department_id!r} but asked for {department_id!r}"
            )
        return []

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Pass-through to v2 dispatcher; coerce non-dict results.

        Runs the result through `to_jsonable` so non-JSON SDK return types
        (firecrawl-py ExtractResponse/SearchData, other pydantic models,
        dataclasses, datetimes) survive the downstream `json.dumps` when
        the runtime serializes the tool result for the LLM."""
        raw = await self.dispatcher.dispatch_tool_use(tool_name, arguments)
        coerced = to_jsonable(raw)
        return coerced if isinstance(coerced, dict) else {"value": coerced}

    async def available_categories(self) -> list[str]:
        """Return sorted distinct categories from validated connectors,
        excluding web_search (it's already a separate tool, not a category)."""
        from openlia.connectors.types import Category, ConnectorStatus

        return sorted(
            {
                c.category.value
                for c in self.dispatcher.connectors.values()
                if c.status == ConnectorStatus.VALIDATED and c.category != Category.WEB_SEARCH
            }
        )

    async def expand_tools(
        self,
        *,
        department_id: str,
        reason: str,
        category_hint: str | None = None,
    ) -> list[dict[str, Any]]:
        """Rank the candidate inventory by relevance to `reason` + `category_hint`.

        Returns up to 8 candidates (DEFAULT_TOP_K). Runtime de-dupes against
        tools already in the working set, so it's safe to return overlap.
        """
        if department_id != self.department_id:
            raise RuntimeError(
                f"bridge pinned to {self.department_id!r} but asked for {department_id!r}"
            )
        raw_candidates: list[dict[str, Any]] = []
        for entry in self.dispatcher.candidate_tools():
            raw_candidates.append(
                {
                    "name": entry["name"],
                    "description": entry.get("description", ""),
                    "category": entry.get("category"),
                    "input_schema": entry.get("input_schema") or {},
                }
            )
        ranked = rank_candidates(
            raw_candidates,
            reason=reason,
            category_hint=category_hint,
        )
        return [
            {
                "name": c["name"],
                "description": c.get("description", ""),
                "parameters": c.get("input_schema") or {},
            }
            for c in ranked
        ]
