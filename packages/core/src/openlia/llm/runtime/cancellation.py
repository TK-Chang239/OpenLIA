"""Cancellation token used to signal executors to stop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CancellationToken:
    """Simple cancellation flag. Call cancel() to signal; check is_cancelled."""

    _cancelled: bool = field(default=False, init=False)

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled
