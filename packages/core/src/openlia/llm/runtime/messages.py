"""Data types shared between runners and their callers.

Full runner implementations (ReportRunner, BatchRunner, ChatRunner)
are added by Plan 5. This file only defines the pure data types so that
scheduler code (Plan 6) can reference them before Plan 5 ships."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReportRequest:
    mode: str
    user_input: str
    custom_sections: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BatchItem:
    id: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BatchResult:
    id: str
    ok: bool
    data: dict[str, Any] | None
    error: str | None


@dataclass
class CancellationToken:
    """Simple cancellation flag. Call cancel() to signal; check cancelled property."""

    _cancelled: bool = field(default=False, init=False)

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled
