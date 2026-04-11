# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

OpenLia is an open-source, self-hosted AI investor assistant. It uses multiple specialized LLM agents called **Departments** (Secretary, Stock Research, Earnings Report, Morning Briefing, Retail Sentiment, Macro Research), each focused on a single financial domain.

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
- `packages/core/` must never import FastAPI, uvicorn, or anything HTTP-related. Test: `from openlia import StockResearchDepartment` must work with only `openlia-core` installed, no server running.
- Route handlers in `packages/server/` call core methods and return results. Business logic belongs in core, not routes.
- Frontend communicates only through the server's REST API.
- Config flows one direction: `.env`/env vars → `core/config.py` → server passes to core at startup. Frontend never touches config directly.

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
│   │       ├── config.py       # Config loader
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

**Debugging process (always follow these 5 steps):**
1. Reproduce the problem
2. Prove you reproduced it
3. Find the root cause
4. Fix it
5. Prove you fixed it

## Spec Files

Before implementing any feature, read the relevant spec in `planning/specs/`. Specs define the purpose, behavior, and UI design for each page and utility tool. They are the source of truth for what to build.

## Planning Docs

`planning/PLAN.md` — full architecture description, deployment modes, data sources, installation.
`planning/projectStructure.md` — detailed directory layout with key design rules.
`planning/specs/pages/` — per-page UI and feature specs.
`planning/specs/UtilityTools/` — specs for sidebar, chat history, file viewer, etc.

Planning docs are excluded from Python package builds and Docker images.
