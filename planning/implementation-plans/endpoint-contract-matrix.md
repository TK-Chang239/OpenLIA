# Endpoint Contract Matrix

Date: 2026-04-21
Source: REM-P0-005 (see `planning/audits/2026-04-21-remediation-checklist.md`).

This matrix is the single source of truth for every HTTP endpoint in OpenLIA. Every existing route and every planned Plan 9-23 route is listed once with its backend path, backend function, frontend client (if any), auth dependency, request DTO, response DTO, owning plan, and test file. New routes cannot merge without updating this matrix and adding tests.

## Conventions

- **Backend paths** are unprefixed (FastAPI routers mount with bare prefixes: `/auth`, `/notifications`, `/jobs`, `/settings/...`, `/admin`).
- **Frontend paths** are the `/api/<rest>` form. The Vite dev proxy strips `/api` — see `frontend/vite.config.ts` and the proxy rewrite rule documented in `README.md`.
- **TestClient** hits bare paths (e.g. `client.post("/auth/login")`), matching backend mounts.
- **Auth column values:**
  - `public` — no auth dependency.
  - `require_auth` — `build_require_auth(db_session_factory, mode)`; personal-mode resolves to the bootstrapped `local` user, company-mode requires a valid `openlia_session` cookie.
  - `require_admin` — `build_require_admin(...)`; same as `require_auth` plus `user.is_admin`.
  - `cookie-optional` — endpoint inspects the session cookie itself (e.g. logout).
  - `wizard-session` — planned; setup routes gate on wizard session token.
- **Mode column values:** `both` (personal + company), `company` (mounted only when `OPENLIA_MODE=company`), `personal`.

## Shipped routes (Phases 0-9)

### Auth — `build_auth_router(db_session_factory)` · mounted only in company mode

| Backend path | Method | Frontend path | Client fn | Auth | Request DTO | Response DTO | Mode | Plan | Test file |
|---|---|---|---|---|---|---|---|---|---|
| `/auth/register` | POST | `/api/auth/register` | `register` (`frontend/src/api/auth.ts`) | public + rate-limited | `RegisterIn {email, password, display_name?, invite_token}` | `{user_id, email, display_name}` + Set-Cookie | company | 2, 9 | `packages/server/tests/test_routes/test_auth_routes.py` |
| `/auth/login` | POST | `/api/auth/login` | `login` | public + rate-limited | `LoginIn {email, password, persistent}` | `{user_id, email, display_name, is_admin, must_change_password}` + Set-Cookie | company | 2, 9 | same |
| `/auth/logout` | POST (204) | `/api/auth/logout` | `logout` | cookie-optional | — | 204 No Content | company | 2, 9 | same |
| `/auth/logout-all` | POST (204) | `/api/auth/logout-all` | `logoutAll` | `require_auth` | — | 204 | company | 2, 9 | same |
| `/auth/session` | GET | `/api/auth/session` | `getSession` | `require_auth` | — | `{user_id, email, display_name, is_admin}` | company | 2, 9 | same |
| `/auth/signup-policy` | GET | `/api/auth/signup-policy` | `getSignupPolicy` | public | — | `{mode, invite_required}` | company | 2, 9 | same |
| `/auth/password-reset/request` | POST | `/api/auth/password-reset/request` | `requestPasswordReset` | public + rate-limited | `{email}` | `{status: "ok"}` | company | 2, 9 | same |
| `/auth/password-reset/consume` | POST | `/api/auth/password-reset/consume` | `consumePasswordReset` | public | `{token, new_password}` | `{status: "ok"}` | company | 2, 9 | same |
| `/auth/change-password` | POST | `/api/auth/change-password` | `changePassword` | `require_auth` | `{current_password, new_password}` | `{status: "ok"}` | company | 2, 9 | same |

### Admin — `build_admin_router(db_session_factory)` · mounted only in company mode

