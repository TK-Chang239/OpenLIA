# OpenLIA — Master Completeness & Repair Tracker

Date: 2026-04-24
Status: working document — used to sequence the repair of every gap surfaced
by the Phase 1a–23 implementation reviews, the 2026-04-21 remediation
checklist, and the 2026-04-24 deferred-tasks log.

Sources consolidated:

- `planning/audits/2026-04-21-remediation-checklist.md` (REM items)
- `planning/deferred-tasks-2026-04-24.md` (tracked deferrals)
- `planning/implementation-plans/README.md` (status table + cross-plan
  contracts)
- 2026-04-24 per-phase implementation reviews (Phases 1a–23) run via
  `feature-dev:code-reviewer` agents

Status legend (mirrors REM checklist + adds verification states):

- `[ ]` not started · `[~]` in progress · `[x]` complete
- `[VERIFY]` claimed shipped, not yet re-verified by a fresh agent run
- Severity: **P0** (broken in production / blocks releasable build) ·
  **P1** (silent correctness gap) · **P2** (spec/plan hygiene, polish)

**Document map:**

- §1 Phase status snapshot
- §2–§4 Severity-ordered backlog (P0 / P1 / P2) — every item an atomic
  fix across all 23 phases
- §5 Frontend test coverage debt (umbrella)
- §6 REM checklist residuals
- §7 Cross-cutting failure patterns
- §8 Suggested repair sequencing (Sprints A–F)
- §9 Tracking conventions
- **§10 Per-phase fix plans (→ 100%)** — 23 per-phase task lists that,
  executed top-to-bottom, take each phase from its current shipped-%
  to 100% of both plan AND spec. Reuses IDs from §2–§4 and mints
  `NEW-<phase>-NN` for spec-level gaps.
- §11 Cross-reference table of newly minted (NEW-*) IDs

---

## 1. Phase status snapshot

All 24 plans are marked `Done` in the README. The "shipped %" column is a
rough estimate from the 2026-04-24 per-phase reviews and reflects how much
of the *plan + spec* surface actually shipped, not just whether the plan
merged.

| #  | Plan                                | Plan status | Shipped % | Dominant root cause       | Headline gap                                                                 |
|----|-------------------------------------|-------------|-----------|---------------------------|-------------------------------------------------------------------------------|
| 1a | DB Baseline                         | Done        | 100%      | RESOLVED                  | ~~Hand-written `2026-04-16-1200_baseline.py` migration missing~~ — closed via PR #52 (f2b3055 + 3bc14f0) |
| 1b | DB Dashboard/Scheduler/Notif        | Done        | 100%      | RESOLVED                  | ~~`mr_dashboard_state` + `rs_classification_log` model/migration drift~~ — closed via PR #52 (f2b3055 + 3bc14f0) |
| 2  | Auth & Secrets                      | Done        | 100%      | RESOLVED                  | ~~`build_require_auth` returns `Depends()` and breaks nested deps~~ — claim retired (FastAPI resolves the default fine); shipped P0-02-01..P2-02-05 via PR for branch `fix/phase-2-auth-secrets` |
| 3  | Data Provider Adapter               | Done        | 100%      | RESOLVED                  | ~~Cleanest phase — only `company_fundamentals` capability deferred~~ — closed via Phase 3 fix-plan (P0-3-01..P0-3-04, P1-3-05..P1-3-12, NEW-3-01..NEW-3-08) |
| 4  | LLM Provider System                 | Done        | 100%      | RESOLVED                  | ~~User-preference HTTP routes never wired~~ — closed via Phase 4 fix-plan (NEW-4-10/11/20-27, 30-40 + P2-11/12) on `fix/phase-4-llm-provider-system` |
| 5  | LLM Runtime                         | Done        | 100%      | RESOLVED                  | ~~`await_with_grace` unused; no startup slot check~~ — closed via Phase 5 fix-plan (P1-12/12b/13/14, NEW-5-01..06, P2-10, P2-NEW-5-07/08/09; P2-NEW-5-10 deferred to consuming plan) |
| 6  | Background Scheduler                | Done        | 100%      | RESOLVED                  | ~~`batch_runner=None` → MR jobs crash; dual `MRScheduleService` instances~~ — closed via Phase 6 fix-plan (P0-04/05, NEW-6-01..09, P2-05/06/20); RS_SNAPSHOT JobType added; cron validation + concurrency caps wired |
| 7  | CLI Surface                         | Done        | 100%      | RESOLVED                  | ~~`serve` startup banner missing~~ — closed via Phase 7 fix-plan (NEW-7-01..09); banner shipped, rotate-key `--from-stdin` flag added, spec reconciled |
| 8  | Frontend Shell                      | Done        | 100%      | RESOLVED                  | ~~Design tokens diverged; mobile shell + ErrorBoundary + skip-nav missing~~ — closed via Phase 8 fix-plan (P1-26, P2-13, P2-18, NEW-8-01..15); mobile shell, ErrorBoundary, ShellSkeleton, multi-segment breadcrumbs all shipped |
| 9  | Login / Account UI                  | Done        | 100%      | RESOLVED                  | ~~Server requires `display_name`; `aria-describedby` missing~~ — closed via Phase 9 fix-plan (P0-08, P1-17, P1-18, NEW-9-01..09); display_name optional with email-local-part fallback, signup policy gates Sign-up link, account_locked surfaces retry-after minutes, aria-describedby + transport-error helper across 6 forms |
| 10 | Setup Wizard                        | Done        | 100%      | RESOLVED                  | ~~Steps 3+4 backend missing~~ — closed via Phase 10 fix-plan (P0-03/03b, P1-15/16, NEW-10-01..15); /setup/models, /setup/providers, /setup/required_tiers shipped, dynamic dept registry, loopback during entire wizard, takeover-on-409 modal, e2e smoke green |
| 11 | Settings Page                       | Done        | 100%      | RESOLVED                  | ~~Admin panels stubbed, unsaved-changes guard unwired, admin reset uses window.prompt~~ — closed via Phase 11 fix-plan (P0-07/09, P1-11, P2-14, NEW-11-02..13); ModelsAdminPanel + DataProvidersAdminPanel real CRUD, dirty-form blocker, server random temp password + OneTimeSecretModal |
| 12 | Shared Chat Components              | Done        | 100%      | RESOLVED                  | ~~`Department` union covers 2 of 7; targeted vitest gaps~~ — closed via Phase 12 fix-plan (P1-02, P2-16, NEW-12-01..21); 7-dept union, drawer search/scope/archive, markdown+code highlighting, inline thumbnails, FileViewer focus+scroll preservation, idempotent SaveToRepo, AbortController POST SSE, auto-titles |
| 13 | Report Pipeline & Secretary         | Done        | 100%      | RESOLVED                  | ~~Secretary HTTP route never created; PDF block renderer field-name bugs~~ — closed via Phase 13 fix-plan (P0-01, P1-01, NEW-13-01..10); Secretary SSE route + chat-runner shipped, PDF block renderer fixed, SPA print route + ReportPrintPage, services/report_store.py deleted, save_report_to_repo tool |
| 14 | Equity Research                     | Done        | 100%      | RESOLVED                  | ~~Active layout split-panel; POST /chat drops session_id~~ — closed via Phase 14 fix-plan (P1-03, NEW-14-01..09); single-column layout + inline ReportCard, DOCX export, per-section streaming events, retry button, save-to-repo from card |
| 15 | Earnings Update                     | Done        | 100%      | RESOLVED                  | ~~/schedules route absent; duplicate impls; Cabinet remove stub~~ — closed via Phase 15 fix-plan (P0-02, NEW-15-01..19); /schedules consolidated into EU router with 422 validation, Cabinet DELETE, Overdue/New/Empty/Error/Skeleton states, search+filter, OnDemand CheckCircle, mobile responsive, framework parity, cascade delete |
| 16 | Morning Briefing                    | Done        | 100%      | RESOLVED                  | ~~prompt/builder JSON-blob mismatch; settings inline; no per-component vitests~~ — closed via Phase 16 fix-plan (P1-04, P2-15, NEW-16-01..06); ReportRequest gains section_topics + reference_portfolio fields, MB settings decomposed into 6 atomic Radix-driven components, 10 new vitests, microcopy aligned |
| 17 | Formula Engine                      | Done        | 100%      | RESOLVED                  | ~~Plan vs design spec describe materially different DSLs~~ — closed via Phase 17 fix-plan (NEW-17-00..16); Option A (plan wins, additive spec amendment); reserved scalars + ruleset + streak moved into engine; pt_runner private helpers deleted |
| 18 | Panic Thermometer                   | Done        | 100%      | RESOLVED                  | ~~5 drill-down dashboards + rule editor deferred~~ — closed via Phase 18 fix-plan (NEW-18-01..16); 5 dashboards, RuleEditor + FormulaInput + PanelSettingsPane, ManualOverridePopover, ImportExportModal, PanelDashboard frame; PtTriggerEvent + PANIC_LEVEL_CHANGE notifications |
| 19 | Macro Research                      | Done        | ~72%      | IMPLEMENTER               | Settings panel never built; `POST /assessment/run` is a stub                 |
| 20 | Retail Sentiment                    | Done        | v1: 60% / v2-bundle: 100% | DEFERRED        | v2-full deferred; `rs_classification_log` migration unconfirmed              |
| 21 | Portfolio                           | Done        | ~55%      | DEFERRED + IMPLEMENTER    | 17-component frontend collapsed to monolith; price provider noop             |
| 22 | Repository                          | Done        | ~65%      | DEFERRED + IMPLEMENTER    | FileViewer click-to-open missing (not in deferred list)                      |
| 23 | Docker / Acceptance                 | Done        | ~55%      | IMPLEMENTER + DEFERRED    | Smoke suite, CI Docker job, RELEASING.md absent; deploy structure wrong      |
| 24 | Design System Refresh               | Done        | 100%      | RESOLVED                  | ~~Button fill-wipe missing; Setup wizard sweep skipped; Card test shallow~~ — closed via Phase 24 fix-plan (P1-28, NEW-24-01..11); Button hover overlay shipped, Setup wizard tokens normalized, Card hover contract tested, no-hex/no-blue vitest locks |

