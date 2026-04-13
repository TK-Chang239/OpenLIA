# Repository Page Spec

## Page Overview

The `Repository`, or `Repo`, is a centralized storage page that holds all reports the user has saved across all `Departments`. Every report saved via the `SaveToRepo` button from any department or `FileViewer` panel is accessible here. The user can browse, search, filter, preview, download, and remove saved reports from this page.

---

## Functionalities

### 1. Saved Reports List

Displays all reports the user has saved, ordered by `saved_at` (most recent first) by default. Each report entry in the list shows:

| Field | Description |
|---|---|
| Filename | Report filename including extension |
| Department | Which department generated the report |
| Generated | Timestamp when the report was originally generated (`generated_at`) |
| Saved | Timestamp when the user saved the report (`saved_at`) |

### 2. Search

A search bar at the top of the page allows the user to search by filename. Search is case-insensitive and matches partial strings. Results update as the user types.

### 3. Filter

The user can apply filters to narrow results. Multiple filters can be active simultaneously. Available filters:

| Filter | Options |
|---|---|
| Department | Secretary, Equity Research, Earnings Update, Morning Briefing, Retail Sentiment |
| Date Generated | Date range picker (from / to) applied to `generated_at` |
| Date Saved | Date range picker (from / to) applied to `saved_at` |

Active filters are displayed as dismissible chips below the search bar. The user can clear individual filters or clear all at once.

### 4. Sort

The user can change the sort order of the results list via a sort dropdown. Sort options:

| Option | Description |
|---|---|
| Date Saved (newest) | Default |
| Date Saved (oldest) | |
| Date Generated (newest) | |
| Date Generated (oldest) | |
| Department | Alphabetical by department name |
| Filename | Alphabetical by filename |

### 5. Open Report in FileViewer

Clicking on a report entry opens it in the `FileViewer` panel, which slides in from the right side of the screen. The chat area shifts left to accommodate the panel, matching the behavior on department pages. The `FileViewer` header shows the filename, department, and both timestamps.

### 6. Download Report

Each report entry has a download button (`FileDownloadButton`) that downloads the report file to the user's local machine. The download button is also available inside the `FileViewer` header when a report is open.

### 7. Remove Report from Repository

Each report entry has a remove button that unsaves the report from the `Repo`. This mirrors the `SaveToRepo` toggle behavior — clicking remove calls the same toggle endpoint, transitioning the report out of the saved state. The report is immediately removed from the visible list on success.

Clicking the remove button opens a confirmation dialog before the action is taken:

```
┌──────────────────────────────────────┐
│  Remove from Repository?             │
│                                      │
│  "q1-macro-briefing.pdf" will be     │
│  removed from your Repository.       │
│                                      │
│          [Cancel]  [Remove]          │
└──────────────────────────────────────┘
```

- **Cancel** — closes the dialog, no action taken
- **Remove** — proceeds with the unsave; report is removed from the list on success

Note: the confirmation dialog only appears when removing from the Repository page. Clicking the `SaveToRepo` toggle button on department pages (to unsave) does **not** show a confirmation dialog.

---

## User Interface Design

### Layout

