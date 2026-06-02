"""Morning Briefing executor (MB rework Phase 3).

Fires a scheduled ``report_mb`` run. The executor is itself the background
job, so it owns the session and runs the engine to completion inline via
``mb_v2_run_service.run_to_completion`` (NOT the detached ``start_run_async``
path the on-demand HTTP route uses). It loads the firing ``mb_schedules`` row
and its bound config, builds a ``RunRequest`` from that config plus a
``BriefingContext`` (schedule label / time / timezone + the run date), runs the
engine, persists into ``report_mb``, stamps ``mb_schedules.last_run_at``, and
emits one ``REPORT_READY`` notification.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.report_mb import CancelToken as MbCancelToken

from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.registry import JobType, NotificationType
from openlia_server.services import mb_v2_run_service

DEPARTMENT = "morning_briefing"


class _CancelBridge(MbCancelToken):
    """Bridge the scheduler's ``CancellationToken`` to the engine's polled
    ``CancelToken``.

    The two are different classes from different layers — the scheduler
    job framework hands the executor an asyncio-``Event``-backed
    ``CancellationToken``, while the ``report_mb`` engine polls a plain
    boolean ``CancelToken``. Without this bridge a graceful-shutdown
    cancel would mark the job cancelled while the LLM generation ran on to
    completion (the gap EU/MR avoid by forwarding their token).
    """

    def __init__(self, source: CancellationToken) -> None:
        super().__init__()
        self._source = source

    @property
    def cancelled(self) -> bool:
        # The engine polls ``cancel_token.cancelled`` as a property (no
        # call), so this MUST stay a property — a plain method would read
        # as an always-truthy bound method and cancel every run.
        # ``CancellationToken.is_cancelled`` is also a property.
        return self._source.is_cancelled


class MBBriefingExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MB_BRIEFING

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        run_service: Any = mb_v2_run_service,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._run_service = run_service

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
            schedule = session.get(MbSchedule, schedule_id)
            if schedule is None:
                raise RuntimeError(f"mb schedule {schedule_id!r} not found at fire time")
            label = schedule.label or ""
            time_label = schedule.time
            timezone = schedule.timezone
            connectors = dict(schedule.enabled_connectors or {})

            request = self._run_service.build_run_request(
                session,
                user_id=user_id,
                trigger_kind="scheduled",
                template_id=schedule.template_id or "mb_default",
                instructions_id=schedule.instructions_id,
                enabled_connectors=connectors,
                provider_kind=schedule.provider_kind or "anthropic",
                model=schedule.model or "claude-sonnet-4-6",
                language=schedule.language,
                length=schedule.length,
                reasoning_effort=schedule.reasoning_effort,
                run_date=date.today().isoformat(),
                schedule_label=label or None,
                time_label=time_label,
                timezone=timezone,
            )

            report_id, _result = await self._run_service.run_to_completion(
                session,
                user_id=user_id,
                request=request,
                trigger_kind="scheduled",
                schedule_id=schedule_id,
                instructions_id=schedule.instructions_id,
                cancel_token=_CancelBridge(cancel_token) if cancel_token is not None else None,
            )

            schedule.last_run_at = datetime.now(UTC)
            session.commit()

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
