"""Morning Briefing engine — single-model tool-use loop.

Forked from the Earnings Update v2 engine (``report_eu``). Public
surface for the server, frontend (via the route layer), and tests. The
Morning Briefing engine writes a recurring market briefing rather than a
single-ticker earnings report: the earnings/ticker anchor is replaced by
a briefing anchor (``BriefingContext``) and the tool catalog favors
market-wide data (multi-ticker quotes, historical prices, market and
symbol news, economic calendar, macro indicators). It keeps the EU
shape: no capability gate (web search is opt-in), no revision flow, and a
fixed connector-gated tool catalog (no discovery). No batch mode.
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
    MacroSnapshotContext,
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
    "MacroSnapshotContext",
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
