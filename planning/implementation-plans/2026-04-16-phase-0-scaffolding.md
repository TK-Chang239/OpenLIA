# Phase 0 — Workspace Scaffolding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the empty OpenLIA monorepo — uv workspace with two Python packages (`openlia-core`, `openlia`), a React+TS+Vite frontend skeleton, shared lint config, and CI — so that every later phase has a working `uv sync --all-packages && npm install && uv run pytest && npm run build` baseline to add to.

> **Note on `uv sync --all-packages`.** A bare `uv sync` only installs dependencies of the workspace root, not of member packages. With multiple members (`openlia-core` + `openlia`), `--all-packages` is required to install every member as editable into the shared `.venv` so tests can `import openlia` / `import openlia_server`. All verification commands below use this form.

**Architecture:** uv workspace at the repo root with two member packages under `packages/`. `openlia-core` is a pure-Python library with zero web deps. `openlia` depends on `openlia-core` via a workspace reference and registers a Typer CLI (`openlia`) plus a FastAPI app factory. The frontend is a separate Vite + React 18 + TypeScript app under `frontend/` (not a Python package). CI runs ruff + pytest + frontend build on every push.

**Tech Stack:** Python 3.12, uv 0.11.x (uv_build backend), ruff, pytest. FastAPI 0.115+, Typer 0.12+, uvicorn 0.34+ (server skeleton only — no routes yet). React 18, TypeScript 5, Vite 5, Vitest 1. GitHub Actions for CI.

**Source spec:** `planning/projectStructure.md` (canonical directory layout + dependency graph + workspace `pyproject.toml` template).

**Depends on:** Nothing — this is the foundation plan.

**Out of scope (handled in later phases):**
- Database, models, Alembic — Phase 1 (`database-design.md`)
- Auth, sessions, route handlers — Phase 3
- Docker / docker-compose — deployment plan (post-Phase 6)
- Pre-commit hooks — opt-in; CI is the enforcement point

---

## File Structure

Files created in this plan:

```
openlia/
├── pyproject.toml                          # uv workspace root (not installable)
├── ruff.toml                               # Shared lint/format config
├── .gitignore
├── .env.example
├── README.md
├── packages/
│   ├── core/
│   │   ├── pyproject.toml                  # Package "openlia-core"
│   │   ├── src/openlia/
│   │   │   ├── __init__.py                 # Exposes __version__
│   │   │   ├── config.py                   # Empty stub (Phase 2 fills it)
│   │   │   └── exceptions.py               # OpenLIAError base class
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_smoke.py               # Import + version test
│   └── server/
│       ├── pyproject.toml                  # Package "openlia" (registers `openlia` script)
│       ├── src/openlia_server/
│       │   ├── __init__.py
│       │   ├── app.py                      # FastAPI factory with /health
│       │   └── cli.py                      # Typer entry point with `serve` command
│       └── tests/
│           ├── __init__.py
│           └── test_smoke.py               # Import + /health + CLI help test
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── index.html
│   ├── public/.gitkeep
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── App.test.tsx
│       └── setupTests.ts
└── .github/workflows/
    └── ci.yml
```

Each file's responsibility is intentionally minimal — Phase 0 is about getting the toolchain green, not designing modules. Later phases own the real code.

---

## Task 1: Repo root — uv workspace, ruff, gitignore, env template

**Files:**
- Create: `pyproject.toml`
- Create: `ruff.toml`
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Verify uv is installed**

Run:
```bash
uv --version
```
Expected: prints version `>= 0.9.5` (e.g. `uv 0.9.5`). If not installed: `curl -LsSf https://astral.sh/uv/install.sh | sh` then re-source shell.

- [ ] **Step 2: Write the workspace `pyproject.toml`**

Create `pyproject.toml`:
```toml
[project]
name = "openlia-workspace"
version = "0.0.0"
description = "OpenLIA monorepo workspace root (not an installable package)."
requires-python = ">=3.12"

[tool.uv]
package = false

[tool.uv.workspace]
members = ["packages/*"]

[dependency-groups]
dev = [
    "ruff>=0.11",
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["packages/core/tests", "packages/server/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = ["-ra", "--strict-markers", "--import-mode=importlib"]
```

