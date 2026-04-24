# Phase 23 — Docker / Packaging / Acceptance fix plan (→ 100%)

**Current:** ~55% shipped. **Root cause:** mixed.
- IMPLEMENTER drift: Dockerfile/release.yml/compose recipes shipped, but recipe set differs from plan (only `compose/` + `lan-only/` exist, not `cloudflare-tunnel/` + `caddy/` + `lan/` per plan tasks 19–21); LAN compose is hardcoded `OPENLIA_MODE: company` against plan's `${OPENLIA_MODE:-personal}`; `core` and `server` package READMEs referenced by `pyproject.readme = "../../README.md"` is wrong (uv_build cannot reach upstream paths in a wheel sdist context); `.dockerignore` excludes all `*.md` then re-allows only `README.md` (planned to also re-allow `CHANGELOG.md`).
- DEFERRED: Container-runtime smoke (REM-P1-019 residual / **P0-10**) never executed; `tests/smoke/` directory absent; `RELEASING.md` absent; CI has no Docker-build-and-boot job; per-recipe `.env.example` files absent; production-env YAML fixture + `test_production_env_snapshot.py` absent; `test_wheel_contents.py` + `test_cookie_secure.py` + `test_proxy_and_cookie_integration.py` + `test_api_prefix_strip.py` listed in plan but partially shipped (api_prefix + frontend_mount + trust_proxy exist; cookie/proxy-integration/wheel-contents absent).
- POLICY GAP: `pyproject.toml` `testpaths` not extended to `tests/` (smoke suite would be uncollected even if added); CI Playwright install runs in `python` job but not gated to whether the runtime image truly needs it for tests vs build.

**Plan-vs-shipped delta (verified 2026-04-24, branch `feat/rs-refreshing-classifier`):**

| Plan task group | Status | Evidence |
|---|---|---|
| A — `/api` strip + ProxyHeaders + frontend mount | Shipped | `app.py:165 _StripApiPrefixMiddleware`, `app.py:328 ProxyHeadersMiddleware`, `_mount_frontend` w/ env+default fallback; `test_api_prefix_strip.py`, `test_trust_proxy_headers.py`, `test_frontend_mount.py` present |
| B — Cookie/secure + production-env fixture | Partial | `test_cookie_secure.py` absent; `test_proxy_and_cookie_integration.py` absent; `tests/fixtures/production_env.yaml` + `test_production_env_snapshot.py` absent |
| C — Dockerfile + `.dockerignore` | Partial | `Dockerfile` present and matches plan; `.dockerignore` missing `!CHANGELOG.md` exemption |
| D — Frontend prod build smoke vitest | Unknown / likely absent | `frontend/src/api/__tests__/prodBase.test.ts` + `buildOutput.test.ts` not verified to exist |
| E — `deploy/` recipes | Wrong shape | Shipped: `deploy/compose/` (combined Cloudflare-or-Caddy?) + `deploy/lan-only/`; plan called for three dirs `cloudflare-tunnel/` + `caddy/` + `lan/`, plus `Caddyfile`, plus per-dir `.env.example`. None of the per-dir `.env.example` files exist; no `Caddyfile` exists; `lan-only/docker-compose.yml` hardcodes `OPENLIA_MODE: company` (plan: `${OPENLIA_MODE:-personal}`) and forces `OPENLIA_COOKIE_SECURE: "false"` (plan: also default-overridable) |
| F — PyPI metadata | Partial | URLs/classifiers/keywords shipped; but `readme = "../../README.md"` resolves outside the package source tree, breaking wheel `Description` (uv_build wheel will not embed); per-package `packages/core/README.md` and `packages/server/README.md` absent; `test_wheel_contents.py` absent; `[tool.hatch.build.targets.wheel.force-include]` block in `core/pyproject.toml` is dead config (build-backend is `uv_build`, not hatchling) |
| G — Release workflow + CI Docker job | Partial | `release.yml` present and uses trusted publishing; PyPI step lacks an explicit token-presence gate (uses `skip-existing: true` instead — different semantics — succeeds on duplicate but still fails if trusted publisher unconfigured); CI `ci.yml` has NO Docker build job |
| H — `tests/smoke/` container suite | Absent | No `tests/` directory at repo root; no smoke conftest; `pyproject.toml` `testpaths` not updated |
| I — Docs / CHANGELOG / `RELEASING.md` | Partial | `CHANGELOG.md` exists with v0.1.0 entry; `RELEASING.md` absent; root `README.md` missing Docker quickstart, deploy table, RELEASING link |

**Container-runtime evidence:** No CI run has executed `docker build` or `docker run … curl /healthz` for this branch. `CHANGELOG.md` itself states: *"Container-runtime smoke (`docker run openlia:dev && curl /healthz`) has not yet been executed in CI."* (P0-10 unresolved.)

---

## Tasks (in execution order)

### 1. **P0-10 — Container-runtime smoke harness (REM-P1-019 residual)**
Build image, boot container, exercise `/healthz` + `/api/healthz` + `/` + invite flow + cookie/proxy propagation in BOTH modes.

- Files (new):
  - `tests/__init__.py` (empty)
  - `tests/smoke/__init__.py` (empty)
  - `tests/smoke/conftest.py` — pytest skipif gate on `SMOKE` env, `_free_port`, `_wait_for`, `run_container` fixture (`docker run -d --rm -p PORT:8000` + tear-down), `image_tag` fixture defaulting to `openlia:dev`.
  - `tests/smoke/test_personal_mode.py` — `test_healthz_returns_personal`, `test_api_prefix_accessible`, `test_spa_served_from_root` (asserts `<div id="root">` in response), `test_setup_wizard_reachable` (200 or 403).
  - `tests/smoke/test_company_mode.py` — `test_company_mode_end_to_end` (CLI `openlia admin invite create --json` → register → login → `/api/auth/me`; asserts UUID-36 invite_id), `test_cookie_secure_flag_propagates` (Secure + HttpOnly), `test_trust_proxy_headers_propagates` (X-Forwarded-For → `/_debug/client_host`).
- Files (edit):
  - `pyproject.toml` — extend `[tool.pytest.ini_options].testpaths` to `["packages/core/tests", "packages/server/tests", "tests"]`.
- Plan ref: Tasks 32–39, 45.
- Acceptance: `SMOKE=1 OPENLIA_IMAGE=openlia:dev uv run pytest tests/smoke/ -v` green; `uv run pytest tests/smoke/` (no SMOKE) reports "skipped" with reason "Set SMOKE=1 to run container smoke tests."

### 2. **P1-22 — Gate PyPI publish on token/trusted-publisher presence**
Current `release.yml` Python job calls `pypa/gh-action-pypi-publish@release/v1` unconditionally — first-ever release without trusted publisher config OIDC-fails.

- Files (edit):
  - `.github/workflows/release.yml` — split into two steps:
    1. `Check publish gate` (id: gate) sets `has_token=${{ secrets.PYPI_API_TOKEN != '' }}`.
    2. `Publish to PyPI (trusted publishing)` runs `if: steps.gate.outputs.has_token != 'true'` AND on tag (preserving id-token: write); fallback step `Skip PyPI` runs `if: steps.gate.outputs.has_token == 'true' && false` — actually, prefer plan's design: try-with-token first; if both unset, log "PyPI publish skipped" and exit 0.
  - Concretely match plan Task 28 lines 1616–1631: env-driven `HAS_TOKEN` output → gated `uv publish dist/*` with `UV_PUBLISH_TOKEN` else explicit skip-log step.
- Acceptance: simulate via `act` or trigger `workflow_dispatch` with no `PYPI_API_TOKEN` secret → workflow green, log shows "PYPI_API_TOKEN unset — artifacts built but not published."

### 3. **P1-23 — Fix `.dockerignore` re-allow list**
Plan re-allows `README.md` AND `CHANGELOG.md`; shipped only re-allows `README.md`. Risk: `pyproject.toml` `readme` resolution + GitHub Release `body_path: CHANGELOG.md` step in release workflow both depend on the file being present in build context.

- Files (edit):
  - `.dockerignore` — under the `*.md` block, add `!CHANGELOG.md` and `!LICENSE*` lines.
- Acceptance: `docker build -t openlia:dev . && docker run --rm openlia:dev ls /app/CHANGELOG.md` (or whatever path the COPY targets) succeeds; release workflow `body_path: CHANGELOG.md` resolves on the runner checkout (independent of dockerignore but the same fix proves the file is everywhere it needs to be).

