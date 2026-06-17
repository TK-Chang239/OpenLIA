# Company Mode Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-enable the deliberately-disabled frontend auth so company mode is usable end-to-end (admin setup → login → invite → second user registers and logs in).

**Architecture:** The backend multi-user stack (auth, sessions, invites, admin, password-reset queue) is complete. The UI remake (PR #97) disabled the frontend login by collapsing all session outcomes to "personal" mode and replacing the auth routes with redirects. We restore the pre-remake `AuthContext` mode detection (404→personal, 401→unauthenticated) and route elements, build the two stub components (`ChangePasswordForm`, `SessionsPanel`), add a desktop sidebar logout, and verify with tests + a manual checklist. Personal mode must stay untouched.

**Tech Stack:** React 18 + TypeScript + Vite + react-router-dom + react-i18next + Tailwind; Vitest + Testing Library (frontend); FastAPI + pytest (backend).

**Spec:** `planning/specs/2026-06-16-company-mode-onboarding-design.md`

---

## File Structure

**Frontend — modify:**
- `frontend/src/auth/AuthContext.tsx` — restore 404/401 mode detection in `refresh` and `logout`.
- `frontend/src/router/routes.tsx` — restore the four auth page route elements.
- `frontend/src/components/auth/ChangePasswordForm.tsx` — replace 3-line stub with real component.
- `frontend/src/components/auth/SessionsPanel.tsx` — replace 3-line stub with "sign out everywhere" action.
- `frontend/src/components/sidebar/Sidebar.tsx` — add desktop logout control.
- `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/zh-TW.json` — new keys.

**Frontend — create (tests):**
- `frontend/src/auth/AuthContext.test.tsx`
- `frontend/src/router/routes.test.tsx`
- `frontend/src/components/auth/ChangePasswordForm.test.tsx`
- `frontend/src/components/auth/SessionsPanel.test.tsx`
- `frontend/src/components/sidebar/Sidebar.signout.test.tsx`

**Backend — verify (no new prod code):**
- Run existing `packages/server/tests/test_routes/test_auth_routes.py`, `test_services/test_auth/test_registration.py`, `test_services/test_admin_invites.py`, `test_routes/test_must_change_password_gate.py`, `test_e2e_smoke_matrix.py`.

---

## Task 1: Restore AuthContext mode detection

Restore the pre-remake logic so 404 (auth routes unmounted = personal) maps to `personal` and any other failure (401 = company, no session) maps to `unauthenticated`. This is the keystone change.

**Files:**
- Modify: `frontend/src/auth/AuthContext.tsx`
- Test: `frontend/src/auth/AuthContext.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/auth/AuthContext.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { status } = useAuth();
  return <div data-testid="status">{status}</div>;
}

describe("AuthContext mode detection", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("maps a 404 session probe to personal mode", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 404 })) as unknown as typeof fetch;
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("personal"),
    );
  });

  it("maps a 401 session probe to unauthenticated", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
  });

  it("maps a 200 session probe to authenticated", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ user_id: "u1", email: "a@b.c", is_admin: true }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ) as unknown as typeof fetch;
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/auth/AuthContext.test.tsx`
Expected: FAIL — the 401 case resolves to "personal" (current code collapses every failure to personal).

- [ ] **Step 3: Restore the refresh/logout logic**

In `frontend/src/auth/AuthContext.tsx`, add the `ApiError` import near the other `../api/auth` import:

```tsx
import { ApiError } from "../api/client";
```

Replace the `refresh` callback (currently lines ~49-68) with:

```tsx
  const refresh = useCallback(async (): Promise<void> => {
    try {
      const fetched = await getSession();
      setUser(fetched.user);
      setMustChangePasswordState(fetched.must_change_password);
      setStatus("authenticated");
    } catch (err) {
      // 404 = auth routes unmounted => personal (single-user, no auth).
      // Any other failure (401 = company, no session) => unauthenticated,
      // which ProtectedRoute redirects to /login.
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

Replace the `logout` callback (currently lines ~77-88) with:

```tsx
  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutRequest();
    } catch (err) {
      console.warn("logout failed", err);
    }
    setUser(null);
    setMustChangePasswordState(false);
    setStatus("unauthenticated");
  }, []);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/auth/AuthContext.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx frontend/src/auth/AuthContext.test.tsx
