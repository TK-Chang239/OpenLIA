# Route Authorization Matrix

Regenerated: 2026-08-16 (Stage 4.4 of `docs/audit-2026-08-16.md`).
Supersedes the 2026-04-21 version, which stopped tracking after Plan 23 and
still referenced deleted surfaces.

This matrix is the authoritative rule set for who can call each HTTP router.
It is generated from the live FastAPI surface (`create_app()` in
`packages/server/src/openlia_server/app.py`) — one row per mounted router,
with its path prefix, methods, router-level auth level, owner-scoping, and
notes. Companion document: `endpoint-contract-matrix.md` (per-endpoint DTOs
and clients). This file is scoped to authorization semantics.

## How to keep this current

- Every new router (`build_*_router` + `include_router`) must land here in the
  same PR that adds it, with an auth-level row.
- `packages/server/tests/test_route_matrix_coverage.py` enumerates the mounted
  routes and asserts each router prefix appears in this file (a substring
  check), so a new top-level router that is not documented fails CI.
- To regenerate the endpoint inventory, run `create_app()` and iterate
  `app.routes` (see the test for the pattern).

## Access levels

Auth is applied through `openlia_server.middleware.auth` builders. A router's
level is the builder it constructs for its handlers (router-level
`dependencies=[...]` or a per-handler default such as `user = require_auth`).

| Level | Meaning | Builder |
|---|---|---|
| `public` | No session required. | none |
| `wizard-session` | Pre-auth; gated by the wizard session token on `WizardState.active_session_token`, plus loopback + `wizard.completed = false`. | `require_wizard_session` / `require_wizard_active` / `require_loopback_during_wizard` (setup router local) |
| `authed` | Authenticated user; does NOT force the company-mode password-reset gate. Personal mode resolves to the bootstrapped `local` user. Used only by the auth router (its own unblock endpoints must stay reachable). | `build_require_auth(db_session_factory, mode)` |
| `active-user` | Authenticated AND (company mode) `must_change_password = false` AND account enabled. The default for user-facing routers. | `build_require_active_user(db_session_factory, mode)` |
| `admin` | `active-user` AND `user.is_admin = true`. | `build_require_active_admin(db_session_factory, mode)` |
| `cookie-optional` | Handler inspects the cookie itself; no auth error if absent (e.g. logout). | handler-local |

Note: `build_require_admin` (the old admin builder without the active-user
gate) is retired; every admin router now uses `build_require_active_admin`.

## Must-change-password behavior (company mode)

A company-mode user with `must_change_password = true` is blocked from every
`active-user` and `admin` route. The unblock path lives on the auth router,
which is deliberately `authed` (not `active-user`) so it stays reachable:

- `POST /auth/change-password` (primary unblock)
- `POST /auth/logout`, `POST /auth/logout-all`
- `GET /auth/session`
- `GET /health`, `GET /healthz`

Personal-mode users never have `must_change_password = true`.

## Owner scoping

Admin never overrides owner scoping for user content (chat, reports, repo,
portfolio, schedules, dashboards, graph). Admin scope is strictly
administrative (invites, users, provider/LLM config, connectors, cache, the
global guardrail audit log, and system-wide graph extraction).

