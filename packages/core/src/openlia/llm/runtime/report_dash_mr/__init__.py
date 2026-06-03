"""Macro Research dashboard engine — single-model tool-use loop.

Forked from the Morning Briefing engine (``report_mb``). Public surface
for the server, frontend (via the route layer), and tests. This engine
produces typed dashboard payloads for the Macro Research department
rather than a narrative briefing: the tool catalog and output tools will
diverge from report_mb in later tasks to emit structured dashboard
sections (charts, metrics, tables) instead of freeform markdown. It
keeps the MB shape: no capability gate (web search is opt-in), no
revision flow, and a fixed connector-gated tool catalog (no discovery).
No batch mode.
"""

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
    BriefingContext,
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
)
from .session import CapabilityError, CredentialError, LLMSession
from .transports import MbDataTransports
from .workspace import RunWorkspace, WrittenSection

__all__ = [
    "BriefingContext",
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
    "Event",
    "EventBroker",
    "EventEmitter",
    "LLMSession",
    "Language",
    "ListEmitter",
    "MbDataTransports",
    "NullEmitter",
    "ReportLength",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "RunWorkspace",
    "Runner",
    "SectionSpec",
    "TemplateSpec",
    "WrittenSection",
    "is_finish_sentinel",
]
