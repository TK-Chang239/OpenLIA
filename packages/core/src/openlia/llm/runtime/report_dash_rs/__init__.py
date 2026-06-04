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
from .schemas import EvidenceItem, RetailSentimentData, RunRequest, RunResult, RunStatus, Signal

try:
    from .runner import Runner
    from .tools.dashboard_tools import (
        CLASSIFY_TOOL_BY_SLUG,
        PAYLOAD_MODEL_BY_SLUG,
        implemented_dashboard_slugs,
    )
except ModuleNotFoundError:
    # Built incrementally — runner/tools land in later tasks.
    pass

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
