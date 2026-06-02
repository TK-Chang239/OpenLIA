"""Earnings Update executor. Runs ReportRunner sequentially for every
ticker the planner returns; one notification per completed report."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ReportComplete, ReportError

from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
    raise_from_report_error,
)
from openlia_server.scheduler.payloads import EUScanPlanner, ReportStore
from openlia_server.scheduler.registry import JobType, NotificationType

DEPARTMENT = "earnings_update"


class EUScanExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.EU_SCAN

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        eu_planner: EUScanPlanner,
        report_runner: Any,
        report_store: ReportStore,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._eu_planner = eu_planner
        self._report_runner = report_runner
        self._report_store = report_store

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        assert user_id is not None
        assert schedule_id is not None

        with self._session_factory() as session:
            schedule = session.get(EuSchedule, schedule_id)
            since = schedule.last_run_at if schedule is not None else None
            targets = self._eu_planner.plan(
                session=session,
                user_id=user_id,
                schedule_id=schedule_id,
                since=since,
            )

        report_ids: list[str] = []
        notifications: list[NotificationSpec] = []

        for target in targets:
            payload: dict[str, Any] | None = None
            async for event in self._report_runner.run(
                department_id=DEPARTMENT,
                user_id=user_id,
                request=target.request,
                cancel_token=cancel_token,
            ):
                if isinstance(event, ReportError):
                    raise_from_report_error(event)
                if isinstance(event, ReportComplete):
                    payload = event.schema

            if payload is None:
                raise RuntimeError(
                    f"ReportRunner returned without ReportComplete for {target.ticker!r}"
                )

            with self._session_factory() as session:
                report_id = self._report_store.save(
                    session=session,
                    user_id=user_id,
                    department=DEPARTMENT,
                    payload=payload,
                )
                session.commit()
            report_ids.append(report_id)
            notifications.append(
                NotificationSpec(
                    type=NotificationType.REPORT_READY,
                    department=DEPARTMENT,
                    message=f"New earnings analysis: {target.ticker}.",
                )
            )

        with self._session_factory() as session:
            schedule = session.get(EuSchedule, schedule_id)
            if schedule is not None:
                schedule.last_run_at = datetime.now(UTC)
                session.commit()

        return JobOutcome(
            result_summary={
                "reports_generated": len(report_ids),
                "report_ids": report_ids,
            },
            notifications=notifications,
        )
