# Phase 9 — Login / Account UI fix plan (to 100%)

**Current shipped:** ~88% (plan ~90% / spec ~85%). **Root cause:** IMPLEMENTER
(contract drift + a11y skipped). Five unauth views + three Account panels
all shipped; tests exist for every file; primary defects are the server
`display_name` contract, sign-up-policy gating never wired, `account_locked`
payload shape mismatch, and inputs never wired to inline error ids via
`aria-describedby`.

## Gap summary (verified against code on 2026-04-24)

1. **P0-08** — `RegisterIn.display_name = Field(min_length=1, max_length=128)`
   (`routes/auth.py:29`). `RegisterForm.tsx:84` sends
   `display_name: form.display_name.trim() || undefined` per spec
   "Display Name (optional, defaults to email local-part)" — blank submission
   → FastAPI 422 (field missing). Spec says optional with email-local-part
   fallback; registration service has no such fallback.
2. **P1-17** — `LoginPage.tsx` never calls `getSignupPolicy()`. Sign-up link
   in `LoginForm.tsx:184` renders whenever `inviteToken` is truthy,
   regardless of server policy. `api/auth.ts:97` exports `getSignupPolicy`
   but no page consumes it. `RegisterPage.tsx` also trusts the URL token
   with only a client-side `length < 8` heuristic (not in spec).
3. **P1-18** — server lockout payload is `{code:"account_locked",
   retry_after_seconds:N}` (`routes/auth.py:148-154`); spec §10.1 + §6.2
   say `{code, message, metadata:{retry_after_seconds}}`.
   `LoginForm.tsx:90-95` reads `body.message` (undefined → falls back to
   static "Account is temporarily locked.") and never reads
   `retry_after_seconds`. User never learns the 15-minute lockout window.
4. **NEW-9-01** — Inline error elements in `FormField.tsx:32-39` carry
   `id="${id}-error"` but no input in `LoginForm.tsx`, `RegisterForm.tsx`,
   `ForgotPasswordForm.tsx`, `ResetPasswordForm.tsx`,
   `MustChangePasswordForm.tsx`, or `pages/account/ChangePasswordForm.tsx`
   sets `aria-describedby={fieldErrors.<x> ? "<id>-error" : undefined}`.
   `PasswordInput.tsx` has no `aria-describedby` prop at all. Spec
   LoginPageSpec §Accessibility bullet 3 requires it; AccountManagementSpec
   inherits via §10.1.
5. **NEW-9-02** — `aria-busy={submitting}` is present on submit buttons
   (good) but spec §Accessibility also implies inputs announce the busy
   state. Verify inputs set `disabled={submitting}` everywhere (they do) —
   this task is a formal audit/test, not a code gap.
6. **NEW-9-03 — AccountManagement parity**
   - `/auth/register` response omits `is_admin` and `must_change_password`
     (`routes/auth.py:117`) → `RegisterForm` calls `setMustChangePassword(
     result.must_change_password)` which is always falsy; `role` mapping
     can silently drop admin-on-self-register edge cases. Align the
     register response with the login response shape.
   - `RegisterPage.tsx:18` rejects invite tokens with `length < 8` client-
     side; spec makes `/auth/signup-policy` + server validation
     authoritative. Remove heuristic; rely on server `invite_invalid` code.
   - `SessionsPanel.tsx` passes an `async` handler straight to
     `onClick={onClick}` — React ignores the returned Promise; minor but
     audit-flagged.
7. **NEW-9-04** — Register response contract alignment (verified gap).
   `auth.py` `register` handler returns
   `{user_id, email, display_name}` only; login returns five fields. Spec
   §9 treats `/auth/register` as equivalent to login (auto-session). The
   frontend `register()` wrapper types it as `BackendLoginResponse` —
   mismatch is silent because `Boolean(undefined)` is `false`.
