"""EODHD data tools — wraps v2.3 transports for the v3 tool catalog.

v3 reuses v2.3's ``research/registry.build_eodhd_tools`` to construct
the underlying ``ResearchTool`` objects (same transports, same
provenance attachment). The wrapper here adds two things v3 needs:

1. Ledger integration — every successful tool call appends one entry
   to the run's ``CitationLedger``, and the returned payload is
   wrapped so the model sees the assigned ``source_id`` (e.g.
   ``eodhd_3``) right next to the data.
2. Failure surfacing — when the underlying tool raises, the wrapper
   returns a structured error the model can read and react to,
   instead of bubbling the exception up to the loop.

The actual EODHD HTTP calls happen inside the v2.3 transport
callables passed in by the wiring layer; this module is pure glue.
"""

from __future__ import annotations

from typing import Any

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
    build_eodhd_tools,
)
from ...report_v2_3.research.registry import (
    FundamentalsTransport,
    NewsTransport,
    PricesTransport,
)
from ..ledger import CitationLedger


def build_data_tools(
    *,
    ledger: CitationLedger,
    fundamentals: FundamentalsTransport,
    prices: PricesTransport,
    news: NewsTransport,
) -> list[ResearchTool]:
    """Return the 3 EODHD tools, each ledger-aware.

    Wraps the v2.3 factories so every successful call lands an entry
    in the v3 ledger and the model receives the ``source_id`` in the
    tool result payload.
    """
    base_tools = build_eodhd_tools(
        fundamentals=fundamentals,
        prices=prices,
        news=news,
    )
    return [_wrap(tool, ledger) for tool in base_tools]


def _wrap(tool: ResearchTool, ledger: CitationLedger) -> ResearchTool:
    """Wrap a v2.3 ResearchTool so its result lands in the v3 ledger."""
    inner_execute = tool.execute

    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            result = inner_execute(args)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"{tool.name} failed: {exc!s}") from exc

        entry = ledger.append(
            tool_name=tool.name,
            arguments=dict(args),
            result_summary=result.summary,
            provenance=_provenance_to_dict(result.provenance),
        )
        # Hand the model a payload that begins with the assigned
        # source_id so it knows what to cite. The raw EODHD payload
        # stays under ``data``.
        annotated_payload: dict[str, Any] = {
            "source_id": entry.source_id,
            "summary": result.summary,
            "data": result.payload,
        }
        return ToolResult(
            payload=annotated_payload,
            provenance=result.provenance,
            summary=result.summary,
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name=tool.descriptor.name,
            description=tool.descriptor.description,
            parameters=dict(tool.descriptor.parameters),
        ),
        execute=_execute,
        metadata=dict(tool.metadata),
    )


def _provenance_to_dict(provenance: Any) -> dict[str, Any]:
    """Best-effort serialization of a v2.3 Provenance variant.

    Provenance is a Pydantic discriminated-union; ``model_dump`` works
    for the common shapes. Falls back to ``str()`` for anything else
    so the ledger never crashes on a new provenance type.
    """
    if hasattr(provenance, "model_dump"):
        try:
            return provenance.model_dump(mode="json")
        except Exception:
            pass
    return {"raw": str(provenance)}
