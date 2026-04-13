# Account Management Spec

## 1) Purpose and Product Role
Account Management is the identity, authentication, and session-control foundation for the entire LIA product. It is responsible for:
- creating and linking user identities,
- issuing and validating sessions,
- protecting all user-scoped resources,
- handling password recovery,
- and enforcing baseline security controls.

This utility is required for all authenticated experiences across Departments, Portfolio, Repository, and saved chat history.

---

## 2) Product Requirements from Login Design
This spec implements and extends the behavior defined by `planning/specs/pages/LoginPageSpec.md`:
- Google OAuth login and auto-account creation
- Email/password login
- Registration
- Forgot password with non-enumerating confirmation
- Keep Me Logged In behavior
- Rate limiting and lockout after 5 consecutive failed attempts for 15 minutes

---

## 3) Scope

### In Scope (v1)
1. Email/password authentication
2. Google OAuth 2.0 authentication
3. Account linking logic (Google + email/password under one user)
4. Session lifecycle management (issue/validate/rotate/revoke)
5. Password reset request and completion
6. Route protection and unauthorized redirects
7. Login abuse protection (rate limiting, lockouts)
8. Audit/security event logging
9. Admin-operational tooling requirements (basic support workflows)

### Out of Scope (v1)
- MFA/2FA
- Additional OAuth providers
- Passwordless login
- Full account deletion workflow
- Organization/team identities and RBAC

---

## 4) Recommended Technical Approach

### 4.1 Auth Stack Recommendation
Use **Next.js + Auth.js (NextAuth) + PostgreSQL adapter** for identity/session orchestration, with a custom user profile table for product-level metadata.

Rationale:
- Fits the current Next.js stack.
- Native support for Google OAuth and credentials provider.
- Mature session handling and callbacks.
- Good compatibility with server actions/API routes.

Alternative acceptable stacks:
- Lucia Auth + custom routes
- Clerk/Auth0/Supabase Auth (managed auth)

If choosing a managed auth provider, still keep local product tables keyed by stable `user_id`.

### 4.2 Database Recommendation
Use **PostgreSQL** as source of truth for account/session metadata.

Rationale:
- Relational constraints are important for auth integrity.
- Strong indexing and transactional guarantees.
- Easy future expansion (audit events, devices, policy controls).

Use Prisma or Drizzle for schema/migrations; Prisma is recommended for team ergonomics.

### 4.3 Email Delivery Recommendation
Use a transactional provider (Resend, SendGrid, Postmark, SES).

Minimum capabilities needed:
- template-based email,
- suppression/bounce handling,
- delivery webhooks,
- domain authentication (SPF/DKIM/DMARC).

Do not send mail directly from app servers using raw SMTP without provider observability.

---

## 5) Data Model and Schema Strategy

## 5.1 Core Tables

### `users`
- `id` UUID PK
- `email` CITEXT UNIQUE NOT NULL
- `password_hash` TEXT NULL
- `email_verified_at` TIMESTAMPTZ NULL
- `failed_login_attempts` INT NOT NULL DEFAULT 0
- `locked_until` TIMESTAMPTZ NULL
- `last_login_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- email unique index (normalized)
- check: `failed_login_attempts >= 0`

### `auth_accounts` (provider linkage)
- `id` UUID PK
- `user_id` UUID FK -> users(id)
- `provider` TEXT NOT NULL (`google`, `credentials`)
- `provider_account_id` TEXT NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique(provider, provider_account_id)
- unique(user_id, provider)

### `sessions`
- `id` UUID PK
- `user_id` UUID FK -> users(id)
- `session_token_hash` TEXT NOT NULL UNIQUE
- `is_persistent` BOOLEAN NOT NULL DEFAULT false
- `expires_at` TIMESTAMPTZ NOT NULL
- `last_seen_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `revoked_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

### `password_reset_tokens`
- `id` UUID PK
- `user_id` UUID FK -> users(id)
- `token_hash` TEXT NOT NULL UNIQUE
- `expires_at` TIMESTAMPTZ NOT NULL
- `used_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

### `auth_events` (audit/security logging)
- `id` UUID PK
- `user_id` UUID NULL
- `event_type` TEXT NOT NULL
- `ip_hash` TEXT NULL
- `user_agent` TEXT NULL
- `metadata_json` JSONB NOT NULL DEFAULT '{}'
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Event examples:
- `login_success`
- `login_failed`
- `account_locked`
- `password_reset_requested`
- `password_reset_completed`
- `oauth_linked`
- `session_revoked`

