# Phase 9 — Login / Account UI fix plan (→ 100%)


**Current:** ~88% shipped. **Root cause:** IMPLEMENTER (contract + a11y gaps).

**Gap summary:** Five views shipped (Login/Register/Forgot/Reset/MustChange) + account management panel. Contract mismatches remain against `LoginPageSpec` (display_name required server-side; sign-up-link visibility not gated by policy; lockout retry-after never surfaced) and a11y: inline errors lack `aria-describedby` wiring.

**Tasks (in execution order):**

1. **P0-08 — Fix `display_name` requirement on `/auth/register`.**
   - Files: `packages/server/src/openlia_server/routes/auth.py:29` (relax `Field(min_length=1)` → `Optional`); `services/auth/registration.py` add `display_name = display_name or email.split("@", 1)[0]` fallback.
   - Spec ref: LoginPageSpec §Registration View.
   - Acceptance: `test_register_accepts_missing_display_name` posts `{email, password}` → 200 with `display_name == email_local_part`.

2. **P1-17 — Gate sign-up link on `GET /auth/signup-policy`.**
   - Files: `frontend/src/pages/LoginPage.tsx` — call `getSignupPolicy()` on mount; show "Sign up" link only when `policy != "closed"` AND `?invite=` present; `frontend/src/api/auth.ts` add `getSignupPolicy()` if missing.
   - Plan ref: Phase 9 Design Rule 11.
   - Spec ref: LoginPageSpec §Login View.
   - Acceptance: vitest — with `policy: "closed"`, link stays hidden even with `?invite=abc`.

3. **P1-18 — Surface `account_locked` retry-after.**
   - Files: `routes/auth.py` (login handler) — populate `message`; `frontend/src/components/auth/LoginForm.tsx` — read `metadata.retry_after_seconds`, render banner.
   - Spec ref: LoginPageSpec §Page Functionality 7, §Feedback & Messaging.
   - Acceptance: vitest — 423 with `metadata.retry_after_seconds=900` renders yellow banner "Try again in 15 minutes."

4. **NEW-9-01 — Wire `aria-describedby` from input to inline error across all five auth forms.** Why new: tracker lists only display_name + policy + lockout; spec §Accessibility requires.
   - Files: `LoginForm.tsx`, `RegisterForm.tsx`, `ForgotPasswordForm.tsx`, `ResetPasswordForm.tsx`, `MustChangePasswordForm.tsx`, `ChangePasswordForm.tsx`.
   - Acceptance: vitest — input receives `aria-describedby` equal to error element's `id` on validation failure.

5. **NEW-9-02 — `aria-busy="true"` on primary button during submission.** Why new: spec §Accessibility bullet 5.
   - Files: same six form files as NEW-9-01.
   - Acceptance: vitest confirms `aria-busy="true"` while `isSubmitting`.

6. **NEW-9-03 — AccountManagementSpec parity pass.** Why new: spec not referenced in tracker.
   - Files: `frontend/src/pages/account/AccountProfile.tsx`, `SessionsPanel.tsx`, `ChangePasswordForm.tsx`.
   - Spec ref: AccountManagementSpec (all sections).
   - Acceptance: spec walk-through lists each section as shipped or gap; any gaps filed as follow-ons.

**Verification:** `uv run pytest packages/server/tests/test_auth*` + `cd frontend && npm run test -- auth` green; manual: register with blank display_name succeeds; `?invite=abc` in `closed` mode shows no sign-up link.
