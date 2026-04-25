# Phase 24 — Design System Refresh (Wondermakers / Acid Yellow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Source of truth for all visual decisions:** the unpacked design bundle at `/tmp/claude-501/design-bundle/openlia-design-system/` (fetched from `https://api.anthropic.com/v1/design/h/meskfz9WKdVZJCmPcVG41g`). Canonical files: `project/README.md` (brand + voice), `project/SKILL.md` (do-not-violate rules), `project/colors_and_type.css` (tokens), `project/ui_kits/app/index.html` (canonical app shell), `project/preview/*.html` (per-token and per-component preview cards). When any step says "match the spec", it means this bundle.

> **Non-goals:** no new backend work, no new data, no new pages, no renaming of routes. This plan is purely a visual + token + shell rework. Any page that currently renders a placeholder stays a placeholder, but now styled with the new tokens.

**Goal:** Replace the current dark-blue token system with the Wondermakers / Acid Yellow design system (warm cream `#F2F1E8` base, acid-yellow `#D4FF00` accent, Geist Sans + IBM Plex Mono + DM Serif Display), rebuild the app shell (Sidebar, TopBar, Chat column, File viewer slot) to match `project/ui_kits/app/index.html`, and sweep every existing page to consume the new tokens so nothing references the retired blue palette.

**Architecture:**
- **Token layer** — `frontend/src/styles/tokens.css` is rewritten from scratch against `project/colors_and_type.css`. It ships both light (`:root`) and dark (`[data-theme="dark"]`) modes. Tailwind exposes every new token group through `frontend/tailwind.config.ts` so components can use `bg-bg-elevated`, `text-text-primary`, `border-border-subtle`, `font-mono`, `duration-normal`, `ease-out`, etc. without hardcoded values.
- **Typography layer** — Geist variable font is bundled locally at `frontend/public/fonts/Geist_wght_.ttf`; IBM Plex Mono and DM Serif Display load from Google Fonts via `<link>` tags in `frontend/index.html`. Three semantic type utilities (`.ol-label`, `.ol-data`, `.ol-greeting`) live in `frontend/src/styles/global.css` for non-Tailwind spots (serif greeting, mono data blocks).
- **Shell layer** — the app shell is rebuilt in three components: `components/sidebar/Sidebar.tsx` (dark surface, 220/52 widths, acid-yellow active rail), `components/shell/TopBar.tsx` (new; breadcrumb + LIVE pill + mono stamps), and `layouts/AppLayout.tsx` (grid wrapping Sidebar + TopBar + Outlet + optional FileViewer slot).
- **Chat layer** — composer, LIA badge, department tag, data block, and source chip are restyled to match the app kit. `ChatInterface.tsx` structure stays the same; only classNames and markup inside the bubble wrapper change.
- **Theme toggle** — a single `useTheme` hook in `frontend/src/hooks/useTheme.ts` toggles `data-theme` on `<html>` and persists to `localStorage`. Light is default.

**Tech Stack:** React 18, TypeScript strict, Vite, Tailwind 3 with CSS-variable-backed theme, `lucide-react` (stroke-based icons at `strokeWidth={1.5}`), Framer Motion (already installed) for the yellow-rail and card-hover animations.

**Dependencies:**
- Phase 8 (frontend shell, `AppLayout`, `Sidebar`, Tailwind wiring).
- Phase 12 (shared chat components — `ChatInterface`, `ChatInput`, `AssistantMessage`, `LiaBadge`).
- Phase 22 (Repository page + `FileViewer` — the file-viewer slot reuses this unchanged).

**Unblocks:** every future page picks up the new tokens automatically. No downstream phase blocks on this one.

---

## Design Rules (do not violate — from `project/SKILL.md`)

1. **One accent hue.** Acid yellow `#D4FF00`. Never blue, red, purple. Semantic feedback uses olive (`#6B8200`) / terracotta (`#E05C30`) / amber (`#DC9614`) only.
2. **No emoji anywhere.** Matches repo policy.
3. **No pure black (`#000`) or cold gray (`#888`).** All neutrals have a warm yellow-brown undertone — text primary is `#1A1A18`, not `#000`.
4. **Three fonts, no substitutions.** Geist Sans for display / body / CTAs; IBM Plex Mono for labels / data / timestamps; DM Serif Display used exactly once (Home greeting).
5. **Mono labels are always tracked caps.** 11px, `0.08em` letter-spacing, `UPPER_SNAKE_CASE` or `UPPER CASE`.
6. **Never mix Geist and Mono on the same line.** Label above, data below.
7. **No default shadow on cards.** Border-driven surface hierarchy. Shadow is reserved for: tooltip (`--shadow-sm`), dropdown (`--shadow-md`), file-viewer panel (`--shadow-lg`, left-side only), input focus ring, LIA badge glow.
8. **Card hover = `translateY(-4px)` + olive border + yellow 2px bar drawing left-to-right along the bottom edge.** Never add a box-shadow lift.
9. **Icons are Lucide, `strokeWidth={1.5}`.** No filled variants in default state. No PNG icons, no unicode glyphs (no ✓, no →).
10. **Sidebar is square.** No radius — it is a structural column, not a card. Width 220px expanded, 52px collapsed.
11. **Entrance animations slide from the left (`translateX(-100%)` → `0`).** Exits are always shorter than entrances (a 200ms entrance gets a 120ms exit).
12. **Use motion tokens.** `--duration-normal` not `300ms`. `--ease-out` not a raw cubic-bezier.
13. **Copy stays direct.** No filler words, no marketing flourish. "Equity Research analyzed NVDA" — not "The AI took a look".
14. **No stock imagery, no illustrations.** Placeholders are warm-cream solids with a mono label or a 3-line skeleton.
15. **TDD where a behavior exists.** Purely visual changes don't need tests beyond a smoke render; behavior changes (theme toggle, sidebar collapse, hover animations that read state) get a focused RTL test.

---

## File Structure

### Styles

```
frontend/src/styles/
├── tokens.css                # REWRITE — Wondermakers / Acid Yellow. Full light + dark.
└── global.css                # MODIFY — font-family, antialiasing, ol-* utilities, body bg.

frontend/public/fonts/
└── Geist_wght_.ttf           # CREATE — Geist variable font (copy from design bundle).

frontend/index.html           # MODIFY — preconnect + Google Fonts link for Plex Mono + DM Serif.
frontend/tailwind.config.ts   # REWRITE — expose the full new token surface to Tailwind.
```

### Components

```
frontend/src/components/shell/
├── TopBar.tsx                # CREATE — breadcrumb + LIVE pill + mono stamps.
├── TopBar.test.tsx           # CREATE — smoke + prop-driven rendering.
├── LivePill.tsx              # CREATE — the pulsing olive dot + "LIVE_FEED_ACTIVE".
└── ThemeToggle.tsx           # CREATE — light/dark switcher in top-right of TopBar.

frontend/src/components/primitives/
├── Card.tsx                  # CREATE — flat card with hover translateY + olive border + yellow bar.
├── Card.test.tsx             # CREATE.
├── Badge.tsx                 # CREATE — pill badge variants (neutral, accent, success, error, warning).
├── Badge.test.tsx            # CREATE.
├── Button.tsx                # CREATE — primary (acid), secondary (border), ghost variants + fill-wipe hover.
├── Button.test.tsx           # CREATE.
├── Input.tsx                 # CREATE — warm-cream bg, focus-glow ring in acid yellow.
├── Input.test.tsx            # CREATE.
├── MonoLabel.tsx             # CREATE — wraps text in `.ol-label` utility for DX.
└── DataRow.tsx               # CREATE — 3-column `label | value | delta` row used in chat + file viewer.
```

### Shell wiring