### 4. **P1-24 — Re-shape `deploy/` to plan-canonical three-recipe layout**
Plan called for `cloudflare-tunnel/`, `caddy/`, `lan/`; shipped `compose/` (ambiguous mixed) + `lan-only/`. Master tracker line item: "LAN compose hardcodes company mode."

- Files (delete):
  - `deploy/compose/docker-compose.yml` (after content moved).
- Files (rename / new):
  - `deploy/cloudflare-tunnel/docker-compose.yml` — promote from `deploy/compose/` content; add `cloudflared` sidecar service with `TUNNEL_TOKEN` env, `depends_on: openlia: condition: service_healthy`. Per plan Task 19.
  - `deploy/caddy/docker-compose.yml` + `deploy/caddy/Caddyfile` — separate stack with `caddy:2` service binding 80/443, `OPENLIA_HOSTNAME` env, SSE flush block (`@sse path /api/chat/sessions/*/stream` + `path /api/departments/*/report` → `flush_interval -1`). Per plan Task 20.
  - `deploy/lan/docker-compose.yml` (rename from `deploy/lan-only/`); change `OPENLIA_MODE: company` → `OPENLIA_MODE: ${OPENLIA_MODE:-personal}`; expose `8080:8000` per plan; keep `OPENLIA_COOKIE_SECURE: "false"`. Per plan Task 21.
  - `deploy/cloudflare-tunnel/.env.example`, `deploy/caddy/.env.example`, `deploy/lan/.env.example` per plan Task 23.
- Files (edit):
  - `deploy/README.md` — rewrite per plan Task 22 (table with three rows, common flow, required secrets including `OPENLIA_SECRET_KEY` generation snippet, Cloudflare Tunnel setup notes, Caddy DNS prereq, LAN firewall warning, ops/backup/upgrade/admin-CLI section).
- Acceptance: 
  - `docker compose -f deploy/cloudflare-tunnel/docker-compose.yml config >/dev/null` exits 0.
  - `docker compose -f deploy/caddy/docker-compose.yml config >/dev/null` exits 0.
  - `docker compose -f deploy/lan/docker-compose.yml config >/dev/null` exits 0.
  - `docker run --rm -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` exits 0.
  - `OPENLIA_MODE=company docker compose -f deploy/lan/docker-compose.yml config | grep OPENLIA_MODE` shows `company`; default resolution shows `personal`.

### 5. **NEW-23-01 — Fix per-package `readme` resolution + create per-package READMEs**
`packages/core/pyproject.toml` and `packages/server/pyproject.toml` both set `readme = "../../README.md"`. uv_build (PEP 517) builds a wheel from each package's source tree; PyPI metadata's `Description` comes from a file inside the sdist. A relative `../../` path escapes the sdist root and produces an empty/invalid description on PyPI.

- Files (new):
  - `packages/core/README.md` — per plan Task 24 final block (4-line description, `pip install openlia`, link to main repo, MIT).
  - `packages/server/README.md` — per plan Task 25 final block.
- Files (edit):
  - `packages/core/pyproject.toml` — change `readme = "../../README.md"` to `readme = "README.md"`; remove the dead `[tool.hatch.build.targets.wheel.force-include]` block (build-backend is `uv_build`, not hatchling — that block is silently ignored).
  - `packages/server/pyproject.toml` — change `readme = "../../README.md"` to `readme = "README.md"`.
- Acceptance: `uv build --package openlia-core && uv build --package openlia` both succeed; `python -c "import zipfile; z = zipfile.ZipFile('dist/openlia-0.1.0-py3-none-any.whl'); print([n for n in z.namelist() if 'METADATA' in n])"` and inspect METADATA has full description text.

### 6. **NEW-23-02 — Write `RELEASING.md`**
- Files (new):
  - `RELEASING.md` at repo root — version-scheme block, pre-flight (versions in both pyprojects must match, `uv.lock` regen, aggregate sanity), CHANGELOG section format, tag+push commands, release workflow side-effects (GHCR multi-arch tags `0.1.0`/`0.1`/`0`/`latest`, `uv build --all-packages` → PyPI gated → GitHub Release auto-notes), post-release verification (`docker pull` + `pip install`), rolling a broken release (PyPI yank, GHCR tag delete, hotfix tag).
- Plan ref: Task 30.
- Acceptance: file exists; root `README.md` Docs section links to it (see NEW-23-06).

