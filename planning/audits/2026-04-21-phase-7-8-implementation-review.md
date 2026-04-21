# Phase 7-8 Implementation Review

Date: 2026-04-21

Scope: implemented Phase 7 CLI surface and Phase 8 frontend shell on `main`.

This review checks implementation quality, errors, consistency with previous
phases, and consistency with the implementation plans after the 2026-04-20
cross-plan contract normalization.

Reviewed against:

- `planning/implementation-plans/2026-04-17-phase-7-cli-surface.md`
- `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md`
- `planning/implementation-plans/README.md`
- `planning/specs/systems/cli-surface-design.md`
- `planning/specs/components/SideBarSpec.md`

Primary implementation references:

- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/_cli_support.py`
- `packages/server/src/openlia_server/db/models/infrastructure.py`
- `packages/server/src/openlia_server/routes/auth.py`
- `packages/server/src/openlia_server/services/auth/password_reset.py`
- `frontend/vite.config.ts`
- `frontend/src/api/auth.ts`
- `frontend/src/auth/AuthContext.tsx`
- `frontend/src/components/sidebar/Sidebar.tsx`
- `frontend/src/router/routes.tsx`

Validation commands run:

```bash
uv run pytest packages/server/tests/test_cli -q
npm --prefix frontend run test
npm --prefix frontend run build
```

Results:

- CLI tests: passed, `70 passed`.
- Frontend tests: failed before test execution because the local
  `frontend/node_modules` tree is missing `tailwindcss`.
- Frontend build: failed before Vite build because the local
  `frontend/node_modules` tree is missing `@types/node`.
- `frontend/package.json` and `frontend/package-lock.json` do list those
  dependencies, so the frontend verification failure appears to be an
  uninstalled local dependency state, not a lockfile defect.

## Executive Summary

Phase 7 is substantially implemented and its dedicated CLI test suite passes.
The main Phase 7 issues are contract drift: `wizard reset` still writes the
legacy integer wizard-state shape, and CLI password reset audit attribution is
not consistent with the plan's `metadata.source="cli"` rule.

Phase 8 is more fragile. The frontend shell compiles in source form, but two
backend integration contracts are wrong in the implementation:

1. The auth client expects the obsolete nested `{user: ...}` response shape
   instead of the backend's flat `{user_id, email, display_name, is_admin,
   must_change_password}` shape.
2. The Vite dev proxy does not strip `/api`, even though frontend clients call
   `/api/...` and backend routers are mounted without an `/api` prefix.

These two Phase 8 issues will break normal login/session bootstrapping in dev
and hide behind fetch-mocked tests because the tests also encode the stale
response shape.

## Severity Definitions

- High: user-facing flow is broken, frontend/backend integration fails, or a
  plan-critical contract is violated.
- Medium: meaningful behavioral drift, missing audit attribution, or likely
  rework when the next phase lands.
- Low: cleanup or consistency issue that does not directly block current
  behavior.

## Findings

### 1. High - Phase 8 Auth Client Uses Obsolete Nested User Payload

Status: open.

Affected files:

- `frontend/src/api/auth.ts`
- `frontend/src/api/auth.test.ts`
- `frontend/src/auth/AuthContext.test.tsx`
- `packages/server/src/openlia_server/routes/auth.py`

Plan and backend contract:

The Phase 8 audit normalization states that `GET /auth/session` and
`POST /auth/login` return a flat payload:

```json
{
  "user_id": "...",
  "email": "...",
  "display_name": "...",
  "is_admin": true,
  "must_change_password": false
}
```

Frontend code must map this at the API boundary:

```ts
{
  id: user_id,
  email,
  display_name,
  role: is_admin ? "admin" : "user"
}
```

Observed implementation:

`frontend/src/api/auth.ts` still expects:

```ts
interface SessionResponse {
  user: AuthUser;
}

