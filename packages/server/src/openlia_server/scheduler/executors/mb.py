"""Morning Briefing executor. Wires MBRequestBuilder → ReportRunner →
ReportStore pipeline and produces one report_ready notification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from openlia.llm import exceptions as llm_exceptions
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ReportComplete, ReportError

from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.payloads import MBRequestBuilder, ReportStore
from openlia_server.scheduler.registry import JobType, NotificationType

DEPARTMENT = "morning_briefing"


def _raise_from_report_error(event: ReportError) -> None:
    exc_cls = getattr(llm_exceptions, event.error_class, None)
    if exc_cls is not None and issubclass(exc_cls, LLMProviderError):
        raise exc_cls(event.message)
    raise RuntimeError(f"{event.error_class}: {event.message}")


class MBBriefingExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MB_BRIEFING

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        mb_builder: MBRequestBuilder,
        report_runner,
        report_store: ReportStore,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._mb_builder = mb_builder
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

        session = self._session_factory()
        try:
            request = self._mb_builder.build(
                session=session, user_id=user_id, schedule_id=schedule_id
            )
        finally:
            session.close()

        report_payload: dict | None = None
        async for event in self._report_runner.run(
            department_id=DEPARTMENT,
            user_id=user_id,
            request=request,
            cancel_token=cancel_token,
        ):
            if isinstance(event, ReportError):
                _raise_from_report_error(event)
            if isinstance(event, ReportComplete):
                report_payload = event.schema

        if report_payload is None:
            raise RuntimeError("ReportRunner returned without a ReportComplete event")

        session = self._session_factory()
        try:
            report_id = self._report_store.save(
                session=session,
                user_id=user_id,
                department=DEPARTMENT,
                payload=report_payload,
            )
            schedule = session.get(MbSchedule, schedule_id)
            label = schedule.label if schedule is not None else None
            time_label = schedule.time if schedule is not None else "scheduled"
            if schedule is not None:
                schedule.last_run_at = datetime.now(UTC)
            session.commit()
        finally:
            session.close()

        display = label if label else time_label
        return JobOutcome(
            result_summary={"report_id": report_id},
            notifications=[
                NotificationSpec(
                    type=NotificationType.REPORT_READY,
                    department=DEPARTMENT,
                    message=f"Your {display} briefing is ready.",
                )
            ],
        )
