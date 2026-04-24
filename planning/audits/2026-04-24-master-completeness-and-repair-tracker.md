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

---

## 1. Phase status snapshot

All 23 plans are marked `Done` in the README. The "shipped %" column is a
rough estimate from the 2026-04-24 per-phase reviews and reflects how much
of the *plan + spec* surface actually shipped, not just whether the plan
merged.

| #  | Plan                                | Plan status | Shipped % | Dominant root cause       | Headline gap                                                                 |
|----|-------------------------------------|-------------|-----------|---------------------------|-------------------------------------------------------------------------------|
| 1a | DB Baseline                         | Done        | ~90%      | IMPLEMENTER               | Hand-written `2026-04-16-1200_baseline.py` migration missing                 |
| 1b | DB Dashboard/Scheduler/Notif        | Done        | ~95%      | IMPLEMENTER               | `mr_dashboard_state` + `rs_classification_log` model/migration drift          |
| 2  | Auth & Secrets                      | Done        | ~92%      | IMPLEMENTER               | `build_require_auth` returns `Depends()` and breaks nested deps              |
| 3  | Data Provider Adapter               | Done        | ~95%      | DEFERRED                  | Cleanest phase — only `company_fundamentals` capability deferred             |
| 4  | LLM Provider System                 | Done        | ~72%      | IMPLEMENTER               | User-preference HTTP routes never wired (service layer present)              |
| 5  | LLM Runtime                         | Done        | ~88%      | IMPLEMENTER               | `await_with_grace` unused; MR/MB prompt files absent; no startup slot check  |
| 6  | Background Scheduler                | Done        | ~92%      | IMPLEMENTER               | `batch_runner=None` → MR jobs crash; dual `MRScheduleService` instances      |
| 7  | CLI Surface                         | Done        | ~97%      | RESOLVED                  | Best-shipped phase — only `serve` startup banner missing                     |
| 8  | Frontend Shell                      | Done        | ~95%      | IMPLEMENTER + SPEC_DRIFT  | Design tokens diverged to Wondermakers/Acid Yellow palette                   |
| 9  | Login / Account UI                  | Done        | ~88%      | IMPLEMENTER               | Server requires `display_name`; `aria-describedby` missing                   |
| 10 | Setup Wizard                        | Done        | ~72%      | IMPLEMENTER               | Step 3 (Models) backend handlers don't exist (frontend hits 404)             |
| 11 | Settings Page                       | Done        | ~72%      | IMPLEMENTER               | New routes use `build_require_auth`, bypass must-change-password             |
| 12 | Shared Chat Components              | Done        | ~90%      | IMPLEMENTER               | `Department` union covers 2 of 7; zero frontend vitests                      |
| 13 | Report Pipeline & Secretary         | Done        | ~75%      | IMPLEMENTER               | Secretary HTTP route never created                                           |
| 14 | Equity Research                     | Done        | ~83%      | IMPLEMENTER               | Active layout diverges from spec; `POST /chat` drops `session_id`            |
| 15 | Earnings Update                     | Done        | ~78%      | IMPLEMENTER               | `/schedules` route absent; `EarningsUpdatePage.tsx` absent                   |
| 16 | Morning Briefing                    | Done        | ~82%      | IMPLEMENTER               | `mb_user_configs` migration absent; prompt/builder JSON-blob mismatch        |
| 17 | Formula Engine                      | Done        | ~70%      | SPEC_DRIFT                | Plan vs design spec describe materially different DSLs                       |
| 18 | Panic Thermometer                   | Done        | ~72%      | DEFERRED + IMPLEMENTER    | 5 drill-down dashboards + rule editor deferred; server tests missed          |
| 19 | Macro Research                      | Done        | ~72%      | IMPLEMENTER               | Settings panel never built; `POST /assessment/run` is a stub                 |
| 20 | Retail Sentiment                    | Done        | v1: 60% / v2-bundle: 100% | DEFERRED        | v2-full deferred; `rs_classification_log` migration unconfirmed              |
| 21 | Portfolio                           | Done        | ~55%      | DEFERRED + IMPLEMENTER    | 17-component frontend collapsed to monolith; price provider noop             |
| 22 | Repository                          | Done        | ~65%      | DEFERRED + IMPLEMENTER    | FileViewer click-to-open missing (not in deferred list)                      |
| 23 | Docker / Acceptance                 | Done        | ~55%      | IMPLEMENTER + DEFERRED    | Smoke suite, CI Docker job, RELEASING.md absent; deploy structure wrong      |

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

