"""Macro Research dashboard executor (MR dashboard redesign).

Fires a scheduled ``report_dash_mr`` run. Like the MB executor, this
executor is itself the background job: it owns the session and runs the
dashboard engine to completion inline via
``mr_dash_run_service.run_to_cache``, which upserts one typed payload into
``mr_dashboard_cache`` and returns the dashboard slug.

The scheduler hands the executor ``schedule_id`` = the dashboard slug
(``_register_schedule`` puts ``schedule.dashboard`` in the schedule_id
slot for ``MrDashboardState`` rows), so the slug arrives directly as
``schedule_id`` and is forwarded to ``run_to_cache`` as
``dashboard_slug``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.report_dash_mr import CancelToken as MrCancelToken

from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.registry import JobType, NotificationType
from openlia_server.services import mr_dash_run_service

DEPARTMENT = "macro_research"


class _CancelBridge(MrCancelToken):
    """Bridge the scheduler's ``CancellationToken`` to the engine's polled
    ``CancelToken``.

    The two are different classes from different layers — the scheduler
    job framework hands the executor an asyncio-``Event``-backed
    ``CancellationToken``, while the ``report_dash_mr`` engine polls a
    plain boolean ``CancelToken``. Without this bridge a graceful-shutdown
    cancel would mark the job cancelled while the LLM generation ran on to
    completion.
    """

    def __init__(self, source: CancellationToken) -> None:
        super().__init__()
        self._source = source

    @property
    def cancelled(self) -> bool:
        # The engine polls ``cancel_token.cancelled`` as a property (no
        # call), so this MUST stay a property — a plain method would read
        # as an always-truthy bound method and cancel every run.
        return self._source.is_cancelled


class MrDashExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MR_DASH

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        run_service: Any = mr_dash_run_service,
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
        assert schedule_id is not None  # schedule_id IS the dashboard slug

        with self._session_factory() as session:
            slug = await self._run_service.run_to_cache(
                session,
                user_id=user_id,
                dashboard_slug=schedule_id,
                cancel_token=_CancelBridge(cancel_token) if cancel_token is not None else None,
            )
            session.commit()

        return JobOutcome(
            result_summary={"dashboard": slug},
            notifications=[
                NotificationSpec(
                    type=NotificationType.ASSESSMENT_READY,
                    department=DEPARTMENT,
                    message=f"Your {slug} macro dashboard is updated.",
                )
            ],
        )
