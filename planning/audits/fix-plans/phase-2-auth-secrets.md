# Phase 2 — Auth & Secrets fix plan (→ 100%)

**Current shipped:** ~93%
**Plan:** [planning/implementation-plans/2026-04-16-phase-2-auth-and-secrets.md](../../implementation-plans/2026-04-16-phase-2-auth-and-secrets.md)
**Spec(s):**
- [planning/specs/components/AccountManagementSpec.md](../../specs/components/AccountManagementSpec.md)
- [planning/specs/pages/LoginPageSpec.md](../../specs/pages/LoginPageSpec.md)
- [planning/specs/systems/database-design.md](../../specs/systems/database-design.md) §3 rate limits, §5 secrets
- [planning/implementation-plans/route-authorization-matrix.md](../../implementation-plans/route-authorization-matrix.md)

**Dominant root cause(s):** IMPLEMENTER drift on three axes — (a) three late-landed routers (`settings_general`, `settings_email`, `settings_models`) still gate on `build_require_auth` instead of `build_require_active_user`, so a forced-reset user can read/write prefs + change email + pick LLM tiers before completing the mandatory password change; (b) `/auth/login` does not revoke a pre-existing session cookie before minting a new one (session-fixation gap vs. AccountManagementSpec §13.2 "login must rotate session identifier"); (c) `services/auth/__init__.py` is a bare `from __future__ import annotations` file so the plan-documented public API (`from openlia_server.services.auth import authenticate, ...`) silently fails and consumers (CLI, new routes) reach into submodules directly. Plus doc-path drift (`route-authorization-matrix.md` lives under `implementation-plans/` but every cross-reference in `REM-P0-006`, fix-plans, and the spec uses the bare `planning/` path) and minor contract drift on the register response body.

**Gap summary:** The heavy lifting shipped correctly — Argon2id hashing, AES-256-GCM row-AAD crypto + rotation CLI, opaque-token session CRUD with TTL/inactivity cap, invite-hashed registration, login + in-row lockout, admin-approved + direct-admin reset, forced-password gate + notifications/jobs/admin regression tests, signup_policy seeding, sliding-window rate limits on `/auth/register|login|password-reset/request`. The remaining gaps are a cluster of **late-added routers** never re-examined under the must-change-password lens, a single **session-fixation corner** on `/auth/login`, and doc/exports/contract hygiene. The previously asserted "P0-06 build_require_auth returns `Depends()` and breaks nested deps" turned out to be **incorrect**: the 13-test `test_must_change_password_gate.py` suite (and every existing middleware/auth_routes test) passes against the shipped factories — FastAPI resolves `user=require_auth` (where the default is `Depends(...)`) correctly via its parameter-default scan. The previous fix-plan's "NEW-2-01 thresholds (5/min + 10/hr)" are also wrong per spec — the correct thresholds are `login_ip=20/5min`, `login_email=10/5min`, `password_reset_ip=5/1hr`, `register_ip=5/1hr` and are all correctly encoded in `middleware/rate_limit.py::LIMITS`.

---

## P0 — Live failures

### P0-02-01 — Forced-password users bypass gate on `/settings/prefs`, `/settings/email`, `/settings/admin/llm/preferences`

**Bug.** `users.must_change_password=true` is supposed to block every authenticated product route per AccountManagementSpec §6 + route-authorization-matrix "must-change-password gate" row and the exemption set in `middleware/auth.py:83-88`. Three late-landed routers instead gate on `build_require_auth`, so a forced-reset user can:
- `GET /settings/prefs` and `PATCH /settings/prefs` (change display_name, theme, language prefs) — `routes/settings_general.py:11, 49`.
- `PATCH /settings/email` (change email with only current-password confirmation) — `routes/settings_email.py:11, 22`.
- `GET|PUT|DELETE /settings/admin/llm/preferences` (rewrite LLM tier roster) — `routes/settings_models.py:12, 26`.

