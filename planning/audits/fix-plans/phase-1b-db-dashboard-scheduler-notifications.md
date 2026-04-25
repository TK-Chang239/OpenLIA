# Phase 1b — DB (Dashboard/Scheduler/Notifications) fix plan (→ 100%)

**Scope note.** This fix plan is scoped to the 12 tables Phase 1b owns:
`pt_user_configs`, `pt_presets`, `mr_dashboard_state`, `mr_assessment_cache`,
`rs_user_config`, `rs_snapshots`, `rs_classification_log`, `fe_saved_formulas`,
`mb_schedules`, `eu_schedules`, `job_runs`, `user_notifications`. Any items the
Master Tracker P0-09 bundle attributes to sibling phases (`mb_user_configs` →
Phase 16, `eu_user_configs` / `eu_watchlist` → Phase 15, `er_user_configs` →
Phase 14, `user_prefs` → Phase 11) are not Phase-1b responsibilities; they
live under those phases' own fix plans.

**Current shipped:** ~92% (originally tracked at 95%; deeper audit demoted it —
two catch-up migrations landed but multiple server-side defaults, CHECK
constraints, spec-drift items, and missing tests are unresolved).

**Plan:** [`2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md`](../../implementation-plans/2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md)

**Specs:**
- [`database-design.md`](../../specs/systems/database-design.md) §7 (PT / MR / RS / FE / scheduler / notifications)
- [`background-task-scheduling-design.md`](../../specs/systems/background-task-scheduling-design.md) §Data Model (`job_runs`, `user_notifications`, `mb_schedules`, `eu_schedules`, `mr_dashboard_state` schedule columns)
- [`retail-sentiment-dashboard-design.md`](../../specs/systems/retail-sentiment-dashboard-design.md) §amendment (`rs_classification_log` v2 follow-on)
- [`macro-research-dalio-dashboards-design.md`](../../specs/systems/macro-research-dalio-dashboards-design.md) (`mr_dashboard_state` cross-ref)

**Dominant root cause(s):** IMPLEMENTER (missing server defaults / CHECKs /
tests) + SPEC_DRIFT (`database-design.md` §7 does not list
`rs_classification_log`, `assessment_schedule`, `last_assessment_at`; those
columns were added by sibling specs after `database-design.md` §7 was
locked) + PLAN_DRIFT (Plan 1B enumerated 11 tables; the as-shipped schema
for Phase 1b is 12 once `rs_classification_log` is included).

**Gap summary:** The two Master-Tracker-flagged items (`mr_dashboard_state`
schedule columns, `rs_classification_log` table) now have migrations
(`2026-04-24-0001_mr_dashboard_state_schedule_cols.py`,
`2026-04-24-0100_rs_classification_log.py`) and both are reachable from
`head` on a linear down_revision chain. However the deeper audit surfaced:
(1) shipped `is_enabled`/`is_shipped`/`composite_settings`/`view_config`/
`threshold_overrides` columns missing Alembic `server_default` so raw-SQL
inserts violate NOT NULL; (2) `mr_dashboard_state.assessment_schedule` has
no CHECK constraining the spec enum `('weekly','quarterly')`; (3)
`rs_snapshots` index omits the `DESC` direction the spec prescribes; (4)
authoritative `database-design.md` §7 summary table still says "29 tables"
and omits `rs_classification_log` plus the two new MR columns — spec
drift not yet reconciled; (5) no frozen-schema parity test compares
`Base.metadata` to the live-migrated DB, and no tests exist for the
catch-up migrations' forward/backward behavior.

---

## P0 — Live failures

None currently observed. Both catch-up migrations apply cleanly under
`alembic upgrade head` on an empty SQLite DB and `test_migrations.py`
passes. The Postgres-deploy failure previously flagged by P0-09 is now
retired for the Phase 1b slice (verification task below confirms it).

1. **P0-09 (Phase 1b slice) — Verification run: confirm the two catch-up
   migrations are reachable from `head` and land the two objects in a
   clean DB.**
   - Files:
     - `packages/server/src/openlia_server/db/migrations/versions/2026-04-24-0001_mr_dashboard_state_schedule_cols.py`
       (down_revision `20260423_2100_mb`, adds `assessment_schedule`
       String(64) + `last_assessment_at` DateTime(tz) via
       `batch_alter_table`).
     - `packages/server/src/openlia_server/db/migrations/versions/2026-04-24-0100_rs_classification_log.py`
       (down_revision `20260424_0001_mr`, creates table +
       `ix_rs_classification_log_ticker_created` +
       `ix_rs_classification_log_batch`).
   - Plan ref: Task 1 (dashboard model) + Task 2 (scheduler) + Task 4
     (Alembic migration).
   - Spec ref: `database-design.md` §7 `mr_dashboard_state`;
     `background-task-scheduling-design.md` §Data Model
     ("`mr_dashboard_state`... `assessment_schedule` (enum: weekly,
     quarterly)... `last_assessment_at` for catch-up logic");
     `retail-sentiment-dashboard-design.md` §v2 follow-on.
   - Acceptance:
     - `uv run alembic -c packages/server/alembic.ini heads` → exactly
       one head `20260424_0100_rs`.
     - `uv run alembic -c packages/server/alembic.ini upgrade head`
       succeeds on empty SQLite DB.
     - `uv run pytest packages/server/tests/test_db/test_migrations.py
       -v` green (EXPECTED_TABLES already lists `rs_classification_log`).
     - Master-tracker P0-09 `mr_dashboard_state` and
       `rs_classification_log` bullets struck through with the commit
       SHA of the verifying run.
   - Verification: `uv run pytest
     packages/server/tests/test_db/test_migrations.py
     packages/server/tests/test_db/test_models_dashboard.py
     packages/server/tests/test_db/test_models_scheduler.py -v`.

---

## P1 — Silent correctness gaps

2. **NEW-1b-02 — Missing `server_default` on `is_enabled` columns of
   `mb_schedules` and `eu_schedules`.**
   - Bug: spec `database-design.md` §7 states "`is_enabled` | `Boolean`
     | NOT NULL, default `true`". Migration
     `2026-04-17-1200_dashboard_scheduler_notifications.py` lines 211 and
     238 declare `sa.Column("is_enabled", sa.Boolean(), nullable=False)`
     with no `server_default`. Model `scheduler.py` (lines 48, 72) has
     only Python-side `default=True`. Any raw SQL `INSERT` that omits
     `is_enabled` raises `IntegrityError`.
   - Files:
     - `packages/server/src/openlia_server/db/migrations/versions/2026-04-17-1200_dashboard_scheduler_notifications.py:211,238`
       — add `server_default=sa.text("1")`.
     - `packages/server/src/openlia_server/db/models/scheduler.py:48,72`
       — add `server_default=text("1")` for parity with migration.
   - Plan ref: Task 2 ("Scheduler + notification models").
   - Spec ref: `database-design.md` §7 `mb_schedules` / `eu_schedules`
     column table; `background-task-scheduling-design.md` §Department
     schedule tables.
   - Acceptance: `INSERT INTO mb_schedules (id, user_id, time, timezone,
     days_of_week) VALUES (...)` without `is_enabled` succeeds; stored
     value is `1`.
   - Verification: new test in `test_models_scheduler.py` that inserts
     via Core-SQL (`connection.execute(text("INSERT..."))`) and asserts
     `is_enabled is True`.

3. **NEW-1b-03 — Missing `server_default` on `pt_presets.is_shipped`.**
   - Bug: spec §7 `pt_presets` says "`is_shipped` | `Boolean` | NOT NULL
     DEFAULT `false`". Migration line ~30 declares no `server_default`;
     model `dashboard.py:78` only has Python-side `default=False`.
   - Files:
     - `packages/server/src/openlia_server/db/migrations/versions/2026-04-17-1200_dashboard_scheduler_notifications.py:30`
     - `packages/server/src/openlia_server/db/models/dashboard.py:78`
   - Plan ref: Task 1.
   - Spec ref: `database-design.md` §7 `pt_presets`.
   - Acceptance: raw SQL insert omitting `is_shipped` succeeds, stored
     value is `0`.

