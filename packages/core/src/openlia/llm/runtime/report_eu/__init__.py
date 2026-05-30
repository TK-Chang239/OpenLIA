"""Earnings Update v2 engine — single-model tool-use loop.

Forked from report_v3. Public surface for the server, frontend (via the
route layer), and tests. EU v2 differs from v3 in three ways: no
capability gate (web search is opt-in), no revision flow, and a fixed
connector-gated tool catalog (no discovery).
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
from .transports import EuDataTransports
from .workspace import RunWorkspace, WrittenSection

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
