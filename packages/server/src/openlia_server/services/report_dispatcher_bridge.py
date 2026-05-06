"""Bridge that lets a report runner consume the v2 connector dispatcher.

The runtime `ToolDispatcher` (in `core/llm/runtime/tools.py`) was designed
against a v1 ``DataProviderDispatcher`` Protocol. The chat path migrated
to the v2 ``Dispatcher`` directly (with ``candidate_tools()``,
``dispatch_tool_use()``); the report path was left wired to
``_EmptyDataDispatcher`` as a placeholder.

This bridge plugs the v2 ``Dispatcher`` into the v1 Protocol, applies the
``ReportToolCache`` policy on the way out (warm-up vs steady-state), and
records every tool call into the cache on the way in. One bridge instance
per report run — fields are pinned at construction so the cache knows
exactly which (user, department, run, day) the call belongs to.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from openlia.connectors.dispatch import Dispatcher
from openlia.llm.types import ToolSchema

from openlia_server.services.report_tool_cache import ReportToolCache

log = logging.getLogger(__name__)


@dataclass
class ReportDispatcherBridge:
    """Implements ``DataProviderDispatcher`` for the report runner."""

    dispatcher: Dispatcher
    cache: ReportToolCache
    user_id: str
    department_id: str
    run_id: str
    run_date: date

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        """Return the cache-filtered tool inventory.

        ``department_id`` is supplied by the runner per call. We trust the
        bridge's pinned ``self.department_id`` (set at construction); the
        Protocol parameter is a check-only assert so a misconfigured
        runner fails fast.
        """
        if department_id != self.department_id:
            raise RuntimeError(
                f"bridge pinned to {self.department_id!r} but asked for {department_id!r}"
            )
        full = self._inventory_as_schemas()
        cached = self.cache.tools_for(
            user_id=self.user_id,
            department_id=self.department_id,
            full_inventory=full,
        )
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in cached
        ]

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch through the v2 ``Dispatcher`` and record usage."""
        success = False
        try:
            payload = await self.dispatcher.dispatch_tool_use(tool_name, arguments)
            success = True
        finally:
            try:
                self.cache.record_tool_call(
                    user_id=self.user_id,
                    department_id=self.department_id,
                    run_id=self.run_id,
                    run_date=self.run_date,
                    tool_name=tool_name,
                    success=success,
                )
            except Exception:
                # Cache bookkeeping must never poison the dispatch path.
                log.exception("report_tool_cache.record_tool_call failed")
        if isinstance(payload, dict):
            return payload
        return {"value": payload}

    async def expand_tools(
        self,
        *,
        department_id: str,
        reason: str,
        category_hint: str | None = None,
    ) -> list[dict[str, Any]]:
        """Escalation hook bound to ``request_additional_tools``.

        Returns the rest of the v2 candidate inventory the cache had hidden
        from ``list_requirement_tools``. The runtime de-dupes against
        already-added tools, so we can safely return the full inventory
        and let the dispatcher pick what's new.
        """
        if department_id != self.department_id:
            raise RuntimeError(
                f"bridge pinned to {self.department_id!r} but asked for {department_id!r}"
            )
        out: list[dict[str, Any]] = []
        for entry in self.dispatcher.candidate_tools():
            out.append(
                {
                    "name": entry["name"],
                    "description": entry.get("description", ""),
                    "parameters": entry.get("input_schema") or {},
                }
            )
        return out

    def _inventory_as_schemas(self) -> list[ToolSchema]:
        out: list[ToolSchema] = []
        for entry in self.dispatcher.candidate_tools():
            out.append(
                ToolSchema(
                    name=entry["name"],
                    description=entry.get("description", ""),
                    parameters=entry.get("input_schema") or {},
                )
            )
        return out