4. **NEW-1b-04 — Missing `server_default` for `composite_settings`,
   `view_config`, `threshold_overrides` JSON columns.**
   - Bug: spec §7 says `composite_settings | JSON | NOT NULL DEFAULT
     {}` (both `pt_user_configs` and `pt_presets`). Same for
     `mr_dashboard_state.view_config` and `mr_dashboard_state.threshold_overrides`
     (`NOT NULL DEFAULT {}`). Migration gives them `nullable=False` but
     no `server_default`; only the ORM supplies `default=dict`.
   - Files:
     - `packages/server/src/openlia_server/db/migrations/versions/2026-04-17-1200_dashboard_scheduler_notifications.py`
       — lines 32, 68, 102, 103, 142, 143 — add `server_default=sa.text("'{}'")`
       (and `"'[]'"` for `panel_config` / `filter_presets`).
     - `packages/server/src/openlia_server/db/models/dashboard.py`
       — mirror `server_default=text(...)` on matching columns.
   - Plan ref: Task 1.
   - Spec ref: `database-design.md` §7 (PT, MR, RS tables).
   - Acceptance: raw-SQL insert omitting these JSON columns succeeds
     and reads back `{}` / `[]` respectively.

5. **NEW-1b-05 — `mr_dashboard_state.assessment_schedule` lacks CHECK
   constraint enforcing the spec enum.**
   - Bug: `background-task-scheduling-design.md` §Department schedule
     tables specifies "`assessment_schedule` (enum: `weekly`,
     `quarterly`)". Catch-up migration
     `2026-04-24-0001_mr_dashboard_state_schedule_cols.py` adds
     `String(length=64)` with no `CheckConstraint`. Anything — even
     typos like `weekley` — is acceptable today.
   - Files:
     - `packages/server/src/openlia_server/db/migrations/versions/2026-04-24-0001_mr_dashboard_state_schedule_cols.py`
       — inside `batch_alter_table("mr_dashboard_state")`, add
       `batch.create_check_constraint("ck_mr_dashboard_state_assessment_schedule",
       "assessment_schedule IS NULL OR assessment_schedule IN ('weekly','quarterly')")`.
     - `packages/server/src/openlia_server/db/models/dashboard.py:113` —
       add matching `CheckConstraint(...)` to `__table_args__`.
   - Plan ref: Task 1 + catch-up migration from 2026-04-24 remediation.
   - Spec ref: `background-task-scheduling-design.md` §Department
     schedule tables; `macro-research-dalio-dashboards-design.md`
     (cross-reference only — does not re-declare the enum).
   - Acceptance: `INSERT INTO mr_dashboard_state(..., assessment_schedule='yearly')`
     raises `IntegrityError`; NULL, `'weekly'`, `'quarterly'` succeed.

6. **NEW-1b-06 — `rs_snapshots` index missing spec-prescribed `DESC`
   direction.**
   - Bug: spec §7 `rs_snapshots` says `ix_rs_snapshots_ticker_captured`
     on `(ticker, captured_at DESC)`. Migration line 171 creates the
     index without `DESC`:
     `batch_op.create_index("ix_rs_snapshots_ticker_captured", ["ticker",
     "captured_at"], unique=False)`. Most recent-snapshot reads scan
     ascending ordering — hot path per ticker gets a full-range scan on
     busy tables.
   - Files:
     - `packages/server/src/openlia_server/db/migrations/versions/2026-04-17-1200_dashboard_scheduler_notifications.py:171`.
     - `packages/server/src/openlia_server/db/models/dashboard.py:191`.
   - Plan ref: Task 1.
   - Spec ref: `database-design.md` §7 `rs_snapshots` **Indexes**.
   - Acceptance: new migration that drops the old index and recreates
     it with `sa.text("captured_at DESC")`. Model's `Index()` uses
     `text("captured_at DESC")`.

