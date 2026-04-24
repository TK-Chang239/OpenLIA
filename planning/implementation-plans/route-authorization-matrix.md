# Route Authorization Matrix

Date: 2026-04-21
Source: REM-P0-006 (see `planning/audits/2026-04-21-remediation-checklist.md`).

This matrix is the authoritative rule set for who can call each HTTP endpoint. Every route has exactly one primary access level, explicit personal-mode and company-mode behaviors, and a documented must-change-password treatment. Owner-scoped resources list their owner field and the enforcement point.

Companion document: `endpoint-contract-matrix.md` (lists DTOs, tests, frontend clients). This file is scoped strictly to authorization semantics.

## Access levels

| Level | Meaning | Dependency |
|---|---|---|
| `public` | No session required. Rate limiting still applies where noted. | none |
| `wizard-session` | Pre-auth, gated by the wizard session token stored on `WizardState.active_session_token` (REM-P1-006). Only usable while `config_store["wizard.completed"] = false`. | planned `require_wizard_session` dep |
| `require_auth` | Authenticated user. Personal mode resolves to the bootstrapped `local` user. Company mode requires a valid `openlia_session` cookie. | `build_require_auth(db_session_factory, mode)` |
| `require_admin` | Authenticated AND `user.is_admin = true`. | `build_require_admin(db_session_factory, mode)` |
| `cookie-optional` | Inspects cookie in-handler (e.g. logout). Treated as semi-public; no auth error if cookie is missing/invalid. | handler-local |

## Must-change-password behavior

Per REM-P1-001, a company-mode authenticated user with `must_change_password = true` is blocked from every `require_auth` and `require_admin` route except the exempt set below. Personal-mode users never have `must_change_password = true`.

**Exempt while `must_change_password = true` (company mode):**

- `POST /auth/change-password`
- `POST /auth/logout`
- `POST /auth/logout-all`
- `GET /auth/session` (frontend needs it to show the forced-change view)
- `GET /health`

All other authenticated endpoints return `403 Forbidden` with `code = "must_change_password"` until the user changes their password.

## Owner scoping

| Resource | Owner FK | Enforcement point |
|---|---|---|
| `ChatSession`, `ChatMessage`, `ChatAttachment` | `ChatSession.user_id` | Plan 12 route factories filter by `user_id == user.id`; admin override not allowed. |
| `Report`, `ReportVersion` | `Report.user_id` | Plan 13 report routes filter/return 404 on mismatch. |
| `RepoItem` | `RepoItem.user_id` | Plan 12 Task 0 model + Plan 22 routes. |
| `PortfolioHolding`, `Watchlist`, `WatchlistItem` | `<table>.user_id` | Plan 21/14 routes. |
| `MbSchedule`, `EuSchedule` | `<table>.user_id` | Plan 15/16 routes; scheduler service validates ownership before `add_schedule/modify_schedule/remove_schedule`. |
| `UserNotification` | `UserNotification.user_id` | Notifications routes filter by `user_id`. |
| `UserLLMPreference` | `UserLLMPreference.user_id` | Plan 11 user LLM picker. |
| `PtUserConfig`, `MrDashboardState`, `RsUserConfig`, `FeSavedFormula` | `<table>.user_id` | Plans 17-20 dashboard routes. |
| `PasswordResetRequest` | requesting user's email + admin reviewer | `/auth/password-reset/*` (by token, no session) and `/admin/password-reset-requests/*` (admin only). |

Admin does NOT override owner scoping for content (chat, report, repo, portfolio). Admin scope is strictly administrative (invites, users, provider config, password reset approvals).

## Mode mounting

| Router | Personal mode | Company mode |
|---|---|---|
| `build_auth_router` | not mounted | mounted |
| `build_admin_router` | not mounted | mounted |
| `build_jobs_router` | mounted | mounted |
| `build_notifications_router` | mounted | mounted |
| `build_data_providers_router` | mounted | mounted |
| `build_llm_providers_admin_router` | mounted | mounted |
| Planned `/setup/*` | loopback only (see below) | mounted |
| Planned `/departments/*` | mounted | mounted |

In personal mode, `require_admin` still applies — the bootstrapped `local` user has `is_admin = true`, so admin checks succeed transparently. In company mode, `is_admin` is enforced against the actual DB row.

## Setup wizard gating

Per REM-P0-007:

- `/setup/status` is always public.
- All other `/setup/*` routes require a valid wizard-session token. Token is minted when the wizard opens and stored on `WizardState.active_session_token`.
- Personal mode: `/setup/*` writes MUST be rejected from non-loopback clients (401 or 403). Check `request.client.host in ("127.0.0.1", "::1")` at the router level.
- Once `wizard.completed = true`, every `/setup/*` write returns `410 Gone`; `/setup/status` continues to return `{completed: true}` so the frontend can decide whether to redirect.

## Shipped routes (Phases 0-9)

### Auth router (`company` only)

