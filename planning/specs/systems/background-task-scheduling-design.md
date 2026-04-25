# Background Task Scheduling System Design

Server-side background task scheduling for OpenLIA. Runs department jobs (Morning Briefing reports, Earnings Update scans, Macro Research assessments) and system maintenance on configured schedules, independent of whether any user has the app open.

## Scope

### In scope

- Scheduler lifecycle (startup, shutdown, crash recovery)
- Job types and their trigger configurations
- Per-user schedule management (CRUD, hot-reload without restart)
- Missed job catch-up on restart
- Execution model (how a job runs, what it produces, where results go)
- Failure handling (retries, failure records, user-visible error state)
- DB tables for job run history and user notifications
- Notification mechanism (polling-based, sidebar dots)
- Cross-reference edits to other specs

### Out of scope

- Frontend auto-refresh timers (PT, MR T1/T2, RS) -- those are client-side polling intervals, not server background tasks.
- Department logic itself (how MB generates a briefing, how EU scans earnings) -- owned by department specs and `llm-runtime-design.md`.
- Multi-instance coordination -- v1 is single-process. Multi-instance job locking deferred to v2.
- MR T4/T5 news-triggered assessments -- manual "Run assessment now" button only in v1. See dev note.

---

## Stack

| Concern | Choice |
|---|---|
| Scheduler library | APScheduler 4.x (async mode) |
| Job store | In-memory (rebuilt from DB on startup) |
| Process model | Runs inside the FastAPI process via `lifespan` hook |
| Schedule source of truth | Department-specific DB tables (`mb_schedules`, `eu_schedules`, `mr_dashboard_state`) |
| Job history | `job_runs` table |
| Notifications | `user_notifications` table, frontend polling |

### Why APScheduler with in-memory job store

APScheduler handles the hard parts: timezone-aware cron scheduling, misfire catch-up, async execution, job coalescing. The in-memory job store is sufficient because our DB tables are already the durable source of truth for what schedules exist -- APScheduler is rebuilt from them on every startup. A persistent APScheduler job store (SQLite-backed) was considered but rejected: it would duplicate schedule information already in department tables, creating two sources of truth and sync bugs.

### Why not Celery or other distributed schedulers

OpenLIA is self-hosted and targets single-process deployments in v1. Celery requires a separate broker process (Redis or RabbitMQ), adding operational complexity that contradicts the zero-ops design goal. APScheduler runs in-process with no external dependencies.

---

## Job Types

### 1. Morning Briefing (`mb_briefing`)

- **Trigger:** Cron (user-configured time, timezone, days of week).
- **Scope:** Per-user. Each user can have multiple schedules (e.g. pre-market and post-market).
- **Execution:** Calls `ReportRunner` with the user's MB section/topic configuration. Collects the full report (no SSE streaming for background jobs). Stores the completed report in the DB. Marks a notification for the user.
- **Schedule source:** `mb_schedules` table rows.

### 2. Earnings Update scan (`eu_scan`)

- **Trigger:** Cron (user-configured time, timezone, days of week).
- **Scope:** Per-user. Each user can have multiple scan schedules (e.g. pre-market scan to catch overnight releases, post-market scan to catch after-hours releases).
- **Execution:** Fetches latest earnings dates for all tickers in the user's EU watchlist. For any company that has released earnings since the last scan, calls `ReportRunner` to generate an analysis report -- sequentially, one ticker at a time. Stores each report in the DB. Marks a notification per report.
- **Schedule source:** `eu_schedules` table rows.

### 3. Macro Research assessment (`mr_assessment`)

- **Trigger:** Cron (weekly or quarterly, user-configurable).
- **Scope:** Per-user. One assessment job per user who has MR enabled.
- **Execution:** Fetches current macro data, runs T4 LLM assessment via `BatchRunner`, then runs T5 synthesis (consuming T1+T2+T4 outputs). Caches results in `mr_assessment_cache`. Marks a notification for the user.
- **Schedule source:** `mr_dashboard_state` table (assessment schedule column).
- **v1 constraint:** The "on news trigger" schedule option described in `macro-research-dalio-dashboards-design.md` is manual-only in v1 -- the user clicks "Run assessment now" in the MR UI. The scheduler only handles the weekly and quarterly cron options.

