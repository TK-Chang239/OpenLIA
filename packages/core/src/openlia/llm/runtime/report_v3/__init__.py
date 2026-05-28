"""v3 equity-research engine — single-model tool-use loop.

Public surface for the server, frontend (via the route layer), and
tests. Phase 0 ships scaffolding only; later phases add tools, the
loop, persistence, and rendering. See
``planning/2026-05-27-equity-research-v3-single-model-spec.md``.
"""

from .ledger import CitationLedger
from .runner import Runner
from .schemas import (
    ChartDataPoint,
    ChartSpec,
    ChartType,
    CitationLogEntry,
    Language,
    ReportLength,
    RunRequest,
    RunResult,
    RunStatus,
    SectionSpec,
    TemplateSpec,
)
from .session import CapabilityError, LLMSession

__all__ = [
    "CapabilityError",
    "ChartDataPoint",
    "ChartSpec",
    "ChartType",
    "CitationLedger",
    "CitationLogEntry",
    "LLMSession",
    "Language",
    "ReportLength",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "Runner",
    "SectionSpec",
    "TemplateSpec",
]
