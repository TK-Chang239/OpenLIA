"""Tests for the MrDashExecutor (MR dashboard redesign Task 9).

The executor runs the report_dash_mr engine inline via
``mr_dash_run_service.run_to_cache``. The scheduler hands it
``schedule_id`` = the dashboard slug, which the executor forwards as
``dashboard_slug``. These tests inject a fake run service that records
the call and returns the slug, then assert the JobOutcome shape (one
ASSESSMENT_READY notification, ``result_summary == {"dashboard": slug}``)
and that the slug threaded through correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from openlia_server.scheduler.executors.base import JobOutcome
from openlia_server.scheduler.executors.mr_dash import MrDashExecutor
from openlia_server.scheduler.registry import NotificationType


@dataclass
class FakeRunService:
    """Stub of mr_dash_run_service.run_to_cache: records the call and
    returns the dashboard slug it was handed."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run_to_cache(
        self,
        db,
        *,
        user_id: str,
        dashboard_slug: str,
        cancel_token: Any = None,
    ) -> str:
        self.calls.append(
            {
                "user_id": user_id,
                "dashboard_slug": dashboard_slug,
                "cancel_token": cancel_token,
            }
        )
        return dashboard_slug


@pytest.mark.asyncio
async def test_mr_dash_executor_runs_dashboard_and_notifies(db_session_factory) -> None:
    run_service = FakeRunService()
    ex = MrDashExecutor(session_factory=db_session_factory, run_service=run_service)

    outcome = await ex._do_work(
        user_id="u1",
        schedule_id="debt_cycle",
        run_id="r1",
        cancel_token=None,
    )

    assert isinstance(outcome, JobOutcome)
    assert outcome.result_summary == {"dashboard": "debt_cycle"}

    assert len(outcome.notifications) == 1
    notif = outcome.notifications[0]
    assert notif.type == NotificationType.ASSESSMENT_READY
    assert notif.department == "macro_research"
    assert "debt_cycle" in notif.message

    # The slug arrived as schedule_id and was forwarded as dashboard_slug.
    assert len(run_service.calls) == 1
    assert run_service.calls[0]["dashboard_slug"] == "debt_cycle"
    assert run_service.calls[0]["user_id"] == "u1"


def test_cancel_bridge_reflects_source_token() -> None:
    from openlia.llm.runtime.cancellation import CancellationToken
    from openlia_server.scheduler.executors.mr_dash import _CancelBridge

    source = CancellationToken()
    bridge = _CancelBridge(source)
    # ``cancelled`` is a property (the engine polls it without calling),
    # delegating to the scheduler token's ``is_cancelled`` property.
    assert bridge.cancelled is False
    source.cancel()
    assert bridge.cancelled is True


@pytest.mark.asyncio
async def test_mr_dash_executor_forwards_cancellation_to_engine(db_session_factory) -> None:
    from openlia.llm.runtime.cancellation import CancellationToken

    run_service = FakeRunService()
    ex = MrDashExecutor(session_factory=db_session_factory, run_service=run_service)

    token = CancellationToken()
    await ex._do_work(
        user_id="u1",
        schedule_id="debt_cycle",
        run_id="r1",
        cancel_token=token,
    )

    forwarded = run_service.calls[0]["cancel_token"]
    assert forwarded is not None
    assert forwarded.cancelled is False
    token.cancel()
    assert forwarded.cancelled is True