- [ ] **P0-06 — Fix `build_require_auth` return shape.**
  - Bug: returns `Depends(require_auth)`; FastAPI does not evaluate nested
    `Depends` stored as inner-function defaults. Already observed as test
    failure (memory observation 850).
  - Files: `packages/server/src/openlia_server/middleware/auth.py` ~lines
    68–75 and 91–100.
  - Source: Phase 2 review.

- [ ] **P0-07 — Apply `build_require_active_user` to `/settings/prefs`,
  `/settings/email`, `/settings/admin/llm`.**
  - Bug: shipped routes use `build_require_auth`; must-change-password users
    can edit settings. Direct violation of REM-P1-001 acceptance criteria.
  - Files: `packages/server/src/openlia_server/routes/settings_general.py`
    (line 49), `routes/settings_email.py` (line 22),
    `routes/settings_models.py` (line 24).
  - Source: Phase 11 review.

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
    - `2026-04-16-1200_baseline.py` — Phase 1a baseline file (only
      `.gitkeep` in versions/ today).
    - `mr_dashboard_state` add `assessment_schedule`, `last_assessment_at`
      (Phase 1b drift).
    - `rs_classification_log` create_table (Phase 1b/20 drift; expected by
      `test_migrations.py` EXPECTED_TABLES but never created).
    - `user_prefs` create_table (Phase 11).
    - `mb_user_configs` create_table (Phase 16).
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

- [ ] **P1-11 — Phase 4 `update_model` route accepts fields it silently
  drops.** `_ModelIn` body includes `model_ref` and `tier`; service call
  passes only `display_name`, `is_tier_default`, `is_enabled`,
  `overrides`. Edit-model UI lies about what it persists. File:
  `packages/server/src/openlia_server/routes/settings.py` lines 604–637.

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

- [ ] **P1-25 — Phase 20 `rs_classification_log` Alembic migration
  unverified.** Model exists in `dashboard.py`; migration file presence
  not confirmed. Same Postgres deploy risk as P0-09 (covered there).

- [ ] **P1-26 — Phase 8 design tokens diverged from plan to Wondermakers /
  Acid Yellow.** Functionally fine; **decision needed**: amend the plan
  to the as-built tokens, or roll the tokens back. Don't leave it
  ambiguous.

- [ ] **P1-27 — End-to-end smoke matrix completion (REM-P1-019).** 11
  product journeys landed in `test_e2e_smoke_matrix.py` (covers personal
  setup, company invite/register, provider CRUD, password reset, repo
  save/open/unsave, Secretary chat, MB follow-up, ER on-demand, EU
  on-demand, EU schedule→notification). Open: container-boot curl —
  blocked on Docker daemon (covered by P0-10).

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

- [ ] **P2-02 — `route-authorization-matrix.md` path inconsistency.**
  REM-P0-006 references `planning/route-authorization-matrix.md`; file
  resolves at `planning/implementation-plans/route-authorization-matrix.md`.
  Either move the file or update the cross-references.

- [ ] **P2-03 — `services/auth/__init__.py` is empty.** Plan required
  re-exports of public API. Consumers import sub-modules directly today
  (works), but `from openlia_server.services.auth import authenticate`
  fails contract.

- [ ] **P2-04 — Phase 1a `models/__init__.py` includes `dashboard`,
  `scheduler`, `departments`** alongside Plan-1A modules; docstring still
  says these were added "in Plan 1B". Update docstring + decide whether
  the Plan-1B+ imports belong in baseline.

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

- [ ] **P2-11 — Phase 4 `/admin/llm/*` vs `/settings/admin/llm/*` prefix.**
  Spec uses the former; shipped uses the latter. Amend the spec to match
  the shipped prefix (already locked in cross-plan contracts as
  `/settings/admin/llm/*`).

- [ ] **P2-12 — Phase 4 user-preference router missing.** Service-layer
  helpers exist; `build_llm_user_router` was never created. Either ship
  the router or remove the helpers and amend the plan.

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

- [ ] **P2-17 — Phase 12 zero frontend vitests.** Plan Task 20 mandated a
  smoke suite. Schedule when time permits.

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

6. P0-06 Fix `build_require_auth` return shape.
7. P0-07 Apply `build_require_active_user` to settings routes.
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
