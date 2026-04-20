# Phase 0-6 Implementation Quality Audit

Date: 2026-04-20

Scope: implementation phases 0 through 6, including Phase 1A and Phase 1B as the full Phase 1 database baseline.

Reviewed against:

- `planning/implementation-plans/2026-04-16-phase-0-scaffolding.md`
- `planning/implementation-plans/2026-04-16-phase-1a-database-baseline.md`
- `planning/implementation-plans/2026-04-17-phase-1b-database-dashboard-scheduler-notifications.md`
- `planning/implementation-plans/2026-04-16-phase-2-auth-and-secrets.md`
- `planning/implementation-plans/2026-04-16-phase-3-data-provider-adapter-system.md`
- `planning/implementation-plans/2026-04-16-phase-4-llm-provider-system.md`
- `planning/implementation-plans/2026-04-17-phase-5-llm-runtime.md`
- `planning/implementation-plans/2026-04-17-phase-6-background-task-scheduling.md`

Validation commands run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Results:

- Python tests: 581 passed, 6 warnings.
- Ruff check: passed.
- Ruff format check: 202 files already formatted.
- Frontend test: 1 passed.
- Frontend build: passed.

## Executive Summary

The Phase 0-6 implementation is broadly test-green and the main architectural spine is present. The database baseline, data provider core, LLM provider abstraction, runtime layer, and scheduler internals are substantially implemented.

However, "green tests" currently overstate production readiness. The highest-risk issues are not ordinary unit-test failures. They are plan-to-code drift and production wiring gaps:

1. Phase 6 scheduler routes are mounted in the real app but are wired to a placeholder auth dependency that always returns 401.
2. Phase 2 secret-key creation writes the key before tightening file permissions.
3. Phase 2 invite tokens are stored and listed in plaintext.
4. Phase 6 app lifespan reads `OPENLIA_DATABASE_URL`, while Phase 0/1A define and document `OPENLIA_DB_URL`.
5. Phase 5 advertises a bounded multi-round tool loop but breaks after one tool round.
6. Phase 4 LLM registry can raise a raw `RuntimeError` when an enabled model references a disabled provider.
7. Multiple HTTP route handlers create SQLAlchemy sessions without closing them.

The main quality conclusion: Phases 0, 1A, 1B, 3, and most of 4 are in good shape. Phases 2, 5, and 6 need targeted hardening before the implementation should be treated as production-ready.

## Severity Definitions

- High: security issue, user-facing route is unusable, or plan-critical behavior is missing.
- Medium: meaningful behavioral drift, operational fragility, or likely production failure under normal use.
- Low: cleanup, consistency, or maintainability issue that does not block current behavior.

## Findings

### 1. High - Phase 6 Scheduler Routes Are Not Wired To Real Auth

Status: open.

Affected files:

- `packages/server/src/openlia_server/auth/deps.py`
- `packages/server/src/openlia_server/routes/jobs.py`
- `packages/server/src/openlia_server/routes/notifications.py`
- `packages/server/src/openlia_server/app.py`
- `packages/server/tests/test_scheduler/test_routes_jobs.py`

Plan expectation:

Phase 6 Task 15 states that the scheduler HTTP routes all require an authenticated user from Plan 2. The routes are user-scoped:

- `GET /jobs/history`
- `POST /jobs/{run_id}/retry`
- `GET /notifications/unread`
- `POST /notifications/read`

Phase 2 already provides the real mode-aware auth dependency in `middleware/auth.py`. In personal mode, it resolves the synthetic `local` user. In company mode, it validates the session cookie.

Observed implementation:

`routes/jobs.py` and `routes/notifications.py` import `get_current_user` from `openlia_server.auth.deps`. That dependency is a placeholder:

```python
def get_current_user() -> User:
    raise HTTPException(status_code=401, detail="Not authenticated")
```

`app.py` mounts the jobs and notifications routers directly:

```python
app.include_router(jobs_router)
app.include_router(notifications_router)
```

There is no dependency override or router factory that binds those routes to `build_require_auth(...)`.

Why tests did not catch it:

The scheduler route tests construct a separate test app and override the placeholder dependency:

```python
app.dependency_overrides[get_current_user] = _fake_user
```

That proves the route handlers work when a user object is injected, but it does not prove the production `create_app()` wiring works.

Impact:

In the real app, the scheduler API is effectively unusable:

- Personal mode requests to `/jobs/history` and `/notifications/unread` return 401 instead of resolving `local`.
- Company mode requests with a valid `openlia_session` cookie still return 401 because the placeholder dependency never validates cookies.
- The Phase 6 claim that the cross-cutting API surfaces shipped is not true in production wiring.

Recommended fix:

Convert the jobs and notifications routers to factories, mirroring Phase 2 and Phase 3 patterns:

```python
def build_jobs_router(*, db_session_factory: Callable[[], DBSession], mode: str) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    ...
```

Then mount in `create_app()` as:

```python
app.include_router(build_jobs_router(db_session_factory=factory, mode=mode))
app.include_router(build_notifications_router(db_session_factory=factory, mode=mode))
```

Recommended regression tests:

- In personal mode, `create_app(db_session_factory=...)` plus seeded local user returns 200 from `/jobs/history`.
- In company mode, no cookie returns 401.
- In company mode, a valid `openlia_session` cookie returns 200.
- In company mode, another user's job run still returns 404 on retry.

### 2. High - Secret Key Creation Has A Permissions Race

Status: open.

Affected file:

- `packages/server/src/openlia_server/db/crypto.py`

Plan expectation:

Phase 2 requires AES-256-GCM key loading from either:

1. `OPENLIA_SECRET_KEY`
2. auto-created `~/.openlia/secret.key` with `0600` permissions

The acceptance criteria explicitly require a fresh run to create `secret.key` with `0600` and loose permissions to fail startup.

Observed implementation:

The file key is created like this:

```python
raw = secrets.token_bytes(KEY_LENGTH_BYTES)
key_path.write_bytes(base64.b64encode(raw))
key_path.chmod(KEY_FILE_MODE)
return raw
```

This writes the secret key before applying the restrictive mode.

Impact:

On systems with a permissive umask, the key can briefly exist with broader permissions before `chmod(0o600)` runs. Any process with access during that window can read the key. Because this key protects provider API keys at rest, exposure compromises encrypted credentials.

Recommended fix:

Use atomic creation with restrictive permissions before publication:

1. Ensure `~/.openlia/` exists with `0700`.
2. Write the key to a temp file in the same directory.
3. Apply `0600` to the temp file before or at creation.
4. Atomically replace the final path with `os.replace(tmp_path, key_path)`.
5. Clean up temp files on failure.

Sketch:

```python
tmp_path = key_path.with_name(f".{key_path.name}.{os.getpid()}.tmp")
fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    with os.fdopen(fd, "wb") as f:
        f.write(base64.b64encode(raw))
    os.replace(tmp_path, key_path)
finally:
    if tmp_path.exists():
        tmp_path.unlink()
```

Recommended regression tests:

- Patch `os.umask` or inspect mode immediately after creation to confirm the file is never created world-readable.
- Confirm existing keys with non-`0600` mode still raise `SecretKeyError`.
- Confirm concurrent first-load calls do not corrupt or partially write the key.

### 3. High - Invite Tokens Are Stored And Listed In Plaintext

Status: open.

Affected files:

- `packages/server/src/openlia_server/db/models/auth.py`
- `packages/server/src/openlia_server/services/auth/registration.py`
- `packages/server/src/openlia_server/routes/admin.py`
- `packages/server/src/openlia_server/db/migrations/versions/2026-04-18-1609_baseline.py`

Plan expectation:

Phase 2 introduces opaque tokens and says bearer tokens are compared to their SHA-256 hash stored in the DB. The specific test language strongly enforces this for sessions and password reset requests. The same token utility is described as covering "sessions, invites, and password-reset links."

Observed implementation:

`SignupInvite` has a plaintext `token` column:

```python
token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
```

Registration looks up the invite by plaintext token:

```python
select(SignupInvite).where(SignupInvite.token == invite_token)
```

The admin list endpoint returns all invite tokens:

```python
"token": r.token
```

Impact:

Any DB read or admin list response exposes reusable invite credentials. This is weaker than the session and password-reset token model and creates an avoidable credential disclosure surface. It also violates the spirit of the Phase 2 token architecture.

Recommended fix:

Migrate `signup_invites` from `token` to `token_hash`.

Behavior should be:

- Invite creation generates a raw token and stores only `hash_token(raw)`.
- The raw token is returned exactly once from `POST /admin/invites`.
- `GET /admin/invites` never returns raw token material.
- Registration hashes the provided invite token and looks up by `token_hash`.
- Existing plaintext invite rows need a migration strategy. Since this project is still early, either invalidate old invites or add a one-time migration that hashes existing values.

Recommended schema shape:

```python
token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
```

Recommended regression tests:

- Creating an invite returns a raw token once.
- The database row stores `token_hash`, not the raw token.
- Listing invites omits token material.
- Registering with the raw token succeeds.
- Registering with an unknown token fails.

### 4. Medium - App Lifespan Reads The Wrong Database Env Var

Status: open.

Affected files:

- `packages/server/src/openlia_server/app.py`
- `packages/server/src/openlia_server/db/bootstrap.py`
- `packages/server/tests/test_app_lifespan.py`

Plan expectation:

Phase 0 documents `OPENLIA_DB_URL`. Phase 1A implements `resolve_db_url()` from `OPENLIA_DB_URL`. The CLI bootstrap path uses this variable.

Observed implementation:

`bootstrap.py` reads:

```python
env = os.environ.get("OPENLIA_DB_URL")
```

`app.py` lifespan reads:

```python
db_url = os.environ.get("OPENLIA_DATABASE_URL")
```

The Phase 6 lifespan tests also use `OPENLIA_DATABASE_URL`, which locks in the drift.

Impact:

`openlia serve` currently works because CLI bootstrap runs before uvicorn and configures the DB using `OPENLIA_DB_URL`. But direct ASGI/factory deployments can diverge:

- A deployment following documented `OPENLIA_DB_URL` may not configure the intended DB in lifespan.
- Scheduler startup may use an already configured engine from earlier bootstrap in CLI mode, but not in direct app-factory mode.
- Test coverage validates the undocumented variable, not the planned variable.

Recommended fix:

Use one resolver everywhere. Best option:

```python
from openlia_server.db.bootstrap import resolve_db_url

db_url = resolve_db_url()
```

If backwards compatibility is desired, support both env vars explicitly:

1. `OPENLIA_DB_URL`
2. `OPENLIA_DATABASE_URL` as a deprecated alias
3. default path under `~/.openlia/openlia.db`

Recommended regression tests:

- `create_app()` with `OPENLIA_DB_URL=sqlite:///:memory:` configures the DB and scheduler.
- `OPENLIA_DATABASE_URL` either works as an alias or is no longer referenced.
- CLI bootstrap and app lifespan agree on the effective DB URL.

### 5. Medium - Runtime Tool Loop Stops After One Round

Status: open.

Affected files:

- `packages/core/src/openlia/llm/runtime/chat.py`
- `packages/core/src/openlia/llm/runtime/report.py`
- `packages/core/src/openlia/llm/runtime/tools.py`

Plan expectation:

Phase 5 describes a runtime tool loop that continues until the LLM returns no more tool calls, bounded to prevent runaway behavior. This matters for:

- multiple independent data calls
- sequential data calls where a second call depends on the first result
- `find_more_data`, which adds a new tool for use in a follow-up turn

Observed implementation:

Both `ChatRunner` and `ReportRunner` contain bounded loops:

```python
for _ in range(10) if tools else range(0):
```

But both break immediately after the first dispatch:

```python
tools = await self._tools.build(department_id, has_web_search=True)
break
```

Impact:

The runtime supports one tool-dispatch round, not a true tool loop.

Specific consequences:

- If the model asks for one tool, sees the result, and then needs another tool, it cannot do that in the same run.
- `find_more_data` can add a tool schema, but the model does not get a chance to call that new tool before final answer generation.
- The implementation is materially weaker than the Phase 5 plan and will limit downstream department quality.

