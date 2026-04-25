#!/usr/bin/env bash
# OpenLIA merge-gate acceptance script.
#
# Runs the full local Phase 23 acceptance battery in order:
#   1. ruff lint + format check
#   2. pytest (workspace + smoke harness, smoke skips without SMOKE=1)
#   3. frontend lint, test, build
#   4. docker build of the production image
#   5. SMOKE=1 pytest tests/smoke/
#   6. docker compose config validate ×3 (cloudflare-tunnel / caddy / lan)
#   7. Caddyfile syntax validate
#   8. `uv build --all-packages` + throwaway venv install
#   9. `openlia --help` smoke
#
# Exits non-zero on the first failure.
#
# Override the image tag with IMAGE=foo:bar bash scripts/acceptance.sh.
set -euo pipefail

IMAGE="${IMAGE:-openlia:gate}"

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

echo "==> ruff check"
uv run ruff check .
echo "==> ruff format --check"
uv run ruff format --check .

echo "==> pytest (workspace; smoke skipped)"
uv run pytest -q

echo "==> frontend lint / test / build"
(cd frontend && npm ci --prefer-offline --no-audit --no-fund)
(cd frontend && npm run lint)
(cd frontend && npm test -- --run)
(cd frontend && npm run build)

echo "==> docker build $IMAGE"
docker build -t "$IMAGE" .

echo "==> SMOKE=1 pytest tests/smoke/"
SMOKE=1 OPENLIA_IMAGE="$IMAGE" uv run pytest tests/smoke/ -v

echo "==> docker compose config (cloudflare-tunnel)"
docker compose -f deploy/cloudflare-tunnel/docker-compose.yml config >/dev/null
echo "==> docker compose config (caddy)"
docker compose -f deploy/caddy/docker-compose.yml config >/dev/null
echo "==> docker compose config (lan)"
docker compose -f deploy/lan/docker-compose.yml config >/dev/null

echo "==> caddy validate Caddyfile"
docker run --rm \
    -v "$REPO_ROOT/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
    caddy:2 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

echo "==> uv build --all-packages"
rm -rf dist/
uv build --all-packages --out-dir dist/

echo "==> throwaway venv install"
GATE_VENV="$(mktemp -d)/openlia-gate-venv"
python3 -m venv "$GATE_VENV"
"$GATE_VENV/bin/pip" install --quiet dist/openlia_core-*.whl dist/openlia-*.whl
"$GATE_VENV/bin/openlia" --help >/dev/null

echo
echo "All acceptance gates passed for $IMAGE."
