# Frontend Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the React shell — router, auth context, API client, Sidebar with notification polling, design tokens, and base primitives — so every downstream page plan (Login, Wizard, Settings, department UIs) can plug in against a stable layout.

**Architecture:** Vite + React 18 + TypeScript + react-router-dom v6 data-router pattern. A single `AuthProvider` owns user/mode state derived from `GET /auth/session` (404 → personal mode, 401 → unauthenticated, 200 → company-authenticated). The `Sidebar` reads a data-driven nav list, polls `GET /notifications/unread` every 60 s, and renders per-department dots. Tailwind v3 with CSS custom properties carries design tokens.

**Tech Stack:** React 18, TypeScript 5 (strict), react-router-dom v6 (data router), Tailwind CSS v3, lucide-react, vitest + @testing-library/react + jsdom (already in scaffold). No MSW — `vi.fn` stubs are enough for this plan.

**Source spec:** `planning/specs/components/SideBarSpec.md`. Design-token set is inferred from the spec (`--color-bg-*`, `--color-text-*`, `--color-accent-*`, `--color-surface-*`, `--color-border-*`, `--color-icon-*`, `--radius-*`).

**Depends on:**
- Plan 2 — `/auth/session`, `/auth/login`, `/auth/logout` endpoints with `openlia_session` cookie (integration-tested in its own plan; this plan fetches-mocks them).
- Plan 6 — `GET /notifications/unread` (`{total, by_department}`) and `POST /notifications/read` (`{department}`).

**Unblocks:** Plan 9 (Login + Account UI), Plan 10 (Setup Wizard), Plan 11 (Settings), Plan 12 (shared chat components), and every department page plan.

**Out of scope:**
- Department page bodies — Plan 8 renders placeholder `<h1>Secretary</h1>` style pages only. Plans 13–20 replace them.
- Login/Wizard UIs themselves — Plan 8 leaves `/login` and `/setup` as placeholders; Plans 9 + 10 build the real screens.
- File viewer pane — referenced as a reserved layout slot but stays empty until Plan 12.
- Mobile bottom tab bar / hamburger overlay — the spec flags both as responsive behavior, but v1 targets desktop-first. Plan 8 ships only the desktop `>1024 px` layout; responsive variants land in a follow-up.

---

## File Structure

### New (frontend)
```
frontend/
├── postcss.config.js                            # Tailwind + autoprefixer wiring
├── tailwind.config.ts                           # Tailwind theme with CSS-var-backed colors
├── src/
│   ├── styles/
│   │   ├── tokens.css                           # Design tokens as :root CSS custom properties
│   │   └── global.css                           # @tailwind directives + reset + html/body baseline
│   ├── api/
│   │   ├── client.ts                            # fetchJson wrapper (credentials: include)
│   │   ├── client.test.ts                       # unit tests for fetchJson
│   │   ├── auth.ts                              # getSession, login, logout fns
│   │   ├── auth.test.ts
│   │   ├── notifications.ts                     # getUnread, markRead fns
│   │   └── notifications.test.ts
│   ├── auth/
│   │   ├── AuthContext.tsx                      # Provider + useAuth hook
│   │   └── AuthContext.test.tsx
│   ├── router/
│   │   ├── routes.tsx                           # route tree + createBrowserRouter
│   │   ├── ProtectedRoute.tsx                   # redirects to /login if unauthenticated
│   │   └── ProtectedRoute.test.tsx
│   ├── layouts/
│   │   ├── AppLayout.tsx                        # Sidebar + Outlet composition
│   │   └── AppLayout.test.tsx
│   ├── components/
│   │   ├── sidebar/
│   │   │   ├── navData.ts                       # CORE_NAV + DEPARTMENT_NAV + ICON_MAP
│   │   │   ├── NavItem.tsx                      # single nav row (expanded + collapsed modes)
│   │   │   ├── NavItem.test.tsx
│   │   │   ├── useCollapsed.ts                  # localStorage-backed collapse state
│   │   │   ├── useCollapsed.test.ts
│   │   │   ├── useNotificationPoll.ts           # 60s polling + markRead
│   │   │   ├── useNotificationPoll.test.ts
│   │   │   ├── Sidebar.tsx                      # assembled 3-zone component
│   │   │   └── Sidebar.test.tsx
│   │   └── primitives/
│   │       ├── Button.tsx
│   │       ├── Button.test.tsx
│   │       ├── Input.tsx
│   │       ├── Input.test.tsx
│   │       ├── Card.tsx
│   │       └── Card.test.tsx
│   └── pages/                                   # Placeholder page components (one per route)
│       ├── placeholder.tsx                      # <PagePlaceholder title> helper
│       ├── Home.tsx
│       ├── Repository.tsx
│       ├── Settings.tsx
│       ├── Login.tsx
│       ├── Setup.tsx
│       └── departments/
│           ├── Secretary.tsx
│           ├── EquityResearch.tsx
│           ├── EarningsUpdate.tsx
│           ├── MorningBriefing.tsx
│           ├── RetailSentiment.tsx
│           ├── MacroResearch.tsx
│           └── PanicThermometer.tsx
```

### Modified (frontend)
- `frontend/package.json` — add `react-router-dom`, `lucide-react`, `tailwindcss`, `postcss`, `autoprefixer`.
- `frontend/src/App.tsx` — becomes a thin wrapper that composes `AuthProvider` + `RouterProvider`.
- `frontend/src/App.test.tsx` — updated to reflect the new root-level assertions.
- `frontend/src/main.tsx` — imports `./styles/global.css` once at the top.
- `frontend/tsconfig.json` — add `"resolveJsonModule"` is already true; no change expected. Verify `"types"` doesn't drop anything.
- `frontend/vite.config.ts` — no change (Tailwind is picked up automatically via PostCSS).

### Modified (planning)
- `planning/implementation-plans/README.md` — flip Plan 8 row status to **Draft**.
- `planning/projectStructure.md` — add the `frontend/src/{api,auth,router,layouts,components,pages,styles}/` tree (if the file already describes frontend layout, update; if not, append).

---

## Design Rules

These are the invariants every task below respects. Read them once before starting.

1. **TypeScript strict.** Every public function and component has explicit parameter + return types. No `any` leaks — use `unknown` and narrow.
2. **fetchJson is the only network primitive.** All API modules call it. It sets `credentials: "include"` so the `openlia_session` cookie flows, parses JSON, and throws `ApiError` for non-2xx with a typed `status` field. Callers branch on `ApiError.status` (401/404/etc.) — they do not call `fetch` directly.
3. **Four auth states.** `"loading" | "authenticated" | "unauthenticated" | "personal"`. `AuthProvider` derives them from the `GET /auth/session` response:
   - HTTP 200 with `{user}` → `authenticated` (company mode).
   - HTTP 401 → `unauthenticated` (company mode, needs login).
   - HTTP 404 → `personal` (route is unmounted; synthesize a `{id: "local", email: null, role: "admin"}` user).
   - Network error / other → `unauthenticated` so the UI falls back to the login route; log the error.
