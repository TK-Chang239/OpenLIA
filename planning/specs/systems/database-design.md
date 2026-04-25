# Database Design Spec

Defines the canonical database schema for OpenLIA: engine choice, type conventions, table definitions, secrets management, and migration strategy. All persistent application state lives here.

---

## 1. Scope and tenancy

### Scope

**Comprehensive DB** -- all persistent application state lives in the database. This includes:

- User accounts, sessions, invites, auth events.
- Admin-configured LLM providers, model roster, data providers, web search providers.
- Per-user LLM tier preferences.
- Chat sessions, messages, attachments (metadata; files on disk).
- Generated reports and version history.
- Portfolio holdings and watchlists.
- Dashboard state for Panic Thermometer, Macro Research, and Retail Sentiment.
- Formula engine saved formulas.
- Setup wizard state and the `config_store` KV escape hatch.

**Not in scope for v1**: provider response caching (data provider API responses are fetched live and not persisted).

### Tenancy model

Single schema, single database file, shared by all users. Personal mode and company mode use the same tables.

- **Personal mode**: a synthetic `local` user row (`id = "local"`, `email = "local@openlia.local"`, `is_admin = true`, `password_hash = NULL`) is seeded on first run. All personal-mode data keys off this sentinel user. No login required; the server assumes the `local` identity on every request.
- **Company mode**: real user rows with real credentials. The admin (wizard operator) is `is_admin = true`; all other registrants are regular users.

Code that queries by `user_id` works identically in both modes -- the only difference is whether the `user_id` is `"local"` or a real UUID.

### Schema architecture

**Hybrid (Approach 1)**: relational core tables for structured, queryable data + JSON columns for flexible substructure that belongs to a row + a narrow `config_store` KV table for genuinely miscellaneous settings.

- Relational tables: users, sessions, invites, providers, models, chat sessions/messages, reports, portfolio, watchlists, dashboard state, formula engine.
- JSON columns: panel configs, metric settings, filter presets, tool call metadata, token usage, step data, structured report content.
- KV escape hatch: `config_store` for one-off operator knobs and feature flags. Kept narrow on purpose.

---

## 2. Engine, types, and conventions

### Engine

**SQLite only for v1.** One file on disk (`~/.openlia/openlia.db` by default, overridable via `OPENLIA_DB_URL`). Postgres is dropped from the v1 matrix.

Why SQLite is the right fit:

- Self-hosted, single-admin, low-concurrency workload -- a 10-person company is well inside SQLite's comfort zone.
- Zero-ops: no separate server to install, secure, patch, or back up. `cp openlia.db openlia.db.bak` is a valid backup.
- Works identically in personal mode (localhost) and company mode (server behind HTTPS tunnel).
- Alembic + SQLAlchemy treat it as a first-class backend; migrations work the same way.

Required PRAGMAs set at connection open (in `db/session.py`):

- `journal_mode=WAL` -- concurrent readers with one writer; essential once a handful of users are chatting simultaneously.
- `synchronous=NORMAL` -- the WAL-safe durability level; `FULL` is overkill for our data.
- `foreign_keys=ON` -- SQLite defaults to OFF. Must be enabled on every connection.
- `busy_timeout=5000` -- wait 5s for a writer lock before failing; smooths over the rare contention case.

### Portable type conventions

Even though v1 is SQLite-only, every column type is chosen so a future Postgres backend would work without a schema rewrite.

| Concept | SQLAlchemy type | Notes |
|---|---|---|
| Primary key | `String(36)` holding a UUID4 string | Application-generated via `uuid.uuid4()`. Avoids `INTEGER AUTOINCREMENT` race conditions and keeps IDs globally unique. |
| Foreign key | `String(36)`, `ForeignKey("parent.id", ondelete=...)` | Cascade rules set per-relationship. |
| Timestamp | `DateTime(timezone=True)` | Always UTC at storage; convert on render. Populated by `server_default=func.now()` for `created_at`, app-side for everything else. |
| Email | `String(320)` | Normalized in the application (lowercase, trimmed) before insert or lookup. No CITEXT dependency. |
| Short text label | `String(N)` with explicit N | e.g. `String(64)` for invite codes, `String(128)` for model identifiers. |
| Long free text | `Text` | Chat messages, report bodies, markdown content. |
| Boolean | `Boolean` | Stored as 0/1 in SQLite, `true`/`false` in Postgres. |
| Enum-like | `String(32)` + Python-side `Enum` validator | Avoids native ENUM portability pain. Checked in the model. |
| Structured sub-document | `JSON` (SQLAlchemy) | Stored as `TEXT` in SQLite, `JSONB` in Postgres. Use for substructure that doesn't merit its own table. |
| Monetary / numeric | `Numeric(precision, scale)` | Never `Float` for money or indicator values used in formulas. |

### ID strategy

- All PKs are `String(36)` UUID4 strings. No hybrid `INTEGER` PKs anywhere.
- Generated by the application (`str(uuid.uuid4())`) via a SQLAlchemy column default, so the ID is known before insert.
- Natural keys (email, invite code, etc.) get unique indexes but never become the PK.

### Timestamps

Every mutable table usually carries:

- `created_at DateTime(timezone=True) NOT NULL DEFAULT now()`
- `updated_at DateTime(timezone=True) NOT NULL DEFAULT now()` -- bumped by SQLAlchemy `onupdate=func.now()`.

Append-only / event tables (`auth_events`, `llm_call_log`, etc.) carry only `created_at`.

**Exemptions.** A handful of mutable tables omit `updated_at` when another column already carries the "last touched" signal. These are called out in §3/§7. Notable case: `sessions` uses `last_seen_at` in place of `updated_at`, so `updated_at` is intentionally absent from the `sessions` column list.

### Soft-delete policy

**No generic soft-delete.** Specific tables that need retention (e.g., `auth_events`, `chat_sessions` for history) keep rows forever. Everything else hard-deletes when the owning user or entity is removed.

Rationale: soft-delete-everywhere introduces `WHERE deleted_at IS NULL` noise in every query and a steady bug tax when it's forgotten.

### Cascade rules

Default: `ondelete="CASCADE"` for rows owned by a user or parent entity (chat messages cascade from session, session cascades from user).

Exceptions:

- `auth_events.user_id` -- `SET NULL`. Audit trail survives user deletion.
- `auth_events.actor_user_id` -- `SET NULL`. Same reasoning.
- `reports.user_id` -- `SET NULL`. Saved reports outlive their author in company mode.
- `signup_invites.created_by_user_id` -- `SET NULL`. Invite history is admin metadata.
- `password_reset_requests.approved_by_user_id` -- `SET NULL`. Audit trail.
- Admin-owned config tables (`llm_providers`, `data_providers`, admin-scoped model roster) -- `RESTRICT` against deleting the admin user. The system needs an admin; deletion must reassign first.

### JSON column discipline

JSON columns are for substructure that belongs *to* a row, not for arbitrary bags. Each JSON column's schema is documented in the model file with a Python `TypedDict` (or Pydantic model) and validated at the service layer on write. Indexing into JSON is allowed in SQLite via `json_extract` but kept rare -- if we find ourselves querying a JSON key frequently, that key gets promoted to a real column.