### 7. **NEW-23-03 — Add "Docker image builds" smoke job to `ci.yml`**
- Files (edit):
  - `.github/workflows/ci.yml` — append a third job `docker:` with `needs: [python, frontend]`, runs `docker/setup-buildx-action@v3` + `docker/build-push-action@v6` (push:false, tag `openlia:ci`, gha cache), then `docker run -d --name openlia-ci -p 8000:8000 openlia:ci` + 30-iteration `for i in $(seq 1 30); do curl -fsS /healthz && exit 0; sleep 1; done`, with `docker logs openlia-ci` on failure and `docker rm -f openlia-ci` cleanup.
- Plan ref: Task 29.
- Acceptance: PR check "Docker image builds" green on next PR; failure mode logs container output.

### 8. **NEW-23-04 — `test_wheel_contents.py` (locks installable surface)**
- Files (new):
  - `packages/server/tests/test_wheel_contents.py` per plan Task 26: `_build_wheel()` runs `uv build --package openlia` from `REPO_ROOT`, then asserts wheel contains `openlia_server/`, NO `planning/`, NO `/tests/`, NO `.venv/`, AND entry-point `openlia = openlia_server.cli:main` registered in `entry_points.txt`.
  - `packages/core/tests/test_wheel_contents.py` — sibling for openlia-core package: asserts `openlia/prompts/`, `openlia/reports/frameworks/` (since plan ships YAML/JSON resources), and NO `tests/`/`planning/`.
- Plan ref: Task 26.
- Acceptance: `uv run pytest packages/server/tests/test_wheel_contents.py packages/core/tests/test_wheel_contents.py -v` green.

### 9. **NEW-23-05 — Cookie/proxy integration tests + production env fixture**
Plan B group 6–9 partially shipped. Add the missing three:

- Files (new):
  - `packages/server/tests/test_cookie_secure.py` per plan Task 6: three tests (`personal_mode_default`, `company_mode_default`, `override_off`) seeding a `User` + `SignupPolicy`, posting `/auth/login`, asserting `Secure` flag presence/absence on `set-cookie`.
  - `packages/server/tests/test_proxy_and_cookie_integration.py` per plan Task 8: `test_company_mode_behind_tls_proxy` — sets `OPENLIA_TRUST_PROXY_HEADERS=true` + `OPENLIA_COOKIE_SECURE=true` + `OPENLIA_MODE=company`, posts to `/api/auth/login` (tests `/api` strip), asserts both `Secure` AND `HttpOnly` in response cookie.
  - `packages/server/tests/fixtures/production_env.yaml` per plan Task 9: keys `OPENLIA_MODE`, `OPENLIA_DB_URL`, `OPENLIA_FRONTEND_DIST`, `OPENLIA_TRUST_PROXY_HEADERS`, `OPENLIA_COOKIE_SECURE`, `OPENLIA_SCHEDULER_ENABLED`.
  - `packages/server/tests/test_production_env_snapshot.py` — loads YAML, asserts the six required keys are a subset of `data.keys()`.
- Plan ref: Tasks 6–9.
- Acceptance: `uv run pytest packages/server/tests/ -k "cookie or proxy or env_snapshot"` green.

### 10. **NEW-23-06 — Rewrite root `README.md` Quickstart + Docs section**
- Files (edit):
  - `README.md` — replace current 33-line stub. Add:
    - "Quickstart" with three sub-sections: Docker (`docker run -d -p 8000:8000 -v openlia_data:/home/openlia/.openlia ghcr.io/TK-Chang239/openlia:latest`), PyPI (`pip install openlia && openlia serve`), From source (uv sync + npm dev).
    - "Deployment recipes" table (cloudflare-tunnel / caddy / lan rows).
    - "Docs" section linking `deploy/README.md`, `RELEASING.md`, `CHANGELOG.md`, `planning/`.
  - `CHANGELOG.md` — promote `[Unreleased]` block to a `[0.1.0] — 2026-04-XX` block once tag cuts; for the audit fix, leave Unreleased and ensure all Phase 23 line items are documented (Docker image, three deploy recipes, OPENLIA_TRUST_PROXY_HEADERS + OPENLIA_COOKIE_SECURE wiring, `/api` prefix stripping, GHCR + gated PyPI release, container smoke suite).
