# Contributing to OpenLIA

Thanks for your interest in improving OpenLIA. This guide covers how to
set up a development environment, the conventions the codebase follows,
and how changes get merged.

By participating you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md). Security issues follow a separate,
private process — see [SECURITY.md](SECURITY.md); do not file them as
public issues or pull requests.

## Ways to contribute

- Report bugs or request features via
  [GitHub Issues](https://github.com/TK-Chang239/OpenLIA/issues) using the
  provided templates.
- Improve documentation.
- Submit code via pull requests.

For anything beyond a small fix, please open an issue first so we can
agree on the approach before you invest time.

## Development setup

Prerequisites: Python 3.12+, [uv](https://github.com/astral-sh/uv) 0.11+,
Node.js 20+.

**Always use `uv` for Python package management — never `pip`.**

```bash
# Backend
uv sync --all-packages       # install the workspace + dev tools
uv run pytest                # run all Python tests
uv run openlia --help        # see CLI commands
uv run openlia serve         # start FastAPI on http://127.0.0.1:8000

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev                  # Vite dev server with /api proxied to FastAPI
npm run build                # production build
```

## Architecture boundaries

OpenLIA is three layers, and the boundaries between them are enforced —
do not cross them:

```
core (openlia-core)   -- pure Python, zero web dependencies
  ^
server (openlia)      -- FastAPI wrapper over core (HTTP + SSE)
  ^
frontend              -- React/TypeScript/Vite, talks to the server
```

- `packages/core/` must never import FastAPI, uvicorn, or anything
  HTTP-related. `from openlia import EquityResearchDepartment` must work
  with only `openlia-core` installed and no server running.
- Business logic belongs in core. Route handlers in `packages/server/`
  call core methods and return the result.
- The frontend communicates only through the server's REST/SSE API — it
  never touches config or core directly.

See [`CLAUDE.md`](CLAUDE.md) and
[`planning/projectStructure.md`](planning/projectStructure.md) for the
full design rules.

## Code style and quality

- **Formatting and linting** use [ruff](https://docs.astral.sh/ruff/):

  ```bash
  uv run ruff check .          # lint
  uv run ruff format .         # format
  uv run ruff check --fix .    # lint + autofix
  ```

- Use modern, strict Python type hints on all function signatures.
- Fail fast and loudly — raise specific exceptions with context rather
  than swallowing errors.
- Keep it simple. No emojis anywhere in the codebase.
- Add tests for new behavior. We aim for roughly 80% coverage as a
  guideline, not a hard gate — write the tests that matter, not tests for
  their own sake.

Before opening a pull request, this should pass locally:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

## Branch and pull request flow

1. Fork the repo (or branch, if you have write access). Use a
   descriptive branch name, e.g. `feat/<slug>` or `fix/<slug>`.
2. Make focused commits with clear messages.
3. Open a pull request against `main` and fill in the PR template.
4. Ensure CI is green. The `CI` workflow runs three jobs, all of which
   must pass:
   - **Python — lint + test** (`ruff check`, `ruff format --check`,
     `pytest`)
   - **Frontend — test + build** (`npm run lint`, `npm test`,
     `npm run build`)
   - **Docker — image builds + boot smoke** (image builds and the
     container answers `/healthz`)

A maintainer will review and merge once CI passes and the change looks
good. Thanks for contributing.
