# Phase 6 — Background Task Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the server-side background task scheduler so Morning Briefing reports, Earnings Update scans, Macro Research assessments, and the nightly pruning sweep all run on configured schedules independently of any user session. Ships the APScheduler wrapper, per-department executors, missed-job catch-up, crash recovery, retry-with-backoff, notification insertion, and the two cross-cutting API surfaces (`/jobs/*` and `/notifications/*`).

**Architecture:** `SchedulerService` wraps APScheduler 4.x `AsyncScheduler`, booted by the FastAPI `lifespan` hook. On startup it rehydrates jobs from three department schedule tables (`mb_schedules`, `eu_schedules`, `mr_dashboard_state`), registers one maintenance job, marks orphan `job_runs` rows as `cancelled`, and fires any missed jobs within the 6-hour grace window. Each job-type has its own async executor that takes (a) a `SessionFactory`, (b) a core runner (`ReportRunner` or `BatchRunner`), and (c) a department-specific payload Protocol supplied by the plan that owns that department. The executors share a common retry/notification base. Hot-reload is supported: schedule CRUD routes call `scheduler.add_job` / `modify_job` / `remove_job` directly — no restart.

**Tech Stack:** APScheduler 4.x (async mode), croniter 2.x (missed-job calculation), SQLAlchemy 2.0+ sync sessions via `asyncio.to_thread`, FastAPI 0.110+ lifespan, pytest + pytest-asyncio, `freezegun` for time-travel tests.

**Source spec:** `planning/specs/systems/background-task-scheduling-design.md`

**Depends on:**
- Plan 1B — tables `mb_schedules`, `eu_schedules`, `job_runs`, `user_notifications`, `mr_dashboard_state`, `mr_assessment_cache`, `rs_snapshots`.
- Plan 1A — tables `users`, `sessions`, `password_reset_requests`; `SessionLocal` session factory; `Base.metadata`.
- Plan 2 — session auth middleware (routes here read `request.state.user`).
- Plan 4 — `LLMProviderError`, `is_transient(exc)`, `TierNotConfiguredError`.
- Plan 5 — `ReportRunner`, `BatchRunner`, `ChatRunner` (unused here), `ReportRequest`, `BatchItem`, `BatchResult`, `CancellationToken`, SSE event types (`ReportComplete`, `ReportError`).

**Unblocks:**
- Plan 15 (Earnings Update) — supplies the real `EUScanPlanner`; plugs schedule CRUD into the hot-reload hooks.
- Plan 16 (Morning Briefing) — supplies the real `MBRequestBuilder`; plugs schedule CRUD.
- Plan 19 (Macro Research) — supplies the real `MRAssessmentBuilder`; wires the weekly/quarterly trigger to `mr_dashboard_state`.
- Plan 7 (CLI) — reuses `run_maintenance_once()` from `executors/maintenance.py`.
- Plan 8 (frontend shell) — `GET /notifications/unread` for sidebar polling.

**Out of scope (handled elsewhere):**
- Department schedule CRUD routes (MB/EU/MR) — their respective department plans. This plan only exposes `SchedulerService.add_job/modify_job/remove_job` so those routes can call it.
- Real `MBRequestBuilder`, `EUScanPlanner`, `MRAssessmentBuilder` payloads — Plans 16, 15, 19 respectively. This plan defines the Protocols and ships **fail-fast stubs** that raise `DepartmentPayloadBuilderNotWired`. Tests use `_fakes.py` substitutes.
- Report persistence table (`reports`) — assumed already created by Plan 1A. This plan calls `ReportStore.save(...)` (Protocol) which Plan 13 will implement; tests pass a fake store.
- Real-time push notifications (SSE/WebSocket). Polling only.
- Multi-instance distributed locking — single-process v1 only.
- MR T4/T5 automatic news-triggered assessments — manual "Run now" only.
- Admin view across all users' jobs — admin queries the DB directly.

---

## File Structure

```
packages/server/src/openlia_server/
├── scheduler/
│   ├── __init__.py                    # Re-exports SchedulerService, JobType, JobStatus
│   ├── settings.py                    # SchedulerSettings dataclass + env loader
│   ├── registry.py                    # JobType / JobStatus / NotificationType enums, job-key helpers
│   ├── services/
│   │   ├── __init__.py                # empty; package marker
│   │   ├── jobs.py                    # JobRunService — CRUD on job_runs
│   │   └── notifications.py           # NotificationService — CRUD on user_notifications
│   ├── recovery.py                    # mark_orphans_cancelled(), detect_missed_runs()
│   ├── payloads.py                    # Protocols + stubs: MBRequestBuilder, EUScanPlanner, MRAssessmentBuilder, ReportStore, MRCacheStore
│   ├── executors/
│   │   ├── __init__.py                # empty
│   │   ├── base.py                    # BaseExecutor — job_runs lifecycle, retry backoff, notification emit
│   │   ├── mb.py                      # MBBriefingExecutor
│   │   ├── eu.py                      # EUScanExecutor
│   │   ├── mr.py                      # MRAssessmentExecutor
│   │   └── maintenance.py             # MaintenanceExecutor + run_maintenance_once() function
│   └── service.py                     # SchedulerService — APScheduler wrapper, hot-reload, lifespan hooks
├── routes/
│   ├── jobs.py                        # NEW — GET /jobs/history, POST /jobs/{run_id}/retry
│   └── notifications.py               # NEW — GET /notifications/unread, POST /notifications/read
└── app.py                             # MODIFIED — lifespan wires SchedulerService, registers new routers

packages/server/tests/
└── test_scheduler/
    ├── conftest.py                    # sys.path helper (--import-mode=importlib pattern)
    ├── _fakes.py                      # FakeReportRunner, FakeBatchRunner, FakeMBBuilder, FakeEUPlanner, FakeMRBuilder, FakeReportStore, FakeMRCacheStore, FakeAPScheduler
    ├── test_settings.py
    ├── test_registry.py
    ├── test_jobs_service.py
    ├── test_notifications_service.py
    ├── test_recovery.py
    ├── test_base_executor.py
    ├── test_maintenance_executor.py
    ├── test_mb_executor.py
    ├── test_eu_executor.py
    ├── test_mr_executor.py
    ├── test_scheduler_service.py
    ├── test_routes_jobs.py
    ├── test_routes_notifications.py
    └── test_lifespan_integration.py   # end-to-end: create schedule → fire → report stored → notification
```

### Design rules

1. **Async executors, sync DB.** SQLAlchemy 2.0 sessions are sync. Every DB call inside an async executor wraps in `await asyncio.to_thread(...)`. Never hold a session across an `await` that could take long.
2. **Session-per-job.** Each job creates its own session via `SessionFactory()` on entry and closes it before returning. Never share a session across jobs.
3. **Fail-fast stubs, not placeholders.** Unimplemented department payload builders raise `DepartmentPayloadBuilderNotWired` with the plan number that will wire them. Tests replace the stubs with `_fakes.py` doubles. This is a concrete ship-ready module, not a TODO.
4. **Job key format** is `"{job_type}:{user_id}"` for user-scoped jobs and `"system_maintenance"` for the singleton maintenance job. `max_running_jobs=1` per key enforces "no overlap within one user + job type."
5. **Cancellation:** executors receive a `CancellationToken` (from Plan 5). On shutdown, `SchedulerService.shutdown(grace_seconds=30)` calls `token.cancel()` on every token and gives jobs 30s to finish. Non-finishing jobs are marked `status=cancelled` in `job_runs`.
6. **Tests avoid importing through a `tests.*` package.** Per repo CLAUDE.md and pytest `--import-mode=importlib`, there are no `__init__.py` files under `tests/`. To let sibling test files share fakes, `conftest.py` does `sys.path.insert(0, str(Path(__file__).parent))` and `_fakes.py` holds the shared classes. All test files use `from _fakes import ...`.
7. **Naming consistency with Plan 5.** Runners are called via `await ...runner.run(department_id=..., user_id=..., request=..., cancel_token=...)`. Events drained with `async for event in runner.run(...): ...`.

### Notes for the executor of this plan

- If APScheduler 4.x's final API names differ from this plan (it was in pre-1.0 during drafting), update the plan to match — the public calls we rely on are: `AsyncScheduler(...)`, `scheduler.start_in_background()`, `scheduler.stop()`, `scheduler.add_schedule(func, trigger, id=..., args=...)`, `scheduler.remove_schedule(id)`, `scheduler.get_schedules()`, and `CronTrigger(...)`. Check `use_context7` → "apscheduler" if shapes have changed.
- `freezegun` can patch `datetime.datetime.now` but not `time.monotonic`. Retry-backoff tests pass a `sleep=FakeSleep()` injectable rather than calling real `asyncio.sleep`.
- `croniter` version matters: use 2.x. 1.x used a different next-prev API.

---

## Task 1: `scheduler/settings.py` — environment-driven settings

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/__init__.py`
- Create: `packages/server/src/openlia_server/scheduler/settings.py`
- Create: `packages/server/tests/test_scheduler/conftest.py`
- Create: `packages/server/tests/test_scheduler/test_settings.py`
- Modify: `packages/server/pyproject.toml` (add `apscheduler>=4.0.0a4` and `croniter>=2.0`)

- [ ] **Step 1: Add dependencies**

Edit `packages/server/pyproject.toml`, under `[project]` → `dependencies`, add two lines to the list:

```toml
"apscheduler>=4.0.0a4",
"croniter>=2.0",
```

Then run:

```bash
uv sync
```

Expected: resolves and installs both packages.

- [ ] **Step 2: Create the sys.path helper conftest**

Create `packages/server/tests/test_scheduler/conftest.py`:

```python
"""Expose this test directory on sys.path so sibling test modules can
`from _fakes import ...` without relying on a tests.* package (which
does not exist under --import-mode=importlib)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 3: Write the failing test for SchedulerSettings**

Create `packages/server/tests/test_scheduler/test_settings.py`:

```python
from __future__ import annotations

import os

import pytest

from openlia_server.scheduler.settings import SchedulerSettings


def test_defaults_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "OPENLIA_SCHEDULER_ENABLED",
        "OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS",
        "OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS",
    ):
        monkeypatch.delenv(k, raising=False)
    s = SchedulerSettings.from_env()
    assert s.enabled is True
    assert s.misfire_grace_seconds == 21_600
    assert s.shutdown_grace_seconds == 30


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True), ("True", True), ("1", True), ("yes", True),
        ("false", False), ("False", False), ("0", False), ("no", False),
    ],
)
def test_enabled_parses_boolean_strings(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_ENABLED", raw)
    assert SchedulerSettings.from_env().enabled is expected


def test_grace_windows_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS", "3600")
    monkeypatch.setenv("OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS", "10")
    s = SchedulerSettings.from_env()
    assert s.misfire_grace_seconds == 3_600
    assert s.shutdown_grace_seconds == 10


def test_negative_grace_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS", "-1")
    with pytest.raises(ValueError, match="misfire_grace_seconds"):
        SchedulerSettings.from_env()


def test_malformed_integer_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS", "not-a-number")
    with pytest.raises(ValueError, match="shutdown_grace_seconds"):
        SchedulerSettings.from_env()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia_server.scheduler'`.

- [ ] **Step 5: Create the empty package init**

Create `packages/server/src/openlia_server/scheduler/__init__.py`:

```python
"""Background task scheduling for OpenLIA server.

Public surface is added incrementally in later tasks. This file only
declares the package boundary for now.
"""
from __future__ import annotations
```

- [ ] **Step 6: Implement SchedulerSettings**

Create `packages/server/src/openlia_server/scheduler/settings.py`:

```python
"""Environment-driven scheduler settings. All knobs are ops-level with
sensible defaults; none are stored in config_store."""
from __future__ import annotations

import os
from dataclasses import dataclass


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"invalid boolean: {raw!r}")


def _parse_int(raw: str | None, default: int, name: str) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name}: cannot parse {raw!r} as int") from exc
    if value < 0:
        raise ValueError(f"{name}: must be >= 0, got {value}")
    return value


@dataclass(frozen=True)
class SchedulerSettings:
    enabled: bool
    misfire_grace_seconds: int
    shutdown_grace_seconds: int

    @classmethod
    def from_env(cls) -> "SchedulerSettings":
        return cls(
            enabled=_parse_bool(os.getenv("OPENLIA_SCHEDULER_ENABLED"), default=True),
            misfire_grace_seconds=_parse_int(
                os.getenv("OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS"),
                default=21_600,
                name="misfire_grace_seconds",
            ),
            shutdown_grace_seconds=_parse_int(
                os.getenv("OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS"),
                default=30,
                name="shutdown_grace_seconds",
            ),
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_settings.py -v`
Expected: 8 tests pass.

- [ ] **Step 8: Commit**

```bash
git add packages/server/pyproject.toml uv.lock \
    packages/server/src/openlia_server/scheduler/__init__.py \
    packages/server/src/openlia_server/scheduler/settings.py \
    packages/server/tests/test_scheduler/conftest.py \
    packages/server/tests/test_scheduler/test_settings.py
git commit -m "phase-6(scheduler): SchedulerSettings from env (apscheduler + croniter deps)"
```

---

## Task 2: `scheduler/registry.py` — enums + job-key helpers

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/registry.py`
- Create: `packages/server/tests/test_scheduler/test_registry.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_registry.py`:

```python
from __future__ import annotations

import pytest

from openlia_server.scheduler.registry import (
    MAINTENANCE_JOB_KEY,
    JobStatus,
    JobType,
    NotificationType,
    department_for_job_type,
    job_key,
    parse_job_key,
)


def test_job_types_match_spec() -> None:
    assert {t.value for t in JobType} == {
        "mb_briefing", "eu_scan", "mr_assessment", "system_maintenance"
    }


def test_job_statuses_match_spec() -> None:
    assert {s.value for s in JobStatus} == {
        "running", "completed", "failed", "cancelled"
    }


def test_notification_types_match_spec() -> None:
    assert {n.value for n in NotificationType} == {
        "report_ready", "assessment_ready", "job_failed"
    }


def test_job_key_user_scoped() -> None:
    assert job_key(JobType.MB_BRIEFING, user_id="u_abc") == "mb_briefing:u_abc"
    assert job_key(JobType.EU_SCAN, user_id="u_abc") == "eu_scan:u_abc"
    assert job_key(JobType.MR_ASSESSMENT, user_id="u_abc") == "mr_assessment:u_abc"


def test_job_key_maintenance_has_fixed_key() -> None:
    assert MAINTENANCE_JOB_KEY == "system_maintenance"
    assert job_key(JobType.SYSTEM_MAINTENANCE, user_id=None) == "system_maintenance"


def test_job_key_user_scoped_requires_user_id() -> None:
    with pytest.raises(ValueError, match="user_id required"):
        job_key(JobType.MB_BRIEFING, user_id=None)


def test_parse_job_key_round_trips() -> None:
    assert parse_job_key("mb_briefing:u_abc") == (JobType.MB_BRIEFING, "u_abc")
    assert parse_job_key("system_maintenance") == (JobType.SYSTEM_MAINTENANCE, None)


def test_parse_job_key_rejects_unknown_prefix() -> None:
    with pytest.raises(ValueError, match="unknown job type"):
        parse_job_key("garbage:u_abc")


def test_department_mapping() -> None:
    assert department_for_job_type(JobType.MB_BRIEFING) == "morning_briefing"
    assert department_for_job_type(JobType.EU_SCAN) == "earnings_update"
    assert department_for_job_type(JobType.MR_ASSESSMENT) == "macro_research"


def test_department_mapping_rejects_maintenance() -> None:
    with pytest.raises(ValueError, match="no department"):
        department_for_job_type(JobType.SYSTEM_MAINTENANCE)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_registry.py -v`
Expected: FAIL on import (module missing).

- [ ] **Step 3: Implement registry.py**

Create `packages/server/src/openlia_server/scheduler/registry.py`:

```python
"""Canonical enums + job-key helpers used throughout the scheduler.

Job keys serve two purposes:
  1. APScheduler schedule id — uniqueness prevents double-registration.
  2. max_instances=1 per key enforces the "no overlap for a given
     user + job type" rule in the spec.
"""
from __future__ import annotations

from enum import Enum


class JobType(str, Enum):
    MB_BRIEFING = "mb_briefing"
    EU_SCAN = "eu_scan"
    MR_ASSESSMENT = "mr_assessment"
    SYSTEM_MAINTENANCE = "system_maintenance"


class JobStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(str, Enum):
    REPORT_READY = "report_ready"
    ASSESSMENT_READY = "assessment_ready"
    JOB_FAILED = "job_failed"


MAINTENANCE_JOB_KEY = "system_maintenance"


_DEPARTMENT_BY_JOB: dict[JobType, str] = {
    JobType.MB_BRIEFING: "morning_briefing",
    JobType.EU_SCAN: "earnings_update",
    JobType.MR_ASSESSMENT: "macro_research",
}


def department_for_job_type(job_type: JobType) -> str:
    try:
        return _DEPARTMENT_BY_JOB[job_type]
    except KeyError as exc:
        raise ValueError(f"no department mapping for {job_type!r}") from exc


def job_key(job_type: JobType, *, user_id: str | None) -> str:
    if job_type is JobType.SYSTEM_MAINTENANCE:
        return MAINTENANCE_JOB_KEY
    if not user_id:
        raise ValueError(f"user_id required for job_type={job_type.value}")
    return f"{job_type.value}:{user_id}"


def parse_job_key(key: str) -> tuple[JobType, str | None]:
    if key == MAINTENANCE_JOB_KEY:
        return (JobType.SYSTEM_MAINTENANCE, None)
    prefix, _, user_id = key.partition(":")
    try:
        job_type = JobType(prefix)
    except ValueError as exc:
        raise ValueError(f"unknown job type in key {key!r}") from exc
    if not user_id:
        raise ValueError(f"missing user_id in key {key!r}")
    return (job_type, user_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_registry.py -v`
Expected: 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/registry.py \
    packages/server/tests/test_scheduler/test_registry.py
git commit -m "phase-6(scheduler): JobType/JobStatus/NotificationType enums + job-key helpers"
```

---

## Task 3: `services/jobs.py` — JobRun CRUD helpers

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/services/__init__.py`
- Create: `packages/server/src/openlia_server/scheduler/services/jobs.py`
- Modify: `packages/server/tests/test_scheduler/conftest.py` (add DB fixtures)
- Create: `packages/server/tests/test_scheduler/test_jobs_service.py`

The service is a set of pure module functions that take a SQLAlchemy `Session` and operate on the `job_runs` table. They never open their own session — callers own session lifecycle.

- [ ] **Step 1: Extend the conftest with DB fixtures**

Append to `packages/server/tests/test_scheduler/conftest.py`:

```python
"""DB fixtures. Reuses the models + Base.metadata from the openlia_server
package. Each test gets a fresh in-memory SQLite with all tables created."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from openlia_server.db.models import Base


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory) -> Iterator[Session]:
    s = session_factory()
    try:
        yield s
    finally:
        s.close()
```

(The `sys.path.insert(...)` lines added in Task 1 stay at the top of the file; append the imports and fixtures after them.)

- [ ] **Step 2: Write the failing test**

Create `packages/server/tests/test_scheduler/test_jobs_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.scheduler.services import jobs as jobs_svc


def _make_user(session: Session, user_id: str = "u_1") -> User:
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        display_name=f"user-{user_id}",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    session.add(user)
    session.commit()
    return user


def test_start_run_inserts_row_and_returns_id(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session,
        user_id="u_1",
        job_type=JobType.MB_BRIEFING,
        schedule_id="sched_1",
    )
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row is not None
    assert row.status == JobStatus.RUNNING.value
    assert row.attempt == 1
    assert row.job_type == "mb_briefing"
    assert row.schedule_id == "sched_1"
    assert row.error_message is None
    assert row.completed_at is None


def test_start_run_for_maintenance_accepts_null_user(db_session: Session) -> None:
    run_id = jobs_svc.start_run(
        db_session,
        user_id=None,
        job_type=JobType.SYSTEM_MAINTENANCE,
        schedule_id=None,
    )
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row is not None
    assert row.user_id is None
    assert row.schedule_id is None