export async function getSession(): Promise<AuthUser> {
  const resp = await fetchJson<SessionResponse>("/api/auth/session");
  return resp.user;
}
```

The backend returns the flat payload from `routes/auth.py`:

```python
return {
    "user_id": auth.user.id,
    "email": auth.user.email,
    "display_name": auth.user.display_name,
    "is_admin": auth.user.is_admin,
    "must_change_password": auth.must_change_password,
}
```

Impact:

A valid session response makes `getSession()` return `undefined`. The
`AuthProvider` then marks the app as `authenticated` with no usable user
object. Login has the same problem. Downstream Phase 9+ UI code will not be
able to rely on `user.id`, `display_name`, `role`, or `must_change_password`.

Why tests did not catch it:

The frontend tests mock the obsolete nested `{user: ...}` payload, so they
validate the wrong contract.

Recommended fix:

- Replace `SessionResponse` with the flat backend DTO.
- Add `display_name` and `must_change_password` to the frontend boundary type
  or explicitly carry `must_change_password` in login state for Phase 9.
- Default `must_change_password` to `false` for `/auth/session` if the backend
  keeps omitting it on refresh.
- Update all auth and AuthProvider tests to mock the flat backend payload.

### 2. High - Vite Proxy Does Not Strip `/api`

Status: open.

Affected file:

- `frontend/vite.config.ts`

Plan and cross-plan contract:

Frontend clients call `/api/...`. The Vite dev proxy must strip `/api` before
forwarding to FastAPI because backend routers are mounted at bare paths like
`/auth/session`, `/notifications/unread`, and `/settings/...`.

Observed implementation:

`frontend/vite.config.ts` currently configures:

```ts
proxy: {
  "/api": "http://localhost:8000",
},
```

Vite preserves the original path in this form, so `/api/auth/session` is
forwarded as `/api/auth/session`.

Impact:

In the dev server, frontend calls to `/api/auth/session`,
`/api/auth/login`, `/api/notifications/unread`, and later settings/department
routes will 404 against the backend's bare route prefixes.

Recommended fix:

Use the contract already documented in the implementation-plan README:

```ts
proxy: {
  "/api": {
    target: "http://localhost:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
},
```

Add a smoke test or explicit manual verification note for
`/api/auth/session -> /auth/session`.

### 3. High - `wizard reset` Still Writes Legacy Integer Wizard State

Status: open.

Affected files:

- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/db/models/infrastructure.py`
- `packages/server/tests/test_cli/test_cli_wizard.py`

Plan contract:

The Phase 7 audit normalization explicitly says:

```text
openlia wizard reset must write:
current_step="mode"
completed_steps=[]
active_session_token=None
```

The old `current_step=1` integer form is superseded by Plan 10.

Observed implementation:

`wizard reset` still creates and updates:

```python
WizardState(
    id=1,
    status="not_started",
    current_step=1,
    mode=None,
)
...
state.current_step = 1
```

The current `WizardState` model is also still Phase 1A shaped:

```python
current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
```

It has no `completed_steps` or `active_session_token` fields yet.

Impact:

When Plan 10 reshapes `wizard_state`, the Phase 7 CLI command will either fail
or write an invalid step value. It also will not clear a stale active wizard
session token, which can leave the setup wizard blocked after reset.

Recommended fix:

- Land the Plan 10 wizard-state migration and model reshape before relying on
  `wizard reset` as a recovery path.
- Patch `wizard reset` in the same work to write:

  ```python
  state.status = "not_started"
  state.current_step = "mode"
  state.completed_steps = []
  state.active_session_token = None
  state.step_data = {}
  ```

- Update `test_cli_wizard.py` and DB model tests to assert the normalized
  shape.

### 4. Medium - CLI Password Reset Audit Event Lacks `metadata.source="cli"`

Status: open.

Affected files:

- `packages/server/src/openlia_server/cli.py`
- `packages/server/src/openlia_server/services/auth/password_reset.py`
- `packages/server/tests/test_cli/test_cli_admin_users.py`

Plan contract:

Phase 7 requires every state-changing admin command to emit audit rows with:

```text
actor_user_id = NULL
metadata.source = "cli"
```

Observed implementation:

`admin reset-password` delegates directly to:

```python
password_reset_service.admin_direct_reset(
    db, user_id=user.id, new_password=password, admin_user_id=None
)
```

`admin_direct_reset()` logs:

```python
events.log_auth_event(
    db,
    event_type="password_reset_by_admin",
    user_id=user.id,
    actor_user_id=admin_user_id,
)
```

No metadata is attached, so there is no `source="cli"` on the CLI-originated
`password_reset_by_admin` event.

Impact:

Audit queries cannot distinguish CLI password resets from UI resets using the
shared source metadata convention. This is inconsistent with disable-user,
enable-user, revoke-sessions, invite lifecycle, and lockout commands that use
`log_cli_event`.

Recommended fix:

Either:

- Extend `admin_direct_reset()` to accept optional metadata and pass
  `{"source": "cli"}` from the CLI, or
- Keep the service UI-neutral and have the CLI write a separate
  `password_reset_by_admin` event through `log_cli_event` without duplicating
  service events.

Prefer the first option to avoid duplicate audit rows.

Recommended regression test:

Add a CLI test for `admin reset-password` that asserts exactly one
`password_reset_by_admin` row with `actor_user_id is None` and
`event_metadata["source"] == "cli"`.

### 5. Low - `log_cli_event` Allows Source Override Despite Guarantee

Status: open.

Affected files:

- `packages/server/src/openlia_server/_cli_support.py`
- `packages/server/tests/test_cli/test_cli_support.py`

Observed implementation:

The helper says it guarantees CLI source:

```python
"""Audit wrapper. Guarantees actor_user_id=None and metadata.source=cli."""
```

But it merges metadata in caller-wins order:

```python
merged: dict[str, Any] = {"source": "cli"}
if metadata:
    merged = {**merged, **metadata}
```

The test suite explicitly asserts that callers can override source with
`"script"`.

Impact:

Current CLI commands do not appear to pass a conflicting source, but the helper
does not enforce the invariant it documents and the plan requires. Future
commands can accidentally create non-CLI-attributed events through the CLI
audit wrapper.

Recommended fix:

Make the wrapper win last:

```python
merged = {**(metadata or {}), "source": "cli"}
```

Update the test to assert `source == "cli"` even when caller metadata contains
`source`.

## Additional Notes

- Phase 7 dedicated CLI tests passed, so the findings above are not broad CLI
  test failures. They are cross-plan contract and audit semantics issues.
- The frontend verification commands could not reach source-level test results
  because dependencies are declared but not installed in the local
  `node_modules` tree. Run `npm --prefix frontend install` before re-running
  frontend verification.
- The earlier `2026-04-20-phase-7-plus-plan-consistency-audit.md` described
  Phase 7 and 8 as mostly unimplemented at that time. This document supersedes
  that baseline for the now-present Phase 7/8 implementation review, but does
  not replace its broader Phase 9+ plan-consistency findings.

## Recommended Work Queue

1. Patch Phase 8 auth DTO mapping and tests to use the flat backend response.
2. Add the Vite `/api` rewrite and verify `/api/auth/session` reaches
   `/auth/session`.
3. Coordinate `wizard reset` with the Plan 10 wizard-state migration and update
   tests to assert the string-step shape.
4. Add CLI audit coverage for `reset-password`, then make the service or CLI
   attach `metadata.source="cli"` without duplicate audit rows.
5. Harden `log_cli_event` so callers cannot override `source="cli"`.
