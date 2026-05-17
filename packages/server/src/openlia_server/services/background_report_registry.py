"""In-process registry of background report-generation tasks.

Each submitted task wraps a runner coroutine (SubagentReportRunner.run
or compatible) in an asyncio.Task. The registry tracks per-task event
rings and subscriber queues so SSE consumers can attach (or re-attach)
to a running generation.

Single-process: this in-memory state does not survive process restart.
The startup sweep (separate module) reconciles the DB by marking any
'generating' rows as failed at startup.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

EVENT_RING_SIZE = 200


@dataclass
class BackgroundReportTask:
    report_id: str
    user_id: str
    asyncio_task: asyncio.Task
    subscriber_queues: set[asyncio.Queue] = field(default_factory=set)
    event_ring: deque = field(default_factory=lambda: deque(maxlen=EVENT_RING_SIZE))
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cancelled: bool = False


class BackgroundReportRegistry:
    def __init__(self) -> None:
        self._by_report_id: dict[str, BackgroundReportTask] = {}
        self._by_user_id: dict[str, set[str]] = {}

    def submit(
        self,
        *,
        user_id: str,
        report_id: str,
        runner_coro: AsyncIterator[Any],
    ) -> BackgroundReportTask:
        """Wrap ``runner_coro`` in an asyncio task and track it. The
        caller is responsible for providing a wrapper that fans events
        out to ``task.subscriber_queues`` and ``task.event_ring`` — this
        registry does NOT do fan-out automatically (the wrapper module
        owns that)."""
        loop = asyncio.get_running_loop()
        placeholder = BackgroundReportTask(
            report_id=report_id,
            user_id=user_id,
            asyncio_task=None,  # filled below
        )

        async def _run():
            try:
                async for event in runner_coro:
                    placeholder.event_ring.append(event)
                    for queue in list(placeholder.subscriber_queues):
                        try:
                            queue.put_nowait(event)
                        except asyncio.QueueFull:
                            try:
                                queue.get_nowait()
                                queue.put_nowait(event)
                            except Exception:
                                pass
            finally:
                self.forget(report_id)

        placeholder.asyncio_task = loop.create_task(_run())
        self._by_report_id[report_id] = placeholder
        self._by_user_id.setdefault(user_id, set()).add(report_id)
        return placeholder

    def get(self, report_id: str) -> BackgroundReportTask | None:
        return self._by_report_id.get(report_id)

    def cancel(self, report_id: str) -> bool:
        task = self._by_report_id.get(report_id)
        if task is None:
            return False
        task.cancelled = True
        if not task.asyncio_task.done():
            task.asyncio_task.cancel()
        return True

    def cancel_user(self, user_id: str) -> list[str]:
        report_ids = list(self._by_user_id.get(user_id, set()))
        for rid in report_ids:
            self.cancel(rid)
        return report_ids

    def list_active(self, user_id: str) -> list[BackgroundReportTask]:
        return [
            self._by_report_id[rid]
            for rid in self._by_user_id.get(user_id, set())
            if rid in self._by_report_id
        ]

    def forget(self, report_id: str) -> None:
        task = self._by_report_id.pop(report_id, None)
        if task is None:
            return
        user_set = self._by_user_id.get(task.user_id)
        if user_set:
            user_set.discard(report_id)
            if not user_set:
                self._by_user_id.pop(task.user_id, None)
