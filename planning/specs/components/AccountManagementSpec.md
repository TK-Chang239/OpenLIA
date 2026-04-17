# Account Management Spec

## 1) Purpose and Product Role

Account Management is the identity, authentication, and session control layer for OpenLIA's **company deployment mode**. It creates user identities, issues and validates sessions, protects user-scoped resources, handles admin-approved password recovery, and enforces baseline abuse controls.

### Deployment-mode scope

- **Personal mode:** No authentication. This spec is inert -- its routes and middleware are not mounted, and its tables are seeded with a single synthetic `local` user so that product tables (Portfolio, Repository, chat history, per-user LLM preferences) can use the same `user_id` FK in both modes. See `database-design.md` for the personal-mode seeding contract.
- **Company mode:** Full spec applies. All user-scoped resources are keyed to the authenticated user.

The **first admin account is created by the Setup Wizard** (see `SetupWizardSpec.md` Step 2b), not through `/auth/register`. After setup, new-account creation is governed by an admin-configured **signup policy**: `invite_only` (v1 default), `closed` (no public registration), or `open` (reserved for v2).

---

## 2) Product Requirements from Login Design

Implements `LoginPageSpec.md`:

- Email/password login
- Registration (subject to signup policy; invite-only in v1 company mode)
- Admin-approved Forgot Password flow (user requests, admin approves, delivers one-time link out-of-band)
- Keep Me Logged In (persistent vs browser-session cookie)
- Rate limiting + 15-minute account lockout after 5 consecutive failed logins

---

## 3) Scope

### In Scope (v1, company mode only)

1. Email/password authentication with Argon2id password hashing
2. Invite-only registration with multi-use, optionally-capped invites
3. Session lifecycle: issue, validate, revoke
4. Admin-approved password reset via `password_reset_requests` table (no SMTP required)
5. Direct admin password reset via `users.must_change_password` flag (for onboarding)
6. Route-protection middleware and unauthenticated redirect
7. Login abuse protection: per-account and per-IP rate limits plus account lockout
8. Audit/security event logging
9. Admin CLI for operational tasks (unlock account, reset password, revoke sessions, manage invites)

### Out of Scope (v1)

- Google OAuth / any OAuth provider (v2)
- MFA / 2FA
- Passwordless / magic-link login
- Self-service account deletion
- Organizations / teams / RBAC beyond `is_admin` (bool)
- SMTP email delivery
- Distributed rate limiting across multiple server instances
- PII export / deletion workflows (GDPR DSR)

---

## 4) Technical Approach

### 4.1 Stack

| Concern | Choice |
|---|---|
| Auth routes | First-party FastAPI routes in `packages/server/src/openlia_server/routes/auth.py` |
| Password hashing | `argon2-cffi` (Argon2id) |
| Session storage | Server-side opaque tokens stored in `sessions` table |
| Session transport | HTTP-only cookie |
| Rate limiting | In-process sliding window (single-instance self-hosted) |
| Database | SQLAlchemy over SQLite. See `database-design.md` for portable type conventions. |

No Next.js, Auth.js, Prisma, Redis, or third-party managed auth. Everything runs inside the FastAPI process.

### 4.2 Why DB-backed opaque sessions (not JWT)

- Revocation is immediate -- a single row update.
- Session rotation doesn't create stale-token edge cases.
- Self-hosted deployments rarely need JWT's stateless scaling benefits.
- No signing-key rotation to manage.
- Aligns with the SQLite transactional guarantees already in use.

---

## 5) Data Model

All tables live in the application database defined by `database-design.md`. Full table schemas, including column types, constraints, indexes, and cascade rules, are the canonical definitions in `database-design.md` Sections 3-4. This section summarizes the tables this spec uses.

### Tables owned by this spec

- **`users`** -- canonical identity. One row per person; synthetic `local` row in personal mode. Key columns: `id`, `email`, `display_name`, `password_hash`, `is_admin`, `is_disabled`, `must_change_password`, `last_login_at`.
- **`sessions`** -- opaque server-side session tokens. Stored hashed (SHA-256). Cookie carries the raw token; server only stores the hash. Key columns: `token_hash`, `user_id`, `expires_at`, `last_seen_at`, `revoked_at`.
- **`signup_invites`** -- multi-use, optionally-capped invite tokens for registration. Key columns: `token`, `max_uses`, `use_count`, `expires_at`, `revoked_at`.
- **`signup_policy`** -- singleton row controlling registration behavior. Key columns: `mode` (`invite_only`, `closed`, `open`), `allowed_email_domains`.
- **`password_reset_requests`** -- admin-approved password reset flow. Key columns: `user_id`, `status`, `token_hash`, `expires_at`, `approved_by_user_id`.
- **`auth_events`** -- append-only audit log. Key columns: `user_id`, `event_type`, `actor_user_id`, `ip_address`, `metadata`.

