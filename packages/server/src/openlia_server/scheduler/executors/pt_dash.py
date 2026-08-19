"""Panic Thermometer dashboard warm-cache executor.

Global fan-out job (no per-user schedule table): recomputes the dashboard
for every enabled user who has a PT config row and upserts the result
into ``pt_dashboard_cache``, so page loads are served instantly — even
the first load after a restart — and composite level-change notifications
fire without anyone having the page open.

The compute is blocking network I/O (EODHD fetches), so each user's
compute is dispatched to a worker thread. Notifications are quiet: this
job's value is the warm cache; level-change alerts are emitted inside
``compute_dashboard`` itself (edge-triggered on the composite level).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from sqlalchemy import select

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import PtUserConfig
from openlia_server.scheduler.executors.base import (
    BaseExecutor,
    JobOutcome,
    SessionFactory,
)
from openlia_server.scheduler.registry import JobType
from openlia_server.services import pt_dash_cache

log = logging.getLogger(__name__)


class PtDashExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.PT_DASH

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        runner_provider: Callable[[], Any],
    ) -> None:
        super().__init__(session_factory=session_factory)
        # Provider, not instance: the runner is constructed later in the app
        # factory than the scheduler wiring runs.
        self._runner_provider = runner_provider

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        runner = self._runner_provider()
        if runner is None:
            return JobOutcome(
                result_summary={"skipped": "pt runner not wired"},
                notifications=[],
            )

        with self._session_factory() as session:
            user_ids = [
                uid
                for (uid,) in session.execute(
                    select(PtUserConfig.user_id)
                    .join(User, User.id == PtUserConfig.user_id)
                    .where(User.is_disabled.is_(False))
                ).all()
            ]

        computed = 0
        failed = 0
        for uid in user_ids:
            if cancel_token is not None and cancel_token.is_cancelled:
                break
            try:
                payload = await asyncio.to_thread(runner.compute_dashboard, uid)
                data = pt_dash_cache.payload_to_dict(payload)
                with self._session_factory() as session:
                    pt_dash_cache.upsert_cache(session, uid, data)
                    session.commit()
                computed += 1
            except Exception as exc:
                failed += 1
                log.warning("pt_dash: compute failed for user %s: %s", uid, exc)

        return JobOutcome(
            result_summary={"users": len(user_ids), "computed": computed, "failed": failed},
            notifications=[],
        )
