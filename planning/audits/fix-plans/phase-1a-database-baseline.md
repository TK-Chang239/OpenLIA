# Phase 1a — Database Baseline fix plan (→ 100%)


**Current:** ~90% shipped. **Root cause:** mixed (IMPLEMENTER + spec drift on baseline migration naming).

**Gap summary:** Plan 1A shipped all 22 models + seed logic, but the hand-authored baseline migration was renamed/redated, `models/__init__.py` docstring drifted, and a handful of spec-grade constraints (email-normalization `CHECK`, JSON-discipline `CHECK`, nightly sweep job) need to be re-verified against the baseline file itself.

**Tasks (in execution order):**

1. **P0-09 (baseline slice) — Canonicalize the baseline migration file name OR amend the plan.**
   - Files: `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py` (rename to `2026-04-16-1200_baseline.py`) OR edit `planning/implementation-plans/2026-04-16-phase-1a-database-baseline.md` Task 10 to record the shipped filename.
   - Plan ref: Task 10 "Baseline migration — create all 22 tables".
   - Spec ref: `database-design.md` §2 "Alembic migration conventions".
   - Acceptance: `uv run pytest packages/server/tests/test_db/test_migrations.py::test_baseline_upgrade_creates_all_tables -v` green against the canonical name; §2 P0-09 baseline bullet struck through.

2. **P2-04 — Fix `models/__init__.py` docstring + decide on Plan-1B import placement.**
   - Files: `packages/server/src/openlia_server/db/models/__init__.py:1-30` (modify).
   - Plan ref: Task 2 "Declarative Base + naming convention".
   - Spec ref: N/A (hygiene).
   - Acceptance: docstring accurately lists which modules were added in Plan 1A vs 1B, matching the import list.

3. **NEW-1a-01 — Verify every spec-required `CHECK` / constraint landed in baseline migration.** Why new: tracker only flags the filename, not per-column constraints.
   - Files: `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py` (audit + patch).
   - Plan ref: Tasks 5–8 (Auth/Config/Content/Infra models).
   - Spec ref: `database-design.md` §2 "Portable type conventions", §3 `users`, §6 `reports`.
   - Acceptance: diff report "`ORM constraints` vs `migration-created constraints`" empty; round-trip test in `test_migrations.py` green.

4. **NEW-1a-02 — Implement the `database-design.md` §7 "Nightly maintenance sweep" stub hook.** Why new: spec §7 defines a daily cleanup pass for `sessions`, `password_reset_requests`, `signup_invites`, `auth_events`. Neither plan nor code registers a job.
   - Files: create `packages/server/src/openlia_server/services/db_maintenance.py`; wire registration in `packages/server/src/openlia_server/app.py` lifespan (behind scheduler-enabled flag).
   - Plan ref: Task 11 "Startup bootstrap" (extend).
   - Spec ref: `database-design.md` §7 "Nightly maintenance sweep".
   - Acceptance: new unit test `test_db_maintenance.py` exercises a synthetic pass; `SchedulerService` registers the job when enabled.

**Verification:** `uv run pytest packages/server/tests/test_db/ -v` green AND `uv run alembic -c packages/server/alembic.ini upgrade head && uv run alembic -c packages/server/alembic.ini downgrade base` round-trips cleanly against SQLite + Postgres.
