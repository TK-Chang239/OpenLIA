"""SSE event types emitted by ReportRunner and ChatRunner.

Plan 5 will add the full runner implementations. This file defines
only the data types so Plan 6 (scheduler) can reference them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SseEvent:
    """Base class for all SSE events."""


@dataclass(frozen=True)
class ReportStart(SseEvent):
    report_id: str
    department: str
    mode: str
    section_titles: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportSection(SseEvent):
    report_id: str
    title: str
    content: str


@dataclass(frozen=True)
class ReportComplete(SseEvent):
    report_id: str
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportError(SseEvent):
    report_id: str
    message: str
    error_class: str = ""
    retryable: bool = False


@dataclass(frozen=True)
class ChatChunk(SseEvent):
    content: str


@dataclass(frozen=True)
class ChatComplete(SseEvent):
    pass
