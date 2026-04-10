# Retail Sentiment Department Spec

## Page Overview
The Retail Sentiment Department will manage a retail sentiment monitor dashboard, where it will aggregate data from social media platforms and sentiment api's to calculate metrics for measuring retail investor sentiments. The user will add specific topics or keywords to the dashboard for RS to monitor.

## Functionalities
1. **Sentiment Dashboard**: RS will be managing a monitor dashboard that aggregates user inputted hashtags/keywords/items and maps them against key performance metrics.
2. **Monitor List**: The user 

## Page Settings
There are no user-configurable settings beyond the monitor list itself.

## User Interface Design

### Layout

The Retail Sentiment page is a live monitoring dashboard. The top of the page holds the monitor list as a tab bar. Below, a dashboard displays sentiment metrics for the selected ticker.

```
┌────────────────────────────────────────────────────────────────┐
│  Retail Sentiment                           [+ Add Ticker]     │
│────────────────────────────────────────────────────────────────│
│                                                                │
│  [AAPL ●] [TSLA] [GME] [NVDA]  ·  + Add                       │
│  ─────────────────────────────────────────────────────────    │
│                                                                │
│  AAPL — Apple Inc.                                             │
│  Last updated: just now  [↺ Refresh]                           │
│                                                                │
│  ┌──────────────────┐ ┌──────────────────┐ ┌────────────────┐ │
│  │ Sentiment Score  │ │  Message Volume  │ │  Divergence    │ │
│  │      72          │ │    14.2K posts   │ │   No signal    │ │
│  │  ████████░░  72% │ │   ↑ +42% vs avg  │ │  ─────────     │ │
│  │    Positive      │ │   High Hype      │ │                │ │
│  └──────────────────┘ └──────────────────┘ └────────────────┘ │
│                                                                │
│  SENTIMENT TREND                        [7D ● 30D  90D]       │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                                                          │ │
│  │  [Line chart — sentiment score over selected period]     │ │
│  │                                                          │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

### Page Header

| Element | Detail |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Retail Sentiment" — `text-xl font-semibold text-[--color-text-primary]`, `pl-6` |
| Add Ticker button | `pr-6`; `Plus` icon (16px) + "Add Ticker"; outline style: `border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] px-3 h-8 hover:bg-[--color-surface-hover]` |

---

### Monitor List (Tab Bar)

A horizontal row of ticker tabs identifying what is being monitored. The selected tab drives the dashboard below.

| Element | Detail |
|---|---|
| Container | `flex items-center gap-1 px-6 py-2 border-b border-[--color-border-subtle] overflow-x-auto` |
| Ticker tab | `flex items-center gap-1.5 px-3 py-1.5 rounded-[--radius-md] text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]`; active: `bg-[--color-surface-active] text-[--color-text-primary] font-medium` |
| Live indicator dot | `w-1.5 h-1.5 rounded-full bg-[--color-feedback-success]` shown on the active tab while data is fresh (within last 5 minutes); pulses gently `opacity 1→0.4→1` over 2s |
| Remove tab | Hovering a tab reveals a `×` button (12px) inline; clicking removes the ticker from the monitor list |
| "+ Add" shortcut | Rightmost item in the tab row; `text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover]`; opens Add Ticker popover |

---

### Dashboard — Ticker Header

Shown above the metrics, identifies the currently viewed ticker.

| Element | Detail |
|---|---|
| Ticker symbol | `text-xl font-semibold text-[--color-text-primary]` |
| Company name | `text-base text-[--color-text-secondary]`, inline after an em dash |
| Last updated | `text-sm text-[--color-text-tertiary]`; e.g., "Last updated: 2 min ago" |
| Refresh button | `↺` icon (14px, `--color-text-secondary`) inline with last-updated text; click triggers a manual data refresh; icon spins during refresh: `animate-spin duration-700` |

---

### Metrics Row

Three cards displayed side by side in a responsive 3-column grid.

#### Sentiment Score Card

Measures the positivity vs. negativity ratio of posts.

| Element | Detail |
|---|---|
| Card container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4` |
| Label | "SENTIMENT SCORE" — section label style: `text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]` |
| Score value | Large numeric display: `text-3xl font-semibold text-[--color-text-primary]` (e.g., "72") |
| Score bar | Horizontal progress bar; fill width = score/100; color: ≥60 `--color-feedback-success`, 40–59 `--color-feedback-warning`, <40 `--color-feedback-error`; track: `bg-[--color-surface-active]`; `h-1.5 rounded-full mt-2` |
| Sentiment label | Below the bar: "Positive" / "Neutral" / "Negative" in the corresponding feedback color; `text-sm font-medium` |
| Score range | Score from 0–100; 0 = fully negative, 50 = neutral, 100 = fully positive |