> **`--import-mode=importlib` + no test `__init__.py` files.** The default pytest import mode ("prepend") adds test dirs to `sys.path` and treats `__init__.py`-bearing test dirs as packages — which causes a collision when two packages both expose `tests.test_smoke` (one from core, one from server). `importlib` mode uses real importlib machinery and sidesteps this entirely. Tasks 2 and 3 therefore do **not** create `tests/__init__.py` files — the `tests/` directories are plain folders that pytest discovers via `testpaths` without needing to import them as packages.

> **`[project]` on a non-package root.** uv reads `requires-python` from `[project]` even when `package = false`. Without this, uv defaults to the host Python (3.13 on this machine) and the Phase 1 lockfile would resolve against the wrong version. The `name`/`version` are placeholders — they're never published.

> **No `[build-system]` block.** `package = false` tells uv not to build the workspace root as a distribution, so the build backend is never consulted. Member packages (Tasks 2 and 3) declare their own `[build-system]`.

> **`[dependency-groups]` (PEP 735)** is the canonical uv way to declare workspace-wide tools that aren't shipped with any package. `uv sync` installs them by default into the workspace `.venv`, which makes `uv run ruff` and `uv run pytest` work from the repo root.

- [ ] **Step 3: Write `ruff.toml`**

Create `ruff.toml`:
```toml
target-version = "py312"
line-length = 100
extend-exclude = ["scripts/"]  # legacy one-off tooling, not part of the shipped product

[lint]
select = [
  "E",    # pycodestyle errors
  "F",    # pyflakes
  "I",    # isort
  "B",    # bugbear
  "UP",   # pyupgrade
  "RUF",  # ruff-specific
]

[lint.per-file-ignores]
"**/tests/**" = ["B011"]  # allow `assert False` patterns in tests

[format]
quote-style = "double"
indent-style = "space"
```

> `scripts/extraction/` predates this plan and contains experimental PDF-extraction tooling. It lives outside the spec (`projectStructure.md` only covers `packages/` and `frontend/`). Exclude it from lint rather than rewrite it; if it becomes production code later, lint it then.

- [ ] **Step 4: Write `.gitignore`**

A `.gitignore` may already exist with project-specific entries. **Preserve all existing entries** and merge the new entries below. Final contents:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
venv/

# uv (Phase 1 will remove this entry once real deps are pinned)
uv.lock

# Node / frontend
node_modules/
frontend/dist/
frontend/.vite/
frontend/coverage/

# Environment
.env
.env.local
.env.*.local

# OS / IDE
.DS_Store
.idea/
.vscode/
*.swp

# OpenLIA runtime user data (lives under ~/.openlia, but block accidental commits if someone runs from repo)
.openlia/

# Build artifacts
dist/
build/

# Extraction pipeline output (contains content from proprietary reports)
scripts/extraction/output/
```

> **Note on `uv.lock`:** ignoring it for Phase 0 keeps the lockfile out of code review noise during scaffolding. Phase 1 (the first plan that pins real dependencies) will remove this entry and commit the lockfile.

> **Note on existing entries:** If `git show HEAD:.gitignore` shows lines not in the list above, preserve them. The list above is what *must* be present; do not delete pre-existing project conventions.

- [ ] **Step 5: Write `.env.example`**

Create `.env.example`:
```bash
# OpenLIA environment configuration
# Copy this file to `.env` and fill in values. `.env` is gitignored.

# Deployment mode: "personal" (single user, no auth) or "company" (multi-user, auth enabled)
OPENLIA_DEPLOYMENT_MODE=personal

# Secret key used to encrypt provider API keys at rest (AES-256-GCM).
# If unset, the server auto-generates one and writes it to ~/.openlia/secret.key on first run.
# OPENLIA_SECRET_KEY=

# Database URL. If unset, defaults to a SQLite file under ~/.openlia/openlia.db.
# The server expands `~` at startup before passing to SQLAlchemy.
# OPENLIA_DB_URL=

