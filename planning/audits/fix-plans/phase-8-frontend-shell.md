# Phase 8 — Frontend Shell fix plan (→ 100%)


**Current:** ~95% shipped. **Root cause:** SPEC_DRIFT + IMPLEMENTER (cosmetic).

**Gap summary:** Shell shipped fully — routing, sidebar, topbar, notification polling, theme, placeholder pages all work. Residual items are design-token divergence, a missing Phase 8 `Secretary.tsx` placeholder, and a styled `PagePlaceholder` instead of bare `<h1>`.

**Tasks (in execution order):**

1. **P1-26 — Resolve design-token divergence (decision + ratify).**
   - Files: `frontend/src/styles/tokens.css` (or equivalent) and `planning/implementation-plans/2026-04-17-phase-8-frontend-shell.md` — pick one: (a) amend plan to the Wondermakers/Acid Yellow palette, or (b) revert token values to plan palette.
   - Acceptance: token file and plan agree.

2. **P2-13 — Decide on `Secretary.tsx` Phase 8 placeholder.**
   - Files: amend plan to reuse `PagePlaceholder`, OR create `frontend/src/pages/Secretary.tsx` as placeholder.
   - Acceptance: plan text matches repo reality.

3. **P2-18 — Decide on `PagePlaceholder` card vs bare `<h1>`.**
   - Files: `frontend/src/pages/placeholder.tsx`; amend Phase 8 plan §"PagePlaceholder component".
   - Acceptance: as-built matches plan text verbatim.

4. **NEW-8-01 — Confirm mobile responsive behavior: hamburger overlay + bottom tab bar.** Why new: tracker does not list this; SideBarSpec §Responsive Behavior mandates `<768px` hidden sidebar + bottom tab bar + hamburger drawer.
   - Files: `frontend/src/components/sidebar/Sidebar.tsx`; add `MobileTabBar.tsx` and `MobileSidebarOverlay.tsx` if missing.
   - Spec ref: SideBarSpec §Responsive Behavior, §Non-Goals.
   - Acceptance: viewport-width vitest asserts sidebar hidden <768px; overlay mounts on hamburger click; `Escape` closes it.

5. **NEW-8-02 — Confirm collapsed-mode tooltip behavior (300ms delay, `role="tooltip"`, `aria-describedby`).** Why new: SideBarSpec §Collapsed Mode + §Accessibility mandate.
   - Files: `frontend/src/components/sidebar/NavItem.tsx`.
   - Acceptance: vitest asserts tooltip appears after 300ms with correct role.

**Verification:** `uv run pytest` + `cd frontend && npm run test` green; manual check at breakpoints 320/768/1024/1440px.
