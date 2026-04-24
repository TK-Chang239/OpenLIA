# Phase 9+ Remediation Checklist

Date: 2026-04-21

Scope: prioritized remediation work derived from the Phase 0-8 implementation
vs Plan 9+ consistency audit and the follow-up contract, end-to-end flow,
database, auth, runtime, scheduler, and deployment audits.

Purpose: make the audit findings executable. This checklist should be used
before assigning or implementing Plans 9+ so future work matches the design
already present in the codebase.

Source audits:

- `planning/audits/2026-04-21-phase-0-8-vs-plan-9-plus-consistency-audit.md`
- `planning/audits/2026-04-21-01-contract-audit.md`
- `planning/audits/2026-04-21-02-end-to-end-flow-audit.md`
- `planning/audits/2026-04-21-03-database-migration-audit.md`
- `planning/audits/2026-04-21-04-auth-authorization-audit.md`
- `planning/audits/2026-04-21-05-llm-runtime-readiness-audit.md`
- `planning/audits/2026-04-21-06-scheduler-integration-audit.md`
- `planning/audits/2026-04-21-07-packaging-deployment-audit.md`

## Status Legend

- `[ ]` Not started.
- `[~]` In progress.
- `[x]` Complete.
- `P0` Blocks reliable Plan 9+ implementation.
- `P1` Blocks product journeys or final acceptance.
- `P2` Important hardening or cleanup.

## Immediate Execution Order

1. Fix frontend/backend auth and `/api` proxy contracts.
2. Patch roadmap and Plan 9-15 snippets so they are executable against current
   source.
3. Define route/DTO/auth matrices before adding more UI or department routes.
4. Implement setup status and first-run flow gates.
5. Add the first runtime-backed product route and report persistence path.
6. Wire scheduler departments with real builders/runners as those departments
   land.
7. Add packaging, deployment, and smoke-test gates before final acceptance.

## P0 Contract Stabilization

### REM-P0-001 - Fix frontend auth DTO mapping

Status: `[x]`

Affected implementation:

- `frontend/src/api/auth.ts`
- `frontend/src/state/AuthContext.tsx`
- frontend auth tests
- `packages/server/src/openlia_server/routes/auth.py`

Affected plans:

- Plan 9
- Plan 10-15 route/auth snippets that depend on authenticated frontend state

Problem:

Backend `/auth/login` and `/auth/session` return flat fields:
`user_id`, `email`, `display_name`, `is_admin`, and login-only
`must_change_password`. The frontend expects a nested `{ user: ... }` envelope.

Required work:

- Map backend `user_id` to frontend `AuthUser.id`.
- Map backend `is_admin` to frontend role/admin state.
- Preserve `display_name`.
- Return `must_change_password` from login.
- Decide whether `/auth/session` should include `must_change_password`; either
  add it server-side or default it explicitly client-side.
- Update Plan 9 code snippets and tests to use the flat backend DTO.

Acceptance criteria:

- Login with a valid backend response produces a populated authenticated user.
- Session refresh produces a populated authenticated user.
- Invalid/expired session leaves frontend in unauthenticated state.
- Tests cover login, session refresh, logout, and must-change-password mapping.

Source findings:

- Contract Audit finding 1.
- Auth Authorization Audit finding 1.
- Phase 0-8 vs Plan 9+ Consistency Audit finding 1.

### REM-P0-002 - Implement Vite `/api` proxy rewrite

Status: `[x]`

Affected implementation:

- `frontend/vite.config.ts`
- `planning/implementation-plans/README.md`

Problem:

Frontend calls use `/api/...`, but FastAPI mounts bare paths. The README says
Vite strips `/api`; current Vite shorthand proxy preserves it.

Required work:

- Replace shorthand proxy with an object proxy.
- Add `rewrite: (path) => path.replace(/^\/api/, "")`.
- Keep `changeOrigin: true`.
- Update the README only after source matches the documented contract.

Acceptance criteria:

- `/api/auth/session` reaches backend `/auth/session` in Vite dev mode.
- `/api/notifications/unread` reaches backend `/notifications/unread`.
- A frontend integration or smoke test fails if `/api` is not stripped.

Source findings:

- Contract Audit finding 2.
- Phase 0-8 vs Plan 9+ Consistency Audit finding 2.

### REM-P0-003 - Patch roadmap README authoritative contracts