4. **ProtectedRoute only redirects when status === "unauthenticated".** `loading` renders a bare spinner; `personal` and `authenticated` render children. Never redirect in `loading`.
5. **Router is a single `createBrowserRouter` tree** consumed by `<RouterProvider>`. No nested `<BrowserRouter>` elsewhere. Routes are defined once in `src/router/routes.tsx` so the tree is inspectable.
6. **Design tokens live in `src/styles/tokens.css` as `:root { --color-...: ... }`.** Tailwind's `theme.extend.colors` references them via `var(--color-...)` so utilities like `bg-surface-hover` map to a token. No component imports a hex directly.
7. **Sidebar nav is data-driven.** `navData.ts` exports two arrays (`CORE_NAV`, `DEPARTMENT_NAV`) and an `ICON_MAP` keyed by the spec's string names. Adding a department means editing one array — not touching `Sidebar.tsx`.
8. **Notification polling is owned by one hook.** `useNotificationPoll` runs inside the Sidebar. It exposes `{unreadByDepartment, markRead(department)}`. When the user navigates to a department's route, the Sidebar calls `markRead(id)` once on `location.pathname` change. Polling interval is a constant — `NOTIFICATION_POLL_MS = 60_000`.
9. **localStorage reads are wrapped.** `useCollapsed` tolerates `window.localStorage` being unavailable (SSR / private mode) by falling back to in-memory state. Tests cover both paths.
10. **No MSW yet.** Tests stub `global.fetch` with `vi.fn` + `vi.stubGlobal`. When a task needs multiple sequential responses, `mockResolvedValueOnce` chains cover it. MSW can be introduced later if tests become unwieldy — Plan 8 stays lean.
11. **Placeholder pages share one component.** `PagePlaceholder({title})` renders `<h1>{title}</h1>` inside a main element. Every department's file exports `<PagePlaceholder title="..." />`. Plans 13–20 replace these files wholesale.
12. **Commits per task.** Each task ends with an explicit `git commit`. Keep commit messages under 72 chars in the subject line and use the `feat(frontend): ...` / `chore(frontend): ...` / `test(frontend): ...` conventional prefix.

---

