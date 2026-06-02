"""EODHD data tools — wraps v2.3 transports for the EU v2 tool catalog.

EU v2 reuses v2.3's ``research/registry.build_eodhd_tools`` to construct
the underlying ``ResearchTool`` objects (same transports, same
provenance attachment). The wrapper here adds two things EU v2 needs:

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

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
    build_eodhd_tools,
    prune_empty,
)
from ...report_v2_3.research.registry import (
    FundamentalsTransport,
    NewsTransport,
    PricesTransport,
)
from ...report_v2_3.schemas import DataProviderSource
from ..ledger import CitationLedger

# Transport the earnings-calendar tool dispatches against. Supplied by
# the server wiring layer; returns the upcoming-events list for a ticker.
EarningsCalendarTransport = Callable[[str], list[dict[str, Any]]]


def build_data_tools(
    *,
    ledger: CitationLedger,
    fundamentals: FundamentalsTransport,
    prices: PricesTransport,
    news: NewsTransport,
) -> list[ResearchTool]:
    """Return the 3 EODHD tools, each ledger-aware.

    Wraps the v2.3 factories so every successful call lands an entry
    in the EU v2 ledger and the model receives the ``source_id`` in the
    tool result payload.
    """
    base_tools = build_eodhd_tools(
        fundamentals=fundamentals,
        prices=prices,
        news=news,
    )
    return [_wrap(tool, ledger) for tool in base_tools]


def _wrap(tool: ResearchTool, ledger: CitationLedger) -> ResearchTool:
    """Wrap a v2.3 ResearchTool so its result lands in the EU v2 ledger."""
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
        # stays under ``data``, pruned of value-less fields so the
        # model's first read (and any cached copy) carries no null or
        # empty noise — connector-agnostic and strictly lossless.
        annotated_payload: dict[str, Any] = {
            "source_id": entry.source_id,
            "summary": result.summary,
            "data": prune_empty(result.payload),
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


def build_earnings_calendar_tool(
    *,
    ledger: CitationLedger,
    earnings_calendar: EarningsCalendarTransport,
) -> ResearchTool:
    """Return the ``get_earnings_calendar`` tool, ledger-aware.

    Wraps a transport callable ``earnings_calendar(ticker) -> list[dict]``
    (the upcoming-events list for a ticker). On a successful call it
    appends one ledger entry so the model receives the assigned
    ``source_id`` alongside the data, and surfaces transport failures as
    a structured ``ToolExecutionError`` the model can react to instead
    of crashing the loop.
    """

    def _execute(args: dict[str, Any]) -> ToolResult:
        ticker = str(args.get("ticker", "")).strip()
        if not ticker:
            raise ToolExecutionError("get_earnings_calendar requires `ticker`.")
        try:
            events = earnings_calendar(ticker)
        except Exception as exc:
            raise ToolExecutionError(
                f"get_earnings_calendar failed for {ticker!r}: {exc!s}"
            ) from exc

        provenance = DataProviderSource(
            provider="EODHD",
            endpoint="calendar/earnings",
            period="upcoming",
            retrieved_at=datetime.now(UTC),
        )
        summary = f"Upcoming earnings for {ticker}: {len(events)} event(s)."
        entry = ledger.append(
            tool_name="get_earnings_calendar",
            arguments=dict(args),
            result_summary=summary,
            provenance=_provenance_to_dict(provenance),
        )
        # Prune the events' value-less fields but keep the
        # ``upcoming_earnings`` key even when empty — an empty list is a
        # meaningful "no upcoming releases" signal, not noise to drop.
        annotated_payload: dict[str, Any] = {
            "source_id": entry.source_id,
            "summary": summary,
            "data": {"ticker": ticker, "upcoming_earnings": prune_empty(list(events))},
        }
        return ToolResult(payload=annotated_payload, provenance=provenance, summary=summary)

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="get_earnings_calendar",
            description=(
                "Fetch the upcoming EODHD earnings calendar for a ticker: "
                "release date(s), timing, and consensus estimates. Use to "
                "confirm the release you are covering and pull estimate "
                "figures to score the print against."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Equity ticker, EODHD-formatted (e.g. 'MSFT.US').",
                    },
                },
                "required": ["ticker"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
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
