# Implementation Plans — Roadmap

This directory holds the per-feature implementation plans that turn the specs in `planning/specs/` into shipping code. Each plan is a self-contained, TDD-style, bite-sized task list executable via `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

## Status

| # | Phase | Plan | Status | File |
|---|---|---|---|---|
| 0 | 0 | Workspace scaffolding | **Done** (2026-04-16) | `2026-04-16-phase-0-scaffolding.md` |
| 1a | 1 | Database baseline — auth/config/content/infrastructure (22 tables) | Done (2026-04-18) | `2026-04-16-phase-1a-database-baseline.md` |
| 1b | 1 | Database baseline — dashboard/scheduler/notifications (11 tables) | Done | `2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md` |
| 2 | 1 | Secrets encryption + auth primitives | Done | `2026-04-16-phase-2-auth-and-secrets.md` |
| 3 | 2 | Data provider adapter system | Done | `2026-04-16-phase-3-data-provider-adapter-system.md` |
| 4 | 2 | LLM provider system | Done (2026-04-19) | `2026-04-16-phase-4-llm-provider-system.md` |
| 5 | 2 | LLM runtime (runners, prompt loader, SSE) | Done (2026-04-19) | `2026-04-17-phase-5-llm-runtime.md` |
| 6 | 3 | Background task scheduling | Done (2026-04-20) | `2026-04-17-phase-6-background-task-scheduling.md` |
| 7 | 3 | CLI surface (`admin`, `wizard reset`, `secrets rotate-key`, `maintenance`) | Done (2026-04-20) | `2026-04-17-phase-7-cli-surface.md` |
| 8 | 4 | Frontend shell (routing, auth context, layout, design tokens) | Draft | `2026-04-17-phase-8-frontend-shell.md` |
| 9 | 4 | Login + Account Management UI | Done (2026-04-21) | `2026-04-17-phase-9-login-and-account-ui.md` |
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

## Standing rules (apply to every plan)

These are cross-plan conventions. Every plan implicitly requires them; do not merge a phase branch that violates them.

### Merge gate (non-negotiable, applies to every PR into `main`)

Before merging any phase PR:

1. `uv run ruff check .` passes (zero errors — run `--fix` first and inspect the diff).
2. `uv run ruff format --check .` passes.
3. `uv run pytest` passes on the **full aggregate suite**, not just the new tests. Running tests only in the directory you added is not sufficient — import/fixture collisions only surface when everything runs together.
4. The `CI` workflow on GitHub Actions is green for the PR head commit.
5. Status table in `planning/implementation-plans/README.md` updated to mark the plan Complete with merge date.

Recommended hardening: enable GitHub branch protection on `main` requiring the `CI / Python — lint + test` and `CI / Frontend — test + build` checks before merge. Historical incident: phases 5 and 6 both merged to `main` with failing CI, breaking the aggregate test collection (see "Test conventions" below).

### Test conventions

- **Unique names for shared test helpers.** Any test-only helper module that is not named `conftest.py` must have a name unique across the whole test tree — prefix with the package being tested (`_scheduler_fakes.py`, `_runtime_fakes.py`), never a generic `_fakes.py`. With `--import-mode=importlib` (our pytest config) two files named `_fakes.py` in different directories collide at collection time.
- **Every test directory gets an `__init__.py`.** Enforces package semantics and keeps fixture discovery predictable.
- **Shared helpers go through `conftest.py` where possible.** Only reach for a free-standing `_xxx_helpers.py` when the helper is a class/dataclass that needs to be imported by name across multiple test modules.
- **One-line sanity command before opening a PR:** `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`. If that fails locally, CI will fail too.

### Cross-plan contracts (locked after the 2026-04-20 audit)

These eight contracts were drifting across plan files before Phase 7 began. They are now normalized; do not reintroduce the old shapes in new plans or edits.

1. **HTTP prefixes.** Backend FastAPI routers use **bare prefixes** (`/auth`, `/notifications`, `/chat/sessions`, `/repo`, `/reports`, `/departments/<slug>/...`). The Vite dev proxy strips `/api` (`rewrite: (p) => p.replace(/^\/api/, "")` — see Plan 0). Frontend code hits `/api/...`; backend TestClient tests hit bare paths.
2. **`reports` table.** Plan 1A's schema is the single source of truth: `report_type`, `title`, `content_markdown`, `content_structured` (JSON — holds the canonical `ReportSchema`), `model_ref`, timestamps from `TimestampMixin`. No `mode`/`schema_json`/`generated_at`/`status` columns — Plan 13+ map onto the existing columns.
3. **`repo_items` table.** Not in Plan 1A. Created by Plan 12 Task 0 before Task 2 uses it.
4. **`wizard_state` shape.** Reshaped by Plan 10 Task 1: `current_step: String` (named step id), `completed_steps: JSON[]`, `active_session_token: String(64) nullable`. Plan 1A's legacy `Integer` `current_step` is migrated in-place.
5. **Runtime event imports.** Always `from openlia.llm.runtime.events import ...` — never `openlia.runtime.events`.
6. **Runtime event fields.** `ReportStart(report_id, department, mode, section_titles)` and `ReportComplete(report_id, schema)` are frozen as shipped in Plan 5. Title lives inside `schema["title"]`; no top-level `title` attribute.
7. **`ReportRequest`.** Plan 5 owns the shape: `mode`, `user_input`, `enabled_sections`, `custom_sections`, `length` (allowed set `("brief", "standard", "long")`). Departments that use `report_length` (`concise`/`normal`/`elaborative`) in their own config tables must map at call-site; do not retroactively extend Plan 5.
8. **`user_prefs` table.** Not in Plan 1A. Created by Plan 11 Task 1. Plan 11's dependency list documents this explicitly.

### Current backend contract (authoritative import paths + shapes)

Locked after the 2026-04-20 Phase 7+ plan audit. Plans 7–15 drifted against the actual Phase 0–6 implementation; the shapes below are what the shipped code exposes. New or revised plans must use these names verbatim.

**Model imports.**

- `from openlia_server.db.models.auth import User, Session, SignupInvite, PasswordResetRequest, LoginAttempt`
- `from openlia_server.db.models.config import LLMProvider, LLMModel, DataProvider, ConfigStore, WizardState`
- `from openlia_server.db.models.content import ChatSession, ChatMessage, Report, RepoItem` (RepoItem created by Plan 12 Task 0)
- `from openlia_server.db.models.infrastructure import JobRun, Notification`

**Auth dependencies.** Router-factory pattern only — do not import a bare `get_current_user`:

```python
from openlia_server.middleware.auth import build_require_auth, build_require_admin

