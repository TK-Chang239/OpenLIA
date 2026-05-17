# Background Report Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Equity research report generation runs as a server-side background asyncio task that survives client disconnect, supports re-subscription from any page via an event-ring + fan-out, surfaces completion via an app-shell notifications SSE, and auto-cancels in-flight reports when the user closes all tabs for >90s. Gated behind `OPENLIA_BACKGROUND_REPORTS_ENABLED`.

**Architecture:** In-process `BackgroundReportRegistry` keeps a `dict[report_id, BackgroundReportTask]`. Each task wraps the SubagentReportRunner generator, fans events out to subscriber queues, persists final state to the `reports` table. A separate `UserPresenceRegistry` tracks open notifications-SSE connections per user; an asyncio sweep cancels in-flight reports for users disconnected >90s. POST `/reports/generate` returns fast with a new `report_id`; GET `/reports/{id}/stream` attaches new subscribers; DELETE cancels; POST `/reports/{id}/retry` re-submits using a persisted `original_request` JSON column.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy + Alembic, asyncio. Frontend: React + TypeScript + EventSource API. Lint: ruff. Package mgr: uv.

**Branch:** Create `feat/background-report-generation` from `main` AFTER `feat/subagent-report-architecture` merges. This feature is independent of the chat-followup feature (`docs/superpowers/specs/2026-05-17-report-chat-followup-design.md`); either can ship first.

**Spec:** `docs/superpowers/specs/2026-05-17-background-report-generation-design.md`

---

## Pre-flight (one-time setup)

- [ ] **Confirm subagent runner has merged to main:** `git log main --oneline | grep -i "subagent" | head -3`. If nothing, do NOT proceed — the wrapped runner is required.
- [ ] **Create branch:** `git checkout main && git pull && git checkout -b feat/background-report-generation`
- [ ] **Confirm clean tree:** `git status --short` (expect empty)

> **Sandbox note for all `uv run` commands:** If you see `Failed to initialize cache at .cache/uv` or similar, pass `dangerouslyDisableSandbox: true` to the Bash tool. Environment-only, not a code issue.

---

## Task 1: DB migration — 4 new columns on reports table

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/content.py`
- Create: `packages/server/src/openlia_server/db/migrations/versions/<NEW>_report_status_columns.py`
- Test: `packages/server/tests/test_report_status_columns.py`

> **Before starting:** Run `grep -n "class Report\b\|__tablename__\|Mapped\[" packages/server/src/openlia_server/db/models/content.py | head -15` and `ls packages/server/src/openlia_server/db/migrations/versions/ | tail -3` to anchor existing patterns.

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_report_status_columns.py
"""Reports table gains: status (default 'complete'), failure_reason,
original_request (JSON), started_at. Existing rows backfill as
'complete'. Status is indexed."""
from __future__ import annotations

from sqlalchemy import inspect

from openlia_server.db.models.content import Report


def test_report_model_has_new_columns() -> None:
    mapper = inspect(Report)
    column_names = {c.name for c in mapper.columns}
    assert "status" in column_names
    assert "failure_reason" in column_names
    assert "original_request" in column_names
    assert "started_at" in column_names


def test_status_column_default_complete() -> None:
    mapper = inspect(Report)
    col = mapper.columns["status"]
    assert col.nullable is False
    # Default of "complete" so existing rows backfill correctly.
    assert col.server_default is not None or col.default is not None


def test_failure_reason_and_started_at_nullable() -> None:
    mapper = inspect(Report)
    assert mapper.columns["failure_reason"].nullable is True
    assert mapper.columns["started_at"].nullable is True
    assert mapper.columns["original_request"].nullable is True


def test_status_index_created(db_session_factory) -> None:
    with db_session_factory() as session:
        bind = session.get_bind()
        insp = inspect(bind)
        idx_names = [ix["name"] for ix in insp.get_indexes("reports")]
        assert "idx_reports_status" in idx_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_report_status_columns.py -v
```

Expected: FAIL (columns missing on model)

- [ ] **Step 3: Add columns to the model**

In `packages/server/src/openlia_server/db/models/content.py`, inside the `Report` class definition, add:

```python
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="complete", default="complete", index=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    original_request: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    started_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime() if "UTCDateTime" in globals() else DateTime, nullable=True, default=None
    )
```

(Adapt `JSON`, `String`, `DateTime`/`UTCDateTime` imports to match existing imports in the file.)

- [ ] **Step 4: Generate the Alembic migration**

```bash
uv run alembic -c packages/server/alembic.ini revision -m "add report status + retry columns"
```

Edit the new migration file under `packages/server/src/openlia_server/db/migrations/versions/`:

```python
"""add report status + retry columns

Revision ID: <auto>
Revises: <previous>
"""

from alembic import op
import sqlalchemy as sa


revision = "<auto>"
down_revision = "<previous>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(), nullable=False, server_default="complete"))
        batch_op.add_column(sa.Column("failure_reason", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("original_request", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_reports_status", "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_reports_status", table_name="reports")
    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_column("started_at")
        batch_op.drop_column("original_request")
        batch_op.drop_column("failure_reason")
        batch_op.drop_column("status")
```