### 5.2 User-Scoped Product Data
All product tables (portfolio items, repository reports, chat histories) must include `user_id` FK constraints and indexed filters by `user_id`.

### 5.3 Migration Plan
1. Create core auth tables.
2. Backfill seed/admin records if needed.
3. Add FK constraints for existing user-scoped tables.
4. Add indexes for high-traffic lookups (email, session token, reset token).

---

## 6) Authentication Flows (Implementation Detail)

### 6.1 Registration (Email/Password)
1. Validate payload (email/password/confirm).
2. Normalize email.
3. Reject if existing user with credentials already exists.
4. Hash password using Argon2id.
5. Create `users` row + `auth_accounts(provider=credentials)` in one transaction.
6. Create session.
7. Set secure cookie and redirect to Secretary.
8. Emit `auth_events` record.

### 6.2 Login (Email/Password)
1. Validate payload.
2. Fetch user by email.
3. If account locked (`locked_until > now()`), return lockout response with remaining time.
4. Verify password hash.
5. If invalid:
   - increment failed counter,
   - set lockout when threshold reached,
   - emit `login_failed` / `account_locked` event,
   - return generic error.
6. If valid:
   - reset failed counter and lockout fields,
   - rotate/create session,
   - update `last_login_at`,
   - emit `login_success`.

### 6.3 Google OAuth
1. Redirect to Google with state + PKCE.
2. Exchange code for tokens server-side.
3. Resolve Google email.
4. If existing email user exists, link provider record.
5. Else create user + provider link.
6. Issue first-party session cookie.
7. Emit `oauth_linked` or `login_success` event.

### 6.4 Forgot Password
1. Accept email.
2. Always return success message to UI.
3. If eligible account exists:
   - generate random token,
   - store hash + TTL,
   - send reset email.
4. Emit `password_reset_requested` event.

### 6.5 Reset Password
1. Validate token and password policy.
2. Verify token hash exists, not expired, not used.
3. Hash new password.
4. Update user password hash.
5. Mark token used.
6. Revoke active sessions.
7. Emit `password_reset_completed`.

### 6.6 Logout
- Revoke current session token and clear cookie.
- Optional “logout all devices” endpoint should revoke all active sessions for user.

---

## 7) Session Design

### 7.1 Cookie Settings
- `HttpOnly: true`
- `Secure: true` (always in production)
- `SameSite: Lax` (or `Strict` if UX allows)
- Path restricted to app root
- Signed/encrypted value or opaque token reference

### 7.2 Session TTL Policy
- Non-persistent session (Keep Me Logged In unchecked): browser-session cookie, short max-age fallback (e.g., 12 hours).
- Persistent session: fixed max-age (e.g., 30 days).
- Inactivity timeout (recommended): rotate and extend only while active, cap with absolute max lifetime.

### 7.3 Rotation and Revocation
- Rotate token on login and password reset.
- Revoke on logout.
- Revoke all sessions on password change/reset and high-risk security events.

---

## 8) Security Controls and Privacy

### 8.1 Credential Security
- Use Argon2id for password hashing with calibrated work factors.
- Compare hashes in constant time.
- Never store plaintext credentials.

### 8.2 Anti-Enumeration and Abuse Controls
- Forgot-password and login errors must avoid revealing account existence.
- Rate limit by:
  - account/email key,
  - IP key,
  - and global route burst limit.
- Lockout policy: 5 consecutive failures, 15-minute lock.

### 8.3 CSRF/XSS Protection
- CSRF token validation for state-changing POST actions when cookie auth is used.
- Strict output encoding and content security policies.
- Do not expose session tokens to client JavaScript.

### 8.4 Data Protection
- Encrypt secrets at rest via platform secret manager.
- Redact PII/sensitive payloads in logs.
- Hash IPs for analytics/audit retention unless raw value is required for legal/security policy.

### 8.5 Compliance and Retention Baseline
- Define retention windows for auth events and reset tokens.
- Document data-subject support process (export/delete) for future compliance phases.

---

## 9) Google OAuth Setup Details

## 9.1 Required Setup Steps
1. Create Google Cloud project.
2. Configure OAuth consent screen (app name, support email, scopes).
3. Create OAuth client credentials (web application).
4. Add authorized redirect URIs for each environment:
   - local: `http://localhost:3000/api/auth/callback/google`
   - production: `https://<domain>/api/auth/callback/google`
5. Store client ID/secret in environment secret manager.
6. Configure Auth.js provider with exact callback URL and trust host settings.