### User-scoped product data contract

Every product table storing user-owned data (`portfolio_holdings`, `chat_sessions`, `chat_messages`, `user_llm_preferences`, `user_notifications`, `mb_schedules`, `eu_schedules`, dashboard state tables) MUST:

1. Include `user_id` as a non-null FK to `users.id`.
2. Carry an index on `user_id` for list queries.
3. In personal mode, all rows belong to the synthetic `local` user (seeded on first startup). This keeps the schema identical across modes.

### Migrations

Alembic migrations live under `packages/server/src/openlia_server/db/migrations/`. Initial ordering:

1. Create auth tables.
2. Seed the synthetic `local` user for personal mode (`id='local'`, `is_admin=true`, `email='local@openlia.local'`, `password_hash=NULL`).
3. Product tables add `user_id` FKs in their own migration files.

---

## 6) Authentication Flows

### 6.1 Registration (email/password, invite-only)

Gated by the admin-configured signup policy.

1. Validate payload (email RFC format, password meets policy).
2. Normalize email (lowercase, trim).
3. Apply signup policy:
   - `closed` -> 403 "Registration is closed."
   - `invite_only` -> validate invite token from URL query param. If missing, invalid, expired, revoked, or at capacity -> 403.
   - `open` -> proceed (v2 only).
4. Apply domain allowlist: if `signup_policy.allowed_email_domains` is non-empty, reject emails not in the list.
5. If a user exists with this email: return generic "registration failed" (no enumeration).
6. Hash password with Argon2id.
7. In a single transaction: insert `users` row, increment `signup_invites.use_count`.
8. Issue session, set cookie, emit `registration` auth event.

### 6.2 Login (email/password)

1. Validate payload.
2. Normalize email; look up user.
3. If no user OR `password_hash IS NULL`: perform a dummy Argon2 verify against a throwaway hash (constant-time padding), emit `login_failure`, return generic error.
4. If `is_disabled = true`: emit `login_failure` with `metadata.reason='disabled'`, return "Account is disabled. Contact your administrator."
5. If the lockout feature is enabled (`config_store.auth.lockout.enabled = true`, the default) **and** `locked_until` is set and in the future: emit `login_failure` with `metadata.reason='locked'`, return a lockout response carrying `retry_after_seconds`. When the feature is disabled, skip this check entirely (do not consult `locked_until`).
6. Verify password against `password_hash`.
7. On invalid: if the lockout feature is enabled, increment `failed_login_attempts`; if the new count `>= 5`, set `locked_until = now() + 15min` and emit `account_locked`. Always emit `login_failure`. When the feature is disabled, do not mutate `failed_login_attempts` or `locked_until`.
8. On valid: reset `failed_login_attempts=0`, clear `locked_until` (regardless of whether the feature is currently enabled, so re-enabling later does not resurrect a stale lock), set `last_login_at=now()`, create a new session, emit `login_success`.
9. If `must_change_password = true`: session is issued but the response includes `{"must_change_password": true}`. The frontend routes to the change-password form before allowing any other action.

### 6.3 Admin-Approved Password Reset

1. **User initiates:** login page "Forgot password?" form -> `POST /auth/password-reset/request` with `{email}`. Server always returns 200 (no email enumeration). If the email matches an active user, a `pending` row is inserted into `password_reset_requests`. Only one `pending` row per user at a time; a second request DELETEs the existing pending row and INSERTs a new one.
2. **Admin reviews:** admin panel (Settings -> Admin -> Password Reset Requests) shows pending requests. Admin clicks Approve or Reject.
   - Approve: server generates 32-byte random token, stores SHA-256 hash in `token_hash`, sets `expires_at = now + 24h`, `status = approved`. UI shows the one-time link to admin exactly once. Admin copies and delivers out-of-band (Slack, Signal, in person).
   - Reject: `status = rejected`, row kept for audit.
