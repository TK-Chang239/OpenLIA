# Frontend Shell Implementation Plan

> **Status:** Plan body backfilled 2026-04-24 during the Phase 8 fix-plan close-out (`fix/phase-8-frontend-shell`).
> The original plan file shipped as a single-line stub. The shell was implemented anyway; this document
> reconciles the as-built code, the design bundle, and Phase 24 (Design System Refresh) so that the plan,
> the specs, and the repository agree.

---

## Scope

Phase 8 ships the **application shell** that wraps every authenticated page:

- `Sidebar` (collapsed/expanded, core + department nav, notification dot, footer with Account, Sign-out, Collapse).
- `TopBar` (breadcrumb, live pill, timestamp stamps, theme toggle).
- `AppLayout` grid that hosts `<Sidebar>` + `<TopBar>` + `<main>` `<Outlet>`.
- `ProtectedRoute`, `MustChangePasswordGate`, and `SetupGate` boot-time gates.
- Theming primitives (`useTheme`, light/dark CSS custom-property switch).
- Notification poll (`useNotificationPoll`, 60-second cadence, stops on 401 or unmount).
- `PagePlaceholder` for not-yet-built routes.
- A global `ErrorBoundary` so a render fault in any child page does not blank the screen.

Phase 8 does **not** ship department pages — those are owned by Phases 11–17. It does ship the
placeholder used by every department before its real page lands.

## Design Tokens (defer to Phase 24)

The Phase 8 stub plan referenced an early "dark blue / Wondermakers" palette draft. Phase 24
(Design System Refresh) supersedes that draft. The shipped token surface — `frontend/src/styles/tokens.css`,
`frontend/tailwind.config.ts` — uses the **Wondermakers / Acid Yellow** palette
(`#D4FF00` accent on warm-cream surfaces). All component code reads its colors via CSS custom
properties (`var(--color-*)`); no hex literals live in shell components.

The token file MUST match the Wondermakers bundle (see `project/colors_and_type.css` in the design
bundle and Phase 24 §"Token layer"). Phase 8 owns the shell, not the token set; any color or
typography churn lives in Phase 24's plan.

## Configuration

The frontend reads two environment variables at build time (Vite `import.meta.env`):

| Variable | Purpose | Default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Origin used to prefix every `/api/...` call. Useful for non-proxied builds (Phase 23 Docker split, reverse proxy without an `/api` strip, frontend served from a CDN). | `""` (relative; goes through Vite dev proxy) |

`frontend/.env.example` documents the variable. `fetchJson` in `frontend/src/api/client.ts`
prefixes every relative path with `import.meta.env.VITE_API_BASE_URL ?? ""`. Paths that already
start with `http(s)://` pass through untouched.

## Dev proxy

`frontend/vite.config.ts` proxies `/api` → `http://localhost:8000` and **strips the `/api` prefix**
before forwarding:

```
rewrite: (path) => path.replace(/^\/api/, "")
```

So a frontend call to `/api/auth/session` reaches the FastAPI backend as `/auth/session`.
Every `frontend/src/api/*.ts` module calls `/api/<route>` accordingly. The older Phase 7-8 audit
that flagged this as missing is **stale** and is superseded by this plan.

## Boot-time routing

```
RouterProvider
└─ "/login" "/register" "/forgot-password" "/reset-password" "/setup" — public routes
└─ ProtectedRoute
   └─ MustChangePasswordGate
      └─ AppLayout
         └─ "/" "/home" "/repository" "/portfolio" "/settings/*" + each /department
└─ "*" → Navigate to "/"
```

- `SetupGate` is implemented as a route-tree element rather than a `window.location.replace`. When
  `getStatus()` returns `wizard_completed === false` and the URL is not `/setup`, the gate emits
  `<Navigate to="/setup" replace />` inside `RouterProvider` so React Router handles the move.
  `getStatus` fires exactly once per app boot.
- `ProtectedRoute` redirects unauthenticated users to `/login`. While `status === "loading"` it
  renders `<ShellSkeleton />` (sidebar + topbar shimmer) so the page does not flash an empty
  text-only `Loading...` state.
- `MustChangePasswordGate` short-circuits the outlet to a forced password-change form when
  `must_change_password === true`.

## Responsive Behavior

| Breakpoint | Behavior |
| --- | --- |
| `≥ md` (≥ 768 px) | Permanent `<Sidebar>` (220 px expanded / 52 px collapsed) + `<TopBar>` + `<main>`. |
| `< md` | `<Sidebar>` is hidden (`hidden md:flex`). `<TopBar>` exposes a hamburger that opens `<MobileSidebarOverlay>` (Radix `<Dialog>`, scrim, `Escape`-closes). `<MobileTabBar>` is fixed to the bottom of the viewport with the top 4 nav entries (Home, Secretary, Equity Research, Earnings Update — slot 5 reserved for "More"). |

`MobileTabBar` is rendered by `AppLayout` as a sibling of `<main>` and only on `< md`. The
`<main>` element compensates with `pb-16 md:pb-0` so the tab bar does not occlude content.

## Collapsed Mode (NavItem tooltip)

When the sidebar is collapsed (52 px), each `NavItem` wraps its `NavLink` in a Radix Tooltip:

- `delayDuration={300}` — 300 ms hover delay.
- The tooltip content has `role="tooltip"` (Radix default) and is connected to the link via
  `aria-describedby` (Radix wires this automatically).
- Tooltip is `forceMount`-free; it only renders while open.

The previous `aria-label`-only behavior is replaced; the link still carries `aria-label` for
SR users when collapsed.

## Sidebar footer

`Account`, `Sign out`, and `Collapse` live in `<footer>` of `<Sidebar>`:

- **Account** is now a `<NavLink to="/settings/account">` (was a non-interactive `<div>`),
  so it is keyboard focusable and announced as a link.
- **Sign out** is a `<button>` that calls `useAuth().logout()` then `navigate("/login")`.
- **Collapse** is a `<button>` that toggles the `useCollapsed` hook (persisted to localStorage).

## TopBar / Landmarks

- `TopBar` no longer carries `role="banner"`; instead `AppLayout` wraps it in a `<header>` element.
  This produces exactly one banner landmark per page (the implicit `<header>` role).
- Breadcrumbs are rendered as a `<nav aria-label="Breadcrumb">` with `<a>` segments where the
  pathname has a known sub-route (Settings tabs, Macro Research drill-downs).

### Breadcrumbs

`shellState.crumbsForPath` walks the pathname segments and maps them through a sub-crumb
dictionary. `/settings/providers` → `Home / Settings / Providers`;
`/macro-research/drilldown/USD` → `Home / Macro Research / Drilldown / USD`.

## Accessibility

- **Skip link.** `AppLayout` renders `<a href="#main" className="sr-only focus:not-sr-only ...">Skip to content</a>`
  as the first focusable element. `<main id="main" tabIndex={-1}>` accepts the focus.
- **Landmarks.** One `<header>` (banner), one `<nav aria-label="Main navigation">` (sidebar),
  one `<nav aria-label="Breadcrumb">` (TopBar), one `<main>`.
- **Keyboard.** Every interactive footer/Sidebar entry is a real `<NavLink>` or `<button>`.
- **Focus rings.** Provided by `tokens.css` (`--focus-ring-color`).

## Theming

`useTheme` reads the persisted theme from `localStorage` first; if absent, it consults
`window.matchMedia('(prefers-color-scheme: dark)').matches` so a dark-mode-OS user does not get a
flash of light on first visit. The chosen theme is written to `<html data-theme>` and back to
`localStorage`. Manual toggle (TopBar) overrides the system preference.

## Loading states

`ProtectedRoute` renders `<ShellSkeleton />` (a sidebar + topbar shimmer that matches the real
shell's grid) instead of a bare `<div>Loading...</div>` while `status === "loading"`. This avoids
the layout shift between bare text and the full shell once auth resolves.

## Notifications

`useNotificationPoll` hits `GET /api/notifications/unread` every 60 s.

- On any 401 response, the timer is cleared and `error: "unauthorized"` is exposed on the hook
  return value. The Sidebar consumer can react (or simply unmount, which `ProtectedRoute`
  guarantees on logout).
- On unmount the timer is cleared via the effect cleanup.
- Other errors are still swallowed; the next tick re-tries.

## Error handling

A class component `ErrorBoundary` (`frontend/src/components/shell/ErrorBoundary.tsx`) wraps
`<RouterProvider>` in `App`. On `componentDidCatch` it logs the error, switches state to
`hasError: true`, and renders a `PagePlaceholder`-styled fallback with a "Reload" button. This
prevents the white-screen-on-throw failure mode.

## Typography

Geist (variable TTF, 100–900) is the display + body face. It is loaded via `@font-face` in
`global.css` and **preloaded** in `index.html` via
`<link rel="preload" href="/fonts/Geist_wght_.ttf" as="font" type="font/ttf" crossorigin>` so the
first paint is correctly typeset. IBM Plex Mono and DM Serif Display load from Google Fonts with
`display=swap` already in the URL.

## Placeholders

- `PagePlaceholder` is the canonical not-yet-built page renderer: a warm-cream solid card with a
  monospace `PAGE_NOT_READY` label and a display-font heading. This matches Phase 24 design rule
  §14 ("placeholders are warm-cream solids with a mono label"). The plan stub's earlier hint at a
  bare `<h1>` is **superseded**.
- **Secretary** is owned by Phase 13 (`SecretaryPage.tsx`). Phase 8 does **not** ship a Secretary
  placeholder; the router wires `/secretary` directly to the Phase 13 page.

## Testing

- `frontend/src/App.test.tsx` covers:
  - Authenticated boot renders the Sidebar.
  - `SetupGate` redirects to `/setup` when `wizard_completed === false`.
  - `MustChangePasswordGate` swaps in the change-password form when `must_change_password === true`.
  - `ProtectedRoute` redirects to `/login` when unauthenticated.
  - Unknown path → `/`.
- Component tests: `Sidebar.test.tsx` (links + collapse + dot + signout + viewport hide-below-md);
  `NavItem.test.tsx` (collapsed tooltip via Radix); `useNotificationPoll.test.ts` (poll + 401 stop);
  `useTheme.test.ts` (system-preference fallback); `client.test.ts` (`VITE_API_BASE_URL` prefixing);
  `ErrorBoundary.test.tsx`; `shellState.test.ts` (multi-segment crumbs).

## Cross-references

- Phase 24 — Design System Refresh (token layer, typography, design rule §14).
- Phase 10 — Setup Wizard (gate behavior consumed by `SetupGate`).
- Phase 13 — Secretary page (router target).
- Phase 23 — Deploy recipes (consume `VITE_API_BASE_URL`).
- `planning/implementation-plans/endpoint-contract-matrix.md` — proxy contract.