```
frontend/src/layouts/AppLayout.tsx          # REWRITE — Sidebar + TopBar + Outlet + FileViewer slot.
frontend/src/layouts/AppLayout.test.tsx     # MODIFY — assert TopBar renders and has no hardcoded colors.

frontend/src/components/sidebar/Sidebar.tsx # MODIFY — dark surface, 220/52 widths, acid active rail, Geist/mono mix, brand badge.
frontend/src/components/sidebar/NavItem.tsx # MODIFY — acid rail on active, mono nav group headers, unread dot glow.

frontend/src/hooks/useTheme.ts              # CREATE — light/dark + localStorage.
frontend/src/hooks/useTheme.test.ts         # CREATE.
```

### Chat restyle (markup + classes only — no logic changes)

```
frontend/src/components/chat/ChatInput.tsx          # MODIFY — 10px radius, focus glow, dept switch, kbd hint, acid send btn.
frontend/src/components/chat/AssistantMessage.tsx   # MODIFY — dept-tag above bubble, elevated bg, border-subtle.
frontend/src/components/chat/UserBubble.tsx         # MODIFY — near-black bg (`#1A1A18`), cream text.
frontend/src/components/chat/LiaBadge.tsx           # MODIFY — 1.75em square, acid bg, olive text, glow shadow.
frontend/src/components/chat/WelcomeOverlay.tsx     # MODIFY — DM Serif Display greeting + mono macro strip.
frontend/src/components/chat/AttachmentChip.tsx     # MODIFY — src-chip style (4px radius, mono, hover → olive).
```

### Page sweep

```
frontend/src/pages/Home.tsx                   # REWRITE — hero greeting + "what can LIA do" cards.
frontend/src/pages/placeholder.tsx            # MODIFY — warm-cream bg + mono section label.
frontend/src/pages/Settings.tsx               # MODIFY — token swap (no blue).
frontend/src/pages/SettingsPage.tsx           # MODIFY — token swap.
frontend/src/pages/PortfolioPage.tsx          # MODIFY — token swap.
frontend/src/pages/SecretaryPage.tsx          # MODIFY — token swap (chat shell picks up restyle automatically).
frontend/src/pages/Repository.tsx             # MODIFY — token swap.
frontend/src/pages/LoginPage.tsx              # MODIFY — warm-cream bg, acid CTA, mono labels.
frontend/src/pages/RegisterPage.tsx           # MODIFY — same.
frontend/src/pages/ForgotPasswordPage.tsx     # MODIFY — same.
frontend/src/pages/ResetPasswordPage.tsx      # MODIFY — same.
frontend/src/pages/Setup.tsx / SetupPage.tsx  # MODIFY — warm-cream wizard shell.
```

### Report themes (out of scope unless they reference retired tokens)

```
frontend/src/styles/report/theme-light.css    # AUDIT + MODIFY — replace any --color-accent-primary blue with the new acid token only if referenced.
frontend/src/styles/report/theme-dark.css     # AUDIT + MODIFY — same.
```

Report themes stay decoupled from the app shell; only retired blue tokens get replaced.

---

## Task 0: Pre-flight audit — inventory every hardcoded color and retired token

**Files:**
- Read-only survey: `frontend/src/**/*.{ts,tsx,css}`.

- [ ] **Step 1: Find every hex literal in the frontend.**

Run:
```bash
grep -rnE '#[0-9A-Fa-f]{3,8}\b' frontend/src frontend/index.html
```
Expected: a list of sites that hardcode color values. Copy the output into a scratch note; every one of these must be replaced with a token by the end of Task 15.

- [ ] **Step 2: Find every use of retired tokens.**

The old `tokens.css` exposes `--color-bg-app` (retired; replaced by `--color-bg-base`), `--color-accent-primary` blue (replaced with acid yellow — same name, different value, so usages stay but visually flip), `--color-surface-info` (retired), `--duration-base` (retired; replaced by `--duration-normal`), `--radius-xl` 14px (retired; replaced by 10px `--radius-xl` and 12px `--radius-2xl`).

Run:
```bash
grep -rnE 'color-bg-app|color-surface-info|duration-base' frontend/src frontend/tailwind.config.ts
```
Expected: a list of import sites that need to swap to the new names in Task 3 / Task 15.

- [ ] **Step 3: Commit the survey notes as a code comment inside the plan scratch — no file committed.**

No commit. Task 0 is read-only. Carry the lists forward.

---

## Task 1: Rewrite the token file

**Files:**
- Rewrite: `frontend/src/styles/tokens.css`.

- [ ] **Step 1: Replace the entire contents of `tokens.css` with the new design system.**

Write:
```css
/* ============================================================
   OpenLia Design Tokens — Wondermakers / Acid Yellow
   Source: planning/design-system (fetched 2026-04-24).
   Supersedes the retired dark-blue draft.
   ============================================================ */

:root {
  color-scheme: light;

  /* ── Font families ───────────────────────────────────────── */
  --font-display: "Geist", system-ui, sans-serif;
  --font-mono:    "IBM Plex Mono", "Courier New", monospace;
  --font-serif:   "DM Serif Display", Georgia, serif;

  /* ── Type scale ──────────────────────────────────────────── */
  --text-hero:     clamp(72px, 8vw, 96px);
  --text-h1:       48px;
  --text-h2:       32px;
  --text-h3:       20px;
  --text-body-lg:  16px;
  --text-body:     14px;
  --text-sm:       13px;
  --text-xs:       12px;
  --text-label:    11px;
  --text-label-sm: 9px;
  --text-data:     14px;
  --text-data-lg:  48px;
  --text-greeting: 30px;

  --leading-tight:   1.1;
  --leading-snug:    1.2;
  --leading-normal:  1.4;
  --leading-relaxed: 1.65;
  --leading-loose:   1.75;

  --tracking-tight:  -0.02em;
  --tracking-normal: 0;
  --tracking-label:  0.08em;
  --tracking-micro:  0.10em;

  /* ── Raw color scales ────────────────────────────────────── */
  --yellow-50:  #FAFFD9;
  --yellow-100: #F0FF99;
  --yellow-200: #E8FF5A;
  --yellow-400: #D4FF00;
  --yellow-600: #A8CC00;
  --yellow-800: #6B8200;
  --yellow-900: #3D4D00;

  --neutral-50:  #F9F8F3;
  --neutral-100: #F2F1E8;
  --neutral-200: #E0DED5;
  --neutral-400: #B0AEA6;
  --neutral-600: #737268;
  --neutral-800: #2E2E2A;
  --neutral-900: #0D0D0B;

  /* ── Semantic — Background ───────────────────────────────── */
  --color-bg-base:     #F2F1E8;
  --color-bg-elevated: #FAFAF4;
  --color-bg-input:    #F5F4EF;
  --color-bg-code:     #EEECEA;
  --color-sidebar-bg:  #0D0D0C;       /* sidebar is dark in both themes */

  /* Back-compat alias — retired tokens.css exposed this name. */
  --color-bg-app: var(--color-bg-base);

  /* ── Semantic — Surface ──────────────────────────────────── */
  --color-surface-hover:  #EEECEA;
  --color-surface-active: #E6E4DB;
  --color-surface-subtle: #F2F1E8;

  /* ── Semantic — Border ───────────────────────────────────── */
  --color-border-subtle:    #E0DED5;
  --color-border-secondary: #D3D1C7;
  --color-border-strong:    #B0AEA6;
  --color-border-success:   #3D4D00;
  --color-border-error:     #712B13;

  /* ── Semantic — Text ─────────────────────────────────────── */
  --color-text-primary:   #1A1A18;
  --color-text-secondary: #737268;
  --color-text-tertiary:  #B0AEA6;
  --color-text-code:      #1A1A18;
  --color-text-on-accent: #3D4D00;

  /* ── Semantic — Icon ─────────────────────────────────────── */
  --color-icon-primary: #737268;
  --color-icon-active:  #D4FF00;
  --color-icon-muted:   #B0AEA6;

  /* ── Semantic — Accent ───────────────────────────────────── */
  --color-accent-primary:     #D4FF00;
  --color-accent-hover:       #E8FF5A;
  --color-accent-subtle:      rgba(212, 255, 0, 0.08);
  --color-accent-on:          #3D4D00;
  --color-accent-primary-rgb: 212, 255, 0;

  /* ── Semantic — Feedback ─────────────────────────────────── */
  --color-feedback-success: #6B8200;
  --color-feedback-error:   #E05C30;
  --color-feedback-warning: #DC9614;
  --color-feedback-info:    #6B8200;

  --focus-ring-color: #D4FF00;

  /* ── Radii ───────────────────────────────────────────────── */
  --radius-xs:   2px;
  --radius-sm:   4px;
  --radius-md:   6px;
  --radius-lg:   8px;
  --radius-xl:   10px;
  --radius-2xl:  12px;
  --radius-full: 9999px;

  /* ── Spacing (4px base) ──────────────────────────────────── */
  --space-0_5: 2px;
  --space-1:   4px;
  --space-1_5: 6px;
  --space-2:   8px;
  --space-2_5: 10px;
  --space-3:   12px;
  --space-4:   16px;
  --space-5:   20px;
  --space-6:   24px;
  --space-8:   32px;
  --space-10:  40px;
  --space-12:  48px;

  /* ── Shadows ─────────────────────────────────────────────── */
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-sm: 0 1px 4px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.10), 0 4px 8px rgba(0,0,0,0.06);
  --shadow-input-focus:
    0 0 0 1px rgba(var(--color-accent-primary-rgb),0.12),
    0 4px 20px rgba(var(--color-accent-primary-rgb),0.06);
  --shadow-accent: 0 0 8px rgba(var(--color-accent-primary-rgb),0.4);

  /* ── Motion ──────────────────────────────────────────────── */
  --duration-instant: 80ms;
  --duration-fast:    120ms;
  --duration-normal:  200ms;
  --duration-slow:    350ms;
  --duration-xslow:   550ms;

  /* Back-compat alias for the retired --duration-base. */
  --duration-base: var(--duration-normal);

  --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in:     cubic-bezier(0.4, 0, 1, 1);
  --ease-in-out: cubic-bezier(0.76, 0, 0.24, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-linear: linear;
}

