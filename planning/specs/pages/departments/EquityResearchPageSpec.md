# Equity Research Department Spec

> **⚠️ HISTORICAL ONLY (2026-08-16).** This v1 spec's engine was **REMOVED** (PRs #220/#222). The live Equity Research surface is the **v3 single-model engine** — see `planning/2026-05-27-equity-research-v3-single-model-spec.md` and `planning/specs/pages/departments/EquityResearchV3PageSpec.md`. Kept for historical reference only.

## Page Overview
The Equity Research Department (EqR) is used by the user to research companies, stocks, and sectors by generating reports. The user will prompt EqR with a company or sector that he is interested in, and any specific topics that he would like the report to focus or elaborate on. EqR supports three report modes that the user can toggle between before generating a report.

## Report Modes

EqR supports three distinct report modes. The user selects a mode before generating a report. Each mode produces a different type of report with its own framework template, default sections, and intended use case.

### Stock Initiation Report (Full Initiation)

A comprehensive deep-dive into a company, intended for first-time research or periodic comprehensive reviews. This is the longer, more thorough report type.

**When to use:** The user wants a complete picture of a company — its business, financials, competitive position, risks, and valuation — from the ground up. Suitable when the user is unfamiliar with the company or wants a full refresh.

**Default sections (13):**
1. Company Overview — company profile, key facts, founding date, headquarters, employees
2. Industry Overview — industry definition, current state, market size, historical and projected growth rates
3. Products and Services — product/service descriptions, pain points addressed, revenue breakdown by segment
4. Business Model — how the company makes money, stakeholder relationships, supply chain or revenue model
5. Competitive Analysis — key competitors, comparison table across dimensions, moat assessment
6. Management Team — executive profiles (education, experience, tenure), governance concerns
7. Competitive Advantages and Weaknesses — structured strengths vs. weaknesses across product, business model, sales, technology, financials
8. Risk Analysis — industry risks, operational risks, financial risks, with overall risk rating
9. Historical Financial Data — 5-year balance sheet and income statement tables, M&A impact notes
10. Financial Analysis — margin ratios over time, financial health ratios, peer comparison on turnover metrics
11. Financial Projections — 3-year revenue, operating income, net income, EPS forecast with assumptions
12. Valuation Analysis — valuation models (P/E, P/B, DCF, EV/EBITDA) with conservative/base/optimistic targets, historical P/E trend, peer valuation comparison
13. Investment Recommendation — final verdict with rating, target price, bull/bear case summary

**Framework template:** `stock_initiation.json`

### Stock Update Report (Event/Earnings Note)

A shorter, focused report on a specific event, earnings release, rating change, or other catalyst. Modeled after professional investment bank research notes (Goldman Sachs, HSBC, Citi, Morgan Stanley style).

**When to use:** The user already has baseline knowledge of the company and wants analysis of a recent development — a quarterly earnings release, a guidance revision, a major contract win, a regulatory event, or any market-moving news.

**Default sections (7):**
1. Investment Thesis / Key Takeaway — one-paragraph thesis stating the event, its significance, and the investment implication (thesis-first writing style)
2. Event Analysis — what happened, why it matters, management commentary, and context relative to expectations
3. Financial Results Summary — key financial figures from the event (revenue, EPS, margins) vs. consensus estimates, with quarter-over-quarter and year-over-year comparisons
4. Estimate Revisions — updated forward estimates (revenue, EPS) for the next 2-3 fiscal years, showing old vs. new estimates and the direction of revisions
5. Valuation and Price Target — updated price target with methodology (forward P/E, DCF, or other), upside/downside from current price, comparison to prior target
6. Bull / Bear / Base Scenarios — three scenario framework with price targets and key assumptions for each
7. Risks — key risks specific to the investment thesis or the event being analyzed

**Framework template:** `stock_update.json`

### Sector Research Report

A report focused on an industry, sector, or thematic trend rather than a single company. Analyzes market sizing, key drivers, competitive landscape, value chain, and maps the thesis to specific investable stocks. Modeled after professional investment bank sector research (Morgan Stanley Foundation/Idea/Global Insight, KGI Industry Report style).

**When to use:** The user wants to understand a sector or industry theme — its growth trajectory, key drivers, competitive dynamics, and which stocks are the best expressions of the thesis. Suitable for analyzing emerging themes (robotics, space economy), established sectors (semiconductors, IT hardware), or cross-sector trends (memory supercycle impact on hardware OEMs).

