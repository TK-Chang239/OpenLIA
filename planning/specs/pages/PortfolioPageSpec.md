# Portfolio Page Spec

## Page Overview
The Portfolio Page manages a list of tickers that the user is tracking. Departments reference the Portfolio to obtain the user's tracked tickers and tailor their reports accordingly (e.g., Earnings Reports scans this list daily, Retail Sentiment scores these tickers, Morning Briefings prioritizes news for these companies).

## Page Functionalities
1. **Ticker Search and Add**: The user can search for tickers via a search bar at the top of the page. Search results show ticker symbol and company name. Adding a ticker places it in the "All" group by default and prompts the user to optionally assign it to additional groups.
2. **Ticker Remove**: The user can remove a ticker from the portfolio entirely, or remove it from a specific group while keeping it in "All".
3. **Groups**: Tickers are organized into groups. The "All" group contains every tracked ticker and cannot be deleted or renamed. Users can create, rename, reorder, and delete custom groups. Deleting a group does not remove its tickers from "All".
4. **View Modes**: The user can switch between two view modes — List View and Card View. The selected view mode persists across sessions.
5. **Sort Order**: The user can sort tickers within any group by alphabetical order (A→Z or Z→A) or by current price (high→low or low→high). The selected sort order persists per group across sessions.
6. **Real-Time Price Data**: Each ticker displays its current price, daily change (absolute and percentage), and a sparkline or area chart depending on the view mode. Price data is sourced from EODHD, which covers all markets including US and TWSE. Price data refreshes automatically during market hours.
7. **Ticker Detail Navigation**: Clicking on a ticker row or card opens a new chat session in the Stock Research Department with that ticker pre-loaded.

---

## Page Design

### Layout

```
┌────────────────────────────────────────────────────────────────┐
│  Portfolio                                                      │
│────────────────────────────────────────────────────────────────│
│  [ Search tickers...                              ] [≡ | ⊞]   │
│  ─────────────────────────────────────────────────────────     │
│  [All ●]  [Tech]  [Dividends]  [Watch List]  [+ New Group]     │
│  ─────────────────────────────────────────────────────────     │
│  Sort: A→Z ▾                                                   │
│                                                                │
│  [Ticker Content Area]                                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

#### Page Header

| Element | Detail |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Title | "Portfolio" — `text-xl font-semibold text-[--color-text-primary]`, `pl-6` |

#### Controls Bar

| Element | Detail |
|---|---|
| Search bar | `flex-1 bg-[--color-bg-input] border border-[--color-border-subtle] rounded-[--radius-md] px-3 h-9 text-sm`; focus: border → `--color-border-secondary`; `Search` icon (14px, `--color-text-tertiary`) prepended inside input |
| View toggle | Two icon buttons side by side: `List` and `Grid`; active: `bg-[--color-surface-active] text-[--color-text-primary]`; inactive: `text-[--color-text-secondary] hover:bg-[--color-surface-hover]`; `rounded-[--radius-md] w-8 h-8` each |
| Controls padding | `px-6 py-3` |

#### Group Tab Bar

| Element | Detail |
|---|---|
| Container | `flex items-center gap-1 px-6 pb-0 pt-0 overflow-x-auto border-b border-[--color-border-subtle]` |
| Tab pill | `px-3 py-2 text-sm rounded-t-md cursor-pointer`; active: `text-[--color-text-primary] font-medium border-b-2 border-[--color-accent-primary] -mb-px`; inactive: `text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]`; transition `--duration-fast` |
| "+ New Group" | Rightmost tab item; `Plus` icon (12px) + "New Group"; on click: inline input appears at the end of the tab bar for naming the group |

#### Sort Control

| Element | Detail |
|---|---|
| Container | `px-6 py-2 flex items-center gap-2` |
| Sort dropdown trigger | `text-sm text-[--color-text-secondary] flex items-center gap-1`; "Sort: A→Z" + `ChevronDown` icon (12px); hover: `text-[--color-text-primary]`; opens a small dropdown menu |
| Dropdown | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-md py-1`; 4 options; active option has `--color-accent-primary` checkmark |