```
┌────────────────────────────────────────────────────────────────┐
│  Repository                                                     │
│────────────────────────────────────────────────────────────────│
│  [ Search reports...                         ]  [ Filters ▾ ]  │
│  ● Equity Research  ● Date Saved: Apr 2026        [Clear all]  │
│  Sort: Date Saved (newest) ▾                                   │
│  ─────────────────────────────────────────────────────────     │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ [FileText]  AAPL-initiation-coverage.pdf                │   │
│  │              Equity Research  ·  Apr 3, 2026  ·  Apr 5  │   │
│  │                                           [↓]  [✕]     │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ [FileText]  AAPL-earnings-q1-2026.pdf                   │   │
│  │              Earnings Updates  ·  Apr 2  ·  Apr 4       │   │
│  │                                           [↓]  [✕]     │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

---

### Page Header

| Element | Spec |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Title | "Repository" — `text-xl font-semibold text-[--color-text-primary]`, `pl-6` |

---

### Controls Bar

| Element | Spec |
|---|---|
| Container | `flex items-center gap-3 px-6 py-3 border-b border-[--color-border-subtle]` |
| Search input | `flex-1 h-9 bg-[--color-bg-input] border border-[--color-border-subtle] rounded-[--radius-md] px-3 text-sm text-[--color-text-primary] placeholder:text-[--color-text-tertiary]`; `Search` icon (14px, `--color-text-tertiary`) prepended; focus: border → `--color-border-secondary` |
| Filters button | `flex items-center gap-1.5 h-9 px-3 rounded-[--radius-md] border border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]`; `SlidersHorizontal` icon (14px); when filters are active: `border-[--color-accent-primary] text-[--color-accent-primary]` |

---

### Active Filter Chips

Shown below the controls bar when one or more filters are active.

| Element | Spec |
|---|---|
| Container | `flex items-center flex-wrap gap-2 px-6 py-2 border-b border-[--color-border-subtle]` |
| Filter chip | `flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-[--color-accent-subtle] border border-[--color-accent-primary]/30 text-sm text-[--color-accent-primary]`; `×` icon button (12px) on the right; click dismisses the individual filter |
| "Clear all" link | `text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] ml-auto`; shown only when filters exist |

---

### Sort Control

| Element | Spec |
|---|---|
| Container | `flex items-center px-6 py-2` |
| Trigger | `flex items-center gap-1 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]`; format: "Sort: Date Saved (newest)"; `ChevronDown` icon (12px); transition `--duration-fast` |
| Dropdown | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-md py-1 min-w-[220px]`; positioned below trigger |
| Option row | `flex items-center justify-between px-3 py-2 text-sm text-[--color-text-primary] hover:bg-[--color-surface-hover] cursor-pointer`; active: `text-[--color-accent-primary]` + `Check` icon (14px, `--color-accent-primary`) right-aligned |

---

### Filters Dropdown

Opened by the "Filters" button.