## Task 1: Install runtime + styling dependencies

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/postcss.config.js`
- Create: `frontend/tailwind.config.ts`

- [ ] **Step 1: Add dependencies**

Run inside `frontend/`:

```bash
cd frontend
npm install react-router-dom@^6.26.0 lucide-react@^0.454.0
npm install --save-dev tailwindcss@^3.4.0 postcss@^8.4.0 autoprefixer@^10.4.0
```

Expected: `package.json` gains all five entries, `package-lock.json` updates, `node_modules/` populates.

- [ ] **Step 2: Write `postcss.config.js`**

Create `frontend/postcss.config.js`:

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3: Write `tailwind.config.ts`**

Create `frontend/tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-app": "var(--color-bg-app)",
        "bg-elevated": "var(--color-bg-elevated)",
        "sidebar-bg": "var(--color-sidebar-bg)",
        "surface-hover": "var(--color-surface-hover)",
        "surface-active": "var(--color-surface-active)",
        "accent-primary": "var(--color-accent-primary)",
        "accent-subtle": "var(--color-accent-subtle)",
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-tertiary": "var(--color-text-tertiary)",
        "icon-primary": "var(--color-icon-primary)",
        "border-subtle": "var(--color-border-subtle)",
      },
      borderRadius: {
        md: "var(--radius-md)",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 4: Verify build pipeline sees Tailwind**

Run:

```bash
cd frontend
npx tailwindcss --help
```

Expected: Tailwind CLI prints its usage banner (confirms the package resolved). No file output needed — the Vite dev server will wire PostCSS automatically once `global.css` exists in Task 2.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json \
        frontend/postcss.config.js frontend/tailwind.config.ts
git commit -m "chore(frontend): add react-router, lucide, and tailwind"
```

---

## Task 2: Design tokens + global stylesheet

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/global.css`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Write tokens.css**

Create `frontend/src/styles/tokens.css`:

```css
:root {
  color-scheme: light dark;

  --color-bg-app: #0f1115;
  --color-bg-elevated: #161a22;
  --color-sidebar-bg: #12151c;

  --color-surface-hover: rgba(255, 255, 255, 0.04);
  --color-surface-active: rgba(255, 255, 255, 0.06);

  --color-accent-primary: #7c9cff;
  --color-accent-subtle: rgba(124, 156, 255, 0.12);

  --color-text-primary: #e8eaf0;
  --color-text-secondary: #a8aec0;
  --color-text-tertiary: #6f758a;

  --color-icon-primary: #a8aec0;

  --color-border-subtle: rgba(255, 255, 255, 0.08);

  --radius-md: 6px;
}
```

- [ ] **Step 2: Write global.css**

Create `frontend/src/styles/global.css`:

```css
@import "./tokens.css";

@tailwind base;
@tailwind components;
@tailwind utilities;

html,
body,
#root {
  height: 100%;
}

body {
  margin: 0;
  background-color: var(--color-bg-app);
  color: var(--color-text-primary);
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 3: Import global.css from main.tsx**

Replace `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 4: Run existing tests to make sure nothing regressed**

```bash
cd frontend
npm run test
```

Expected: `App.test.tsx` still passes (it doesn't depend on styling).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/ frontend/src/main.tsx
git commit -m "feat(frontend): add design tokens and global stylesheet"
```

---

## Task 3: API client (`fetchJson` + `ApiError`)

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/client.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/client.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { fetchJson, ApiError } from "./client";

describe("fetchJson", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("parses JSON on 200", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ) as unknown as typeof fetch;

    const body = await fetchJson<{ ok: boolean }>("/x");
    expect(body).toEqual({ ok: true });
  });

  it("sends credentials: include by default", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response("null", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = spy as unknown as typeof fetch;

    await fetchJson("/x");
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("include");
  });

  it("throws ApiError with status on 4xx", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "nope" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    await expect(fetchJson("/x")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });
  });

  it("returns null for 204 No Content", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;

    const body = await fetchJson("/x");
    expect(body).toBeNull();
  });

  it("wraps network failures as ApiError with status 0", async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("Network request failed")) as unknown as typeof fetch;

    await expect(fetchJson("/x")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });
});

export class _Touch extends ApiError {}
```

(The trailing `_Touch` export ensures the type import stays live in strict mode if vitest tree-shakes the import.)

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/api/client.test.ts
```

Expected: FAIL (`client.ts` does not exist).

- [ ] **Step 3: Implement client.ts**

Create `frontend/src/api/client.ts`:

```ts
export class ApiError extends Error {
  public readonly status: number;
  public readonly body: unknown;

  constructor(status: number, message: string, body: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export interface FetchOptions extends Omit<RequestInit, "body"> {
  json?: unknown;
}

export async function fetchJson<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { json, headers, ...rest } = options;

  const init: RequestInit = {
    credentials: "include",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  };

  if (json !== undefined) {
    init.body = JSON.stringify(json);
  }

  let response: Response;
  try {
    response = await fetch(path, init);
  } catch (err) {
    const message = err instanceof Error ? err.message : "network error";
    throw new ApiError(0, message);
  }

  if (response.status === 204) {
    return null as T;
  }

  const contentType = response.headers.get("Content-Type") ?? "";
  const parsedBody = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : null;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `HTTP ${response.status} on ${path}`,
      parsedBody,
    );
  }

  return parsedBody as T;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/api/client.test.ts
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(frontend): add fetchJson api client with ApiError"
```

---

## Task 4: Auth API module (`getSession`, `login`, `logout`)

**Files:**
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/auth.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/auth.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getSession, login, logout } from "./auth";
import { ApiError } from "./client";

describe("auth api", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("getSession returns the user on 200", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          user: { id: "u1", email: "a@x.com", role: "admin" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const user = await getSession();
    expect(user).toEqual({ id: "u1", email: "a@x.com", role: "admin" });
  });

  it("getSession re-throws ApiError on 401/404 so callers can branch", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;

    await expect(getSession()).rejects.toBeInstanceOf(ApiError);
  });

  it("login posts credentials and returns the user", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user: { id: "u1", email: "a", role: "user" } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = spy as unknown as typeof fetch;

    const user = await login({ email: "a", password: "p", persistent: true });
    expect(user.id).toBe("u1");

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/auth/login");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      email: "a",
      password: "p",
      persistent: true,
    });
  });

  it("logout POSTs and resolves on 204", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 })) as unknown as typeof fetch;

    await expect(logout()).resolves.toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/api/auth.test.ts
```

Expected: FAIL (`auth.ts` does not exist).

- [ ] **Step 3: Implement auth.ts**

Create `frontend/src/api/auth.ts`:

```ts
import { fetchJson } from "./client";

export interface AuthUser {
  id: string;
  email: string | null;
  role: "admin" | "user";
}

interface SessionResponse {
  user: AuthUser;
}

export async function getSession(): Promise<AuthUser> {
  const resp = await fetchJson<SessionResponse>("/api/auth/session");
  return resp.user;
}

export interface LoginInput {
  email: string;
  password: string;
  persistent: boolean;
}

export async function login(input: LoginInput): Promise<AuthUser> {
  const resp = await fetchJson<SessionResponse>("/api/auth/login", {
    method: "POST",
    json: input,
  });
  return resp.user;
}

export async function logout(): Promise<null> {
  return fetchJson<null>("/api/auth/logout", { method: "POST" });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/api/auth.test.ts
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/api/auth.test.ts
git commit -m "feat(frontend): add auth api (getSession, login, logout)"
```

---

## Task 5: Notifications API module (`getUnread`, `markRead`)

**Files:**
- Create: `frontend/src/api/notifications.ts`
- Create: `frontend/src/api/notifications.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/notifications.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getUnread, markRead } from "./notifications";

describe("notifications api", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("getUnread returns total + by_department", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          total: 3,
          by_department: { morning_briefing: 2, earnings_update: 1 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const resp = await getUnread();
    expect(resp.total).toBe(3);
    expect(resp.by_department.morning_briefing).toBe(2);
  });

  it("markRead POSTs the department", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    global.fetch = spy as unknown as typeof fetch;

    await markRead("morning_briefing");

    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/notifications/read");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      department: "morning_briefing",
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/api/notifications.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement notifications.ts**

Create `frontend/src/api/notifications.ts`:

```ts
import { fetchJson } from "./client";

export interface UnreadResponse {
  total: number;
  by_department: Record<string, number>;
}

export async function getUnread(): Promise<UnreadResponse> {
  return fetchJson<UnreadResponse>("/api/notifications/unread");
}

export async function markRead(department: string): Promise<null> {
  return fetchJson<null>("/api/notifications/read", {
    method: "POST",
    json: { department },
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/api/notifications.test.ts
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/notifications.ts frontend/src/api/notifications.test.ts
git commit -m "feat(frontend): add notifications api (getUnread, markRead)"
```

---

## Task 6: `AuthContext` + `useAuth` hook

**Files:**
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/auth/AuthContext.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/auth/AuthContext.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthContext";
import { ApiError } from "../api/client";

function Probe() {
  const { status, user } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user-id">{user?.id ?? ""}</span>
    </div>
  );
}

describe("AuthProvider", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("200 → authenticated with user", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user: { id: "u1", email: "a", role: "admin" } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );
    expect(screen.getByTestId("user-id").textContent).toBe("u1");
  });

  it("401 → unauthenticated", async () => {
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
    expect(screen.getByTestId("user-id").textContent).toBe("");
  });

  it("404 → personal mode with synthetic local user", async () => {
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
    expect(screen.getByTestId("user-id").textContent).toBe("local");
  });

  it("throws when useAuth is called outside of a provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Probe />)).toThrow(/useAuth must be used inside AuthProvider/);
    spy.mockRestore();
  });

  it("login() updates state to authenticated after success", async () => {
    const fetchMock = vi
      .fn()
      // Initial getSession → 401
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      // login() → 200
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user: { id: "u2", email: "b", role: "user" } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    global.fetch = fetchMock as unknown as typeof fetch;

    function ProbeWithButton() {
      const { status, login } = useAuth();
      return (
        <div>
          <span data-testid="status">{status}</span>
          <button
            onClick={() => {
              void login({ email: "b", password: "p", persistent: false });
            }}
          >
            go
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <ProbeWithButton />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );

    await act(async () => {
      screen.getByRole("button", { name: "go" }).click();
    });

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated"),
    );
  });

  it("treats unexpected ApiError like unauthenticated", async () => {
    global.fetch = vi.fn().mockRejectedValue(new ApiError(500, "boom")) as unknown as typeof fetch;

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("unauthenticated"),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/auth/AuthContext.test.tsx
```

Expected: FAIL (`AuthContext.tsx` does not exist).

- [ ] **Step 3: Implement AuthContext.tsx**

Create `frontend/src/auth/AuthContext.tsx`:

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
import {
  getSession,
  login as loginRequest,
  logout as logoutRequest,
  type AuthUser,
  type LoginInput,
} from "../api/auth";
import { ApiError } from "../api/client";

export type AuthStatus =
  | "loading"
  | "authenticated"
  | "unauthenticated"
  | "personal";

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  login: (input: LoginInput) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const LOCAL_USER: AuthUser = { id: "local", email: null, role: "admin" };

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): JSX.Element {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      const fetched = await getSession();
      setUser(fetched);
      setStatus("authenticated");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setUser(LOCAL_USER);
        setStatus("personal");
        return;
      }
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const login = useCallback(
    async (input: LoginInput): Promise<void> => {
      const fetched = await loginRequest(input);
      setUser(fetched);
      setStatus("authenticated");
    },
    [],
  );

  const logout = useCallback(async (): Promise<void> => {
    await logoutRequest();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, refresh }),
    [status, user, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/auth/AuthContext.test.tsx
```

Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx frontend/src/auth/AuthContext.test.tsx
git commit -m "feat(frontend): add AuthProvider with 4-state machine"
```

---

## Task 7: Placeholder page component + per-route pages

**Files:**
- Create: `frontend/src/pages/placeholder.tsx`
- Create: `frontend/src/pages/Home.tsx`
- Create: `frontend/src/pages/Repository.tsx`
- Create: `frontend/src/pages/Settings.tsx`
- Create: `frontend/src/pages/Login.tsx`
- Create: `frontend/src/pages/Setup.tsx`
- Create: `frontend/src/pages/departments/Secretary.tsx`
- Create: `frontend/src/pages/departments/EquityResearch.tsx`
- Create: `frontend/src/pages/departments/EarningsUpdate.tsx`
- Create: `frontend/src/pages/departments/MorningBriefing.tsx`
- Create: `frontend/src/pages/departments/RetailSentiment.tsx`
- Create: `frontend/src/pages/departments/MacroResearch.tsx`
- Create: `frontend/src/pages/departments/PanicThermometer.tsx`

- [ ] **Step 1: Write placeholder.tsx**

Create `frontend/src/pages/placeholder.tsx`:

```tsx
interface PagePlaceholderProps {
  title: string;
}

export function PagePlaceholder({ title }: PagePlaceholderProps): JSX.Element {
  return (
    <section className="p-8">
      <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Page body arrives in a later plan.
      </p>
    </section>
  );
}
```

- [ ] **Step 2: Write the 12 page files**

Each file is two lines. Create them in bulk:

`Home.tsx`:

```tsx
import { PagePlaceholder } from "./placeholder";
export default function Home(): JSX.Element { return <PagePlaceholder title="Home" />; }
```

`Repository.tsx`:

```tsx
import { PagePlaceholder } from "./placeholder";
export default function Repository(): JSX.Element { return <PagePlaceholder title="Repository" />; }
```

`Settings.tsx`:

```tsx
import { PagePlaceholder } from "./placeholder";
export default function Settings(): JSX.Element { return <PagePlaceholder title="Settings" />; }
```

`Login.tsx`:

```tsx
import { PagePlaceholder } from "./placeholder";
export default function Login(): JSX.Element { return <PagePlaceholder title="Login" />; }
```

`Setup.tsx`:

```tsx
import { PagePlaceholder } from "./placeholder";
export default function Setup(): JSX.Element { return <PagePlaceholder title="Setup Wizard" />; }
```

`departments/Secretary.tsx`:

```tsx
import { PagePlaceholder } from "../placeholder";
export default function Secretary(): JSX.Element { return <PagePlaceholder title="Secretary" />; }
```

`departments/EquityResearch.tsx`:

```tsx
import { PagePlaceholder } from "../placeholder";
export default function EquityResearch(): JSX.Element { return <PagePlaceholder title="Equity Research" />; }
```

`departments/EarningsUpdate.tsx`:

```tsx
import { PagePlaceholder } from "../placeholder";
export default function EarningsUpdate(): JSX.Element { return <PagePlaceholder title="Earnings Update" />; }
```

`departments/MorningBriefing.tsx`:

```tsx
import { PagePlaceholder } from "../placeholder";
export default function MorningBriefing(): JSX.Element { return <PagePlaceholder title="Morning Briefing" />; }
```

`departments/RetailSentiment.tsx`:

```tsx
import { PagePlaceholder } from "../placeholder";
export default function RetailSentiment(): JSX.Element { return <PagePlaceholder title="Retail Sentiment" />; }
```

`departments/MacroResearch.tsx`:

```tsx
import { PagePlaceholder } from "../placeholder";
export default function MacroResearch(): JSX.Element { return <PagePlaceholder title="Macro Research" />; }
```

`departments/PanicThermometer.tsx`:

```tsx
import { PagePlaceholder } from "../placeholder";
export default function PanicThermometer(): JSX.Element { return <PagePlaceholder title="Panic Thermometer" />; }
```

- [ ] **Step 3: Run typecheck**

```bash
cd frontend
npm run lint
```

Expected: PASS. No tests yet — the router task (Task 9) will exercise them.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/
git commit -m "feat(frontend): add placeholder pages for every route"
```

---

## Task 8: Sidebar nav data (`navData.ts`)

**Files:**
- Create: `frontend/src/components/sidebar/navData.ts`

- [ ] **Step 1: Create navData.ts**

This is a pure data module — tests come in Task 10 when `NavItem` renders it.

Create `frontend/src/components/sidebar/navData.ts`:

```ts
import {
  Home,
  FolderOpen,
  MessageSquare,
  TrendingUp,
  ClipboardList,
  Sun,
  BarChart2,
  Globe,
  Thermometer,
  type LucideIcon,
} from "lucide-react";

export interface NavEntry {
  id: string;
  label: string;
  icon: LucideIcon;
  path: string;
  /** Department id used to correlate with /notifications/unread.by_department. null for core pages. */
  departmentId: string | null;
}

export const CORE_NAV: readonly NavEntry[] = [
  { id: "home", label: "Home", icon: Home, path: "/", departmentId: null },
  {
    id: "repository",
    label: "Repository",
    icon: FolderOpen,
    path: "/repository",
    departmentId: null,
  },
];

export const DEPARTMENT_NAV: readonly NavEntry[] = [
  {
    id: "secretary",
    label: "Secretary",
    icon: MessageSquare,
    path: "/secretary",
    departmentId: "secretary",
  },
  {
    id: "equity_research",
    label: "Equity Research",
    icon: TrendingUp,
    path: "/equity-research",
    departmentId: "equity_research",
  },
  {
    id: "earnings_update",
    label: "Earnings Update",
    icon: ClipboardList,
    path: "/earnings-update",
    departmentId: "earnings_update",
  },
  {
    id: "morning_briefing",
    label: "Morning Briefing",
    icon: Sun,
    path: "/morning-briefing",
    departmentId: "morning_briefing",
  },
  {
    id: "retail_sentiment",
    label: "Retail Sentiment",
    icon: BarChart2,
    path: "/retail-sentiment",
    departmentId: "retail_sentiment",
  },
  {
    id: "macro_research",
    label: "Macro Research",
    icon: Globe,
    path: "/macro-research",
    departmentId: "macro_research",
  },
  {
    id: "panic_thermometer",
    label: "Panic Thermometer",
    icon: Thermometer,
    path: "/panic-thermometer",
    departmentId: "panic_thermometer",
  },
];
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/sidebar/navData.ts
git commit -m "feat(frontend): add sidebar nav data (core + departments)"
```

---

## Task 9: `useCollapsed` hook (localStorage-backed)

**Files:**
- Create: `frontend/src/components/sidebar/useCollapsed.ts`
- Create: `frontend/src/components/sidebar/useCollapsed.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/sidebar/useCollapsed.test.ts`:

```ts
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCollapsed, COLLAPSED_STORAGE_KEY } from "./useCollapsed";

describe("useCollapsed", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("defaults to false when storage is empty", () => {
    const { result } = renderHook(() => useCollapsed());
    expect(result.current[0]).toBe(false);
  });

  it("reads persisted value on mount", () => {
    window.localStorage.setItem(COLLAPSED_STORAGE_KEY, "true");
    const { result } = renderHook(() => useCollapsed());
    expect(result.current[0]).toBe(true);
  });

  it("persists value on toggle", () => {
    const { result } = renderHook(() => useCollapsed());
    act(() => result.current[1](true));
    expect(window.localStorage.getItem(COLLAPSED_STORAGE_KEY)).toBe("true");
    expect(result.current[0]).toBe(true);
  });

  it("tolerates localStorage throwing (private mode)", () => {
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("QuotaExceeded");
      });

    const { result } = renderHook(() => useCollapsed());
    act(() => result.current[1](true));
    expect(result.current[0]).toBe(true);
    expect(setItem).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/components/sidebar/useCollapsed.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement useCollapsed.ts**

Create `frontend/src/components/sidebar/useCollapsed.ts`:

```ts
import { useCallback, useState } from "react";

export const COLLAPSED_STORAGE_KEY = "sidebar_collapsed";

function readInitial(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function useCollapsed(): [boolean, (next: boolean) => void] {
  const [collapsed, setCollapsed] = useState<boolean>(readInitial);

  const update = useCallback((next: boolean) => {
    setCollapsed(next);
    try {
      window.localStorage.setItem(COLLAPSED_STORAGE_KEY, String(next));
    } catch {
      // swallow — in-memory state is the source of truth
    }
  }, []);

  return [collapsed, update];
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/components/sidebar/useCollapsed.test.ts
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/sidebar/useCollapsed.ts \
        frontend/src/components/sidebar/useCollapsed.test.ts
git commit -m "feat(frontend): add localStorage-backed useCollapsed hook"
```

---

## Task 10: `NavItem` component

**Files:**
- Create: `frontend/src/components/sidebar/NavItem.tsx`
- Create: `frontend/src/components/sidebar/NavItem.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/sidebar/NavItem.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Home } from "lucide-react";
import { NavItem } from "./NavItem";

function renderAt(route: string, ui: React.ReactElement) {
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>);
}

describe("NavItem", () => {
  it("renders label in expanded mode and marks active on matching path", () => {
    renderAt(
      "/repository",
      <NavItem
        label="Repository"
        icon={Home}
        path="/repository"
        collapsed={false}
        hasUnread={false}
      />,
    );
    const link = screen.getByRole("link", { name: /repository/i });
    expect(link.getAttribute("aria-current")).toBe("page");
  });

  it("hides label and exposes aria-label in collapsed mode", () => {
    renderAt(
      "/home",
      <NavItem
        label="Home"
        icon={Home}
        path="/"
        collapsed={true}
        hasUnread={false}
      />,
    );
    expect(screen.queryByText("Home")).toBeNull();
    expect(screen.getByRole("link")).toHaveAttribute("aria-label", "Home");
  });

  it("renders a notification dot only when hasUnread is true", () => {
    const { rerender } = renderAt(
      "/",
      <NavItem
        label="Morning Briefing"
        icon={Home}
        path="/morning-briefing"
        collapsed={false}
        hasUnread={false}
      />,
    );
    expect(screen.queryByTestId("nav-item-dot")).toBeNull();

    rerender(
      <MemoryRouter initialEntries={["/"]}>
        <NavItem
          label="Morning Briefing"
          icon={Home}
          path="/morning-briefing"
          collapsed={false}
          hasUnread={true}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("nav-item-dot")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/components/sidebar/NavItem.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement NavItem.tsx**

Create `frontend/src/components/sidebar/NavItem.tsx`:

```tsx
import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

export interface NavItemProps {
  label: string;
  icon: LucideIcon;
  path: string;
  collapsed: boolean;
  hasUnread: boolean;
}

export function NavItem({
  label,
  icon: Icon,
  path,
  collapsed,
  hasUnread,
}: NavItemProps): JSX.Element {
  return (
    <NavLink
      to={path}
      end={path === "/"}
      aria-label={collapsed ? label : undefined}
      className={({ isActive }) =>
        [
          "relative flex items-center gap-[10px] rounded-md px-2 py-[10px] w-full",
          "transition-colors duration-[120ms]",
          collapsed ? "justify-center" : "",
          isActive
            ? "bg-accent-subtle text-text-primary"
            : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
        ]
          .filter(Boolean)
          .join(" ")
      }
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            <span
              aria-hidden="true"
              className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-accent-primary"
            />
          ) : null}
          <span className="relative inline-flex">
            <Icon
              size={18}
              strokeWidth={1.5}
              className={isActive ? "text-accent-primary" : "text-icon-primary"}
            />
            {hasUnread ? (
              <span
                data-testid="nav-item-dot"
                className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-accent-primary"
              />
            ) : null}
          </span>
          {collapsed ? null : (
            <span className="text-sm font-medium truncate">{label}</span>
          )}
        </>
      )}
    </NavLink>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/components/sidebar/NavItem.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/sidebar/NavItem.tsx \
        frontend/src/components/sidebar/NavItem.test.tsx
git commit -m "feat(frontend): add NavItem with active state and unread dot"
```

---

## Task 11: `useNotificationPoll` hook

**Files:**
- Create: `frontend/src/components/sidebar/useNotificationPoll.ts`
- Create: `frontend/src/components/sidebar/useNotificationPoll.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/sidebar/useNotificationPoll.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import {
  useNotificationPoll,
  NOTIFICATION_POLL_MS,
} from "./useNotificationPoll";

describe("useNotificationPoll", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    global.fetch = originalFetch;
  });

  it("fetches unread on mount and exposes by_department map", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 2, by_department: { morning_briefing: 2 } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const { result } = renderHook(() => useNotificationPoll());

    await vi.waitFor(() => {
      expect(result.current.unreadByDepartment.morning_briefing).toBe(2);
    });
  });

  it("polls again after NOTIFICATION_POLL_MS", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    global.fetch = spy as unknown as typeof fetch;

    renderHook(() => useNotificationPoll());

    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(1));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NOTIFICATION_POLL_MS);
    });

    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
  });

  it("markRead POSTs and refreshes the counts", async () => {
    const responses = [
      new Response(
        JSON.stringify({ total: 1, by_department: { morning_briefing: 1 } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
      new Response(null, { status: 204 }), // markRead
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ];
    const spy = vi.fn().mockImplementation(() => {
      const next = responses.shift();
      return Promise.resolve(next ?? new Response(null, { status: 500 }));
    });
    global.fetch = spy as unknown as typeof fetch;

    const { result } = renderHook(() => useNotificationPoll());

    await vi.waitFor(() =>
      expect(result.current.unreadByDepartment.morning_briefing).toBe(1),
    );

    await act(async () => {
      await result.current.markRead("morning_briefing");
    });

    await vi.waitFor(() =>
      expect(result.current.unreadByDepartment.morning_briefing ?? 0).toBe(0),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/components/sidebar/useNotificationPoll.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement useNotificationPoll.ts**

Create `frontend/src/components/sidebar/useNotificationPoll.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getUnread,
  markRead as markReadApi,
  type UnreadResponse,
} from "../../api/notifications";

export const NOTIFICATION_POLL_MS = 60_000;

export interface NotificationPollResult {
  unreadByDepartment: Record<string, number>;
  markRead: (department: string) => Promise<void>;
  refresh: () => Promise<void>;
}

export function useNotificationPoll(): NotificationPollResult {
  const [state, setState] = useState<Record<string, number>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const apply = useCallback((resp: UnreadResponse) => {
    setState(resp.by_department);
  }, []);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      const resp = await getUnread();
      apply(resp);
    } catch {
      // swallow — next tick will try again
    }
  }, [apply]);

  const markRead = useCallback(
    async (department: string): Promise<void> => {
      try {
        await markReadApi(department);
      } catch {
        // still refresh; server is authoritative
      }
      await refresh();
    },
    [refresh],
  );

  useEffect(() => {
    let cancelled = false;

    const tick = async (): Promise<void> => {
      await refresh();
      if (cancelled) return;
      timer.current = setTimeout(tick, NOTIFICATION_POLL_MS);
    };

    void tick();

    return () => {
      cancelled = true;
      if (timer.current !== null) {
        clearTimeout(timer.current);
        timer.current = null;
      }
    };
  }, [refresh]);

  return { unreadByDepartment: state, markRead, refresh };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/components/sidebar/useNotificationPoll.test.ts
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/sidebar/useNotificationPoll.ts \
        frontend/src/components/sidebar/useNotificationPoll.test.ts
git commit -m "feat(frontend): add 60s notification polling hook"
```

---

## Task 12: Assembled `Sidebar` component

**Files:**
- Create: `frontend/src/components/sidebar/Sidebar.tsx`
- Create: `frontend/src/components/sidebar/Sidebar.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/sidebar/Sidebar.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "./Sidebar";

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders every core and department link with its accessible name", async () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /repository/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /secretary/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /equity research/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /panic thermometer/i })).toBeInTheDocument();
  });

  it("toggles collapsed state via the toggle button", async () => {
    renderAt("/");
    const toggle = screen.getByRole("button", { name: /collapse sidebar/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await act(async () => {
      toggle.click();
    });
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /expand sidebar/i }),
      ).toHaveAttribute("aria-expanded", "false"),
    );
  });

  it("shows an unread dot on the department with a positive count", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 1, by_department: { morning_briefing: 1 } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    renderAt("/");
    await waitFor(() => {
      const link = screen.getByRole("link", { name: /morning briefing/i });
      expect(link.querySelector('[data-testid="nav-item-dot"]')).not.toBeNull();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/components/sidebar/Sidebar.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement Sidebar.tsx**

Create `frontend/src/components/sidebar/Sidebar.tsx`:

```tsx
import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { ChevronLeft, ChevronRight, Settings, User } from "lucide-react";
import { CORE_NAV, DEPARTMENT_NAV } from "./navData";
import { NavItem } from "./NavItem";
import { useCollapsed } from "./useCollapsed";
import { useNotificationPoll } from "./useNotificationPoll";

export function Sidebar(): JSX.Element {
  const [collapsed, setCollapsed] = useCollapsed();
  const { unreadByDepartment, markRead } = useNotificationPoll();
  const location = useLocation();

  useEffect(() => {
    const match = DEPARTMENT_NAV.find((entry) => entry.path === location.pathname);
    if (match?.departmentId && (unreadByDepartment[match.departmentId] ?? 0) > 0) {
      void markRead(match.departmentId);
    }
  }, [location.pathname, markRead, unreadByDepartment]);

  return (
    <nav
      aria-label="Main navigation"
      className={[
        "flex flex-col h-screen bg-sidebar-bg border-r border-border-subtle",
        "transition-[width] duration-200 ease-in-out",
        collapsed ? "w-[60px]" : "w-[240px]",
      ].join(" ")}
    >
      <header
        className={[
          "h-14 flex items-center border-b border-border-subtle flex-shrink-0",
          collapsed ? "justify-center" : "justify-between px-4",
        ].join(" ")}
      >
        {collapsed ? null : (
          <span className="text-xl font-semibold tracking-tight text-text-primary">
            LIA
          </span>
        )}
        <button
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed(!collapsed)}
          className="w-7 h-7 rounded-md text-text-secondary hover:bg-surface-hover hover:text-text-primary inline-flex items-center justify-center"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {CORE_NAV.map((entry) => (
          <NavItem
            key={entry.id}
            label={entry.label}
            icon={entry.icon}
            path={entry.path}
            collapsed={collapsed}
            hasUnread={false}
          />
        ))}

        {collapsed ? (
          <div className="my-2 h-px bg-border-subtle" aria-hidden="true" />
        ) : (
          <div
            role="separator"
            className="px-2 pt-4 pb-1 text-xs font-medium uppercase tracking-[0.04em] text-text-tertiary"
          >
            Departments
          </div>
        )}

        {DEPARTMENT_NAV.map((entry) => (
          <NavItem
            key={entry.id}
            label={entry.label}
            icon={entry.icon}
            path={entry.path}
            collapsed={collapsed}
            hasUnread={
              entry.departmentId !== null &&
              (unreadByDepartment[entry.departmentId] ?? 0) > 0
            }
          />
        ))}
      </div>

      <footer className="flex-shrink-0 border-t border-border-subtle px-2 py-2 space-y-0.5">
        <NavItem
          label="Settings"
          icon={Settings}
          path="/settings"
          collapsed={collapsed}
          hasUnread={false}
        />
        <div
          className={[
            "flex items-center gap-[10px] px-2 py-[10px]",
            collapsed ? "justify-center" : "",
          ].join(" ")}
        >
          <span className="w-[18px] h-[18px] rounded-full bg-accent-primary inline-flex items-center justify-center">
            <User size={11} className="text-white" strokeWidth={1.5} />
          </span>
          {collapsed ? null : (
            <span className="text-sm text-text-secondary truncate">Account</span>
          )}
        </div>
      </footer>
    </nav>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/components/sidebar/Sidebar.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/sidebar/Sidebar.tsx \
        frontend/src/components/sidebar/Sidebar.test.tsx
git commit -m "feat(frontend): assemble Sidebar shell with notifications"
```

---

## Task 13: Base primitives — `Button`, `Input`, `Card`

**Files:**
- Create: `frontend/src/components/primitives/Button.tsx`
- Create: `frontend/src/components/primitives/Button.test.tsx`
- Create: `frontend/src/components/primitives/Input.tsx`
- Create: `frontend/src/components/primitives/Input.test.tsx`
- Create: `frontend/src/components/primitives/Card.tsx`
- Create: `frontend/src/components/primitives/Card.test.tsx`

- [ ] **Step 1: Write Button test**

Create `frontend/src/components/primitives/Button.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children and fires onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    screen.getByRole("button", { name: "Save" }).click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("applies primary and secondary variants", () => {
    const { rerender } = render(<Button variant="primary">A</Button>);
    expect(screen.getByRole("button").className).toContain("bg-accent-primary");
    rerender(<Button variant="secondary">A</Button>);
    expect(screen.getByRole("button").className).toContain("bg-surface-hover");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Implement Button.tsx**

Create `frontend/src/components/primitives/Button.tsx`:

```tsx
import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({
  variant = "primary",
  className,
  type = "button",
  ...rest
}: ButtonProps): JSX.Element {
  const base =
    "inline-flex items-center justify-center h-9 px-3 rounded-md text-sm font-medium transition-colors duration-[120ms] disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClass =
    variant === "primary"
      ? "bg-accent-primary text-white hover:opacity-90"
      : "bg-surface-hover text-text-primary hover:bg-surface-active";
  return (
    <button
      type={type}
      className={[base, variantClass, className ?? ""].join(" ")}
      {...rest}
    />
  );
}
```

- [ ] **Step 3: Write Input test**

Create `frontend/src/components/primitives/Input.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Input } from "./Input";

describe("Input", () => {
  it("renders with a label and links ids via htmlFor/id", () => {
    render(<Input label="Email" id="email" defaultValue="a@b.com" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveValue("a@b.com");
    expect(input.id).toBe("email");
  });

  it("shows an error message when provided", () => {
    render(<Input label="Email" id="email" error="required" />);
    expect(screen.getByText("required")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });
});
```

- [ ] **Step 4: Implement Input.tsx**

Create `frontend/src/components/primitives/Input.tsx`:

```tsx
import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  id: string;
  error?: string;
}

export function Input({
  label,
  id,
  error,
  className,
  ...rest
}: InputProps): JSX.Element {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm text-text-secondary">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? "true" : undefined}
        className={[
          "h-9 px-3 rounded-md bg-bg-elevated border border-border-subtle text-sm text-text-primary",
          "focus:outline-none focus:border-accent-primary",
          className ?? "",
        ].join(" ")}
        {...rest}
      />
      {error ? (
        <span className="text-xs text-red-400" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Write Card test**

Create `frontend/src/components/primitives/Card.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card } from "./Card";

describe("Card", () => {
  it("renders children inside a region", () => {
    render(<Card aria-label="section"><p>hi</p></Card>);
    expect(screen.getByRole("region", { name: "section" })).toContainHTML("<p>hi</p>");
  });
});
```

- [ ] **Step 6: Implement Card.tsx**

Create `frontend/src/components/primitives/Card.tsx`:

```tsx
import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

export function Card({ children, className, ...rest }: CardProps): JSX.Element {
  return (
    <section
      role="region"
      className={[
        "bg-bg-elevated border border-border-subtle rounded-md p-4",
        className ?? "",
      ].join(" ")}
      {...rest}
    >
      {children}
    </section>
  );
}
```

- [ ] **Step 7: Run all primitive tests**

```bash
cd frontend
npm run test -- src/components/primitives
```

Expected: PASS (6 tests total — 3 Button, 2 Input, 1 Card).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/primitives/
git commit -m "feat(frontend): add Button, Input, Card primitives"
```

---

## Task 14: `ProtectedRoute`

**Files:**
- Create: `frontend/src/router/ProtectedRoute.tsx`
- Create: `frontend/src/router/ProtectedRoute.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/router/ProtectedRoute.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

function wrap(initialRoute: string) {
  return (
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<p>Login page</p>} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <p>Protected content</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("redirects to /login when unauthenticated", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 })) as unknown as typeof fetch;

    render(wrap("/"));

    await waitFor(() =>
      expect(screen.getByText("Login page")).toBeInTheDocument(),
    );
  });

  it("renders children when authenticated", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user: { id: "u1", email: "a", role: "admin" } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    render(wrap("/"));

    await waitFor(() =>
      expect(screen.getByText("Protected content")).toBeInTheDocument(),
    );
  });

  it("renders children in personal mode (404 from /auth/session)", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 404 })) as unknown as typeof fetch;

    render(wrap("/"));

    await waitFor(() =>
      expect(screen.getByText("Protected content")).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/router/ProtectedRoute.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement ProtectedRoute.tsx**

Create `frontend/src/router/ProtectedRoute.tsx`:

```tsx
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

interface ProtectedRouteProps {
  children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps): JSX.Element {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div role="status" aria-live="polite" className="p-8 text-text-secondary">
        Loading...
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/router/ProtectedRoute.test.tsx
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/ProtectedRoute.tsx \
        frontend/src/router/ProtectedRoute.test.tsx
git commit -m "feat(frontend): add ProtectedRoute with loading/personal/auth states"
```

---

## Task 15: `AppLayout`

**Files:**
- Create: `frontend/src/layouts/AppLayout.tsx`
- Create: `frontend/src/layouts/AppLayout.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/layouts/AppLayout.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { AppLayout } from "./AppLayout";

describe("AppLayout", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user: { id: "local", email: null, role: "admin" } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;
    // Seed the notifications fetch too — the Sidebar will call it.
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  });

  it("renders the Sidebar and the outlet content side by side", async () => {
    render(
      <MemoryRouter initialEntries={["/home-route"]}>
        <AuthProvider>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/home-route" element={<p>Body</p>} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("navigation", { name: /main navigation/i }),
      ).toBeInTheDocument();
      expect(screen.getByText("Body")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend
npm run test -- src/layouts/AppLayout.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement AppLayout.tsx**

Create `frontend/src/layouts/AppLayout.tsx`:

```tsx
import { Outlet } from "react-router-dom";
import { Sidebar } from "../components/sidebar/Sidebar";

export function AppLayout(): JSX.Element {
  return (
    <div className="flex h-screen w-full bg-bg-app text-text-primary">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend
npm run test -- src/layouts/AppLayout.test.tsx
```

Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layouts/AppLayout.tsx frontend/src/layouts/AppLayout.test.tsx
git commit -m "feat(frontend): add AppLayout composing Sidebar and Outlet"
```

---

## Task 16: Router definition (`routes.tsx`) + App root wiring

**Files:**
- Create: `frontend/src/router/routes.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

- [ ] **Step 1: Create routes.tsx**

Create `frontend/src/router/routes.tsx`:

```tsx
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import Home from "../pages/Home";
import Repository from "../pages/Repository";
import Settings from "../pages/Settings";
import Login from "../pages/Login";
import Setup from "../pages/Setup";
import Secretary from "../pages/departments/Secretary";
import EquityResearch from "../pages/departments/EquityResearch";
import EarningsUpdate from "../pages/departments/EarningsUpdate";
import MorningBriefing from "../pages/departments/MorningBriefing";
import RetailSentiment from "../pages/departments/RetailSentiment";
import MacroResearch from "../pages/departments/MacroResearch";
import PanicThermometer from "../pages/departments/PanicThermometer";

export const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  { path: "/setup", element: <Setup /> },
  {
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: "/", element: <Navigate to="/secretary" replace /> },
      { path: "/repository", element: <Repository /> },
      { path: "/settings", element: <Settings /> },
      { path: "/home", element: <Home /> },
      { path: "/secretary", element: <Secretary /> },
      { path: "/equity-research", element: <EquityResearch /> },
      { path: "/earnings-update", element: <EarningsUpdate /> },
      { path: "/morning-briefing", element: <MorningBriefing /> },
      { path: "/retail-sentiment", element: <RetailSentiment /> },
      { path: "/macro-research", element: <MacroResearch /> },
      { path: "/panic-thermometer", element: <PanicThermometer /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
```

- [ ] **Step 2: Rewrite App.tsx**

Replace `frontend/src/App.tsx`:

```tsx
import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { router } from "./router/routes";

export default function App(): JSX.Element {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
```

- [ ] **Step 3: Update App.test.tsx**

Replace `frontend/src/App.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    const sessionOk = new Response(
      JSON.stringify({ user: { id: "u1", email: "a", role: "admin" } }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    const unreadOk = new Response(
      JSON.stringify({ total: 0, by_department: {} }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    global.fetch = vi
      .fn()
      .mockImplementation((input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes("/auth/session")) return Promise.resolve(sessionOk.clone());
        if (url.includes("/notifications/unread"))
          return Promise.resolve(unreadOk.clone());
        return Promise.resolve(new Response(null, { status: 204 }));
      }) as unknown as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("boots with the Sidebar visible when authenticated", async () => {
    render(<App />);
    await waitFor(() => {
      expect(
        screen.getByRole("navigation", { name: /main navigation/i }),
      ).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 4: Run the entire test suite**

```bash
cd frontend
npm run test
```

Expected: all tests pass across every module introduced in Tasks 1–16.

- [ ] **Step 5: Run typecheck**

```bash
cd frontend
npm run lint
```

Expected: `tsc --noEmit` reports zero errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/router/routes.tsx frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): wire router with AuthProvider and AppLayout"
```

---

## Task 17: Dev-server smoke test

**Files:** none. This is a manual verification pass per CLAUDE.md's rule: *"For UI or frontend changes, start the dev server and use the feature in a browser before reporting the task as complete."*

- [ ] **Step 1: Start the Vite dev server**

```bash
cd frontend
npm run dev
```

Expected: server binds on `http://localhost:5173` with the `/api` proxy pointed at `http://localhost:8000`.

- [ ] **Step 2: Open the app in a browser**

Visit `http://localhost:5173/`.

Because Plan 2's auth endpoints are not running, `fetch('/api/auth/session')` will fail — treated as `unauthenticated` → the app redirects to `/login` and the Login placeholder renders. This is the expected v1 behavior without a backend.

- [ ] **Step 3: Verify the Sidebar renders when bypassed**

Temporarily stub the auth response: in the browser devtools console, run

```js
window.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : input.toString();
  if (url.includes("/auth/session"))
    return new Response(JSON.stringify({ user: { id: "u1", email: "a", role: "admin" } }),
      { status: 200, headers: { "Content-Type": "application/json" } });
  if (url.includes("/notifications/unread"))
    return new Response(JSON.stringify({ total: 1, by_department: { morning_briefing: 1 } }),
      { status: 200, headers: { "Content-Type": "application/json" } });
  return new Response(null, { status: 204 });
};
```

Then navigate to `/` — the layout should render with the Sidebar on the left, department links listed, and a dot on Morning Briefing. Clicking Morning Briefing removes the dot (`markRead` fires).

- [ ] **Step 4: Verify collapse persistence**

Click the chevron to collapse the Sidebar. Refresh the page. Expected: it stays collapsed (localStorage).

- [ ] **Step 5: Stop the dev server**

`Ctrl-C` in the terminal. No commit for this task — it's a verification step.

---

## Task 18: Update roadmap + project structure doc

**Files:**
- Modify: `planning/implementation-plans/README.md`
- Modify: `planning/projectStructure.md`

- [ ] **Step 1: Flip Plan 8 row to Draft**

In `planning/implementation-plans/README.md` replace the Plan 8 row:

```markdown
| 8 | 4 | Frontend shell (routing, auth context, layout, design tokens) | Not started | — |
```

with:

```markdown
| 8 | 4 | Frontend shell (routing, auth context, layout, design tokens) | Draft | `2026-04-17-phase-8-frontend-shell.md` |
```

- [ ] **Step 2: Update projectStructure.md**

Open `planning/projectStructure.md`. Find the section that describes the `frontend/src/` layout. If the section lists only `App.tsx`, `main.tsx`, etc., replace it with this tree so the structure matches what Plan 8 produced:

```
frontend/src/
├── api/                       # fetchJson + typed endpoint modules (auth, notifications, ...)
├── auth/                      # AuthProvider + useAuth + 4-state status machine
├── router/                    # createBrowserRouter tree, ProtectedRoute
├── layouts/                   # AppLayout (Sidebar + Outlet)
├── components/
│   ├── sidebar/               # Sidebar shell, NavItem, useCollapsed, useNotificationPoll, navData
│   └── primitives/            # Button, Input, Card
├── pages/                     # Placeholder page components; replaced by Plans 13–20
│   └── departments/
├── styles/                    # tokens.css + global.css (Tailwind entry)
├── App.tsx
└── main.tsx
```

If the file has no frontend section yet, append a new one titled "Frontend layout (Plan 8+)".

- [ ] **Step 3: Commit**

```bash
git add planning/implementation-plans/README.md planning/projectStructure.md
git commit -m "docs(plan): flip plan 8 to draft and refresh frontend structure"
```

---

## Notes for the implementer

### Why vi.fn over MSW
The scaffold already depends on `jsdom` + testing-library. Introducing MSW ($ ≈ 60 KB gzipped, worker setup, etc.) for a handful of fetches is over-scope. If later plans run into multi-endpoint orchestration tests (Setup Wizard with 15 endpoints, for example), revisit MSW as a Plan 10 concern.

### Why the `/api` prefix
`vite.config.ts` already proxies `/api → http://localhost:8000`. Every call in `src/api/*.ts` therefore uses `/api/...` so the same code works in dev (proxied) and in production (Docker build serves the SPA from the same origin as the FastAPI app — no CORS, same cookie scope).

### Four-state auth is deliberately explicit
`loading` is a first-class value because `ProtectedRoute` must never redirect during the initial `getSession()` call — a redirect there would make `/secretary` unmountable and steal focus from a user who is already signed in. A naive `isLoggedIn: boolean` would fold `loading` into `false`, causing a redirect flash on every mount.

### Personal mode synthetic user
In personal mode the backend doesn't mount `/auth/session`, so the frontend can't observe an actual user identity. The synthetic `LOCAL_USER = {id: "local", email: null, role: "admin"}` matches what `require_auth` produces server-side (see Plan 2's `LOCAL_USER_ID = "local"`). Keeping the two in sync lets UI code treat `user.id === "local"` as the single "am I in personal mode?" check, but most code should branch on `status === "personal"` instead because that's typed narrower.

### Notification polling pitfalls
- `setTimeout` is chained via `await refresh(); timer.current = setTimeout(...)` so the interval is measured *after* the response lands, not from wall-clock every 60 s. If the server takes 5 s to respond, the next tick fires at 65 s. This prevents queue buildup on slow networks.
- The `markRead` path calls `refresh()` after the POST to resync counts. Don't optimistically patch state — the server is authoritative, and optimistic patching interacts badly with the auto-poll that happens seconds later.
- When the user navigates between department pages quickly, multiple `markRead` calls can fire back-to-back. They're idempotent server-side (see Plan 6's `user_notifications` idempotency), so no debouncing is required in Plan 8.

### Tailwind v3, not v4
Tailwind v4 (CSS-first config, PostCSS-less) is a big migration. v3 is stable, the config shape below matches every example in the SideBar spec, and it composes cleanly with plain CSS variables. Revisit v4 as a standalone chore later.

### Strict-mode double-mount for polling
React's `<React.StrictMode>` intentionally double-mounts effects in development. `useNotificationPoll` handles this correctly because:
- Each mount starts its own `setTimeout` chain.
- The cleanup function clears its own timer and sets `cancelled = true`.
- The second mount's timer is scheduled after the first mount's cleanup, so only one chain is ever live.

There will be an *extra* initial fetch in dev (two mounts → two `tick()` calls). That's cosmetic and matches Strict Mode's design. Production builds won't do this.

### Layout decisions deferred to later plans
- **Mobile/tablet responsive.** The Sidebar spec defines hamburger overlay + bottom tab bar for small screens. Skipped here to keep Plan 8 focused on the desktop shell.
- **File viewer pane.** The CLAUDE.md architecture diagram shows an optional file viewer pane alongside the main area. Plan 12 (shared chat components) introduces it. Plan 8's `AppLayout` leaves room for it structurally but does not render it.
- **Tooltips in collapsed mode.** The spec describes 300 ms-delay tooltips next to collapsed nav icons. Skipped in Plan 8 — non-blocking, low-priority polish. Add as a follow-up to `NavItem`.
- **Keyboard focus management.** The spec calls for arrow-key navigation within the nav list. Plan 8 uses stock `<NavLink>` tab focus, which covers WCAG AA. Richer keyboard handling lands in an accessibility follow-up.

### Test file convention
All `*.test.ts(x)` files live beside their source. Vitest's default `include` glob (`**/*.{test,spec}.{js,ts,tsx}`) picks them up without extra config. No separate `tests/` tree — that's a server-side pattern.

### TypeScript strict — `JSX.Element` return type
Every component declares `: JSX.Element` as its return. This catches accidental `undefined` returns (a common cause of silent blank screens). The rule is enforced by repetition in this plan — if you reach a component file that omits it, add it before running tests.

---

## Execution Handoff

Plan complete and saved to `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints. REQUIRED SUB-SKILL: `superpowers:executing-plans`.

Which approach?
