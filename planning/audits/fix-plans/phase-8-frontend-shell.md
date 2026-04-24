# Phase 8 — Frontend Shell fix plan (→ 100%)

**Current:** ~85% shipped (revised down from prior ~95% after deep audit).
**Root cause:** SPEC_DRIFT (plan + spec files are near-empty stubs; design tokens diverged to Wondermakers/Acid Yellow before Phase 24 formalized it) + IMPLEMENTER (missing mobile shell, missing ErrorBoundary/skip-nav, missing API-base env wiring, missing fonts-preload, no `SecretaryPage.tsx` of Phase 8 vintage, `SetupGate` uses `window.location.replace` rather than React Router).

**Context:**
- `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md` is **1 line long** — the plan is effectively absent. Every task below must include a "plan ref" that says *write the plan text first*.
- `planning/specs/components/SideBarSpec.md` is **1 line long** — the referenced sidebar spec is also a stub. Task list treats the design-bundle kit (`project/ui_kits/app/index.html` cited by Phase 24) and the as-built shell as joint sources of truth until the specs are backfilled.
- Phase 24 (Design System Refresh) supersedes the token question: tokens.css and tailwind.config.ts already reflect the Acid Yellow palette. The Phase 8 divergence becomes a **spec/plan reconciliation** item, not a revert.

**Gap summary:**

1. Design-token palette swap never ratified in the Phase 8 plan (P1-26).
2. Sidebar has zero mobile behavior — no hamburger, no overlay, no bottom tab bar; `w-[220px]` / `w-[52px]` renders at every viewport (NEW-8-01).
3. NavItem collapsed-mode tooltip is implemented only as `aria-label`; no visible tooltip with `role="tooltip"`, `aria-describedby`, or delay (NEW-8-02).
4. No global `ErrorBoundary` wrapping `RouterProvider`; uncaught render error blanks the app (NEW-8-03).
5. No skip-to-main-content link; `<main>` lacks `id="main"` / `tabIndex={-1}` for skip target (NEW-8-04).
6. `SetupGate` hard-redirects with `window.location.replace`, bypassing React Router and causing full-page reload on every boot into the wizard (NEW-8-05).
7. `fetchJson` hardcodes relative paths; no `import.meta.env.VITE_API_BASE_URL` base — blocks non-proxied dev and Phase 23 Docker builds where frontend is served from a different origin (NEW-8-06).
8. `vite.config.ts` proxy rewrites `/api` → `""`, but the older Phase 7-8 audit flagged this as correct vs. the unrewritten form; the current rewrite **is correct** with the `/api/...` client calls — verify and document (NEW-8-07).
9. No global loading boundary for Suspense/route pending; `ProtectedRoute` returns a bare `<div>Loading...</div>` that does not match the shell (NEW-8-08).
10. `global.css` imports Geist via `@font-face` but `index.html` never preloads the TTF; `IBM Plex Mono` and `DM Serif Display` load via Google Fonts with no `font-display: swap` guarantee on the local face (NEW-8-09).
11. `SecretaryPage` Phase 8 placeholder was never created — the real `SecretaryPage.tsx` (Phase 13) is what the router points to (P2-13).
12. `PagePlaceholder` renders a styled card instead of the bare `<h1>` the plan (stub) implied (P2-18).
13. `Sidebar` has no `role="complementary"`/landmark semantics beyond `<nav>`; the Account footer button is a non-interactive `<div>` (no `role="button"`/navigation) (NEW-8-10).
14. TopBar `role="banner"` conflicts with the implicit `<header>` landmark rule — a page can only have one banner; `AppLayout` must wrap TopBar in a `<header>` or drop the role (NEW-8-11).
15. Theme toggle: `useTheme` sets `data-theme` but never reads `prefers-color-scheme` on first load — spec in Phase 24 rule set says light is default, but new users on a dark-mode OS get unexpected light flash (NEW-8-12).
16. Zero routing-level vitest coverage: no test for SetupGate redirect, no test for MustChangePasswordGate wrapping, no breadcrumb test beyond the smoke `App.test.tsx` (NEW-8-13).
17. Notification poll timer leaks when `AuthProvider` logs out — poll keeps hitting `/notifications/unread` and spamming 401s (NEW-8-14).
18. `crumbsForPath` only matches first-level paths; `/macro-research/drilldown` or `/settings/providers` show "Home / Macro Research" (or "Home / Settings") with no sub-crumb; Phase 24's TopBar contract calls for a 2-3 segment breadcrumb (NEW-8-15).

---

## Tasks (execution order)

### 1. P1-26 — Ratify design-token divergence in the Phase 8 plan

