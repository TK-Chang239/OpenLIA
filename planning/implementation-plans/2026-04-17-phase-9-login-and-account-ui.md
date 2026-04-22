# Login + Account Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Audit 2026-04-20 normalizations (apply before executing this plan):**
> - Backend login/session responses are **flat**: `{user_id, email, display_name, is_admin, must_change_password}`. Test fixtures that mock `{user: {id, email, role}, must_change_password}` are pre-audit drift — replace with the flat shape and map at the frontend boundary (`id = user_id`, `role = is_admin ? "admin" : "user"`).
> - The auth error payload `{code, message, field?, metadata?}` assumed in this plan is correct; keep it.
> - Admin gating uses `is_admin`, not `role`. Any `user.role === "admin"` check must become `user.role === "admin"` post-mapping or `is_admin === true` pre-mapping — do not read `role` off the raw response.

**Goal:** Ship the company-mode authentication UI on top of the Phase 8 shell — Login, invite-gated Registration, Forgot Password (in-place), Reset Password (standalone route), Must-Change-Password gate, and the Account section (profile, change password, sessions/logout-all) that Plan 11 will slot into Settings.

**Architecture:** A single `AuthLayout` centers an `AuthCard` for every unauthenticated view. `LoginPage` owns three in-place sub-views (`login` / `register` / `forgot`) selected by URL (`/login`, `/register`, `/forgot-password`) so browser back/forward works. `/reset-password?token=...` is a separate route because it's reached via a one-time link. `MustChangePasswordGate` is a wrapper component mounted inside `ProtectedRoute` — when `useAuth().mustChangePassword` is true it replaces the outlet with a forced change-password screen. The Account section ships as pure components (`AccountProfile`, `ChangePasswordForm`, `SessionsPanel`) that Plan 11 composes into `/settings`. All forms are uncontrolled + `useState`-driven; no form libraries. Password strength uses a tiny in-house heuristic — zxcvbn is not pulled in.

**Tech Stack:** React 18, TypeScript 5 (strict), react-router-dom v6, Tailwind CSS v3, lucide-react, vitest + @testing-library/react + jsdom. Everything already installed in Plan 8.

**Source specs:**
- `planning/specs/pages/LoginPageSpec.md`
- `planning/specs/components/AccountManagementSpec.md`

**Depends on:**
- Plan 2 — server auth endpoints (`/auth/login`, `/auth/logout`, `/auth/logout-all`, `/auth/register`, `/auth/session`, `/auth/password-reset/request`, `/auth/password-reset/consume`, `/auth/change-password`, `/auth/signup-policy`) with `openlia_session` cookie; error response shape `{code, message, field?, metadata?}`; `must_change_password` returned on the login response.
- Plan 8 — `fetchJson` / `ApiError`, `AuthContext` / `useAuth`, `ProtectedRoute`, router tree, design tokens, Tailwind config, placeholder `Login` / `Setup` pages.

**Unblocks:**
- Plan 10 (Setup Wizard) — reuses `AuthCard`, `FormField`, `Banner`, and the primary button styling.
- Plan 11 (Settings) — embeds `AccountProfile`, `ChangePasswordForm`, `SessionsPanel` into the Account section.

**Out of scope:**
- Admin-side Password Reset Requests UI, Users list, Invites list — these live in Settings → Admin and belong to Plan 11.
- Setup Wizard's own sign-up-first flow — Plan 10.
- 2FA / OAuth / passwordless / CAPTCHA — non-goals per `LoginPageSpec.md` §Non-Goals.
- Responsive < 768 px polish — v1 targets desktop per Plan 8's stance. Mobile full-bleed card variant from the spec is implemented (it's a single class toggle), but hamburgers and bottom-tab navigation are not.

---

## File Structure

### New (frontend)
```
frontend/src/
├── api/
│   ├── auth.ts                           # EXTEND: add register, getSignupPolicy,
│   │                                     #   requestPasswordReset, consumePasswordReset,
│   │                                     #   changePassword, logoutAll
│   └── auth.test.ts                      # EXTEND with matching unit tests
├── auth/
│   ├── AuthContext.tsx                   # EXTEND: mustChangePassword state + setters
│   ├── AuthContext.test.tsx              # EXTEND tests
│   └── passwordStrength.ts               # NEW: strength heuristic (0-4)
│       passwordStrength.test.ts          # NEW
├── components/
│   ├── primitives/
│   │   ├── Banner.tsx                    # NEW: inline form banner (error|success|warning)
│   │   ├── Banner.test.tsx               # NEW
│   │   ├── FormField.tsx                 # NEW: label + input + helper + error stack
│   │   ├── FormField.test.tsx            # NEW
│   │   ├── PasswordInput.tsx             # NEW: <input> + show/hide toggle
│   │   ├── PasswordInput.test.tsx        # NEW
│   │   ├── PasswordStrengthMeter.tsx     # NEW: 4 bars + label
│   │   └── PasswordStrengthMeter.test.tsx# NEW
│   └── auth/
│       ├── AuthLayout.tsx                # NEW: centered single-column shell
│       ├── AuthCard.tsx                  # NEW: bordered card, mobile full-bleed
│       ├── LoginForm.tsx                 # NEW: email+password+keep-me in-place
│       ├── LoginForm.test.tsx
│       ├── RegisterForm.tsx              # NEW: email+password+confirm+display_name
│       ├── RegisterForm.test.tsx
│       ├── ForgotPasswordForm.tsx        # NEW
│       ├── ForgotPasswordForm.test.tsx
│       ├── ResetPasswordForm.tsx         # NEW: used by /reset-password route
│       ├── ResetPasswordForm.test.tsx
│       ├── MustChangePasswordForm.tsx    # NEW
│       ├── MustChangePasswordForm.test.tsx
│       └── AccountChrome.tsx             # NEW: shared Account section header
├── pages/
│   ├── LoginPage.tsx                     # REPLACE placeholder
│   ├── LoginPage.test.tsx                # NEW
│   ├── RegisterPage.tsx                  # NEW
│   ├── RegisterPage.test.tsx
│   ├── ForgotPasswordPage.tsx            # NEW
│   ├── ForgotPasswordPage.test.tsx
│   ├── ResetPasswordPage.tsx             # NEW
│   ├── ResetPasswordPage.test.tsx
│   └── account/
│       ├── AccountProfile.tsx            # NEW
│       ├── AccountProfile.test.tsx
│       ├── ChangePasswordForm.tsx        # NEW
│       ├── ChangePasswordForm.test.tsx
│       ├── SessionsPanel.tsx             # NEW
│       └── SessionsPanel.test.tsx
└── router/
    ├── routes.tsx                        # EXTEND: add /register, /forgot-password,
    │                                     #         /reset-password, swap /login page
    ├── MustChangePasswordGate.tsx        # NEW: render-gate inside ProtectedRoute
    └── MustChangePasswordGate.test.tsx   # NEW
```

### Modified (frontend)
- `frontend/src/styles/tokens.css` — add feedback colors, additional radii, focus-ring token, duration tokens, `bg-base` / `bg-input` aliases used by the spec.
- `frontend/tailwind.config.ts` — expose the new tokens so spec classes like `bg-[--color-feedback-error]/10` continue to work via arbitrary-value escape, but also add named utilities (`bg-feedback-error`, `text-feedback-error`, etc.) for terser component code.
- `frontend/src/router/routes.tsx` — register four new routes, wrap `ProtectedRoute` children in `MustChangePasswordGate`.
- `frontend/src/router/ProtectedRoute.tsx` — already redirects 401 → `/login`; extend `next` query-param handling (minor, covered in Task 13).
- `frontend/src/api/auth.ts` — extend exports as listed above.
- `frontend/src/api/auth.test.ts` — extend tests.
- `frontend/src/auth/AuthContext.tsx` — add `mustChangePassword: boolean` to context, `login()` action returns the flag, `clearMustChangePassword()` setter after successful forced change.
- `frontend/src/auth/AuthContext.test.tsx` — extend tests.
- `frontend/src/pages/Login.tsx` — deleted, replaced by `frontend/src/pages/LoginPage.tsx` (filename change to match the new namespace).

### Modified (planning)
- `planning/implementation-plans/README.md` — flip Plan 9 row to **Draft** and set its file column.
- `planning/projectStructure.md` — append the new `components/auth/`, `components/primitives/` additions, `pages/account/`, and `router/MustChangePasswordGate.tsx` under the frontend tree.

---

## Design Rules

These are invariants every task below respects. Read them once before starting.

1. **Personal mode never reaches this UI.** Every form component is mounted only under routes that require `status === "authenticated"` or `status === "unauthenticated"`. `ProtectedRoute` already handles the redirect for `personal`; `LoginPage` short-circuits via `useAuth()` — if `status !== "unauthenticated"`, it navigates to `/`.
2. **`/auth/*` is the backend prefix; `/api` is the frontend proxy prefix from Plan 8.** Every new API call uses `/api/auth/...`, matching Plan 8's `getSession` / `login` / `logout`.
3. **Forms are uncontrolled-but-state-synced.** Each form owns a single `formState` object via `useState`; inputs call a `setField("email", value)` helper. No refs, no react-hook-form.
4. **Client validation is thin.** Only three checks fire before submit: email format (RFC-ish regex), password minimum length (8), password-confirm equality. Everything else — rate-limit, lockout, weak-password server-side rules, invite validity — surfaces via the server's `{code, message, field?, metadata?}` response. Tests cover server-side error surfacing explicitly; client-side validation tests only cover the three local checks.
5. **Error mapping is one function.** `mapApiErrorToFormState(err: ApiError)` lives inline in each form and returns `{banner?: BannerProps, fieldErrors?: Record<string, string>}`. It reads `err.body.code`, `err.body.field`, and `err.body.metadata`. The same shape is produced regardless of which form called it, so the tests reuse fixtures.
6. **Banner is declarative, not imperative.** Forms render `<Banner>` when the state contains a banner; they don't dispatch to a global toast. This keeps the surface minimal and tests local.
7. **PasswordInput is controlled.** It takes `value`, `onChange`, `id`, and optional `autoComplete`. The show/hide toggle is internal state only — parents don't opt into it.
8. **Password strength is deterministic.** `passwordStrength(pw)` returns `0 | 1 | 2 | 3 | 4`. Pure function, unit-tested with a table of fixtures. Empty string → `0` (treated as "no bars"). Length < 8 → `1`. Otherwise count among {lowercase, uppercase, digit, symbol}: 2 classes → `2`, 3 classes → `3`, 4 classes → `4`.
9. **Must-Change-Password is a render gate, not a route.** `MustChangePasswordGate` sits between `ProtectedRoute` and the outlet. When `useAuth().mustChangePassword === true`, it renders `<MustChangePasswordForm />` inside `AuthLayout` regardless of the current path. On success the gate clears the flag in context and re-renders the outlet — no navigate() needed.
10. **Login response drives both auth state and the must-change flag.** `/api/auth/login` returns flat backend fields: `{user_id, email, display_name, is_admin, must_change_password}`. `api/auth.ts` maps that boundary shape into `{user: AuthUser, must_change_password}` for `AuthContext`. If the UI sees `must_change_password: true`, `AuthProvider` persists it across re-mounts until `changePassword()` succeeds or `logout()` is called.
11. **Signup policy is fetched once per `LoginPage` mount, with a 401/404 fallback.** The registration link only renders when `signupPolicy.invite_required === true` *and* `?invite=<token>` is present in the URL. 404 on `/auth/signup-policy` → treat as `invite_required: true, mode: "invite_only"` (the v1 default per `AccountManagementSpec.md` §2).
12. **`/reset-password` is the only auth route that doesn't share `LoginPage`.** The token is a one-time URL sent out-of-band; direct-linking semantics demand its own page component.
13. **Sessions panel shows only counts, not a list.** Per `AccountManagementSpec.md` §15 Open Q2, a full sessions-UI is a non-goal in v1 — we surface just "1 active session" and a "Sign out all other devices" button. The server's `/auth/logout-all` endpoint is what we hit.
14. **Tests don't share MSW — use `vi.fn` for fetch mocks.** Matches Plan 8's style. `beforeEach` restores mocks; each test sets its own chain with `mockResolvedValueOnce`.
15. **Commits per task.** Each task ends with an explicit `git add` + `git commit`. Use `feat(frontend): ...`, `test(frontend): ...`, `chore(frontend): ...` conventional prefixes. Keep the subject line under 72 chars.

