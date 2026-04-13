# OpenLia - Project Directory Structure

```
openlia/
├── pyproject.toml              # Root workspace config (uv workspace)
├── uv.lock                     # Shared lockfile (auto-generated)
├── .env.example                # Template for API keys and config
├── .gitignore
├── LICENSE
├── README.md
├── Dockerfile
├── docker-compose.yml
│
│
│   ============================================================
│   PACKAGES - Installable Python packages (the three layers)
│   ============================================================
│
├── packages/
│   │
│   │   --------------------------------------------------------
│   │   CORE - The library layer (pure Python, no web deps)
│   │   `pip install openlia-core` installs this package alone
│   │   `pip install openlia` installs this + server
│   │   --------------------------------------------------------
│   │
│   ├── core/
│   │   ├── pyproject.toml          # Package: "openlia-core"
│   │   ├── src/
│   │   │   └── openlia/
│   │   │       ├── __init__.py
│   │   │       │
│   │   │       ├── departments/            # All department agents
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py             # Base department class
│   │   │       │   ├── secretary.py
│   │   │       │   ├── equity_research.py
│   │   │       │   ├── earnings_update.py
│   │   │       │   ├── morning_briefing.py
│   │   │       │   ├── retail_sentiment.py
│   │   │       │   └── macro_research.py
│   │   │       │
│   │   │       ├── llm/                    # LLM abstraction layer
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py             # Abstract LLM interface
│   │   │       │   ├── openai.py           # OpenAI adapter
│   │   │       │   ├── anthropic.py        # Anthropic adapter
│   │   │       │   ├── openrouter.py       # OpenRouter adapter
│   │   │       │   └── ollama.py           # Local model adapter
│   │   │       │
│   │   │       ├── data/                   # Data source adapters
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py             # Abstract data interface
│   │   │       │   ├── eodhd.py            # EODHD adapter
│   │   │       │   └── news.py             # News API adapter
│   │   │       │
│   │   │       ├── prompts/                # Prompt templates (YAML)
│   │   │       │   ├── secretary.yaml
│   │   │       │   ├── equity_research.yaml
│   │   │       │   ├── earnings_update.yaml
│   │   │       │   ├── morning_briefing.yaml
│   │   │       │   ├── retail_sentiment.yaml
│   │   │       │   └── macro_research.yaml
│   │   │       │
│   │   │       ├── reports/                # Report generation
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py             # Base report class
│   │   │       │   └── templates/          # Report templates
│   │   │       │
│   │   │       ├── config.py               # Config loader (.env / env vars)
│   │   │       └── exceptions.py           # Custom exceptions
│   │   │
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_departments/
│   │       ├── test_llm/
│   │       └── test_data/
│   │
│   │   --------------------------------------------------------
│   │   SERVER - The FastAPI server layer
│   │   Depends on core. Handles HTTP, auth, sessions, storage.
│   │   --------------------------------------------------------
│   │
│   └── server/
│       ├── pyproject.toml          # Package: "openlia" (includes CLI)
│       ├── src/
│       │   └── openlia_server/
│       │       ├── __init__.py
│       │       ├── app.py              # FastAPI app factory
│       │       ├── cli.py              # `openlia serve` CLI entry point
│       │       │
│       │       ├── routes/             # API endpoints
│       │       │   ├── __init__.py
│       │       │   ├── departments.py  # Department chat endpoints
│       │       │   ├── portfolio.py    # Portfolio CRUD
│       │       │   ├── reports.py      # Report storage/retrieval
│       │       │   ├── auth.py         # Auth endpoints (login, etc.)
│       │       │   └── settings.py     # Settings + setup wizard API
│       │       │
│       │       ├── middleware/         # Request processing
│       │       │   ├── __init__.py
│       │       │   ├── auth.py         # Auth middleware (toggle on/off)
│       │       │   └── rate_limit.py   # Rate limiting for shared mode
│       │       │
│       │       ├── db/                 # Database layer
│       │       │   ├── __init__.py
│       │       │   ├── models.py       # SQLAlchemy/SQLite models
│       │       │   ├── migrations/     # Alembic migrations
│       │       │   └── session.py      # DB session management
│       │       │
│       │       └── services/           # Business logic between routes and core
│       │           ├── __init__.py
│       │           ├── chat.py         # Chat history management
│       │           ├── portfolio.py    # Portfolio service
│       │           └── repository.py   # Report repository service
│       │
│       └── tests/
│           ├── __init__.py
│           ├── test_routes/
│           └── test_middleware/
│
│
│   ============================================================
│   FRONTEND - React web UI (not a Python package)
│   ============================================================
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       │
│       ├── pages/                  # One page per department + other pages
│       │   ├── SecretaryPage.tsx
│       │   ├── StockResearchPage.tsx
│       │   ├── EarningsUpdatePage.tsx
│       │   ├── MorningBriefingPage.tsx
│       │   ├── RetailSentimentPage.tsx
│       │   ├── MacroResearchPage.tsx
│       │   ├── PortfolioPage.tsx
│       │   ├── RepositoryPage.tsx
│       │   ├── SettingsPage.tsx
│       │   └── SetupWizardPage.tsx
│       │
│       ├── components/             # Shared UI components
│       │   ├── Sidebar.tsx
│       │   ├── ChatWindow.tsx
│       │   ├── FileViewer.tsx
│       │   ├── ReportThumbnail.tsx
│       │   └── ...
│       │
│       ├── api/                    # API client (axios/fetch wrappers)
│       │   └── client.ts
│       │
│       └── styles/
│
│
│   ============================================================
│   PLANNING - Specs, plans, and project management docs
│   ============================================================
│
├── planning/
│   ├── PLAN.md                     # Master plan (this document)
│   │
│   ├── specs/
│   │   ├── pages/
│   │   │   ├── departments/
│   │   │   │   ├── SecretaryPageSpec.md
│   │   │   │   ├── StockResearchPageSpec.md
│   │   │   │   ├── EarningsUpdatePageSpec.md
│   │   │   │   ├── MorningBriefingsPageSpec.md
│   │   │   │   ├── RetailSentimentPageSpec.md
│   │   │   │   └── MacroResearchPageSpec.md
│   │   │   ├── PortfolioPageSpec.md
│   │   │   ├── RepositoryPageSpec.md
│   │   │   └── SettingsPageSpec.md
│   │   │
│   │   └── utility_tools/
│   │       ├── AccountManagementSpec.md
│   │       ├── ChatHistorySpec.md
│   │       ├── FileViewerSpec.md
│   │       ├── FileDownloadSpec.md
│   │       ├── SaveToRepoSpec.md
│   │       └── SideBarSpec.md
│   │
│   ├── logs/                       # Progress logs (one per commit)
│   │   └── ...
│   │
│   └── checklist.md                # Master build checklist
│
│
│   ============================================================
│   ROOT CONFIG FILES
│   ============================================================
│
├── ruff.toml                       # Shared linting/formatting config
└── .github/
    └── workflows/
        └── ci.yml                  # CI: lint, test, build
```


