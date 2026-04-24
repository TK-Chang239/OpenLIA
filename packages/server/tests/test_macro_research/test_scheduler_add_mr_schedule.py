from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.service import SchedulerService


def _mk_service(executors=None):
    svc = SchedulerService.__new__(SchedulerService)
    inner = MagicMock()
    inner.add_schedule = AsyncMock()
    inner.remove_schedule = AsyncMock()
    svc.scheduler = inner
    svc.executors = executors or {JobType.MR_ASSESSMENT: MagicMock()}
    svc.settings = MagicMock(misfire_grace_seconds=21600)
    svc._active_tokens = {}
    return svc, inner


@pytest.mark.asyncio
async def test_accepts_mr_dashboard_state_row() -> None:
    svc, inner = _mk_service()
    row = MrDashboardState(
        id="mrs-1",
        user_id="u-1",
        dashboard="world_order",
        view_config={},
        threshold_overrides={},
        assessment_schedule="0 0 * * 0",
    )
    await svc.add_schedule(row)
    inner.add_schedule.assert_awaited_once()
    _args, kwargs = inner.add_schedule.call_args
    assert kwargs.get("id", "").startswith("mr_assessment:u-1")


@pytest.mark.asyncio
async def test_rejects_mr_row_without_schedule() -> None:
    svc, _ = _mk_service()
    row = MrDashboardState(
        id="mrs-2",
        user_id="u-1",
        dashboard="world_order",
        view_config={},
        threshold_overrides={},
        assessment_schedule=None,
    )
    with pytest.raises(ValueError, match="assessment_schedule"):
        await svc.add_schedule(row)
