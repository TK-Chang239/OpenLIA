# Macro Research Department Spec

> **SUPERSEDED (data architecture) — 2026-08-16.** The *data* behind these dashboards was rebuilt. The authoritative design is now:
> - **`planning/specs/systems/macro-research-llm-dashboard-redesign.md`** (the shipped engine: a single-model LLM tool-use loop with the model's *native* web search as the macro backbone; no required connector; supersedes the old need-id / tiered-assembler data architecture).
>
> The page **layout/visual** design below still holds; only how the data is produced changed. **Shipped state (verified in `frontend/src/pages/departments/MacroResearch.tsx`):** the dashboards are **live** — a **Summary** tab plus five framework tabs (T1 Debt Cycle, T2 Four Seasons, T3 All-Weather, T4 World Order, T5 Five Forces), each polling `getDashboard(slug)` with an auto-refresh cadence control and a Settings panel. (Known cosmetic gaps flagged in the 2026-08-16 audit Stage 5.C: the header's date and "42 streaming series" count are still hardcoded, and `IMPLEMENTED_DASHBOARDS` is hardcoded.)

## Page Overview

The Macro Research Department (MR) provides five framework-driven dashboards based on Ray Dalio's macro investing methodology. Each dashboard maps 1:1 to a Dalio framework: Debt Cycle, Four Economic Seasons, All-Weather Portfolio Audit, Long-Term World Order, and Five Interlocking Forces. Dashboards update periodically with live market data, formula engine evaluations, and LLM assessments.

MR is a dashboard department -- there is no chat interface.

Full design spec: `planning/specs/systems/macro-research-dalio-dashboards-design.md`

## Functions

1. **Five Framework Dashboards**: Each of the five Dalio frameworks has its own dashboard tab with indicators, visualizations, and assessments. T1 (Debt Cycle) and T2 (Four Seasons) use a formula engine for threshold-based evaluation. T3 (All-Weather) uses computational risk math. T4 (World Order) and T5 (Five Forces) use LLM assessment.
2. **Summary Tab**: A default landing tab that provides a composite assessment across all five frameworks with mini visualizations and a cross-framework synthesis narrative.
3. **Auto-Refresh**: Market data and economic indicators refresh on a configurable interval. LLM assessments (T4/T5) run on a user-configurable schedule (quarterly or weekly), plus a manual "Run assessment now" button for ad-hoc runs. Automatic news-triggered runs are deferred to v2 (see `macro-research-dalio-dashboards-design.md` § Per-Dashboard Settings T4/T5).
4. **Smart Mode**: When enabled, the LLM periodically reviews and adjusts thresholds across all dashboards based on evolving macro conditions. Each adjustment is logged with rationale.
5. **Cross-Dashboard Dependencies**: T5 synthesizes T1+T2+T4 outputs. T3 consumes T1+T2+T5 outputs. Execution order for a full run: T1 -> T2 -> T4 -> T5 -> T3.
6. **Portfolio Integration**: T3 reads the user's actual portfolio from the Portfolio page for the All-Weather audit. Falls back to 60/40 benchmark if no portfolio is configured.

---

## User Interface Design

### Layout

MR uses a tabbed single-page dashboard. Six tabs: **Summary** (default landing) | Debt Cycle | Four Seasons | All-Weather | World Order | Five Forces.

```
+----------------------------------------------------------------+
|  Macro Research                  [Auto-refresh v]  [Settings]   |
|----------------------------------------------------------------|
|  [Summary *] [Debt Cycle] [Four Seasons] [All-Weather]         |
|              [World Order] [Five Forces]                        |
|----------------------------------------------------------------|
|                                                                 |
|                    (active tab content)                          |
|                                                                 |
+----------------------------------------------------------------+
```

---

### Page Header

| Element | Detail |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Macro Research" -- `text-xl font-semibold text-[--color-text-primary]`, left-aligned, `pl-6` |
| Auto-refresh dropdown | Right of header; options: Off / 5 min / 15 min; `text-sm text-[--color-text-secondary]`; controls market data refresh interval for T1/T2 formula engine dashboards |
| Settings button | Right of header, `pr-6`; `Settings` icon (16px) + "Settings" label; outline style matching other departments; opens Settings panel |

---

### Tab Bar

| Element | Detail |
|---|---|
| Container | `flex items-center gap-1 px-6 bg-[--color-bg-base] border-b border-[--color-border-subtle]` |
| Tab | `px-4 py-2.5 text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:text-[--color-text-primary]`; active: `text-[--color-text-primary] font-medium border-b-2 border-[--color-text-primary]` |
| Default active tab | Summary |

---

### Summary Tab

The default landing view. Composite assessment banner at top, five clickable framework cards in a 2-column grid (T5 full-width at bottom), cross-framework synthesis callout at the bottom. Clicking any card navigates to that framework's tab.

See design spec Section "Summary Tab" for full detail on the composite banner, framework cards with mini visualizations, and synthesis block.

---

### T1 -- Debt Cycle Tab

Formula engine dashboard. Four indicators (Debt/GDP, Interest/Revenue, TIPS Yield, DXY) with user-configurable thresholds. Sections: headline scorecard, phase assessment with historical analogs, monetary policy space, asset implications (gold thesis + bond risk), watchlist triggers, synthesis verdict.

See design spec Section "T1 -- Debt Cycle Dashboard" for full detail.

---

### T2 -- Four Seasons Tab

Formula engine dashboard. Four indicators (PMI, Real GDP, CPI, Credit Spreads) mapped to a 2x2 growth/inflation matrix. Sections: quadrant inputs table with directional arrows, quadrant map with position markers, transition risk (bull/bear case), asset playbook with season-to-asset mapping, synthesis verdict.

See design spec Section "T2 -- Four Seasons Dashboard" for full detail.

---

### T3 -- All-Weather Tab

Computational dashboard. Reads portfolio from the Portfolio page (or 60/40 fallback). Sections: portfolio comparison doughnut charts, season coverage map (cross-references T2), risk parity audit bar charts, gold allocation gradient bar (cross-references T1/T2/T5), retail investor caveats, synthesis verdict.

See design spec Section "T3 -- All-Weather Portfolio Audit" for full detail.

---

### T4 -- World Order Tab

LLM assessment dashboard. Sections: reserve currency health scorecard, reserve currency composition chart (multi-line, 1999-present), empire cycle stage timeline strip, Dalio quote callout, Stage 5 markers checklist, historical analog grid (similar + different), wealth shift signals, currency and bond risk implications, synthesis verdict.

See design spec Section "T4 -- World Order Assessment" for full detail.

---

### T5 -- Five Forces Tab

LLM assessment dashboard. Synthesis template consuming T1+T2+T4. Sections: force scorecard with intensity bars (1-10 scale), active force count banner, reinforcement loop analysis (feedback loops between forces), market data reference, gold allocation signal with gradient bar, scenario analysis (bull/bear), synthesis verdict.

See design spec Section "T5 -- Five Interlocking Forces Dashboard" for full detail.

---

### Settings Panel

Collapsible drawer or modal. Contains:

**Global Settings:**
- Auto-refresh interval (market data): Off / 5 min / 15 min
- T4/T5 LLM assessment schedule: Quarterly / Weekly
- Smart Mode toggle: Off (default) / On -- when enabled, LLM adjusts thresholds periodically

**Per-Dashboard Settings (T1, T2):** Data source selector, params table (threshold editor with AI badge when Smart Mode active), rule editor, preset loader (Dalio defaults / Conservative / Relaxed).

**Per-Dashboard Settings (T3):** Portfolio source, volatility estimates, coverage thresholds.

**Per-Dashboard Settings (T4, T5):** LLM model, manual "Run assessment now" button, scoring anchors. (News-trigger keywords and sensitivity controls are deferred to v2 -- see `macro-research-dalio-dashboards-design.md`.)

> **Implementation note (Phase 19, NEW-19-12):** the assessment schedule
> is stored as a single user-level recurring cron persisted on the
> canonical `world_order` `mr_dashboard_state` row (see
> `services/mr_schedules.py:CANONICAL_DASHBOARD`). One scheduled run
> assesses every T4/T5-bearing dashboard for the user. Per-dashboard
> schedules are deferred — the manual "Run assessment now" button on
> each T4/T5 tab covers the per-dashboard ad-hoc case.

See design spec Section "Settings Panel" for full detail.

---

### States

| State | Visual Treatment |
|---|---|
| **Loading (initial)** | Skeleton placeholders for each section; spinner on tab bar |
| **Loading (refresh)** | Subtle loading indicator per dashboard; existing data remains visible |
| **Data available** | Full dashboard rendered |
| **LLM running (T4/T5)** | Pulsing indicator on dashboard header; "Assessment in progress..." label; previous assessment remains visible |
| **LLM complete** | New assessment replaces previous; timestamp updates |
| **No portfolio (T3)** | Fallback to 60/40 benchmark; amber banner: "Set up your Portfolio for personalized analysis" with link to Portfolio page |
| **Error** | Inline error row below affected section: `text-sm text-[--color-feedback-error]` + retry link |
| **Stale data** | Amber timestamp label: "Data is N hours old" when auto-refresh is off and data exceeds staleness threshold |

---

### Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Full layout; 2-column grids, all charts at full size |
| Tablet (768-1024px) | Single column; all grids collapse to stacked |
| Mobile (<768px) | Single column; horizontal padding reduced to `px-4`; charts reduce height; tab bar scrolls horizontally |

---

## Page Settings

All configuration is accessed via the Settings panel in the page header. There is no Report Settings modal -- MR does not generate reports.

## Report Framework

Not applicable. MR is a dashboard department and does not generate text reports. Evaluation is handled by the formula engine (T1/T2), computational risk math (T3), and LLM assessment (T4/T5).

## Configurations

- Formula engine: Shared with Panic Thermometer (safe expression evaluator DSL)
- LLM for T4/T5 assessments: User-configurable in Settings
- Data sources: EODHD (market data, economic events, macro indicators, news)

---

## Data Requirements

MR is a pre-fetch dashboard department. T1/T2 use formula engine evaluation, T3 uses computational risk math, T4/T5 use LLM assessment.

**Basic (department disabled without these):**

| Requirement | Type | Description |
|---|---|---|
| Macro indicators | `macro_indicators` | Debt/GDP, interest rates, CPI, PMI, GDP, credit spreads for T1 (Debt Cycle) and T2 (Four Seasons) |
| Economic events | `economic_events` | Economic calendar events for T1/T2 formula engine inputs |
| Historical prices | `historical_prices` | Price history for DXY proxy, gold, bonds, equities used across T1-T5 dashboards |

**Advanced (features degrade gracefully if missing):**

| Requirement | Type | Description | Without It |
|---|---|---|---|
| Company news | `company_news` | News articles for T4 (World Order) and T5 (Five Forces) LLM context | T4 and T5 assessments lack current events context; assessments rely solely on market data |
| Stock quote | `stock_quote` | Real-time prices for dashboard auto-refresh | Dashboard shows last-close prices only; no intraday refresh |

---

## Non-Goals (v1)

- Chat interface or conversational interaction
- Report generation, PDF/DOCX export
- Real-time streaming updates (SSE) -- polling is sufficient
- User-editable LLM prompts for T4/T5
- Historical playback (viewing past dashboard states)
- Alerting/notifications when dashboard status changes
- Multi-country support (US-focused in v1)

## Open Questions

- EODHD macro indicator availability for Debt/GDP and Interest/Revenue -- may need to compute from economic events or hardcode with manual update.
- DXY proxy -- EODHD may not carry DXY directly; UUP (ETF) is a proxy.
- IMF COFER data for T4 reserve composition chart -- quarterly with lag, hardcoded snapshots.
- T4/T5 LLM cost per run -- settings should show estimated cost based on configured model.
- Formula engine extraction into shared module with Panic Thermometer.
