# openlia

Server, CLI, and persistence layer for [OpenLIA](https://github.com/TK-Chang239/OpenLIA), the open-source self-hosted AI investor assistant. Bundles a FastAPI app with per-Department routers, SSE report streams, chat sessions, repo/report save surfaces, Playwright PDF export, SQLAlchemy + Alembic persistence, auth/rate-limit middleware, and the Typer-based `openlia` CLI (`serve`, `admin`, `wizard`, `secrets`, `maintenance`).

```bash
pip install openlia
openlia serve                  # http://127.0.0.1:8000
```

Depends on [`openlia-core`](https://pypi.org/project/openlia-core/) for the Department agents and provider adapters. See the main [OpenLIA repo](https://github.com/TK-Chang239/OpenLIA) for the Docker image, deployment recipes, and full architecture.

MIT License.