git commit -m "fix(auth): restore company-mode 401 detection in AuthContext"
```

---

## Task 2: Restore the four auth route elements

Replace the `<Navigate to="/" replace />` redirect stubs with the real page components (they already exist).

**Files:**
- Modify: `frontend/src/router/routes.tsx`
- Test: `frontend/src/router/routes.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/router/routes.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import type { ReactElement } from "react";
import type { RouteObject } from "react-router-dom";
import { routes } from "./routes";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";

function findByPath(rs: RouteObject[], path: string): RouteObject | undefined {
  for (const r of rs) {
    if (r.path === path) return r;
    if (r.children) {
      const found = findByPath(r.children, path);
      if (found) return found;
    }
  }
  return undefined;
}

describe("auth routes are enabled", () => {
  it.each([
    ["/login", LoginPage],
    ["/register", RegisterPage],
    ["/forgot-password", ForgotPasswordPage],
    ["/reset-password", ResetPasswordPage],
  ])("%s renders its real page element", (path, Page) => {
    const route = findByPath(routes, path as string);
    expect(route).toBeTruthy();
    const element = route!.element as ReactElement;
    expect(element.type).toBe(Page);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/router/routes.test.tsx`
Expected: FAIL — `element.type` is `Navigate`, not the page components.

- [ ] **Step 3: Restore the route imports and elements**

In `frontend/src/router/routes.tsx`, add the page imports alongside the other page imports (near line 7-12):

```tsx
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { ResetPasswordPage } from "../pages/ResetPasswordPage";
```

Replace the four redirect lines (currently lines 74-78):

```tsx
      // Login pages disabled — redirect any attempt back to the shell.
      { path: "/login", element: <Navigate to="/" replace /> },
      { path: "/register", element: <Navigate to="/" replace /> },
      { path: "/forgot-password", element: <Navigate to="/" replace /> },
      { path: "/reset-password", element: <Navigate to="/" replace /> },
```

with:

```tsx
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
```

Leave the `Navigate` import in place (still used by `/home` and the catch-all `*` route).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/router/routes.test.tsx`
Expected: PASS (4 cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/routes.tsx frontend/src/router/routes.test.tsx
git commit -m "feat(auth): re-enable login/register/forgot/reset routes"
```

---

## Task 3: Add i18n keys for change-password and sessions

The new components reference keys that must resolve to English in tests and exist in both locales (bilingual support).

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Add English keys**

In `frontend/src/i18n/locales/en.json`, inside the existing `settings.account` object (which already has `change_password_section_title` and `active_sessions_section_title`), add:

```json
"change_password": {
  "current_label": "Current Password",
  "new_label": "New Password",
  "confirm_label": "Confirm New Password",
  "submit": "Change password",
  "success": "Password changed."
},
"sessions": {
  "description": "Signing out of all devices ends every session, including this one. You'll need to sign in again.",
  "sign_out_all": "Sign out of all devices"
}
```

In the existing `auth.errors` object, add:

```json
"enter_current_password": "Enter your current password."
```

(The keys `password_too_short`, `passwords_do_not_match`, `new_password_must_differ`, `invalid_value`, and `password_change_failed` already exist under `auth.errors` — do not duplicate them.)

- [ ] **Step 2: Add Traditional Chinese keys**

In `frontend/src/i18n/locales/zh-TW.json`, inside `settings.account`, add:

```json
"change_password": {
  "current_label": "目前密碼",
  "new_label": "新密碼",
  "confirm_label": "確認新密碼",
  "submit": "變更密碼",
  "success": "密碼已變更。"
},
"sessions": {
  "description": "登出所有裝置會結束每個工作階段，包括目前這個。您需要重新登入。",
  "sign_out_all": "登出所有裝置"
}
```

In `auth.errors`, add:

```json
"enter_current_password": "請輸入目前的密碼。"
```

- [ ] **Step 3: Verify JSON parses and locales stay in sync**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json','utf8')); JSON.parse(require('fs').readFileSync('src/i18n/locales/zh-TW.json','utf8')); console.log('ok')"`
Expected: prints `ok` (both files are valid JSON).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "i18n: add change-password and sessions keys (en + zh-TW)"
```

---

## Task 4: Build the real ChangePasswordForm

Replace the 3-line stub with a working form modeled on `MustChangePasswordForm`, calling the existing `changePassword` API. Stays on the page and shows a success banner (no redirect).

**Files:**
- Modify: `frontend/src/components/auth/ChangePasswordForm.tsx`
- Test: `frontend/src/components/auth/ChangePasswordForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/auth/ChangePasswordForm.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChangePasswordForm } from "./ChangePasswordForm";

function renderForm() {
  return render(<ChangePasswordForm />);
}

describe("ChangePasswordForm", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("blocks submit when confirm does not match", async () => {
    global.fetch = vi.fn() as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "OldPass1!" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Different1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByText(/passwords do not match/i)).toBeTruthy(),
    );
    expect((global.fetch as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBe(0);
  });

  it("posts to change-password and shows success on 204", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;
    renderForm();
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "OldPass1!" },
    });
    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "Abcdefg1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    await waitFor(() =>
      expect(screen.getByText(/password changed/i)).toBeTruthy(),
    );
    const call = (global.fetch as unknown as { mock: { calls: [string][] } }).mock.calls[0];
    expect(call[0]).toContain("/api/auth/change-password");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/auth/ChangePasswordForm.test.tsx`
Expected: FAIL — stub renders only "Change Password (stub)"; no labeled inputs.

- [ ] **Step 3: Implement the component**

Replace the entire contents of `frontend/src/components/auth/ChangePasswordForm.tsx` with:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { changePassword } from "../../api/auth";
import { ApiError } from "../../api/client";
import { mapTransportError } from "../../api/errors";
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

export function ChangePasswordForm() {
  const { t } = useTranslation();
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
      errs.current_password = t("auth.errors.enter_current_password");
    }
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = t("auth.errors.password_too_short", { min: PASSWORD_MIN });
    }
    if (newPw !== confirm) {
      errs.confirm = t("auth.errors.passwords_do_not_match");
    }
    if (newPw === current && newPw.length > 0) {
      errs.new_password = t("auth.errors.new_password_must_differ");
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ current_password: current, new_password: newPw });
      setCurrent("");
      setNewPw("");
      setConfirm("");
      setBanner({
        message: t("settings.account.change_password.success"),
        variant: "success",
      });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 0 || err.status >= 500) {
          setBanner(mapTransportError(err));
        } else {
          const body = (err.body as ServerError | null) ?? {};
          if (body.field) {
            setFieldErrors({ [body.field]: body.message ?? t("auth.errors.invalid_value") });
          } else {
            setBanner({
              message: body.message ?? t("auth.errors.password_change_failed"),
              variant: "error",
            });
          }
        }
      } else {
        setBanner(mapTransportError(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="current_password"
        label={t("settings.account.change_password.current_label")}
        error={fieldErrors.current_password}
      >
        <PasswordInput
          id="current_password"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.current_password)}
          disabled={submitting}
          describedBy={fieldErrors.current_password ? "current_password-error" : undefined}
        />
      </FormField>

      <FormField
        id="new_password"
        label={t("settings.account.change_password.new_label")}
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
          describedBy={fieldErrors.new_password ? "new_password-error" : undefined}
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="confirm"
        label={t("settings.account.change_password.confirm_label")}
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="confirm"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
          describedBy={fieldErrors.confirm ? "confirm-error" : undefined}
        />
      </FormField>

      <button
        type="submit"
        disabled={submitting}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label={t("auth.loading_aria")} />
        ) : (
          t("settings.account.change_password.submit")
        )}
      </button>
    </form>
  );
}
```

Note: `BannerVariant` already includes `"success"` and `"error"` (used elsewhere in the app). If `tsc` reports `"success"` is not assignable, use `"info"` for the success banner instead.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/auth/ChangePasswordForm.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/ChangePasswordForm.tsx frontend/src/components/auth/ChangePasswordForm.test.tsx
git commit -m "feat(auth): implement ChangePasswordForm in account settings"
```

---

## Task 5: Build SessionsPanel ("sign out of all devices")

No "list my sessions" endpoint exists; scope to the existing `logout-all`. Because that revokes every session including the current one, on success we reset client auth state and bounce to `/login`.

**Files:**
- Modify: `frontend/src/components/auth/SessionsPanel.tsx`
- Test: `frontend/src/components/auth/SessionsPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/auth/SessionsPanel.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SessionsPanel } from "./SessionsPanel";
import { AuthProvider } from "../../auth/AuthContext";

function renderPanel() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SessionsPanel />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("SessionsPanel", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("calls logout-all when the button is clicked", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // AuthProvider session probe
      .mockResolvedValueOnce(new Response(null, { status: 204 })) // logout-all
      .mockResolvedValueOnce(new Response(null, { status: 204 })) // logout
      as unknown as typeof fetch;
    renderPanel();
    fireEvent.click(
      await screen.findByRole("button", { name: /sign out of all devices/i }),
    );
    await waitFor(() => {
      const calls = (global.fetch as unknown as { mock: { calls: [string][] } }).mock.calls;
      expect(calls.some((c) => String(c[0]).includes("/api/auth/logout-all"))).toBe(true);
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/auth/SessionsPanel.test.tsx`
Expected: FAIL — stub renders only "Sessions (stub)"; no button.

- [ ] **Step 3: Implement the component**

Replace the entire contents of `frontend/src/components/auth/SessionsPanel.tsx` with:

```tsx
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { logoutAll } from "../../api/auth";
import { mapTransportError } from "../../api/errors";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";

export function SessionsPanel() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);

  async function onSignOutAll() {
    setBanner(null);
    setSubmitting(true);
    try {
      await logoutAll();
      // logout-all revokes every session including this one; reset local auth
      // state and send the user back to the login screen.
      await logout();
      navigate("/login", { replace: true });
    } catch (err) {
      setBanner(mapTransportError(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {banner && <Banner variant={banner.variant} message={banner.message} />}
      <p className="text-sm text-text-secondary">
        {t("settings.account.sessions.description")}
      </p>
      <button
        type="button"
        onClick={() => {
          void onSignOutAll();
        }}
        disabled={submitting}
        aria-busy={submitting}
        className="self-start h-10 px-4 rounded-md border border-border-subtle text-sm font-medium text-text-primary flex items-center justify-center hover:bg-bg-elevated transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label={t("auth.loading_aria")} />
        ) : (
          t("settings.account.sessions.sign_out_all")
        )}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/auth/SessionsPanel.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/SessionsPanel.tsx frontend/src/components/auth/SessionsPanel.test.tsx
git commit -m "feat(auth): SessionsPanel sign-out-of-all-devices action"
```

---

## Task 6: Add desktop sidebar logout

The desktop `Sidebar` has no logout (only the mobile overlay does). Add one gated on `status === "authenticated"` so it is invisible in personal mode.

**Files:**
- Modify: `frontend/src/components/sidebar/Sidebar.tsx`
- Test: `frontend/src/components/sidebar/Sidebar.signout.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/sidebar/Sidebar.signout.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { mockState, mockLogout } = vi.hoisted(() => ({
  mockState: { status: "authenticated" as string },
  mockLogout: vi.fn(),
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    status: mockState.status,
    user: { id: "u1", display_name: "Ada Admin", email: "ada@corp.com" },
    logout: mockLogout,
  }),
}));

vi.mock("./useNotificationPoll", () => ({
  useNotificationPoll: () => ({ unreadByDepartment: {}, markRead: vi.fn() }),
}));

import { Sidebar } from "./Sidebar";

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar desktop sign-out", () => {
  it("shows the sign-out button when authenticated", () => {
    mockState.status = "authenticated";
    renderSidebar();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeTruthy();
  });

  it("hides the sign-out button in personal mode", () => {
    mockState.status = "personal";
    renderSidebar();
    expect(screen.queryByRole("button", { name: /sign out/i })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/sidebar/Sidebar.signout.test.tsx`
Expected: FAIL — no sign-out button exists in the desktop sidebar.

- [ ] **Step 3: Add the logout control**

In `frontend/src/components/sidebar/Sidebar.tsx`:

(a) Extend the lucide-react import (line 5) to include `LogOut`:

```tsx
import { ChevronLeft, ChevronRight, LogOut, Settings } from "lucide-react";
```

(b) Extend the react-router-dom import (line 3) to include `useNavigate`:

```tsx
import { useLocation, useNavigate } from "react-router-dom";
```

(c) Destructure `logout` from `useAuth` and add a navigate handle (lines ~36):

```tsx
  const { status, user, logout } = useAuth();
  const navigate = useNavigate();
```

(d) Add the handler just after the `useEffect` block (around line 43):

```tsx
  async function handleSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }
```

(e) In the footer, immediately after the Settings `NavItem` (the `<NavItem ... path="/settings" ... />` near line 158-164), add:

```tsx
        {status === "authenticated" && (
          <button
            type="button"
            onClick={() => {
              void handleSignOut();
            }}
            aria-label={t("shell.sign_out")}
            className={[
              "flex items-center gap-[10px] rounded-md w-full",
              "transition-colors duration-normal ease-out",
              collapsed ? "justify-center px-0 py-[9px]" : "px-[10px] py-[9px]",
            ].join(" ")}
            style={{ color: "var(--color-sidebar-text)" }}
          >
            <LogOut size={16} strokeWidth={1.5} />
            {!collapsed && (
              <span className="text-[13px] font-display truncate">
                {t("shell.sign_out")}
              </span>
            )}
          </button>
        )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/sidebar/Sidebar.signout.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/sidebar/Sidebar.tsx frontend/src/components/sidebar/Sidebar.signout.test.tsx
git commit -m "feat(shell): add desktop sidebar sign-out in company mode"
```

---

## Task 7: Verify backend onboarding endpoints (no new prod code)

Confirm the existing backend auth/admin/onboarding tests pass; add one end-to-end gap test only if the full register→login→invite loop is not already covered.

**Files:**
- Verify: existing `packages/server/tests/test_routes/test_auth_routes.py`, `test_services/test_auth/test_registration.py`, `test_services/test_admin_invites.py`, `test_routes/test_must_change_password_gate.py`, `test_e2e_smoke_matrix.py`.

- [ ] **Step 1: Run the existing auth/admin/onboarding suites**

Run:
```bash
uv run pytest \
  packages/server/tests/test_routes/test_auth_routes.py \
  packages/server/tests/test_services/test_auth/ \
  packages/server/tests/test_services/test_admin_invites.py \
  packages/server/tests/test_routes/test_must_change_password_gate.py \
  packages/server/tests/test_e2e_smoke_matrix.py \
  -v
```
Expected: PASS. (Note from project memory: the full `packages/server/` suite can hang on SSE/stream tests — run these targeted paths, not the whole package.)

- [ ] **Step 2: Check for an end-to-end onboarding test**

Run: `grep -rln "register" packages/server/tests/test_e2e_smoke_matrix.py packages/server/tests/test_routes/test_auth_routes.py`
Inspect whether a single test exercises: create-first-admin → admin login → create invite → register second user with that invite → second user login. If such a test exists, skip Step 3.

- [ ] **Step 3: Add the gap test only if missing**

If Step 2 shows no end-to-end coverage, open `packages/server/tests/test_routes/test_auth_routes.py`, copy its company-mode app/client fixture pattern, and add a test that walks the full loop:

1. Seed signup policy `invite_only` and create the first admin (mirror how `test_admin_invites.py` builds the admin + session).
2. As admin, `POST /admin/invites` → capture `token`.
3. `POST /auth/register` with `{email, password, invite_token: token}` → expect 201.
4. `POST /auth/login` with the new user's credentials → expect 200 and a `Set-Cookie: openlia_session`.
5. As admin, `POST /admin/users/{id}/disable` → then that user's `GET /auth/session` returns 401.

Use the exact fixture names that `test_auth_routes.py` already defines (do not invent a new client fixture). Run:
```bash
uv run pytest packages/server/tests/test_routes/test_auth_routes.py -v
```
Expected: PASS including the new test.

- [ ] **Step 4: Commit (only if a test was added)**

```bash
git add packages/server/tests/test_routes/test_auth_routes.py
git commit -m "test(auth): end-to-end company onboarding loop"
```

---

## Task 8: Remake-assumption audit, full verification, and manual checklist

Catch any other place that assumed "login disabled / personal-only", then run the full verification gates.

**Files:**
- Verify only (fix inline if the audit finds a real issue, with its own commit).

- [ ] **Step 1: Audit for stale "login disabled" assumptions**

Run:
```bash
grep -rni "login.*disabled\|disabled.*login\|personal mode\|collapse.*personal\|remake" frontend/src --include=*.ts --include=*.tsx
grep -rn "unauthenticated" frontend/src --include=*.tsx
```
Review each hit. Confirm `ProtectedRoute` still redirects `unauthenticated → /login` and that no other component hardcodes personal-only behavior that breaks company login. If a real blocker is found, fix it and commit separately with a clear message.

- [ ] **Step 2: Frontend typecheck + lint + full test run**

Run:
```bash
cd frontend && npx tsc --noEmit && npm run lint && npx vitest run
```
Expected: tsc clean; lint clean; all vitest suites pass. (Project memory notes a pre-existing `SettingsShellBlocker` AbortSignal failure can make vitest exit non-zero — confirm any failure is that known issue and not introduced by this work by checking the failing test name.)

- [ ] **Step 3: Backend lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 4: Manual browser checklist (operator-run)**

Start the server in company mode and walk the loop:
```bash
OPENLIA_MODE=company OPENLIA_SECRET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" uv run openlia serve
```
Then in the browser (Vite dev on :5173 proxying to backend):
1. Fresh DB → redirected to `/setup`; choose Company; create first admin; finish wizard.
2. Land on `/login`; log in as the admin → reach the app shell.
3. Settings → Admin → Invites: create an invite, copy the token.
4. Open a private window → `/register`, register a second user with the token → logged in.
5. As admin, Settings → Admin → Users: disable the second user → confirm their next action 401s and bounces to `/login`.
6. Settings → Account: change password succeeds; "Sign out of all devices" returns to `/login`.
7. Desktop sidebar shows a Sign out control; it logs out to `/login`.

Personal-mode regression:
```bash
OPENLIA_MODE=personal uv run openlia serve
```
8. Fresh personal instance boots straight into the app with no login UI and no Sign out control.

- [ ] **Step 5: Final commit / branch wrap-up**

Ensure all work is committed on the feature branch. The branch is ready for PR once Steps 1-4 pass.

---

## Self-Review Notes (author)

- **Spec coverage:** route restore (T2), AuthContext detection (T1), ChangePasswordForm (T4), SessionsPanel = sign-out-all (T5), desktop logout (T6), admin-mediated reset pages re-enabled via routes (T2 — `/forgot-password`, `/reset-password` use existing `ForgotPasswordForm`/`ResetPasswordForm`), backend verification (T7), audit + manual checklist (T8). All spec sections mapped.
- **Out of scope honored:** no `GET /auth/sessions` endpoint added; no email infra; no new roles; personal mode untouched (T1 keeps 404→personal; T6 hides logout in personal).
- **Type consistency:** `changePassword`, `logoutAll`, `getSession` signatures match `api/auth.ts`; `ApiError.status` matches `api/client.ts`; i18n keys added in T3 are consumed in T4/T5; `BannerVariant` fallback noted.
