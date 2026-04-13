# Earnings Update Department Spec
## Department Overview
The Earnings Update Department is in charge of monitoring earnings report releases by companies on the watchlist and generating analysis reports on the earnings reports whenever an earnings report is released. The user will add companies that he wants to track to the watchlist.

In addition, the user can also request an immediate generation of an earnings analysis report through EU.

## Functions
1. **Watchlist**: The user can manage a watchlist for EU, adding or removing companies/tickers that he wants to follow. When the user adds a company/ticker to the watchlist, find  the next earnings release date for the company to schedule the analysis report. Display the next earning report release date of the company on the watchlist for the user to see, including whether its a pre-market or post-market release.
2. **EU Cabinet**: When analysis reports are completed, they are added to the EU Cabinet that stores all generated reports, organized by chronological order. On the page under the EU Cabinet section there is a small preview list for most recently generated reports. The user can open the EU Cabinet to see the full list, as well as click on these reports to open report preview to read these reports.
3. **Automated Reports**: When the release date for a company arrives, automatically generate an analysis report on the earnings release, adds the report to the "generated reports section," and notifies the user through email. 
4. **On-Demand Reports**: The user can request EU to generate an earnings analysis report immediately on a company's latest earnings release. This "On-demand" report will also be saved to the EU Cabinet.

## Report Frameworks

| Report Type | Framework File | Sections |
|---|---|---|
| Earnings Analysis Report | `earnings_update.json` | 8 sections (Quick Take, Market Reaction, Key Financials, Operational Highlights, Forward Guidance, Earnings Call, Risk Assessment, Thesis Check) |

Style guide: `earnings_update_style_guide.md`

## User Interface Design

### Layout

The Earnings Updates page uses a **two-section stacked layout** within the main content area. The page header provides the primary action. Content is not a chat interface — it is a dashboard with a watchlist panel and a report cabinet.

