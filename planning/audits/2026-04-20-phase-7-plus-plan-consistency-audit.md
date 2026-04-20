# Phase 7+ Implementation Plan Consistency Audit

Date: 2026-04-20

Scope: implementation plans starting with Phase 7 / Plan 7 through Plan 15.
This audit checks the written implementation plans for consistency with the
currently shipped Phase 0-6 implementation and with cross-plan contracts.

Reviewed against:

- `planning/implementation-plans/2026-04-17-phase-7-cli-surface.md`
- `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md`
- `planning/implementation-plans/2026-04-17-phase-9-login-and-account-ui.md`
- `planning/implementation-plans/2026-04-17-phase-10-setup-wizard.md`
- `planning/implementation-plans/2026-04-17-phase-11-settings-page.md`
- `planning/implementation-plans/2026-04-17-phase-12-shared-chat-components.md`
- `planning/implementation-plans/2026-04-17-phase-13-report-pipeline-and-secretary.md`
- `planning/implementation-plans/2026-04-17-phase-14-equity-research.md`
- `planning/implementation-plans/2026-04-17-phase-15-earnings-update.md`

Implementation references:

- `frontend/vite.config.ts`
- `frontend/src/App.tsx`
- `packages/server/src/openlia_server/app.py`
- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/auth/deps.py`
- `packages/server/src/openlia_server/middleware/auth.py`
- `packages/server/src/openlia_server/db/session.py`
- `packages/server/src/openlia_server/db/bootstrap.py`
- `packages/server/src/openlia_server/db/models/auth.py`
- `packages/server/src/openlia_server/db/models/content.py`
- `packages/server/src/openlia_server/db/models/infrastructure.py`
- `packages/server/src/openlia_server/routes/admin.py`
- `packages/server/src/openlia_server/routes/auth.py`
- `packages/server/src/openlia_server/routes/notifications.py`
- `packages/server/src/openlia_server/routes/settings.py`

Validation commands run:

None. This was a static consistency audit using the code-review graph plus
targeted file reads. No files were modified during the audit itself.

## Executive Summary

Phase 7 and later plans are mostly not implemented yet. The current CLI is
still the minimal `serve` command from the scaffold, and the frontend remains a
minimal `App.tsx` placeholder.

The larger issue is not simply missing implementation. Several Phase 7+ plans
still carry stale API shapes from earlier drafts. If executed as written, they
will fail early with import errors, route mismatches, invalid SQLAlchemy field
names, or frontend/backend response-shape mismatches.

The highest-risk drift:

1. Frontend plans use `/api/...`, but the current Vite proxy does not rewrite
   `/api` away and the FastAPI app mounts unprefixed routes.
2. Phase 8/9 auth clients expect nested `{user: ...}` responses, but the
   backend returns flat `user_id`, `email`, `display_name`, `is_admin` fields.
3. Phase 10-15 plans repeatedly import non-existent server APIs such as
   `openlia_server.db.models.user`, `get_db_session`, `require_user`,
   `openlia_server.auth.current_user`, and `openlia.runtime.requests`.
4. Phase 11 duplicates admin routes that already exist from Phase 2.
5. Later plans use integer IDs where the shipped schema uses UUID strings.
6. Wizard state and config-store value types drift between Phase 7 and Phase 10.
7. Notification/job routes are still wired to a placeholder auth dependency.

Recommendation: normalize the shared backend/frontend contracts in the plans
before executing any Phase 7+ implementation work. Phase 8 and Phase 9 should
be corrected first because every later UI plan depends on their API client,
auth context, and routing conventions.

## Severity Definitions

- High: executing the plan as written will produce a broken user-facing flow,
  fail to compile/import, or conflict with already shipped production routes.
- Medium: meaningful behavioral drift, likely test fragility, or a plan shape
  that will force avoidable rework.
- Low: documentation or naming cleanup that does not directly block execution.

## Current Implementation Baseline

The graph reports the current implementation as concentrated around server DB,
auth, provider configuration, LLM runtime, and scheduling. The current CLI has
only `serve`; there is no implemented Phase 7 admin/wizard/secrets/maintenance
surface.

Relevant current code:

```python
# packages/server/src/openlia_server/cli.py
@app.command()
def serve(...):
    bootstrap()
    uvicorn.run("openlia_server.app:create_app", ...)