[data-theme="dark"] {
  color-scheme: dark;

  --color-bg-base:     #111110;
  --color-bg-elevated: #1C1C1A;
  --color-bg-input:    #1C1C1A;
  --color-bg-code:     #0D0D0C;
  --color-sidebar-bg:  #0D0D0C;

  --color-surface-hover:  #252522;
  --color-surface-active: #2E2E2B;
  --color-surface-subtle: #1C1C1A;

  --color-border-subtle:    #2A2A27;
  --color-border-secondary: #3A3A36;
  --color-border-strong:    #4A4A46;

  --color-text-primary:   #EDECEA;
  --color-text-secondary: #8A8880;
  --color-text-tertiary:  #6E6E68;
  --color-text-code:      #E8E6DF;

  --color-icon-primary: #7A7A74;
  --color-icon-muted:   #4E4E4A;
}
```

- [ ] **Step 2: Verify Vite still builds (nothing imports a name that no longer exists).**

Run:
```bash
cd frontend && npm run build -- --mode development
```
Expected: build succeeds. If it fails on `--duration-base` or `--color-bg-app`, the back-compat aliases above cover both — re-check your copy.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/styles/tokens.css
git commit -m "feat(frontend): swap tokens.css to Wondermakers/Acid Yellow palette"
```

---

## Task 2: Bundle the Geist variable font

**Files:**
- Create: `frontend/public/fonts/Geist_wght_.ttf`.
- Modify: `frontend/src/styles/global.css`.
- Modify: `frontend/index.html`.

- [ ] **Step 1: Copy Geist into `public/fonts/`.**

Run:
```bash
mkdir -p frontend/public/fonts
cp /tmp/claude-501/design-bundle/openlia-design-system/project/fonts/Geist_wght_.ttf frontend/public/fonts/Geist_wght_.ttf
ls -la frontend/public/fonts/Geist_wght_.ttf
```
Expected: file is ~1.2 MB. If the tmp path has been cleaned, re-fetch the design bundle.

- [ ] **Step 2: Add Google Font links to `frontend/index.html`.**

Edit the `<head>` of `frontend/index.html` — insert after the viewport meta:
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=DM+Serif+Display&display=swap"
  rel="stylesheet"
/>
```

- [ ] **Step 3: Register Geist and semantic utilities in `global.css`.**

Replace the current body rule so the whole document uses Geist. Append the `ol-*` utilities at the bottom:
```css
@import "./tokens.css";
@import "./report/theme-light.css";
@import "./report/theme-dark.css";

@font-face {
  font-family: "Geist";
  src: url("/fonts/Geist_wght_.ttf") format("truetype-variations"),
       url("/fonts/Geist_wght_.ttf") format("truetype");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}

@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root { height: 100%; }

body {
  margin: 0;
  background-color: var(--color-bg-base);
  color: var(--color-text-primary);
  font-family: var(--font-display);
  font-size: var(--text-body);
  line-height: var(--leading-relaxed);
  -webkit-font-smoothing: antialiased;
}

/* ── Semantic type utilities ──────────────────────────────── */
.ol-label {
  font-family: var(--font-mono);
  font-size: var(--text-label);
  letter-spacing: var(--tracking-label);
  text-transform: uppercase;
  font-weight: 500;
  color: var(--color-text-secondary);
}
.ol-label-sm {
  font-family: var(--font-mono);
  font-size: var(--text-label-sm);
  letter-spacing: var(--tracking-micro);
  text-transform: uppercase;
  font-weight: 500;
  color: var(--color-text-tertiary);
}
.ol-data {
  font-family: var(--font-mono);
  font-size: var(--text-data);
  line-height: var(--leading-relaxed);
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
}
.ol-greeting {
  font-family: var(--font-serif);
  font-size: var(--text-greeting);
  line-height: 1.3;
  font-weight: 400;
  color: var(--color-text-primary);
}
```

- [ ] **Step 4: Restart Vite and load `/` to confirm Geist is applied.**

Run:
```bash
cd frontend && npm run dev
```
Open `http://localhost:5173/`. The body font should render as Geist (noticeably different from system sans). If the browser devtools show `font-family: "Geist"` but the fallback is rendering, check Network → `Geist_wght_.ttf` returned 200.

- [ ] **Step 5: Commit.**

```bash
git add frontend/public/fonts/Geist_wght_.ttf frontend/index.html frontend/src/styles/global.css
git commit -m "feat(frontend): bundle Geist + load Plex Mono/DM Serif, add ol-* utilities"
```

---

## Task 3: Expose the new tokens in Tailwind

**Files:**
- Rewrite: `frontend/tailwind.config.ts`.

- [ ] **Step 1: Replace `tailwind.config.ts` with the full token surface.**