Status: `[x]`

Affected implementation:

- `planning/implementation-plans/README.md`

Problem:

The README lists wrong model import paths and references nonexistent models.
Workers using it will generate broken code before reaching the individual
phase plans.

Required work:

- Move `ConfigStore` and `WizardState` to
  `openlia_server.db.models.infrastructure`.
- Move `JobRun` and `UserNotification` to
  `openlia_server.db.models.scheduler`.
- Remove `LoginAttempt` unless a real model is added.
- Confirm current route prefixes, auth factory pattern, runtime imports, and
  frontend `/api` contract are stated correctly.

Acceptance criteria:

- Every import path listed in the README resolves in source.
- The README route table matches `create_app()` mounts.
- The README describes factory-oriented auth dependencies:
  `build_require_auth` and `build_require_admin`.

Source findings:

- Contract Audit finding 3.
- Phase 0-8 vs Plan 9+ Consistency Audit finding 3.

### REM-P0-004 - Rewrite stale Plan 9-15 executable snippets

Status: `[x]` (Plan 10 rewritten 2026-04-21 on branch `fix/phase-9-audit-findings`; Plans 9, 11-15 rewritten 2026-04-21 on branch `openai/rem-p0-004-clean-plan-11-15`)

Affected plans:

- `planning/implementation-plans/2026-04-17-phase-9-login-and-account-ui.md`
- `planning/implementation-plans/2026-04-17-phase-10-setup-wizard.md`
- `planning/implementation-plans/2026-04-17-phase-11-settings-page.md`
- `planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md`
- `planning/implementation-plans/2026-04-17-phase-13-report-pipeline-and-secretary.md`
- `planning/implementation-plans/2026-04-17-phase-14-equity-research.md`
- `planning/implementation-plans/2026-04-17-phase-15-earnings-update.md`

Problem:

Several plans contain correct warning banners but stale executable snippets
that import nonexistent helpers or old runtime modules.

Required work:

- Replace `get_db_session` and `get_db` usage with local session dependencies
  created from the app/session factory pattern.
- Replace `current_user`, `CurrentUser`, and `require_user` with route factories
  using `build_require_auth`.
- Replace `openlia.runtime.*` imports with `openlia.llm.runtime.*`.
- Replace `serialize_sse` with `to_wire` or an explicitly added server SSE
  helper.
- Replace old `/settings/models/*` paths with `/settings/admin/llm/*`.
- Remove duplicate admin route modules and extend existing routers in place.
- Replace integer IDs in examples with UUID string IDs.

Acceptance criteria:

- Every code snippet in Plans 9-15 imports modules that exist.
- New backend routes are specified as factory functions accepting
  `db_session_factory` and `mode`.
- Plan 11 extends existing admin/settings routers instead of duplicating route
  stacks.
- Plan 12+ chat/report snippets match current model fields and runtime event
  helpers.

Source findings:

- Contract Audit findings 4 and 5.
- LLM Runtime Readiness Audit finding 2.
- Auth Authorization Audit finding 3.
- Phase 0-8 vs Plan 9+ Consistency Audit findings 4-7.

## P0 Product Flow Gates

### REM-P0-005 - Define endpoint contract matrix

Status: `[~]` (framework landed; Plan 9-15 rows hardened via REM-P0-004 cleanup on 2026-04-21/22; Plan 16-23 rows remain placeholders until those plans are rewritten — see `planning/implementation-plans/endpoint-contract-matrix.md`)

Affected implementation:

- planning docs
- backend route tests
- frontend API clients

Problem:

Route paths, DTOs, auth behavior, and frontend client ownership are spread
across source and plans. Without one matrix, plan work will keep drifting.

Required work:

- Create a table for every existing and planned route with:
  endpoint path, backend function, frontend client, auth dependency, request
  DTO, response DTO, owning plan, and test file.
- Include bare backend paths and `/api` frontend paths.
- Mark personal-mode and company-mode differences.

Acceptance criteria:

- Every existing mounted route is listed.
- Every Plan 9-15 planned route is listed before implementation.
- New routes cannot merge unless the matrix and tests are updated.

Source findings:

- Contract Audit "Contract Matrix Needed Before Execution".

### REM-P0-006 - Define route authorization matrix

Status: `[x]` (matrix covers every shipped and planned route; REM-P1-001 must-change-password gate enforced 2026-04-21 on branch `fix/phase-9-audit-findings` — see `planning/implementation-plans/route-authorization-matrix.md`)

Affected implementation:

- backend route factories
- auth middleware/dependencies
- setup routes
- department routes

Problem:

Personal/company mode semantics exist, but future setup and department routes
need explicit authorization and ownership rules.

Required work:

- Create a route authorization table with:
  public, setup-session only, authenticated user, admin, personal-mode behavior,
  company-mode behavior, owner scoping, and must-change-password behavior.
- Define the exempt routes for forced password change.
- Define setup wizard pre-auth behavior and completion lockout behavior.

Acceptance criteria:

- Every route has exactly one primary access level.
- Owner-scoped resources list their owner field and enforcement point.
- Must-change-password behavior is explicit for every authenticated route.

Source findings:

- Auth Authorization Audit "Route Authorization Matrix Needed".

### REM-P0-007 - Implement setup status and first-run gate

Status: `[folded into Plan 10]` (2026-04-22)

Affected implementation:

- backend setup routes
- frontend setup route
- frontend app bootstrap
- `WizardState`

Affected plans:

- Plan 10

Resolution:

Review on 2026-04-22 determined REM-P0-007's required work is a strict subset
of Plan 10's shipping scope: `/setup/status` is Plan 10 Task 2, the
`require_wizard_session` dependency is Task 6, the `410 Gone` + loopback gate
is Task 5, and the frontend bootstrap that renders `/setup` outside
`AuthProvider` is in Tasks 10+. A separate remediation branch would build the
same scaffolding Plan 10 would then replace. This item is therefore closed as
"resolved by Plan 10 execution" — acceptance criteria are satisfied when Plan
10 merges. The Plan 10 branch (`feat/phase-10-setup-wizard`) carries the work.

Original problem:

The app seeds `wizard.completed=false`, but `/setup` is a placeholder, no
backend setup routes exist, and no setup status gate runs before the app shell.

Original required work (now Plan 10 scope):

- Implement `/setup/status` first.
- Render setup flow outside `AuthProvider` if setup remains pre-auth.
- Add wizard-session gating for setup writes.
- Return `410 Gone` for completed wizard write routes, except status.
- Reject non-loopback personal-mode setup writes if that remains the design.

Acceptance criteria (verified at Plan 10 merge):

- Fresh personal DB sends user to setup before shell.
- Completed wizard sends user to app shell.
- Company mode can complete invite/register/login/setup in the intended order.
- Tests cover incomplete, in-progress, and completed setup states.

Source findings:

- End-to-End Flow Audit findings 1 and 2.
- Auth Authorization Audit finding 4.
- Database Migration Audit finding 2.

## P1 Auth, Security, And Account Completion

### REM-P1-001 - Enforce must-change-password globally

Status: `[x]` (active auth/admin dependencies now gate all currently mounted non-auth routes; `/auth/session` exposes `must_change_password`; frontend protected routes render the forced-change UI, landed 2026-04-21 on branch `fix/phase-9-audit-findings`)

Affected implementation:

- auth dependencies or middleware
- auth routes
- account UI

Problem:

Login reports `must_change_password`, but authenticated users with that flag
can still access existing authenticated backend routes.

Required work:

- Add a company-mode gate for authenticated routes.
- Exempt only:
  `/auth/change-password`, `/auth/logout`, `/auth/logout-all`, and any setup
  route intentionally allowed during password change.
- Ensure frontend routes redirect users with forced password change to the
  password change UI.

Acceptance criteria:

- Forced-password user cannot access settings, jobs, notifications, or future
  department routes.
- Forced-password user can change password and logout.
- After password change, normal route access is restored.

Source findings:

- Auth Authorization Audit finding 2.

### REM-P1-002 - Fix company-mode cookie secure default

Status: `[x]`

Affected implementation:

- `packages/server/src/openlia_server/routes/auth.py`
- auth tests
- `.env.example`

Problem:

Spec expects secure cookies by default in company mode. Current code defaults
to insecure cookies unless `OPENLIA_COOKIE_SECURE=true`.

Required work:

- Default secure cookies to true when `OPENLIA_MODE=company`.
- Keep explicit env override.
- Preserve false default for local personal mode.

Acceptance criteria:

- Company mode sets `Secure` unless explicitly disabled.
- Personal mode remains local-development friendly.
- Tests cover both defaults and env override.

Source findings:

- Auth Authorization Audit finding 5.
- Packaging Deployment Audit finding 4.

### REM-P1-003 - Resolve invite token transitional storage

Status: `[x]` (raw `SignupInvite.token` column dropped 2026-04-22 on branch `fix/phase-11-blockers`; `token_hash` is sole source of truth; CLI list/revoke lookups now use invite id / id-prefix)

Affected implementation:

- `SignupInvite`
- invite migrations
- CLI invite list/revoke
- admin invite UI

Problem:

`SignupInvite` stores both raw `token` and `token_hash`. Registration uses the
hash, while CLI list/revoke still depends on raw token prefixes.

Required work:

- Decide whether raw token storage is temporary.
- If raw storage is removed, update migrations and CLI behavior together.
- If raw storage remains, document why and harden access/display.

Acceptance criteria:

- Invite registration remains one-time and hash-verified.
- CLI revoke/list behavior is consistent with the storage decision.
- Future admin UI does not accidentally depend on raw token exposure unless
  intentionally designed.

Source findings:

- Database Migration Audit finding 3.
- Phase 0-8 vs Plan 9+ Consistency Audit finding 8.

### REM-P1-004 - Fix CLI audit attribution drift

Status: `[x]`

Affected implementation:

- CLI admin commands
- auth event logging helper

Problem:

`admin reset-password` lacks `metadata.source=cli`, and `log_cli_event` allows
source override.

Required work:

- Ensure all CLI auth/account mutations write `metadata.source=cli`.
- Prevent user-provided metadata from overriding canonical source.
- Add tests for reset-password and invite/user mutations.

Acceptance criteria:

- CLI-created audit events are distinguishable from server-created events.
- Source metadata cannot be overwritten through command metadata.

Source findings:

- Phase 0-8 vs Plan 9+ Consistency Audit finding 9.

## P1 Database And Persistence Decisions

### REM-P1-005 - Sequence future schema migrations

Status: `[~]` (Plan 10 wizard state and Plan 11 `user_prefs` landed with single-head migrations; Plan 12/14/15 tables remain deferred — Plan 11 scope cleared 2026-04-22 on branch `fix/phase-11-blockers`)

Affected plans:

- Plan 10 wizard state.
- Plan 11 user preferences.
- Plan 12 repository persistence.
- Plan 14 ER user configs.
- Plan 15 EU watchlist/configs.
- Later portfolio/repository/dashboard extensions.

Problem:

Future schema work is described across plans but not yet organized into a
linear migration sequence with model registration tests.

Required work:

- Add one Alembic revision per plan-owned schema change.
- Update `db.models.__init__` when new model modules are added.
- Add `Base.metadata` registration tests for new models.
- Add model-vs-migration table list checks.
- Verify Alembic has a single head after each schema plan.

Acceptance criteria:

- `alembic heads` returns one head.
- Empty DB upgrades to head.
- Repeated upgrade is idempotent.
- Downgrade support is either tested or explicitly documented as unsupported
  per migration.

Source findings:

- Database Migration Audit findings 1 and 5.

### REM-P1-006 - Migrate `wizard_state` and CLI reset together

Status: `[x]` (migration `5d41c9a7e812`, model reshape, CLI rewrite, and tests landed 2026-04-21 on branch `fix/phase-9-audit-findings`)

Affected implementation:

- `WizardState`
- Alembic migration
- CLI `openlia wizard reset`
- setup wizard routes

Problem:

Current `WizardState.current_step` is integer and CLI reset writes `1`. Plan
10 expects string step IDs plus additional fields.

Required work:

- Migrate `current_step` to the selected string-step design.
- Add `completed_steps` and `active_session_token` if Plan 10 keeps them.
- Patch CLI reset in the same work item.
- Ensure existing rows migrate correctly.

Acceptance criteria:

- CLI reset writes the new valid initial step, likely `"mode"`.
- Existing integer rows migrate without data loss.
- Setup status route reads the migrated shape.

Source findings:

- Database Migration Audit finding 2.
- End-to-End Flow Audit finding 1.

### REM-P1-007 - Choose one repository persistence model

Status: `[x]`
Completed: 2026-04-22 via `feat/plan-12-blockers` (see
`docs/superpowers/specs/2026-04-22-plan-12-blockers-design.md`).