---

## Task 1: Extend design tokens + Tailwind config

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Extend tokens.css**

Replace the contents of `frontend/src/styles/tokens.css`:

```css
:root {
  color-scheme: light dark;

  /* Backgrounds */
  --color-bg-app: #0f1115;
  --color-bg-base: #0f1115;          /* alias for auth views */
  --color-bg-elevated: #161a22;
  --color-bg-input: #12151c;
  --color-sidebar-bg: #12151c;

  /* Surfaces */
  --color-surface-hover: rgba(255, 255, 255, 0.04);
  --color-surface-active: rgba(255, 255, 255, 0.06);

  /* Accents */
  --color-accent-primary: #7c9cff;
  --color-accent-hover: #94acff;
  --color-accent-subtle: rgba(124, 156, 255, 0.12);

  /* Text */
  --color-text-primary: #e8eaf0;
  --color-text-secondary: #a8aec0;
  --color-text-tertiary: #6f758a;

  /* Icons */
  --color-icon-primary: #a8aec0;

  /* Borders */
  --color-border-subtle: rgba(255, 255, 255, 0.08);
  --color-border-secondary: rgba(124, 156, 255, 0.55);

  /* Feedback */
  --color-feedback-error: #ef6b6b;
  --color-feedback-success: #62c28b;
  --color-feedback-warning: #e0b355;

  /* Focus ring */
  --focus-ring-color: rgba(124, 156, 255, 0.35);

  /* Radii */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 10px;
  --radius-xl: 14px;

  /* Motion */
  --duration-fast: 120ms;
  --duration-base: 200ms;
}
```

- [ ] **Step 2: Extend tailwind.config.ts**

Replace `frontend/tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-app": "var(--color-bg-app)",
        "bg-base": "var(--color-bg-base)",
        "bg-elevated": "var(--color-bg-elevated)",
        "bg-input": "var(--color-bg-input)",
        "sidebar-bg": "var(--color-sidebar-bg)",
        "surface-hover": "var(--color-surface-hover)",
        "surface-active": "var(--color-surface-active)",
        "accent-primary": "var(--color-accent-primary)",
        "accent-hover": "var(--color-accent-hover)",
        "accent-subtle": "var(--color-accent-subtle)",
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-tertiary": "var(--color-text-tertiary)",
        "icon-primary": "var(--color-icon-primary)",
        "border-subtle": "var(--color-border-subtle)",
        "border-secondary": "var(--color-border-secondary)",
        "feedback-error": "var(--color-feedback-error)",
        "feedback-success": "var(--color-feedback-success)",
        "feedback-warning": "var(--color-feedback-warning)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      transitionDuration: {
        fast: "var(--duration-fast)",
        base: "var(--duration-base)",
      },
      ringColor: {
        focus: "var(--focus-ring-color)",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 3: Run existing tests**

```bash
cd frontend
npm run test -- --run
```

Expected: all Plan 8 tests still pass (no component references the new tokens yet).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/tailwind.config.ts
git commit -m "feat(frontend): extend design tokens for auth forms"
```

---

## Task 2: `passwordStrength` heuristic

**Files:**
- Create: `frontend/src/auth/passwordStrength.ts`
- Create: `frontend/src/auth/passwordStrength.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/auth/passwordStrength.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { passwordStrength } from "./passwordStrength";

describe("passwordStrength", () => {
  it("returns 0 for empty input", () => {
    expect(passwordStrength("")).toBe(0);
  });

  it("returns 1 for < 8 chars regardless of class mix", () => {
    expect(passwordStrength("aB1!")).toBe(1);
    expect(passwordStrength("abc")).toBe(1);
  });

  it("returns 2 for 8+ chars with 2 character classes", () => {
    expect(passwordStrength("abcdefgh")).toBe(2);       // 1 class → still 2 (length carries)
    expect(passwordStrength("abcdefgH")).toBe(2);       // 2 classes
    expect(passwordStrength("abcdefg1")).toBe(2);       // 2 classes
  });

  it("returns 3 for 8+ chars with 3 classes", () => {
    expect(passwordStrength("Abcdefg1")).toBe(3);
  });

  it("returns 4 for 8+ chars with 4 classes", () => {
    expect(passwordStrength("Abcdefg1!")).toBe(4);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/auth/passwordStrength.test.ts
```

Expected: FAIL (module missing).

- [ ] **Step 3: Implement passwordStrength.ts**

Create `frontend/src/auth/passwordStrength.ts`:

```ts
export type StrengthLevel = 0 | 1 | 2 | 3 | 4;

export function passwordStrength(pw: string): StrengthLevel {
  if (pw.length === 0) return 0;
  if (pw.length < 8) return 1;

  let classes = 0;
  if (/[a-z]/.test(pw)) classes += 1;
  if (/[A-Z]/.test(pw)) classes += 1;
  if (/[0-9]/.test(pw)) classes += 1;
  if (/[^a-zA-Z0-9]/.test(pw)) classes += 1;

  if (classes >= 4) return 4;
  if (classes === 3) return 3;
  return 2;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/auth/passwordStrength.test.ts
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/passwordStrength.ts frontend/src/auth/passwordStrength.test.ts
git commit -m "feat(frontend): add passwordStrength heuristic"
```

---

## Task 3: Extend `api/auth.ts` with the full auth surface

**Files:**
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/api/auth.test.ts`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/api/auth.test.ts` (before the closing `});` of the outer `describe`):

```ts
  it("login surfaces must_change_password flag", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user_id: "u1",
          email: "a",
          display_name: "A",
          is_admin: false,
          must_change_password: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const result = await login({ email: "a", password: "p", persistent: false });
    expect(result.user.id).toBe("u1");
    expect(result.must_change_password).toBe(true);
  });

  it("register posts invite + credentials", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user_id: "u2",
          email: "b",
          display_name: "B",
          is_admin: false,
          must_change_password: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    global.fetch = spy as unknown as typeof fetch;

    const result = await register({
      email: "b@x.com",
      password: "pw12345!",
      display_name: "B",
      invite_token: "tok_abc",
    });

    expect(result.user.email).toBe("b");
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/register");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      email: "b@x.com",
      password: "pw12345!",
      display_name: "B",
      invite_token: "tok_abc",
    });
  });

  it("getSignupPolicy returns mode + invite_required", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ mode: "invite_only", invite_required: true }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const policy = await getSignupPolicy();
    expect(policy.invite_required).toBe(true);
    expect(policy.mode).toBe("invite_only");
  });

  it("requestPasswordReset always resolves (neutral 200)", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    ) as unknown as typeof fetch;

    await expect(requestPasswordReset("a@x.com")).resolves.toBeNull();
  });

  it("consumePasswordReset posts token + new password", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await consumePasswordReset({ token: "t", new_password: "newpw123!" });

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/password-reset/consume");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      token: "t",
      new_password: "newpw123!",
    });
  });

  it("changePassword posts current + new password", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await changePassword({ current_password: "a", new_password: "b" });

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/change-password");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      current_password: "a",
      new_password: "b",
    });
  });

  it("logoutAll POSTs /logout-all", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await expect(logoutAll()).resolves.toBeNull();
    expect(spy.mock.calls[0][0]).toBe("/api/auth/logout-all");
  });
```

Also update the top-of-file import to pull in the new symbols:

```ts
import {
  getSession,
  login,
  logout,
  register,
  getSignupPolicy,
  requestPasswordReset,
  consumePasswordReset,
  changePassword,
  logoutAll,
} from "./auth";
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend
npm run test -- --run src/api/auth.test.ts
```

Expected: FAIL (missing exports).

- [ ] **Step 3: Extend auth.ts**

Replace `frontend/src/api/auth.ts`:

```ts
import { fetchJson } from "./client";

export interface AuthUser {
  id: string;
  email: string | null;
  display_name?: string | null;
  role: "admin" | "user";
}

interface SessionResponse {
  user_id: string;
  email: string | null;
  display_name?: string | null;
  is_admin: boolean;
  must_change_password?: boolean;
}

function mapAuthUser(resp: SessionResponse): AuthUser {
  return {
    id: resp.user_id,
    email: resp.email,
    display_name: resp.display_name,
    role: resp.is_admin ? "admin" : "user",
  };
}

export async function getSession(): Promise<AuthUser> {
  const resp = await fetchJson<SessionResponse>("/api/auth/session");
  return mapAuthUser(resp);
}

export interface LoginInput {
  email: string;
  password: string;
  persistent: boolean;
}

export interface LoginResult {
  user: AuthUser;
  must_change_password: boolean;
}

export async function login(input: LoginInput): Promise<LoginResult> {
  const resp = await fetchJson<SessionResponse>("/api/auth/login", {
    method: "POST",
    json: input,
  });
  return {
    user: mapAuthUser(resp),
    must_change_password: Boolean(resp.must_change_password),
  };
}

export async function logout(): Promise<null> {
  return fetchJson<null>("/api/auth/logout", { method: "POST" });
}

export async function logoutAll(): Promise<null> {
  return fetchJson<null>("/api/auth/logout-all", { method: "POST" });
}

export interface RegisterInput {
  email: string;
  password: string;
  display_name?: string;
  invite_token: string;
}

export async function register(input: RegisterInput): Promise<LoginResult> {
  const resp = await fetchJson<SessionResponse>("/api/auth/register", {
    method: "POST",
    json: input,
  });
  return {
    user: mapAuthUser(resp),
    must_change_password: Boolean(resp.must_change_password),
  };
}

export interface SignupPolicy {
  mode: "invite_only" | "closed" | "open";
  invite_required: boolean;
}

export async function getSignupPolicy(): Promise<SignupPolicy> {
  return fetchJson<SignupPolicy>("/api/auth/signup-policy");
}

export async function requestPasswordReset(email: string): Promise<null> {
  return fetchJson<null>("/api/auth/password-reset/request", {
    method: "POST",
    json: { email },
  });
}

export interface ConsumePasswordResetInput {
  token: string;
  new_password: string;
}

export async function consumePasswordReset(
  input: ConsumePasswordResetInput,
): Promise<null> {
  return fetchJson<null>("/api/auth/password-reset/consume", {
    method: "POST",
    json: input,
  });
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export async function changePassword(
  input: ChangePasswordInput,
): Promise<null> {
  return fetchJson<null>("/api/auth/change-password", {
    method: "POST",
    json: input,
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend
npm run test -- --run src/api/auth.test.ts
```

