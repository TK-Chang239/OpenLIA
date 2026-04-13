# Macro Research Department -- Dalio Framework Dashboards

Redesign of the Macro Research department from a chat-based report generator into five framework-driven dashboards based on Ray Dalio's macro methodology. Each dashboard maps 1:1 to a Dalio framework. Dashboards update periodically with live data and LLM assessments.

Source article: "Ray Dalio's Methodology: An Investing Framework Distilled From 500 Years of History" (TradingKey, Apr 2026). Reference mockups in `MacroResearcherHTML/`.


## Department Identity

- **Name:** Macro Research (MR)
- **Type:** Dashboard department (no chat interface)
- **Data access pattern:** Pre-fetch (code fetches data, then formula engine or LLM evaluates)
- **Sidebar entry:** "Macro Research" with the same icon and position as the current MR entry


## Five Frameworks, Five Dashboards

| ID | Framework | Evaluation Method | Refresh Cadence |
|----|-----------|-------------------|-----------------|
| T1 | Debt Cycle | Formula engine (shared with Panic Thermometer) | Auto-refresh on data; re-evaluate on economic releases |
| T2 | Four Economic Seasons | Formula engine | Auto-refresh on data; re-evaluate on ISM/BLS/BEA releases |
| T3 | All-Weather Portfolio Audit | Computational (risk math) | Recomputes when upstream dashboards or Portfolio data changes |
| T4 | Long-Term World Order | LLM assessment | User-configurable: quarterly, weekly, or on significant news trigger |
| T5 | Five Interlocking Forces | LLM assessment (synthesis of T1+T2+T4) | User-configurable: quarterly, weekly, or on significant news trigger |


## Cross-Dashboard Dependencies

```
T1 (Debt Cycle)  ──────────────────────────┐
                                             v
T4 (World Order) ──────────────────────────> T5 (Five Forces) ──> T3 (All-Weather Audit)
                                             ^
T2 (Four Seasons) ─────────────────────────┘
                         |
                         └──────────────────> T3 (season context for bond caveat)
```

No dashboard can be faithfully run without its upstream dependencies. T5 requires T1, T2, and T4 outputs. T3 requires T1, T2, and T5 outputs.

Execution order for a full run: T1 -> T2 -> T4 -> T5 -> T3.

For data-only refresh (no LLM re-run): T1/T2 re-evaluate via formula engine, T3 recomputes from cached upstream outputs. T4/T5 retain their cached LLM assessments until the next scheduled or triggered LLM run.


## Page-Level Structure

### Layout

The MR page is a tabbed single-page dashboard. Six tabs: **Summary** (default landing) | Debt Cycle | Four Seasons | All-Weather | World Order | Five Forces.

```
┌────────────────────────────────────────────────────────────────┐
│  Macro Research                  [Auto-refresh ▼]  [Settings]  │
│────────────────────────────────────────────────────────────────│
│  [Summary *] [Debt Cycle] [Four Seasons] [All-Weather]         │
│              [World Order] [Five Forces]                       │
│────────────────────────────────────────────────────────────────│
│                                                                │
│                    (active tab content)                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Page Header

| Element | Detail |
|---------|--------|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Macro Research" -- `text-xl font-semibold text-[--color-text-primary]`, left-aligned, `pl-6` |
| Auto-refresh dropdown | Right of header; options: Off / 5 min / 15 min; `text-sm text-[--color-text-secondary]`; controls market data refresh interval for T1/T2 formula engine dashboards |
| Settings button | Right of header, `pr-6`; `Settings` icon (16px) + "Settings" label; outline style matching other departments; opens Settings panel |

### Tab Bar

| Element | Detail |
|---------|--------|
| Container | `flex items-center gap-1 px-6 bg-[--color-bg-base] border-b border-[--color-border-subtle]` |
| Tab | `px-4 py-2.5 text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:text-[--color-text-primary]`; active: `text-[--color-text-primary] font-medium border-b-2 border-[--color-text-primary]` |
| Default active tab | Summary |


## Summary Tab

The default landing view. Provides a high-level overview of all five frameworks without switching tabs. Clicking any framework card navigates to that framework's tab.

### Composite Assessment Banner

A single card at the top synthesizing all five frameworks.

| Element | Detail |
|---------|--------|
| Container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4` |
| Label | "Composite Macro Assessment" -- `text-xs font-medium uppercase tracking-wide text-[--color-text-tertiary]` |
| Verdict | Large text (22px) colored by severity (green/amber/red). Derived from worst-case across all five frameworks: if any framework is red, composite is red; else if any is amber, composite is amber; else green. |
| Description | 1-2 sentence summary of the combined framework read -- `text-sm text-[--color-text-secondary]` |
| Severity indicator | Five colored bars (one per framework), each 24x8px rounded. Color matches that framework's current status. Count label below: "X critical -- Y elevated" |
| Timestamp | "Updated N min ago" -- `text-xs text-[--color-text-tertiary]`, right-aligned |