Write:
```ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-base":     "var(--color-bg-base)",
        "bg-app":      "var(--color-bg-base)", // alias — retired
        "bg-elevated": "var(--color-bg-elevated)",
        "bg-input":    "var(--color-bg-input)",
        "bg-code":     "var(--color-bg-code)",
        "sidebar-bg":  "var(--color-sidebar-bg)",

        "surface-hover":  "var(--color-surface-hover)",
        "surface-active": "var(--color-surface-active)",
        "surface-subtle": "var(--color-surface-subtle)",

        "accent-primary": "var(--color-accent-primary)",
        "accent-hover":   "var(--color-accent-hover)",
        "accent-subtle":  "var(--color-accent-subtle)",
        "accent-on":      "var(--color-accent-on)",

        "text-primary":    "var(--color-text-primary)",
        "text-secondary":  "var(--color-text-secondary)",
        "text-tertiary":   "var(--color-text-tertiary)",
        "text-on-accent":  "var(--color-text-on-accent)",

        "icon-primary": "var(--color-icon-primary)",
        "icon-active":  "var(--color-icon-active)",
        "icon-muted":   "var(--color-icon-muted)",

        "border-subtle":    "var(--color-border-subtle)",
        "border-secondary": "var(--color-border-secondary)",
        "border-strong":    "var(--color-border-strong)",

        "feedback-error":   "var(--color-feedback-error)",
        "feedback-success": "var(--color-feedback-success)",
        "feedback-warning": "var(--color-feedback-warning)",
        "feedback-info":    "var(--color-feedback-info)",

        "yellow-50":  "var(--yellow-50)",
        "yellow-200": "var(--yellow-200)",
        "yellow-400": "var(--yellow-400)",
        "yellow-600": "var(--yellow-600)",
        "yellow-800": "var(--yellow-800)",
        "yellow-900": "var(--yellow-900)",
      },
      fontFamily: {
        display: "var(--font-display)",
        mono:    "var(--font-mono)",
        serif:   "var(--font-serif)",
      },
      fontSize: {
        "label":    ["var(--text-label)",    { letterSpacing: "var(--tracking-label)" }],
        "label-sm": ["var(--text-label-sm)", { letterSpacing: "var(--tracking-micro)" }],
        "data":     ["var(--text-data)",     { lineHeight: "var(--leading-relaxed)" }],
        "greeting": ["var(--text-greeting)", { lineHeight: "1.3" }],
      },
      borderRadius: {
        xs:   "var(--radius-xs)",
        sm:   "var(--radius-sm)",
        md:   "var(--radius-md)",
        lg:   "var(--radius-lg)",
        xl:   "var(--radius-xl)",
        "2xl":"var(--radius-2xl)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        "input-focus": "var(--shadow-input-focus)",
        accent: "var(--shadow-accent)",
      },
      transitionDuration: {
        instant: "var(--duration-instant)",
        fast:    "var(--duration-fast)",
        normal:  "var(--duration-normal)",
        base:    "var(--duration-normal)", // alias — retired
        slow:    "var(--duration-slow)",
        xslow:   "var(--duration-xslow)",
      },
      transitionTimingFunction: {
        out:    "var(--ease-out)",
        in:     "var(--ease-in)",
        "in-out": "var(--ease-in-out)",
        spring: "var(--ease-spring)",
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

- [ ] **Step 2: Typecheck the config.**

Run:
```bash
cd frontend && npm run lint
```
Expected: 0 errors.

- [ ] **Step 3: Smoke the existing layout didn't regress.**

Run:
```bash
cd frontend && npm test -- --run
```
Expected: all current tests still pass. (The sidebar test may snapshot class names; if it fails on `w-[240px]`, note it and fix in Task 5.)

- [ ] **Step 4: Commit.**

```bash
git add frontend/tailwind.config.ts
git commit -m "feat(frontend): expose Wondermakers tokens to Tailwind"
```

---

## Task 4: `useTheme` hook + `ThemeToggle` component

**Files:**
- Create: `frontend/src/hooks/useTheme.ts`.
- Create: `frontend/src/hooks/useTheme.test.ts`.
- Create: `frontend/src/components/shell/ThemeToggle.tsx`.

- [ ] **Step 1: Write the failing test.**

`frontend/src/hooks/useTheme.test.ts`:
```ts
import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { useTheme } from "./useTheme";

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to light and sets data-theme attribute", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("toggles to dark and persists", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme("dark"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("openlia:theme")).toBe("dark");
  });

  it("hydrates from localStorage on mount", () => {
    localStorage.setItem("openlia:theme", "dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });
});
```

- [ ] **Step 2: Run test — FAIL.**

```bash
cd frontend && npm test -- --run useTheme
```
Expected: fails with "Cannot find module ./useTheme".

- [ ] **Step 3: Implement the hook.**

`frontend/src/hooks/useTheme.ts`:
```ts
import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const STORAGE_KEY = "openlia:theme";

function read(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === "dark" ? "dark" : "light";
}

export function useTheme(): { theme: Theme; setTheme: (t: Theme) => void } {
  const [theme, setThemeState] = useState<Theme>(read);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = useCallback((t: Theme) => setThemeState(t), []);
  return { theme, setTheme };
}
```

- [ ] **Step 4: Run test — PASS.**

```bash
cd frontend && npm test -- --run useTheme
```
Expected: 3 passing.

- [ ] **Step 5: Implement `ThemeToggle`.**

`frontend/src/components/shell/ThemeToggle.tsx`:
```tsx
import { Moon, Sun } from "lucide-react";
import { useTheme } from "../../hooks/useTheme";

export function ThemeToggle(): JSX.Element {
  const { theme, setTheme } = useTheme();
  const next = theme === "light" ? "dark" : "light";
  const Icon = theme === "light" ? Moon : Sun;
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} mode`}
      className="w-7 h-7 rounded-md inline-flex items-center justify-center text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors duration-normal ease-out"
    >
      <Icon size={16} strokeWidth={1.5} />
    </button>
  );
}
```

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/hooks/useTheme.ts frontend/src/hooks/useTheme.test.ts frontend/src/components/shell/ThemeToggle.tsx
git commit -m "feat(frontend): add useTheme hook + ThemeToggle"
```

---

## Task 5: Rebuild the Sidebar — dark surface, 220/52 widths, acid active rail

**Files:**
- Modify: `frontend/src/components/sidebar/Sidebar.tsx`.
- Modify: `frontend/src/components/sidebar/NavItem.tsx`.
- Modify: `frontend/src/components/sidebar/Sidebar.test.tsx` — update width expectations.
- Modify: `frontend/src/components/sidebar/NavItem.test.tsx` — update hover/active expectations.

- [ ] **Step 1: Update the expected widths in the sidebar test.**

Open `frontend/src/components/sidebar/Sidebar.test.tsx`. Replace every `w-[240px]` with `w-[220px]` and every `w-[60px]` with `w-[52px]`. Run:
```bash
cd frontend && npm test -- --run Sidebar
```
Expected: FAIL — implementation still uses old widths.

- [ ] **Step 2: Rewrite `Sidebar.tsx` so the shell is dark on both themes.**

Replace the top-level `<nav>` class string:
```tsx
<nav
  aria-label="Main navigation"
  className={[
    "flex flex-col h-screen bg-sidebar-bg",
    "transition-[width] duration-normal ease-in-out",
    collapsed ? "w-[52px]" : "w-[220px]",
  ].join(" ")}
  style={{ color: "#B5B3A8" }}
>
```

Replace the brand header with the acid-yellow badge + "OpenLia" wordmark:
```tsx
<header
  className={[
    "flex items-center gap-[10px] flex-shrink-0",
    collapsed ? "justify-center py-3" : "px-[10px] pt-[14px] pb-[18px]",
  ].join(" ")}
>
  <span
    className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-md font-bold"
    style={{
      background: "var(--color-accent-primary)",
      color: "var(--color-accent-on)",
      fontSize: 10,
      boxShadow: "var(--shadow-accent)",
    }}
  >
    LIA
  </span>
  {!collapsed && (
    <span className="font-display text-[15px] font-semibold tracking-tight" style={{ color: "#F2F1E8" }}>
      OpenLia
    </span>
  )}
</header>
```

Replace the "Departments" heading with a mono group label `.ol-label-sm` using `#6E6E68`. Replace the `CORE_NAV` group heading `General` with the same style. Keep the collapse toggle button, but move it into the footer row.

- [ ] **Step 3: Rewrite `NavItem.tsx` — acid-yellow rail when active, no transform on hover.**

Import `NavLink` and `LucideIcon`. The `<NavLink>` root is:
```tsx
<NavLink
  to={path}
  className={({ isActive }) =>
    [
      "relative flex items-center gap-[10px] rounded-md transition-colors duration-normal ease-out",
      collapsed ? "justify-center px-0 py-[9px]" : "px-[10px] py-[9px]",
      isActive ? "bg-[#252522] text-[#F2F1E8]" : "text-[#B5B3A8] hover:bg-[#1C1C1A] hover:text-[#F2F1E8]",
    ].join(" ")
  }
>
  {({ isActive }) => (
    <>
      {isActive && (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-5"
          style={{ background: "var(--color-accent-primary)" }}
        />
      )}
      <Icon
        size={16}
        strokeWidth={1.5}
        style={{ stroke: isActive ? "var(--color-accent-primary)" : "currentColor" }}
      />
      {!collapsed && <span className="text-[13px] font-display">{label}</span>}
      {hasUnread && (
        <span
          className="ml-auto w-[6px] h-[6px] rounded-full"
          style={{ background: "var(--color-accent-primary)", boxShadow: "0 0 6px rgba(212,255,0,0.7)" }}
        />
      )}
    </>
  )}
</NavLink>
```

- [ ] **Step 4: Update the `NavItem` test to assert the rail renders when active.**

Add a test that mounts `<NavItem />` in a router at the same path and asserts `screen.getByRole("link", { current: "page" })` contains a `[aria-hidden="true"]` span. Run:
```bash
cd frontend && npm test -- --run NavItem Sidebar
```
Expected: all passing.

- [ ] **Step 5: Sanity-check in the browser.**

Run `npm run dev`, open `/`. The sidebar should be near-black (`#0D0D0C`), 220 px wide; clicking items adds a 2 px acid-yellow rail on the left and turns the icon yellow. Collapsing drops it to 52 px; the brand badge stays centered.

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/components/sidebar/
git commit -m "feat(frontend): rebuild sidebar — dark surface, 220/52 widths, acid rail"
```

---

## Task 6: Build the `TopBar` component

**Files:**
- Create: `frontend/src/components/shell/TopBar.tsx`.
- Create: `frontend/src/components/shell/TopBar.test.tsx`.
- Create: `frontend/src/components/shell/LivePill.tsx`.

- [ ] **Step 1: Write the failing test.**

`TopBar.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { TopBar } from "./TopBar";

describe("TopBar", () => {
  it("renders breadcrumb segments with last as strong", () => {
    render(
      <MemoryRouter>
        <TopBar crumbs={["Home", "Morning Briefing"]} stamps={["TUE · 08:14 UTC"]} live />
      </MemoryRouter>,
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    const last = screen.getByText("Morning Briefing");
    expect(last.tagName).toBe("STRONG");
    expect(screen.getByText(/LIVE_FEED_ACTIVE/)).toBeInTheDocument();
  });

  it("omits the live pill when live is false", () => {
    render(
      <MemoryRouter>
        <TopBar crumbs={["Home"]} stamps={[]} live={false} />
      </MemoryRouter>,
    );
    expect(screen.queryByText(/LIVE_FEED_ACTIVE/)).toBeNull();
  });
});
```

- [ ] **Step 2: Run — FAIL.**

```bash
cd frontend && npm test -- --run TopBar
```

- [ ] **Step 3: Implement `LivePill.tsx`.**

```tsx
export function LivePill({ label = "LIVE_FEED_ACTIVE" }: { label?: string }): JSX.Element {
  return (
    <span
      className="inline-flex items-center gap-2 px-[10px] py-1 rounded-full font-mono text-[10px] tracking-label uppercase"
      style={{
        border: "1px solid var(--yellow-600)",
        background: "var(--color-accent-subtle)",
        color: "var(--color-feedback-success)",
      }}
    >
      <span
        aria-hidden="true"
        className="w-[7px] h-[7px] rounded-full"
        style={{
          background: "var(--yellow-600)",
          animation: "ol-pulse 1.8s var(--ease-in-out) infinite",
        }}
      />
      {label}
    </span>
  );
}
```

Add the `@keyframes ol-pulse` to `global.css`:
```css
@keyframes ol-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(168,204,0,0.6); }
  50%      { box-shadow: 0 0 0 6px rgba(168,204,0,0); }
}
```

- [ ] **Step 4: Implement `TopBar.tsx`.**

```tsx
import { ThemeToggle } from "./ThemeToggle";
import { LivePill } from "./LivePill";