def test_start_run_retry_of_copies_attempt_plus_one(db_session: Session) -> None:
    _make_user(db_session)
    original = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_failed(db_session, original, error_message="boom")
    db_session.commit()

    retry = jobs_svc.start_run(
        db_session,
        user_id="u_1",
        job_type=JobType.MB_BRIEFING,
        schedule_id="s1",
        retry_of=original,
    )
    db_session.commit()

    retry_row = db_session.get(JobRun, retry)
    assert retry_row is not None
    assert retry_row.retry_of == original
    assert retry_row.attempt == 1  # user-triggered retry starts a new attempt chain


def test_mark_completed(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(
        db_session, run_id, result_summary='{"report_id": "r_1"}'
    )
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.COMPLETED.value
    assert row.completed_at is not None
    assert row.result_summary == '{"report_id": "r_1"}'


def test_mark_failed(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s1"
    )
    jobs_svc.mark_failed(db_session, run_id, error_message="ContextLengthError: 8192")
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.FAILED.value
    assert row.error_message == "ContextLengthError: 8192"
    assert row.completed_at is not None


def test_mark_cancelled(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MR_ASSESSMENT, schedule_id="s1"
    )
    jobs_svc.mark_cancelled(
        db_session, run_id, error_message="Server restarted during execution"
    )
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.CANCELLED.value
    assert row.error_message == "Server restarted during execution"


def test_bump_attempt_stays_running_and_records_error(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.bump_attempt(db_session, run_id, error_message="transient timeout")
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.RUNNING.value
    assert row.attempt == 2
    assert row.error_message == "transient timeout"


def test_list_orphans_returns_running_ids_only(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    r2 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s2"
    )
    jobs_svc.mark_completed(db_session, r1)
    db_session.commit()
    assert jobs_svc.list_orphans(db_session) == [r2]


def test_most_recent_for_schedule(db_session: Session) -> None:
    _make_user(db_session)
    older = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(db_session, older)
    db_session.commit()

    newer = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(db_session, newer)
    db_session.commit()

    row = jobs_svc.most_recent_for_schedule(db_session, "s1")
    assert row is not None
    assert row.id == newer


def test_list_for_user_filters_by_type_and_pagination(db_session: Session) -> None:
    _make_user(db_session)
    ids: list[str] = []
    for _ in range(5):
        ids.append(
            jobs_svc.start_run(
                db_session,
                user_id="u_1",
                job_type=JobType.MB_BRIEFING,
                schedule_id="s1",
            )
        )
    jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s2"
    )
    db_session.commit()

    mb = jobs_svc.list_for_user(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, limit=3, offset=0
    )
    assert len(mb) == 3
    mb_page2 = jobs_svc.list_for_user(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, limit=3, offset=3
    )
    assert len(mb_page2) == 2
    mb_ids = {r.id for r in mb} | {r.id for r in mb_page2}
    assert mb_ids == set(ids)


def test_list_for_user_filters_by_status(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(db_session, r1)
    r2 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_failed(db_session, r2, error_message="nope")
    db_session.commit()

    failed = jobs_svc.list_for_user(
        db_session, user_id="u_1", status=JobStatus.FAILED
    )
    assert [r.id for r in failed] == [r2]


def test_list_for_user_since_filter(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    db_session.commit()
    # Shift r1 into the past.
    row = db_session.get(JobRun, r1)
    row.started_at = datetime.now(timezone.utc) - timedelta(days=5)
    db_session.commit()

    r2 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    db_session.commit()

    recent = jobs_svc.list_for_user(
        db_session,
        user_id="u_1",
        since=datetime.now(timezone.utc) - timedelta(days=1),
    )
    assert [r.id for r in recent] == [r2]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_jobs_service.py -v`
Expected: FAIL on import — `openlia_server.scheduler.services` missing.

- [ ] **Step 4: Create the services package + jobs module**

Create `packages/server/src/openlia_server/scheduler/services/__init__.py`:

```python
"""Scheduler DB services. One module per table it owns."""
from __future__ import annotations
```

Create `packages/server/src/openlia_server/scheduler/services/jobs.py`:

```python
"""CRUD helpers for the `job_runs` table.

All functions take an active SQLAlchemy Session; none commit. Callers
own transaction boundaries so a single executor run can insert a
job_runs row + a user_notifications row in one commit."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobStatus, JobType


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_run(
    session: Session,
    *,
    user_id: str | None,
    job_type: JobType,
    schedule_id: str | None,
    retry_of: str | None = None,
) -> str:
    run_id = uuid.uuid4().hex
    run = JobRun(
        id=run_id,
        user_id=user_id,
        job_type=job_type.value,
        schedule_id=schedule_id,
        status=JobStatus.RUNNING.value,
        started_at=_now(),
        completed_at=None,
        error_message=None,
        result_summary=None,
        retry_of=retry_of,
        attempt=1,
    )
    session.add(run)
    return run_id


def mark_completed(
    session: Session, run_id: str, *, result_summary: str | None = None
) -> None:
    row = _require(session, run_id)
    row.status = JobStatus.COMPLETED.value
    row.completed_at = _now()
    row.result_summary = result_summary


def mark_failed(session: Session, run_id: str, *, error_message: str) -> None:
    row = _require(session, run_id)
    row.status = JobStatus.FAILED.value
    row.completed_at = _now()
    row.error_message = error_message


def mark_cancelled(
    session: Session, run_id: str, *, error_message: str | None = None
) -> None:
    row = _require(session, run_id)
    row.status = JobStatus.CANCELLED.value
    row.completed_at = _now()
    if error_message is not None:
        row.error_message = error_message


def bump_attempt(session: Session, run_id: str, *, error_message: str) -> None:
    """Increment attempt counter after a transient failure; stays RUNNING."""
    row = _require(session, run_id)
    row.attempt += 1
    row.error_message = error_message


def list_orphans(session: Session) -> list[str]:
    stmt = select(JobRun.id).where(JobRun.status == JobStatus.RUNNING.value)
    return [row[0] for row in session.execute(stmt)]


def most_recent_for_schedule(
    session: Session, schedule_id: str
) -> JobRun | None:
    stmt = (
        select(JobRun)
        .where(JobRun.schedule_id == schedule_id)
        .order_by(JobRun.started_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def list_for_user(
    session: Session,
    *,
    user_id: str,
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    since: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[JobRun]:
    stmt = select(JobRun).where(JobRun.user_id == user_id)
    if job_type is not None:
        stmt = stmt.where(JobRun.job_type == job_type.value)
    if status is not None:
        stmt = stmt.where(JobRun.status == status.value)
    if since is not None:
        stmt = stmt.where(JobRun.started_at >= since)
    stmt = stmt.order_by(JobRun.started_at.desc()).offset(offset).limit(limit)
    return list(session.execute(stmt).scalars())


def _require(session: Session, run_id: str) -> JobRun:
    row = session.get(JobRun, run_id)
    if row is None:
        raise LookupError(f"job_run {run_id!r} not found")
    return row
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_jobs_service.py -v`
Expected: 12 tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/services/__init__.py \
    packages/server/src/openlia_server/scheduler/services/jobs.py \
    packages/server/tests/test_scheduler/conftest.py \
    packages/server/tests/test_scheduler/test_jobs_service.py
git commit -m "phase-6(scheduler): JobRun service (start/mark_*/bump_attempt/list)"
```

---

## Task 4: `services/notifications.py` — UserNotification CRUD helpers

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/services/notifications.py`
- Create: `packages/server/tests/test_scheduler/test_notifications_service.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_notifications_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import UserNotification
from openlia_server.scheduler.registry import NotificationType
from openlia_server.scheduler.services import notifications as notif_svc


def _make_user(session: Session, uid: str = "u_1") -> None:
    u = User(
        id=uid,
        email=f"{uid}@e.com",
        display_name=f"user-{uid}",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    session.add(u)
    session.commit()


def test_insert_notification(db_session: Session) -> None:
    _make_user(db_session)
    notif_id = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="Your 7:00 AM briefing is ready.",
        job_run_id=None,
    )
    db_session.commit()
    row = db_session.get(UserNotification, notif_id)
    assert row is not None
    assert row.type == "report_ready"
    assert row.department == "morning_briefing"
    assert row.read_at is None


def test_unread_counts_by_department(db_session: Session) -> None:
    _make_user(db_session)
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="a",
        job_run_id=None,
    )
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="b",
        job_run_id=None,
    )
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="earnings_update",
        message="c",
        job_run_id=None,
    )
    db_session.commit()
    counts = notif_svc.unread_counts_by_department(db_session, user_id="u_1")
    assert counts == {"morning_briefing": 2, "earnings_update": 1}
    assert notif_svc.unread_total(db_session, user_id="u_1") == 3


def test_mark_read_only_affects_unread_rows_for_department(db_session: Session) -> None:
    _make_user(db_session)
    n1 = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="a",
        job_run_id=None,
    )
    n2 = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="earnings_update",
        message="b",
        job_run_id=None,
    )
    db_session.commit()

    affected = notif_svc.mark_department_read(
        db_session, user_id="u_1", department="morning_briefing"
    )
    db_session.commit()
    assert affected == 1
    assert db_session.get(UserNotification, n1).read_at is not None
    assert db_session.get(UserNotification, n2).read_at is None


def test_mark_department_read_skips_already_read(db_session: Session) -> None:
    _make_user(db_session)
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="a",
        job_run_id=None,
    )
    db_session.commit()
    first = notif_svc.mark_department_read(
        db_session, user_id="u_1", department="morning_briefing"
    )
    db_session.commit()
    second = notif_svc.mark_department_read(
        db_session, user_id="u_1", department="morning_briefing"
    )
    db_session.commit()
    assert first == 1
    assert second == 0


def test_prune_older_than(db_session: Session) -> None:
    _make_user(db_session)
    old_id = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="old",
        job_run_id=None,
    )
    db_session.commit()
    old_row = db_session.get(UserNotification, old_id)
    old_row.created_at = datetime.now(timezone.utc) - timedelta(days=45)
    db_session.commit()

    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="fresh",
        job_run_id=None,
    )
    db_session.commit()

    removed = notif_svc.prune_older_than(
        db_session, cutoff=datetime.now(timezone.utc) - timedelta(days=30)
    )
    db_session.commit()
    assert removed == 1
    assert db_session.get(UserNotification, old_id) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_notifications_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the notifications service**

Create `packages/server/src/openlia_server/scheduler/services/notifications.py`:

```python
"""CRUD for the `user_notifications` table. Polling-based mechanism:
insert on job completion/failure, read via unread_counts, clear via
mark_department_read."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import UserNotification
from openlia_server.scheduler.registry import NotificationType


def _now() -> datetime:
    return datetime.now(timezone.utc)


def insert(
    session: Session,
    *,
    user_id: str,
    type: NotificationType,
    department: str,
    message: str,
    job_run_id: str | None,
) -> str:
    notif_id = uuid.uuid4().hex
    row = UserNotification(
        id=notif_id,
        user_id=user_id,
        type=type.value,
        department=department,
        message=message,
        job_run_id=job_run_id,
        created_at=_now(),
        read_at=None,
    )
    session.add(row)
    return notif_id


def unread_total(session: Session, *, user_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.read_at.is_(None),
        )
    )
    return int(session.execute(stmt).scalar_one())


def unread_counts_by_department(
    session: Session, *, user_id: str
) -> dict[str, int]:
    stmt = (
        select(UserNotification.department, func.count())
        .where(
            UserNotification.user_id == user_id,
            UserNotification.read_at.is_(None),
        )
        .group_by(UserNotification.department)
    )
    return {dept: int(count) for dept, count in session.execute(stmt).all()}


def mark_department_read(
    session: Session, *, user_id: str, department: str
) -> int:
    stmt = (
        update(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.department == department,
            UserNotification.read_at.is_(None),
        )
        .values(read_at=_now())
        .execution_options(synchronize_session="fetch")
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)


def prune_older_than(session: Session, *, cutoff: datetime) -> int:
    stmt = delete(UserNotification).where(UserNotification.created_at < cutoff)
    return int(session.execute(stmt).rowcount or 0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_notifications_service.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/services/notifications.py \
    packages/server/tests/test_scheduler/test_notifications_service.py
git commit -m "phase-6(scheduler): UserNotification service (insert/unread/mark_read/prune)"
```

---

## Task 5: `recovery.py` — crash recovery + missed-job detection

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/recovery.py`
- Create: `packages/server/tests/test_scheduler/test_recovery.py`

Two responsibilities, both invoked once at startup before the scheduler starts firing:

1. **Crash recovery:** any `job_runs` row still at `status=running` is from a crashed prior session. Flip to `cancelled` with a standard error message.
2. **Missed-job detection:** for a given cron trigger + `last_run_at`, return `True` if the most recent fire-time in the past is (a) after `last_run_at` and (b) within the misfire grace window.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_recovery.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.recovery import (
    mark_orphans_cancelled,
    should_catch_up,
)
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.scheduler.services import jobs as jobs_svc


def _make_user(session: Session, uid: str = "u_1") -> None:
    session.add(
        User(
            id=uid,
            email=f"{uid}@e.com",
            display_name=f"u-{uid}",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.commit()


def test_mark_orphans_cancelled_flips_all_running_rows(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    r2 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s2"
    )
    r3 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MR_ASSESSMENT, schedule_id="s3"
    )
    jobs_svc.mark_completed(db_session, r3)
    db_session.commit()

    n = mark_orphans_cancelled(db_session)
    db_session.commit()
    assert n == 2

    for rid in (r1, r2):
        row = db_session.get(JobRun, rid)
        assert row.status == JobStatus.CANCELLED.value
        assert row.error_message == "Server restarted during execution"
        assert row.completed_at is not None

    unchanged = db_session.get(JobRun, r3)
    assert unchanged.status == JobStatus.COMPLETED.value


def test_mark_orphans_cancelled_is_idempotent(db_session: Session) -> None:
    assert mark_orphans_cancelled(db_session) == 0
    db_session.commit()


def test_should_catch_up_fires_when_last_run_predates_recent_cron_tick() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    last_run = datetime(2026, 4, 17, 6, 30, tzinfo=timezone.utc)
    # Cron "every day at 07:00 UTC" has a 07:00 tick today between last_run and now.
    assert should_catch_up(
        cron_expression="0 7 * * *",
        timezone_name="UTC",
        last_run_at=last_run,
        now=now,
        grace_seconds=21_600,
    ) is True


def test_should_catch_up_skipped_when_tick_is_older_than_grace() -> None:
    now = datetime(2026, 4, 17, 23, 0, tzinfo=timezone.utc)
    last_run = datetime(2026, 4, 16, 20, 0, tzinfo=timezone.utc)
    # Last tick was 07:00 today (16 hours ago) — beyond 6-hour grace.
    assert should_catch_up(
        cron_expression="0 7 * * *",
        timezone_name="UTC",
        last_run_at=last_run,
        now=now,
        grace_seconds=21_600,
    ) is False


def test_should_catch_up_no_prior_run_fires_if_recent_tick_in_grace() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    assert should_catch_up(
        cron_expression="0 7 * * *",
        timezone_name="UTC",
        last_run_at=None,
        now=now,
        grace_seconds=21_600,
    ) is True


def test_should_catch_up_skips_when_last_run_is_after_tick() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    last_run = datetime(2026, 4, 17, 7, 30, tzinfo=timezone.utc)
    assert should_catch_up(
        cron_expression="0 7 * * *",
        timezone_name="UTC",
        last_run_at=last_run,
        now=now,
        grace_seconds=21_600,
    ) is False


def test_should_catch_up_respects_non_utc_timezone() -> None:
    # Schedule "07:00 America/New_York" corresponds to 11:00 UTC in April.
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    last_run = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    assert should_catch_up(
        cron_expression="0 7 * * *",
        timezone_name="America/New_York",
        last_run_at=last_run,
        now=now,
        grace_seconds=21_600,
    ) is True


def test_should_catch_up_rejects_bad_cron() -> None:
    with pytest.raises(ValueError, match="cron"):
        should_catch_up(
            cron_expression="not a cron",
            timezone_name="UTC",
            last_run_at=None,
            now=datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc),
            grace_seconds=21_600,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_recovery.py -v`
Expected: FAIL — `openlia_server.scheduler.recovery` missing.

- [ ] **Step 3: Implement recovery.py**

Create `packages/server/src/openlia_server/scheduler/recovery.py`:

```python
"""Startup recovery helpers: mark orphan job_runs rows as cancelled and
determine whether a schedule needs to catch up on a missed run."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import CroniterBadCronError, croniter
from sqlalchemy import update
from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobStatus


ORPHAN_ERROR_MESSAGE = "Server restarted during execution"


def mark_orphans_cancelled(session: Session) -> int:
    """Flip every `status=running` row to `cancelled`. Idempotent: returns
    the number of rows updated (0 if no orphans)."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(JobRun)
        .where(JobRun.status == JobStatus.RUNNING.value)
        .values(
            status=JobStatus.CANCELLED.value,
            completed_at=now,
            error_message=ORPHAN_ERROR_MESSAGE,
        )
        .execution_options(synchronize_session="fetch")
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)


def should_catch_up(
    *,
    cron_expression: str,
    timezone_name: str,
    last_run_at: datetime | None,
    now: datetime,
    grace_seconds: int,
) -> bool:
    """Return True if the most recent past tick of the cron expression
    (a) is after last_run_at (or last_run_at is None) and
    (b) is within grace_seconds of `now`.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except Exception as exc:  # noqa: BLE001 — zoneinfo raises different errors
        raise ValueError(f"invalid timezone {timezone_name!r}") from exc

    try:
        local_now = now.astimezone(tz)
        it = croniter(cron_expression, local_now)
        prev_local = it.get_prev(datetime)
    except CroniterBadCronError as exc:
        raise ValueError(f"invalid cron {cron_expression!r}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"cron parse failed for {cron_expression!r}") from exc

    prev_utc = prev_local.astimezone(timezone.utc)

    # The previous tick must be within the grace window of `now`.
    if now - prev_utc > timedelta(seconds=grace_seconds):
        return False

    # If we already ran that tick (or later), skip.
    if last_run_at is not None and last_run_at >= prev_utc:
        return False

    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_recovery.py -v`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/recovery.py \
    packages/server/tests/test_scheduler/test_recovery.py
git commit -m "phase-6(scheduler): crash recovery + missed-job detection"
```

---

## Task 6: `payloads.py` — department payload Protocols + fail-fast stubs

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/payloads.py`
- Create: `packages/server/tests/test_scheduler/test_payloads.py`

Each department (MB, EU, MR) has a Protocol describing how the scheduler reaches into that department's world to assemble the inputs a runner needs. Plans 15/16/19 implement the real versions; Plan 6 ships stubs that raise a dedicated exception and a fake set in `_fakes.py` for this plan's own tests.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_payloads.py`:

```python
from __future__ import annotations

import pytest

from openlia_server.scheduler.payloads import (
    DepartmentPayloadBuilderNotWired,
    EUScanTarget,
    MRAssessmentPayload,
    StubEUScanPlanner,
    StubMBRequestBuilder,
    StubMRAssessmentBuilder,
    StubMRCacheStore,
    StubReportStore,
)


def test_eu_scan_target_holds_ticker_and_request() -> None:
    from openlia.llm.runtime.messages import ReportRequest

    req = ReportRequest(mode="stock_update", user_input="AAPL earnings")
    target = EUScanTarget(ticker="AAPL", request=req)
    assert target.ticker == "AAPL"
    assert target.request is req


def test_mr_assessment_payload_carries_items_schema_and_synthesize() -> None:
    from pydantic import BaseModel

    from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest

    class _T4Stub(BaseModel):
        score: float

    def _synth(results: list[BatchResult]) -> ReportRequest:
        joined = ",".join(r.id for r in results)
        return ReportRequest(mode="mr_synthesis", user_input=f"synth({joined})")

    payload = MRAssessmentPayload(
        items=[BatchItem(id="i1", context={"metric": "debt_burden"})],
        t4_task="debt_cycle",
        t4_schema=_T4Stub,
        synthesize=_synth,
    )
    assert payload.items[0].id == "i1"
    assert payload.t4_task == "debt_cycle"
    assert payload.t4_schema is _T4Stub
    req = payload.synthesize(
        [BatchResult(id="i1", ok=True, data={"score": 1.0}, error=None)]
    )
    assert req.mode == "mr_synthesis"
    assert "synth(i1)" in req.user_input


def test_stub_mb_builder_raises() -> None:
    stub = StubMBRequestBuilder()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 16"):
        stub.build(session=None, user_id="u_1", schedule_id="s_1")


def test_stub_eu_planner_raises() -> None:
    stub = StubEUScanPlanner()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 15"):
        stub.plan(
            session=None, user_id="u_1", schedule_id="s_1", since=None
        )


def test_stub_mr_builder_raises() -> None:
    stub = StubMRAssessmentBuilder()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 19"):
        stub.build(session=None, user_id="u_1")


def test_stub_report_store_raises() -> None:
    stub = StubReportStore()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 13"):
        stub.save(
            session=None,
            user_id="u_1",
            department="morning_briefing",
            payload={},
        )


def test_stub_mr_cache_store_raises() -> None:
    stub = StubMRCacheStore()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 19"):
        stub.save(
            session=None, user_id="u_1", payload={}
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_payloads.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement payloads.py**

Create `packages/server/src/openlia_server/scheduler/payloads.py`:

```python
"""Cross-department payload surface. The scheduler knows *how* to run a
job, not *what* inputs a given department needs — that knowledge lives
in the plan that owns the department. Each Protocol below is implemented
(for real) by one of Plans 13/15/16/19 and (for tests) by `_fakes.py`
in this plan's test tree."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest


class DepartmentPayloadBuilderNotWired(RuntimeError):
    """Raised by a stub payload builder to signal that the department-owning
    plan has not provided a real implementation yet."""


# ------------------------------------------------------------------
# MB — Morning Briefing
# ------------------------------------------------------------------

class MBRequestBuilder(Protocol):
    """Given a user + schedule_id, build the ReportRequest for the
    morning briefing. Owned by Plan 16."""

    def build(
        self, *, session: Session, user_id: str, schedule_id: str
    ) -> ReportRequest: ...


class StubMBRequestBuilder:
    def build(
        self, *, session: Session | None, user_id: str, schedule_id: str
    ) -> ReportRequest:
        raise DepartmentPayloadBuilderNotWired(
            "MBRequestBuilder not provided — Plan 16 (Morning Briefing) will "
            "supply the real implementation."
        )


# ------------------------------------------------------------------
# EU — Earnings Update
# ------------------------------------------------------------------

@dataclass(frozen=True)
class EUScanTarget:
    ticker: str
    request: ReportRequest


class EUScanPlanner(Protocol):
    """Given a user + EU schedule + the last time this schedule ran,
    return a list of (ticker, request) tuples for companies that have
    released earnings since. Owned by Plan 15."""

    def plan(
        self,
        *,
        session: Session,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]: ...


class StubEUScanPlanner:
    def plan(
        self,
        *,
        session: Session | None,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]:
        raise DepartmentPayloadBuilderNotWired(
            "EUScanPlanner not provided — Plan 15 (Earnings Update) will "
            "supply the real implementation."
        )


# ------------------------------------------------------------------
# MR — Macro Research
# ------------------------------------------------------------------

@dataclass(frozen=True)
class MRAssessmentPayload:
    """Output of MRAssessmentBuilder.

    `synthesize` is a callable the builder owns: it takes the list of
    T4 BatchResults produced by BatchRunner and returns the finished
    ReportRequest for T5 (synthesis). The builder is responsible for
    formatting T4 results into T5's user_input / custom_sections; the
    executor only orchestrates the two runner calls. This keeps all
    prompt-construction logic inside the department layer (Plan 19)
    and out of the scheduler.
    """

    items: list[BatchItem]
    t4_task: str
    t4_schema: type
    synthesize: Callable[[list[BatchResult]], ReportRequest]


class MRAssessmentBuilder(Protocol):
    """Given a user, build the batch items for T4 (plus the pydantic
    schema and task slot name BatchRunner needs) and a `synthesize`
    callable that converts T4 BatchResults into the T5 ReportRequest.
    Owned by Plan 19."""

    def build(
        self, *, session: Session, user_id: str
    ) -> MRAssessmentPayload: ...


class StubMRAssessmentBuilder:
    def build(
        self, *, session: Session | None, user_id: str
    ) -> MRAssessmentPayload:
        raise DepartmentPayloadBuilderNotWired(
            "MRAssessmentBuilder not provided — Plan 19 (Macro Research) will "
            "supply the real implementation."
        )


# ------------------------------------------------------------------
# ReportStore — where finished ReportRunner outputs land
# ------------------------------------------------------------------

class ReportStore(Protocol):
    """Persist a report produced by a background ReportRunner run.
    Owned by Plan 13 (report rendering pipeline)."""

    def save(
        self,
        *,
        session: Session,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str: ...  # returns report_id


class StubReportStore:
    def save(
        self,
        *,
        session: Session | None,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str:
        raise DepartmentPayloadBuilderNotWired(
            "ReportStore not provided — Plan 13 (report rendering pipeline) "
            "will supply the real implementation."
        )


# ------------------------------------------------------------------
# MRCacheStore — where T4/T5 output lands
# ------------------------------------------------------------------

class MRCacheStore(Protocol):
    """Persist T4/T5 output into mr_assessment_cache. Owned by Plan 19."""

    def save(
        self, *, session: Session, user_id: str, payload: dict[str, Any]
    ) -> str: ...  # returns cache_id


class StubMRCacheStore:
    def save(
        self, *, session: Session | None, user_id: str, payload: dict[str, Any]
    ) -> str:
        raise DepartmentPayloadBuilderNotWired(
            "MRCacheStore not provided — Plan 19 (Macro Research) will supply "
            "the real implementation."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_payloads.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/payloads.py \
    packages/server/tests/test_scheduler/test_payloads.py
git commit -m "phase-6(scheduler): payload Protocols + fail-fast stubs for MB/EU/MR"
```

---

## Task 7: `_fakes.py` — shared test doubles

**Files:**
- Create: `packages/server/tests/test_scheduler/_fakes.py`
- Create: `packages/server/tests/test_scheduler/test_fakes.py`

Collects every test double used by the executor/service/route tests in Tasks 8–14 into one file so sibling test files can `from _fakes import ...`. Per the repo's `--import-mode=importlib` constraint, there is no `tests.*` package — the `sys.path.insert(...)` in `conftest.py` (added in Task 1) makes this work.

- [ ] **Step 1: Write the failing shape test**

Create `packages/server/tests/test_scheduler/test_fakes.py`:

```python
"""Only asserts that every fake can be instantiated and its basic
behavior — the full behavioral tests live alongside each executor /
service / route test file."""
from __future__ import annotations

import asyncio

import pytest

from _fakes import (
    FakeEUPlanner,
    FakeMBBuilder,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeReportStore,
    FakeSleep,
)
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia.llm.runtime.messages import BatchItem, ReportRequest


@pytest.mark.asyncio
async def test_fake_sleep_records_durations_without_waiting() -> None:
    fs = FakeSleep()
    await fs(30)
    await fs(120)
    assert fs.calls == [30, 120]


def test_fake_mb_builder_returns_scripted_request() -> None:
    fb = FakeMBBuilder(request=ReportRequest(mode="mb", user_input="morning"))
    out = fb.build(session=None, user_id="u_1", schedule_id="s_1")
    assert out.mode == "mb"


def test_fake_eu_planner_returns_configured_targets() -> None:
    from openlia_server.scheduler.payloads import EUScanTarget

    targets = [
        EUScanTarget(
            ticker="AAPL",
            request=ReportRequest(mode="stock_update", user_input="aapl"),
        )
    ]
    fp = FakeEUPlanner(targets=targets)
    assert fp.plan(session=None, user_id="u_1", schedule_id="s_1", since=None) == targets


def test_fake_mr_builder_returns_batch_and_synth() -> None:
    from openlia.llm.runtime.messages import BatchResult

    fb = FakeMRBuilder(
        items=[BatchItem(id="i1", context={})],
        synth=ReportRequest(mode="mr_synth", user_input="t5"),
    )
    p = fb.build(session=None, user_id="u_1")
    assert p.items[0].id == "i1"
    assert p.t4_task == "t4"

    req = p.synthesize(
        [BatchResult(id="i1", ok=True, data={"x": 1}, error=None)]
    )
    assert req.mode == "mr_synth"
    assert fb.received_results[0][0].id == "i1"


def test_fake_report_store_captures_saves() -> None:
    store = FakeReportStore(next_id="r_xyz")
    rid = store.save(
        session=None, user_id="u_1", department="morning_briefing", payload={"a": 1}
    )
    assert rid == "r_xyz"
    assert store.saves[0]["department"] == "morning_briefing"


def test_fake_mr_cache_store_captures_saves() -> None:
    store = FakeMRCacheStore(next_id="c_1")
    cid = store.save(session=None, user_id="u_1", payload={"risk": "low"})
    assert cid == "c_1"
    assert store.saves[0]["user_id"] == "u_1"


@pytest.mark.asyncio
async def test_fake_report_runner_streams_scripted_events_and_returns() -> None:
    rr = FakeReportRunner(
        events=[
            ReportStart(
                report_id="r_1",
                department="morning_briefing",
                mode="mb",
                section_titles=["s1"],
            ),
            ReportComplete(report_id="r_1", schema={"title": "t", "sections": []}),
        ]
    )

    collected: list = []
    async for ev in rr.run(
        department_id="morning_briefing",
        user_id="u_1",
        request=ReportRequest(mode="mb", user_input="x"),
        cancel_token=None,
    ):
        collected.append(ev)
    assert len(collected) == 2
    assert rr.calls[0]["department_id"] == "morning_briefing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_fakes.py -v`
Expected: FAIL — `_fakes` not importable yet.

- [ ] **Step 3: Implement _fakes.py**

Create `packages/server/tests/test_scheduler/_fakes.py`:

```python
"""Shared test doubles for Plan 6 scheduler tests.

Imported by sibling test files via `from _fakes import FakeFoo`. The
`sys.path.insert(...)` in conftest.py makes this directory importable
as top-level modules under --import-mode=importlib."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from openlia.llm.runtime.events import SseEvent
from openlia.llm.runtime.messages import (
    Attachment,
    BatchItem,
    BatchResult,
    ChatMessage,
    ReportRequest,
)
from openlia_server.scheduler.payloads import (
    EUScanTarget,
    MRAssessmentPayload,
)


# ------------------------------------------------------------------
# FakeSleep — swap for asyncio.sleep in retry-backoff tests.
# ------------------------------------------------------------------

@dataclass
class FakeSleep:
    calls: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


# ------------------------------------------------------------------
# Payload builder fakes
# ------------------------------------------------------------------

@dataclass
class FakeMBBuilder:
    request: ReportRequest

    def build(
        self, *, session: Session | None, user_id: str, schedule_id: str
    ) -> ReportRequest:
        return self.request


@dataclass
class FakeEUPlanner:
    targets: list[EUScanTarget]
    raise_exc: Exception | None = None
    received: list[dict[str, Any]] = field(default_factory=list)

    def plan(
        self,
        *,
        session: Session | None,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]:
        self.received.append(
            {
                "user_id": user_id,
                "schedule_id": schedule_id,
                "since": since,
            }
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return list(self.targets)


@dataclass
class FakeMRBuilder:
    items: list[BatchItem]
    synth: ReportRequest
    t4_task: str = "t4"
    t4_schema: type = field(default_factory=lambda: _default_t4_schema())
    received_results: list[list[BatchResult]] = field(default_factory=list)

    def build(
        self, *, session: Session | None, user_id: str
    ) -> MRAssessmentPayload:
        def _synthesize(results: list[BatchResult]) -> ReportRequest:
            self.received_results.append(list(results))
            return self.synth

        return MRAssessmentPayload(
            items=list(self.items),
            t4_task=self.t4_task,
            t4_schema=self.t4_schema,
            synthesize=_synthesize,
        )


def _default_t4_schema() -> type:
    from pydantic import BaseModel

    class _T4(BaseModel):
        label: str
        score: float

    return _T4


@dataclass
class FakeReportStore:
    next_id: str = "r_stub"
    saves: list[dict[str, Any]] = field(default_factory=list)

    def save(
        self,
        *,
        session: Session | None,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str:
        self.saves.append(
            {
                "user_id": user_id,
                "department": department,
                "payload": payload,
            }
        )
        return self.next_id


@dataclass
class FakeMRCacheStore:
    next_id: str = "c_stub"
    saves: list[dict[str, Any]] = field(default_factory=list)

    def save(
        self,
        *,
        session: Session | None,
        user_id: str,
        payload: dict[str, Any],
    ) -> str:
        self.saves.append({"user_id": user_id, "payload": payload})
        return self.next_id


# ------------------------------------------------------------------
# Runner fakes
# ------------------------------------------------------------------

@dataclass
class FakeReportRunner:
    """Scripted ReportRunner. Emits `events` in order, then stops.

    If `raise_exc` is set, raises it mid-iteration after emitting any
    events accumulated before the failure marker.
    """

    events: list[SseEvent]
    raise_exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
        cancel_token: Any | None = None,
    ) -> AsyncIterator[SseEvent]:
        self.calls.append(
            {
                "department_id": department_id,
                "user_id": user_id,
                "request": request,
            }
        )
        for ev in self.events:
            if cancel_token is not None and getattr(cancel_token, "is_cancelled", False):
                return
            yield ev
        if self.raise_exc is not None:
            raise self.raise_exc


@dataclass
class FakeBatchRunner:
    results: list[BatchResult]
    raise_exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        *,
        department_id: str,
        task: str,
        items: list[BatchItem],
        schema: type,
        concurrency: int = 8,
        user_id: str | None = None,
    ) -> list[BatchResult]:
        self.calls.append(
            {
                "department_id": department_id,
                "task": task,
                "items": list(items),
                "user_id": user_id,
            }
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return list(self.results)


# ------------------------------------------------------------------
# A trivial chat-message fake in case a test needs one (ChatRunner
# isn't used by the scheduler, but a ChatMessage value may be needed
# to exercise Attachment passthrough in future tasks).
# ------------------------------------------------------------------

def make_chat_message(text: str = "hi") -> ChatMessage:
    return ChatMessage(role="user", content=text, attachments=[])


def make_attachment() -> Attachment:
    return Attachment(kind="image", url="u", mime_type="image/png")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_fakes.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/tests/test_scheduler/_fakes.py \
    packages/server/tests/test_scheduler/test_fakes.py
git commit -m "phase-6(scheduler): shared test doubles (runners + payload builders + sleep)"
```

---

## Task 8: `executors/base.py` — BaseExecutor (job lifecycle + retry + notifications)

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/__init__.py`
- Create: `packages/server/src/openlia_server/scheduler/executors/base.py`
- Create: `packages/server/tests/test_scheduler/test_base_executor.py`

The base executor runs the full lifecycle of a single job: open a `job_runs` row, call the subclass's `_do_work`, retry on transient errors with exponential backoff (30s → 120s → 480s), mark completion / failure / cancellation, and insert notifications (success notifications from the subclass's outcome; a `job_failed` notification generated by the base when retries are exhausted).

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_base_executor.py`:

```python
from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest
from sqlalchemy.orm import Session

from _fakes import FakeSleep
from openlia.llm.exceptions import (
    AuthError,
    RateLimitError,
    TierNotConfiguredError,
)
from openlia.llm.runtime.cancellation import CancellationToken
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.base import (
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
)
from openlia_server.scheduler.registry import (
    JobStatus,
    JobType,
    NotificationType,
)


class _ScriptedExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MB_BRIEFING

    def __init__(self, *, script, **kw):
        super().__init__(**kw)
        self._script = list(script)
        self.calls: list[dict] = []

    async def _do_work(self, *, user_id, schedule_id, run_id, cancel_token):
        self.calls.append(
            {"user_id": user_id, "schedule_id": schedule_id, "run_id": run_id}
        )
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _make_user(session: Session, uid: str = "u_1") -> None:
    session.add(
        User(
            id=uid,
            email=f"{uid}@e.com",
            display_name=f"u-{uid}",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.commit()


def _success() -> JobOutcome:
    return JobOutcome(
        result_summary={"report_id": "r_1"},
        notifications=[
            NotificationSpec(
                type=NotificationType.REPORT_READY,
                department="morning_briefing",
                message="ok",
            )
        ],
    )


@pytest.mark.asyncio
async def test_successful_first_try_writes_completed_row_and_notification(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[_success()],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 1
        assert row.result_summary == '{"report_id": "r_1"}'
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].job_run_id == run_id
    assert sleep.calls == []


@pytest.mark.asyncio
async def test_transient_then_success_bumps_attempt_and_backs_off(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[
            RateLimitError("429"),
            RateLimitError("429 again"),
            _success(),
        ],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 3
    assert sleep.calls == [30, 120]


@pytest.mark.asyncio
async def test_non_transient_error_fails_immediately_without_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[AuthError("bad key")],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert "AuthError" in row.error_message
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "job_failed"
        assert notifs[0].department == "morning_briefing"
    assert sleep.calls == []


@pytest.mark.asyncio
async def test_tier_not_configured_fails_and_inserts_job_failed_notification(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    ex = _ScriptedExecutor(
        script=[TierNotConfiguredError("thinking")],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        notifs = s.query(UserNotification).all()
        assert notifs[0].type == "job_failed"
        assert "TierNotConfigured" in notifs[0].message


@pytest.mark.asyncio
async def test_transient_failure_exhausts_retries_then_fails(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[RateLimitError(str(i)) for i in range(4)],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert row.attempt == 4
    assert sleep.calls == [30, 120, 480]


@pytest.mark.asyncio
async def test_cancel_before_start_short_circuits(session_factory) -> None:
    with session_factory() as s:
        _make_user(s)
    tok = CancellationToken()
    tok.cancel()
    ex = _ScriptedExecutor(
        script=[_success()],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1", cancel_token=tok)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.CANCELLED.value
        assert ex.calls == []


@pytest.mark.asyncio
async def test_maintenance_style_skips_notifications_when_user_id_is_none(
    session_factory,
) -> None:
    ex = _ScriptedExecutor(
        script=[
            JobOutcome(
                result_summary={"pruned_sessions": 2}, notifications=[]
            )
        ],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    # Override job_type for this test: maintenance-style job uses SYSTEM_MAINTENANCE
    ex.job_type = JobType.SYSTEM_MAINTENANCE  # type: ignore[misc]
    run_id = await ex.execute(user_id=None, schedule_id=None)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.user_id is None
        assert s.query(UserNotification).count() == 0


@pytest.mark.asyncio
async def test_cancelled_error_raised_by_work_records_cancelled_and_reraises(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    ex = _ScriptedExecutor(
        script=[asyncio.CancelledError()],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    with pytest.raises(asyncio.CancelledError):
        await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.query(JobRun).one()
        assert row.status == JobStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_retry_honors_cancel_token_between_attempts(session_factory) -> None:
    with session_factory() as s:
        _make_user(s)
    tok = CancellationToken()
    sleep_calls: list[float] = []

    async def cancelling_sleep(_: float) -> None:
        sleep_calls.append(_)
        tok.cancel()

    ex = _ScriptedExecutor(
        script=[RateLimitError("1"), _success()],
        session_factory=session_factory,
        sleep=cancelling_sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1", cancel_token=tok)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.CANCELLED.value
    assert sleep_calls == [30]


@pytest.mark.asyncio
async def test_retry_of_sets_pointer(session_factory) -> None:
    with session_factory() as s:
        _make_user(s)
    ex_first = _ScriptedExecutor(
        script=[AuthError("bad key")],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    failed_id = await ex_first.execute(user_id="u_1", schedule_id="s_1")

    ex_retry = _ScriptedExecutor(
        script=[_success()],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    retry_id = await ex_retry.execute(
        user_id="u_1", schedule_id="s_1", retry_of=failed_id
    )

    with session_factory() as s:
        retry_row = s.get(JobRun, retry_id)
        assert retry_row.retry_of == failed_id
        assert retry_row.status == JobStatus.COMPLETED.value
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_base_executor.py -v`
Expected: FAIL — base executor module missing.

- [ ] **Step 3: Create the executors package init**

Create `packages/server/src/openlia_server/scheduler/executors/__init__.py`:

```python
"""Scheduler executors. One per JobType."""
from __future__ import annotations
```

- [ ] **Step 4: Implement `executors/base.py`**

Create `packages/server/src/openlia_server/scheduler/executors/base.py`:

```python
"""Common job lifecycle: open a job_runs row, run the subclass's _do_work
with retry-and-backoff, close the row, insert notifications."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from sqlalchemy.orm import Session

from openlia.llm.exceptions import LLMProviderError, is_transient
from openlia.llm.runtime.cancellation import CancellationToken
from openlia_server.scheduler.registry import (
    JobType,
    NotificationType,
    department_for_job_type,
)
from openlia_server.scheduler.services import jobs as jobs_svc
from openlia_server.scheduler.services import notifications as notif_svc


DEFAULT_BACKOFF_SECONDS: tuple[int, ...] = (30, 120, 480)


@dataclass(frozen=True)
class NotificationSpec:
    type: NotificationType
    department: str
    message: str


@dataclass(frozen=True)
class JobOutcome:
    result_summary: dict[str, Any]
    notifications: list[NotificationSpec]


SessionFactory = Callable[[], Session]
AsyncSleep = Callable[[float], Awaitable[None]]


class BaseExecutor:
    """Abstract job executor. Subclasses set `job_type` and implement
    `_do_work`. Safe to instantiate directly only in tests."""

    job_type: ClassVar[JobType]

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        sleep: AsyncSleep | None = None,
        backoff_seconds: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._backoff_seconds = backoff_seconds

    async def execute(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        cancel_token: CancellationToken | None = None,
        retry_of: str | None = None,
    ) -> str:
        run_id = self._start_run(
            user_id=user_id, schedule_id=schedule_id, retry_of=retry_of
        )

        if cancel_token is not None and cancel_token.is_cancelled:
            self._cancel(run_id, "Cancelled before execution")
            return run_id

        attempts_remaining = len(self._backoff_seconds)
        last_error_msg: str | None = None

        for attempt_index in range(attempts_remaining + 1):
            try:
                outcome = await self._do_work(
                    user_id=user_id,
                    schedule_id=schedule_id,
                    run_id=run_id,
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                self._cancel(run_id, "Job cancelled")
                raise
            except LLMProviderError as exc:
                last_error_msg = f"{type(exc).__name__}: {exc!s}"
                if is_transient(exc) and attempt_index < attempts_remaining:
                    self._bump_attempt(run_id, last_error_msg)
                    await self._sleep(self._backoff_seconds[attempt_index])
                    if cancel_token is not None and cancel_token.is_cancelled:
                        self._cancel(run_id, "Cancelled between retries")
                        return run_id
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                last_error_msg = f"{type(exc).__name__}: {exc!s}"
                break
            else:
                self._complete(run_id=run_id, user_id=user_id, outcome=outcome)
                return run_id

        assert last_error_msg is not None
        self._fail(run_id=run_id, user_id=user_id, error_message=last_error_msg)
        return run_id

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        raise NotImplementedError

    # ---- internal session-per-step helpers -------------------------

    def _start_run(
        self, *, user_id: str | None, schedule_id: str | None, retry_of: str | None
    ) -> str:
        with self._session_factory() as session:
            run_id = jobs_svc.start_run(
                session,
                user_id=user_id,
                job_type=self.job_type,
                schedule_id=schedule_id,
                retry_of=retry_of,
            )
            session.commit()
            return run_id

    def _bump_attempt(self, run_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            jobs_svc.bump_attempt(session, run_id, error_message=error_message)
            session.commit()

    def _cancel(self, run_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            jobs_svc.mark_cancelled(session, run_id, error_message=error_message)
            session.commit()

    def _complete(
        self, *, run_id: str, user_id: str | None, outcome: JobOutcome
    ) -> None:
        with self._session_factory() as session:
            jobs_svc.mark_completed(
                session,
                run_id,
                result_summary=json.dumps(outcome.result_summary),
            )
            if user_id is not None:
                for n in outcome.notifications:
                    notif_svc.insert(
                        session,
                        user_id=user_id,
                        type=n.type,
                        department=n.department,
                        message=n.message,
                        job_run_id=run_id,
                    )
            session.commit()

    def _fail(
        self, *, run_id: str, user_id: str | None, error_message: str
    ) -> None:
        with self._session_factory() as session:
            jobs_svc.mark_failed(session, run_id, error_message=error_message)
            if user_id is not None:
                notif_svc.insert(
                    session,
                    user_id=user_id,
                    type=NotificationType.JOB_FAILED,
                    department=department_for_job_type(self.job_type),
                    message=error_message,
                    job_run_id=run_id,
                )
            session.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_base_executor.py -v`
Expected: 10 tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/executors/__init__.py \
    packages/server/src/openlia_server/scheduler/executors/base.py \
    packages/server/tests/test_scheduler/test_base_executor.py
git commit -m "phase-6(scheduler): BaseExecutor — job lifecycle + retry backoff + notifications"
```

---

## Task 9: `executors/maintenance.py` — nightly pruning sweep

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/maintenance.py`
- Create: `packages/server/tests/test_scheduler/test_maintenance_executor.py`

Maintenance runs the DB-only pruning sweep defined in `background-task-scheduling-design.md` and the additional `job_runs` pruning rule from Plan 1B. System-scoped (user_id=None), no notifications. Also exports a `run_maintenance_once(session)` free function so Plan 7's `openlia maintenance` CLI can invoke the same sweep synchronously.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_maintenance_executor.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from _fakes import FakeSleep
from openlia_server.db.models.auth import PasswordResetRequest, Session as AuthSession, User
from openlia_server.db.models.dashboard import (
    MrAssessmentCache,
    RsSnapshot,
)
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.maintenance import (
    MaintenanceExecutor,
    run_maintenance_once,
)
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.scheduler.services import jobs as jobs_svc


def _seed(session: Session) -> dict[str, list[str]]:
    """Insert expired + fresh rows in every target table. Returns a
    dict mapping table -> list of ids expected to survive the sweep."""
    now = datetime.now(timezone.utc)

    user = User(
        id="u_1",
        email="u@e.com",
        display_name="u",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    session.add(user)
    session.flush()

    # sessions: expired > 7d ago, fresh. token_hash must be unique.
    s_old = AuthSession(
        id="s_old", user_id="u_1", token_hash="h_old",
        created_at=now - timedelta(days=9),
        last_seen_at=now - timedelta(days=9),
        expires_at=now - timedelta(days=8),
    )
    s_new = AuthSession(
        id="s_new", user_id="u_1", token_hash="h_new",
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=1),
    )
    session.add_all([s_old, s_new])

    # password_reset_requests: approved with expires_at<now → flip to expired;
    # any row with requested_at older than 90d → delete.
    r_flip = PasswordResetRequest(
        id="r_flip", user_id="u_1", status="approved",
        requested_at=now - timedelta(days=2),
        expires_at=now - timedelta(hours=1),
    )
    r_old = PasswordResetRequest(
        id="r_old", user_id="u_1", status="consumed",
        requested_at=now - timedelta(days=100),
        expires_at=now - timedelta(days=99),
    )
    r_live = PasswordResetRequest(
        id="r_live", user_id="u_1", status="pending",
        requested_at=now, expires_at=now + timedelta(days=1),
    )
    session.add_all([r_flip, r_old, r_live])

    # mr_assessment_cache: expired > 30d ago → delete
    c_old = MrAssessmentCache(
        id="c_old", dashboard="debt_cycle", assessment_type="t4",
        input_hash="h1", result={}, model_ref="m", token_usage=None,
        generated_at=now - timedelta(days=40),
        expires_at=now - timedelta(days=31),
    )
    c_new = MrAssessmentCache(
        id="c_new", dashboard="debt_cycle", assessment_type="t4",
        input_hash="h2", result={}, model_ref="m", token_usage=None,
        generated_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=6),
    )
    session.add_all([c_old, c_new])

    # rs_snapshots: captured > 90d ago → delete. snapshot_data / source_breakdown
    # are JSON columns per Plan 1B — pass dicts, not strings.
    rs_old = RsSnapshot(
        id="rs_old", ticker="AAPL", snapshot_data={},
        source_breakdown={}, captured_at=now - timedelta(days=100),
    )
    rs_new = RsSnapshot(
        id="rs_new", ticker="AAPL", snapshot_data={},
        source_breakdown={}, captured_at=now - timedelta(days=10),
    )
    session.add_all([rs_old, rs_new])

    # user_notifications: created > 30d ago → delete
    n_old = UserNotification(
        id="n_old", user_id="u_1", type="report_ready",
        department="morning_briefing", message="m",
        job_run_id=None, created_at=now - timedelta(days=40), read_at=None,
    )
    n_new = UserNotification(
        id="n_new", user_id="u_1", type="report_ready",
        department="morning_briefing", message="m",
        job_run_id=None, created_at=now - timedelta(days=1), read_at=None,
    )
    session.add_all([n_old, n_new])

    # job_runs: completed/cancelled > 90d ago → delete; failed retained
    j_old_ok = JobRun(
        id="j_old_ok", user_id="u_1", job_type="mb_briefing",
        schedule_id="s", status=JobStatus.COMPLETED.value,
        started_at=now - timedelta(days=120),
        completed_at=now - timedelta(days=120), attempt=1,
    )
    j_old_cancel = JobRun(
        id="j_old_cancel", user_id="u_1", job_type="mb_briefing",
        schedule_id="s", status=JobStatus.CANCELLED.value,
        started_at=now - timedelta(days=95),
        completed_at=now - timedelta(days=95), attempt=1,
    )
    j_old_failed = JobRun(
        id="j_old_failed", user_id="u_1", job_type="mb_briefing",
        schedule_id="s", status=JobStatus.FAILED.value,
        started_at=now - timedelta(days=200),
        completed_at=now - timedelta(days=200),
        error_message="x", attempt=1,
    )
    j_new_ok = JobRun(
        id="j_new_ok", user_id="u_1", job_type="mb_briefing",
        schedule_id="s", status=JobStatus.COMPLETED.value,
        started_at=now - timedelta(days=2),
        completed_at=now - timedelta(days=2), attempt=1,
    )
    session.add_all([j_old_ok, j_old_cancel, j_old_failed, j_new_ok])

    session.commit()

    return {
        "sessions": ["s_new"],
        "password_reset_requests": ["r_flip", "r_live"],
        "mr_assessment_cache": ["c_new"],
        "rs_snapshots": ["rs_new"],
        "user_notifications": ["n_new"],
        "job_runs": ["j_old_failed", "j_new_ok"],
    }


def test_run_maintenance_once_prunes_every_target(db_session: Session) -> None:
    expected = _seed(db_session)

    summary = run_maintenance_once(db_session)
    db_session.commit()

    # Summary counts
    assert summary["sessions_deleted"] == 1
    assert summary["password_resets_expired"] == 1
    assert summary["password_resets_deleted"] == 1
    assert summary["mr_cache_deleted"] == 1
    assert summary["rs_snapshots_deleted"] == 1
    assert summary["notifications_deleted"] == 1
    assert summary["job_runs_deleted"] == 2

    # Table contents
    surviving_sessions = {
        s.id for s in db_session.query(AuthSession).all()
    }
    assert surviving_sessions == set(expected["sessions"])

    prrs = {r.id: r.status for r in db_session.query(PasswordResetRequest).all()}
    assert prrs == {"r_flip": "expired", "r_live": "pending"}

    caches = {c.id for c in db_session.query(MrAssessmentCache).all()}
    assert caches == set(expected["mr_assessment_cache"])

    snaps = {r.id for r in db_session.query(RsSnapshot).all()}
    assert snaps == set(expected["rs_snapshots"])

    notifs = {n.id for n in db_session.query(UserNotification).all()}
    assert notifs == set(expected["user_notifications"])

    runs = {j.id for j in db_session.query(JobRun).all()}
    assert runs == set(expected["job_runs"])


@pytest.mark.asyncio
async def test_maintenance_executor_writes_completed_job_run(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    ex = MaintenanceExecutor(session_factory=session_factory, sleep=FakeSleep())
    run_id = await ex.execute(user_id=None, schedule_id=None)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row is not None
        assert row.status == JobStatus.COMPLETED.value
        assert row.job_type == JobType.SYSTEM_MAINTENANCE.value
        # Summary JSON-serialized into result_summary
        import json
        summary = json.loads(row.result_summary)
        assert summary["sessions_deleted"] == 1
        assert s.query(UserNotification).filter_by(job_run_id=run_id).count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_maintenance_executor.py -v`
Expected: FAIL — maintenance module missing.

- [ ] **Step 3: Implement `executors/maintenance.py`**

Create `packages/server/src/openlia_server/scheduler/executors/maintenance.py`:

```python
"""System maintenance job: the nightly pruning sweep. DB-only, no LLM,
no notifications. Also exposes `run_maintenance_once(session)` as a
module-level function so Plan 7's `openlia maintenance` CLI can invoke
the exact same sweep synchronously."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from openlia.llm.runtime.cancellation import CancellationToken
from openlia_server.db.models.auth import PasswordResetRequest, Session as AuthSession
from openlia_server.db.models.dashboard import MrAssessmentCache, RsSnapshot
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.base import BaseExecutor, JobOutcome
from openlia_server.scheduler.registry import JobStatus, JobType


SESSIONS_RETENTION_DAYS = 7
PASSWORD_RESET_RETENTION_DAYS = 90
MR_CACHE_POST_EXPIRY_DAYS = 30
RS_SNAPSHOT_RETENTION_DAYS = 90
NOTIFICATION_RETENTION_DAYS = 30
JOB_RUN_RETENTION_DAYS = 90


def run_maintenance_once(session: Session) -> dict[str, int]:
    """Run every pruning rule once. Returns a counts dict suitable for
    serializing into job_runs.result_summary."""
    now = datetime.now(timezone.utc)

    sessions_deleted = session.execute(
        delete(AuthSession).where(
            AuthSession.expires_at < now - timedelta(days=SESSIONS_RETENTION_DAYS)
        )
    ).rowcount or 0

    password_resets_expired = session.execute(
        update(PasswordResetRequest)
        .where(
            PasswordResetRequest.status == "approved",
            PasswordResetRequest.expires_at < now,
        )
        .values(status="expired")
        .execution_options(synchronize_session="fetch")
    ).rowcount or 0

    password_resets_deleted = session.execute(
        delete(PasswordResetRequest).where(
            PasswordResetRequest.requested_at
            < now - timedelta(days=PASSWORD_RESET_RETENTION_DAYS)
        )
    ).rowcount or 0

    mr_cache_deleted = session.execute(
        delete(MrAssessmentCache).where(
            MrAssessmentCache.expires_at
            < now - timedelta(days=MR_CACHE_POST_EXPIRY_DAYS)
        )
    ).rowcount or 0

    rs_snapshots_deleted = session.execute(
        delete(RsSnapshot).where(
            RsSnapshot.captured_at
            < now - timedelta(days=RS_SNAPSHOT_RETENTION_DAYS)
        )
    ).rowcount or 0

    notifications_deleted = session.execute(
        delete(UserNotification).where(
            UserNotification.created_at
            < now - timedelta(days=NOTIFICATION_RETENTION_DAYS)
        )
    ).rowcount or 0

    job_runs_deleted = session.execute(
        delete(JobRun).where(
            JobRun.status.in_(
                [JobStatus.COMPLETED.value, JobStatus.CANCELLED.value]
            ),
            JobRun.started_at < now - timedelta(days=JOB_RUN_RETENTION_DAYS),
        )
    ).rowcount or 0

    return {
        "sessions_deleted": int(sessions_deleted),
        "password_resets_expired": int(password_resets_expired),
        "password_resets_deleted": int(password_resets_deleted),
        "mr_cache_deleted": int(mr_cache_deleted),
        "rs_snapshots_deleted": int(rs_snapshots_deleted),
        "notifications_deleted": int(notifications_deleted),
        "job_runs_deleted": int(job_runs_deleted),
    }


class MaintenanceExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.SYSTEM_MAINTENANCE

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        with self._session_factory() as session:
            summary = run_maintenance_once(session)
            session.commit()
        return JobOutcome(result_summary=summary, notifications=[])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_maintenance_executor.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/executors/maintenance.py \
    packages/server/tests/test_scheduler/test_maintenance_executor.py
git commit -m "phase-6(scheduler): MaintenanceExecutor + run_maintenance_once()"
```

---

## Task 10: `executors/mb.py` — MBBriefingExecutor

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/mb.py`
- Create: `packages/server/tests/test_scheduler/test_mb_executor.py`

The MB executor asks the injected `MBRequestBuilder` for a `ReportRequest`, streams it through `ReportRunner`, saves the resulting report via `ReportStore`, updates the `mb_schedules.last_run_at` column, and returns one `report_ready` notification.

Because `ReportRunner` converts provider errors into a `ReportError` SSE event and returns (see Plan 5), the executor has to translate those terminal events back into the original typed exception so `BaseExecutor`'s retry logic can classify them. A `ReportError` with an unknown `error_class` becomes a non-transient `RuntimeError`.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_mb_executor.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from _fakes import FakeMBBuilder, FakeReportRunner, FakeReportStore, FakeSleep
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportStart,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun, MbSchedule, UserNotification
from openlia_server.scheduler.executors.mb import MBBriefingExecutor
from openlia_server.scheduler.registry import JobStatus


def _seed(session: Session) -> None:
    session.add(
        User(
            id="u_1", email="u@e.com", display_name="u",
            password_hash="h", is_admin=False, is_disabled=False,
        )
    )
    session.add(
        MbSchedule(
            id="sch_mb", user_id="u_1",
            time="07:00", timezone="UTC",
            days_of_week='["mon","tue","wed","thu","fri"]',
            label="Pre-Market", is_enabled=True,
            created_at=datetime.now(timezone.utc), last_run_at=None,
        )
    )
    session.commit()


def _events_for_success(report_id: str = "r_1") -> list:
    return [
        ReportStart(
            report_id=report_id, department="morning_briefing",
            mode="mb", section_titles=["Overnight"],
        ),
        ReportComplete(
            report_id=report_id,
            schema={"title": "Briefing", "sections": [{"id": "s1", "body": "x"}]},
        ),
    ]


@pytest.mark.asyncio
async def test_mb_happy_path_saves_report_and_updates_last_run(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMBBuilder(
        request=ReportRequest(mode="morning_briefing", user_input="go")
    )
    runner = FakeReportRunner(events=_events_for_success())
    store = FakeReportStore(next_id="r_final")

    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mb_builder=builder,
        report_runner=runner,
        report_store=store,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        import json
        assert json.loads(row.result_summary) == {"report_id": "r_final"}

        sched = s.get(MbSchedule, "sch_mb")
        assert sched.last_run_at is not None

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].department == "morning_briefing"
        assert "Pre-Market" in notifs[0].message

    assert runner.calls[0]["department_id"] == "morning_briefing"
    assert store.saves[0]["department"] == "morning_briefing"


@pytest.mark.asyncio
async def test_mb_report_error_with_transient_class_triggers_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMBBuilder(
        request=ReportRequest(mode="morning_briefing", user_input="go")
    )

    class TwoPhaseRunner:
        """First call emits ReportError(RateLimitError), second succeeds."""

        def __init__(self) -> None:
            self.phase = 0

        async def run(self, **_):
            self.phase += 1
            if self.phase == 1:
                yield ReportStart(
                    report_id="r_a", department="morning_briefing",
                    mode="mb", section_titles=[],
                )
                yield ReportError(
                    report_id="r_a",
                    error_class="RateLimitError",
                    message="429",
                )
                return
            for ev in _events_for_success("r_b"):
                yield ev

    sleep = FakeSleep()
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=sleep,
        mb_builder=builder,
        report_runner=TwoPhaseRunner(),
        report_store=FakeReportStore(next_id="r_final"),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 2
    assert sleep.calls == [30]


@pytest.mark.asyncio
async def test_mb_report_error_non_transient_fails_without_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    runner = FakeReportRunner(
        events=[
            ReportStart(
                report_id="r_1", department="morning_briefing",
                mode="mb", section_titles=[],
            ),
            ReportError(
                report_id="r_1",
                error_class="TierNotConfiguredError",
                message="thinking",
            ),
        ]
    )
    sleep = FakeSleep()
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=sleep,
        mb_builder=FakeMBBuilder(
            request=ReportRequest(mode="morning_briefing", user_input="go")
        ),
        report_runner=runner,
        report_store=FakeReportStore(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert "TierNotConfigured" in row.error_message
        notifs = s.query(UserNotification).all()
        assert notifs[0].type == "job_failed"
    assert sleep.calls == []


@pytest.mark.asyncio
async def test_mb_runner_returns_no_terminal_event_is_non_transient_failure(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    runner = FakeReportRunner(
        events=[
            ReportStart(
                report_id="r_1", department="morning_briefing",
                mode="mb", section_titles=[],
            ),
        ]
    )
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mb_builder=FakeMBBuilder(
            request=ReportRequest(mode="morning_briefing", user_input="go")
        ),
        report_runner=runner,
        report_store=FakeReportStore(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert "ReportComplete" in row.error_message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_mb_executor.py -v`
Expected: FAIL — `executors.mb` missing.

- [ ] **Step 3: Implement `executors/mb.py`**

Create `packages/server/src/openlia_server/scheduler/executors/mb.py`:

```python
"""Morning Briefing executor. Wires an MBRequestBuilder → ReportRunner →
ReportStore pipeline and produces one `report_ready` notification per
successful run."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

from openlia.llm import exceptions as llm_exceptions
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
)
from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.payloads import MBRequestBuilder, ReportStore
from openlia_server.scheduler.registry import (
    JobType,
    NotificationType,
)


DEPARTMENT = "morning_briefing"


def _raise_from_report_error(event: ReportError) -> None:
    """Map error_class back to the original LLMProviderError (if known)
    so BaseExecutor's is_transient() classification still works."""
    exc_cls = getattr(llm_exceptions, event.error_class, None)
    if exc_cls is not None and issubclass(exc_cls, LLMProviderError):
        raise exc_cls(event.message)
    raise RuntimeError(f"{event.error_class}: {event.message}")


class MBBriefingExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MB_BRIEFING

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        mb_builder: MBRequestBuilder,
        report_runner,
        report_store: ReportStore,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._mb_builder = mb_builder
        self._report_runner = report_runner
        self._report_store = report_store

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        assert user_id is not None
        assert schedule_id is not None

        with self._session_factory() as session:
            request = self._mb_builder.build(
                session=session, user_id=user_id, schedule_id=schedule_id
            )

        report_payload: dict | None = None
        async for event in self._report_runner.run(
            department_id=DEPARTMENT,
            user_id=user_id,
            request=request,
            cancel_token=cancel_token,
        ):
            if isinstance(event, ReportError):
                _raise_from_report_error(event)
            if isinstance(event, ReportComplete):
                report_payload = event.schema

        if report_payload is None:
            raise RuntimeError(
                "ReportRunner returned without a ReportComplete event"
            )

        with self._session_factory() as session:
            report_id = self._report_store.save(
                session=session,
                user_id=user_id,
                department=DEPARTMENT,
                payload=report_payload,
            )
            schedule = session.get(MbSchedule, schedule_id)
            label = schedule.label if schedule is not None else None
            time_label = schedule.time if schedule is not None else "scheduled"
            if schedule is not None:
                schedule.last_run_at = datetime.now(timezone.utc)
            session.commit()

        display = label if label else time_label
        return JobOutcome(
            result_summary={"report_id": report_id},
            notifications=[
                NotificationSpec(
                    type=NotificationType.REPORT_READY,
                    department=DEPARTMENT,
                    message=f"Your {display} briefing is ready.",
                )
            ],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_mb_executor.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/executors/mb.py \
    packages/server/tests/test_scheduler/test_mb_executor.py
git commit -m "phase-6(scheduler): MBBriefingExecutor (builder→runner→store→notify)"
```

---

## Task 11: `executors/eu.py` — EUScanExecutor

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/eu.py`
- Create: `packages/server/tests/test_scheduler/test_eu_executor.py`

EU differs from MB in two ways:

1. The planner returns a list of `EUScanTarget(ticker, request)` tuples — one per company whose earnings have been released since `last_run_at`. The executor runs `ReportRunner` sequentially for each target (the spec explicitly says "sequentially, one ticker at a time") and produces **one notification per successful report**.
2. If the planner returns an empty list (no new earnings), the run completes cleanly with zero reports and zero notifications.
3. If any single ticker fails, the whole scan fails — retry will re-scan all tickers (acceptable for v1 per the spec's open-question note on EU scan efficiency).

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_eu_executor.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from _fakes import (
    FakeEUPlanner,
    FakeReportRunner,
    FakeReportStore,
    FakeSleep,
)
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportStart,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import (
    EuSchedule,
    JobRun,
    UserNotification,
)
from openlia_server.scheduler.executors.eu import EUScanExecutor
from openlia_server.scheduler.payloads import EUScanTarget
from openlia_server.scheduler.registry import JobStatus


def _seed(session: Session) -> None:
    session.add(
        User(
            id="u_1", email="u@e.com", display_name="u",
            password_hash="h", is_admin=False, is_disabled=False,
        )
    )
    session.add(
        EuSchedule(
            id="sch_eu", user_id="u_1",
            time="16:30", timezone="America/New_York",
            days_of_week='["mon","tue","wed","thu","fri"]',
            label="Post-Market", is_enabled=True,
            created_at=datetime.now(timezone.utc), last_run_at=None,
        )
    )
    session.commit()


def _ok_events(report_id: str, ticker: str) -> list:
    return [
        ReportStart(
            report_id=report_id, department="earnings_update",
            mode="stock_update", section_titles=["Scorecard"],
        ),
        ReportComplete(
            report_id=report_id,
            schema={"title": f"{ticker} earnings", "sections": []},
        ),
    ]


class _ScriptedMultiRunner:
    """ReportRunner fake that yields different event streams per call."""

    def __init__(self, streams: list[list]) -> None:
        self._streams = list(streams)
        self.calls: list[dict] = []

    async def run(self, *, department_id, user_id, request, cancel_token=None):
        self.calls.append(
            {"department_id": department_id, "user_id": user_id, "request": request}
        )
        stream = self._streams.pop(0)
        for ev in stream:
            yield ev


@pytest.mark.asyncio
async def test_eu_scan_no_new_earnings_completes_with_zero_reports(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    planner = FakeEUPlanner(targets=[])
    runner = _ScriptedMultiRunner(streams=[])
    store = FakeReportStore()

    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        eu_planner=planner,
        report_runner=runner,
        report_store=store,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_eu")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        summary = json.loads(row.result_summary)
        assert summary == {"reports_generated": 0, "report_ids": []}
        assert s.query(UserNotification).count() == 0
        assert s.get(EuSchedule, "sch_eu").last_run_at is not None


@pytest.mark.asyncio
async def test_eu_scan_runs_each_target_sequentially_and_notifies_each(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    targets = [
        EUScanTarget(
            ticker="AAPL",
            request=ReportRequest(mode="stock_update", user_input="AAPL"),
        ),
        EUScanTarget(
            ticker="MSFT",
            request=ReportRequest(mode="stock_update", user_input="MSFT"),
        ),
        EUScanTarget(
            ticker="NVDA",
            request=ReportRequest(mode="stock_update", user_input="NVDA"),
        ),
    ]
    runner = _ScriptedMultiRunner(
        streams=[
            _ok_events("r_aapl", "AAPL"),
            _ok_events("r_msft", "MSFT"),
            _ok_events("r_nvda", "NVDA"),
        ]
    )
    store = FakeReportStore()
    # Return distinct IDs per save.
    saved_ids: list[str] = []

    def _save(*, session, user_id, department, payload):
        saved_ids.append(f"rep_{len(saved_ids)+1}")
        store.saves.append(
            {
                "user_id": user_id,
                "department": department,
                "payload": payload,
            }
        )
        return saved_ids[-1]

    store.save = _save  # type: ignore[method-assign]

    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        eu_planner=FakeEUPlanner(targets=targets),
        report_runner=runner,
        report_store=store,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_eu")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        summary = json.loads(row.result_summary)
        assert summary == {
            "reports_generated": 3,
            "report_ids": ["rep_1", "rep_2", "rep_3"],
        }

        notifs = sorted(
            s.query(UserNotification).all(), key=lambda n: n.message
        )
        assert len(notifs) == 3
        messages = [n.message for n in notifs]
        assert "AAPL" in messages[0]
        assert "MSFT" in messages[1]
        assert "NVDA" in messages[2]
        for n in notifs:
            assert n.type == "report_ready"
            assert n.department == "earnings_update"

    # The runner must be called once per target, in order.
    tickers_called = [c["request"].user_input for c in runner.calls]
    assert tickers_called == ["AAPL", "MSFT", "NVDA"]


@pytest.mark.asyncio
async def test_eu_planner_receives_last_run_at_as_since(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)
        previous = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
        s.get(EuSchedule, "sch_eu").last_run_at = previous
        s.commit()

    planner = FakeEUPlanner(targets=[])
    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        eu_planner=planner,
        report_runner=_ScriptedMultiRunner(streams=[]),
        report_store=FakeReportStore(),
    )
    await ex.execute(user_id="u_1", schedule_id="sch_eu")
    assert planner.received[0]["since"] is not None
    assert planner.received[0]["since"].hour == 12


@pytest.mark.asyncio
async def test_eu_mid_scan_transient_error_triggers_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    targets = [
        EUScanTarget(
            ticker="AAPL",
            request=ReportRequest(mode="stock_update", user_input="AAPL"),
        ),
        EUScanTarget(
            ticker="MSFT",
            request=ReportRequest(mode="stock_update", user_input="MSFT"),
        ),
    ]

    # First attempt: AAPL succeeds, MSFT hits a RateLimitError.
    # Second attempt: both succeed.
    first_attempt = [
        _ok_events("r_aapl_1", "AAPL"),
        [
            ReportStart(
                report_id="r_msft_1", department="earnings_update",
                mode="stock_update", section_titles=[],
            ),
            ReportError(
                report_id="r_msft_1",
                error_class="RateLimitError",
                message="429",
            ),
        ],
    ]
    second_attempt = [
        _ok_events("r_aapl_2", "AAPL"),
        _ok_events("r_msft_2", "MSFT"),
    ]
    runner = _ScriptedMultiRunner(streams=first_attempt + second_attempt)
    sleep = FakeSleep()

    ex = EUScanExecutor(
        session_factory=session_factory,
        sleep=sleep,
        eu_planner=FakeEUPlanner(targets=targets),
        report_runner=runner,
        report_store=FakeReportStore(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_eu")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 2
    assert sleep.calls == [30]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_executor.py -v`
Expected: FAIL — `executors.eu` missing.

- [ ] **Step 3: Implement `executors/eu.py`**

Create `packages/server/src/openlia_server/scheduler/executors/eu.py`:

```python
"""Earnings Update executor. Runs ReportRunner sequentially for every
ticker the planner returns; one notification per completed report."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ReportComplete, ReportError
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.executors.mb import _raise_from_report_error
from openlia_server.scheduler.payloads import EUScanPlanner, ReportStore
from openlia_server.scheduler.registry import JobType, NotificationType


DEPARTMENT = "earnings_update"


class EUScanExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.EU_SCAN

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        eu_planner: EUScanPlanner,
        report_runner,
        report_store: ReportStore,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._eu_planner = eu_planner
        self._report_runner = report_runner
        self._report_store = report_store

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        assert user_id is not None
        assert schedule_id is not None

        # Read last_run_at + resolve targets in one session.
        with self._session_factory() as session:
            schedule = session.get(EuSchedule, schedule_id)
            since = schedule.last_run_at if schedule is not None else None
            targets = self._eu_planner.plan(
                session=session,
                user_id=user_id,
                schedule_id=schedule_id,
                since=since,
            )

        report_ids: list[str] = []
        notifications: list[NotificationSpec] = []

        for target in targets:
            payload: dict | None = None
            async for event in self._report_runner.run(
                department_id=DEPARTMENT,
                user_id=user_id,
                request=target.request,
                cancel_token=cancel_token,
            ):
                if isinstance(event, ReportError):
                    _raise_from_report_error(event)
                if isinstance(event, ReportComplete):
                    payload = event.schema

            if payload is None:
                raise RuntimeError(
                    f"ReportRunner returned without ReportComplete for {target.ticker!r}"
                )

            with self._session_factory() as session:
                report_id = self._report_store.save(
                    session=session,
                    user_id=user_id,
                    department=DEPARTMENT,
                    payload=payload,
                )
                session.commit()
            report_ids.append(report_id)
            notifications.append(
                NotificationSpec(
                    type=NotificationType.REPORT_READY,
                    department=DEPARTMENT,
                    message=f"New earnings analysis: {target.ticker}.",
                )
            )

        # Update schedule.last_run_at once at the end of a successful scan.
        with self._session_factory() as session:
            schedule = session.get(EuSchedule, schedule_id)
            if schedule is not None:
                schedule.last_run_at = datetime.now(timezone.utc)
                session.commit()

        return JobOutcome(
            result_summary={
                "reports_generated": len(report_ids),
                "report_ids": report_ids,
            },
            notifications=notifications,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_eu_executor.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/executors/eu.py \
    packages/server/tests/test_scheduler/test_eu_executor.py
git commit -m "phase-6(scheduler): EUScanExecutor (sequential per-ticker reports + per-report notify)"
```

---

## Task 12: `executors/mr.py` — MRAssessmentExecutor

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/mr.py`
- Create: `packages/server/tests/test_scheduler/test_mr_executor.py`

MR is the only executor that chains two runners:

1. `BatchRunner.run()` fans T4 items out in parallel → list of `BatchResult`.
2. The builder's `synthesize(results)` callable turns those results into a `ReportRequest` for T5.
3. `ReportRunner.run()` streams the synthesis report; its `ReportComplete.schema` becomes the T5 payload.
4. `MRCacheStore.save()` persists the full assessment (T4 results + T5 schema) into `mr_assessment_cache`.
5. One `assessment_ready` notification fires.

MR jobs are scoped to a `(user_id, dashboard)` pair, not a `MrSchedule` row. Plan 1B did not ship per-user MR scheduling columns on `mr_dashboard_state`; Plan 19 will add them and call `SchedulerService.add_job` at that time. For Plan 6 we still need the executor so Plan 19 can drop it in. The executor takes `schedule_id` as the dashboard key (e.g. `"debt_cycle"`) — that's the value SchedulerService will pass through from Plan 19.

If `BatchRunner` raises `LLMProviderError`, it propagates up to `BaseExecutor`'s retry loop unchanged. If `ReportRunner` emits `ReportError`, the executor reuses `_raise_from_report_error` (defined in `executors/mb.py`) so retry classification stays consistent with MB and EU.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_scheduler/test_mr_executor.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from _fakes import (
    FakeBatchRunner,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeSleep,
)
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportStart,
)
from openlia.llm.runtime.messages import (
    BatchItem,
    BatchResult,
    ReportRequest,
)
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.mr import MRAssessmentExecutor
from openlia_server.scheduler.registry import JobStatus


def _seed(session: Session) -> None:
    session.add(
        User(
            id="u_1", email="u@e.com", display_name="u",
            password_hash="h", is_admin=False, is_disabled=False,
        )
    )
    session.commit()


def _t5_ok_events(report_id: str = "r_t5") -> list:
    return [
        ReportStart(
            report_id=report_id, department="macro_research",
            mode="mr_synthesis", section_titles=["Assessment"],
        ),
        ReportComplete(
            report_id=report_id,
            schema={
                "title": "Debt Cycle — debt burden rising",
                "sections": [{"id": "assessment", "body": "..."}],
            },
        ),
    ]


@pytest.mark.asyncio
async def test_mr_happy_path_runs_t4_then_t5_and_caches_result(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMRBuilder(
        items=[
            BatchItem(id="debt_burden", context={"metric": "debt_burden"}),
            BatchItem(id="credit_growth", context={"metric": "credit_growth"}),
        ],
        synth=ReportRequest(mode="mr_synthesis", user_input="synthesize"),
    )
    batch_runner = FakeBatchRunner(
        results=[
            BatchResult(id="debt_burden", ok=True, data={"score": 0.8}, error=None),
            BatchResult(id="credit_growth", ok=True, data={"score": 0.6}, error=None),
        ]
    )
    report_runner = FakeReportRunner(events=_t5_ok_events())
    cache = FakeMRCacheStore(next_id="cache_abc")

    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mr_builder=builder,
        batch_runner=batch_runner,
        report_runner=report_runner,
        mr_cache_store=cache,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        summary = json.loads(row.result_summary)
        assert summary == {"cache_id": "cache_abc", "dashboard": "debt_cycle"}

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "assessment_ready"
        assert notifs[0].department == "macro_research"
        assert "debt_cycle" in notifs[0].message.lower() or "Debt" in notifs[0].message

    # BatchRunner was called once with T4 items and the builder's schema/task.
    assert len(batch_runner.calls) == 1
    call = batch_runner.calls[0]
    assert call["department_id"] == "macro_research"
    assert call["task"] == builder.t4_task
    assert [item.id for item in call["items"]] == ["debt_burden", "credit_growth"]

    # The synthesize callback received the exact BatchResult objects.
    assert len(builder.received_results) == 1
    assert [r.id for r in builder.received_results[0]] == [
        "debt_burden",
        "credit_growth",
    ]

    # ReportRunner was called exactly once, with the synth request.
    assert len(report_runner.calls) == 1
    assert report_runner.calls[0]["department_id"] == "macro_research"
    assert report_runner.calls[0]["request"].mode == "mr_synthesis"

    # Cache received the T5 schema as the persisted payload, tagged with dashboard.
    assert len(cache.saves) == 1
    saved_payload = cache.saves[0]["payload"]
    assert saved_payload["dashboard"] == "debt_cycle"
    assert saved_payload["t5"]["title"].startswith("Debt Cycle")
    assert saved_payload["t4"] == [
        {"id": "debt_burden", "ok": True, "data": {"score": 0.8}, "error": None},
        {"id": "credit_growth", "ok": True, "data": {"score": 0.6}, "error": None},
    ]


@pytest.mark.asyncio
async def test_mr_batch_returns_partial_failures_still_feeds_synthesis(
    session_factory,
) -> None:
    """Per spec: T4 items are independent. A per-item error does NOT fail
    the job — it gets passed to synthesize() so T5 can narrate around the
    gap. Only a BatchRunner-level exception (LLMProviderError) aborts."""
    with session_factory() as s:
        _seed(s)

    builder = FakeMRBuilder(
        items=[BatchItem(id="a", context={}), BatchItem(id="b", context={})],
        synth=ReportRequest(mode="mr_synthesis", user_input="s"),
    )
    batch_runner = FakeBatchRunner(
        results=[
            BatchResult(id="a", ok=True, data={"x": 1}, error=None),
            BatchResult(id="b", ok=False, data=None, error="timeout"),
        ]
    )
    report_runner = FakeReportRunner(events=_t5_ok_events())
    cache = FakeMRCacheStore(next_id="cache_xy")

    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mr_builder=builder,
        batch_runner=batch_runner,
        report_runner=report_runner,
        mr_cache_store=cache,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        assert s.get(JobRun, run_id).status == JobStatus.COMPLETED.value
        assert s.query(UserNotification).count() == 1

    # The synthesize callback saw BOTH results (ok=True and ok=False).
    passed = builder.received_results[0]
    assert len(passed) == 2
    assert passed[1].ok is False
    assert passed[1].error == "timeout"

    # The cache row preserved the partial-failure record.
    saved = cache.saves[0]["payload"]
    assert saved["t4"][1] == {"id": "b", "ok": False, "data": None, "error": "timeout"}


@pytest.mark.asyncio
async def test_mr_t5_report_error_transient_triggers_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMRBuilder(
        items=[BatchItem(id="a", context={})],
        synth=ReportRequest(mode="mr_synthesis", user_input="s"),
    )
    batch_runner = FakeBatchRunner(
        results=[BatchResult(id="a", ok=True, data={"x": 1}, error=None)]
    )

    class _TwoPhaseReport:
        def __init__(self) -> None:
            self.phase = 0

        async def run(self, **_):
            self.phase += 1
            if self.phase == 1:
                yield ReportStart(
                    report_id="r_1", department="macro_research",
                    mode="mr_synthesis", section_titles=[],
                )
                yield ReportError(
                    report_id="r_1",
                    error_class="RateLimitError",
                    message="429",
                )
                return
            for ev in _t5_ok_events("r_2"):
                yield ev

    sleep = FakeSleep()
    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=sleep,
        mr_builder=builder,
        batch_runner=batch_runner,
        report_runner=_TwoPhaseReport(),
        mr_cache_store=FakeMRCacheStore(next_id="cache_ok"),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 2
    assert sleep.calls == [30]

    # BatchRunner was only called once — we don't re-run T4 on a T5 retry.
    assert len(batch_runner.calls) == 1


@pytest.mark.asyncio
async def test_mr_batch_runner_transient_failure_retries_both_stages(
    session_factory,
) -> None:
    """If BatchRunner itself raises a transient LLMProviderError on attempt 1,
    the executor re-runs _do_work from the top on attempt 2 — including
    re-calling mr_builder.build() and BatchRunner."""
    with session_factory() as s:
        _seed(s)

    from openlia.llm.exceptions import RateLimitError

    builder = FakeMRBuilder(
        items=[BatchItem(id="a", context={})],
        synth=ReportRequest(mode="mr_synthesis", user_input="s"),
    )

    class _FlakyBatch:
        def __init__(self) -> None:
            self.calls: list = []

        async def run(self, *, department_id, task, items, schema, concurrency=8, user_id=None):
            self.calls.append({"department_id": department_id})
            if len(self.calls) == 1:
                raise RateLimitError("429", tier="medium")
            return [BatchResult(id="a", ok=True, data={"x": 1}, error=None)]

    batch = _FlakyBatch()
    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mr_builder=builder,
        batch_runner=batch,
        report_runner=FakeReportRunner(events=_t5_ok_events()),
        mr_cache_store=FakeMRCacheStore(next_id="cache_ok"),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        assert s.get(JobRun, run_id).status == JobStatus.COMPLETED.value
        assert s.get(JobRun, run_id).attempt == 2
    assert len(batch.calls) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_mr_executor.py -v`
Expected: FAIL — `executors.mr` missing.

- [ ] **Step 3: Implement `executors/mr.py`**

Create `packages/server/src/openlia_server/scheduler/executors/mr.py`:

```python
"""Macro Research assessment executor.

Chains BatchRunner (T4, per-metric analyses) → mr_builder.synthesize()
→ ReportRunner (T5, synthesis). Persists the combined result into
mr_assessment_cache and emits one `assessment_ready` notification."""
from __future__ import annotations

from dataclasses import asdict
from typing import ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ReportComplete, ReportError
from openlia.llm.runtime.messages import BatchResult
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.executors.mb import _raise_from_report_error
from openlia_server.scheduler.payloads import MRAssessmentBuilder, MRCacheStore
from openlia_server.scheduler.registry import JobType, NotificationType


DEPARTMENT = "macro_research"


def _serialize_batch_result(r: BatchResult) -> dict:
    # BatchResult is a frozen dataclass of plain JSON-compatible fields.
    return asdict(r)


class MRAssessmentExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MR_ASSESSMENT

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        mr_builder: MRAssessmentBuilder,
        batch_runner,
        report_runner,
        mr_cache_store: MRCacheStore,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._mr_builder = mr_builder
        self._batch_runner = batch_runner
        self._report_runner = report_runner
        self._mr_cache_store = mr_cache_store

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        assert user_id is not None
        assert schedule_id is not None
        dashboard = schedule_id  # MR jobs are keyed by dashboard name.

        # 1. Build the T4 payload.
        with self._session_factory() as session:
            payload = self._mr_builder.build(session=session, user_id=user_id)

        # 2. Run T4 in parallel. A BatchRunner-level exception propagates
        #    up to BaseExecutor's retry loop unchanged. Per-item failures
        #    come back inside BatchResult.ok=False and are passed through
        #    to the synthesize callback so T5 can narrate around them.
        batch_results: list[BatchResult] = await self._batch_runner.run(
            department_id=DEPARTMENT,
            task=payload.t4_task,
            items=payload.items,
            schema=payload.t4_schema,
            user_id=user_id,
        )

        # 3. Builder owns the T4→T5 transformation.
        synth_request = payload.synthesize(batch_results)

        # 4. Stream T5.
        t5_schema: dict | None = None
        async for event in self._report_runner.run(
            department_id=DEPARTMENT,
            user_id=user_id,
            request=synth_request,
            cancel_token=cancel_token,
        ):
            if isinstance(event, ReportError):
                _raise_from_report_error(event)
            if isinstance(event, ReportComplete):
                t5_schema = event.schema

        if t5_schema is None:
            raise RuntimeError(
                f"ReportRunner returned without ReportComplete for "
                f"MR assessment (dashboard={dashboard!r})"
            )

        # 5. Persist combined assessment.
        cache_payload = {
            "dashboard": dashboard,
            "t4": [_serialize_batch_result(r) for r in batch_results],
            "t5": t5_schema,
        }
        with self._session_factory() as session:
            cache_id = self._mr_cache_store.save(
                session=session,
                user_id=user_id,
                payload=cache_payload,
            )
            session.commit()

        return JobOutcome(
            result_summary={"cache_id": cache_id, "dashboard": dashboard},
            notifications=[
                NotificationSpec(
                    type=NotificationType.ASSESSMENT_READY,
                    department=DEPARTMENT,
                    message=f"New {dashboard} assessment ready.",
                )
            ],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_mr_executor.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/executors/mr.py \
    packages/server/tests/test_scheduler/test_mr_executor.py
git commit -m "phase-6(scheduler): MRAssessmentExecutor (BatchRunner T4 -> ReportRunner T5 -> cache)"
```

---

## Task 13: `service.py` — SchedulerService (APScheduler wrapper)

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/service.py`
- Create: `packages/server/tests/test_scheduler/test_scheduler_service.py`
- Modify: `packages/server/tests/test_scheduler/_fakes.py` (add `FakeAPScheduler`)

This is the largest single module in Plan 6. It wraps APScheduler 4.x `AsyncScheduler`, turns `MbSchedule`/`EuSchedule` rows into `CronTrigger` schedules, rehydrates the registry on startup, runs missed-job backfill inside the grace window, spawns the daily maintenance job, and manages graceful shutdown. MR jobs are **not** rehydrated here — Plan 1B's `mr_dashboard_state` does not yet carry scheduling columns, so Plan 19 will register MR jobs at its own startup path via `add_schedule()` once it adds those columns.

### Design notes

1. **Fake APScheduler for tests.** `FakeAPScheduler` mirrors the AsyncScheduler surface we rely on: `start_in_background()`, `stop()`, `add_schedule(...)`, `remove_schedule(id)`, `get_schedules()`. Each call is recorded so tests can assert on IDs, triggers, and args without a real scheduler running. The `SchedulerService` takes the scheduler *instance* by constructor injection, so production wires a real `AsyncScheduler` and tests wire a fake.
2. **Cron translation.** `_cron_trigger_for(schedule)` converts a `time="HH:MM"` + `timezone="UTC"` + `days_of_week='["mon","tue",...]'` tuple into an APScheduler `CronTrigger` (hour, minute, day_of_week, timezone).
3. **Job callback.** `_run_job(job_type, user_id, schedule_id)` is what APScheduler invokes. It creates a `CancellationToken`, tracks it in `self._active_tokens[job_key]`, calls the registered executor's `execute(...)`, and removes the token from the dict when done.
4. **Hot-reload.** `modify_schedule(schedule)` is just `remove_schedule()` + `add_schedule()` — APScheduler 4.x does not expose a stable "update trigger in place" call, and atomicity here is unnecessary (a missing intermediate tick is cheap compared to code complexity).
5. **Missed-job backfill.** On startup, after re-registering each schedule, `recovery.should_catch_up(...)` is asked whether the most recent expected tick was within the grace window but never produced a `job_runs` row. If so, `scheduler.add_schedule(...)` is called with a `DateTrigger(run_time=now + 1s)` so the missed tick fires immediately after the scheduler starts.

### Step 1: Extend `_fakes.py` with `FakeAPScheduler`

- [ ] **Step 1a: Add the fake**

Add to `packages/server/tests/test_scheduler/_fakes.py` (append at the bottom, before the final `# ---` separator if any):

```python
# ------------------------------------------------------------------
# FakeAPScheduler — stand-in for APScheduler AsyncScheduler in tests
# ------------------------------------------------------------------

@dataclass
class _ScheduledJob:
    id: str
    func: Any  # Callable
    trigger: Any
    args: tuple
    kwargs: dict
    misfire_grace_time: float | None


@dataclass
class FakeAPScheduler:
    started: bool = False
    stopped: bool = False
    jobs: dict[str, _ScheduledJob] = field(default_factory=dict)

    def start_in_background(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def add_schedule(
        self,
        func,
        trigger,
        *,
        id: str,
        args: tuple = (),
        kwargs: dict | None = None,
        misfire_grace_time: float | None = None,
    ) -> str:
        if id in self.jobs:
            raise ValueError(f"duplicate schedule id: {id}")
        self.jobs[id] = _ScheduledJob(
            id=id,
            func=func,
            trigger=trigger,
            args=args,
            kwargs=kwargs or {},
            misfire_grace_time=misfire_grace_time,
        )
        return id

    async def remove_schedule(self, id: str) -> None:
        self.jobs.pop(id, None)

    async def get_schedules(self) -> list[_ScheduledJob]:
        return list(self.jobs.values())

    async def fire(self, id: str) -> Any:
        """Test helper: run a scheduled job's callback synchronously."""
        job = self.jobs[id]
        return await job.func(*job.args, **job.kwargs)
```

Confirm the top of `_fakes.py` already imports `Any` and has `@dataclass`/`field` available; Task 7 did this. No new top-level imports required.

- [ ] **Step 1b: Commit the fake extension**

```bash
git add packages/server/tests/test_scheduler/_fakes.py
git commit -m "phase-6(scheduler): FakeAPScheduler test double"
```

### Step 2: Write the failing SchedulerService tests

- [ ] **Step 2: Write the tests**

Create `packages/server/tests/test_scheduler/test_scheduler_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import ClassVar

import pytest
from sqlalchemy.orm import Session

from _fakes import FakeAPScheduler, FakeSleep
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import EuSchedule, JobRun, MbSchedule
from openlia_server.scheduler.executors.base import (
    BaseExecutor,
    JobOutcome,
    SessionFactory,
)
from openlia_server.scheduler.registry import (
    JobStatus,
    JobType,
    MAINTENANCE_JOB_KEY,
    job_key,
)
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings


# --- Minimal recording executor for dispatch tests -----------------

class _RecordingExecutor(BaseExecutor):
    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        job_type: JobType,
        outcome: JobOutcome | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=FakeSleep())
        # BaseExecutor has job_type as ClassVar — override on the instance.
        self.job_type = job_type  # type: ignore[misc]
        self.calls: list[dict] = []
        self._outcome = outcome or JobOutcome(
            result_summary={"ok": True}, notifications=[]
        )
        self._raise_exc = raise_exc

    async def _do_work(self, *, user_id, schedule_id, run_id, cancel_token):
        self.calls.append(
            {
                "user_id": user_id,
                "schedule_id": schedule_id,
                "run_id": run_id,
                "cancel_token": cancel_token,
            }
        )
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._outcome


def _seed_user(session: Session) -> None:
    session.add(
        User(
            id="u_1", email="u@e.com", display_name="u",
            password_hash="h", is_admin=False, is_disabled=False,
        )
    )
    session.commit()


def _mb_schedule(
    *,
    id: str = "sch_mb",
    user_id: str = "u_1",
    time: str = "07:00",
    tz: str = "UTC",
    enabled: bool = True,
    last_run_at: datetime | None = None,
) -> MbSchedule:
    return MbSchedule(
        id=id, user_id=user_id,
        time=time, timezone=tz,
        days_of_week='["mon","tue","wed","thu","fri"]',
        label="Pre-Market", is_enabled=enabled,
        created_at=datetime.now(timezone.utc),
        last_run_at=last_run_at,
    )


def _eu_schedule(
    *,
    id: str = "sch_eu",
    user_id: str = "u_1",
    enabled: bool = True,
) -> EuSchedule:
    return EuSchedule(
        id=id, user_id=user_id,
        time="16:30", timezone="America/New_York",
        days_of_week='["mon","tue","wed","thu","fri"]',
        label="Post-Market", is_enabled=enabled,
        created_at=datetime.now(timezone.utc),
        last_run_at=None,
    )


# --- Tests ---------------------------------------------------------

@pytest.mark.asyncio
async def test_start_registers_maintenance_job(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    assert scheduler.started is True
    assert MAINTENANCE_JOB_KEY in scheduler.jobs
    assert svc.is_running is True


@pytest.mark.asyncio
async def test_start_rehydrates_enabled_mb_and_eu_schedules(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)
        s.add(_mb_schedule(id="sch_mb", enabled=True))
        s.add(_mb_schedule(id="sch_mb_off", enabled=False))
        s.add(_eu_schedule(id="sch_eu", enabled=True))
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    assert job_key(JobType.MB_BRIEFING, "u_1") in scheduler.jobs
    assert job_key(JobType.EU_SCAN, "u_1") in scheduler.jobs
    assert "mb_briefing:u_1" in scheduler.jobs  # same as above, explicit form
    assert all(
        k != job_key(JobType.MB_BRIEFING, "u_1_off")
        for k in scheduler.jobs
    )


@pytest.mark.asyncio
async def test_start_skips_schedules_for_disabled_users(
    session_factory,
) -> None:
    with session_factory() as s:
        s.add(
            User(
                id="u_bad", email="x@e.com", display_name="x",
                password_hash="h", is_admin=False, is_disabled=True,
            )
        )
        s.add(_mb_schedule(id="sch_bad", user_id="u_bad"))
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    assert job_key(JobType.MB_BRIEFING, "u_bad") not in scheduler.jobs


@pytest.mark.asyncio
async def test_disabled_flag_does_not_start_scheduler(session_factory) -> None:
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=False),
    )
    await svc.start()

    assert scheduler.started is False
    assert svc.is_running is False
    assert scheduler.jobs == {}


@pytest.mark.asyncio
async def test_add_schedule_registers_job_with_correct_key_and_trigger(
    session_factory,
) -> None:
    from apscheduler.triggers.cron import CronTrigger

    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    await svc.add_schedule(_mb_schedule(time="09:30", tz="America/New_York"))

    key = job_key(JobType.MB_BRIEFING, "u_1")
    assert key in scheduler.jobs
    job = scheduler.jobs[key]
    assert isinstance(job.trigger, CronTrigger)
    assert job.args == (JobType.MB_BRIEFING, "u_1", "sch_mb")


@pytest.mark.asyncio
async def test_modify_schedule_replaces_existing_job(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    await svc.add_schedule(_mb_schedule(time="07:00"))
    await svc.modify_schedule(_mb_schedule(time="08:30"))

    key = job_key(JobType.MB_BRIEFING, "u_1")
    assert key in scheduler.jobs
    # Trigger swap: there's still exactly one MB job for u_1.
    mb_ids = [k for k in scheduler.jobs if k.startswith("mb_briefing:")]
    assert mb_ids == [key]


@pytest.mark.asyncio
async def test_remove_schedule_unregisters_job(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()
    await svc.add_schedule(_mb_schedule())

    await svc.remove_schedule(
        job_type=JobType.MB_BRIEFING, user_id="u_1"
    )
    assert job_key(JobType.MB_BRIEFING, "u_1") not in scheduler.jobs


@pytest.mark.asyncio
async def test_add_schedule_raises_when_executor_not_registered(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    # Intentionally pass executors={} so MB is unregistered.
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={},
    )
    await svc.start()

    with pytest.raises(RuntimeError, match="no executor registered"):
        await svc.add_schedule(_mb_schedule())


@pytest.mark.asyncio
async def test_dispatch_routes_call_to_registered_executor(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MB_BRIEFING: mb_exec},
    )
    await svc.start()
    await svc.add_schedule(_mb_schedule())

    # Fire the APScheduler callback manually.
    key = job_key(JobType.MB_BRIEFING, "u_1")
    await scheduler.fire(key)

    assert len(mb_exec.calls) == 1
    assert mb_exec.calls[0]["user_id"] == "u_1"
    assert mb_exec.calls[0]["schedule_id"] == "sch_mb"
    assert mb_exec.calls[0]["cancel_token"] is not None


@pytest.mark.asyncio
async def test_startup_backfills_missed_tick_within_grace(
    session_factory,
) -> None:
    """Schedule ran at 07:00 UTC daily. last_run_at is 2 days ago, grace
    is 6 hours. The schedule's most recent tick is today 07:00 — within
    6h if startup is <=13:00 — so a catch-up run must be queued."""
    from apscheduler.triggers.date import DateTrigger

    now = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    with session_factory() as s:
        _seed_user(s)
        s.add(
            _mb_schedule(
                time="07:00",
                tz="UTC",
                last_run_at=datetime(2026, 4, 16, 7, 0, tzinfo=timezone.utc),
            )
        )
        s.commit()

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(
            enabled=True, misfire_grace_seconds=6 * 3600
        ),
        executors={JobType.MB_BRIEFING: mb_exec},
        clock=lambda: now,
    )
    await svc.start()

    # The normal cron registration.
    assert job_key(JobType.MB_BRIEFING, "u_1") in scheduler.jobs
    # Plus a one-shot backfill with a DateTrigger.
    backfill_key = f"{job_key(JobType.MB_BRIEFING, 'u_1')}:backfill"
    assert backfill_key in scheduler.jobs
    assert isinstance(scheduler.jobs[backfill_key].trigger, DateTrigger)


@pytest.mark.asyncio
async def test_startup_does_not_backfill_when_tick_outside_grace(
    session_factory,
) -> None:
    """Daily 07:00 UTC, last ran 5 days ago, grace is 6 hours, startup is
    18:00 UTC. The most recent tick was 07:00 today — 11h ago — outside
    6h. No backfill."""
    now = datetime(2026, 4, 17, 18, 0, tzinfo=timezone.utc)
    with session_factory() as s:
        _seed_user(s)
        s.add(
            _mb_schedule(
                time="07:00",
                tz="UTC",
                last_run_at=datetime(2026, 4, 12, 7, 0, tzinfo=timezone.utc),
            )
        )
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(
            enabled=True, misfire_grace_seconds=6 * 3600
        ),
        clock=lambda: now,
    )
    await svc.start()

    assert f"{job_key(JobType.MB_BRIEFING, 'u_1')}:backfill" not in scheduler.jobs


@pytest.mark.asyncio
async def test_startup_marks_running_jobs_as_cancelled(
    session_factory,
) -> None:
    """If a previous process died with status=running rows, recovery flips
    them to status=cancelled before rehydration."""
    with session_factory() as s:
        _seed_user(s)
        s.add(
            JobRun(
                id="run_orphan",
                job_key="mb_briefing:u_1",
                job_type=JobType.MB_BRIEFING.value,
                user_id="u_1",
                schedule_id="sch_mb",
                attempt=1,
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    with session_factory() as s:
        row = s.get(JobRun, "run_orphan")
        assert row.status == JobStatus.CANCELLED.value
        assert "restart" in (row.error_message or "").lower()


@pytest.mark.asyncio
async def test_shutdown_cancels_active_tokens_and_stops_scheduler(
    session_factory,
) -> None:
    import asyncio

    with session_factory() as s:
        _seed_user(s)

    # Executor that parks forever so we can observe cancellation.
    class _Sleeper(BaseExecutor):
        def __init__(self, *, session_factory: SessionFactory) -> None:
            super().__init__(session_factory=session_factory, sleep=FakeSleep())
            self.cancel_seen = asyncio.Event()

        job_type: ClassVar[JobType] = JobType.MB_BRIEFING

        async def _do_work(self, *, user_id, schedule_id, run_id, cancel_token):
            # Wait for cancellation.
            while not cancel_token.is_cancelled:
                await asyncio.sleep(0.01)
            self.cancel_seen.set()
            raise asyncio.CancelledError

    sleeper = _Sleeper(session_factory=session_factory)
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True, shutdown_grace_seconds=1),
        executors={JobType.MB_BRIEFING: sleeper},
    )
    await svc.start()
    await svc.add_schedule(_mb_schedule())

    # Kick off a job in the background and let it reach its sleep.
    key = job_key(JobType.MB_BRIEFING, "u_1")
    task = asyncio.create_task(scheduler.fire(key))
    await asyncio.sleep(0.05)

    await svc.shutdown()

    assert sleeper.cancel_seen.is_set()
    assert scheduler.stopped is True
    # Let the job task unwind.
    with pytest.raises(asyncio.CancelledError):
        await task
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_scheduler_service.py -v`
Expected: FAIL — `service.SchedulerService` missing.

### Step 3: Implement `service.py`

- [ ] **Step 4: Implement the service**

Create `packages/server/src/openlia_server/scheduler/service.py`:

```python
"""SchedulerService — APScheduler wrapper that owns the lifecycle
(startup rehydration, hot-reload add/modify/remove, graceful shutdown)
for the four job types defined in registry.JobType."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from openlia.llm.runtime.cancellation import CancellationToken
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import (
    EuSchedule,
    MbSchedule,
)
from openlia_server.scheduler.executors.base import BaseExecutor, SessionFactory
from openlia_server.scheduler.recovery import (
    mark_orphans_cancelled,
    should_catch_up,
)
from openlia_server.scheduler.registry import (
    JobType,
    MAINTENANCE_JOB_KEY,
    job_key,
)
from openlia_server.scheduler.settings import SchedulerSettings


log = logging.getLogger(__name__)

_DAY_NAMES = {
    "mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
    "fri": "fri", "sat": "sat", "sun": "sun",
}


@dataclass
class SchedulerService:
    session_factory: SessionFactory
    scheduler: Any  # APScheduler AsyncScheduler (or FakeAPScheduler in tests)
    settings: SchedulerSettings
    executors: dict[JobType, BaseExecutor] = field(default_factory=dict)
    clock: Callable[[], datetime] = field(
        default_factory=lambda: (lambda: datetime.now(timezone.utc))
    )

    is_running: bool = field(init=False, default=False)
    _active_tokens: dict[str, CancellationToken] = field(
        init=False, default_factory=dict
    )

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    async def start(self) -> None:
        if not self.settings.enabled:
            log.info("scheduler disabled via settings; skipping start")
            return

        # 1. Crash recovery: mark any status=running rows as cancelled.
        with self.session_factory() as session:
            mark_orphans_cancelled(session)
            session.commit()

        # 2. Start the APScheduler instance.
        self.scheduler.start_in_background()
        self.is_running = True

        # 3. Register the singleton maintenance job (daily 03:00 UTC).
        await self._register_maintenance_job()

        # 4. Rehydrate per-user MB/EU schedules.
        with self.session_factory() as session:
            enabled_user_ids = {
                u.id
                for u in session.query(User).filter(User.is_disabled.is_(False))
            }
            mb_rows = (
                session.query(MbSchedule)
                .filter(MbSchedule.is_enabled.is_(True))
                .all()
            )
            eu_rows = (
                session.query(EuSchedule)
                .filter(EuSchedule.is_enabled.is_(True))
                .all()
            )

        for row in mb_rows:
            if row.user_id not in enabled_user_ids:
                continue
            await self._register_schedule(
                job_type=JobType.MB_BRIEFING, schedule=row
            )
            await self._maybe_backfill(
                job_type=JobType.MB_BRIEFING, schedule=row
            )

        for row in eu_rows:
            if row.user_id not in enabled_user_ids:
                continue
            await self._register_schedule(
                job_type=JobType.EU_SCAN, schedule=row
            )
            await self._maybe_backfill(
                job_type=JobType.EU_SCAN, schedule=row
            )

    async def shutdown(self) -> None:
        """Cancel all in-flight jobs, wait up to `shutdown_grace_seconds`
        for them to unwind, then stop the APScheduler instance."""
        if not self.is_running:
            return

        for token in list(self._active_tokens.values()):
            token.cancel()

        deadline = self.clock() + timedelta(
            seconds=self.settings.shutdown_grace_seconds
        )
        while self._active_tokens and self.clock() < deadline:
            await asyncio.sleep(0.05)

        await self.scheduler.stop()
        self.is_running = False

    # ------------------------------------------------------------
    # Hot-reload API (called by route handlers)
    # ------------------------------------------------------------

    async def add_schedule(self, schedule: MbSchedule | EuSchedule) -> None:
        job_type = self._job_type_for(schedule)
        await self._register_schedule(job_type=job_type, schedule=schedule)

    async def modify_schedule(self, schedule: MbSchedule | EuSchedule) -> None:
        job_type = self._job_type_for(schedule)
        await self.remove_schedule(
            job_type=job_type, user_id=schedule.user_id
        )
        await self._register_schedule(job_type=job_type, schedule=schedule)

    async def remove_schedule(
        self, *, job_type: JobType, user_id: str
    ) -> None:
        await self.scheduler.remove_schedule(job_key(job_type, user_id))

    async def remove_all_for_user(self, user_id: str) -> None:
        """Called when a user is disabled: yank every per-user job."""
        for jt in (JobType.MB_BRIEFING, JobType.EU_SCAN, JobType.MR_ASSESSMENT):
            try:
                await self.scheduler.remove_schedule(job_key(jt, user_id))
            except Exception:
                # remove_schedule is idempotent in our fake; real APScheduler
                # may raise on unknown id — that's fine.
                pass

    # ------------------------------------------------------------
    # Job callback (invoked by APScheduler at trigger time)
    # ------------------------------------------------------------

    async def _run_job(
        self,
        job_type: JobType,
        user_id: str | None,
        schedule_id: str | None,
    ) -> None:
        key = (
            MAINTENANCE_JOB_KEY
            if job_type is JobType.SYSTEM_MAINTENANCE
            else job_key(job_type, user_id or "")
        )
        if key in self._active_tokens:
            log.info("skipping %s: previous run still active", key)
            return

        executor = self.executors.get(job_type)
        if executor is None:
            log.error("no executor registered for %s", job_type)
            return

        token = CancellationToken()
        self._active_tokens[key] = token
        try:
            await executor.execute(
                user_id=user_id,
                schedule_id=schedule_id,
                cancel_token=token,
            )
        except asyncio.CancelledError:
            # Expected during shutdown.
            pass
        except Exception:
            log.exception("unhandled error in scheduled job %s", key)
        finally:
            self._active_tokens.pop(key, None)

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    async def _register_schedule(
        self,
        *,
        job_type: JobType,
        schedule: MbSchedule | EuSchedule,
    ) -> None:
        if job_type not in self.executors:
            raise RuntimeError(
                f"no executor registered for job_type={job_type.value!r}"
            )
        trigger = self._cron_trigger_for(schedule)
        await self.scheduler.add_schedule(
            self._run_job,
            trigger,
            id=job_key(job_type, schedule.user_id),
            args=(job_type, schedule.user_id, schedule.id),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )

    async def _register_maintenance_job(self) -> None:
        if JobType.SYSTEM_MAINTENANCE not in self.executors:
            # OK in tests; production wires the real one.
            log.info("no maintenance executor registered — skipping")
            return
        trigger = CronTrigger(hour=3, minute=0, timezone=timezone.utc)
        await self.scheduler.add_schedule(
            self._run_job,
            trigger,
            id=MAINTENANCE_JOB_KEY,
            args=(JobType.SYSTEM_MAINTENANCE, None, None),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )

    async def _maybe_backfill(
        self,
        *,
        job_type: JobType,
        schedule: MbSchedule | EuSchedule,
    ) -> None:
        cron = self._cron_expression_for(schedule)
        if not should_catch_up(
            cron_expression=cron,
            timezone_name=schedule.timezone,
            last_run_at=schedule.last_run_at,
            now=self.clock(),
            grace_seconds=self.settings.misfire_grace_seconds,
        ):
            return

        run_time = self.clock() + timedelta(seconds=1)
        await self.scheduler.add_schedule(
            self._run_job,
            DateTrigger(run_time=run_time),
            id=f"{job_key(job_type, schedule.user_id)}:backfill",
            args=(job_type, schedule.user_id, schedule.id),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )

    # --- cron helpers ---

    @staticmethod
    def _job_type_for(schedule: MbSchedule | EuSchedule) -> JobType:
        if isinstance(schedule, MbSchedule):
            return JobType.MB_BRIEFING
        if isinstance(schedule, EuSchedule):
            return JobType.EU_SCAN
        raise TypeError(f"unknown schedule type: {type(schedule).__name__}")

    @staticmethod
    def _cron_trigger_for(schedule: MbSchedule | EuSchedule) -> CronTrigger:
        hour, minute = [int(p) for p in schedule.time.split(":")]
        days_raw = json.loads(schedule.days_of_week)
        days = ",".join(_DAY_NAMES[d] for d in days_raw)
        return CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=days,
            timezone=schedule.timezone,
        )

    @staticmethod
    def _cron_expression_for(
        schedule: MbSchedule | EuSchedule,
    ) -> str:
        """croniter-compatible 5-field string. Used only by should_catch_up."""
        hour, minute = [int(p) for p in schedule.time.split(":")]
        days_raw = json.loads(schedule.days_of_week)
        # croniter wants 0-6 Mon=0 format? No — croniter accepts mon..sun.
        days = ",".join(_DAY_NAMES[d] for d in days_raw)
        return f"{minute} {hour} * * {days}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_scheduler_service.py -v`
Expected: 13 tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/service.py \
    packages/server/tests/test_scheduler/test_scheduler_service.py
git commit -m "phase-6(scheduler): SchedulerService (APScheduler wrapper + rehydrate/backfill/shutdown)"
```

---

## Task 14: `wiring.py` + FastAPI lifespan

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/wiring.py`
- Create: `packages/server/tests/test_scheduler/test_wiring.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Create: `packages/server/tests/test_app_lifespan.py`

The scheduler is owned by the FastAPI lifespan. `app.state.scheduler` is set on startup and torn down on shutdown. Route handlers in Task 15 call `request.app.state.scheduler.add_schedule(...)` when a user creates a new `MbSchedule` / `EuSchedule`.

`wiring.build_scheduler_service(...)` is where we construct the executor graph. It accepts injection points for every department builder so that:

- **Production** wires real `ReportRunner`/`BatchRunner` (from Plan 5) + stubs for unreleased department builders. Those stubs raise `DepartmentPayloadBuilderNotWired` when fired, which the executor converts into a failed `job_runs` row — so the system ships without panic-crashing.
- **Plans 13/15/16/19** update `wiring.py` to swap their stub for the real implementation as each ships.
- **Tests** can wire fakes for whichever subsystem they're exercising.

- [ ] **Step 1: Write the failing wiring test**

Create `packages/server/tests/test_scheduler/test_wiring.py`:

```python
from __future__ import annotations

import pytest

from _fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeReportRunner,
)
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


@pytest.mark.asyncio
async def test_build_scheduler_service_wires_all_executors(
    session_factory,
) -> None:
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
    )

    assert JobType.MB_BRIEFING in svc.executors
    assert JobType.EU_SCAN in svc.executors
    assert JobType.MR_ASSESSMENT in svc.executors
    assert JobType.SYSTEM_MAINTENANCE in svc.executors


def test_build_scheduler_service_uses_stubs_when_builders_unprovided(
    session_factory,
) -> None:
    """If a department's builder isn't provided, the executor fires but its
    stub raises DepartmentPayloadBuilderNotWired on first call. The
    scheduler layer treats that as a normal failed run, not a crash."""
    from openlia_server.scheduler.payloads import (
        DepartmentPayloadBuilderNotWired,
    )

    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
    )

    mb_exec = svc.executors[JobType.MB_BRIEFING]
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 16"):
        # MBBriefingExecutor grabs the builder on _do_work; call directly.
        mb_exec._mb_builder.build(
            session=None, user_id="u_1", schedule_id="s_1"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_wiring.py -v`
Expected: FAIL — `wiring` missing.

- [ ] **Step 3: Implement `wiring.py`**

Create `packages/server/src/openlia_server/scheduler/wiring.py`:

```python
"""Construct the SchedulerService executor graph.

Each Plan that ships a real department builder will update this module
to inject its real implementation. Until then, stubs raise
DepartmentPayloadBuilderNotWired when fired — which the executor logs
as a failed job_runs row but does NOT treat as a crash."""
from __future__ import annotations

from typing import Any

from openlia_server.scheduler.executors.base import SessionFactory
from openlia_server.scheduler.executors.eu import EUScanExecutor
from openlia_server.scheduler.executors.maintenance import MaintenanceExecutor
from openlia_server.scheduler.executors.mb import MBBriefingExecutor
from openlia_server.scheduler.executors.mr import MRAssessmentExecutor
from openlia_server.scheduler.payloads import (
    EUScanPlanner,
    MBRequestBuilder,
    MRAssessmentBuilder,
    MRCacheStore,
    ReportStore,
    StubEUScanPlanner,
    StubMBRequestBuilder,
    StubMRAssessmentBuilder,
    StubMRCacheStore,
    StubReportStore,
)
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings


def build_scheduler_service(
    *,
    session_factory: SessionFactory,
    settings: SchedulerSettings,
    scheduler: Any,
    report_runner: Any,
    batch_runner: Any,
    mb_builder: MBRequestBuilder | None = None,
    eu_planner: EUScanPlanner | None = None,
    mr_builder: MRAssessmentBuilder | None = None,
    report_store: ReportStore | None = None,
    mr_cache_store: MRCacheStore | None = None,
) -> SchedulerService:
    mb_builder = mb_builder or StubMBRequestBuilder()
    eu_planner = eu_planner or StubEUScanPlanner()
    mr_builder = mr_builder or StubMRAssessmentBuilder()
    report_store = report_store or StubReportStore()
    mr_cache_store = mr_cache_store or StubMRCacheStore()

    executors = {
        JobType.MB_BRIEFING: MBBriefingExecutor(
            session_factory=session_factory,
            mb_builder=mb_builder,
            report_runner=report_runner,
            report_store=report_store,
        ),
        JobType.EU_SCAN: EUScanExecutor(
            session_factory=session_factory,
            eu_planner=eu_planner,
            report_runner=report_runner,
            report_store=report_store,
        ),
        JobType.MR_ASSESSMENT: MRAssessmentExecutor(
            session_factory=session_factory,
            mr_builder=mr_builder,
            batch_runner=batch_runner,
            report_runner=report_runner,
            mr_cache_store=mr_cache_store,
        ),
        JobType.SYSTEM_MAINTENANCE: MaintenanceExecutor(
            session_factory=session_factory,
        ),
    }

    return SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=settings,
        executors=executors,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_wiring.py -v`
Expected: 2 tests pass.

### Step 5: Add lifespan to `app.py`

- [ ] **Step 5: Write the failing lifespan test**

Create `packages/server/tests/test_app_lifespan.py`:

```python
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def test_lifespan_sets_scheduler_on_app_state_when_enabled() -> None:
    """With OPENLIA_SCHEDULER_ENABLED=1, the lifespan must create the
    SchedulerService and park it on app.state.scheduler."""
    # Force-disable startup DB hits by pointing at an in-memory SQLite
    # via whatever env var Plan 1B uses. Plan 6 assumes the DB layer
    # is already wired via create_app().
    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "1",
            "OPENLIA_DATABASE_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert getattr(app.state, "scheduler", None) is not None
            assert app.state.scheduler.is_running is True


def test_lifespan_skips_scheduler_when_disabled() -> None:
    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "0",
            "OPENLIA_DATABASE_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            # Either attribute is missing or is_running=False.
            svc = getattr(app.state, "scheduler", None)
            assert svc is None or svc.is_running is False
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_app_lifespan.py -v`
Expected: FAIL — lifespan not wired.

- [ ] **Step 7: Wire the lifespan**

Replace the contents of `packages/server/src/openlia_server/app.py` with:

```python
"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler import AsyncScheduler
from fastapi import FastAPI

from openlia_server.db.session import build_session_factory
from openlia_server.llm.wiring import build_llm_runners  # from Plan 5
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # 1. Session factory (from Plan 1B).
    session_factory = build_session_factory()
    app.state.session_factory = session_factory

    # 2. LLM runners (from Plan 5).
    runners = build_llm_runners(session_factory=session_factory)
    app.state.report_runner = runners.report
    app.state.batch_runner = runners.batch
    app.state.chat_runner = runners.chat

    # 3. Scheduler.
    settings = SchedulerSettings.from_env()
    scheduler_instance = AsyncScheduler()
    scheduler_service = build_scheduler_service(
        session_factory=session_factory,
        settings=settings,
        scheduler=scheduler_instance,
        report_runner=runners.report,
        batch_runner=runners.batch,
    )
    await scheduler_service.start()
    app.state.scheduler = scheduler_service

    try:
        yield
    finally:
        await scheduler_service.shutdown()


def create_app() -> FastAPI:
    """Build the FastAPI app. Phase 1+ registers routers here."""
    app = FastAPI(
        title="OpenLIA",
        version="0.1.0",
        lifespan=_lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

> **Note for the executor:** if Plan 5's runner wiring module has a different import path or factory signature, adjust the `build_llm_runners` call (and this plan's doc) to match. The same applies to `build_session_factory` from Plan 1B. These are the only two cross-plan seams.

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_app_lifespan.py packages/server/tests/test_scheduler/test_wiring.py -v`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/wiring.py \
    packages/server/src/openlia_server/app.py \
    packages/server/tests/test_scheduler/test_wiring.py \
    packages/server/tests/test_app_lifespan.py
git commit -m "phase-6(scheduler): wire SchedulerService into FastAPI lifespan"
```

---

## Task 15: Routes — `/jobs/history`, `/jobs/{run_id}/retry`, `/notifications/unread`, `/notifications/read`

**Files:**
- Create: `packages/server/src/openlia_server/routes/jobs.py`
- Create: `packages/server/src/openlia_server/routes/notifications.py`
- Modify: `packages/server/src/openlia_server/app.py` (register routers)
- Modify: `packages/server/src/openlia_server/scheduler/service.py` (add `run_retry`)
- Create: `packages/server/tests/test_scheduler/test_routes_jobs.py`
- Create: `packages/server/tests/test_scheduler/test_routes_notifications.py`

Four endpoints. All require an authenticated user (dependency from Plan 2). All user-scoped — a user can only see their own runs and notifications.

| Endpoint | Purpose |
|---|---|
| `GET /jobs/history?limit=50&offset=0` | list job_runs for current user, newest first |
| `POST /jobs/{run_id}/retry` | manually re-fire a failed/cancelled run; returns the new run_id |
| `GET /notifications/unread` | `{"by_department": {"morning_briefing": 2, ...}, "total": 3}` |
| `POST /notifications/read` body `{"department": "morning_briefing"}` | mark that department's notifications read |

### Step 1: Extend SchedulerService with `run_retry`

- [ ] **Step 1: Write the retry test**

Append to `packages/server/tests/test_scheduler/test_scheduler_service.py`:

```python
@pytest.mark.asyncio
async def test_run_retry_fires_original_schedule_as_one_shot(
    session_factory,
) -> None:
    from apscheduler.triggers.date import DateTrigger
    from openlia_server.db.models.scheduler import JobRun

    with session_factory() as s:
        _seed_user(s)
        s.add(_mb_schedule())
        s.add(
            JobRun(
                id="run_failed",
                job_key=job_key(JobType.MB_BRIEFING, "u_1"),
                job_type=JobType.MB_BRIEFING.value,
                user_id="u_1",
                schedule_id="sch_mb",
                attempt=3,
                status=JobStatus.FAILED.value,
                started_at=datetime.now(timezone.utc) - timedelta(hours=2),
                finished_at=datetime.now(timezone.utc) - timedelta(hours=1),
                error_class="RateLimitError",
                error_message="429",
            )
        )
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    await svc.run_retry(run_id="run_failed")

    retry_key = f"{job_key(JobType.MB_BRIEFING, 'u_1')}:retry:run_failed"
    assert retry_key in scheduler.jobs
    assert isinstance(scheduler.jobs[retry_key].trigger, DateTrigger)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest packages/server/tests/test_scheduler/test_scheduler_service.py::test_run_retry_fires_original_schedule_as_one_shot -v`
Expected: FAIL — `run_retry` missing.

- [ ] **Step 3: Implement `run_retry` in `service.py`**

Add to `SchedulerService`:

```python
    async def run_retry(self, *, run_id: str) -> None:
        """Fire a one-shot re-run of a prior job_runs row. Looks up the
        original (job_type, user_id, schedule_id) and schedules a
        DateTrigger for `now + 1s`."""
        from openlia_server.db.models.scheduler import JobRun

        with self.session_factory() as session:
            original = session.get(JobRun, run_id)
            if original is None:
                raise LookupError(f"job_run {run_id!r} not found")
            job_type = JobType(original.job_type)
            user_id = original.user_id
            schedule_id = original.schedule_id

        run_time = self.clock() + timedelta(seconds=1)
        await self.scheduler.add_schedule(
            self._run_job,
            DateTrigger(run_time=run_time),
            id=f"{job_key(job_type, user_id or '')}:retry:{run_id}",
            args=(job_type, user_id, schedule_id),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_scheduler/test_scheduler_service.py::test_run_retry_fires_original_schedule_as_one_shot -v`
Expected: PASS.

### Step 2: Write failing route tests

- [ ] **Step 5: Write `test_routes_jobs.py`**

Create `packages/server/tests/test_scheduler/test_routes_jobs.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from openlia_server.app import create_app
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobStatus, JobType


@pytest.fixture
def client_with_user(monkeypatch, session_factory, tmp_path) -> TestClient:
    """Stand up an app with a logged-in user and a pre-stubbed scheduler.

    We don't actually start APScheduler here — we monkey-patch
    build_scheduler_service to return a lightweight shim that can only
    answer run_retry (which is all the routes need)."""
    from _fakes import FakeAPScheduler, FakeBatchRunner, FakeReportRunner
    from openlia_server.scheduler import wiring as wiring_mod
    from openlia_server.scheduler.settings import SchedulerSettings

    def _build(*args, **kwargs):
        svc = wiring_mod.build_scheduler_service(
            session_factory=kwargs["session_factory"],
            settings=SchedulerSettings(enabled=True),
            scheduler=FakeAPScheduler(),
            report_runner=FakeReportRunner(events=[]),
            batch_runner=FakeBatchRunner(results=[]),
        )
        return svc

    monkeypatch.setattr(
        "openlia_server.app.build_scheduler_service", _build
    )
    monkeypatch.setattr(
        "openlia_server.app.build_session_factory", lambda: session_factory
    )

    with session_factory() as s:
        s.add(
            User(
                id="u_1", email="u@e.com", display_name="u",
                password_hash="h", is_admin=False, is_disabled=False,
            )
        )
        s.commit()

    app = create_app()

    # Override the auth dependency to return our seeded user.
    from openlia_server.auth.deps import get_current_user  # from Plan 2

    def _fake_user():
        with session_factory() as s:
            return s.get(User, "u_1")

    app.dependency_overrides[get_current_user] = _fake_user

    return TestClient(app)


def _seed_run(
    session,
    *,
    id: str,
    status: JobStatus,
    job_type: JobType = JobType.MB_BRIEFING,
    user_id: str = "u_1",
    started_minutes_ago: int = 10,
) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        JobRun(
            id=id,
            job_key=f"{job_type.value}:{user_id}",
            job_type=job_type.value,
            user_id=user_id,
            schedule_id="sch_mb",
            attempt=1,
            status=status.value,
            started_at=now,
            finished_at=now if status is not JobStatus.RUNNING else None,
            result_summary=json.dumps({"ok": True}) if status is JobStatus.COMPLETED else None,
            error_class="RateLimitError" if status is JobStatus.FAILED else None,
            error_message="429" if status is JobStatus.FAILED else None,
        )
    )


def test_jobs_history_returns_current_users_runs_newest_first(
    client_with_user, session_factory
) -> None:
    with session_factory() as s:
        _seed_run(s, id="run_1", status=JobStatus.COMPLETED)
        _seed_run(s, id="run_2", status=JobStatus.FAILED)
        _seed_run(s, id="run_3", status=JobStatus.COMPLETED)
        # Another user's run — must NOT appear.
        s.add(
            User(
                id="u_other", email="x@e.com", display_name="x",
                password_hash="h", is_admin=False, is_disabled=False,
            )
        )
        _seed_run(s, id="run_other", status=JobStatus.COMPLETED, user_id="u_other")
        s.commit()

    r = client_with_user.get("/jobs/history")
    assert r.status_code == 200
    body = r.json()
    ids = [row["id"] for row in body["runs"]]
    assert "run_other" not in ids
    assert set(ids) == {"run_1", "run_2", "run_3"}
    # Newest first — started_at is the same for all, so the API should
    # break ties by id desc as a stable fallback. Just check the set.
    assert body["total"] == 3


def test_jobs_history_pagination(client_with_user, session_factory) -> None:
    with session_factory() as s:
        for i in range(5):
            _seed_run(s, id=f"r{i}", status=JobStatus.COMPLETED)
        s.commit()

    r = client_with_user.get("/jobs/history?limit=2&offset=0")
    assert r.status_code == 200
    assert len(r.json()["runs"]) == 2
    assert r.json()["total"] == 5


def test_retry_endpoint_schedules_new_run(
    client_with_user, session_factory
) -> None:
    with session_factory() as s:
        _seed_run(s, id="run_fail", status=JobStatus.FAILED)
        s.commit()

    r = client_with_user.post("/jobs/run_fail/retry")
    assert r.status_code == 202
    body = r.json()
    assert body["run_id"] == "run_fail"
    assert body["retry_scheduled"] is True


def test_retry_refuses_someone_elses_run(
    client_with_user, session_factory
) -> None:
    with session_factory() as s:
        s.add(
            User(
                id="u_other", email="x@e.com", display_name="x",
                password_hash="h", is_admin=False, is_disabled=False,
            )
        )
        _seed_run(s, id="run_other", status=JobStatus.FAILED, user_id="u_other")
        s.commit()

    r = client_with_user.post("/jobs/run_other/retry")
    assert r.status_code == 404  # 404, not 403 — don't leak existence
```

- [ ] **Step 6: Write `test_routes_notifications.py`**

Create `packages/server/tests/test_scheduler/test_routes_notifications.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import UserNotification


# Reuse the fixture from test_routes_jobs.py
pytest_plugins = ["test_routes_jobs"]


def _seed_notif(
    session,
    *,
    id: str,
    department: str,
    user_id: str = "u_1",
    read_at=None,
) -> None:
    session.add(
        UserNotification(
            id=id,
            user_id=user_id,
            type="report_ready",
            department=department,
            message=f"notif {id}",
            created_at=datetime.now(timezone.utc),
            read_at=read_at,
        )
    )


def test_unread_returns_counts_by_department(
    client_with_user, session_factory
) -> None:
    with session_factory() as s:
        _seed_notif(s, id="n1", department="morning_briefing")
        _seed_notif(s, id="n2", department="morning_briefing")
        _seed_notif(s, id="n3", department="earnings_update")
        # One already read — should not count.
        _seed_notif(
            s, id="n4", department="morning_briefing",
            read_at=datetime.now(timezone.utc),
        )
        s.commit()

    r = client_with_user.get("/notifications/unread")
    assert r.status_code == 200
    body = r.json()
    assert body["by_department"] == {
        "morning_briefing": 2,
        "earnings_update": 1,
    }
    assert body["total"] == 3


def test_mark_read_flips_all_department_notifications(
    client_with_user, session_factory
) -> None:
    with session_factory() as s:
        _seed_notif(s, id="n1", department="morning_briefing")
        _seed_notif(s, id="n2", department="morning_briefing")
        _seed_notif(s, id="n3", department="earnings_update")
        s.commit()

    r = client_with_user.post(
        "/notifications/read",
        json={"department": "morning_briefing"},
    )
    assert r.status_code == 200
    assert r.json() == {"marked_read": 2}

    with session_factory() as s:
        remaining = (
            s.query(UserNotification)
            .filter(UserNotification.read_at.is_(None))
            .all()
        )
        assert [n.id for n in remaining] == ["n3"]
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_scheduler/test_routes_jobs.py packages/server/tests/test_scheduler/test_routes_notifications.py -v`
Expected: FAIL — routers not registered.

### Step 3: Implement the routers

- [ ] **Step 8: Implement `routes/jobs.py`**

Create `packages/server/src/openlia_server/routes/jobs.py`:

```python
"""Job history + manual retry endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from openlia_server.auth.deps import get_current_user  # Plan 2
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.services import jobs as jobs_service


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobRunOut(BaseModel):
    id: str
    job_type: str
    status: str
    attempt: int
    started_at: str | None
    finished_at: str | None
    result_summary: str | None
    error_class: str | None
    error_message: str | None


class JobsHistoryOut(BaseModel):
    runs: list[JobRunOut]
    total: int


class RetryAck(BaseModel):
    run_id: str
    retry_scheduled: bool


@router.get("/history", response_model=JobsHistoryOut)
def jobs_history(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    limit: int = Field(default=50, ge=1, le=200),
    offset: int = Field(default=0, ge=0),
) -> JobsHistoryOut:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        runs, total = jobs_service.list_for_user(
            session=session, user_id=user.id, limit=limit, offset=offset
        )
    return JobsHistoryOut(
        runs=[
            JobRunOut(
                id=r.id,
                job_type=r.job_type,
                status=r.status,
                attempt=r.attempt,
                started_at=r.started_at.isoformat() if r.started_at else None,
                finished_at=r.finished_at.isoformat() if r.finished_at else None,
                result_summary=r.result_summary,
                error_class=r.error_class,
                error_message=r.error_message,
            )
            for r in runs
        ],
        total=total,
    )


@router.post("/{run_id}/retry", response_model=RetryAck, status_code=202)
async def retry_run(
    run_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> RetryAck:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        row = session.get(JobRun, run_id)
        if row is None or row.user_id != user.id:
            # Don't leak existence of someone else's run.
            raise HTTPException(status_code=404, detail="job_run not found")

    await request.app.state.scheduler.run_retry(run_id=run_id)
    return RetryAck(run_id=run_id, retry_scheduled=True)
```

- [ ] **Step 9: Implement `routes/notifications.py`**

Create `packages/server/src/openlia_server/routes/notifications.py`:

```python
"""Notification polling endpoints (no SSE in v1)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from openlia_server.auth.deps import get_current_user  # Plan 2
from openlia_server.db.models.auth import User
from openlia_server.scheduler.services import notifications as notif_service


router = APIRouter(prefix="/notifications", tags=["notifications"])


class UnreadOut(BaseModel):
    by_department: dict[str, int]
    total: int


class ReadIn(BaseModel):
    department: str


class ReadOut(BaseModel):
    marked_read: int


@router.get("/unread", response_model=UnreadOut)
def unread(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> UnreadOut:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        by_dept = notif_service.unread_counts_by_department(
            session=session, user_id=user.id
        )
        total = notif_service.unread_total(
            session=session, user_id=user.id
        )
    return UnreadOut(by_department=by_dept, total=total)


@router.post("/read", response_model=ReadOut)
def mark_read(
    body: ReadIn,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> ReadOut:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        n = notif_service.mark_department_read(
            session=session, user_id=user.id, department=body.department
        )
        session.commit()
    return ReadOut(marked_read=n)
```

- [ ] **Step 10: Register routers in `app.py`**

Add two imports + two `include_router` calls inside `create_app()`:

```python
from openlia_server.routes import jobs as jobs_router
from openlia_server.routes import notifications as notifications_router
# ...
def create_app() -> FastAPI:
    app = FastAPI(title="OpenLIA", version="0.1.0", lifespan=_lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(jobs_router.router)
    app.include_router(notifications_router.router)

    return app
```

- [ ] **Step 11: Run all route tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_scheduler/test_routes_jobs.py packages/server/tests/test_scheduler/test_routes_notifications.py -v`
Expected: all pass.

- [ ] **Step 12: Commit**

```bash
git add packages/server/src/openlia_server/routes/jobs.py \
    packages/server/src/openlia_server/routes/notifications.py \
    packages/server/src/openlia_server/app.py \
    packages/server/src/openlia_server/scheduler/service.py \
    packages/server/tests/test_scheduler/test_routes_jobs.py \
    packages/server/tests/test_scheduler/test_routes_notifications.py \
    packages/server/tests/test_scheduler/test_scheduler_service.py
git commit -m "phase-6(scheduler): jobs + notifications HTTP routes + run_retry"
```

---

## Task 16: End-to-end integration test

**Files:**
- Create: `packages/server/tests/test_scheduler/test_lifespan_integration.py`

This test exercises the whole chain: SchedulerService registered through `wiring.build_scheduler_service`, a seeded `MbSchedule`, the `FakeAPScheduler.fire()` helper to trigger the callback, and assertions on the final state (`job_runs`, `user_notifications`, report saved, `mb_schedules.last_run_at` updated). This is our "nothing is silently mocked past the seam we actually want to mock" test.

- [ ] **Step 1: Write the integration test**

Create `packages/server/tests/test_scheduler/test_lifespan_integration.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from _fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeMBBuilder,
    FakeReportRunner,
    FakeReportStore,
)
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import (
    JobRun,
    MbSchedule,
    UserNotification,
)
from openlia_server.scheduler.registry import (
    JobStatus,
    JobType,
    job_key,
)
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


@pytest.mark.asyncio
async def test_end_to_end_morning_briefing_fires_saves_and_notifies(
    session_factory,
) -> None:
    # --- seed ---
    with session_factory() as s:
        s.add(
            User(
                id="u_1", email="u@e.com", display_name="u",
                password_hash="h", is_admin=False, is_disabled=False,
            )
        )
        s.add(
            MbSchedule(
                id="sch_mb", user_id="u_1",
                time="07:00", timezone="UTC",
                days_of_week='["mon","tue","wed","thu","fri"]',
                label="Pre-Market", is_enabled=True,
                created_at=datetime.now(timezone.utc),
                last_run_at=None,
            )
        )
        s.commit()

    # --- real executor graph, fake APScheduler + fake runners/builders ---
    fake_scheduler = FakeAPScheduler()
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=fake_scheduler,
        report_runner=FakeReportRunner(
            events=[
                ReportStart(
                    report_id="r_1", department="morning_briefing",
                    mode="mb", section_titles=["Overnight"],
                ),
                ReportComplete(
                    report_id="r_1",
                    schema={"title": "Briefing", "sections": []},
                ),
            ]
        ),
        batch_runner=FakeBatchRunner(results=[]),
        mb_builder=FakeMBBuilder(
            request=ReportRequest(mode="morning_briefing", user_input="go")
        ),
        report_store=FakeReportStore(next_id="rep_final"),
    )
    await svc.start()

    # Confirm the schedule was rehydrated.
    key = job_key(JobType.MB_BRIEFING, "u_1")
    assert key in fake_scheduler.jobs

    # --- fire the scheduled callback ---
    await fake_scheduler.fire(key)

    # --- asserts ---
    with session_factory() as s:
        runs = s.query(JobRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == JobStatus.COMPLETED.value
        assert run.user_id == "u_1"
        assert run.job_type == JobType.MB_BRIEFING.value
        assert json.loads(run.result_summary) == {"report_id": "rep_final"}

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].department == "morning_briefing"

        sched = s.get(MbSchedule, "sch_mb")
        assert sched.last_run_at is not None

    await svc.shutdown()
    assert fake_scheduler.stopped is True
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `uv run pytest packages/server/tests/test_scheduler/test_lifespan_integration.py -v`
Expected: PASS.

- [ ] **Step 3: Full-suite check**

Run the whole scheduler test tree + app tests:

```bash
uv run pytest packages/server/tests/test_scheduler/ packages/server/tests/test_app_lifespan.py -v
```

Expected: all pass (no red, no warnings about unawaited coroutines).

- [ ] **Step 4: Commit**

```bash
git add packages/server/tests/test_scheduler/test_lifespan_integration.py
git commit -m "phase-6(scheduler): end-to-end integration test (seed -> fire -> report + notif)"
```

- [ ] **Step 5: Flip README.md**

Modify `planning/implementation-plans/README.md`: change the Plan 6 row from "Not started" to `[Draft](2026-04-17-phase-6-background-task-scheduling.md)`.

---

## Self-review (plan author)

Spec: `planning/specs/systems/background-task-scheduling-design.md`.

| Spec section | Plan coverage |
|---|---|
| Job types (4: mb_briefing, eu_scan, mr_assessment, system_maintenance) | Task 2 (`JobType` enum) |
| Job key format `{type}:{user_id}` + maintenance singleton | Task 2 (`job_key`, `MAINTENANCE_JOB_KEY`) |
| `job_runs` table read/write | Task 3 (`services/jobs.py`) |
| `user_notifications` table read/write | Task 4 (`services/notifications.py`) |
| Crash recovery (running → cancelled) | Task 5 (`mark_orphans_cancelled`) + Task 13 startup |
| Missed-job catch-up inside grace window | Task 5 (`should_catch_up`) + Task 13 `_maybe_backfill` |
| Executor lifecycle (start_run → complete/fail/cancel, retry up to 3 with 30/120/480s backoff) | Task 8 (`BaseExecutor`) |
| MB executor: single ReportRunner call, save, update last_run_at, one notification | Task 10 |
| EU executor: planner + sequential per-ticker, one notification per report | Task 11 |
| MR executor: BatchRunner(T4) → synthesize → ReportRunner(T5) → cache | Task 12 |
| Maintenance executor: nightly prune sweep (sessions, password resets, mr_assessment_cache, rs_snapshots, notifications, job_runs) | Task 9 |
| APScheduler lifecycle (startup rehydrate, shutdown w/ 30s grace) | Task 13 |
| Hot-reload on schedule CRUD (add/modify/remove) | Task 13 + Task 15 (routes will call this in Plans 15/16) |
| Disabled user: yank all their jobs | Task 13 (`remove_all_for_user`) |
| Env vars (`OPENLIA_SCHEDULER_ENABLED`, misfire grace, shutdown grace) | Task 1 (`SchedulerSettings`) |
| `GET /jobs/history` | Task 15 |
| `POST /jobs/{run_id}/retry` | Task 15 (also extends `SchedulerService.run_retry`) |
| `GET /notifications/unread` + `POST /notifications/read` | Task 15 |
| Polling (no SSE) | Task 15 (routes) + implied by Task 4 service shape |

**Known deferrals** (noted in the relevant tasks):

- **MR scheduling rehydration.** `mr_dashboard_state` in Plan 1B does not carry `assessment_schedule` / `last_assessment_at`. The `MRAssessmentExecutor` is fully implemented in Task 12 so Plan 19 can drop it in; Plan 19 will add the columns and call `SchedulerService.add_schedule` for dashboards after the user opts in.
- **Department payload builders** (`MBRequestBuilder`, `EUScanPlanner`, `MRAssessmentBuilder`, `ReportStore`, `MRCacheStore`) are Protocol + fail-fast stub now. Plans 13/15/16/19 replace stubs with real implementations in `wiring.py`.
- **Real APScheduler version.** Drafted against APScheduler 4.x pre-1.0. If the final 4.x API names shift, the plan executor should adjust method names (`start_in_background`, `stop`, `add_schedule(func, trigger, id=..., args=...)`, `remove_schedule(id)`, `get_schedules()`) and amend the plan in-place.

**Placeholders found on author review:** none. Every step includes complete code. Type names used in later tasks (`JobOutcome`, `NotificationSpec`, `ReportStore`, `MRCacheStore`, `EUScanTarget`, `MRAssessmentPayload`, `CancellationToken`, runner shapes) match their definitions in earlier tasks.

**Type-consistency spot checks:**

- `SchedulerService._run_job(job_type, user_id, schedule_id)` signature matches every `scheduler.add_schedule(..., args=(job_type, user_id, schedule_id))` call (Tasks 13, 15).
- `BaseExecutor.execute(user_id, schedule_id, cancel_token, retry_of=None)` is the shape used by `_run_job` and every route that invokes an executor directly.
- `MRAssessmentPayload.synthesize` is a `Callable[[list[BatchResult]], ReportRequest]` — same in Task 6 (definition), Task 7 (fake), Task 12 (consumer).
- `JobOutcome(result_summary, notifications)` — dict + list[NotificationSpec] — same in Task 8 (base), Tasks 9/10/11/12 (subclasses).

