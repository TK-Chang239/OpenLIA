# OpenLIA

Open-source, self-hosted AI investor assistant. Multiple specialized LLM
agents (Departments) for equity research, earnings updates, morning
briefings, retail sentiment, macro research, and panic-thermometer
monitoring.

Two deployment modes from one codebase: **personal** (single user,
localhost, no auth) and **company** (multi-user, network-accessible,
invite-based auth).

## Quickstart

### Docker

```bash
docker run -d \
    -p 8000:8000 \
    -v openlia_data:/home/openlia/.openlia \
    ghcr.io/tk-chang239/openlia:latest
```

Then open <http://127.0.0.1:8000> and follow the Setup Wizard.

For production deployments (Cloudflare Tunnel, Caddy, LAN), see the
[deploy/](deploy/README.md) recipes.

### PyPI

```bash
pip install openlia
openlia serve                  # http://127.0.0.1:8000
```

`openlia` brings in `openlia-core` automatically. Both packages are
published to PyPI on each `v*.*.*` tag.

### From source

Prerequisites: Python 3.12+, [uv](https://github.com/astral-sh/uv) 0.11+,
Node.js 20+.

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

## Deployment recipes

| Recipe | Public surface | TLS | Use when |
|---|---|---|---|
| [`deploy/cloudflare-tunnel/`](deploy/cloudflare-tunnel/) | Cloudflare Tunnel sidecar | Cloudflare edge | Cloudflare account, no firewall changes wanted. |
| [`deploy/caddy/`](deploy/caddy/) | Host ports 80/443 | Automatic Let's Encrypt | Public FQDN with DNS pointing here. |
| [`deploy/lan/`](deploy/lan/) | Host port 8080 (HTTP) | None | Trusted LAN, single user or small team. |

See [deploy/README.md](deploy/README.md) for the full setup flow,
required env vars, and ops/backup/upgrade procedures.

## Layout

- `packages/core/` — `openlia-core`: pure-Python library (departments,
  LLM adapters, data adapters, report generation). Zero web dependencies.
- `packages/server/` — `openlia`: FastAPI server + Typer CLI. Depends on
  `openlia-core` via workspace reference.
- `frontend/` — React + TypeScript + Vite app. Talks to the server via
  REST + SSE.
- `deploy/` — three Docker compose recipes for production deployment.
- `planning/` — Specs, master plan, and per-phase implementation plans.
  Not shipped.

## Docs

- [`deploy/README.md`](deploy/README.md) — three Docker compose recipes,
  required secrets, ops/backup/upgrade procedures.
- [`RELEASING.md`](RELEASING.md) — version scheme, release workflow,
  rolling a broken release.
- [`CHANGELOG.md`](CHANGELOG.md) — release notes (Keep-a-Changelog
  format).
- [`planning/`](planning/) — full architecture description, per-phase
  specs, and implementation plans.
- [`planning/PLAN.md`](planning/PLAN.md) — top-level architecture and
  feature catalogue.
- [`planning/projectStructure.md`](planning/projectStructure.md) —
  canonical directory layout and design rules.

## License

MIT.
