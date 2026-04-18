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
