# Sidebar Spec

---

## Overview

The Sidebar is the primary navigation component of the product. It is a persistent vertical panel anchored to the left edge of the screen that allows users to move between the product's top-level pages and departments. It is always present in the layout and serves as the consistent spatial anchor from which all navigation originates.

The Sidebar is not a drawer or overlay — it occupies a fixed column in the page layout. All page content renders to its right. On mobile, it collapses to a bottom tab bar or a hamburger-triggered overlay (see Responsive Behavior).

---

## Layout

```
┌──────────┬──────────────────────────────────────────────┐
│          │                                              │
│          │                                              │
│ Sidebar  │         Main Content Area                    │
│          │         (active page renders here)           │
│          │                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

- Sidebar width: **240px** (expanded) / **60px** (collapsed, icon-only mode)
- Main content area takes the remaining viewport width
- Sidebar does not overlay content — it pushes the layout
- Sidebar height: full viewport height (`100vh`), fixed position
- Sidebar is not scrollable by default; if nav items overflow, the items section scrolls independently while header and footer remain fixed

---

## Structure

The Sidebar is composed of three vertically stacked zones:

```
┌──────────────────────┐
│  Header              │  ← Product logo / wordmark, collapse toggle
├──────────────────────┤
│                      │
│  Navigation Items    │  ← Primary pages and departments (scrollable)
│                      │
├──────────────────────┤
│  Footer              │  ← User profile, settings
└──────────────────────┘
```

### Zone 1 — Header

| Element | Detail |
|---|---|
| Container | `h-14 flex items-center border-b border-[--color-border-subtle] flex-shrink-0` |
| Product wordmark | "LIA" — `text-xl font-semibold text-[--color-text-primary] tracking-tight`; hidden in collapsed mode (fade out `opacity 1→0, 150ms`) |
| Collapse toggle | `ChevronLeft` (expanded) / `ChevronRight` (collapsed) — Lucide, 16px; `w-7 h-7 rounded-[--radius-md] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]`; `aria-expanded`, `aria-label` toggling |
| Layout — expanded | `justify-between px-4` |
| Layout — collapsed | `justify-center` — only toggle button visible |

### Zone 2 — Navigation Items

| Element | Detail |
|---|---|
| Container | `flex-1 overflow-y-auto px-2 py-2 space-y-0.5` |
| Nav items | Each item: `flex items-center gap-[10px] rounded-[--radius-md] px-2 py-[10px] w-full`; expanded: icon + label; collapsed: icon only, centered with `mx-auto` |
| Section labels | `text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] px-2 pt-4 pb-1`; hidden in collapsed mode — replaced by a `1px bg-[--color-border-subtle]` horizontal divider |
| Scroll behavior | Zone scrolls independently; header and footer remain sticky |

### Zone 3 — Footer

| Element | Detail |
|---|---|
| Container | `flex-shrink-0 border-t border-[--color-border-subtle] px-2 py-2 space-y-0.5` |
| Settings nav item | Standard nav item: `Settings` Lucide icon (18px) + "Settings" label; navigates to `/settings` |
| User identity row | Non-interactive row: `flex items-center gap-[10px] px-2 py-[10px]`; avatar: `w-[18px] h-[18px] rounded-full bg-[--color-accent-primary] flex items-center justify-center` with `User` icon (11px, white); label: `text-sm text-[--color-text-secondary] truncate`; label hidden in collapsed mode |

---

## Navigation Structure

The Sidebar organizes destinations into two groups: **Core Pages** and **Departments**.

### Core Pages

Always-visible top-level destinations, above the department list.

| Page | Lucide Icon | Description |
|---|---|---|
| Home | `Home` | Default landing page — redirects to Secretary |
| Repository | `FolderOpen` | Saved reports store; destination for reports saved via `SaveToRepo` |

### Departments

Each department is a nav item that navigates to that department's dedicated page (chat interface, report feed, or dashboard).

| Department | Lucide Icon | Description |
|---|---|---|
| Secretary | `MessageSquare` | General-purpose LLM assistant; product home page |
| Equity Research | `TrendingUp` | Stock research report generation |
| Earnings Update | `ClipboardList` | Earnings monitoring and analysis |
| Morning Briefing | `Sun` | Daily briefing report generation and archive |
| Retail Sentiment | `BarChart2` | Social media sentiment monitoring dashboard |
| Macro Research | `Globe` | Dalio framework macro dashboards (Debt Cycle, Four Seasons, All-Weather, World Order, Five Forces) |
| Panic Thermometer | `Thermometer` | Panic-driven indicator dashboards (Oil, Inflation, Fed Language, Wage Growth, Diplomacy) with formula-based threshold evaluation |

All icons are from the **Lucide** library, stroke-weight 1.5px, rendered at 18×18px. Icon names are the component key used in the `ICON_MAP` record in the Sidebar implementation.

**Note:** The department list should be data-driven, not hardcoded, so new departments can be added without a Sidebar code change.

### Section Labels

- A non-interactive label ("Departments") separates the core pages group from the departments group
- Labels are uppercase, small font, muted color — purely organizational, not clickable
- In collapsed (icon-only) mode, section labels are hidden

---

## Collapsed Mode

The Sidebar can be toggled between **expanded** (240px, icon + label) and **collapsed** (60px, icon only) states.

```
Expanded:                        Collapsed:
┌──────────────────────┐         ┌────────┐
│  ⬡  ProductName  ‹   │         │  ⬡  ›  │
├──────────────────────┤         ├────────┤
│  🏠  Home            │         │  🏠    │
│  🗂  Repository      │         │  🗂    │
│  ─── Departments ─── │         │  ────  │
│  📈  Equity Research  │         │  📈    │
│  📋  Earnings Update │         │  📋    │
│  ☀️  Morning Brief   │         │  ☀️    │
│  💬  Retail Sentiment│         │  💬    │
│  🌐  Macro Research  │         │  🌐    │
│  🌡  Panic Thermo.   │         │  🌡    │
├──────────────────────┤         ├────────┤
│  👤  User Name       │         │  👤    │
│  ⚙️  Settings        │         │  ⚙️    │
└──────────────────────┘         └────────┘
```

- Collapse state is **persisted** in `localStorage` so the user's preference survives page refresh and session
- In collapsed mode, hovering a nav item shows a **tooltip** with the item label (replaces the hidden text label)
- The collapse toggle button (`‹` / `›` chevron) sits in the header and is always accessible
- Main content area smoothly expands to fill the recovered width when Sidebar collapses (CSS transition, ~200ms)

---

## Nav Item Design

### Expanded State

| Property | Spec |
|---|---|
| Height | 40px per item |
| Padding | 8px horizontal, 10px vertical |
| Icon size | 18×18px, left-aligned |
| Icon–label gap | 10px |
| Label | ~14px, medium weight, single line, truncates with ellipsis if overflowing |
| Border radius | 6px |
| Cursor | `pointer` |

### Collapsed State

| Property | Spec |
|---|---|
| Width | 60px (full Sidebar width) |
| Icon | Centered horizontally and vertically within the 40px item height (`mx-auto`) |
| Label | Hidden (animated out: `opacity 1→0, width auto→0, 150ms`) |
| Tooltip | Appears after 300ms hover delay, positioned to the right of the Sidebar edge |

#### Tooltip Design

| Property | Spec |
|---|---|
| Container | `rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] shadow-md px-2.5 py-1 text-sm text-[--color-text-primary] whitespace-nowrap` |
| Position | `left: 100%; margin-left: 12px; top: 50%; transform: translateY(-50%)`; `z-index: 50` |
| Entry animation | `opacity 0→1, x -4→0, duration 120ms` |
| Exit animation | `opacity 1→0, x 0→-4, duration 120ms` |
| Trigger | `onMouseEnter` with 300ms delay; `onMouseLeave` cancels delay and hides immediately |

### Nav Item States

| State | Background | Label | Icon | Other |
|---|---|---|---|---|
| Default | transparent | `--color-text-secondary` | `--color-icon-primary` | — |
| Hovered | `--color-surface-hover` | `--color-text-primary` | `--color-icon-primary` | transition `120ms ease` |
| Active | `--color-accent-subtle` | `--color-text-primary` | `--color-accent-primary` | 3px left accent bar (see below) |
| Focused (keyboard) | `--color-surface-hover` | `--color-text-primary` | `--color-icon-primary` | `--focus-ring-color` outline |
| Disabled | transparent, `opacity: 0.4` | `--color-text-secondary` | `--color-icon-primary` | `cursor: not-allowed` |

All transitions: `background-color`, `color` — `120ms ease`.

### Active Item Indicator

The active page is indicated by three simultaneous signals:
1. **Background tint**: `--color-accent-subtle` fill on the item
2. **Icon color**: `--color-accent-primary`
3. **Left accent bar**: a `3px × (item-height - 16px)` pill, `background: --color-accent-primary`, `border-radius: 9999px`, `position: absolute left-0 top-2 bottom-2`

Only one item is active at a time, derived from the current route. `aria-current="page"` is set on the active anchor.

### Notification Badge

> **Cross-reference note (2026-04-16):** Notification mechanism formalized by `background-task-scheduling-design.md`. Dots are driven by polling `GET /notifications/unread`, which returns per-department unread counts from the `user_notifications` table. Notifications are created by the background task scheduler when scheduled jobs complete or fail (MB briefings, EU earnings scans, MR assessments).

When a background job produces a result (report ready or job failed) while the user is away from that department's page, the department's nav item shows a notification dot.

| Property | Spec |
|---|---|
| Shape | `w-1.5 h-1.5 rounded-full` (6px circle) |
| Color | `bg-[--color-accent-primary]` |
| Position | Top-right corner of the icon, offset `top-0 right-0` — overlapping the icon's top-right quadrant |
| Visibility | Shown when unread count > 0 for that department; hidden once the user visits the page |
| Collapsed mode | Dot visible on the icon |
| Expanded mode | Dot visible on the icon (same position — does not move to the label) |
| Animation | Fades in `opacity 0→1` over `120ms` when first shown |

**Polling mechanism:** The frontend polls `GET /notifications/unread` every 60 seconds while the app is open, and on each page navigation. The response includes `{total: N, by_department: {"morning_briefing": 2, ...}}`. The sidebar renders a dot on each department that has a non-zero count.

**Clearing:** When the user navigates to a department page, the frontend calls `POST /notifications/read` with `{department: "<department_id>"}`, which marks those notifications as read and the dot disappears.

The dot is the only badge type in v1 — no numeric count badges.

---

## Behavior & Interactions

### Navigation

- Clicking a nav item navigates to the corresponding page
- Navigation is client-side (no full page reload) — the Sidebar persists across page transitions without re-rendering
- The active state updates immediately on click, before the new page content loads

### Collapse / Expand

- Toggled by clicking the collapse button in the Sidebar header
- Transition: width animates between 240px and 60px over 200ms (`ease-in-out`)
- Main content area width adjusts simultaneously via CSS (`margin-left` or `grid-template-columns`)
- Labels fade out during collapse (opacity transition), fade in during expand
- Collapse state stored in `localStorage` key `sidebar_collapsed` (boolean)

### Keyboard Navigation

- All nav items are focusable via `Tab`
- `Enter` or `Space` activates a focused item
- `Arrow Up` / `Arrow Down` moves focus between nav items within the list
- `Escape` from a focused nav item returns focus to the last active element in the main content

### External State Awareness

- If a report is saved via `SaveToRepoButton`, consider showing a **badge** on the Repository nav item (e.g. a dot or count) to surface new saves — particularly useful if multiple agents are generating reports in the background
- Badge clears when the user visits the Repository page

---

## Design Tokens

| Token | Usage |
|---|---|
| `--color-sidebar-bg` | Sidebar background (distinct from main content bg) |
| `--color-text-primary` | Active / hovered item label |
| `--color-text-secondary` | Default item label |
| `--color-surface-hover` | Item hover background |
| `--color-surface-active` | Active item background |
| `--color-accent-primary` | Active item icon color, accent bar |
| `--color-border-subtle` | Optional: hairline border on Sidebar's right edge |
| `--color-icon-primary` | Default icon color |
| `--color-icon-active` | Active item icon color (may alias `--color-accent-primary`) |

All colors reference tokens — no hardcoded values — so Sidebar adapts automatically to light and dark mode.

---

## Accessibility

- Sidebar root element: `<nav aria-label="Main navigation">`
- Nav item list: `<ul>` with each item as `<li><a>` or `<li><button>` depending on routing approach
- Active item: `aria-current="page"` on the active nav item
- Collapse toggle: `aria-expanded="true/false"` reflecting current state; `aria-label="Collapse sidebar"` / `"Expand sidebar"` toggling with state
- Collapsed mode tooltips: rendered as `role="tooltip"` elements linked via `aria-describedby`
- Disabled items: `aria-disabled="true"` — item remains focusable so users understand it exists but is unavailable
- Section labels: `role="separator"` or wrapped in `<li role="presentation">` to not pollute the nav item count for screen readers
- Focus management: when Sidebar collapses via keyboard, focus should not be lost — keep focus on the collapse toggle button

---

## Responsive Behavior

### Desktop (>1024px)
- Full Sidebar, expanded by default
- Collapse toggle available

### Tablet (768–1024px)
- Sidebar defaults to **collapsed** (icon-only, 60px)
- Collapse toggle still available to expand if user prefers
- Main content fills remaining width

### Mobile (<768px)
- Sidebar is **hidden** from the layout entirely
- Navigation replaced by a **bottom tab bar** showing the 5–6 most important destinations (icons only, labels below)
- A hamburger menu button in the top-left of the main content header opens the full Sidebar as a **slide-in overlay** (not a layout shift — the overlay sits on top of content)
- Overlay Sidebar: full height, same structure as desktop Sidebar, dismissible by tapping outside or pressing `Escape`

| Breakpoint | Sidebar Mode |
|---|---|
| >1024px | Persistent layout column, expanded by default |
| 768–1024px | Persistent layout column, collapsed by default |
| <768px | Hidden; bottom tab bar + overlay drawer |

---

## Non-Goals (v1)

- **Drag-to-resize** — Sidebar width is fixed at 240px expanded / 60px collapsed; no user-resizable handle
- **Pinned / favorited pages** — no user customization of nav item order or visibility
- **Nested sub-navigation** — no expandable accordion items within the Sidebar; all destinations are flat
- **Search within nav** — no search or filter field in the Sidebar
- **Numeric count badges** — department notification signals are binary dots only (present/absent); no `(3)` or `99+` style counters on nav items in v1. See § Notification Badge for the per-department dot mechanism.
- **Contextual nav changes** — Sidebar content is the same on all pages; no page-specific secondary nav items injected into the Sidebar

---

## Open Questions

- Should the Repository nav item show a live badge count of unseen saved reports, or just a dot indicator?
- Is there a defined order for department nav items, or should it be alphabetical? Should users be able to reorder them in a future version?
- What happens to disabled department nav items — do they appear grayed out, or are they hidden entirely until the department is available?
- Should collapse state be synced across tabs/devices (server-persisted preference) or remain local (`localStorage` only)?
- Is there a "New department" CTA at the bottom of the Departments group for admins to provision new departments, or is that handled elsewhere?
- On mobile, which destinations appear in the bottom tab bar if there are more destinations than tab slots?