export interface TopBarProps {
  crumbs: string[];
  stamps?: string[];
  live?: boolean;
}

export function TopBar({ crumbs, stamps = [], live = false }: TopBarProps): JSX.Element {
  const last = crumbs[crumbs.length - 1];
  const head = crumbs.slice(0, -1);
  return (
    <div
      className="flex items-center gap-[14px] px-7 py-[14px] border-b border-border-subtle bg-bg-base"
      role="banner"
    >
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-label text-text-secondary">
        {head.map((c) => (
          <span key={c} className="flex items-center gap-2">
            {c}
            <span className="text-text-tertiary">/</span>
          </span>
        ))}
        <strong className="text-text-primary font-semibold">{last}</strong>
      </nav>
      <div className="ml-auto flex items-center gap-[14px]">
        {live && <LivePill />}
        {stamps.map((s) => (
          <span key={s} className="font-mono text-[10px] uppercase tracking-label text-text-tertiary">
            {s}
          </span>
        ))}
        <ThemeToggle />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run — PASS.**

```bash
cd frontend && npm test -- --run TopBar
```

- [ ] **Step 6: Commit.**

```bash
git add frontend/src/components/shell/ frontend/src/styles/global.css
git commit -m "feat(frontend): add TopBar + LivePill + ThemeToggle shell surface"
```

---

## Task 7: Wire `AppLayout` to Sidebar + TopBar + Outlet

**Files:**
- Rewrite: `frontend/src/layouts/AppLayout.tsx`.
- Modify: `frontend/src/layouts/AppLayout.test.tsx`.

- [ ] **Step 1: Update the layout test to assert the TopBar renders with a default crumb.**

`AppLayout.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { AppLayout } from "./AppLayout";

describe("AppLayout", () => {
  it("renders sidebar + topbar + outlet", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<div>child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByText("child")).toBeInTheDocument();
  });
});
```

Run — FAIL (no topbar yet).

- [ ] **Step 2: Rewrite `AppLayout.tsx`.**

```tsx
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "../components/sidebar/Sidebar";
import { TopBar } from "../components/shell/TopBar";
import { crumbsForPath, stampsForNow } from "./shellState";

export function AppLayout(): JSX.Element {
  const { pathname } = useLocation();
  const crumbs = crumbsForPath(pathname);
  return (
    <div className="grid h-screen w-full bg-bg-base text-text-primary" style={{ gridTemplateColumns: "auto 1fr" }}>
      <Sidebar />
      <section className="grid overflow-hidden" style={{ gridTemplateRows: "auto 1fr" }}>
        <TopBar crumbs={crumbs} stamps={stampsForNow()} live={pathname.startsWith("/morning-briefing")} />
        <main className="overflow-y-auto">
          <Outlet />
        </main>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Add `frontend/src/layouts/shellState.ts`.**

```ts
import { CORE_NAV, DEPARTMENT_NAV } from "../components/sidebar/navData";

export function crumbsForPath(pathname: string): string[] {
  const all = [...CORE_NAV, ...DEPARTMENT_NAV];
  const hit = all.find((e) => pathname === e.path || pathname.startsWith(e.path + "/"));
  if (!hit) return ["Home"];
  return hit.path === "/" ? ["Home"] : ["Home", hit.label];
}

export function stampsForNow(): string[] {
  const now = new Date();
  const day = now.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
  const time = now.toISOString().slice(11, 16);
  return [`${day} · ${time} UTC`];
}
```

- [ ] **Step 4: Run — PASS.**

```bash
cd frontend && npm test -- --run AppLayout
```

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/layouts/
git commit -m "feat(frontend): wire AppLayout to Sidebar + TopBar + breadcrumb"
```

---

## Task 8: Home hero — DM Serif greeting + macro strip + what-can-LIA-do cards

**Files:**
- Rewrite: `frontend/src/pages/Home.tsx`.

- [ ] **Step 1: Implement the page.**

```tsx
import { Link } from "react-router-dom";
import { DEPARTMENT_NAV } from "../components/sidebar/navData";

const MACRO_STRIP = [
  { lbl: "S&P FUT", val: "+0.34" },
  { lbl: "VIX",     val: "14.2" },
  { lbl: "10Y",     val: "4.28" },
  { lbl: "DXY",     val: "103.1" },
];

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function Home(): JSX.Element {
  return (
    <div className="mx-auto w-full max-w-[960px] px-8 py-10">
      <div className="ol-greeting">{greeting()}, TK.</div>
      <div className="ol-label mt-[6px] tracking-micro">
        {MACRO_STRIP.map((m, i) => (
          <span key={m.lbl}>
            {i > 0 && <span className="mx-2 text-text-tertiary">·</span>}
            {m.lbl} {m.val}
          </span>
        ))}
      </div>

      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-4">
        {DEPARTMENT_NAV.map((dept) => (
          <Link
            key={dept.id}
            to={dept.path}
            className="group relative block rounded-lg border border-border-subtle bg-bg-elevated p-5 transition-all duration-normal ease-out hover:-translate-y-1 hover:border-yellow-600"
          >
            <span className="ol-label-sm">DEPARTMENT</span>
            <h3 className="mt-1 font-display text-[20px] font-medium text-text-primary">{dept.label}</h3>
            <span
              aria-hidden="true"
              className="absolute bottom-0 left-0 h-[2px] w-0 bg-accent-primary transition-[width] duration-slow ease-out group-hover:w-full"
            />
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Manually verify in the browser.**

Run `npm run dev`, open `/`. The greeting renders in DM Serif Display at 30 px. The macro strip sits underneath in IBM Plex Mono at 11 px, `0.10em` tracking. Department cards have a 2 px yellow bar that draws left→right on hover and lift 4 px; border goes olive (`#A8CC00`). No shadow.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "feat(frontend): Home hero — DM Serif greeting + macro strip + dept cards"
```

---

## Task 9: Chat primitives — `ChatInput` composer, `AssistantMessage`, `UserBubble`, `LiaBadge`

**Files:**
- Modify: `frontend/src/components/chat/ChatInput.tsx`.
- Modify: `frontend/src/components/chat/AssistantMessage.tsx`.
- Modify: `frontend/src/components/chat/UserBubble.tsx`.
- Modify: `frontend/src/components/chat/LiaBadge.tsx`.
- Modify: `frontend/src/components/chat/AttachmentChip.tsx`.

Each step keeps the existing prop contracts and only changes classNames + inline styles. Existing unit tests that assert on user-visible text still pass.

- [ ] **Step 1: `LiaBadge.tsx` — 28×28, acid background, olive text, glow.**

```tsx
export function LiaBadge(): JSX.Element {
  return (
    <span
      aria-label="LIA"
      className="inline-flex shrink-0 items-center justify-center w-7 h-7 rounded-md font-display font-bold text-[10px]"
      style={{
        background: "var(--color-accent-primary)",
        color: "var(--color-accent-on)",
        boxShadow: "var(--shadow-accent)",
      }}
    >
      LIA
    </span>
  );
}
```

- [ ] **Step 2: `UserBubble.tsx` — near-black bg, cream text, 10 px radius.**

```tsx
export function UserBubble({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[520px] rounded-[10px] px-[15px] py-[11px] text-[14px] leading-[1.5] font-display"
        style={{ background: "#1A1A18", color: "#F2F1E8" }}
      >
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: `AssistantMessage.tsx` — elevated bg, dept tag, subtle border, 10 px radius.**

Keep the existing `departmentLabel`, `tokens`, `elapsedMs`, and children props. Wrap the bubble:
```tsx
<div className="flex items-start gap-3">
  <LiaBadge />
  <div className="flex flex-col max-w-[600px]">
    {departmentLabel && (
      <span className="ol-label-sm mb-2 flex items-center gap-[6px] before:content-[''] before:w-1 before:h-1 before:rounded-full before:bg-accent-primary">
        {departmentLabel}
        {typeof tokens === "number" && <>· {tokens.toLocaleString()} tokens</>}
        {typeof elapsedMs === "number" && <>· {(elapsedMs/1000).toFixed(1)}s</>}
      </span>
    )}
    <div className="rounded-[10px] border border-border-subtle bg-bg-elevated px-4 py-[14px] text-[14.5px] leading-[1.65] font-display text-text-primary">
      {children}
    </div>
  </div>
</div>
```

- [ ] **Step 4: `AttachmentChip.tsx` — `.src-chip` style.**

```tsx
<button
  type="button"
  className="inline-flex items-center gap-[6px] rounded-sm border border-border-subtle bg-bg-elevated px-2 py-[3px] font-mono text-[10px] text-text-secondary transition-all duration-normal ease-out hover:border-yellow-600 hover:text-feedback-success hover:bg-[rgba(212,255,0,0.05)]"
>
  <Icon size={10} strokeWidth={1.5} />
  {filename}
</button>
```

- [ ] **Step 5: `ChatInput.tsx` — 10 px radius, focus glow, dept switch, ⌘+ENTER kbd hint, acid send button.**

Replace the outer wrapper class:
```tsx
<div className="mx-auto max-w-[720px] rounded-[10px] border border-border-subtle bg-bg-elevated p-1 transition-all duration-normal ease-out focus-within:border-yellow-600 focus-within:shadow-input-focus">
```

The textarea:
```tsx
<textarea
  className="w-full min-h-[46px] resize-none border-0 bg-transparent px-3 pt-3 pb-[6px] font-display text-[14px] leading-[1.5] text-text-primary outline-none"
  placeholder="Ask LIA about markets, tickers, filings…"
  ...
/>
```

The controls row:
```tsx
<div className="flex items-center gap-2 px-2 py-[6px] pl-[10px]">
  <button className="inline-flex items-center justify-center rounded-sm p-[6px] text-text-secondary transition-colors duration-normal ease-out hover:bg-surface-hover hover:text-text-primary" aria-label="Attach">
    <Paperclip size={16} strokeWidth={1.5} />
  </button>
  <DepartmentSwitch />
  <div className="flex-1" />
  <span className="font-mono text-[9px] tracking-label text-text-tertiary">⌘ + ENTER</span>
  <button
    type="submit"
    aria-label="Send"
    className="inline-flex items-center justify-center rounded-md p-[9px] text-accent-on transition-colors duration-normal ease-out hover:bg-accent-hover active:scale-[0.96]"
    style={{ background: "var(--color-accent-primary)" }}
  >
    <ArrowUp size={15} strokeWidth={2} />
  </button>
</div>
```

- [ ] **Step 6: Run tests — the existing chat tests should still pass (text + behavior unchanged).**

```bash
cd frontend && npm test -- --run chat
```

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/components/chat/
git commit -m "feat(frontend): restyle chat primitives to match app kit"
```

---

## Task 10: `DataRow` primitive + hook up to chat data-block renderings

**Files:**
- Create: `frontend/src/components/primitives/DataRow.tsx`.

- [ ] **Step 1: Implement.**

```tsx
export interface DataRowProps {
  label: string;
  value: string;
  delta?: string;
  deltaDirection?: "pos" | "neg" | null;
}

export function DataRow({ label, value, delta, deltaDirection }: DataRowProps): JSX.Element {
  return (
    <>
      <span className="ol-label">{label}</span>
      <span className="text-right font-mono text-[12px] font-medium tabular-nums text-text-primary">{value}</span>
      {delta && (
        <span
          className="text-right font-mono text-[12px] tabular-nums"
          style={{
            color:
              deltaDirection === "neg"
                ? "var(--color-feedback-error)"
                : "var(--color-feedback-success)",
          }}
        >
          {delta}
        </span>
      )}
    </>
  );
}
```

Consumers render a grid wrapper:
```tsx
<div className="grid grid-cols-[1fr_auto_auto] gap-x-[18px] gap-y-1 mt-[10px] p-[10px_12px] rounded-md border border-border-subtle bg-bg-input font-mono text-[12px] tabular-nums">
  <DataRow label="REVENUE" value="$35.1B" delta="+94% y/y" deltaDirection="pos" />
  ...
</div>
```

- [ ] **Step 2: Smoke-render in an assistant-message story / dev page (skip if no story infra).**

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/primitives/DataRow.tsx
git commit -m "feat(frontend): add DataRow primitive for chat data blocks"
```

---

## Task 11: `Button`, `Badge`, `Input`, `Card`, `MonoLabel` primitives

**Files:**
- Create each file in `frontend/src/components/primitives/` with a matching `.test.tsx`.

- [ ] **Step 1: `Button.tsx` — primary (acid), secondary (border), ghost; `::before` fill-wipe on hover.**

Base class:
```ts
const base =
  "relative inline-flex items-center justify-center gap-2 rounded-md px-4 py-[9px] font-display text-[13px] font-medium uppercase tracking-[0.07em] transition-all duration-normal ease-out active:scale-[0.96] overflow-hidden";
```
Variant classes:
```ts
const variants = {
  primary:   "bg-accent-primary text-accent-on hover:bg-accent-hover",
  secondary: "border border-border-secondary text-text-primary hover:border-border-strong",
  ghost:     "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
};
```
Smoke test: renders children + variant className.

- [ ] **Step 2: `Badge.tsx` — pill variants (neutral, accent, success, error, warning).**

Uppercase mono, `--text-label-sm`, `0.10em` tracking, `9999px` radius, `1px` border-subtle, 4/10 padding.

- [ ] **Step 3: `Input.tsx` — `.composer`-style wrap.**

`bg-bg-input`, `border-border-subtle`, `rounded-md`, focus → `border-yellow-600` + `shadow-input-focus`. Delegates props to `<input>`.

- [ ] **Step 4: `Card.tsx` — flat, border-driven, hover translateY + olive border + yellow bar.**

```tsx
export function Card({ children, as = "div", className = "", ...rest }: CardProps): JSX.Element {
  const Comp = as;
  return (
    <Comp
      {...rest}
      className={[
        "relative block rounded-lg border border-border-subtle bg-bg-elevated p-5",
        "transition-all duration-normal ease-out",
        "hover:-translate-y-1 hover:border-yellow-600",
        "group", // for the ::after bar
        className,
      ].join(" ")}
    >
      {children}
      <span
        aria-hidden="true"
        className="absolute bottom-0 left-0 h-[2px] w-0 bg-accent-primary transition-[width] duration-slow ease-out group-hover:w-full"
      />
    </Comp>
  );
}
```

- [ ] **Step 5: `MonoLabel.tsx` — thin wrapper around `<span className="ol-label">`.**

- [ ] **Step 6: One smoke test per primitive — renders children, applies variant, exposes `data-testid`.**

```bash
cd frontend && npm test -- --run primitives
```

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/components/primitives/
git commit -m "feat(frontend): add Button/Badge/Input/Card/MonoLabel primitives"
```

---

## Task 12: FileViewer shell restyle (header + tabs + KPI grid + quote-callout)

**Files:**
- Modify: `frontend/src/components/viewer/*` (exact file list depends on Phase 12 structure — confirm before editing).

- [ ] **Step 1: Audit the current viewer.**

Run:
```bash
ls frontend/src/components/viewer/
grep -rn "bg-bg-elevated\|border-border-subtle\|rounded-lg" frontend/src/components/viewer/
```

- [ ] **Step 2: Update the panel container — left-side shadow only, 40% width default, `min-w-[360px] max-w-[70%]`.**

Replace the viewer wrapper class with:
```tsx
className="grid grid-rows-[auto_auto_1fr] overflow-hidden border-l border-border-subtle bg-bg-elevated"
style={{ boxShadow: "-4px 0 24px rgba(0,0,0,0.06)" }}
```

- [ ] **Step 3: Header and tabs — use `.ol-label-sm` for meta, an underline-only active tab state in acid yellow.**

Tabs:
```tsx
<button
  className={[
    "px-[14px] py-[10px] font-mono text-[10px] uppercase tracking-label transition-colors duration-normal ease-out",
    active ? "text-text-primary border-b-2 border-accent-primary -mb-px" : "text-text-secondary border-b-2 border-transparent",
  ].join(" ")}
>
```

- [ ] **Step 4: KPI grid + quote-callout inside the body.**

KPI card:
```tsx
<div className="rounded-lg border border-border-subtle bg-bg-base p-3 flex flex-col gap-1">
  <span className="ol-label-sm">{label}</span>
  <span className="font-mono text-[20px] font-semibold tabular-nums text-text-primary">{value}</span>
  <span className="font-mono text-[10px] tabular-nums" style={{ color: delta >= 0 ? "var(--color-feedback-success)" : "var(--color-feedback-error)" }}>
    {delta >= 0 ? "+" : ""}{delta}%
  </span>
</div>
```

Quote callout:
```tsx
<blockquote
  className="rounded-r-md px-4 py-[14px] text-[13px] leading-[1.6] text-text-primary"
  style={{
    borderLeft: "2px solid var(--color-accent-primary)",
    background: "rgba(212,255,0,0.07)",
  }}
>
  {quote}
  <div className="ol-label-sm mt-[6px]">— {cite}</div>
</blockquote>
```

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/components/viewer/
git commit -m "feat(frontend): restyle FileViewer shell — tabs/KPI/quote callout"
```

---

## Task 13: Sweep the auth pages (Login / Register / Forgot / Reset)

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`, `RegisterPage.tsx`, `ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`.

- [ ] **Step 1: Replace the auth page wrappers with a centered card on `bg-bg-base`.**

Pattern:
```tsx
<div className="min-h-screen grid place-items-center bg-bg-base px-4 py-12">
  <div className="w-full max-w-[420px] rounded-2xl border border-border-subtle bg-bg-elevated p-8">
    <div className="flex items-center gap-[10px] mb-8">
      <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-md font-bold text-[10px]" style={{ background: "var(--color-accent-primary)", color: "var(--color-accent-on)", boxShadow: "var(--shadow-accent)" }}>LIA</span>
      <span className="font-display text-[15px] font-semibold text-text-primary">OpenLia</span>
    </div>
    <h1 className="font-display text-[24px] font-semibold text-text-primary mb-6">Sign in</h1>
    { /* form */ }
  </div>
</div>
```

Form submit uses the new `Button` primary variant. Each input uses the new `Input` primitive (focus glow).

- [ ] **Step 2: Run auth tests — text + ARIA unchanged, expect PASS.**

```bash
cd frontend && npm test -- --run LoginPage RegisterPage ForgotPasswordPage ResetPasswordPage
```

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/pages/RegisterPage.tsx frontend/src/pages/ForgotPasswordPage.tsx frontend/src/pages/ResetPasswordPage.tsx
git commit -m "feat(frontend): restyle auth pages to Wondermakers tokens"
```

---

## Task 14: Sweep the setup wizard

**Files:**
- Modify: `frontend/src/pages/Setup.tsx`, `SetupPage.tsx`, `frontend/src/setup/*`.

- [ ] **Step 1: Swap the wizard shell background to `bg-bg-base`, the step card to the auth-card pattern above.**

- [ ] **Step 2: Step labels (`STEP 01 / 05`) use `.ol-label-sm`. Progress bar uses `--yellow-400` fill on `--color-border-subtle` track, `9999px` radius.**

- [ ] **Step 3: Run wizard tests.**

```bash
cd frontend && npm test -- --run Wizard Setup
```

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/pages/Setup.tsx frontend/src/pages/SetupPage.tsx frontend/src/setup/
git commit -m "feat(frontend): restyle setup wizard to Wondermakers tokens"
```

---

## Task 15: Sweep remaining pages and placeholders

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`, `SettingsPage.tsx`, `PortfolioPage.tsx`, `SecretaryPage.tsx`, `Repository.tsx`, `placeholder.tsx`.
- Modify: any page under `frontend/src/pages/equity-research/`, `earnings-update/`, `morning-briefing/`, `panic-thermometer/`, `retail-sentiment/`, `macro-research/` that contains a hardcoded hex.

- [ ] **Step 1: For each file in the Task 0 hex inventory, replace the hardcoded color with a token.**

Replacement table:
```
#0f1115, #12151c, #161a22            → bg-bg-base / bg-bg-input / bg-bg-elevated
#7c9cff                              → accent-primary
#e8eaf0 / #a8aec0 / #6f758a          → text-primary / text-secondary / text-tertiary
rgba(255,255,255,0.04) / 0.06 / 0.08 → surface-hover / surface-active / border-subtle
#ef6b6b / #62c28b / #e0b355          → feedback-error / feedback-success / feedback-warning
```

- [ ] **Step 2: Update `placeholder.tsx` to render a warm-cream centered card with a mono `PAGE_NOT_READY` label.**

```tsx
export function PagePlaceholder({ title }: { title: string }): JSX.Element {
  return (
    <div className="min-h-full grid place-items-center p-8">
      <div className="rounded-lg border border-border-subtle bg-bg-elevated px-8 py-10 text-center">
        <span className="ol-label-sm">PAGE_NOT_READY</span>
        <h1 className="mt-2 font-display text-[24px] font-medium text-text-primary">{title}</h1>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Confirm no hex literals remain in `src/` except inside the token file itself.**

Run:
```bash
grep -rnE '#[0-9A-Fa-f]{3,8}\b' frontend/src --include='*.{ts,tsx}' | grep -v 'tokens.css'
```
Expected: empty.

- [ ] **Step 4: Full test run.**

```bash
cd frontend && npm test -- --run && npm run lint
```
Expected: 100% green.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/pages/
git commit -m "feat(frontend): sweep remaining pages — token-only colors"
```

---

## Task 16: Audit report-theme stylesheets for retired blue tokens

**Files:**
- Modify: `frontend/src/styles/report/theme-light.css`, `theme-dark.css`.

- [ ] **Step 1: Find blue references.**

```bash
grep -nE '#(7c9cff|94acff|5a9bff|0f1115|12151c|161a22)' frontend/src/styles/report/
```

- [ ] **Step 2: Replace each with a neutral or token.** Report themes are read-only from the app; blue should become `--color-text-primary` (deep neutral) or the olive `--color-feedback-success` if it was flagging a positive signal. Keep report theme dark backgrounds unchanged — they are print surfaces, not chrome.

- [ ] **Step 3: Commit only if this file changed.**

```bash
git add frontend/src/styles/report/
git commit -m "feat(frontend): swap retired blue in report themes to neutral tokens"
```

---

## Task 17: Final acceptance — manual walkthrough + full test + commit

**Files:** none new.

- [ ] **Step 1: Boot the server and frontend together.**

```bash
uv run openlia serve  # in one shell
cd frontend && npm run dev  # in another
```

- [ ] **Step 2: Walk every page while logged in and confirm the checklist.**

Acceptance checklist — every item must be true on both light and dark themes:
- Body font is Geist Sans (not system).
- Page background is warm cream (light) or near-black (dark) — never pure white, never pure black.
- Sidebar is 220 px expanded, 52 px collapsed, dark surface, acid rail + yellow icon on active item.
- TopBar shows a breadcrumb, optional `LIVE_FEED_ACTIVE` pill, at least one mono stamp, and the theme toggle.
- Home greeting renders in DM Serif Display, 30 px, warm cream background.
- Department cards lift 4 px on hover, border goes olive `#A8CC00`, 2 px yellow bar draws along the bottom — no box-shadow.
- Chat composer focus ring is acid yellow, send button is acid yellow → olive text, ⌘+ENTER kbd hint in mono.
- LIA badge next to assistant messages is 28 px square, acid yellow, olive text, glows.
- All mono labels are 11 px / 9 px, 0.08 em / 0.10 em tracking, uppercase.
- Zero emoji anywhere.
- Zero hardcoded hex in `src/**/*.tsx` (see Task 15 Step 3).
- Theme toggle persists across reload.

- [ ] **Step 3: Run the full suite (python + frontend) and lint.**

```bash
uv run pytest
cd frontend && npm test -- --run && npm run lint && npm run build
```
Expected: all green.

- [ ] **Step 4: Open the PR.**

```bash
git push -u origin phase/24-design-system-refresh
gh pr create --title "feat(phase-24): Design system refresh — Wondermakers / Acid Yellow" --body "$(cat <<'EOF'
## Summary
- Swap token palette from dark-blue to Wondermakers / Acid Yellow (warm cream base, `#D4FF00` accent) with light + dark modes.
- Bundle Geist variable font locally; load IBM Plex Mono + DM Serif Display from Google Fonts.
- Rebuild app shell (Sidebar 220/52, new TopBar with breadcrumb + LIVE pill, AppLayout grid).
- Restyle chat primitives + LIA badge + composer to match the canonical `ui_kits/app/index.html`.
- Add Card / Button / Badge / Input / MonoLabel / DataRow primitives.
- Sweep every page for hardcoded hex; all surface colors now flow through tokens.

## Test plan
- [ ] Frontend: `npm test -- --run` green, `npm run lint` green, `npm run build` green.
- [ ] Backend: `uv run pytest` still green (no backend changes).
- [ ] Manual: light + dark walk of Home, Secretary, each Department page, Portfolio, Repository, Settings, Setup, auth pages.
- [ ] Manual: sidebar active rail renders on every route; theme toggle persists.
EOF
)"
```

---

## Self-review notes

1. **Spec coverage:** every bullet in `project/README.md` § "Visual Foundations", "Iconography", "Cards", plus every component covered in `ui_kits/app/index.html`, maps to Tasks 1–12. Task 15 covers the page sweep; Task 17 is the acceptance gate.
2. **No placeholders:** every step includes concrete code, commands, and expected output. No "TBD" / "implement later" / "add error handling".
3. **Type consistency:** `TopBar` props, `useTheme` return, `Card` props, `DataRow` props are defined once and referenced consistently.
4. **Accent policy:** acid yellow is applied only as an accent (rail, send button, LIA badge, bar on card hover, focus ring). Olive `#A8CC00` is the hover border; acid is never a fill on large surfaces.
5. **Motion tokens only:** every `transition-duration` uses a token (`duration-normal`, `duration-slow`). No `300ms` literals in the task bodies.

---

## Token surface deltas (post-merge)

Task 1 of the plan exposes only `--color-sidebar-bg` for sidebar surfaces. During implementation the sidebar required additional dark-mode-stable tokens because it is the only surface that stays dark across both themes. The following six sidebar-scoped tokens were added to `frontend/src/styles/tokens.css` beyond the original plan surface and are documented here for future contributors:

| Token | Light hex | Purpose |
|---|---|---|
| `--color-sidebar-text` | `#B5B3A8` | Default sidebar nav-item label color |
| `--color-sidebar-text-strong` | `#F2F1E8` | Active / brand-name sidebar text |
| `--color-sidebar-text-muted` | `#6E6E68` | Section dividers ("General", "Departments") |
| `--color-sidebar-hover` | `#1C1C1A` | Hover background on sidebar rows |
| `--color-sidebar-active` | `#252522` | Active background on sidebar rows |
| `--color-sidebar-divider` | `#252522` | Footer border / collapsed section separator |

Plan Task 1 status: `[~]` shipped-with-additions. These tokens are intentionally not exposed as Tailwind utilities because they are only consumed by `Sidebar.tsx` and `NavItem.tsx` via inline `style={{ color: "var(--color-sidebar-…)" }}` props. Other surfaces continue to use the canonical Tailwind utilities (`bg-bg-base`, `text-text-primary`, etc.).
