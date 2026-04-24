# Phase 24 — Design System Refresh (Wondermakers / Acid Yellow) fix plan (→ 100%)

**Current:** ~85% shipped. **Root cause:** mixed.
- IMPLEMENTER drift: `Button.tsx` is missing the `::before` fill-wipe hover overlay specified in plan Task 11 Step 1; `Card.test.tsx` predates Phase 24 (Apr 20 file) and only asserts the `region` role — it does NOT exercise the Phase-24 hover contract (translateY, olive border, yellow `::after` bar drawing left→right); `AuthLayout.tsx` uses inline `style={{ background: "var(--color-accent-primary)", color: "var(--color-accent-on)", boxShadow: "var(--shadow-accent)" }}` for the LIA badge instead of the Tailwind `bg-accent-primary text-accent-on shadow-accent` token classes that the plan's design system normalization established as the canonical access route.
- DEFERRED: Task 14 (Setup wizard sweep) was never executed — `frontend/src/setup/WizardProgress.tsx` uses `bg-[--color-border-subtle]` track + `duration-200` literal instead of `duration-normal` token, has no `rounded-full` radius (plan: `9999px`), and no `STEP X / Y` `.ol-label-sm` rendered anywhere in `WizardShell` / `WizardFooter`; Task 16 (report theme audit) was a no-op — files are unchanged from `885b20f` and no grep-locked test prevents future drift; Task 17 final acceptance walkthrough never recorded — no light+dark manual walk evidence in PR #41 body, no `npm run build` smoke commit.
- SPEC_DRIFT: `tokens.css` exposes four sidebar-scoped tokens (`--color-sidebar-text`, `--color-sidebar-text-strong`, `--color-sidebar-text-muted`, `--color-sidebar-divider`, `--color-sidebar-hover`, `--color-sidebar-active`) that are NOT in the plan's Task 1 token surface (plan only exposes `--color-sidebar-bg`). The Sidebar wires these via inline `style={{ color: "var(--color-sidebar-text)" }}` props rather than Tailwind classes — they work, but they're an undocumented expansion to the canonical token list.
- POLICY GAP: plan Task 11 Step 6 mandates "one smoke test per primitive" — `DataRow.test.tsx` and `MonoLabel.test.tsx` were never created; plan Task 5 Step 1 mandates updating `Sidebar.test.tsx` widths from `w-[240px]/w-[60px]` to `w-[220px]/w-[52px]` — the test file no longer asserts widths at all (likely had width assertions removed during the test rewrite); plan Task 5 Step 4 mandates adding a NavItem rail-on-active test — file not touched in `e23da2f`.

**Plan-vs-shipped delta (verified 2026-04-24, branch `main` after PR #41 merge):**

| Plan task | Status | Evidence |
|---|---|---|
| 0 — Pre-flight hex/token audit | Done (implicit) | `grep -rE '#[0-9A-Fa-f]{3,8}\b' frontend/src --include='*.tsx'` returns one match (`&#9612;` HTML entity in `AssistantMessage.tsx`, not a color). Zero retired-token usages (`color-bg-app`, `color-surface-info`, `duration-base`) outside `tokens.css`'s back-compat aliases. |
| 1 — Rewrite `tokens.css` | Done + drift | Light + dark sets present; back-compat aliases for `color-bg-app` / `duration-base` present; **drift**: six `--color-sidebar-*` tokens added beyond plan surface (no doc update). |
| 2 — Geist + Plex Mono + DM Serif | Done | `frontend/public/fonts/Geist_wght_.ttf` 168,932 bytes; `index.html` has Google Fonts preconnect + link; `global.css` has `@font-face Geist` + `.ol-label`/`.ol-label-sm`/`.ol-data`/`.ol-greeting`. |
| 3 — Tailwind config | Done | `tailwind.config.ts` exposes full token surface incl. `bg-base/elevated/input/code`, `accent-*`, `text-*`, `icon-*`, `border-*`, `feedback-*`, `yellow-*`, font families, fontSize tokens, `transitionDuration` aliases (`base` → retired, `normal`). |
| 4 — `useTheme` + `ThemeToggle` | Done | `useTheme.ts` + `useTheme.test.ts` (3 tests passing); `ThemeToggle.tsx` ships in `components/shell/`. |
| 5 — Sidebar 220/52 + acid rail | Done + test debt | `Sidebar.tsx` uses `w-[52px]` / `w-[220px]` correctly; uses `--color-sidebar-*` tokens. **Test debt**: `Sidebar.test.tsx` does NOT assert widths (plan Step 1 explicitly required `w-[220px]/w-[52px]` updates); `NavItem.test.tsx` does NOT assert rail renders when active (plan Step 4 explicitly required). |
| 6 — TopBar + LivePill | Done | `TopBar.tsx` + `TopBar.test.tsx` (2 tests passing); `LivePill.tsx` references `ol-pulse` keyframe; `@keyframes ol-pulse` defined in `global.css:67`. |
| 7 — AppLayout grid + shellState | Done | `AppLayout.tsx` rewritten with `gridTemplateColumns: "auto 1fr"` + `gridTemplateRows: "auto 1fr"`; `shellState.ts` exposes `crumbsForPath` + `stampsForNow`. |
| 8 — Home hero | Done | `Home.tsx` rewritten with `.ol-greeting` + macro strip + DEPARTMENT_NAV cards + yellow-bar-on-hover. |
| 9 — Chat primitives restyle | Done | `ChatInput.tsx` (10px radius, focus glow, mono kbd hint, acid send button); `AssistantMessage.tsx` (LiaBadge + dept tag + bg-elevated bubble); `UserBubble.tsx` (near-black `#1A1A18` + cream); `LiaBadge.tsx` (acid bg + olive text + glow); `AttachmentChip.tsx` (src-chip mono style). |
| 10 — `DataRow` primitive | Partial | `DataRow.tsx` shipped; **no `DataRow.test.tsx`** — violates plan Task 11 Step 6 "one smoke test per primitive". |
| 11 — Button/Badge/Input/Card/MonoLabel primitives | Partial | Files shipped + tests for Badge/Button/Card/Input. **Drift**: `Button.tsx` does NOT include the `::before` fill-wipe overlay the plan's variant treatment requires (plan: "primary (acid), secondary (border), ghost variants + fill-wipe hover" — Button has only `bg-accent-primary hover:bg-accent-hover`; no `::before` overflow-hidden wipe). **Test debt**: `MonoLabel.test.tsx` missing; `Card.test.tsx` is the Apr 20 pre-Phase-24 file — only asserts `region` role, not hover bar / olive border / translateY classes. |
| 12 — FileViewer shell | Done | `FileViewer.tsx` + `ViewerHeader.tsx` use `bg-bg-elevated` + `border-border-subtle` + tab acid-yellow underline. |
| 13 — Auth pages sweep | Done + drift | `AuthLayout.tsx` ships LIA badge + brand wordmark; `AuthCard.tsx` uses `bg-bg-elevated rounded-2xl border border-border-subtle`. **Drift**: AuthLayout LIA badge uses inline `style={{ background: var(--color-accent-primary), color: var(--color-accent-on), boxShadow: var(--shadow-accent) }}` — should use `bg-accent-primary text-accent-on shadow-accent` Tailwind classes for parity with the rest of the codebase. |
| 14 — Setup wizard sweep | NOT DONE | `frontend/src/setup/WizardProgress.tsx` uses `bg-[--color-border-subtle]` track + `duration-200` literal (plan: `duration-normal` + `9999px` radius); `WizardShell.tsx` / `WizardFooter.tsx` show no `STEP X / Y` `.ol-label-sm` mono label (plan Task 14 Step 2 explicit); `SetupPage.tsx` still uses `text-[--color-text-secondary]` `[--color-feedback-error]` arbitrary-value brackets instead of Tailwind tokens. |
| 15 — Page sweep (Settings/Portfolio/Secretary/placeholder) | Effectively done | `placeholder.tsx` matches plan exactly (`PAGE_NOT_READY` ol-label-sm card). Other pages: zero hex literals, all token-driven via inherited primitive components. |
| 16 — Report theme audit | No-op (acceptable) | Files unchanged from `885b20f`; `grep -nE '#(7c9cff|94acff|5a9bff|0f1115|12151c|161a22)' frontend/src/styles/report/*.css` returns zero matches. **Hygiene gap**: no test locks the no-blue-tokens contract — future drift goes uncaught. |
| 17 — Final acceptance walkthrough | NOT DONE | PR #41 body has no light+dark walk record; no `npm run build` exit-zero log; no acceptance checklist closure. |

**Pre-existing primitive audit (out-of-band):** `frontend/src/components/primitives/` contains four files predating Phase 24 (Apr 20): `Banner.tsx`, `FormField.tsx`, `PasswordInput.tsx`, `PasswordStrengthMeter.tsx`. They were not in the Phase 24 plan but consume the global token surface; they may reference retired tokens or use stale palette assumptions. No grep evidence of retired token usage, but no explicit verification ran.

---

## Tasks (in execution order)

### 1. **P1-28 — Implement Button `::before` fill-wipe hover overlay**
Plan Task 11 Step 1 specifies "primary (acid), secondary (border), ghost variants + fill-wipe hover" — current `Button.tsx` only has solid color swap. The fill-wipe is what gives the design system its distinctive feel; without it the buttons read as generic Tailwind buttons.

- Files (edit):
  - `frontend/src/components/primitives/Button.tsx` — add `relative overflow-hidden` to base (already present); inject `<span aria-hidden className="absolute inset-0 -translate-x-full bg-accent-hover transition-transform duration-normal ease-out group-hover:translate-x-0" />` for primary variant; gate to only render on `primary`. Match design bundle's `project/preview/buttons.html` reference (left-edge wipe, 200 ms, `cubic-bezier(0.16,1,0.3,1)`).
  - `frontend/src/components/primitives/Button.test.tsx` — add a render test that asserts the `<span aria-hidden>` exists for `variant="primary"` and is absent for `variant="secondary"` and `variant="ghost"`.
- Plan ref: Task 11 Step 1 ("`::before` fill-wipe on hover").
- Acceptance: `cd frontend && npm test -- --run Button` green; manual hover on `<Button variant="primary">Sign in</Button>` in dev shows acid → olive wipe sweeping left-to-right over `--duration-normal`.

### 2. **NEW-24-01 — Deepen `Card.test.tsx` to assert Phase-24 hover contract**
Current test predates Phase 24 (Apr 20, 365 bytes) — only asserts `<section role="region">` renders children. Phase 24 mandates `hover:-translate-y-1`, `hover:border-yellow-600`, and an `<span aria-hidden>` 2 px bar that draws left→right on hover. None of those are tested today, so a regression that strips the bar would ship green.

- Files (edit):
  - `frontend/src/components/primitives/Card.test.tsx` — add three tests:
    1. `it("renders the yellow accent bar as aria-hidden span")` — asserts `getByRole("region").querySelector("[aria-hidden='true']")` is non-null and has `bg-accent-primary` in its className.
    2. `it("composes hover translate + olive border classes on the wrapper")` — asserts the wrapper element's className contains `hover:-translate-y-1` and `hover:border-yellow-600`.
    3. `it("does not apply a default box-shadow")` — asserts the wrapper's computed className does NOT include `shadow-`. Plan Design Rule 7: "No default shadow on cards. Border-driven surface hierarchy."
- Plan ref: Task 11 Step 4 + Design Rules 7, 8.
- Acceptance: `cd frontend && npm test -- --run primitives/Card` green with 4 tests (1 existing + 3 new).

### 3. **NEW-24-02 — Add `DataRow.test.tsx` + `MonoLabel.test.tsx` smoke tests**
Plan Task 11 Step 6 explicitly mandates "one smoke test per primitive". Two primitives shipped without:

- Files (new):
  - `frontend/src/components/primitives/DataRow.test.tsx` — three tests:
    1. Renders label + value as `.ol-label` + tabular-nums spans.
    2. Renders delta as success color when `deltaDirection="pos"` (asserts inline `style.color === "var(--color-feedback-success)"` via `getAttribute("style")`).
    3. Renders delta as error color when `deltaDirection="neg"`.
  - `frontend/src/components/primitives/MonoLabel.test.tsx` — two tests:
    1. Renders children inside a span with `.ol-label` class.
    2. Forwards arbitrary props (e.g. `data-testid`).
- Plan ref: Task 11 Step 6.
- Acceptance: `cd frontend && npm test -- --run primitives/DataRow primitives/MonoLabel` green with 5 tests.

### 4. **NEW-24-03 — Restore `Sidebar.test.tsx` width assertions (220/52)**
Plan Task 5 Step 1 explicitly required updating the test from `w-[240px]/w-[60px]` to `w-[220px]/w-[52px]` so the failing test drives the implementation rewrite. The current test file has no width assertions at all — it tests link rendering only. A regression to 200px or 60px would slip through.

- Files (edit):
  - `frontend/src/components/sidebar/Sidebar.test.tsx` — add two tests inside the existing `describe("Sidebar")`:
    1. `it("renders at 220px expanded width by default")` — asserts `screen.getByRole("navigation", { name: "Main navigation" }).className` contains `w-[220px]`.
    2. `it("collapses to 52px when the toggle is clicked")` — clicks the collapse button (find by accessible name; falls back to footer-row last button), asserts the className flips to `w-[52px]`.
- Plan ref: Task 5 Step 1, Step 5 manual verification ("220 px wide … drops it to 52 px").
- Acceptance: `cd frontend && npm test -- --run Sidebar` green; both new assertions present in test report.

### 5. **NEW-24-04 — Add NavItem rail-on-active test**
Plan Task 5 Step 4 mandates "Update the NavItem test to assert the rail renders when active." Today the rail is a 2 px `<span aria-hidden>` overlay positioned absolute-left-0 with `bg-accent-primary` — visually distinctive but completely untested.

- Files (edit):
  - `frontend/src/components/sidebar/NavItem.test.tsx` (or create if absent) — add test:
    ```tsx
    it("renders the acid-yellow rail when route is active", () => {
      render(
        <MemoryRouter initialEntries={["/morning-briefing"]}>
          <NavItem path="/morning-briefing" label="Morning Briefing" Icon={Sun} />
        </MemoryRouter>
      );
      const link = screen.getByRole("link", { current: "page" });
      const rail = link.querySelector("[aria-hidden='true']");
      expect(rail).not.toBeNull();
      expect(rail!.className).toMatch(/absolute|w-\[2px\]/);
    });
    ```
- Plan ref: Task 5 Step 4.
- Acceptance: `cd frontend && npm test -- --run NavItem` green.

### 6. **NEW-24-05 — Document the six `--color-sidebar-*` tokens beyond plan surface**
`tokens.css:63-69` defines `--color-sidebar-text`, `--color-sidebar-text-strong`, `--color-sidebar-text-muted`, `--color-sidebar-hover`, `--color-sidebar-active`, `--color-sidebar-divider`. Plan Task 1 only mints `--color-sidebar-bg`. The expansion is reasonable (sidebar is the only persistent dark surface in light mode), but the plan and design-bundle README must reflect the canonical surface or future contributors will pick a different convention.

- Files (edit):
  - `frontend/src/styles/tokens.css` — add a comment block above line 63: `/* Sidebar-scoped tokens. The sidebar is the only surface that stays dark in both themes; these tokens encode the dark palette so the Tailwind layer never has to hardcode hex values. */`
  - `planning/implementation-plans/2026-04-24-phase-24-design-system-refresh.md` — append a "Token surface deltas (post-merge)" appendix section listing the six new tokens with their light-mode hex values; mark plan Task 1 with `[~]` shipped-with-additions.
  - `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md` — note in Phase 24 row of §1: "Sidebar tokens expanded beyond plan; documented post-merge."
- Plan ref: Task 1 Step 1 (token surface authority).
- Acceptance: `grep -c -- '--color-sidebar-' frontend/src/styles/tokens.css` ≥ 7; plan file contains the appendix.

### 7. **NEW-24-06 — Setup wizard sweep (plan Task 14)**
Three concrete shipped-vs-spec gaps:

- Files (edit):
  - `frontend/src/setup/WizardProgress.tsx` — replace `bg-[--color-border-subtle]` and `bg-[--color-accent-primary]` arbitrary-value brackets with Tailwind tokens (`bg-border-subtle`, `bg-accent-primary`); replace `duration-200` with `duration-normal`; add `rounded-full` to outer track; add `aria-label="Wizard progress"`.
  - `frontend/src/setup/WizardShell.tsx` — render a `<span className="ol-label-sm">{`STEP ${current.toString().padStart(2,"0")} / ${max.toString().padStart(2,"0")}`}</span>` above the title in the wizard chrome. Plan Task 14 Step 2.
  - `frontend/src/pages/SetupPage.tsx` — replace `text-[--color-text-secondary]` / `[--color-feedback-error]` / `border-[--color-border-secondary]` / `rounded-[--radius-md]` arbitrary-value brackets with Tailwind tokens (`text-text-secondary`, `text-feedback-error`, `border-border-secondary`, `rounded-md`). Bracket-syntax tokens bypass the `tailwind.config.ts` mapping and produce identical output but break the codebase convention.
  - `frontend/src/setup/WizardShell.test.tsx` — add a test asserting the `STEP 01 / 06` (or current/max) label renders.
- Plan ref: Task 14 Steps 1–3.
- Acceptance: `cd frontend && npm test -- --run Wizard Setup` green; manual: open `/setup` in dev, see "STEP 01 / 06" mono label above each step title; progress bar is a pill (`rounded-full`).

### 8. **NEW-24-07 — Audit pre-Phase-24 primitives against new tokens**
`Banner.tsx`, `FormField.tsx`, `PasswordInput.tsx`, `PasswordStrengthMeter.tsx` ship dated Apr 20 (predate Phase 24 by 4 days). They consume the token surface but were not in the Phase 24 sweep — silent palette drift would slip through.

- Files (verify; edit only on findings):
  - `frontend/src/components/primitives/Banner.tsx` — confirm only token classes (`bg-bg-`, `text-text-`, `border-border-`, `feedback-*`); replace any `[--color-…]` bracket-syntax with Tailwind tokens.
  - `frontend/src/components/primitives/FormField.tsx` — same.
  - `frontend/src/components/primitives/PasswordInput.tsx` — same.
  - `frontend/src/components/primitives/PasswordStrengthMeter.tsx` — verify the strength bar uses `feedback-error` / `feedback-warning` / `feedback-success` (olive/amber/terracotta), not retired bright reds/greens.
- Acceptance: `grep -nE '\[--color-|#[0-9A-Fa-f]{3,8}' frontend/src/components/primitives/Banner.tsx frontend/src/components/primitives/FormField.tsx frontend/src/components/primitives/PasswordInput.tsx frontend/src/components/primitives/PasswordStrengthMeter.tsx` returns zero matches; `npm test -- --run primitives` stays green.

### 9. **NEW-24-08 — AuthLayout Tailwind class consistency**
The LIA badge in `AuthLayout.tsx:11-19` uses inline `style={{ background: "var(--color-accent-primary)", color: "var(--color-accent-on)", boxShadow: "var(--shadow-accent)" }}`. Sidebar header at `Sidebar.tsx:48-53` uses the same inline pattern. Plan and `tailwind.config.ts` expose `bg-accent-primary`, `text-accent-on`, and `shadow-accent` as first-class utilities — using them keeps grep-discoverability uniform.

- Files (edit):
  - `frontend/src/components/auth/AuthLayout.tsx` — swap the badge to `<span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-md font-bold text-[10px] bg-accent-primary text-accent-on shadow-accent">LIA</span>`.
  - `frontend/src/components/sidebar/Sidebar.tsx` — same swap on the brand-header LIA badge (lines ~46-53). Keep the inline `color: "var(--color-sidebar-text)"` props (those tokens are sidebar-scoped and not exposed as Tailwind utilities — see NEW-24-05).
- Plan ref: design-system normalization (rule 12 "use motion tokens" generalized to "use token utilities, not inline CSS variables").
- Acceptance: `grep -n 'var(--color-accent-primary)' frontend/src/components/auth/AuthLayout.tsx frontend/src/components/sidebar/Sidebar.tsx` returns zero matches; visual regression nil.

### 10. **NEW-24-09 — Lock the no-blue-tokens contract on report themes**
Task 16 was a passive no-op because no blue references existed. To keep it that way, add a vitest that scans `frontend/src/styles/report/*.css` and fails if any of the retired blue hex values are reintroduced.

- Files (new):
  - `frontend/src/styles/report/__tests__/no_retired_blue.test.ts`:
    ```ts
    import { readFileSync, readdirSync } from "node:fs";
    import { resolve } from "node:path";
    import { describe, it, expect } from "vitest";

    const RETIRED = /#(7c9cff|94acff|5a9bff|0f1115|12151c|161a22)\b/i;

    describe("report themes", () => {
      const dir = resolve(__dirname, "..");
      const files = readdirSync(dir).filter((f) => f.endsWith(".css"));
      for (const f of files) {
        it(`${f} contains no retired blue tokens`, () => {
          const text = readFileSync(resolve(dir, f), "utf-8");
          expect(text).not.toMatch(RETIRED);
        });
      }
    });
    ```
- Plan ref: Task 16.
- Acceptance: `cd frontend && npm test -- --run no_retired_blue` green; deliberately injecting `#7c9cff` into `theme-light.css` makes it red.

### 11. **NEW-24-10 — Final acceptance walkthrough (plan Task 17)**
Plan Task 17 mandates a manual light+dark walk of every page + `uv run pytest && cd frontend && npm test -- --run && npm run lint && npm run build`. PR #41 body includes a checkbox-style test plan but no commit / artifact proves it ran.

- Files (new):
  - `planning/audits/fix-plans/phase-24-acceptance-walkthrough.md` — short doc capturing the dual-theme walk results: per-page screenshot or text confirmation of (a) Geist body font, (b) cream/near-black background, (c) sidebar 220 px + acid rail, (d) breadcrumb + LIVE pill on `/morning-briefing`, (e) DM Serif greeting on Home, (f) card hover olive border + yellow bar, (g) chat composer focus glow, (h) LIA badge glow, (i) zero emoji, (j) zero hex in `src/**/*.tsx` (Task 0 grep), (k) theme persistence across reload.
- Files (verify; commit log evidence):
  - `cd frontend && npm run build` — exit 0; commit the resulting `dist/index.html` reference into the walkthrough doc as the "build smoke" line.
  - `uv run pytest && cd frontend && npm test -- --run && npm run lint` — exit 0 across the three commands.
- Plan ref: Task 17 Steps 1–3.
- Acceptance: walkthrough doc exists, lists all 11 acceptance items as `[x]`, and the doc is referenced from `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md` Phase 24 row.

### 12. **NEW-24-11 — Lock the "zero hex literals in src" contract with a vitest**
Plan Task 15 Step 3 is the canonical `grep -rnE '#[0-9A-Fa-f]{3,8}\b' frontend/src --include='*.{ts,tsx}' | grep -v 'tokens.css'` invariant. Currently uncodified — a regression slips through.

- Files (new):
  - `frontend/src/styles/__tests__/no_hex_literals.test.ts`:
    ```ts
    import { execSync } from "node:child_process";
    import { describe, it, expect } from "vitest";

    describe("frontend source", () => {
      it("contains no hex color literals outside tokens.css", () => {
        const out = execSync(
          "grep -rnE '#[0-9A-Fa-f]{3,8}\\b' src --include='*.tsx' --include='*.ts' | grep -v tokens.css | grep -v '&#' || true",
          { cwd: process.cwd(), encoding: "utf-8" }
        );
        expect(out.trim()).toBe("");
      });
    });
    ```
  - Note the `grep -v '&#'` suppresses HTML entities like `&#9612;` (a Unicode block character used in `AssistantMessage.tsx:29` as a streaming-cursor glyph).
- Plan ref: Task 15 Step 3.
- Acceptance: `cd frontend && npm test -- --run no_hex_literals` green today; deliberately adding `color: #ff0000` to any `.tsx` file makes it red.

---

## Verification (one shot)

```bash
# Unit tests + lint + build
cd frontend && npm test -- --run && npm run lint && npm run build && cd ..

# Hex-literal invariant (Task 15 Step 3)
grep -rnE '#[0-9A-Fa-f]{3,8}\b' frontend/src --include='*.tsx' --include='*.ts' | grep -v tokens.css | grep -v '&#' && echo "FAIL: hex literals present" || echo "OK"

# Retired-token usage outside tokens.css
grep -rnE 'color-bg-app|color-surface-info|duration-base' frontend/src --include='*.tsx' --include='*.ts' --include='*.css' | grep -v tokens.css && echo "FAIL: retired tokens used" || echo "OK"

# Required font assets
test -f frontend/public/fonts/Geist_wght_.ttf && echo "OK Geist"
grep -F "IBM+Plex+Mono" frontend/index.html >/dev/null && echo "OK Plex Mono link"
grep -F "DM+Serif+Display" frontend/index.html >/dev/null && echo "OK DM Serif link"

# Sidebar widths shipped
grep -F 'w-[220px]' frontend/src/components/sidebar/Sidebar.tsx && grep -F 'w-[52px]' frontend/src/components/sidebar/Sidebar.tsx && echo "OK sidebar widths"

# All primitives have a smoke test
for p in Card Input Badge Button MonoLabel DataRow; do
  test -f "frontend/src/components/primitives/$p.test.tsx" && echo "OK $p" || echo "MISSING $p.test.tsx"
done

# Final acceptance doc exists
test -f planning/audits/fix-plans/phase-24-acceptance-walkthrough.md && echo "OK walkthrough"
```

Every line must print `OK …` (or empty for the negative greps).

---

## ID cross-reference

| ID         | Source        | Title                                                    | Severity |
|------------|---------------|----------------------------------------------------------|----------|
| P1-28      | Audit         | Button missing `::before` fill-wipe hover overlay        | P1       |
| NEW-24-01  | Audit         | Deepen `Card.test.tsx` to assert hover bar + olive border | P2      |
| NEW-24-02  | Audit         | `DataRow.test.tsx` + `MonoLabel.test.tsx` smoke tests    | P2       |
| NEW-24-03  | Audit         | Restore `Sidebar.test.tsx` width assertions (220/52)     | P2       |
| NEW-24-04  | Audit         | NavItem rail-on-active test                              | P2       |
| NEW-24-05  | Audit         | Document six `--color-sidebar-*` tokens beyond plan      | P2       |
| NEW-24-06  | Audit         | Setup wizard sweep (plan Task 14)                        | P1       |
| NEW-24-07  | Audit         | Pre-Phase-24 primitives (Banner/FormField/Pwd*) audit    | P2       |
| NEW-24-08  | Audit         | AuthLayout/Sidebar inline-style → Tailwind class swap    | P2       |
| NEW-24-09  | Audit         | Lock no-blue-tokens contract on report themes (vitest)   | P2       |
| NEW-24-10  | Audit         | Final acceptance walkthrough doc + build smoke           | P2       |
| NEW-24-11  | Audit         | Lock no-hex-literals contract on src (vitest)            | P2       |
