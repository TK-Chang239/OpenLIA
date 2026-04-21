# Phase 0-8 Implementation vs Plan 9+ Consistency Audit

Date: 2026-04-21

Scope: current implementation through Phase 8, reviewed against future
implementation plans 9 through 15. This audit checks whether the future plans
are executable against the implementation that is already in place.

Reviewed against:

- `planning/implementation-plans/README.md`
- `planning/implementation-plans/2026-04-17-phase-9-login-and-account-ui.md`
- `planning/implementation-plans/2026-04-17-phase-10-setup-wizard.md`
- `planning/implementation-plans/2026-04-17-phase-11-settings-page.md`
- `planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md`
- `planning/implementation-plans/2026-04-17-phase-13-report-pipeline-and-secretary.md`
- `planning/implementation-plans/2026-04-17-phase-14-equity-research.md`
- `planning/implementation-plans/2026-04-17-phase-15-earnings-update.md`

Primary implementation references:

- `frontend/vite.config.ts`
- `frontend/src/api/auth.ts`
- `packages/core/src/openlia/llm/runtime/events.py`
- `packages/core/src/openlia/llm/runtime/messages.py`
- `packages/server/src/openlia_server/app.py`
- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/db/crypto.py`
- `packages/server/src/openlia_server/db/models/auth.py`
- `packages/server/src/openlia_server/db/models/config.py`
- `packages/server/src/openlia_server/db/models/content.py`
- `packages/server/src/openlia_server/db/models/infrastructure.py`
- `packages/server/src/openlia_server/db/models/scheduler.py`
- `packages/server/src/openlia_server/middleware/auth.py`
- `packages/server/src/openlia_server/routes/admin.py`
- `packages/server/src/openlia_server/routes/auth.py`
- `packages/server/src/openlia_server/routes/jobs.py`
- `packages/server/src/openlia_server/routes/notifications.py`
- `packages/server/src/openlia_server/routes/settings.py`
- `packages/server/src/openlia_server/services/llm_providers.py`

Validation commands run:

None. This was a static consistency audit using the code-review graph plus
targeted file and plan reads. No source or plan files were modified except this
audit document.

## Executive Summary

The Phase 0-8 implementation has moved past several findings from the older
audits: scheduler job/notification routes now use real auth factories, app
lifespan uses `OPENLIA_DB_URL`, and secret-key creation avoids the write-then-
chmod race.

However, future plans 9 through 15 are not yet safe to execute as written.
Many plan files have top-of-file "audit normalization" notes that describe the
right contracts, but later executable code blocks still contain stale imports,
wrong DTO shapes, duplicate route modules, integer IDs, old chat field names,
and nonexistent runtime helpers. The highest-risk active issue is that Phase 9
would preserve the currently broken Phase 8 auth client instead of correcting
it.

Recommendation: patch the roadmap README and the individual Plan 9-15 code
blocks before assigning implementation work. Treat the normalization banners as
warnings, not as sufficient fixes.

## Severity Definitions

- High: executing the plan as written will produce broken user-facing behavior,
  import failures, duplicated routes, or frontend/backend contract failures.
- Medium: meaningful drift, security-hardening gap, or implementation detail
  likely to cause rework.
- Low: documentation cleanup that does not directly block execution.

## Current Implementation Baseline

The current backend contract is factory-oriented:

- Auth dependencies are produced by
  `openlia_server.middleware.auth.build_require_auth(...)` and
  `build_require_admin(...)`.
- There is no shipped `get_db_session`, `get_db`, `current_user`, or
  `require_user` dependency helper for new routers to import.
- Backend TestClient paths are bare paths such as `/auth/session`,
  `/settings/admin/llm/providers`, `/jobs/history`, and
  `/notifications/unread`.
- Frontend code is expected to call `/api/...`, with Vite stripping `/api`
  before proxying to FastAPI.
- IDs for users, invites, sessions, reports, schedules, and related FKs are
  UUID strings, not integers.
- Runtime report requests use
  `openlia.llm.runtime.messages.ReportRequest(mode, user_input,
  enabled_sections, custom_sections, length)`.
- Runtime events expose `to_wire(event)`, not `serialize_sse(event)`.

## Findings

### 1. High - Phase 9 Preserves The Obsolete Auth Envelope

Status: open.

Affected files:

- `frontend/src/api/auth.ts`
- `packages/server/src/openlia_server/routes/auth.py`
- `planning/implementation-plans/2026-04-17-phase-9-login-and-account-ui.md`

Observed implementation:

The backend returns flat login/session payloads:

```json
{
  "user_id": "...",
  "email": "...",
  "display_name": "...",
  "is_admin": true,
  "must_change_password": false
}
```

`frontend/src/api/auth.ts` still expects:

```ts
interface SessionResponse {
  user: AuthUser;
}
```

Plan 9 says `/api/auth/login` returns `{user, must_change_password}` and
replaces `auth.ts` with the same nested shape.

Impact:

Executing Plan 9 as written will keep the Phase 8 auth integration broken.
`getSession()` and `login()` will return `undefined` for valid backend
responses, and all account/settings/admin role logic built on top of
`AuthContext` will be unreliable.

Recommended fix:

- Patch Phase 8 implementation first:
  - Map backend `user_id` to frontend `id`.
  - Map `is_admin` to frontend `role`.
  - Carry `display_name`.
  - Return `must_change_password` from `login()`.
  - Default `must_change_password` to `false` for `/auth/session`, unless the
    backend is updated to include it.
- Rewrite Plan 9 auth API tests and code blocks around the flat DTO.

### 2. High - Vite `/api` Rewrite Is Documented But Not Implemented

Status: open.

Affected files:

- `frontend/vite.config.ts`
- `planning/implementation-plans/README.md`
- all frontend plans that call `/api/...`

Observed implementation:

The roadmap README says the frontend `/api` proxy is already shipped with:

```ts
rewrite: (p) => p.replace(/^\/api/, "")
```

But `frontend/vite.config.ts` still has:

```ts
proxy: {
  "/api": "http://localhost:8000",
}
```

Vite preserves `/api` in that shorthand form.

Impact:

Frontend calls such as `/api/auth/session`, `/api/settings/admin/llm/providers`,
and `/api/departments/...` proxy to FastAPI with the `/api` prefix still
present. Backend routes are bare, so dev-server integration returns 404.

Recommended fix:

Patch `frontend/vite.config.ts`:

```ts
proxy: {
  "/api": {
    target: "http://localhost:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
}
```

Then update `planning/implementation-plans/README.md` only after the source
change lands.

### 3. High - Roadmap README's Authoritative Backend Contract Has Wrong Imports

Status: open.

Affected file:

- `planning/implementation-plans/README.md`

Observed implementation:

The README's "Current backend contract" lists several wrong model locations:

- `ConfigStore` and `WizardState` are listed under
  `openlia_server.db.models.config`, but source defines them in
  `openlia_server.db.models.infrastructure`.
- `JobRun` and `Notification` are listed under
  `openlia_server.db.models.infrastructure`, but source defines `JobRun` and
  `UserNotification` in `openlia_server.db.models.scheduler`.
- `LoginAttempt` is listed, but no `LoginAttempt` model exists.

Impact:

The README is intended to prevent future plan drift, but it currently
reintroduces drift. Implementation workers using it as source of truth may add
wrong imports before reaching individual plan code.

Recommended fix:

Update the README model-import section to:

```python
from openlia_server.db.models.auth import User, Session, SignupInvite, PasswordResetRequest, AuthEvent, SignupPolicy
from openlia_server.db.models.config import LLMProvider, LLMModel, DataProvider, DataProviderRequirementMapping, WebSearchProvider, UserLLMPreference
from openlia_server.db.models.content import ChatSession, ChatMessage, ChatAttachment, Report
from openlia_server.db.models.infrastructure import WizardState, ConfigStore
from openlia_server.db.models.scheduler import MbSchedule, EuSchedule, JobRun, UserNotification
```

Add `RepoItem` only after Plan 12 creates it, or document it as pending.

### 4. High - Plan 10 Notes Are Correct But Its Code Blocks Are Still Stale

Status: open.

Affected files:

- `planning/implementation-plans/2026-04-17-phase-10-setup-wizard.md`
- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/db/models/infrastructure.py`
- `packages/server/src/openlia_server/services/llm_providers.py`

Observed implementation:

Plan 10's normalization banner correctly says:

- no `get_db_session` / `get_db`
- no nonexistent LLM helpers
- `wizard.completed` can be a Python bool
- `wizard_state.current_step` must become a string

But later code blocks still:

- import `get_db_session`
- call `.lower()` directly on `config_store["wizard.completed"]`
- call nonexistent `llm_svc.test_provider`, `clear_all_providers`,
  `add_model`, and `list_data_provider_rows`

Current source also still has legacy CLI wizard reset behavior:

```python
current_step=1
```

Impact:

Plan 10 will fail at import/runtime unless an implementer manually ignores
large parts of the plan. If only the DB migration is implemented, `openlia
wizard reset` will write an invalid wizard state after the migration.

Recommended fix:

- Rewrite Plan 10's executable code blocks to use a router factory with a local
  session dependency.
- Add or avoid service helpers explicitly; do not call unshipped helpers.
- Replace boolean parsing with a helper that accepts bool and string values.
- In the same task that reshapes `wizard_state`, patch `openlia wizard reset`
  to write:

```python
state.status = "not_started"
state.current_step = "mode"
state.completed_steps = []
state.active_session_token = None
state.step_data = {}
```

### 5. High - Plan 11 Still Duplicates Existing Admin Routes

Status: open.

Affected files:

- `planning/implementation-plans/2026-04-17-phase-11-settings-page.md`
- `packages/server/src/openlia_server/routes/admin.py`
- `packages/server/src/openlia_server/routes/settings.py`

Observed implementation:

The top of Plan 11 says not to create duplicate admin route/service modules.
The plan body still creates:

- `routes/admin_invites.py`
- `routes/admin_users.py`
- `routes/admin_password_reset_requests.py`
- `services/admin_invites.py`
- `services/admin_users.py`
- `services/admin_password_reset.py`

The shipped backend already exposes the admin surface in `routes/admin.py`:

- `GET /admin/invites`
- `POST /admin/invites`
- `POST /admin/invites/{invite_id}/revoke`
- `GET /admin/users`
- `POST /admin/users/{user_id}/disable`
- `POST /admin/users/{user_id}/enable`
- `POST /admin/users/{user_id}/reset-password`
- `GET /admin/password-reset-requests`
- `POST /admin/password-reset-requests/{request_id}/approve`
- `POST /admin/password-reset-requests/{request_id}/reject`

Plan 11 also still contains stale `/settings/models/*` references, integer IDs,
`db.models.user`, `db.models.llm`, and bare `require_auth` imports.

Impact:

Executing Plan 11 as written will create parallel admin APIs with conflicting
paths and likely conflicting response shapes.

Recommended fix:

- Delete the duplicate-admin tasks from Plan 11.
- Add frontend clients against existing `/admin/*` routes.
- If response fields are missing for Settings UI, extend `routes/admin.py`
  directly.
- Point LLM admin UI at `/api/settings/admin/llm/*`, matching the shipped
  `build_llm_providers_admin_router()`.

### 6. High - Plan 12 Still Uses Old ChatSession Fields And Integer IDs

Status: open.

Affected files:

- `planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md`
- `packages/server/src/openlia_server/db/models/content.py`

Observed implementation:

The shipped `ChatSession` fields are:

```python
id: str
user_id: str
is_pinned: bool
is_archived: bool
context: dict | None
```

Plan 12's banner states this correctly, but its tests and service code still
assert or write:

- `row.pinned`
- `row.archived_at`
- `ChatSession(..., pinned=False)`
- `session_id: int`
- `user_id: int`

The route snippets also import missing `get_db_session` and `require_user`.

Impact:

Plan 12 will fail at model construction, route import, and frontend/backend DTO
typing unless an implementer rewrites the snippets.

Recommended fix:

- Rewrite Plan 12 services around `is_pinned` and `is_archived`.
- Use UUID string IDs in Python and TypeScript.
- Decide explicitly whether archive timestamps are needed. If yes, add a
  migration; if no, remove `archived_at` from API DTOs.
- Use router factories with `build_require_auth(...)` and local session
  dependencies.
- Put `RepoItem` either in `db.models.content` and update `models/__init__.py`,
  or create `db.models.repo` and update import registration deliberately.

### 7. High - Plans 13-15 Still Contain Stale Auth And Runtime Snippets

Status: open.

Affected files:

- `planning/implementation-plans/2026-04-17-phase-13-report-pipeline-and-secretary.md`
- `planning/implementation-plans/2026-04-17-phase-14-equity-research.md`
- `planning/implementation-plans/2026-04-17-phase-15-earnings-update.md`
- `packages/core/src/openlia/llm/runtime/events.py`
- `packages/core/src/openlia/llm/runtime/messages.py`

Observed implementation:

Plan 13 still imports:

```python
from openlia_server.auth import current_user, CurrentUser
from openlia_server.db.session import get_session
```

Plan 14 still imports:

```python
from openlia_server.auth import current_user, CurrentUser
from openlia.runtime.requests import ReportRequest
from openlia.runtime.sse import sse_stream
```

Plan 15 still imports:

```python
from openlia_server.db.models.users import User
from openlia_server.middleware.auth import require_user
from openlia.llm.runtime.events import serialize_sse
```

The shipped runtime exposes:

- `openlia.llm.runtime.messages.ReportRequest`
- `openlia.llm.runtime.events.to_wire`

Impact:

These plans will fail with import errors before implementing department
behavior. Some tests may pass only if implementers create compatibility shims
that are not part of the planned architecture.

Recommended fix:

- Rewrite every department router as a factory:

```python
def build_department_router(*, db_session_factory, mode: str, ...) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
```

- Replace every `current_user` / `require_user` / `get_session` / `get_db`
  snippet.
- Replace `openlia.runtime.*` imports with `openlia.llm.runtime.*`.
- Serialize SSE frames by calling `to_wire(event)` and wrapping it in the route,
  or add a real server helper before using it.

### 8. Medium - Invite Token Hardening Is Partial

Status: open.

Affected files:

- `packages/server/src/openlia_server/db/models/auth.py`
- `packages/server/src/openlia_server/routes/admin.py`
- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/services/auth/registration.py`

Observed implementation:

Registration uses `token_hash`, and admin list no longer returns raw token
material. However, `SignupInvite` still stores both:

```python
token
token_hash
```

The CLI create/list/revoke flow still prints, lists prefixes from, and revokes
by the raw `token` column.

Impact:

The HTTP admin API is closer to the desired security shape, but the database
and CLI still expose reusable invite credentials. Future Plan 9/11 UI should
not depend on raw invite-token listing or revocation by raw token prefix.

Recommended fix:

- Migrate `signup_invites` to store only `token_hash`.
- Return raw invite tokens exactly once from creation paths.
- Make CLI revoke by invite ID or a non-secret display code, not by token
  prefix.
- Keep list responses free of token material.

### 9. Medium - CLI Audit Attribution Still Has Drift

Status: open.

Affected files:

- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/_cli_support.py`
- `packages/server/src/openlia_server/services/auth/password_reset.py`

Observed implementation:

`admin reset-password` delegates to `admin_direct_reset(...)`, which logs
`password_reset_by_admin` without CLI metadata. Separately, `log_cli_event()`
documents that it guarantees `metadata.source="cli"`, but caller metadata can
override the source value because caller keys win.

Impact:

Future Settings/admin work may rely on audit rows for provenance, but current
CLI reset events cannot be distinguished from UI-originated resets. The helper
also allows future CLI commands to accidentally violate its documented
guarantee.

Recommended fix:

- Extend `admin_direct_reset()` to accept optional metadata and pass
  `{"source": "cli"}` from the CLI.
- Make `log_cli_event()` merge with `source="cli"` winning last.
- Add CLI tests for reset-password audit metadata and source override
  prevention.

## Resolved Or No-Longer-Applicable Older Findings

The following older findings from prior audits are already resolved in current
source and should not block Plan 9+ consistency work:

- Scheduler routes now use real auth factories:
  - `app.py` mounts `build_jobs_router(db_session_factory=factory, mode=mode)`
  - `app.py` mounts
    `build_notifications_router(db_session_factory=factory, mode=mode)`
- `routes/jobs.py` and `routes/notifications.py` bind
  `build_require_auth(...)`.
- App lifespan now resolves DB configuration through `resolve_db_url()` /
  `OPENLIA_DB_URL`.
- Secret-key file creation now uses `os.open(..., 0o600)` plus atomic
  `os.replace(...)`, avoiding the permissions race.
- Route session lifecycle was previously resolved by `make_session_dependency`
  and auth-session `try/finally` closure.

## Recommended Work Queue

1. Patch `planning/implementation-plans/README.md` so the authoritative
   contract matches current source exactly.
2. Patch Phase 8 implementation:
   - Vite `/api` rewrite.
   - Auth DTO boundary mapping from flat backend responses.
3. Rewrite Plan 9 auth/account API snippets around the flat DTO.
4. Rewrite Plan 10 code blocks for session dependencies, bool config parsing,
   LLM service calls, and CLI wizard reset compatibility.
5. Rewrite Plan 11 to extend existing admin/settings routes rather than
   creating duplicate admin route stacks.
6. Rewrite Plan 12 for UUID string IDs, `is_pinned` / `is_archived`, and real
   auth/session patterns.
7. Rewrite Plans 13-15 runtime and route snippets to use
   `openlia.llm.runtime.*`, `to_wire`, router factories, and shipped model
   paths.

Only after those plan patches land should implementation workers execute Plans
9 through 15 task-by-task.