| Element | Spec |
|---|---|
| Panel | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md p-4 w-[300px]`; positioned below the Filters button |
| Section label | `text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] mb-2` |
| Department filter | Checklist — each department on its own row: `flex items-center gap-2 py-1.5 text-sm text-[--color-text-primary]`; checkbox uses `--color-accent-primary` when checked |
| Date range | Two `<input type="date">` fields side by side, labeled "From" / "To"; standard input style `h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm` |
| Apply button | Accent filled `h-8 px-3 rounded-[--radius-md] text-sm w-full mt-3` |

---

### Report Entry Row

Each row is a full-width item in a bordered list. The list container uses `divide-y divide-[--color-border-subtle]` with `border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden mx-6 my-2`.

| Element | Spec |
|---|---|
| Row container | `flex items-center gap-4 px-4 py-3.5 hover:bg-[--color-surface-hover] cursor-pointer`; transition `--duration-fast` |
| File icon | `FileText` Lucide icon, 20px, `--color-text-secondary`; `flex-shrink-0` |
| Text column | `flex flex-col min-w-0 flex-1` |
| Filename | `text-base font-medium text-[--color-text-primary] truncate` |
| Metadata line | `text-xs text-[--color-text-secondary] flex items-center gap-1.5 mt-0.5`; format: "[Department badge] · Generated [date] · Saved [date]" |
| Department badge | `text-xs rounded-full px-2 py-0.5 font-medium`; each department has a distinct muted tint: Equity Research `bg-[--color-info]/10 text-[--color-info]`; Earnings Update `bg-[--color-success]/10 text-[--color-success]`; Macro `bg-[--color-warning]/10 text-[--color-warning]`; Morning `bg-[--color-accent-subtle] text-[--color-accent-primary]`; Retail Sentiment `bg-[--color-info]/10 text-[--color-info]` |
| Action buttons | `flex items-center gap-1 flex-shrink-0 ml-2`; hidden by default on desktop, revealed on row hover; always visible on touch |
| Download button | Icon-only `w-7 h-7 rounded-[--radius-sm] flex items-center justify-center text-[--color-text-secondary] hover:bg-[--color-surface-active] hover:text-[--color-text-primary]`; `Download` icon (14px) |
| Remove button | Same size; `Trash2` icon (14px); hover: `text-[--color-feedback-error] bg-[--color-feedback-error]/10` |

---

### Loading State

While the initial report list is fetching:

| Element | Spec |
|---|---|
| Skeleton rows | 8 rows inside the bordered list container; each row: `flex items-center gap-4 px-4 py-3.5` |
| Icon placeholder | `w-5 h-5 rounded bg-[--color-surface-hover] animate-pulse` |
| Filename placeholder | `h-4 rounded bg-[--color-surface-hover] animate-pulse`; widths vary: 40%, 55%, 35%, 50% alternating |
| Metadata placeholder | `h-3 rounded bg-[--color-surface-hover] animate-pulse w-48 mt-1.5` |

---

### Infinite Scroll

- The report list loads 50 entries on page load
- A loading indicator appears at the bottom of the list when fetching more: three animated dots (same pattern as chat loading indicator)
- When all entries are loaded: "All reports loaded" in `text-xs text-[--color-text-tertiary] text-center py-4`

---

### FileViewer Panel (from Repo)

When a report is opened from the Repo, the FileViewer header shows Download + Close buttons only — no "Save to Repo" button (the report is already saved).

```
┌────────────────────────────────────────────────────────────┐
│  AAPL-initiation-coverage.pdf   [↓ Download]  [✕ Close]    │
│  PDF · 12 pages · Equity Research · Generated Apr 3, 2026  │
└────────────────────────────────────────────────────────────┘
```

---

### Remove Report Confirmation Modal

```
┌──────────────────────────────────────────────────────────┐
│  Remove from Repository?                          [✕]    │
│──────────────────────────────────────────────────────────│
│  "q1-macro-briefing.pdf" will be removed from your       │
│  Repository.                                             │
│                                                          │
│                          [Cancel]  [Remove]              │
└──────────────────────────────────────────────────────────┘
```

| Element | Spec |
|---|---|
| Modal | `bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle] max-w-[400px] w-full p-6`; centered |
| Filename in body | Quoted, `font-medium text-[--color-text-primary]` |
| Cancel | Outline `h-9 px-4 rounded-[--radius-md] border border-[--color-border-secondary] text-sm text-[--color-text-secondary]` |
| Remove | Destructive `h-9 px-4 rounded-[--radius-md] bg-[--color-feedback-error] text-white text-sm font-medium hover:opacity-90` |
| On remove success | Row fades out `opacity 1→0, height → 0, duration 200ms`; toast: "Report removed from Repository" with "Undo" link for 4s |

---

### Empty States

**No saved reports:**

| Element | Spec |
|---|---|
| Container | `flex flex-col items-center justify-center flex-1 gap-3 text-center px-6` |
| Icon | `BookOpen` (40px, `--color-text-tertiary`) |
| Heading | `text-base font-medium text-[--color-text-primary]` — "No saved reports yet." |
| Sub-text | `text-sm text-[--color-text-secondary]` — "Save a report from any department to see it here." |

**Search or filter returns no results:**

| Element | Spec |
|---|---|
| Icon | `SearchX` (40px, `--color-text-tertiary`) |
| Heading | "No reports match your search." |
| Sub-text | "Try adjusting your filters or search terms." |
| Action | "Clear filters" accent text link |

---

### Toast Notifications

| Event | Message | Duration |
|---|---|---|
| Report removed | "Removed from Repository" + "Undo" link | 4s |
| Undo remove | "Report restored." | 2s |
| Remove failed | "Failed to remove. Try again." (error color) | 4s |

Toast style: `fixed bottom-4 right-4 z-50 flex items-center gap-3 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md px-4 py-3 text-sm text-[--color-text-primary]`; entry: `opacity 0→1, y 8→0, duration 200ms`; exit: `opacity 1→0, duration 150ms`.

---

## Report Framework

Not applicable — the Repository does not generate reports.

---

## Configurations

None — the Repository has no user-configurable settings.