**Default sections (8):**
1. Sector Thesis / Key Takeaway — the main investment thesis for the sector with 4-6 numbered takeaways
2. Industry Overview and Market Sizing — what the industry is, market size, growth trajectory, key data sources
3. Key Drivers and Trends — 3-5 forces shaping the sector (demand, technology, supply, regulatory)
4. Market Data and Analysis — quantitative industry data, pricing, supply/demand dynamics, historical comparisons
5. Competitive Landscape and Value Chain — key players, market share, supply chain mapping, picks-and-shovels plays
6. Company Analysis and Stock Implications — stock recommendations, rating changes, peer comparison table
7. Valuation — sector/peer valuation framework, target price methodology, historical range context
8. Risks — key risks to the sector thesis

**Framework template:** `sector_research.json`

### Mode Differences Summary

| Aspect | Stock Initiation Report | Stock Update Report | Sector Research Report |
|---|---|---|---|
| Purpose | Comprehensive company initiation | Event-driven or earnings update | Sector/industry analysis |
| Typical length | Long (13 sections, full financial tables) | Short (7 sections, focused analysis) | Medium-long (8 sections, data-heavy) |
| Subject | Single company | Single company + event | Industry, sector, or theme |
| Intended audience | User new to a company or wanting full review | User tracking a known company | User analyzing a sector or thematic trend |
| Trigger | User enters a ticker with no specific event | User enters a ticker with a specific event | User enters a sector, industry, or thematic topic |
| Framework | `stock_initiation.json` | `stock_update.json` | `sector_research.json` |

## Functions
1. **Report Generation**: EqR generates reports according to the selected report mode. In Stock Initiation mode, the report follows the full initiation framework. In Stock Update mode, it follows the event/earnings note framework. In Sector Research mode, it follows the sector analysis framework. The user selects the mode before generating.
2. **LLM Chatbot**: EqR operates as a LLM chatbot, handling follow-up questions from the user regarding the company, sector, or report. Follow-up conversations happen within the same chat session regardless of which report mode was used.
3. **Save Reports**: After reports are generated, there are options to save the report to the Repository or to download it as PDF or DOCX files.
4. **Report Preview**: When reports are generated, a thumbnail card appears in the chat showing the report type (Stock Initiation Report, Stock Update Report, or Sector Research Report). Opening the thumbnail opens a report preview for reading in greater detail.

## Page Settings
In the settings page for EqR, changeable settings are available as below:
1. Report Mode: A segmented control at the top of the settings modal to switch between Stock Initiation Report, Stock Update Report, and Sector Research Report. Changing the mode switches the displayed section list to the selected mode's defaults.
2. Report Sections: Each mode has its own set of default sections. The user can check or uncheck sections to include or exclude them from reports generated in that mode. Changes are saved per mode.
3. Custom Sections: A button that allows users to add custom sections to the currently selected mode. Opens a form to input a section name and a description of what the section should cover.
4. Length Adjuster: Allows user to choose the length of reports — Concise, Normal, or Elaborative. This setting applies to all report modes.

## User Interface Design

### Layout

EqR uses a full-height chat interface. There are two states: **Welcome** (no active conversation) and **Active** (conversation in progress).

**Welcome State:**

```
┌────────────────────────────────────────────────────────────────┐
│  Equity Research                           [⚙ Report Settings]  │
│────────────────────────────────────────────────────────────────│
│                                                                │
│                                                                │
│                      Equity Research                            │
│       Research companies, sectors, and market trends           │
│                                                                │
│   ┌───────────────────────────────────────────────────────┐   │
│   │  [AAPL]  [TSLA]  [NVDA]  [MSFT]  [From Portfolio ↗]  │   │
│   └───────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Enter a ticker, company, or sector (e.g., AAPL, Semis)  │ │
│  │                                                  [Send]  │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

**Active State:**

```
┌────────────────────────────────────────────────────────────────┐
│  Equity Research                           [⚙ Report Settings]  │
│────────────────────────────────────────────────────────────────│
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                                                          │ │
│  │       [Scrollable chat: messages + report cards]         │ │
│  │                                                          │ │
│  └──────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Ask a follow-up question...                     [Send]  │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

### Page Header

| Element | Detail |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` — does not scroll |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Equity Research" — `text-xl font-semibold text-[--color-text-primary]`, left-aligned, `pl-6` |
| Report Settings button | Right of header, `pr-6`; `Settings` icon (16px) + "Report Settings" label; `text-sm text-[--color-text-secondary]`; outline style: `border border-[--color-border-secondary] rounded-[--radius-md] px-3 h-8`; hover: `bg-[--color-surface-hover] text-[--color-text-primary]`; opens Report Settings modal |

---

### Welcome State

Shown when there is no active conversation. Centered vertically in the content area between the header and input.

| Element | Detail |
|---|---|
| Heading | "Equity Research" — `text-2xl font-semibold text-[--color-text-primary]`, horizontally centered |
| Sub-text | "Research companies, sectors, and market trends" — `text-md text-[--color-text-secondary]`, centered, `mt-2` |
| Suggestion chips | 5 chips: "AAPL", "TSLA", "NVDA", "MSFT", and "From Portfolio ↗". The first four immediately populate the input and submit. "From Portfolio" opens a compact picker showing the user's tracked tickers |
| Chip style | `px-3.5 py-2 rounded-full border border-[--color-border-secondary] text-sm text-[--color-text-secondary]`; hover: `bg-[--color-surface-hover] text-[--color-text-primary]`; transition `--duration-fast` |
| "From Portfolio" chip | Same style, with `ArrowUpRight` icon (12px) inline; opens a popover listing Portfolio tickers in a scrollable list, each row clickable to populate the input |
| Entry animation | Heading + sub-text: `opacity 0→1, y 12→0, duration 250ms`; chips stagger in `40ms` apart |

---

### Chat Message Area

Replaces the welcome content once a conversation starts. Scrolls independently.

| Element | Detail |
|---|---|
| Container | `flex-1 overflow-y-auto px-6 py-6` |
| Content max-width | `max-w-[680px] mx-auto` |
| User messages | Right-aligned bubble: `rounded-2xl rounded-br-sm px-4 py-2.5 bg-[--color-surface-active] text-[--color-text-primary] text-md`; `max-w-[72%]` |
| Assistant messages | Left-aligned, no bubble: `text-md text-[--color-text-primary] leading-relaxed`; full-width up to chat max-width; markdown rendered (bold, bullets, tables, inline code, code blocks) |
| Timestamps | Hidden by default; fade in on hover: `text-xs text-[--color-text-tertiary]`, `--duration-fast` |
| Streaming | Token-by-token reveal with blinking cursor `▌` at the insertion point |
| Loading indicator | Animated three-dot pulse while awaiting first token: three `w-1.5 h-1.5 rounded-full bg-[--color-text-tertiary]` dots, opacity cycling `0.3→1→0.3` over 1.2s, staggered `200ms` apart |
| Message entry | `opacity 0→1, y 8→0, duration 200ms, ease-out` |

---

### Report Thumbnail Card

When EqR completes a report, a structured card appears within the assistant's response area. The card title reflects which report mode was used.

**Stock Initiation Report card:**
```
┌──────────────────────────────────────────────────────────────┐
│ [FileText]  Stock Initiation Report                          │
│             AAPL  ·  Apple Inc.  ·  Apr 9, 2026              │
│──────────────────────────────────────────────────────────────│
│ Apple Inc. is a global technology leader headquartered in     │
│ Cupertino, CA. The company designs and sells consumer        │
│ electronics, software, and digital services...               │
│                                          [read more →]       │
│──────────────────────────────────────────────────────────────│
│ [Open Report]          [Download ▾]    [Save to Repo]        │
└──────────────────────────────────────────────────────────────┘
```

**Stock Update Report card:**
```
┌──────────────────────────────────────────────────────────────┐
│ [FileText]  Stock Update Report                              │
│             AAPL  ·  Apple Inc.  ·  Apr 9, 2026              │
│──────────────────────────────────────────────────────────────│
│ Apple Inc. reported a strong Q1 2026, with revenue of        │
│ $124.3B exceeding consensus estimates by 3.2%. iPhone        │
│ sales drove outperformance, particularly in emerging...      │
│                                          [read more →]       │
│──────────────────────────────────────────────────────────────│
│ [Open Report]          [Download ▾]    [Save to Repo]        │
└──────────────────────────────────────────────────────────────┘
```

**Sector Research Report card:**
```
┌──────────────────────────────────────────────────────────────┐
│ [FileText]  Sector Research Report                           │
│             Semiconductors  ·  Apr 9, 2026                   │
│──────────────────────────────────────────────────────────────│
│ Memory is increasingly the primary constraint on AI demand.  │
│ We model Global OEM/ODM gross margins down a median 60bps   │
│ Y/Y in 2026 vs. Street up ~10bps. Downgrading DELL, HPQ...  │
│                                          [read more →]       │
│──────────────────────────────────────────────────────────────│
│ [Open Report]          [Download ▾]    [Save to Repo]        │
└──────────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Card container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden shadow-sm`; `max-w-[560px]` |
| Header row | `px-4 py-3 flex items-start gap-3`; `FileText` icon (16px, `--color-text-tertiary`); two-line label — report type title ("Stock Initiation Report", "Stock Update Report", or "Sector Research Report") (`text-base font-medium text-[--color-text-primary]`); ticker/sector + company/industry name + date (`text-sm text-[--color-text-secondary]`) |
| Preview text | `px-4 py-3 text-sm text-[--color-text-secondary] leading-relaxed`; `line-clamp-3`; "read more →" text link at end; clicking expands to full preview inline |
| Action row | `px-4 py-2.5 flex items-center gap-2 bg-[--color-bg-base] border-t border-[--color-border-subtle]` |
| Open Report | `px-3 h-7 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm hover:bg-[--color-accent-hover]`; opens FileViewer |
| Download | Outline button with `▾` chevron; dropdown: "Download as PDF" / "Download as DOCX" |
| Save to Repo | Text-icon button; `Bookmark` icon toggles filled/outline; on save: brief scale pulse on icon |
| Card entry animation | `opacity 0→1, y 12→0, duration 250ms, ease-out` |

---

### Message Input

Always visible, pinned to the bottom of the page.

| Element | Detail |
|---|---|
| Container | `flex-shrink-0 px-6 py-4 border-t border-[--color-border-subtle] bg-[--color-bg-base]` |
| Inner wrapper | `max-w-[680px] mx-auto` |
| Input field | Multi-line `<textarea>`; grows from 1 to 4 lines (~120px max) before scrolling; `bg-[--color-bg-input] rounded-xl border border-[--color-border-subtle] px-4 py-3`; on focus: border → `--color-border-secondary`; transition `--duration-fast` |
| Placeholder — welcome | "Enter a ticker, company, or sector (e.g., AAPL, Semiconductors)..." |
| Placeholder — active | "Ask a follow-up question about the company, sector, or report..." |
| Send button | `w-8 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white`; `ArrowUp` icon (14px); disabled when empty: `opacity-40 cursor-not-allowed` |
| Stop button | Replaces send while streaming; `bg-[--color-surface-active] text-[--color-text-secondary]`; `Square` icon (14px) |
| Keyboard | Enter = submit; Shift+Enter = newline |
| Helper text | `mt-2 text-xs text-[--color-text-tertiary] text-center` — "Press Enter to send · Shift+Enter for new line" |

---

### Report Settings Modal

Opened via the "Report Settings" button in the page header.

```
┌──────────────────────────────────────────────────────────┐
│  Report Settings                                   [✕]   │
│──────────────────────────────────────────────────────────│
│  Report Mode                                             │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Stock Initiation ● │ Stock Update │ Sector Research │ │
│  └─────────────────────────────────────────────────────┘ │
│──────────────────────────────────────────────────────────│
│  Report Length                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │   Concise   │   Normal ●   │   Elaborative          │ │
│  └─────────────────────────────────────────────────────┘ │
│──────────────────────────────────────────────────────────│
│  SECTIONS  (Stock Initiation Report)                     │
│  ☑  Company Overview                                     │
│  ☑  Industry Overview                                    │
│  ☑  Products and Services                                │
│  ☑  Business Model                                       │
│  ☑  Competitive Analysis                                 │
│  ☑  Management Team                                      │
│  ☑  Competitive Advantages and Weaknesses                │
│  ☑  Risk Analysis                                        │
│  ☑  Historical Financial Data                            │
│  ☑  Financial Analysis                                   │
│  ☑  Financial Projections                                │
│  ☑  Valuation Analysis                                   │
│  ☑  Investment Recommendation                            │
│──────────────────────────────────────────────────────────│
│  CUSTOM SECTIONS                             [+ Add]     │
│──────────────────────────────────────────────────────────│
│                          [Cancel]  [Save Settings]       │
└──────────────────────────────────────────────────────────┘
```

When "Stock Update" is selected, the sections list changes to:

```
│  SECTIONS  (Stock Update Report)                         │
│  ☑  Investment Thesis / Key Takeaway                     │
│  ☑  Event Analysis                                       │
│  ☑  Financial Results Summary                            │
│  ☑  Estimate Revisions                                   │
│  ☑  Valuation and Price Target                           │
│  ☑  Bull / Bear / Base Scenarios                         │
│  ☑  Risks                                                │
```

When "Sector Research" is selected, the sections list changes to:

```
│  SECTIONS  (Sector Research Report)                      │
│  ☑  Sector Thesis / Key Takeaway                         │
│  ☑  Industry Overview and Market Sizing                  │
│  ☑  Key Drivers and Trends                               │
│  ☑  Market Data and Analysis                             │
│  ☑  Competitive Landscape and Value Chain                │
│  ☑  Company Analysis and Stock Implications              │
│  ☑  Valuation                                            │
│  ☑  Risks                                                │
```

| Element | Detail |
|---|---|
| Backdrop | `bg-black/40`, full-viewport, click-to-dismiss |
| Modal container | `bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle] w-full max-w-[480px]`; fixed centered |
| Report Mode toggle | 3-option segmented control at top: "Stock Initiation" / "Stock Update" / "Sector Research"; active: `bg-[--color-surface-active] font-medium`; switching modes changes the section list below; selection persists across modal open/close |
| Report Length | 3-option segmented control: Concise / Normal / Elaborative; active: `bg-[--color-surface-active] font-medium`; contained in a bordered pill group; applies to both modes |
| Section rows | Checkbox left + section name `text-base text-[--color-text-primary]`; `py-2.5 px-6 border-b border-[--color-border-subtle]`; checked checkbox fills `--color-accent-primary`; section list is mode-specific — each mode maintains its own checked/unchecked state |
| Section label | "SECTIONS" header includes the current mode name in parentheses, e.g., "SECTIONS (Equity Research Report)" |
| Custom sections | "+ Add" opens a new row with name input (required) + description textarea (optional) + `✕` remove; custom sections are per-mode; existing custom sections are editable inline |
| Footer buttons | Cancel (outline) + Save Settings (accent filled); `h-9 px-4 rounded-[--radius-md]` |
| Entry animation | `opacity 0→1, scale 0.97→1, duration 200ms, ease-out` |

---

### States

| State | Visual Treatment |
|---|---|
| **Welcome** | Centered heading + chips; no chat history |
| **Generating** | Typing indicator; send → stop; textarea dimmed |
| **Streaming** | Token-by-token reveal; blinking cursor; stop button active |
| **Idle** | Input fully enabled; chat scrollable |
| **Response Stopped** | Partial response retained; italicized muted "Response stopped." appended |
| **Error** | Inline error below last message with "Try again" `RotateCcw` button |

---

### Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Centered chat at `max-w-[680px]`; full layout |
| Tablet (768–1024px) | Chat fills available width; same component structure |
| Mobile (<768px) | Reduced horizontal padding `px-4`; modal becomes full-width bottom sheet |

## Report Frameworks

EqR uses three JSON framework templates, one per report mode. Each framework defines the section structure, ordering, and LLM instructions for generating that report type.

| Report Mode | Framework File | Sections |
|---|---|---|
| Stock Initiation Report | `stock_initiation.json` | 13 sections (full initiation) |
| Stock Update Report | `stock_update.json` | 7 sections (event/earnings note) |
| Sector Research Report | `sector_research.json` | 8 sections (sector/industry analysis) |

Framework files ship with the core package at `packages/core/src/openlia/reports/frameworks/`. See the Report Rendering Pipeline spec for how frameworks are filled by the LLM and rendered into the final report.

## Data Requirements

EqR is a tool-calling department. The LLM receives mapped tools and the runtime expansion meta-tool, deciding which tools to call based on the user's prompt and selected report mode.

**Basic (department disabled without these):**

| Requirement | Type | Description |
|---|---|---|
| Stock quote | `stock_quote` | Real-time or delayed stock price, volume, daily change for valuation and price context |
| Company profile | `company_profile` | Company name, sector, industry, description, key facts for Company Overview sections |
| Financial statements | `financial_statements` | Income statement, balance sheet, cash flow statement for financial analysis, projections, and valuation |

**Advanced (features degrade gracefully if missing):**

| Requirement | Type | Description | Without It |
|---|---|---|---|
| Company news | `company_news` | Recent news articles for event analysis and sector trends | Reports lack current news context; Stock Update event analysis is weaker |
| Historical prices | `historical_prices` | Historical daily OHLCV data for trend analysis and chart context | No historical price charts or MA-based valuation context |
| Analyst ratings | `analyst_ratings` | Consensus estimates, recommendations, and price targets | Estimate Revisions and Valuation sections lack consensus comparison |
| Insider transactions | `insider_transactions` | Insider buying and selling activity | Management Team section lacks insider activity data |
| Earnings data | `earnings_data` | Earnings dates, EPS history, and earnings surprises | Financial analysis lacks earnings trend data and beat/miss history |

## Configurations
- LLM Model: