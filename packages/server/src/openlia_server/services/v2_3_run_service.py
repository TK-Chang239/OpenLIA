"""Service layer for v2.3 run lifecycle.

Wraps the ReportRunner + StateStore so the route layer can do:
  - start_run(...)         -> persists initial state, runs to first suspend/complete
  - answer_run(...)        -> resumes from persisted state, runs to next suspend/complete
  - get_run(...)           -> reads persisted state

The service owns the persistence boundary: every entry point commits the
DB session after a successful save so the suspended state survives the
HTTP response.
"""

from __future__ import annotations

import uuid

from openlia.llm.runtime.report_v2_3.persistence import StateNotFoundError
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyAnswers,
    Language,
    ReportType,
)
from openlia.llm.runtime.report_v2_3.state import ReportState
from sqlalchemy.orm import Session as DBSession

from .v2_3_runner_factory import V23RunnerFactory
from .v2_3_state_store import SqlStateStore


def start_run(
    *,
    db: DBSession,
    runner_factory: V23RunnerFactory,
    user_id: str,
    raw_prompt: str,
    language: Language,
    report_type: ReportType,
    tickers: list[str],
) -> ReportState:
    """Begin a new v2.3 run. Persists the resulting state."""
    state = ReportState(
        run_id=str(uuid.uuid4()),
        user_id=user_id,
        raw_prompt=raw_prompt,
        language=language,
        report_type=report_type,
        tickers=tickers,
    )
    runner = runner_factory()
    state = runner.start(state)

    store = SqlStateStore(db)
    store.save(state)
    db.commit()
    return state


def answer_run(
    *,
    db: DBSession,
    runner_factory: V23RunnerFactory,
    user_id: str,
    run_id: str,
    answers: ClarifyAnswers,
) -> ReportState:
    """Resume a suspended run with the user's clarifier answers."""
    store = SqlStateStore(db)
    state = store.load(run_id)
    if state.user_id != user_id:
        raise PermissionError(f"run {run_id} does not belong to user {user_id}")

    runner = runner_factory()
    state = runner.resume(state, answers)

    store.save(state)
    db.commit()
    return state


def get_run(*, db: DBSession, user_id: str, run_id: str) -> ReportState:
    store = SqlStateStore(db)
    state = store.load(run_id)
    if state.user_id != user_id:
        raise PermissionError(f"run {run_id} does not belong to user {user_id}")
    return state


__all__ = [
    "StateNotFoundError",
    "answer_run",
    "get_run",
    "start_run",
]
