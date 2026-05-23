"""SQL-backed StateStore for the v2.3 equity-research pipeline.

Persists each ReportRunner ReportState into `er_v2_3_run_state` so a
`WAITING_ON_USER` suspend in one HTTP request can resume in a later one.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.persistence import (
    StateNotFoundError,
    StateStore,
)
from openlia.llm.runtime.report_v2_3.state import ReportState
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from openlia_server.db.models.er_v2_3_run_state import ErV23RunState


class SqlStateStore(StateStore):
    """StateStore implementation that reads/writes `er_v2_3_run_state`.

    Holds a reference to a SQLAlchemy `Session`; the caller owns the
    transaction boundary (typically per-request via FastAPI dependency).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, state: ReportState) -> None:
        row = self._session.execute(
            select(ErV23RunState).where(ErV23RunState.run_id == state.run_id)
        ).scalar_one_or_none()

        payload = state.model_dump_json()
        now = datetime.now(UTC)

        if row is None:
            row = ErV23RunState(
                run_id=state.run_id,
                user_id=state.user_id,
                status=state.status.value,
                state_json=payload,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.status = state.status.value
            row.state_json = payload
            row.updated_at = now

    def load(self, run_id: str) -> ReportState:
        row = self._session.execute(
            select(ErV23RunState).where(ErV23RunState.run_id == run_id)
        ).scalar_one_or_none()
        if row is None:
            raise StateNotFoundError(run_id)
        return ReportState.model_validate_json(row.state_json)

    def delete(self, run_id: str) -> None:
        self._session.execute(delete(ErV23RunState).where(ErV23RunState.run_id == run_id))