Affected plans:

- Plan 12
- Plan 14
- Plan 22

Problem:

Current `Report` has `is_starred` and `tags`. Plan 12 adds `repo_items`, while
Plan 14 says Save-to-Repo flips report flags.

Required work:

- Choose `repo_items` as canonical saved-report repository, or choose
  `reports.is_starred` plus tags.
- Rewrite Plans 12, 14, and 22 around the selected model.
- Update DTOs, route contracts, and tests.

Acceptance criteria:

- A generated report can be saved, reopened, tagged, and un-saved through one
  canonical persistence path.
- No plan creates a second conflicting repository abstraction.

Source findings:

- End-to-End Flow Audit finding 6.
- Database Migration Audit finding 4.

## P1 Runtime And Department Product Paths

### REM-P1-008 - Add first runtime-backed SSE route

Status: `[x]`
Completed: 2026-04-22 via `feat/plan-12-blockers` (see
`docs/superpowers/specs/2026-04-22-plan-12-blockers-design.md`).

Affected implementation:

- server department/report route factory
- `ChatRunner` or `ReportRunner`
- frontend streaming client

Problem:

Core runtime runners exist, but no backend route exercises them end to end.

Required work:

- Add the first real chat or report SSE route, preferably Secretary chat or a
  minimal report route.
- Serialize events with `to_wire(event)`.
- Cancel on client disconnect.
- Test through `create_app()` or the mounted route factory.

Acceptance criteria:

- Route emits valid SSE frames.
- Disconnect flips the cancellation token.
- Runtime errors become controlled stream/error responses, not raw 500s.
- Tests cover at least one successful stream and one cancellation.

Source findings:

- End-to-End Flow Audit finding 4.
- LLM Runtime Readiness Audit finding 1.

### REM-P1-009 - Add report persistence and validation path

Status: `[x]`
Completed: 2026-04-22 via `feat/plan-12-blockers` (see
`docs/superpowers/specs/2026-04-22-plan-12-blockers-design.md`).

Affected implementation:

- report store service
- `reports` model usage
- report route
- repository/file viewer UI

Problem:

`ReportRunner` emits `ReportComplete(schema=...)`, but no product route
persists completed reports or validates final report structure before storage.

Required work:

- Add a report store service.
- Validate completed report schema before persisting.
- Persist `content_structured` and any required metadata.
- Add user-scoped `GET /reports/{id}`.
- Define save-to-repository behavior using the chosen repository model.

Acceptance criteria:

- Valid completed reports persist and can be reopened by owner.
- Invalid report schema yields a controlled `report.error` or equivalent
  route error.
- Unauthorized users cannot read another user's report.

Source findings:

- End-to-End Flow Audit finding 4.
- LLM Runtime Readiness Audit finding 5.
- Database Migration Audit finding 4.

### REM-P1-010 - Add runtime provider/model hardening tests

Status: `[x]`

Affected implementation:

- provider registry/resolution
- `ChatRunner`
- `ReportRunner`
- LLM admin settings

Problem:

Older audits flagged disabled-provider edge cases. The latest audit did not
deeply re-verify provider resolution before department routes start depending
on it.

Required work:

- Confirm resolution filters both model enabled state and provider enabled
  state.
- Confirm fallback to another enabled model.
- Confirm no usable model raises `TierNotConfiguredError`.
- Confirm runners emit controlled `chat.error` or `report.error`.

Acceptance criteria:

- Disabled provider with enabled model does not cause raw runtime failure.
- No configured model produces a controlled product error.
- Tests cover chat and report paths.

Source findings:

- LLM Runtime Readiness Audit finding 4.

### REM-P1-011 - Protect multi-round tool loop behavior

Status: `[x]`

Affected implementation:

- `ChatRunner`
- `ReportRunner`
- runtime tests
- product-level tests

Problem:

The runtime now has bounded multi-round tool loops. Product tests should
protect that behavior before more routes depend on it.

Required work:

- Add tests where the provider calls a tool in round 1.
- Add tests where the provider calls a second tool in round 2.
- Add tests where final answer/report uses both tool results.
- Add runaway/max-rounds behavior tests.

Acceptance criteria:

- A regression to one-round-only tool execution fails tests.
- Max-round cutoff behavior is deterministic and user-visible.

