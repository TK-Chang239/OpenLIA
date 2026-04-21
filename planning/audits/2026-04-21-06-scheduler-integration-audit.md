# Scheduler Integration Audit

Date: 2026-04-21

Scope: scheduler service lifecycle, route integration, executor wiring,
department payload builders, notifications, and future department schedule
plans.

Validation commands run: none. Static audit only.

## Executive Summary

The scheduler core is relatively complete and well-tested. It starts,
rehydrates MB/EU schedules, registers maintenance, supports retries, records
job runs, cancels on shutdown, and exposes job/notification routes with real
auth. The main risk is integration with future departments: scheduler wiring
currently injects stubs, app startup passes `report_runner=None` and
`batch_runner=None`, and no real EU/MB/MR payload builders are wired yet.

## Current Scheduler Baseline

Implemented:

- `SchedulerService`
- APScheduler adapter in app lifespan
- MB/EU schedule models
- job runs
- user notifications
- base executor retry/cancel semantics
- MB/EU/MR/Maintenance executors
- startup orphan cancellation
- missed-job catch-up within grace window
- `/jobs/history`
- `/jobs/{run_id}/retry`
- `/notifications/unread`
- `/notifications/read`

## Findings

### 1. High - App Startup Uses Stub Department Builders

`build_scheduler_service()` defaults to:

- `StubMBRequestBuilder`
- `StubEUScanPlanner`
- `StubMRAssessmentBuilder`
- `StubReportStore`
- `StubMRCacheStore`

`app.py` currently passes `report_runner=None` and `batch_runner=None`.

Impact: if a user has enabled schedules before real builders are wired, fired
jobs can fail as planned stubs. This is acceptable during phases, but not for
final product.

Required fix:

- Each department plan must update scheduler wiring with real implementations.
- App startup must construct real `ReportRunner`, `BatchRunner`, and stores.
- Tests must prove the production `create_app()` path wires real dependencies.

### 2. High - Future Plan 15 Must Use Existing Scheduler Hot-Reload API

Plan 15 adds EU watchlist/config/schedules. It must integrate with:

- `SchedulerService.add_schedule(schedule)`
- `modify_schedule(schedule)`
- `remove_schedule(job_type=..., user_id=...)`
- existing `eu_schedules` table

Risk: route snippets in Plan 15 still use stale auth/session helpers and may
build a parallel schedule surface that does not hot-reload APScheduler.

Required fix:

- Rewrite Plan 15 routes as factories.
- After DB schedule create/update/delete, call app scheduler hot-reload API.
- Test with fake scheduler through `create_app()`.

### 3. Medium - Retry Endpoint Assumes Scheduler Exists

`/jobs/{run_id}/retry` accesses `request.app.state.scheduler`. If scheduler is
disabled, this state is `None`.

Impact: with `OPENLIA_SCHEDULER_ENABLED=false`, routes can fail if called.

Required fix:

- Return 503 or clear error when scheduler disabled.
- Add route tests for scheduler disabled mode.

### 4. Medium - Notification Read Route Commits Locally

`notifications.mark_read` commits inside the route because the scheduler
notification service does not own commits.

Impact: acceptable, but future route session patterns should keep transaction
ownership explicit and consistent.

Required fix:

- Document route-level transaction ownership.
- Prefer local `make_session_dependency` where not using scheduler
  `session_factory`.

### 5. Medium - MR Startup Rehydration Is Deferred

Scheduler service rehydrates MB and EU schedules. MR executor exists but MR
schedule persistence is deferred to a later plan.

Impact: Plan 19 must explicitly add MR schedule state and startup registration.

Required fix:

- Add MR schedule fields/table in Plan 19.
- Register MR jobs on startup or through department startup path.

## Scheduler Acceptance Tests Needed

Before final product:

- `create_app()` with real runners executes an EU scan end to end.
- EU watchlist + schedule creates report and notification.
- Retry creates a new one-shot run and preserves ownership checks.
- Disabled scheduler returns controlled errors from jobs/notifications routes.
- User deletion removes schedules and registered APScheduler jobs.
- App shutdown cancels active jobs and marks rows consistently.
