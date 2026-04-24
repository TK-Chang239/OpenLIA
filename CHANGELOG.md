# Changelog

All notable changes to OpenLIA are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Morning Briefing follow-up Q&A: the shared `ChatInterface` + `ReportThumbnail`
  are wired into the MB page with a side-by-side viewer and a dedicated Chat
  tab (Phase 16 deferred gap closed).
- `OnDemandBriefingButton` now streams via the shared `useReportStream` hook.
- Release workflow (`.github/workflows/release.yml`): on `v*.*.*` tag, builds
  and pushes the Docker image to GHCR (amd64 + arm64) and publishes
  `openlia-core` + `openlia` wheels to PyPI via trusted publishing, then
  creates a GitHub Release with generated notes.
- PyPI metadata: `[project.urls]`, classifiers, keywords, and `readme` added
  to both `openlia-core` and `openlia`.

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