Expected: PASS (all Plan 8 cases + 7 new cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/api/auth.test.ts
git commit -m "feat(frontend): extend auth api with register/reset/change"
```

---

## Task 4: Extend `AuthContext` with `mustChangePassword`

**Files:**
- Modify: `frontend/src/auth/AuthContext.tsx`
- Modify: `frontend/src/auth/AuthContext.test.tsx`

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/auth/AuthContext.test.tsx`:

```tsx
  it("exposes mustChangePassword: false by default after session fetch", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        user_id: "u1",
        email: "a",
        display_name: "A",
        is_admin: true,
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(result.current.mustChangePassword).toBe(false);
  });

  it("login() sets mustChangePassword from server response", async () => {
    global.fetch = vi
      .fn()
      // initial /auth/session → 401 (unauthenticated)
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      // /auth/login → 200 with must_change_password: true
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            email: "a",
            display_name: "A",
            is_admin: false,
            must_change_password: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => expect(result.current.status).toBe("unauthenticated"));

    await act(async () => {
      await result.current.signIn({
        email: "a",
        password: "p",
        persistent: false,
      });
    });

    expect(result.current.status).toBe("authenticated");
    expect(result.current.mustChangePassword).toBe(true);
  });

  it("clearMustChangePassword() resets the flag", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            email: "a",
            display_name: "A",
            is_admin: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    act(() => {
      result.current.setMustChangePassword(true);
    });
    expect(result.current.mustChangePassword).toBe(true);

    act(() => {
      result.current.clearMustChangePassword();
    });
    expect(result.current.mustChangePassword).toBe(false);
  });
```

Also make sure the test file imports `renderHook` and `act` from `@testing-library/react`:

```tsx
import { renderHook } from "@testing-library/react";
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend
npm run test -- --run src/auth/AuthContext.test.tsx
```

Expected: FAIL (new fields / methods missing on context).

- [ ] **Step 3: Extend AuthContext.tsx**

Open `frontend/src/auth/AuthContext.tsx` and replace its contents with:

```tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError } from "../api/client";
import {
  getSession,
  login as apiLogin,
  logout as apiLogout,
  type AuthUser,
  type LoginInput,
} from "../api/auth";

export type AuthStatus =
  | "loading"
  | "authenticated"
  | "unauthenticated"
  | "personal";

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  mustChangePassword: boolean;
  signIn: (input: LoginInput) => Promise<void>;
  signOut: () => Promise<void>;
  setMustChangePassword: (v: boolean) => void;
  clearMustChangePassword: () => void;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const LOCAL_USER: AuthUser = {
  id: "local",
  email: null,
  role: "admin",
  display_name: "Local User",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mustChangePassword, setMustChangePasswordState] =
    useState<boolean>(false);

  const loadSession = useCallback(async () => {
    try {
      const u = await getSession();
      setUser(u);
      setStatus("authenticated");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setUser(LOCAL_USER);
          setStatus("personal");
          return;
        }
        if (err.status === 401) {
          setUser(null);
          setStatus("unauthenticated");
          return;
        }
      }
      console.error("session load failed", err);
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const signIn = useCallback(async (input: LoginInput) => {
    const result = await apiLogin(input);
    setUser(result.user);
    setMustChangePasswordState(result.must_change_password);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } catch (err) {
      // ignore — still clear local state
      console.warn("logout failed", err);
    }
    setUser(null);
    setMustChangePasswordState(false);
    setStatus("unauthenticated");
  }, []);

  const setMustChangePassword = useCallback((v: boolean) => {
    setMustChangePasswordState(v);
  }, []);

  const clearMustChangePassword = useCallback(() => {
    setMustChangePasswordState(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      mustChangePassword,
      signIn,
      signOut,
      setMustChangePassword,
      clearMustChangePassword,
      refreshSession: loadSession,
    }),
    [
      status,
      user,
      mustChangePassword,
      signIn,
      signOut,
      setMustChangePassword,
      clearMustChangePassword,
      loadSession,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
```

NOTE: If Plan 8 already shipped a version of `AuthContext.tsx` with different method names (`login()` vs `signIn()`), preserve the Plan 8 names and add the mustChangePassword pieces without renaming. The tests above assume `signIn` — adjust to match Plan 8's actual name before running.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend
npm run test -- --run src/auth/AuthContext.test.tsx
```

Expected: PASS (Plan 8 cases + 3 new cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx frontend/src/auth/AuthContext.test.tsx
git commit -m "feat(frontend): track mustChangePassword in AuthContext"
```

---

## Task 5: `Banner` primitive

**Files:**
- Create: `frontend/src/components/primitives/Banner.tsx`
- Create: `frontend/src/components/primitives/Banner.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/primitives/Banner.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Banner } from "./Banner";

describe("Banner", () => {
  it("renders message with error variant by default", () => {
    render(<Banner message="Bad password" />);
    const el = screen.getByRole("alert");
    expect(el.textContent).toContain("Bad password");
    expect(el.className).toMatch(/feedback-error/);
  });

  it("renders success variant with CheckCircle icon", () => {
    render(<Banner message="Saved" variant="success" />);
    const el = screen.getByRole("status");
    expect(el.className).toMatch(/feedback-success/);
  });

  it("renders warning variant", () => {
    render(<Banner message="Slow down" variant="warning" />);
    const el = screen.getByRole("alert");
    expect(el.className).toMatch(/feedback-warning/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/primitives/Banner.test.tsx
```

Expected: FAIL (missing file).

- [ ] **Step 3: Implement Banner.tsx**

Create `frontend/src/components/primitives/Banner.tsx`:

```tsx
import { AlertCircle, AlertTriangle, CheckCircle } from "lucide-react";
import type { ReactNode } from "react";

export type BannerVariant = "error" | "success" | "warning";

export interface BannerProps {
  message: ReactNode;
  variant?: BannerVariant;
}

const VARIANT_CLASS: Record<BannerVariant, string> = {
  error:
    "bg-feedback-error/10 text-feedback-error border border-feedback-error/20",
  success:
    "bg-feedback-success/10 text-feedback-success border border-feedback-success/20",
  warning:
    "bg-feedback-warning/10 text-feedback-warning border border-feedback-warning/20",
};

const VARIANT_ICON: Record<BannerVariant, typeof AlertCircle> = {
  error: AlertCircle,
  success: CheckCircle,
  warning: AlertTriangle,
};

export function Banner({ message, variant = "error" }: BannerProps) {
  const Icon = VARIANT_ICON[variant];
  const role = variant === "success" ? "status" : "alert";
  return (
    <div
      role={role}
      className={`rounded-md px-4 py-3 text-sm mb-5 flex items-start gap-2 ${VARIANT_CLASS[variant]}`}
    >
      <Icon size={14} className="mt-0.5 flex-shrink-0" />
      <span>{message}</span>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/primitives/Banner.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/primitives/Banner.tsx \
        frontend/src/components/primitives/Banner.test.tsx
git commit -m "feat(frontend): add Banner primitive"
```

---

## Task 6: `FormField` primitive

**Files:**
- Create: `frontend/src/components/primitives/FormField.tsx`
- Create: `frontend/src/components/primitives/FormField.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/primitives/FormField.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FormField } from "./FormField";

describe("FormField", () => {
  it("renders label + input bound via id", () => {
    render(
      <FormField id="email" label="Email">
        <input id="email" />
      </FormField>,
    );
    const label = screen.getByText("Email");
    expect(label.getAttribute("for")).toBe("email");
    expect(screen.getByLabelText("Email")).toBeTruthy();
  });

  it("renders helper text when provided", () => {
    render(
      <FormField id="pw" label="Password" helper="At least 8 chars">
        <input id="pw" />
      </FormField>,
    );
    expect(screen.getByText("At least 8 chars")).toBeTruthy();
  });

  it("renders inline error with aria-describedby wiring", () => {
    render(
      <FormField id="e" label="Email" error="Required">
        <input id="e" />
      </FormField>,
    );
    const err = screen.getByText("Required");
    expect(err.id).toBe("e-error");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/primitives/FormField.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement FormField.tsx**

Create `frontend/src/components/primitives/FormField.tsx`:

```tsx
import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

export interface FormFieldProps {
  id: string;
  label: string;
  helper?: string;
  error?: string;
  children: ReactNode;
}

export function FormField({
  id,
  label,
  helper,
  error,
  children,
}: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1.5 mb-4">
      <label
        htmlFor={id}
        className="text-sm font-medium text-text-primary"
      >
        {label}
      </label>
      {children}
      {helper && !error && (
        <span className="text-xs text-text-secondary">{helper}</span>
      )}
      {error && (
        <span
          id={`${id}-error`}
          className="text-xs text-feedback-error flex items-center gap-1"
        >
          <AlertCircle size={12} />
          {error}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/primitives/FormField.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/primitives/FormField.tsx \
        frontend/src/components/primitives/FormField.test.tsx
git commit -m "feat(frontend): add FormField primitive"
```

---

## Task 7: `PasswordInput` primitive

**Files:**
- Create: `frontend/src/components/primitives/PasswordInput.tsx`
- Create: `frontend/src/components/primitives/PasswordInput.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/primitives/PasswordInput.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PasswordInput } from "./PasswordInput";

describe("PasswordInput", () => {
  it("renders masked by default", () => {
    render(
      <PasswordInput id="pw" value="hunter2" onChange={() => undefined} />,
    );
    const input = screen.getByTestId("password-input") as HTMLInputElement;
    expect(input.type).toBe("password");
  });

  it("toggles to text when show/hide pressed", () => {
    render(
      <PasswordInput id="pw" value="hunter2" onChange={() => undefined} />,
    );
    const toggle = screen.getByRole("button", { name: /show password/i });
    fireEvent.click(toggle);
    const input = screen.getByTestId("password-input") as HTMLInputElement;
    expect(input.type).toBe("text");
    const toggleAgain = screen.getByRole("button", { name: /hide password/i });
    fireEvent.click(toggleAgain);
    expect((screen.getByTestId("password-input") as HTMLInputElement).type).toBe(
      "password",
    );
  });

  it("forwards onChange with the new string value", () => {
    const handle = vi.fn();
    render(<PasswordInput id="pw" value="" onChange={handle} />);
    const input = screen.getByTestId("password-input");
    fireEvent.change(input, { target: { value: "abc" } });
    expect(handle).toHaveBeenCalledWith("abc");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/primitives/PasswordInput.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement PasswordInput.tsx**

Create `frontend/src/components/primitives/PasswordInput.tsx`:

```tsx
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

export interface PasswordInputProps {
  id: string;
  value: string;
  onChange: (next: string) => void;
  autoComplete?: string;
  placeholder?: string;
  hasError?: boolean;
  disabled?: boolean;
}

export function PasswordInput({
  id,
  value,
  onChange,
  autoComplete = "current-password",
  placeholder,
  hasError = false,
  disabled = false,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const borderClass = hasError
    ? "border-feedback-error ring-2 ring-feedback-error/20"
    : "border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus";

  return (
    <div className="relative">
      <input
        id={id}
        data-testid="password-input"
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        disabled={disabled}
        className={`w-full h-10 rounded-md bg-bg-input px-3 pr-10 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors duration-fast border ${borderClass}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute right-3 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center rounded-sm text-text-secondary hover:text-text-primary"
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/primitives/PasswordInput.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/primitives/PasswordInput.tsx \
        frontend/src/components/primitives/PasswordInput.test.tsx
git commit -m "feat(frontend): add PasswordInput primitive"
```

---

## Task 8: `PasswordStrengthMeter`

**Files:**
- Create: `frontend/src/components/primitives/PasswordStrengthMeter.tsx`
- Create: `frontend/src/components/primitives/PasswordStrengthMeter.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/primitives/PasswordStrengthMeter.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PasswordStrengthMeter } from "./PasswordStrengthMeter";

describe("PasswordStrengthMeter", () => {
  it("renders nothing when value is empty", () => {
    const { container } = render(<PasswordStrengthMeter value="" />);
    expect(container.firstChild).toBeNull();
  });

  it("labels 'Weak' when length < 8", () => {
    render(<PasswordStrengthMeter value="abc" />);
    expect(screen.getByText("Weak")).toBeTruthy();
  });

  it("labels 'Fair' at 2 classes", () => {
    render(<PasswordStrengthMeter value="abcdefgH" />);
    expect(screen.getByText("Fair")).toBeTruthy();
  });

  it("labels 'Good' at 3 classes", () => {
    render(<PasswordStrengthMeter value="Abcdefg1" />);
    expect(screen.getByText("Good")).toBeTruthy();
  });

  it("labels 'Strong' at 4 classes", () => {
    render(<PasswordStrengthMeter value="Abcdefg1!" />);
    expect(screen.getByText("Strong")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/primitives/PasswordStrengthMeter.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement PasswordStrengthMeter.tsx**

Create `frontend/src/components/primitives/PasswordStrengthMeter.tsx`:

```tsx
import { passwordStrength, type StrengthLevel } from "../../auth/passwordStrength";

export interface PasswordStrengthMeterProps {
  value: string;
}

const LABELS: Record<StrengthLevel, string> = {
  0: "",
  1: "Weak",
  2: "Fair",
  3: "Good",
  4: "Strong",
};

const BAR_COLOR: Record<StrengthLevel, string> = {
  0: "bg-border-subtle",
  1: "bg-feedback-error",
  2: "bg-feedback-warning",
  3: "bg-feedback-warning",
  4: "bg-feedback-success",
};

const LABEL_COLOR: Record<StrengthLevel, string> = {
  0: "text-text-tertiary",
  1: "text-feedback-error",
  2: "text-feedback-warning",
  3: "text-feedback-warning",
  4: "text-feedback-success",
};

export function PasswordStrengthMeter({ value }: PasswordStrengthMeterProps) {
  if (value.length === 0) return null;
  const level = passwordStrength(value);
  return (
    <div className="flex flex-col gap-1 mt-1.5">
      <div className="flex justify-between items-center">
        <div className="flex gap-1 flex-1">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full ${
                i <= level ? BAR_COLOR[level] : "bg-border-subtle"
              }`}
            />
          ))}
        </div>
        <span className={`text-xs ml-2 ${LABEL_COLOR[level]}`}>
          {LABELS[level]}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/primitives/PasswordStrengthMeter.test.tsx
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/primitives/PasswordStrengthMeter.tsx \
        frontend/src/components/primitives/PasswordStrengthMeter.test.tsx
git commit -m "feat(frontend): add PasswordStrengthMeter"
```

---

## Task 9: `AuthLayout` + `AuthCard`

**Files:**
- Create: `frontend/src/components/auth/AuthLayout.tsx`
- Create: `frontend/src/components/auth/AuthCard.tsx`

These are small enough that one test each is fine and we'll batch them.

- [ ] **Step 1: Implement AuthLayout.tsx**

Create `frontend/src/components/auth/AuthLayout.tsx`:

```tsx
import type { ReactNode } from "react";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main
      aria-label="Authentication"
      className="min-h-screen bg-bg-base flex flex-col items-center justify-center p-4"
    >
      <div className="mb-6 flex flex-col items-center">
        <span className="text-2xl font-semibold text-text-primary">LIA</span>
        <span className="text-sm text-text-secondary mt-1">
          Your financial assistant
        </span>
      </div>
      {children}
    </main>
  );
}
```

- [ ] **Step 2: Implement AuthCard.tsx**

Create `frontend/src/components/auth/AuthCard.tsx`:

```tsx
import type { ReactNode } from "react";

export function AuthCard({ children }: { children: ReactNode }) {
  return (
    <section className="bg-bg-elevated border border-border-subtle rounded-xl shadow-lg w-full max-w-[420px] px-8 py-10 md:border md:shadow-lg md:rounded-xl max-md:border-0 max-md:shadow-none max-md:rounded-none max-md:px-6 max-md:py-8">
      {children}
    </section>
  );
}
```

- [ ] **Step 3: Smoke test both**

Create `frontend/src/components/auth/AuthLayout.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthLayout } from "./AuthLayout";
import { AuthCard } from "./AuthCard";

describe("AuthLayout + AuthCard", () => {
  it("renders wordmark + card children inside <main>", () => {
    render(
      <AuthLayout>
        <AuthCard>
          <div>FormContent</div>
        </AuthCard>
      </AuthLayout>,
    );
    expect(screen.getByRole("main").getAttribute("aria-label")).toBe(
      "Authentication",
    );
    expect(screen.getByText("LIA")).toBeTruthy();
    expect(screen.getByText("FormContent")).toBeTruthy();
  });
});
```

- [ ] **Step 4: Run test**

```bash
cd frontend
npm run test -- --run src/components/auth/AuthLayout.test.tsx
```

Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/AuthLayout.tsx \
        frontend/src/components/auth/AuthCard.tsx \
        frontend/src/components/auth/AuthLayout.test.tsx
git commit -m "feat(frontend): add AuthLayout + AuthCard shell"
```

---

## Task 10: `LoginForm`

**Files:**
- Create: `frontend/src/components/auth/LoginForm.tsx`
- Create: `frontend/src/components/auth/LoginForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/auth/LoginForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LoginForm } from "./LoginForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderInProvider(inviteToken?: string) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginForm inviteToken={inviteToken} />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LoginForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("disables submit until email + password non-empty", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 }));
    global.fetch = global.fetch as unknown as typeof fetch;
    renderInProvider();
    const button = screen.getByRole("button", { name: /log in/i });
    expect((button as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows inline email error for bad format", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderInProvider();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "notemail" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() =>
      expect(screen.getByText(/enter a valid email/i)).toBeTruthy(),
    );
  });

  it("shows the sign-up link only when inviteToken is present", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    const { rerender } = renderInProvider();
    expect(screen.queryByText(/sign up/i)).toBeNull();
    rerender(
      <MemoryRouter>
        <AuthProvider>
          <LoginForm inviteToken="abc" />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByText(/sign up/i)).toBeTruthy();
  });

  it("renders lockout banner from account_locked code", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // initial session probe
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "account_locked",
            message: "Too many failed attempts.",
            metadata: { retry_after_seconds: 900 },
          }),
          { status: 423, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    renderInProvider();

    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: /log in/i }) as HTMLButtonElement)
          .disabled,
      ).toBe(true),
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "pw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/Too many/),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/auth/LoginForm.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement LoginForm.tsx**

Create `frontend/src/components/auth/LoginForm.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";
import { PasswordInput } from "../primitives/PasswordInput";

export interface LoginFormProps {
  inviteToken?: string;
}

interface FormState {
  email: string;
  password: string;
  persistent: boolean;
}

const INITIAL_STATE: FormState = {
  email: "",
  password: "",
  persistent: false,
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
  metadata?: Record<string, unknown>;
}

export function LoginForm({ inviteToken }: LoginFormProps) {
  const { signIn } = useAuth();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const canSubmit =
    form.email.trim().length > 0 &&
    form.password.length > 0 &&
    !submitting;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    if (!EMAIL_RE.test(form.email)) {
      setFieldErrors({ email: "Enter a valid email address." });
      return;
    }

    setSubmitting(true);
    try {
      await signIn({
        email: form.email.trim(),
        password: form.password,
        persistent: form.persistent,
      });
      const next = searchParams.get("next") ?? "/";
      navigate(next, { replace: true });
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  function handleError(err: unknown) {
    if (!(err instanceof ApiError)) {
      setBanner({
        message: "Unexpected error. Please try again.",
        variant: "error",
      });
      return;
    }
    const body = (err.body as ServerError | null) ?? {};
    if (body.code === "account_locked") {
      setBanner({
        message: body.message ?? "Account is temporarily locked.",
        variant: "warning",
      });
      return;
    }
    if (body.code === "rate_limited") {
      setBanner({
        message: body.message ?? "Too many attempts. Please wait.",
        variant: "warning",
      });
      return;
    }
    if (body.field) {
      setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
      return;
    }
    setBanner({
      message: body.message ?? "Email or password is incorrect.",
      variant: "error",
    });
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField id="email" label="Email" error={fieldErrors.email}>
        <input
          id="email"
          type="email"
          autoComplete="username"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          disabled={submitting}
          className={`w-full h-10 rounded-md border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors duration-fast ${
            fieldErrors.email
              ? "border-feedback-error ring-2 ring-feedback-error/20"
              : "border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus"
          }`}
        />
      </FormField>

      <FormField id="password" label="Password" error={fieldErrors.password}>
        <PasswordInput
          id="password"
          value={form.password}
          onChange={(v) => update("password", v)}
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.password)}
          disabled={submitting}
        />
      </FormField>

      <div className="flex items-center gap-2 mb-5">
        <input
          type="checkbox"
          id="persistent"
          checked={form.persistent}
          onChange={(e) => update("persistent", e.target.checked)}
          className="accent-accent-primary w-4 h-4 rounded-sm cursor-pointer"
          disabled={submitting}
        />
        <label
          htmlFor="persistent"
          className="text-sm text-text-secondary cursor-pointer"
        >
          Keep me logged in
        </label>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Log In"
        )}
      </button>

      <div className="flex items-center justify-between mt-4">
        <Link
          to="/forgot-password"
          className="text-sm text-accent-primary hover:text-accent-hover"
        >
          Forgot password?
        </Link>
      </div>

      {inviteToken && (
        <p className="mt-6 text-sm text-text-secondary text-center">
          Don&apos;t have an account?{" "}
          <Link
            to={`/register?invite=${encodeURIComponent(inviteToken)}`}
            className="text-accent-primary hover:text-accent-hover"
          >
            Sign up
          </Link>
        </p>
      )}
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/auth/LoginForm.test.tsx
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/LoginForm.tsx \
        frontend/src/components/auth/LoginForm.test.tsx
git commit -m "feat(frontend): add LoginForm"
```

---

## Task 11: `RegisterForm`

**Files:**
- Create: `frontend/src/components/auth/RegisterForm.tsx`
- Create: `frontend/src/components/auth/RegisterForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/auth/RegisterForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RegisterForm } from "./RegisterForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderForm(inviteToken = "tok_xyz") {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <RegisterForm inviteToken={inviteToken} />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("RegisterForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("rejects mismatched passwords before submitting", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderForm();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg2" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
  });

  it("surfaces invite_invalid as banner", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: "invite_invalid",
            message: "This invite link is no longer valid. Contact your administrator for a new one.",
          }),
          { status: 403, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    renderForm();

    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: /create account/i }) as HTMLButtonElement)
          .disabled,
      ).toBe(false),
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "b@x.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/no longer valid/),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/auth/RegisterForm.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement RegisterForm.tsx**