> **Dev note (v2):** Automatic news-triggered MR assessments. The server would periodically poll news feeds (e.g. every 30 min), run keyword matching against the user's configured trigger keywords, and fire a T4/T5 assessment if a significant match is found. Design considerations: defining "significant," deduplicating triggers across polling cycles, rate-limiting LLM cost for users with sensitive keyword lists, and interaction with the existing weekly/quarterly schedule (skip the next scheduled run if a trigger already ran recently).

### 4. Nightly maintenance (`system_maintenance`)

- **Trigger:** Once on server startup, then daily interval (configurable, default 24 hours).
- **Scope:** System-wide (not per-user).
- **Execution:** Runs the pruning sweep defined in `database-design.md`:

| Target | Rule |
|---|---|
| `sessions` | Delete where `expires_at < now() - 7 days`. |
| `password_reset_requests` | Flip to `expired` where `status = 'approved' AND expires_at < now()`. Delete rows older than 90 days. |
| `mr_assessment_cache` | Delete where `expires_at < now() - 30 days`. |
| `rs_snapshots` | Delete where `captured_at < now() - <retention_days>`. |
| `user_notifications` | Delete where `created_at < now() - 30 days`. |

- **Schedule source:** Hardcoded in the scheduler startup code (not user-configurable).

### Job concurrency model

Jobs run sequentially within a user's scope -- if User A's 7:00 AM briefing is still generating when their 7:05 AM EU scan is due, the scan waits. But User A's jobs and User B's jobs can run in parallel. The maintenance job runs independently of user jobs.

APScheduler's `max_running_jobs` per-job-type setting enforces this. Each user-scoped job is keyed as `{job_type}:{user_id}` with `max_instances=1`. The maintenance job has its own single-instance key.

---

## Scheduler Lifecycle

### Startup sequence

1. FastAPI `lifespan` hook initializes the APScheduler `AsyncScheduler`.
2. Scheduler queries the DB for all active schedules across all users (`mb_schedules`, `eu_schedules`, `mr_dashboard_state`).
3. For each schedule row, registers an APScheduler job with the appropriate cron trigger.
4. Registers the single system maintenance job (daily interval + immediate first run).
5. **Missed job catch-up:** For each schedule, compares `last_run_at` (from the most recent `job_runs` row for that schedule) against the most recent scheduled time that should have fired. If a job was missed within the misfire grace window (default 6 hours), fires it immediately. Missed jobs older than the grace window are skipped -- a stale 7 AM briefing at 3 PM is not useful.
6. **Crash recovery:** Any `job_runs` rows still in `status=running` from a prior server session are marked `status=cancelled` with `error_message="Server restarted during execution"`.
7. Scheduler starts.

### Shutdown sequence

1. FastAPI `lifespan` shutdown signal triggers graceful scheduler shutdown.
2. Currently executing jobs are given a grace period (default 30 seconds) to finish. If a job is mid-LLM-call, it uses the `CancellationToken` from `llm-runtime-design.md` to signal the runner to stop.
3. Jobs that don't finish within the grace period are cancelled. Their run is recorded as `status=cancelled` in `job_runs`.
4. Scheduler shuts down.

### Hot-reload (schedule CRUD while server is running)

When a user adds, edits, or removes a schedule via Settings or a department page:

1. The route handler writes the change to the DB (insert/update/delete the schedule row).
2. The route handler calls the `SchedulerService` to sync: add, modify, or remove the corresponding APScheduler job in memory.
3. No server restart needed. The change takes effect immediately for the next scheduled fire time.

### Disabled users

When an admin disables a user (`is_disabled = true`), the scheduler removes all of that user's jobs from the in-memory APScheduler. Schedule rows remain in the DB (not deleted) so they can be restored if the user is re-enabled. On re-enable, the scheduler rebuilds that user's jobs from their existing schedule rows.

---

## Execution Model

### How a job runs

1. APScheduler fires the job at the scheduled time, calling an async executor function.
2. The executor inserts a `job_runs` row with `status=running`, `started_at=now()`, `attempt=1`.
3. The executor resolves the user's configuration for that department (MB sections/topics, EU watchlist tickers, MR assessment settings).
4. The executor calls the appropriate runner:
   - **MB:** `ReportRunner.run(department_id="morning_briefing", user_id=..., request=...)` -- collects the full report from the async iterator (no SSE streaming for background jobs, events are consumed internally).
   - **EU:** Data fetch first (check each watchlist ticker for new earnings since `last_run_at`). Then `ReportRunner.run(...)` for each ticker with new earnings, sequentially.
   - **MR:** `BatchRunner.run(...)` for T4 assessment, then T5 synthesis consuming T4 output.
   - **Maintenance:** Direct DB queries for pruning (no LLM involvement).