3. **User redeems:** clicks the link -> `/reset-password?token=<...>` page -> enters new password -> `POST /auth/password-reset/consume`. Server validates hash + status + expiry, updates `users.password_hash`, sets `consumed_at` and `status = consumed`, **revokes all existing sessions** for that user, logs `password_reset_consumed` auth event.

Rate limit: 5 requests per IP per hour on the request endpoint.

### 6.4 Direct Admin Password Reset (Onboarding)

Admin uses CLI or admin panel to reset a user's password directly:

1. Admin sets a new temporary password for the user.
2. Server hashes and updates `users.password_hash`, sets `users.must_change_password = true`, revokes all sessions.
3. Admin delivers the temporary password out-of-band.
4. User logs in with the temporary password; the `must_change_password` flag forces a password-change form before any other action.
5. On successful change: `must_change_password` set to `false`, emit `password_changed` auth event.

### 6.5 Logout

- `POST /auth/logout`: set `revoked_at = now()` on the current session; clear cookie.
- `POST /auth/logout-all`: set `revoked_at = now()` on all non-revoked sessions for `current_user`.

---

## 7) Session Design

### 7.1 Cookie

| Attribute | Value |
|---|---|
| Name | `openlia_session` |
| Value | 32-byte base64url random token; only SHA-256 hash is persisted |
| `HttpOnly` | `true` |
| `Secure` | Controlled by `OPENLIA_COOKIE_SECURE` (defaults `true` in company mode, `false` in personal) |
| `SameSite` | `Lax` |
| `Path` | `/` |

### 7.2 TTL

- **Persistent** (Keep Me Logged In): `expires_at = now() + 30 days`, cookie `Max-Age=30 days`.
- **Non-persistent**: browser-session cookie (no `Max-Age`); server enforces `expires_at = now() + 12 hours` as an absolute cap.
- **Inactivity cap** (company mode): a session with `last_seen_at < now() - 30 days` is treated as expired regardless of `expires_at`.
- **Personal mode**: the Keep Me Logged In checkbox is not shown (no login form). The server sets a 1-year cookie purely so the browser persists it across restarts; per § 10.3, `require_auth()` returns the synthetic `local` user without consulting the `sessions` table at all, so `expires_at` and the inactivity cap are not enforced. No env var override.

### 7.3 Rotation

- Issue a new session row on login and on successful password reset (both admin-approved and direct).
- `POST /auth/logout` revokes only the current session; `POST /auth/logout-all` revokes every session for the user.
- A successful password reset (either flow) revokes all active sessions (forces re-login).

---

## 8) Security Controls

### 8.1 Credential handling

- Argon2id with `argon2-cffi`: `time_cost=3`, `memory_cost=65536` (64 MiB), `parallelism=4`.
- All password comparisons go through `argon2-cffi`'s constant-time verify.
- Passwords, session tokens, reset tokens, and invite tokens are never logged.

### 8.2 Anti-enumeration and timing

Uniform error code, status, and message for: unknown email, wrong password, disabled account. Timing padded by a dummy Argon2 verify when the user or `password_hash` is missing.

### 8.3 Rate limiting

Sliding-window counters in process memory. Single-instance deployment is the v1 assumption.

| Key | Limit |
|---|---|
| `login:ip=<ip>` | 20 attempts / 5 min |
| `login:email=<email>` | 10 attempts / 5 min |
| `password-reset-request:ip=<ip>` | 5 requests / 1 hour |
| `register:ip=<ip>` | 5 requests / 1 hour |

Account lockout (5 consecutive failures -> 15 min lock) is separate and persisted on the `users` row so it survives restarts. The feature is gated by the `auth.lockout.enabled` key in `config_store` (default `true`); admins can toggle it with `openlia admin lockout enable | disable | status`. When disabled, the login path neither increments `failed_login_attempts` nor consults `locked_until`.

### 8.4 CSRF

Cookies use `SameSite=Lax`, which blocks cross-site form POSTs. The frontend is same-origin to the backend in production (static files served by FastAPI) and proxied same-origin in dev (Vite). No additional CSRF token is required for v1.

### 8.5 Data protection