| Resource | Owner FK | Enforced in |
|---|---|---|
| `ChatSession` / `ChatMessage` / `ChatAttachment` | `ChatSession.user_id` | `routes/chat_sessions.py`, `chat_stream.py`, `files.py` |
| `Report` / `ReportVersion` (v1 engine) | `Report.user_id` | `routes/reports.py`, `reports_stream.py`, `reports_revise.py` |
| `ReportV3Run` (+ revisions, instructions, templates) | `<table>.user_id` | `routes/departments/equity_research_v3.py` |
| `EuV2Run` / EU v2 settings / watchlist / instructions / templates | `<table>.user_id` | `routes/departments/earnings_update_v2.py` |
| EU v1 config / schedules / watchlist | `<table>.user_id` | `routes/departments/earnings_update.py` |
| MB v2 runs / schedules / instructions / templates | `<table>.user_id` | `routes/departments/morning_briefing.py` |
| `MrDashboardState` / `MrDashboardCache` | `<table>.user_id` | `routes/departments/macro_research.py`, `mr_schedules.py` |
| `RsDashboardCache` / RS config / schedule | `<table>.user_id` | `routes/departments/retail_sentiment.py` |
| PT per-user config / saved presets | `<table>.user_id` (shipped presets are global read) | `routes/departments/panic_thermometer.py` |
| `RepoItem` (+ v2/v3/eu/mb saved-run rows) | `RepoItem.user_id` etc. | `routes/repo.py` |
| `PortfolioHolding` / groups / prefs / series | `<table>.user_id` | `routes/portfolio.py` |
| `JobRun` | `JobRun.user_id` | `routes/jobs.py` |
| `UserNotification` / presence | `UserNotification.user_id` | `routes/notifications.py`, `notifications_stream.py` |
| `UserLLMPreference` (per-department model pref) | `UserLLMPreference.user_id` | `routes/department_model_pref.py` |
| `ReportTemplate` | `ReportTemplate.user_id` | `routes/report_templates.py` |
| Graph constructs / proposals | `GraphUserConstruct.user_id` / `GraphExtractionProposal.user_id` | `routes/graph.py` |
| User skills (company mode) | `DatabaseSkillStore` per `user_id` | `routes/skills.py` |
| User prefs (disclaimer accept, settings, timezone, market basket) | `UserPrefs.user_id` | `routes/settings_general.py`, `settings_email.py`, `disclaimer.py` |
| `PasswordResetRequest` | requesting email + admin reviewer | `routes/auth.py`, `routes/admin.py` |

## Mode mounting

Only the auth and admin routers are company-only. Every other router is mounted
in both modes; admin-level routers still resolve transparently in personal mode
because the bootstrapped `local` user has `is_admin = true`.

| Router group | Personal | Company |
|---|---|---|
| `build_auth_router` (`/auth`) | not mounted | mounted |
| `build_admin_router` (`/admin`) | not mounted | mounted |
| all other routers below | mounted | mounted |

## Setup wizard gating (`/setup/*`)

- `GET /setup/status` — always public.
- `GET /setup/state` — `wizard-session` (token only, no cookie).
- All `/setup/*` writes (`mode`, `identity`, `providers`, `models`,
  `models/test`, `access_control`, `admin`, `takeover`, `finish`) require
  `require_loopback_during_wizard` + `require_wizard_active` (+ the wizard
  session token). Personal mode additionally rejects non-loopback clients.
- Once `wizard.completed = true`, writes return `410 Gone`; `/setup/status`
  keeps returning `{completed: true}`.
- Stage 0.2 note: `POST /setup/takeover` gains `require_wizard_active` and the
  loopback gate reads the true transport peer (`_CaptureRealClientMiddleware`),
  not a proxy-forwarded `X-Forwarded-For`.

## Router authorization matrix

Prefixes are the FastAPI mount prefixes (the runtime `/api` prefix is stripped
by `_StripApiPrefixMiddleware`). Methods listed are the HTTP verbs actually
mounted (HEAD/OPTIONS omitted).