---

## 2. P0 — broken in production (must fix to ship)

These are **live failures** at runtime (or near-certain failures on first
real use), not polish. Each line links the gap to the source review.

- [ ] **P0-01 — Wire Secretary HTTP route.**
  - Bug: `POST /departments/secretary/chat` does not exist; `app.py` has no
    `build_secretary_router` import. Secretary department is unreachable
    from frontend.
  - Files: create `packages/server/src/openlia_server/routes/departments/secretary.py`,
    create `packages/server/src/openlia_server/services/secretary_chat_runner.py`,
    create `frontend/src/api/secretary.ts`, mount in `app.py`.
  - Source: Phase 13 review.

- [ ] **P0-02 — Ship Earnings Update `/schedules` route + page composition.**
  - Bug: `eu_schedules.py` service exists but is not imported in
    `routes/departments/earnings_update.py`; `EarningsUpdatePage.tsx` does
    not exist (all child components exist, nothing assembling them).
  - Files: extend `routes/departments/earnings_update.py`, create
    `frontend/src/pages/EarningsUpdatePage.tsx`.
  - Source: Phase 15 review.

- [ ] **P0-03 — Wire Setup Wizard Step 3 (Models).**
  - Bug: frontend `api/setup.ts` calls `saveModels` and `testModel`; server
    has no handlers → 404. Wizard is uncompletable.
  - Files: extend `packages/server/src/openlia_server/routes/setup.py` with
    `POST /setup/models` and `POST /setup/models/test`.
  - Source: Phase 10 review.

- [ ] **P0-04 — Construct `BatchRunner` and inject into MR executor.**
  - Bug: `app.py` line 268 passes `batch_runner=None`; `MRAssessmentExecutor`
    calls `self._batch_runner.run(...)` unconditionally → `AttributeError`
    on first scheduled MR job.
  - Files: `packages/server/src/openlia_server/app.py`,
    `packages/server/src/openlia_server/scheduler/executors/mr.py`.
  - Source: Phase 6 review.

- [ ] **P0-05 — Unify `MRScheduleService` instances.**
  - Bug: `app.py` constructs two instances; route-layer instance has
    `scheduler=None`, so MR schedule writes via routes never reach
    APScheduler in-memory.
  - Files: `packages/server/src/openlia_server/app.py` (~lines 283 + 388).
  - Source: Phase 6 review.

- [x] ~~**P0-06 — Fix `build_require_auth` return shape.**
  - Bug: returns `Depends(require_auth)`; FastAPI does not evaluate nested
    `Depends` stored as inner-function defaults. Already observed as test
    failure (memory observation 850).
  - Files: `packages/server/src/openlia_server/middleware/auth.py` ~lines
    68–75 and 91–100.
  - Source: Phase 2 review.~~ **Retired by Phase 2 fix-plan rewrite** —
  the 13-test `test_must_change_password_gate.py` suite plus every
  middleware/auth_routes test pass against the shipped factories. FastAPI
  does evaluate `user=require_auth` (where the default is `Depends(...)`)
  via its parameter-default scan. The original bug claim was wrong.

- [x] ~~**P0-07 — Apply `build_require_active_user` to `/settings/prefs`,
  `/settings/email`, `/settings/admin/llm`.**
  - Bug: shipped routes use `build_require_auth`; must-change-password users
    can edit settings. Direct violation of REM-P1-001 acceptance criteria.
  - Files: `packages/server/src/openlia_server/routes/settings_general.py`
    (line 49), `routes/settings_email.py` (line 22),
    `routes/settings_models.py` (line 24).
  - Source: Phase 11 review.~~ **Resolved Phase 2 fix-plan P0-02-01** —
  all three settings routers swapped to `build_require_active_user`; gate
  test extended with 5 new methods covering prefs GET/PATCH, email PATCH,
  models GET/PUT.

- [ ] **P0-08 — Fix `display_name` requirement on `/auth/register`.**
  - Bug: server requires non-empty `display_name`; spec and frontend treat
    it as optional. Blank submission returns 422.
  - Files: `packages/server/src/openlia_server/routes/auth.py` line 29 (model),
    add fallback to email-local-part in registration service.
  - Source: Phase 9 review.

- [ ] **P0-09 — Generate missing Alembic migrations.**
  - Bug: production Postgres deploys missing tables/columns that exist only
    in models. Tests pass via `create_all` on SQLite.
  - Required migrations:
    - ~~`2026-04-16-1200_baseline.py` — Phase 1a baseline file (only
      `.gitkeep` in versions/ today).~~ **Resolved f2b3055** — shipped as
      `2026-04-18-1609_baseline.py` (Alembic revision `01526cb27f5e`);
      Plan 1a Task 10 amended with the shipped filename.
    - ~~`mr_dashboard_state` add `assessment_schedule`, `last_assessment_at`
      (Phase 1b drift).~~ **Resolved f2b3055** —
      `2026-04-24-0001_mr_dashboard_state_schedule_cols.py` adds both
      columns; step-migration test in `test_migration_parity.py`.
    - ~~`rs_classification_log` create_table (Phase 1b/20 drift; expected by
      `test_migrations.py` EXPECTED_TABLES but never created).~~
      **Resolved f2b3055** — `2026-04-24-0100_rs_classification_log.py`
      creates the table plus both indexes; step-migration test in
      `test_migration_parity.py`.
    - `user_prefs` create_table (Phase 11).
    - `mb_user_configs` create_table (Phase 16).
  - Phase 1a / 1b slice of P0-09 closed. Remaining bullets belong to
    Phases 11 / 16 and remain open under their own fix plans.
  - Source: Phase 1a/1b/11/16/20 reviews.