The forced-password regression suite `tests/test_routes/test_must_change_password_gate.py` covers `notifications`, `jobs`, `settings/data-providers`, `settings/admin/llm/providers`, `admin/invites`, `admin/users`, `admin/password-reset-requests` but *not* these three routers — confirmed by grepping the test file: no call touches `/settings/prefs`, `/settings/email`, or `/settings/admin/llm/preferences`. Missing coverage is why this regressed unnoticed.

**Files.**
- `packages/server/src/openlia_server/routes/settings_general.py:11` (import), `:49` (factory call), `:55, :64` (`user: User = require_auth` param defaults).
- `packages/server/src/openlia_server/routes/settings_email.py:11` (import), `:22` (factory call), `:29` (param default).
- `packages/server/src/openlia_server/routes/settings_models.py:12` (import), `:26` (factory call), `:32, :41, :71` (param defaults).

**Plan ref.** Task 13 "`require_active_user` and must-change-password gate" (`2026-04-16-phase-2-auth-and-secrets.md`) — "use `build_require_active_user` on every authenticated product route".
**Spec ref.** `AccountManagementSpec.md` §6 + `route-authorization-matrix.md` must-change-password gate row.

**Acceptance.**
1. Replace the import and factory call in all three files with `build_require_active_user`.
2. Extend `tests/test_routes/test_must_change_password_gate.py::TestForcedPasswordBlocksProductRoutes` with three new methods:
   - `test_settings_prefs_get_blocked` — `GET /settings/prefs` → 403 `{"code":"must_change_password"}`.
   - `test_settings_prefs_patch_blocked` — `PATCH /settings/prefs {"theme":"dark"}` → 403.
   - `test_settings_email_patch_blocked` — `PATCH /settings/email {"new_email":"x@y.z","current_password":"..."}` → 403 (gate must fire *before* the password check).
   - `test_settings_models_list_blocked` — `GET /settings/admin/llm/preferences` → 403.
   - `test_settings_models_put_blocked` — `PUT /settings/admin/llm/preferences` → 403.
3. Existing positive tests in `test_settings_general_routes.py` / `test_settings_email_routes.py` / `test_settings_models_routes.py` still pass (they authenticate non-forced users).

**Verification.** `uv run pytest packages/server/tests/test_routes/test_must_change_password_gate.py packages/server/tests/test_routes/test_settings_general_routes.py packages/server/tests/test_routes/test_settings_email_routes.py packages/server/tests/test_routes/test_settings_models_routes.py -v` green.

---

### P0-02-02 — `/auth/login` does not rotate/revoke pre-existing session cookie (session fixation)

**Bug.** `AccountManagementSpec.md` §13.2 "Session fixation: login must rotate session identifier" and §8 "issue a new session row on login" imply the caller's existing cookie must be revoked before a new one is minted. Current handler in `routes/auth.py:119-180` calls `sessions.create_session(...)` and `_set_cookie(...)` unconditionally, ignoring the inbound `openlia_session` cookie. A pre-seeded attacker cookie therefore stays valid alongside the victim's new cookie — both will resolve via `sessions.validate_session` because the old session row is never revoked. Compare with `/auth/logout` at `:182-193` which correctly looks up and revokes the bound session.

**Files.**
- `packages/server/src/openlia_server/routes/auth.py:119-180` (login handler — must accept `openlia_session: str | None = Cookie(...)`, validate, and `sessions.revoke_session(db, old.session.id)` before `create_session`).

**Plan ref.** Plan Task 14 "`/auth/login`" handler (same file, same plan). Spec requires rotation per §13.2.
**Spec ref.** `AccountManagementSpec.md` §8 "Session lifecycle", §13.2 "Session fixation".

**Acceptance.**
1. On `/auth/login`, before the `create_session` call: read the inbound `openlia_session` cookie, and if present call `sessions.validate_session` + `sessions.revoke_session` (idempotent no-op if cookie is invalid, expired, or missing).
2. New test `test_auth_routes.py::TestRegisterLoginLogout::test_login_rotates_prior_session`:
   - Register + log out (or create a stale session manually and set cookie).
   - Seed a prior session for the same user, attach its cookie, then `POST /auth/login`.
   - Assert the prior session is revoked (`sessions.validate_session(db, old_raw)` returns `None`) and the new cookie value differs.
