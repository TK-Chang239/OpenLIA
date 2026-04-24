# syntax=docker/dockerfile:1.7

# ---------- Stage 1: frontend build ----------
FROM node:20-bookworm-slim AS frontend-build

WORKDIR /build/frontend

# Install dependencies first — maximum layer cache reuse.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Bring in the source and build.
COPY frontend/ ./
RUN npm run build \
    && test -f dist/index.html

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# System deps:
#   curl             — healthcheck
#   ca-certificates  — TLS
#   fonts + chromium deps — Playwright PDF export (REM-P2-002)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        fonts-liberation \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libasound2 \
        libpangocairo-1.0-0 \
        libpango-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for ~/.openlia ownership.
RUN useradd --create-home --shell /bin/bash --uid 1000 openlia

# Install uv (Astral).
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app

# Layer cache: copy lockfile + manifests before full source.
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/server/pyproject.toml packages/server/pyproject.toml

ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv sync --frozen --no-dev --all-packages --no-install-project

# Copy the actual source and re-sync to install the local workspace.
COPY packages/ packages/
RUN uv sync --frozen --no-dev --all-packages

# Install Playwright's Chromium into a shared path.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN uv run playwright install --with-deps chromium \
    && chown -R openlia:openlia /opt/playwright

# Copy the built frontend from Stage 1.
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

RUN chown -R openlia:openlia /app

USER openlia
WORKDIR /app

# Runtime defaults — override via env or compose.
ENV OPENLIA_MODE=personal \
    OPENLIA_FRONTEND_DIST=/app/frontend/dist \
    OPENLIA_DB_URL=sqlite:////home/openlia/.openlia/openlia.db \
    OPENLIA_SCHEDULER_ENABLED=false \
    PATH="/app/.venv/bin:${PATH}"

# ~/.openlia holds sqlite + secret.key; make it exist with 0700.
RUN mkdir -p /home/openlia/.openlia && chmod 700 /home/openlia/.openlia

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["openlia"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