# Server bind address (defaults: 127.0.0.1:8000 in personal, 0.0.0.0:8000 in company)
# OPENLIA_HOST=127.0.0.1
# OPENLIA_PORT=8000
```

- [ ] **Step 6: Verify `uv sync` succeeds on the empty workspace**

Run:
```bash
uv sync
```
Expected: completes without error, creates `.venv/`, installs the dev group (ruff, pytest). No `requires-python` warning. (Workspace members don't exist yet, so plain `uv sync` is appropriate here. Tasks 2+ use `uv sync --all-packages`.)

- [ ] **Step 7: Verify `ruff check .` runs cleanly**

Run:
```bash
uv run ruff check .
```
Expected: `All checks passed!` (no Python files exist yet, so nothing to lint).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml ruff.toml .gitignore .env.example
git commit -m "chore: scaffold uv workspace, ruff config, gitignore, env template"
```

---

## Task 2: `openlia-core` package skeleton with smoke test

**Files:**
- Create: `packages/core/pyproject.toml`
- Create: `packages/core/src/openlia/__init__.py`
- Create: `packages/core/src/openlia/exceptions.py`
- Create: `packages/core/src/openlia/config.py`
- Create: `packages/core/tests/test_smoke.py`

> **Note:** do **not** create `packages/core/tests/__init__.py`. Task 1's pytest config uses `--import-mode=importlib`, which discovers test files without needing packaged test dirs. Having `__init__.py` in both core and server test dirs would collide on the shared module name `tests.test_smoke`.

- [ ] **Step 1: Write the failing test first**

Create `packages/core/tests/test_smoke.py`:
```python
"""Smoke tests proving the openlia-core package is installable and importable."""

import subprocess
import sys

import openlia
from openlia.exceptions import OpenLIAError


def test_package_has_version():
    assert hasattr(openlia, "__version__")
    assert isinstance(openlia.__version__, str)
    assert openlia.__version__  # non-empty


def test_base_exception_is_subclass_of_exception():
    assert issubclass(OpenLIAError, Exception)


def test_no_web_imports_in_core():
    """openlia-core must not import any web framework. The boundary rule from CLAUDE.md.

    Runs in a subprocess so the server-tests' fastapi import doesn't contaminate
    sys.modules in the parent pytest session.
    """
    probe = (
        "import openlia, sys; "
        "forbidden = {'fastapi', 'uvicorn', 'starlette'}; "
        "leaked = sorted(forbidden & set(sys.modules.keys())); "
        "assert not leaked, f'core leaked web imports: {leaked}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
```

- [ ] **Step 2: Run the test to confirm it fails (no package yet)**

