# Changelog

All notable changes to OpenLIA are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Report retention.** Reports not saved to the Repository are now
  automatically expired 7 days after generation. Saved reports persist
  indefinitely until manually deleted. Expired and manually-deleted reports
  leave a "no longer available" tombstone in the originating chat artifact
  card so conversation history stays intact; they no longer surface in the
  Repository or other department listings. The retention window is
  configurable via the `OPENLIA_UNSAVED_REPORT_RETENTION_DAYS` env var
  (default `7`). `DELETE /reports/{id}` now tombstones rather than dropping
  the row; export endpoints return **410 Gone** on tombstoned reports.
  **Migration note:** the first nightly sweep after deploying will
  tombstone any pre-existing reports already past the retention window.

### Added
- Morning Briefing follow-up Q&A: the shared `ChatInterface` + `ReportThumbnail`
  are wired into the MB page with a side-by-side viewer and a dedicated Chat
  tab (Phase 16 deferred gap closed).
- `OnDemandBriefingButton` now streams via the shared `useReportStream` hook.
- Release workflow (`.github/workflows/release.yml`): on `v*.*.*` tag, builds
  and pushes the Docker image to GHCR (amd64 + arm64) and publishes
  `openlia-core` + `openlia` wheels to PyPI via trusted publishing, then
  creates a GitHub Release with generated notes. PyPI publish is gated on
  `PYPI_API_TOKEN` presence; without the token, wheels build and the workflow
  logs a skip line instead of failing.
- PyPI metadata: `[project.urls]`, classifiers, keywords, and `readme` added
  to both `openlia-core` and `openlia`. Per-package `README.md` files now
  ship inside each wheel so PyPI's project description is populated.
- `[tool.uv.build-backend].source-include` in `packages/core/pyproject.toml`
  explicitly ships `openlia/prompts/**/*.yaml` and
  `openlia/reports/frameworks/**/*` resources in the wheel.
- Three Docker deployment recipes under `deploy/`: `cloudflare-tunnel/`
  (cloudflared sidecar), `caddy/` (automatic Let's Encrypt + SSE flush
  block), and `lan/` (HTTP on port 8080, mode-toggleable). Each ships a
  per-recipe `.env.example`.
- `OPENLIA_TRUST_PROXY_HEADERS` + `OPENLIA_COOKIE_SECURE` env wiring
  documented in `deploy/README.md` plus `tests/fixtures/production_env.yaml`
  snapshot pinned via `test_production_env_snapshot.py`.
- Cookie/proxy integration coverage: `test_cookie_secure.py` (3-case mode
  matrix) + `test_proxy_and_cookie_integration.py` (company-mode behind
  TLS proxy with /api strip).
- `/api` prefix stripping middleware verified in production via
  `test_api_prefix_strip.py`; reverse-proxy configs forward `/api/*`
  untouched.
- `openlia admin create-invite --json` flag emits machine-readable
  `{invite_id, token, url}` JSON for scripting and the smoke harness.
- Wheel-contents tests (`test_wheel_contents.py` in both packages) lock the
  installable surface: server wheel ships `openlia_server/` + `openlia`
  console script; core wheel ships `openlia/prompts/*.yaml` +
  `openlia/reports/frameworks/`. Neither ships `tests/`, `planning/`, or
  `.venv/`.
- Frontend production build vitests: `prodBase.test.ts` asserts no
  `https?://host/api` literal escapes into source; `buildOutput.test.ts`
  asserts the Vite build emits a hashed bundle reference and the SPA mount
  point. `buildOutput` skips when `dist/` is absent.
- Container-runtime smoke harness under `tests/smoke/` (P0-10 closed):
  `test_personal_mode.py` and `test_company_mode.py` boot a real Docker
  container, exercise `/healthz` + `/api` prefix + SPA + setup wizard +
  invite/register/login flow + cookie/proxy header propagation. Skips
  cleanly without `SMOKE=1`.