| Backend path | Method | Frontend path | Client fn | Auth | Request DTO | Response DTO | Mode | Plan | Test file |
|---|---|---|---|---|---|---|---|---|---|
| `/admin/invites` | GET | `/api/admin/invites` | *(Plan 11)* | `require_admin` | — | `{invites: [...]}` | company | 7, 11 | `test_admin_routes.py` |
| `/admin/invites` | POST (201) | `/api/admin/invites` | *(Plan 11)* | `require_admin` | `{email?, role, expires_at?}` | created invite | company | 7, 11 | same |
| `/admin/invites/{invite_id}/revoke` | POST (204) | `/api/admin/invites/{id}/revoke` | *(Plan 11)* | `require_admin` | — | 204 | company | 7, 11 | same |
| `/admin/users` | GET | `/api/admin/users` | *(Plan 11)* | `require_admin` | — | `{users: [...]}` | company | 7, 11 | same |
| `/admin/users/{user_id}/disable` | POST (204) | `/api/admin/users/{id}/disable` | *(Plan 11)* | `require_admin` | — | 204 | company | 7, 11 | same |
| `/admin/users/{user_id}/enable` | POST (204) | `/api/admin/users/{id}/enable` | *(Plan 11)* | `require_admin` | — | 204 | company | 7, 11 | same |
| `/admin/users/{user_id}/reset-password` | POST (204) | `/api/admin/users/{id}/reset-password` | *(Plan 11)* | `require_admin` | — | 204 | company | 7, 11 | same |
| `/admin/password-reset-requests` | GET | `/api/admin/password-reset-requests` | *(Plan 11)* | `require_admin` | — | list | company | 7, 11 | same |
| `/admin/password-reset-requests/{id}/approve` | POST | `/api/admin/password-reset-requests/{id}/approve` | *(Plan 11)* | `require_admin` | — | approval payload | company | 7, 11 | same |
| `/admin/password-reset-requests/{id}/reject` | POST (204) | `/api/admin/password-reset-requests/{id}/reject` | *(Plan 11)* | `require_admin` | — | 204 | company | 7, 11 | same |

### Jobs — `build_jobs_router(db_session_factory, mode)`

| Backend path | Method | Frontend path | Client fn | Auth | Request DTO | Response DTO | Mode | Plan | Test file |
|---|---|---|---|---|---|---|---|---|---|
| `/jobs/history` | GET | `/api/jobs/history` | *(Plan 11)* | `require_auth` | query: `department?`, `status?`, `limit` | `JobsHistoryOut` | both | 6, 11 | `packages/server/tests/test_scheduler/test_routes_jobs.py` |
| `/jobs/{run_id}/retry` | POST (202) | `/api/jobs/{id}/retry` | *(Plan 11)* | `require_auth` | — | `RetryAck` (503 if scheduler disabled) | both | 6, 11 | same |

### Notifications — `build_notifications_router(db_session_factory, mode)`

| Backend path | Method | Frontend path | Client fn | Auth | Request DTO | Response DTO | Mode | Plan | Test file |
|---|---|---|---|---|---|---|---|---|---|
| `/notifications/unread` | GET | `/api/notifications/unread` | `getUnread` (`frontend/src/api/notifications.ts`) | `require_auth` | — | `UnreadOut {counts_by_department}` | both | 6, 8 | `packages/server/tests/test_scheduler/test_routes_notifications.py` |
| `/notifications/read` | POST | `/api/notifications/read` | `markRead` | `require_auth` | `{department}` | `MarkReadOut` | both | 6, 8 | same |

### Settings — data providers — `build_data_providers_router(db_session_factory)`

| Backend path | Method | Frontend path | Client fn | Auth | Request DTO | Response DTO | Mode | Plan | Test file |
|---|---|---|---|---|---|---|---|---|---|
| `/settings/data-providers` | GET | `/api/settings/data-providers` | *(Plan 11)* | `require_admin` | — | `{providers: [...]}` | both | 3, 11 | `test_data_providers_routes.py` |
| `/settings/data-providers` | POST (201) | same | *(Plan 11)* | `require_admin` | `_CreateDataProviderIn` | `_DataProviderOut` | both | 3, 11 | same |
| `/settings/data-providers/auto-map` | POST | `/api/settings/data-providers/auto-map` | *(Plan 11)* | `require_admin` | — | `{mappings: [...]}` | both | 3, 11 | same |
| `/settings/data-providers/mappings` | GET | same | *(Plan 11)* | `require_admin` | — | mapping list | both | 3, 11 | same |
| `/settings/data-providers/mappings/{requirement_type}` | PUT | same | *(Plan 11)* | `require_admin` | `{provider_id}` | mapping | both | 3, 11 | same |
| `/settings/data-providers/mappings/{requirement_type}` | DELETE (204) | same | *(Plan 11)* | `require_admin` | — | 204 | both | 3, 11 | same |
| `/settings/data-providers/{provider_id}` | PATCH | same | *(Plan 11)* | `require_admin` | `_UpdateDataProviderIn` | `_DataProviderOut` | both | 3, 11 | same |
| `/settings/data-providers/{provider_id}` | DELETE (204) | same | *(Plan 11)* | `require_admin` | — | 204 | both | 3, 11 | same |
| `/settings/data-providers/{provider_id}/test-connection` | POST | same | *(Plan 11)* | `require_admin` | — | `{ok, detail}` | both | 3, 11 | `test_data_providers_integration.py` |

