# Phase 23 — Docker packaging, production build, and final acceptance

- **Plan number:** 23 (final)
- **Phase bucket:** Phase 7 (Ancillary pages + packaging)
- **Spec sources:** `planning/PLAN.md` §Deployment & §Installation; `planning/specs/pages/SetupWizardSpec.md` §Company mode
- **Depends on:** every prior plan (0–22). Ship-gate for v1.
- **Unblocks:** `v1.0.0` release tag.
- **Branch:** `feat/phase-23-docker-packaging-acceptance`

This plan ships the production-deployable artifacts: a multi-stage Docker image, PyPI wheel/sdist, FastAPI static-file serving (already partially wired — extended here), proxy-aware cookie/forwarded-header handling, three `deploy/` compose examples (Cloudflare Tunnel, Caddy, LAN-only), GHCR + PyPI release workflow, smoke tests that boot the container in both modes, and a final acceptance checklist that aggregates every cross-plan merge gate.

---

## Locked contracts (must not violate)

Re-read `planning/implementation-plans/README.md` before starting. The Plan 23 execution must respect:

1. **Contract #1 — HTTP prefixes.** Vite dev proxy strips `/api`. In **production**, FastAPI serves the static SPA from `/` and backend routers keep **bare prefixes** (`/auth`, `/reports`, `/departments/...`). Production reverse proxies (Caddy, Cloudflared) also strip `/api` before forwarding — the image must expose paths the same way the dev proxy does. Concretely: the production container accepts requests on `/api/...` from the browser AND on bare paths from TestClient; the `/api` prefix must therefore be handled **inside the image** (a small ASGI middleware strips `/api` before routing). This matches the dev proxy exactly and keeps browser-side code identical between `npm run dev` and the built bundle.
2. **Frontend dist location inside the image.** Mount at `OPENLIA_FRONTEND_DIST=/app/frontend/dist`; SPA fallback handler already lives in `app.py :: _mount_frontend` — do not re-implement.
3. **SPA fallback must not shadow routers.** The existing `_API_PREFIXES` tuple in `app.py` gates the fallback. If Plan 23 adds `/api` stripping middleware, the fallback's prefix check still runs on the post-strip path (i.e. still sees `auth`, `reports`, etc.). No change needed to `_API_PREFIXES`.
4. **No `planning/`, `tests/`, `.git/`, `node_modules/` inside the image.** `.dockerignore` enforces this; a task verifies via `docker run ... ls`.
5. **Scheduler startup must not block on missing providers.** The image ships with `OPENLIA_SCHEDULER_ENABLED=false` by default in both compose examples; users flip it on once providers are configured via the wizard.
6. **Secret-key bootstrap.** The image writes to `~/.openlia/secret.key` under the non-root user's home. Compose examples mount `/home/openlia/.openlia` as a named volume so the key survives container rebuilds.
7. **IDs are `str(uuid.uuid4())`.** Not relevant to packaging itself, but the smoke test for company-mode invite creation must receive UUID-36 ids back; assert length.
8. **Cross-plan merge gate.** Final task runs the full aggregate suite (`ruff check`, `ruff format --check`, `pytest`, `npm run lint`, `npm run build`, `npm test`, `docker build`, smoke tests) and updates the status table in `planning/implementation-plans/README.md` to mark Plan 23 Done.

---

## Pre-work: confirm the starting state

Before touching anything, the plan assumes these facts (verified 2026-04-23):

- `packages/server/src/openlia_server/app.py :: _mount_frontend` already reads `OPENLIA_FRONTEND_DIST`, mounts `/assets`, and registers a SPA fallback. Plan 23 extends it (adds `ProxyHeadersMiddleware`, adds `/api` stripping, bakes a default dist path) — does NOT rewrite.
- `packages/server/src/openlia_server/routes/auth.py :: _cookie_secure` already honors `OPENLIA_COOKIE_SECURE` with a sensible default (company mode → secure, personal mode → not secure). Plan 23 only adds an integration test for this wiring.
- `packages/server/pyproject.toml` already declares `[project.scripts] openlia = "openlia_server.cli:main"`. Plan 23 adds `[project.urls]`, classifiers, `readme`, and a long description.
- `.github/workflows/ci.yml` covers lint+test+build. Plan 23 adds a **separate** `release.yml` workflow — it does not modify `ci.yml`.
- No `Dockerfile`, `.dockerignore`, or `deploy/` directory exists yet. All new files.
- No PyPI publishing has happened yet — the release workflow must tolerate the first-ever publish (no `dist/` drift).

If any of those assumptions is false on the branch HEAD, stop and reconcile before proceeding.

---

## Task layout

Tasks are 2–5 minutes each. TDD where Python changes — test first, implementation second. For Dockerfile/compose/CI configs the pattern is: write file → build/lint/validate → commit. Exactly one commit per task. The task numbers drive the commit message prefix: `task-23-<N>:`.

Aggregate count: **48 tasks** in 9 groups.

- Group A (Tasks 1–5): Static-file serving + proxy headers — FastAPI side
- Group B (Tasks 6–10): Cookie/secure header test coverage
- Group C (Tasks 11–15): Dockerfile + `.dockerignore`
- Group D (Tasks 16–18): Frontend production build verification
- Group E (Tasks 19–23): `deploy/` compose examples
- Group F (Tasks 24–27): PyPI packaging metadata
- Group G (Tasks 28–31): GitHub Actions release workflow
- Group H (Tasks 32–39): Smoke tests (personal + company)
- Group I (Tasks 40–48): Documentation, CHANGELOG, final acceptance

---

## Group A — Static-file serving + proxy headers (FastAPI)

### Task 1 — Write failing test for `/api`-prefix stripping in production ASGI

TDD: production deployments (Caddy, Cloudflared, reverse proxies) forward `/api/...` requests from the browser directly to the container. The dev Vite proxy already strips `/api`. The production container must do the same so frontend code does not fork behavior between dev and prod.

Create `packages/server/tests/test_api_prefix_strip.py`:

```python
"""`/api` prefix stripping in production (mirror of Vite dev proxy)."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from openlia_server.app import create_app


def test_api_prefix_is_stripped_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    app = create_app()
    client = TestClient(app)

    bare = client.get("/healthz")
    prefixed = client.get("/api/healthz")

    assert bare.status_code == 200
    assert prefixed.status_code == 200
    assert bare.json() == prefixed.json()


def test_api_prefix_strip_leaves_non_api_paths_untouched(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    app = create_app()
    client = TestClient(app)

    # /healthz without the /api prefix still works
    r = client.get("/healthz")
    assert r.status_code == 200

    # /api-ish-but-not-api prefix (e.g. /apidoc) is not stripped
    r = client.get("/apidoc")
    assert r.status_code == 404  # just confirming we didn't eat the 'api' substring
```

Run:

```bash
uv run pytest packages/server/tests/test_api_prefix_strip.py -v
```

Expected: the `test_api_prefix_is_stripped_in_production` test fails with `404 Not Found` on `GET /api/healthz` (routers don't see the `/api` prefix today).

Commit: `task-23-1: add failing test for /api prefix stripping in production ASGI`

### Task 2 — Implement `/api` prefix stripping middleware

Add a small ASGI middleware to `packages/server/src/openlia_server/app.py`. Place it immediately below the existing `_is_loopback_request` helper (around line 123):

```python
class _StripApiPrefixMiddleware:
    """Strip a leading `/api` segment from incoming HTTP paths.

    Mirrors the Vite dev proxy (`rewrite: (p) => p.replace(/^\/api/, "")`)
    so the built SPA can call `/api/...` in production and dev without
    branching on environment. Non-HTTP scopes (websocket, lifespan) pass
    through unchanged.
    """

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            raw_path = scope.get("raw_path")
            if path == "/api" or path.startswith("/api/"):
                new_path = path[4:] or "/"
                scope = dict(scope)
                scope["path"] = new_path
                if raw_path is not None:
                    # raw_path is bytes; slice off b"/api" if present.
                    if raw_path.startswith(b"/api/") or raw_path == b"/api":
                        scope["raw_path"] = raw_path[4:] or b"/"
        await self._app(scope, receive, send)
```

And register it as the outermost middleware inside `create_app`, immediately after the `FastAPI(...)` construction and before any `app.include_router(...)` call:

```python
    app.add_middleware(_StripApiPrefixMiddleware)
```

Run:

```bash
uv run pytest packages/server/tests/test_api_prefix_strip.py -v
```

Expected: both tests pass.

Commit: `task-23-2: strip /api prefix in production ASGI (mirror Vite dev proxy)`

### Task 3 — Write failing test for `OPENLIA_TRUST_PROXY_HEADERS` wiring

Plan 23 wires uvicorn's `ProxyHeadersMiddleware` behind an env flag so Cloudflare Tunnel and Caddy can send `X-Forwarded-For`/`X-Forwarded-Proto` and FastAPI sees the real client IP + scheme.

Create `packages/server/tests/test_trust_proxy_headers.py`:

```python
"""OPENLIA_TRUST_PROXY_HEADERS wiring for reverse-proxy deployments."""
from __future__ import annotations

from fastapi.testclient import TestClient

from openlia_server.app import create_app


def test_forwarded_headers_ignored_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.delenv("OPENLIA_TRUST_PROXY_HEADERS", raising=False)

    app = create_app()
    client = TestClient(app)

    r = client.get(
        "/_debug/client_host",
        headers={
            "X-Forwarded-For": "203.0.113.42",
            "X-Forwarded-Proto": "https",
        },
    )
    assert r.status_code == 200
    # Without trust flag, we see the raw client, not the X-Forwarded-For value.
    assert r.json()["host"] != "203.0.113.42"


def test_forwarded_headers_honored_when_flag_set(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.setenv("OPENLIA_TRUST_PROXY_HEADERS", "true")

    app = create_app()
    client = TestClient(app)

    r = client.get(
        "/_debug/client_host",
        headers={
            "X-Forwarded-For": "203.0.113.42",
            "X-Forwarded-Proto": "https",
        },
    )
    assert r.status_code == 200
    assert r.json()["host"] == "203.0.113.42"
    assert r.json()["scheme"] == "https"
```

The tests need a tiny debug route exposing `request.client.host` and `request.url.scheme`. Add it behind an env gate in Task 4 — for now, run the failing test:

```bash
uv run pytest packages/server/tests/test_trust_proxy_headers.py -v
```

Expected: all three tests fail (route missing + middleware not wired).

Commit: `task-23-3: add failing tests for OPENLIA_TRUST_PROXY_HEADERS wiring`

### Task 4 — Wire `ProxyHeadersMiddleware` + debug client-host route

In `packages/server/src/openlia_server/app.py`:

1. Add at top: `from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware`.
2. Inside `create_app`, immediately after adding `_StripApiPrefixMiddleware`:

```python
    if os.environ.get("OPENLIA_TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes"):
        # Accept X-Forwarded-For / X-Forwarded-Proto from any upstream. The
        # compose examples put OpenLIA behind a TLS-terminating proxy on the
        # same docker network, so forwarded_allow_ips="*" is correct there.
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
```

3. Register the debug route immediately after the existing `/health` route:

```python
    @app.get("/_debug/client_host", include_in_schema=False)
    def _debug_client_host(request: Request) -> dict[str, str | None]:
        host = request.client.host if request.client else None
        return {"host": host, "scheme": request.url.scheme}
```

Run:

```bash
uv run pytest packages/server/tests/test_trust_proxy_headers.py -v
```

Expected: all three tests pass.

Commit: `task-23-4: wire ProxyHeadersMiddleware behind OPENLIA_TRUST_PROXY_HEADERS`

### Task 5 — Bake default `OPENLIA_FRONTEND_DIST` for the Docker image

The image will copy the built frontend to `/app/frontend/dist`. If the env var is unset, the existing `_mount_frontend` function exits early. Change behavior so that the image's default path auto-activates when the directory exists:

In `packages/server/src/openlia_server/app.py`, modify `_mount_frontend` (around line 316) — add a default-path fallback:

```python
def _mount_frontend(app: FastAPI) -> None:
    """Serve `frontend/dist` with SPA fallback when configured.

    Resolution order:
      1. OPENLIA_FRONTEND_DIST env var (wins if set, even if the path is
         missing — makes misconfiguration loud).
      2. /app/frontend/dist (Docker image default).
      3. <repo>/frontend/dist (local `npm run build` for manual testing).

    Skips silently if no candidate resolves to a directory containing
    index.html, so dev servers and tests don't need a built bundle.
    """
    candidates: list[str] = []
    env_dist = os.environ.get("OPENLIA_FRONTEND_DIST")
    if env_dist:
        candidates.append(env_dist)
    else:
        candidates.append("/app/frontend/dist")
        here = os.path.dirname(os.path.abspath(__file__))
        repo_dist = os.path.normpath(os.path.join(here, "..", "..", "..", "..", "..", "frontend", "dist"))
        candidates.append(repo_dist)

    for candidate in candidates:
        dist_dir = os.path.abspath(candidate)
        if not os.path.isdir(dist_dir):
            continue
        index_html = os.path.join(dist_dir, "index.html")
        if not os.path.isfile(index_html):
            continue
        # Match existing body: mount /assets, register SPA fallback.
        assets_dir = os.path.join(dist_dir, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            head = full_path.split("/", 1)[0]
            if head in _API_PREFIXES:
                raise HTTPException(status_code=404)
            candidate_file = os.path.normpath(os.path.join(dist_dir, full_path))
            if full_path and candidate_file.startswith(dist_dir + os.sep) and os.path.isfile(candidate_file):
                return FileResponse(candidate_file)
            return FileResponse(index_html)

        return  # first matching candidate wins
```

Add a quick test at `packages/server/tests/test_frontend_mount.py`:

```python
"""Static frontend mount — default-path resolution."""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from openlia_server.app import create_app


def _write_dist(root) -> str:
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html><body>SPA</body></html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hello');")
    return str(dist)


def test_frontend_mount_from_env_var(monkeypatch, tmp_path):
    dist = _write_dist(tmp_path)
    monkeypatch.setenv("OPENLIA_FRONTEND_DIST", dist)
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")

    client = TestClient(create_app())

    r = client.get("/")
    assert r.status_code == 200
    assert "SPA" in r.text

    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "hello" in r.text


def test_frontend_mount_skips_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENLIA_FRONTEND_DIST", raising=False)
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")

    client = TestClient(create_app())
    # No mount — /healthz still responds, / returns 404.
    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 404
```

Run:

```bash
uv run pytest packages/server/tests/test_frontend_mount.py -v
```

Expected: both tests pass.

Commit: `task-23-5: add default /app/frontend/dist resolution + mount tests`

---

## Group B — Cookie/secure header integration coverage

### Task 6 — Test `OPENLIA_COOKIE_SECURE=true` forces Secure flag in company mode

Create `packages/server/tests/test_cookie_secure.py`:

```python
"""OPENLIA_COOKIE_SECURE cookie-flag wiring for reverse-proxy TLS."""
from __future__ import annotations

from fastapi.testclient import TestClient

from openlia_server.app import create_app
from openlia_server.db.session import SessionLocal
from openlia_server.db.models.auth import User, SignupPolicy
from openlia_server.services.auth.passwords import hash_password


def _seed_user(email: str, password: str) -> str:
    with SessionLocal() as s:
        s.add(SignupPolicy(id="default", require_invite=True))
        user = User(
            id="u-" + email.split("@")[0],
            email=email,
            display_name="Test",
            password_hash=hash_password(password),
            is_admin=False,
            must_change_password=False,
        )
        s.add(user)
        s.commit()
        return user.id


def test_cookie_secure_default_in_personal_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.delenv("OPENLIA_COOKIE_SECURE", raising=False)

    app = create_app()
    client = TestClient(app)
    # Personal mode has no auth router; no cookie to inspect.
    # Just verify the app still boots.
    assert client.get("/healthz").status_code == 200


def test_cookie_secure_on_in_company_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")
    monkeypatch.delenv("OPENLIA_COOKIE_SECURE", raising=False)

    app = create_app()
    _seed_user("a@example.com", "password-strong-1!")

    client = TestClient(app)
    r = client.post(
        "/auth/login",
        json={"email": "a@example.com", "password": "password-strong-1!"},
    )
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert "Secure" in set_cookie, set_cookie


def test_cookie_secure_override_off(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")

    app = create_app()
    _seed_user("b@example.com", "password-strong-1!")
    client = TestClient(app)

    r = client.post(
        "/auth/login",
        json={"email": "b@example.com", "password": "password-strong-1!"},
    )
    assert r.status_code == 200
    assert "Secure" not in r.headers.get("set-cookie", "")
```

Run:

```bash
uv run pytest packages/server/tests/test_cookie_secure.py -v
```

Expected: all three tests pass as-is (wiring already lives in `routes/auth.py :: _cookie_secure`). If any fail, stop — the existing code has drifted and needs a separate fix before Plan 23 continues.

Commit: `task-23-6: add integration coverage for OPENLIA_COOKIE_SECURE wiring`

### Task 7 — Document cookie/proxy env contract in `app.py` docstring

Add a module-level docstring section to `packages/server/src/openlia_server/app.py` (replacing the terse `"""FastAPI application factory."""` header):

```python
"""FastAPI application factory.

Environment contract (production-relevant subset):

    OPENLIA_MODE               personal | company (default: personal)
    OPENLIA_DB_URL             SQLAlchemy URL; defaults to ~/.openlia/openlia.db
    OPENLIA_FRONTEND_DIST      Absolute path to built SPA. Resolution order:
                                 1. this env var
                                 2. /app/frontend/dist (Docker default)
                                 3. <repo>/frontend/dist
    OPENLIA_TRUST_PROXY_HEADERS  "true" to honor X-Forwarded-For / X-Forwarded-Proto
                                 (set when OpenLIA runs behind Cloudflare Tunnel,
                                 Caddy, or any TLS-terminating proxy).
    OPENLIA_COOKIE_SECURE       "true" forces Secure flag on session cookies;
                                 defaults to true when OPENLIA_MODE=company,
                                 false otherwise.
    OPENLIA_SCHEDULER_ENABLED   "true" to run APScheduler jobs; default false.
    OPENLIA_SECRET_KEY          32-byte base64 AES-256-GCM key; if unset, the
                                 server reads/writes ~/.openlia/secret.key (0600).

The `/api/...` prefix from the dev Vite proxy is also stripped at runtime by
`_StripApiPrefixMiddleware` so the same built bundle works locally and in
production (Caddy, Cloudflare Tunnel) without per-environment rewrites.
"""
```

No code change — docstring only. Run `uv run ruff format --check .` to confirm.

Commit: `task-23-7: document production env contract in app.py`

### Task 8 — Assert proxy headers + cookie flag co-exist cleanly

Create `packages/server/tests/test_proxy_and_cookie_integration.py`:

```python
"""Smoke test the full reverse-proxy deployment posture."""
from __future__ import annotations

from fastapi.testclient import TestClient

from openlia_server.app import create_app
from openlia_server.db.session import SessionLocal
from openlia_server.db.models.auth import User, SignupPolicy
from openlia_server.services.auth.passwords import hash_password


def test_company_mode_behind_tls_proxy(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "true")
    monkeypatch.setenv("OPENLIA_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/x.db")

    app = create_app()
    with SessionLocal() as s:
        s.add(SignupPolicy(id="default", require_invite=True))
        s.add(
            User(
                id="u-proxy",
                email="p@example.com",
                display_name="Proxy",
                password_hash=hash_password("password-strong-1!"),
                is_admin=False,
                must_change_password=False,
            )
        )
        s.commit()

    client = TestClient(app)
    r = client.post(
        "/api/auth/login",  # /api prefix — strip middleware must handle it
        json={"email": "p@example.com", "password": "password-strong-1!"},
        headers={
            "X-Forwarded-For": "198.51.100.17",
            "X-Forwarded-Proto": "https",
        },
    )
    assert r.status_code == 200
    sc = r.headers.get("set-cookie", "")
    assert "Secure" in sc
    assert "HttpOnly" in sc
```

Run:

```bash
uv run pytest packages/server/tests/test_proxy_and_cookie_integration.py -v
```

Expected: pass.

Commit: `task-23-8: integration test for /api strip + proxy headers + secure cookie`

### Task 9 — Snapshot the production env posture in a YAML fixture

Create `packages/server/tests/fixtures/production_env.yaml`:

```yaml
# Canonical production env var snapshot — used by smoke tests and by
# deploy/* compose examples. Keep in sync with docstring in app.py.
OPENLIA_MODE: company
OPENLIA_DB_URL: sqlite:////home/openlia/.openlia/openlia.db
OPENLIA_FRONTEND_DIST: /app/frontend/dist
OPENLIA_TRUST_PROXY_HEADERS: "true"
OPENLIA_COOKIE_SECURE: "true"
OPENLIA_SCHEDULER_ENABLED: "false"
```

Add a trivial test `packages/server/tests/test_production_env_snapshot.py` that loads the YAML and asserts key set:

```python
from pathlib import Path
import yaml


def test_production_env_snapshot_has_required_keys():
    path = Path(__file__).parent / "fixtures" / "production_env.yaml"
    data = yaml.safe_load(path.read_text())
    required = {
        "OPENLIA_MODE",
        "OPENLIA_DB_URL",
        "OPENLIA_FRONTEND_DIST",
        "OPENLIA_TRUST_PROXY_HEADERS",
        "OPENLIA_COOKIE_SECURE",
        "OPENLIA_SCHEDULER_ENABLED",
    }
    assert required.issubset(set(data.keys()))
```

Run `uv run pytest packages/server/tests/test_production_env_snapshot.py -v`.

Commit: `task-23-9: snapshot canonical production env posture`

### Task 10 — Full aggregate sanity run

Run the aggregate Python suite to confirm Group A + B changes haven't broken anything:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Expected: zero lint errors, zero format errors, all tests pass.

No file change. No commit (dry gate before moving to Docker).

---

## Group C — Dockerfile + `.dockerignore`

### Task 11 — Write `.dockerignore`

Create `/Users/tkchang/Projects/OpenLIA/.dockerignore`:

```
# Version control
.git
.gitignore
.gitattributes

# Python build artifacts
**/__pycache__
**/*.pyc
**/*.pyo
**/*.pyd
**/.pytest_cache
**/.ruff_cache
**/.mypy_cache
**/*.egg-info
dist/
build/
.venv/
.env
.env.*

# Test trees
**/tests/
packages/*/tests/
tests/

# Frontend local artifacts
frontend/node_modules
frontend/dist
frontend/.vite
frontend/coverage

# Planning & docs that ship separately
planning/
docs/
*.md
!README.md
!CHANGELOG.md

# Editor/OS cruft
.idea/
.vscode/
.DS_Store
Thumbs.db

# Local SQLite databases + secrets
*.db
*.sqlite*
*.key
~/.openlia/
```

Commit: `task-23-11: add .dockerignore excluding planning, tests, node_modules, local dbs`

### Task 12 — Dockerfile Stage 1 (frontend build)

Create `/Users/tkchang/Projects/OpenLIA/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

# ---------- Stage 1: frontend build ----------
FROM node:20-bookworm-slim AS frontend-build

WORKDIR /build/frontend

# Install dependencies first — maximum layer cache reuse.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Now bring in the source and build.
COPY frontend/ ./
RUN npm run build

# Sanity check: index.html must exist.
RUN test -f dist/index.html

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# System deps: we need curl for healthcheck, ca-certificates for TLS,
# fonts + chromium deps for playwright's PDF export (Plan 13). Keep the
# list minimal — anything beyond this gets questioned in review.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        fonts-liberation \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libasound2 \
        libpangocairo-1.0-0 \
        libpango-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user + home dir for ~/.openlia.
RUN useradd --create-home --shell /bin/bash --uid 1000 openlia

# Install uv (Astral).
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

# Layer cache: copy only pyproject.toml + lockfiles first.
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/server/pyproject.toml packages/server/pyproject.toml

# Sync workspace deps (no dev, all members). This builds a .venv under /app/.venv.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv sync --frozen --no-dev --all-packages --no-install-project

# Now copy the actual source and re-sync to install the local workspace packages.
COPY packages/ packages/
RUN uv sync --frozen --no-dev --all-packages

# Install Playwright's Chromium into the image. Run as root so the browser
# lives under /root/.cache, but point the non-root user at the same path
# via PLAYWRIGHT_BROWSERS_PATH.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN uv run playwright install --with-deps chromium \
    && chown -R openlia:openlia /opt/playwright || true

# Copy the built frontend from Stage 1.
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

# Hand over the working tree + venv to the non-root user.
RUN chown -R openlia:openlia /app

USER openlia
WORKDIR /app

# Runtime defaults — override via env or compose.
ENV OPENLIA_MODE=personal \
    OPENLIA_FRONTEND_DIST=/app/frontend/dist \
    OPENLIA_DB_URL=sqlite:////home/openlia/.openlia/openlia.db \
    OPENLIA_SCHEDULER_ENABLED=false \
    PATH="/app/.venv/bin:${PATH}"

# Ensure ~/.openlia exists so the secret-key bootstrap + SQLite can write.
RUN mkdir -p /home/openlia/.openlia && chmod 700 /home/openlia/.openlia

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["openlia"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
```

No build yet — the next task builds it.

Commit: `task-23-12: add multi-stage Dockerfile (frontend build -> python runtime)`

### Task 13 — Build the image locally

```bash
cd /Users/tkchang/Projects/OpenLIA
docker build -t openlia:dev .
```

Expected: build succeeds. The frontend stage runs `npm ci && npm run build` and produces `dist/index.html`; the runtime stage syncs the uv workspace and installs Chromium. Total image size should land in the 800 MB – 1.3 GB range — Chromium dominates.

If the build fails:
- Missing `uv.lock` — run `uv sync --all-packages` at repo root first, commit the lockfile, retry.
- Playwright install fails — re-check `apt-get install` list against `mcr.microsoft.com/playwright`'s official deps list.
- Frontend build fails — run `npm run build` locally and fix before retrying the image.

No commit for the build itself — it's a verification step. If the build surfaced a `Dockerfile` bug, fix the Dockerfile and commit as `task-23-13: fix Dockerfile <specific-issue>` (anything in-repo, not the build log).

### Task 14 — Smoke-run the image: personal mode

```bash
docker run --rm -d --name openlia-smoke -p 8000:8000 openlia:dev
sleep 5
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/api/healthz
curl -fsSI http://127.0.0.1:8000/ | head -1
docker logs openlia-smoke | tail -20
docker stop openlia-smoke
```

Expected:
- `GET /healthz` → `{"status":"ok","mode":"personal"}`
- `GET /api/healthz` → same (confirms `/api` strip middleware in the image)
- `GET /` → `HTTP/1.1 200 OK` with SPA HTML
- Logs show `Uvicorn running on http://0.0.0.0:8000`

No commit. If any assertion fails, fix and re-run Task 13 first.

### Task 15 — Verify `planning/`, `tests/`, `node_modules/` are absent from the image

```bash
docker run --rm openlia:dev ls /app
docker run --rm openlia:dev sh -c 'ls /app/packages/server/tests 2>/dev/null || echo MISSING'
docker run --rm openlia:dev sh -c 'ls /app/planning 2>/dev/null || echo MISSING'
docker run --rm openlia:dev sh -c 'ls /app/frontend/node_modules 2>/dev/null || echo MISSING'
docker run --rm openlia:dev sh -c 'ls /app/frontend/dist/index.html'
```

Expected: `MISSING` for tests, planning, node_modules; success for `/app/frontend/dist/index.html`.

If any of those unexpectedly contains content, update `.dockerignore` and re-run Task 13.

No commit unless `.dockerignore` needed a fix. If so: `task-23-15: tighten .dockerignore to exclude <path>`.

---

## Group D — Frontend production build verification

### Task 16 — Pin the production API base-URL strategy

The frontend uses relative `/api/...` paths (verified against `frontend/src/api/*`). In production the same-origin SPA + API posture keeps this working. Add a one-line smoke test to lock the assumption.

Create `frontend/src/api/__tests__/prodBase.test.ts`:

```typescript
import { describe, it, expect } from "vitest";

// The codebase must never hard-code an absolute API URL — the browser always
// hits the same origin, and /api is either proxied (dev) or stripped by
// _StripApiPrefixMiddleware (prod). Anything starting with http:// or https://
// is a bug waiting to happen.
import fs from "node:fs";
import path from "node:path";

function walk(dir: string, out: string[] = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(entry.name)) out.push(p);
  }
  return out;
}

describe("frontend API base URL", () => {
  it("never hard-codes a remote host for /api paths", () => {
    const apiDir = path.resolve(__dirname, "..");
    const files = walk(apiDir).filter((f) => !f.includes("__tests__"));
    const offenders: string[] = [];
    for (const f of files) {
      const body = fs.readFileSync(f, "utf-8");
      if (/['"`](https?:\/\/[^'"`]+)\/api/.test(body)) {
        offenders.push(f);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});
```

Run:

```bash
cd frontend && npm test -- --run prodBase
```

Expected: pass.

Commit: `task-23-16: lock frontend /api paths to same-origin only`

### Task 17 — Produce a reference production bundle

```bash
cd frontend
npm ci
npm run build
ls -lh dist/index.html
du -sh dist/
```

Expected: `index.html` exists; `dist/` is ~5–15 MB (heavy on the PDF.js worker + echarts). Record the size in the commit message for tracking.

No code change — verification only. If the build warns about chunks > 500 KB, that is expected and tolerated; not addressed in this plan.

No commit needed. Move on.

### Task 18 — Add a `frontend` build-smoke vitest

Create `frontend/src/api/__tests__/buildOutput.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

// Skips when dist/ doesn't exist (CI builds separately).
const dist = path.resolve(__dirname, "../../../../frontend/dist");
const indexHtml = path.join(dist, "index.html");

describe("frontend production build", () => {
  it.skipIf(!fs.existsSync(indexHtml))(
    "index.html references hashed asset bundles",
    () => {
      const html = fs.readFileSync(indexHtml, "utf-8");
      // Vite output always hashes main chunks: /assets/index-<hash>.js
      expect(html).toMatch(/\/assets\/index-[\w-]+\.js/);
      expect(html).toMatch(/<div id="root">/);
    },
  );
});
```

Run `cd frontend && npm test -- --run buildOutput` — passes (skips if `dist/` missing, i.e. CI dev-time).

Commit: `task-23-18: add smoke vitest for the production build shape`

---

## Group E — `deploy/` compose examples

### Task 19 — `deploy/cloudflare-tunnel/docker-compose.yml`

Create the file:

```yaml
# Production deployment: OpenLIA behind Cloudflare Tunnel.
#
# Prereq: create a tunnel in your Cloudflare dashboard, generate a token,
# and expose your desired hostname (e.g. openlia.example.com) pointing at
# http://openlia:8000 on this docker network.
#
# Start:
#   OPENLIA_IMAGE=ghcr.io/your-org/openlia:latest \
#   TUNNEL_TOKEN=eyJhIjoi... \
#   docker compose up -d

services:
  openlia:
    image: ${OPENLIA_IMAGE:-ghcr.io/openlia/openlia:latest}
    restart: unless-stopped
    environment:
      OPENLIA_MODE: company
      OPENLIA_TRUST_PROXY_HEADERS: "true"
      OPENLIA_COOKIE_SECURE: "true"
      OPENLIA_DB_URL: sqlite:////home/openlia/.openlia/openlia.db
      OPENLIA_SCHEDULER_ENABLED: "true"
      OPENLIA_SECRET_KEY: ${OPENLIA_SECRET_KEY:-}
    volumes:
      - openlia_data:/home/openlia/.openlia
    # No published port — tunnel sidecar reaches it over the docker network.
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${TUNNEL_TOKEN:?set TUNNEL_TOKEN to your Cloudflare Tunnel credentials}
    depends_on:
      openlia:
        condition: service_healthy

volumes:
  openlia_data:
```

Validate syntax:

```bash
docker compose -f deploy/cloudflare-tunnel/docker-compose.yml config >/dev/null
```

Expected: no errors. (Does not start the stack.)

Commit: `task-23-19: add deploy/cloudflare-tunnel compose example`

### Task 20 — `deploy/caddy/docker-compose.yml` + `Caddyfile`

Create `deploy/caddy/docker-compose.yml`:

```yaml
# Production deployment: OpenLIA behind Caddy (automatic TLS via Let's
# Encrypt). Point DNS at this host first, then:
#
#   OPENLIA_IMAGE=ghcr.io/openlia/openlia:latest \
#   OPENLIA_HOSTNAME=openlia.example.com \
#   docker compose up -d
#
# Caddy obtains+renews the cert on its own. Ports 80/443 must be reachable
# from the internet for the ACME HTTP-01 challenge to work.

services:
  openlia:
    image: ${OPENLIA_IMAGE:-ghcr.io/openlia/openlia:latest}
    restart: unless-stopped
    environment:
      OPENLIA_MODE: company
      OPENLIA_TRUST_PROXY_HEADERS: "true"
      OPENLIA_COOKIE_SECURE: "true"
      OPENLIA_DB_URL: sqlite:////home/openlia/.openlia/openlia.db
      OPENLIA_SCHEDULER_ENABLED: "true"
      OPENLIA_SECRET_KEY: ${OPENLIA_SECRET_KEY:-}
    volumes:
      - openlia_data:/home/openlia/.openlia
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      OPENLIA_HOSTNAME: ${OPENLIA_HOSTNAME:?set OPENLIA_HOSTNAME to your fully-qualified domain}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      openlia:
        condition: service_healthy

volumes:
  openlia_data:
  caddy_data:
  caddy_config:
```

And `deploy/caddy/Caddyfile`:

```
{$OPENLIA_HOSTNAME} {
    encode zstd gzip

    # Reverse proxy ALL paths to OpenLIA on port 8000. The container strips
    # /api internally (so browser-side /api/... calls Just Work), serves the
    # SPA from /, and serves static assets from /assets/*.
    reverse_proxy openlia:8000 {
        # Pass real client info — OPENLIA_TRUST_PROXY_HEADERS=true honors these.
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Long-lived SSE streams — don't buffer.
    @sse {
        path /api/chat/sessions/*/stream
        path /api/departments/*/report
    }
    reverse_proxy @sse openlia:8000 {
        flush_interval -1
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

Validate:

```bash
docker compose -f deploy/caddy/docker-compose.yml config >/dev/null
docker run --rm -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Expected: both validations pass.

Commit: `task-23-20: add deploy/caddy compose + Caddyfile with SSE flush`

### Task 21 — `deploy/lan/docker-compose.yml`

Create `deploy/lan/docker-compose.yml`:

```yaml
# LAN-only deployment — no TLS, no public exposure.
#
# WARNING: This posture trusts every device on your LAN. Suitable for
# a trusted home or small-office network; NOT for coworking spaces, hotel
# Wi-Fi, or anywhere you don't control every connected host. Add firewall
# rules restricting inbound :8080 to your subnet before first run.
#
# Start:
#   OPENLIA_IMAGE=ghcr.io/openlia/openlia:latest \
#   docker compose up -d

services:
  openlia:
    image: ${OPENLIA_IMAGE:-ghcr.io/openlia/openlia:latest}
    restart: unless-stopped
    environment:
      # Personal mode is the typical LAN choice (no login), but this file
      # works for company mode too — just flip to company and create an
      # invite via `docker compose exec openlia openlia admin invite create`.
      OPENLIA_MODE: ${OPENLIA_MODE:-personal}
      OPENLIA_TRUST_PROXY_HEADERS: "false"
      OPENLIA_COOKIE_SECURE: "false"
      OPENLIA_DB_URL: sqlite:////home/openlia/.openlia/openlia.db
      OPENLIA_SCHEDULER_ENABLED: "true"
      OPENLIA_SECRET_KEY: ${OPENLIA_SECRET_KEY:-}
    volumes:
      - openlia_data:/home/openlia/.openlia
    ports:
      - "8080:8000"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  openlia_data:
```

Validate:

```bash
docker compose -f deploy/lan/docker-compose.yml config >/dev/null
```

Expected: no errors.

Commit: `task-23-21: add deploy/lan compose example (no TLS, LAN-only)`

### Task 22 — `deploy/README.md`

Create `deploy/README.md`:

```markdown
# OpenLIA deployment recipes

Three compose stacks, each focused on one deployment posture. All three use
the same `openlia` image (ghcr.io/openlia/openlia) and differ only in what
sits in front of it.

| Directory | TLS | Public reachable | Use when |
|---|---|---|---|
| `cloudflare-tunnel/` | Yes (Cloudflare) | Yes, via tunnel | You want zero inbound ports, Cloudflare-managed DNS + TLS, and to skip owning a public IP. **Recommended for most self-hosters.** |
| `caddy/` | Yes (Let's Encrypt) | Yes, direct | You own the VPS + domain, want your own TLS termination, and are OK exposing 80/443. |
| `lan/` | No | No (LAN only) | You only want it on your home/office LAN. |

## Common flow

1. Pull or build the image:
   ```bash
   docker pull ghcr.io/openlia/openlia:latest
   ```
2. `cd` into one of the three directories.
3. Copy `.env.example` to `.env` (create your own if missing), set the
   secrets below.
4. `docker compose up -d`.
5. First boot runs the Setup Wizard at the app's root URL.

## Required secrets

- `OPENLIA_SECRET_KEY` — 32-byte base64 AES-256-GCM key. If unset, the
  container generates one on first boot and persists it to
  `/home/openlia/.openlia/secret.key` inside the named volume. Set
  explicitly if you want to rotate keys out-of-band.
  Generate: `python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"`.

## Cloudflare Tunnel specifics

- Create a tunnel in Cloudflare Zero Trust → Access → Tunnels.
- Set the public hostname to e.g. `openlia.example.com` pointing at
  `http://openlia:8000` on the docker network.
- Export `TUNNEL_TOKEN` in your shell before `docker compose up`.

## Caddy specifics

- Point your DNS A/AAAA at the host *before* starting, otherwise the
  ACME HTTP-01 challenge fails and Caddy keeps retrying (harmless but noisy).
- Ports 80 **and** 443 must be internet-reachable.
- The Caddyfile disables response buffering for SSE stream endpoints;
  don't remove that block or chat streaming will appear frozen.

## LAN specifics

- Consider adding `ufw`/pfSense rules restricting `:8080` to your subnet.
- Personal mode is the default (no login). Switch to company mode by
  setting `OPENLIA_MODE=company` and creating an invite:
  ```bash
  docker compose exec openlia openlia admin invite create --email you@example.com --role admin
  ```
- The printed URL works only on the LAN, so open it on a device on the
  same network.

## Ops basics

- Backup `/home/openlia/.openlia/` (mounted as `openlia_data` named volume).
  That single directory contains the SQLite DB and the AES secret key.
- Upgrade: `docker compose pull && docker compose up -d`. Alembic runs on
  startup via `openlia serve`; schema migrations are automatic.
- Logs: `docker compose logs -f openlia`.
- Admin commands: `docker compose exec openlia openlia admin <command>`.
```

Commit: `task-23-22: add deploy/README walking through all three recipes`

### Task 23 — `.env.example` files for each recipe

For each of the three `deploy/*/` dirs, add `.env.example`:

`deploy/cloudflare-tunnel/.env.example`:
```
OPENLIA_IMAGE=ghcr.io/openlia/openlia:latest
TUNNEL_TOKEN=replace-with-tunnel-token-from-cloudflare
OPENLIA_SECRET_KEY=
```

`deploy/caddy/.env.example`:
```
OPENLIA_IMAGE=ghcr.io/openlia/openlia:latest
OPENLIA_HOSTNAME=openlia.example.com
OPENLIA_SECRET_KEY=
```

`deploy/lan/.env.example`:
```
OPENLIA_IMAGE=ghcr.io/openlia/openlia:latest
OPENLIA_MODE=personal
OPENLIA_SECRET_KEY=
```

Commit: `task-23-23: add .env.example for each deploy recipe`

---

## Group F — PyPI packaging metadata

### Task 24 — Add `readme`, `urls`, classifiers to `packages/core/pyproject.toml`

Edit `packages/core/pyproject.toml`, replacing the `[project]` block:

```toml
[project]
name = "openlia-core"
version = "0.1.0"
description = "OpenLIA core library — departments, LLM adapters, data adapters, report generation. Pure Python library."
readme = "README.md"
requires-python = ">=3.12"
authors = [{name = "OpenLIA contributors"}]
license = {text = "MIT"}
keywords = ["llm", "finance", "investor", "ai", "agents", "reports"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Financial and Insurance Industry",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Topic :: Office/Business :: Financial :: Investment",
    "Typing :: Typed",
]
dependencies = [
    "httpx>=0.28.1",
    "pydantic>=2.6",
    "pyyaml>=6.0",
    "jinja2>=3.1",
]

[project.urls]
Homepage = "https://github.com/TK-Chang239/OpenLIA"
Source = "https://github.com/TK-Chang239/OpenLIA"
Issues = "https://github.com/TK-Chang239/OpenLIA/issues"
Changelog = "https://github.com/TK-Chang239/OpenLIA/blob/main/CHANGELOG.md"
```

(Note the duplicate `httpx` entry in the current file is deleted.)

Create a minimal `packages/core/README.md`:

```markdown
# openlia-core

Core library for [OpenLIA](https://github.com/TK-Chang239/OpenLIA) — LLM
adapters, data adapters, department logic, report generation. Pure Python;
no HTTP server dependencies.

Most users want the full server: `pip install openlia` (which pulls
`openlia-core` transitively). Install this package directly only if you're
embedding OpenLIA's department logic in another application.

```python
from openlia import EquityResearchDepartment
```

See the [main repository](https://github.com/TK-Chang239/OpenLIA) for full docs.

## License

MIT.
```

Verify build still works:

```bash
uv build --package openlia-core
ls dist/
```

Expected: `openlia_core-0.1.0-py3-none-any.whl` and `openlia_core-0.1.0.tar.gz` produced.

Commit: `task-23-24: add PyPI metadata + README for openlia-core`

### Task 25 — Add `readme`, `urls`, classifiers to `packages/server/pyproject.toml`

Edit `packages/server/pyproject.toml`:

```toml
[project]
name = "openlia"
version = "0.1.0"
description = "OpenLIA — self-hosted AI investor assistant: FastAPI server, CLI, and persistence layer."
readme = "README.md"
requires-python = ">=3.12"
authors = [{name = "OpenLIA contributors"}]
license = {text = "MIT"}
keywords = ["llm", "finance", "investor", "ai", "agents", "fastapi", "self-hosted"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: FastAPI",
    "Intended Audience :: Financial and Insurance Industry",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Topic :: Office/Business :: Financial :: Investment",
    "Typing :: Typed",
]
dependencies = [
    "openlia-core",
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "typer>=0.12",
    "httpx>=0.27",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "argon2-cffi>=23.1",
    "cryptography>=42.0",
    "email-validator>=2.2",
    "apscheduler>=4.0.0a4",
    "croniter>=2.0",
    "playwright>=1.58.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[project.scripts]
openlia = "openlia_server.cli:main"

[project.urls]
Homepage = "https://github.com/TK-Chang239/OpenLIA"
Source = "https://github.com/TK-Chang239/OpenLIA"
Issues = "https://github.com/TK-Chang239/OpenLIA/issues"
Documentation = "https://github.com/TK-Chang239/OpenLIA#readme"
Changelog = "https://github.com/TK-Chang239/OpenLIA/blob/main/CHANGELOG.md"

[tool.uv.sources]
openlia-core = { workspace = true }

[tool.uv.build-backend]
module-name = "openlia_server"
module-root = "src"
```

Create a minimal `packages/server/README.md`:

```markdown
# openlia

Self-hosted AI investor assistant. Install:

```bash
pip install openlia
openlia serve
```

Then open http://localhost:8000 and follow the Setup Wizard.

See the [main repository](https://github.com/TK-Chang239/OpenLIA) for deployment
recipes (Docker, Cloudflare Tunnel, Caddy, LAN-only) and full documentation.

## License

MIT.
```

Verify:

```bash
rm -rf dist/
uv build --package openlia
ls dist/
```

Expected: `openlia-0.1.0-py3-none-any.whl` and `openlia-0.1.0.tar.gz`.

Commit: `task-23-25: add PyPI metadata + README for openlia`

### Task 26 — Write a "what's-in-the-wheel" test

Create `packages/server/tests/test_wheel_contents.py`:

```python
"""Lock the installable surface so we don't accidentally ship planning/."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_wheel() -> Path:
    dist = REPO_ROOT / "dist"
    if dist.exists():
        for p in dist.glob("openlia-*.whl"):
            p.unlink()
    subprocess.run(
        ["uv", "build", "--package", "openlia"],
        cwd=REPO_ROOT,
        check=True,
    )
    wheels = list((REPO_ROOT / "dist").glob("openlia-*.whl"))
    assert len(wheels) == 1, wheels
    return wheels[0]


def test_wheel_excludes_planning_and_tests():
    wheel = _build_wheel()
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()

    assert any(n.startswith("openlia_server/") for n in names)
    assert not any("planning/" in n for n in names)
    assert not any("/tests/" in n for n in names)
    assert not any(".venv/" in n for n in names)


def test_wheel_entry_point_registered():
    wheel = _build_wheel()
    with zipfile.ZipFile(wheel) as zf:
        entry_points = zf.read(
            [n for n in zf.namelist() if n.endswith("entry_points.txt")][0]
        ).decode()
    assert "openlia = openlia_server.cli:main" in entry_points
```

Run:

```bash
uv run pytest packages/server/tests/test_wheel_contents.py -v
```

Expected: both tests pass. Slow (runs `uv build`) — mark with `@pytest.mark.slow` if the suite develops a speed budget, but not required for Plan 23.

Commit: `task-23-26: test wheel contents + entry point registration`

### Task 27 — End-to-end "`pip install openlia`" dry run

Build both wheels and install them into a throwaway venv to confirm the PyPI flow works without a PyPI round-trip:

```bash
python -m venv /tmp/openlia-pip-test
/tmp/openlia-pip-test/bin/pip install --upgrade pip
uv build --all-packages
/tmp/openlia-pip-test/bin/pip install dist/openlia_core-0.1.0-py3-none-any.whl dist/openlia-0.1.0-py3-none-any.whl
/tmp/openlia-pip-test/bin/openlia --help
/tmp/openlia-pip-test/bin/python -c "from openlia import EquityResearchDepartment; print('ok')"
rm -rf /tmp/openlia-pip-test
```

Expected:
- `openlia --help` prints the Typer root help.
- `from openlia import EquityResearchDepartment` succeeds.

If this fails, the metadata in Tasks 24/25 is wrong. Fix and amend the earlier commits (do not commit a new fix on top — amend with `git commit --amend` ONLY if the branch has not been pushed; otherwise a new `task-23-27: fix <thing>` commit).

No new commit on success (verification only).

---

## Group G — GitHub Actions release workflow

### Task 28 — Create `.github/workflows/release.yml`

Create the file:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  docker:
    name: Build & push Docker image (GHCR)
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository_owner }}/openlia
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=raw,value=latest

      - name: Build & push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: true
          platforms: linux/amd64,linux/arm64
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  pypi:
    name: Build & publish Python wheels
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write  # trusted publishing to PyPI
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.11"

      - name: Set up Python
        run: uv python install 3.12

      - name: Build wheels + sdists for all workspace packages
        run: uv build --all-packages

      - name: List dist/
        run: ls -la dist/

      - name: Check if PYPI_API_TOKEN is configured
        id: gate
        env:
          HAS_TOKEN: ${{ secrets.PYPI_API_TOKEN != '' }}
        run: echo "has_token=$HAS_TOKEN" >> "$GITHUB_OUTPUT"

      - name: Publish to PyPI (token auth)
        if: steps.gate.outputs.has_token == 'true'
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
        run: uv publish dist/*

      - name: Skip PyPI (no token configured)
        if: steps.gate.outputs.has_token != 'true'
        run: echo "PYPI_API_TOKEN unset — artifacts built but not published. Attach them to the GitHub Release manually or set the secret."

  release-notes:
    name: GitHub Release
    needs: [docker, pypi]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Extract tag
        id: tag
        run: echo "name=${GITHUB_REF#refs/tags/}" >> "$GITHUB_OUTPUT"

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.tag.outputs.name }}
          generate_release_notes: true
          body_path: CHANGELOG.md
```

Lint the YAML:

```bash
yq '.' .github/workflows/release.yml >/dev/null
# Or if yq isn't available:
python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
```

Expected: no parse errors.

Commit: `task-23-28: add release workflow (GHCR multi-arch + gated PyPI + release notes)`

### Task 29 — Harden CI: add a "Docker image builds" smoke job to `ci.yml`

Edit `.github/workflows/ci.yml`, adding a third job:

```yaml
  docker:
    name: Docker — image builds
    runs-on: ubuntu-latest
    needs: [python, frontend]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image (no push)
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          push: false
          tags: openlia:ci
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Smoke start + healthcheck
        run: |
          docker run -d --name openlia-ci -p 8000:8000 openlia:ci
          for i in $(seq 1 30); do
            if curl -fsS http://127.0.0.1:8000/healthz >/dev/null; then
              echo "OK after ${i}s"
              exit 0
            fi
            sleep 1
          done
          echo "Container failed to become healthy in 30s"
          docker logs openlia-ci
          exit 1

      - name: Cleanup
        if: always()
        run: docker rm -f openlia-ci || true
```

This ensures every PR exercises the image build end-to-end.

Commit: `task-23-29: add Docker build + smoke job to CI`

### Task 30 — Document the release process

Create `RELEASING.md` at repo root:

```markdown
# Releasing OpenLIA

Version scheme: [SemVer](https://semver.org/). Tags are of the form `v0.1.0`,
`v0.2.0`, `v1.0.0`.

## Pre-flight

1. All Plan 23 tasks shipped, `main` green.
2. `CHANGELOG.md` updated (see "Write release notes" below).
3. Version bumped in:
   - `packages/core/pyproject.toml` → `[project].version`
   - `packages/server/pyproject.toml` → `[project].version`
   Both must match.
4. `uv.lock` regenerated: `uv sync --all-packages`.
5. Aggregate sanity: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q && cd frontend && npm run lint && npm run build && npm test`.

## Write release notes

Prepend a section to `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/):

```markdown
## [0.1.0] — 2026-04-XX

### Added
- Initial public release.
- …
```

## Tag + push

```bash
git commit -am "release: v0.1.0"
git tag v0.1.0
git push origin main v0.1.0
```

The `Release` workflow triggers on the `v*` tag push. It:
- Builds `linux/amd64` + `linux/arm64` images and pushes to
  `ghcr.io/TK-Chang239/openlia` with tags `0.1.0`, `0.1`, `0`, `latest`.
- Builds `openlia-core` and `openlia` wheels + sdists via `uv build --all-packages`.
- If `PYPI_API_TOKEN` secret is set, publishes to PyPI.
- Creates a GitHub Release at the tag with autogenerated notes.

## Post-release verification

```bash
docker pull ghcr.io/TK-Chang239/openlia:0.1.0
docker run --rm -p 8000:8000 ghcr.io/TK-Chang239/openlia:0.1.0 &
sleep 5
curl http://localhost:8000/healthz

pip install --upgrade openlia==0.1.0
openlia --help
```

## Rolling a broken release

1. Yank from PyPI: `pip-yank openlia 0.1.0` (or `uv publish --yank`).
2. Delete the GHCR tag (requires GitHub web UI or `gh api ...`).
3. Tag `v0.1.1` with the fix and push.
```

Commit: `task-23-30: add RELEASING.md with tag-driven release process`

### Task 31 — Add a matching `CHANGELOG.md` stub

Create `CHANGELOG.md` at repo root:

```markdown
# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/).

## [Unreleased]

### Added
- Phase 23: production Docker image (multi-stage, non-root, Playwright bundled).
- Phase 23: `deploy/` recipes — Cloudflare Tunnel, Caddy, LAN-only.
- Phase 23: `OPENLIA_TRUST_PROXY_HEADERS` + `OPENLIA_COOKIE_SECURE` wired.
- Phase 23: `/api` prefix stripping in production ASGI (mirrors Vite dev proxy).
- Phase 23: GHCR multi-arch release workflow + gated PyPI publish.
- Phase 23: smoke tests for personal and company modes run against the container.

### Changed
- Phase 23: `_mount_frontend` resolves `/app/frontend/dist` automatically in the
  image, falls back to `<repo>/frontend/dist` for manual builds.

### Deprecated

_none_

### Removed

_none_

### Fixed

_none_

### Security

- Phase 23: default `Secure` flag on session cookies in company mode.
- Phase 23: ProxyHeadersMiddleware honored only when `OPENLIA_TRUST_PROXY_HEADERS=true`.
```

Commit: `task-23-31: add CHANGELOG.md stub for v0.1.0`

---

## Group H — Smoke tests (personal + company modes)

These tests actually boot the container. They live at **repo root** under
`tests/smoke/` (NOT under `packages/`), because they exercise the whole image,
not any single package. They are opt-in: only run when the `SMOKE=1` env var
is set, so `uv run pytest` in the normal path skips them.

### Task 32 — Create `tests/smoke/` scaffolding

Create `tests/__init__.py` (empty).
Create `tests/smoke/__init__.py` (empty).
Create `tests/smoke/conftest.py`:

```python
"""Smoke-test harness: pulls up the openlia container and tears it down.

Opt-in via SMOKE=1. Otherwise the whole directory is skipped.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Iterator

import httpx
import pytest


def _smoke_enabled() -> bool:
    return os.environ.get("SMOKE", "0").lower() in ("1", "true", "yes")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for(url: str, *, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(0.5)
    raise RuntimeError(f"{url} never returned 200 within {timeout}s: {last!r}")


pytestmark = pytest.mark.skipif(
    not _smoke_enabled(),
    reason="Set SMOKE=1 to run container smoke tests.",
)


@pytest.fixture
def run_container():
    containers: list[str] = []

    def _run(*, image: str, env: dict[str, str], name: str) -> tuple[str, int]:
        port = _free_port()
        args = ["docker", "run", "-d", "--rm", "--name", name, "-p", f"{port}:8000"]
        for k, v in env.items():
            args.extend(["-e", f"{k}={v}"])
        args.append(image)
        subprocess.run(args, check=True)
        containers.append(name)
        base = f"http://127.0.0.1:{port}"
        _wait_for(f"{base}/healthz", timeout=60.0)
        return base, port

    yield _run

    for name in containers:
        subprocess.run(["docker", "rm", "-f", name], check=False)


@pytest.fixture
def image_tag() -> str:
    return os.environ.get("OPENLIA_IMAGE", "openlia:dev")
```

Commit: `task-23-32: add tests/smoke/ scaffolding (container harness)`

### Task 33 — Write personal-mode smoke test (failing first)

Create `tests/smoke/test_personal_mode.py`:

```python
"""Personal-mode container smoke test."""
from __future__ import annotations

import httpx


def test_healthz_returns_personal(run_container, image_tag):
    base, _ = run_container(
        image=image_tag,
        env={"OPENLIA_MODE": "personal"},
        name="openlia-smoke-personal",
    )
    r = httpx.get(f"{base}/healthz", timeout=5.0)
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "mode": "personal"}


def test_api_prefix_accessible(run_container, image_tag):
    base, _ = run_container(
        image=image_tag,
        env={"OPENLIA_MODE": "personal"},
        name="openlia-smoke-personal-api",
    )
    # Browser-side /api call must reach the same route as the bare path.
    r = httpx.get(f"{base}/api/healthz", timeout=5.0)
    assert r.status_code == 200
    assert r.json()["mode"] == "personal"


def test_spa_served_from_root(run_container, image_tag):
    base, _ = run_container(
        image=image_tag,
        env={"OPENLIA_MODE": "personal"},
        name="openlia-smoke-personal-spa",
    )
    r = httpx.get(f"{base}/", timeout=5.0)
    assert r.status_code == 200
    assert "<div id=\"root\">" in r.text or "<div id='root'>" in r.text


def test_setup_wizard_reachable(run_container, image_tag):
    base, _ = run_container(
        image=image_tag,
        env={"OPENLIA_MODE": "personal"},
        name="openlia-smoke-personal-wizard",
    )
    r = httpx.get(f"{base}/api/setup/state", timeout=5.0)
    assert r.status_code in (200, 403)  # 403 when wizard gate blocks non-loopback
```

Run:

```bash
SMOKE=1 OPENLIA_IMAGE=openlia:dev uv run pytest tests/smoke/test_personal_mode.py -v
```

Expected: all four pass (prerequisite: `docker build -t openlia:dev .` completed in Task 13). The last test tolerates `403` because the wizard gate checks loopback.

Commit: `task-23-33: add personal-mode container smoke test`

### Task 34 — Write company-mode smoke test

Create `tests/smoke/test_company_mode.py`:

```python
"""Company-mode container smoke test — creates an invite via CLI, registers."""
from __future__ import annotations

import json
import secrets
import subprocess

import httpx


def _exec(container: str, *args: str) -> str:
    res = subprocess.run(
        ["docker", "exec", container, "openlia", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout


def test_company_mode_end_to_end(run_container, image_tag):
    base, _ = run_container(
        image=image_tag,
        env={
            "OPENLIA_MODE": "company",
            "OPENLIA_COOKIE_SECURE": "false",  # no TLS in smoke harness
        },
        name="openlia-smoke-company",
    )

    # 1. healthz
    r = httpx.get(f"{base}/healthz")
    assert r.status_code == 200
    assert r.json()["mode"] == "company"

    # 2. create an admin invite via CLI inside the container
    email = f"smoke-{secrets.token_hex(4)}@example.com"
    out = _exec(
        "openlia-smoke-company",
        "admin",
        "invite",
        "create",
        "--email",
        email,
        "--role",
        "admin",
        "--json",
    )
    invite = json.loads(out)
    assert "token" in invite
    assert len(invite["invite_id"]) == 36  # UUID-36 per contract

    # 3. register
    password = "Sm0kePass!" + secrets.token_hex(4)
    r = httpx.post(
        f"{base}/api/auth/register",
        json={
            "invite_token": invite["token"],
            "email": email,
            "display_name": "Smoke",
            "password": password,
        },
    )
    assert r.status_code == 200, r.text

    # 4. log in with the same client (cookie jar carries session)
    client = httpx.Client(base_url=base)
    r = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == email
    assert r.json()["is_admin"] is True

    # 5. /api/auth/me works (session cookie sticks)
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == email
```

Run:

```bash
SMOKE=1 OPENLIA_IMAGE=openlia:dev uv run pytest tests/smoke/test_company_mode.py -v
```

Expected: all assertions pass. The admin invite CLI subcommand must accept `--json` and print `{"token": "...", "invite_id": "..."}`. If it doesn't, Plan 7 shipped without the JSON output — add that in a separate follow-up. For Plan 23, this test locks the contract.

Commit: `task-23-34: add company-mode container smoke test with invite flow`

### Task 35 — Verify CLI `--json` on admin invite create

If Task 34 fails because `--json` isn't implemented:

1. Add the flag to `packages/server/src/openlia_server/cli.py`'s admin invite-create subcommand.
2. Add a unit test under `packages/server/tests/cli/test_admin_invite.py` asserting JSON output.
3. Confirm the smoke test now passes.

If Task 34 already passes, this task is a no-op — skip ahead. Either way:

Commit (only if change): `task-23-35: add --json to admin invite create for machine-readable output`

### Task 36 — Assert `OPENLIA_COOKIE_SECURE` propagates end-to-end

Extend `tests/smoke/test_company_mode.py` with:

```python
def test_cookie_secure_flag_propagates(run_container, image_tag):
    base, _ = run_container(
        image=image_tag,
        env={
            "OPENLIA_MODE": "company",
            "OPENLIA_COOKIE_SECURE": "true",
        },
        name="openlia-smoke-company-secure",
    )

    email = f"sec-{secrets.token_hex(4)}@example.com"
    out = _exec(
        "openlia-smoke-company-secure",
        "admin",
        "invite",
        "create",
        "--email",
        email,
        "--role",
        "user",
        "--json",
    )
    invite = json.loads(out)

    password = "Sec0rePass!"
    httpx.post(
        f"{base}/api/auth/register",
        json={
            "invite_token": invite["token"],
            "email": email,
            "display_name": "Sec",
            "password": password,
        },
    )
    r = httpx.post(
        f"{base}/api/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    sc = r.headers.get("set-cookie", "")
    assert "Secure" in sc
    assert "HttpOnly" in sc
```

Run:

```bash
SMOKE=1 uv run pytest tests/smoke/test_company_mode.py::test_cookie_secure_flag_propagates -v
```

Expected: passes.

Commit: `task-23-36: smoke-assert OPENLIA_COOKIE_SECURE propagates through container`

### Task 37 — Assert `OPENLIA_TRUST_PROXY_HEADERS` propagates end-to-end

Add to `tests/smoke/test_company_mode.py`:

```python
def test_trust_proxy_headers_propagates(run_container, image_tag):
    base, _ = run_container(
        image=image_tag,
        env={
            "OPENLIA_MODE": "company",
            "OPENLIA_COOKIE_SECURE": "false",
            "OPENLIA_TRUST_PROXY_HEADERS": "true",
        },
        name="openlia-smoke-company-proxy",
    )

    r = httpx.get(
        f"{base}/_debug/client_host",
        headers={"X-Forwarded-For": "198.51.100.99", "X-Forwarded-Proto": "https"},
    )
    assert r.status_code == 200
    assert r.json()["host"] == "198.51.100.99"
    assert r.json()["scheme"] == "https"
```

Run, commit: `task-23-37: smoke-assert OPENLIA_TRUST_PROXY_HEADERS propagates through container`

### Task 38 — Ensure smoke tests are skipped when `SMOKE` unset

```bash
uv run pytest tests/smoke/ -v
```

Expected: all smoke tests reported as skipped with reason "Set SMOKE=1 to run container smoke tests."

If any test ran despite `SMOKE` being unset, the `pytestmark` wiring is wrong. Fix before committing.

No commit (verification).

### Task 39 — Update `pytest.ini_options` testpaths to include `tests/`

Edit `pyproject.toml` at repo root. Change:

```toml
testpaths = ["packages/core/tests", "packages/server/tests"]
```

to:

```toml
testpaths = ["packages/core/tests", "packages/server/tests", "tests"]
```

Verify:

```bash
uv run pytest --collect-only -q | tail -30
```

Expected: smoke tests now appear in the collection report (even if skipped).

Commit: `task-23-39: add tests/ to pytest testpaths so smoke suite is collected`

---

## Group I — Documentation, CHANGELOG, final acceptance

### Task 40 — Rewrite root `README.md` Quickstart section

Locate the existing `README.md` at repo root. Replace the "Quickstart" section (or add one right after the project description) with:

```markdown
## Quickstart

### Docker (recommended)

```bash
docker run -d --name openlia -p 8000:8000 \
    -v openlia_data:/home/openlia/.openlia \
    ghcr.io/TK-Chang239/openlia:latest
open http://localhost:8000
```

First boot drops you into the Setup Wizard. Choose **personal mode** for
single-user localhost, **company mode** for multi-user network access.

For production (Cloudflare Tunnel, Caddy, or LAN-only), use the recipes in
[`deploy/`](./deploy/README.md).

### PyPI (pip install)

```bash
python -m venv .venv
. .venv/bin/activate
pip install openlia
openlia serve
```

`pip install openlia` pulls the library (`openlia-core`) and the server
(`openlia`) together. The `openlia` console script is your entry point.

### From source (development)

```bash
uv sync --all-packages
cd frontend && npm install && cd ..

# Terminal 1: backend
uv run openlia serve

# Terminal 2: frontend dev server
cd frontend && npm run dev
# Browser: http://localhost:8080
```

### Deployment recipes

| Directory | Posture |
|---|---|
| [`deploy/cloudflare-tunnel/`](./deploy/cloudflare-tunnel/) | Cloudflare Tunnel (recommended — zero inbound ports) |
| [`deploy/caddy/`](./deploy/caddy/) | Caddy reverse proxy with automatic TLS |
| [`deploy/lan/`](./deploy/lan/) | LAN-only, no TLS |
```

Commit: `task-23-40: rewrite README Quickstart with Docker + PyPI + source flows`

### Task 41 — Link docs into the root README table of contents

Add or extend a short "Docs" section in `README.md`:

```markdown
## Docs

- [Deployment recipes](./deploy/README.md)
- [Release process](./RELEASING.md)
- [Changelog](./CHANGELOG.md)
- [Planning & specs](./planning/) (not shipped with the image)
```

Commit: `task-23-41: link deploy, release, changelog from README`

### Task 42 — Update the plan index

Edit `planning/implementation-plans/README.md`. In the status table, change
the Plan 23 row from:

```
| 23 | 7 | Docker packaging + production build + final acceptance | Not started | — |
```

to:

```
| 23 | 7 | Docker packaging + production build + final acceptance | Draft | `2026-04-23-phase-23-docker-packaging-acceptance.md` |
```

(At merge time — Task 48 — the same row flips `Draft → Done` with a date.)

Commit: `task-23-42: register Plan 23 in the implementation-plans index`

### Task 43 — Run the full Python aggregate suite

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Expected: all three green. If the smoke tests are skipped because `SMOKE` is
unset, that is correct — they are opt-in.

Paste the final pytest summary line into the commit body for the record, e.g.
`XXXX passed, YY skipped in ZZs`.

Commit: `task-23-43: aggregate Python sanity run (lint + format + test)`

### Task 44 — Run the frontend aggregate suite

```bash
cd frontend
npm ci
npm run lint
npm test
npm run build
```

Expected: `tsc --noEmit` clean, all vitest tests pass, `vite build` produces
`dist/index.html`.

Commit: `task-23-44: aggregate frontend sanity (lint + test + build)`

### Task 45 — Full container smoke run

```bash
docker build -t openlia:acceptance .
SMOKE=1 OPENLIA_IMAGE=openlia:acceptance uv run pytest tests/smoke/ -v
```

Expected: every smoke test passes. Paste the summary line into the commit
message.

Commit: `task-23-45: full container smoke pass (personal + company)`

### Task 46 — Validate all three compose stacks parse

```bash
docker compose -f deploy/cloudflare-tunnel/docker-compose.yml config >/dev/null
docker compose -f deploy/caddy/docker-compose.yml config >/dev/null
docker compose -f deploy/lan/docker-compose.yml config >/dev/null
docker run --rm -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Expected: zero errors.

No commit (verification). If any stack failed, fix and commit as
`task-23-46: fix <file> <issue>`.

### Task 47 — Cross-plan merge-gate checklist

This single task runs the canonical merge gate from the
`planning/implementation-plans/README.md` "Merge gate" block **and** every
Plan-23-specific acceptance item in one pass:

```bash
set -e
uv run ruff check .
uv run ruff format --check .
uv run pytest -q

cd frontend
npm run lint
npm test -- --run
npm run build
cd ..

docker build -t openlia:gate .
SMOKE=1 OPENLIA_IMAGE=openlia:gate uv run pytest tests/smoke/ -v

docker compose -f deploy/cloudflare-tunnel/docker-compose.yml config >/dev/null
docker compose -f deploy/caddy/docker-compose.yml config >/dev/null
docker compose -f deploy/lan/docker-compose.yml config >/dev/null

uv build --all-packages
python -m venv /tmp/openlia-gate-venv
/tmp/openlia-gate-venv/bin/pip install --upgrade pip
/tmp/openlia-gate-venv/bin/pip install dist/openlia_core-*.whl dist/openlia-*.whl
/tmp/openlia-gate-venv/bin/openlia --help >/dev/null
rm -rf /tmp/openlia-gate-venv

echo "GATE PASSED"
```

Expected final line: `GATE PASSED`.

If any step fails, fix the underlying bug and commit that fix as a separate
task-appendix commit (`task-23-47-fixup-<n>: <description>`), then re-run
this gate. Do not mark Plan 23 Done until the full gate passes in a single
invocation.

No commit for the gate itself — it's a dry run. The commit below captures the
final status-table flip.

### Task 48 — Flip Plan 23 to Done and open the PR

Edit `planning/implementation-plans/README.md`. Change the Plan 23 row to:

```
| 23 | 7 | Docker packaging + production build + final acceptance | **Done** (2026-04-XX) | `2026-04-23-phase-23-docker-packaging-acceptance.md` |
```

(Use the actual merge date in place of `XX`.)

Commit: `task-23-48: mark Plan 23 Done in status table`

Then open the PR. Body template:

```markdown
Closes Plan 23 (final plan). Delivers:

- Multi-stage Dockerfile → ghcr.io image (amd64+arm64, non-root, Playwright
  bundled, ~1 GB).
- `pip install openlia` from PyPI (gated on `PYPI_API_TOKEN` secret).
- Production FastAPI: `/api` prefix strip middleware mirrors Vite dev proxy,
  `ProxyHeadersMiddleware` behind `OPENLIA_TRUST_PROXY_HEADERS`, automatic
  `/app/frontend/dist` resolution.
- Three `deploy/` recipes: Cloudflare Tunnel, Caddy, LAN-only.
- Smoke tests (opt-in via `SMOKE=1`) booting the container in both modes and
  exercising invite-driven registration + login.
- `release.yml` GitHub Actions workflow: tag-driven GHCR + PyPI + release notes.
- `CI` extended with a Docker build + healthcheck smoke job.
- `RELEASING.md`, `CHANGELOG.md`, `README.md` Quickstart, `deploy/README.md`.

Acceptance gate (all passed locally):
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean
- `uv run pytest -q` — N passed, M skipped
- `cd frontend && npm run lint && npm test && npm run build` — clean
- `docker build -t openlia:gate .` — succeeds
- `SMOKE=1 pytest tests/smoke/ -v` — full pass
- Three `deploy/` composes `docker compose config` — clean
- `pip install dist/*.whl` into fresh venv, `openlia --help` — clean

Ship-ready for `v0.1.0`.
```

When CI green + reviewer approves + merged, cut the `v0.1.0` tag to kick off
the release workflow.

---

## Acceptance criteria (one-liner per item)

A PR implementing Plan 23 is mergeable when all of the following are true:

1. Every task 1–48 is a single commit on `feat/phase-23-docker-packaging-acceptance`, in order.
2. `docker build -t openlia:ci .` succeeds on CI's Ubuntu runner.
3. `docker run` of the built image passes `/healthz` within 30 seconds.
4. `GET /api/healthz` and `GET /healthz` against the container return identical JSON.
5. `GET /` serves the built SPA (contains `<div id="root">`).
6. `GET /assets/<hashed-bundle>.js` returns 200 with JS content.
7. Personal-mode smoke suite passes under `SMOKE=1`.
8. Company-mode smoke suite passes under `SMOKE=1` — including invite creation via `openlia admin invite create --json` and full login round-trip.
9. `OPENLIA_COOKIE_SECURE=true` causes login responses to carry `Set-Cookie: ...; Secure; HttpOnly`.
10. `OPENLIA_TRUST_PROXY_HEADERS=true` causes `X-Forwarded-For` to become `request.client.host`.
11. All three `deploy/*.yml` stacks pass `docker compose config`.
12. `deploy/caddy/Caddyfile` passes `caddy validate`.
13. `uv build --all-packages` produces `openlia_core-*.whl`, `openlia_core-*.tar.gz`, `openlia-*.whl`, `openlia-*.tar.gz`.
14. Installing those wheels into a fresh venv yields a working `openlia --help`.
15. The wheel for `openlia` does **not** contain `planning/`, `tests/`, or `.venv/` (see `test_wheel_contents.py`).
16. `.github/workflows/release.yml` triggers on `v*` tags, builds multi-arch GHCR images, and optionally publishes to PyPI when `PYPI_API_TOKEN` is set.
17. `.github/workflows/ci.yml` includes a `Docker — image builds` job that builds + smokes the image on every PR.
18. `README.md` Quickstart covers Docker, PyPI, and from-source flows.
19. `deploy/README.md` walks through all three recipes with ops basics.
20. `RELEASING.md` documents the tag-driven release process.
21. `CHANGELOG.md` has an Unreleased section populated with Phase 23 entries.
22. `planning/implementation-plans/README.md` marks Plan 23 Done with a date.
23. Aggregate merge gate runs clean: `ruff check`, `ruff format --check`, `pytest -q`, `npm run lint`, `npm test`, `npm run build`.
24. The PR description contains the exact summary in Task 48.

When all 24 are checked, Plan 23 is complete and the repo is cleared to cut `v0.1.0`.

---

## Post-release follow-ups (out of scope for Plan 23, tracked here)

These are intentionally deferred so Plan 23 stays shippable. File tickets
after v0.1.0 ships:

- **Container size reduction.** Split Playwright out into an `openlia:lite`
  tag that omits Chromium (PDF export disabled). Should cut image size
  roughly in half.
- **Homebrew formula.** `brew install openlia` as an alternative to Docker
  + PyPI. Needs a stable release cadence first.
- **Windows smoke tests.** Current smoke suite assumes a POSIX docker host.
  Add a Windows-hosted runner to the release workflow when a native
  Windows user asks for it.
- **Trusted publishing to PyPI.** Currently the workflow uses
  `PYPI_API_TOKEN`; swap to OIDC trusted publishing once the project is
  claimed on PyPI.
- **Supply-chain attestations.** Add `actions/attest-build-provenance` to
  the release workflow so GHCR images + PyPI artifacts carry SLSA provenance.
- **Kubernetes manifest examples.** Many deployments will want Helm; defer
  until real demand exists so we don't maintain a chart with zero users.
- **Automated image vulnerability scanning.** Add `trivy` or `grype` scans
  to the release workflow; gate at `CRITICAL` severity.

---

## Why this plan is shippable as-is

- Respects every cross-plan contract in `planning/implementation-plans/README.md`. In particular, contract #1 (`/api` prefixes) is preserved in prod exactly as the dev Vite proxy handles it — a single middleware, explicit test coverage, identical semantics.
- Does not extend any schema, add DB columns, or change any router signature. Pure packaging + infrastructure work.
- Every new Python file has tests. Every Dockerfile / compose / CI file has a validation command in its own task.
- Smoke tests are opt-in — the default `pytest` path on contributor laptops stays fast.
- PyPI publish is gated on a secret existing, so the first release can ship from a fork or a personal account without breaking the workflow.
- Release workflow is orthogonal to CI; CI stays fast, Release takes longer and runs only on tags.
- Rollback story documented (`RELEASING.md` → "Rolling a broken release").
- No hidden work: every acceptance criterion maps to a specific task, every task ends with a commit, the final task flips the status table and opens the PR.

This is the last plan. After it merges, `v0.1.0` ships.