- CI Docker build job (`.github/workflows/ci.yml::docker`) builds the image
  via `docker/build-push-action` (gha cache), runs the container, polls
  `/healthz` for 30s, and dumps `docker logs` on failure.
- `RELEASING.md` documents version scheme, pre-flight, tag/push, workflow
  side-effects, post-release verification, and rolling a broken release.
- `scripts/acceptance.sh` runs the full local merge-gate (lint, format,
  pytest, frontend lint/test/build, docker build, smoke, compose validate
  ×3, Caddyfile validate, `uv build --all-packages`, throwaway venv
  install, `openlia --help`).
- Root `README.md` rewritten with Docker / PyPI / from-source quickstarts
  plus a deployment recipes table and a Docs section linking
  `deploy/README.md`, `RELEASING.md`, `CHANGELOG.md`, and `planning/`.

### Changed
- `deploy/lan/docker-compose.yml` (renamed from `deploy/lan-only/`) now
  exposes `8080:8000` and defaults `OPENLIA_MODE` to `personal`,
  overridable via `.env`.
- `.dockerignore` re-allows `CHANGELOG.md` and `LICENSE*` in addition to
  `README.md` so wheel/release tooling can find them in the build context.
- `packages/core/pyproject.toml` and `packages/server/pyproject.toml`:
  `readme = "../../README.md"` → `readme = "README.md"` (relative paths
  outside the package source tree are not embedded by `uv_build`). Dead
  `[tool.hatch.build.targets.wheel.force-include]` block removed from
  `core/pyproject.toml` (build-backend is `uv_build`, not hatchling).

## [0.1.0] — 2026-04-24

Initial pre-release. Feature-complete backend + frontend; Docker image
defined but not yet run through a container-boot smoke test.

### Added
- **Core package** (`openlia-core`): pure-Python library with seven
  Department agents (Secretary, Equity Research, Earnings Update, Morning
  Briefing, Retail Sentiment, Macro Research, Panic Thermometer), LLM
  adapters (OpenAI, Anthropic, OpenRouter, Ollama), data adapters (EODHD,
  news), YAML prompt templates, and schema-first report generation.
- **Server package** (`openlia`): FastAPI app, Typer CLI (`openlia serve`),
  SQLAlchemy + Alembic persistence (23 migrations), auth/rate-limit
  middleware, per-department routers, SSE report streams, chat sessions,
  repo/report save surfaces, Playwright-based PDF export.
- **Frontend**: React + TypeScript + Vite SPA with one page per Department,
  shared `ChatInterface`, report renderer, portfolio, repository, settings,
  and setup wizard. 419 Vitest cases; ~1400 backend pytest cases.
- **Dalio Macro Research dashboards**: Summary, Debt Cycle, Four Seasons,
  All Weather, World Order, Five Forces (Phase 19 frontend, 2026-04-24).
- **E2E product-journey smoke matrix** (REM-P1-019, 2026-04-24): six
  personal/company journeys cover setup, invite → login, provider CRUD,
  password reset + must-change-password gate, and repo save/open/unsave.
- **Design system refresh** (Phase 24): Wondermakers / Acid Yellow brand
  tokens and component migration.
- **Deployment artifacts**: multi-stage `Dockerfile` (Node build → Python
  runtime with Playwright Chromium), two `docker-compose` recipes under
  `deploy/` (lan-only, Cloudflare Tunnel / Caddy), healthcheck on
  `/healthz`.

### Known gaps at 0.1.0

- Container-runtime smoke (`docker run openlia:dev && curl /healthz`) has
  not yet been executed in CI.
- Phase 20 Retail Sentiment ships metric snapshots directly; the documented
  NLP classification pass + `rs_classification_log` table are deferred.
- Some P3 polish items (atomic component refactors, URL-synced filter
  hooks, Chart.js drill-downs) are tracked in
  `planning/deferred-tasks-2026-04-24.md`.

[Unreleased]: https://github.com/TK-Chang239/OpenLIA/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/TK-Chang239/OpenLIA/releases/tag/v0.1.0