Recommended fix:

Remove the unconditional `break`, but keep the bounded loop.

For chat:

1. Generate with current conversation and tools.
2. If no tool calls, stream final answer or use the response text depending on provider contract.
3. Emit tool start/result events.
4. Append tool results to conversation.
5. Rebuild tools.
6. Continue until no tool calls or max rounds reached.

For reports:

1. Run data-gathering generate call.
2. Dispatch tool calls.
3. Append tool results.
4. Rebuild tools.
5. Continue until no tool calls or max rounds reached.
6. Then enter structured writing phase.

Recommended regression tests:

- Provider returns tool call round 1, then tool call round 2, then no tool calls; dispatcher is invoked twice.
- `find_more_data` adds a new tool in round 1; provider calls it in round 2.
- Max round cap stops infinite tool-call loops cleanly with an error event or controlled fallback.

### 6. Medium - Disabled LLM Providers Can Crash Resolution

Status: open.

Affected files:

- `packages/server/src/openlia_server/services/llm_registry.py`
- `packages/core/src/openlia/llm/resolver.py`

Plan expectation:

Phase 4 builds a resolver that should select a usable model for a tier or raise `TierNotConfiguredError` when no usable model exists. Downstream Phase 5 runners catch `LLMProviderError` and emit in-stream error events.

Observed implementation:

`SQLModelRegistry.get_tier_default()` and `get_any_in_tier()` filter on `LLMModel.is_enabled`, but not on `LLMProvider.is_enabled`.

If the selected model belongs to a disabled provider, `_build_row()` raises:

```python
raise RuntimeError(f"llm_models.{model.id} references missing/disabled provider")
```

Impact:

This can bypass the planned error taxonomy. Runtime callers generally catch `LLMProviderError`, not arbitrary `RuntimeError`, so a disabled provider can produce an unhandled request failure instead of a clean `TierNotConfiguredError` or admin-actionable error event.

Recommended fix:

Prefer skipping unusable rows in registry selection:

- Join `LLMModel` to `LLMProvider`.
- Filter both `LLMModel.is_enabled` and `LLMProvider.is_enabled`.
- If no usable row exists, return `None` so `resolve()` can proceed to fallback or raise `TierNotConfiguredError`.

Also consider cascading behavior when disabling a provider:

- Either prevent disabling providers with enabled models, or
- automatically mark dependent models disabled.

Recommended regression tests:

- Enabled default model on disabled provider is skipped.
- Resolver falls back to another enabled provider in the same tier.
- If no enabled provider remains, `TierNotConfiguredError` is raised.
- `ChatRunner` and `ReportRunner` convert that error into `chat.error` / `report.error`.

### 7. Medium - HTTP Routes Leak SQLAlchemy Sessions

Status: resolved (2026-04-20, branch `fix/route-session-lifecycle`).

Resolution:

- Introduced `openlia_server.db.deps.make_session_dependency(factory)` —
  yields a session, commits on success, rolls back on exception, always
  closes. Unit-tested in `tests/test_db/test_deps.py`.
- Migrated every handler in `routes/auth.py`, `routes/admin.py`, and
  `routes/settings.py` (data-providers + LLM admin) to take
  `db: DBSession = Depends(session_dep)` instead of calling
  `db_session_factory()` directly.
- `middleware/auth.py`'s `require_auth` now wraps its factory call in
  `try/finally` so the per-request auth session closes on every path.
- Test fixtures that previously injected `lambda: db_session` now pass
  `session_mod.SessionLocal` so close() does not invalidate the shared
  fixture session.
- `ruff.toml` adds `flake8-bugbear.extend-immutable-calls` for FastAPI's
  `Depends`/`Query`/... so the idiomatic default-arg form lints clean.

Affected files:

- `packages/server/src/openlia_server/routes/auth.py`
- `packages/server/src/openlia_server/routes/admin.py`
- `packages/server/src/openlia_server/routes/settings.py`
- `packages/server/src/openlia_server/routes/jobs.py`
- `packages/server/src/openlia_server/routes/notifications.py`

