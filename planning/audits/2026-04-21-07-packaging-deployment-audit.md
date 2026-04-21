# Packaging And Deployment Audit

Date: 2026-04-21

Scope: development quickstart, CI, env vars, package metadata, static frontend
serving, Docker/compose readiness, reverse proxy/cookie settings, and runtime
dependencies for final product deployment.

Validation commands run: none. Static audit only.

## Executive Summary

The development package layout is reasonable, and CI runs Python plus frontend
test/build jobs. Production deployment is not ready yet. There is no Dockerfile
or compose file, no production static-file serving, `.env.example` uses an
obsolete mode variable, company-mode cookie defaults are weaker than spec, and
Playwright/PDF dependencies are not present in package metadata because the
report pipeline is not implemented yet.

## Current Deployment Baseline

Present:

- workspace `pyproject.toml`
- `packages/core` package metadata
- `packages/server` package metadata
- Typer console script: `openlia`
- Vite frontend package
- CI workflow for Python and frontend
- `.env.example`

Missing:

- Dockerfile
- docker-compose examples
- production static frontend serving
- production smoke tests
- proxy/cookie deployment docs
- report/PDF runtime dependencies

## Findings

### 1. High - `.env.example` Documents The Wrong Mode Variable

`.env.example` uses:

```env
OPENLIA_DEPLOYMENT_MODE=personal
```

Source reads:

```env
OPENLIA_MODE
```

Impact: operators following the env example cannot enable company mode.

Required fix: replace with `OPENLIA_MODE=personal` and document allowed values.

### 2. High - No Production Static Frontend Serving Exists

Current `openlia serve` starts FastAPI only. Vite is dev-only. No code serves
`frontend/dist` from FastAPI.

Impact: a packaged install or Docker container cannot serve the full app as one
product.

Required fix in Plan 23:

- Build frontend assets.
- Include them in server package or container image.
- Mount static files with SPA fallback.
- Ensure API routes are not shadowed by static fallback.

### 3. High - Docker/Compose Deployment Is Not Present

No Dockerfile or docker-compose files exist.

Impact: planned Cloudflare/Caddy/LAN deployment recipes cannot be validated.

Required fix:

- Multi-stage Dockerfile:
  - Node frontend build
  - Python runtime
  - persistent `/data` or `/app/.openlia` volume
- Compose examples for:
  - LAN-only
  - Caddy reverse proxy
  - Cloudflare Tunnel

### 4. Medium - Cookie Secure Default Differs From Spec

Spec expects `OPENLIA_COOKIE_SECURE` true by default in company mode. Current
auth route helper defaults false unless env is set.

Impact: company-mode deployments can run insecure cookies by default.

Required fix: default to secure in company mode, allow env override.

### 5. Medium - CI Frontend Build Is Good, But E2E Is Missing

CI runs:

- Python lint/format/test.
- Frontend typecheck/test/build.

Missing:

- backend/frontend integration smoke.
- personal/company mode boot smoke.
- route contract smoke.
- production static serving smoke.

Required fix:

- Add a small smoke job once static serving exists.
- Start server against temp SQLite DB.
- Verify `/health`, `/`, and one API endpoint.

### 6. Medium - Report/PDF Dependencies Are Not Yet Packaged

Plans 13+ mention Playwright/PDF export. Current package metadata does not
include Playwright or browser installation steps.

Impact: PDF export will fail in packaged/container deployments unless Plan 13
or Plan 23 adds runtime dependencies and install steps.

Required fix:

- Decide whether PDF export depends on Playwright in server package.
- Add install instructions and Docker browser deps.
- Add a PDF export smoke test in container or CI where feasible.

### 7. Medium - Host/Port Env Vars Are Documented But Not Used By CLI

`.env.example` documents `OPENLIA_HOST` and `OPENLIA_PORT`. `openlia serve`
uses Typer options with defaults and does not read these env vars.

Impact: operators may set env vars and see no effect.

Required fix:

- Either remove env vars from `.env.example`, or
- Wire Typer options to env vars.

## Deployment Readiness Gate

Before final acceptance:

1. `.env.example` matches source.
2. `openlia serve` can serve API and frontend in production mode.
3. Docker image boots with mounted persistent state.
4. Company-mode cookies are secure by default.
5. Reverse proxy docs are tested.
6. Playwright/PDF dependencies are installed where needed.
7. CI or manual smoke proves personal and company boot.
