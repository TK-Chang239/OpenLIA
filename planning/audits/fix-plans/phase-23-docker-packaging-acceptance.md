# Phase 23 — Docker / Packaging / Acceptance fix plan (→ 100%)


**Current:** ~55% shipped. **Root cause:** mixed (DEFERRED smoke matrix + IMPLEMENTER compose/release drift).

**Gap summary:** Container never built end-to-end; release workflow PyPI gate missing; `.dockerignore` excludes `CHANGELOG.md`; LAN compose hardcodes company mode; no `RELEASING.md`; CI has no Docker-build job; smoke-tests directory absent.

**Tasks (in execution order):**

1. **P0-10 — Container-runtime smoke: build image, run container, curl `/healthz` + `/`.**
   - Files: `packages/server/tests/smoke/__init__.py` (new), `test_personal_mode_smoke.py`, `test_company_mode_smoke.py`, `test_cookie_propagation.py`, `test_proxy_propagation.py`, `test_cli_invite_json.py`, conftest with `SMOKE` env gate. Update `pyproject.toml` `testpaths`.
   - Plan ref: Tasks 32–39, 45.
   - Acceptance: `SMOKE=1 uv run pytest packages/server/tests/smoke/` passes; each test builds `openlia:dev`, runs the container, asserts `curl /healthz` 200.

2. **P1-22 — Gate PyPI publish on token presence; fall back to dry run.**
   - Files: `.github/workflows/release.yml` (wrap `pypa/gh-action-pypi-publish` step in `if: secrets.PYPI_API_TOKEN != ''`).
   - Acceptance: tag push with no token configured completes workflow green, logs "PyPI publish skipped".

3. **P1-23 — Fix `.dockerignore` to exempt `CHANGELOG.md` (and `LICENSE`).**
   - Files: `.dockerignore` — add `!CHANGELOG.md` and `!LICENSE*`.
   - Acceptance: `docker build .` succeeds and both `pyproject.toml`'s `readme`/license references resolve inside image.

4. **P1-24 — Make `deploy/lan-only/docker-compose.yml` mode-configurable.**
   - Files: `deploy/lan-only/docker-compose.yml` (`OPENLIA_MODE: ${OPENLIA_MODE:-personal}`); `deploy/lan-only/.env.example` (new).
   - Spec ref: `planning/PLAN.md` "deployment modes".
   - Acceptance: `OPENLIA_MODE=personal docker compose -f deploy/lan-only/docker-compose.yml config` shows personal; default resolves without auth.

5. **NEW-23-01 — Add `cloudflare-tunnel` + `caddy` compose recipes.**
   - Files: `deploy/cloudflare-tunnel/docker-compose.yml` (new); `deploy/caddy/docker-compose.yml` + `deploy/caddy/Caddyfile` (new); `.env.example` per dir.
   - Plan ref: Tasks 19 + 20.
   - Why new: tracker lumps under deferred compose fixes.
   - Acceptance: `docker compose -f <each>/docker-compose.yml config` validates.

6. **NEW-23-02 — Write `RELEASING.md`.**
   - Files: `RELEASING.md` (new at repo root) — cut tag, bump CHANGELOG, verify release workflow, PyPI trusted-publisher setup.
   - Plan ref: Task 30.
   - Acceptance: doc exists; referenced from root `README.md` TOC.

7. **NEW-23-03 — Add "Docker image builds" smoke job to `ci.yml`.**
   - Files: `.github/workflows/ci.yml` — new job running `docker build .` + health curl.
   - Plan ref: Task 29.
   - Acceptance: PR checks show "Docker image builds" green.

8. **NEW-23-04 — Add `test_wheel_contents.py` asserting `planning/`, `tests/`, `node_modules/` absent from built wheel; `frontend/dist` present.**
   - Files: `packages/server/tests/test_wheel_contents.py` (new); `packages/core/tests/test_wheel_contents.py` (new).
   - Plan ref: Task 26.
   - Acceptance: green after `uv build`.

9. **NEW-23-05 — Cookie/proxy integration tests + production env snapshot fixture.**
   - Files: `test_cookie_secure.py`, `test_proxy_and_cookie_integration.py`, `test_production_env_snapshot.py` + fixture YAML.
   - Plan ref: Tasks 6–9.
   - Acceptance: `uv run pytest packages/server/tests/ -k "cookie or proxy or env_snapshot"` green.

10. **NEW-23-06 — Rewrite root `README.md` Quickstart + link RELEASING.md + CHANGELOG stub refresh.**
    - Files: `README.md`, `CHANGELOG.md` (v0.1.0 stub).
    - Plan ref: Tasks 40, 41, 31.
    - Acceptance: README Quickstart shows `uv run openlia serve` + `docker compose up -d` paths; CHANGELOG references tag.

**Verification:** `SMOKE=1 uv run pytest packages/server/tests/smoke/ && uv build && docker build -t openlia:dev . && docker compose -f deploy/lan-only/docker-compose.yml config && gh workflow view release.yml`.

