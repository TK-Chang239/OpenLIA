# Implementation Plans — Roadmap

This directory holds the per-feature implementation plans that turn the specs in `planning/specs/` into shipping code. Each plan is a self-contained, TDD-style, bite-sized task list executable via `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

## Status

| # | Phase | Plan | Status | File |
|---|---|---|---|---|
| 0 | 0 | Workspace scaffolding | **Done** (2026-04-16) | `2026-04-16-phase-0-scaffolding.md` |
| 1a | 1 | Database baseline — auth/config/content/infrastructure (22 tables) | Done (2026-04-18) | `2026-04-16-phase-1a-database-baseline.md` |
| 1b | 1 | Database baseline — dashboard/scheduler/notifications (11 tables) | Draft | `2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md` |
| 2 | 1 | Secrets encryption + auth primitives | Draft | `2026-04-16-phase-2-auth-and-secrets.md` |
| 3 | 2 | Data provider adapter system | Draft | `2026-04-16-phase-3-data-provider-adapter-system.md` |
| 4 | 2 | LLM provider system | Draft | `2026-04-16-phase-4-llm-provider-system.md` |
| 5 | 2 | LLM runtime (runners, prompt loader, SSE) | Draft | `2026-04-17-phase-5-llm-runtime.md` |
| 6 | 3 | Background task scheduling | Draft | `2026-04-17-phase-6-background-task-scheduling.md` |
| 7 | 3 | CLI surface (`admin`, `wizard reset`, `secrets rotate-key`, `maintenance`) | Draft | `2026-04-17-phase-7-cli-surface.md` |
| 8 | 4 | Frontend shell (routing, auth context, layout, design tokens) | Draft | `2026-04-17-phase-8-frontend-shell.md` |
| 9 | 4 | Login + Account Management UI | Draft | `2026-04-17-phase-9-login-and-account-ui.md` |
| 10 | 4 | Setup Wizard | Draft | `2026-04-17-phase-10-setup-wizard.md` |
| 11 | 4 | Settings page | Draft | `2026-04-17-phase-11-settings-page.md` |
| 12 | 4 | Shared chat components (ChatInterface, ChatHistory, FileViewer, FileDownload, SaveToRepo) | Draft | `2026-04-17-phase-12-shared-chat-components.md` |
| 13 | 5 | Report rendering pipeline + Secretary department | Draft | `2026-04-17-phase-13-report-pipeline-and-secretary.md` |
| 14 | 5 | Equity Research department (initiation / update / sector) | Draft | `2026-04-17-phase-14-equity-research.md` |
| 15 | 5 | Earnings Update department + scan scheduling | Draft | `2026-04-17-phase-15-earnings-update.md` |
| 16 | 5 | Morning Briefing department + briefing scheduling | Not started | — |
| 17 | 6 | Formula engine DSL | Not started | — |
| 18 | 6 | Panic Thermometer page | Not started | — |
| 19 | 6 | Macro Research Dalio dashboards (5 dashboards) | Not started | — |
| 20 | 6 | Retail Sentiment dashboard (12 metrics, 3 tabs) | Not started | — |
| 21 | 7 | Portfolio page | Not started | — |
| 22 | 7 | Repository page | Not started | — |
| 23 | 7 | Docker packaging + production build + final acceptance | Not started | — |

---

## Phase 1 — Persistence foundation

Goal: everything above the data layer needs a database and encrypted secrets. Phase 1 makes those exist.

### Plan 1 — Database baseline

- **Spec:** `planning/specs/systems/database-design.md` (29 tables, 11 sections)
- **Scope:** SQLAlchemy 2.x models for all 29 tables, Alembic baseline migration, `openlia_server/db/session.py` + engine factory with SQLite WAL mode, `~/.openlia/` bootstrap, DB path resolution (env override + default), auto-migrate on `openlia serve` startup.
- **Depends on:** Phase 0.
- **Unblocks:** every plan from 2 onward.
- **Scale:** large (29 tables, migration machinery) — may be split into 1A (core tables) + 1B (dashboard / scheduler / notifications tables) if too large for a single plan.

### Plan 2 — Secrets encryption + auth primitives

- **Specs:** `database-design.md` §5 (encryption), `AccountManagementSpec.md`, `LoginPageSpec.md` (server-side pieces only).
- **Scope:** AES-256-GCM secrets module (`openlia/security/secrets.py`), `OPENLIA_SECRET_KEY` env + `~/.openlia/secret.key` 0600 fallback, row-id AAD, Argon2id password hashing, opaque session tokens, session middleware (toggleable auth), invite-only registration service, admin-approved password reset flow, `password_reset_requests` management, no UI (server + DB only).
- **Depends on:** Plan 1 (tables `users`, `sessions`, `invites`, `password_reset_requests`).
- **Unblocks:** Plan 3/4 (store encrypted provider API keys), Plan 7 (admin CLI), Plan 9 (Login UI).

---

## Phase 2 — Providers (data + LLM + runtime)

Goal: a department is (provider + runtime + prompts + routes). Phase 2 builds the first three in order.

### Plan 3 — Data provider adapter system

- **Spec:** `planning/specs/systems/data-provider-design.md`
- **Scope:** Adapter base class (`openlia/data/base.py`), requirements manifest (`data/manifest/requirements.yaml` — union of all department needs), EODHD adapter (as the default), per-category provider configuration model, `data_providers` + `data_provider_requirement_mapping` table CRUD, admin routes (`/settings/data-providers/*`), capability resolver (given a requirement type, which provider serves it).
- **Depends on:** Plans 1, 2.
- **Unblocks:** every department plan (5.x and 6.x).

### Plan 4 — LLM provider system

- **Spec:** `planning/specs/systems/llm-provider-design.md`
- **Scope:** Six provider adapters (OpenAI, Anthropic, Gemini, OpenRouter, OpenAI-compatible, Ollama) with a common `LLMProvider` interface, capability map (`core/llm/capabilities.py`), three-tier model-role structure (Thinking / Everyday / Quick), admin-managed model roster + `user_llm_preferences` pointer table, resolver (user preference → tier default → any enabled → `TierNotConfiguredError`), connection-testing flow, `/settings/models/*` routes.
- **Depends on:** Plans 1, 2.
- **Unblocks:** Plan 5.

### Plan 5 — LLM runtime (runners, prompt loader, SSE)

- **Spec:** `planning/specs/systems/llm-runtime-design.md`
- **Scope:** Three runners (`ChatRunner`, `ReportRunner`, `BatchRunner`) under `openlia/llm/runtime/`, per-department YAML prompt loader with Jinja2, framework JSON + style-guide markdown injection, tool-schema construction (requirement tools + `find_more_data` + `web_search`), `chat.*` / `report.*` SSE event taxonomy, hybrid web-search sourcing (provider-native → Brave/Tavily/Serper/You.com fallback), cancellation via client disconnect, `TierNotConfiguredError` surfaced as dedicated SSE error events.
- **Depends on:** Plans 3, 4.
- **Unblocks:** every department plan.

---

## Phase 3 — Scheduling & operational surface

### Plan 6 — Background task scheduling

- **Spec:** `planning/specs/systems/background-task-scheduling-design.md`
- **Scope:** APScheduler 4.x `AsyncScheduler` inside the FastAPI lifespan, four job types (MB briefing, EU scan, MR assessment, nightly maintenance), per-user schedule tables (`mb_schedules`, `eu_schedules`), DB-as-source-of-truth rebuild on startup (MB + EU only — see note), missed-job 6-hour grace catch-up via croniter, 3× exponential retry (30/120/480s), template-method `BaseExecutor` with concrete MB/EU/MR/Maintenance subclasses, fail-fast stub Protocols for department payload builders (`MBRequestBuilder`, `EUScanPlanner`, `MRAssessmentBuilder`, `ReportStore`, `MRCacheStore`) wired up in `scheduler/wiring.py`, failure records in `job_runs`, polling routes (`/jobs/history`, `/jobs/{run_id}/retry`, `/notifications/unread`, `/notifications/read`).
- **Depends on:** Plans 1A, 1B, 2, 4, 5.
- **Unblocks:** scheduled departments (Plans 15, 16, 19).
- **Note:** MR scheduling rehydration on startup is deferred — Plan 1B's `mr_dashboard_state` does not carry `assessment_schedule` / `last_assessment_at` columns. Plan 19 will add those columns and register MR jobs via `SchedulerService.add_schedule()` at its own startup path. The `MRAssessmentExecutor` itself ships complete in Plan 6.

### Plan 7 — CLI surface

- **Spec:** `planning/specs/systems/cli-surface-design.md`
- **Scope:** Expand the Typer app from Phase 0 to add `admin` (9 user/invite/session management subcommands), `wizard reset`, `secrets rotate-key`, `maintenance`. All non-`serve` commands connect directly to the DB without the server running. `WAL`-aware locking for `secrets rotate-key` (exclusive access).
- **Depends on:** Plans 1, 2 (DB + secrets), Plan 6 (maintenance sweep reuses scheduler pruning logic).
- **Unblocks:** company-mode deployment (admin can create the first invite from the CLI).

---

## Phase 4 — Frontend shell & core UX

Goal: the shell and core screens (login, wizard, settings) that every department page plugs into.

### Plan 8 — Frontend shell

- **Specs:** `planning/specs/components/SideBarSpec.md`, (plus design token conventions drawn from across specs)
- **Scope:** App layout (sidebar + main + optional file viewer pane), React Router routes, auth context + API client with session-cookie handling, design-token layer (CSS custom properties), base component primitives (Button, Input, Card, etc.), sidebar with notification-dot polling against `/notifications`, dev-mode proxy wiring.
- **Depends on:** Plan 2 (session endpoints), Plan 6 (notifications endpoint).
- **Unblocks:** every page plan.

### Plan 9 — Login + Account Management UI

- **Specs:** `planning/specs/pages/LoginPageSpec.md`, `planning/specs/components/AccountManagementSpec.md`
- **Scope:** Login page, Reset Password request page, Must Change Password view, invite-gated registration UI, account section in Settings. Company-mode only; personal-mode bypasses login entirely.
- **Depends on:** Plans 2, 8.
- **Unblocks:** Plan 10 (wizard company mode requires login).

### Plan 10 — Setup Wizard

- **Spec:** `planning/specs/pages/SetupWizardSpec.md`
- **Scope:** Dual-mode wizard (personal / company), mode selector, AI model config (three tiers), data provider config (per-category), Web Search tab, AI review step for department readiness, env-var-override read-only rendering, `/setup/*` endpoints (15 routes), DB-canonical config storage.
- **Depends on:** Plans 3, 4, 5, 8, 9.
- **Unblocks:** users can actually boot into the app → all subsequent pages become testable end-to-end.

### Plan 11 — Settings page

- **Spec:** `planning/specs/pages/SettingsPageSpec.md`
- **Scope:** Four sections — Models (user picker over admin roster + admin CRUD), Data Providers (admin CRUD), Admin (invites, users, reset requests), Account (profile, password, sessions). Admin section gated to `role=admin`.
- **Depends on:** Plans 3, 4, 8, 9.
- **Unblocks:** post-wizard config changes without re-running the wizard.

### Plan 12 — Shared chat components

- **Specs:** `ChatInterfaceSpec.md`, `ChatHistorySpec.md`, `FileViewerSpec.md`, `FileDownloadSpec.md`, `SaveToRepoSpec.md`
- **Scope:** Chat pane with token-by-token SSE streaming, chat-history drawer, file-viewer (markdown, PDF, charts), file download trigger, save-to-repo dialog. Pure UI components — department pages plug these in.
- **Depends on:** Plans 5 (SSE event types), 8.
- **Unblocks:** every department UI.

---

## Phase 5 — Report-generating departments

Goal: the four departments that produce narrative text reports via `ReportRunner`.

### Plan 13 — Report rendering pipeline + Secretary

- **Specs:** `planning/specs/systems/report-rendering-pipeline-design.md`, `planning/specs/pages/departments/SecretaryPageSpec.md`
- **Scope:** Report composition layer (framework JSON + style guide → prompt → LLM → structured JSON → markdown render), `report.*` SSE event taxonomy, `ReportSchema` payload on `report.complete`, framework/style-guide physical move from `planning/frameworks/` into `packages/core/src/openlia/reports/frameworks/`. Secretary is the simplest chat-only department and validates the whole pipeline end-to-end.
- **Depends on:** Plans 5, 12.
- **Unblocks:** the other three report-generating departments.

### Plan 14 — Equity Research department

- **Spec:** `planning/specs/pages/departments/EquityResearchPageSpec.md`
- **Scope:** Three modes (initiation, stock update, sector research), per-mode framework JSON + style guide, YAML prompts, data-requirement mapping (`stock_quote`, `company_profile`, `financial_statements`, `earnings_data`, `analyst_ratings`, `insider_transactions`, etc.), chat history, file artifacts.
- **Depends on:** Plan 13.

### Plan 15 — Earnings Update department + scan scheduling

- **Spec:** `planning/specs/pages/departments/EarningsUpdatePageSpec.md`
- **Scope:** Scorecard-focused post-earnings report (beat/miss, guidance, thesis check), EU scan scheduler job, `eu_schedules` user config, earnings-calendar data requirement, `job_runs` integration for failure surfacing.
- **Depends on:** Plans 6, 13.

### Plan 16 — Morning Briefing department + briefing scheduling

- **Spec:** `planning/specs/pages/departments/MorningBriefingsPageSpec.md`
- **Scope:** 7-section standard briefing + user-defined custom sections, Reference Portfolio toggle, `mb_schedules` user config, MB briefing scheduler job.
- **Depends on:** Plans 6, 13, 21 (Portfolio — for Reference Portfolio data).
  - Note: if Plan 21 isn't ready, Reference Portfolio can be gated off in v1 and wired in a follow-up.

---

## Phase 6 — Dashboard departments

Goal: the four departments that render computed metrics + LLM assessments, not narrative reports.

### Plan 17 — Formula engine DSL

- **Spec:** `planning/specs/systems/formula-engine-design.md`
- **Scope:** DSL parser, evaluator, safe-eval context, requirement-tool integration, shared by PT (threshold rules) and MR T1/T2 (metric computation). Standalone library — no department code.
- **Depends on:** Plan 3 (data providers supply the numeric inputs).
- **Unblocks:** Plans 18, 19.

### Plan 18 — Panic Thermometer page

- **Spec:** `planning/specs/pages/departments/PanicThermometerPageSpec.md`
- **Scope:** Data context panels, threshold-based rules, composite scoring, per-panel settings, preset libraries, import/export, `pt_user_configs` / `pt_presets` tables.
- **Depends on:** Plan 17.

### Plan 19 — Macro Research Dalio dashboards

- **Specs:** `planning/specs/pages/departments/MacroResearchPageSpec.md`, `planning/specs/systems/macro-research-dalio-dashboards-design.md`
- **Scope:** Five dashboards (Debt Cycle, Four Seasons, All-Weather Portfolio, World Order, Five Forces), T1/T2 formula-engine evaluation, T3 computational risk math, T4/T5 LLM assessment (cron schedule), `mr_dashboard_state` / `mr_assessment_cache` tables, Smart Mode threshold adjustments.
- **Depends on:** Plans 6, 17.

### Plan 20 — Retail Sentiment dashboard

- **Specs:** `planning/specs/pages/departments/RetailSentimentPageSpec.md`, `planning/specs/systems/retail-sentiment-dashboard-design.md`
- **Scope:** 12 metrics, 3 analytical tabs, batch NLP classification, cross-source validation, `rs_user_config` / `rs_snapshots` / `rs_classification_log` tables, reliability matrix, engagement weighting.
- **Depends on:** Plans 3, 5, 6.

---

## Phase 7 — Ancillary pages + packaging

### Plan 21 — Portfolio page

- **Spec:** `planning/specs/pages/PortfolioPageSpec.md`
- **Scope:** Holdings CRUD, intraday-price refresh, position analytics, integration hook for MB Reference Portfolio toggle.
- **Depends on:** Plans 3, 8.

### Plan 22 — Repository page

- **Spec:** `planning/specs/pages/RepositoryPageSpec.md`
- **Scope:** Saved reports browser, file-viewer integration, tag/search, delete/archive, tied to the `SaveToRepo` dialog from Plan 12.
- **Depends on:** Plans 8, 12, 13.

### Plan 23 — Docker packaging + production build + final acceptance

- **Specs:** `planning/PLAN.md` §Deployment, `planning/specs/pages/SetupWizardSpec.md` §Company mode
- **Scope:** Multi-stage Dockerfile (frontend build → Python runtime), `docker-compose` examples (Cloudflare Tunnel, Caddy reverse proxy, LAN-only), `pip install openlia` flow from PyPI, end-to-end smoke test for both deployment modes, production-mode FastAPI static-file serving, `OPENLIA_TRUST_PROXY_HEADERS` / `OPENLIA_COOKIE_SECURE` wiring.
- **Depends on:** everything.

---

## Guidance for writing each plan

1. **Read the source-of-truth spec first.** The GAPS.md entries for each spec list unresolved questions — resolve them in the plan (or explicitly defer with a rationale) before decomposing tasks.
2. **Follow `superpowers:writing-plans` format.** Every task: exact file paths, complete code (no "fill in"), exact commands, expected output, TDD-first.
3. **Cap tasks at 2-5 minutes each.** A task that writes a failing test is one task; running it is the next.
4. **State dependencies explicitly.** If Plan N requires something from Plan M that hasn't been executed, either (a) defer the dependent slice to a follow-up plan, or (b) sequence N after M.
5. **One working feature per plan.** Don't ship half a department — if a plan can't end with "this department is usable," split it differently.
6. **Update this index** when a plan is written (file column) and again when it's executed (status column).

## Conventions

- **Filenames:** `YYYY-MM-DD-phase-N-<slug>.md` where slug describes the plan's scope (e.g., `phase-1-database-baseline`).
- **Status values:** `Not started` | `Draft` (written but not reviewed) | `Ready` (reviewed and ready to execute) | `In progress` | `Done`.
- **Branch names:** one branch per plan, `feat/phase-N-<slug>`.
- **Commits:** one commit per task (or per atomic sub-step) within the plan.