7. **NEW-1b-07 — `database-design.md` §7 summary is stale — does not
   list `rs_classification_log`, `assessment_schedule`,
   `last_assessment_at`.**
   - Bug: `database-design.md` line ~920 closes with "29 tables total"
     and a numbered table list that stops at `fe_saved_formulas` (#29).
     Post-2026-04-24 the DB has 30+ tables including
     `rs_classification_log`. The §7 `mr_dashboard_state` column table
     (lines ~725–740) still shows 7 columns; shipped model has 9.
     Because `database-design.md` is the cited source-of-truth in the
     Phase 1b plan, spec drift risks future reviewers re-regressing
     the shipped schema.
   - Files:
     - `planning/specs/systems/database-design.md` — amend §7
       `mr_dashboard_state` column table (add `assessment_schedule
       String(32) NULL CHECK ... weekly|quarterly`, `last_assessment_at
       DateTime(tz) NULL`); add `rs_classification_log` column table;
       update table-count summary.
   - Plan ref: Plan 1B "Source spec" paragraph cites
     `database-design.md` §7 as authoritative.
   - Spec ref: `background-task-scheduling-design.md` §Department
     schedule tables; `retail-sentiment-dashboard-design.md` §v2 follow-on.
   - Acceptance: §7 column table matches shipped `MrDashboardState`
     columns; §7 summary count matches `EXPECTED_TABLES` length in
     `test_migrations.py`.

8. **NEW-1b-08 — Frozen-schema parity test absent.**
   - Bug: no test compares `Base.metadata` columns/indexes against the
     live-Alembic-migrated DB after `upgrade head`. The two catch-up
     migrations could silently diverge from the model (e.g. missing
     default, missing CHECK, wrong type) and every existing test would
     still pass because `test_models_*.py` uses `create_all` (ORM
     metadata) while `test_migrations.py` only checks the set of table
     names.
   - Files:
     - `packages/server/tests/test_db/test_migrations.py` — add
       `test_metadata_matches_alembic_head` that (a) runs
       `alembic upgrade head` against a temp SQLite DB,
       (b) reflects the DB with `MetaData(); meta.reflect(bind=eng)`,
       (c) per-table compares column names, types (coarse), nullability,
       primary keys, and unique constraints against `Base.metadata`.
   - Plan ref: Task 4 "Alembic round-trip" (Plan 1B defines the test
     module that this gap lives in).
   - Spec ref: This is implicit — every other spec assumes the two
     schemas agree.
   - Acceptance: the test fails against the current tree for any drift
     item above (NEW-1b-02..06), and passes once they are reconciled.

9. **NEW-1b-09 — Catch-up migrations lack round-trip tests.**
   - Bug: `test_baseline_downgrade_drops_all_tables` exercises `head →
     base` but no test asserts:
     - upgrading to `20260423_2100_mb` then stepping forward with
       `20260424_0001_mr` adds both columns (and backwards removes them).
     - upgrading to `20260424_0001_mr` then stepping forward with
       `20260424_0100_rs` creates the table + both indexes (and
       downgrade drops both).
   - Files:
     - `packages/server/tests/test_db/test_migrations.py` — add two
       step-migration tests.
   - Plan ref: Task 4.
   - Spec ref: n/a (test debt).
   - Acceptance: new tests pass; introducing a regression in either
     catch-up migration breaks exactly one test.

---

## P2 — Drift / hygiene

10. **P2-04 (Phase 1b slice) — `models/__init__.py` docstring still
    attributes `dashboard`, `scheduler`, `departments` to "Plan 1B"; in
    reality `departments` was minted in Phases 14/15/16.**
    - File: `packages/server/src/openlia_server/db/models/__init__.py:12–14`.
    - Acceptance: docstring lists `departments` under its owning phases.

11. **NEW-1b-01 (RETIRED) — `job_runs` FK cascade on schedule deletion.**
    - Original claim: "historical `job_runs` rows must survive parent
      schedule deletion via SET NULL FK". Re-reading the spec: both
      `database-design.md` §7 `job_runs` and
      `background-task-scheduling-design.md` §`job_runs` explicitly
      call `schedule_id` soft-polymorphic with "no FK constraint"
      (Plan 1B "Soft-polymorphic FK" bullet is authoritative). Model
      `scheduler.py:95` correctly omits `ForeignKey(...)`. No action;
      mark retired so a future reviewer doesn't re-raise it.
    - Files: none.
    - Acceptance: retired in §10 / §11 of the master tracker.

12. **NEW-1b-10 — Plan-vs-reality table count: Plan 1B text says "11
    tables"; as shipped the Phase-1b-owned schema is 12
    (`rs_classification_log` added post-plan).**
    - Bug: Plan 1B goal paragraph and File Structure block enumerate
      "11 tables"; Master-Tracker §1 row still says "DB
      Dashboard/Scheduler/Notif". Either (a) amend the plan to call
      out the v2 addition, or (b) move `rs_classification_log`
      ownership to Phase 20's fix plan explicitly. Current audit owns
      the migration from Phase 1b because it lives under the dashboard
      model module; keep ownership here and amend plan text.
    - Files:
      - `planning/implementation-plans/2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md`
        — add a "2026-04-24 amendment" block noting the 12th table.
    - Plan ref: Goal paragraph.
    - Spec ref: `retail-sentiment-dashboard-design.md` §v2 follow-on.
    - Acceptance: plan text, `EXPECTED_TABLES` comment
      (`test_migrations.py:47`), and database-design.md count all agree.

13. **NEW-1b-11 — `mb_user_configs`, `eu_user_configs`, `eu_watchlist`
    mis-attributed to Phase 1b in the master tracker's P0-09 item.**
    - Bug: `2026-04-24-master-completeness-and-repair-tracker.md` P0-09
      lumps `mb_user_configs create_table (Phase 16)` into the same
      remediation paragraph that also names Phase 1b drift. Migrations
      for those tables are owned by Phases 15/16, not 1b.
    - Files:
      - `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md`
        §2 P0-09 — already labels each bullet with its phase; keep as-is
        but explicitly note in the Phase 1b fix-plan header that only
        `mr_dashboard_state` + `rs_classification_log` bullets are
        Phase-1b-owned.
    - Plan ref: Phase 1b plan (scope boundary).
    - Acceptance: Phase-1b fix plan header clearly scopes the work and
      this file does not claim ownership of 15/16 items.

14. **NEW-1b-12 — `JobRun` has no SA `relationship()` to `UserNotification`
    or `User` — acceptable but undocumented.**
    - Bug: spec does not require relationships, but other models in the
      repo declare `relationship(...)` for navigational ergonomics.
      Non-blocking; flag for consistency review in a later hygiene pass.
    - Files: `packages/server/src/openlia_server/db/models/scheduler.py`.
    - Acceptance: decision recorded in the model module docstring
      ("no `relationship()` by design; service layer joins explicitly").

---

## Missing tests

- **JSON server-default round-trip.** After NEW-1b-04 ships: raw-SQL
  insert omitting `composite_settings` returns `{}`, omitting
  `panel_config` returns `[]`, etc.
- **`is_enabled` / `is_shipped` server-default round-trip.** Raw-SQL
  inserts that omit these boolean columns succeed.
- **`assessment_schedule` enum CHECK.** Insert `'weekly'`, `'quarterly'`,
  NULL succeed; `'yearly'` and `''` fail.
- **Step-by-step migration tests.** Covered by NEW-1b-09: two tests
  that assert the `20260424_0001_mr` and `20260424_0100_rs` migrations
  each apply + downgrade cleanly.
- **Frozen-schema parity test.** Covered by NEW-1b-08.
- **`rs_classification_log` model contract.**
  `test_models_dashboard.py` does not currently exercise
  `RsClassificationLog` columns, indexes, or defaults. Add a
  `test_rs_classification_log_columns`, `test_rs_classification_log_indexes`,
  `test_rs_classification_log_prompt_tokens_default_zero`.
- **`mr_dashboard_state` new columns exercised at ORM level.** Existing
  column test (line ~200) includes `assessment_schedule` +
  `last_assessment_at` but no test inserts a row with either value;
  add one.
- **Migration single-head test.** Add
  `test_single_alembic_head` that asserts `alembic heads` returns one
  revision (currently not enforced by tests).

## Verification checklist

- [ ] `uv run alembic -c packages/server/alembic.ini heads` → one head
      (`20260424_0100_rs`).
- [ ] `uv run alembic -c packages/server/alembic.ini upgrade head` on a
      fresh SQLite DB succeeds.
- [ ] `uv run alembic -c packages/server/alembic.ini downgrade base`
      succeeds.
- [ ] `uv run pytest packages/server/tests/test_db/test_migrations.py -v`
      green.
- [ ] `uv run pytest
      packages/server/tests/test_db/test_models_dashboard.py
      packages/server/tests/test_db/test_models_scheduler.py -v` green.
- [ ] `uv run pytest
      packages/server/tests/test_routes/departments/test_retail_sentiment_classifier_audit.py -v`
      green (exercises `rs_classification_log` end-to-end).
- [ ] Master tracker P0-09 bullets for `mr_dashboard_state` columns and
      `rs_classification_log` struck through with commit SHA.
- [ ] Master tracker P1-25 struck through.
- [ ] `planning/specs/systems/database-design.md` §7 updated to reflect
      shipped columns + tables (NEW-1b-07).