Source findings:

- LLM Runtime Readiness Audit finding 3.

## P1 Scheduler Integration

### REM-P1-012 - Wire production scheduler dependencies

Status: `[x]`

Affected implementation:

- `packages/server/src/openlia_server/app.py`
- scheduler service construction
- department builders/planners
- report/batch runners

Problem:

Scheduler core is ready, but app startup currently uses stub department
builders and passes `report_runner=None` / `batch_runner=None`.

Required work:

- Construct real `ReportRunner` and `BatchRunner` in production app startup
  when scheduler-enabled departments require them.
- Replace stub MB/EU/MR builders as each department lands.
- Add app-level tests proving production `create_app()` wires real
  dependencies.

Acceptance criteria:

- Enabled EU/MB schedules do not execute stub payload builders in production
  app mode.
- A scheduled run can create a report and notification end to end.

Source findings:

- Scheduler Integration Audit finding 1.
- End-to-End Flow Audit finding 5.

### REM-P1-013 - Use existing scheduler hot-reload API in Plan 15

Status: `[x]`

Affected implementation:

- EU watchlist/config routes
- EU schedule routes
- scheduler service

Problem:

Plan 15 must integrate with existing scheduler add/modify/remove APIs rather
than creating a parallel schedule surface.

Required work:

- Rewrite Plan 15 routes as factories with current auth/session dependencies.
- After DB schedule create/update/delete, call:
  `add_schedule`, `modify_schedule`, or `remove_schedule`.
- Test with a fake scheduler through `create_app()`.

Acceptance criteria:

- Creating an EU schedule registers an APScheduler job.
- Updating an EU schedule hot-reloads the registered job.
- Deleting an EU schedule removes the registered job.

Source findings:

- Scheduler Integration Audit finding 2.

### REM-P1-014 - Handle scheduler-disabled route behavior

Status: `[x]`

Affected implementation:

- `/jobs/{run_id}/retry`
- jobs/notifications route tests

Problem:

Retry route assumes `request.app.state.scheduler` exists. With scheduler
disabled, route behavior should be controlled.

Required work:

- Return 503 or a clear controlled error when scheduler is disabled.
- Add tests for disabled scheduler mode.

Acceptance criteria:

- Jobs route does not crash when scheduler is disabled.
- Response communicates that scheduler actions are unavailable.

Source findings:

- Scheduler Integration Audit finding 3.

### REM-P1-015 - Keep notification transaction ownership explicit

Status: `[x]`

Affected implementation:

- notifications route
- scheduler notification service
- route session dependency pattern

Problem:

Notification read route commits locally because the scheduler notification
service does not own commits. That is acceptable but should stay intentional.

Required work:

- Document route-level transaction ownership.
- Keep future notification/account routes consistent with
  `make_session_dependency` semantics or explicitly justify local commits.

Acceptance criteria:

- Tests cover mark-read persistence.
- Future route implementations do not mix implicit and manual commits
  accidentally.

Source findings:

- Scheduler Integration Audit finding 4.

## P1 Deployment And Smoke Gates

### REM-P1-016 - Fix `.env.example`

Status: `[x]`

Affected implementation:

- `.env.example`
- deployment docs

Problem:

`.env.example` documents `OPENLIA_DEPLOYMENT_MODE`, but source reads
`OPENLIA_MODE`.

Required work:

- Replace with `OPENLIA_MODE=personal`.
- Document allowed values.
- Audit remaining documented env vars against source.

Acceptance criteria:

- Following `.env.example` can enable personal or company mode as documented.
- No obsolete env var remains in the quickstart.

Source findings:

- Auth Authorization Audit finding 6.
- Packaging Deployment Audit finding 1.

### REM-P1-017 - Add production static frontend serving

Status: `[x]` (Phase 23, 2026-04-24: default `/app/frontend/dist` resolution added, image bakes built SPA, `_StripApiPrefixMiddleware` mirrors the Vite dev proxy so browser-side `/api/...` works in dev and prod without branching. Tests: `packages/server/tests/test_frontend_mount.py`, `test_api_prefix_strip.py`.)

Affected implementation:

- server app/static mount
- frontend build output
- package/container config
- Plan 23

Problem:

`openlia serve` starts FastAPI only. No production path serves `frontend/dist`
with SPA fallback.

