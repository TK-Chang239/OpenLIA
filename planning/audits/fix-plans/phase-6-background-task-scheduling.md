# Phase 6 — Background Task Scheduling fix plan (→ 100%)


**Current:** ~92% shipped. **Root cause:** IMPLEMENTER.

**Gap summary:** Scheduler core (settings, registry, job CRUD, executors, routes, lifecycle) all shipped correctly. Two live wiring bugs break MR: `build_scheduler_service` is called with `batch_runner=None`, and `MRScheduleService` is constructed twice.

**Tasks (in execution order):**

1. **P0-04 — Construct `BatchRunner` and inject into MR executor wiring.**
   - Files: `packages/server/src/openlia_server/app.py:260-276`; `services/runtime.py` (add `build_batch_runner(session_factory)`); `scheduler/wiring.py` (verify signature propagation).
   - Plan ref: Task 14 (`wiring.py` + lifespan) + Task 12 (MRAssessmentExecutor).
   - Spec ref: `background-task-scheduling-design.md` §Execution Model.
   - Acceptance: scheduled `mr_assessment` job executes against a real BatchRunner and produces `job_runs.status=success`; `test_mr_executor_batch.py` asserts non-None `batch_runner`.

2. **P0-05 — Unify `MRScheduleService` — one instance, registered after scheduler start.**
   - Files: `packages/server/src/openlia_server/app.py:280-289, 354-408`; `routes/mr_schedules.py` (read service from `app.state` at request time).
   - Plan ref: Task 13 + Task 14 lifespan integration.
   - Spec ref: `background-task-scheduling-design.md` §Hot-reload — schedule CRUD must mutate the live scheduler.
   - Acceptance: `POST /mr-schedules` creates a row and the schedule appears in `scheduler_svc.get_schedules()`; `test_mr_schedules_live.py::test_create_registers_with_live_scheduler`.

3. **P2-05 — Populate `scheduler/__init__.py` with public re-exports.**
   - Files: `packages/server/src/openlia_server/scheduler/__init__.py:1-7` (re-export `SchedulerService`, `JobType`, `JobStatus`).
   - Acceptance: `from openlia_server.scheduler import SchedulerService, JobType, JobStatus` imports clean.

4. **P2-06 — Fix `app.py` docstring contradiction on `OPENLIA_SCHEDULER_ENABLED`.**
   - Files: `packages/server/src/openlia_server/app.py:17` (docstring default matches `SchedulerSettings.from_env()` which defaults to `True`).
   - Acceptance: docstring reads `default true`.

5. **P2-20 — MR scheduler persistence hardening.**
   - Files: `packages/server/src/openlia_server/services/mr_schedules.py` (verify `rehydrate_all`); add `test_mr_rehydrate.py`.
   - Plan ref: Task 13 + Phase 19 MR cross-ref.
   - Spec ref: `background-task-scheduling-design.md` §Startup sequence.
   - Acceptance: restart test: seed `mr_dashboard_state` row, invoke lifespan, assert `scheduler_svc.get_schedules()` contains the rehydrated entry.

**Verification:** `uv run pytest packages/server/tests/test_scheduler/ packages/server/tests/test_routes/test_mr_schedules_live.py` green; `grep -n "batch_runner=None" packages/server/src/openlia_server/app.py` returns no matches.
