"""Earnings Update v2 engine — single-model tool-use loop.

Forked from report_v3. Public surface for the server, frontend (via the
route layer), and tests. EU v2 differs from v3 in three ways: no
capability gate (web search is opt-in), no revision flow, and a fixed
connector-gated tool catalog (no discovery).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .events import (
    BrokerEmitter,
    CancelToken,
    Event,
    EventBroker,
    EventEmitter,
    ListEmitter,
    NullEmitter,
    is_finish_sentinel,
)
from .ledger import CitationLedger
from .runner import Runner
from .schemas import (
    ChartDataPoint,
    ChartSpec,
    ChartType,
    CitationLogEntry,
    CoverMetric,
    CoverSpec,
    EnabledConnectors,
    Language,
    ReportLength,
    RunRequest,
    RunResult,
    RunStatus,
    SectionSpec,
    TemplateSpec,
    TriggerContext,
)
from .session import CapabilityError, CredentialError, LLMSession
from .workspace import RunWorkspace, WrittenSection


@dataclass(frozen=True)
class EuDataTransports:
    """Callables the EU v2 data tools dispatch against.

    Supplied by the server wiring layer so the core package stays free
    of the EODHD SDK. ``earnings_calendar`` returns the upcoming-events
    list for a ticker.
    """

    fundamentals: Callable[[str], dict[str, Any]]
    prices: Callable[[str, str, str], list[dict[str, Any]]]
    news: Callable[[str, int], list[dict[str, Any]]]
    earnings_calendar: Callable[[str], list[dict[str, Any]]]


__all__ = [
    "BrokerEmitter",
    "CancelToken",
    "CapabilityError",
    "ChartDataPoint",
    "ChartSpec",
    "ChartType",
    "CitationLedger",
    "CitationLogEntry",
    "CoverMetric",
    "CoverSpec",
    "CredentialError",
    "EnabledConnectors",
    "EuDataTransports",
    "Event",
    "EventBroker",
    "EventEmitter",
    "LLMSession",
    "Language",
    "ListEmitter",
    "NullEmitter",
    "ReportLength",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "RunWorkspace",
    "Runner",
    "SectionSpec",
    "TemplateSpec",
    "TriggerContext",
    "WrittenSection",
    "is_finish_sentinel",
]