```

The current app mounts:

```python
if mode == "company":
    app.include_router(build_auth_router(db_session_factory=factory))
    app.include_router(build_admin_router(db_session_factory=factory))

app.include_router(build_data_providers_router(db_session_factory=factory))
app.include_router(build_llm_providers_admin_router(db_session_factory=factory, mode=mode))
app.include_router(jobs_router)
app.include_router(notifications_router)
```

The current frontend is still:

```tsx
export default function App() {
  return (
    <main>
      <h1>OpenLIA</h1>
      <p>Self-hosted AI investor assistant.</p>
    </main>
  );
}
```

## Findings

### 1. High - Frontend `/api` Contract Does Not Match Vite Or FastAPI Wiring

Status: open.

Affected plans:

- Plan 8 - Frontend Shell
- Plan 9 - Login + Account Management UI
- Plan 10 - Setup Wizard
- Plan 11 - Settings Page
- Plan 12 - Shared Chat Components
- Plan 13 - Report Pipeline + Secretary
- Plan 14 - Equity Research
- Plan 15 - Earnings Update

Affected implementation files:

- `frontend/vite.config.ts`
- `packages/server/src/openlia_server/app.py`

Plan expectation:

Plan 8 says every frontend API module should call `/api/...` because
`vite.config.ts` proxies `/api` to the backend. Plans 13 and 14 go further and
state that the Vite proxy rewrites `/api/*` to `/*`.

Observed implementation:

The Vite config currently does not define a rewrite:

```ts
proxy: {
  "/api": "http://localhost:8000",
},
```

FastAPI mounts routes without an `/api` prefix, such as `/auth/session`,
`/settings/data-providers`, `/jobs/history`, and `/notifications/unread`.

Impact:

Frontend calls like `/api/auth/session`, `/api/notifications/unread`,
`/api/settings/...`, and `/api/departments/...` will be proxied to the backend
with the `/api` prefix still present. The backend does not mount those routes,
so the calls will 404.

Recommended fix:

Pick one contract and apply it consistently before Phase 8 executes:

1. Preferably add a Vite proxy rewrite:

   ```ts
   proxy: {
     "/api": {
       target: "http://localhost:8000",
       changeOrigin: true,
       rewrite: (path) => path.replace(/^\/api/, ""),
     },
   },
   ```

2. Or mount the FastAPI API under `/api`, then update every existing route and
   test expectation accordingly.

The current plans are written for option 1, so option 1 is the lower-blast
change.

### 2. High - Auth Response Shape In Phase 8/9 Does Not Match Backend

Status: open.

Affected plans:

- Plan 8 - Frontend Shell
- Plan 9 - Login + Account Management UI
- Plan 11 - Settings Page

Affected implementation file:

- `packages/server/src/openlia_server/routes/auth.py`

Plan expectation:

The frontend auth API is written around:

```ts
interface SessionResponse {
  user: AuthUser;
}

interface LoginResult {
  user: AuthUser;
  must_change_password: boolean;
}
```

Tests in Plan 9 mock:

```json
{
  "user": {"id": "u1", "email": "a", "role": "user"},
  "must_change_password": true
}
```

Observed implementation:

The backend returns flat login fields:

```python
return {
    "user_id": auth.user.id,
    "email": auth.user.email,
    "display_name": auth.user.display_name,
    "is_admin": auth.user.is_admin,
    "must_change_password": auth.must_change_password,
}
```

The session route also returns flat fields and omits `must_change_password`:

```python
return {
    "user_id": user.id,
    "email": user.email,
    "display_name": user.display_name,
    "is_admin": user.is_admin,
}
```

There is no `role` column on `User`; the shipped schema uses `is_admin`.

Impact:

`getSession()`, `login()`, `AuthContext`, `ProtectedRoute`, and Settings admin
gating will not work as planned. Code that checks `auth.user.role === "admin"`
will misclassify or crash unless the frontend maps `is_admin` to a role.

Recommended fix:

Update Phase 8/9/11 frontend contracts to match the backend:

```ts
interface AuthUserResponse {
  user_id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
  must_change_password?: boolean;
}
```

Then map at the frontend boundary:

```ts
const user = {
  id: resp.user_id,
  email: resp.email,
  display_name: resp.display_name,
  role: resp.is_admin ? "admin" : "user",
};
```

Also update `/auth/session` to return `must_change_password`, or make the
frontend explicitly default it to false after a session refresh.

### 3. High - Later Plans Import Server APIs That Do Not Exist

Status: open.

Affected plans:

- Plan 10 - Setup Wizard
- Plan 11 - Settings Page
- Plan 12 - Shared Chat Components
- Plan 13 - Report Pipeline + Secretary
- Plan 14 - Equity Research
- Plan 15 - Earnings Update

Examples from plans:

- `from openlia_server.db.models.user import User`
- `from openlia_server.db.models.users import User`
- `from openlia_server.db.models.llm import LLMModel`
- `from openlia_server.db.session import get_db_session`
- `from openlia_server.db.session import get_db`
- `from openlia_server.middleware.auth import require_auth`
- `from openlia_server.middleware.auth import require_user`
- `from openlia_server.auth import current_user, CurrentUser`
- `from openlia_server.security.passwords import argon2_hash`
- `from openlia.runtime.requests import ReportRequest`
- `from openlia.llm.runtime.events import serialize_sse`

Observed implementation:

Current equivalents are different:

- `User` is in `openlia_server.db.models.auth`.
- `LLMModel` is in `openlia_server.db.models.config`.
- There is no `get_db_session`, `get_db`, or `get_session` dependency helper
  in `db/session.py`; only `SessionLocal()`.
- Auth dependencies are factory-based: `build_require_auth(...)` and
  `build_require_admin(...)`.
- `openlia_server.auth.deps.get_current_user` exists, but is a placeholder that
  always raises 401.
- Password hashing is under `openlia_server.services.auth.passwords`.
- `ReportRequest` is in `openlia.llm.runtime.messages`.
- `events.py` exposes `to_wire(...)`; it does not expose `serialize_sse`.

Impact:

Executing these plans as written will fail with import errors or route
dependency errors before reaching intended implementation logic.

Recommended fix:

Create a "Current Backend Contract" section in
`planning/implementation-plans/README.md` and update Phase 10-15 plans to use:

- `openlia_server.db.models.auth.User`
- `openlia_server.db.models.config.LLMModel`
- router factories that accept `db_session_factory` and `mode`
- `build_require_auth(...)` / `build_require_admin(...)`
- `openlia_server.services.auth.passwords.hash_password`
- `openlia.llm.runtime.messages.ReportRequest`
- `openlia.llm.runtime.events.to_wire(...)`

If simple FastAPI dependency helpers are desired, add them as a dedicated
compatibility task before Plan 10 rather than assuming they already exist.

### 4. High - Phase 11 Duplicates Existing Admin Routes

Status: open.

Affected plan:

- Plan 11 - Settings Page

Affected implementation files:

- `packages/server/src/openlia_server/routes/admin.py`
- `packages/server/src/openlia_server/app.py`

Plan expectation:

Plan 11 creates:

- `routes/admin_invites.py`
- `routes/admin_users.py`
- `routes/admin_password_reset_requests.py`
- `services/admin_invites.py`
- `services/admin_users.py`
- `services/admin_password_reset.py`

Observed implementation:

The backend already mounts an admin router in company mode:

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

Impact:

If Plan 11 adds the new routers as written, FastAPI will have duplicated route
paths with conflicting response shapes and status codes. Even if route order
makes one implementation "win", the codebase will carry two admin service
surfaces for the same operations.

Recommended fix:

Revise Plan 11 to reuse and extend `routes/admin.py` and existing
`services/auth/*` modules. Settings should add typed frontend clients for the
current `/admin/*` API or explicitly patch that one router, not create a
parallel admin stack.

### 5. High - UUID String IDs Drift To Integer IDs In Later Plans

Status: open.

Affected plans:

- Plan 11 - Settings Page
- Plan 12 - Shared Chat Components
- Plan 15 - Earnings Update

Observed implementation:

The shipped schema uses UUID strings for primary and foreign keys:

```python
class User:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

class SignupInvite:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

class ChatSession:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

class Report:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
```

Plan drift examples:

- Plan 11 DTOs use `id: int` for invites and users.
- Plan 11 services take `user_id: int`, `admin_id: int`, and `invite_id: int`.
- Plan 12 chat/repo services take `user_id: int`, `session_id: int`, and
  `report_id: int`.
- Plan 15 repeatedly imports `db.models.users.User` and uses older route/test
  fixture assumptions.

Impact:

Route validation, `db.get(...)`, path parameter types, and SQLAlchemy
relationships will be wrong. Tests will either fail immediately or build local
test-only factories that do not reflect production schema.

Recommended fix:

Update all Phase 11+ plan code blocks to use `str` IDs, UUID string generation,
and current model locations. Treat IDs as opaque strings at the API boundary.

### 6. Medium - Phase 12 Uses Old Chat Model Field Names

Status: open.

Affected plan:

- Plan 12 - Shared Chat Components

Affected implementation file:

- `packages/server/src/openlia_server/db/models/content.py`

Plan expectation:

Plan 12 service code uses:

```python
ChatSession(user_id=user_id, department=department, title=title, pinned=False)
...
stmt = stmt.where(ChatSession.archived_at.is_(None))
```

Observed implementation:

`ChatSession` fields are:

```python
is_pinned: Mapped[bool]
is_archived: Mapped[bool]
context: Mapped[dict | None]
```

There is no `pinned` column and no `archived_at` column.

Impact:

Phase 12 chat session CRUD will fail at model construction and query time.

Recommended fix:

Update Plan 12 to use `is_pinned` and `is_archived`. If archive timestamps are
required by the UI, add a new migration deliberately; do not assume the column.

### 7. Medium - Phase 7 Wizard Reset Conflicts With Phase 10 Wizard Shape

Status: open.

Affected plans:

- Plan 7 - CLI Surface
- Plan 10 - Setup Wizard

Affected implementation file:

- `packages/server/src/openlia_server/db/models/infrastructure.py`

Plan expectation:

Plan 10 reshapes `wizard_state.current_step` from integer to string step IDs
and adds `completed_steps` plus `active_session_token`.

Plan 7 still implements `openlia wizard reset` with:

```python
WizardState(... current_step=1 ...)
...
state.current_step = 1
```

Impact:

If Phase 7 executes before Phase 10, the CLI reset works only with the old
shape. After Phase 10 executes, the same CLI command writes an invalid
`current_step` type unless Phase 10 also patches Phase 7's CLI behavior.

Recommended fix:

Add an explicit Phase 10 task to update `openlia wizard reset`:

```python
state.current_step = "mode"
state.completed_steps = []
state.active_session_token = None
```

Also update Phase 7's forward-compatibility notes to warn that its reset shape
is superseded by Phase 10.

### 8. Medium - `config_store["wizard.completed"]` Type Is Inconsistent

Status: open.

Affected plan:

- Plan 10 - Setup Wizard

Affected implementation file:

- `packages/server/src/openlia_server/db/bootstrap.py`

Observed implementation:

Bootstrap seeds:

```python
"wizard.completed": False
```

Plan 10 status code reads:

```python
completed = (_load_config(db, "wizard.completed") or "").lower() == "true"
```

The plan tests sometimes seed `value="true"`.

Impact:

When the existing boolean seed is present, calling `.lower()` on a bool will
raise `AttributeError`. This blocks `/setup/status` on a normal bootstrapped DB.

Recommended fix:

Normalize config-store boolean handling:

```python
def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False
```

Then update tests to cover both the legacy/string value and the shipped boolean
seed.

### 9. Medium - Notification And Job Routes Still Use Placeholder Auth

Status: open.

Affected plans:

- Plan 8 - Frontend Shell
- Plan 12+ plans that rely on authenticated app shell behavior

Affected implementation files:

- `packages/server/src/openlia_server/auth/deps.py`
- `packages/server/src/openlia_server/routes/jobs.py`
- `packages/server/src/openlia_server/routes/notifications.py`

Observed implementation:

`routes/notifications.py` depends on `get_current_user`, which is a stub:

```python
def get_current_user() -> User:
    raise HTTPException(status_code=401, detail="Not authenticated")
```

Plan 8's Sidebar polls:

```ts
fetchJson<UnreadResponse>("/api/notifications/unread")
```

Impact:

Even after fixing the `/api` proxy, Sidebar notification polling will return
401 in real app wiring. Current tests override the dependency and do not prove
production behavior.

Recommended fix:

Convert `jobs_router` and `notifications_router` to router factories that bind
`build_require_auth(db_session_factory=factory, mode=mode)`, mirroring
`routes/auth.py`, `routes/admin.py`, and `routes/settings.py`.

### 10. Medium - Phase 11 Lists The Wrong LLM Admin Route Prefix

Status: open.

Affected plan:

- Plan 11 - Settings Page

Affected implementation file:

- `packages/server/src/openlia_server/routes/settings.py`

Plan expectation:

Plan 11 says Plan 4 LLM admin CRUD lives under `/settings/models/*`.

Observed implementation:

The current LLM admin router is mounted at:

```python
APIRouter(prefix="/settings/admin/llm", tags=["llm-admin"])
```

Impact:

Settings Models/Admin frontend clients will call the wrong endpoints if the
plan is executed as written.

Recommended fix:

Update Plan 11 to use `/settings/admin/llm/*` or add a compatibility router
intentionally. Do not leave both names implicit.

### 11. Medium - Plan 10 Assumes LLM Provider Service Functions That Do Not Exist

Status: open.

Affected plan:

- Plan 10 - Setup Wizard

Affected implementation file:

- `packages/server/src/openlia_server/services/llm_providers.py`

Plan expectation examples:

- `llm_svc.test_provider(...)`
- `llm_svc.clear_all_providers(db)`
- `llm_svc.add_model(...)`
- `llm_svc.list_data_provider_rows(db)`

Observed implementation:

The current service exposes provider/model CRUD such as:

- `create_provider(...)`
- `get_provider(...)`
- `list_providers(...)`
- `create_model(...)`
- `list_models_for_provider(...)`
- `set_user_preference(...)`

There is no `test_provider`, `clear_all_providers`, `add_model`, or
`list_data_provider_rows`.

Impact:

Setup Wizard provider/model tasks will fail unless the plan first adds those
service helpers or rewrites the wizard to use the existing CRUD APIs.

Recommended fix:

Revise Plan 10 to call current `llm_providers.py` functions, and keep data
provider interactions in `services/data_providers.py`.

### 12. Low - Plan 7 Is Internally Useful But Currently Unimplemented

Status: open.

Affected plan:

- Plan 7 - CLI Surface

Observed implementation:

`packages/server/src/openlia_server/cli.py` currently has only:

- root Typer app
- `serve`
- `main`

There is no `_cli_support.py`, no `admin`, no `wizard`, no `secrets`, and no
`maintenance` command yet.

Impact:

This is not a defect by itself because Plan 7 is still marked Draft. It matters
because Phase 8+ plans sometimes treat the CLI as an available alternative
seeding path.

Recommended fix:

Before using CLI commands in downstream smoke tests, either implement Phase 7 or
mark those smoke-test steps as conditional.

## Recommended Contract Normalization Before Execution

Before any Phase 7+ implementation begins, update the plans so they agree on
these contracts:

1. Frontend API calls use `/api/...`, and Vite rewrites `/api` away.
2. Backend route paths remain unprefixed unless a deliberate `/api` FastAPI
   mount is introduced.
3. Auth backend responses are flat today; frontend maps them to UI types.
4. User/admin state is `is_admin` in the DB, optionally mapped to frontend
   `"admin" | "user"`.
5. IDs are UUID strings, not integers.
6. Current model imports:
   - `openlia_server.db.models.auth.User`
   - `openlia_server.db.models.auth.SignupInvite`
   - `openlia_server.db.models.config.LLMModel`
   - `openlia_server.db.models.content.ChatSession`
   - `openlia_server.db.models.content.Report`
7. Current auth pattern is router factories using `build_require_auth` and
   `build_require_admin`.
8. Add real FastAPI DB dependency helpers only if a plan first implements and
   tests them.
9. `ReportRequest` lives at `openlia.llm.runtime.messages.ReportRequest`.
10. SSE wire conversion currently uses `openlia.llm.runtime.events.to_wire`.

## Suggested Next Work

1. Patch Phase 8 and Phase 9 first. They define the frontend API/auth contract
   all later UI plans consume.
2. Patch Phase 10-12 server snippets to current import paths, UUID IDs, auth
   factories, and model fields.
3. Patch Phase 13-15 to current runtime imports and SSE serialization before
   implementing department routes.
4. Next useful step: add the "Current Backend Contract" section to
   `planning/implementation-plans/README.md` so the plan fixes have one shared
   source of truth.

## Suggested Plan Patch Sequence

1. Start with the API boundary:
   - Update `frontend/vite.config.ts` assumptions in Plan 8 to require an
     `/api` rewrite, or explicitly decide to mount FastAPI under `/api`.
   - Update every Phase 8+ frontend API snippet to match that decision.

2. Normalize auth before writing more UI:
   - Update Phase 8/9 frontend auth clients to map the backend's flat
     `user_id`, `email`, `display_name`, `is_admin`, and
     `must_change_password` response into a frontend `AuthUser`.
   - Add `must_change_password` to `/auth/session` or explicitly default it in
     `AuthContext.refreshSession()`.

3. Add a "Current Backend Contract" section to
   `planning/implementation-plans/README.md` before editing individual plans.
   It should freeze:
   - Current model import paths.
   - UUID string IDs.
   - Router-factory auth pattern.
   - Current runtime import paths for `ReportRequest` and SSE event wiring.

4. Rewrite Phase 10-12 backend snippets against the current server shape:
   - Use `openlia_server.db.models.auth.User`.
   - Use `build_require_auth(...)` / `build_require_admin(...)`.
   - Treat all IDs as strings.
   - Use `is_pinned` / `is_archived` for chat sessions unless a migration adds
     new fields.

5. Rewrite Phase 13-15 runtime and department snippets after Phase 12 is
   normalized:
   - Import `ReportRequest` from `openlia.llm.runtime.messages`.
   - Use `openlia.llm.runtime.events.to_wire(...)` or add a real SSE helper
     first.
   - Avoid assuming `openlia_server.auth.current_user` exists unless a
     compatibility dependency is intentionally implemented.

6. Only after the plans are normalized, execute them task-by-task. Otherwise
   implementation workers will spend most of their time repairing stale plan
   scaffolding instead of building the intended phase behavior.
