# Phase 6 — Background Task Scheduling fix plan (to 100%)

**Current:** ~92% shipped. **Root cause:** IMPLEMENTER.

**Gap summary.** Scheduler core (APScheduler bootstrap, `SchedulerService`
lifecycle, per-job-type executors, `job_runs` + `user_notifications` writes,
hot-reload CRUD, misfire catch-up, crash recovery, `/jobs/*` and
`/notifications/*` routes) all shipped. Four classes of residual defects:

1. Two live wiring bugs in `app.py` that render scheduled MR unusable
   (P0-04, P0-05).
2. Stub builders still in the wiring fallback path (`StubMB…`, `StubEU…`,
   `StubMR…`, `StubReportStore`) — they raise `DepartmentPayloadBuilderNotWired`
   at fire time, masquerading as a controlled error but failing every real
   scheduled job when the real wiring path isn't taken.
3. Minor docstring / packaging polish (P2-05, P2-06).
4. Coverage gaps: no integration test asserts production `create_app()`
   wires a non-None `batch_runner`; no test catches the dual-instance MR bug;
   no test exercises the `/jobs/{run_id}/retry` route against a disabled
   scheduler; no spec/code check for per-department concurrency caps.

**Acceptance for 100%:** all P0/P1 items green + verification commands pass
and the "Missing tests" list below is committed.

---

## P0 — live production failures

### P0-04 — Construct `BatchRunner` and inject into MR executor wiring

- **Severity:** P0 (master tracker id preserved).
- **Bug:** `packages/server/src/openlia_server/app.py:266` passes
  `batch_runner=None` into `build_scheduler_service(...)`. The MR executor
  at `packages/server/src/openlia_server/scheduler/executors/mr.py:74`
  calls `await self._batch_runner.run(...)` unconditionally — on first
  scheduled MR_ASSESSMENT fire the job raises `AttributeError: 'NoneType'
  object has no attribute 'run'`. `BaseExecutor.execute` catches it into
  `last_error_msg` and writes `job_runs.status='failed'` + a `job_failed`
  notification, so the job is visibly broken to every user who configured
  an MR schedule.
- **Files:**
  - `packages/server/src/openlia_server/app.py:260-276` — remove
    `batch_runner=None`; build a real runner.
  - `packages/server/src/openlia_server/services/runtime.py` — add
    `build_batch_runner(db_session_factory)` alongside the existing
    `build_chat_runner` / `build_report_runner` (lines 16–20).
  - `packages/server/src/openlia_server/scheduler/wiring.py:40` — keep
    `batch_runner` required; remove any default-to-None fallback.
  - `packages/server/src/openlia_server/scheduler/executors/mr.py:74` —
    remains unchanged; this fix is upstream.
- **Plan ref:** Task 12 (MRAssessmentExecutor), Task 14 (lifespan +
  `wiring.py`).
- **Spec ref:** `background-task-scheduling-design.md` §Execution Model
  ("MR: BatchRunner.run(...) for T4 assessment, then T5 synthesis…").
- **Acceptance:**
  1. `grep -n "batch_runner=None" packages/server/src/openlia_server/app.py`
     returns no matches.
  2. A scheduled `JobType.MR_ASSESSMENT` run against a fake
     `MRAssessmentBuilder` + `FakeBatchRunner` produces
     `job_runs.status='completed'` and an `assessment_ready` notification.
  3. New test `test_mr_executor_batch.py::test_production_wiring_has_batch_runner`
     boots `create_app()` and asserts
     `app.state.scheduler.executors[JobType.MR_ASSESSMENT]._batch_runner is not None`.
- **Verification:** `uv run pytest
  packages/server/tests/test_scheduler/test_mr_executor.py
  packages/server/tests/test_app_lifespan.py -k mr_batch_runner`.

### P0-05 — Unify `MRScheduleService` — one instance, scheduler-bound

- **Severity:** P0 (master tracker id preserved).
- **Bug:** `app.py` constructs the service twice:
  - lifespan build at `app.py:280-282` — receives the live
    `scheduler_svc`;
  - factory build at `app.py:388` — `scheduler=None`.
  The factory instance is the one bound into `build_mr_schedule_router(
  ..., mr_schedule_service=mr_schedule_svc)` at `app.py:402-408`, so every
  `PUT /departments/macro_research/schedule` writes the DB row but skips
  `scheduler.modify_schedule` (guarded by `if self._scheduler is not None`
  at `services/mr_schedules.py:62`). Result: MR schedules configured via
  the UI are invisible to APScheduler until the next server restart
  (rehydration path).
- **Files:**
  - `packages/server/src/openlia_server/app.py:280-289` — keep the
    lifespan build, stash on `app.state.mr_schedule_service` (not
    `…_lifespan`), and set the factory-time `scheduler=None` build to
    late-bind via `app.state.mr_schedule_service`.
  - `packages/server/src/openlia_server/app.py:388-408` — change
    `build_mr_schedule_router(..., mr_schedule_service=...)` to accept a
    getter (`lambda: request.app.state.mr_schedule_service`) or rebuild
    the router during lifespan after the scheduler exists.
  - `packages/server/src/openlia_server/routes/mr_schedules.py:19-58` —
    read the service from `request.app.state` inside each handler instead
    of the closed-over factory argument (matches the `_require_scheduler`
    pattern in `routes/jobs.py:40` and `routes/notifications.py:30`).
- **Plan ref:** Task 13 (MR schedule service) + Task 14 (lifespan
  integration).
- **Spec ref:** `background-task-scheduling-design.md` §Hot-reload
  ("The route handler calls the `SchedulerService` to sync…No server
  restart needed").
- **Acceptance:**
  1. `grep -n "MRScheduleService(.*scheduler=None" packages/server/src/openlia_server/app.py`
     returns no matches.
  2. `PUT /departments/macro_research/schedule` with a running fake
     scheduler calls `scheduler.modify_schedule(...)` exactly once.
  3. New test `test_mr_schedules_live.py::test_upsert_registers_with_live_scheduler`
     asserts the schedule shows in `scheduler_svc._active_tokens` keys
     after the HTTP call (via `FakeAPScheduler.added_schedule_ids`).
- **Verification:** `uv run pytest
  packages/server/tests/test_routes/test_mr_schedules_live.py
  packages/server/tests/test_scheduler/test_lifespan_integration.py`.

### NEW-6-01 — Stub builders still reachable in the `or StubXxx()` fallback

- **Severity:** P0 (latent).
- **Bug:** `scheduler/wiring.py:47-51` keeps
  `mb_builder = mb_builder or StubMBRequestBuilder()`,
  `eu_planner or StubEUScanPlanner()`,
  `mr_builder or StubMRAssessmentBuilder()`,
  `report_store or StubReportStore()`,
  `mr_cache_store or StubMRCacheStore()`. Phase-6 audit (2026-04-21,
  lines 40-60) noted the stubs are acceptable "during phases"; they are
  not acceptable now that Phases 15/16/19 shipped real implementations.
  If a future caller forgets to pass any of the five, the scheduler
  silently installs a stub that raises `DepartmentPayloadBuilderNotWired`
  at fire time — recorded as `job_runs.status='failed'` with no build-time
  signal.
- **Files:**
  - `packages/server/src/openlia_server/scheduler/wiring.py:34-83` —
    make all five builders required keyword args (no defaults); delete
    the `or Stub…()` branches.
  - `packages/server/src/openlia_server/scheduler/payloads.py` — move
    the `StubXxx` classes under a `# test-only` banner and re-export only
    from `tests/test_scheduler/_scheduler_fakes.py`.
- **Plan ref:** Tasks 8–12 + Task 14 ("real implementations injected per
  department phase").
- **Spec ref:** §Execution Model is silent on stubs; the spec requires
  real builders for every shipping job type.
- **Acceptance:** `build_scheduler_service()` raises `TypeError` if any
  builder is omitted; `test_wiring.py::test_build_requires_real_builders`.
- **Verification:** `grep -n "Stub" packages/server/src/openlia_server/scheduler/wiring.py`
  returns no matches; prod test boot passes.

---

## P1 — silent correctness / spec drift

### NEW-6-02 — No production integration test for `create_app()` scheduler wiring

- **Severity:** P1.
- **Bug:** The 2026-04-21 audit (line 60) called for "tests must prove the
  production `create_app()` path wires real dependencies." No such test
  exists. `test_app_lifespan.py` asserts the scheduler starts but does
  not walk `app.state.scheduler.executors` to confirm the MB/EU/MR/
  Maintenance executors each hold non-stub collaborators.
- **Files:** new `packages/server/tests/test_app_lifespan.py::test_scheduler_wires_real_builders`.
- **Plan ref:** Task 14 (lifespan acceptance).
- **Spec ref:** §Server Integration (FastAPI lifespan example).
- **Acceptance:** Test asserts `type(executor._mb_builder).__name__ ==
  "MbRequestBuilderImpl"`, same for EU planner (`EuScanPlannerImpl`), MR
  builder (`MRAssessmentBuilderImpl`), MR cache (`MRCacheStoreImpl`), and
  that `_batch_runner` is not None for MR.

### NEW-6-03 — RS snapshot scheduling not yet a `JobType`

- **Severity:** P1 (master tracker NEW-20-01).
- **Bug:** Phase 20 review flagged Retail Sentiment should join the
  scheduler (`JobType.RS_SNAPSHOT`). Phase 6 registry
  (`scheduler/registry.py:14-19`) only lists MB/EU/MR/Maintenance; no
  RS executor exists (`scheduler/executors/` holds mr.py, eu.py, mb.py,
  maintenance.py — no rs.py). Spec §Job Types does not include RS today,
  but the Phase 20 spec requires it.
- **Files:**
  - `packages/server/src/openlia_server/scheduler/registry.py` — add
    `RS_SNAPSHOT = "rs_snapshot"` + department mapping.
  - `packages/server/src/openlia_server/scheduler/executors/rs.py` — new
    executor wrapping `RsRunner`.
  - `packages/server/src/openlia_server/scheduler/wiring.py` — inject.
  - `planning/specs/systems/background-task-scheduling-design.md` §Job
    Types — add Section 5 covering RS snapshot cron + cadence.
- **Plan ref:** cross-plan; belongs to Phase 20 delivery but Phase 6 must
  absorb the registry + wiring extension.
- **Spec ref:** Phase 20 spec + this file §Job Types (to amend).
- **Acceptance:** `JobType.RS_SNAPSHOT` exists; `test_wiring.py` includes
  RS; `scheduler/executors/rs.py` writes `job_runs` with department
  `retail_sentiment`.

### NEW-6-04 — No reschedule when user updates `user_config`

- **Severity:** P1.
- **Bug:** Task 13 and spec §Hot-reload cover schedule-row edits
  (`mb_schedules` / `eu_schedules` / `mr_dashboard_state.assessment_schedule`),
  but _department config_ changes (e.g. MB section list, EU watchlist
  delta, MR dashboard threshold overrides) do not trigger any scheduler
  refresh. Today that's correct for MB/MR because the payload builders
  read config at fire time, but EU's `eu_planner.plan()` also reads
  `user_id` + `since`, not the watchlist directly — so a just-added
  ticker does fire, but there is no test asserting that invariant. Add a
  regression test; if broken, add a hook.
- **Files:**
  - new `packages/server/tests/test_scheduler/test_config_change_reschedule.py`.
  - possible wiring: `packages/server/src/openlia_server/services/eu_watchlist.py`
    (on write, call `request.app.state.scheduler.modify_schedule` for the
    affected EU row — optional; only if test fails).
- **Plan ref:** Task 13 (hot-reload) + Phase 15 watchlist wiring.
- **Spec ref:** `background-task-scheduling-design.md` §Hot-reload +
  §Execution Model.
- **Acceptance:** Test adds ticker → fires schedule → executor plans the
  new ticker.

### NEW-6-05 — Per-department concurrency cap unenforced

- **Severity:** P1 (spec drift).
- **Bug:** Spec §Job concurrency model mandates
  "APScheduler's `max_running_jobs` per-job-type setting" with
  `max_instances=1` per `{job_type}:{user_id}` key. Current
  `scheduler/service.py:_register_schedule` (line 237) does not pass
  `max_instances` or `coalesce` to `scheduler.add_schedule(...)`. In
  practice, the self-rolled guard in `_run_job` (`if key in self._active_tokens`)
  enforces single-instance — but the spec-documented APScheduler knob is
  missing, and there is no global cap per spec §Open Question 2.
- **Files:**
  - `packages/server/src/openlia_server/scheduler/service.py:237-255`,
    `service.py:273-280` — pass `max_instances=1, coalesce=True` to
    `scheduler.add_schedule`.
  - `packages/server/src/openlia_server/scheduler/settings.py` — add
    optional `max_concurrent_jobs: int | None` sourced from
    `OPENLIA_SCHEDULER_MAX_CONCURRENT_JOBS`.
  - `packages/server/src/openlia_server/scheduler/service.py:76` — if
    `settings.max_concurrent_jobs` is set, pass it into the APScheduler
    constructor options.
- **Plan ref:** Task 6/7 (APScheduler adapter + settings).
- **Spec ref:** §Job concurrency model + §Open Questions #2.
- **Acceptance:** `FakeAPScheduler.add_schedule` captures
  `max_instances=1, coalesce=True` for every registration; unit test in
  `test_scheduler_service.py`.

### NEW-6-06 — Cron validation gap for MR assessment_schedule

- **Severity:** P1.
- **Bug:** `services/mr_schedules.py:39-64` stores `cron_expression`
  verbatim; the only validation is the route-level empty-string check
  (`routes/mr_schedules.py:46-47`). Downstream,
  `scheduler/service.py:317-324` parses via
  `CronTrigger.from_crontab(schedule.assessment_schedule or "0 0 * * 0")`
  — if the user stored an invalid expression, the scheduler silently
  falls back to weekly Sunday midnight. The MB/EU services validate HH:MM
  + tz + days (`services/mb_schedules.py:42-50`,
  `services/eu_schedules.py:50-58`); MR should validate cron at write
  time.
- **Files:**
  - `packages/server/src/openlia_server/services/mr_schedules.py:39-64` —
    call `CronTrigger.from_crontab(cron_expression)` in a try/except;
    raise `ValueError` on invalid; surface 400 in the route.
  - `packages/server/src/openlia_server/routes/mr_schedules.py:44-51` —
    catch and map to `HTTPException(400)`.
  - `packages/server/src/openlia_server/scheduler/service.py:317-324` —
    remove the `"0 0 * * 0"` silent default; raise if missing.
- **Plan ref:** Task 13.
- **Spec ref:** §Per-user settings (MR cadence = weekly/quarterly) +
  implicit contract that schedules must be valid cron.
- **Acceptance:** `test_mr_schedules_service.py::test_invalid_cron_rejected`
  asserts `ValueError`; route returns 400.

### P2-20 — MR scheduler persistence hardening (rehydration test)

- **Severity:** P1 (was P2-20 in master tracker; upgrade because MR
  persistence is now the only rehydration path).
- **Bug:** `MRScheduleService.rehydrate_all`
  (`services/mr_schedules.py:83-102`) works, but has no lifespan-level
  test that proves a row created in a prior session reappears in the
  scheduler after restart. The lifespan calls it wrapped in
  `try/except` (`app.py:283-286`) and swallows the exception.
- **Files:** new `packages/server/tests/test_services/test_mr_schedule_rehydrate.py`;
  remove the bare `except Exception` at `app.py:285-286` once the test is
  green (narrow to specific exceptions).
- **Plan ref:** Task 13 + REM-P2-004.
- **Spec ref:** §Startup sequence.
- **Acceptance:** seed `mr_dashboard_state.assessment_schedule`, invoke
  lifespan, assert `FakeAPScheduler.added_schedule_ids` contains
  `job_key(JobType.MR_ASSESSMENT, user_id)`.

---

## P2 — polish / packaging

### P2-05 — Scheduler `__init__.py` has no public re-exports

- **Bug:** `packages/server/src/openlia_server/scheduler/__init__.py` only
  declares a docstring; plan called for `from .service import
  SchedulerService`, `from .registry import JobType, JobStatus,
  NotificationType`.
- **Files:** `packages/server/src/openlia_server/scheduler/__init__.py`.
- **Plan ref:** Task 5 (package skeleton).
- **Acceptance:** `from openlia_server.scheduler import SchedulerService,
  JobType, JobStatus, NotificationType` succeeds.

### P2-06 — `app.py` docstring default contradicts `SchedulerSettings`

- **Bug:** `app.py:17` says `OPENLIA_SCHEDULER_ENABLED ... default false`;
  `SchedulerSettings.from_env()` at `scheduler/settings.py:45` defaults to
  `True`.
- **Files:** `packages/server/src/openlia_server/app.py:17`.
- **Plan ref:** Task 14.
- **Acceptance:** docstring reads "default true".

### NEW-6-07 — `result_summary` stored as JSON string, spec says JSON object

- **Severity:** P2.
- **Bug:** `scheduler/executors/base.py:149` calls
  `json.dumps(outcome.result_summary)`. Spec §Data Model
  (`job_runs.result_summary`) says "JSON. E.g.
  `{"reports_generated": 3, "report_ids": [...]}`". SQLite-text column
  works; Postgres `jsonb` column would double-encode. Confirm DB column
  type in `packages/server/src/openlia_server/db/models/scheduler.py`.
- **Files:** `packages/server/src/openlia_server/scheduler/executors/base.py:149`;
  `packages/server/src/openlia_server/db/models/scheduler.py` — confirm
  `result_summary` is `Text` (OK) or `JSON` (must stop json.dumps-ing).
- **Acceptance:** one decision, test captures the contract.

### NEW-6-08 — Maintenance job cadence mismatch with spec

- **Severity:** P2.
- **Bug:** Spec §Job Types #4 ("Once on server startup, then daily
  interval"). Implementation registers a pure cron at 03:00 UTC
  (`scheduler/service.py:248`). Two drift points: no
  immediate-first-run, cadence is cron not interval. Amend one
  (spec or code).
- **Files:** `packages/server/src/openlia_server/scheduler/service.py:245-255`
  or `planning/specs/systems/background-task-scheduling-design.md` §Job
  Types #4.
- **Acceptance:** single source of truth.

### NEW-6-09 — Notification polling endpoint spec contract

- **Severity:** P2.
- **Bug:** Spec §Notifications #2 says `GET /notifications/unread` returns
  `{total: N, by_department: {...}}`. Verify actual shape in
  `routes/notifications.py` matches; existing
  `test_routes_notifications.py` may not pin the key names.
- **Files:** `packages/server/src/openlia_server/routes/notifications.py`;
  `packages/server/tests/test_scheduler/test_routes_notifications.py`.
- **Acceptance:** shape test green.

---

## Missing tests

- `test_app_lifespan.py::test_scheduler_wires_real_builders` — NEW-6-02.
- `test_scheduler/test_mr_executor.py::test_batch_runner_required` —
  P0-04 negative test (raises at wiring when batch_runner is None).
- `test_routes/test_mr_schedules_live.py::test_upsert_registers_with_live_scheduler`
  — P0-05.
- `test_routes/test_mr_schedules_live.py::test_delete_unregisters_from_live_scheduler`
  — P0-05 companion.
- `test_scheduler/test_wiring.py::test_build_requires_real_builders` —
  NEW-6-01.
- `test_services/test_mr_schedule_rehydrate.py` — P2-20.
- `test_services/test_mr_schedules_service.py::test_invalid_cron_rejected`
  — NEW-6-06.
- `test_scheduler/test_scheduler_service.py::test_add_schedule_sets_max_instances`
  — NEW-6-05.
- `test_scheduler/test_config_change_reschedule.py` — NEW-6-04.
- `test_routes_jobs.py::test_retry_when_scheduler_disabled_returns_503`
  — audit finding #3 (2026-04-21).
- `test_routes_notifications.py::test_unread_response_shape` — NEW-6-09.

---

## Verification

```bash
# P0 gate
grep -n "batch_runner=None" packages/server/src/openlia_server/app.py                  # 0 hits
grep -n "MRScheduleService(.*scheduler=None" packages/server/src/openlia_server/app.py # 0 hits
grep -n "Stub" packages/server/src/openlia_server/scheduler/wiring.py                  # 0 hits

# Test gate
uv run pytest \
  packages/server/tests/test_scheduler/ \
  packages/server/tests/test_services/test_mr_schedules_service.py \
  packages/server/tests/test_services/test_mr_schedule_rehydrate.py \
  packages/server/tests/test_routes/test_mr_schedules_live.py \
  packages/server/tests/test_app_lifespan.py

# Boot gate
OPENLIA_SCHEDULER_ENABLED=true uv run openlia serve &  \
  curl -fsS localhost:8000/healthz && kill %1
```

All three gates green → Phase 6 at 100%.
