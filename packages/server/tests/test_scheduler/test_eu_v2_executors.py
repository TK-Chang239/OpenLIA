from __future__ import annotations

import pytest
from openlia_server.scheduler.executors.eu_v2 import (
    EuV2DispatchExecutor,
    EuV2SyncExecutor,
)


@pytest.mark.asyncio
async def test_sync_executor_invokes_syncer(session_factory):
    calls = {}

    class Syncer:
        def sync_all(self, *, session):
            calls["ran"] = True
            return 2

    ex = EuV2SyncExecutor(session_factory=session_factory, syncer=Syncer())
    run_id = await ex.execute(user_id=None, schedule_id=None)
    assert calls["ran"] is True
    assert run_id is not None


@pytest.mark.asyncio
async def test_dispatch_executor_fires_due_rows(session_factory):
    fired = []

    class Dispatcher:
        def dispatch_due(self, *, session, now):
            fired.append(now)
            return 1

    ex = EuV2DispatchExecutor(session_factory=session_factory, dispatcher=Dispatcher())
    run_id = await ex.execute(user_id=None, schedule_id=None)
    assert len(fired) == 1
    assert run_id is not None