- Search bar spans full width of the controls bar
- View mode toggle sits in the top-right of the controls bar
- Group tabs are a horizontal scrollable tab bar below the controls bar
- Sort control sits below the group tabs, left-aligned
- Ticker content area fills the remaining space and scrolls independently

---

### Search and Add Flow

| Element | Detail |
|---|---|
| Search bar | Full-width input at the top of the page, labeled "Search tickers" |
| Search results | Dropdown list below the search bar showing matching ticker symbol + company name |
| Add action | Clicking a search result adds the ticker to "All" |
| Group assignment prompt | After adding, a small popup appears listing existing groups with checkboxes to optionally assign the ticker to additional groups |

#### Search Results Dropdown

| Element | Spec |
|---|---|
| Container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md py-1`; positioned directly below the search bar; `w-full max-w-search-bar z-30` |
| Result row | `flex items-center gap-3 px-4 py-2.5 hover:bg-[--color-surface-hover] cursor-pointer`; transition `--duration-fast` |
| Ticker symbol | `text-sm font-semibold text-[--color-text-primary] w-12 flex-shrink-0` |
| Company name | `text-sm text-[--color-text-secondary] flex-1 truncate` |
| Exchange label | `text-xs text-[--color-text-tertiary] flex-shrink-0` — e.g., "NASDAQ", "NYSE", "TWSE" |
| Already added row | `flex items-center gap-3 px-4 py-2.5 cursor-default opacity-50`; "Already added" `text-xs text-[--color-text-tertiary]` right-aligned |
| No results | Single row: `px-4 py-3 text-sm text-[--color-text-secondary]` — "No tickers found for "[query]"" |
| Max rows | 8 results; scrollable if more |
| Keyboard | `ArrowUp`/`ArrowDown` navigates rows; `Enter` selects; `Escape` dismisses |

#### Group Assignment Popup

Shown immediately after a ticker is added, anchored below the search bar. Allows the user to optionally assign the new ticker to additional groups.

| Element | Spec |
|---|---|
| Container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md p-4 w-[260px]`; appears with `opacity 0→1, y -4→0, duration 150ms`; auto-dismisses after 4s or on any click outside |
| Header | `text-sm font-medium text-[--color-text-primary] mb-3` — "Add to groups" |
| Group row | `flex items-center gap-2 py-1.5 text-sm text-[--color-text-primary]`; checkbox left-aligned; group name |
| "All" row | Always shown first, always checked and disabled (cannot be removed from All) |
| Custom group rows | Unchecked by default; user can check to add |
| Done button | `w-full h-8 mt-3 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm hover:bg-[--color-accent-hover]` |

---

#### Group Context Menu

Triggered by right-click or long-press on a group tab.

| Element | Spec |
|---|---|
| Menu container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-md py-1 min-w-[160px] z-40`; appears at cursor position |
| Menu item | `flex items-center gap-2 px-3 py-2 text-sm text-[--color-text-primary] hover:bg-[--color-surface-hover] cursor-pointer` |
| Rename | `Pencil` icon (14px) + "Rename"; click: tab name becomes an inline `<input>`, focused, select-all; Enter or blur saves |
| Reorder | `GripVertical` icon (14px) + "Reorder…"; opens a simple reorder modal (drag list) |
| Delete | `Trash2` icon (14px) + "Delete group"; `text-[--color-feedback-error]`; click shows confirm popover |
| Delete confirm | Small inline popover: "Delete group and keep tickers in All?" + "Delete" (destructive) + "Cancel" |
| "All" group | Context menu not shown — "All" cannot be renamed, reordered, or deleted |

---

### List View

The traditional list view where every ticker occupies a single horizontal row. The content area displays one group at a time, selected via the tab bar.

| Element | Position | Detail |
|---|---|---|
| Ticker symbol | Left | `text-base font-semibold text-[--color-text-primary]` (e.g., AAPL) |
| Company name | Left, below symbol | `text-xs text-[--color-text-secondary]` (e.g., Apple Inc.); truncated with ellipsis |
| Sparkline | Center | Miniature line chart ~80×28px showing the day's price movement; no axes or labels; green line if up, red line if down; implemented via inline SVG |
| Current price | Right | `text-base font-medium text-[--color-text-primary]`, right-aligned |
| Metric badge | Far right | `text-sm font-medium rounded-full px-2 py-0.5`; positive: `bg-[--color-feedback-success]/10 text-[--color-feedback-success]`; negative: `bg-[--color-feedback-error]/10 text-[--color-feedback-error]`; neutral: `text-[--color-text-secondary]`; tappable to toggle dollar/percent display |
| Row container | `flex items-center gap-4 px-6 py-3 border-b border-[--color-border-subtle] hover:bg-[--color-surface-hover] cursor-pointer`; transition `--duration-fast` |
| Row height | ~60px |
| Remove reveal | On hover (desktop): `Trash2` icon button (14px, `--color-text-tertiary`) revealed at the far right edge; hover icon: `--color-feedback-error`; on mobile: swipe-left reveals red delete zone |

#### Groups in List View

Groups use a **top tab bar** layout. The tab bar sits below the search bar as a horizontal row of pills (e.g., `[All] [Tech] [Dividends]`). Selecting a tab replaces the list content below with that group's tickers. Only one group is visible at a time.

| Element | Detail |
|---|---|
| Tab bar | Horizontally scrollable row of group pills |
| Active tab | Visually highlighted (bold text, underline, or filled background) |
| "+ New Group" button | Positioned at the end of the tab bar; opens an inline input to name a new group |
| Group context menu | Long-press or right-click a tab to rename, reorder, or delete the group |

---

### Card View

Each ticker is represented as a self-contained card providing a visual performance snapshot. Cards are arranged in a responsive grid within the selected group.

| Element | Position | Detail |
|---|---|---|
| Card container | — | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden`; hover: `border-[--color-border-secondary] shadow-sm`; transition `--duration-fast`; cursor pointer |
| Ticker symbol | Top left | `text-base font-bold text-[--color-text-primary] px-4 pt-4` |
| Company name | Below symbol | `text-xs text-[--color-text-secondary] px-4 pb-2`; truncated |
| Daily performance area chart | Card body | Area chart filling a ~100px-tall zone in the card middle; green gradient fill (`--color-feedback-success` at 40% opacity → transparent) if up; red gradient fill (`--color-feedback-error` at 40% → transparent) if down; line color matches fill color at full opacity; no axes, no labels |
| Current price | Bottom right | `text-lg font-semibold text-[--color-text-primary] px-4 pb-1` |
| Metric badge | Below price | Same style as list view badge; `px-4 pb-4` |
| Card dimensions | — | ~160px wide minimum; height auto-sized to content + chart zone |

#### Groups in Card View

Groups use a **sectioned grid** layout. The user scrolls vertically through all groups. Each group has a section header followed by a responsive grid of cards (2–3 cards wide depending on viewport). Groups are separated by a horizontal divider.

| Element | Detail |
|---|---|
| Section header | Group name in bold with a count of tickers in the group (e.g., "Tech (5)") |
| Card grid | Cards wrap to the next row; 3 wide on desktop, 2 on tablet, 1 on mobile |
| Divider | Subtle horizontal line between groups |
| Group context menu | Accessible via a menu icon on the section header; allows rename, reorder, delete |

---

### Feedback & Messaging

| Message Type | Placement | Appearance |
|---|---|---|
| Ticker added | Toast notification, bottom-right | "AAPL added to Portfolio" |
| Ticker removed | Toast notification, bottom-right | "AAPL removed" + "Undo" link; 5s window |
| Group deleted | Toast notification, bottom-right | "Group 'Tech' deleted" + "Undo" link; 5s window |
| Search — no results | Inline in results dropdown | "No tickers found for "[query]"" in muted text |
| Price data unavailable | Inline in ticker row/card | Muted "—" in place of price and sparkline |

#### Toast Notification Design

| Element | Spec |
|---|---|
| Container | `fixed bottom-4 right-4 z-50 flex items-center gap-3 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md px-4 py-3 text-sm text-[--color-text-primary] min-w-[240px]` |
| Entry animation | `opacity 0→1, y 8→0, duration 200ms, ease-out` |
| Exit animation | `opacity 1→0, y 0→4, duration 150ms` |
| Auto-dismiss | 4s for informational; 5s for toasts with Undo |
| Undo link | `text-[--color-accent-primary] hover:text-[--color-accent-hover] ml-auto font-medium`; clicking reverses the action and dismisses the toast immediately |
| Multiple toasts | Stack vertically with `gap-2`; max 3 visible at once; oldest dismisses first |

