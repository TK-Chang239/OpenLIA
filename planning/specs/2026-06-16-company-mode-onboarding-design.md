# Company Mode Onboarding — Re-enable Login & Admin Loop (Design)

Status: design / approved-to-plan
Date: 2026-06-16
Scope: Make company mode usable end-to-end — an admin completes setup, logs in,
invites users, and a second user registers and logs in. This is primarily
**re-enabling deliberately-disabled frontend auth**, not new backend work.

## Goal

Restore the company-mode onboarding loop in the browser:

1. Operator runs the setup wizard in company mode → first admin created.
2. Admin logs in.
3. Admin creates a signup invite.
4. A second user registers with the invite token and logs in.
5. Admin can manage users (disable/enable/reset-password) and the
   admin-mediated password-reset queue.

Personal mode (the default, single-user, no-auth deployment) must remain
completely unaffected.

## Background — current state

The backend multi-user stack is complete and already gated to company mode
(`OPENLIA_MODE=company`):

- Session-cookie auth (`openlia_session`, SHA256 token hash, `sessions` table),
  login/logout/logout-all, login lockout (5 fails → 15 min), rate limiting,
  session-fixation defense. `routes/auth.py`
- Admin surface: invites (create/list/revoke), user management
  (list/disable/enable/reset-password), password-reset approval queue.
  `routes/admin.py`
- Signup policy (`closed` / `invite_only`, email-domain allowlist).
- Wizard company path: `mode → admin → models → providers → access_control →
  review`, with `create_first_admin` and `set_signup_policy`.
- Per-user data scoping is correct: reports filter `WHERE user_id == user.id`;
  chat sessions enforce ownership.