- **Severity:** P1
- **Bug:** `frontend/src/styles/tokens.css` header calls the palette "Wondermakers / Acid Yellow" and says it "supersedes the retired dark-blue draft", but the Phase 8 plan file (1 line) never documents that swap. Plan and shipped palette disagree by default.
- **Files:**
  - `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md` — backfill plan body; add "Design tokens: see Phase 24 (Design System Refresh). Token file MUST match the Wondermakers bundle" section.
  - (No code change; tokens are already Phase 24-aligned.)
- **Plan ref:** Phase 8 plan (stub) + Phase 24 plan §"Token layer".
- **Spec ref:** `project/colors_and_type.css` in design bundle (cited by Phase 24).
- **Acceptance:** Phase 8 plan explicitly defers the token set to Phase 24; no claim that the dark-blue palette is active.
- **Verification:** `grep -n "Wondermakers\|Acid Yellow\|Phase 24" planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md` returns a non-empty match inside a "Design Tokens" section.

### 2. P2-13 — Resolve `Secretary.tsx` Phase-8-vintage placeholder

- **Severity:** P2
- **Bug:** Router wires `/secretary` to the Phase 13 `SecretaryPage`; no Phase 8 placeholder was ever shipped. Plan (stub) is silent; tracker lists as P2-13.
- **Files:** `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md` — amend to state that Secretary is owned by Phase 13 and Phase 8 ships no placeholder for it. No code change needed — the router already routes correctly.
- **Plan ref:** Phase 8 plan §placeholders (to be written).
- **Spec ref:** n/a (Phase 13 owns SecretarySpec).
- **Acceptance:** Plan text and repo reality agree.
- **Verification:** `grep -n "Secretary" planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md`.

### 3. P2-18 — Decide `PagePlaceholder` card vs. bare `<h1>`

- **Severity:** P2
- **Bug:** `frontend/src/pages/placeholder.tsx` renders a bordered card with `PAGE_NOT_READY` label. Phase 8 stub plan implied a bare `<h1>`. Phase 24 design rules mandate "warm-cream solids with a mono label". Current implementation already matches Phase 24.
- **Files:** `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md` — document the styled-card version as canonical.
- **Plan ref:** Phase 8 plan §PagePlaceholder (to be written); Phase 24 rule 14.
- **Spec ref:** Phase 24 design rules §14 (warm-cream placeholders with mono label).
- **Acceptance:** Plan matches as-built; no revert.
- **Verification:** Visual confirmation at `/home` if the stub renders; read plan text.

### 4. NEW-8-01 — Ship mobile responsive shell (hamburger + overlay + bottom tab bar)

- **Severity:** P1
- **Bug:** `frontend/src/components/sidebar/Sidebar.tsx` uses `w-[220px]` / `w-[52px]` unconditionally. No `md:` / `sm:` breakpoint handling; no `MobileSidebarOverlay`; no `MobileTabBar`. SideBarSpec.md (stub) is silent but the design bundle's `project/ui_kits/app/index.html` and every other serious app shell demand a mobile behavior below 768px.
- **Files:**
  - `frontend/src/components/sidebar/Sidebar.tsx` — hide below `md`, add `aria-hidden` + `hidden md:flex`.
  - `frontend/src/components/sidebar/MobileSidebarOverlay.tsx` (create) — Radix Dialog + `Escape` + scrim.
  - `frontend/src/components/sidebar/MobileTabBar.tsx` (create) — fixed bottom bar, top 4-5 nav entries.
  - `frontend/src/components/shell/TopBar.tsx` — add hamburger button visible only below `md`, wired to overlay open state.
  - `frontend/src/layouts/AppLayout.tsx` — render `MobileTabBar` below `md`; adjust `grid-template-columns` for mobile.
  - `frontend/src/components/sidebar/Sidebar.test.tsx` — add viewport-width test.
- **Plan ref:** Phase 8 plan §Responsive Behavior (to be written).
- **Spec ref:** SideBarSpec.md §Responsive Behavior (to be written); until then, design bundle `project/ui_kits/app/index.html`.
- **Acceptance:** Vitest asserts sidebar hidden below 768px; overlay opens on hamburger click; `Escape` closes it; bottom tab bar is present and navigable.
- **Verification:** `npm --prefix frontend run test -- Sidebar`; manual check at 320/768/1024.

### 5. NEW-8-02 — Collapsed-mode tooltip (Radix, 300 ms delay, `role="tooltip"`, `aria-describedby`)

