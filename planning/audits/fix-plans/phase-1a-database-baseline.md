# Phase 1a — Database Baseline fix plan (→ 100%)

**Current shipped:** ~88% (22 tables live, round-trips work on SQLite, but the ORM/migration
contract diverges in two places, planned filename is wrong, the `models/__init__.py` leaks
Plan 1B/14/16/20 imports, and the spec-mandated nightly sweep is absent).

**Plan:** [`planning/implementation-plans/2026-04-16-phase-1a-database-baseline.md`](../../implementation-plans/2026-04-16-phase-1a-database-baseline.md)
**Spec:** [`planning/specs/systems/database-design.md`](../../specs/systems/database-design.md)

**Dominant root cause(s):** mixed — IMPLEMENTER drift (filename, docstrings stripped,
`is_starred`/`tags` dropped from Report ORM but kept in migration, module-docstrings lost,
`models/__init__.py` imports Plan 1B+ submodules) + SPEC_DRIFT (UTCDateTime column-type
impedance mismatch with migration `DateTime(timezone=True)` + `CURRENT_TIMESTAMP` default;
nightly maintenance sweep never implemented; signup invite moved from plaintext `token` to
`token_hash` without amending the spec).

**Gap summary:** Plan 1a shipped all 22 baseline tables plus a working round-trip migration
at the *wrong* filename (`2026-04-18-1609_baseline.py` instead of the planned
`2026-04-16-1200_baseline.py`). The shipped code silently diverges from the spec in three
places that will bite later: (1) `Report.is_starred`/`Report.tags` were deleted from the
ORM but the migration still creates those NOT-NULL columns, so `INSERT INTO reports`
through the ORM now depends on the DB default that Alembic did not set; (2) every datetime
column is `UTCDateTime` (naive on write) in the ORM but `DateTime(timezone=True)` in the
migration — Postgres will reject the mix even though SQLite tolerates it; (3) the
spec-mandated nightly sweep (`sessions`, `password_reset_requests`, `mr_assessment_cache`,
`rs_snapshots`, `user_notifications`, `job_runs`) has no code path. Hygiene gaps pile on:
`models/__init__.py` imports `dashboard`/`departments`/`scheduler` (all Plan 1B+), module
docstrings were stripped from `base.py`/`bootstrap.py`/`content.py`/`departments.py`,
`db/__init__.py` exports `run_bootstrap` instead of `bootstrap`, and `bootstrap.py` reaches
into `services.auth.signup_policy` (Plan 2) which breaks Plan 1a's layering contract.

---

## P0 — Live failures

