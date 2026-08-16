# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

OpenLia is an open-source, self-hosted AI investor assistant. It uses multiple specialized LLM agents called **Departments** (Secretary, Equity Research, Earnings Update, Morning Briefing, Retail Sentiment, Macro Research, Panic Thermometer), each focused on a single financial domain.

Two deployment modes from the same codebase: **personal** (single user, localhost, no auth) and **company** (multi-user, network-accessible, auth enabled).

## Architecture: Three Layers

```
core (openlia-core)   -- pure Python, zero web dependencies
  ^
server (openlia)      -- FastAPI wrapper, exposes core over HTTP + SSE
  ^
frontend              -- React/TypeScript/Vite, talks to server via REST + SSE
```

**Boundary rules (enforce strictly):**
- `packages/core/` must never import FastAPI, uvicorn, or anything HTTP-related. Test: `from openlia import EquityResearchDepartment` must work with only `openlia-core` installed, no server running.
- Route handlers in `packages/server/` call core methods and return results. Business logic belongs in core, not routes.
- Frontend communicates only through the server's REST API.
- Config flows one direction: `.env`/env vars are loaded at startup by the server CLI (`packages/server/src/openlia_server/cli.py`, via python-dotenv) and read from `os.environ` where needed; the server passes config to core at startup. (`core/config.py` is a reserved placeholder stub, not an active loader.) Frontend never touches config directly.

## Project Structure

```
openlia/
├── packages/
│   ├── core/               # Package: openlia-core (library layer)
│   │   └── src/openlia/
│   │       ├── departments/    # One file per department + base.py
│   │       ├── llm/            # Provider adapters (openai, anthropic, openrouter, ollama)
│   │       ├── data/           # Data source adapters (eodhd, news)
│   │       ├── prompts/        # YAML prompt templates per department
│   │       ├── reports/        # Report generation + templates
│   │       ├── config.py       # Reserved placeholder stub (not an active loader; .env is loaded by server cli.py)
│   │       └── exceptions.py
│   └── server/             # Package: openlia (server + CLI)
│       └── src/openlia_server/
│           ├── app.py          # FastAPI app factory
│           ├── cli.py          # `openlia serve` CLI entry point
│           ├── routes/         # departments, portfolio, reports, auth, settings
│           ├── middleware/     # auth (toggleable), rate_limit
│           ├── db/             # SQLAlchemy models, Alembic migrations, session
│           └── services/       # Business logic between routes and core
├── frontend/               # React/TypeScript/Vite (not a Python package)
│   └── src/
│       ├── pages/          # One page per department + Portfolio, Repo, Settings, SetupWizard
│       ├── components/     # Sidebar, ChatWindow, FileViewer, ReportThumbnail, ...
│       ├── api/            # API client wrappers
│       └── styles/
├── planning/               # Specs, master plan, logs (not shipped)
│   ├── PLAN.md             # Full architecture and feature descriptions
│   ├── specs/              # Per-feature spec files (read before implementing)
│   └── projectStructure.md # Detailed directory layout with design rules
├── pyproject.toml          # uv workspace root (not an installable package)
├── ruff.toml               # Shared lint/format config
└── .github/workflows/ci.yml
```

## Commands

**Package management — always use `uv`, never `pip`:**
```bash
uv add <package>                          # add dependency
uv run <command>                          # run in project environment
```

**Linting and formatting:**
```bash
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run ruff check --fix .                 # lint + autofix
```

**Tests:**
```bash
uv run pytest                             # run all tests
uv run pytest packages/core/tests/        # run core tests only
uv run pytest packages/server/tests/      # run server tests only
uv run pytest -k "test_name"              # run a single test
```

**Run the server (development):**
```bash
uv run openlia serve                      # starts on localhost:8000
```

**Frontend (development):**
```bash
cd frontend && npm install
npm run dev                               # Vite dev server with proxy to FastAPI
npm run build                             # build static files for production
```

## Coding Standards

1. Use `uv` for all package management (`uv add`, `uv run`).
2. Use `ruff` for all formatting and linting.
3. Use modern, strict Python type hints on all function signatures.
4. Fail fast and loudly — raise specific exceptions with context, never swallow errors.
5. Keep it simple. No over-engineering, no unnecessary defensive programming, no extra features.
6. No emojis anywhere.
7. Aim for ~80% test coverage but it is not a hard requirement — only build necessary tests.
8. When something is ambiguous, ask for clarification instead of guessing.
9. If implementation diverges from implementation plan, update the plan to reflect the new version.
10. From now on, unless explicitly asked to explain in detail, remove all filler words. No 'the', 'is', 'am', 'are'. Direct answer only. Use short 3-6 word sentences. Run tools first, show the result, then stop. Do not narrate. Example: Instead 'The solution is to use async', say 'Use async'."

**Debugging process (always follow these 5 steps):**
1. Reproduce the problem
2. Prove you reproduced it
3. Find the root cause
4. Fix it
5. Prove you fixed it

## Spec Files

Before implementing any feature, read the relevant spec in `planning/specs/`. Specs define the purpose, behavior, and UI design for each page and utility tool. They are the source of truth for what to build.

## Planning Docs

**Start at `planning/README.md`** — it's the entry-point index that tells you which docs to read for the task you're doing and in what order.

`planning/PLAN.md` — full architecture description, deployment modes, data sources, installation.
`planning/projectStructure.md` — detailed directory layout with key design rules.
`planning/specs/pages/` — per-page UI and feature specs.
`planning/specs/components/` — specs for shared components (sidebar, chat interface, file viewer, etc.).
`planning/specs/systems/` — cross-cutting system design specs (data provider, report rendering, macro research dashboards).

Planning docs are excluded from Python package builds and Docker images.

## Equity Research Engine

**v3 (`report_v3`) is the sole equity-research engine**, served at `/equity-research`. The legacy v1, v2, v2.2, and v2.3 engines were removed (PRs #220/#222); do not reintroduce or reference them.

- **Core:** `packages/core/src/openlia/llm/runtime/report_v3/` — a single-model tool-use loop (one LLM session, one tool loop, one final emit). It reuses shared library submodules from `report_v2_3/` (`schemas`, `research/`, `templates/`) — those are kept **only** as a shared library for v3 and Earnings Update; the rest of `report_v2_3` (its pipeline engine) is gone. Earnings Update v2 (`report_eu/`) is a fork of v3.
- **Server:** `routes/departments/equity_research_v3.py` + `services/v3_*`. The engine is always on (the old `REPORT_ENGINE_VERSION` gate is retired). DB tables: `report_v3*`.
- **Frontend:** `pages/departments/EquityResearchV3.tsx` + `components/equity-research-v3/`. The shared `ErComposer` / `WelcomeStage` live under `components/equity-research/`.
- The generic `runtime/report.py` / `subagent_runner.py` / `reports/` engine and the v1 `reports` table are **not** equity-specific — Morning Briefing and the legacy earnings_update route still use them. Keep them.