Run:
```bash
uv run pytest packages/core/tests/test_smoke.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia'` (the package doesn't exist yet).

- [ ] **Step 3: Write the package `pyproject.toml`**

Create `packages/core/pyproject.toml`:
```toml
[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"

[project]
name = "openlia-core"
version = "0.1.0"
description = "OpenLIA core library — departments, LLM adapters, data adapters, report generation. Zero web dependencies."
requires-python = ">=3.12"
authors = [{name = "OpenLIA contributors"}]
license = {text = "MIT"}
dependencies = [
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[tool.uv.build-backend]
module-name = "openlia"
module-root = "src"
```

- [ ] **Step 4: Write the package source files**

Create `packages/core/src/openlia/__init__.py`:
```python
"""OpenLIA core library — pure Python, zero web dependencies."""

__version__ = "0.1.0"
```

Create `packages/core/src/openlia/exceptions.py`:
```python
"""Base exception hierarchy for openlia-core."""


class OpenLIAError(Exception):
    """Base class for all OpenLIA errors raised from the core library."""
```

Create `packages/core/src/openlia/config.py` (intentionally minimal — Phase 2's LLM/data plans fill this in):
```python
"""Config loader. Populated by Phase 2 (LLM provider + data provider plans)."""
```

- [ ] **Step 5: Sync and run the test — expect PASS**

Run:
```bash
uv sync --all-packages
uv run pytest packages/core/tests/test_smoke.py -v
```
Expected: 3 passed. The `--all-packages` flag installs `openlia-core` editable into the workspace `.venv` so `import openlia` resolves. If `test_no_web_imports_in_core` fails, something in `openlia/__init__.py` is importing fastapi/uvicorn/starlette transitively — fix the import.

- [ ] **Step 6: Verify ruff is still clean**

Run:
```bash
uv run ruff check packages/core
```
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add packages/core/
git commit -m "feat(core): scaffold openlia-core package with smoke tests"
```

---

## Task 3: `openlia` server package — FastAPI factory + Typer CLI + smoke test

**Files:**
- Create: `packages/server/pyproject.toml`
- Create: `packages/server/src/openlia_server/__init__.py`
- Create: `packages/server/src/openlia_server/app.py`
- Create: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_smoke.py`

> **Note:** do **not** create `packages/server/tests/__init__.py` — see the Task 2 note on why `--import-mode=importlib` + unpackaged test dirs is the chosen approach.

- [ ] **Step 1: Write the failing tests first**

Create `packages/server/tests/test_smoke.py`:
```python
"""Smoke tests for the openlia server package."""

from fastapi.testclient import TestClient
from typer.testing import CliRunner

import openlia
from openlia_server.app import create_app
from openlia_server.cli import app as cli_app


def test_core_is_importable_from_server():
    """Server depends on core via workspace reference."""
    assert openlia.__version__


def test_app_factory_returns_fastapi_instance():
    app = create_app()
    assert app.title == "OpenLIA"


def test_health_endpoint_returns_200():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cli_help_runs():
    runner = CliRunner()
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.stdout


def test_cli_serve_help_runs():
    runner = CliRunner()
    result = runner.invoke(cli_app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.stdout
    assert "--port" in result.stdout
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:
```bash
uv run pytest packages/server/tests/test_smoke.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia_server'` (and likely also `fastapi` / `typer` since they're not declared yet).

- [ ] **Step 3: Write the package `pyproject.toml`**

Create `packages/server/pyproject.toml`:
```toml
[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"

[project]
name = "openlia"
version = "0.1.0"
description = "OpenLIA server — FastAPI app, CLI, and persistence layer."
requires-python = ">=3.12"
authors = [{name = "OpenLIA contributors"}]
license = {text = "MIT"}
dependencies = [
    "openlia-core",
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "typer>=0.12",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[project.scripts]
openlia = "openlia_server.cli:main"

[tool.uv.sources]
openlia-core = { workspace = true }

[tool.uv.build-backend]
module-name = "openlia_server"
module-root = "src"
```

> `httpx` is included because `fastapi.testclient.TestClient` requires it.

- [ ] **Step 4: Write the package source files**

Create `packages/server/src/openlia_server/__init__.py`:
```python
"""OpenLIA server package — FastAPI app + Typer CLI."""

__version__ = "0.1.0"
```

Create `packages/server/src/openlia_server/app.py`:
```python
"""FastAPI application factory."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Build the FastAPI app. Phase 1+ will register routers here."""
    app = FastAPI(title="OpenLIA", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

Create `packages/server/src/openlia_server/cli.py`:
```python
"""Typer CLI entry point. Registered as the `openlia` console script."""

import typer
import uvicorn

app = typer.Typer(
    name="openlia",
    help="OpenLIA — open-source self-hosted AI investor assistant.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Force Typer into multi-command mode so `serve` shows as a named subcommand."""


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (development)."),
) -> None:
    """Start the OpenLIA HTTP server."""
    uvicorn.run(
        "openlia_server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def main() -> None:
    """Console-script entry point."""
    app()
```

- [ ] **Step 5: Sync and run the tests — expect PASS**

Run:
```bash
uv sync --all-packages
uv run pytest packages/server/tests/test_smoke.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Verify the `openlia` console script is installed**

Run:
```bash
uv run openlia --help
```
Expected: Typer help output listing the `serve` subcommand.

- [ ] **Step 7: Verify the server actually starts (manual check)**

Run in one terminal:
```bash
uv run openlia serve --port 8765
```
In another terminal:
```bash
curl http://127.0.0.1:8765/health
```
Expected: `{"status":"ok"}`. Then `Ctrl-C` the server.

- [ ] **Step 8: Verify ruff is still clean**

Run:
```bash
uv run ruff check packages/server
```
Expected: `All checks passed!`

- [ ] **Step 9: Commit**

```bash
git add packages/server/
git commit -m "feat(server): scaffold openlia server with FastAPI factory and Typer CLI"
```

---

## Task 4: Frontend scaffold (Vite + React 18 + TypeScript + Vitest)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/public/.gitkeep`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`
- Create: `frontend/src/setupTests.ts`

- [ ] **Step 1: Verify Node.js is installed**

Run:
```bash
node --version
npm --version
```
Expected: Node `>= 20`, npm `>= 10`. If older, install Node 20 LTS via the user's preferred manager.

- [ ] **Step 2: Write `package.json`**

Create `frontend/package.json`:
```json
{
  "name": "openlia-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^15.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^24.0.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.6.0"
  }
}
```

- [ ] **Step 3: Write the TypeScript configs**

Create `frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

- [ ] **Step 4: Write the Vite + Vitest configs**

Create `frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

Create `frontend/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
  },
});
```

- [ ] **Step 5: Write the HTML entry**

Create `frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenLIA</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/public/.gitkeep` (empty file — placeholder for static assets).

- [ ] **Step 6: Write the failing component test first**

Create `frontend/src/setupTests.ts`:
```ts
import "@testing-library/jest-dom";
```

Create `frontend/src/App.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the OpenLIA heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /openlia/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Install dependencies and run the test — expect FAIL**

Run:
```bash
cd frontend && npm install && npm test
```
Expected: FAIL with `Cannot find module './App'` (App.tsx doesn't exist yet) or similar.

- [ ] **Step 8: Write the minimal App + main**

Create `frontend/src/App.tsx`:
```tsx
export default function App() {
  return (
    <main>
      <h1>OpenLIA</h1>
      <p>Self-hosted AI investor assistant.</p>
    </main>
  );
}
```

Create `frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 9: Re-run the test — expect PASS**

Run:
```bash
cd frontend && npm test
```
Expected: 1 passed.

- [ ] **Step 10: Verify production build succeeds**

Run:
```bash
cd frontend && npm run build
```
Expected: `vite build` writes to `frontend/dist/`. Inspect `frontend/dist/index.html` exists.

- [ ] **Step 11: Verify the dev server starts (manual check)**

Run:
```bash
cd frontend && npm run dev
```
Expected: Vite prints `Local: http://localhost:5173/`. Open the URL in a browser, see the "OpenLIA" heading. Then `Ctrl-C`.

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React 18 + TypeScript + Vitest"
```

---

## Task 5: GitHub Actions CI (lint + test + build)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python:
    name: Python — lint + test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.11"

      - name: Set up Python
        run: uv python install 3.12

      - name: Sync workspace (all members)
        run: uv sync --all-packages

      - name: Lint (ruff)
        run: uv run ruff check .

      - name: Format check (ruff)
        run: uv run ruff format --check .

      - name: Test (pytest)
        run: uv run pytest -v

  frontend:
    name: Frontend — test + build
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install
        run: npm ci

      - name: Type check
        run: npm run lint

      - name: Test
        run: npm test

      - name: Build
        run: npm run build
```

- [ ] **Step 2: Verify the YAML parses**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no output (parses cleanly). If it errors, fix the YAML.

- [ ] **Step 3: Verify `ruff format --check .` matches what CI will run**

Run:
```bash
uv run ruff format --check .
```
Expected: `All files already formatted!` (or `1 file would be reformatted` followed by a re-format and re-check until clean).

If files would be reformatted:
```bash
uv run ruff format .
```
Then re-run the check until it passes.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for Python + frontend"
```

> **Note:** Confirming the workflow actually passes on GitHub Actions requires pushing to a remote. Skip the push for now — the next plan (or whichever PR first lands code) will exercise it.

---

## Task 6: LICENSE, top-level README, final integration verification

**Files:**
- Create: `LICENSE`
- Create: `README.md`

- [ ] **Step 1: Write `LICENSE` (MIT)**

Create `LICENSE`:
```
MIT License

Copyright (c) 2026 OpenLIA contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Write `README.md`**

Create `README.md`:
```markdown
# OpenLIA

Open-source, self-hosted AI investor assistant. Multiple specialized LLM agents (Departments) for equity research, earnings updates, morning briefings, retail sentiment, macro research, and panic-thermometer monitoring.

## Quickstart (development)

Prerequisites: Python 3.12+, [uv](https://github.com/astral-sh/uv) 0.11+, Node.js 20+.

```bash
# Backend
uv sync --all-packages                         # install workspace + dev tools
uv run pytest                                  # run all Python tests
uv run openlia --help                          # see CLI commands
uv run openlia serve                           # start FastAPI on http://127.0.0.1:8000

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev                                    # Vite dev server with /api proxied to FastAPI
```

## Layout

- `packages/core/` — `openlia-core`: pure-Python library (departments, LLM adapters, data adapters, report generation). Zero web dependencies.
- `packages/server/` — `openlia`: FastAPI server + Typer CLI. Depends on `openlia-core` via workspace reference.
- `frontend/` — React + TypeScript + Vite app. Talks to the server via REST + SSE.
- `planning/` — Specs, master plan, and per-phase implementation plans. Not shipped.

See `planning/PLAN.md` for full architecture and `planning/projectStructure.md` for the canonical directory layout.

## License

MIT.
```

- [ ] **Step 3: Final clean-room verification**

Run, in order, from the repo root:
```bash
uv sync --all-packages
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
uv run openlia --help
( cd frontend && npm install && npm run lint && npm test && npm run build )
```

Expected:
- `uv sync --all-packages`: completes, `.venv/` exists with `openlia-core` and `openlia` editable.
- `ruff check`: `All checks passed!`
- `ruff format --check`: `All files already formatted!` (or `N files already formatted`).
- `pytest`: 8 passed (3 from core + 5 from server).
- `openlia --help`: prints Typer help with `serve` subcommand.
- `npm install`: completes, `node_modules/` exists.
- `npm run lint`: `tsc --noEmit` exits 0.
- `npm test`: 1 passed.
- `npm run build`: writes `frontend/dist/`.

If any step fails, stop and fix before committing.

- [ ] **Step 4: Commit**

```bash
git add LICENSE README.md
git commit -m "docs: add LICENSE and top-level README"
```

- [ ] **Step 5: Confirm the working tree is clean**

Run:
```bash
git status
```
Expected: `nothing to commit, working tree clean`.

---

## Acceptance Criteria

Phase 0 is done when **all of the following are true** on a fresh clone:

1. `uv sync --all-packages` succeeds with no errors and installs both workspace members editable.
2. `uv run pytest -v` reports 8 passed (3 core smoke + 5 server smoke).
3. `uv run ruff check .` reports `All checks passed!`.
4. `uv run ruff format --check .` reports formatted.
5. `uv run openlia --help` prints help including the `serve` subcommand.
6. `uv run openlia serve` starts a server that responds 200 on `GET /health`.
7. `cd frontend && npm install && npm test && npm run build` all succeed; the dev server (`npm run dev`) renders the "OpenLIA" heading at `http://localhost:5173`.
8. `from openlia import __version__` works in `uv run python -c '...'` *without* importing fastapi/uvicorn — the boundary rule from CLAUDE.md is enforced by `test_no_web_imports_in_core`.
9. `.github/workflows/ci.yml` exists and parses as valid YAML.

If any of these fail, the plan is not complete.

---

## Dependencies for Downstream Plans

Plans that build on Phase 0:

- **Phase 1 (database)** adds `sqlalchemy`, `alembic`, and `argon2-cffi` to `packages/server/pyproject.toml`; creates `packages/server/src/openlia_server/db/` with models, session, migrations; commits the first `alembic` baseline migration; removes `uv.lock` from `.gitignore` and commits it.
- **Phase 2 (LLM provider, etc.)** adds Pydantic-modeled config classes to `packages/core/src/openlia/config.py` and starts populating `packages/core/src/openlia/llm/`.
- **Phase 3 (auth)** adds session middleware to `app.py` and starts populating `packages/server/src/openlia_server/routes/`.

Phase 0 itself does **not** create `packages/core/src/openlia/departments/`, `packages/core/src/openlia/llm/`, `packages/core/src/openlia/data/`, or any of the runtime user-data layout (`~/.openlia/`). Those are owned by their respective phase plans.