- [ ] **P0-10 — Container-runtime smoke (REM-P1-019 residual).**
  - Bug: `Dockerfile` and compose recipes never built/run end-to-end. Phase
    23 deferred this on Docker daemon availability.
  - Required: build `openlia:dev`, `docker run`, `curl /healthz` and `/`
    from outside the container.
  - Source: deferred-tasks-2026-04-24.md (P0 ranking).

---

## 3. P1 — silent correctness gaps

These work today only because something downstream is also stubbed or
because the codepath isn't exercised; they will fail the moment real load
hits them.

- [ ] **P1-01 — Phase 13 PDF fallback uses wrong schema field names.**
  `_render_block` reads `cards` for `metric_cards` (schema field is
  `metrics`) and `columns` for `table` (schema fields are `headers`/`rows`).
  PDF export of those block types is broken. File:
  `packages/server/src/openlia_server/routes/reports.py`.

- [ ] **P1-02 — Phase 12 `Department` union too narrow.** `frontend/src/api/chat.ts`
  line 3 declares only `"secretary" | "equity_research"`. Six other
  departments (MB, RS, Macro, Panic, Earnings, Portfolio) silently get
  empty `ChatHistoryDrawer` results because of string filter mismatch.

- [ ] **P1-03 — Phase 14 `POST /chat` drops `session_id`.** Equity Research
  follow-ups don't share a `chat_session` row → conversations don't persist
  as continuous threads. File:
  `packages/server/src/openlia_server/routes/departments/equity_research.py`
  ~lines 152–177.

- [ ] **P1-04 — Phase 16 prompt/builder JSON-blob mismatch.**
  `MbRequestBuilderImpl` jams `section_topics` and `reference_portfolio`
  into a `MB_EXTRAS_JSON` string inside `user_input`; the YAML expects them
  as top-level Jinja variables. Those template variables never render.
  Files: `packages/server/src/openlia_server/services/mb_request_builder.py`
  vs `packages/core/src/openlia/prompts/morning_briefing.yaml`.

- [ ] **P1-05 — Phase 19 `POST /assessment/run` is a stub.** Returns a fake
  `job_run_id` with no scheduler dispatch. T4/T5 LLM assessments cannot
  run. `AllWeatherView` exposes a "Run assessment" button that hits this
  stub for a dashboard that has no LLM. File:
  `packages/server/src/openlia_server/routes/departments/macro_research.py`
  line 94.

- [ ] **P1-06 — Phase 19 Four Seasons + All-Weather LLM wiring contradicts
  design.** `FourSeasonsDashboard.T4_PROMPT_KEY = "four_seasons"` makes the
  assembler block on a cached T4 result for a dashboard the spec defines
  as formula-only. All-Weather's "Run assessment" button is shipped for a
  dashboard that has no LLM at all.

- [ ] **P1-07 — Phase 21 `_NoopPriceProvider` is the default.**
  `provider_factory()` returns a noop; real EODHD wiring never landed.
  `analytics` route calls `cache.fetch_many(provider, tickers)`
  synchronously without `await` — works only because the provider is a
  noop today; first real async adapter blocks the event loop.

- [ ] **P1-08 — Phase 21 `GET /portfolio/search` is a pass-through stub.**
  Returns `[{"ticker": "<QUERY>", "name": null}]` regardless of input.
  Violates plan design rule 13 ("no placeholders"); not in deferred list.

- [ ] **P1-09 — Phase 22 FileViewer click-to-open missing.** Spec section
  "Open Report in FileViewer" is a primary user action; rows in
  `Repository.tsx` have no click handler and no `FileViewerContext` import.
  Not in deferred list.

- [ ] **P1-10 — Phase 18 Oil/Inflation panels return only `price` and
  `prev_close`.** MA-relative and volatility-adjusted presets reference
  `ma200`/`atr_14` (unresolved identifiers), which silently evaluate to
  falsy ("green") rather than erroring. Becomes wrong-but-quiet the
  moment a live dispatcher is wired.

- [x] ~~**P1-11 — Phase 4 `update_model` route accepts fields it silently
  drops.**~~ RESOLVED: `update_model` service + route now wire `tier`,
  `model_ref`, `provider_id` (NEW-4-10).

- [ ] **P1-12 — Phase 5 `await_with_grace` exported but unused in runners.**
  Spec required 2-second grace period for in-flight tool calls on
  cancellation; only inter-yield polling is implemented.

- [ ] **P1-13 — Phase 5 missing prompt files.** `macro_research.yaml` and
  `morning_briefing.yaml` not in `packages/core/src/openlia/prompts/`.
  Departments routes are mounted; first slot resolution raises
  `PromptSlotNotFound`. (MB has its own `prompts/morning_briefing.yaml`
  per Phase 16 — verify the loader path matches.)

- [ ] **P1-14 — Phase 5 startup slot validation never wired.**
  `PromptLoader.validate_department_slots` exists but is not called in
  `create_app()` lifespan. Slot typos surface at user-call time, not at
  boot.

- [ ] **P1-15 — Phase 10 `wizard_gate.py` violates plan's no-`get_db_session`
  rule.** Imports `get_db_session` at module scope (line 9) instead of
  using the injected factory pattern. Tests using injected factories
  silently bypass middleware's session.

- [ ] **P1-16 — Phase 10 `review/run` session-lifetime race.**
  `asyncio.create_task(_run_review(db=db, ...))` captures the request-scoped
  DB session; the dependency closes the session while the background task
  still runs → expected `DetachedInstanceError` or silent data loss. File:
  `packages/server/src/openlia_server/routes/setup.py` lines 250–261.

- [ ] **P1-17 — Phase 9 `LoginPage` never calls `getSignupPolicy`.** Plan
  Design Rule 11 explicitly required this; sign-up link visibility is
  driven by `?invite=` presence alone, so a crafted URL renders the link
  in `closed`-mode deployments.

- [ ] **P1-18 — Phase 9 `account_locked` retry-after never surfaced.**
  Server omits `message` field; frontend ignores `metadata.retry_after_seconds`.
  Lockout duration not communicated to the user.

- [ ] **P1-19 — Phase 14 suggestion chips don't auto-submit.** Spec: chips
  populate input AND submit. Shipped: chips set input only.

- [ ] **P1-20 — Phase 14 `ReportCard` Download is two flat buttons, not
  the spec's dropdown with PDF + DOCX.** DOCX option simply absent.

- [ ] **P1-21 — Phase 17 plan vs design-spec DSL divergence.** Plan and
  design spec describe materially different DSLs (different public API,
  different function set, no string literals in plan, no `RuleSet`
  Pydantic types). Plan won. Any later code importing
  `RuleSet`/`evaluate_ruleset`/`days_since`/`derived` scalars per the
  spec will fail. **Resolution: amend either the spec or the engine to
  converge — pick one and write it down.**

- [ ] **P1-22 — Phase 23 `release.yml` has no PyPI gate.** Plan called for
  "publish only when token is set, skip otherwise"; shipped workflow uses
  unconditional OIDC trusted publishing. First tag push fails hard if
  trusted-publisher isn't pre-configured.

