"""report_dash_rs: Retail Sentiment dashboard engine (report_dash_mr sibling)."""

from __future__ import annotations

from ..report_dash_mr import (
    CancelToken,
    EnabledConnectors,
    EventBroker,
    EventEmitter,
    LLMSession,
    MbDataTransports,
    NullEmitter,
)
from .runner import Runner
from .schemas import EvidenceItem, RetailSentimentData, RunRequest, RunResult, RunStatus, Signal
from .tools.dashboard_tools import (
    CLASSIFY_TOOL_BY_SLUG,
    PAYLOAD_MODEL_BY_SLUG,
    implemented_dashboard_slugs,
)

__all__ = [
    "CLASSIFY_TOOL_BY_SLUG",
    "PAYLOAD_MODEL_BY_SLUG",
    "CancelToken",
    "EnabledConnectors",
    "EventBroker",
    "EventEmitter",
    "EvidenceItem",
    "LLMSession",
    "MbDataTransports",
    "NullEmitter",
    "RetailSentimentData",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "Runner",
    "Signal",
    "implemented_dashboard_slugs",
]
