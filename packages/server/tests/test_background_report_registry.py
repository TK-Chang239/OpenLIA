"""BackgroundReportRegistry tracks per-process in-flight reports. It
supports: submit (wrap a generator coro), get, cancel one, cancel all
for a user, forget (called by the wrapper's finally clause), and
per-task event ring + subscriber queues."""

from __future__ import annotations

import asyncio

import pytest
from openlia_server.services.background_report_registry import (
    EVENT_RING_SIZE,
    BackgroundReportRegistry,
    BackgroundReportTask,
)


@pytest.mark.asyncio
async def test_submit_creates_task_and_get_returns_it() -> None:
    registry = BackgroundReportRegistry()

    async def runner():
        yield {"type": "noop"}

    task = registry.submit(user_id="u1", report_id="r1", runner_coro=runner())
    assert isinstance(task, BackgroundReportTask)
    assert registry.get("r1") is task
    # Let it finish to avoid leaking.
    await asyncio.wait_for(task.asyncio_task, timeout=1.0)
    registry.forget("r1")
    assert registry.get("r1") is None


@pytest.mark.asyncio
async def test_cancel_cancels_underlying_task() -> None:
    registry = BackgroundReportRegistry()

    async def long_runner():
        await asyncio.sleep(10)
        yield {"type": "noop"}

    task = registry.submit(user_id="u1", report_id="r1", runner_coro=long_runner())
    assert registry.cancel("r1") is True
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task.asyncio_task, timeout=1.0)


@pytest.mark.asyncio
async def test_cancel_user_cancels_only_that_users_reports() -> None:
    registry = BackgroundReportRegistry()

    async def long_runner():
        await asyncio.sleep(10)
        yield {"type": "noop"}

    t1 = registry.submit(user_id="u1", report_id="r1", runner_coro=long_runner())
    t2 = registry.submit(user_id="u1", report_id="r2", runner_coro=long_runner())
    t3 = registry.submit(user_id="u2", report_id="r3", runner_coro=long_runner())
    cancelled = registry.cancel_user("u1")
    assert sorted(cancelled) == ["r1", "r2"]
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t1.asyncio_task, timeout=1.0)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t2.asyncio_task, timeout=1.0)
    # u2's task untouched (still running) — cancel it for cleanup.
    registry.cancel("r3")
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t3.asyncio_task, timeout=1.0)


def test_default_event_ring_size_is_200() -> None:
    assert EVENT_RING_SIZE == 200


@pytest.mark.asyncio
async def test_list_active_returns_only_running_tasks_for_user() -> None:
    registry = BackgroundReportRegistry()

    async def long_runner():
        await asyncio.sleep(10)
        yield {"type": "noop"}

    registry.submit(user_id="u1", report_id="r1", runner_coro=long_runner())
    registry.submit(user_id="u1", report_id="r2", runner_coro=long_runner())
    registry.submit(user_id="u2", report_id="r3", runner_coro=long_runner())
    active = registry.list_active("u1")
    assert {t.report_id for t in active} == {"r1", "r2"}
    # cleanup
    registry.cancel_user("u1")
    registry.cancel_user("u2")


@pytest.mark.asyncio
async def test_event_ring_truncates_at_ring_size() -> None:
    """The per-task event_ring keeps only EVENT_RING_SIZE entries."""
    registry = BackgroundReportRegistry()

    async def chatty():
        for i in range(EVENT_RING_SIZE * 3):
            yield {"i": i}

    task = registry.submit(user_id="u1", report_id="r1", runner_coro=chatty())
    await asyncio.wait_for(task.asyncio_task, timeout=2.0)
    assert len(task.event_ring) == EVENT_RING_SIZE
    # Last item retained
    assert task.event_ring[-1]["i"] == EVENT_RING_SIZE * 3 - 1


@pytest.mark.asyncio
async def test_fanout_drops_oldest_on_full_subscriber_queue() -> None:
    """When a subscriber queue fills, the producer drops the oldest
    item and pushes the new one (drop-oldest policy)."""
    registry = BackgroundReportRegistry()

    async def chatty():
        for i in range(2000):
            yield {"i": i}

    task = registry.submit(user_id="u1", report_id="r1", runner_coro=chatty())
    # Attach a tiny queue BEFORE the chatty runner gets far.
    tiny_q: asyncio.Queue = asyncio.Queue(maxsize=4)
    task.subscriber_queues.add(tiny_q)
    await asyncio.wait_for(task.asyncio_task, timeout=2.0)
    # Tiny queue should be full or near-full; whatever's in it must be
    # tail items (oldest dropped).
    drained = []
    while not tiny_q.empty():
        drained.append(tiny_q.get_nowait())
    assert drained, "queue should retain at least one item"
    assert all(item["i"] >= 1500 for item in drained), (
        "drop-oldest policy should keep only the most recent items"
    )