Create `frontend/src/components/auth/RegisterForm.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";
import { PasswordInput } from "../primitives/PasswordInput";
import { PasswordStrengthMeter } from "../primitives/PasswordStrengthMeter";

export interface RegisterFormProps {
  inviteToken: string;
}

interface FormState {
  email: string;
  password: string;
  confirm: string;
  display_name: string;
}

const INITIAL_STATE: FormState = {
  email: "",
  password: "",
  confirm: "",
  display_name: "",
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PASSWORD_MIN = 8;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
}

export function RegisterForm({ inviteToken }: RegisterFormProps) {
  const { refreshSession, setMustChangePassword } = useAuth();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const canSubmit =
    form.email.trim().length > 0 &&
    form.password.length > 0 &&
    form.confirm.length > 0 &&
    !submitting;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (!EMAIL_RE.test(form.email)) {
      errs.email = "Enter a valid email address.";
    }
    if (form.password.length < PASSWORD_MIN) {
      errs.password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (form.password !== form.confirm) {
      errs.confirm = "Passwords do not match.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      const result = await register({
        email: form.email.trim(),
        password: form.password,
        display_name: form.display_name.trim() || undefined,
        invite_token: inviteToken,
      });
      setMustChangePassword(result.must_change_password);
      await refreshSession();
      navigate("/", { replace: true });
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  function handleError(err: unknown) {
    if (!(err instanceof ApiError)) {
      setBanner({
        message: "Unexpected error. Please try again.",
        variant: "error",
      });
      return;
    }
    const body = (err.body as ServerError | null) ?? {};
    if (
      body.code === "invite_invalid" ||
      body.code === "invite_required" ||
      body.code === "signup_closed"
    ) {
      setBanner({
        message:
          body.message ??
          "This invite link is no longer valid. Contact your administrator for a new one.",
        variant: "error",
      });
      return;
    }
    if (body.field) {
      setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
      return;
    }
    setBanner({
      message: body.message ?? "Registration failed. Please try again.",
      variant: "error",
    });
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField id="email" label="Email" error={fieldErrors.email}>
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          disabled={submitting}
          className={`w-full h-10 rounded-md border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors duration-fast ${
            fieldErrors.email
              ? "border-feedback-error ring-2 ring-feedback-error/20"
              : "border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus"
          }`}
        />
      </FormField>

      <FormField id="password" label="Password" error={fieldErrors.password}>
        <PasswordInput
          id="password"
          value={form.password}
          onChange={(v) => update("password", v)}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.password)}
          disabled={submitting}
        />
        <PasswordStrengthMeter value={form.password} />
      </FormField>

      <FormField
        id="confirm"
        label="Confirm Password"
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="confirm"
          value={form.confirm}
          onChange={(v) => update("confirm", v)}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
        />
      </FormField>

      <FormField id="display_name" label="Display Name (optional)">
        <input
          id="display_name"
          type="text"
          autoComplete="name"
          value={form.display_name}
          onChange={(e) => update("display_name", e.target.value)}
          disabled={submitting}
          className="w-full h-10 rounded-md border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors duration-fast border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus"
        />
      </FormField>

      <button
        type="submit"
        disabled={!canSubmit}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Create Account"
        )}
      </button>

      <p className="mt-6 text-sm text-text-secondary text-center">
        Already have an account?{" "}
        <Link to="/login" className="text-accent-primary hover:text-accent-hover">
          Log in
        </Link>
      </p>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/auth/RegisterForm.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/RegisterForm.tsx \
        frontend/src/components/auth/RegisterForm.test.tsx
git commit -m "feat(frontend): add RegisterForm"
```

---

## Task 12: `ForgotPasswordForm`

**Files:**
- Create: `frontend/src/components/auth/ForgotPasswordForm.tsx`
- Create: `frontend/src/components/auth/ForgotPasswordForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/auth/ForgotPasswordForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ForgotPasswordForm } from "./ForgotPasswordForm";

describe("ForgotPasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("always shows neutral confirmation after submit", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    render(
      <MemoryRouter>
        <ForgotPasswordForm />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "a@x.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /request reset/i }));

    await waitFor(() =>
      expect(
        screen.getByRole("status").textContent,
      ).toMatch(/your admin has been notified/i),
    );

    expect(spy.mock.calls[0][0]).toBe("/api/auth/password-reset/request");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/auth/ForgotPasswordForm.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement ForgotPasswordForm.tsx**

Create `frontend/src/components/auth/ForgotPasswordForm.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset } from "../../api/auth";
import { Banner } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NEUTRAL_MESSAGE =
  "If the email matches an account, your admin has been notified. They'll send you a reset link.";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setEmailError(null);
    if (!EMAIL_RE.test(email)) {
      setEmailError("Enter a valid email address.");
      return;
    }
    setSubmitting(true);
    try {
      await requestPasswordReset(email.trim());
    } catch {
      // Anti-enumeration: even on unexpected errors, show neutral message.
    } finally {
      setSubmitting(false);
      setDone(true);
    }
  }

  if (done) {
    return (
      <div>
        <Banner variant="success" message={NEUTRAL_MESSAGE} />
        <p className="mt-6 text-sm text-text-secondary text-center">
          <Link to="/login" className="text-accent-primary hover:text-accent-hover">
            Back to Log In
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <p className="text-sm text-text-secondary mb-5">
        Enter your email and we&apos;ll notify your admin to approve a password
        reset.
      </p>

      <FormField id="email" label="Email" error={emailError ?? undefined}>
        <input
          id="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
          className={`w-full h-10 rounded-md border bg-bg-input px-3 text-sm text-text-primary outline-none transition-colors duration-fast ${
            emailError
              ? "border-feedback-error ring-2 ring-feedback-error/20"
              : "border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus"
          }`}
        />
      </FormField>

      <button
        type="submit"
        disabled={submitting || email.trim().length === 0}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Request Reset"
        )}
      </button>

      <p className="mt-6 text-sm text-text-secondary text-center">
        <Link to="/login" className="text-accent-primary hover:text-accent-hover">
          Back to Log In
        </Link>
      </p>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/auth/ForgotPasswordForm.test.tsx
```

Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/ForgotPasswordForm.tsx \
        frontend/src/components/auth/ForgotPasswordForm.test.tsx
git commit -m "feat(frontend): add ForgotPasswordForm"
```

---

## Task 13: `ResetPasswordForm`

**Files:**
- Create: `frontend/src/components/auth/ResetPasswordForm.tsx`
- Create: `frontend/src/components/auth/ResetPasswordForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/auth/ResetPasswordForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ResetPasswordForm } from "./ResetPasswordForm";

function renderForm(token = "t-1") {
  return render(
    <MemoryRouter>
      <ResetPasswordForm token={token} />
    </MemoryRouter>,
  );
}

describe("ResetPasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows confirm-mismatch error before submit", async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Different1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
  });

  it("shows success banner on 204 and renders back link", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toMatch(/password updated/i),
    );
  });

  it("surfaces token_invalid as error banner with no form", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "token_invalid",
          message:
            "This reset link has expired or has already been used. Contact your administrator for a new one.",
        }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/expired or has already been used/i),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/auth/ResetPasswordForm.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement ResetPasswordForm.tsx**

Create `frontend/src/components/auth/ResetPasswordForm.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { consumePasswordReset } from "../../api/auth";
import { ApiError } from "../../api/client";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";
import { PasswordInput } from "../primitives/PasswordInput";
import { PasswordStrengthMeter } from "../primitives/PasswordStrengthMeter";

const PASSWORD_MIN = 8;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
}

export interface ResetPasswordFormProps {
  token: string;
}