| Route | Access | Must-change-password | Rate limit | Notes |
|---|---|---|---|---|
| `POST /auth/register` | public | n/a | `register_ip` | Writes session cookie on success. |
| `POST /auth/login` | public | n/a | `login_ip`, `login_email` | Returns `must_change_password` flag. |
| `POST /auth/logout` | cookie-optional | exempt | — | Clears cookie regardless of session validity. |
| `POST /auth/logout-all` | `require_auth` | exempt | — | Revokes every session for the user. |
| `GET  /auth/session` | `require_auth` | exempt | — | Frontend gate for forced-change view. |
| `GET  /auth/signup-policy` | public | n/a | — | Used by `/register` UI to decide whether to show the invite field. |
| `POST /auth/password-reset/request` | public | n/a | `password_reset_ip` | Always returns `{status: "ok"}`, does not leak account existence. |
| `POST /auth/password-reset/consume` | public (token-authenticated) | n/a | — | Token validated in service; no session required. |
| `POST /auth/change-password` | `require_auth` | **exempt (primary unblock path)** | — | Writes `must_change_password = false` on success. |

### Admin router (`company` only)

All routes: `require_admin`. Must-change-password: not exempt — an admin with a pending forced change cannot manage others until they change their own password.

`/admin/invites` (GET/POST), `/admin/invites/{id}/revoke`, `/admin/users` (GET), `/admin/users/{id}/disable`, `/admin/users/{id}/enable`, `/admin/users/{id}/reset-password`, `/admin/password-reset-requests` (GET), `/admin/password-reset-requests/{id}/approve`, `/admin/password-reset-requests/{id}/reject`.

### Jobs router (both modes)

| Route | Access | Owner scope | Must-change-password | Notes |
|---|---|---|---|---|
| `GET  /jobs/history` | `require_auth` | `JobRun.user_id == user.id` | **blocked** | Plan 11 wires this into the UI. Admin does NOT see other users' jobs. |
| `POST /jobs/{run_id}/retry` | `require_auth` | `JobRun.user_id == user.id` | **blocked** | Returns 503 when scheduler disabled (REM-P1-014). |

### Notifications router (both modes)

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `GET  /notifications/unread` | `require_auth` | `UserNotification.user_id == user.id` | **blocked** |
| `POST /notifications/read` | `require_auth` | `UserNotification.user_id == user.id` | **blocked** |

### Settings — data providers (both modes)

All routes: `require_admin`. Must-change-password: blocked.

Endpoints: `GET/POST /settings/data-providers`, `POST /settings/data-providers/auto-map`, `GET /settings/data-providers/mappings`, `PUT/DELETE /settings/data-providers/mappings/{requirement_type}`, `PATCH/DELETE /settings/data-providers/{provider_id}`, `POST /settings/data-providers/{provider_id}/test-connection`.

### Settings — LLM admin (both modes)

All routes: `require_admin`. Must-change-password: blocked. Prefix: `/settings/admin/llm/*`.

Endpoints: provider CRUD + model CRUD + `remote-models` discovery + department tier mapping + capability overrides (see contract matrix for full list).

### Infrastructure

| Route | Access | Must-change-password |
|---|---|---|
| `GET /health` | public | n/a (exempt by design — frontend uses it to detect server readiness) |

## Planned routes (Plans 10-23)

### Plan 10 — Setup (`/setup/*`)

- `GET /setup/status` — public, exempt from must-change-password (only reachable pre-completion anyway).
- All other `/setup/*` routes — wizard-session, no cookie session required.
- Personal mode: loopback-only (see "Setup wizard gating" above).
- Company mode: accessible to any client until `wizard.completed = true`. After completion, writes return 410.

### Plan 11 — Settings page

- No new backend routes. The frontend-only Plan 11 consumes existing admin/settings/LLM-admin routes. Non-admin users see only the "Models (user preference)" and "Account" subsections. Admin sees Admin + Data Providers + LLM admin tabs.

### Plan 12 — Shared chat + repository

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `GET/POST /chat/sessions` | `require_auth` | `ChatSession.user_id` | blocked |
| `GET/PATCH/DELETE /chat/sessions/{id}` | `require_auth` | `ChatSession.user_id == user.id` | blocked |
| `GET /chat/sessions/{id}/messages` | `require_auth` | same | blocked |
| `POST /chat/stream` (SSE) | `require_auth` | runner loads session and validates `user_id` | blocked |
| `GET/POST /repo/items` | `require_auth` | `RepoItem.user_id` | blocked |
| `GET/DELETE /repo/items/{id}` | `require_auth` | `RepoItem.user_id == user.id` | blocked |

### Plan 13 — Secretary + report pipeline

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `POST /departments/secretary/chat` (SSE) | `require_auth` | chat session owner | blocked |
| `POST /reports` | `require_auth` | writes `Report.user_id = user.id` | blocked |
| `GET /reports/{id}` | `require_auth` | `Report.user_id == user.id` | blocked |
| `GET /reports/{id}/stream` (SSE resume) | `require_auth` | same | blocked |

### Plan 14 — Equity Research

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `POST /departments/equity-research/chat` (SSE) | `require_auth` | session owner | blocked |
| `GET/POST/PATCH/DELETE /departments/equity-research/configs` | `require_auth` | `ErUserConfig.user_id` | blocked |

### Plan 15 — Earnings Update

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `POST /departments/earnings-update/chat` | `require_auth` | session owner | blocked |
| `GET/POST/DELETE /departments/earnings-update/watchlist` | `require_auth` | `EuWatchlistItem.user_id` | blocked |
| `GET/POST/PATCH/DELETE /departments/earnings-update/schedules` | `require_auth` | `EuSchedule.user_id` | blocked |

### Plan 16 — Morning Briefing (shipped)

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `GET/PUT /departments/morning-briefing/config` | `require_auth` | `MbConfig.user_id` | blocked |
| `GET/PUT/DELETE /departments/morning-briefing/schedule` | `require_auth` | `MbSchedule.user_id` | blocked |
| `POST /departments/morning-briefing/report` (SSE) | `require_auth` | writes `Report.user_id = user.id` | blocked |
| `POST /departments/morning-briefing/chat/session` | `require_auth` | `ChatSession.user_id` (resolve-or-create) | blocked |

### Plan 19 — Macro Research (shipped)

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `GET /departments/macro-research/dashboards` | `require_auth` | — (enumerates preset dashboards) | blocked |
| `GET /departments/macro-research/dashboards/{slug}` | `require_auth` | snapshot derived per-user where applicable | blocked |
| `GET/PUT /departments/macro-research/dashboards/{slug}/config` | `require_auth` | `MrDashboardConfig.user_id` | blocked |
| `POST /departments/macro-research/dashboards/{slug}/assessment/run` | `require_auth` | writes `MrAssessmentRun.user_id = user.id` | blocked |
| `GET/PUT/DELETE /departments/macro-research/schedule` | `require_auth` | `MrSchedule.user_id` | blocked |

### Plan 20 — Retail Sentiment (shipped)

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `GET /departments/retail-sentiment/dashboard` | `require_auth` | snapshot aggregated globally; read-only | blocked |
| `GET /departments/retail-sentiment/dashboard/history` | `require_auth` | snapshot history | blocked |
| `GET/PUT /departments/retail-sentiment/config` | `require_auth` | `RsUserConfig.user_id` | blocked |
| `POST /departments/retail-sentiment/run` | `require_auth` | writes `RsSnapshot` globally; audit by user | blocked |
| `GET /departments/retail-sentiment/stocks/{ticker}/sentiment` | `require_auth` | — | blocked |
| `GET /departments/retail-sentiment/spikes` | `require_auth` | — | blocked |

### Plans 17-18 — Formula engine + Panic Thermometer

- `/departments/{slug}/state` — `require_auth`, owner scope on `<Pt|Fe>UserConfig.user_id` / `FeSavedFormula.user_id`.
- `/departments/{slug}/metrics` — `require_auth`, owner scope. PT preset endpoints that are globally readable are `public` for GET, `require_admin` for mutations.

### Plan 21 — Portfolio (shipped)

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `GET/POST/PATCH/DELETE /portfolio/holdings` | `require_auth` | `PortfolioHolding.user_id` | blocked |
| `GET /portfolio/analytics` | `require_auth` | derived from user's holdings | blocked |
| `POST /portfolio/refresh-prices` | `require_auth` | operates on user's holdings | blocked |
| `POST /portfolio/import-csv` / `GET /portfolio/export-csv` | `require_auth` | user's holdings only | blocked |
| `GET /portfolio/search` | `require_auth` | provider-backed ticker search; no PII | blocked |

### Plan 22 — Repository (shipped)

| Route | Access | Owner scope | Must-change-password |
|---|---|---|---|
| `GET /repo/items` | `require_auth` | `RepoItem.user_id` | blocked |
| `POST /repo/items` | `require_auth` | writes `RepoItem.user_id = user.id` | blocked |
| `DELETE /repo/items` | `require_auth` | `RepoItem.user_id == user.id` (bulk) | blocked |
| `GET /repo/facets` | `require_auth` | aggregates over user's RepoItem rows | blocked |

### Plan 23 — Production static serving

- `GET /` + SPA fallback — public. API routes resolve before fallback so static serving cannot shadow `/auth/*`, `/admin/*`, etc.

## Merge gate

- No new route lands without a row in both this matrix and the endpoint contract matrix.
- Every owner-scoped row must point at the FK field and the enforcement point.
- Must-change-password behavior is explicit for every authenticated route.
- REM-P0-006 stays `[~]` until (a) this matrix covers every shipped and planned route and (b) the must-change-password gate (REM-P1-001) is enforced in code matching the exempt set above.