### The `config_store` KV escape hatch

One small key-value table, `config_store (key String PK, value JSON, updated_at)`, holds genuinely miscellaneous settings that don't belong to a user or entity: wizard completion flag, feature toggles, one-off operator knobs. Kept narrow on purpose -- it is not a dumping ground. When a key pattern grows (e.g., multiple LLM-tier keys), it gets promoted to a real table.

### Email normalization

All email comparisons happen on lowercased, `.strip()`-ed values. Normalization lives in a single helper `normalize_email(raw: str) -> str` used by every insert, lookup, and unique constraint enforcer. The column has a `UNIQUE` index on the normalized value.

### Naming conventions

- Table names: `snake_case`, plural (`users`, `chat_sessions`, `signup_invites`).
- Column names: `snake_case`, singular, no table prefix.
- FK columns: `<entity>_id` (e.g., `user_id`).
- Boolean columns: prefix with `is_` or `has_` (`is_admin`, `has_completed_wizard`).
- Index names: `ix_<table>_<columns>`; unique index names: `uq_<table>_<columns>`.
- Enum-valued columns: value set documented in the model docstring; invalid values fail at the service layer.

### Alembic migration conventions

- Single migration branch, no branches, no merges.
- Migration filename format: `YYYY-MM-DD-HHMM_<slug>.py` (Alembic-native timestamp + slug).
- Every migration must be reversible (`downgrade()` implemented) unless the change is data-destructive in a way that downgrade can't recover from -- in which case the migration docstring explicitly states "not reversible" and the reason.
- New columns added to existing tables must have a server-side default or be nullable, so the migration runs against a populated prod DB without a rewrite step.

---

## 3. Core tables: users, auth, sessions, invites

### `users`

The canonical identity table. One row per person; one synthetic `local` row in personal mode.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | UUID4. Personal mode uses `id = "local"` (sentinel). |
| `email` | `String(320)` | UNIQUE NOT NULL | Normalized (lowercase, trimmed). Personal mode: `"local@openlia.local"`. |
| `display_name` | `String(128)` | NOT NULL | Shown in UI. Defaults to email local-part on registration. |
| `password_hash` | `String(256)` | NULL | Argon2id hash. NULL for personal-mode `local` row (no password needed). |
| `is_admin` | `Boolean` | NOT NULL DEFAULT `false` | One admin in company mode. `true` for personal-mode `local` row. |
| `is_disabled` | `Boolean` | NOT NULL DEFAULT `false` | Soft-lock. Disabled users cannot log in; existing sessions invalidated. |
| `must_change_password` | `Boolean` | NOT NULL DEFAULT `false` | Set by admin direct password reset. Forces change-password flow on next login. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |
| `last_login_at` | `DateTime(tz)` | NULL | Updated on successful login. |
| `failed_login_attempts` | `Integer` | NOT NULL DEFAULT `0` | Consecutive failed-password counter. Reset to 0 on a successful login. Only mutated when the lockout feature is enabled (see `config_store.auth.lockout.enabled`). |
| `locked_until` | `DateTime(tz)` | NULL | Wall-clock time at which the account becomes loggable again. NULL = not locked. Set when `failed_login_attempts >= 5`. |

**Indexes:** `uq_users_email`, `ix_users_locked_until`.

**Notes:**

- The personal-mode seed row is inserted by the first-run migration or by `openlia serve` at startup if it doesn't exist. Always `id = "local"`.
- `password_hash` being nullable means login code must explicitly check "if the row is `local`, password auth is disabled; otherwise hash must be present." No fallback / empty-hash matching.
- Password hashing: Argon2id via `argon2-cffi`. Parameters: time_cost=3, memory_cost=65536 (64 MiB), parallelism=4.
- `failed_login_attempts` and `locked_until` are persisted on the row (not in-memory) so the lockout survives restarts. Both columns are still maintained on the personal-mode `local` row but are never consulted (password auth is disabled there).
- No `auth_accounts` table in v1. A `users.id` row *is* the identity.

### `sessions`

Opaque server-side session tokens. Issued on login, stored hashed, presented by the client as a cookie.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | Internal row identifier. |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `token_hash` | `String(64)` | UNIQUE NOT NULL | SHA-256 of the opaque token (32 random bytes, base64url-encoded). Never stored in plaintext. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `last_seen_at` | `DateTime(tz)` | NOT NULL | Updated per authenticated request (throttled to once per minute). |
| `expires_at` | `DateTime(tz)` | NOT NULL | Company mode: 30 days when "Keep Me Logged In" is checked at login, 12 hours otherwise (server-enforced absolute cap on the browser-session cookie). Personal mode: 1 year (cookie persistence convenience only -- the server short-circuits session lookup for the synthetic `local` user, so this value is not consulted at runtime). See `AccountManagementSpec.md` § 7.2. |
| `user_agent` | `String(512)` | NULL | For "your sessions" UI in Settings. |
| `ip_address` | `String(64)` | NULL | Last-seen IP. Trusted only when `OPENLIA_TRUST_PROXY_HEADERS=true`. |
| `revoked_at` | `DateTime(tz)` | NULL | Set on logout or admin revocation. Row kept for audit. |

**Indexes:** `uq_sessions_token_hash`, `ix_sessions_user_id`, `ix_sessions_expires_at`.

**Notes:**

- Opaque tokens (not JWT) because revocation must be instant and session metadata lives in one place.
- Cookie flags: `HttpOnly`, `Secure` (controlled by `OPENLIA_COOKIE_SECURE`, defaults true in company mode), `SameSite=Lax`.
- Nightly prune: delete rows where `expires_at < now() - 7 days`.

### `signup_invites`

Multi-use, optionally-capped invite tokens. Admin creates; prospective users present at registration.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `token_hash` | `String(64)` | UNIQUE NOT NULL | SHA-256 hex digest of the URL-safe random bearer token (32 bytes base64url, returned once to the creator and never persisted). Lookup is by `token_hash(presented_token)`. See §5 "Non-encrypted credential columns". |
| `label` | `String(128)` | NULL | Admin-facing note ("Q2 hires", "contractors"). |
| `created_by_user_id` | `String(36)` | FK `users.id` SET NULL | |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `expires_at` | `DateTime(tz)` | NULL | Optional admin-set expiry. NULL = never expires. |
| `max_uses` | `Integer` | NULL | NULL = unlimited. Otherwise capped. |
| `use_count` | `Integer` | NOT NULL DEFAULT `0` | Incremented atomically on successful registration. |
| `revoked_at` | `DateTime(tz)` | NULL | Admin-revoked. Further registrations rejected. |

**Indexes:** `uq_signup_invites_token_hash`.

**Registration flow:**

1. User hits `/register?invite=<token>`.
2. Server validates: invite exists, not revoked, not expired, `use_count < max_uses` (if cap set).
3. User fills email + password + display name.
4. On commit: insert into `users`, increment `use_count` in the same transaction.

### `signup_policy`

Single-row table controlling registration behavior.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK CHECK `id = 1` | Enforced singleton. |
| `mode` | `String(32)` | NOT NULL | One of `invite_only`, `closed`, `open`. v1: `invite_only` (company default), `closed` (no registration). `open` reserved for v2. |
| `allowed_email_domains` | `JSON` | NOT NULL DEFAULT `[]` | Optional allowlist (e.g., `["company.com"]`). Empty = no domain restriction. Applied on top of invite validation. |
| `updated_at` | `DateTime(tz)` | NOT NULL | |
| `updated_by_user_id` | `String(36)` | FK `users.id` SET NULL | |

Seeded on wizard completion: personal mode -> `closed`; company mode -> `invite_only`.

### `password_reset_requests`

Admin-approved password reset flow. User initiates from login page, admin approves and delivers a one-time link out-of-band. No SMTP required.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `status` | `String(32)` | NOT NULL | One of `pending`, `approved`, `consumed`, `rejected`, `expired`. |
| `requested_at` | `DateTime(tz)` | NOT NULL | |
| `requested_ip` | `String(64)` | NULL | Subject to `OPENLIA_TRUST_PROXY_HEADERS`. |
| `approved_by_user_id` | `String(36)` | FK `users.id` SET NULL | The admin who approved. |
| `approved_at` | `DateTime(tz)` | NULL | |
| `token_hash` | `String(64)` | UNIQUE NULL | SHA-256 of the one-time token. NULL until approved. |
| `expires_at` | `DateTime(tz)` | NULL | NULL until approved; 24h from approval. |
| `consumed_at` | `DateTime(tz)` | NULL | Set when user redeems. |

**Indexes:** `ix_password_reset_requests_user_status` on `(user_id, status)`.

**Flow:**

1. **User initiates**: login page "Forgot password?" -> enters email -> `POST /auth/password-reset/request`. Server always returns 200 (no email enumeration). If email matches a user, a `pending` row is inserted. Only one `pending` row per user at a time; a second request DELETEs the existing `pending` row (if any) and INSERTs a new one in the same transaction.
2. **Admin reviews**: admin panel shows pending requests. Admin clicks Approve or Reject.
   - Approve: server generates 32-byte random token, stores SHA-256 hash in `token_hash`, sets `expires_at = now + 24h`, `status = approved`. UI shows the one-time link to admin exactly once. Admin copies and delivers out-of-band (Slack, Signal, in person).
   - Reject: `status = rejected`, row kept for audit.
3. **User redeems**: clicks link -> reset-password page -> enters new password -> `POST /auth/password-reset/consume`. Server validates hash + status + expiry, updates `users.password_hash`, sets `consumed_at` and `status = consumed`, **revokes all existing sessions** for that user, logs auth event.

**Guardrails:**

- Rate limit on request endpoint: 5 per IP per hour (in-memory sliding window).
- One `pending` row per user at a time. Re-request overwrites pending row.
- Approved tokens expire in 24h. Expired rows flipped by nightly sweep.
- Consuming a token revokes all sessions for that user.

### `auth_events`

Append-only audit log. Forensic trail for security and admin visibility.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` SET NULL | NULL for events with no associated user (e.g., failed login for unknown email). |
| `event_type` | `String(64)` | NOT NULL | One of: `login_success`, `login_failure`, `logout`, `account_locked`, `password_changed`, `password_reset_requested`, `password_reset_approved`, `password_reset_rejected`, `password_reset_consumed`, `password_reset_by_admin`, `session_revoked`, `user_disabled`, `user_enabled`, `invite_created`, `invite_revoked`, `registration`, `auth.lockout_setting_changed`. |
| `actor_user_id` | `String(36)` | FK `users.id` SET NULL | Who performed the action. Same as `user_id` for self-actions. |
| `ip_address` | `String(64)` | NULL | Subject to `OPENLIA_TRUST_PROXY_HEADERS`. |
| `user_agent` | `String(512)` | NULL | |
| `metadata` | `JSON` | NULL | Event-specific context (invite ID, session ID, etc.). |
| `created_at` | `DateTime(tz)` | NOT NULL | |

**Indexes:** `ix_auth_events_user_created` on `(user_id, created_at)`, `ix_auth_events_type_created` on `(event_type, created_at)`.

No `updated_at`. Rows are immutable. Retention: indefinite in v1.

### Rate limiting

Login / registration / password-change rate limits use an in-process sliding window keyed by `(route, ip, email_or_user_id)`. Single-instance deployment means no cross-process coordination needed. Implemented in `middleware/rate_limit.py`, not a DB table.

---

## 4. LLM and data provider config tables

### `llm_providers`

One row per configured provider credential set. Admin can have multiple entries for the same provider type (e.g., two OpenAI keys for different budgets).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `kind` | `String(32)` | NOT NULL | One of `openai`, `anthropic`, `gemini`, `openrouter`, `openai_compat`, `ollama`. Maps to an adapter in `core/openlia/llm/`. |
| `label` | `String(128)` | NOT NULL | Admin-facing name ("OpenAI prod", "local Ollama"). |
| `api_key_encrypted` | `Text` | NULL | AES-256-GCM encrypted. NULL for `ollama` and when `env_var_name` is set. |
| `env_var_name` | `String(64)` | NULL | If set, runtime reads key from this env var instead of DB. |
| `base_url` | `String(512)` | NULL | Required for `openai_compat`, `ollama`, self-hosted mirrors. |
| `extra_config` | `JSON` | NULL | Adapter-specific knobs (organization ID, project ID, custom headers). |
| `is_enabled` | `Boolean` | NOT NULL DEFAULT `true` | Disabled providers' models vanish from user pickers. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |
| `created_by_user_id` | `String(36)` | FK `users.id` SET NULL | |

**Indexes:** `ix_llm_providers_kind`, `ix_llm_providers_enabled`.

**CHECK constraint:** exactly one of `api_key_encrypted` / `env_var_name` must be set, except when `kind = 'ollama'` where both may be NULL.

### `llm_models`

Admin's roster of LLM models. Each row is a model the admin has explicitly made available. A provider may expose many models; only those added here appear to users.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `provider_id` | `String(36)` | FK `llm_providers.id` RESTRICT, NOT NULL | Can't delete a provider that still has models. |
| `tier` | `String(16)` | NOT NULL | One of `thinking`, `everyday`, `quick`. |
| `model_ref` | `String(128)` | NOT NULL | Provider-native model identifier. |
| `display_name` | `String(128)` | NOT NULL | Admin-authored label shown to users. Defaults to `model_ref`. |
| `is_tier_default` | `Boolean` | NOT NULL DEFAULT `false` | At most one per tier (partial unique index). Fallback when user has no preference. |
| `is_enabled` | `Boolean` | NOT NULL DEFAULT `true` | Admin can hide without deleting. |
| `overrides` | `JSON` | NULL | Per-model settings: `temperature`, `max_tokens`, `reasoning_effort`, etc. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Indexes:** `ix_llm_models_tier_enabled`, `uq_llm_models_tier_default` (partial unique: `WHERE is_tier_default = true`), `ix_llm_models_provider_id`.

**No hard requirement to populate every tier.** Admin configures zero-or-many models per tier. Setup Wizard and Settings show a soft reminder: "We recommend configuring at least one model per tier so every department works." If a department calls into an unconfigured tier, it surfaces a `TierNotConfiguredError` rather than silently downgrading.

### `user_llm_preferences`

Per-user, per-tier model choice. Pointer table -- holds no credentials.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `user_id` | `String(36)` | FK `users.id` CASCADE | Part of composite PK. |
| `tier` | `String(16)` | | One of `thinking`, `everyday`, `quick`. Part of composite PK. |
| `model_id` | `String(36)` | FK `llm_models.id` CASCADE, NOT NULL | User's chosen model. Cascade on delete -> falls back to tier default. |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Primary key:** `(user_id, tier)`.

**Resolver order** in `core/openlia/llm/resolver.py`:

1. `user_llm_preferences` for `(user_id, tier)` -> if the pointed-to model is enabled, use it.
2. Else, `llm_models` where `tier = X AND is_tier_default = true AND is_enabled = true`.
3. Else, any enabled `llm_models` row in tier X (deterministic tiebreak: oldest `created_at`).
4. Else, raise `TierNotConfiguredError` with a message naming the empty tier.

`model_defaults.py` is repurposed to hold *shipped suggestions* for the wizard's first-run pickers, not runtime fallbacks.

### `data_providers`

Admin's data source roster. Admin-only configuration; no per-user BYO keys.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `kind` | `String(32)` | NOT NULL | `eodhd`, `fmp`, `finnhub`, `polygon`, `alphavantage`, `news_api`, ... |
| `label` | `String(128)` | NOT NULL | Admin-facing name. |
| `api_key_encrypted` | `Text` | NULL | AES-256-GCM encrypted. NULL when `env_var_name` is set. |
| `env_var_name` | `String(64)` | NULL | Alternative to DB-stored key. |
| `base_url` | `String(512)` | NULL | For self-hosted mirrors. |
| `extra_config` | `JSON` | NULL | Adapter-specific knobs. |
| `is_enabled` | `Boolean` | NOT NULL DEFAULT `true` | |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |
| `created_by_user_id` | `String(36)` | FK `users.id` SET NULL | |

**Indexes:** `ix_data_providers_kind`, `ix_data_providers_enabled`.

### `data_provider_requirement_mapping`

Which provider serves which requirement type, and in what fallback order.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `requirement_type` | `String(64)` | Part of composite PK | One of the types from the manifest (`stock_quote`, `company_news`, etc.). |
| `provider_id` | `String(36)` | FK `data_providers.id` CASCADE, Part of composite PK | |
| `priority` | `Integer` | NOT NULL | Lower = tried first. |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Primary key:** `(requirement_type, provider_id)`.

### `web_search_providers`

Configured search backends for LLM runtime tool calls.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `kind` | `String(32)` | NOT NULL | One of `brave`, `tavily`, `serper`, `you`. Provider-native web search (Anthropic, OpenAI) is read from LLM capabilities, not configured here. |
| `label` | `String(128)` | NOT NULL | |
| `api_key_encrypted` | `Text` | NULL | AES-256-GCM encrypted. |
| `env_var_name` | `String(64)` | NULL | |
| `is_enabled` | `Boolean` | NOT NULL DEFAULT `true` | |
| `priority` | `Integer` | NOT NULL DEFAULT `100` | Lower = tried first. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Indexes:** `ix_web_search_providers_enabled_priority`.

---

## 5. Secrets, encryption at rest, and env-var precedence

### Threat model (v1)

**In scope:** casual theft of the DB file (stolen laptop, backup tape, accidental git commit). A user with non-root read access to the DB but not to the process's secrets dir.

**Out of scope:** root-level attacker, malicious admin, sophisticated attackers with filesystem + memory access.

### Encryption scheme

- **Algorithm:** AES-256-GCM via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`. Authenticated encryption; rejects tampered ciphertext.
- **Key length:** 32 bytes (256 bits).
- **Key source (priority order):**
  1. `OPENLIA_SECRET_KEY` env var (base64-encoded 32 bytes). Set this in production deployments.
  2. Key file at `~/.openlia/secret.key` (0600 permissions, enforced at startup; server refuses to start if looser). Auto-generated on first run when env var is unset.
- **Ciphertext layout** in `api_key_encrypted` columns: `base64( nonce(12) || ciphertext || tag(16) )`. Fresh 12-byte nonce per encryption.
- **Associated data (AAD):** the row's `id` (UUID) is passed as AAD. Binds ciphertext to its row.

### Encrypted columns

- `llm_providers.api_key_encrypted`
- `data_providers.api_key_encrypted`
- `web_search_providers.api_key_encrypted`

### Non-encrypted credential columns (each has its own protection)

- `users.password_hash` -- Argon2id hash (one-way).
- `sessions.token_hash` -- SHA-256 (one-way).
- `password_reset_requests.token_hash` -- SHA-256 (one-way).
- `signup_invites.token_hash` -- SHA-256 (one-way) of the opaque bearer token. Raw token shown to the creator once on issuance and never persisted. Protected by randomness + admin revocation.

### Env-var precedence

Every provider row has two mutually exclusive credential sources: `api_key_encrypted` or `env_var_name`. At resolution time:

1. If `env_var_name` is set and `os.environ[env_var_name]` is present -> use env value. Never read encrypted column.
2. Else if `api_key_encrypted` is set -> decrypt and use.
3. Else (both unset, `kind = ollama` only) -> no credential needed.
4. Else -> raise `ProviderCredentialMissingError`.

**UI behavior:**

- Env-var-sourced: read-only field showing env var name ("Reading from `OPENAI_API_KEY`").
- DB-encrypted: masked field (`sk-...XXXX`, last 4 chars) with "Change key" button. Current key never displayed in full.

### Key rotation

CLI command: `openlia secrets rotate-key`.

- Accepts new key via stdin or `--new-key` flag.
- Walks every encrypted column, decrypts with old key, re-encrypts with new.
- Runs in a transaction; all-or-nothing.
- On success, writes new key to `~/.openlia/secret.key` (if file-backed) or prints instructions for `OPENLIA_SECRET_KEY`.
- No routine rotation requirement. Run manually on suspicion of compromise.

### First-run bootstrap

On `openlia serve` startup:

1. If `OPENLIA_SECRET_KEY` set -> validate 32 bytes, use it.
2. Else check `~/.openlia/secret.key`:
   - Exists: validate 0600 permissions, read. If looser: refuse to start.
   - Missing: generate 32 random bytes, write with 0600 perms, log a message.
3. Store key in module-level constant. Never log the key.

### Backup implications

A working backup requires **both**: `openlia.db` + `secret.key` (or the `OPENLIA_SECRET_KEY` value). Losing either makes API-key columns unrecoverable.

---

## 6. Chat, reports, and repository tables

### `chat_sessions`

One row per conversation thread. A user can have multiple sessions per department.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `department` | `String(32)` | NOT NULL | `secretary`, `equity_research`, `earnings_update`, `morning_briefing`, `macro_research`, `retail_sentiment`. |
| `title` | `String(256)` | NULL | Auto-generated from first message, editable. NULL until first message. |
| `is_pinned` | `Boolean` | NOT NULL DEFAULT `false` | User-pinned sessions appear at top. |
| `is_archived` | `Boolean` | NOT NULL DEFAULT `false` | Hidden from default sidebar; retrievable via filter. |
| `context` | `JSON` | NULL | Department-specific session context: `{"ticker": "AAPL", "mode": "stock_update"}`. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | Bumped on every new message. |

**Indexes:** `ix_chat_sessions_user_department` on `(user_id, department)`, `ix_chat_sessions_user_updated` on `(user_id, updated_at DESC)`.

### `chat_messages`

Individual messages within a session. Append-only.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `session_id` | `String(36)` | FK `chat_sessions.id` CASCADE, NOT NULL | |
| `role` | `String(16)` | NOT NULL | `user`, `assistant`, `system`, `tool`. |
| `content` | `Text` | NOT NULL | Message body. For `tool`: JSON-serialized tool result. For `assistant`: streamed markdown. |
| `tool_calls` | `JSON` | NULL | When assistant invoked tools: `[{"tool": "stock_quote", "args": {...}, "result_message_id": "..."}]`. |
| `model_ref` | `String(128)` | NULL | Which LLM model generated this. NULL for `user`/`system`. |
| `token_usage` | `JSON` | NULL | `{"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}`. |
| `created_at` | `DateTime(tz)` | NOT NULL | Also the display order (append-only). |

**Indexes:** `ix_chat_messages_session_created` on `(session_id, created_at)`.

**Notes:**

- No `updated_at`. Messages are immutable.
- Streaming: assistant message row inserted once stream completes. Cancelled streams stored with `\n\n[generation interrupted]` marker.
- System messages (framework preamble) stored for faithful replay; hidden by default in UI.

### `chat_attachments`

Files uploaded into a chat message. Metadata in DB; files on disk.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `message_id` | `String(36)` | FK `chat_messages.id` CASCADE, NOT NULL | |
| `filename` | `String(256)` | NOT NULL | Original filename. |
| `mime_type` | `String(128)` | NOT NULL | |
| `size_bytes` | `Integer` | NOT NULL | |
| `storage_path` | `String(512)` | NOT NULL | Relative path under `~/.openlia/uploads/<user_id>/<session_id>/`. |
| `created_at` | `DateTime(tz)` | NOT NULL | |

**Indexes:** `ix_chat_attachments_message_id`.

**Notes:**

- Files stored on filesystem, not as BLOBs. Table is an index into the file store.
- Cascade delete: session -> messages -> attachment rows. Post-delete hook removes orphaned files.
- Size limit: 10MB per file, 50MB per session (configurable at route layer).

### `reports`

Generated reports saved to the user's repository.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` SET NULL | Reports outlive author in company mode. |
| `department` | `String(32)` | NOT NULL | |
| `report_type` | `String(64)` | NOT NULL | `stock_initiation`, `stock_update`, `sector_research`, `earnings_update`, `morning_briefing`. |
| `title` | `String(512)` | NOT NULL | Auto-generated by LLM, editable. |
| `subject` | `String(128)` | NULL | Primary subject (ticker, sector, date). Used for search/filter. |
| `content_markdown` | `Text` | NOT NULL | Full report body in markdown. Canonical content. |
| `content_structured` | `JSON` | NOT NULL | `ReportSchema` payload: sections array, metadata, citations, figures. |
| `source_session_id` | `String(36)` | FK `chat_sessions.id` SET NULL | Chat that triggered generation. |
| `model_ref` | `String(128)` | NOT NULL | |
| `token_usage` | `JSON` | NULL | Total token usage for the generation run. |
| `generation_duration_ms` | `Integer` | NULL | Wall-clock time. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Indexes:** `ix_reports_user_department`, `ix_reports_user_created` on `(user_id, created_at DESC)`, `ix_reports_subject`, `ix_reports_report_type`.

**Starring / saved-to-repo signal:** originally modeled as `reports.is_starred` + `reports.tags`. Superseded by the `repo_items (user_id, report_id, created_at)` join table introduced in migration `2026-04-22-2200_repo_items_and_drop_legacy_report_cols.py`. Presence of a `repo_items` row means the user has saved the report to their Repository view; absence means not saved. User-applied tag strings were cut in the same migration (no v1 consumer depended on them). See §6 `repo_items` below.

### `repo_items`

Join table recording which reports a user has saved to their Repository view. Replaces the legacy `reports.is_starred` column.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | Saved-state belongs to the user; deleting the user drops their saves. |
| `report_id` | `String(36)` | FK `reports.id` CASCADE, NOT NULL | Report deletion drops the save. |
| `created_at` | `DateTime(tz)` | NOT NULL DEFAULT `now()` | When the user starred it. |

**Unique constraint:** `uq_repo_items_user_report` on `(user_id, report_id)` -- one row per user/report.

**Indexes:** `ix_repo_items_user_id_created_at` on `(user_id, created_at)` for the Repository "recent first" list.

### `report_versions`

Version tracking when a user re-generates or edits a report. Append-only snapshots.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `report_id` | `String(36)` | FK `reports.id` CASCADE, NOT NULL | |
| `version_number` | `Integer` | NOT NULL | 1-indexed, monotonically increasing. |
| `content_markdown` | `Text` | NOT NULL | Snapshot. |
| `content_structured` | `JSON` | NOT NULL | Snapshot. |
| `change_reason` | `String(64)` | NULL | `regenerated`, `user_edit`, `section_regenerated`. |
| `model_ref` | `String(128)` | NULL | NULL for user edits. |
| `created_at` | `DateTime(tz)` | NOT NULL | |

**Unique constraint:** `uq_report_versions_report_version` on `(report_id, version_number)`.

**Notes:**

- `reports` always holds current version. `report_versions` holds previous.
- Version 1 snapshotted lazily on first edit/regeneration.

### `portfolio_holdings`