export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (newPw !== confirm) {
      errs.confirm = "Passwords do not match.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await consumePasswordReset({ token, new_password: newPw });
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError) {
        const body = (err.body as ServerError | null) ?? {};
        if (body.code === "token_invalid" || body.code === "token_expired") {
          setBanner({
            message:
              body.message ??
              "This reset link has expired or has already been used. Contact your administrator for a new one.",
            variant: "error",
          });
        } else if (body.field) {
          setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
        } else {
          setBanner({
            message: body.message ?? "Reset failed. Please try again.",
            variant: "error",
          });
        }
      } else {
        setBanner({
          message: "Unexpected error. Please try again.",
          variant: "error",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div>
        <Banner
          variant="success"
          message="Password updated successfully. You can now log in."
        />
        <p className="mt-6 text-sm text-text-secondary text-center">
          <Link
            to="/login"
            className="text-accent-primary hover:text-accent-hover"
          >
            Back to Log In
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="new_password"
        label="New Password"
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="confirm"
        label="Confirm New Password"
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="confirm"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
        />
      </FormField>

      <button
        type="submit"
        disabled={submitting || newPw.length === 0 || confirm.length === 0}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Reset Password"
        )}
      </button>

      <p className="mt-6 text-sm text-text-secondary text-center">
        <Link to="/login" className="text-accent-primary hover:text-accent-hover">
          Back to Log In
        </Link>
      </p>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/auth/ResetPasswordForm.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/ResetPasswordForm.tsx \
        frontend/src/components/auth/ResetPasswordForm.test.tsx
git commit -m "feat(frontend): add ResetPasswordForm"
```

---

## Task 14: `MustChangePasswordForm`

**Files:**
- Create: `frontend/src/components/auth/MustChangePasswordForm.tsx`
- Create: `frontend/src/components/auth/MustChangePasswordForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/auth/MustChangePasswordForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MustChangePasswordForm } from "./MustChangePasswordForm";
import { AuthProvider } from "../../auth/AuthContext";

function renderForm() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <MustChangePasswordForm />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("MustChangePasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("requires confirm to match", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Different1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /set password/i }));
    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
  });

  it("on success clears mustChangePassword flag", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // session probe
      .mockResolvedValueOnce(new Response(null, { status: 204 })) // change-password
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            email: "a",
            display_name: "A",
            is_admin: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;

    renderForm();
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /set password/i }));
    await waitFor(() =>
      expect(
        (global.fetch as unknown as { mock: { calls: unknown[] } }).mock.calls
          .length,
      ).toBeGreaterThanOrEqual(2),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/components/auth/MustChangePasswordForm.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement MustChangePasswordForm.tsx**

Create `frontend/src/components/auth/MustChangePasswordForm.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { changePassword } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";
import { PasswordInput } from "../primitives/PasswordInput";
import { PasswordStrengthMeter } from "../primitives/PasswordStrengthMeter";

const PASSWORD_MIN = 8;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
}

export function MustChangePasswordForm() {
  const { clearMustChangePassword, refreshSession } = useAuth();
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (current.length === 0) {
      errs.current_password = "Enter your current (temporary) password.";
    }
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (newPw !== confirm) {
      errs.confirm = "Passwords do not match.";
    }
    if (newPw === current && newPw.length > 0) {
      errs.new_password = "New password must differ from the temporary one.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ current_password: current, new_password: newPw });
      clearMustChangePassword();
      await refreshSession();
    } catch (err) {
      if (err instanceof ApiError) {
        const body = (err.body as ServerError | null) ?? {};
        if (body.field) {
          setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
        } else {
          setBanner({
            message: body.message ?? "Password change failed.",
            variant: "error",
          });
        }
      } else {
        setBanner({
          message: "Unexpected error. Please try again.",
          variant: "error",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <p className="text-sm text-text-secondary mb-5">
        Your administrator has reset your password. Please set a new one to
        continue.
      </p>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="current_password"
        label="Temporary Password"
        error={fieldErrors.current_password}
      >
        <PasswordInput
          id="current_password"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.current_password)}
          disabled={submitting}
        />
      </FormField>

      <FormField
        id="new_password"
        label="New Password"
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="confirm"
        label="Confirm New Password"
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="confirm"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
        />
      </FormField>

      <button
        type="submit"
        disabled={submitting}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Set Password"
        )}
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/components/auth/MustChangePasswordForm.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/MustChangePasswordForm.tsx \
        frontend/src/components/auth/MustChangePasswordForm.test.tsx
git commit -m "feat(frontend): add MustChangePasswordForm"
```

---

## Task 15: Page components (`LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`)

These pages compose `AuthLayout` + `AuthCard` + a form. Each is small.

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/LoginPage.test.tsx`
- Create: `frontend/src/pages/RegisterPage.tsx`
- Create: `frontend/src/pages/RegisterPage.test.tsx`
- Create: `frontend/src/pages/ForgotPasswordPage.tsx`
- Create: `frontend/src/pages/ForgotPasswordPage.test.tsx`
- Create: `frontend/src/pages/ResetPasswordPage.tsx`
- Create: `frontend/src/pages/ResetPasswordPage.test.tsx`
- Delete: `frontend/src/pages/Login.tsx` (placeholder from Plan 8)

- [ ] **Step 1: Implement LoginPage.tsx**

Create `frontend/src/pages/LoginPage.tsx`:

```tsx
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { LoginForm } from "../components/auth/LoginForm";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { status } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const invite = searchParams.get("invite") ?? undefined;

  useEffect(() => {
    if (status === "authenticated" || status === "personal") {
      const next = searchParams.get("next") ?? "/";
      navigate(next, { replace: true });
    }
  }, [status, searchParams, navigate]);

  return (
    <AuthLayout>
      <AuthCard>
        <LoginForm inviteToken={invite} />
      </AuthCard>
    </AuthLayout>
  );
}
```

- [ ] **Step 2: Implement RegisterPage.tsx**

Create `frontend/src/pages/RegisterPage.tsx`:

```tsx
import { useSearchParams, Navigate } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { RegisterForm } from "../components/auth/RegisterForm";
import { Banner } from "../components/primitives/Banner";

export function RegisterPage() {
  const [searchParams] = useSearchParams();
  const invite = searchParams.get("invite");

  if (!invite) {
    return <Navigate to="/login" replace />;
  }

  return (
    <AuthLayout>
      <AuthCard>
        {invite.length < 8 ? (
          <Banner
            variant="error"
            message="This invite link is no longer valid. Contact your administrator for a new one."
          />
        ) : (
          <RegisterForm inviteToken={invite} />
        )}
      </AuthCard>
    </AuthLayout>
  );
}
```

- [ ] **Step 3: Implement ForgotPasswordPage.tsx**

Create `frontend/src/pages/ForgotPasswordPage.tsx`:

```tsx
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { ForgotPasswordForm } from "../components/auth/ForgotPasswordForm";

export function ForgotPasswordPage() {
  return (
    <AuthLayout>
      <AuthCard>
        <ForgotPasswordForm />
      </AuthCard>
    </AuthLayout>
  );
}
```

- [ ] **Step 4: Implement ResetPasswordPage.tsx**

Create `frontend/src/pages/ResetPasswordPage.tsx`:

```tsx
import { useSearchParams } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { ResetPasswordForm } from "../components/auth/ResetPasswordForm";
import { Banner } from "../components/primitives/Banner";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  return (
    <AuthLayout>
      <AuthCard>
        {token ? (
          <ResetPasswordForm token={token} />
        ) : (
          <Banner
            variant="error"
            message="This reset link is invalid. Contact your administrator for a new one."
          />
        )}
      </AuthCard>
    </AuthLayout>
  );
}
```

- [ ] **Step 5: Write a smoke test per page**

Create `frontend/src/pages/LoginPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { AuthProvider } from "../auth/AuthContext";

describe("LoginPage", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders LoginForm under AuthLayout when unauthenticated", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;

    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("LIA")).toBeTruthy());
    expect(screen.getByRole("button", { name: /log in/i })).toBeTruthy();
  });
});
```

Create `frontend/src/pages/RegisterPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RegisterPage } from "./RegisterPage";
import { AuthProvider } from "../auth/AuthContext";

describe("RegisterPage", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("redirects when no invite param", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/register"]}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    // RegisterForm is not rendered — its label "Confirm Password" is absent.
    expect(screen.queryByLabelText("Confirm Password")).toBeNull();
  });

  it("renders RegisterForm with invite param", () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/register?invite=tok_abcdefgh"]}>
        <AuthProvider>
          <RegisterPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("Confirm Password")).toBeTruthy();
  });
});
```

Create `frontend/src/pages/ForgotPasswordPage.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ForgotPasswordPage } from "./ForgotPasswordPage";

describe("ForgotPasswordPage", () => {
  it("renders the forgot form inside the auth layout", () => {
    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: /request reset/i })).toBeTruthy();
  });
});
```

Create `frontend/src/pages/ResetPasswordPage.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ResetPasswordPage } from "./ResetPasswordPage";