### Settings — LLM admin — `build_llm_providers_admin_router(db_session_factory, mode)`

Prefix: `/settings/admin/llm` — NOT `/settings/models/*`.

| Backend path | Method | Frontend path | Client fn | Auth | Request DTO | Response DTO | Mode | Plan | Test file |
|---|---|---|---|---|---|---|---|---|---|
| `/settings/admin/llm/providers` | GET | `/api/settings/admin/llm/providers` | *(Plan 11)* | `require_admin` | — | `list[_ProviderOut]` | both | 4, 11 | `test_llm_admin_routes.py` |
| `/settings/admin/llm/providers/test` | POST | same | *(Plan 11)* | `require_admin` | provider test body | `_TestOut` | both | 4, 11 | same |
| `/settings/admin/llm/providers` | POST (201) | same | *(Plan 11)* | `require_admin` | `_ProviderIn` | `_ProviderOut` | both | 4, 11 | same |
| `/settings/admin/llm/providers/{provider_id}` | PUT | same | *(Plan 11)* | `require_admin` | `_ProviderIn` | `_ProviderOut` | both | 4, 11 | same |
| `/settings/admin/llm/providers/{provider_id}` | DELETE (204) | same | *(Plan 11)* | `require_admin` | — | 204 | both | 4, 11 | same |
| `/settings/admin/llm/providers/{provider_id}/models` | GET | same | *(Plan 11)* | `require_admin` | — | `list[_ModelOut]` | both | 4, 11 | same |
| `/settings/admin/llm/providers/{provider_id}/remote-models` | GET | same | *(Plan 11)* | `require_admin` | — | `list[dict]` | both | 4, 11 | same |
| `/settings/admin/llm/models` | POST (201) | same | *(Plan 11)* | `require_admin` | `_ModelIn` | `_ModelOut` | both | 4, 11 | same |
| `/settings/admin/llm/models/{model_id}` | PUT | same | *(Plan 11)* | `require_admin` | `_ModelIn` | `_ModelOut` | both | 4, 11 | same |
| `/settings/admin/llm/models/{model_id}` | DELETE (204) | same | *(Plan 11)* | `require_admin` | — | 204 | both | 4, 11 | same |
| `/settings/admin/llm/department/{department_id}` | POST | same | *(Plan 11)* | `require_admin` | `{tier, model_id}` | mapping | both | 4, 11 | same |
| `/settings/admin/llm/capability_override/{provider_kind}/{model:path}` | POST | same | *(Plan 11)* | `require_admin` | capability body | updated caps | both | 4, 11 | same |

### Infrastructure

| Backend path | Method | Frontend path | Client fn | Auth | Request DTO | Response DTO | Mode | Plan | Test file |
|---|---|---|---|---|---|---|---|---|---|
| `/health` | GET | `/api/health` | — | public | — | `{status: "ok"}` | both | 0 | `packages/server/tests/test_app.py` |

## Planned routes (Plans 10-23)

Each planned route MUST be added to this matrix before its plan executes. The entries below are placeholders derived from plan content; refine them during REM-P0-004 rewrites.

### Plan 10 — Setup wizard (`/setup/*`, 15 routes)

- `/setup/status` (GET, public) — returns `{mode, current_step, completed, env_overrides}`. Frontend: `getSetupStatus` (`frontend/src/api/setup.ts`, to be created).
- `/setup/mode` (POST, wizard-session) — choose personal vs company.
- `/setup/models/tier/{tier}` (POST, wizard-session) — set Thinking/Everyday/Quick model.
- `/setup/data-providers/{category}` (POST, wizard-session) — set category provider.
- `/setup/web-search` (POST, wizard-session) — configure Brave/Tavily/Serper/You.com fallback.
- `/setup/review` (GET/POST, wizard-session) — AI readiness check per department.
- `/setup/complete` (POST, wizard-session) — flips `config_store["wizard.completed"] = true`.
- Remaining routes (provider CRUD during wizard, per-category default, invite creation, admin bootstrap): enumerate in the Plan 10 rewrite.

All `/setup/*` writes must return `410 Gone` once `wizard.completed = true`, except `/setup/status`.

### Plan 11 — Settings page frontend clients