- API keys (LLM, data providers, web search) are encrypted at rest with AES-256-GCM per `database-design.md` Section 5. Session tokens and password reset tokens are stored as SHA-256 hashes (one-way). Passwords are Argon2id hashes.
- IP addresses are stored in plaintext in `auth_events.ip_address` and `sessions.ip_address`. Behind a proxy, only trusted when `OPENLIA_TRUST_PROXY_HEADERS=true`.
- User-Agent strings are truncated to 512 chars.

### 8.6 Retention

- `auth_events`: indefinite in v1.
- `sessions`: rows with `expires_at < now() - 7 days` are pruned by the nightly maintenance sweep.
- `password_reset_requests`: `approved` rows with `expires_at < now()` are flipped to `expired`. Rows older than 90 days are deleted.

---

## 9) API Surface

All routes live in `packages/server/src/openlia_server/routes/auth.py`. Not mounted in personal mode.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Email/password signup, requires invite token in v1 |
| POST | `/auth/login` | Email/password login |
| POST | `/auth/logout` | Revoke current session |
| POST | `/auth/logout-all` | Revoke all sessions for the current user |
| GET | `/auth/session` | `{user_id, email, display_name, is_admin}` or 401 |
| POST | `/auth/password-reset/request` | User initiates password reset. Always returns 200. |
| POST | `/auth/password-reset/consume` | User redeems approved reset token with `{token, new_password}` |
| POST | `/auth/change-password` | Authenticated user changes password with `{current_password, new_password}` |
| GET | `/auth/signup-policy` | Returns `{mode, invite_required}` for the login page to gate registration UI |

