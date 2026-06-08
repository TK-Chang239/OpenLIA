"""Tests for the MrDashExecutor (MR dashboard redesign).

The executor runs the report_dash_mr engine inline via
``mr_dash_run_service.run_to_cache``. It branches on the ``schedule_id`` the
scheduler hands it:

* a single dashboard slug (ad-hoc "Run now") regenerates just that dashboard;
* the ``MR_DASH_ALL`` sentinel (a scheduled cron fire) regenerates every
  framework dashboard in dependency order.

These tests inject a fake run service that records calls (and can be told to
fail specific slugs), then assert the JobOutcome shape and the slugs/order
that threaded through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from openlia.llm.runtime.report_dash_mr import implemented_dashboard_slugs
from openlia_server.scheduler.executors.base import JobOutcome
from openlia_server.scheduler.executors.mr_dash import (
    DASHBOARD_REFRESH_ORDER,
    MrDashExecutor,
)
from openlia_server.scheduler.registry import MR_DASH_ALL, NotificationType


@dataclass
class FakeRunService:
    """Stub of mr_dash_run_service.run_to_cache: records the call and returns
    the dashboard slug it was handed. Slugs listed in ``fail_slugs`` raise."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    fail_slugs: frozenset[str] = frozenset()

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
        if dashboard_slug in self.fail_slugs:
            raise RuntimeError(f"boom: {dashboard_slug}")
        return dashboard_slug


@pytest.mark.asyncio
async def test_mr_dash_executor_runs_single_dashboard_and_notifies(db_session_factory) -> None:
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

    # An ad-hoc run regenerates only the slug it was handed.
    assert len(run_service.calls) == 1
    assert run_service.calls[0]["dashboard_slug"] == "debt_cycle"
    assert run_service.calls[0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_mr_dash_executor_all_regenerates_every_dashboard_in_order(
    db_session_factory,
) -> None:
    run_service = FakeRunService()
    ex = MrDashExecutor(session_factory=db_session_factory, run_service=run_service)

    outcome = await ex._do_work(
        user_id="u1",
        schedule_id=MR_DASH_ALL,
        run_id="r1",
        cancel_token=None,
    )

    ran = [c["dashboard_slug"] for c in run_service.calls]
    assert ran == list(DASHBOARD_REFRESH_ORDER)
    assert outcome.result_summary == {
        "dashboards": list(DASHBOARD_REFRESH_ORDER),
        "failed": [],
    }
    assert len(outcome.notifications) == 1
    assert "updated" in outcome.notifications[0].message


@pytest.mark.asyncio
async def test_mr_dash_executor_all_continues_past_a_single_failure(
    db_session_factory,
) -> None:
    run_service = FakeRunService(fail_slugs=frozenset({"four_seasons"}))
    ex = MrDashExecutor(session_factory=db_session_factory, run_service=run_service)

    outcome = await ex._do_work(
        user_id="u1",
        schedule_id=MR_DASH_ALL,
        run_id="r1",
        cancel_token=None,
    )

    # Every dashboard was still attempted, and the others succeeded.
    assert [c["dashboard_slug"] for c in run_service.calls] == list(DASHBOARD_REFRESH_ORDER)
    assert outcome.result_summary["failed"] == ["four_seasons"]
    assert "four_seasons" not in outcome.result_summary["dashboards"]
    assert len(outcome.result_summary["dashboards"]) == len(DASHBOARD_REFRESH_ORDER) - 1


@pytest.mark.asyncio
async def test_mr_dash_executor_all_raises_when_every_dashboard_fails(
    db_session_factory,
) -> None:
    run_service = FakeRunService(fail_slugs=frozenset(DASHBOARD_REFRESH_ORDER))
    ex = MrDashExecutor(session_factory=db_session_factory, run_service=run_service)

    # All failed -> re-raise the first error so the base executor can retry.
    with pytest.raises(RuntimeError, match="boom: debt_cycle"):
        await ex._do_work(
            user_id="u1",
            schedule_id=MR_DASH_ALL,
            run_id="r1",
            cancel_token=None,
        )


def test_dashboard_refresh_order_matches_implemented_slugs() -> None:
    # The scheduled all-run must cover exactly the dashboards the engine can
    # produce; a new dashboard added to the engine forces updating the order.
    assert set(DASHBOARD_REFRESH_ORDER) == set(implemented_dashboard_slugs())
    assert len(DASHBOARD_REFRESH_ORDER) == len(set(DASHBOARD_REFRESH_ORDER))


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