The frontend auth UI was **deliberately disabled** during the UI remake
(commit `ca39452f`, PR #97). Everything still exists:

- Pages `LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`
  exist but `router/routes.tsx` replaces each with `<Navigate to="/" replace />`.
- Forms `LoginForm`, `RegisterForm`, `ForgotPasswordForm`, `ResetPasswordForm`,
  `MustChangePasswordForm` exist **with tests**.
- Admin panels `InvitesPanel`, `UsersPanel`, `ResetRequestsPanel` exist and are
  wired to `api/admin.ts`; reachable only once login works.
- `auth/AuthContext.tsx#refresh` collapses **every** session-fetch outcome to
  `personal` mode, so `ProtectedRoute` never sees `unauthenticated` and never
  redirects to `/login`.
- Only `ChangePasswordForm` and `SessionsPanel` are 3-line stubs.
- `ApiError` (`api/client.ts`) carries `.status`, so the frontend can already
  distinguish `404` (personal) from `401` (company, not logged in).

## In scope

1. Restore the four auth route elements in `router/routes.tsx`.
2. Restore `AuthContext` mode detection (404 → personal, 401 → unauthenticated).
3. Build the real `ChangePasswordForm` component.
4. Build `SessionsPanel` as a "sign out of all other devices" action.
5. Add a logout control to the desktop `Sidebar`.
6. Admin-mediated password reset path (forgot-password + reset-password pages),
   wired to the existing approval queue. No email infra — token hand-off is
   out-of-band.
7. Verification: automated tests (pytest + vitest) and a manual browser
   checklist; an audit pass for other remake-era "login disabled" assumptions.

## Out of scope

- Per-session listing UI (no `GET /auth/sessions` endpoint exists; not adding
  one). `SessionsPanel` is a single "sign out everywhere" action in this pass.
- Email-based password reset / email verification — system has no email infra.
- New RBAC roles beyond `is_admin`; multi-tenant org scoping.
- Any change to personal-mode behavior or to the setup wizard logic itself.

## Design

### 1. Route elements (`frontend/src/router/routes.tsx`)

Re-add the page imports and replace the four redirect stubs (lines 75-78) with
the real pages — the exact pre-remake structure:

```tsx
{ path: "/login", element: <LoginPage /> },
{ path: "/register", element: <RegisterPage /> },
{ path: "/forgot-password", element: <ForgotPasswordPage /> },
{ path: "/reset-password", element: <ResetPasswordPage /> },
```

These remain children of `<SetupGate />`, before `<ProtectedRoute>`, so they are
reachable without auth. Do **not** touch the post-remake `/` → `<Home />`
mapping or any other route.

### 2. Mode detection (`frontend/src/auth/AuthContext.tsx`)

Restore the pre-remake `refresh` and `logout` semantics (verified to have
existed before the remake):

```tsx
const refresh = useCallback(async (): Promise<void> => {
  try {
    const fetched = await getSession();
    setUser(fetched.user);
    setMustChangePasswordState(fetched.must_change_password);
    setStatus("authenticated");
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      setUser(LOCAL_USER);
      setMustChangePasswordState(false);
      setStatus("personal");
      return;
    }
    setUser(null);
    setMustChangePasswordState(false);
    setStatus("unauthenticated");
  }
}, []);
```

`logout` sets `unauthenticated` (company). Personal mode never renders a logout
control, so personal users never reach this path. `ProtectedRoute` already
contains the `unauthenticated → <Navigate to="/login">` branch — no change
needed there.

Rationale for status-based detection over a new `/api/config` mode endpoint:
the `404` (auth routes unmounted in personal mode) vs `401` (company, no
session) distinction is deterministic and already wired; it was the original
design and needs no backend addition.

### 3. `ChangePasswordForm` (`frontend/src/components/auth/ChangePasswordForm.tsx`)

Real component modeled on the existing `MustChangePasswordForm`:

- Fields: current password, new password, confirm new password.
- Client validation: new == confirm; min length matching backend policy.
- Calls existing `changePassword({ current_password, new_password })`.
- Surfaces backend errors (wrong current password, policy failure); shows
  success state. Rendered inside `AccountSection`.

### 4. `SessionsPanel` (`frontend/src/components/auth/SessionsPanel.tsx`)

Scoped to existing backend support (`logout-all` only):

- Explanatory line + a "Sign out of all other devices" button calling
  `logoutAll()`.
- Confirm + success/error states.
- Comment noting a full per-session list is a future enhancement requiring a
  new `GET /auth/sessions` endpoint.

### 5. Desktop sidebar logout (`frontend/src/components/sidebar/Sidebar.tsx`)

Add a sign-out control matching the mobile overlay's behavior
(`MobileSidebarOverlay` lines ~114-127): visible only when
`status === "authenticated"`; calls `logout()` then navigates to `/login`.
Invisible in personal mode.

## Data flow

```
Browser load
  → AuthContext.refresh() → GET /api/auth/session
      200  → authenticated → app shell
      404  → personal      → synthetic local admin, no login UI
      401  → unauthenticated → ProtectedRoute → /login

/login → LoginForm → POST /api/auth/login → cookie set → authenticated
/register?invite=TOKEN → RegisterForm → POST /api/auth/register → authenticated
/forgot-password → ForgotPasswordForm → POST /api/auth/password-reset/request
   → admin approves in ResetRequestsPanel → token conveyed out-of-band
/reset-password?token=… → ResetPasswordForm → POST /api/auth/password-reset/consume
Account → ChangePasswordForm → POST /api/auth/change-password
Account → SessionsPanel → POST /api/auth/logout-all
```

## Error handling

- Login: lockout (`423`) and rate-limit (`429`) already surfaced by
  `LoginForm`; verify still correct after re-enable.
- Register: invalid/expired/exhausted invite, domain-policy rejection — surfaced
  by `RegisterForm`.
- `must_change_password`: existing `MustChangePasswordGate` blocks the app until
  resolved; unchanged.
- Network/`ApiError 0`: forms show a generic failure; `refresh` treats a non-404
  error as `unauthenticated` (fail safe — prompts login rather than silently
  granting personal access).

## Testing

- **pytest** (`packages/server/tests`): confirm/extend coverage of
  register-with-invite, login + lockout, logout-all, and admin
  invite/user/reset endpoints.
- **vitest**: new tests for `ChangePasswordForm` and `SessionsPanel`; a test
  asserting `AuthContext` maps `404 → personal` and `401 → unauthenticated`.
- **Audit pass**: grep for other remake-era assumptions that login is disabled
  / personal-only, beyond the three files above.
- **Manual checklist** (operator-run): wizard → first admin → login → create
  invite → register 2nd user with token → 2nd user login → admin disables 2nd
  user → 2nd user locked out. Personal regression: a fresh personal instance
  boots with no login UI.

## Risks

- Personal mode is the default and most-used; the `404 → personal` branch must
  stay correct. Covered by the audit pass and the personal regression check.
- Pre-existing CI red (`SettingsShellBlocker` AbortSignal in vitest; alembic
  drift in pytest) is unrelated and must not be conflated with this work.