### 9.2 Is Google OAuth Required?
- For the Login spec, **yes**: Google OAuth is a required v1 feature.
- System must still support email/password for users who prefer credentials.

### 9.3 Required OAuth Scopes (v1)
- `openid`
- `email`
- `profile`

Do not request broader Google scopes in v1.

---

## 10) Email System Setup Details

### 10.1 Provider Selection Criteria
- High deliverability
- API reliability and dashboard observability
- Webhook support
- Template support
- Cost at expected volume

### 10.2 Reset Email Template Requirements
- Neutral copy (no account enumeration clues)
- Single CTA with signed reset URL
- Expiration notice
- Security note if user did not request reset

### 10.3 Delivery and Reliability Requirements
- Retry transient provider failures with backoff.
- Track delivery status via webhooks.
- Alert on sustained failure rates.

---

## 11) API Surface (Conceptual)
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/logout-all`
- `GET /auth/session`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /auth/oauth/google/start`
- `GET /auth/oauth/google/callback`

Error format:
- `code`: stable machine-readable key
- `message`: safe user-facing message
- `field`: optional field pointer
- `request_id`: correlation id for support/debugging

---

## 12) Frontend Integration Contract

### 12.1 Login Page Behavior Contract
Must honor all UI states in `LoginPageSpec.md`:
- input-level validation messages,
- form-level error banners,
- loading/submitting states,
- rate-limit lock messaging,
- redirect-on-success.

### 12.2 Protected Route Middleware
- If no valid session, redirect to `/login`.
- Preserve intended path in a safe `next` parameter.
- Reject unsafe external redirect targets.

---

## 13) Operational Monitoring and Alerting
Track:
- login success/failure rate
- lockout count
- password reset request and completion rates
- OAuth callback failure rate
- session creation/revocation volume
- suspicious anomalies (credential stuffing patterns)

Alerts:
- sudden spike in failed logins
- reset-email delivery failures
- OAuth provider outage/error spike

---

## 14) Testing and Verification Strategy

### 14.1 Unit Tests
- password policy validator
- lockout calculations
- token expiry checks
- email normalization

### 14.2 Integration Tests
- register/login/logout flow
- forgot/reset flow with token invalidation
- Google OAuth callback happy path and failure path
- session persistence behavior for Keep Me Logged In

### 14.3 Security Tests
- CSRF checks on mutation routes
- brute-force simulation against login route
- session fixation and reuse checks
- token replay prevention

### 14.4 End-to-End Tests
- full UI journey for login/register/forgot-password from login page
- protected route redirect behavior

---

## 15) Implementation Phases

### Phase 0: Decisions and Setup
- Finalize stack choice (Auth.js + Prisma + Postgres + email provider).
- Provision secrets and environment configuration.
- Document local/dev/prod callback URLs.

### Phase 1: Data and Auth Skeleton
- Create schemas and migrations.
- Implement credential auth with secure session cookies.
- Implement middleware-based route protection.

### Phase 2: OAuth and Account Linking
- Add Google OAuth flow.
- Implement account-linking rules and conflict handling.

### Phase 3: Recovery and Hardening
- Add forgot/reset password flow.
- Add lockout/rate-limiting and audit event logging.
- Add revocation flows and rotation policies.

### Phase 4: Observability and Launch Readiness
- Add auth metrics dashboards.
- Configure security alerts.
- Run load and abuse validation tests.

---

## 16) Environment Variables (Expected)
- `DATABASE_URL`
- `AUTH_SECRET`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `APP_BASE_URL`
- `EMAIL_PROVIDER_API_KEY`
- `EMAIL_FROM_ADDRESS`
- `RATE_LIMIT_REDIS_URL` (if distributed limiter is used)

---

## 17) Key Architectural Questions to Resolve Before Build
1. **Auth library choice:** Auth.js vs managed provider?
2. **Session model:** DB-backed opaque session vs JWT-only session?
3. **Email verification policy:** required before full access or deferred?
4. **Password policy strictness:** exact minimum length/entropy requirements?
5. **Rate limiting backend:** in-memory vs Redis for multi-instance deployment?
6. **PII retention policy:** how long to keep auth events and IP-linked data?
7. **Account linking rules:** how to resolve edge cases if OAuth email changes?
8. **Support tooling:** what minimum admin actions are required at launch?

---

## 18) Non-Goals (v1)
- Multi-tenant organization model
- Role-based permission matrix
- Device/session management UI for end users
- Social login providers beyond Google
- MFA enrollment and recovery

---