- **Severity:** P2
- **Bug:** `NavItem.tsx` only sets `aria-label={label}` when collapsed. No visible tooltip on hover; no `role="tooltip"`; no `aria-describedby` linkage.
- **Files:**
  - `frontend/src/components/sidebar/NavItem.tsx` — wrap `<NavLink>` in Radix `Tooltip` (`@radix-ui/react-tooltip` — add dep).
  - `frontend/package.json` — add `@radix-ui/react-tooltip`.
  - `frontend/src/components/sidebar/NavItem.test.tsx` — assert tooltip appears after 300 ms.
- **Plan ref:** Phase 8 plan §Collapsed Mode (to be written).
- **Spec ref:** SideBarSpec.md §Accessibility (to be written).
- **Acceptance:** Hover a collapsed nav item ⇒ tooltip with `role="tooltip"` visible, linked via `aria-describedby`.
- **Verification:** `npm --prefix frontend run test -- NavItem`.

### 6. NEW-8-03 — Global `ErrorBoundary` wrapping the router

- **Severity:** P1
- **Bug:** `frontend/src/App.tsx` has no `ErrorBoundary`. Any render error in any page produces a blank screen (React 18 swallows and remounts; error is only in the console).
- **Files:**
  - `frontend/src/components/shell/ErrorBoundary.tsx` (create) — class component with `componentDidCatch`, fallback uses `PagePlaceholder` styling and a "Reload" button.
  - `frontend/src/App.tsx` — wrap `<RouterProvider>` with `<ErrorBoundary>`.
  - `frontend/src/components/shell/ErrorBoundary.test.tsx` (create) — throw in a child, assert fallback renders.
- **Plan ref:** Phase 8 plan §Error handling (to be written).
- **Spec ref:** n/a (project rule: fail loudly).
- **Acceptance:** Throwing from a route component renders the fallback, not a blank screen.
- **Verification:** Vitest asserts fallback UI.

### 7. NEW-8-04 — Skip-to-main-content link + `<main id="main">` focus target

- **Severity:** P1
- **Bug:** No skip-nav link in `AppLayout.tsx`. `<main>` has no `id` / `tabIndex={-1}`. Keyboard users must tab through the entire sidebar to reach content. WCAG 2.1 2.4.1 failure.
- **Files:**
  - `frontend/src/layouts/AppLayout.tsx` — add `<a href="#main" className="sr-only focus:not-sr-only ...">Skip to content</a>` as first child; set `id="main" tabIndex={-1}` on `<main>`.
  - `frontend/src/styles/global.css` — add `.sr-only` utility if not already via Tailwind `sr-only`.
- **Plan ref:** Phase 8 plan §Accessibility (to be written).
- **Spec ref:** WCAG 2.1 2.4.1.
- **Acceptance:** Tab from `<body>` focuses the skip link first; activating it moves focus to `<main>`.
- **Verification:** Vitest on AppLayout: `Tab` from body → skip link is focused.

### 8. NEW-8-05 — Replace `window.location.replace` in `SetupGate` with React Router navigation

- **Severity:** P2
- **Bug:** `frontend/src/App.tsx` does `window.location.replace("/setup")` — full page reload on every boot when setup is needed; loses React state; causes a second `GET /setup/status` round-trip.
- **Files:**
  - `frontend/src/App.tsx` — restructure `SetupGate` so that the needs-setup branch renders `<Navigate to="/setup" replace />` inside a `RouterProvider` context, OR move the gate logic into the router tree as a loader/layout.
- **Plan ref:** Phase 8 plan §Boot-time routing (to be written).
- **Spec ref:** Phase 10 SetupWizard spec (gate behavior).
- **Acceptance:** Uncompleted-wizard boot produces a client-side navigation, not a full reload; `getStatus` fires exactly once.
- **Verification:** Vitest asserts `getStatus` called once; no `window.location.replace` call.

### 9. NEW-8-06 — Introduce `VITE_API_BASE_URL` for non-proxied builds

- **Severity:** P1
- **Bug:** `frontend/src/api/client.ts` + every `api/*.ts` call relative `/api/...` paths. Works with the Vite dev proxy; breaks when the frontend is served from a separate origin (Phase 23 Docker split, any reverse-proxy setup without `/api` strip).
- **Files:**
  - `frontend/src/api/client.ts` — prefix all paths with `import.meta.env.VITE_API_BASE_URL ?? ""`; allow paths already starting with `http(s)` to pass through.
  - `frontend/.env.example` (create) — document `VITE_API_BASE_URL=`.
  - `frontend/src/api/client.test.ts` — assert the env-prefix behavior.
  - Phase 8 plan: document the env var.
