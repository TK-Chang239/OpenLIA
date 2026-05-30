"""Concrete ``EuV2CalendarSyncer`` / ``EuV2Dispatcher`` bound to the EU v2
service layer + EODHD transports + run service.

These are the production implementations the scheduler wiring injects into
``EuV2SyncExecutor`` / ``EuV2DispatchExecutor``. The Protocols themselves
live in ``scheduler/payloads.py``; the executors stay thin and call straight
through to these.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from openlia.llm.runtime.report_eu import EventBroker
from sqlalchemy.orm import Session as DBSession

from openlia_server.services.eu_v2_calendar_sync import sync_all_watchlists
from openlia_server.services.eu_v2_dispatch import (
    mark_failed,
    mark_reported,
    select_due_rows,
)
from openlia_server.services.eu_v2_run_service import build_run_request, start_run_async
from openlia_server.services.eu_v2_wiring import build_eu_v2_transports

log = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3


class EuV2CalendarSyncerImpl:
    """Weekly sync across all watchlists using the env-wired EODHD calendar."""

    def __init__(
        self,
        *,
        transports_factory: Callable[[], object | None] = build_eu_v2_transports,
    ) -> None:
        self._transports_factory = transports_factory

    def sync_all(self, *, session: DBSession) -> int:
        transports = self._transports_factory()
        if transports is None:
            log.info("EU v2 sync skipped: EODHD transports not configured.")
            return 0
        return sync_all_watchlists(
            session,
            earnings_calendar=transports.earnings_calendar,
            now=datetime.now(UTC),
        )


class EuV2DispatcherImpl:
    """Fire each due scheduled earnings run via the EU v2 run service.

    Scheduled runs have no live SSE client, so each fire gets a throwaway
    ``EventBroker`` + empty cancel registry — events go nowhere but the run
    still persists through the background task's fresh session.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], DBSession],
    ) -> None:
        self._session_factory = session_factory

    def dispatch_due(self, *, session: DBSession, now: datetime) -> int:
        fired = 0
        for row in select_due_rows(session, now=now):
            try:
                request = build_run_request(
                    session,
                    user_id=row.user_id,
                    ticker=row.ticker,
                    trigger_kind="scheduled",
                    fiscal_period=None,
                    report_date=row.fiscal_date,
                    release_timing=row.release_timing,
                    eps_estimate=row.eps_estimate,
                    revenue_estimate=row.revenue_estimate,
                )
                report_id = start_run_async(
                    session,
                    user_id=row.user_id,
                    request=request,
                    broker=EventBroker(),
                    cancel_registry={},
                    session_factory=self._session_factory,
                    trigger_kind="scheduled",
                )
                mark_reported(session, row_id=row.id, report_id=report_id)
                fired += 1
            except Exception:
                log.exception("EU v2 dispatch failed for schedule row %s", row.id)
                mark_failed(session, row_id=row.id, max_attempts=_MAX_ATTEMPTS)
        return fired


__all__ = ["EuV2CalendarSyncerImpl", "EuV2DispatcherImpl"]