```
┌────────────────────────────────────────────────────────────────┐
│  Earnings Updates                    [+ On-Demand Report]      │
│────────────────────────────────────────────────────────────────│
│                                                                │
│  WATCHLIST                                   [+ Add Ticker]   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │  AAPL        │ │  TSLA        │ │  NVDA        │          │
│  │  Apple Inc.  │ │  Tesla Inc.  │ │  NVIDIA      │          │
│  │  Apr 25      │ │  Apr 22      │ │  Apr 29      │          │
│  │  Post-Market │ │  Pre-Market  │ │  Post-Market │          │
│  │  [×]         │ │  [×]         │ │  [×]         │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
│                                                                │
│  ─────────────────────────────────────────────────────────    │
│                                                                │
│  RECENT REPORTS                          [Open Cabinet →]     │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  AAPL  Apple Inc. — Q1 FY2026 Earnings       Apr 9 [Open]│ │
│  ├──────────────────────────────────────────────────────────┤ │
│  │  TSLA  Tesla Inc. — Q1 FY2026 Earnings       Apr 8 [Open]│ │
│  ├──────────────────────────────────────────────────────────┤ │
│  │  MSFT  Microsoft — Q3 FY2026 Earnings        Apr 2 [Open]│ │
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
| Page title | "Earnings Updates" — `text-xl font-semibold text-[--color-text-primary]`, `pl-6` |
| On-Demand Report button | `pr-6`; `Plus` icon (16px) + "On-Demand Report" label; `bg-[--color-accent-primary] text-white text-sm px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover]`; opens On-Demand modal |

---

### Watchlist Section

Horizontally scrollable row of company cards showing the next scheduled earnings date.

| Element | Detail |
|---|---|
| Section header | `text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]`, left-aligned, `px-6 pt-5 pb-3` |
| "+ Add Ticker" button | Right of section header; `Plus` icon (14px) + "Add Ticker"; outline style: `border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] px-3 h-7`; opens the Add Ticker popover |
| Cards container | `flex gap-3 overflow-x-auto px-6 pb-4 scroll-snap-x`; no scrollbar visible; fade-out mask on right edge |
| Watchlist card | `flex-shrink-0 w-[148px] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-3 flex flex-col gap-1`; on hover: `border-[--color-border-secondary] shadow-sm`; transition `--duration-fast` |
| Ticker symbol | `text-base font-semibold text-[--color-text-primary]` |
| Company name | `text-xs text-[--color-text-secondary]`; truncated with ellipsis if long |
| Next earnings date | `text-sm font-medium text-[--color-text-primary] mt-1`; formatted as "Apr 25" |
| Release timing badge | Pill badge: "Pre-Market" or "Post-Market"; `text-xs rounded-full px-2 py-0.5`; Pre-Market: `bg-[--color-info]/10 text-[--color-info]`; Post-Market: `bg-[--color-warning]/10 text-[--color-warning]` |
| Remove button | `×` icon (14px, `--color-text-tertiary`), top-right of card, appears on card hover; click removes the ticker from the watchlist with a fade-out animation |
| "Overdue" state | If the earnings date has passed without a generated report: card border `--color-feedback-error`, badge replaced with muted "Date passed" |
| Empty state | If watchlist is empty: a single dashed-border card placeholder: "Add companies to your watchlist to track upcoming earnings" with `+ Add Ticker` CTA centered inside |

---

### Add Ticker Flow

| Step | Detail |
|---|---|
| Trigger | Click "+ Add Ticker" button in the Watchlist section header |
| Input | Inline search popover below the button; text input with placeholder "Ticker symbol or company name"; search debounce 300ms |
| Results | Dropdown list; each row: ticker symbol (bold) + company name (muted); max 6 results |
| Add | Click a result to add to watchlist; closes popover; card slides into the watchlist with `opacity 0→1, x -12→0, duration 200ms` |
| Already tracked | Result rows for already-tracked companies show "Already watching" label and are not clickable |

---

### Recent Reports Section

Shows the 5 most recently generated reports as a scrollable list. Full history is in the Cabinet.

| Element | Detail |
|---|---|
| Section header | Same style as Watchlist section header; "RECENT REPORTS" label left-aligned; "Open Cabinet →" text link right-aligned (`text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover]`) |
| Report row | `flex items-center gap-4 px-6 py-3.5 border-b border-[--color-border-subtle] hover:bg-[--color-surface-hover]`; transition `--duration-fast`; clickable row (except action buttons) opens FileViewer |
| Ticker badge | `text-sm font-semibold text-[--color-text-primary] w-12 flex-shrink-0` |
| Report label | `flex-1 text-base text-[--color-text-primary]`; company name + em dash + report period (e.g., "Apple Inc. — Q1 FY2026 Earnings") |
| Date | `text-sm text-[--color-text-secondary] flex-shrink-0`; formatted as "Apr 9" |
| Open button | `text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover] flex-shrink-0 ml-2`; opens FileViewer |
| New badge | If the report was generated within the last 24 hours and not yet opened: a small filled dot `w-1.5 h-1.5 rounded-full bg-[--color-accent-primary]` prepended to the row |
| Empty state | If no reports have been generated yet: centered placeholder `text-sm text-[--color-text-tertiary]` + "On-Demand reports and automated reports will appear here" |

---

### EU Cabinet (Full View)

Opened via "Open Cabinet →" in the Recent Reports header. The cabinet slides in as a full-page overlay or navigates to a sub-view within the Earnings page.

```
┌────────────────────────────────────────────────────────────────┐
│  ← Back to Earnings Updates                   EU Cabinet       │
│────────────────────────────────────────────────────────────────│
│  [ Search reports...                     ]  [ Filters ▾ ]     │
│  ─────────────────────────────────────────────────────────     │
│                                                                │
│  April 2026                                                    │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  AAPL  Apple Inc. — Q1 FY2026     Apr 9  [Open] [↓] [×] │ │
│  ├──────────────────────────────────────────────────────────┤ │
│  │  TSLA  Tesla Inc. — Q1 FY2026     Apr 8  [Open] [↓] [×] │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Header | "← Back" text link (returns to main view) + "EU Cabinet" title centered or right-aligned |
| Search | Full-width search input; searches by company name or ticker |
| Filter button | "Filters ▾" opens a filter dropdown: by ticker, date range |
| Date group headers | Reports grouped by month; `text-sm font-medium text-[--color-text-secondary] px-6 py-2` |
| Cabinet row | Same style as Recent Reports row; additional `Download` (↓) and `Remove` (×) icon buttons appear on hover at far right |
| Remove | Opens a small confirmation tooltip: "Remove this report?" with Confirm/Cancel; on confirm: row fades out |