3. Do *not* revoke all sessions — only the cookie currently presented. "Log out everywhere" lives on `/auth/logout-all`.

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py -v` green.

---

## P1 — Silent correctness gaps

### P1-02-01 — `services/auth/__init__.py` is empty; plan-documented public API unusable

**Bug.** The plan (file §"Architecture summary") and projectStructure deviation note promise a re-exporting `services/auth/__init__.py` so callers can write `from openlia_server.services.auth import authenticate, register, request_reset, ...`. The shipped file contains only a single line (`from __future__ import annotations` per prior commit state; currently effectively empty — `cat` on file prints nothing before the EOF marker). Every internal caller works around this by importing the submodule directly (`from openlia_server.services.auth import login as login_service`, etc.). The CLI, future Phase 7 helpers, and any external importer that follows the plan will silently `ImportError`.

**Files.**
- `packages/server/src/openlia_server/services/auth/__init__.py` (empty; should re-export: `authenticate`, `AccountDisabledError`, `AccountLockedError`, `InvalidCredentialsError` from `login`; `register`, `normalize_email`, `InviteInvalidError`, `InviteRequiredError`, `RegistrationFailedError` from `registration`; `request_reset`, `approve_request`, `reject_request`, `consume_token`, `admin_direct_reset`, `change_password`, `TokenInvalidError`, `TokenExpiredError` from `password_reset`; `create_session`, `validate_session`, `revoke_session`, `revoke_all_sessions`, `prune_expired`, `PERSISTENT_TTL`, `NON_PERSISTENT_TTL` from `sessions`; `hash_password`, `verify_password`, `validate_password_policy`, `dummy_verify`, `WeakPasswordError` from `passwords`; `generate_opaque_token`, `hash_token` from `tokens`; `log_auth_event` from `events`; `seed_signup_policy`, `get_policy`, `check_email_allowed`, `assert_registration_open`, `SignupClosedError`, `EmailDomainNotAllowedError` from `signup_policy`; `AuthError` from `errors`).

**Plan ref.** Task 4–11 bullets "re-exports public API" and "Deviations from projectStructure.md" in `2026-04-16-phase-2-auth-and-secrets.md` header.
**Spec ref.** `AccountManagementSpec.md` §7 (service surface) + `projectStructure.md`.

**Acceptance.**
1. Populate `__init__.py` with the re-exports above.
2. Internal callers that currently import submodules directly may keep doing so — this change is purely additive.
3. Add a smoke test `test_services/test_auth/test_public_api.py` asserting `from openlia_server.services.auth import authenticate, register, request_reset, create_session, hash_password, log_auth_event, AuthError` succeeds.

**Verification.** `uv run pytest packages/server/tests/test_services/test_auth/ -v` green.

---

### P1-02-02 — `/auth/register` response body missing `is_admin` and `must_change_password`

**Bug.** `routes/auth.py:117` returns `{"user_id", "email", "display_name"}`. The sibling `/auth/login` at `:174-180` and `/auth/session` at `:207-213` return the fuller shape `{"user_id", "email", "display_name", "is_admin", "must_change_password"}`. AccountManagementSpec §10 "Register response = Login response shape" and LoginPageSpec's auth-state model require the frontend to receive the same structure from both paths so it can skip the "re-fetch session" round-trip after register.

**Files.**
- `packages/server/src/openlia_server/routes/auth.py:117` (register return payload).

**Plan ref.** Plan Task 14 "`POST /auth/register`".
**Spec ref.** `AccountManagementSpec.md` §10, `LoginPageSpec.md` post-register flow.

**Acceptance.**
1. Register returns `{"user_id", "email", "display_name", "is_admin": user.is_admin, "must_change_password": user.must_change_password}`.
2. `test_auth_routes.py::TestRegisterLoginLogout::test_full_cycle` asserts both new keys (and not just `email`).

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py -v` green.