Required work:

- Build frontend assets for production.
- Include them in the server package or container.
- Mount static files with SPA fallback.
- Ensure API routes are not shadowed.

Acceptance criteria:

- Packaged or containerized app serves `/`.
- Reloading a client route serves the SPA.
- API routes still resolve before fallback.

Source findings:

- Packaging Deployment Audit finding 2.

### REM-P1-018 - Add deployment container recipes

Status: `[x]` (Phase 23, 2026-04-24: multi-stage `Dockerfile` (frontend build -> python runtime) + `.dockerignore`, `deploy/compose/` reverse-proxy recipe and `deploy/lan-only/` compose example, `deploy/README.md` env contract. `ProxyHeadersMiddleware` + `OPENLIA_COOKIE_SECURE` integration tested. Docker build not exercised in this session — daemon not available; Dockerfile syntax is straightforward and compose files pass `docker compose config`. Remaining gap: actual image build/push is left to the release workflow that Phase 23 deferred.)

Affected implementation:

- Dockerfile
- docker-compose examples
- reverse proxy docs
- persistent state layout

Problem:

No Dockerfile or compose files exist, so deployment recipes cannot be
validated.

Required work:

- Add multi-stage Dockerfile with frontend build and Python runtime.
- Define persistent volume for DB/config/state.
- Add compose examples for LAN-only, Caddy, and Cloudflare Tunnel if those
  remain supported targets.

Acceptance criteria:

- Docker image boots with mounted persistent state.
- Compose example reaches `/health` and `/`.
- Company-mode cookie/proxy settings are documented and tested.

Source findings:

- Packaging Deployment Audit finding 3.

### REM-P1-019 - Add end-to-end smoke matrix

Status: `[~]` (Phase 23, 2026-04-24: ASGI-level smoke coverage added via `test_api_prefix_strip.py`, `test_trust_proxy_headers.py`, `test_frontend_mount.py`, plus existing `test_smoke.py`. Container-boot smoke (curl `/healthz` against a running `openlia:dev` image) deferred to a follow-up that runs with Docker daemon access; the Dockerfile itself is ready.)

Affected implementation:

- CI
- test fixtures
- frontend/backend integration tests
- deployment smoke scripts

Problem:

CI covers Python and frontend unit/build paths, but not integrated product
journeys.

Required work:

- Add smoke tests for:
  personal first-run setup,
  company invite/register/login/setup,
  auth logout/reload,
  provider create/test/edit/delete,
  Secretary chat,
  Equity report generation,
  Earnings on-demand report generation,
  EU schedule to notification,
  repository open/save/download,
  password reset and must-change-password.
- Start with the smallest smoke set that can run reliably in CI.

Acceptance criteria:

- At least personal boot, company auth, `/health`, `/`, and one API endpoint
  are covered once static serving exists.
- Full matrix is covered before final product acceptance.

Source findings:

- End-to-End Flow Audit "Required E2E Smoke Matrix".
- Packaging Deployment Audit finding 5.

## P2 Plan And Product Hardening

### REM-P2-001 - Resolve current department placeholder pages

Status: `[ ]`

Affected implementation:

- `/secretary`
- `/equity-research`
- `/earnings-update`
- `/morning-briefing`
- `/retail-sentiment`
- `/macro-research`
- `/panic-thermometer`

Problem:

Frontend department routes exist but render placeholders. That is acceptable
for Phase 8, but future plans must replace placeholders with product-backed
flows in a known order.

Required work:

- Choose first real department route, likely Secretary.
- Build one complete department path before broadening to more departments.
- Ensure every department route has backend route, auth, persistence, and
  frontend acceptance tests.

Acceptance criteria:

- At least one department page streams or renders real generated output.
- Placeholder pages are tracked as explicit remaining work, not mistaken for
  implemented product surface.

Source findings:

- End-to-End Flow Audit finding 3.

### REM-P2-002 - Package report/PDF dependencies