#### Message Volume Card

Measures how much people are talking about the ticker.

| Element | Detail |
|---|---|
| Label | "MESSAGE VOLUME" |
| Volume value | `text-3xl font-semibold text-[--color-text-primary]`; formatted with K/M suffix (e.g., "14.2K") |
| Delta vs. average | `text-sm font-medium`; e.g., "↑ +42% vs. 7-day avg"; color: up `--color-feedback-success`, down `--color-feedback-error`, flat `--color-text-secondary` |
| Hype label | "High Hype" / "Average Activity" / "Low Activity" in muted secondary color; `text-sm text-[--color-text-secondary] mt-1` |

#### Divergence Card

Flags when price and sentiment are moving in opposite directions.

| Element | Detail |
|---|---|
| Label | "DIVERGENCE" |
| Signal value | Text display: "No signal" (neutral), "Bearish signal" (price up, sentiment down), "Bullish signal" (sentiment up, price down); `text-xl font-semibold` in appropriate feedback color or `--color-text-primary` if no signal |
| Sub-description | One-line explanation: e.g., "Price rising while sentiment is declining — potential reversal signal"; `text-sm text-[--color-text-secondary] mt-1`; shown only when a signal is active |
| Icon | When signal active: `AlertTriangle` (16px, `--color-feedback-warning`) next to the label |
| No signal state | Displays a long horizontal dash `——` in `--color-text-tertiary` as the value |

---

### Sentiment Trend Chart

A line chart showing the sentiment score over the selected time period.

| Element | Detail |
|---|---|
| Section label | "SENTIMENT TREND" — section label style |
| Time period selector | Right of section label: "7D" / "30D" / "90D" segmented control; active: `text-[--color-text-primary] font-medium`; inactive: `text-[--color-text-secondary]`; same segmented pill style as Report Settings modal |
| Chart container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4`; height ~200px |
| Chart line | Single smooth line for the sentiment score; color matches score level — above 60: `--color-feedback-success`, 40–60: `--color-feedback-warning`, below 40: `--color-feedback-error` |
| Axes | Minimal — y-axis shows 0/50/100 labels in `text-xs text-[--color-text-tertiary]`; x-axis shows date labels at endpoints and midpoint only |
| Tooltip | On hover: shows date + score in a small floating card `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-sm px-2.5 py-1.5 text-sm` |
| Loading state | Chart area replaced with a `animate-pulse bg-[--color-surface-hover] rounded-[--radius-lg]` skeleton |

---

### Add Ticker Flow

| Step | Detail |
|---|---|
| Trigger | "+ Add Ticker" button in header or "+ Add" shortcut in tab bar |
| Input | Inline popover with search input; placeholder "Search by ticker or keyword" |
| Results | Dropdown list: ticker symbol + company name, max 8 rows |
| Add action | Click result: ticker is added to the monitor list and selected; new tab appears with a slide-in animation |
| Duplicate guard | Already-monitored tickers show "Already monitoring" and are not clickable |

---

### States

| State | Visual Treatment |
|---|---|
| **Empty monitor list** | Full-page empty state: centered `Eye` icon (40px, `--color-text-tertiary`) + "Nothing to monitor yet" heading + "Add a ticker to start tracking retail sentiment" sub-text + accent "Add Ticker" button |
| **Loading data** | Metrics cards show skeleton placeholders; chart area shows pulse skeleton |
| **Data fresh** | Live indicator dot shown on active tab; metrics displayed |
| **Stale data (>15 min)** | Live indicator dot not shown; "Last updated: 18 min ago" text; Refresh button highlighted |
| **Error fetching data** | Inline error in the metrics area: `text-sm text-[--color-feedback-error]` + "Refresh" retry button |

---

### Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | 3-column metrics row; chart at full width |
| Tablet (768–1024px) | 3-column metrics row collapses to 2-column + stacked third card |
| Mobile (<768px) | Single-column stacked metrics cards; chart fills full width |

## Metrics
- Sentiment Score :The "Positivity" vs. "Negativity" of the crowd.
- Message Volume: How much people are talking about a stock (Hype).
- Divergence: When the price goes up but sentiment goes down (a warning sign).
## Configuartions