- Plan ref: Tasks 40, 41, 31.
- Acceptance: `grep -F "ghcr.io/TK-Chang239/openlia" README.md` exits 0; `grep -F "RELEASING.md" README.md` exits 0; `grep -F "container smoke" CHANGELOG.md` exits 0.

### 11. **NEW-23-07 — Frontend production build smoke vitests**
Plan group D Tasks 16 + 18 shipped only as plan text; no test file confirmed. Lock frontend assumption that `/api/...` calls never embed an absolute URL, and that Vite build output references hashed bundles.

- Files (new):
  - `frontend/src/api/__tests__/prodBase.test.ts` per plan Task 16: walks `frontend/src/api/**/*.{ts,tsx}` and asserts no source contains `'https?://[host]/api'` literal.
  - `frontend/src/api/__tests__/buildOutput.test.ts` per plan Task 18: skipIf `dist/index.html` missing; otherwise asserts `/assets/index-<hash>.js` reference and `<div id="root">` marker.
- Plan ref: Tasks 16, 18.
- Acceptance: `cd frontend && npm test -- --run prodBase buildOutput` exits 0 (the build-output test skips if dist absent — fine for dev runs).

### 12. **NEW-23-08 — CLI `--json` flag for admin invite create**
Smoke suite (Task 1) depends on `openlia admin invite create --email … --role … --json` producing `{"token":..., "invite_id":...}`. Verify the flag exists; if absent, add it.

- Files (verify; edit only if missing):
  - `packages/server/src/openlia_server/cli.py` — admin invite-create subcommand: add `json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON.")`; on True, `typer.echo(json.dumps({"invite_id": invite.id, "token": invite.token}))` and skip the human-readable rendering.
  - `packages/server/tests/test_cli/test_admin_invite.py` — assert `--json` output is parseable, contains UUID-36 `invite_id` and non-empty `token`.
- Plan ref: Task 35.
- Acceptance: `uv run openlia admin invite create --email t@e.com --role user --json | python -m json.tool` exits 0.

### 13. **NEW-23-09 — Wire `OPENLIA_HOST` / `OPENLIA_PORT` env binding for `openlia serve`**
Old audit Finding 7 (still present): `cli.py:75-92` reads `OPENLIA_HOST` / `OPENLIA_PORT` env vars but Typer Option defaults are `None` — runtime binding works only if the user passes the flag. Verify behavior, write a test.

- Files (verify):
  - `packages/server/src/openlia_server/cli.py` — confirm fallback chain: flag → env → hardcoded default per mode (127.0.0.1 personal / 0.0.0.0 company).
- Files (new):
  - `packages/server/tests/test_cli/test_serve_env_binding.py` — invokes `cli serve --help` for the contract; second test stubs uvicorn.run and asserts `host` arg = env value when only env set.
- Acceptance: setting `OPENLIA_HOST=0.0.0.0 OPENLIA_PORT=9000 openlia serve` (mocked) passes through to uvicorn correctly.

### 14. **NEW-23-10 — Migration runner verification on container start**
Plan Locked-Contract #6 says secret-key bootstrap; `deploy/README.md` says "Alembic runs on startup via `openlia serve`". Verify `app.py` lifespan or `cli.py:serve` actually calls `alembic upgrade head` (or equivalent) before uvicorn binds. If absent, add it.

- Files (verify):
  - `packages/server/src/openlia_server/app.py` lifespan / `cli.py:serve` — confirm DB migrations run before serving.
- Files (new test):
  - `packages/server/tests/test_app_migration_on_start.py` — boots app against an empty SQLite file in `tmp_path`, asserts schema is at head after `create_app()` (i.e. queries `alembic_version` table for the latest revision id from `packages/server/src/openlia_server/db/migrations/versions/`).
- Files (smoke addition):
  - `tests/smoke/test_personal_mode.py::test_fresh_volume_migrates` — start container with empty named volume, assert `/healthz` returns 200 within 30 s (proves migrations ran without crashing).
- Acceptance: smoke test green; unit test green.

### 15. **NEW-23-11 — Final acceptance one-shot script**
Plan Task 47 specifies a single `set -e` shell block running every gate (lint, format, pytest, frontend lint/test/build, docker build, smoke, compose validate ×3, Caddyfile validate, `uv build --all-packages`, throwaway venv install, `openlia --help`). Capture as a checked-in script for reproducibility.