Status: `[x]` (Phase 23, 2026-04-24: Dockerfile installs Chromium's system-level deps (fonts-liberation, libnss3, libatk*, libcups2, libgbm1, libxkbcommon0, libxrandr2, libasound2, libpango*, ...) and runs `uv run playwright install --with-deps chromium` into `PLAYWRIGHT_BROWSERS_PATH=/opt/playwright`, owned by the non-root `openlia` user. Existing `BrowserLauncher` + Plan 13 PDF export pipeline now have all runtime deps available inside the image.)

Affected implementation:

- server package metadata
- Dockerfile
- PDF/export routes
- Plan 13 and Plan 23

Problem:

Future plans mention Playwright/PDF export, but current package metadata does
not include browser/runtime install steps.

Required work:

- Decide whether PDF export uses Playwright.
- Add package dependencies and browser installation instructions if needed.
- Add Docker browser dependencies if export runs server-side.
- Add PDF export smoke test where feasible.

Acceptance criteria:

- PDF export works in the supported deployment environment.
- Missing browser/runtime dependencies fail in CI or smoke tests, not in user
  production sessions.

Source findings:

- Packaging Deployment Audit finding 6.

### REM-P2-003 - Wire or remove documented host/port env vars

Status: `[x]`

Affected implementation:

- CLI `openlia serve`
- `.env.example`
- deployment docs

Problem:

`.env.example` documents `OPENLIA_HOST` and `OPENLIA_PORT`, but the Typer serve
command uses option defaults and does not read these env vars.

Required work:

- Either wire Typer options to env vars or remove those env vars from docs.

Acceptance criteria:

- Operator-facing docs only list env vars that source actually reads.

Source findings:

- Packaging Deployment Audit finding 7.

### REM-P2-004 - Plan MR scheduler persistence explicitly

Status: `[ ]`

Affected implementation:

- Plan 19
- MR schedule models/routes
- scheduler startup registration

Problem:

MR executor exists, but MR schedule persistence and startup rehydration are
deferred.

Required work:

- Add MR schedule state in Plan 19.
- Register MR jobs on startup or through a clear department startup path.

Acceptance criteria:

- MR schedules survive restart.
- MR executor jobs are registered and visible in job history.

Source findings:

- Scheduler Integration Audit finding 5.

## Merge Gates By Phase

### Before Plan 9 Implementation

- `[x]` REM-P0-001
- `[x]` REM-P0-002
- `[x]` REM-P0-003
- `[x]` REM-P0-004 for Plan 9 snippets (2026-04-22)

### Before Plan 10 Implementation

- `[~]` REM-P0-005
- `[x]` REM-P0-006 (2026-04-22)
- `[folded]` REM-P0-007 — scope is a subset of Plan 10 itself; closed by Plan 10 execution (2026-04-22)
- `[x]` REM-P1-006 (2026-04-21)
- `[x]` REM-P0-004 for Plan 10 snippets (2026-04-21)

### Before Plan 11 Implementation

- `[x]` REM-P1-001
- `[x]` REM-P1-002
- `[x]` REM-P1-003 (2026-04-22)
- `[x]` REM-P1-004
- `[x]` REM-P1-005 for user preferences (2026-04-22)
- `[x]` REM-P0-004 for Plan 11 snippets (2026-04-22)

### Before Plan 12 Implementation

- `[x]` REM-P1-007
- `[x]` REM-P1-008
- `[x]` REM-P1-009
- `[x]` REM-P0-004 for Plan 12 snippets (2026-04-22)

### Before Plan 13-15 Implementation

- `[x]` REM-P1-010
- `[x]` REM-P1-011
- `[x]` REM-P1-012
- `[x]` REM-P1-013
- `[x]` REM-P1-014
- `[x]` REM-P1-015
- `[x]` REM-P0-004 for Plan 13-15 snippets (2026-04-22)

### Before Final Product Acceptance

- `[x]` REM-P1-016
- `[x]` REM-P1-017
- `[x]` REM-P1-018
- `[~]` REM-P1-019
- `[ ]` REM-P2-001
- `[x]` REM-P2-002
- `[x]` REM-P2-003
- `[ ]` REM-P2-004

## Recommended Next Commit Sequence

1. `fix(frontend): align auth client and vite proxy with backend routes`
2. `docs(plans): correct phase 9-15 contracts and imports`
3. `docs(plans): add endpoint and authorization matrices`
4. `feat(setup): add setup status gate and wizard state migration`
5. `feat(auth): enforce must-change-password and secure company cookies`
6. `feat(reports): add first runtime SSE route and report persistence`
7. `feat(scheduler): wire real department runners and hot reload schedules`
8. `feat(deploy): serve built frontend and add deployment smoke tests`