### P0-09 — Baseline migration filename does not match plan
- **Bug.** Plan Task 10 Step 3 specifies `2026-04-16-1200_baseline.py`; the shipped file
  is `2026-04-18-1609_baseline.py` (Alembic revision `01526cb27f5e`). Master tracker §1
  row "1a" calls out this exact mismatch ("Hand-written `2026-04-16-1200_baseline.py`
  migration missing"). The contents *are* the Plan 1a baseline — just named wrong.
- **Files.**
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py`
    (rename candidate).
  - `planning/implementation-plans/2026-04-16-phase-1a-database-baseline.md` lines
    2299, 2411 (Task 10, Step 3).
  - `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md` lines 51,
    146–158 (P0-09 list item), line 491 (sweep summary).
- **Plan ref.** Task 10 ("Baseline migration — create all 22 tables"), Step 3.
- **Spec ref.** §2 "Alembic migration conventions" (filename format
  `YYYY-MM-DD-HHMM_<slug>.py`). The current name *does* match the format but not the
  planned timestamp; every downstream plan that references the baseline migration
  (e.g. Plan 10 `down_revision`) cites the April-16 file that does not exist.
- **Acceptance.** Either (a) rename to `2026-04-16-1200_baseline.py` and update every
  `down_revision` reference in `versions/*.py` that chains off the baseline, OR (b) edit
  the plan Task 10 wording to record the shipped filename and strike P0-09 baseline
  bullet in the master tracker. (b) is the safer option — existing migrations already
  chain off `01526cb27f5e`, renaming the file would require renaming the revision ID
  too; leave the ID, edit the plan.
- **Verification.**
  - `grep -Rn "2026-04-16-1200_baseline\|down_revision.*baseline" packages/server/ planning/` →
    no orphaned references.
  - `cd packages/server && uv run alembic heads` → prints one head.
  - `uv run pytest packages/server/tests/test_db/test_migrations.py -v` → green.

### P0-1a-01 — `Report.is_starred` + `Report.tags` columns exist in migration but not in ORM
- **Bug.** `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py:534,535`
  creates `is_starred Boolean NOT NULL` and `tags JSON NOT NULL` without `server_default`.
  The current `Report` ORM in `packages/server/src/openlia_server/db/models/content.py:83-107`
  has NO `is_starred` column and NO `tags` column. A plain `Report(...)` insert through
  the ORM never sets those columns, so SQLite accepts the row (silently fills NULL and
  then violates NOT NULL at commit time) and Postgres would reject it outright. The master
  tracker observation 1164 confirms "`RepoItem` table present, `Report` lacks `is_starred`
  (repo_items model won)".
- **Files.**
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py:534-535`.
  - `packages/server/src/openlia_server/db/models/content.py:83-107`.
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-22-2200_repo_items_and_drop_legacy_report_cols.py`
    (the later migration already exists but must be confirmed to actually drop the two
    columns — read once and line up with §6).
- **Plan ref.** Task 7 Step 3 content.py listing (Report class, lines 1710-1737 of the
  plan) explicitly defines `is_starred` + `tags`.
- **Spec ref.** §6 `reports` column list: `is_starred Boolean NOT NULL DEFAULT false`,
  `tags JSON NOT NULL DEFAULT []`.
- **Acceptance.**
  - Either: (a) add `is_starred` + `tags` back to `Report` ORM with spec defaults; OR
    (b) confirm `2026-04-22-2200_*.py` drops both columns from the shipped schema AND
    amend the spec + cross-plan contract #2 to drop them from §6 (they are now replaced
    by `repo_items.created_at` for the "starred / saved" signal).
  - Regardless of path, ORM-columns-vs-migration-columns must match. Run a schema-parity
    test (see `test_orm_migration_parity` under Missing tests).
- **Verification.**
  - `cd packages/server && uv run alembic upgrade head && sqlite3 <db> '.schema reports'` →
    matches ORM column set.
  - New test `test_orm_migration_parity_reports` green.
  - `uv run python -c "from openlia_server.db.models.content import Report; print({c.name for c in Report.__table__.columns})"`
    matches the schema.

### P0-1a-02 — `UTCDateTime` ORM type stores naive, migration expects aware
- **Bug.** `packages/server/src/openlia_server/db/base.py:23-46` defines `UTCDateTime`
  that on write `astimezone(UTC).replace(tzinfo=None)` — a naive value. The migration
  declares every datetime column as `sa.DateTime(timezone=True)` with
  `server_default=sa.text("(CURRENT_TIMESTAMP)")` (see line 36 and 45 occurrences). On
  SQLite this works by accident (SQLite ignores `timezone=True`). On Postgres the
  naive-value INSERT into a `TIMESTAMP WITH TIME ZONE` column will be interpreted as
  local-time-of-the-server, breaking the spec contract ("Always UTC at storage; convert
  on render"). This contradicts spec §2 "Timestamp" row.
- **Files.**
  - `packages/server/src/openlia_server/db/base.py:23-67`.
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py`
    (every `sa.DateTime(timezone=True)` — 45 occurrences).
- **Plan ref.** Task 2 Step 3 (`TimestampMixin` defines columns as
  `DateTime(timezone=True)`); Task 6/7/8 model listings all use `DateTime(timezone=True)`.
  The `UTCDateTime` TypeDecorator is not in the plan at all — it was added post-hoc
  (observation 1159). Either the migration needs to be aware-on-disk (decorator stores
  aware) or the ORM decorator must be replaced with `DateTime(timezone=True)` passthrough.
- **Spec ref.** §2 "Portable type conventions" Timestamp row: "Always UTC at storage;
  convert on render. Populated by `server_default=func.now()`".
- **Acceptance.**
  - Pick ONE of two fixes:
    - **Fix A (recommended, matches spec):** change `UTCDateTime.process_bind_param` to
      `return value.astimezone(UTC)` (keep tzinfo). The migration's
      `DateTime(timezone=True)` is already correct; the decorator's extra `.replace(
      tzinfo=None)` is the only bug.
    - **Fix B:** keep naive storage and change every migration column to `sa.DateTime()`
      without `timezone=True` — but this breaks the Postgres-portability promise in §2
      and invalidates the already-shipped `ix_sessions_expires_at`, `locked_until`, etc.
  - Add a round-trip test: insert an aware datetime, reload via ORM, assert
    `result.tzinfo is UTC` AND the underlying raw column value (SELECT via `text`) is
    ISO-8601 with `+00:00` suffix.
- **Verification.**
  - `grep -n "replace(tzinfo=None)" packages/server/src/openlia_server/db/base.py` →
    empty after fix.
  - New test `test_utc_datetime_round_trip_preserves_offset` green on SQLite.
  - `OPENLIA_DB_URL=postgresql+psycopg://...` round-trip smoke passes (optional but
    documented as CI-gate for v1→v2 Postgres work).

### P0-1a-03 — `models/__init__.py` leaks Plan 1B+, Plan 14/15/16 submodules as Plan 1a deliverables
- **Bug.** `packages/server/src/openlia_server/db/models/__init__.py:16-34` imports
  `dashboard`, `departments`, `scheduler`. Per Plan 1a Task 8 Step 3, the final form
  should be `from openlia_server.db.models import auth, config, content, infrastructure`
  only. The `departments` module holds `ErUserConfig`, `EuUserConfig`, `EuWatchlistEntry`,
  `MbUserConfig` (Plan 14/15/16), none of which belong in Plan 1a. Observation 1160
  flags "undocumented `departments` module in init".
- **Files.**
  - `packages/server/src/openlia_server/db/models/__init__.py:16-34`.
- **Plan ref.** Task 8 Step 3 (final `__init__.py` snippet, lines 2002-2012 of plan).
- **Spec ref.** §9 Table inventory (33 tables spread across Plans 1a+1b+11+12+14+15+16;
  §7 dashboard belongs to Plan 1b, §7 department-specific state belongs to Plans 14–20).
- **Acceptance.**
  - Revert `models/__init__.py` to the Plan 1a final form `auth, config, content,
    infrastructure`. Move the Plan 1B+ imports into a Plan-1B-owned re-export (or drop
    them entirely — `import openlia_server.db.models.dashboard` works fine as a deep
    import; `models/__init__.py` is only needed for Alembic autogenerate registration,
    and `env.py` already imports every model by side-effect via model files' own
    registration on `Base.metadata`).
  - If explicit re-exports are retained for convenience, add a docstring that names
    the owning Plan per submodule (`auth` → Plan 1a, `dashboard` → Plan 1b, etc.) and
    add a test that asserts Plan 1a's submodule list is exactly
    `{auth, config, content, infrastructure}`.
- **Verification.**
  - `python -c "from openlia_server.db.models import __all__; assert set(__all__) == {'auth','config','content','infrastructure'}"`
    — exit 0.
  - `uv run pytest packages/server/tests/test_db/test_migrations.py -v` still green
    (autogenerate picks up models via env.py, not via this `__init__.py`).

### P0-1a-04 — `bootstrap._seed_signup_policy` imports Plan 2 service code
- **Bug.** `packages/server/src/openlia_server/db/bootstrap.py:107-115` calls
  `openlia_server.services.auth.signup_policy.seed_signup_policy`. Plan 1a's Task 11
  Step 3 (lines 2633-2671 of plan) restricts seeding to `_seed_local_user()` and
  `_seed_config_store()` — NO `signup_policy` seed, NO services.auth dependency. The
  `services/auth` package is owned by Plan 2. This is a layer inversion: Plan 1a
  becomes uninstallable without Plan 2 present, breaking the "openlia_server.db is
  self-contained" invariant that enabled Plan 2 to be a separate PR.
- **Files.**
  - `packages/server/src/openlia_server/db/bootstrap.py:107-115`.
  - `packages/server/src/openlia_server/services/auth/signup_policy.py` (not inspected;
    confirm the function exists).
- **Plan ref.** Task 11 Step 3 — bootstrap body lists 3 responsibilities; seeding
  signup_policy is NOT one of them.
- **Spec ref.** §3 `signup_policy` ("Seeded on wizard completion: personal mode ->
  `closed`; company mode -> `invite_only`"). Wizard completion is Plan 10's job, not
  startup bootstrap's.
- **Acceptance.**
  - Remove `_seed_signup_policy` from `bootstrap.py`. Move the seed into Plan 10's
    wizard-completion handler (or Plan 2's first-run path if Plan 2 owns signup_policy).
  - Add a test `test_bootstrap_does_not_touch_signup_policy` that boots against a
    fresh DB and asserts `SELECT COUNT(*) FROM signup_policy == 0`.
  - Update Plan 2 / Plan 10 to own the seed if not already scoped.
- **Verification.**
  - `grep -n "signup_policy\|services.auth" packages/server/src/openlia_server/db/bootstrap.py`
    → no matches.
  - `uv run pytest packages/server/tests/test_db/test_bootstrap.py` green.

---

## P1 — Silent correctness gaps

### P1-1a-01 — Spec-required `CHECK` constraints not audited end-to-end (NEW-1a-01 re-scoped)
- **Bug.** Spec §4 `llm_providers` mandates `CHECK constraint: exactly one of
  api_key_encrypted / env_var_name must be set, except when kind='ollama'`. No such
  check exists in the migration or the ORM (`models/config.py:22-40`). Similarly
  `data_providers` has the same implicit rule (§4 `data_providers`) with no constraint.
  `web_search_providers` likewise. The CheckConstraint audit has to cover every §3, §4,
  §6, §7 row:
  - `users.email` normalization: spec §2 "Email normalization" says `normalize_email`
    is app-layer — acceptable as-is.
  - `users.failed_login_attempts >= 0`: spec defines counter, no negative floor in DB;
    add `CHECK (failed_login_attempts >= 0)` for safety.
  - `signup_policy.mode IN ('invite_only','closed','open')` — absent.
  - `password_reset_requests.status IN ('pending','approved','consumed','rejected','expired')` — absent.
  - `auth_events.event_type IN (...)` — spec enumerates 17 values; absent.
  - `llm_models.tier IN ('thinking','everyday','quick')` — absent.
  - `user_llm_preferences.tier IN (...)` — absent.
  - `chat_sessions.department IN ('secretary','equity_research','earnings_update','morning_briefing','macro_research','retail_sentiment')` — absent.
  - `chat_messages.role IN ('user','assistant','system','tool')` — absent.
  - `wizard_state.status IN ('not_started','in_progress','completed')` — absent.
  - `portfolio_holdings.currency` ISO-4217 — absent.
- **Files.** `packages/server/src/openlia_server/db/models/{auth,config,content,infrastructure}.py`;
  `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py`.
- **Plan ref.** Task 5 Step 4 (auth), Task 6 Step 3 (config), Task 7 Step 3 (content),
  Task 8 Step 3 (infrastructure). None explicitly list CHECKs, but the plan defers to
  spec §2 portable-type-conventions ("Enum-valued columns: value set documented in the
  model docstring; invalid values fail at the service layer"). That service-layer
  validation is OK for enum-string fields, but `llm_providers` credential-exclusivity
  is *not* a pure enum — it is a multi-column invariant that only a DB CHECK can guard.
- **Spec ref.** §2, §3, §4, §6, §7.
- **Acceptance.**
  - Add a new Alembic migration `2026-04-2X-0000_add_spec_checks.py` that adds every
    missing CHECK constraint listed above under `batch_alter_table` (SQLite needs the
    recreate-table trick).
  - Add ORM-level `CheckConstraint` to the corresponding `__table_args__`.
  - Add a parity test asserting every constraint named in the spec is present in
    `Base.metadata.tables[...].constraints`.
- **Verification.**
  - New test `test_spec_check_constraints_present` — green.
  - Round-trip migration test still green.

### P1-1a-02 — Migration uses `(CURRENT_TIMESTAMP)` instead of `func.now()` — drops sub-second precision on SQLite
- **Bug.** Every `created_at` / `updated_at` in the baseline migration is
  `server_default=sa.text("(CURRENT_TIMESTAMP)")`. SQLite's `CURRENT_TIMESTAMP` returns
  second-precision `YYYY-MM-DD HH:MM:SS`. The ORM uses `server_default=func.now()`
  which SQLAlchemy renders to `CURRENT_TIMESTAMP` for SQLite anyway — but with
  `UTCDateTime` returning the value, the ORM can read back a truncated value and fail
  equality tests comparing `before` vs `after` across the second boundary. This is
  distinct from P0-1a-02: here the *default function* is the issue.
- **Files.** `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py` (45 occurrences).
- **Plan ref.** Task 10 Step 3 — plan does not mandate `(CURRENT_TIMESTAMP)` vs
  `func.now()`, but the ORM's `server_default=func.now()` is supposed to round-trip
  through Alembic autogenerate; if the migration uses a different SQL text, autogenerate
  will flag the schema as drifted next run.
- **Spec ref.** §2 timestamp row.
- **Acceptance.**
  - Either regenerate the migration with the current ORM and let Alembic render the
    matching default, OR add `compare_server_default=True` to `env.py` context.configure
    and confirm `alembic revision --autogenerate` produces an empty migration.
- **Verification.**
  - `cd packages/server && uv run alembic revision --autogenerate -m "check-clean"` then
    inspect the generated file is empty (`pass` in both upgrade/downgrade). Delete the
    empty revision afterwards.
  - Consider committing `compare_server_default=True` to `env.py` to lock this going
    forward.

### P1-1a-03 — `wizard_state` shape drift (Integer `current_step` vs String)
- **Bug.** Plan 1a Task 8 and spec §7 define `current_step: Integer NOT NULL DEFAULT
  1`. Plan 10 (setup wizard) reshaped `wizard_state` to `current_step: String(32)`,
  `completed_steps: JSON[]`, `active_session_token: String(64)`. The cross-plan
  contract #4 (README line 68) locks Plan 10's shape. The ORM in
  `packages/server/src/openlia_server/db/models/infrastructure.py:18-29` matches Plan
  10. The baseline migration (line 104) still creates `current_step Integer NOT NULL`;
  later migration `2026-04-21-0001_reshape_wizard_state.py` flips it. This is expected
  (plan 10 is a follow-up migration) BUT Plan 1a's spec §7 row and Task 8 Step 3 listing
  were never amended. A fresh reader of Plan 1a/spec §7 sees the obsolete shape.
- **Files.**
  - `planning/specs/systems/database-design.md` §7 `wizard_state` rows (lines 652-661).
  - `planning/implementation-plans/2026-04-16-phase-1a-database-baseline.md` Task 8 Step
    3 (WizardState ORM snippet, lines 1967-1985).
- **Plan ref.** Plan 1a Task 8 + Plan 10 Task 1 (reshape).
- **Spec ref.** §7 `wizard_state`.
- **Acceptance.**
  - Update spec §7 `wizard_state` row to document the current shape (String
    `current_step`, `completed_steps`, `active_session_token`) with a note "Shape
    finalized by Plan 10; original Plan 1a shape was Integer `current_step`".
  - Update Plan 1a Task 8 Step 3 wizard_state listing with a foot-note pointing to
    Plan 10's migration.
- **Verification.**
  - `grep -n "Integer.*current_step\|current_step.*Integer" planning/specs/systems/database-design.md planning/implementation-plans/2026-04-16-phase-1a-database-baseline.md` →
    only appears inside explicit "legacy" or "superseded" context.

### P1-1a-04 — `signup_invites.token` spec says plaintext, ORM ships `token_hash`
- **Bug.** Spec §3 `signup_invites`: `token String(64) UNIQUE NOT NULL` "Stored in
  plaintext (bearer credential; looked up by value)". Shipped ORM/migration uses
  `token_hash String(64)` (observation 120, Apr 18 2026). Observation 120 says "tokens
  migrated from plaintext to hashed storage" — a design change that was made but never
  back-applied to the spec or plan.
- **Files.**
  - `packages/server/src/openlia_server/db/models/auth.py:79-91`.
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py:358-386`.
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-20-0001_add_signup_invites_token.py`
    (the migration that flipped plaintext→hash; confirm).
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-22-2000_drop_signup_invite_raw_token.py`
    (drop of legacy column; confirm).
  - `planning/specs/systems/database-design.md` §3 `signup_invites` lines 204-216.
- **Plan ref.** Plan 1a Task 5 auth ORM listing.
- **Spec ref.** §3 `signup_invites`.
- **Acceptance.**
  - Update spec §3 `signup_invites` to say `token_hash String(64) UNIQUE NOT NULL`,
    stored as SHA-256 of the opaque bearer token. Note §5 "Non-encrypted credential
    columns" — add invite-token to the hashed-credential list.
  - Update Plan 1a Task 5 Step 4 auth ORM snippet (line 976-989 of plan) to match.
- **Verification.**
  - `grep -n "signup_invites.*token[^_]" planning/specs/systems/database-design.md` → no
    plaintext references.

### P1-1a-05 — `sessions` table missing `TimestampMixin`'s `updated_at` contract documented in §2
- **Bug.** Spec §2 "Timestamps" says "Every mutable table carries `created_at` AND
  `updated_at`. Append-only tables carry only `created_at`." `sessions` is mutable
  (rows have `last_seen_at`, `revoked_at` mutated). Yet `Session` ORM
  (`auth.py:54-76`) declares only `created_at`, `last_seen_at`, `expires_at`,
  `revoked_at` — no `updated_at`. Spec §3 `sessions` row list also omits `updated_at`
  (line 180-191). The spec §3 list wins locally but contradicts §2's global rule.
- **Files.**
  - `packages/server/src/openlia_server/db/models/auth.py:54-76`.
  - `planning/specs/systems/database-design.md` §2 vs §3 contradiction.
- **Plan ref.** Task 5 Step 4 (Session class — no `TimestampMixin`).
- **Spec ref.** §2 "Timestamps" vs §3 `sessions`.
- **Acceptance.**
  - Resolve the §2/§3 contradiction: amend §2 to say "Mutable tables *usually* carry
    both — exceptions are called out per-table"; keep `sessions` without `updated_at`
    since `last_seen_at` is the operational equivalent. Document the exemption in §3.
- **Verification.** `grep -A2 "### \`sessions\`" planning/specs/systems/database-design.md` →
  notes the §2 exemption.

### P1-1a-06 — `OPENLIA_HOME` env var unspecified
- **Bug.** `bootstrap.openlia_home()` (lines 15-19) reads `OPENLIA_HOME` with
  precedence above `~/.openlia`. Spec §8 "Environment variables" lists
  `OPENLIA_DB_URL`, `OPENLIA_SECRET_KEY`, `OPENLIA_TRUST_PROXY_HEADERS`,
  `OPENLIA_COOKIE_SECURE` only — no `OPENLIA_HOME`. Plan 1a Task 4 Step 3 (lines 700-
  707) also does not mention this env var.
- **Files.**
  - `packages/server/src/openlia_server/db/bootstrap.py:15-19`.
  - `planning/specs/systems/database-design.md` §8 (lines 905-915).
- **Plan ref.** Task 4 Step 3.
- **Spec ref.** §8.
- **Acceptance.** Add `OPENLIA_HOME` to spec §8 with default
  `~/.openlia` and note it's the filesystem root for the SQLite file, uploads, and
  `secret.key`. Back-apply to Plan 1a's file-structure section.
- **Verification.** `grep "OPENLIA_HOME" planning/specs/systems/database-design.md` → one
  row in §8.

### P1-1a-07 — `db/__init__.py` exports `run_bootstrap` alias instead of plan's `bootstrap`
- **Bug.** Plan Task 11 Step 3 (lines 2677-2696) re-exports `bootstrap` as
  `bootstrap`. Shipped `packages/server/src/openlia_server/db/__init__.py:4,19` aliases
  it to `run_bootstrap`. `cli.py` imports `bootstrap` directly from
  `openlia_server.db.bootstrap` (confirmed by grep). Any caller who imports
  `openlia_server.db.bootstrap` as a name from the package gets the aliased
  `run_bootstrap` and the plan-mandated `bootstrap` isn't in `__all__`.
- **Files.**
  - `packages/server/src/openlia_server/db/__init__.py:4,19`.
- **Plan ref.** Task 11 Step 3.
- **Spec ref.** n/a (hygiene).
- **Acceptance.** Rename the alias back to `bootstrap` OR add both
  (`from openlia_server.db.bootstrap import bootstrap` + keep `run_bootstrap` as a
  back-compat alias) and note the decision in `db/__init__.py`'s docstring.
- **Verification.** `uv run python -c "from openlia_server.db import bootstrap; bootstrap"` exits 0.

### P1-1a-08 — `get_db_session` in `session.py` not in plan, no test
- **Bug.** `session.py:45-56` exports `get_db_session`, a FastAPI dependency that
  commits-on-success / rollbacks-on-exception. Plan Task 3 does not define it.
  Plan-1a's test `test_session.py` does not cover it. Rollback-on-exception is a
  subtle correctness contract.
- **Files.**
  - `packages/server/src/openlia_server/db/session.py:45-56`.
  - `packages/server/tests/test_db/test_session.py` — should be extended.
- **Plan ref.** Task 3 (must be amended) OR move this helper to Plan 2's auth middleware
  scope.
- **Spec ref.** n/a.
- **Acceptance.** Write two tests: one proving commit on clean exit, one proving
  rollback on exception, using a throwaway model row.
- **Verification.** `uv run pytest packages/server/tests/test_db/test_session.py::test_get_db_session_commits_on_success
  packages/server/tests/test_db/test_session.py::test_get_db_session_rolls_back_on_error` green.

### P1-1a-09 — Plan's `resolve_db_url` test expects pre-expansion but shipped code silently expands `~`
- **Bug.** Plan Task 4 Step 1 test `test_resolve_db_url_uses_env_var` expects
  `OPENLIA_DB_URL=sqlite:///tmp/explicit.db` round-trips verbatim. Shipped
  `_expand_sqlite_url` *always* calls `os.path.expanduser` on the path portion. Passing
  `/tmp/explicit.db` without `~` is fine (expansion is a no-op), but the test hides a
  real subtlety: if an operator sets `OPENLIA_DB_URL=sqlite:///~custom/openlia.db`
  (no slash between `~` and `custom`), `expanduser` returns `~custom/openlia.db`
  unchanged (no user `custom` exists) and the app starts against a relative path. Not
  a bug in isolation but a silent UX gap.
- **Files.** `packages/server/src/openlia_server/db/bootstrap.py:28-42`.
- **Plan ref.** Task 4 Step 1 test list.
- **Spec ref.** §8.
- **Acceptance.** Add a test `test_resolve_db_url_absolute_path_unchanged` and
  `test_resolve_db_url_raises_on_non_sqlite_with_tilde` that freezes current behavior.
- **Verification.** New tests green.

---

## P2 — Drift / hygiene

### P2-04 — `base.py`, `bootstrap.py`, `content.py`, `departments.py` have only `from __future__ import annotations` on line 1; module docstrings stripped
- **Bug.** Plan Task 2/Task 4/Task 7 specify module docstrings in every db module file
  (quoted extensively in the plan). Shipped files start with `from __future__ import
  annotations` on line 1. Some module observations (#1159) note the doc-strip. Module
  docstrings carry the spec-reference anchors that make future audits possible.
- **Files.**
  - `packages/server/src/openlia_server/db/base.py:1`.
  - `packages/server/src/openlia_server/db/bootstrap.py:1`.
  - `packages/server/src/openlia_server/db/models/content.py:1`.
  - `packages/server/src/openlia_server/db/models/departments.py:1` (if kept — see P0-1a-03).
- **Plan ref.** Task 2 Step 3, Task 4 Step 3, Task 7 Step 3.
- **Spec ref.** n/a.
- **Acceptance.** Restore module docstrings copying from plan verbatim (spec-section
  references included).
- **Verification.** `grep -L '"""' packages/server/src/openlia_server/db/*.py packages/server/src/openlia_server/db/models/*.py` →
  empty output.

### P2-1a-01 — `base.py` docstring on `Base`, `TimestampMixin` stripped
- **Bug.** Plan Task 2 Step 3 `Base` class has docstring "Common base for every ORM
  model in the server." Shipped (`base.py:49-53`) has none. Same for `TimestampMixin`
  (lines 56-67).
- **Files.** `packages/server/src/openlia_server/db/base.py:49-67`.
- **Plan ref.** Task 2 Step 3.
- **Spec ref.** n/a.
- **Acceptance.** Restore class docstrings from plan.
- **Verification.** `uv run python -c "from openlia_server.db.base import Base, TimestampMixin; assert Base.__doc__; assert TimestampMixin.__doc__"`
  exits 0.

### P2-1a-02 — Duplicate `from pathlib import Path as _Path` alongside `from pathlib import Path`
- **Bug.** `bootstrap.py:5-6` imports `Path` twice. Ruff would flag as F811 but
  somehow passes (one is aliased). Cleanup.
- **Files.** `packages/server/src/openlia_server/db/bootstrap.py:5-6`.
- **Plan ref.** Task 4 Step 3 / Task 11 Step 3.
- **Acceptance.** Drop the `_Path` alias; use the unaliased `Path` everywhere in the file.
- **Verification.** `grep -n "_Path" packages/server/src/openlia_server/db/bootstrap.py` → empty.

### P2-1a-03 — `bootstrap._run_alembic_upgrade` hard-codes a relative `script_location` fix-up
- **Bug.** `bootstrap.py:76-82` reads `alembic.ini`, then OVERRIDES `script_location`
  with an absolute path built from `_ALEMBIC_INI_PATH.parent`. This means
  `alembic.ini`'s own `script_location = src/openlia_server/db/migrations` is ignored
  by production callers but honored by the CLI. Two code paths with different truth.
- **Files.** `packages/server/src/openlia_server/db/bootstrap.py:75-82`;
  `packages/server/alembic.ini:2`.
- **Plan ref.** Task 11 Step 3 (plan snippet only calls `set_main_option("sqlalchemy.url",
  url)` — no script_location override).
- **Acceptance.** Change `alembic.ini`'s `script_location` to an absolute path expression
  via `%(here)s` — `script_location = %(here)s/src/openlia_server/db/migrations`. Then
  drop the `set_main_option("script_location", ...)` in bootstrap.
- **Verification.** Bootstrap + CLI both point to the same migrations dir; round-trip
  test green in both contexts.

### P2-1a-04 — `cli.py` bootstrap import pattern not verified against plan
- **Bug.** Plan Task 12 Step 3 shows `from openlia_server.db import bootstrap` (imports
  the function, re-exported from the package `__init__.py`). Shipped `cli.py` (not
  re-read here but gh/grep above) imports `bootstrap` directly. Combined with P1-1a-07
  (`run_bootstrap` alias), this means the package's `__init__.py` and `cli.py`
  disagree on the public name.
- **Files.** `packages/server/src/openlia_server/cli.py` (line with `bootstrap` import).
- **Acceptance.** Consistent name: after P1-1a-07 fix, confirm `cli.py` uses
  `from openlia_server.db import bootstrap`.
- **Verification.** `grep -n "bootstrap" packages/server/src/openlia_server/cli.py` matches `from openlia_server.db import bootstrap`.

### P2-1a-05 — `env.py` imports `openlia_server.db.models` without explicitly stabilizing order
- **Bug.** `env.py:8` does `import openlia_server.db.models`. `models/__init__.py`
  imports submodules in the order `auth, config, content, dashboard, departments,
  infrastructure, scheduler`. `infrastructure` is registered AFTER `dashboard`; if
  dashboard ever references infrastructure via a string FK, autogenerate ordering can
  emit stale cross-refs. Low-probability but fixable.
- **Files.** `packages/server/src/openlia_server/db/models/__init__.py:16-24`.
- **Acceptance.** Reorder to bottom-up dependency order: `auth, infrastructure, config,
  content, dashboard, departments, scheduler` (noting that P0-1a-03 may strip the last
  three). Add a comment on the ordering rule.
- **Verification.** autogenerate with current ORM emits empty migration.

### NEW-1a-02 — Nightly maintenance sweep job absent
- **Bug.** Spec §7 "Nightly maintenance sweep" defines 6 prune rules for `sessions`,
  `password_reset_requests`, `mr_assessment_cache`, `rs_snapshots`, `user_notifications`,
  `job_runs`. No code path exists in Plan 1a *or* Plan 6 (scheduling) that registers
  this job. Plan 1a's out-of-scope line says "Nightly maintenance sweep — Plan 6/7
  (this plan does not install the pruner)", so the audit verifies the handoff:
  - Plan 6 (scheduling) and Plan 7 (CLI surface) should implement it. Grep
    `packages/server/src/openlia_server/services` and `cli.py` for `maintenance_sweep`
    or equivalent.
- **Files.** TBD after Plan 6/7 grep.
- **Plan ref.** Plan 1a "Out of scope" section; Plan 6 scheduling; Plan 7 CLI surface.
- **Spec ref.** §7 "Nightly maintenance sweep".
- **Acceptance.**
  - Either (a) confirm Plan 6/7 shipped a sweep service with a unit test for each
    prune rule and a registered recurring job, then close NEW-1a-02 without Plan 1a
    code changes; OR (b) if absent, open a follow-up under Plan 7's fix plan and
    cross-link here.
  - Add a tracker cross-reference so this item is not dropped.
- **Verification.** `grep -rn "def.*maintenance_sweep\|maintenance-sweep\|nightly_sweep" packages/server/` → at least one implementation hit and at least one test hit.

---

## Missing tests

- `test_orm_migration_parity_reports` — load `Base.metadata` + inspect the live DB after
  `alembic upgrade head`; assert `Report.__table__.columns.keys()` == SQLite's PRAGMA
  for `reports`. Catches P0-1a-01 permanently.
- `test_utc_datetime_round_trip_preserves_offset` — insert aware datetime, reload,
  assert `result.tzinfo is UTC`. Catches P0-1a-02.
- `test_utc_datetime_naive_input_treated_as_utc` — insert naive datetime, reload,
  assert `result.tzinfo is UTC`. Locks the current decorator's naive-input handling.
- `test_models_init_exports_only_plan_1a_submodules` — asserts
  `set(openlia_server.db.models.__all__) == {"auth","config","content","infrastructure"}`.
  Catches P0-1a-03 regressions.
- `test_bootstrap_does_not_touch_signup_policy` — boot against fresh DB, assert
  `SELECT COUNT(*) FROM signup_policy == 0`. Catches P0-1a-04.
- `test_spec_check_constraints_present` — parametrize over every spec-defined CHECK;
  assert presence in `Base.metadata.tables[...].constraints`. Catches P1-1a-01.
- `test_alembic_autogenerate_is_clean` — run `alembic revision --autogenerate -m test`
  against the current `Base.metadata`; assert the generated file has empty upgrade
  and downgrade bodies (then delete the revision). Catches P1-1a-02.
- `test_get_db_session_commits_on_success` + `test_get_db_session_rolls_back_on_error` —
  see P1-1a-08.
- `test_resolve_db_url_absolute_path_unchanged` + `test_resolve_db_url_openlia_home_env_var` —
  see P1-1a-06 and P1-1a-09.
- `test_baseline_has_module_docstring` — asserts `module.__doc__ is not None` for
  every file under `packages/server/src/openlia_server/db/`. Catches P2-04.

---

## Verification checklist

- `uv run pytest packages/server/tests/test_db/ -v` — all Plan 1a tests green.
- `uv run pytest packages/server/tests/test_db/test_migrations.py -v` — round-trip green.
- `cd packages/server && uv run alembic revision --autogenerate -m "check-clean"` —
  produces empty upgrade/downgrade (then delete the temp revision).
- `cd packages/server && uv run alembic upgrade head && uv run alembic downgrade base` —
  round-trip clean.
- `grep -Rn "UTCDateTime\|DateTime(timezone=True)" packages/server/src/openlia_server/db/` —
  consistent within model files (only `UTCDateTime` shows up in ORM, only
  `DateTime(timezone=True)` in migrations; no mixed usage inside a single layer).
- `grep -Rn "datetime" packages/server/src/openlia_server/db/models/*.py | grep -v "UTCDateTime\|datetime\b\|from datetime"` —
  no naked `DateTime(timezone=True)` in ORM files.
- `grep -L '"""' packages/server/src/openlia_server/db/*.py packages/server/src/openlia_server/db/models/*.py` —
  empty (every module has a docstring).
- `grep -n "services.auth\|services\\." packages/server/src/openlia_server/db/bootstrap.py` —
  empty (Plan 1a does not reach into Plan 2 services).
- `python -c "from openlia_server.db.models import __all__; assert sorted(__all__) == ['auth','config','content','infrastructure']"` —
  exit 0.
- `python -c "from openlia_server.db import bootstrap; bootstrap"` — exit 0, name matches plan.
- `grep -Rn "CURRENT_TIMESTAMP\|(CURRENT_TIMESTAMP)" packages/server/src/openlia_server/db/migrations/versions/` —
  either zero matches (regenerated with func.now()) or every match is inside a
  comment/docstring explaining the compatibility choice.
- `uv run pytest packages/server/tests/ -v -k "bootstrap or migration or model"` — full
  Plan 1a acceptance suite green.
- `grep -n "OPENLIA_HOME" planning/specs/systems/database-design.md` — documented in §8.
- `grep -n "token_hash\|signup_invites" planning/specs/systems/database-design.md` —
  §3 says `token_hash`, not plaintext `token`.