User's reference portfolio. Manual entry, not brokerage sync.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `ticker` | `String(16)` | NOT NULL | Uppercase, normalized in app code. |
| `name` | `String(256)` | NULL | Auto-populated from data provider on add. |
| `shares` | `Numeric(18, 6)` | NULL | NULL = watchlist only. |
| `cost_basis` | `Numeric(18, 6)` | NULL | Average cost per share. |
| `currency` | `String(3)` | NOT NULL DEFAULT `'USD'` | ISO 4217. |
| `notes` | `Text` | NULL | Freeform user notes. |
| `added_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Unique constraint:** `uq_portfolio_user_ticker` on `(user_id, ticker)`.

### `watchlists`

User-defined ticker groupings independent of portfolio holdings.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `name` | `String(128)` | NOT NULL | |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Unique constraint:** `uq_watchlists_user_name` on `(user_id, name)`.

### `watchlist_items`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `watchlist_id` | `String(36)` | FK `watchlists.id` CASCADE | Part of composite PK. |
| `ticker` | `String(16)` | NOT NULL | Part of composite PK. Uppercase, normalized. |
| `added_at` | `DateTime(tz)` | NOT NULL | |

**Primary key:** `(watchlist_id, ticker)`.

---

## 7. Department-specific state, dashboard config, and infrastructure tables

### `wizard_state`

Tracks setup wizard progress. Singleton row.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `Integer` | PK CHECK `id = 1` | Enforced singleton. |
| `status` | `String(32)` | NOT NULL DEFAULT `'not_started'` | `not_started`, `in_progress`, `completed`. |
| `current_step` | `String(32)` | NOT NULL DEFAULT `'mode'` | Slug of the step the admin is on (`mode`, `admin`, `llm`, `data`, `smtp`, `summary`, `done`). |
| `completed_steps` | `JSON` | NOT NULL DEFAULT `[]` | Ordered list of completed step slugs. Drives the progress bar. |
| `active_session_token` | `String(64)` | NULL | SHA-256 hex of the wizard's anti-replay session cookie. Cleared on completion or reset. |
| `mode` | `String(16)` | NULL | `personal` or `company`. Set on step 1. |
| `step_data` | `JSON` | NOT NULL DEFAULT `{}` | Per-step intermediate state. Cleared on completion. |
| `started_at` | `DateTime(tz)` | NULL | |
| `completed_at` | `DateTime(tz)` | NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Notes:**

- Seeded with `status = 'not_started'` on first startup.
- `openlia serve` checks this on boot; if not completed, all non-wizard routes redirect.
- `openlia wizard reset` CLI resets to `not_started` and clears `active_session_token` + `completed_steps`.
- Shape finalized by Plan 10 setup wizard. Original Plan 1a shape used an `Integer` `current_step` without the `completed_steps` / `active_session_token` columns; migration `2026-04-21-0001_reshape_wizard_state.py` flipped `current_step` to `String(32)` and added the two new columns, and `2026-04-22-1800_drop_wizard_state_legacy_columns.py` removed the vestigial integer column.

### `config_store`

Narrow KV escape hatch for miscellaneous settings.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `key` | `String(128)` | PK | Dotted namespace: `feature.dark_mode`, `system.telemetry_opt_in`. |
| `value` | `JSON` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Expected keys in v1:**

- `wizard.completed` -- fast boolean check.
- `system.instance_id` -- UUID4 for anonymous telemetry.
- `system.secret_key_fingerprint` -- SHA-256 of first 8 bytes of secret key; detects key mismatch.
- `auth.lockout.enabled` -- boolean, default `true`. When `false`, the login flow skips both the increment of `users.failed_login_attempts` and the check on `users.locked_until`. Toggled via `openlia admin lockout enable | disable`. See `AccountManagementSpec.md` § 6.2 and `cli-surface-design.md`.

### `pt_user_configs`

Per-user Panic Thermometer dashboard configuration. Replaces `window.storage`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, UNIQUE | One config per user. |
| `active_preset_id` | `String(36)` | FK `pt_presets.id` SET NULL | Currently loaded preset. NULL = custom unsaved config. |
| `panel_config` | `JSON` | NOT NULL | Full panel layout array. Each element: `{"panel_id": "vix", "enabled": true, "thresholds": {...}, "weight": 1.5}`. |
| `composite_settings` | `JSON` | NOT NULL DEFAULT `{}` | Global scoring: `{"aggregation": "weighted_average", "alert_threshold": 75}`. |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

### `pt_presets`

Named configuration snapshots. Shipped library presets + user-created.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NULL | NULL for shipped library presets (global). |
| `name` | `String(128)` | NOT NULL | |
| `description` | `Text` | NULL | |
| `is_shipped` | `Boolean` | NOT NULL DEFAULT `false` | Shipped presets seeded by migration. |
| `panel_config` | `JSON` | NOT NULL | Same shape as `pt_user_configs.panel_config`. |
| `composite_settings` | `JSON` | NOT NULL DEFAULT `{}` | |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Unique constraints:** `uq_pt_presets_user_name` on `(user_id, name)`. Partial unique on `(name) WHERE user_id IS NULL` for shipped presets.

**Notes:**

- "Load preset" copies into `pt_user_configs`. "Save as preset" snapshots from `pt_user_configs`.
- Import/export serializes a preset row as JSON file download/upload.

### `mr_dashboard_state`

Per-user state for Macro Research Dalio dashboards. One row per user per dashboard.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `dashboard` | `String(32)` | NOT NULL | `debt_cycle`, `four_seasons`, `all_weather`, `world_order`, `five_forces`. |
| `view_config` | `JSON` | NOT NULL DEFAULT `{}` | Saved view: selected country, time range, chart zoom, collapsed panels. |
| `threshold_overrides` | `JSON` | NOT NULL DEFAULT `{}` | User-customized T1/T2 thresholds. Keys are indicator IDs. Empty = all defaults. |
| `assessment_schedule` | `String(64)` | NULL | Cadence at which the background scheduler regenerates the T4/T5 assessment, stored as a 5-field cron expression (`'MIN HOUR DOM MON DOW'`) evaluated in UTC. Service-layer helpers also accept the shorthands `weekly`, `quarterly` and expand them to their canonical cron form before persisting. NULL = follow the global default for the dashboard. |
| `last_assessment_at` | `DateTime(tz)` | NULL | UTC timestamp of the most recent successful assessment run. Used by catch-up logic to decide whether to regenerate on next scheduler tick. |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Unique constraint:** `uq_mr_dashboard_user_dashboard` on `(user_id, dashboard)`.

**Schedule columns.** `assessment_schedule` / `last_assessment_at` were added by migration `2026-04-24-0001_mr_dashboard_state_schedule_cols.py` to support the Macro-Research background-assessment loop. The enum is defined in `background-task-scheduling-design.md` §Department schedule tables.

### `mr_assessment_cache`

Cached T4/T5 LLM assessment results. Global (not per-user) because assessments depend on market data and thresholds, not user identity.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `dashboard` | `String(32)` | NOT NULL | |
| `assessment_type` | `String(16)` | NOT NULL | `t4` or `t5`. |
| `input_hash` | `String(64)` | NOT NULL | SHA-256 of canonical input payload. Same hash = cache hit. |
| `result` | `JSON` | NOT NULL | LLM's structured assessment output. |
| `model_ref` | `String(128)` | NOT NULL | |
| `token_usage` | `JSON` | NULL | |
| `generated_at` | `DateTime(tz)` | NOT NULL | |
| `expires_at` | `DateTime(tz)` | NOT NULL | `generated_at + cadence` (e.g., +7 days). |

**Unique constraint:** `uq_mr_assessment_dash_type_hash` on `(dashboard, assessment_type, input_hash)`.

**Notes:** Expired entries kept 30 days for historical comparison, then pruned.

### `rs_user_config`

Per-user Retail Sentiment dashboard configuration.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, UNIQUE | |
| `active_tab` | `String(32)` | NOT NULL DEFAULT `'overview'` | `overview`, `source_analysis`, `signal_validation`. |
| `metric_settings` | `JSON` | NOT NULL DEFAULT `{}` | Per-metric visibility and display: `{"wsb_mention_velocity": {"visible": true, "chart_range": "7d"}}`. |
| `filter_presets` | `JSON` | NOT NULL DEFAULT `[]` | Saved filter sets. |
| `refresh_interval_minutes` | `Integer` | NOT NULL DEFAULT `60` | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Notes:** RS watchlist handled by `watchlists`/`watchlist_items` tables. Dashboard references watchlist by ID.

### `rs_snapshots`

Point-in-time sentiment metric snapshots for historical trend view. Global (not per-user).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `ticker` | `String(16)` | NOT NULL | |
| `snapshot_data` | `JSON` | NOT NULL | All 12 metric values. |
| `source_breakdown` | `JSON` | NULL | Per-source contribution data. |
| `captured_at` | `DateTime(tz)` | NOT NULL | |

**Indexes:** `ix_rs_snapshots_ticker_captured` on `(ticker, captured_at DESC)`.

**Notes:** Captured once per refresh cycle per ticker. 90-day retention (configurable via `config_store` key `rs.snapshot_retention_days`).

### `rs_classification_log`

Append-only audit trail of every retail-sentiment LLM classification request. Used to debug scoring regressions and to drive the v2 refresher/training pipeline.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `ticker` | `String(16)` | NOT NULL | Normalized uppercase. |
| `batch_id` | `String(36)` | NULL | Groups classifications produced by a single refresh pass. NULL if triggered ad-hoc. |
| `classifier_version` | `String(32)` | NOT NULL | e.g. `rs-v1`, `rs-refreshing-v2`. |
| `model_ref` | `String(128)` | NOT NULL | Provider/model the classifier called. |
| `prompt_tokens` | `Integer` | NOT NULL DEFAULT `0` | |
| `completion_tokens` | `Integer` | NOT NULL DEFAULT `0` | |
| `classification` | `JSON` | NOT NULL | Raw structured output returned by the LLM. |
| `latency_ms` | `Integer` | NULL | Wall-clock time for the classifier call. |
| `error` | `Text` | NULL | Error string if the classification failed; row still written to preserve a complete audit. |
| `created_at` | `DateTime(tz)` | NOT NULL DEFAULT `now()` | |

**Indexes:** `ix_rs_classification_log_ticker_created` on `(ticker, created_at)`; `ix_rs_classification_log_batch` on `(batch_id)`.

**Notes:** Added by migration `2026-04-24-0100_rs_classification_log.py` as the v2 follow-on to `retail-sentiment-dashboard-design.md`. Append-only; no user-facing delete path. Pruning is scoped to the nightly maintenance sweep (§7 below) once the retention policy is locked.

### `fe_saved_formulas`

User-created formulas for PT custom panels and MR T1/T2 overrides.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `name` | `String(128)` | NOT NULL | |
| `expression` | `Text` | NOT NULL | Formula DSL expression (parsed and validated on save). |
| `description` | `Text` | NULL | |
| `department_scope` | `String(32)` | NULL | `panic_thermometer`, `macro_research`, or NULL (generic). |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `updated_at` | `DateTime(tz)` | NOT NULL | |

**Unique constraint:** `uq_fe_formulas_user_name` on `(user_id, name)`.

**Notes:** Shipped example formulas stored in code as constants, not in DB. Users "copy to my formulas" for an editable DB row.

### `mb_schedules`

Per-user Morning Briefing schedules. A user can configure multiple schedules per day (e.g., a pre-market and a post-market briefing). Added by `background-task-scheduling-design.md`; UI in `MorningBriefingsPageSpec.md` § Settings View — Schedule.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `time` | `String(5)` | NOT NULL | HH:MM format |
| `timezone` | `String(64)` | NOT NULL | IANA timezone (e.g. `America/New_York`) |
| `days_of_week` | `Text` | NOT NULL | JSON array of day abbreviations (e.g. `["Mon","Tue","Wed","Thu","Fri"]`) |
| `label` | `String(64)` | NULL | User-assigned label (e.g. "Pre-Market") |
| `is_enabled` | `Boolean` | NOT NULL, default `true` | |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `last_run_at` | `DateTime(tz)` | NULL | Updated by the scheduler after each successful run |

**Indexes:** `ix_mb_schedules_user` on `(user_id)`.

### `eu_schedules`

Per-user Earnings Update scan schedules. Same shape as `mb_schedules`. Added by `background-task-scheduling-design.md`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `time` | `String(5)` | NOT NULL | HH:MM format |
| `timezone` | `String(64)` | NOT NULL | IANA timezone (e.g. `America/New_York`) |
| `days_of_week` | `Text` | NOT NULL | JSON array of day abbreviations (e.g. `["Mon","Tue","Wed","Thu","Fri"]`) |
| `label` | `String(64)` | NULL | User-assigned label (e.g. "Pre-Market Scan") |
| `is_enabled` | `Boolean` | NOT NULL, default `true` | |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `last_run_at` | `DateTime(tz)` | NULL | Updated by the scheduler after each successful run |

**Indexes:** `ix_eu_schedules_user` on `(user_id)`.

### `job_runs`

History of every scheduled background job execution. Added by `background-task-scheduling-design.md`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | UUID |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NULL | NULL for `system_maintenance` |
| `job_type` | `String(32)` | NOT NULL | `mb_briefing`, `eu_scan`, `mr_assessment`, `system_maintenance` |
| `schedule_id` | `String(36)` | NULL | FK to the department-specific schedule table row. NULL for maintenance and user-triggered retries. |
| `status` | `String(16)` | NOT NULL | `running`, `completed`, `failed`, `cancelled` |
| `started_at` | `DateTime(tz)` | NOT NULL | |
| `completed_at` | `DateTime(tz)` | NULL | |
| `error_message` | `Text` | NULL | NULL on success |
| `result_summary` | `Text` | NULL | JSON. E.g. `{"reports_generated": 3, "report_ids": [...]}` |
| `retry_of` | `String(36)` | FK `job_runs.id`, NULL | Points to original failed run if this is a user-triggered retry |
| `attempt` | `Integer` | NOT NULL, default 1 | 1 for first try, 2-4 for automatic retries |

**Indexes:**
- `ix_job_runs_user_type_started` on `(user_id, job_type, started_at)`.
- `ix_job_runs_status` on `(status)`.
- `ix_job_runs_schedule` on `(schedule_id, started_at)`.

### `user_notifications`

Lightweight notification records for background job results. Added by `background-task-scheduling-design.md`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `String(36)` | PK | UUID |
| `user_id` | `String(36)` | FK `users.id` CASCADE, NOT NULL | |
| `type` | `String(32)` | NOT NULL | `report_ready`, `assessment_ready`, `job_failed` |
| `department` | `String(32)` | NOT NULL | `morning_briefing`, `earnings_update`, `macro_research` |
| `message` | `Text` | NOT NULL | Human-readable summary |
| `job_run_id` | `String(36)` | FK `job_runs.id`, NULL | |
| `created_at` | `DateTime(tz)` | NOT NULL | |
| `read_at` | `DateTime(tz)` | NULL | NULL until read |

**Indexes:** `ix_notifications_user_unread` on `(user_id, read_at)`.

**Retention:** 30 days (pruned by nightly maintenance sweep).

### Nightly maintenance sweep

Single `openlia maintenance` CLI command handles all pruning:

| Target | Rule |
|---|---|
| `sessions` | Delete where `expires_at < now() - 7 days`. |
| `password_reset_requests` | Flip to `expired` where `status = 'approved' AND expires_at < now()`. Delete rows older than 90 days. |
| `mr_assessment_cache` | Delete where `expires_at < now() - 30 days`. |
| `rs_snapshots` | Delete where `captured_at < now() - <retention_days>`. |
| `user_notifications` | Delete where `created_at < now() - 30 days`. |
| `job_runs` | Delete where `status IN ('completed', 'cancelled') AND started_at < now() - 90 days`. Failed runs kept longer for audit. |

Server runs this once on startup and on a configurable daily interval via the background task scheduler (see `background-task-scheduling-design.md`). CLI command available for manual runs.

---

## 8. Environment variables

Complete list of env vars introduced or affected by this design:

| Variable | Purpose | Default |
|---|---|---|
| `OPENLIA_HOME` | Filesystem root for the SQLite DB, uploads, and `secret.key`. `OPENLIA_DB_URL` and secret-key-file resolution fall back to `$OPENLIA_HOME/...` when unset. | `~/.openlia` |
| `OPENLIA_DB_URL` | SQLAlchemy database URL | `sqlite:///$OPENLIA_HOME/openlia.db` |
| `OPENLIA_SECRET_KEY` | Base64-encoded 32-byte AES key for API key encryption | Falls back to `$OPENLIA_HOME/secret.key` file |
| `OPENLIA_TRUST_PROXY_HEADERS` | Trust `X-Forwarded-For` / `X-Forwarded-Proto` headers | `false` |
| `OPENLIA_COOKIE_SECURE` | Set `Secure` flag on session cookie | `true` in company mode, `false` in personal |

Provider-specific env vars (e.g., `OPENAI_API_KEY`, `EODHD_API_KEY`) are read by name when an `env_var_name` column references them. They are not enumerated here because the admin chooses the names during setup.

---

## 9. Table inventory

40 tables total. This count matches `EXPECTED_TABLES` in `packages/server/tests/test_db/test_migrations.py` (single source of truth for the shipped schema). Rows 36-40 are owned by later phase plans (11/14/15/16) but land in the same Alembic migration chain, so they are listed here for completeness; their column definitions live in the owning plans, not in this spec.

| # | Table | Section | Category |
|---|---|---|---|
| 1 | `users` | 3 | Auth |
| 2 | `sessions` | 3 | Auth |
| 3 | `signup_invites` | 3 | Auth |
| 4 | `signup_policy` | 3 | Auth |
| 5 | `password_reset_requests` | 3 | Auth |
| 6 | `auth_events` | 3 | Auth |
| 7 | `llm_providers` | 4 | Config |
| 8 | `llm_models` | 4 | Config |
| 9 | `user_llm_preferences` | 4 | Config |
| 10 | `data_providers` | 4 | Config |
| 11 | `data_provider_requirement_mapping` | 4 | Config |
| 12 | `web_search_providers` | 4 | Config |
| 13 | `chat_sessions` | 6 | Content |
| 14 | `chat_messages` | 6 | Content |
| 15 | `chat_attachments` | 6 | Content |
| 16 | `reports` | 6 | Content |
| 17 | `report_versions` | 6 | Content |
| 18 | `repo_items` | 6 | Content |
| 19 | `portfolio_holdings` | 6 | Content |
| 20 | `watchlists` | 6 | Content |
| 21 | `watchlist_items` | 6 | Content |
| 22 | `wizard_state` | 7 | Infrastructure |
| 23 | `config_store` | 7 | Infrastructure |
| 24 | `pt_user_configs` | 7 | Dashboard |
| 25 | `pt_presets` | 7 | Dashboard |
| 26 | `mr_dashboard_state` | 7 | Dashboard |
| 27 | `mr_assessment_cache` | 7 | Dashboard |
| 28 | `rs_user_config` | 7 | Dashboard |
| 29 | `rs_snapshots` | 7 | Dashboard |
| 30 | `rs_classification_log` | 7 | Dashboard (v2 follow-on) |
| 31 | `fe_saved_formulas` | 7 | Dashboard |
| 32 | `mb_schedules` | 7 | Scheduler |
| 33 | `eu_schedules` | 7 | Scheduler |
| 34 | `job_runs` | 7 | Scheduler |
| 35 | `user_notifications` | 7 | Scheduler |
| 36 | `user_prefs` | Plan 11 | User preferences |
| 37 | `er_user_configs` | Plan 14 | Equity Research |
| 38 | `eu_watchlist` | Plan 15 | Earnings Update |
| 39 | `eu_user_configs` | Plan 15 | Earnings Update |
| 40 | `mb_user_configs` | Plan 16 | Morning Briefing |