5. On success: store the report/result in the appropriate table, update `job_runs` to `status=completed` with `result_summary`, update the schedule's `last_run_at`.
6. Insert a `user_notifications` row for the user.

### Retry on failure

1. If the runner raises a **transient error** (network timeout, rate limit, provider temporarily unavailable -- error classes defined in `llm-provider-design.md`), retry up to 3 times with exponential backoff: 30s, 120s, 480s.
2. Each retry increments `attempt` on the same `job_runs` row and updates `error_message` with the latest error.
3. If all retries fail or a **non-transient error** occurs (invalid API key, model not found, `TierNotConfiguredError`):
   - Update `job_runs` to `status=failed` with `error_message`.
   - Insert a `user_notifications` row with `type=job_failed` so the user sees the failure in their department UI.
4. A failed job does not block future runs of the same schedule. The next scheduled time fires normally.

### User-triggered retry

When the user clicks "Retry" on a failed job record in the department UI:

1. The frontend calls `POST /jobs/{run_id}/retry`.
2. The server creates a new `job_runs` row with `retry_of` pointing to the original failed run.
3. The job executes immediately as a one-off (not through APScheduler's scheduler -- direct async call).
4. Same execution path and failure handling as a scheduled run.

---

## Data Model

### `job_runs` table

History of every scheduled job execution.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | text | PK | UUID |
| `user_id` | text | FK -> users.id, nullable | NULL for `system_maintenance` |
| `job_type` | text | NOT NULL | `mb_briefing`, `eu_scan`, `mr_assessment`, `system_maintenance` |
| `schedule_id` | text | nullable | FK to the department-specific schedule table row. NULL for maintenance and user-triggered retries. |
| `status` | text | NOT NULL | `running`, `completed`, `failed`, `cancelled` |
| `started_at` | text | NOT NULL | ISO 8601 |
| `completed_at` | text | nullable | ISO 8601 |
| `error_message` | text | nullable | NULL on success |
| `result_summary` | text | nullable | JSON. E.g. `{"reports_generated": 3, "report_ids": [...]}` for EU, `{"report_id": "..."}` for MB. |
| `retry_of` | text | FK -> job_runs.id, nullable | Points to the original failed run if this is a user-triggered retry. |
| `attempt` | integer | NOT NULL, default 1 | 1 for first try, 2-4 for automatic retries. |

**Indexes:**
- `ix_job_runs_user_type_started` on `(user_id, job_type, started_at)` -- listing a user's job history filtered by type.
- `ix_job_runs_status` on `(status)` -- finding `running` rows on startup for crash recovery.
- `ix_job_runs_schedule` on `(schedule_id, started_at)` -- finding the most recent run for a schedule (catch-up logic).

### `user_notifications` table

Lightweight notification records for background job results.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | text | PK | UUID |
| `user_id` | text | FK -> users.id, NOT NULL | |
| `type` | text | NOT NULL | `report_ready`, `assessment_ready`, `job_failed` |
| `department` | text | NOT NULL | `morning_briefing`, `earnings_update`, `macro_research` |
| `message` | text | NOT NULL | Human-readable summary |
| `job_run_id` | text | FK -> job_runs.id, nullable | Links to the job that produced this notification |
| `created_at` | text | NOT NULL | ISO 8601 |
| `read_at` | text | nullable | NULL until read |

**Indexes:**
- `ix_notifications_user_unread` on `(user_id, read_at)` -- fast unread count query (WHERE read_at IS NULL).

**Retention:** Notifications older than 30 days are pruned by the nightly maintenance sweep.

### Department schedule tables

Schedule storage lives in department-specific tables. The scheduler queries all three on startup.

**`mb_schedules`** -- already implied by the MB spec's schedule settings UI. Columns: `id`, `user_id`, `time` (HH:MM), `timezone`, `days_of_week` (JSON array), `label`, `is_enabled`, `created_at`, `last_run_at`.

**`eu_schedules`** -- new table, mirrors `mb_schedules`. Columns: `id`, `user_id`, `time` (HH:MM), `timezone`, `days_of_week` (JSON array), `label`, `is_enabled`, `created_at`, `last_run_at`.

**`mr_dashboard_state`** -- already defined in `database-design.md`. Assessment schedule column: `assessment_schedule` stores a 5-field cron expression in UTC (shipped contract); service-layer helpers accept the shorthands `weekly` / `quarterly` and expand them to cron before persisting. `last_assessment_at` captures the most recent successful assessment for catch-up logic.

No unified `scheduled_jobs` table. The scheduler queries the three department tables directly. This keeps schedule ownership with the department that defines it.

---

## Server Integration

### File layout

```
packages/server/src/openlia_server/
├── scheduler/
│   ├── __init__.py          # SchedulerService export
│   ├── service.py           # SchedulerService: init, startup, shutdown, hot-reload
│   ├── executors.py         # Job executor functions (mb_briefing, eu_scan, mr_assessment, maintenance)
│   └── recovery.py          # Missed-job detection and catch-up logic
```

This lives in the server package, not core. The scheduler orchestrates calls to core's runners but is itself a server concern -- it depends on the DB, the FastAPI lifecycle, and user session context. Core remains pure with no scheduling awareness.

### FastAPI integration

The scheduler is initialized and torn down via the FastAPI `lifespan` context manager:

```python
# app.py (simplified)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = SchedulerService(db=get_session, ...)
    await scheduler.startup()       # build jobs from DB, catch up missed, start
    app.state.scheduler = scheduler
    yield
    await scheduler.shutdown()      # graceful stop with grace period
```

Route handlers that modify schedules access the scheduler through `request.app.state.scheduler`:

```python
# routes/morning_briefing.py (simplified)
@router.post("/mb/schedules")
async def create_schedule(request: Request, payload: MBScheduleCreate):
    schedule = db.create_mb_schedule(payload)
    request.app.state.scheduler.add_job(schedule)
    return schedule
```

### API surface

Cross-cutting endpoints added by this spec:

| Method | Path | Purpose |
|---|---|---|
| GET | `/jobs/history` | List job runs for the current user. Query params: `job_type`, `status`, `since`, `limit`, `offset`. Paginated. |
| POST | `/jobs/{run_id}/retry` | Retry a failed job run. Returns the new `job_runs` row. |

Department-specific schedule CRUD endpoints (create/edit/delete schedules) belong to each department's own route file, not here. This spec only adds the cross-cutting job history and retry surface.

Notification endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/notifications/unread` | Returns `{total: N, by_department: {"morning_briefing": 2, "earnings_update": 1, ...}}`. |
| POST | `/notifications/read` | Body: `{department: "morning_briefing"}`. Marks matching unread notifications as read for the current user. |

---

## Notifications

### Mechanism

Polling-based. No real-time push (SSE/WebSocket) for notifications in v1.

1. When a job completes or fails, the executor inserts a `user_notifications` row.
2. The frontend polls `GET /notifications/unread` on a regular interval (every 60 seconds while the app is open) and on page navigation.
3. The response includes unread counts per department. The sidebar renders notification dots per department based on these counts.
4. When the user navigates to the relevant department page, the frontend calls `POST /notifications/read` with the department, marking those notifications as read and clearing the dot.

### Notification types

| Type | Department | Message example |
|---|---|---|
| `report_ready` | morning_briefing | "Your 7:00 AM Pre-Market briefing is ready." |
| `report_ready` | earnings_update | "New earnings analysis: AAPL Q2 2026." |
| `assessment_ready` | macro_research | "T4/T5 macro assessment updated." |
| `job_failed` | morning_briefing | "Your 7:00 AM briefing failed: LLM provider unreachable." |
| `job_failed` | earnings_update | "Earnings scan failed: data provider timeout." |
| `job_failed` | macro_research | "T4 assessment failed: Thinking tier not configured." |

---

## Configuration

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENLIA_SCHEDULER_ENABLED` | `true` | Set to `false` to disable all background scheduling. Server starts normally but no jobs fire. Useful for development and testing. |
| `OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS` | `21600` (6 hours) | Missed jobs older than this are skipped on catch-up. |
| `OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS` | `30` | Time to wait for running jobs to finish on shutdown. |

These are ops-level knobs with sensible defaults. No DB `config_store` equivalent -- not user-facing.

### Per-user settings

Stored in department tables, surfaced in department UIs:

- **MB:** Schedule time, timezone, days of week, label. Via MB Settings view (already specced in `MorningBriefingsPageSpec.md`).
- **EU:** Schedule time, timezone, days of week, label. Via EU Settings (cross-reference edit pending -- see below).
- **MR:** Assessment frequency: weekly / quarterly. Via MR Settings (already specced in `macro-research-dalio-dashboards-design.md`).

### Default schedules for new users

No default schedules are created automatically. Users must explicitly add their first schedule. This avoids surprise LLM costs and aligns with existing specs -- MB's empty state says "Configure a schedule in Settings to start receiving your morning briefings automatically."

---

## Related Specs

The scheduler is intentionally cross-cutting. The pieces it depends on, or that depend on it, live elsewhere:

| Spec | What lives there |
|---|---|
| `database-design.md` | Authoritative schema for `job_runs`, `user_notifications`, `mb_schedules`, `eu_schedules`, `mr_dashboard_state`. Nightly maintenance sweep (notification pruning at 30 days) is also defined there. |
| `projectStructure.md` | `packages/server/src/openlia_server/scheduler/` directory layout. |
| `MorningBriefingsPageSpec.md` | MB schedule UI (time, timezone, days of week, multiple schedules per user) and per-section configuration that the `mb_briefing` executor consumes. |
| `EarningsUpdatePageSpec.md` | EU schedule UI (mirrors MB pattern) and watchlist configuration that the `eu_scan` executor consumes. |
| `macro-research-dalio-dashboards-design.md` | T4/T5 assessment schedule (Quarterly / Weekly) consumed by the `mr_assessment` executor. v1 is schedule-driven only; news-triggered runs are manual ("Run assessment now"). |
| `AccountManagementSpec.md` | User-scoped tables include `user_notifications`; disabled-user behavior (jobs do not fire while `users.is_disabled = true`) is enforced here. |
| `SideBarSpec.md` | Notification dot mechanism (polling `GET /notifications/unread`, per-department dots, clear on page visit). |
| `cli-surface-design.md` | `openlia maintenance` runs the same nightly sweep manually (notification pruning, expired session cleanup). |

---

## Testing Strategy

### Unit

- Missed-job detection: various `last_run_at` vs current time vs grace window scenarios.
- Crash recovery: `running` rows from prior sessions marked `cancelled` on startup.
- Retry backoff timing: 30s, 120s, 480s exponential sequence.
- Job key construction: `{job_type}:{user_id}` uniqueness.
- Notification unread count aggregation by department.

### Integration

- Full lifecycle: create schedule -> scheduler picks it up -> job fires -> report stored -> notification created -> user reads notification.
- Hot-reload: add/edit/remove schedule while server is running, verify APScheduler reflects the change.
- Failure path: mock LLM provider failure -> verify retry attempts -> verify failure record and notification.
- User-triggered retry: fail a job -> retry via API -> verify new `job_runs` row with `retry_of` link.
- Catch-up on startup: stop server, advance clock past a scheduled time, restart, verify missed job fires.

### Edge cases

- Multiple EU earnings in one scan (3 tickers released earnings -- sequential report generation, one notification per report).
- Concurrent users: User A's job running while User B's fires in parallel.
- Schedule deleted while job is running (job completes normally, no future runs).
- User disabled/deleted (admin disables user -- their scheduled jobs should not fire).

---

## Non-Goals (v1)

- Real-time push notifications (SSE/WebSocket) for job completion -- polling is sufficient.
- Multi-instance job coordination / distributed locking.
- MR T4/T5 automatic news-triggered assessments (manual "Run now" only).
- Job priority / queue weighting between users.
- Admin dashboard for viewing all users' job history (admin can query the DB directly).
- Email/SMS delivery of completed reports (v1 is in-app only).
- Retry policies configurable per user or per department (global 3-retry policy).

---

## Open Questions

1. **EU scan efficiency at scale.** If a user has 50 tickers in their watchlist, the scan checks all 50 for new earnings every run. Should the scan use a bulk earnings-calendar API call (one request for all tickers) or per-ticker lookups? Depends on data provider capabilities -- resolve during implementation.
2. **Concurrent report generation limit.** If 10 users all have 7:00 AM MB schedules, the server fires 10 parallel ReportRunner calls. Should there be a global concurrency cap to avoid overwhelming the LLM provider? APScheduler supports `max_running_jobs` globally, but the right limit depends on the provider's rate limits. Consider a configurable `OPENLIA_SCHEDULER_MAX_CONCURRENT_JOBS` env var.
3. **Notification retention vs job_runs retention.** Notifications are pruned at 30 days. Should `job_runs` rows also be pruned, or kept indefinitely for audit? Leaning toward pruning completed runs older than 90 days, keeping failed runs longer.
