"""ReportState persistence — protocol + in-memory implementation.

The runner does NOT call the store itself; the calling layer (API route,
background task, test) is responsible for `save()` after each `start()` or
`resume()` returns. That keeps `ReportRunner` synchronous and trivially
testable, and lets the server pick its own transaction boundary.

A SQL-backed implementation lives in `packages/server/.../services/v2_3_state_store.py`.
"""

from __future__ import annotations

from typing import Protocol

from .state import ReportState


class StateNotFoundError(KeyError):
    """Raised when a StateStore can't find the requested run_id."""


class StateStore(Protocol):
    """Persistent home for ReportState across suspend/resume."""

    def save(self, state: ReportState) -> None: ...

    def load(self, run_id: str) -> ReportState: ...

    def delete(self, run_id: str) -> None: ...


class InMemoryStateStore(StateStore):
    """Dict-backed StateStore. Tests and single-process dev use this."""

    def __init__(self) -> None:
        self._by_run_id: dict[str, str] = {}

    def save(self, state: ReportState) -> None:
        self._by_run_id[state.run_id] = state.model_dump_json()

    def load(self, run_id: str) -> ReportState:
        if run_id not in self._by_run_id:
            raise StateNotFoundError(run_id)
        return ReportState.model_validate_json(self._by_run_id[run_id])

    def delete(self, run_id: str) -> None:
        self._by_run_id.pop(run_id, None)

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._by_run_id