describe("ResetPasswordPage", () => {
  it("shows error banner when token missing", () => {
    render(
      <MemoryRouter initialEntries={["/reset-password"]}>
        <ResetPasswordPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert").textContent).toMatch(/invalid/i);
  });

  it("renders the reset form when token present", () => {
    render(
      <MemoryRouter initialEntries={["/reset-password?token=abc"]}>
        <ResetPasswordPage />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("New Password")).toBeTruthy();
  });
});
```

- [ ] **Step 6: Delete Plan 8's Login placeholder**

```bash
rm frontend/src/pages/Login.tsx
```

- [ ] **Step 7: Run the page tests**

```bash
cd frontend
npm run test -- --run src/pages/LoginPage.test.tsx \
                       src/pages/RegisterPage.test.tsx \
                       src/pages/ForgotPasswordPage.test.tsx \
                       src/pages/ResetPasswordPage.test.tsx
```

Expected: PASS (7 tests).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx \
        frontend/src/pages/LoginPage.test.tsx \
        frontend/src/pages/RegisterPage.tsx \
        frontend/src/pages/RegisterPage.test.tsx \
        frontend/src/pages/ForgotPasswordPage.tsx \
        frontend/src/pages/ForgotPasswordPage.test.tsx \
        frontend/src/pages/ResetPasswordPage.tsx \
        frontend/src/pages/ResetPasswordPage.test.tsx
git add -u frontend/src/pages/Login.tsx
git commit -m "feat(frontend): add login/register/forgot/reset pages"
```

---

## Task 16: `MustChangePasswordGate`

**Files:**
- Create: `frontend/src/router/MustChangePasswordGate.tsx`
- Create: `frontend/src/router/MustChangePasswordGate.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/router/MustChangePasswordGate.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { MustChangePasswordGate } from "./MustChangePasswordGate";
import { AuthProvider, useAuth } from "../auth/AuthContext";

function Probe() {
  const { setMustChangePassword } = useAuth();
  return (
    <div>
      <button onClick={() => setMustChangePassword(true)}>trigger</button>
      <span>outlet-content</span>
    </div>
  );
}

describe("MustChangePasswordGate", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders outlet when flag is false", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        user_id: "u1",
        email: "a",
        display_name: "A",
        is_admin: false,
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    render(
      <MemoryRouter>
        <AuthProvider>
          <Routes>
            <Route element={<MustChangePasswordGate />}>
              <Route path="/" element={<Probe />} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("outlet-content")).toBeTruthy(),
    );
  });

  it("renders the change-password form when flag is true", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user_id: "u1",
          email: "a",
          display_name: "A",
          is_admin: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    function TriggerGate() {
      const { setMustChangePassword } = useAuth();
      setMustChangePassword(true);
      return null;
    }

    render(
      <MemoryRouter>
        <AuthProvider>
          <TriggerGate />
          <Routes>
            <Route element={<MustChangePasswordGate />}>
              <Route path="/" element={<Probe />} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /set password/i })).toBeTruthy(),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/router/MustChangePasswordGate.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement MustChangePasswordGate.tsx**

Create `frontend/src/router/MustChangePasswordGate.tsx`:

```tsx
import { Outlet } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { MustChangePasswordForm } from "../components/auth/MustChangePasswordForm";
import { useAuth } from "../auth/AuthContext";

export function MustChangePasswordGate() {
  const { mustChangePassword } = useAuth();
  if (mustChangePassword) {
    return (
      <AuthLayout>
        <AuthCard>
          <MustChangePasswordForm />
        </AuthCard>
      </AuthLayout>
    );
  }
  return <Outlet />;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/router/MustChangePasswordGate.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/MustChangePasswordGate.tsx \
        frontend/src/router/MustChangePasswordGate.test.tsx
git commit -m "feat(frontend): add MustChangePasswordGate"
```

---

## Task 17: Wire new routes into `routes.tsx`

**Files:**
- Modify: `frontend/src/router/routes.tsx`

- [ ] **Step 1: Open `routes.tsx` and verify the current shape**

```bash
cat frontend/src/router/routes.tsx
```

Expected: it calls `createBrowserRouter` with a tree that includes `ProtectedRoute` around the app routes and a bare `/login` → `Login` placeholder.

- [ ] **Step 2: Replace the route tree**

Replace `frontend/src/router/routes.tsx` with:

```tsx
import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import { MustChangePasswordGate } from "./MustChangePasswordGate";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";
import { Home } from "../pages/Home";
import { Repository } from "../pages/Repository";
import { Settings } from "../pages/Settings";
import { Setup } from "../pages/Setup";
import { Secretary } from "../pages/departments/Secretary";
import { EquityResearch } from "../pages/departments/EquityResearch";
import { EarningsUpdate } from "../pages/departments/EarningsUpdate";
import { MorningBriefing } from "../pages/departments/MorningBriefing";
import { RetailSentiment } from "../pages/departments/RetailSentiment";
import { MacroResearch } from "../pages/departments/MacroResearch";
import { PanicThermometer } from "../pages/departments/PanicThermometer";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <MustChangePasswordGate />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { path: "/", element: <Home /> },
              { path: "/secretary", element: <Secretary /> },
              { path: "/equity-research", element: <EquityResearch /> },
              { path: "/earnings-update", element: <EarningsUpdate /> },
              { path: "/morning-briefing", element: <MorningBriefing /> },
              { path: "/retail-sentiment", element: <RetailSentiment /> },
              { path: "/macro-research", element: <MacroResearch /> },
              { path: "/panic-thermometer", element: <PanicThermometer /> },
              { path: "/repository", element: <Repository /> },
              { path: "/settings", element: <Settings /> },
              { path: "/setup", element: <Setup /> },
            ],
          },
        ],
      },
    ],
  },
]);
```

If Plan 8 used different page-component names (e.g. `Login.tsx` vs `LoginPage.tsx`, or a different route structure), adjust the imports to the real files under `frontend/src/pages/` before committing. The new components for Plan 9 are `LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`, and `MustChangePasswordGate`.

- [ ] **Step 3: Run the full test suite**

```bash
cd frontend
npm run test -- --run
```

Expected: all existing Plan 8 tests pass and all Plan 9 tests continue to pass. No import errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/routes.tsx
git commit -m "feat(frontend): wire login/register/reset routes"
```

---

## Task 18: `ChangePasswordForm` (Account section)

**Files:**
- Create: `frontend/src/pages/account/ChangePasswordForm.tsx`
- Create: `frontend/src/pages/account/ChangePasswordForm.test.tsx`

This is the authenticated-user-initiated variant — they know their current password and want to change it from Settings.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/account/ChangePasswordForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChangePasswordForm } from "./ChangePasswordForm";

describe("ChangePasswordForm", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("requires all three fields", () => {
    render(<ChangePasswordForm />);
    expect(
      (
        screen.getByRole("button", { name: /change password/i }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it("shows success banner on 204", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;
    render(<ChangePasswordForm />);
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "oldpw123" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toMatch(/updated/i),
    );
  });

  it("surfaces invalid_credentials on 401 as field error", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "invalid_credentials",
          message: "Current password is incorrect.",
          field: "current_password",
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    render(<ChangePasswordForm />);
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "wrong" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Newpw12345!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByText(/Current password is incorrect/i)).toBeTruthy(),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/pages/account/ChangePasswordForm.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement ChangePasswordForm.tsx**

Create `frontend/src/pages/account/ChangePasswordForm.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { changePassword } from "../../api/auth";
import { ApiError } from "../../api/client";
import { Banner, type BannerVariant } from "../../components/primitives/Banner";
import { FormField } from "../../components/primitives/FormField";
import { PasswordInput } from "../../components/primitives/PasswordInput";
import { PasswordStrengthMeter } from "../../components/primitives/PasswordStrengthMeter";

const PASSWORD_MIN = 8;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
}

export function ChangePasswordForm() {
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit =
    current.length > 0 &&
    newPw.length > 0 &&
    confirm.length > 0 &&
    !submitting;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (newPw !== confirm) {
      errs.confirm = "Passwords do not match.";
    }
    if (newPw === current && newPw.length > 0) {
      errs.new_password = "New password must differ from the current one.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ current_password: current, new_password: newPw });
      setBanner({
        message: "Password updated.",
        variant: "success",
      });
      setCurrent("");
      setNewPw("");
      setConfirm("");
    } catch (err) {
      if (err instanceof ApiError) {
        const body = (err.body as ServerError | null) ?? {};
        if (body.field) {
          setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
        } else {
          setBanner({
            message: body.message ?? "Password change failed.",
            variant: "error",
          });
        }
      } else {
        setBanner({
          message: "Unexpected error. Please try again.",
          variant: "error",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="max-w-md">
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="account_current_password"
        label="Current Password"
        error={fieldErrors.current_password}
      >
        <PasswordInput
          id="account_current_password"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.current_password)}
          disabled={submitting}
        />
      </FormField>

      <FormField
        id="account_new_password"
        label="New Password"
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="account_new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="account_confirm_password"
        label="Confirm New Password"
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="account_confirm_password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
        />
      </FormField>

      <button
        type="submit"
        disabled={!canSubmit}
        aria-busy={submitting}
        className="h-10 px-4 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Change Password"
        )}
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/pages/account/ChangePasswordForm.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/account/ChangePasswordForm.tsx \
        frontend/src/pages/account/ChangePasswordForm.test.tsx
git commit -m "feat(frontend): add account ChangePasswordForm"
```

---

## Task 19: `AccountProfile`

**Files:**
- Create: `frontend/src/pages/account/AccountProfile.tsx`
- Create: `frontend/src/pages/account/AccountProfile.test.tsx`

Profile is read-only in v1 — displays id, email, display name, role. Editing display name is a non-goal per `AccountManagementSpec.md` §3 Out of Scope.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/account/AccountProfile.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AccountProfile } from "./AccountProfile";
import { AuthProvider } from "../../auth/AuthContext";

describe("AccountProfile", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders email + role for authenticated user", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user: {
            id: "u1",
            email: "x@y.com",
            role: "admin",
            display_name: "Alice",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <AccountProfile />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByText("x@y.com")).toBeTruthy());
    expect(screen.getByText("Alice")).toBeTruthy();
    expect(screen.getByText(/admin/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/pages/account/AccountProfile.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement AccountProfile.tsx**

Create `frontend/src/pages/account/AccountProfile.tsx`:

```tsx
import { useAuth } from "../../auth/AuthContext";

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline gap-4 py-2 border-b border-border-subtle last:border-b-0">
      <dt className="w-40 text-sm text-text-secondary">{label}</dt>
      <dd className="text-sm text-text-primary">{value ?? "—"}</dd>
    </div>
  );
}

export function AccountProfile() {
  const { user, status } = useAuth();
  if (status === "loading" || !user) {
    return <p className="text-sm text-text-secondary">Loading…</p>;
  }
  return (
    <dl className="max-w-md">
      <Row label="Email" value={user.email} />
      <Row label="Display name" value={user.display_name ?? null} />
      <Row label="Role" value={user.role} />
      <Row label="User ID" value={user.id} />
    </dl>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/pages/account/AccountProfile.test.tsx
```

Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/account/AccountProfile.tsx \
        frontend/src/pages/account/AccountProfile.test.tsx
git commit -m "feat(frontend): add AccountProfile read-only view"
```

---

## Task 20: `SessionsPanel` (logout-all)

**Files:**
- Create: `frontend/src/pages/account/SessionsPanel.tsx`
- Create: `frontend/src/pages/account/SessionsPanel.test.tsx`

Per Design Rule 13 and `AccountManagementSpec.md` §15 Open Q2, the v1 UI is minimal: one-line "You are signed in on this device" plus a "Sign out all other devices" action. The button hits `/auth/logout-all`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/account/SessionsPanel.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SessionsPanel } from "./SessionsPanel";

describe("SessionsPanel", () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the current-session line and the sign-out-all button", () => {
    render(<SessionsPanel />);
    expect(screen.getByText(/signed in on this device/i)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /sign out all other devices/i }),
    ).toBeTruthy();
  });

  it("POSTs /auth/logout-all on click and shows success", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    render(<SessionsPanel />);
    fireEvent.click(
      screen.getByRole("button", { name: /sign out all other devices/i }),
    );

    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toMatch(
        /other sessions signed out/i,
      ),
    );
    expect(spy.mock.calls[0][0]).toBe("/api/auth/logout-all");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- --run src/pages/account/SessionsPanel.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement SessionsPanel.tsx**

Create `frontend/src/pages/account/SessionsPanel.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { logoutAll } from "../../api/auth";
import { Banner, type BannerVariant } from "../../components/primitives/Banner";

export function SessionsPanel() {
  const [submitting, setSubmitting] = useState(false);
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);

  async function onClick() {
    setSubmitting(true);
    setBanner(null);
    try {
      await logoutAll();
      setBanner({
        message: "Other sessions signed out.",
        variant: "success",
      });
    } catch {
      setBanner({
        message: "Unable to sign out other sessions. Please try again.",
        variant: "error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-md">
      <p className="text-sm text-text-primary mb-4">
        You are signed in on this device.
      </p>
      {banner && <Banner variant={banner.variant} message={banner.message} />}
      <button
        type="button"
        onClick={onClick}
        disabled={submitting}
        aria-busy={submitting}
        className="h-10 px-4 rounded-md border border-border-subtle bg-bg-elevated text-sm font-medium text-text-primary hover:bg-surface-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : null}
        Sign out all other devices
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- --run src/pages/account/SessionsPanel.test.tsx
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/account/SessionsPanel.tsx \
        frontend/src/pages/account/SessionsPanel.test.tsx
git commit -m "feat(frontend): add SessionsPanel (logout-all)"
```

---

## Task 21: Sidebar logout action + full suite sanity pass

Plan 8's Sidebar already has a hook for user actions. Wire a "Sign out" button that calls `signOut()` from context and navigates to `/login`.

**Files:**
- Modify: `frontend/src/components/sidebar/Sidebar.tsx`
- Modify: `frontend/src/components/sidebar/Sidebar.test.tsx`

- [ ] **Step 1: Inspect the Plan 8 Sidebar**

```bash
cat frontend/src/components/sidebar/Sidebar.tsx
```

Expected: you'll see a three-zone layout (logo, nav, user/settings block).

- [ ] **Step 2: Append a sign-out test**

Append to `frontend/src/components/sidebar/Sidebar.test.tsx`:

```tsx
import { fireEvent, waitFor } from "@testing-library/react";
// … existing imports remain

it("calls signOut when the sign-out button is clicked", async () => {
  const spy = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          user_id: "u1",
          email: "a",
          display_name: "A",
          is_admin: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 })); // logout
  global.fetch = spy as unknown as typeof fetch;

  render(
    <MemoryRouter>
      <AuthProvider>
        <Sidebar />
      </AuthProvider>
    </MemoryRouter>,
  );

  await waitFor(() =>
    expect(screen.queryByRole("button", { name: /sign out/i })).toBeTruthy(),
  );
  fireEvent.click(screen.getByRole("button", { name: /sign out/i }));

  await waitFor(() => {
    const urls = spy.mock.calls.map((c: unknown[]) => c[0]);
    expect(urls).toContain("/api/auth/logout");
  });
});
```

(Use the existing `describe` block at the bottom of the file; imports like `MemoryRouter`, `Sidebar`, `AuthProvider`, `render`, `screen`, `vi` are already at the top from Plan 8.)

- [ ] **Step 3: Add a sign-out button inside the Sidebar**

Inside `Sidebar.tsx`, find the footer / user area. Add (after the existing user block):

```tsx
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
```

```tsx
const { status, signOut } = useAuth();
const navigate = useNavigate();

async function handleSignOut() {
  await signOut();
  navigate("/login", { replace: true });
}

// inside the footer zone JSX, render only when authenticated (not personal):
{status === "authenticated" && (
  <button
    type="button"
    onClick={handleSignOut}
    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-text-secondary rounded-md hover:bg-surface-hover"
    aria-label="Sign out"
  >
    <LogOut size={16} />
    Sign out
  </button>
)}
```

(Insert this in whichever footer JSX the Plan 8 Sidebar uses; the exact structure may differ. Preserve existing children and only add the sign-out button.)

- [ ] **Step 4: Run the full suite**

```bash
cd frontend
npm run test -- --run
```

Expected: every test passes — Plan 8's sidebar tests, all new Plan 9 tests, and the new sidebar sign-out test.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/sidebar/Sidebar.tsx \
        frontend/src/components/sidebar/Sidebar.test.tsx
git commit -m "feat(frontend): add sidebar sign-out action"
```

---

## Task 22: Manual smoke test

**Files:**
- None changed — this is a dev-server walkthrough.

- [ ] **Step 1: Start the backend in company mode**

In one terminal at repo root:

```bash
OPENLIA_MODE=company uv run openlia serve
```

Expected: the server boots on `http://127.0.0.1:8000` and the auth routes are mounted.

- [ ] **Step 2: Create an invite via CLI (Plan 7)**

In a second terminal:

```bash
uv run openlia admin create-invite --label "qa" --max-uses 3
```

Expected: prints an invite URL like `http://127.0.0.1:8000/register?invite=<token>`.

- [ ] **Step 3: Start the frontend dev server**

```bash
cd frontend
npm run dev
```

Expected: Vite serves on port 5173 (default) and proxies `/api/*` to FastAPI.

- [ ] **Step 4: Walk the flows in a real browser**

Open the dev URL, log out if needed, then visit each flow:

1. `http://localhost:5173/login` — expect the login card, no sign-up link.
2. `http://localhost:5173/register?invite=<token>` — expect the register form; submit; expect redirect to `/`.
3. Log out from the sidebar.
4. `http://localhost:5173/forgot-password` — submit any email; expect neutral success banner.
5. `http://localhost:5173/reset-password?token=abc` — submit new password; expect server to return `token_invalid`; expect error banner.
6. Use `openlia admin reset-password <email>` to set a temporary password; log in — expect the `Must Change Password` screen to take over.
7. After setting a new password, expect the sidebar and normal app to appear.
8. Visit `/settings` — the Account section isn't wired up until Plan 11. For Plan 9 smoke, render `AccountProfile` + `ChangePasswordForm` + `SessionsPanel` in isolation via the existing test suite (already green) and skip the integrated view.

- [ ] **Step 5: Document findings**

If the walkthrough surfaces any gap with the spec (copy, color, contrast, tab order), capture it as a short note at the bottom of this file under a new `## Deviations` section and adjust the spec/plan accordingly rather than shipping silently.

- [ ] **Step 6: Commit any fixes from Step 5**

```bash
git status
# If anything changed during the walkthrough, commit it now with:
git commit -am "fix(frontend): address Plan 9 smoke-test findings"
```

---

## Task 23: Update planning docs

**Files:**
- Modify: `planning/implementation-plans/README.md`
- Modify: `planning/projectStructure.md`

- [ ] **Step 1: Flip Plan 9 row in README**

In `planning/implementation-plans/README.md`, change the Plan 9 row from:

```
| 9 | 4 | Login + Account Management UI | Not started | — |
```

to:

```
| 9 | 4 | Login + Account Management UI | Draft | `2026-04-17-phase-9-login-and-account-ui.md` |
```

- [ ] **Step 2: Append new frontend tree to projectStructure.md**

Under the `frontend/src/` section, append (or merge with the existing tree):

```
components/
├── auth/
│   ├── AuthLayout.tsx
│   ├── AuthCard.tsx
│   ├── LoginForm.tsx
│   ├── RegisterForm.tsx
│   ├── ForgotPasswordForm.tsx
│   ├── ResetPasswordForm.tsx
│   └── MustChangePasswordForm.tsx
└── primitives/
    ├── Banner.tsx
    ├── FormField.tsx
    ├── PasswordInput.tsx
    └── PasswordStrengthMeter.tsx
pages/
├── LoginPage.tsx
├── RegisterPage.tsx
├── ForgotPasswordPage.tsx
├── ResetPasswordPage.tsx
└── account/
    ├── AccountProfile.tsx
    ├── ChangePasswordForm.tsx
    └── SessionsPanel.tsx
router/
└── MustChangePasswordGate.tsx
auth/
└── passwordStrength.ts
```

If `projectStructure.md` already carries a frontend tree, update the relevant sections in place instead of appending a duplicate.

- [ ] **Step 3: Commit**

```bash
git add planning/implementation-plans/README.md planning/projectStructure.md
git commit -m "docs: mark Plan 9 as Draft and update projectStructure"
```

---

## Self-Review Checklist (run after executing the plan, not during planning)

After Task 23, verify:

1. **Spec coverage (`LoginPageSpec.md`):**
   - Login view (Task 10) ✓
   - Registration view, invite-gated (Tasks 11 + 15) ✓
   - Forgot Password in-place view (Task 12 + its own `/forgot-password` route in Task 17) ✓
   - Reset Password standalone page (Tasks 13 + 15) ✓
   - Must Change Password view + gate (Tasks 14 + 16) ✓
   - Keep Me Logged In checkbox (Task 10) ✓
   - Client + server-side validation, inline + banner errors (Tasks 10–14) ✓
   - Password strength indicator (Task 8) ✓
   - Anti-enumeration neutral confirmation (Task 12) ✓
   - Rate-limit / account-locked banners (Task 10) ✓
   - Focus management on submit, `aria-busy`, `aria-describedby` — verify in the smoke test (Task 22). A spot-check pass here is required; if any are missing, add a small follow-up task before closing the plan.
   - View transition animations (light fade) — Tailwind `transition-colors duration-fast` covers color transitions; the 100–150 ms fade on swap is handled by React re-rendering between `/login`, `/register`, `/forgot-password` routes at their natural render boundary.

2. **Spec coverage (`AccountManagementSpec.md`):**
   - `/auth/logout-all` from the Sessions panel (Task 20) ✓
   - Direct admin reset must-change flow (Task 14 + 16) ✓
   - Admin-approved password reset (Tasks 12 + 13 + 15) ✓
   - Error-code surface (`invalid_credentials`, `account_locked`, `invite_invalid`, `token_invalid`, `token_expired`, `rate_limited`, `weak_password`, `email_in_use`) is handled by each form's `handleError` — grep for each code once and add a fallback banner where missing.

3. **Type consistency:** `AuthUser`, `LoginInput`, `RegisterInput`, `ChangePasswordInput`, `ConsumePasswordResetInput`, `SignupPolicy` — all defined once in `api/auth.ts` and imported by callers. `AuthStatus` stays `"loading" | "authenticated" | "unauthenticated" | "personal"` across Plan 8 + Plan 9.

4. **Placeholder scan:** No "TBD", "TODO", "implement later", "similar to X", or "fill in" present. All test code is complete; all implementation code is complete; all commands are runnable.

5. **Commit discipline:** 23 tasks → ~23 commits. Each commit message uses the `feat(frontend)` / `test(frontend)` / `docs:` / `chore(frontend)` / `fix(frontend)` convention with an under-72-char subject line.