def build_foo_router(*, db_session_factory, mode: str) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/foo")
    @router.get("/bar")
    def bar(user: User = Depends(require_auth)): ...
    return router
```

Mount in `app.py` with `app.include_router(build_foo_router(db_session_factory=factory, mode=mode))`.

**Password hashing.** `from openlia_server.services.auth.passwords import hash_password, verify_password` (not `openlia_server.security.passwords`).

**DB session access.** No `get_db_session` / `get_db` helper ships today. Use `SessionLocal()` as a context manager, or add a `session_dependency()` inside the router factory that yields from `db_session_factory()` and closes on exit. Plans that need it must include the helper in their own Task 0.

**Auth HTTP response shape (flat).** Backend returns:

```json
{
  "user_id": "<uuid>",
  "email": "...",
  "display_name": "...",
  "is_admin": true,
  "must_change_password": false
}
```

Frontend maps at the boundary: `role = is_admin ? "admin" : "user"`, `id = user_id`. There is no nested `{user: ...}` envelope and no `role` column in the DB.

**IDs are UUID strings.** `User.id`, `SignupInvite.id`, `ChatSession.id`, `Report.id`, `RepoItem.id`, and all FKs to them are `String(36)`. Plans must type DTOs and path parameters as `str`; generate with `uuid.uuid4().hex`-style strings.

**ChatSession fields.** `is_pinned: bool`, `is_archived: bool`, `context: dict | None`. There is no `pinned` or `archived_at` column; add a migration deliberately if archive timestamps are needed.

**`config_store["wizard.completed"]`.** Bootstrap seeds a Python `bool`. Readers must tolerate both `bool` and `"true"`/`"false"` strings — never call `.lower()` on the raw value without a type guard.

**LLM admin route prefix.** `/settings/admin/llm/*` (not `/settings/models/*`). Frontend clients in Plan 11 hit `/api/settings/admin/llm/...`.

**LLM provider service surface.** `packages/server/src/openlia_server/services/llm_providers.py` exposes `create_provider`, `get_provider`, `list_providers`, `update_provider`, `delete_provider`, `create_model`, `list_models_for_provider`, `set_user_preference`. There is no `test_provider`, `clear_all_providers`, `add_model`, or `list_data_provider_rows` — Plan 10's wizard flow must use the shipped CRUD or add helpers in its own Task 0.

**Runtime imports.** `from openlia.llm.runtime.messages import ReportRequest` and `from openlia.llm.runtime.events import to_wire` (SSE serialization). `serialize_sse` does not exist.

**Frontend `/api` proxy.** Already shipped in `frontend/vite.config.ts`: target `http://localhost:8000`, `changeOrigin: true`, `rewrite: (p) => p.replace(/^\/api/, "")`. Backend routes remain unprefixed; tests using `TestClient` hit bare paths.

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

- **Filenames:** `YYYY-MM-DD-phase-N-<slug>.md` where `N` is the **plan number** (column `#` in the status table above), not the phase bucket. Historic artifact: the slug reuses the word "phase" for plan numbers, so `phase-3-data-provider-adapter-system.md` is Plan 3, which belongs to **Phase 2** per the status table. When in doubt, the status-table `#` and `Phase` columns are authoritative; the filename is a historical alias.
- **Status values:** `Not started` | `Draft` (written but not reviewed) | `Ready` (reviewed and ready to execute) | `In progress` | `Done`. ("Complete" is a legacy alias for `Done` — use `Done` for new edits.)
- **Branch names:** one branch per plan, `feat/phase-N-<slug>`.
- **Commits:** one commit per task (or per atomic sub-step) within the plan.