Admin endpoints (require `is_admin = true`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/users` | List users (id, email, display_name, is_admin, is_disabled, last_login_at) |
| POST | `/admin/users/{id}/disable` | Disable user, revoke sessions |
| POST | `/admin/users/{id}/enable` | Re-enable user |
| POST | `/admin/users/{id}/reset-password` | Direct admin reset with `{new_password}` |
| GET | `/admin/invites` | List invites (id, token, label, use_count, max_uses, expires_at, revoked_at) |
| POST | `/admin/invites` | Create invite with `{label?, max_uses?, expires_at?}` |
| POST | `/admin/invites/{id}/revoke` | Revoke an invite |
| GET | `/admin/password-reset-requests` | List pending requests |
| POST | `/admin/password-reset-requests/{id}/approve` | Approve and return one-time link |
| POST | `/admin/password-reset-requests/{id}/reject` | Reject request |

Error response shape:

```json
{
  "code": "invalid_credentials",
  "message": "Email or password is incorrect.",
  "field": "password",
  "request_id": "a1b2c3..."
}
```

Stable error codes: `invalid_credentials`, `account_locked`, `account_disabled`, `rate_limited`, `signup_closed`, `invite_required`, `invite_invalid`, `weak_password`, `email_in_use`, `token_invalid`, `token_expired`, `must_change_password`.

---

## 10) Frontend Integration Contract

### 10.1 Login page

Implements all states from `LoginPageSpec.md`. The frontend must honor:

- Inline field errors from `{field, message}`.
- Form-level banner errors from top-level `{code, message}`.
- Lockout state from `code='account_locked'` + `metadata.retry_after_seconds`.
- `must_change_password` response: route to change-password form before any other action.
- Redirect-on-success to a safe (same-origin, relative) `next` query param; fall back to `/secretary`.

### 10.2 Protected routes

A FastAPI dependency `require_auth()`:

- Reads the `openlia_session` cookie, hashes it, looks up `sessions` by `token_hash`.
- Rejects (401) if not found, revoked, past `expires_at`, or stale beyond the inactivity cap.
- Attaches `current_user` to `request.state`.
- Debounced `last_seen_at` update -- only writes if > 60 s since the last update (avoids write amplification).

Unauthenticated requests to protected routes return 401. The frontend intercepts this and redirects to `/login?next=<path>`.

### 10.3 Personal-mode shim

`require_auth()` in personal mode returns the synthetic `local` user without touching the `sessions` table. Every route keyed by `user_id` therefore works identically across modes.

---

## 11) Admin CLI Tooling

Invoked via `openlia admin <cmd>`. Company-mode only -- personal mode rejects with "CLI admin commands require company mode."

| Command | Effect |
|---|---|
| `list-users` | List id, email, is_admin, is_disabled, last login |
| `unlock <email>` | Clear `locked_until` and reset `failed_login_attempts` |
| `lockout enable \| disable \| status` | Toggle the `auth.lockout.enabled` config key (default `true`); `status` prints current value, last-changed timestamp, and the actor. Emits `auth.lockout_setting_changed` on every successful toggle. |
| `reset-password <email>` | Prompt for new password, hash, update, set `must_change_password=true`, revoke all sessions |
| `disable-user <email>` | Set `is_disabled=true`, revoke all sessions |
| `enable-user <email>` | Set `is_disabled=false` |
| `revoke-sessions <email>` | Revoke all sessions for that user |
| `create-invite` | Generate invite with optional `--label`, `--max-uses`, `--expires` flags. Prints the invite URL. |
| `list-invites` | List all invites with usage stats |
| `revoke-invite <token>` | Revoke an invite |

Each command emits a matching `auth_events` row.

---

## 12) Environment Variables

| Var | Default | Purpose |
|---|---|---|
| `OPENLIA_MODE` | `personal` | `personal` \| `company` |
| `OPENLIA_COOKIE_SECURE` | `true` (company) / `false` (personal) | Force `Secure` flag on session cookie |
| `OPENLIA_TRUST_PROXY_HEADERS` | `false` | Trust `X-Forwarded-For` / `X-Forwarded-Proto` from reverse proxy |
| `OPENLIA_PASSWORD_MIN_LENGTH` | `8` | Minimum password length |
| `OPENLIA_SECRET_KEY` | falls back to `~/.openlia/secret.key` | AES-256-GCM key for API key encryption (see `database-design.md` Section 5) |

No SMTP, OAuth, or Google env vars in v1.

---

## 13) Testing Strategy

### 13.1 Unit
- Argon2 verify: correct password, wrong password, tuned work-factor benchmark
- Email normalization across Unicode and whitespace cases
- Lockout state transitions (counter reset, expiry)
- Session hashing and TTL math
- Password policy validator
- Invite validation (expired, revoked, at capacity)

### 13.2 Integration
- Register with invite -> login -> logout -> login against SQLite in-memory
- Admin-approved password reset: request -> approve -> consume with token-replay protection
- Direct admin reset -> must_change_password flow
- Invite lifecycle: create, use, cap, revoke
- Keep Me Logged In cookie attributes and TTL
- Rate limiter enforcement

### 13.3 Security
- Session fixation: login must rotate session identifier
- Token replay prevention on password reset consume
- `SameSite=Lax` CSRF behavior
- Anti-enumeration timing (no statistically significant delta between unknown-email and wrong-password paths)

### 13.4 End-to-End
- Full browser flow for login / register / forgot-password in company mode
- Personal mode: auth routes return 404; protected routes resolve as `local` user

---

## 14) Implementation Phases

### Phase 1 -- Core tables + credentials auth
Auth tables (per `database-design.md` Section 3), `sessions` cookie issuance, `require_auth` dependency, login / logout / register with Argon2, personal-mode shim, synthetic `local` user seed, invite-only registration.

### Phase 2 -- Password reset flows
`password_reset_requests` table, admin-approved flow (`/auth/password-reset/request` + `/auth/password-reset/consume`), direct admin reset with `must_change_password`, admin panel endpoints.

### Phase 3 -- Hardening
Rate limiter, persisted account lockout, `auth_events` recording with retention sweep, admin CLI, anti-enumeration timing audit.

---

## 15) Open Questions

1. **Email verification gate.** v1 credentials emails are unverified. Should v2 add verification before granting access? (Low priority for invite-only deployments where the admin controls who registers.)
2. **Sessions UI.** `/auth/logout-all` exists. Should Settings surface a "sign out other devices" action? (Non-goal in v1 UI per the original spec.)
3. **Password complexity.** v1 enforces only `OPENLIA_PASSWORD_MIN_LENGTH`. Add zxcvbn-style strength checks?
4. **Multi-instance deployments.** In-memory rate limiter doesn't share state across instances. v2 could move to Redis. Company-scale deployments of OpenLIA are expected to be single-instance in v1.

---

## 16) Non-Goals (v1)

- Google OAuth / any OAuth provider
- MFA / 2FA
- Magic-link / passwordless login
- SMTP email delivery
- Self-service account deletion
- Organizations, teams, or RBAC beyond `is_admin` bool
- Distributed rate limiting across multiple server instances
- PII export / deletion workflows (GDPR DSR)