### Framework Cards

Five clickable cards in a 2-column grid (T5 full-width at the bottom since it is the synthesis dashboard). Each card:

| Element | Detail |
|---------|--------|
| Container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4 cursor-pointer hover:shadow-sm` |
| Header row | Framework name (`text-sm font-medium`) + status badge (right-aligned) |
| Compact visualization | Framework-specific mini visualization (see below) |
| Summary line | `text-xs text-[--color-text-tertiary] mt-2` |
| LLM timestamp | For T4/T5: "LLM assessed -- last run: [date]" -- `text-xs text-[--color-text-tertiary]` |

Compact visualizations per card:
- **T1:** Mini scorecard -- three rows showing indicator name + current value (colored by status)
- **T2:** Mini 2x2 quadrant grid with active season highlighted
- **T3:** Risk contribution bars (equities/bonds/gold) showing percentage
- **T4:** Stage timeline strip (six boxes, active stage in red)
- **T5:** Force intensity bars (five rows with score/10)

### Cross-Framework Synthesis

Amber callout block at the bottom of the Summary tab. Generated by the T5 LLM assessment. Ties together findings from all five frameworks into a single narrative paragraph. Updates whenever T5 runs.


## T1 -- Debt Cycle Dashboard

### Evaluation Method

Formula engine (shared with Panic Thermometer). Four indicators with user-configurable thresholds evaluated against live data. Phase assessment, asset implications, and synthesis are LLM-generated narrative sections that refresh when indicators change materially.

### Indicators

| Indicator | Default Source | Default Warning Zone | What It Tests |
|-----------|---------------|---------------------|---------------|
| Government Debt / GDP | EODHD macro indicators or economic events | Above 100% | Structural fiscal constraint |
| Interest Expense / Revenue | EODHD economic events (fiscal data) | Above 15% | Active fiscal pressure |
| Real Interest Rate (10Y TIPS yield) | EODHD historical prices (TIP ETF) or macro indicator | Near zero or negative | Gold demand trigger |
| US Dollar Index (DXY) | EODHD historical prices (DXY proxy ETF) or macro indicator | Sustained decline below 100 | Currency confidence / debasement signal |

### Sections

**Section A -- Headline Scorecard**

Four-column table: indicator name + spark bar / current value / Dalio warning zone description / status badge. Column widths: `2fr / 1fr / 1.2fr / 90px`. Each row evaluates its formula engine rule set against live data.

The spark bar (5px height track) is a secondary encoding of the same red/amber/green signal carried by the badge. Fill color matches status. Width represents proximity to threshold (visual approximation, not computed).

Status levels: green (healthy), amber (elevated), red (critical). Evaluated by the formula engine against user-configurable thresholds.

**Section B -- Phase Assessment**

Derived from the scorecard results. Phase classification: Expansion / Plateau / Late Plateau / Deleveraging. Computed deterministically from indicator statuses.

Three sub-components:

1. *Phase narrative* -- Left-bordered callout block (amber 3px left border, no border-radius). Describes the current phase and its implications. LLM-generated.

2. *Historical analog* -- Two-column layout. Each analog has "Similar:" and "Different:" sections. The "Different" content is mandatory -- forces the system to document where the current situation departs from the historical pattern. LLM-generated.

3. *Time-to-constraint estimate* -- Specific timeline with bounding conditions. LLM-generated.

**Section C -- Monetary Policy Space**

Three metric cards in a `g3` grid: rate cut headroom (neutral color), QE credibility (amber), currency debasement risk (red). Each card has a small label (11px), large value (18px), unit description, and 2-3 sentence note. Computed from indicator data.

**Section D -- Asset Implications**

Two-card `g2` grid:

1. *Gold / real assets thesis* -- Narrative explaining why the debt cycle reading supports or undermines gold allocation. References TIPS yield direction, interest/revenue trajectory, monetization probability, and Dalio's guidance.
2. *Long-duration bond risk* -- Narrative explaining the structural setup for long bonds. References issuance supply, foreign demand trends, QE credibility, and regime-specific duration risk.

LLM-generated. Updates when the phase assessment or indicators change materially.

**Section E -- Watchlist Triggers**

List of conditions that would change the phase classification. Each trigger row: colored dot (6px, red/amber/green) + fixed-width name column (min-width 160px) + free-flow description. Same shift-row component used across T1, T4, and T5.

**Section F -- Synthesis Verdict**

Amber callout block. Explicitly labeled with downstream consumption notes: "Bottom line for T5 and T3 consumption." States what the output feeds into (T5 Force 1 score, T3 gold allocation check).

### Data Refresh

| Data Type | Refresh Trigger | Source |
|-----------|----------------|--------|
| TIPS yield (live) | Auto-refresh interval (default 5 min) | `get_live_price_data` or `get_historical_stock_prices` |
| DXY (live) | Auto-refresh interval | `get_live_price_data` or `get_historical_stock_prices` |
| Debt/GDP | On economic event release (quarterly) | `get_economic_events` or `get_macro_indicator` |
| Interest/Revenue | On economic event release (fiscal data) | `get_economic_events` |
| LLM sections (phase, asset implications, synthesis) | When indicator statuses change | LLM call with current data context |


## T2 -- Four Seasons Dashboard

### Evaluation Method

Formula engine. Four indicators mapped to a 2x2 growth/inflation matrix. Season classification and transition risk are LLM-generated narrative sections.

### Indicators

| Indicator | Default Source | Axis | What It Tests |
|-----------|---------------|------|---------------|
| Manufacturing PMI | EODHD economic events (ISM) | Growth | Expansion vs contraction trend |
| Real GDP (annualized) | EODHD economic events (BEA) | Growth | Growth momentum and direction |
| CPI (YoY + MoM) | EODHD economic events (BLS) | Inflation | Inflation heating or cooling |
| Credit Spreads (IG/HY) | EODHD historical prices (HYG/LQD ETFs) | Corroborating | Credit stress confirmation |

### Season Classification Logic

1. Growth axis: GDP trend is primary signal, PMI trend is secondary. If both agree, axis is clear. If they conflict, GDP direction wins and confidence is "mixed."
2. Inflation axis: Headline CPI YoY is primary, Core CPI YoY is secondary. If headline is driven by a transitory component (e.g. energy shock), weight core more heavily for the forward-looking projection.
3. Combine into quadrant: Spring (rising growth / falling inflation), Summer (rising / rising), Autumn (falling / rising), Winter (falling / falling).
4. If either axis is ambiguous, label as "transitioning" between two seasons and name both.
5. Credit spreads corroborate: tight spreads moderate a growth-falling signal; widening spreads confirm it.
6. Assign confidence: clear (both axes unambiguous), mixed (one axis ambiguous), transitioning (one axis in the process of flipping).

### Season-to-Asset Mapping

| Season | Growth | Inflation | Best Performing | Worst Performing |
|--------|--------|-----------|-----------------|------------------|
| Spring | Rising | Falling | Equities | Commodities |
| Summer | Rising | Rising | Commodities, inflation-linked bonds | Long-duration nominal government bonds |
| Autumn | Falling | Rising (stagflation) | Gold, real assets | Equities, long-duration government bonds |
| Winter | Falling | Falling | Long-duration bonds, cash | Commodities |

### Sections

**Section A -- Quadrant Inputs Table**

Five-column grid: indicator name + spark bar / current value / 3-month trend description / axis signal badge / directional arrow. Column widths: `1.8fr / 1fr / 0.9fr / 0.9fr / 100px`. Directional arrows are CSS triangles (no emoji): up arrow (green), down arrow (red), flat (amber rectangle).

**Section B -- Quadrant Map**

Fixed aspect-ratio (1.6:1) container divided into four quadrants by separator lines. Axis labels at edges (Rising/Slowing Growth horizontal, Rising/Slowing Inflation vertical). Each quadrant holds: season name, two-line description, colored asset pill.

Two position markers: current assessment (red dot) and previous assessment (amber dot), positioned with absolute percentages to show directional movement. Manually positioned to reflect the diagnostic verdict (not computed from raw indicator values -- Dalio's framework does not support that precision).

**Section C -- Transition Risk**

Two-panel `g2` layout: bull case (left) and bear case (right). No colored backgrounds -- both scenarios presented as equally worth understanding. A "key indicator to watch" block at the bottom names the specific data point (a PMI level, a GDP print, a named release date) that would change the season classification. This is the falsifying condition.

**Section D -- Asset Playbook**

Four colored cells in a `g4` grid, one per season. Colors match the quadrant map: amber (commodities/summer), red (gold/autumn), green (equities/spring), blue (long bonds/winter). Each cell: uppercase asset label, 12px title describing regime alignment, 11px body explaining the mechanism.

Gray-background stress test block at the bottom. Describes what happens to the user's portfolio (from Portfolio page) if the season transition completes. LLM-generated.

**Section E -- Synthesis Verdict**

Amber callout. Downstream consumption: T3 coverage map, T5 Force assessment, Morning Briefing watchlist.

### Data Refresh

| Data Type | Refresh Trigger | Source |
|-----------|----------------|--------|
| Credit spreads (ETF prices) | Auto-refresh interval | `get_live_price_data` |
| PMI | On ISM release (monthly) | `get_economic_events` |
| CPI | On BLS release (monthly) | `get_economic_events` |
| GDP | On BEA release (quarterly) | `get_economic_events` |
| LLM sections | When indicator statuses change | LLM call with current data context |


## T3 -- All-Weather Portfolio Audit

### Evaluation Method

Computational (risk math). Reads the user's actual portfolio from the Portfolio page and audits it against the All-Weather reference allocation. If no portfolio is configured, falls back to 60/40 as default benchmark and prompts the user to set up their Portfolio.

### Risk Contribution Model

Simplified linear risk contribution (weight x annualized volatility). Does not account for correlations. Sufficient for the diagnostic purpose of demonstrating concentration.

Long-run volatility estimates (hardcoded, updated when volatility regime changes materially):
- Equities: ~16.5% annualized (long-run S&P 500 historical)
- Long bonds (TLT-equivalent): ~11.5% annualized
- Intermediate bonds: ~7% annualized
- Gold: ~16% annualized (GLD 30-year historical)
- Commodities: ~18% annualized (representative broad index)

### Sections

**Portfolio Comparison Strip**

Two side-by-side doughnut charts in a `g2` layout: user's portfolio (from Portfolio page) vs. All-Weather reference (30/40/15/7.5/7.5). Chart.js doughnut with `cutout: '60%'`. Custom HTML legends. Color assignment: blue (equities), purple (long bonds), light purple (intermediate bonds), amber (gold), teal (commodities).

**Section A -- Season Coverage Map**

Four colored cells in a 2x2 grid mirroring the T2 quadrant layout. Each cell: season name, coverage status badge, explanation of gaps, and what All-Weather holds for that season.

Three coverage states:
- Exposed (red `#FCEBEB`): portfolio has no assets that perform well in this season
- Partial (amber `#FAEEDA`): some coverage but below 20% combined weight
- Strong (teal `#E1F5EE`): 20%+ combined weight in season-appropriate assets