## Root pyproject.toml (uv workspace)

The root `pyproject.toml` defines the uv workspace. It is not itself an installable package.

```toml
[build-system]
requires = ["uv_build>=0.9.5,<0.10.0"]
build-backend = "uv_build"

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv]
package = false
```


## Package dependency graph

```
core (openlia-core)     -- zero web dependencies, pure Python
  ^
  |
server (openlia)        -- depends on core via workspace reference, provides CLI
  ^
  |
frontend               -- talks to server via HTTP, no Python dependency
```

The server's `pyproject.toml` references core as a workspace dependency and registers the CLI:

```toml
[project]
name = "openlia"
dependencies = [
    "openlia-core",
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "sqlalchemy>=2.0",
]

[project.scripts]
openlia = "openlia_server.cli:main"

[tool.uv.sources]
openlia-core = { workspace = true }
```


## Key design rules

1. **core has zero web imports.** If you find yourself importing FastAPI, uvicorn, or anything HTTP-related inside `packages/core/`, the boundary is leaking. Test: `from openlia import StockResearchDepartment` must work in a Jupyter notebook with only `openlia-core` installed.

2. **Server is a thin wrapper.** Routes call core department methods and return the results. Business logic lives in core, not in route handlers.

3. **Frontend is decoupled.** It communicates only through the server's REST API. It could be replaced with a different UI without touching any Python code.

4. **Planning docs are not shipped.** The `planning/` directory is for development only. It is excluded from the Python package builds and Docker images.

5. **Config flows one direction.** `.env` or environment variables are read by `core/config.py`. The server passes config to core at startup. The frontend never touches config directly.