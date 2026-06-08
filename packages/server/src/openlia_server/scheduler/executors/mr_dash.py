"""Macro Research dashboard executor (MR dashboard redesign).

Fires a ``report_dash_mr`` run. Like the MB executor, this executor is
itself the background job: it owns the session and runs the dashboard
engine to completion inline via ``mr_dash_run_service.run_to_cache``,
which upserts one typed payload into ``mr_dashboard_cache``.

Two modes, keyed on the ``schedule_id`` the scheduler hands the executor:

* ``MR_DASH_ALL`` (a scheduled cron fire) -> regenerate **every** framework
  dashboard. The user sets one cadence and expects all of their macro
  dashboards to refresh on it.
* any single dashboard slug (an ad-hoc "Run now") -> regenerate just that
  dashboard, unchanged from the original per-dashboard behavior.

The all-dashboards run regenerates in dependency order so derived
dashboards read freshly-cached upstream state:

  debt_cycle, world_order -> seed five_forces (F1/F3)
  all five frameworks      -> seed summary

so five_forces runs after debt_cycle + world_order, and summary runs last.
Each dashboard commits in its own session before the next runs, so a later
dashboard's ``run_to_cache`` reads the just-written cache rows. One
dashboard failing does not abort the batch: the failure is logged and the
run continues so a single flaky dashboard cannot block the others. The job
only fails outright when *no* dashboard succeeded, re-raising the first
error so the base executor's transient-retry/backoff still applies.
"""

from __future__ import annotations

import logging
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
from openlia_server.scheduler.registry import MR_DASH_ALL, JobType, NotificationType
from openlia_server.services import mr_dash_run_service

DEPARTMENT = "macro_research"

log = logging.getLogger(__name__)

# Every framework dashboard, in dependency order: upstream dashboards first so
# the derived ones (five_forces, summary) read freshly-cached state. Kept in
# sync with report_dash_mr.implemented_dashboard_slugs() — the parity is
# asserted in test_mr_dash_executor.
DASHBOARD_REFRESH_ORDER: tuple[str, ...] = (
    "debt_cycle",
    "world_order",
    "four_seasons",
    "all_weather",
    "five_forces",
    "summary",
)


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
        assert schedule_id is not None
        bridge = _CancelBridge(cancel_token) if cancel_token is not None else None
        if schedule_id == MR_DASH_ALL:
            return await self._refresh_all(user_id=user_id, bridge=bridge)
        return await self._refresh_one(user_id=user_id, slug=schedule_id, bridge=bridge)

    async def _run_one(self, *, user_id: str, slug: str, bridge: _CancelBridge | None) -> None:
        """Regenerate a single dashboard in its own committed session."""
        with self._session_factory() as session:
            await self._run_service.run_to_cache(
                session,
                user_id=user_id,
                dashboard_slug=slug,
                cancel_token=bridge,
            )
            session.commit()

    async def _refresh_one(
        self, *, user_id: str, slug: str, bridge: _CancelBridge | None
    ) -> JobOutcome:
        await self._run_one(user_id=user_id, slug=slug, bridge=bridge)
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

    async def _refresh_all(self, *, user_id: str, bridge: _CancelBridge | None) -> JobOutcome:
        refreshed: list[str] = []
        failed: list[str] = []
        first_error: Exception | None = None

        for slug in DASHBOARD_REFRESH_ORDER:
            if bridge is not None and bridge.cancelled:
                break
            try:
                await self._run_one(user_id=user_id, slug=slug, bridge=bridge)
            except Exception as exc:
                # Broad by design: one dashboard's failure must not abort the
                # batch. Logged below; re-raised only if every dashboard fails.
                if bridge is not None and bridge.cancelled:
                    # Graceful shutdown surfaces as a non-completed run; stop
                    # the batch rather than logging it as a dashboard failure.
                    break
                log.exception("macro dashboard %s failed during scheduled refresh", slug)
                failed.append(slug)
                if first_error is None:
                    first_error = exc
                continue
            refreshed.append(slug)

        if not refreshed:
            # Re-raise the original error so the base executor's transient
            # retry/backoff still applies when every dashboard failed.
            if first_error is not None:
                raise first_error
            raise RuntimeError("macro dashboard refresh produced no dashboards")

        return JobOutcome(
            result_summary={"dashboards": refreshed, "failed": failed},
            notifications=[
                NotificationSpec(
                    type=NotificationType.ASSESSMENT_READY,
                    department=DEPARTMENT,
                    message=f"Your macro dashboards are updated ({len(refreshed)} refreshed).",
                )
            ],
        )