- Files (new):
  - `scripts/acceptance.sh` — exact shell block from plan Tasks 47–48 (parametrized on `IMAGE=${IMAGE:-openlia:gate}`).
  - `scripts/README.md` — document `bash scripts/acceptance.sh` as the merge-gate command.
- Acceptance: `bash scripts/acceptance.sh` exits 0 on a clean checkout (long-running ~10 min; not in CI by default — runs in NEW-23-03 Docker job + nightly).

### 16. **NEW-23-12 — Lint cleanup of dead `[tool.hatch.build]` block in core pyproject**
Discovered while inspecting NEW-23-01: `packages/core/pyproject.toml` lines 51–53 contain a `[tool.hatch.build.targets.wheel.force-include]` block targeting `src/openlia/prompts` and `src/openlia/reports/frameworks`. Build-backend is `uv_build`. The block is silently ignored — and worse, hides whether prompts/frameworks resources actually ship in the wheel. uv_build has its own `[tool.uv.build-backend]` mechanism; verify those resources are included via a `MANIFEST.in`-equivalent or explicit `[tool.uv.build-backend.source-include]`.

- Files (edit):
  - `packages/core/pyproject.toml` — delete dead hatch block; add `[tool.uv.build-backend]` `source-include = ["src/openlia/prompts/**/*.yaml", "src/openlia/reports/frameworks/**/*"]` (verify exact uv_build syntax against current `uv` 0.11 docs).
- Files (NEW-23-04 verification):
  - `packages/core/tests/test_wheel_contents.py` — assert `openlia/prompts/secretary.yaml` (or similar canonical resource) IS in the wheel.
- Acceptance: `python -c "import zipfile; print([n for n in zipfile.ZipFile('dist/openlia_core-0.1.0-py3-none-any.whl').namelist() if 'prompts' in n])"` shows YAML files.

---

## Verification (one shot)

```bash
# Group A+B+E+F+I unit/integration coverage
uv run ruff check . && uv run ruff format --check .
uv run pytest packages/server/tests/ packages/core/tests/ -q

# Container smoke (P0-10)
docker build -t openlia:dev .
SMOKE=1 OPENLIA_IMAGE=openlia:dev uv run pytest tests/smoke/ -v

# Compose recipes
docker compose -f deploy/cloudflare-tunnel/docker-compose.yml config >/dev/null
docker compose -f deploy/caddy/docker-compose.yml config >/dev/null
docker compose -f deploy/lan/docker-compose.yml config >/dev/null
docker run --rm -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2 \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

# PyPI dry-run
uv build --all-packages
python -m venv /tmp/openlia-gate-venv
/tmp/openlia-gate-venv/bin/pip install dist/openlia_core-*.whl dist/openlia-*.whl
/tmp/openlia-gate-venv/bin/openlia --help

# Release workflow shape
gh workflow view release.yml | grep -E "PYPI_API_TOKEN|trusted publishing|skip"

# Docs link sanity
grep -F "ghcr.io/TK-Chang239/openlia" README.md
grep -F "RELEASING.md" README.md
test -f RELEASING.md && test -f deploy/cloudflare-tunnel/.env.example
```

Every line must exit 0.

---

## ID cross-reference

| ID | Source | Title |
|---|---|---|
| P0-10 | Master tracker | Container-runtime smoke (REM-P1-019 residual) |
| P1-22 | Master tracker | Gate PyPI publish on token presence |
| P1-23 | Master tracker | Fix `.dockerignore` re-allow list |
| P1-24 | Master tracker | LAN compose hardcoded mode |
| NEW-23-01 | Audit | Per-package README + readme path fix |
| NEW-23-02 | Audit | RELEASING.md |
| NEW-23-03 | Audit | CI Docker build job |
| NEW-23-04 | Audit | Wheel-contents tests |
| NEW-23-05 | Audit | Cookie/proxy integration + env fixture |
| NEW-23-06 | Audit | README rewrite + CHANGELOG refresh |
| NEW-23-07 | Audit | Frontend prod build vitests |
| NEW-23-08 | Audit | CLI `--json` admin invite |
| NEW-23-09 | Audit | OPENLIA_HOST/PORT env binding |
| NEW-23-10 | Audit | Migration-on-start verification |
| NEW-23-11 | Audit | scripts/acceptance.sh |
| NEW-23-12 | Audit | core pyproject hatch-block cleanup |