- No new backend endpoints beyond those listed above; Plan 11 wires the existing admin/settings routers into frontend pages. Add a `frontend/src/api/settings.ts` module and reference it in this matrix during the plan rewrite.

### Plan 12 — Shared chat + repo

- `/chat/sessions` (GET/POST, `require_auth`) — list/create chat sessions.
- `/chat/sessions/{id}` (GET/PATCH/DELETE, `require_auth` + owner scope).
- `/chat/sessions/{id}/messages` (GET, `require_auth` + owner scope).
- `/chat/stream` (POST, `require_auth`, SSE) — multi-round ChatRunner driver. Emits `chat.*` events per Plan 5 event taxonomy.
- `/repo/items` (GET, `require_auth` + owner scope) — list saved reports/files.
- `/repo/items` (POST, `require_auth`) — save a generated report (persists `repo_items`).
- `/repo/items/{id}` (GET/DELETE, `require_auth` + owner scope).

### Plan 13 — Secretary + report pipeline

- `/departments/secretary/chat` (POST, `require_auth`, SSE) — Secretary ChatRunner.
- `/reports` (POST, `require_auth`) — kick off a ReportRunner (generic handler for chat-only departments).
- `/reports/{id}` (GET, `require_auth` + owner scope).
- `/reports/{id}/stream` (GET, `require_auth`, SSE resume).

### Plan 14 — Equity Research

- `/departments/equity-research/chat` (POST, SSE) — mode: initiation | update | sector.
- `/departments/equity-research/configs` (GET/POST/PATCH/DELETE, `require_auth` + owner scope) — per-user config rows.

### Plan 15 — Earnings Update

- `/departments/earnings-update/chat` (POST, SSE).
- `/departments/earnings-update/watchlist` (GET/POST/DELETE, `require_auth` + owner scope).
- `/departments/earnings-update/schedules` (GET/POST/PATCH/DELETE, `require_auth` + owner scope) — CRUD flows call scheduler `add_schedule/modify_schedule/remove_schedule` APIs in the same transaction.

### Plan 16 — Morning Briefing (shipped)

Router: `build_morning_briefing_router` mounted at `/departments/morning-briefing`.

- `/departments/morning-briefing/config` (GET, `require_auth`) — returns `MbConfig` (report_length, enabled_section_ids, section_topics, custom_sections, reference_portfolio).
- `/departments/morning-briefing/config` (PUT, `require_auth`) — upserts `MbConfig`.
- `/departments/morning-briefing/schedule` (GET, `require_auth`) — returns `{schedule: MbSchedule | null}`.
- `/departments/morning-briefing/schedule` (PUT, `require_auth`) — upserts one MB schedule (time, timezone, days_of_week, label).
- `/departments/morning-briefing/schedule` (DELETE, `require_auth`) — 204 on delete.
- `/departments/morning-briefing/report` (POST, `require_auth`, SSE) — on-demand briefing; emits `report.*` events terminating in `report.saved` or `report.error`.
- `/departments/morning-briefing/chat/session` (POST, `require_auth`) — resolve-or-create the user's single MB `ChatSession`.
- Recent reports listing reuses `/reports?department=morning_briefing` from Plan 13.
- Test file: `packages/server/tests/test_routes_morning_briefing.py`.
- Frontend client: `frontend/src/api/morning-briefing.ts`.

### Plan 18 — Panic Thermometer (shipped)

Router: `build_panic_thermometer_router` mounted at `/departments/panic-thermometer`.
See `packages/server/src/openlia_server/routes/departments/panic_thermometer.py` for the full CRUD surface (dashboard, panels, rules, formulas, run).

### Plan 19 — Macro Research (shipped)

Router: `build_macro_research_router` mounted at `/departments/macro_research`. Schedule routes mounted by `build_mr_schedule_router` at `/departments/macro_research/schedule`.