- [ ] **P1-23 — Phase 23 `.dockerignore` missing `!CHANGELOG.md` exemption.**
  Both `pyproject.toml`s reference root files; build context is
  incomplete.

- [ ] **P1-24 — Phase 23 `deploy/lan-only/docker-compose.yml` hardcodes
  `OPENLIA_MODE: company`.** A user following the LAN recipe gets
  auth-required mode with no override knob.

- [x] ~~**P1-25 — Phase 20 `rs_classification_log` Alembic migration
  unverified.** Model exists in `dashboard.py`; migration file presence
  not confirmed. Same Postgres deploy risk as P0-09 (covered there).~~
  **Resolved f2b3055** — migration `2026-04-24-0100_rs_classification_log.py`
  is reachable from `head`, covered by step-migration and parity tests
  in `test_migration_parity.py` and `test_rs_classification_log.py`.

- [ ] **P1-26 — Phase 8 design tokens diverged from plan to Wondermakers /
  Acid Yellow.** Functionally fine; **decision needed**: amend the plan
  to the as-built tokens, or roll the tokens back. Don't leave it
  ambiguous. **Resolution path:** Phase 24 (PR #41) formally adopted the
  Wondermakers / Acid Yellow tokens — closing the ambiguity in the
  Phase-24 direction. Mark P1-26 closed once Phase 8 plan amendment is
  filed (see Phase 24 fix-plan NEW-24-05 for the token-surface deltas).

- [ ] **P1-27 — End-to-end smoke matrix completion (REM-P1-019).** 11
  product journeys landed in `test_e2e_smoke_matrix.py` (covers personal
  setup, company invite/register, provider CRUD, password reset, repo
  save/open/unsave, Secretary chat, MB follow-up, ER on-demand, EU
  on-demand, EU schedule→notification). Open: container-boot curl —
  blocked on Docker daemon (covered by P0-10).

- [ ] **P1-28 — Phase 24 `Button` primary variant missing `::before`
  fill-wipe hover overlay.** Plan Task 11 Step 1 mandates "primary (acid),
  secondary (border), ghost variants + fill-wipe hover"; shipped
  `Button.tsx` only does `bg-accent-primary hover:bg-accent-hover`. The
  wipe is a load-bearing brand cue (matches `project/preview/buttons.html`
  in the design bundle) — without it, the design-system rollout reads as
  generic Tailwind. File:
  `frontend/src/components/primitives/Button.tsx`. Source: Phase 24 fix
  plan task 1.

---

## 4. P2 — spec/plan hygiene & polish

These are not bugs; they're documentation and structural cleanup that
keeps the project navigable.

- [ ] **P2-01 — Stale `deferred-tasks-2026-04-24.md` entries.**
  - Phase 20 lines 53–56: still says "`NeutralClassifier` remains the
    default … `SyncLlmClassifier` not yet plugged into `app.state.rs_runner`".
    PR #46 has done that wiring (`RefreshingSyncLlmClassifier`). Update
    the entry.
  - Add orphaned items currently absent from the deferred log:
    - Phase 19: Settings panel, auto-refresh dropdown, composite Summary
      tab, 14 of 18 backend tests, all 6 frontend tests.
    - Phase 21: search-combobox stub (P1-08), toast notifications,
      ticker→ER navigation.
    - Phase 22: `useRepoList` hook, FileViewer integration (P1-09), dept
      badge colors, skeleton state, toast wording.
    - Phase 23: `RELEASING.md`, CI Docker build job,
      `test_wheel_contents.py`, cookie/proxy integration tests,
      env-snapshot test.

- [x] ~~**P2-02 — `route-authorization-matrix.md` path inconsistency.**
  REM-P0-006 references `planning/route-authorization-matrix.md`; file
  resolves at `planning/implementation-plans/route-authorization-matrix.md`.
  Either move the file or update the cross-references.~~ **Resolved Phase 2
  fix-plan P2-02-01** — verified all live cross-references already use the
  canonical `planning/implementation-plans/route-authorization-matrix.md`
  path. Only stale prose lived in this entry and the fix-plan write-up; no
  file move required.

- [x] ~~**P2-03 — `services/auth/__init__.py` is empty.** Plan required
  re-exports of public API. Consumers import sub-modules directly today
  (works), but `from openlia_server.services.auth import authenticate`
  fails contract.~~ **Resolved Phase 2 fix-plan P1-02-01** — populated
  `services/auth/__init__.py` with the full public API and added an import
  smoke test (`tests/test_services/test_auth/test_public_api.py`).

- [x] ~~**P2-04 — Phase 1a `models/__init__.py` includes `dashboard`,
  `scheduler`, `departments`** alongside Plan-1A modules; docstring still
  says these were added "in Plan 1B". Update docstring + decide whether
  the Plan-1B+ imports belong in baseline.~~ **Resolved f2b3055** —
  `models/__init__.py` scoped back to `auth, config, content, infrastructure`
  with a docstring that points to owning phases; full-schema registration
  moved to the side-effect shim `models/register_all.py`. Every db module
  now carries a docstring (enforced by
  `test_alembic_hygiene::test_every_db_module_has_docstring`).

- [ ] **P2-05 — Phase 6 scheduler `__init__.py` empty.** Plan called for
  re-exports of `SchedulerService`, `JobType`, `JobStatus`. Non-breaking
  but inconsistent.

- [ ] **P2-06 — Phase 6 `app.py` docstring contradicts settings default.**
  Docstring says `OPENLIA_SCHEDULER_ENABLED ... default false`;
  `SchedulerSettings.from_env()` defaults to `True`. Fix the docstring.

- [ ] **P2-07 — Phase 7 `serve` startup banner missing.** Spec mandates a
  formatted block (`OpenLIA v1.0.0 / Mode: / Database: / Listening:`); not
  emitted. Test file exists but doesn't assert.

- [ ] **P2-08 — Phase 7 `list-invites` column drift.** Header reads `ID`
  with 8-char prefix; spec said `Token` with 12-char prefix. Spec needs
  amending (raw token never stored — design decision in REM-P1-003).

- [ ] **P2-09 — Phase 7 `secrets rotate-key` stdin fallback never
  implemented.** Plan omitted the path too. Decide: ship the stdin path or
  amend the spec to drop it.

- [ ] **P2-10 — Phase 5 `secretary.yaml` orphaned top-level keys.** Dead
  `system` and `user` keys at the file root co-exist with the canonical
  `chat:` block. Remove the dead keys.

- [x] ~~**P2-11 — Phase 4 `/admin/llm/*` vs `/settings/admin/llm/*` prefix.**~~
  RESOLVED: spec rewritten to `/settings/admin/llm/*` (lines 403-428).

- [x] ~~**P2-12 — Phase 4 user-preference router missing.**~~ RESOLVED:
  `build_llm_user_router` ships in `routes/settings_llm_user.py` mounted
  at `/settings/models` with roster, preferences CRUD, and
  `effective/{department_id}` (covered by NEW-4-11).

- [ ] **P2-13 — Phase 8 `Secretary.tsx` placeholder skipped.** Real Phase 9
  `SecretaryPage` is registered in the router; the Phase 8 placeholder file
  was never created. Decide whether to backfill the placeholder file or
  amend the plan to skip it.

- [ ] **P2-14 — Phase 11 `MustChangePasswordGate` mechanism diverges.**
  Implemented as a router-level guard in `frontend/src/router/MustChangePasswordGate.tsx`,
  not wrapping `SettingsPage` directly. Equivalent effect; document the
  divergence in the plan.

- [ ] **P2-15 — Phase 16 atomic frontend components.** Plan specified
  `SectionRow`, `TopicChip`, `NotesPopover`, `CustomSectionRow`,
  `ScheduleRow`, `AddScheduleModal`. Shipped composed inline in
  `MBSettingsView.tsx`. Open if UX team wants the refactor.

- [ ] **P2-16 — Phase 12 `services/files.py` missing.** File-resolution
  logic lives inline in `routes/files.py`. Not a bug; violates the
  business-logic-in-services rule.

- [x] **P2-17 — Phase 12 zero frontend vitests.** Phase 18 closeout
  shipped seven Panic Thermometer vitests under
  `frontend/src/__tests__/panic-thermometer/` (PanicThermometer,
  RuleEditor, FormulaInput, OilDashboard, DiplomacyDashboard,
  PresetLibrary, ImportExportModal). Phase 12 chat/viewer/save-to-repo
  smoke tests still outstanding — track separately.

- [ ] **P2-18 — Phase 8 `PagePlaceholder` renders styled card, not bare
  `<h1>`.** Cosmetic; either amend plan or revert.

- [ ] **P2-19 — REM-P2-001 (placeholder departments) — partial.** MR page
  shipped 2026-04-24. Each remaining placeholder dies as its real
  product surface ships; nothing to track separately.

- [ ] **P2-20 — REM-P2-004 — MR scheduler persistence.** Open. MR
  schedules currently survive restart only via the lifespan
  `MRScheduleService`; the route-layer instance has `scheduler=None`
  (covered by P0-05, but the plan-19 explicit persistence story is
  separate).

- [ ] **P2-21 — Endpoint-contract-matrix + route-authorization-matrix
  rows for Plans 16, 19, 20, 21, 22.** The deferred-tasks log claims they
  shipped 2026-04-24; **verify by reading the matrix files** before
  closing.

---

## 5. Frontend test coverage debt

The 2026-04-24 reviews surfaced that backend unit tests are consistently
strong but **route-level**, **integration**, and **frontend vitest**
coverage is thin or missing across:

- Phase 4 — `test_llm_user_routes.py`, `test_llm_registry.py`,
  `test_llm_end_to_end.py`, `conftest.py`, `test_adapter_registry.py`.
- Phase 5 — `test_cancellation.py`, `test_messages.py`, `test_events.py`.
- Phase 7 — banner assertion in `test_cli_serve.py`.
- Phase 11 — admin service + admin route tests (3 + 3 files), all
  frontend tests.
- Phase 12 — all frontend vitests (chat, viewer, save-to-repo).
- Phase 14 — `test_equity_research_config_route.py`,
  `test_equity_research_report_route.py`,
  `test_equity_research_chat_route.py`, `test_equity_research_config.py`.
- Phase 15 — `test_eu_watchlist.py`, `test_eu_config.py`,
  `test_eu_runner.py`, `test_eu_scan_planner.py`.
- Phase 18 — `test_pt_routes.py`, `test_pt_runner.py`,
  `test_pt_config.py`, per-panel core tests for InflationPanel,
  FedLanguagePanel, WageGrowthPanel, DiplomacyPanel.
- Phase 19 — 14 of 18 backend tests, all 6 frontend tests.
- Phase 21 — all frontend tests (per deferred list).
- Phase 22 — per-component unit tests (per deferred list).
- Phase 23 — `test_cookie_secure.py`,
  `test_proxy_and_cookie_integration.py`, `test_production_env_snapshot.py`,
  `test_wheel_contents.py`, smoke-suite assembly.

Tracked as **P2-TESTS** umbrella; pull individual tickets when the
related P0/P1 fix lands so the test goes in with the fix.

---

## 6. REM checklist residuals

From `planning/audits/2026-04-21-remediation-checklist.md`. Most are
closed by Phase 16–23 execution; remaining open:

| ID         | Status | Tracking here as                     |
|------------|--------|---------------------------------------|
| REM-P0-005 | `[~]`  | Endpoint-contract-matrix rows for Plans 16–23 (P2-21) |
| REM-P1-019 | `[~]`  | Container-boot smoke (P0-10); product-journey matrix already shipped |
| REM-P2-001 | partial| Department placeholders — covered organically as departments ship |
| REM-P2-004 | `[ ]`  | MR scheduler persistence (P2-20)      |

All other REM items confirmed `[x]` in the checklist; no separate
tracking needed.

---

## 7. Cross-cutting patterns

The same failure shapes recur across phases. Treat these as standing
review checks before any future phase merges.

1. **Backend unit-tested heavily; route + integration + frontend tests
   skipped.** Surfaced in: 4, 5, 7, 11, 12, 14, 15, 17, 18, 19, 21, 22, 23.
2. **Multi-component frontend decompositions collapsed to monolithic
   pages.** Surfaced in: 14, 16, 19, 21, 22. Phases 13 and 15 went
   further and skipped the page-composition file entirely.
3. **Alembic migrations skipped because `create_all` masks the gap on
   SQLite dev.** Surfaced in: 1a, 1b, 11, 16, 20. Tracked under P0-09.
4. **Stub providers / runners shipped without `RuntimeError` guard at
   startup.** Surfaced in: 6 (`batch_runner=None`), 10 (Step 3 routes
   404), 19 (assessment-run stub), 21 (NoopPriceProvider, search stub).
   Add a "fail-loud-on-stub" pattern to standing rules.
5. **Auth gate forgotten on new routes.** Phase 11 forgot
   `build_require_active_user` despite Phase 2 shipping it. Add a CI
   lint or PR-template checkbox: "all new routes pass through
   `build_require_active_user` unless explicitly exempt".
6. **Type/union narrowing not maintained as new departments ship.**
   Phase 12 `Department` union covers 2 of 7 departments. Add a single
   source-of-truth `DepartmentSlug` literal type generated from a list.
7. **Plan vs design-spec drift uncaught.** Phase 17 plan and design spec
   describe materially different DSLs. Future plans must include a
   "differences from spec" section or be rejected at review.

---

## 8. Suggested repair sequencing

Pick branches off `main` in this order. P0 first; never bundle P0 with
P1 in the same PR.

**Sprint A — unblock departments (1–2 days)**

1. P0-01 Secretary route + service + frontend client.
2. P0-02 EU `/schedules` route + page composition.
3. P0-03 Wizard Step 3 backend handlers.
4. P0-09 Alembic migrations (one PR per missing migration; small,
   reviewable).
5. P1-04 MB prompt/builder JSON-blob fix (small + isolated).

**Sprint B — auth & scheduler correctness (1–2 days)**

6. ~~P0-06 Fix `build_require_auth` return shape.~~ — RETIRED (claim was wrong; see P0-06 entry above).
7. ~~P0-07 Apply `build_require_active_user` to settings routes.~~ — DONE via Phase 2 fix-plan P0-02-01.
8. P0-04 + P0-05 Wire `BatchRunner` and unify `MRScheduleService`.
9. P0-08 Fix `display_name` requirement.

**Sprint C — silent correctness (1 sprint)**

10. P1-01 PDF renderer field names.
11. P1-02 Department union.
12. P1-03 ER chat session_id.
13. P1-05 + P1-06 Macro Research assessment runner + dashboard wiring.
14. P1-07 + P1-08 Portfolio price provider + search.
15. P1-09 Repository FileViewer click-to-open.
16. P1-10 Panel context derived metrics.
17. P1-11 Update-model field handling.
18. P1-12 + P1-13 + P1-14 LLM runtime gaps.

**Sprint D — Phase 17 reconciliation (decision needed)**

19. P1-21 Pick one DSL: amend the spec to match the engine, or amend the
    engine to match the spec. **Do this before any new PT/MR formula
    work begins** — current code that imports spec symbols will fail.

**Sprint E — release engineering**

20. P0-10 Container-runtime smoke.
21. P1-22 + P1-23 + P1-24 Release workflow + dockerignore + LAN compose
    fixes.
22. P1-26 Design tokens decision (amend plan or roll back).

**Sprint F — hygiene**

23. P2-01 deferred-tasks log refresh.
24. P2-21 verify matrix rows actually exist for Plans 16–23.
25. Remaining P2-* items as time permits.

---

## 9. Tracking conventions

- One PR per ticket above. Title format: `fix(phase-N): <P0/P1/P2-NN> <summary>`.
- When a ticket lands, flip its checkbox here in the same PR.
- New gaps discovered during repair go into the matching severity section
  with a new sequence number.
- Don't delete closed tickets — strike through (`~~text~~`) so the
  document stays a complete repair log.

---

## 10. Per-phase fix plans (to 100%)

Per-phase fix plans live as individual files under
[`fix-plans/`](./fix-plans/). Each file is self-contained: current
shipped-%, root cause, gap summary, ordered tasks with file paths +
plan + spec refs + acceptance, and a one-line verification command.

Open only the phase you are working on - the master tracker stays
navigable, and a session that loads one fix plan pays for ~30-80 lines
instead of all 1,000+.

| Phase | File | Current | Root cause |
|-------|------|---------|------------|
| 1a | ~~[phase-1a-database-baseline.md](./fix-plans/phase-1a-database-baseline.md)~~ | 100% | RESOLVED (PR #52) |
| 1b | ~~[phase-1b-db-dashboard-scheduler-notifications.md](./fix-plans/phase-1b-db-dashboard-scheduler-notifications.md)~~ | 100% | RESOLVED (PR #52) |
| 2 | ~~[phase-2-auth-secrets.md](./fix-plans/phase-2-auth-secrets.md)~~ | 100% | RESOLVED |
| 3 | ~~[phase-3-data-provider-adapter.md](./fix-plans/phase-3-data-provider-adapter.md)~~ | 100% | RESOLVED (fix/phase-3-data-provider-adapter) |
| 4 | ~~[phase-4-llm-provider-system.md](./fix-plans/phase-4-llm-provider-system.md)~~ | 100% | RESOLVED (fix/phase-4-llm-provider-system) |
| 5 | ~~[phase-5-llm-runtime.md](./fix-plans/phase-5-llm-runtime.md)~~ | 100% | RESOLVED (fix/phase-5-llm-runtime) |
| 6 | ~~[phase-6-background-task-scheduling.md](./fix-plans/phase-6-background-task-scheduling.md)~~ | 100% | RESOLVED (fix/phase-6-background-task-scheduling) |
| 7 | ~~[phase-7-cli-surface.md](./fix-plans/phase-7-cli-surface.md)~~ | 100% | RESOLVED (fix/phase-7-cli-surface) |
| 8 | ~~[phase-8-frontend-shell.md](./fix-plans/phase-8-frontend-shell.md)~~ | 100% | RESOLVED (fix/phase-8-frontend-shell) |
| 9 | ~~[phase-9-login-account-ui.md](./fix-plans/phase-9-login-account-ui.md)~~ | 100% | RESOLVED (fix/phase-9-login-account-ui) |
| 10 | ~~[phase-10-setup-wizard.md](./fix-plans/phase-10-setup-wizard.md)~~ | 100% | RESOLVED (fix/phase-10-setup-wizard) |
| 11 | ~~[phase-11-settings-page.md](./fix-plans/phase-11-settings-page.md)~~ | 100% | RESOLVED (fix/phase-11-settings-page) |
| 12 | ~~[phase-12-shared-chat-components.md](./fix-plans/phase-12-shared-chat-components.md)~~ | 100% | RESOLVED (fix/phase-12-shared-chat-components) |
| 13 | ~~[phase-13-report-pipeline-secretary.md](./fix-plans/phase-13-report-pipeline-secretary.md)~~ | 100% | RESOLVED (fix/phase-13-report-pipeline-secretary) |
| 14 | ~~[phase-14-equity-research.md](./fix-plans/phase-14-equity-research.md)~~ | 100% | RESOLVED (fix/phase-14-equity-research) |
| 15 | ~~[phase-15-earnings-update.md](./fix-plans/phase-15-earnings-update.md)~~ | 100% | RESOLVED (fix/phase-15-earnings-update) |
| 16 | ~~[phase-16-morning-briefing.md](./fix-plans/phase-16-morning-briefing.md)~~ | 100% | RESOLVED (fix/phase-16-morning-briefing) |
| 17 | ~~[phase-17-formula-engine.md](./fix-plans/phase-17-formula-engine.md)~~ | 100% | RESOLVED (fix/phase-17-formula-engine) |
| 18 | ~~[phase-18-panic-thermometer.md](./fix-plans/phase-18-panic-thermometer.md)~~ | 100% | RESOLVED (fix/phase-18-panic-thermometer) |
| 19 | [phase-19-macro-research.md](./fix-plans/phase-19-macro-research.md) | ~72% | IMPLEMENTER |
| 20 | [phase-20-retail-sentiment.md](./fix-plans/phase-20-retail-sentiment.md) | v1 ~60% / v2 100% | DEFERRED + SPEC_DRIFT |
| 21 | [phase-21-portfolio.md](./fix-plans/phase-21-portfolio.md) | ~55% | mixed |
| 22 | [phase-22-repository.md](./fix-plans/phase-22-repository.md) | ~65% | mixed |
| 23 | [phase-23-docker-packaging-acceptance.md](./fix-plans/phase-23-docker-packaging-acceptance.md) | ~55% | DEFERRED + IMPLEMENTER |
| 24 | ~~[phase-24-design-system-refresh.md](./fix-plans/phase-24-design-system-refresh.md)~~ | 100% | RESOLVED (fix/phase-24-design-system-refresh) |

**How to use:**

1. Pick a phase from section 8 Sprint sequencing.
2. Open its fix plan file.
3. Work tasks top-to-bottom; each task has plan ref + spec ref +
   acceptance criterion baked in.
4. When a task closes, strike through both the section 10 fix-plan
   line AND the matching section 2/3/4 severity-ordered entry (and,
   for NEW-* IDs, the section 11 row).

## 11. Newly minted IDs (from Section 10 fix plans)

Cross-reference for IDs introduced by the per-phase fix plans that are
NOT in §2–§4. These are mostly spec-level gaps (a11y contracts, spec
deferrals, missing submodules, per-phase test debt slices).

| ID            | Phase | Title                                                        | Severity |
|---------------|-------|--------------------------------------------------------------|----------|
| ~~NEW-1a-01~~ | 1a    | ~~Spec-required `CHECK` constraints audit in baseline~~ — migration `2026-04-24-0300_spec_check_constraints.py` + `test_spec_check_constraints.py` (f2b3055) | P1 |
| ~~NEW-1a-02~~ | 1a    | ~~Nightly maintenance sweep job~~ — already shipped in Phase 6 (`scheduler/executors/maintenance.py`); cross-link verified (3bc14f0) | P2 |
| ~~NEW-1b-01~~ | 1b    | ~~`job_runs` FK cascade audit~~ — RETIRED; `schedule_id` is soft-polymorphic per spec (no FK by design) | P2 |
| ~~NEW-1b-02~~ | 1b    | ~~`mb_schedules`/`eu_schedules` `is_enabled` `server_default`~~ — migration `2026-04-24-0200_plan_1b_server_defaults_and_checks.py` + ORM mirror (f2b3055) | P1 |
| ~~NEW-1b-03~~ | 1b    | ~~`pt_presets.is_shipped` `server_default`~~ — same migration (f2b3055) | P1 |
| ~~NEW-1b-04~~ | 1b    | ~~`composite_settings`/`view_config`/`threshold_overrides` JSON `server_default`~~ — same migration (f2b3055) | P1 |
| ~~NEW-1b-05~~ | 1b    | ~~`mr_dashboard_state.assessment_schedule` enum CHECK~~ — added in 0200 migration + ORM `__table_args__` (f2b3055) | P1 |
| ~~NEW-1b-06~~ | 1b    | ~~`rs_snapshots` index missing `DESC`~~ — index recreated DESC on `captured_at` (f2b3055) | P1 |
| ~~NEW-1b-07~~ | 1b    | ~~`database-design.md` §7 stale~~ — spec amended for `rs_classification_log`, MR new columns, table count (f2b3055) | P1 |
| ~~NEW-1b-08~~ | 1b    | ~~Frozen-schema parity test~~ — `test_migration_parity.py` (f2b3055) | P1 |
| ~~NEW-1b-09~~ | 1b    | ~~Catch-up migration step tests~~ — covered in `test_migration_parity.py` (f2b3055) | P1 |
| ~~NEW-1b-10~~ | 1b    | ~~Plan-vs-reality table count (11→12)~~ — Phase 1b plan amended; scope note added to fix plan header (3bc14f0) | P2 |
| ~~NEW-1b-11~~ | 1b    | ~~Phase-15/16 tables mis-attributed to 1b in P0-09~~ — fix-plan header re-scoped to 12-table boundary (3bc14f0) | P2 |
| ~~NEW-1b-12~~ | 1b    | ~~`JobRun` relationship() decision undocumented~~ — model docstring records explicit-join design (3bc14f0) | P2 |
| NEW-2-01      | 2     | Auth rate-limit threshold test                               | P2       |
| ~~NEW-3-01~~  | 3     | ~~`catalog`/`review`/`dispatch`/`python_providers`/`sentiment` stubs~~ — packages added with `__deferred__ = True` markers | P2 |
| ~~NEW-3-02~~  | 3     | ~~Data-provider spec amendment header~~ — Implementation Status table prepended to `data-provider-design.md` | P2 |
| ~~NEW-3-03~~  | 3     | ~~`auto_map` mode-docstring audit~~ — service docstring + route response now both note `mode: heuristic`, NOT the spec's AI review | P2 |
| ~~NEW-3-04~~  | 3     | ~~Setup Wizard Step 2 thin wrapper decision~~ — DECISION: no thin wrapper. Step 2 reuses the existing `POST /settings/data-providers` admin route directly; the wizard frontend will call it. Logged for Plan 10 owners. | P2 |
| ~~NEW-3-05~~  | 3     | ~~Alembic migration for `category`/`mode`/`mcp_url`/`mcp_auth_header`~~ — migration `2026-04-24-0400_data_providers_category_mode_mcp.py` with backfill | P1 |
| ~~NEW-3-06~~  | 3     | ~~`ProviderEntry.extra_config` immutability~~ — wrapped in `MappingProxyType` at validation time | P2 |
| ~~NEW-3-07~~  | 3     | ~~EODHD `_format_ticker` exchange suffix~~ — sourced from `extra_config["exchange_suffix"]` (default `US`) | P2 |
| ~~NEW-3-08~~  | 3     | ~~Better error for legacy MCP rows missing both `base_url` and `mcp_url`~~ — `ProviderEntry._transport_requirements` includes provider id in the message | P2 |
| ~~NEW-4-01~~  | 4     | ~~`build_llm_user_router` (sub of P2-12)~~ — `routes/settings_llm_user.py` mounted at `/settings/models` | P1 |
| ~~NEW-4-02~~  | 4     | ~~`openlia.llm` / `services.auth` public exports alignment~~ — `__init__.py` populated; covered by `test_public_api.py` | P2 |
| ~~NEW-4-03~~  | 4     | ~~Connection-test adapter-registry coverage~~ — adapter retry tests added (`test_adapter_retry.py`) | P2 |
| ~~NEW-4-10~~  | 4     | ~~PUT `/settings/admin/llm/models/{id}` silently drops `tier`/`model_ref`/`provider_id`~~ — `update_model` service + route now wire all fields; `test_update_model_persists_tier_and_model_ref` | P0 |
| ~~NEW-4-11~~  | 4     | ~~User-pref router mis-pathed at `/settings/admin/llm`~~ — `build_llm_user_router` mounts `/settings/models` with roster + `effective/{department_id}` | P0 |
| ~~NEW-4-20~~  | 4     | ~~`with_retries` exported but unused~~ — wrapped in all 6 adapters (anthropic/openai/gemini/openrouter/openai_compat/ollama) | P1 |
| ~~NEW-4-21~~  | 4     | ~~`openlia.llm.__init__` empty~~ — full public API re-exported | P1 |
| ~~NEW-4-22~~  | 4     | ~~Wizard Step 3 `POST /setup/models` + `/setup/models/test` missing~~ — handlers added in `routes/setup.py`; `test_e2e_wizard_models.py` | P1 |
| ~~NEW-4-23~~  | 4     | ~~No `evaluate_requirements` / per-dept `REQUIREMENTS`~~ — `capabilities.evaluate_requirements`, `department_requirements.DEPARTMENT_REQUIREMENTS`, `test_capabilities_gate.py` | P1 |
| ~~NEW-4-24~~  | 4     | ~~`remote-models` 500s for openrouter/ollama~~ — route returns `{skipped:true}`; admin tests | P1 |
| ~~NEW-4-25~~  | 4     | ~~openai_compat advertised_capabilities not capturable~~ — `_ModelIn.advertised_capabilities`; auto-writes capability_override row | P1 |
| ~~NEW-4-26~~  | 4     | ~~`get_provider_api_key` 500s on tampered ciphertext~~ — wraps `DecryptError` -> `AuthError`; service test added | P1 |
| ~~NEW-4-27~~  | 4     | ~~`run_test` defaulted to false~~ — defaults to true; explicit opt-out requires `skip_reason` | P1 |
| ~~NEW-4-30~~  | 4     | ~~`SHIPPED_TIER_DEFAULTS` not exported~~ — re-exported from `openlia.llm` | P2 |
| ~~NEW-4-31~~  | 4     | ~~`uq_llm_models_tier_default` partial index missing `postgresql_where`~~ — added on ORM + baseline migration | P2 |
| ~~NEW-4-32~~  | 4     | ~~`ModelsSection` placeholder + missing admin panel~~ — section renders three-tier roster against `/settings/models`; admin panel lists provider+model CRUD with delete/set-default | P2 |
| ~~NEW-4-33~~  | 4     | ~~OpenAI `context_window` always None~~ — falls back to `capabilities_for(...).max_context_tokens` | P2 |
| ~~NEW-4-34~~  | 4     | ~~`update_provider` cannot clear `env_var_name`/`api_key`~~ — `_Unchanged` sentinel + `clear_api_key`/`clear_env_var_name` flags | P2 |
| ~~NEW-4-35~~  | 4     | ~~`_TRANSIENT`/`is_transient` not re-exported~~ — `is_transient` exposed via `openlia.llm` | P2 |
| ~~NEW-4-36~~  | 4     | ~~`_http.py` may be empty~~ — verified contains `make_client`/`status_to_exception`/`wrap_httpx_error` | P2 |
| ~~NEW-4-37~~  | 4     | ~~No `SQLModelRegistry` ↔ `resolve()` integration test~~ — covered by existing `test_llm_registry.py` (4-stage round-trip) | P2 |
| ~~NEW-4-38~~  | 4     | ~~No wizard-Step-3 → DB → `resolve()` e2e~~ — `test_e2e_wizard_models.py` posts three tiers, asserts persistence + resolver | P2 |
| ~~NEW-4-39~~  | 4     | ~~`OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_TIER` env override unwired~~ — `SQLModelRegistry.get_department_tier_override` consults env first | P2 |
| ~~NEW-4-40~~  | 4     | ~~Department default tier mapping audit~~ — confirmed seven entries in both spec and `department_defaults.py` | P2 |
| NEW-5-01      | 5     | Runtime events + messages unit tests                         | P2       |
| NEW-7-01      | 7     | `test_serve_prints_banner` (pair with P2-07)                 | P2       |
| NEW-8-01      | 8     | Mobile responsive sidebar / tab bar                          | P1       |
| NEW-8-02      | 8     | Collapsed-mode tooltip a11y                                  | P2       |
| NEW-9-01      | 9     | `aria-describedby` on all auth form inputs                   | P1       |
| NEW-9-02      | 9     | `aria-busy` on primary submit buttons                        | P2       |
| NEW-9-03      | 9     | AccountManagementSpec parity audit                           | P2       |
| NEW-10-01     | 10    | Reconcile two SetupWizard spec files                         | P2       |
| NEW-10-02     | 10    | Step 3 `tier_complete` frontend gate                         | P1       |
| NEW-10-03     | 10    | Concurrent-session takeover dialog                           | P2       |
| NEW-11-01     | 11    | SettingsPageSpec per-tab parity audit                        | P2       |
| NEW-12-01     | 12    | FileDownloadSpec dropdown contract                           | P1       |
| NEW-12-02     | 12    | SaveToRepoSpec toast + idempotency                           | P1       |
| NEW-12-03     | 12    | ChatInterfaceSpec streaming-cursor / cancel                  | P1       |
| NEW-13-01     | 13    | `RedirectCard` Secretary chat block                          | P1       |
| NEW-13-02     | 13    | Secretary welcome-state animations + stop label              | P2       |
| NEW-13-03     | 13    | Secretary route backend tests                                | P2       |
| NEW-14-01     | 14    | Restore spec-compliant ER Active layout                      | P1       |
| NEW-14-02     | 14    | `FromPortfolioPicker` popover                                | P2       |
| NEW-15-01     | 15    | EU page FileViewer + sidebar dot wiring                      | P1       |
| NEW-15-02     | 15    | EU Watchlist Overdue + New-badge + market badge colors       | P2       |
| NEW-15-03     | 15    | EU Cabinet search + filter dropdown                          | P2       |
| NEW-15-04     | 15    | EU loading skeleton                                          | P2       |
| NEW-15-05     | 15    | EU Cabinet remove-confirmation tooltip                       | P2       |
| NEW-16-01     | 16    | MB frontend vitests (Archive/Settings/OnDemand)              | P2       |
| NEW-16-02     | 16    | MB chat-session hook test + matrix row                       | P2       |
| NEW-17-01     | 17    | Formula spec reconciliation writeup                          | P1       |
| NEW-17-02     | 17    | `RuleSet` + `evaluate_ruleset`                               | P1       |
| NEW-17-03     | 17    | Reserved derived scalars (`derived.py`)                      | P1       |
| NEW-17-04     | 17    | `AND`/`OR`/`NOT` keyword aliases                             | P2       |
| NEW-17-05     | 17    | `days_since` / `cross_above` / `cross_below` functions       | P1       |
| NEW-18-01     | 18    | Oil + WageGrowth drill-down dashboards                       | P1       |
| NEW-18-02     | 18    | Inflation + FedLanguage + Diplomacy drill-downs              | P1       |
| NEW-18-03     | 18    | RuleEditor + FormulaInput + PanelSettingsPane                | P1       |
| NEW-18-04     | 18    | ManualOverride + ImportExport + PresetLibrary                | P2       |
| NEW-18-05     | 18    | PT server + per-panel tests                                  | P2       |
| NEW-18-06     | 18    | PT auto-refresh dropdown verification                        | P2       |
| NEW-19-01     | 19    | MR Settings panel + ScheduleEditor wiring                    | P1       |
| NEW-19-02     | 19    | MR Summary tab + auto-refresh                                | P2       |
| NEW-19-03     | 19    | MR backend tests (14 files)                                  | P2       |
| NEW-19-04     | 19    | MR frontend tests (6 files)                                  | P2       |
| NEW-19-05     | 19    | MR matrix rows                                               | P2       |
| NEW-20-01     | 20    | RS scheduler integration (`JobType.RS_SNAPSHOT`)             | P1       |
| NEW-20-02     | 20    | RS `/schedule` routes                                        | P1       |
| NEW-20-03     | 20    | RS metrics 8–12                                              | P1       |
| NEW-20-04     | 20    | RS narrative synthesis LLM call                              | P1       |
| NEW-20-05     | 20    | RS frontend decomposition                                    | P1       |
| NEW-20-06     | 20    | RS typed API client + hooks                                  | P2       |
| NEW-21-01     | 21    | Portfolio decomposition into 15 components + 4 hooks         | P1       |
| NEW-21-02     | 21    | Portfolio → ER ticker navigation                             | P1       |
| NEW-21-03     | 21    | Portfolio toast + Undo                                       | P2       |
| NEW-21-04     | 21    | Portfolio groups reorder + rename + delete                   | P2       |
| NEW-21-05     | 21    | Portfolio market-closed/stale states + swipe + sort persist  | P2       |
| NEW-22-01     | 22    | `useRepoList` hook                                           | P2       |
| NEW-22-02     | 22    | Repository decomposition                                     | P1       |
| NEW-22-03     | 22    | Repository department-tinted badges                          | P2       |
| NEW-22-04     | 22    | Repository undo toast                                        | P2       |
| NEW-23-01     | 23    | cloudflare-tunnel + caddy compose recipes                    | P1       |
| NEW-23-02     | 23    | `RELEASING.md`                                               | P2       |
| NEW-23-03     | 23    | CI Docker-build smoke job                                    | P1       |
| NEW-23-04     | 23    | `test_wheel_contents.py`                                     | P2       |
| NEW-23-05     | 23    | Cookie/proxy integration + env-snapshot tests                | P2       |
| NEW-23-06     | 23    | README Quickstart + CHANGELOG stub                           | P2       |
| NEW-24-01     | 24    | Deepen `Card.test.tsx` to assert hover bar + olive border    | P2       |
| NEW-24-02     | 24    | `DataRow.test.tsx` + `MonoLabel.test.tsx` smoke tests        | P2       |
| NEW-24-03     | 24    | Restore `Sidebar.test.tsx` width assertions (220/52)         | P2       |
| NEW-24-04     | 24    | NavItem rail-on-active test                                  | P2       |
| NEW-24-05     | 24    | Document six `--color-sidebar-*` tokens beyond plan          | P2       |
| NEW-24-06     | 24    | Setup wizard sweep (plan Task 14)                            | P1       |
| NEW-24-07     | 24    | Pre-Phase-24 primitives audit (Banner/FormField/Pwd*)        | P2       |
| NEW-24-08     | 24    | AuthLayout/Sidebar inline-style → Tailwind class swap        | P2       |
| NEW-24-09     | 24    | Lock no-blue-tokens contract on report themes (vitest)       | P2       |
| NEW-24-10     | 24    | Final acceptance walkthrough doc + build smoke               | P2       |
| NEW-24-11     | 24    | Lock no-hex-literals contract on src (vitest)                | P2       |

When closing any NEW-* item, strike through the row above AND the
matching numbered task in §10.
