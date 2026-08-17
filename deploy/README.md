# OpenLIA Deployment

Three production-ready Docker recipes. Pick one and copy the matching
`.env.example` to `.env` before booting.

| Recipe | Public surface | TLS | Use when |
|---|---|---|---|
| `cloudflare-tunnel/` | Cloudflare Tunnel sidecar (no host port) | Cloudflare edge | You already use Cloudflare, want zero firewall changes, and want DDoS / WAF in front of OpenLIA. |
| `caddy/` | Host ports 80/443 | Caddy automatic Let's Encrypt | You control DNS for a public FQDN and want a single-binary reverse proxy. |
| `lan/` | Host port 8080 (HTTP, no TLS) | None | Trusted LAN deployment for a small team or a single-user workstation. |

## Common flow

```bash
cd deploy/<recipe>
cp .env.example .env
$EDITOR .env                # paste OPENLIA_SECRET_KEY + recipe-specific keys
docker compose up -d
docker compose logs -f openlia
```

## Required secrets

Every recipe needs:

- `OPENLIA_IMAGE` — the OpenLIA container image (default
  `ghcr.io/tk-chang239/openlia:latest`; pin to a versioned tag in production).
- `OPENLIA_SECRET_KEY` — base64-encoded 32-byte AES-256-GCM key used to
  encrypt provider credentials at rest. Generate it with:

  ```bash
  python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
  ```

  If unset, the server auto-generates one to `~/.openlia/secret.key` on
  first boot. Persisting it via env makes backups / disaster recovery
  predictable.

Recipe-specific keys:

| Recipe | Extra env keys |
|---|---|
| `cloudflare-tunnel/` | `TUNNEL_TOKEN` (Cloudflare Zero Trust connector token). |
| `caddy/` | `OPENLIA_HOSTNAME` (public FQDN with DNS pointing here). |
| `lan/` | `OPENLIA_MODE` (`personal` default, or `company` for multi-user). |

## Cloudflare Tunnel notes

1. In the Cloudflare Zero Trust dashboard, go to *Networks > Tunnels >
   Create a tunnel*.
2. Pick the Cloudflared connector and copy the install token. Paste it
   into `.env` as `TUNNEL_TOKEN`.
3. Add a public hostname route pointing
   `lia.example.com → http://openlia:8000` on the docker network.
4. `docker compose up -d` — the `cloudflared` sidecar opens an outbound
   connection to Cloudflare; no inbound firewall changes needed.

## Caddy DNS prerequisite

Before `docker compose up -d`, point the FQDN you set in
`OPENLIA_HOSTNAME` at this host's public IP (A and/or AAAA record).
Without working DNS the ACME HTTP-01 challenge fails and Caddy will
serve the site over plain HTTP only.

## LAN firewall warning

The LAN recipe binds `0.0.0.0:8080` with no TLS. Only run it on a
trusted network. If you must traverse the public internet, use one of
the TLS-terminating recipes instead — cookies are not marked `Secure`
in this mode and credentials would otherwise travel in the clear.

## Environment contract

Production-relevant env vars (full list in
`packages/server/src/openlia_server/app.py`):

| Variable | Default | Purpose |
|---|---|---|
| `OPENLIA_MODE` | `personal` | `personal` (no auth) or `company` (auth required). |
| `OPENLIA_DB_URL` | `sqlite:////home/openlia/.openlia/openlia.db` | SQLAlchemy URL. |
| `OPENLIA_FRONTEND_DIST` | `/app/frontend/dist` | Built SPA path; resolved inside the image. |
| `OPENLIA_TRUST_PROXY_HEADERS` | `false` | Set `true` behind Cloudflare Tunnel / Caddy / nginx. |
| `OPENLIA_COOKIE_SECURE` | `true` if company mode, `false` otherwise | Forces `Secure` flag on session cookies. |
| `OPENLIA_SCHEDULER_ENABLED` | `false` | Turn on once providers are wired via the Setup Wizard. |
| `OPENLIA_SECRET_KEY` | auto-generated to `~/.openlia/secret.key` | 32-byte base64 AES-256-GCM key. |

## `/api` prefix handling

The image mirrors the Vite dev proxy: it strips `/api` from inbound
paths via `_StripApiPrefixMiddleware`. Browser-side code always calls
`/api/...`; in dev it is proxied, in production it is stripped at the
ASGI layer. Reverse-proxy configs should forward `/api/*` untouched.

## Volumes

`/home/openlia/.openlia` holds the SQLite database, `secret.key`, and
any other persistent state. Mount it as a named volume so it survives
container rebuilds.

## First boot

1. `docker compose up -d`
2. Browse to the service URL; the Setup Wizard guides you through LLM +
   data-provider configuration.
3. Once configured, the scheduler is on by default — Morning Briefing,
   Earnings Update scans, and Macro Research assessments run on cron.

## Operations

### Backup

The only stateful path is `/home/openlia/.openlia` inside the container.
Snapshot the named volume:

```bash
docker run --rm -v openlia_data:/data -v "$PWD":/backup alpine \
    tar czf /backup/openlia-$(date +%F).tgz -C /data .
```

### Upgrade

```bash
docker compose pull
docker compose up -d
```

Alembic migrations run automatically on startup via `openlia serve`.

### Admin CLI

In company mode, manage users and invites by `exec`ing into the running
container:

```bash
docker compose exec openlia openlia admin create-invite --label "Eng team" --max-uses 10 --expires 7d
docker compose exec openlia openlia admin list-invites
docker compose exec openlia openlia admin list-users
docker compose exec openlia openlia admin reset-password alice@example.com
```

See `openlia admin --help` (and `openlia --help`) for the full surface.