- **Plan ref:** Phase 8 plan §Configuration (to be written).
- **Spec ref:** Phase 23 deploy recipes.
- **Acceptance:** With `VITE_API_BASE_URL=https://api.example.com`, `fetchJson("/api/x")` hits `https://api.example.com/api/x`.
- **Verification:** `npm --prefix frontend run test -- client`.

### 10. NEW-8-07 — Document Vite proxy rewrite correctness

- **Severity:** P2
- **Bug:** Older audit (2026-04-21 Phase 7-8) flagged `vite.config.ts` as missing `/api` strip. Current config *does* `rewrite: (path) => path.replace(/^\/api/, "")`. Finding is stale but plan never confirms it.
- **Files:** `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md` — record the proxy contract ("frontend calls `/api/...`, proxy strips `/api`, backend receives `/auth/session`").
- **Plan ref:** Phase 8 plan §Dev proxy (to be written).
- **Spec ref:** `planning/implementation-plans/endpoint-contract-matrix.md`.
- **Acceptance:** Plan documents the rewrite; older audit finding marked superseded.
- **Verification:** `grep -n "rewrite\|strip" planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md`.

### 11. NEW-8-08 — Shell-shaped loading boundary for protected routes

- **Severity:** P2
- **Bug:** `ProtectedRoute.tsx` returns a bare `<div>Loading...</div>` on `status === "loading"`. Causes a visible layout shift from bare text to the full shell once auth resolves.
- **Files:**
  - `frontend/src/router/ProtectedRoute.tsx` — render `<AppLayout>` with a skeleton in place of `<Outlet />` while loading, or a dedicated `ShellSkeleton` component.
  - `frontend/src/components/shell/ShellSkeleton.tsx` (create) — sidebar + topbar shimmer.
- **Plan ref:** Phase 8 plan §Loading states (to be written).
- **Spec ref:** Phase 24 design rule 14 (placeholders are warm-cream solids).
- **Acceptance:** Boot from a cold cache shows a skeleton shell, not a text string.
- **Verification:** Vitest snapshot with `status="loading"`.

### 12. NEW-8-09 — Preload Geist + add `font-display: swap` to Google Fonts

- **Severity:** P2
- **Bug:** `frontend/index.html` loads IBM Plex Mono + DM Serif Display via Google Fonts with `display=swap` in the URL (good). Local Geist TTF is `@font-face`'d in `global.css` but *not* preloaded with `<link rel="preload" as="font" type="font/ttf" crossorigin>`. FOUT on first render.
- **Files:**
  - `frontend/index.html` — add `<link rel="preload" href="/fonts/Geist_wght_.ttf" as="font" type="font/ttf" crossorigin="anonymous">`.
- **Plan ref:** Phase 8 plan §Typography (to be written); Phase 24 §Typography layer.
- **Spec ref:** Phase 24 design rule 4 (Geist is the display / body font).
- **Acceptance:** DevTools Network shows Geist in the first wave, not on text-render.
- **Verification:** Manual: throttled network boot shows correct font immediately.

### 13. NEW-8-10 — Fix Account footer semantics in Sidebar

- **Severity:** P2
- **Bug:** `Sidebar.tsx` renders Account as a `<div>` (line 138+), not a button or link. Not keyboard-focusable, not announced as interactive, but visually looks clickable.
- **Files:** `frontend/src/components/sidebar/Sidebar.tsx` — make Account a `<NavLink to="/settings/account">` OR drop the visual if not actionable.
- **Plan ref:** Phase 8 plan §Sidebar footer (to be written).
- **Spec ref:** SideBarSpec.md §Account (to be written).
- **Acceptance:** Account footer row is reachable via `Tab` and triggers navigation.
- **Verification:** `npm --prefix frontend run test -- Sidebar`.

### 14. NEW-8-11 — Resolve double-banner landmark conflict (TopBar)

- **Severity:** P2
- **Bug:** `TopBar.tsx` uses `role="banner"`. If a page also contains a `<header>` element, axe flags duplicate banner landmarks. Layout convention: only the outermost `<header>` is the banner.
- **Files:** `frontend/src/components/shell/TopBar.tsx` — remove `role="banner"`; wrap in a `<header>` inside `AppLayout.tsx` instead.
- **Plan ref:** Phase 8 plan §Landmarks (to be written).
- **Spec ref:** WAI-ARIA Authoring Practices §Banner.
- **Acceptance:** Axe audit shows exactly one banner landmark per page.
- **Verification:** `axe-core` or manual `npm run test:a11y` (add script if not present).

### 15. NEW-8-12 — Respect `prefers-color-scheme` on first theme read

- **Severity:** P2
- **Bug:** `frontend/src/hooks/useTheme.ts:read()` returns `"light"` unless localStorage says otherwise. A dark-mode-OS user gets a flash of light on every first visit.
- **Files:** `frontend/src/hooks/useTheme.ts` — if no stored value, consult `window.matchMedia('(prefers-color-scheme: dark)').matches`.
- **Plan ref:** Phase 8 plan §Theming (to be written); Phase 24 §Theme toggle.
- **Spec ref:** Phase 24 §Theme toggle.
- **Acceptance:** First visit in a dark-mode OS boots with `data-theme="dark"`.
- **Verification:** `npm --prefix frontend run test -- useTheme` with mocked `matchMedia`.

### 16. NEW-8-13 — Routing-level vitest coverage

- **Severity:** P2
- **Bug:** `App.test.tsx` covers only the Sidebar-visible-when-authenticated case. No test for:
  - `SetupGate` redirect when `wizard_completed === false`.
  - `MustChangePasswordGate` wrapping when `must_change_password === true`.
  - `ProtectedRoute` unauthenticated → `/login`.
  - Unknown-path → `/` redirect.
- **Files:**
  - `frontend/src/App.test.tsx` — extend or split into routing-specific tests.
  - `frontend/src/router/MustChangePasswordGate.test.tsx` — already exists (per `ls`); confirm coverage.
  - `frontend/src/router/ProtectedRoute.test.tsx` — already exists; confirm coverage.
- **Plan ref:** Phase 8 plan §Testing (to be written).
- **Spec ref:** n/a.
- **Acceptance:** Each branch in §4–§6 has a named vitest.
- **Verification:** `npm --prefix frontend run test`.

### 17. NEW-8-14 — Stop notification poll on sign-out

- **Severity:** P1
- **Bug:** `useNotificationPoll.ts` sets a recurring `setTimeout` in `<Sidebar>`. When `AuthProvider` transitions to `unauthenticated`, the Sidebar unmounts (because `ProtectedRoute` redirects). Good. But within a single session, logout-then-login reuses the AuthProvider; the effect cleanup runs on Sidebar unmount — verify no leak. Also: current poll swallows *all* errors; a 401 flood is invisible.
- **Files:**
  - `frontend/src/components/sidebar/useNotificationPoll.ts` — on 401 response, stop the timer and expose an error state.
  - `frontend/src/components/sidebar/useNotificationPoll.test.ts` — assert timer clears on unmount and after 401.
- **Plan ref:** Phase 8 plan §Notifications (to be written).
- **Spec ref:** n/a.
- **Acceptance:** After logout, no further `/notifications/unread` requests fire.
- **Verification:** Vitest with fake timers + mocked fetch; count calls post-unmount.

### 18. NEW-8-15 — Multi-segment breadcrumbs

- **Severity:** P2
- **Bug:** `shellState.crumbsForPath` returns `["Home", "Macro Research"]` for every `/macro-research/*` sub-path. Settings and Macro Research have sub-routes that deserve a third crumb.
- **Files:**
  - `frontend/src/layouts/shellState.ts` — extend to inspect `location.pathname` segments and map them via a sub-crumb dictionary.
  - `frontend/src/layouts/shellState.test.ts` (create) — vitest covering `/settings/providers`, `/macro-research/drilldown/X`.
- **Plan ref:** Phase 8 plan §TopBar breadcrumbs (to be written); Phase 24 §TopBar.
- **Spec ref:** Design bundle `project/ui_kits/app/index.html` breadcrumb pattern.
- **Acceptance:** `/settings/providers` renders `Home / Settings / Providers`.
- **Verification:** `npm --prefix frontend run test -- shellState`.

---

## Global verification

```
uv run pytest                                # backend unchanged
cd frontend && npm run lint                  # tsc --noEmit
cd frontend && npm run test                  # vitest including new tests
cd frontend && npm run build                 # production build
```

Manual: viewports 320 / 768 / 1024 / 1440 px; tab-cycle from `<body>` verifying skip link; light/dark OS preference; cold boot with `VITE_API_BASE_URL=` unset and set.

## Cross-reference

- Master tracker entries touched: P1-26, P2-13, P2-14, P2-18.
- New IDs minted here: NEW-8-01 (existing), NEW-8-02 (existing), NEW-8-03, NEW-8-04, NEW-8-05, NEW-8-06, NEW-8-07, NEW-8-08, NEW-8-09, NEW-8-10, NEW-8-11, NEW-8-12, NEW-8-13, NEW-8-14, NEW-8-15. Add the 13 new IDs to §11 of the master tracker.