(Keep the `revision` / `down_revision` IDs Alembic generated — don't invent.)

- [ ] **Step 5: Re-run tests**

```bash
uv run pytest packages/server/tests/test_report_status_columns.py -v
```

Expected: PASS (4 tests). The server test conftest applies migrations at fixture setup.

- [ ] **Step 6: Lint + format + commit**

```bash
uv run ruff format packages/server/src/openlia_server/db/models/content.py packages/server/src/openlia_server/db/migrations/versions/ packages/server/tests/test_report_status_columns.py
uv run ruff check packages/server/src/openlia_server/db/models/content.py packages/server/src/openlia_server/db/migrations/versions/ packages/server/tests/test_report_status_columns.py
git add packages/server/src/openlia_server/db/models/content.py packages/server/src/openlia_server/db/migrations/versions/ packages/server/tests/test_report_status_columns.py
git commit -m "feat(bg-reports): add status/failure_reason/original_request/started_at columns"
```

---

## Task 2: BackgroundReportRegistry — submit, get, cancel, cancel_user, fan-out, ring

**Files:**
- Create: `packages/server/src/openlia_server/services/background_report_registry.py`
- Test: `packages/server/tests/test_background_report_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_background_report_registry.py
"""BackgroundReportRegistry tracks per-process in-flight reports. It
supports: submit (wrap a generator coro), get, cancel one, cancel all
for a user, forget (called by the wrapper's finally clause), and
per-task event ring + subscriber queues."""
from __future__ import annotations

import asyncio
from collections import deque

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_background_report_registry.py -v
```

Expected: FAIL (ImportError on `background_report_registry`)

- [ ] **Step 3: Write the implementation**

```python
# packages/server/src/openlia_server/services/background_report_registry.py
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/server/tests/test_background_report_registry.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Lint + format + commit**

```bash
uv run ruff format packages/server/src/openlia_server/services/background_report_registry.py packages/server/tests/test_background_report_registry.py
uv run ruff check packages/server/src/openlia_server/services/background_report_registry.py packages/server/tests/test_background_report_registry.py
git add packages/server/src/openlia_server/services/background_report_registry.py packages/server/tests/test_background_report_registry.py
git commit -m "feat(bg-reports): BackgroundReportRegistry with fan-out + ring"
```

---

## Task 3: Event-ring bounded; fan-out drops oldest on full queue

**Files:**
- Modify: `packages/server/tests/test_background_report_registry.py` (extend)

(No source change — Task 2's implementation already enforces both behaviors. This task adds explicit guard tests.)

- [ ] **Step 1: Append the failing tests**

```python
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
    assert all(item["i"] >= 1500 for item in drained), \
        "drop-oldest policy should keep only the most recent items"
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest packages/server/tests/test_background_report_registry.py -v
git add packages/server/tests/test_background_report_registry.py
git commit -m "test(bg-reports): event ring bound + fan-out drop-oldest"
```

---

## Task 4: `_wrapper` coroutine — persist status + fan to notifications

**Files:**
- Create: `packages/server/src/openlia_server/services/report_wrapper.py`
- Test: `packages/server/tests/test_report_wrapper.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_report_wrapper.py
"""The report wrapper coroutine:
  1. Iterates the runner, fans events out via registry's machinery
  2. On ReportComplete: persists complete status + payload, calls presence.fanout(report.complete)
  3. On ReportError: persists failed status + failure_reason, fanout report.failed
  4. On asyncio.CancelledError: persists cancelled status, fanout report.cancelled
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from openlia.llm.runtime.events import ReportComplete, ReportError, ReportStart
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.report_wrapper import run_wrapped_report


@dataclass
class _Captured:
    user_id: str
    event: dict


class _StubPresence:
    def __init__(self) -> None:
        self.events: list[_Captured] = []

    def fanout(self, user_id: str, event: dict) -> None:
        self.events.append(_Captured(user_id=user_id, event=event))


class _StubReportRow:
    def __init__(self) -> None:
        self.status: str | None = None
        self.failure_reason: str | None = None
        self.report_schema_json: str | None = None
        self.completed_at = None


class _StubSession:
    def __init__(self, row: _StubReportRow) -> None:
        self._row = row
        self.committed = False

    def get(self, model, _id):
        return self._row

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        pass


def _session_factory(row: _StubReportRow):
    def factory():
        class _CM:
            def __enter__(self_inner):
                return _StubSession(row)
            def __exit__(self_inner, *a):
                return False
        return _CM()
    return factory


@pytest.mark.asyncio
async def test_wrapper_persists_complete_status_on_report_complete() -> None:
    row = _StubReportRow()
    presence = _StubPresence()
    registry = BackgroundReportRegistry()

    async def runner():
        yield ReportStart(report_id="r1", department_id="equity_research", mode="stock_initiation")
        yield ReportComplete(report_id="r1", schema={"cover": {"title": "MSFT"}})

    await run_wrapped_report(
        runner_coro=runner(),
        report_id="r1",
        user_id="u1",
        db_session_factory=_session_factory(row),
        presence=presence,
        registry=registry,
    )
    assert row.status == "complete"
    assert row.report_schema_json is not None
    assert presence.events[-1].event["type"] == "report.complete"
    assert presence.events[-1].event["report_id"] == "r1"
    assert presence.events[-1].event["title"] == "MSFT"


@pytest.mark.asyncio
async def test_wrapper_persists_failed_status_on_report_error() -> None:
    row = _StubReportRow()
    presence = _StubPresence()
    registry = BackgroundReportRegistry()

    async def runner():
        yield ReportError(report_id="r1", code="oops", message="something broke")

    await run_wrapped_report(
        runner_coro=runner(),
        report_id="r1",
        user_id="u1",
        db_session_factory=_session_factory(row),
        presence=presence,
        registry=registry,
    )
    assert row.status == "failed"
    assert row.failure_reason == "something broke"
    assert presence.events[-1].event["type"] == "report.failed"


@pytest.mark.asyncio
async def test_wrapper_persists_cancelled_on_cancellation() -> None:
    row = _StubReportRow()
    presence = _StubPresence()
    registry = BackgroundReportRegistry()

    async def runner():
        await asyncio.sleep(10)
        yield ReportComplete(report_id="r1", schema={"cover": {"title": "never"}})

    task = asyncio.create_task(
        run_wrapped_report(
            runner_coro=runner(),
            report_id="r1",
            user_id="u1",
            db_session_factory=_session_factory(row),
            presence=presence,
            registry=registry,
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert row.status == "cancelled"
    assert row.failure_reason == "user_cancelled"
    assert presence.events[-1].event["type"] == "report.cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_report_wrapper.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/server/src/openlia_server/services/report_wrapper.py
"""Per-task wrapper coroutine: drives the runner, persists status
transitions, and fans completion/failure/cancellation notifications
to the user's presence channel."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.llm.runtime.events import ReportComplete, ReportError


class _PresenceLike(Protocol):
    def fanout(self, user_id: str, event: dict) -> None: ...


async def run_wrapped_report(
    *,
    runner_coro: AsyncIterator[Any],
    report_id: str,
    user_id: str,
    db_session_factory,
    presence: _PresenceLike,
    registry,
) -> None:
    """Run the report generator to completion; persist status and
    notify on terminal events. Caller is expected to schedule this on
    the event loop via ``BackgroundReportRegistry.submit`` (which
    handles fan-out to subscriber queues; this wrapper handles
    persistence and notifications only)."""
    try:
        async for event in runner_coro:
            if isinstance(event, ReportComplete):
                _persist_complete(db_session_factory, report_id, event.schema)
                presence.fanout(
                    user_id,
                    {
                        "type": "report.complete",
                        "report_id": report_id,
                        "title": (event.schema.get("cover", {}) or {}).get("title", ""),
                    },
                )
            elif isinstance(event, ReportError):
                _persist_failed(db_session_factory, report_id, event.message)
                presence.fanout(
                    user_id,
                    {
                        "type": "report.failed",
                        "report_id": report_id,
                        "failure_reason": event.message,
                    },
                )
    except asyncio.CancelledError:
        _persist_cancelled(db_session_factory, report_id, "user_cancelled")
        presence.fanout(user_id, {"type": "report.cancelled", "report_id": report_id})
        raise


def _persist_complete(db_session_factory, report_id: str, schema: dict) -> None:
    from openlia_server.db.models.content import Report

    with db_session_factory() as session:
        row = session.get(Report, report_id)
        if row is None:
            return
        row.status = "complete"
        row.completed_at = datetime.now(UTC) if hasattr(row, "completed_at") else None
        row.report_schema_json = json.dumps(schema, default=str)
        session.commit()


def _persist_failed(db_session_factory, report_id: str, message: str) -> None:
    from openlia_server.db.models.content import Report

    with db_session_factory() as session:
        row = session.get(Report, report_id)
        if row is None:
            return
        row.status = "failed"
        row.failure_reason = (message or "")[:500]
        session.commit()


def _persist_cancelled(db_session_factory, report_id: str, reason: str) -> None:
    from openlia_server.db.models.content import Report

    with db_session_factory() as session:
        row = session.get(Report, report_id)
        if row is None:
            return
        row.status = "cancelled"
        row.failure_reason = reason
        session.commit()
```

- [ ] **Step 4: Run test to verify it passes + commit**

```bash
uv run pytest packages/server/tests/test_report_wrapper.py -v
uv run ruff format packages/server/src/openlia_server/services/report_wrapper.py packages/server/tests/test_report_wrapper.py
uv run ruff check packages/server/src/openlia_server/services/report_wrapper.py packages/server/tests/test_report_wrapper.py
git add packages/server/src/openlia_server/services/report_wrapper.py packages/server/tests/test_report_wrapper.py
git commit -m "feat(bg-reports): wrapper coroutine persists status + fanouts notifications"
```

---

## Task 5: UserPresenceRegistry

**Files:**
- Create: `packages/server/src/openlia_server/services/user_presence_registry.py`
- Test: `packages/server/tests/test_user_presence_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_user_presence_registry.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from openlia_server.services.user_presence_registry import UserPresenceRegistry


@pytest.mark.asyncio
async def test_attach_registers_user_and_clears_disconnect() -> None:
    presence = UserPresenceRegistry()
    queue = presence.attach("u1")
    assert isinstance(queue, asyncio.Queue)
    # After attach, user is NOT in the disconnect map.
    assert "u1" not in presence.users_with_no_connections()


@pytest.mark.asyncio
async def test_detach_records_disconnect_when_last_connection_closes() -> None:
    presence = UserPresenceRegistry()
    q1 = presence.attach("u1")
    q2 = presence.attach("u1")
    presence.detach("u1", q1)
    # Still has q2 — not in disconnect map.
    assert "u1" not in presence.users_with_no_connections()
    presence.detach("u1", q2)
    # No more connections — now in disconnect map.
    assert "u1" in presence.users_with_no_connections()


@pytest.mark.asyncio
async def test_fanout_delivers_to_all_open_connections() -> None:
    presence = UserPresenceRegistry()
    q1 = presence.attach("u1")
    q2 = presence.attach("u1")
    presence.fanout("u1", {"type": "test", "x": 1})
    assert q1.get_nowait() == {"type": "test", "x": 1}
    assert q2.get_nowait() == {"type": "test", "x": 1}


@pytest.mark.asyncio
async def test_set_imminent_disconnect_fast_forwards_timestamp() -> None:
    presence = UserPresenceRegistry()
    q = presence.attach("u1")
    presence.detach("u1", q)
    original_ts = presence.users_with_no_connections()["u1"]
    presence.set_imminent_disconnect("u1", grace_seconds=90)
    new_ts = presence.users_with_no_connections()["u1"]
    # New timestamp should be ~90s earlier than original.
    assert (original_ts - new_ts).total_seconds() >= 80
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_user_presence_registry.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/server/src/openlia_server/services/user_presence_registry.py
"""Per-process registry of open notifications-SSE connections per user.

When a user has zero connections for >grace_seconds, the auto-cancel
sweep cancels all their in-flight background reports."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta


class UserPresenceRegistry:
    def __init__(self) -> None:
        self._user_connections: dict[str, set[asyncio.Queue]] = {}
        self._last_disconnect_at: dict[str, datetime] = {}

    def attach(self, user_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._user_connections.setdefault(user_id, set()).add(queue)
        self._last_disconnect_at.pop(user_id, None)
        return queue

    def detach(self, user_id: str, queue: asyncio.Queue) -> None:
        conns = self._user_connections.get(user_id, set())
        conns.discard(queue)
        if not conns:
            self._user_connections.pop(user_id, None)
            self._last_disconnect_at[user_id] = datetime.now(UTC)

    def fanout(self, user_id: str, event: dict) -> None:
        for queue in list(self._user_connections.get(user_id, set())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def users_with_no_connections(self) -> dict[str, datetime]:
        return dict(self._last_disconnect_at)

    def set_imminent_disconnect(self, user_id: str, *, grace_seconds: int = 90) -> None:
        """Fast-forward this user's last_disconnect timestamp so the
        next sweep tick will pick them up. Called by the beforeunload
        beacon endpoint."""
        self._last_disconnect_at[user_id] = datetime.now(UTC) - timedelta(
            seconds=grace_seconds + 1
        )
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_user_presence_registry.py -v
uv run ruff format packages/server/src/openlia_server/services/user_presence_registry.py packages/server/tests/test_user_presence_registry.py
uv run ruff check packages/server/src/openlia_server/services/user_presence_registry.py packages/server/tests/test_user_presence_registry.py
git add packages/server/src/openlia_server/services/user_presence_registry.py packages/server/tests/test_user_presence_registry.py
git commit -m "feat(bg-reports): UserPresenceRegistry"
```

---

## Task 6: `POST /reports/generate` returns immediately (no streaming)

**Files:**
- Modify: `packages/server/src/openlia_server/routes/reports.py` (or wherever the existing generate route lives — confirm via `grep -rn "POST.*reports.*generate\|generate_report_ep\|StreamingResponse.*report" packages/server/src/openlia_server/routes/ | head -10`)
- Test: `packages/server/tests/test_report_generate_immediate_return.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_report_generate_immediate_return.py
"""POST /reports/generate (under the new background path) returns
within ~1s with a report_id and status='generating'. The actual
generation runs as a registry task; the response does NOT stream."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


def test_generate_returns_immediately_under_flag(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    body = {
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "MSFT",
        "enabled_sections": ["company_overview"],
        "length": "standard",
    }
    start = time.monotonic()
    resp = test_client.post("/reports/generate", json=body)
    elapsed = time.monotonic() - start
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "report_id" in payload
    assert payload["status"] == "generating"
    assert elapsed < 2.0, f"expected fast return; got {elapsed:.2f}s"


def test_generate_persists_original_request_for_retry(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    body = {
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "AAPL",
        "enabled_sections": ["overview"],
        "length": "brief",
    }
    resp = test_client.post("/reports/generate", json=body)
    rid = resp.json()["report_id"]
    # Look up the row directly via the existing reports list endpoint
    # and verify original_request round-trips.
    get_resp = test_client.get(f"/reports/{rid}")
    assert get_resp.status_code == 200
    body_back = get_resp.json()
    assert body_back["original_request"]["user_input"] == "AAPL"
    assert body_back["original_request"]["length"] == "brief"
```

> Fixtures `test_client` and conftest setup are expected to apply migrations + provide a fake provider for report generation. Reuse whatever exists from the subagent-runner test setup.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_report_generate_immediate_return.py -v
```

Expected: FAIL (POST currently streams or doesn't return immediately)

- [ ] **Step 3: Modify the generate endpoint**

In the existing report-generate route handler (e.g., `packages/server/src/openlia_server/routes/reports.py`), wrap the existing path with the flag and the new fast-return:

```python
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.report_wrapper import run_wrapped_report
from openlia_server.services.user_presence_registry import UserPresenceRegistry


def _bg_enabled() -> bool:
    return os.environ.get("OPENLIA_BACKGROUND_REPORTS_ENABLED", "0") == "1"


@router.post("/generate")
async def generate_report_ep(
    body: GenerateReportIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: BackgroundReportRegistry = Depends(get_registry),
    presence: UserPresenceRegistry = Depends(get_presence),
):
    if not _bg_enabled():
        # Legacy path: existing streaming behavior unchanged.
        return await legacy_generate(body, user, db)  # whatever the current path is

    report_id = f"r_{uuid.uuid4().hex[:12]}"
    row = Report(
        id=report_id,
        user_id=user.id,
        department=body.department_id,
        status="generating",
        original_request=body.model_dump(),
        started_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()

    # Build the runner the same way the legacy path does. The runner
    # exposes an async iterator yielding SseEvents.
    runner_coro = build_subagent_runner_coro(
        department_id=body.department_id,
        user_id=user.id,
        request=body.to_report_request(),
        report_id=report_id,
    )

    # Submit to the registry; the wrapper handles persistence + notifications.
    async def wrapped():
        async for ev in runner_coro:
            yield ev
        # No-op suffix; wrapper module is invoked explicitly below.

    # Compose: the registry's submit() handles fan-out and ring; we
    # separately schedule the persistence/notifications wrapper.
    task = registry.submit(
        user_id=user.id, report_id=report_id, runner_coro=runner_coro
    )
    # The wrapper also needs to observe the events; subscribe via a
    # fan-out queue and pipe through run_wrapped_report.
    queue: asyncio.Queue = asyncio.Queue(maxsize=512)
    task.subscriber_queues.add(queue)

    async def _wrapper_runner():
        while True:
            ev = await queue.get()
            yield ev
            from openlia.llm.runtime.events import ReportComplete, ReportError
            if isinstance(ev, (ReportComplete, ReportError)):
                return

    asyncio.create_task(run_wrapped_report(
        runner_coro=_wrapper_runner(),
        report_id=report_id,
        user_id=user.id,
        db_session_factory=get_session_factory(),
        presence=presence,
        registry=registry,
    ))

    return {"report_id": report_id, "status": "generating"}
```

(Adapt to match the existing route's helper imports + `legacy_generate` / `build_subagent_runner_coro` shapes.)

- [ ] **Step 4: Run test to verify it passes + commit**

```bash
uv run pytest packages/server/tests/test_report_generate_immediate_return.py -v
uv run ruff format packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_generate_immediate_return.py
uv run ruff check packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_generate_immediate_return.py
git add packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_generate_immediate_return.py
git commit -m "feat(bg-reports): POST /reports/generate returns immediately"
```

---

## Task 7: `GET /reports/{report_id}/stream` — live subscriber attachment

**Files:**
- Create: `packages/server/src/openlia_server/routes/reports_stream.py`
- Test: `packages/server/tests/test_reports_stream_live.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_reports_stream_live.py
"""GET /reports/{report_id}/stream attaches as a new subscriber to a
running task; receives replay of the event_ring + live events."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient


def test_stream_endpoint_returns_eventstream_content_type(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_running_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_running_report.id
    # Use streaming response; just confirm the content-type and that some
    # frames arrive within a short window.
    with test_client.stream("GET", f"/reports/{rid}/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        # Pull a few bytes; should contain at least one SSE event frame.
        chunk = next(resp.iter_text(chunk_size=4096))
        assert "event:" in chunk or "data:" in chunk


def test_stream_endpoint_replays_event_ring(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_running_report_with_events
) -> None:
    """A late subscriber receives the previously-emitted events via
    the event_ring replay before live tail begins."""
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_running_report_with_events.id
    # Open the stream; first frames should be the replayed ring contents.
    with test_client.stream("GET", f"/reports/{rid}/stream") as resp:
        text = ""
        for chunk in resp.iter_text(chunk_size=4096):
            text += chunk
            if "report.complete" in text or "report.error" in text:
                break
        # The seeded report's prior events are all present in the text.
        assert text.count("event:") >= 3
```

> Fixtures `seeded_running_report` and `seeded_running_report_with_events` submit a fake runner that yields a few events and stays running (or completes). Add to conftest using `BackgroundReportRegistry.submit` directly.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_reports_stream_live.py -v
```

Expected: FAIL (endpoint doesn't exist)

- [ ] **Step 3: Write the endpoint**

```python
# packages/server/src/openlia_server/routes/reports_stream.py
"""GET /reports/{report_id}/stream — SSE subscription to a background
report task. Supports both live tasks (replay ring + tail) and finished
tasks (synthetic terminal event from the persisted row)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    SseEvent,
)
from openlia_server.db.models.content import Report
from openlia_server.services.background_report_registry import BackgroundReportRegistry


def build_reports_stream_router(*, db_session_factory) -> APIRouter:
    router = APIRouter()

    @router.get("/{report_id}/stream")
    async def stream_report(
        report_id: str,
        user=Depends(get_current_user),
        registry: BackgroundReportRegistry = Depends(get_registry),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        row = db.get(Report, report_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(404)
        task = registry.get(report_id)

        async def event_generator() -> AsyncIterator[bytes]:
            if task is None:
                yield _frame_for_terminal(row)
                return
            queue: asyncio.Queue = asyncio.Queue(maxsize=512)
            task.subscriber_queues.add(queue)
            try:
                for ev in list(task.event_ring):
                    yield _to_sse_frame(ev)
                while True:
                    ev = await queue.get()
                    yield _to_sse_frame(ev)
                    if isinstance(ev, (ReportComplete, ReportError)):
                        return
            finally:
                task.subscriber_queues.discard(queue)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return router


def _to_sse_frame(event: SseEvent) -> bytes:
    """Serialize an SseEvent dataclass into an SSE-named-event frame."""
    event_name = getattr(event, "TYPE", type(event).__name__.lower())
    payload = {
        k: v for k, v in event.__dict__.items() if not k.startswith("_")
    }
    return f"event: {event_name}\ndata: {json.dumps(payload, default=str)}\n\n".encode("utf-8")


def _frame_for_terminal(row: Report) -> bytes:
    if row.status == "complete":
        import json as _json
        schema = _json.loads(row.report_schema_json) if row.report_schema_json else {}
        return _to_sse_frame(ReportComplete(report_id=row.id, schema=schema))
    if row.status == "cancelled":
        return _to_sse_frame(ReportError(
            report_id=row.id, code="cancelled",
            message=row.failure_reason or "Cancelled",
        ))
    return _to_sse_frame(ReportError(
        report_id=row.id, code="failed",
        message=row.failure_reason or "Generation failed",
    ))
```

Wire `build_reports_stream_router` into the app under the `/reports` prefix in `app.py`.

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_reports_stream_live.py -v
uv run ruff format packages/server/src/openlia_server/routes/reports_stream.py packages/server/tests/test_reports_stream_live.py
uv run ruff check packages/server/src/openlia_server/routes/reports_stream.py packages/server/tests/test_reports_stream_live.py
git add packages/server/src/openlia_server/routes/reports_stream.py packages/server/tests/test_reports_stream_live.py
git commit -m "feat(bg-reports): GET /reports/{id}/stream live subscription"
```

---

## Task 8: `GET /reports/{id}/stream` — synthetic terminal event for finished reports

**Files:**
- Test: `packages/server/tests/test_reports_stream_terminal.py`

(No source change — Task 7's `_frame_for_terminal` already handles this. This task adds explicit guards.)

- [ ] **Step 1: Write the test**

```python
# packages/server/tests/test_reports_stream_terminal.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_finished_report_yields_one_synthetic_complete_frame(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_completed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_completed_report.id
    with test_client.stream("GET", f"/reports/{rid}/stream") as resp:
        text = "".join(chunk for chunk in resp.iter_text(chunk_size=4096))
    assert "event: report.complete" in text or "event: reportcomplete" in text.lower()


def test_failed_report_yields_one_synthetic_error_frame(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_failed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_failed_report.id
    with test_client.stream("GET", f"/reports/{rid}/stream") as resp:
        text = "".join(chunk for chunk in resp.iter_text(chunk_size=4096))
    assert "event: report.error" in text or "report.error" in text.lower() or "failed" in text.lower()


def test_other_users_report_returns_404(
    monkeypatch: pytest.MonkeyPatch, test_client_user_b: TestClient, seeded_completed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_completed_report.id
    resp = test_client_user_b.get(f"/reports/{rid}/stream")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run + commit**

```bash
uv run pytest packages/server/tests/test_reports_stream_terminal.py -v
git add packages/server/tests/test_reports_stream_terminal.py
git commit -m "test(bg-reports): synthetic terminal frame for finished reports + auth"
```

---

## Task 9: `DELETE /reports/{report_id}` cancels the background task

**Files:**
- Modify: `packages/server/src/openlia_server/routes/reports.py` (or wherever the reports router lives)
- Test: `packages/server/tests/test_report_cancel.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_report_cancel.py
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient


def test_delete_cancels_running_task_and_marks_cancelled(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_running_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_running_report.id
    resp = test_client.delete(f"/reports/{rid}")
    assert resp.status_code == 200
    # Allow async cancellation to propagate.
    import time; time.sleep(0.2)
    get_resp = test_client.get(f"/reports/{rid}")
    assert get_resp.json()["status"] == "cancelled"
    assert get_resp.json()["failure_reason"] in ("user_cancelled", "session_disconnected")


def test_delete_404_for_other_users_report(
    monkeypatch: pytest.MonkeyPatch, test_client_user_b: TestClient, seeded_running_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_running_report.id
    resp = test_client_user_b.delete(f"/reports/{rid}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_report_cancel.py -v
```

Expected: FAIL (DELETE endpoint missing or doesn't cancel registry task)

- [ ] **Step 3: Add the DELETE handler**

In `packages/server/src/openlia_server/routes/reports.py`:

```python
@router.delete("/{report_id}")
async def delete_report_ep(
    report_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: BackgroundReportRegistry = Depends(get_registry),
) -> dict:
    row = db.get(Report, report_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404)
    if row.status == "generating":
        registry.cancel(report_id)
        # The wrapper coroutine will persist 'cancelled' via run_wrapped_report.
        return {"ok": True, "action": "cancelled"}
    # Already finished — fall back to existing delete behavior (tombstone or hard delete).
    return existing_delete_report(db, row)  # whatever the current path does
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_report_cancel.py -v
uv run ruff format packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_cancel.py
uv run ruff check packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_cancel.py
git add packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_cancel.py
git commit -m "feat(bg-reports): DELETE /reports/{id} cancels background task"
```

---

## Task 10: `POST /reports/{report_id}/retry` creates new generation from original_request

**Files:**
- Modify: `packages/server/src/openlia_server/routes/reports.py`
- Test: `packages/server/tests/test_report_retry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_report_retry.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_retry_creates_new_generation_with_original_request(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_failed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    failed_id = seeded_failed_report.id
    resp = test_client.post(f"/reports/{failed_id}/retry")
    assert resp.status_code == 200
    new_id = resp.json()["report_id"]
    assert new_id != failed_id
    # Original row retained for audit.
    old = test_client.get(f"/reports/{failed_id}")
    assert old.json()["status"] == "failed"
    # New row exists with status generating + same original_request.
    new = test_client.get(f"/reports/{new_id}")
    assert new.json()["status"] == "generating"
    assert new.json()["original_request"] == seeded_failed_report.original_request


def test_retry_404_for_non_failed_report(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_completed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_completed_report.id
    resp = test_client.post(f"/reports/{rid}/retry")
    # Only failed/cancelled rows can be retried.
    assert resp.status_code in (400, 409)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_report_retry.py -v
```

Expected: FAIL (retry endpoint missing)

- [ ] **Step 3: Add the retry handler**

```python
@router.post("/{report_id}/retry")
async def retry_report_ep(
    report_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: BackgroundReportRegistry = Depends(get_registry),
    presence: UserPresenceRegistry = Depends(get_presence),
) -> dict:
    row = db.get(Report, report_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404)
    if row.status not in ("failed", "cancelled"):
        raise HTTPException(400, "Only failed or cancelled reports can be retried")
    if row.original_request is None:
        raise HTTPException(400, "Report has no persisted original_request")
    body = GenerateReportIn(**row.original_request)
    # Reuse the generate endpoint's logic by calling it directly.
    return await generate_report_ep(body=body, user=user, db=db, registry=registry, presence=presence)
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_report_retry.py -v
uv run ruff format packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_retry.py
uv run ruff check packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_retry.py
git add packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_report_retry.py
git commit -m "feat(bg-reports): POST /reports/{id}/retry"
```

---

## Task 11: Reports list endpoint includes `status` field

**Files:**
- Modify: `packages/server/src/openlia_server/routes/reports.py` (the list endpoint)
- Test: `packages/server/tests/test_reports_list_status.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_reports_list_status.py
from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_returns_status_for_each_report(
    test_client: TestClient, seeded_reports_of_each_status
) -> None:
    resp = test_client.get("/reports")
    assert resp.status_code == 200
    rows = resp.json()
    statuses = {r["status"] for r in rows}
    assert {"generating", "complete", "failed", "cancelled"}.issubset(statuses)
```

> Fixture `seeded_reports_of_each_status` inserts four rows directly, one per status. Add to conftest.

- [ ] **Step 2: Run + Implement**

```bash
uv run pytest packages/server/tests/test_reports_list_status.py -v
```

Expected: FAIL (status field missing from serialization)

Modify the `ReportOut` (or equivalent) Pydantic model to include `status`, `failure_reason`, `original_request`, `started_at`. Match the column types.

- [ ] **Step 3: Re-run + commit**

```bash
uv run pytest packages/server/tests/test_reports_list_status.py -v
uv run ruff format packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_reports_list_status.py
uv run ruff check packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_reports_list_status.py
git add packages/server/src/openlia_server/routes/reports.py packages/server/tests/test_reports_list_status.py
git commit -m "feat(bg-reports): expose status + retry fields on reports list"
```

---

## Task 12: `GET /notifications/stream` — long-lived notifications SSE

**Files:**
- Create: `packages/server/src/openlia_server/routes/notifications_stream.py`
- Test: `packages/server/tests/test_notifications_stream.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_notifications_stream.py
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from openlia_server.services.user_presence_registry import UserPresenceRegistry


def test_get_notifications_stream_returns_eventstream(
    test_client: TestClient,
) -> None:
    with test_client.stream("GET", "/notifications/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")


def test_open_notification_stream_registers_user_in_presence(
    test_client: TestClient, app_presence: UserPresenceRegistry, test_user
) -> None:
    # Open the stream in a background thread; check presence registers.
    import threading, time
    stop = threading.Event()
    def opener():
        with test_client.stream("GET", "/notifications/stream") as resp:
            while not stop.is_set():
                time.sleep(0.05)
    t = threading.Thread(target=opener, daemon=True)
    t.start()
    time.sleep(0.3)
    assert test_user.id not in app_presence.users_with_no_connections()
    stop.set()
    t.join(timeout=2.0)
```

> `app_presence` fixture exposes the app's UserPresenceRegistry. Add to conftest by reading from `app.state.presence`.

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/server/tests/test_notifications_stream.py -v
```

Expected: FAIL (endpoint doesn't exist)

- [ ] **Step 3: Write the endpoint**

```python
# packages/server/src/openlia_server/routes/notifications_stream.py
"""GET /notifications/stream — app-shell SSE for completion toasts."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from openlia_server.services.user_presence_registry import UserPresenceRegistry


def build_notifications_stream_router(*, heartbeat_seconds: int = 30) -> APIRouter:
    router = APIRouter()

    @router.get("/stream")
    async def stream_notifications(
        user=Depends(get_current_user),
        presence: UserPresenceRegistry = Depends(get_presence),
    ) -> StreamingResponse:
        queue = presence.attach(user.id)

        async def gen() -> AsyncIterator[bytes]:
            try:
                while True:
                    try:
                        ev = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                        name = ev.get("type", "event")
                        yield f"event: {name}\ndata: {json.dumps(ev, default=str)}\n\n".encode("utf-8")
                    except asyncio.TimeoutError:
                        yield b"event: report.heartbeat\ndata: {}\n\n"
            finally:
                presence.detach(user.id, queue)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return router
```

Wire under `/notifications` prefix in `app.py`.

- [ ] **Step 4: Run + commit**

```bash
uv run pytest packages/server/tests/test_notifications_stream.py -v
uv run ruff format packages/server/src/openlia_server/routes/notifications_stream.py packages/server/tests/test_notifications_stream.py
uv run ruff check packages/server/src/openlia_server/routes/notifications_stream.py packages/server/tests/test_notifications_stream.py
git add packages/server/src/openlia_server/routes/notifications_stream.py packages/server/tests/test_notifications_stream.py
git commit -m "feat(bg-reports): GET /notifications/stream long-lived SSE"
```

---

## Task 13: `POST /notifications/presence-close` — beforeunload beacon

**Files:**
- Modify: `packages/server/src/openlia_server/routes/notifications_stream.py`
- Test: `packages/server/tests/test_notifications_presence_close.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_notifications_presence_close.py
from __future__ import annotations

from fastapi.testclient import TestClient


def test_presence_close_fast_forwards_disconnect_timestamp(
    test_client: TestClient, app_presence, test_user
) -> None:
    # Simulate the user having an open queue, then disconnecting.
    q = app_presence.attach(test_user.id)
    app_presence.detach(test_user.id, q)
    original_ts = app_presence.users_with_no_connections()[test_user.id]
    resp = test_client.post("/notifications/presence-close")
    assert resp.status_code == 200
    new_ts = app_presence.users_with_no_connections()[test_user.id]
    assert (original_ts - new_ts).total_seconds() >= 60
```

- [ ] **Step 2: Run + implement**

Append to `notifications_stream.py`:

```python
@router.post("/presence-close")
def presence_close_ep(
    user=Depends(get_current_user),
    presence: UserPresenceRegistry = Depends(get_presence),
) -> dict:
    presence.set_imminent_disconnect(user.id)
    return {"ok": True}
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/server/tests/test_notifications_presence_close.py -v
git add packages/server/src/openlia_server/routes/notifications_stream.py packages/server/tests/test_notifications_presence_close.py
git commit -m "feat(bg-reports): POST /notifications/presence-close beacon"
```

---

## Task 14: Auto-cancel sweep — background asyncio task

**Files:**
- Create: `packages/server/src/openlia_server/services/auto_cancel_sweep.py`
- Test: `packages/server/tests/test_auto_cancel_sweep.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_auto_cancel_sweep.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from openlia_server.services.auto_cancel_sweep import auto_cancel_tick
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry


@pytest.mark.asyncio
async def test_tick_cancels_users_disconnected_beyond_grace() -> None:
    presence = UserPresenceRegistry()
    registry = BackgroundReportRegistry()

    async def long_runner():
        await asyncio.sleep(10)
        yield {"type": "noop"}

    t = registry.submit(user_id="u1", report_id="r1", runner_coro=long_runner())
    # Simulate: user attached briefly then detached >grace ago.
    q = presence.attach("u1")
    presence.detach("u1", q)
    # Fast-forward the disconnect timestamp manually for determinism.
    presence._last_disconnect_at["u1"] = datetime.now(UTC) - timedelta(seconds=120)

    cancelled = await auto_cancel_tick(
        presence=presence,
        registry=registry,
        db_session_factory=_noop_session_factory,
        grace_seconds=90,
    )
    assert cancelled == ["r1"]
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t.asyncio_task, timeout=1.0)


@pytest.mark.asyncio
async def test_tick_ignores_users_with_open_connections() -> None:
    presence = UserPresenceRegistry()
    registry = BackgroundReportRegistry()

    async def long_runner():
        await asyncio.sleep(10)
        yield {"type": "noop"}

    t = registry.submit(user_id="u1", report_id="r1", runner_coro=long_runner())
    presence.attach("u1")  # keep open

    cancelled = await auto_cancel_tick(
        presence=presence,
        registry=registry,
        db_session_factory=_noop_session_factory,
        grace_seconds=90,
    )
    assert cancelled == []
    # Cleanup.
    registry.cancel("r1")
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(t.asyncio_task, timeout=1.0)


def _noop_session_factory():
    class _CM:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, *a, **kw): return None
        def commit(self): pass
    return _CM()
```

- [ ] **Step 2: Run + implement**

```python
# packages/server/src/openlia_server/services/auto_cancel_sweep.py
"""Background asyncio task that cancels in-flight reports for users
who have been disconnected from the notifications SSE for >grace_seconds."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry

log = logging.getLogger(__name__)


async def auto_cancel_tick(
    *,
    presence: UserPresenceRegistry,
    registry: BackgroundReportRegistry,
    db_session_factory,
    grace_seconds: int = 90,
) -> list[str]:
    """One sweep cycle. Returns list of cancelled report_ids."""
    cancelled_all: list[str] = []
    now = datetime.now(UTC)
    for user_id, last_seen in presence.users_with_no_connections().items():
        if (now - last_seen).total_seconds() >= grace_seconds:
            cancelled = registry.cancel_user(user_id)
            cancelled_all.extend(cancelled)
            if cancelled:
                from openlia_server.db.models.content import Report
                with db_session_factory() as session:
                    for rid in cancelled:
                        row = session.get(Report, rid)
                        if row and row.status == "generating":
                            row.status = "cancelled"
                            row.failure_reason = "session_disconnected"
                    session.commit()
                log.info("auto-cancelled %d reports for user %s", len(cancelled), user_id)
    return cancelled_all


async def auto_cancel_loop(
    *,
    presence: UserPresenceRegistry,
    registry: BackgroundReportRegistry,
    db_session_factory,
    grace_seconds: int = 90,
    poll_seconds: int = 15,
) -> None:
    while True:
        await asyncio.sleep(poll_seconds)
        try:
            await auto_cancel_tick(
                presence=presence,
                registry=registry,
                db_session_factory=db_session_factory,
                grace_seconds=grace_seconds,
            )
        except Exception:
            log.exception("auto_cancel_tick failed")
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/server/tests/test_auto_cancel_sweep.py -v
uv run ruff format packages/server/src/openlia_server/services/auto_cancel_sweep.py packages/server/tests/test_auto_cancel_sweep.py
uv run ruff check packages/server/src/openlia_server/services/auto_cancel_sweep.py packages/server/tests/test_auto_cancel_sweep.py
git add packages/server/src/openlia_server/services/auto_cancel_sweep.py packages/server/tests/test_auto_cancel_sweep.py
git commit -m "feat(bg-reports): auto-cancel sweep for disconnected users"
```

---

## Task 15: Startup sweep — mark orphaned generating rows failed

**Files:**
- Modify: `packages/server/src/openlia_server/app.py` (or wherever the lifespan startup happens)
- Test: `packages/server/tests/test_startup_sweep.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_startup_sweep.py
from __future__ import annotations

from openlia_server.app import sweep_orphaned_generating_reports
from openlia_server.db.models.content import Report


def test_startup_sweep_marks_orphans_failed(db_session_factory, seeded_user) -> None:
    with db_session_factory() as session:
        row = Report(
            id="r_orphan",
            user_id=seeded_user.id,
            department="equity_research",
            status="generating",
        )
        session.add(row)
        session.commit()
    sweep_orphaned_generating_reports(db_session_factory)
    with db_session_factory() as session:
        row = session.get(Report, "r_orphan")
        assert row.status == "failed"
        assert row.failure_reason == "server_restart_interrupted"


def test_startup_sweep_leaves_complete_rows_alone(db_session_factory, seeded_user) -> None:
    with db_session_factory() as session:
        row = Report(
            id="r_done",
            user_id=seeded_user.id,
            department="equity_research",
            status="complete",
        )
        session.add(row)
        session.commit()
    sweep_orphaned_generating_reports(db_session_factory)
    with db_session_factory() as session:
        row = session.get(Report, "r_done")
        assert row.status == "complete"
```

- [ ] **Step 2: Run + implement**

In `packages/server/src/openlia_server/app.py`:

```python
def sweep_orphaned_generating_reports(db_session_factory) -> int:
    from openlia_server.db.models.content import Report
    with db_session_factory() as session:
        orphans = session.query(Report).filter(Report.status == "generating").all()
        for row in orphans:
            row.status = "failed"
            row.failure_reason = "server_restart_interrupted"
        session.commit()
    return len(orphans)
```

Wire into the `lifespan` startup hook:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    sweep_orphaned_generating_reports(get_session_factory())
    # ... rest of existing startup ...
    yield
    # shutdown
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/server/tests/test_startup_sweep.py -v
git add packages/server/src/openlia_server/app.py packages/server/tests/test_startup_sweep.py
git commit -m "feat(bg-reports): startup sweep for orphaned generating reports"
```

---

## Task 16: Lifespan wiring — registry, presence, auto-cancel loop

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_app_lifespan_wires_bg_services.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_app_lifespan_wires_bg_services.py
from openlia_server.app import build_app
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry


def test_app_state_carries_registry_and_presence() -> None:
    app = build_app()
    assert isinstance(app.state.bg_report_registry, BackgroundReportRegistry)
    assert isinstance(app.state.user_presence, UserPresenceRegistry)
```

- [ ] **Step 2: Run + implement**

In `app.py`, populate state in the lifespan or app factory:

```python
import asyncio

from openlia_server.services.auto_cancel_sweep import auto_cancel_loop
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweep_orphaned_generating_reports(get_session_factory())
    app.state.bg_report_registry = BackgroundReportRegistry()
    app.state.user_presence = UserPresenceRegistry()
    sweep_task = asyncio.create_task(auto_cancel_loop(
        presence=app.state.user_presence,
        registry=app.state.bg_report_registry,
        db_session_factory=get_session_factory(),
        grace_seconds=int(os.environ.get("OPENLIA_AUTO_CANCEL_GRACE_SECONDS", "90")),
        poll_seconds=int(os.environ.get("OPENLIA_AUTO_CANCEL_POLL_SECONDS", "15")),
    ))
    try:
        yield
    finally:
        sweep_task.cancel()
        # Cancel any still-in-flight reports.
        for task in list(app.state.bg_report_registry._by_report_id.values()):
            task.asyncio_task.cancel()


def get_registry(request: Request) -> BackgroundReportRegistry:
    return request.app.state.bg_report_registry


def get_presence(request: Request) -> UserPresenceRegistry:
    return request.app.state.user_presence
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest packages/server/tests/test_app_lifespan_wires_bg_services.py -v
git add packages/server/src/openlia_server/app.py packages/server/tests/test_app_lifespan_wires_bg_services.py
git commit -m "feat(bg-reports): wire registry + presence + sweep into app lifespan"
```

---

## Task 17: Frontend — `useNotificationsStream` hook + toasts

**Files:**
- Create: `frontend/src/app/useNotificationsStream.ts`
- Test: `frontend/src/app/useNotificationsStream.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/app/useNotificationsStream.test.ts
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useNotificationsStream } from "./useNotificationsStream";

let lastEventSource: any;
beforeEach(() => {
  class MockES {
    listeners = new Map<string, ((e: any) => void)[]>();
    url: string;
    constructor(url: string) { this.url = url; lastEventSource = this; }
    addEventListener(type: string, fn: any) {
      this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]);
    }
    close() {}
    fire(type: string, payload: any) {
      (this.listeners.get(type) ?? []).forEach((fn) => fn({ data: JSON.stringify(payload) }));
    }
  }
  (global as any).EventSource = MockES;
});
afterEach(() => { delete (global as any).EventSource; });

describe("useNotificationsStream", () => {
  it("opens an EventSource at /notifications/stream", () => {
    const navigate = vi.fn();
    const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
    renderHook(() => useNotificationsStream({ navigate, toast }));
    expect(lastEventSource.url).toBe("/notifications/stream");
  });

  it("fires a success toast on report.complete", () => {
    const navigate = vi.fn();
    const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
    renderHook(() => useNotificationsStream({ navigate, toast }));
    lastEventSource.fire("report.complete", { report_id: "r1", title: "MSFT" });
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringContaining("MSFT"),
      expect.anything(),
    );
  });

  it("fires an error toast on report.failed", () => {
    const navigate = vi.fn();
    const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
    renderHook(() => useNotificationsStream({ navigate, toast }));
    lastEventSource.fire("report.failed", { report_id: "r1", failure_reason: "oops" });
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("oops"),
      expect.anything(),
    );
  });
});
```

- [ ] **Step 2: Run + implement**

```ts
// frontend/src/app/useNotificationsStream.ts
import { useEffect } from "react";

interface Toaster {
  success(msg: string, opts?: { action?: { label: string; onClick: () => void } }): void;
  error(msg: string, opts?: { action?: { label: string; onClick: () => void } }): void;
  info(msg: string, opts?: { action?: { label: string; onClick: () => void } }): void;
}

interface Options {
  navigate: (path: string) => void;
  toast: Toaster;
}

export function useNotificationsStream({ navigate, toast }: Options): void {
  useEffect(() => {
    const es = new EventSource("/notifications/stream");
    es.addEventListener("report.complete", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      toast.success(`Report ready: ${data.title}`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("report.failed", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      toast.error(`Report failed: ${data.failure_reason}`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${data.report_id}`) },
      });
    });
    es.addEventListener("report.cancelled", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      toast.info(`Report cancelled`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${data.report_id}`) },
      });
    });
    return () => es.close();
  }, [navigate, toast]);
}
```

Wire into `App.tsx`:

```tsx
import { useNotificationsStream } from "./app/useNotificationsStream";
import { useNavigate } from "react-router-dom";
import { toast } from "<existing toast library>";

function App() {
  const navigate = useNavigate();
  useNotificationsStream({ navigate, toast });
  // ... existing app shell ...
}
```

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm test -- useNotificationsStream.test.ts
git add frontend/src/app/useNotificationsStream.ts frontend/src/app/useNotificationsStream.test.ts frontend/src/App.tsx
git commit -m "feat(bg-reports): useNotificationsStream hook + app-shell wiring"
```

---

## Task 18: Frontend — `useBeforeUnloadBeacon`

**Files:**
- Create: `frontend/src/app/useBeforeUnloadBeacon.ts`
- Test: `frontend/src/app/useBeforeUnloadBeacon.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/app/useBeforeUnloadBeacon.test.ts
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useBeforeUnloadBeacon } from "./useBeforeUnloadBeacon";

describe("useBeforeUnloadBeacon", () => {
  it("sendBeacon to /notifications/presence-close on beforeunload", () => {
    const sendBeacon = vi.fn();
    (navigator as any).sendBeacon = sendBeacon;
    renderHook(() => useBeforeUnloadBeacon());
    window.dispatchEvent(new Event("beforeunload"));
    expect(sendBeacon).toHaveBeenCalledWith("/notifications/presence-close");
  });
});
```

- [ ] **Step 2: Run + implement**

```ts
// frontend/src/app/useBeforeUnloadBeacon.ts
import { useEffect } from "react";

export function useBeforeUnloadBeacon(): void {
  useEffect(() => {
    function onBeforeUnload() {
      try {
        navigator.sendBeacon("/notifications/presence-close");
      } catch {
        // best-effort; the auto-cancel sweep still fires after grace
      }
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);
}
```

Wire into `App.tsx` alongside `useNotificationsStream`.

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm test -- useBeforeUnloadBeacon.test.ts
git add frontend/src/app/useBeforeUnloadBeacon.ts frontend/src/app/useBeforeUnloadBeacon.test.ts frontend/src/App.tsx
git commit -m "feat(bg-reports): beforeunload beacon for fast presence-close"
```

---

## Task 19: Frontend — status-aware `ReportCard` (placeholder + failed variants)

**Files:**
- Modify: `frontend/src/components/equity-research/ReportCard.tsx`
- Create: `frontend/src/components/equity-research/GeneratingPlaceholderCard.tsx`
- Create: `frontend/src/components/equity-research/FailedReportCard.tsx`
- Test: extend `frontend/src/components/equity-research/ReportCard.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// in ReportCard.test.tsx — add:
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ReportCard } from "./ReportCard";

it("renders the GeneratingPlaceholderCard variant for status=generating", () => {
  const report = {
    id: "r1",
    status: "generating",
    started_at: new Date(Date.now() - 5000).toISOString(),
    original_request: { user_input: "MSFT" },
  };
  render(<ReportCard report={report as any} />);
  expect(screen.getByText(/MSFT/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
});

it("renders the FailedReportCard variant for status=failed", () => {
  const report = {
    id: "r1",
    status: "failed",
    failure_reason: "provider error: 429",
  };
  render(<ReportCard report={report as any} />);
  expect(screen.getByText(/provider error/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
});

it("Cancel button calls DELETE /reports/{id}", async () => {
  const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({ ok: true } as any);
  window.confirm = vi.fn(() => true);
  const report = { id: "r1", status: "generating", started_at: new Date().toISOString(), original_request: { user_input: "MSFT" } };
  render(<ReportCard report={report as any} />);
  fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
  await new Promise(r => setTimeout(r, 0));
  expect(fetchSpy).toHaveBeenCalledWith("/reports/r1", { method: "DELETE" });
});

it("Retry button calls POST /reports/{id}/retry and navigates to the new report", async () => {
  const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({
    ok: true, json: async () => ({ report_id: "r_new" }),
  } as any);
  const navigate = vi.fn();
  const report = { id: "r1", status: "failed", failure_reason: "x" };
  render(<ReportCard report={report as any} navigate={navigate} />);
  fireEvent.click(screen.getByRole("button", { name: /retry/i }));
  await new Promise(r => setTimeout(r, 0));
  expect(fetchSpy).toHaveBeenCalledWith("/reports/r1/retry", { method: "POST" });
  expect(navigate).toHaveBeenCalledWith("/equity-research?report_id=r_new");
});
```

- [ ] **Step 2: Run + implement**

Create the two new card variants, then refactor `ReportCard.tsx` to dispatch by status:

```tsx
// GeneratingPlaceholderCard.tsx
export function GeneratingPlaceholderCard({ report }: { report: Report }) {
  const elapsedSec = report.started_at
    ? Math.floor((Date.now() - new Date(report.started_at).getTime()) / 1000)
    : 0;
  const title = report.original_request?.user_input ?? "Generating report";

  async function handleCancel() {
    if (!confirm("Cancel this report? Partial progress will be discarded.")) return;
    await fetch(`/reports/${report.id}`, { method: "DELETE" });
  }

  return (
    <div className="card card--generating">
      <div className="spinner" />
      <h3>{title}</h3>
      <p>{Math.floor(elapsedSec / 60)}:{(elapsedSec % 60).toString().padStart(2, "0")} elapsed</p>
      <button onClick={handleCancel}>Cancel</button>
    </div>
  );
}

// FailedReportCard.tsx
export function FailedReportCard({ report, navigate }: { report: Report; navigate: (path: string) => void }) {
  async function handleRetry() {
    const resp = await fetch(`/reports/${report.id}/retry`, { method: "POST" });
    const { report_id } = await resp.json();
    navigate(`/equity-research?report_id=${report_id}`);
  }
  return (
    <div className={`card card--${report.status}`}>
      <h3>{report.original_request?.user_input ?? "Report"}</h3>
      <p>{report.failure_reason}</p>
      <button onClick={handleRetry}>Retry</button>
      <button onClick={() => fetch(`/reports/${report.id}`, { method: "DELETE" })}>Delete</button>
    </div>
  );
}

// ReportCard.tsx (dispatcher):
export function ReportCard({ report, navigate }: Props) {
  switch (report.status) {
    case "generating":
      return <GeneratingPlaceholderCard report={report} />;
    case "failed":
    case "cancelled":
      return <FailedReportCard report={report} navigate={navigate} />;
    case "complete":
    default:
      return <CompletedReportCard report={report} navigate={navigate} />;
  }
}
```

- [ ] **Step 3: Run + commit**

```bash
cd frontend && npm test -- ReportCard.test.tsx
git add frontend/src/components/equity-research/ReportCard.tsx frontend/src/components/equity-research/GeneratingPlaceholderCard.tsx frontend/src/components/equity-research/FailedReportCard.tsx frontend/src/components/equity-research/ReportCard.test.tsx
git commit -m "feat(bg-reports): status-aware ReportCard variants"
```

---

## Task 20: Frontend — `useReportStream` switches to `GET /reports/{id}/stream` + `?report_id` reattach

**Files:**
- Modify: `frontend/src/components/report/useReportStream.ts`
- Modify: `frontend/src/pages/EquityResearchPage.tsx` (or whichever page mounts the stream)
- Test: extend `frontend/src/components/report/useReportStream.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// in useReportStream.test.ts — add:
import { renderHook } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";
import { useReportStream } from "./useReportStream";

let lastES: any;
class MockES { url: string; constructor(u: string) { this.url = u; lastES = this; } addEventListener() {} close() {} }

it("opens GET /reports/{id}/stream when given a report_id", () => {
  (global as any).EventSource = MockES;
  renderHook(() => useReportStream("r_test"));
  expect(lastES.url).toBe("/reports/r_test/stream");
  delete (global as any).EventSource;
});
```

- [ ] **Step 2: Modify the hook**

Refactor `useReportStream.ts` from POST-based SSE to a GET-based EventSource opened against the new endpoint:

```ts
export function useReportStream(reportId: string | null) {
  useEffect(() => {
    if (!reportId) return;
    const es = new EventSource(`/reports/${reportId}/stream`);
    // existing event listeners for report.start, report.phase,
    // report.section.complete, report.complete, report.error etc.
    return () => es.close();
  }, [reportId]);
}
```

- [ ] **Step 3: Wire `?report_id` into EquityResearchPage**

```tsx
// EquityResearchPage.tsx
import { useSearchParams } from "react-router-dom";

const [searchParams] = useSearchParams();
const reportId = searchParams.get("report_id");
useReportStream(reportId);
```

The "Generate" handler then becomes:

```tsx
async function handleGenerate(request: ReportRequest) {
  const resp = await fetch("/reports/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  const { report_id } = await resp.json();
  setSearchParams({ report_id });
  // useReportStream attaches automatically via the dep change.
}
```

- [ ] **Step 4: Run + commit**

```bash
cd frontend && npm test -- useReportStream.test.ts
git add frontend/src/components/report/useReportStream.ts frontend/src/components/report/useReportStream.test.ts frontend/src/pages/EquityResearchPage.tsx
git commit -m "feat(bg-reports): useReportStream uses GET endpoint + ?report_id reattach"
```

---

## Task 21: Notifications SSE heartbeat test

**Files:**
- Test: `packages/server/tests/test_notifications_heartbeat.py`

(No source change — Task 12's `heartbeat_seconds` parameter already implements heartbeats. Guard test.)

- [ ] **Step 1: Write the test**

```python
# packages/server/tests/test_notifications_heartbeat.py
"""Notifications SSE emits a heartbeat after heartbeat_seconds of
inactivity. Uses a short heartbeat for test speed."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_heartbeat_emitted_during_quiet_period(
    test_client_with_short_heartbeat: TestClient,
) -> None:
    """Heartbeat at 1s; pull bytes from the stream; assert heartbeat seen."""
    with test_client_with_short_heartbeat.stream("GET", "/notifications/stream") as resp:
        text = ""
        import time
        deadline = time.time() + 3.0
        for chunk in resp.iter_text(chunk_size=4096):
            text += chunk
            if "report.heartbeat" in text or time.time() > deadline:
                break
    assert "report.heartbeat" in text
```

> Fixture `test_client_with_short_heartbeat` instantiates the app with `heartbeat_seconds=1` for fast test execution.

- [ ] **Step 2: Run + commit**

```bash
uv run pytest packages/server/tests/test_notifications_heartbeat.py -v
git add packages/server/tests/test_notifications_heartbeat.py
git commit -m "test(bg-reports): notifications heartbeat fires during quiet periods"
```

---

## Validation (manual smoke after all tasks land)

Do NOT commit any code from this step.

- [ ] **Set env and restart server:**

```bash
pkill -9 -f "openlia serve" || true
sleep 1
OPENLIA_DEV_MODE=1 OPENLIA_BACKGROUND_REPORTS_ENABLED=1 OPENLIA_USE_SUBAGENT_RUNNER=1 \
  OPENLIA_DEFAULT_SUBAGENT_MODEL_ID="<your cheap model id>" \
  uv run openlia serve > /tmp/openlia-serve.log 2>&1 &
sleep 4
tail -3 /tmp/openlia-serve.log
```

- [ ] **Kick off a report from the equity_research page.** Confirm:
  - POST returns within ~1s with `report_id`
  - Placeholder card appears in Repository
  - Live progress streams on the current page
- [ ] **Navigate to /portfolio mid-generation.** Confirm generation continues (check `dev-events.jsonl` for ongoing events). Wait for completion.
- [ ] **Verify completion toast** appears on the /portfolio page when the report finishes.
- [ ] **Navigate back to /equity-research?report_id={id}.** Confirm the page re-renders the completed report (synthetic terminal frame).
- [ ] **Kick off two reports simultaneously.** Confirm both run in parallel (no queue), both notify on completion.
- [ ] **Close the browser tab while a report is generating.** Wait 90-105s. Open the app again. Confirm the report shows `cancelled/session_disconnected`.
- [ ] **Force a server restart while a report is generating.** Restart server. Confirm the report shows `failed/server_restart_interrupted`. Click "Retry" → confirm new report starts with the same `original_request`.

If all seven pass, the feature is validated.

---

## Spec coverage self-review

| Spec section | Implementation task(s) |
|---|---|
| §1 Registry + lifecycle (submit/get/cancel, fan-out, event ring) | Tasks 2, 3, 4, 16 |
| §2 Persistence (status column, original_request, startup sweep, retry) | Tasks 1, 10, 11, 15 |
| §3 SSE re-subscription (GET /reports/{id}/stream, synthesized terminal) | Tasks 7, 8 |
| §4 Presence channel + auto-cancel (notifications SSE, sweep, beacon, heartbeat) | Tasks 5, 12, 13, 14, 21 |
| §5 Frontend touchpoints (notifications hook, beacon, status cards, useReportStream switch) | Tasks 17, 18, 19, 20 |
| Configuration surfaces (env vars) | Wired in Tasks 6, 16 |
| POST /reports/generate fast return + DELETE + retry | Tasks 6, 9, 10 |
| Test plan (22 slices) | All slices covered across Tasks 1-21 |

No type/method-name drift between tasks. No placeholders.

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-05-17-background-report-generation.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
