# scripts/

Helper scripts that are not part of the runtime image.

## `acceptance.sh`

Single-command merge gate for OpenLIA. Runs the entire Phase 23
acceptance battery in order:

1. `ruff check` + `ruff format --check`
2. `uv run pytest -q` (workspace; smoke suite skips without `SMOKE=1`)
3. `npm ci` + `npm run lint` + `npm test -- --run` + `npm run build`
4. `docker build -t $IMAGE .`
5. `SMOKE=1 OPENLIA_IMAGE=$IMAGE uv run pytest tests/smoke/ -v`
6. `docker compose config` validation for each
   `deploy/<recipe>/docker-compose.yml`
7. `caddy validate` against `deploy/caddy/Caddyfile`
8. `uv build --all-packages` + `pip install` into a throwaway venv
9. `openlia --help` smoke

```bash
bash scripts/acceptance.sh             # IMAGE=openlia:gate by default
IMAGE=ghcr.io/example/openlia:rc bash scripts/acceptance.sh
```

Failures exit non-zero on the first broken gate. Use this before tagging
a release or merging a phase-completion PR.
