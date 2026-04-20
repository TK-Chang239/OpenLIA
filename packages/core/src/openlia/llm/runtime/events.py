"""SSE event dataclasses (chat.* and report.* discriminated union).

Every event has a class-level `TYPE` literal used by `to_wire()` to build
the on-the-wire dict. Serialization into SSE frames (`data: ...\\n\\n`)
happens in the server route; this module stays pure-data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

ReportPhaseName = Literal["fetching_data", "writing", "finalizing"]
_ALLOWED_PHASES: tuple[str, ...] = ("fetching_data", "writing", "finalizing")


@dataclass(frozen=True)
class ChatStart:
    TYPE = "chat.start"
    message_id: str


@dataclass(frozen=True)
class ChatToolCallStart:
    TYPE = "chat.tool_call.start"
    message_id: str
    call_id: str
    tool_name: str
    args_preview: str


@dataclass(frozen=True)
class ChatToolCallResult:
    TYPE = "chat.tool_call.result"
    message_id: str
    call_id: str
    ok: bool
    summary: str


@dataclass(frozen=True)
class ChatToken:
    TYPE = "chat.token"
    message_id: str
    text: str


@dataclass(frozen=True)
class ChatReportThumbnail:
    TYPE = "chat.report_thumbnail"
    message_id: str
    report_id: str
    mode: str


@dataclass(frozen=True)
class ChatDone:
    TYPE = "chat.done"
    message_id: str
    stop_reason: str


@dataclass(frozen=True)
class ChatError:
    TYPE = "chat.error"
    message_id: str
    error_class: str
    message: str


@dataclass(frozen=True)
class ReportStart:
    TYPE = "report.start"
    report_id: str
    department: str
    mode: str
    section_titles: list[str]


@dataclass(frozen=True)
class ReportPhase:
    TYPE = "report.phase"
    report_id: str
    phase: str

    def __post_init__(self) -> None:
        if self.phase not in _ALLOWED_PHASES:
            raise ValueError(f"phase must be one of {_ALLOWED_PHASES}, got {self.phase!r}")


@dataclass(frozen=True)
class ReportToolCall:
    TYPE = "report.tool_call"
    report_id: str
    tool_name: str
    summary: str


@dataclass(frozen=True)
class ReportComplete:
    TYPE = "report.complete"
    report_id: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class ReportError:
    TYPE = "report.error"
    report_id: str
    error_class: str
    message: str


SseEvent = (
    ChatStart
    | ChatToolCallStart
    | ChatToolCallResult
    | ChatToken
    | ChatReportThumbnail
    | ChatDone
    | ChatError
    | ReportStart
    | ReportPhase
    | ReportToolCall
    | ReportComplete
    | ReportError
)


def to_wire(event: SseEvent) -> dict[str, Any]:
    """Return a JSON-serializable dict with `type` plus the event fields."""
    payload = {"type": event.TYPE}
    payload.update(asdict(event))
    return payload
