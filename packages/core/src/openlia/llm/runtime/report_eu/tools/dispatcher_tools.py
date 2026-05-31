"""Dispatcher-backed connector tools for the EU v2 catalog.

Mirrors the curated EODHD wrapper in ``data_tools.py`` (ledger
integration + ``source_id`` echo + structured failures) but builds its
tools from a connector ``Dispatcher`` instead of v2.3 transports, and
runs ``execute`` asynchronously so it can await the dispatcher.

For every candidate tool the dispatcher exposes (``provider__tool``),
this module emits one async, ledger-aware ``ResearchTool`` — skipping
EODHD (curated elsewhere) and any provider the run did not enable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from openlia.connectors.serialization import to_jsonable

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
    prune_empty,
)
from ...report_v2_3.schemas import DataProviderSource
from ..ledger import CitationLedger


def build_dispatcher_tools(
    *,
    ledger: CitationLedger,
    dispatcher: Any,
    enabled_provider_ids: frozenset[str],
) -> list[ResearchTool]:
    """Wrap a dispatcher's candidate tools as EU v2 ``ResearchTool``s.

    One async, ledger-aware tool per candidate whose provider is enabled
    and is not the curated EODHD provider.
    """
    tools: list[ResearchTool] = []
    for td in dispatcher.candidate_tools():
        name = td["name"]
        provider_id = name.split("__", 1)[0]
        if provider_id == "eodhd":
            continue
        if provider_id not in enabled_provider_ids:
            continue
        tools.append(_build_tool(td, ledger=ledger, dispatcher=dispatcher))
    return tools


def _build_tool(
    td: dict[str, Any],
    *,
    ledger: CitationLedger,
    dispatcher: Any,
) -> ResearchTool:
    name = td["name"]
    provider_id, _, tool_part = name.partition("__")

    async def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            raw = await dispatcher.dispatch_tool_use(name, args)
        except Exception as exc:
            raise ToolExecutionError(f"{name} failed: {exc!s}") from exc

        data = prune_empty(to_jsonable(raw))
        provenance = DataProviderSource(
            provider=provider_id.upper(),
            endpoint=tool_part,
            period="latest",
            retrieved_at=datetime.now(UTC),
        )
        summary = f"{provider_id} {tool_part} result"
        entry = ledger.append(
            tool_name=name,
            arguments=dict(args),
            result_summary=summary,
            provenance=_provenance_to_dict(provenance),
        )
        return ToolResult(
            payload={"source_id": entry.source_id, "summary": summary, "data": data},
            provenance=provenance,
            summary=summary,
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name=name,
            description=td.get("description", ""),
            parameters=td.get("input_schema") or {"type": "object", "properties": {}},
        ),
        execute=_execute,
    )


def _provenance_to_dict(provenance: Any) -> dict[str, Any]:
    """Best-effort serialization of a v2.3 Provenance variant."""
    if hasattr(provenance, "model_dump"):
        try:
            return provenance.model_dump(mode="json")
        except Exception:
            pass
    return {"raw": str(provenance)}


__all__ = ["build_dispatcher_tools"]