8. **NEW-9-05 — Network/offline error mapping.** Each form's
   `handleError` treats "not an `ApiError`" as "Unexpected error. Please
   try again." but never differentiates offline (`TypeError: Failed to
   fetch`) from 5xx. Spec §Feedback & Messaging asks for a distinct
   tone for rate-limit/lockout (already done) but not offline — still,
   a shared helper `mapTransportError(err)` would halve duplicated error
   handlers across six forms.
9. **NEW-9-06 — Cookie/session handling.** `fetchJson` uses
   `credentials: "include"` (verified in Phase 8); Phase 9 adds nothing
   new. However `getSession()` on 401 returns a rejected promise; the
   `LoginPage` `useEffect` redirect for already-authenticated users
   depends on `status === "authenticated"` — no bug, but missing test
   that a 401 `getSession` after logout clears `mustChangePassword`.
10. **NEW-9-07 — ForgotPasswordForm error swallowing.** Catch block
    sets `done=true` on **any** failure (lines 26-33). A 500 is
    indistinguishable from success. Spec §Forgot Password View calls
    for neutral confirmation on success OR 200 from server; a 5xx
    should surface a banner. Anti-enumeration applies to "email not
    found", not to network failure.
11. **NEW-9-08 — Spec label drift.** Spec says primary button label
    "Log In" (title case, two words). Shipped: "Log In" (matches).
    Spec says "Request Reset"; shipped: "Request Reset" (matches).
    "Sign up" link wording: "Don't have an account? Sign up"
    (matches). **No label drift detected.** Keep this task as a
    documented audit pass so the next reviewer does not re-walk.
12. **NEW-9-09 — Vitest coverage gaps.** Tests exist for every form
    (`LoginForm.test.tsx`, `RegisterForm.test.tsx`, etc.) but none
    assert: (a) redirect to `?next=` after login, (b) `display_name`
    omitted from register body, (c) `account_locked` banner carries
    retry-after minutes, (d) signup link hidden when policy is
    `closed`, (e) `aria-describedby` wiring. All listed acceptance
    criteria below become vitest cases.

## Tasks (execute in order)

1. **P0-08 — Make `display_name` optional on `/auth/register` with
   email-local-part fallback.**
   - Files:
     - `packages/server/src/openlia_server/routes/auth.py` — `RegisterIn`:
       change `display_name: str = Field(min_length=1, max_length=128)`
       to `display_name: str | None = Field(default=None, max_length=128)`.
     - `packages/server/src/openlia_server/services/auth/registration.py`
       — inside `register()`, compute
       `display_name = (display_name or "").strip() or email.split("@",1)[0]`
       before insert.
   - Spec ref: `LoginPageSpec.md` Registration View, Display Name
     "optional, defaults to email local-part".
   - Acceptance: pytest `test_register_accepts_missing_display_name`
     posts `{email, password, invite_token}` → 201, `users.display_name
     == "alice"` for `alice@example.com`.

2. **P1-17 — Fetch and honor signup policy on LoginPage + RegisterPage.**
   - Files:
     - `frontend/src/pages/LoginPage.tsx` — on mount, call
       `getSignupPolicy()`; on 404 or failure default to
       `{mode:"invite_only", invite_required:true}`. Pass
       `policyMode` prop to `LoginForm`.
     - `frontend/src/components/auth/LoginForm.tsx` — render Sign up
       link only when `policyMode !== "closed"` AND `inviteToken`
       present.
     - `frontend/src/pages/RegisterPage.tsx` — call
       `getSignupPolicy()`; if `mode === "closed"` render a banner
       "Registration is closed." with Back to Log In link; remove the
       client-side `length < 8` heuristic.
   - Plan ref: Design Rule 11.
   - Spec ref: `LoginPageSpec.md` Login View (Sign up link visibility);
     `AccountManagementSpec.md` §6.1 step 3.
   - Acceptance:
     - vitest: LoginPage with `policy.mode="closed"` + `?invite=abc`
       → no "Sign up" link in DOM.
     - vitest: RegisterPage with `policy.mode="closed"` → banner
       shown, no form.

3. **P1-18 — Align server `account_locked` payload with spec and
   surface retry-after on the client.**
   - Files:
     - `packages/server/src/openlia_server/routes/auth.py:147-154` —
       return `{"code":"account_locked", "message":"Account is
       temporarily locked.", "metadata":{"retry_after_seconds":
       exc.retry_after_seconds}}`.
     - `frontend/src/components/auth/LoginForm.tsx:90-95` — read
       `body.metadata?.retry_after_seconds`, convert to minutes
       (ceil), render `Try again in N minutes.` warning banner.
   - Spec ref: `LoginPageSpec.md` §Page Functionality 7, §Feedback &
     Messaging Rate limit / account locked.
     `AccountManagementSpec.md` §10.1, §9 error shape.
   - Acceptance:
     - pytest: locked user login → 423 body matches the three-key
       shape.
     - vitest: `account_locked` + `metadata.retry_after_seconds: 900`
       → banner text "Try again in 15 minutes."

4. **NEW-9-01 — Wire `aria-describedby` in every auth form.**
   - Files:
     - `frontend/src/components/primitives/PasswordInput.tsx` — add
       `describedBy?: string` prop, forward as `aria-describedby`.
     - `frontend/src/components/auth/LoginForm.tsx`,
       `RegisterForm.tsx`, `ForgotPasswordForm.tsx`,
       `ResetPasswordForm.tsx`, `MustChangePasswordForm.tsx`,
       `frontend/src/pages/account/ChangePasswordForm.tsx` — on each
       input set
       `aria-describedby={fieldErrors.<x> ? "<id>-error" : undefined}`
       (for `<input>`) or pass `describedBy={...}` to `PasswordInput`.
   - Spec ref: `LoginPageSpec.md` §Accessibility bullet 3.
   - Acceptance: vitest — submit each form with an invalid field;
     assert the input's `aria-describedby` equals the error `<span>`
     `id` (`<field>-error`). Six test cases, one per form.

5. **NEW-9-02 — `aria-busy` audit + test coverage.**
   - Files: same six forms.
   - Work: verify `aria-busy={submitting}` on every submit button
     (already present) and add one vitest per form asserting
     `aria-busy="true"` during submission, `"false"` after resolve.
   - Spec ref: `LoginPageSpec.md` §Accessibility bullet 5.
   - Acceptance: six passing vitest assertions.

6. **NEW-9-04 — Align register response with login shape.**
   - Files:
     - `packages/server/src/openlia_server/routes/auth.py:117` —
       return `{"user_id", "email", "display_name", "is_admin",
       "must_change_password": False}` (always false on fresh signup).
     - `frontend/src/api/auth.ts` — keep existing `register()` wrapper;
       now `result.must_change_password` is authoritative.
   - Spec ref: `AccountManagementSpec.md` §6.1 step 8 (issue session);
     §9 API surface consistency.
   - Acceptance: pytest asserts register response has five fields
     including `is_admin: false, must_change_password: false`.

7. **NEW-9-03 — AccountManagementSpec parity sweep.**
   - Files:
     - `frontend/src/pages/account/AccountProfile.tsx` — confirm
       labels (Email, Display name, Role, User ID) match
       `AccountManagementSpec.md` §10 account panel (no admin role
       flag drift).
     - `frontend/src/pages/account/SessionsPanel.tsx` — wrap the
       async `onClick` so React does not see a `Promise`:
       `onClick={() => { void onClick(); }}`.
   - Acceptance: spec walk-through recorded as inline comments on
     PR; no functional regression tests beyond an eslint pass.

8. **NEW-9-05 — Shared transport-error helper.**
   - Files: add `frontend/src/api/errors.ts` exporting
     `mapTransportError(err): { message: string; variant: BannerVariant }`
     that distinguishes `TypeError`/offline, 5xx, and unknown.
     Use in `LoginForm`, `RegisterForm`, `ForgotPasswordForm`,
     `ResetPasswordForm`, `MustChangePasswordForm`,
     `pages/account/ChangePasswordForm.tsx`, `SessionsPanel.tsx`.
   - Spec ref: `LoginPageSpec.md` §Feedback & Messaging, §Error.
   - Acceptance: vitest — each form, when `fetchJson` throws a
     `TypeError`, renders banner "Can't reach the server. Check your
     connection."; on 5xx (`ApiError` with `status>=500`) renders
     "Something went wrong on our end. Please try again."

9. **NEW-9-07 — ForgotPasswordForm: surface transport failure.**
   - Files: `frontend/src/components/auth/ForgotPasswordForm.tsx` —
     in the `catch` block, distinguish `ApiError.status === 429` (rate
     limit banner) and transport failures (use NEW-9-05 helper). Only
     show the neutral success banner on 2xx.
   - Spec ref: `LoginPageSpec.md` §Forgot Password View (neutral on
     success, error on network/rate).
   - Acceptance: vitest — 500 response shows error banner, not
     success banner.

10. **NEW-9-09 — Fill vitest coverage gaps.**
    - Files: `LoginPage.test.tsx`, `LoginForm.test.tsx`,
      `RegisterForm.test.tsx`, `RegisterPage.test.tsx`.
    - Cases:
      - `?next=/secretary` query param: on login success, router
        navigates to `/secretary` (assert mock `navigate`).
      - `RegisterForm` omits `display_name` from POST body when
        input is blank (assert `fetchJson` call body).
      - Sign-up link: combine policy + invite matrix
        (`closed+invite`, `invite_only+invite`, `invite_only+no-
        invite`, `open+no-invite`) — four cases, only the last two
        relevant to v1.
    - Acceptance: all listed cases pass; coverage report shows
      forms at >=85% line coverage.

## Verification

```bash
uv run pytest packages/server/tests/test_auth_register.py \
  packages/server/tests/test_auth_login.py
cd frontend && npm run test -- auth account Login Register Forgot Reset MustChange
```

Manual:

- Blank `display_name` on register → 201 and profile panel shows
  email local-part.
- `/login?invite=abc` with `signup_policy.mode="closed"` → no Sign
  up link.
- Lock an account (5 failed logins), attempt login → yellow banner
  "Try again in 15 minutes.".
- Disconnect network, submit any auth form → "Can't reach the
  server. Check your connection." banner.
- Screen reader (VoiceOver): submit empty login form, confirm the
  email input announces the inline error text via
  `aria-describedby`.
