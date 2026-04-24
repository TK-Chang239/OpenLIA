# OpenLIA Deployment

This directory ships the minimal deployment recipes for OpenLIA.

## Recipes

- `compose/` — company mode behind a reverse proxy (Cloudflare Tunnel, Caddy,
  nginx). Cookies are `Secure`, `X-Forwarded-*` trusted. Port is NOT published
  on the host; terminate TLS at the proxy and forward on the docker network.
- `lan-only/` — company mode exposed directly on `:8000` for a LAN deployment
  with no TLS. `OPENLIA_COOKIE_SECURE=false` because the browser will connect
  over plain HTTP.

## Environment contract

Production-relevant env vars (full list in `packages/server/src/openlia_server/app.py`):

| Variable | Default | Purpose |
|---|---|---|
| `OPENLIA_MODE` | `personal` | `personal` (no auth) or `company` (auth required). |
| `OPENLIA_DB_URL` | `sqlite:////home/openlia/.openlia/openlia.db` | SQLAlchemy URL. |
| `OPENLIA_FRONTEND_DIST` | `/app/frontend/dist` | Built SPA path; resolved inside the image. |
| `OPENLIA_TRUST_PROXY_HEADERS` | `false` | `true` behind Cloudflare Tunnel / Caddy. |
| `OPENLIA_COOKIE_SECURE` | `true` if company, `false` otherwise | Forces `Secure` on session cookies. |
| `OPENLIA_SCHEDULER_ENABLED` | `false` | Turn on once providers are wired via the Setup Wizard. |
| `OPENLIA_SECRET_KEY` | auto-generated to `~/.openlia/secret.key` | 32-byte base64 AES-256-GCM key. |

## `/api` prefix handling

The image mirrors the Vite dev proxy: it strips `/api` from inbound paths
via `_StripApiPrefixMiddleware`. Browser-side code always calls `/api/...`;
in dev it is proxied, in production it is stripped at the ASGI layer.
Reverse-proxy configs should forward `/api/*` untouched.

## Volumes

`/home/openlia/.openlia` holds the SQLite database, `secret.key`, and any
other persistent state. Mount it as a named volume so it survives container
rebuilds.

## First boot

1. `docker compose up -d`
2. Browse to the service URL; the Setup Wizard will guide you through LLM
   + data-provider configuration.
3. Once configured, flip `OPENLIA_SCHEDULER_ENABLED` to `true` and
   `docker compose up -d` again to start scheduled jobs (Morning Briefing,
   Earnings Update scans, Macro Research assessments).