Cross-references the T2 current season verdict to highlight which season the user is currently exposed in.

**Section B -- Risk Parity Audit**

Bar chart rows showing risk contribution per asset class. Fill color: red if contribution >60%, amber if 40-60%, green if below 40%. Shows both the user's portfolio and the All-Weather reference for comparison.

Prose block below explaining the risk parity mechanism: why capital weight != risk weight, how equity volatility dominates, and how All-Weather corrects this.

**Section C -- Gold Allocation Check**

Gradient bar (CSS linear-gradient from green through amber to red, 0% to 20%+). Three vertical needle markers positioned with `position: absolute`:
- User's current gold allocation (red label)
- All-Weather baseline: 7.5% (amber label)
- Stress-environment guidance: ~15% (green label)

Three metric cards below: current gold weight, applicable reference range, allocation gap.

The applicable reference range is derived from upstream dashboards:
1. Read T1 phase classification. If "late plateau" or "deleveraging": use stress-environment guidance (~15%). Otherwise: use normal range (5-10%).
2. Read T2 season. If "autumn" or "transitioning to autumn": gold is seasonally aligned -- do not discount.
3. Read T5 active force count. If 4-5 forces at 7+: stress-environment confirmed.

Amber callout block cross-referencing T1, T2, and T5 to justify the derived range.

**Section D -- Retail Investor Caveats**

Four cells in a `g2` grid. No color coding (required reading regardless of direction). Order: leverage assumption (most fundamental), bond allocation risk in current regime (most relevant), rebalancing cadence, equity-bond correlation regime.

Bond caveat is adapted based on the T2 season verdict -- in inflationary regimes (summer/autumn), the high bond allocation underperforms.

**Synthesis Verdict**

Red callout (the only red synthesis across all templates -- T3's findings are directly actionable). Bottom line for the user's portfolio in the current macro environment.

### Data Refresh

T3 recomputes whenever:
- The user's Portfolio data changes (additions, removals, weight changes)
- T1, T2, or T5 outputs update (phase classification, season verdict, force count)
- Market prices update (for live portfolio valuation)

T3 does not make its own LLM calls. The gold allocation rationale callout references cached T1/T2/T5 synthesis text.


## T4 -- World Order Assessment

### Evaluation Method

LLM assessment. Runs on a user-configurable schedule: quarterly, weekly, or on significant news trigger. The LLM receives current data (fetched by the server before the call) and Dalio's world order framework as the system prompt.

### Data Inputs

| Data | Source | Refresh |
|------|--------|---------|
| USD FX reserve share | Hardcoded from IMF COFER (updated quarterly on COFER release) | Quarterly |
| Central bank gold purchases | EODHD or WGC data | Quarterly |
| Foreign Treasury holdings | EODHD economic events (TIC data) | Monthly |
| Dollar Index (DXY) | EODHD historical prices | Auto-refresh |
| Geopolitical news | EODHD news API | On LLM run |

### Sections

**Section A -- Reserve Currency Health Indicators**

Four-column scorecard table (same format as T1 scorecard). Indicators: USD share of global FX reserves, net central bank gold purchases, foreign Treasury holdings trend, Dollar Index (DXY). LLM populates the trend context narratives. Status badges assigned by the LLM based on Dalio's framework.

**Reserve Currency Composition Chart**

Multi-line Chart.js chart showing USD, EUR, JPY, CNY, Other reserve shares over time (1999-present). USD line: blue, solid, `borderWidth: 2` (visually dominant). Others: dashed, `borderWidth: 1.5`. Y-axis: 0-80%. Data hardcoded from IMF COFER annual snapshots; updated when fresh COFER data is released.

**Section B -- Empire Cycle Stage**

Stage timeline strip: six flex boxes (Rise / Peak / Plateau / Pressure / Pre-breakdown / Breakdown). Visual states: `.past` (gray gradient, progressively darker), `.active` (red, no border-radius), `.future` (muted background/text).

Dalio direct quote callout: amber background, italic text, source attribution. Shown when a relevant public statement exists classifying the current stage.

Stage 5 markers checklist: shift-row component (dot + stage badge + body). Each marker assessed as Confirmed / Developing / Not yet. LLM evaluates each marker against current data and news.

**Section C -- Historical Analog Grid**

Three cells in a `g3` grid with colored backgrounds: green (closest parallel), amber (partial parallel), red (illustrative/cautionary). Each cell has: bold title, "Similar:" paragraph, "Different:" paragraph. The "Different" content is mandatory -- the LLM must document departures, not just parallels. Color ordering maps to confidence in the analogy.

**Section D -- Wealth Shift Signals**

Four shift-row entries tracking capital migration from financial to real assets:
- Institutional (CB gold buying): early/mid/late stage
- Market (gold/equity ratio trend): early/mid/late stage
- Geopolitical (sanctions, reserve diversification): early/mid/late stage
- Retail/ETF (fund flows): early/mid/late stage

Combined wealth shift stage = median of the component readings (prevents one strong signal from inflating the aggregate).

**Section E -- Currency & Bond Risk Implications**

Two-panel `g2` layout. Currency table: major currencies + gold with directional badges. Bond risk assessment. Neutral gray backgrounds -- investment implications, not diagnostic outputs.

**Synthesis Verdict**

Amber callout. Downstream: T5 Force 3 intensity score, T3 gold allocation independent justification, Morning Briefing FX note.


## T5 -- Five Interlocking Forces Dashboard

### Evaluation Method

LLM assessment. This is the synthesis template -- it consumes outputs from T1, T2, and T4. Same schedule options as T4 (quarterly/weekly/news trigger, user-configurable).

### The Five Forces

| Force | What It Covers | Score Source |
|-------|---------------|-------------|
| 1. Debt & Money Cycle | Debt levels, monetary policy, currency system | Derived from T1 output |
| 2. Domestic Political Cycle | Polarization, institutional effectiveness, fiscal gridlock | LLM-assessed independently |
| 3. Geopolitical Cycle | Great-power competition, sanctions, trade war, reserve currency weaponization | Derived from T4 output |
| 4. Technology Wave | AI disruption, productivity shifts, labor market displacement | LLM-assessed independently |
| 5. Natural Forces | Pandemics, climate events, conflicts, exogenous shocks | LLM-assessed independently |

### Force Intensity Scoring

Each force is scored 1-10 against a historical baseline:
- 1-3: Below historical average or manageable in isolation
- 4-6: Moderately elevated -- flagged but not alarming
- 7-8: Significantly above historical norms -- historically notable in isolation
- 9-10: At or approaching historical extremes -- conditions seen only in major turning-point periods

A force scoring 7+ is classified as "active." The count of active forces is the headline metric.

### Active Force Count Interpretation

| Active Forces (score >= 7) | Framework Interpretation |
|----------------------------|------------------------|
| 0-1 | Normal -- standard diversification adequate |
| 2-3 | Elevated -- defensive positioning warranted |
| 4-5 | Historical turning point zone -- structural hedging required |

### Sections

**Section A -- Force Scorecard**

Five rows using the `force-row` grid: `120px / 1fr / auto`. Left cell: force label, sub-label, status badge, intensity bar. Center cell: evidence summary. Intensity bar: `width: [score x 10]%`, fill color red above 7/10, amber below.

Badge labels: Critical (score >= 8), High (score 7-7.9), Elevated (score 5-6.9), Moderate (score < 5).

**Active Force Count Block**

Wide banner card between Sections A and B. Count displayed in large text (28px, font-weight 500, colored red). Slightly elevated surface (`bg-[--color-bg-elevated]`). Interpretation label below referencing the table above.

**Section B -- Reinforcement Loop Analysis**

Four cells in a `g2` grid. Each cell describes one feedback loop. Component: `.loop-block` (gray background, no border) with title, two arrow-row entries (chip -> arrow -> chip), and prose description. Chips are small bordered labels showing the force name.

Requires at minimum:
1. One primary bidirectional loop (each force makes the other worse)
2. One secondary loop (between two different forces)
3. One amplifier (accelerates a loop without being a direct participant)

**Section C -- Market Data Reference**

Six metric cards in a `g3` grid. Consolidated data points from T1 and T4: gold price, debt/GDP, interest/revenue, CB gold demand, BRICS gold share, TIPS yield. No color coding -- reference data, not diagnostic outputs. Each card: 11px label, 20px value, 12px unit, 11px note.

**Section D -- Gold Allocation Signal**

Gradient bar (reused from T3) with the full derivation chain as a numbered list:
1. Count active forces (score >= 7)
2. Map count to Dalio guidance range (from interpretation table)
3. Cross-check with T4 world order stage (if Stage 5, do not discount guidance)
4. Cross-check with T2 season (if autumn or transitioning, gold is seasonally aligned)
5. Output recommended structural range with explicit rationale

Three needle markers on the gradient bar: current allocation (from Portfolio), applicable reference, stress-environment guidance.

**Section E -- Scenario Analysis**

Two colored cells: bull case (green `#EAF3DE`) and bear case (red `#FCEBEB`). Labeled as scenarios for forces decoupling vs. all five intensifying. Equal visual weight -- no implied probability. Scenario titles describe structural outcomes, not market direction.

**Synthesis Verdict**

Amber callout (not red -- forward-looking judgment, not a threshold already crossed). Downstream: T3 gold allocation check, Morning Briefing context, portfolio risk watchlist.


## Settings Panel

Accessible from the Settings button in the page header. Collapsible drawer or modal.

### Global Settings

| Setting | Type | Default |
|---------|------|---------|
| Auto-refresh interval (market data) | Dropdown | 5 min |
| T4/T5 LLM assessment schedule | Dropdown | Quarterly |
| T4/T5 news trigger sensitivity | Dropdown | Significant events only |

### Per-Dashboard Settings (T1, T2)

Formula engine dashboards share the Panic Thermometer settings pattern:

1. **Data source selector** -- dropdown to change the underlying ticker or event type per indicator
2. **Params table** -- key-value editor for threshold values. Each row: param name, current value, inline edit field. Values can be numeric literals.
3. **Rule editor** (advanced) -- ordered list of rules per indicator. Each rule: status color, formula, label. Users can reorder, edit formulas, add/delete rules. "Test" button evaluates against current data.
4. **Preset loader** -- dropdown to load a preset library. Presets: "Dalio defaults" (thresholds from the article), "Conservative" (tighter thresholds), "Relaxed" (wider thresholds).

### Per-Dashboard Settings (T3)

1. **Portfolio source** -- "Use Portfolio page" (default) or "Custom benchmark" (enter weights manually)
2. **Volatility estimates** -- editable table of annualized volatility per asset class (defaults to long-run historicals)
3. **Coverage thresholds** -- what combined weight counts as "partial" vs "strong" coverage per season

### Per-Dashboard Settings (T4, T5)

1. **Assessment schedule** -- Quarterly / Weekly / On news trigger
2. **News trigger keywords** -- editable keyword list for detecting significant events that warrant a re-run
3. **LLM model** -- which configured LLM to use for assessments
4. **Manual run button** -- "Run assessment now" to trigger an immediate LLM run


## Data Refresh Strategy

| Data Type | Refresh Interval | Source |
|-----------|-----------------|--------|
| Price-based tickers (live) | User-configurable (default 5 min) | `get_live_price_data` |
| Price-based tickers (history) | Daily at market close | `get_historical_stock_prices` |
| Economic events | 1 hour | `get_economic_events` |
| Macro indicators | On release | `get_macro_indicator` |
| News (for T4/T5 triggers) | 30 min | Company news API |
| LLM assessments (T4/T5) | User-configurable schedule | LLM call with fetched data context |
| Portfolio data (for T3) | On change | Portfolio page data |

Auto-refresh toggle in the header with options: Off / 5 min / 15 min. A "last updated" timestamp is shown per dashboard.


## Visual Design System

All dashboards use the existing OpenLIA design system (CSS variables, Tailwind utility classes). The shared component patterns are:

### Color Semantics

| Color | Semantic Role | CSS Variable or Hex |
|-------|--------------|-------------------|
| Red | Critical / warning zone breached | `--color-feedback-error` or `#E24B4A` (badge: `#FCEBEB` bg, `#A32D2D` text) |
| Amber | Elevated / transitional / watch | `#EF9F27` (badge: `#FAEEDA` bg, `#854F0B` text) |
| Green | Healthy / expansionary / covered | `--color-feedback-success` or `#639922` (badge: `#EAF3DE` bg, `#3B6D11` text) |
| Blue | Informational / equities | `#378ADD` (badge: `#E6F1FB` bg, `#0C447C` text) |
| Purple | Bonds / mixed confidence | `#7F77DD` (badge: `#EEEDFE` bg, `#3C3489` text) |
| Teal | Commodities / strong coverage | `#1D9E75` (badge: `#E1F5EE` bg, `#0F6E56` text) |
| Gray | Structural / neutral / historical | `--color-text-tertiary` |

Text on colored backgrounds always uses the 800/900 stop of the same ramp -- never black, never gray.

### Shared Components

| Component | Used In | Pattern |
|-----------|---------|---------|
| Four-column scorecard grid | T1, T4 | `2fr / 1fr / 1.2fr / 90px` with spark bars |
| Shift-row list (dot + badge + body) | T1 watchlist, T4 Stage 5 markers, T5 force rows | Signal list with colored dots |
| Season coverage cells | T2 quadrant map, T3 coverage map | Four colors mapping to four seasons |
| Gradient allocation bar with needles | T3 Section C, T5 Section D | CSS linear-gradient with absolute-positioned markers |
| Status badge | All dashboards | `inline-flex gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full` with dot |
| Synthesis verdict callout | All dashboards | Colored background block at bottom of each dashboard |
| `g2` / `g3` / `g4` grid | All dashboards | `gap-3 grid-cols-{n}` with `minmax(0, 1fr)` |

### Card Hierarchy

Three levels:
1. **Card** -- Primary section container. `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4`. Never nested.
2. **Sub-card (sm)** -- Secondary surface inside a card. `bg-[--color-bg-base] rounded-[--radius-md] p-3`. For metric cells, sub-sections.
3. **Colored callout** -- No border. Background from semantic color ramp. For verdicts and direct quotes only.

### Typography

| Element | Style |
|---------|-------|
| Section label | 11px, uppercase, `letter-spacing: 0.5px`, `text-[--color-text-tertiary]` |
| Body text | 13px, `text-[--color-text-secondary]`, `leading-relaxed` |
| Emphasis in body | `text-[--color-text-primary] font-medium` |
| Large metric value | 18-22px, `font-medium`, colored by semantic status |
| Fine print / sources | 11px, `text-[--color-text-tertiary]` |


## Responsive Behavior

| Breakpoint | Behavior |
|------------|----------|
| Desktop (>1024px) | Full layout; 2-column grids, all charts at full size |
| Tablet (768-1024px) | Single column; all grids collapse to stacked |
| Mobile (<768px) | Single column; horizontal padding reduced to `px-4`; charts reduce height; tab bar scrolls horizontally |


## States

| State | Visual Treatment |
|-------|-----------------|
| Loading (initial) | Skeleton placeholders for each section; spinner on tab bar |
| Loading (refresh) | Subtle loading indicator per dashboard; existing data remains visible |
| Data available | Full dashboard rendered |
| LLM running (T4/T5) | Pulsing indicator on the dashboard header; "Assessment in progress..." label; previous assessment remains visible |
| LLM complete | New assessment replaces previous; timestamp updates |
| No portfolio (T3) | Fallback to 60/40 benchmark; amber banner: "Set up your Portfolio for personalized analysis" with link to Portfolio page |
| Error | Inline error row below affected section: `text-sm text-[--color-feedback-error]` + retry link |
| Stale data | Amber timestamp label: "Data is N hours old" when auto-refresh is off and data exceeds staleness threshold |


## Integration with OpenLIA Architecture

### Core Layer (`packages/core/`)

- `departments/macro_research.py` -- Department class. No HTTP dependencies.
- `departments/macro_research/formula_config.py` -- Default formula engine rule sets and params for T1/T2 indicators.
- `departments/macro_research/risk_math.py` -- Risk contribution calculations for T3.
- `departments/macro_research/prompts/` -- YAML prompt templates for T4/T5 LLM assessments, structured with Dalio's framework as system context.
- `departments/macro_research/schemas.py` -- Pydantic models for dashboard state, indicator data, LLM assessment outputs.

### Server Layer (`packages/server/`)

- `routes/macro_research.py` -- REST endpoints: GET dashboard state, POST trigger LLM assessment, GET/PUT settings.
- `services/macro_research.py` -- Orchestration: data fetching, formula evaluation, LLM call scheduling, dependency ordering.
- Background scheduler: manages T4/T5 periodic LLM runs based on user-configured schedule.

### Frontend (`frontend/`)

- `pages/MacroResearch.tsx` -- Page component with tab navigation.
- `pages/MacroResearch/SummaryTab.tsx` -- Summary tab with framework cards.
- `pages/MacroResearch/DebtCycleTab.tsx` -- T1 dashboard.
- `pages/MacroResearch/FourSeasonsTab.tsx` -- T2 dashboard.
- `pages/MacroResearch/AllWeatherTab.tsx` -- T3 dashboard.
- `pages/MacroResearch/WorldOrderTab.tsx` -- T4 dashboard.
- `pages/MacroResearch/FiveForcesTab.tsx` -- T5 dashboard.
- `components/MacroResearch/` -- Shared components: Scorecard, QuadrantMap, GradientBar, ForceRow, StageTimeline, SeasonCoverageCell, SynthesisVerdict.


## Non-Goals (v1)

- Real-time streaming updates (SSE) for dashboard data -- polling is sufficient
- User-editable LLM prompts for T4/T5 assessments
- Historical playback (viewing past dashboard states)
- Alerting/notifications when dashboard status changes
- PDF/DOCX export of dashboard state
- Multi-country support (US-focused in v1)


## Open Questions

1. **EODHD macro indicator availability:** Debt-to-GDP and interest/revenue may not be available as direct EODHD endpoints. May need to compute from multiple economic event data points or hardcode with manual update on release. Need to verify during implementation.
2. **DXY proxy:** EODHD may not carry DXY directly. UUP (ETF) is a proxy. Need to verify ticker availability.
3. **IMF COFER data for T4:** This is quarterly with a lag. The reserve composition chart will use hardcoded snapshots updated on COFER release. A production version could fetch from the IMF API if the user provides access.
4. **T4/T5 LLM cost:** Each assessment run consumes LLM tokens. Weekly runs may be expensive depending on the model. The settings should show estimated cost per run based on the configured model.
5. **Formula engine sharing with Panic Thermometer:** The formula engine DSL, parser, and evaluator should be extracted into a shared module that both Panic Thermometer and Macro Research T1/T2 use. Implementation plan should account for this refactor.