Plan expectation:

The plans emphasize direct SQLAlchemy session usage, but route handlers still need clear transaction and lifecycle ownership. Phase 1A establishes `SessionLocal`; later plans call into service layers.

Observed implementation:

Many route handlers call:

```python
db = db_session_factory()
```

and never close the session.

Examples:

- `routes/auth.py` registration, login, logout, reset, change-password handlers.
- `routes/admin.py` invite, user, and password-reset management handlers.
- `routes/settings.py` data-provider and LLM-provider handlers.

Impact:

In tests, this is mostly hidden because the factory often returns a fixture-owned session. In production, unclosed sessions can leak connections and transaction state. With SQLite this may show up as locking behavior; with other SQLAlchemy-supported backends it can exhaust the connection pool.

Recommended fix:

Introduce a route-level dependency:

```python
def get_db() -> Iterator[DBSession]:
    with SessionLocal() as session:
        yield session
```

For router factories that receive a session factory:

```python
def session_dependency() -> Iterator[DBSession]:
    with db_session_factory() as session:
        yield session
```

Then inject sessions with `Depends(session_dependency)`.

Recommended regression tests:

- Use a session factory double that records `close()` calls.
- Exercise representative success and error paths.
- Confirm sessions close even when service methods raise.

## Phase-By-Phase Assessment

### Phase 0 - Workspace Scaffolding

Assessment: good.

Evidence:

- Python, frontend, lint, and build gates pass.
- The monorepo structure is present.
- The frontend remains intentionally minimal, which matches Phase 0 scope.

Residual risk:

- None material for Phase 0.

### Phase 1A - Database Baseline

Assessment: good.

Evidence:

- Engine/session/bootstrap/migration tests pass.
- `OPENLIA_DB_URL` is implemented in `bootstrap.resolve_db_url()`.
- Core auth/config/content/infrastructure tables are present.

Residual risk:

- App lifespan env-var drift was introduced later by Phase 6, not by Phase 1A itself.

### Phase 1B - Dashboard, Scheduler, Notifications Tables

Assessment: good.

Evidence:

- Dashboard and scheduler model tests pass.
- Migration tests validate the full 33-table schema.
- The 1B tables are available for Phase 6.

Residual risk:

- No major schema issue found in this pass.

### Phase 2 - Auth And Secrets

Assessment: mostly implemented, but security hardening required.

Strong areas:

- Argon2id password hashing.
- Session token hashing.
- Password reset token hashing.
- Login lockout state machine.
- Mode-aware `build_require_auth()` / `build_require_admin()`.
- Company-mode `/auth/*` and `/admin/*` route coverage.

Main gaps:

- Secret-key file creation race.
- Plaintext invite-token storage and listing.
- Route session lifecycle leaks.

### Phase 3 - Data Provider Adapter System

Assessment: good for the planned v1 adapter spine.

Strong areas:

- Adapter abstraction exists.
- EODHD adapter covers the planned initial capabilities.
- Manifest loader/checker exists.
- Deterministic provider resolution and auto-map service exist.
- Provider API keys use row-bound AES-GCM encryption.

Residual risk:

- `EODHDAdapter.__init__()` uses `assert entry.base_url is not None`. This is acceptable in tests but should eventually become a normal `ValueError` because Python can remove asserts under optimization.
- `category` and `mode` are accepted by `create_provider()` but not persisted to the current DB model. This is not a current breakage because adapter kind derives category and base URL derives mode, but it is worth revisiting before expanding providers.

### Phase 4 - LLM Provider System

Assessment: mostly good, with one resolver robustness issue.

Strong areas:

- Provider adapter set is broad and tested.
- Typed LLM request/response objects exist.
- Capability map and tier defaults exist.
- SQL-backed model registry bridges server config to core resolver.
- API-key encryption is applied to LLM providers.

Main gap:

- Disabled providers can still be selected through enabled model rows and cause `RuntimeError`.

### Phase 5 - LLM Runtime

Assessment: useful v1, but materially weaker than the plan around tool loops.

Strong areas:

- Prompt loading and slot validation exist.
- Chat/report/batch runners exist.
- SSE event taxonomy exists.
- Tool dispatcher supports parallel dispatch.
- Cancellation token support exists.
- Structured report generation exists.

Main gap:

- The planned bounded multi-round tool loop is implemented as a one-round dispatch.

### Phase 6 - Background Task Scheduling

Assessment: scheduler internals are strong; app integration needs correction.

Strong areas:

- Scheduler settings, registry, job services, notification services, recovery, payload protocols, executors, APScheduler wrapper, and route handlers all exist.
- Retry/backoff and notification insertion are covered.
- Lifespan integration has tests.
- End-to-end scheduler integration test exists.

Main gaps:

- Jobs/notifications routes are not usable through real `create_app()` auth wiring.
- Lifespan uses `OPENLIA_DATABASE_URL` instead of the planned `OPENLIA_DB_URL`.
- Route tests cover a hand-built app with dependency override, not the production app factory.

## Recommended Fix Order

1. Fix Phase 6 route auth wiring.
   - This turns the scheduler API from test-only to actually usable.

2. Fix Phase 2 security hardening.
   - Atomic secret-key creation.
   - Hashed invite tokens and no token material in invite lists.

3. Align DB env-var handling.
   - Use `resolve_db_url()` in app lifespan.
   - Update tests to use `OPENLIA_DB_URL`.

4. Restore Phase 5 multi-round tool loop.
   - Remove unconditional one-round `break`.
   - Add explicit max-round behavior.

5. Harden LLM registry provider selection.
   - Skip disabled providers.
   - Raise planned typed errors.

6. Normalize route session lifecycle.
   - Introduce session dependencies and close sessions on all paths.

## Additional Regression Test Checklist

Add tests that exercise the production app factory, not only isolated service or hand-built test apps:

- `create_app()` personal mode: `/jobs/history` returns 200 for seeded `local` user.
- `create_app()` company mode: valid cookie can access `/jobs/history`.
- `create_app()` company mode: no cookie gets 401.
- `create_app()` company mode: `/notifications/unread` works with valid cookie.
- `OPENLIA_DB_URL` controls app lifespan DB configuration.
- Secret key is atomically created with `0600`.
- Invite token raw value is returned only on creation and never stored.
- ChatRunner performs two sequential tool rounds.
- ReportRunner performs two sequential tool rounds before writing.
- Disabled LLM provider rows are skipped during tier resolution.
- Route sessions close on success and on error.

## Suggested Next Work

1. Create a short stabilization branch for Phase 2, Phase 5, and Phase 6
   hardening before starting new feature phases. The current green test suite
   does not cover the highest-risk production wiring and security issues.

2. Fix production app wiring first:
   - Convert jobs and notifications routes to router factories that use
     `build_require_auth(...)`.
   - Use `resolve_db_url()` / `OPENLIA_DB_URL` consistently in app lifespan.
   - Add production `create_app()` route tests for personal and company mode.

3. Fix credential and token handling next:
   - Make secret-key creation atomic with `0600` permissions before publication.
   - Stop storing invite tokens in plaintext.
   - Return raw invite tokens only once at creation time.

4. Then restore runtime behavior promised by the plans:
   - Implement bounded multi-round tool loops for chat and report runners.
   - Add tests for at least two sequential tool rounds.

5. Before expanding provider or department features, harden the LLM registry:
   - Skip disabled providers during model resolution.
   - Raise typed resolver errors instead of raw `RuntimeError`.

6. Keep the route session lifecycle work separate from feature work. Introduce
   a shared session dependency or context helper and migrate routes in small
   batches so regressions are easy to isolate.

7. Next useful step: add the "Current Backend Contract" section to
   `planning/implementation-plans/README.md` so the plan fixes have one shared
   source of truth.

## Current Quality Gate Snapshot

The implementation is currently green on the existing gate suite:

```text
581 passed, 6 warnings
ruff check passed
ruff format --check passed
frontend vitest passed
frontend build passed
```

Do not treat that as sufficient acceptance for Phases 2, 5, and 6 until the gaps above are fixed. The current suite proves many units work, but it misses important production wiring and security properties.
