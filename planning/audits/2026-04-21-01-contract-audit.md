# Contract Audit

Date: 2026-04-21

Scope: backend routes, frontend API clients, DTO shapes, auth dependencies,
runtime event contracts, and model/import paths needed for Plans 9+.

Validation commands run: none. Static audit using the code-review graph plus
targeted source and plan reads.

## Executive Summary

The product contract is not yet stable enough for Plan 9+ execution. The
backend route surface is small and consistent in source, but the frontend API
clients and future plans still encode older contracts. The most urgent issues
are the broken auth DTO mapping, missing Vite `/api` rewrite, stale roadmap
import table, and repeated plan snippets that import nonexistent helpers.

## Current Contract Baseline

Backend routes currently mount bare paths:

- `/auth/*` in company mode only.
- `/admin/*` in company mode only.
- `/settings/data-providers/*`.
- `/settings/admin/llm/*`.
- `/jobs/*`.
- `/notifications/*`.
- `/health` and `/healthz`.

Frontend clients currently call:

- `/api/auth/session`
- `/api/auth/login`
- `/api/auth/logout`
- `/api/notifications/unread`
- `/api/notifications/read`

Runtime contracts currently expose:

- `openlia.llm.runtime.messages.ReportRequest`
- `openlia.llm.runtime.events.to_wire`
- `ReportStart(report_id, department, mode, section_titles)`
- `ReportComplete(report_id, schema)`

Auth dependency contract:

- Use `build_require_auth(db_session_factory=..., mode=...)`.
- Use `build_require_admin(db_session_factory=..., mode=...)`.
- Do not import `get_db_session`, `get_db`, `current_user`, or `require_user`;
  they do not ship.

## Findings

### 1. High - Auth DTO Contract Is Broken At The Frontend Boundary

Backend `/auth/login` and `/auth/session` return flat fields:

- `user_id`
- `email`
- `display_name`
- `is_admin`
- `must_change_password` on login

`frontend/src/api/auth.ts` expects a nested `{user: ...}` envelope. Plan 9
also replaces `auth.ts` with the same stale nested shape.

Impact: session refresh and login can mark the app authenticated with an
undefined user object. Plan 9 would preserve the defect.

Required fix:

- Define a backend DTO type with `user_id`, `email`, `display_name`, `is_admin`,
  and optional `must_change_password`.
- Map to frontend `AuthUser` at the API boundary.
- Update Phase 8 auth tests and every Plan 9 auth snippet.

### 2. High - `/api` Proxy Rewrite Is Claimed But Not Implemented

The roadmap README says the Vite proxy strips `/api`, but
`frontend/vite.config.ts` still uses:

```ts
proxy: {
  "/api": "http://localhost:8000",
}
```

Impact: `/api/auth/session` proxies to `/api/auth/session`, while FastAPI
mounts `/auth/session`. Every frontend API call will 404 in dev.

Required fix:

```ts
proxy: {
  "/api": {
    target: "http://localhost:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
}
```

### 3. High - Roadmap README Has Wrong "Authoritative" Import Paths

The README incorrectly lists:

- `ConfigStore` and `WizardState` under `db.models.config`.
- `JobRun` and `Notification` under `db.models.infrastructure`.
- `LoginAttempt`, which does not exist.

Current source has:

- `WizardState`, `ConfigStore` in `db.models.infrastructure`.
- `JobRun`, `UserNotification` in `db.models.scheduler`.
- no `LoginAttempt`.

Impact: workers using the README will write wrong imports before they even read
individual plans.

Required fix: patch the README model import block before more Plan 9+ work.

### 4. High - Future Plans Still Use Nonexistent Server Dependencies

Plan 10-15 executable snippets still include old patterns:

- `from openlia_server.db.session import get_db_session`
- `from openlia_server.db.session import get_db`
- `from openlia_server.auth import current_user, CurrentUser`
- `from openlia_server.middleware.auth import require_user`
- `from openlia.llm.runtime.events import serialize_sse`
- `from openlia.runtime.requests import ReportRequest`

Impact: implementation will fail at import time unless compatibility shims are
added. Adding shims would hide contract drift rather than fixing it.

Required fix: rewrite each route as a router factory with local session
dependency and `build_require_auth`.

### 5. Medium - Admin And Settings Contracts Are Split Across Old And New Names

Current LLM admin routes are under `/settings/admin/llm/*`. Plan 11 still has
multiple `/settings/models/*` snippets. Current admin routes already live in
`routes/admin.py`; Plan 11 still creates duplicate `routes/admin_*` modules.

Impact: duplicate route stacks and frontend calls to wrong endpoints.

Required fix:

- Settings Models admin client uses `/api/settings/admin/llm/*`.
- Admin section clients use existing `/api/admin/*`.
- Extend existing routers in place.

## Contract Matrix Needed Before Execution

Create and maintain a single table with:

- endpoint path
- backend route function
- frontend client function
- auth dependency
- request DTO
- response DTO
- owning plan
- test file

This table should be committed before Plan 9 implementation continues.

## Recommended Fix Order

1. Patch `frontend/vite.config.ts`.
2. Patch `frontend/src/api/auth.ts` and auth tests.
3. Patch `planning/implementation-plans/README.md`.
4. Rewrite Plan 9 auth snippets.
5. Rewrite Plan 10-15 stale imports and route factories.
