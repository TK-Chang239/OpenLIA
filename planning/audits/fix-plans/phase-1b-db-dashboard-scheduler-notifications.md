# Phase 1b — DB Dashboard/Scheduler/Notifications fix plan (→ 100%)


**Current:** ~95% shipped. **Root cause:** IMPLEMENTER (catch-up migrations already landed 2026-04-24; tracker entries need reconciliation).

**Gap summary:** The two flagged Plan-1B gaps (`mr_dashboard_state` columns, `rs_classification_log` table) now have migration files. Remaining work is closing tracker entries after one verification run plus tightening Plan-1B model FK cascade rules that diverge from the spec.

**Tasks (in execution order):**

1. **P0-09 (Plan-1B slice) — Verify `2026-04-24-0001_mr_dashboard_state_schedule_cols.py` and `2026-04-24-0100_rs_classification_log.py` are reachable from head revision.**
   - Files: `packages/server/src/openlia_server/db/migrations/versions/2026-04-24-0001_mr_dashboard_state_schedule_cols.py`, `…/2026-04-24-0100_rs_classification_log.py` (verify `down_revision` chain).
   - Plan ref: Task 4 "Follow-up migration".
   - Spec ref: `database-design.md` §7 `mr_dashboard_state`; §20 Retail Sentiment amendment requires `rs_classification_log`.
   - Acceptance: `uv run pytest packages/server/tests/test_db/test_migrations.py -v` green; tracker P0-09 `mr_dashboard_state` + `rs_classification_log` bullets struck through.

2. **P1-25 — Close "rs_classification_log migration unverified" once Task 1 passes.**
   - Files: this tracker (coordinator closeout).
   - Acceptance: tracker bullet struck through with commit SHA of the verifying run.

3. **NEW-1b-01 — Audit `ON DELETE` cascade on `job_runs` → `mb_schedules`/`eu_schedules` FK.** Why new: spec §7 `job_runs` specifies "schedule row FK sets NULL on delete so historical runs survive"; neither plan nor current model declaration is clearly tested.
   - Files: `packages/server/src/openlia_server/db/models/scheduler.py` (audit), matching migration patch if needed.
   - Plan ref: Task 2 "Scheduler + notification models".
   - Spec ref: `database-design.md` §7 `job_runs`.
   - Acceptance: new unit test in `test_models_scheduler.py` asserts historical `job_runs` rows survive parent-schedule deletion.

**Verification:** `uv run pytest packages/server/tests/test_db/test_migrations.py packages/server/tests/test_db/test_models_dashboard.py packages/server/tests/test_db/test_models_scheduler.py -v`.
