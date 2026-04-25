"""SSE event dataclasses (chat.* and report.* discriminated union).

Every event has a class-level `TYPE` literal used by `to_wire()` to build
the on-the-wire dict. Serialization into SSE frames (`data: ...\\n\\n`)
happens in the server route; this module stays pure-data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

ReportPhaseName = Literal["fetching_data", "writing", "finalizing"]
_ALLOWED_PHASES: tuple[str, ...] = ("fetching_data", "writing", "finalizing")


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp (e.g. `2026-04-24T23:18:00.123456+00:00`)."""
    return datetime.now(UTC).isoformat()


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
    # Optional structured payload for UI-consumable tools (e.g. Secretary's
    # `suggest_redirect`, which echoes `{department, reason, prefill}` so
    # the frontend can render a `RedirectCard`). None for data-provider
    # tools whose payloads feed the LLM, not the UI.
    structured: dict[str, Any] | None = None


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
    # `mode` is the canonical field per the runtime spec (e.g. "stock_initiation").
    mode: str
    # `filename` retained for FE backwards compatibility — emitting code may
    # pass an empty string. Treat as deprecated; consumers should prefer `mode`.
    filename: str = ""


@dataclass(frozen=True)
class ChatDone:
    TYPE = "chat.done"
    message_id: str
    stop_reason: str
    ts: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class ChatError:
    TYPE = "chat.error"
    message_id: str
    error_class: str
    message: str
    ts: str = field(default_factory=_utc_now_iso)


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
class ReportToolCallStart:
    TYPE = "report.tool_call.start"
    report_id: str
    call_id: str
    tool_name: str
    args_preview: str


@dataclass(frozen=True)
class ReportToolCall:
    TYPE = "report.tool_call"
    report_id: str
    tool_name: str
    summary: str
    call_id: str = ""


@dataclass(frozen=True)
class ReportSectionStart:
    TYPE = "report.section.start"
    report_id: str
    section_id: str
    title: str
    idx: int
    total: int


@dataclass(frozen=True)
class ReportSectionChunk:
    TYPE = "report.section.chunk"
    report_id: str
    section_id: str
    text: str


@dataclass(frozen=True)
class ReportSectionComplete:
    TYPE = "report.section.complete"
    report_id: str
    section_id: str
    blocks: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class ReportComplete:
    TYPE = "report.complete"
    report_id: str
    # TODO(plan-13): narrow to ReportSchema once Phase 13 ships the type.
    schema: dict[str, Any]
    ts: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class ReportError:
    TYPE = "report.error"
    report_id: str
    error_class: str
    message: str
    ts: str = field(default_factory=_utc_now_iso)


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
    | ReportToolCallStart
    | ReportToolCall
    | ReportSectionStart
    | ReportSectionChunk
    | ReportSectionComplete
    | ReportComplete
    | ReportError
)


def to_wire(event: SseEvent) -> dict[str, Any]:
    """Return a JSON-serializable dict with `type` plus the event fields."""
    payload = {"type": event.TYPE}
    payload.update(asdict(event))
    return payload
