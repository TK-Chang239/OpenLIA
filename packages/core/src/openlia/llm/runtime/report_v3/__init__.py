"""v3 equity-research engine — single-model tool-use loop.

Public surface for the server, frontend (via the route layer), and
tests. Phase 0 shipped scaffolding; Phase 1 ships the tool catalog +
main loop. Persistence and rendering land in Phase 2. See
``planning/2026-05-27-equity-research-v3-single-model-spec.md``.
"""

from .ledger import CitationLedger
from .runner import DataTransports, Runner
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
from .session import CapabilityError, CredentialError, LLMSession
from .workspace import RunWorkspace, WrittenSection

__all__ = [
    "CapabilityError",
    "ChartDataPoint",
    "ChartSpec",
    "ChartType",
    "CitationLedger",
    "CitationLogEntry",
    "CredentialError",
    "DataTransports",
    "LLMSession",
    "Language",
    "ReportLength",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "RunWorkspace",
    "Runner",
    "SectionSpec",
    "TemplateSpec",
    "WrittenSection",
]
