"""EU v2 scheduler executors.

Two thin executors over the EU v2 service layer:

- ``EuV2SyncExecutor`` runs the weekly watchlist calendar sync across all
  users (``EuV2CalendarSyncer.sync_all``).
- ``EuV2DispatchExecutor`` fires every due scheduled earnings run
  (``EuV2Dispatcher.dispatch_due``).

Both are global jobs (``user_id``/``schedule_id`` are ``None``); all logic
lives in the injected syncer/dispatcher, the executors only open a session
via ``session_factory`` and report a ``JobOutcome``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from openlia.llm.runtime.cancellation import CancellationToken

from openlia_server.scheduler.executors.base import (
    BaseExecutor,
    JobOutcome,
    SessionFactory,
)
from openlia_server.scheduler.payloads import EuV2CalendarSyncer, EuV2Dispatcher
from openlia_server.scheduler.registry import JobType


class EuV2SyncExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.EU_V2_SYNC

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        syncer: EuV2CalendarSyncer,
    ) -> None:
        super().__init__(session_factory=session_factory)
        self._syncer = syncer

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        with self._session_factory() as session:
            synced = self._syncer.sync_all(session=session)
        return JobOutcome(result_summary={"rows_synced": synced}, notifications=[])


class EuV2DispatchExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.EU_V2_DISPATCH

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        dispatcher: EuV2Dispatcher,
    ) -> None:
        super().__init__(session_factory=session_factory)
        self._dispatcher = dispatcher

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            fired = self._dispatcher.dispatch_due(session=session, now=now)
        return JobOutcome(result_summary={"runs_fired": fired}, notifications=[])