---

## 10. Deployment posture

Company mode defaults to HTTPS-domain deployment from v1. Three recommended recipes:

### Cloudflare Tunnel (recommended default)

- Admin runs `cloudflared tunnel` alongside `openlia serve` on the same machine.
- Cloudflare provisions TLS, DNS, and DDoS protection. No port forwarding, no firewall rules.
- Set `OPENLIA_TRUST_PROXY_HEADERS=true` and `OPENLIA_COOKIE_SECURE=true`.
- Optional: add Cloudflare Access for an extra authentication layer (v2 consideration for SSO integration).

### Docker + Caddy (self-managed)

- Admin runs OpenLIA in Docker behind a Caddy reverse proxy.
- Caddy auto-provisions Let's Encrypt TLS certs.
- Requires a public domain and port 443 open.
- Set `OPENLIA_TRUST_PROXY_HEADERS=true` and `OPENLIA_COOKIE_SECURE=true`.

### LAN-only (fallback)

- Admin runs `openlia serve --host 0.0.0.0 --port 8000` on the local network.
- No TLS by default. Users access via `http://<lan-ip>:8000`.
- Set `OPENLIA_COOKIE_SECURE=false`.
- Appropriate for small offices where all users are on the same network.

---

## 11. v2 horizon

Items explicitly deferred from v1 but anticipated:

- **Google OAuth**: re-introduce `auth_accounts` table (user_id, provider, provider_user_id, linked_at). Auto-link on email match or create pending-approval user. Library: `authlib`.
- **SMTP integration**: optional module for delivering password-reset links and invite emails automatically. Gate behind an env var.
- **Cloudflare Access SSO**: trust `Cf-Access-Jwt-Assertion` as an auth mode, auto-provision users from CF identity.
- **Provider response caching**: add a `data_cache` table to reduce API call volume for frequently accessed data.
- **User-authored custom tools**: per-department tool registration (OpenAPI specs, MCP servers, Python callables).
- **Postgres support**: portable types chosen in Section 2 mean the schema migrates cleanly. Add a Postgres-specific session engine and connection pool configuration.

---

## Cross-references

This spec requires follow-up edits to the following existing specs (tracked in `planning/GAPS.md` under "Database Design > Remaining Tasks"):

- `planning/specs/components/AccountManagementSpec.md`
- `planning/specs/pages/LoginPageSpec.md`
- `planning/specs/pages/SetupWizardSpec.md`
- `planning/specs/pages/SettingsPageSpec.md`
- `planning/specs/systems/llm-provider-design.md`
- `planning/specs/systems/llm-runtime-design.md`
- `planning/specs/systems/data-provider-design.md`
- `planning/specs/pages/departments/PanicThermometerPageSpec.md`
- `planning/specs/systems/macro-research-dalio-dashboards-design.md`
- `planning/specs/systems/retail-sentiment-dashboard-design.md`
- `planning/specs/components/ChatHistorySpec.md`
- `planning/PLAN.md`
- `planning/projectStructure.md`