---

### P1-02-03 — `_STATUS_MAP["must_change_password"] = 200` is dead code + misleading

**Bug.** `routes/auth.py:302` maps `must_change_password → 200`. No AuthError with that code is ever raised from any auth route (the must-change-password signal is a non-fatal flag on the `/auth/login` and `/auth/session` response bodies, and a 403 from the middleware gate with a `detail={"code":"must_change_password"}` shape). The entry either lures a future contributor into raising an AuthError with that code (which would then return HTTP 200 + body `{"code":"must_change_password","message":"..."}`, contradicting the middleware's 403) or is silent dead code. Either way it's a trap.

**Files.**
- `packages/server/src/openlia_server/routes/auth.py:302` (`_STATUS_MAP`).

**Plan ref.** Task 14 error-code table.
**Spec ref.** `AccountManagementSpec.md` §10 "Stable error codes".

**Acceptance.**
1. Remove the `"must_change_password": 200` entry from `_STATUS_MAP`.
2. Add a comment above the map explaining that `must_change_password` is a flag, not an AuthError code, and the 403 is enforced by `middleware.auth.build_require_active_user`.

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py packages/server/tests/test_routes/test_must_change_password_gate.py -v` green.

---

### P1-02-04 — No integration test covers rate-limit 429s on `/auth/login`, `/auth/register`, `/auth/password-reset/request`

**Bug.** `middleware/rate_limit.py::LIMITS` encodes the thresholds spec'd in `AccountManagementSpec.md` §8.3 table (`login_ip=20/5min`, `login_email=10/5min`, `register_ip=5/1hr`, `password_reset_ip=5/1hr`) and the unit test at `tests/test_middleware/test_rate_limit.py` covers the sliding-window math. No integration test validates that `/auth/login`, `/auth/register`, or `/auth/password-reset/request` actually wire `LIMITS[...]` and return 429 with `{"code":"rate_limited"}` + proper retry headers after N+1 calls within the window. Regressions (e.g., a future refactor that uses a stale local `limit, window` pair) would not be caught.

**Files.**
- `packages/server/src/openlia_server/routes/auth.py:86-93, 128-137, 229-234` (currently untested at integration level).
- `packages/server/tests/test_routes/test_auth_routes.py` (missing `TestRateLimits`).

**Plan ref.** Plan Task 12 + spec §8.3.
**Spec ref.** `AccountManagementSpec.md` §8.3 "Abuse limits" table.

**Acceptance.** New `TestRateLimits` class in `test_auth_routes.py` with:
1. `test_login_ip_429_after_20`: 20 login POSTs from one IP → 21st returns 429 + `{"code":"rate_limited"}`.
2. `test_login_email_429_after_10`: 10 login POSTs to one email → 11th returns 429.
3. `test_register_429_after_5`: 5 register POSTs with distinct payloads from one IP → 6th returns 429 *before* the invite check runs.
4. `test_password_reset_429_after_5`: 5 password-reset-request POSTs → 6th returns 429.
5. Uses `from openlia_server.middleware.rate_limit import limiter; limiter().clear()` (or the existing `_clear_rate_limiter` fixture in `tests/test_routes/conftest.py:11-15`) to avoid cross-test bleed.

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py::TestRateLimits -v` green.

---

### P1-02-05 — Personal mode: no test proves `/auth/*` routes are *not* mounted AND `/admin/*` is unmounted

**Bug.** `test_auth_routes.py::TestPersonalModeNoAuthRoutes` asserts `/auth/register` and `/auth/session` → 404 in personal mode (good). It does *not* assert `/admin/invites`, `/admin/users`, or the other six `/admin/*` routes are 404 in personal mode. `app.py:338-340` only mounts both routers under `if mode == "company":`, but a future refactor could accidentally lift `admin` out of the guard. Also no test asserts that `/auth/login`, `/auth/logout`, `/auth/logout-all`, `/auth/signup-policy`, `/auth/change-password`, `/auth/password-reset/request`, `/auth/password-reset/consume` all return 404 in personal mode.

**Files.**
- `packages/server/tests/test_routes/test_auth_routes.py::TestPersonalModeNoAuthRoutes` (only covers two of the nine `/auth/*` paths and zero `/admin/*` paths).

**Plan ref.** Plan Task 15 `app.py` mount + spec §2 "personal vs company".
**Spec ref.** `AccountManagementSpec.md` §2 "Deployment modes", `PLAN.md` auth section.

**Acceptance.**
1. Parametrized test `test_personal_mode_auth_routes_404` over every `/auth/*` path (GET or POST as appropriate). All → 404.
2. Parametrized test `test_personal_mode_admin_routes_404` over every `/admin/*` path. All → 404.

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py -v` green.

---

### P1-02-06 — Password-reset consume path has no integration test for token-replay + wrong-email rotation

**Bug.** `services/auth/password_reset.py::consume_token` marks `status='consumed'` and revokes all sessions. Good. The plan Task 11 demands two integration assertions that don't exist anywhere in `test_routes/test_auth_routes.py` or `test_services/test_auth/test_password_reset.py` (file exists per plan but only covers the service layer; the route-level replay path is not asserted):
1. Replaying the same token returns 400 `{"code":"token_invalid"}` (because second consume finds `status='consumed'` and falls into the `status != "approved"` branch).
2. All active sessions for the reset user are revoked — including a session created mid-flight (i.e., attacker holds an older cookie, victim resets, attacker's cookie no longer validates).

**Files.**
- `packages/server/src/openlia_server/services/auth/password_reset.py:94-129` (consume_token).
- `packages/server/tests/test_routes/test_auth_routes.py::TestPasswordResetFlow` (only covers the silent-200 request path; no approve/consume flow).

**Plan ref.** Task 11 "Admin-approved password reset".
**Spec ref.** `AccountManagementSpec.md` §5 "Password reset flow", §13.2 "Token replay prevention".

**Acceptance.** New `TestPasswordResetFlow::test_request_approve_consume_revokes_sessions_and_replay_blocked`:
1. Register user + authenticate session A.
2. `POST /auth/password-reset/request` for that email.
3. Call `approve_request(...)` via the service to obtain the raw reset token (or hit `/admin/password-reset-requests/{id}/approve` with an admin cookie).
4. `POST /auth/password-reset/consume {token, new_password}` → 200.
5. Session A cookie no longer validates (`GET /auth/session` → 401).
6. Second `POST /auth/password-reset/consume` with the same token → 400 `{"code":"token_invalid"}`.

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py::TestPasswordResetFlow -v` green.

---

### P1-02-07 — No test proves cookie flags (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`) match spec across both modes

**Bug.** `routes/auth.py::_set_cookie` hardcodes `httponly=True`, `samesite="lax"`, `path="/"` and computes `secure` from `_cookie_secure()` (defaults to `True` in company, `False` otherwise, override via `OPENLIA_COOKIE_SECURE`). `database-design.md` §8 and `AccountManagementSpec.md` §8.2 pin exactly these values. No test asserts the cookie attributes on a successful `/auth/login` response — a regression that drops `HttpOnly` or flips `SameSite` to `None` would ship silently.

**Files.**
- `packages/server/src/openlia_server/routes/auth.py:276-285` (`_set_cookie`).
- `packages/server/tests/test_routes/test_auth_routes.py` (missing cookie-attribute assertions).

**Plan ref.** Plan Task 14 cookie issuance.
**Spec ref.** `AccountManagementSpec.md` §8.2 cookie table, `database-design.md` §8.

**Acceptance.** New `TestCookieFlags`:
1. `test_login_sets_httponly_lax_path_in_company_mode` — inspect `Set-Cookie` header (`resp.headers["set-cookie"]` via `resp.raw`) and assert `HttpOnly`, `SameSite=Lax`, `Path=/` are present and `Max-Age` is ~30d when `persistent=True`, absent when `persistent=False`.
2. `test_login_sets_secure_when_OPENLIA_COOKIE_SECURE_true` — `monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "true")`; assert `Secure` in cookie.
3. `test_login_omits_secure_when_OPENLIA_COOKIE_SECURE_false` — same with `"false"`; assert no `Secure`.

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py::TestCookieFlags -v` green.

---

### P1-02-08 — No test proves `authenticate` preserves original order of failure events when lockout is enabled then resets

**Bug.** `services/auth/login.py::authenticate` emits `login_failure` before `account_locked`, but on the *6th* failure that crosses the threshold it emits `login_failure` *last* (lines 93-111). Existing `test_login.py::TestLockout::test_five_failures_lock` only asserts the 6th call raises `account_locked`; no test asserts the sequence of `auth_events` rows (`login_failure * 5`, then `account_locked`, then `login_failure` with reason=`locked`) so forensic audits would miss a regression.

**Files.**
- `packages/server/src/openlia_server/services/auth/login.py:90-111` (ordering).
- `packages/server/tests/test_services/test_auth/test_login.py::TestLockout` (missing event-sequence assertion).

**Plan ref.** Plan Task 10 lockout state machine.
**Spec ref.** `AccountManagementSpec.md` §13.2 "Audit trail".

**Acceptance.** Extend `test_login.py::TestLockout` with `test_lockout_emits_ordered_events`:
1. Make 5 wrong-password attempts, then one more.
2. Query `auth_events` ordered by `created_at` and assert the event-type sequence: `login_failure * 5`, `account_locked`, `login_failure` (reason=`locked`).

**Verification.** `uv run pytest packages/server/tests/test_services/test_auth/test_login.py -v` green.

---

## P2 — Drift / hygiene

### P2-02-01 — `route-authorization-matrix.md` path inconsistency

**Bug.** File lives at `planning/implementation-plans/route-authorization-matrix.md`. `REM-P0-006`, the current fix-plan draft, several per-phase audits (`planning/audits/fix-plans/phase-19-macro-research.md:40`), and the master tracker §10 all cross-reference `planning/route-authorization-matrix.md` (shorter path). Any tooling that tries to resolve the bare path (e.g., markdown link-check) 404s.

**Files.**
- `planning/implementation-plans/route-authorization-matrix.md` (canonical file).
- `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md:340-342` (cross-reference).
- `planning/audits/2026-04-21-remediation-checklist.md:248`.
- `planning/audits/fix-plans/phase-19-macro-research.md:40`.

**Plan ref.** N/A (infra doc).
**Spec ref.** N/A.

**Acceptance.** Pick one path and migrate. Either (a) `git mv planning/implementation-plans/route-authorization-matrix.md planning/route-authorization-matrix.md` and update relative links inside the doc, or (b) update every cross-reference to the longer path. Master tracker P2-21 already tracks the sibling `endpoint-contract-matrix.md` drift; do both in the same pass.

**Verification.** `grep -rn "route-authorization-matrix" planning/` — every match resolves to an existing file.

---

### P2-02-02 — `InviteInvalidError` vs `signup_closed` maps to 403 but spec mentions 403 in AccountManagementSpec §10 only for `account_disabled`; verify matrix

**Bug.** Low-value drift: `_STATUS_MAP` in `routes/auth.py:288-303` maps `invite_required=403`, `invite_invalid=403`, `email_domain_not_allowed=403`, `signup_closed=403`. These are **unauthorized-to-register** signals, not "auth required" (401). `AccountManagementSpec.md` §10 lists the stable error codes but doesn't pin an HTTP status per code. The 403 choice is defensible (server understood, refusing) but should be frozen into the matrix + test so a future "401 for all registration rejections" refactor is a conscious decision, not a drift.

**Files.**
- `packages/server/src/openlia_server/routes/auth.py:288-303`.
- `planning/implementation-plans/route-authorization-matrix.md` (status-code column for `/auth/register`).

**Plan ref.** Task 14 error-code table.
**Spec ref.** `AccountManagementSpec.md` §10.

**Acceptance.**
1. Pin the code→status table in the route-authorization-matrix under a new "`/auth/register` error codes" section.
2. Add a test `test_auth_routes.py::TestRegisterErrors::test_email_domain_rejected` that exercises an allowlist + non-matching email and asserts 403 `{"code":"email_domain_not_allowed"}`.

**Verification.** `uv run pytest packages/server/tests/test_routes/test_auth_routes.py::TestRegisterErrors -v` green.

---

### P2-02-03 — `crypto.py` rotation CLI has no round-trip integration test with real LLM/Data/WebSearch rows

**Bug.** `cli.py:678-757` rotates every `api_key_encrypted` across three models. `tests/test_cli/test_cli_crypto_rotation.py` is only 37 lines and only exercises the low-level `encrypt_with_key` / `decrypt_with_key` helpers — not the CLI command. A regression in the command's `db.execute("BEGIN EXCLUSIVE")` / rollback path or in the iteration over `(LLMProvider, DataProvider, WebSearchProvider)` would pass unit tests and break in production.

**Files.**
- `packages/server/src/openlia_server/cli.py:678-757` (`secrets_rotate_key`).
- `packages/server/tests/test_cli/test_cli_crypto_rotation.py` (insufficient).

**Plan ref.** "Out of scope (deferred): `openlia secrets rotate-key` CLI wrapper — Plan 7". Plan 7 ships the CLI wrapper; since it's live today and rotation is in-scope (Plan 2 Task 3), this audit claims it.
**Spec ref.** `AccountManagementSpec.md` §9 "Key rotation", `database-design.md` §5.

**Acceptance.** New `test_cli_crypto_rotation.py::TestRotateKeyCLI`:
1. Seed one `LLMProvider`, one `DataProvider`, one `WebSearchProvider` with a known plaintext encrypted under `OPENLIA_SECRET_KEY=<old>`.
2. `CliRunner().invoke(app, ["secrets", "rotate-key", "--new-key", <new_b64>])` → exit code 0, output contains `"3 values re-encrypted"`.
3. Swap env to the new key, reset `_cached_key`, decrypt each row — plaintext matches.
4. Invoke again with the same new key → exit 1 `"new key must differ from the current key."`.

**Verification.** `uv run pytest packages/server/tests/test_cli/test_cli_crypto_rotation.py -v` green.

---

### P2-02-04 — `signup_policy.seed_signup_policy` idempotency isn't asserted at route-level

**Bug.** `services/auth/signup_policy.py:1257-1272` — second call short-circuits when a row exists (preventing personal→company mode flip from silently opening registration). Unit test covers this (`test_signup_policy.py::test_seed_is_idempotent`). No integration test covers the bootstrap path — i.e., a server restart with `OPENLIA_MODE` flipped personal→company does *not* change the persisted `mode` (intentional — admin must manually flip).

**Files.**
- `packages/server/src/openlia_server/db/bootstrap.py` (adds seed call).

**Plan ref.** Task 8 "Wire into bootstrap".
**Spec ref.** `AccountManagementSpec.md` §3 "Signup modes".

**Acceptance.** `test_db/test_bootstrap.py` (or the existing bootstrap smoke) gets `test_mode_flip_does_not_overwrite_policy`: run `bootstrap` with `OPENLIA_MODE=personal` then again with `OPENLIA_MODE=company`; assert the row is still `mode="closed"`. Optional: add an admin-only endpoint `PUT /admin/signup-policy` to flip modes explicitly (spec §3 permits it, plan defers — leave deferred if a separate phase owns it).

**Verification.** `uv run pytest packages/server/tests/test_db/ -v` green.

---

### P2-02-05 — Register response does not verify invite `token_hash` lookup after the REM-P1-003 hashed-token migration

**Bug.** `services/auth/registration.py:45-47` uses `tokens.hash_token(invite_token)` on lookup, correctly matching the post-REM-P1-003 `token_hash` schema. `tests/test_services/test_auth/test_registration.py` still refers to `SignupInvite(... token=token ...)` per the plan draft (Task 9 Step 1). That's stale fixture shape — at minimum confirm the test file updated; if not, refresh the fixture to store `token_hash=tokens.hash_token(raw)` and pass the `raw` string as `invite_token`.

**Files.**
- `packages/server/tests/test_services/test_auth/test_registration.py` (fixture).

**Plan ref.** Plan Task 9 + REM-P1-003 remediation log (2026-04-22).
**Spec ref.** N/A (hash-at-rest migration).

**Acceptance.** Fixture in `test_registration.py::make_invite` stores `token_hash=tokens.hash_token(raw_token)` and returns both rows + raw token. Every test that calls `registration.register(..., invite_token=...)` passes the raw string, not the DB column.

**Verification.** `uv run pytest packages/server/tests/test_services/test_auth/test_registration.py -v` green.

---

## Missing tests

- `tests/test_routes/test_must_change_password_gate.py` — add settings_prefs/email/models coverage (ties to P0-02-01).
- `tests/test_routes/test_auth_routes.py::TestRegisterLoginLogout::test_login_rotates_prior_session` (P0-02-02).
- `tests/test_services/test_auth/test_public_api.py` — import smoke of the newly populated `__init__.py` (P1-02-01).
- `tests/test_routes/test_auth_routes.py::TestRateLimits` — 4 methods covering every rate-limited route (P1-02-04).
- `tests/test_routes/test_auth_routes.py::TestPersonalModeNoAuthRoutes` — parametrize every `/auth/*` and `/admin/*` route → 404 (P1-02-05).
- `tests/test_routes/test_auth_routes.py::TestPasswordResetFlow::test_request_approve_consume_revokes_sessions_and_replay_blocked` (P1-02-06).
- `tests/test_routes/test_auth_routes.py::TestCookieFlags` — 3 methods covering `HttpOnly`, `SameSite`, `Secure`, `Path=/`, `Max-Age` (P1-02-07).
- `tests/test_services/test_auth/test_login.py::TestLockout::test_lockout_emits_ordered_events` (P1-02-08).
- `tests/test_routes/test_auth_routes.py::TestRegisterErrors::test_email_domain_rejected` (P2-02-02).
- `tests/test_cli/test_cli_crypto_rotation.py::TestRotateKeyCLI` — full rotation round-trip across 3 provider tables (P2-02-03).
- `tests/test_db/test_bootstrap.py::test_mode_flip_does_not_overwrite_policy` (P2-02-04).

## Verification checklist

- [ ] `uv run pytest packages/server/tests/test_middleware/ -v` green.
- [ ] `uv run pytest packages/server/tests/test_services/test_auth/ -v` green.
- [ ] `uv run pytest packages/server/tests/test_routes/test_auth_routes.py packages/server/tests/test_routes/test_must_change_password_gate.py -v` green.
- [ ] `uv run pytest packages/server/tests/test_routes/test_settings_general_routes.py packages/server/tests/test_routes/test_settings_email_routes.py packages/server/tests/test_routes/test_settings_models_routes.py -v` green.
- [ ] `uv run pytest packages/server/tests/test_cli/test_cli_crypto_rotation.py packages/server/tests/test_cli/test_cli_secrets.py -v` green.
- [ ] `uv run pytest packages/server/tests/test_db/test_crypto.py -v` green.
- [ ] `grep -rn "build_require_auth(" packages/server/src/openlia_server/routes/settings_{general,email,models}.py` returns zero matches (all swapped to `build_require_active_user`).
- [ ] `from openlia_server.services.auth import authenticate, register, request_reset, create_session, hash_password, log_auth_event, AuthError` succeeds in a Python REPL against the installed `openlia` package.
- [ ] Every cross-reference to `route-authorization-matrix.md` in `planning/` resolves to an existing file.
- [ ] Cookie attributes on `/auth/login` response in company mode match spec table (`HttpOnly`, `SameSite=Lax`, `Secure` when `OPENLIA_COOKIE_SECURE=true`, `Path=/`).
- [ ] `/auth/login` called with a stale cookie revokes the stale session before issuing a new one.