---

### Behavior & Interactions

#### Search
- Search triggers on input with a short debounce (~300ms)
- Results are filtered by ticker symbol and company name
- Pressing Enter or clicking a result adds the ticker
- If the ticker is already in the portfolio, the result shows "Already added" and is not actionable

#### Ticker Removal
- Swipe-left on a row (mobile) or hover to reveal a remove icon (desktop)
- Removing from a custom group only removes the group assignment; the ticker stays in "All"
- Removing from "All" removes the ticker from the portfolio entirely and all groups
- Removal is undoable for 5 seconds via the toast notification

#### Group Management
- Groups can be reordered by dragging tabs (desktop) or via a reorder option in the context menu
- "All" is always the first tab and cannot be moved
- Deleting a group with tickers shows a confirmation: "Delete group 'Tech'? Tickers will remain in your portfolio."

#### View Mode Toggle
- Toggling between List and Card view animates with a short crossfade (~150ms)
- The selected view mode is persisted and restored on next visit

#### Sort Order
- A sort dropdown below the group tabs offers four options: A→Z, Z→A, Price High→Low, Price Low→High
- Selecting a sort option applies immediately without a page reload
- Sort preference is saved per group and restored on next visit
- Newly added tickers are inserted into the current sort order, not appended to the end

#### Price Refresh
- Price data auto-refreshes at a regular interval during market hours
- Outside market hours, the last closing price is shown with a "Market closed" indicator

---

## States

| State | Description |
|---|---|
| **Empty** | No tickers in portfolio; shows a centered empty state: `BarChart2` icon (40px, `--color-text-tertiary`) + "Your portfolio is empty" heading + "Search above to add tickers" sub-text |
| **Populated** | Tickers displayed in the selected view mode and group |
| **Loading** | Skeleton rows/cards shown while price data is being fetched: `bg-[--color-surface-hover] rounded-[--radius-md] animate-pulse`; sparkline zone is a solid rounded rectangle; price/badge zones are narrow rounded rectangles |
| **Market Closed** | Price values shown are the last closing price; a "Market closed" muted indicator `text-xs text-[--color-text-tertiary]` appears in the sort bar, below the view toggle |
| **Search Active** | Search bar focused; results dropdown appears below with matching rows |
| **Error** | Price data unavailable: sparkline replaced with `—`; price shows "—" in `--color-text-tertiary`; badge hidden; subtle "Refresh" icon button shown on row hover |

---

## Accessibility

- Search bar has `role="combobox"` with `aria-expanded` reflecting dropdown visibility
- Search results use `role="listbox"` with `aria-activedescendant` for keyboard navigation
- Group tab bar uses `role="tablist"` with `role="tab"` for each group and `aria-selected` on the active tab
- View mode toggle is keyboard-accessible and announces the active mode to screen readers
- Ticker rows/cards are focusable and announce ticker name, price, and change on focus
- Remove and group context menu actions are keyboard-accessible
- Sufficient color contrast for all text and UI elements (WCAG AA minimum)
- Price change colors (green/red) are supplemented with icons or text direction (+/-) for color-blind users

---

## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Full layout; Card View shows 3 columns; List View shows all columns |
| Tablet (768–1024px) | Card View shows 2 columns; List View hides sparkline column |
| Mobile (<768px) | Card View shows 1 column; List View hides sparkline; swipe-to-remove enabled |

---

## Page Settings
There are no user-configurable settings for this page.

## Report Framework
There are no report frameworks for this page.

## Configurations
- LLM: None (this page does not interact with any LLM)

---

## Non-Goals (v1)
- Portfolio performance tracking (total value, P&L, allocation percentages)
- Actual share holdings or cost-basis entry
- Price alerts or push notifications from this page
- Drag-and-drop reordering of tickers within a group
- Import/export of ticker lists (CSV, etc.)
- Historical chart timeframes beyond intraday on this page

---

## Open Questions
- Should there be a confirmation prompt before opening a new Stock Research chat session if the user already has an active session for that department?
