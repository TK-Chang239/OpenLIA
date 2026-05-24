"""Service layer for v2.3 run lifecycle.

Wraps the ReportRunner + StateStore so the route layer can do:
  - start_run(...)         -> persists initial state, runs to first suspend/complete
  - answer_run(...)        -> resumes from persisted state, runs to next suspend/complete
  - get_run(...)           -> reads persisted state
  - list_runs(...)         -> lightweight summaries for the Repository surface
  - delete_run(...)        -> drop a run

The service owns the persistence boundary: every entry point commits the
DB session after a successful save so the suspended state survives the
HTTP response.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from openlia.llm.runtime.report_v2_3.events import RunnerEvent
from openlia.llm.runtime.report_v2_3.persistence import StateNotFoundError
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyAnswers,
    Language,
    ReportLength,
    ReportType,
)
from openlia.llm.runtime.report_v2_3.state import ReportState
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.er_v2_3_run_state import ErV23RunState

from .v2_3_runner_factory import V23RunnerFactory
from .v2_3_state_store import SqlStateStore

Observer = Callable[[RunnerEvent], None]


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Lightweight projection of a persisted run for list views.

    Decodes only the small subset of ``state_json`` the Repository UI
    actually needs (tickers, prompt head, report_type, language) — the
    full state stays out of the list response.
    """

    run_id: str
    status: str
    tickers: list[str]
    raw_prompt: str
    report_type: str
    length: str
    language: str
    created_at: datetime
    updated_at: datetime


def start_run(
    *,
    db: DBSession,
    runner_factory: V23RunnerFactory,
    user_id: str,
    raw_prompt: str,
    language: Language,
    report_type: ReportType,
    length: ReportLength,
    tickers: list[str],
    template_id: str | None = None,
    observer: Observer | None = None,
) -> ReportState:
    """Begin a new v2.3 run. Persists the resulting state.

    When ``observer`` is supplied, the runner emits ``RunnerEvent``
    instances at every stage boundary so an SSE route can stream
    progress live. The observer is invoked synchronously inside the
    runner; the route layer typically passes a callback that pushes to
    a queue consumed by the SSE generator.
    """
    state = ReportState(
        run_id=str(uuid.uuid4()),
        user_id=user_id,
        raw_prompt=raw_prompt,
        language=language,
        report_type=report_type,
        length=length,
        template_id=template_id,
        tickers=tickers,
    )
    runner = runner_factory()
    state = runner.start(state, observer=observer)

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
    observer: Observer | None = None,
) -> ReportState:
    """Resume a suspended run with the user's clarifier answers."""
    store = SqlStateStore(db)
    state = store.load(run_id)
    if state.user_id != user_id:
        raise PermissionError(f"run {run_id} does not belong to user {user_id}")

    runner = runner_factory()
    state = runner.resume(state, answers, observer=observer)

    store.save(state)
    db.commit()
    return state


def list_runs(
    *,
    db: DBSession,
    user_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[RunSummary]:
    """Return the caller's runs newest-first.

    Filters on ``status`` when supplied (e.g. ``"complete"``). The
    ``state_json`` blob is parsed in Python because SQLite (our dev
    backend) has no first-class JSON ops we want to depend on; for
    production scale this would migrate to a denormalized projection
    or PostgreSQL JSON path expressions.
    """
    stmt = (
        select(ErV23RunState)
        .where(ErV23RunState.user_id == user_id)
        .order_by(ErV23RunState.updated_at.desc())
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(ErV23RunState.status == status)
    rows = db.execute(stmt).scalars().all()
    out: list[RunSummary] = []
    for row in rows:
        try:
            payload = json.loads(row.state_json)
        except json.JSONDecodeError:
            continue
        out.append(
            RunSummary(
                run_id=row.run_id,
                status=row.status,
                tickers=list(payload.get("tickers") or []),
                raw_prompt=str(payload.get("raw_prompt") or ""),
                report_type=str(payload.get("report_type") or ""),
                length=str(payload.get("length") or "normal"),
                language=str(payload.get("language") or ""),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return out


def delete_run(*, db: DBSession, user_id: str, run_id: str) -> None:
    """Delete a run if it belongs to the caller."""
    store = SqlStateStore(db)
    state = store.load(run_id)
    if state.user_id != user_id:
        raise PermissionError(f"run {run_id} does not belong to user {user_id}")
    store.delete(run_id)
    db.commit()


def get_run(*, db: DBSession, user_id: str, run_id: str) -> ReportState:
    store = SqlStateStore(db)
    state = store.load(run_id)
    if state.user_id != user_id:
        raise PermissionError(f"run {run_id} does not belong to user {user_id}")
    return state


__all__ = [
    "RunSummary",
    "StateNotFoundError",
    "answer_run",
    "delete_run",
    "get_run",
    "list_runs",
    "start_run",
]