| Router (`build_*`) | Prefix | Methods | Auth level | Owner scope | Notes |
|---|---|---|---|---|---|
| setup | `/setup` | GET, POST | public (`/status`) · wizard-session (rest) | global (pre-auth) | Loopback + wizard-active gate on all writes. Company-mode reachable until completion. |
| auth | `/auth` | GET, POST, DELETE | public · authed · cookie-optional | per-user sessions | `register`/`login`/`signup-policy`/`password-reset/*` public; `logout` cookie-optional; `session`/`logout-all`/`change-password`/`sessions` authed. Company only. Rate-limited (register/login/password-reset). |
| admin | `/admin` | GET, POST | admin | global (administrative) | invites, users (disable/enable/reset-password/**role**), password-reset-request review. Company only. `/admin/users/{id}/role` is the Stage-3 in-app promote/demote route. |
| admin_graph | `/admin/graph` | POST | admin | global | `POST /admin/graph/extract-now` triggers system-wide graph extraction. |
| admin_skills | `/admin/skills` | GET | active-user + in-handler admin check | system skills (global) | Router builder is `active-user`; each handler calls `_admin_only(user)`, so effectively admin. `GET /admin/skills`, `/admin/skills/audit`. |
| guardrail_events | `/admin/guardrail-events` | GET, DELETE | admin | global audit log | Stage 0.3: switched from bare auth to `active-admin`. GET returns all users' rows (incl. `response_excerpt`); DELETE wipes the global log. |
| connectors | `/connectors` | GET, POST, PUT, DELETE | admin (router-level `dependencies`) | global by design (process-wide installed connectors) | CRUD + builtins + python-package/lib install + validate + sync-template-specs. |
| cache | `/cache` | GET, DELETE | admin (router-level `dependencies`) | global | `GET /cache/stats`, `DELETE /cache/documents`. |
| settings (llm admin) | `/settings/admin/llm` | GET, POST, PUT, DELETE | admin | global | Provider + model CRUD, `remote-models` discovery, `department/{id}` mapping, `capability_override/{kind}/{model:path}`. |
| settings_llm_slots | `/settings/admin/llm/slot-defaults` | GET, PUT, DELETE | admin | global | Slot-default model bindings. |
| settings_general | `/settings` | GET, PATCH, PUT | active-user | `UserPrefs.user_id` | `prefs`, `timezone`, `departments`, `enabled-models`, `preferences/market-basket`, `graph-extraction-time`. |
| settings_email | `/settings` | PATCH | active-user | `UserPrefs.user_id` | `PATCH /settings/email`. |
| jobs | `/jobs` | GET, POST | active-user | `JobRun.user_id` | `history`, `{run_id}/retry` (503 when scheduler disabled). |
| notifications | `/notifications` | GET, POST | active-user | `UserNotification.user_id` | `unread`, `read`. |
| notifications_stream | *(bare)* → `/notifications/stream`, `/notifications/presence-close` | GET, POST | active-user | `user.id` presence | SSE stream + presence-close beacon. |
| dept_health | `/dept-health` | GET, POST | public | global cache | `GET /dept-health` (cache read), `POST /dept-health/refresh` (recompute). No auth by design (drives sidebar enable/disable). |
| capabilities | *(bare)* → `/capabilities` | GET | public | global manifest | Engine capability manifest for the frontend. |
| markets | `/markets` | GET | active-user | global (shared index cache) | `GET /markets/indices`; `{available:false}` when no EODHD key. |
| portfolio | `/portfolio` | GET, POST, PATCH, DELETE | active-user | `PortfolioHolding.user_id` (+ groups/prefs/series) | holdings, analytics, refresh-prices, import/export-csv, search, groups (+reorder), prefs, value-series, ticker-series. |
| reports | `/reports` | GET, POST, DELETE | active-user | `Report.user_id` | v1 engine (MB legacy + EU v1): list, `generate`, `{id}`, `{id}/render`, `{id}/retry`, `{id}/export/{docx,pdf}` (+ `docx` legacy alias), delete. |
| reports_stream | *(bare)* → `/reports/{id}/stream` | GET | active-user | `Report.user_id` | SSE resume for v1 report runs. |
| reports_revise | *(bare)* → `/reports/{id}/revise` | POST | active-user | `Report.user_id` | v1 report revision kickoff. |
| repo | `/repo` | GET, POST, DELETE | active-user | `RepoItem.user_id` (+ v2/v3/eu/mb saved-run rows) | `items` (filtered/paginated), `facets`, and per-engine saved-run collections `v2-runs`/`v3-runs`/`eu-runs`/`mb-runs`. |
| report_templates | `/report-templates` | GET, POST, PUT, DELETE | active-user | `ReportTemplate.user_id` | CRUD + `ingest`/`parse`; `v23/*` sub-paths are template-FORMAT helpers (builtins/parse/validate), shared library — not a report engine. |
| department_model_pref | `/departments/{department}` | GET, PUT, DELETE | active-user | `UserLLMPreference.user_id` | `/departments/{department}/model-pref`. |
| files | *(bare)* → `/chat/attachments/{id}/download` | GET | active-user | `ChatSession.user_id` | Attachment download, owner-scoped. |
| chat_sessions | `/chat/sessions` | GET, POST, PATCH, PUT, DELETE | active-user | `ChatSession.user_id` | list/create/get/patch/delete, `by-department/{department}`, `{id}/messages` (GET+POST), `{id}/model`. |
| chat_stream | `/chat/sessions` | GET | active-user | `ChatSession.user_id` | `GET /chat/sessions/{id}/stream` (SSE). |
| graph | `/graph` | GET, POST, DELETE | active-user | `GraphUserConstruct.user_id` / proposals | constructs (list/delete), proposals (list/accept/dismiss). |
| skills | `/skills` | GET, POST, PATCH, DELETE | active-user | user scope (`DatabaseSkillStore` per user in company mode) | list, install, `{id}` patch/delete, `{id}/body`. Stage 3: PATCH of system skills and `folder_path` install must be admin-gated. |
| disclaimer | `/disclaimer` | GET, POST | active-user | `UserPrefs.user_id` | `disclaimer`, `status`, `accept`. |
| dev | `/dev` | GET | public (env-gated) | global | `info`/`events`/`events/stream`; every handler 404s unless `OPENLIA_DEV_MODE`. |
| secretary | `/departments/secretary` | GET, POST | active-user | chat session owner | `/chat` (GET welcome + POST SSE). |
| equity_research_v3 | `/departments/equity-research/v3` | GET, POST, DELETE | active-user | `ReportV3Run.user_id` | runs (start/get/cancel/delete/revise/revisions), revision events/cancel, instructions, templates, exports (`html`/`pdf`/`docx`), `events` (SSE). Sole equity engine. |
| earnings_update (v1) | `/departments/earnings-update` | GET, POST, PATCH, DELETE | active-user | `<table>.user_id` | Legacy v1 engine: config, report, reports, schedules, watchlist. Runs on the generic v1 `reports` pipeline. |
| earnings_update_v2 | `/departments/earnings-update/v2` | GET, POST, PUT, DELETE | active-user | `EuV2Run.user_id` | runs (start/get/cancel/delete), `events` (SSE), settings, instructions, templates, watchlist (+sync), schedule, data-sources, exports. |
| morning_briefing | `/departments/morning-briefing` | GET, POST, PATCH, DELETE | active-user | `<table>.user_id` | MB v2: runs (start/get/cancel/delete), `events` (SSE), schedules, instructions, templates, data-sources, exports. |
| macro_research | `/departments/macro_research` | GET, POST, PUT, DELETE | active-user | `MrDashboardState.user_id` | dashboards (list/get/refresh), schedule (GET/PUT/DELETE via `mr_schedules`). |
| mr_schedules | `/departments/macro_research/schedule` | GET, PUT, DELETE | active-user | `MrDashboardState.user_id` | Assessment schedule CRUD; validates ownership before scheduler calls. |
| retail_sentiment | `/departments/retail_sentiment` | GET, POST, PUT | active-user | `RsDashboardCache.user_id` | `dashboard/{ticker}` (+history/refresh), config, schedule. |
| panic_thermometer | `/departments/panic_thermometer` | GET, POST, PUT, DELETE | active-user | PT config `user_id` (presets: user rows + global shipped) | dashboard, config (+import/export), presets CRUD (+apply), formula parse/test, ruleset preview. |

App-level (not a router): `GET /health`, `GET /healthz` — public; `GET /_debug/client_host` (`include_in_schema=false`); `/docs`, `/redoc`, `/openapi.json` — FastAPI built-ins; SPA fallback `GET /{full_path}` — public, mounted only when `OPENLIA_FRONTEND_DIST` is set.

## Merge gate

- No new router lands without a row in this matrix and per-endpoint rows in the
  contract matrix (enforced by `test_route_matrix_coverage.py` for prefixes).
- Every owner-scoped router points at its FK column and enforcement file.
- Auth level is explicit for every router; the auth router is intentionally the
  only `authed` (not `active-user`) surface, so its unblock endpoints stay
  reachable under the password-reset gate.

## Removed since April 2026 (do not re-add)

- The standalone data-provider registry and its `/settings/...` admin routes —
  folded into the Connectors surface (`/connectors`, admin-gated).
- Per-user equity-research config rows and the legacy equity-research chat
  endpoint — v3 (`/departments/equity-research/v3`) is the sole equity engine;
  it has no per-user config CRUD or standalone chat route.
- Equity-research v1 / v2 / v2.3 engine routes and their config endpoints
  (removed in PRs #220/#222). The `report-templates` `v23/*` paths that remain
  are template-format helpers, not an engine.
