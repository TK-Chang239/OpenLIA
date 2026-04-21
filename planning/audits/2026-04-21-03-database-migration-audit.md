# Database Migration Audit

Date: 2026-04-21

Scope: current SQLAlchemy models, Alembic revisions, bootstrap behavior, and
planned schema changes needed by Plans 9+.

Validation commands run: none. Static audit only.

## Executive Summary

The current migration baseline covers auth/config/content/infrastructure plus
dashboard/scheduler tables, and migration tests exist. The main risks are
future-plan schema drift: Plan 10 reshapes `wizard_state`, Plan 11 adds
`user_prefs`, Plan 12 may add `repo_items`, Plan 14/15 add department config
tables, and several plans still use wrong module paths or field names. These
must be sequenced with explicit migrations and source registration updates.

## Current Baseline

Current model groups:

- `db.models.auth`: users, sessions, signup invites, signup policy, password
  reset requests, auth events.
- `db.models.config`: LLM/data/web-search providers, models, preferences, data
  requirement mapping.
- `db.models.content`: chat sessions/messages/attachments, reports,
  report versions, portfolio, watchlists.
- `db.models.infrastructure`: wizard state, config store.
- `db.models.dashboard`: dashboard/formula tables.
- `db.models.scheduler`: MB/EU schedules, job runs, user notifications.

Current migrations:

- baseline migration
- dashboard/scheduler/notifications migration
- signup-invites raw-token compatibility migration

## Findings

### 1. High - Future Schema Changes Need A Sequenced Migration Plan

Required future tables/changes:

- Plan 10: `wizard_state.current_step` integer -> string,
  `completed_steps`, `active_session_token`.
- Plan 11: `user_prefs`.
- Plan 12: `repo_items` if repository save uses a separate table.
- Plan 14: `er_user_configs`.
- Plan 15: `eu_watchlist`, `eu_user_configs`.
- Later plans: portfolio/repository/dashboard extensions.

Risk: these plans currently mix correct normalization notes with stale code
snippets. If migrations are generated from stale snippets, models and DB will
diverge.

Required fix:

- Add one migration per plan-owned schema change.
- Update `db.models.__init__` when adding any new model module.
- Add `Base.metadata` registration tests for new modules.
- Add model-vs-migration table list tests after every schema plan.

### 2. High - `wizard_state` Migration Must Patch CLI In Same Work

Current `WizardState.current_step` is integer. CLI `openlia wizard reset`
writes integer `1`. Plan 10 expects string step IDs and new fields.

Impact: after the migration, the existing CLI reset command can write invalid
state unless patched with the model migration.

Required fix:

- Migration changes field type and adds fields.
- Model changes in same commit/task.
- CLI reset writes `current_step="mode"`, `completed_steps=[]`,
  `active_session_token=None`.
- Tests cover both migrated existing rows and CLI reset.

### 3. Medium - Invite Token Schema Is In A Transitional State

`SignupInvite` stores both `token` and `token_hash`. Registration uses
`token_hash`, but CLI list/revoke still depends on raw `token`.

Impact: future admin/account UI should not assume raw token listing remains.

Required fix:

- Decide whether raw token storage is temporary.
- If removing it, add migration and CLI behavior change together.

### 4. Medium - Repo Persistence Semantics Are Not Settled

Current `Report` has `is_starred` and `tags`. No `RepoItem` exists.
Plan 12 adds `repo_items`; Plan 14 says Save-to-Repo flips `is_starred`.

Impact: two repository models can emerge.

Required decision:

- Pick `repo_items`, or
- Pick report flags/tags.

Then rewrite Plans 12, 14, and 22 around that single persistence model.

### 5. Medium - Alembic Head Must Stay Linear And Tested

The current migration tests run Alembic upgrade/downgrade/idempotence. That is
good. Future generated revisions must avoid duplicate heads.

Required checks:

- `uv run alembic -c packages/server/alembic.ini heads` returns one head.
- `upgrade head` works on an empty DB.
- `downgrade base` works or unsupported downgrades are explicitly documented.
- `upgrade head` works twice.

## Recommended Migration Gate

For every schema plan:

1. Add failing model test.
2. Add model/migration.
3. Run DB model tests.
4. Run Alembic upgrade/downgrade tests.
5. Run full `uv run pytest`.
6. Update contract README if import paths or table ownership changed.
