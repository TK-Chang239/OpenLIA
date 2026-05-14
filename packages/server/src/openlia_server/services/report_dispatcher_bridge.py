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
        """Pass-through to v2 dispatcher; coerce non-dict results."""
        payload = await self.dispatcher.dispatch_tool_use(tool_name, arguments)
        return payload if isinstance(payload, dict) else {"value": payload}

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
        """Escalation hook bound to `request_additional_tools`.

        Returns the full candidate inventory. Runtime de-dupes against
        already-added tools. PR3.4 will replace this with rank_candidates;
        for now (PR3.2) keep behavior identical to today.
        """
        if department_id != self.department_id:
            raise RuntimeError(
                f"bridge pinned to {self.department_id!r} but asked for {department_id!r}"
            )
        return [
            {
                "name": entry["name"],
                "description": entry.get("description", ""),
                "parameters": entry.get("input_schema") or {},
            }
            for entry in self.dispatcher.candidate_tools()
        ]
