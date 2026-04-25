"""Retail Sentiment snapshot executor.

Wraps `RsRunner.run_many(...)` against a per-user ticker list. The RS
service writes its own snapshot rows; the executor only counts results
and emits one assessment_ready notification per fire."""

from __future__ import annotations

from typing import Any, ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from sqlalchemy import select

from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.payloads import RSSnapshotRunner
from openlia_server.scheduler.registry import JobType, NotificationType

DEPARTMENT = "retail_sentiment"


class RSSnapshotExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.RS_SNAPSHOT

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        rs_runner: RSSnapshotRunner,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._rs_runner = rs_runner

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        assert user_id is not None

        with self._session_factory() as session:
            tickers = [
                t
                for (t,) in session.execute(
                    select(EuWatchlistEntry.ticker).where(EuWatchlistEntry.user_id == user_id)
                ).all()
            ]

        results: list[Any] = []
        if tickers:
            results = list(self._rs_runner.run_many(tickers))

        return JobOutcome(
            result_summary={
                "tickers_processed": len(tickers),
                "snapshots_written": len(results),
            },
            notifications=[
                NotificationSpec(
                    type=NotificationType.ASSESSMENT_READY,
                    department=DEPARTMENT,
                    message=f"Retail sentiment snapshot updated ({len(results)} tickers).",
                )
            ],
        )