## 19) Deliverables Checklist
- [ ] Finalized architecture decision record (ADR)
- [ ] Database schema + migrations
- [ ] Auth endpoints and middleware
- [ ] Google OAuth setup in all environments
- [ ] Password reset email templates and delivery integration
- [ ] Security hardening controls (CSRF/rate limit/lockout)
- [ ] Test suite (unit/integration/e2e/security)
- [ ] Runbook for auth incidents and support operations

---

## 20) Pre-Implementation Clarification Checklist (Must Decide First)

### 20.1 Product and UX Decisions
1. Is email verification mandatory before first login for email/password signups?
2. Should users be able to log in immediately after registration if email is unverified?
3. Should OAuth-only users be allowed to set a password later from Settings?
4. What exact copy should appear for login failures, lockouts, and password reset confirmations?
5. Should "logout all devices" be available in v1 UI or backend-only?

### 20.2 Security Policy Decisions
1. Password policy final values (minimum length, complexity, breach-password checks).
2. Lockout policy details beyond baseline (counter reset window, IP weighting, captcha fallback).
3. Session policy values:
   - persistent session absolute TTL,
   - non-persistent session fallback TTL,
   - inactivity timeout.
4. Should suspicious login detection (new geo/device heuristics) be included in v1?
5. Auth-event retention period and redaction policy for privacy/compliance.

### 20.3 Architecture Decisions
1. Final auth engine: Auth.js vs managed auth platform.
2. Session style: database-backed opaque sessions vs JWT-only sessions.
3. ORM choice: Prisma vs Drizzle.
4. Rate limit backend: Redis vs platform-native rate limits.
5. Email provider final choice: Resend, SendGrid, Postmark, or SES.

### 20.4 Operational Decisions
1. Who receives auth incident alerts (email/Slack/PagerDuty)?
2. What are launch SLOs for auth endpoints (p95 latency, error-rate budget)?
3. What support runbooks are required at launch (account unlock, manual verification, provider outage)?
4. What environment promotion process is required for OAuth callback updates?

---

## 21) Accounts and Setup Checklist (What You Need to Create)

### 21.1 Cloud and Infrastructure
- [ ] **Hosting account** (e.g., Vercel) for web deployment and env management.
- [ ] **PostgreSQL database** (Neon/Supabase/RDS/etc.) with production and staging instances.
- [ ] **Redis instance** (Upstash/ElastiCache/etc.) if distributed rate limiting is enabled.

### 21.2 Authentication Provider Setup
- [ ] **Google Cloud account/project** for OAuth.
- [ ] OAuth consent screen configured.
- [ ] OAuth web client credentials created.
- [ ] Authorized redirect URIs configured for local/staging/prod.
- [ ] Test users added if app is in testing mode.

### 21.3 Email Delivery Setup
- [ ] **Transactional email provider account** (Resend/SendGrid/Postmark/SES).
- [ ] Sending domain added and verified (SPF/DKIM/DMARC).
- [ ] API key with least privilege generated.
- [ ] Password reset template created and versioned.
- [ ] Bounce/complaint webhook endpoint configured.

### 21.4 Secrets and Environment Management
- [ ] Secret storage configured in deployment platform.
- [ ] Environment variables set for local, staging, production:
  - `DATABASE_URL`
  - `AUTH_SECRET`
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `APP_BASE_URL`
  - `EMAIL_PROVIDER_API_KEY`
  - `EMAIL_FROM_ADDRESS`
  - `RATE_LIMIT_REDIS_URL` (if used)
- [ ] Secret rotation policy documented (owner + rotation cadence).

### 21.5 Domain and DNS
- [ ] Production domain selected.
- [ ] DNS access available to configure verification and email records.
- [ ] HTTPS/TLS managed by hosting platform and validated.

### 21.6 Monitoring and Incident Tools
- [ ] Logging/monitoring account (Datadog, Sentry, or equivalent).
- [ ] Alert channel configured (Slack/email/on-call).
- [ ] Auth dashboard and alert thresholds created.

### 21.7 Team Access and Ownership
- [ ] Named owners for auth architecture, security review, and incident response.
- [ ] Access control policy for production secrets and DB admin roles.
- [ ] Break-glass process documented for emergency production access.

### 21.8 Pre-Build Exit Criteria
Before implementation starts, confirm all of the following:
- [ ] Decisions in Section 20 are finalized and documented.
- [ ] All required external accounts in Section 21 are created.
- [ ] Local, staging, and production callback/base URLs are finalized.
- [ ] Test plan owners are assigned (unit/integration/security/e2e).
- [ ] Security sign-off checklist approved.
