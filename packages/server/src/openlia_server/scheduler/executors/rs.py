"""Retail Sentiment dashboard executor.

Runs ``rs_dash_run_service.run_to_cache`` for each target ticker and upserts
one ``rs_dashboard_cache`` row per ticker. Mirrors ``MrDashExecutor`` in
session-handling and async-call pattern.

The executor handles two dispatch modes distinguished by ``schedule_id``:

- **Scheduled fan-out**: ``schedule_id`` matches the user's ``RsSchedule.id``
  (a UUID). All watchlist tickers are processed.
- **Manual single-ticker refresh**: the ``/refresh/{ticker}`` route enqueues
  with ``schedule_id = ticker`` (a stock symbol that does not match the
  schedule UUID). Only that ticker is processed.
"""

from __future__ import annotations

from typing import ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.report_dash_rs import CancelToken as RsCancelToken
from sqlalchemy import select

from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.registry import JobType, NotificationType
from openlia_server.services import rs_dash_run_service, rs_schedules

DEPARTMENT = "retail_sentiment"


class _CancelBridge(RsCancelToken):
    """Bridge the scheduler's ``CancellationToken`` to the engine's polled
    ``CancelToken``.

    The RS engine (via ``report_dash_mr``) polls ``cancel_token.cancelled`` as
    a property, while the scheduler hands the executor an asyncio-Event-backed
    ``CancellationToken``. Without this bridge a graceful-shutdown cancel would
    mark the job cancelled while LLM generation ran on to completion.
    """

    def __init__(self, source: CancellationToken) -> None:
        super().__init__()
        self._source = source

    @property
    def cancelled(self) -> bool:
        return self._source.is_cancelled


class RSSnapshotExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.RS_SNAPSHOT

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)

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
            watchlist = [
                t
                for (t,) in session.execute(
                    select(EuWatchlistEntry.ticker).where(EuWatchlistEntry.user_id == user_id)
                ).all()
            ]
            sched = rs_schedules.get_schedule(session, user_id=user_id)

        sched_id = getattr(sched, "id", None)
        if schedule_id and schedule_id != sched_id:
            targets = [schedule_id]  # manual single-ticker refresh
        else:
            targets = watchlist  # scheduled fan-out (or no schedule_id)

        engine_token = _CancelBridge(cancel_token) if cancel_token is not None else None

        processed = 0
        for ticker in targets:
            if cancel_token is not None and cancel_token.is_cancelled:
                break
            with self._session_factory() as session:
                await rs_dash_run_service.run_to_cache(
                    session,
                    user_id=user_id,
                    ticker=ticker,
                    cancel_token=engine_token,
                )
                session.commit()
            processed += 1

        return JobOutcome(
            result_summary={
                "tickers_processed": len(targets),
                "snapshots_written": processed,
            },
            notifications=[
                NotificationSpec(
                    type=NotificationType.ASSESSMENT_READY,
                    department=DEPARTMENT,
                    message=(
                        f"Retail sentiment updated "
                        f"({processed} ticker{'s' if processed != 1 else ''})."
                    ),
                )
            ],
        )