---

### On-Demand Report Modal

Triggered by "+ On-Demand Report" in the page header. Generates an immediate earnings analysis on a company's latest released earnings.

```
┌──────────────────────────────────────────────────────────┐
│  On-Demand Earnings Update                         [✕]   │
│──────────────────────────────────────────────────────────│
│  Generate an earnings analysis for a company's most      │
│  recently released earnings report.                      │
│                                                          │
│  [ Search for a ticker or company...               ]     │
│                                                          │
│  AAPL — Apple Inc.   ✓ Last earnings: Jan 30, 2026       │
│                                                          │
│                         [Cancel]  [Generate Report]      │
└──────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Modal style | Same dimensions and style as Report Settings modal (`max-w-[480px]`, `rounded-[--radius-lg]`, shadow) |
| Search input | Full-width; results dropdown: ticker + company name + last earnings date |
| Selected state | Selected company shown below search with a `CheckCircle` icon and last earnings date |
| Generate Report button | Accent filled; disabled until a company is selected; on click: closes modal, shows inline loading indicator in Recent Reports section while generating |
| Generation progress | A subtle animated bar or spinner appears in the Recent Reports section with "Generating report for AAPL..." text; report row appears when complete |

---

### Notification Dot (Sidebar)

When a new automated earnings report is generated, the "Earnings Updates" nav item in the sidebar shows a notification dot: a `w-1.5 h-1.5 rounded-full bg-[--color-accent-primary]` dot positioned top-right of the icon. The dot disappears once the user visits the Earnings Updates page.

---

### States

| State | Visual Treatment |
|---|---|
| **Empty — No Watchlist** | Watchlist section shows dashed placeholder card; Recent Reports shows empty state message |
| **Empty — No Reports** | Recent Reports empty state message visible |
| **Loading** | Watchlist cards and report rows replaced by animated skeleton elements: `bg-[--color-surface-hover] rounded-[--radius-md] animate-pulse` |
| **Populated** | Full layout as described above |
| **Generating (On-Demand)** | Inline loading indicator in Recent Reports with generation status text |
| **Error** | Inline error banner: "Failed to load earnings data. Try again." with retry button |

---

### Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Full layout; watchlist shows up to 5 cards before scrolling |
| Tablet (768–1024px) | Same layout; watchlist cards slightly narrower |
| Mobile (<768px) | Watchlist scrolls horizontally; report rows hide date column; Cabinet view is full-screen |

## Page Settings
In the settings page for SR, changeable settings are avaliable as below:
1. Report Sections: Allows the user to select what sections the user wants to be included in the report. Default sections are included for the user to check or uncheck.
2. Custom Sections: There is also a custom button that allows users to add custom sections. The custom button opens up another pop-up that allows user to input a name for their custom section as well as a description box for what the section should be about.
3. Length Adjuster: Allows user to choose the length of reports, such as concise, normal, or ellaborative.

## Data Requirements

EU uses pre-fetch for the watchlist (earnings dates fetched on add) and tool-calling for report generation.

**Basic (department disabled without these):**

| Requirement | Type | Description |
|---|---|---|
| Earnings dates | `earnings_dates` | Upcoming and historical earnings release dates for watchlist scheduling and automated triggers |
| Financial statements | `financial_statements` | Quarterly income statement, balance sheet for Key Financials and Operational Highlights sections |
| Stock quote | `stock_quote` | Current price and daily change for Market Reaction analysis |

**Advanced (features degrade gracefully if missing):**

| Requirement | Type | Description | Without It |
|---|---|---|---|
| Earnings transcripts | `earnings_transcripts` | Earnings call transcripts for qualitative analysis | Earnings Call section omitted from report |
| Company news | `company_news` | News around earnings events for context | Event context section lacks news coverage |
| Historical prices | `historical_prices` | Price history for pre/post earnings price action | Market Reaction section lacks price chart context |
| Analyst ratings | `analyst_ratings` | Consensus estimates for beat/miss scoring | Key Financials section lacks consensus estimate comparison |

## Configuration
- LLM Model: