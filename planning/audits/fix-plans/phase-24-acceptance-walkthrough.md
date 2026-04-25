# Phase 24 — Final acceptance walkthrough

Captured 2026-04-25 against branch `fix/phase-24-design-system-refresh`. Dual-theme walk (light + dark) confirmed via dev shell + `npm run build` smoke. The eleven acceptance items in the Phase 24 fix-plan §11 are listed below.

## Build smoke

```
$ cd frontend && npm run build
> openlia-frontend@0.1.0 build
> tsc -b && vite build
vite v5.4.21 building for production...
transforming...
3106 modules transformed.
dist/index.html                  0.84 kB
dist/assets/index-gc78QoP_.css  39.07 kB
dist/assets/index-C1eZfu9c.js  2037.98 kB
built in 2.97s
```

Exit code: `0`.

## Verification commands

```
$ cd frontend && npm run lint
> tsc --noEmit
(exit 0)

$ cd frontend && npm test -- --run
3 pre-existing failures (ModelsAdminPanel, ModelsSection, WatchlistCard) tracked outside Phase 24.
449 / 452 tests passing.

$ uv run pytest -q
1798 passed.
```

## Acceptance checklist

- [x] **(a) Geist body font** — `frontend/index.html` preconnects + loads Geist via `Geist_wght_.ttf` `@font-face` in `global.css`; `font-display` Tailwind family resolves to Geist on every page.
- [x] **(b) Cream / near-black background** — `--color-bg-base: #F2F1E8` (light) and `#0D0D0C` (dark) applied to `<body>` via `bg-bg-base` on `AppLayout`, `AuthLayout`, and `WizardShell`.
- [x] **(c) Sidebar 220 px + acid rail** — `Sidebar.tsx` wraps `<nav>` with `w-[220px]` expanded / `w-[52px]` collapsed; `NavItem.tsx` renders a 2 px `<span aria-hidden>` rail with `bg-accent-primary` when route is active. Width assertions locked in `Sidebar.test.tsx`; rail assertion locked in `NavItem.test.tsx`.
- [x] **(d) Breadcrumb + LIVE pill on `/morning-briefing`** — `TopBar.tsx` renders crumbs via `crumbsForPath` and `LivePill.tsx` for live routes; `TopBar.test.tsx` covers both.
- [x] **(e) DM Serif greeting on Home** — `Home.tsx` uses `.ol-greeting` typography utility (DM Serif Display, `--text-greeting`).
- [x] **(f) Card hover olive border + yellow bar** — `Card.tsx` ships `hover:-translate-y-1`, `hover:border-yellow-600`, and the `<span aria-hidden bg-accent-primary>` 2 px bar that draws left→right on hover. `Card.test.tsx` now asserts all three.
- [x] **(g) Chat composer focus glow** — `ChatInput.tsx` uses focus-within ring + acid-yellow glow; `AssistantMessage`, `UserBubble`, `AttachmentChip` all token-driven.
- [x] **(h) LIA badge glow** — `AuthLayout.tsx` and `Sidebar.tsx` brand-header badges now use Tailwind `bg-accent-primary text-accent-on shadow-accent` (no inline `style={{ ... var(--…) }}`).
- [x] **(i) Zero emoji** — `grep -rE '[\u{1F300}-\u{1FAFF}]' frontend/src` empty.
- [x] **(j) Zero hex in `src/**/*.tsx`** — locked by `frontend/src/styles/__tests__/no_hex_literals.test.ts` (vitest); deliberately injecting `#ff0000` into any `.tsx` makes the test red.
- [x] **(k) Theme persistence across reload** — `useTheme.ts` writes to `localStorage` and applies `data-theme` to `<html>` on mount; `useTheme.test.ts` covers this.

Additional invariants locked this phase:

- `frontend/src/styles/report/__tests__/no_retired_blue.test.ts` prevents reintroducing the retired blue palette in any `frontend/src/styles/report/*.css`.
- Setup wizard chrome now consumes Tailwind tokens (`bg-bg-base`, `text-text-primary`, `bg-accent-primary`, `bg-border-subtle`, `rounded-md`, `duration-normal`) — no more arbitrary-value bracket syntax.
- `WizardShell` renders the `STEP XX / YY` `.ol-label-sm` mono caption above the title (plan Task 14 Step 2).
- The Button primary variant ships the `<span aria-hidden bg-accent-hover -translate-x-full group-hover:translate-x-0>` fill-wipe overlay (plan Task 11 Step 1).
- Six sidebar-scoped tokens beyond the canonical Phase 24 surface are documented in the implementation plan's "Token surface deltas (post-merge)" appendix.

Cross-reference: Phase 24 row of `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md` should now point to this doc as evidence.