- `GET /departments/macro_research/dashboards` (`require_auth`) — enumerates the five Dalio dashboards. Response: `{ "dashboards": [{ "slug": str, "display_name": str }] }`.
- `GET /departments/macro_research/dashboards/{slug}?smart_mode=<bool>` (`require_auth`) — snapshot for one dashboard (`debt_cycle`, `four_seasons`, `all_weather`, `world_order`, `five_forces`). Optional `smart_mode` query flag is forwarded to `mr_runner.run`. Response: `DashboardResult` (slug, display_name, severity, tiers, headline, generated_at, smart_mode_active).
- `GET /departments/macro_research/dashboards/{slug}/config` (`require_auth`) — returns `{ "view_config": {...}, "threshold_overrides": {...} }`.
- `PUT /departments/macro_research/dashboards/{slug}/config` (`require_auth`) — body `{ "view_config"?: {...}, "threshold_overrides"?: {...} }`; returns the merged row.
- `PUT /departments/macro_research/dashboards/{slug}/threshold-overrides` (`require_auth`, NEW-19-08) — body `{ "threshold_overrides": {...} }`; returns the merged row. Use this when you only need to mutate threshold overrides; the combined `/config` endpoint stays for view_config writes.
- `POST /departments/macro_research/dashboards/{slug}/assessment/run` (`require_auth`, 202) — body `{ "force"?: bool }`. Inserts a `JobRun` row keyed to `JobType.MR_ASSESSMENT` + `user_id` + `schedule_id=slug`, then dispatches via `app.state.scheduler.run_now`. Returns `{ "job_run_id": str, "status": "queued" | "cancelled" }` (cancelled when scheduler is disabled).
- `GET /departments/macro_research/schedule` (`require_auth`) — returns `{ "cron_expression": str | null, "last_assessment_at": str | null }`.
- `PUT /departments/macro_research/schedule` (`require_auth`) — body `{ "cron_expression": str }`; 400 on invalid crontab. Persists on the canonical `world_order` `mr_dashboard_state` row (see NEW-19-12 implementation note in `MacroResearchPageSpec.md`).
- `DELETE /departments/macro_research/schedule` (`require_auth`, 204).
- Test files: `packages/server/tests/test_macro_research/test_routes_macro_research.py`, `packages/server/tests/test_macro_research/test_routes_mr_schedules.py`.
- Frontend client: `frontend/src/api/macro_research.ts`.

### Plan 20 — Retail Sentiment (shipped)

Router: `build_retail_sentiment_router` mounted at `/departments/retail-sentiment`.

- `/departments/retail-sentiment/dashboard` (GET, `require_auth`) — current tabbed metric snapshot.
- `/departments/retail-sentiment/dashboard/history` (GET, `require_auth`).
- `/departments/retail-sentiment/config` (GET/PUT, `require_auth`).
- `/departments/retail-sentiment/run` (POST, `require_auth`) — trigger a refresh.
- `/departments/retail-sentiment/stocks/{ticker}/sentiment` (GET, `require_auth`).
- `/departments/retail-sentiment/spikes` (GET, `require_auth`).
- Test file: `packages/server/tests/test_routes_retail_sentiment.py`.
- NLP classification + `rs_classification_log` table documented in Phase 20 spec are deferred; endpoint shape stable.

### Plan 21 — Portfolio (shipped)

Router: `build_portfolio_router` mounted at `/portfolio`.

- `/portfolio/holdings` (GET/POST/PATCH/DELETE, `require_auth` + owner scope).
- `/portfolio/analytics` (GET, `require_auth`).
- `/portfolio/refresh-prices` (POST, `require_auth`).
- `/portfolio/import-csv` (POST, `require_auth`) / `/portfolio/export-csv` (GET, `require_auth`).
- `/portfolio/search` (GET, `require_auth`).
- Test file: `packages/server/tests/test_routes_portfolio.py`.

### Plan 22 — Repository (shipped)

Router: `build_repo_router` mounted at `/repo`.

- `/repo/items` (GET, `require_auth` + owner scope) — list saved reports/files; accepts filter query params.
- `/repo/items` (POST, `require_auth`) — save a generated report to the repo (idempotent via source_report_id).
- `/repo/items` (DELETE, `require_auth`) — bulk unsave.
- `/repo/facets` (GET, `require_auth`) — returns facet counts used by the Repo filter bar.
- Test file: `packages/server/tests/test_routes_repo.py`. Additional E2E coverage: `test_e2e_smoke_matrix.py::test_journey_repo_save_open_unsave`.

### Plan 23 — Packaging + production static serving

- `GET /` and SPA fallback routes — static mount of `frontend/dist`, declared in `app.py` only for production mode. API routes resolve first.

## Merge gate

- Every new or renamed route must land in this matrix in the same PR as the code.
- Every route row must point at at least one test file; if the test does not exist yet the row's `Test file` column is `TODO-<plan>-<task>` until the test lands.
- Changes to auth, request, or response DTOs update both the row and the frontend client entry.
- REM-P0-005 stays `[~]` until every shipped route has a populated row with a real test file, and every Plan 10-23 row exists as a placeholder.
