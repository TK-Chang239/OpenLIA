"""NEW-6-07 — result_summary contract.

The DB column for `job_runs.result_summary` is `Text`, so the executor
serializes outcomes via `json.dumps(...)`. Confirm both ends of the
contract agree: write a JSON-encoded summary, read it back, and
re-decode to a dict that matches the executor's outcome."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import ClassVar

import pytest
from _scheduler_fakes import FakeSleep
from openlia.llm.runtime.cancellation import CancellationToken
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.executors.base import (
    BaseExecutor,
    JobOutcome,
    SessionFactory,
)
from openlia_server.scheduler.registry import JobStatus, JobType


class _SmokeExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MB_BRIEFING

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        outcome: JobOutcome,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=FakeSleep())
        self._outcome = outcome

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        return self._outcome


@pytest.mark.asyncio
async def test_result_summary_roundtrips_as_json_text(session_factory) -> None:
    with session_factory() as s:
        s.add(
            User(
                id="u_1",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
                created_at=datetime.now(UTC),
            )
        )
        s.commit()

    summary = {"reports_generated": 3, "report_ids": ["a", "b", "c"]}
    executor = _SmokeExecutor(
        session_factory=session_factory,
        outcome=JobOutcome(result_summary=summary, notifications=[]),
    )
    run_id = await executor.execute(
        user_id="u_1",
        schedule_id="sch_1",
        cancel_token=None,
    )

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        # Stored as a JSON-encoded string in a Text column.
        assert isinstance(row.result_summary, str)
        decoded = json.loads(row.result_summary)
        assert decoded == summary
