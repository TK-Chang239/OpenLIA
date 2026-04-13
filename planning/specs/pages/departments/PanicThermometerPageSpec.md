# Panic thermometer — full implementation spec

## Overview

A single-page React dashboard that monitors five crisis indicators derived from the report *"6 Key Indicators to Determine Whether to Enter the Market"*. The dashboard acts as a real-time "panic thermometer" — scoring each indicator as green / amber / red and rolling them into a composite threat level. Data is sourced from EODHD APIs with periodic auto-refresh.

**Core design principle: zero hardcoded thresholds.** Every trigger condition is a user-defined formula that evaluates against live and historical data. The report's suggested values (e.g. "$85 Brent", "0.5% wage MoM") ship as editable defaults in a "Report defaults" preset, not as constants baked into the code.

---

## Formula engine

### Concept

Each dashboard panel has a **rule set** — an ordered list of conditions that map to status levels (green → amber → red → dark_red). Each condition is a formula string that the engine evaluates against a **data context** object containing live values, computed indicators, and history.

A rule set is a JSON array evaluated top-to-bottom; the first matching condition wins. If nothing matches, the panel defaults to green.

```jsonc
// Example: oil duration panel
{
  "panel": "oil",
  "rules": [
    { "status": "dark_red", "formula": "streak_days > streak_dark_red AND price > price_threshold", "label": "Firmly in 2022 scenario" },
    { "status": "red",      "formula": "streak_days > streak_red AND price > price_threshold",      "label": "Approaching 2022 playbook" },
    { "status": "amber",    "formula": "price > price_threshold",                                    "label": "Monitoring" },
    { "status": "green",    "formula": "true",                                                       "label": "Base case intact" }
  ],
  "params": {
    "price_threshold": 85,
    "streak_red": 30,
    "streak_dark_red": 90
  }
}
```

The `params` object holds the tunable numbers. Users edit params via the settings UI; they never need to touch the formula strings unless they want advanced customization.

### Data context

The engine injects a data context before evaluating formulas. Each panel gets its own context built from EODHD API responses:

```typescript
interface DataContext {
  // Common (available to all panels using price-based instruments)
  price: number;            // latest close or live price
  prev_close: number;       // previous session close
  change_pct: number;       // session % change

  // Moving averages (computed from history)
  ma20: number;
  ma50: number;
  ma100: number;
  ma200: number;

  // Derived
  price_vs_ma200: number;   // price / ma200 — ratio (>1 = above, <1 = below)
  ma50_vs_ma200: number;    // ma50 / ma200 — golden/death cross detection
  pct_from_high: number;    // drawdown from 52-week high (negative %)
  pct_from_low: number;     // bounce from 52-week low (positive %)
  high_52w: number;
  low_52w: number;

  // Streak / duration
  streak_days: number;      // consecutive days meeting the panel's streak condition
  
  // Volatility
  atr_14: number;           // 14-day average true range
  std_20: number;           // 20-day rolling standard deviation of returns

  // Panel-specific fields (injected per dashboard — see each panel section)
  [key: string]: number | string | boolean;
}
```

### Supported formula syntax

Formulas are simple boolean expressions. No arbitrary code execution — this is a safe DSL parsed by a sandboxed evaluator.

**Operators**: `>`, `<`, `>=`, `<=`, `==`, `!=`, `AND`, `OR`, `NOT`, `(`, `)`

**Operands**: any key from the data context, any key from the params object, or a numeric/string literal.

**Built-in functions**:

| Function | Returns | Description |
|----------|---------|-------------|
| `cross_above(fast, slow)` | boolean | True if `fast` crossed above `slow` in the latest bar |
| `cross_below(fast, slow)` | boolean | True if `fast` crossed below `slow` in the latest bar |
| `consecutive(field, op, value)` | number | Count of consecutive latest bars where `field op value` is true |
| `pct_change(field, n_days)` | number | Percentage change over the last N trading days |
| `avg(field, n_days)` | number | Simple average of `field` over the last N trading days |
| `max(field, n_days)` / `min(field, n_days)` | number | Max/min over the last N days |
| `slope(field, n_days)` | number | Linear regression slope (positive = rising) |
| `days_since(event_type)` | number | Trading days since the last occurrence of an economic event |
| `percentile(field, lookback, pct)` | number | The value at the given percentile rank within trailing window |

**Examples of formulas users might write**:

| Goal | Formula |
|------|---------|
| Oil above a fixed price | `price > price_threshold` |
| Oil above its 200-day MA | `price > ma200` |
| Oil 20% above its MA200 | `price_vs_ma200 > 1.20` |
| Oil in a death cross | `cross_below(ma50, ma200)` |
| Oil in 90th percentile of year | `price > percentile(price, 252, 90)` |
| Wage MoM accelerating | `pct_change(value, 1) > 0 AND value > wage_threshold` |
| Two consecutive hot wage prints | `consecutive(value, ">", wage_threshold) >= 2` |
| Breakeven rising fast | `slope(value, 30) > slope_threshold` |
| Diplomacy window expired | `days_elapsed >= window_days` |

### Preset libraries

Ship three preset libraries that users can load with one click:

| Preset | Philosophy |
|--------|-----------|
| **Report defaults** | Uses the exact thresholds from the original report ($85 oil, 0.5% wages, 3.0% breakeven, etc.). Good starting point. |
| **MA-relative** | All price thresholds are expressed relative to moving averages (e.g. oil red when `price_vs_ma200 > 1.30`). Adapts automatically to different price regimes. |
| **Volatility-adjusted** | Thresholds scale with ATR or rolling standard deviation. A $5 move means different things at ATR=2 vs ATR=8. |

Users can also export/import rule sets as JSON for sharing.

---

## Dashboard 1 — Oil price duration

### What it measures

How long oil has remained in an "elevated" state. The user defines what "elevated" means — it could be an absolute price, a multiple of the MA200, a percentile rank, or an ATR band.

### Default params (from report — editable)

```jsonc
{
  "ticker": "BNO.US",
  "price_threshold": 85,
  "streak_amber": 1,
  "streak_red": 30,
  "streak_dark_red": 90,
  "reset_below_days": 20,
  "history_lookback_months": 6
}
```

### Default rules

```jsonc
[
  { "status": "dark_red", "formula": "streak_days >= streak_dark_red", "label": "{streak_days} days elevated — 2022 scenario" },
  { "status": "red",      "formula": "streak_days >= streak_red",      "label": "{streak_days} days elevated — scenario upgrade risk" },
  { "status": "amber",    "formula": "price > price_threshold",        "label": "Above threshold, monitoring" },
  { "status": "green",    "formula": "true",                           "label": "Below threshold" }
]
```

### Alternative user configurations (examples)

**MA-relative mode**: user changes the amber rule formula to `price > ma200 * 1.15` and removes the `price_threshold` param entirely. The threshold adapts as the moving average shifts.

**Volatility band mode**: user sets amber to `price > ma200 + atr_14 * 2` — oil is only "elevated" when it breaks two ATRs above its 200-day MA.

**Percentile mode**: user sets amber to `price > percentile(price, 252, 90)` — oil is elevated when it's in the 90th percentile of the trailing year.

### Panel-specific data context

```typescript
{
  price: number;              // BNO latest close / live
  streak_days: number;        // Consecutive days above whatever the amber rule evaluates to
  ma20: number;
  ma50: number;
  ma200: number;
  price_vs_ma200: number;
  atr_14: number;
  high_52w: number;
  low_52w: number;
  pct_from_high: number;
}
```

### Data source

- **History**: `EODHD:get_historical_stock_prices` with the user-configured `ticker` and `start_date` = `history_lookback_months` ago.
- **Live**: `EODHD:get_live_price_data` with the same ticker.

### UI

- **Metric card**: days above threshold (or MA), current price, status pill.
- **Chart**: line chart with the user's threshold rendered as a reference line. If the user is using an MA-relative threshold, the MA line is plotted dynamically. Area above threshold shaded in the status color.
- **Threshold editor**: inline controls to change the threshold mode (absolute / MA-relative / ATR-band / percentile) and the numeric param values. Changes re-evaluate immediately.

---

## Dashboard 2 — Inflation expectations

### What it measures

The market's implied expectation of average annual inflation over the next five years. Since EODHD does not carry the FRED T5YIE index directly, this panel uses proxy data with user-configurable thresholds.

### Default params (from report — editable)

```jsonc
{
  "primary_ticker": "TIP.US",
  "event_type_filter": "Michigan 5 Year Inflation Expectations",
  "level_amber": 2.5,
  "level_red": 3.0,
  "level_dark_red": 3.5,
  "tip_lookback_months": 6,
  "slope_lookback_days": 30,
  "slope_threshold": 0.02
}
```

### Default rules

```jsonc
[
  { "status": "dark_red", "formula": "michigan_5y >= level_dark_red",                                          "label": "Expectations unanchored ({michigan_5y}%)" },
  { "status": "red",      "formula": "michigan_5y >= level_red",                                               "label": "Expectations drifting ({michigan_5y}%)" },
  { "status": "red",      "formula": "michigan_5y == null AND slope(tip_price, slope_lookback_days) > slope_threshold", "label": "TIP rising fast (no survey data)" },
  { "status": "amber",    "formula": "michigan_5y >= level_amber",                                             "label": "Approaching concern zone" },
  { "status": "green",    "formula": "true",                                                                   "label": "Expectations anchored" }
]
```

### Alternative user configurations

**Pure TIP mode**: user drops the Michigan survey rules and uses `price > ma200 AND slope(tip_price, 30) > slope_threshold` — purely market-derived.

**Relative to history mode**: user sets red to `michigan_5y > percentile(michigan_5y, 60, 90)` — only alarmed when the survey is in the 90th percentile of its 5-year range.

### Panel-specific data context

```typescript
{
  michigan_5y: number | null;    // Latest Michigan 5Y inflation expectation (from economic events)
  michigan_prev: number | null;  // Previous month's value
  tip_price: number;             // TIP ETF latest close
  tip_ma200: number;             // TIP 200-day MA
  // ... standard price context fields for TIP
}
```

### Data source

- **TIP ETF**: `EODHD:get_historical_stock_prices` with `ticker` = `primary_ticker`.
- **Michigan survey**: `EODHD:get_economic_events` with `country=US` → filter for `event_type_filter`.

### UI

- **Metric card**: latest Michigan 5Y expectation, TIP price, status pill.
- **Chart**: dual-axis line chart — TIP price (left axis), Michigan survey points at monthly intervals (right axis). User-defined level bands drawn as horizontal reference lines on the right axis. Band colors change with each threshold.
- **Threshold editor**: numeric inputs for each level, plus a dropdown for threshold mode.

---

## Dashboard 3 — Fed language tracker

### What it measures

Whether the Fed's public posture is shifting from patience to alarm. The report emphasizes watching what Powell says, not what the Fed does.

### Default params (editable)

```jsonc
{
  "dovish_keywords": ["look through", "transitory", "patient", "well anchored"],
  "neutral_keywords": ["monitoring closely", "data dependent", "will act as appropriate"],
  "hawkish_keywords": ["broadly-based price pressures", "concerned about inflation", "persistent inflation"],
  "crisis_keywords": ["inflation expectations becoming unanchored", "emergency", "expedited"],
  "news_lookback_days": 30,
  "news_search_tags": "Fed,FOMC,Powell,Federal Reserve"
}
```

### Default rules

```jsonc
[
  { "status": "dark_red", "formula": "crisis_keyword_detected",                               "label": "Emergency posture — '{matched_phrase}'" },
  { "status": "red",      "formula": "hawkish_keyword_detected",                              "label": "Hawkish pivot — '{matched_phrase}'" },
  { "status": "amber",    "formula": "neutral_keyword_detected AND NOT dovish_keyword_detected", "label": "Neutral pivot" },
  { "status": "green",    "formula": "true",                                                  "label": "Dovish / wait-and-see" }
]
```

### User customization

Users have full control over all four keyword lists — they can add, remove, or rewrite any trigger phrase. The formula engine performs case-insensitive substring matching against news headlines and summaries.

Advanced users can also modify the rule formulas — e.g. requiring `hawkish_keyword_detected AND slope(tip_price, 14) > 0` to only trigger red when hawkish language coincides with rising inflation expectations.

### Panel-specific data context

```typescript
{
  dovish_keyword_detected: boolean;
  neutral_keyword_detected: boolean;
  hawkish_keyword_detected: boolean;
  crisis_keyword_detected: boolean;
  matched_phrase: string;              // The specific phrase that matched
  matched_headline: string;            // The headline containing the match
  matched_date: string;                // ISO date of the matching article
  days_since_fomc: number;             // Days since last FOMC decision event
  manual_override: string | null;      // User-set status if any
}
```

### Data source

- `EODHD:get_company_news` — search for `news_search_tags`
- `EODHD:get_economic_events` with `country=US` → filter for FOMC-related entries

### UI

- **Metric card**: current detected posture label, date of last FOMC statement, status pill.
- **Timeline**: horizontal timeline showing FOMC meeting dates as dots, colored by detected posture at that time.
- **Keyword scanner**: last 5 Fed-related headlines with matched trigger phrases highlighted in the status color. Each keyword list (dovish / neutral / hawkish / crisis) is editable inline.
- **Manual override toggle**: user can force the status if they disagree with automated detection. Override persists to `window.storage`.

---

## Dashboard 4 — Wage growth

### What it measures

Month-over-month growth in average hourly earnings. Two consecutive months above a user-defined threshold signals a wage-price spiral risk.

### Default params (from report — editable)

```jsonc
{
  "event_type_filter": "Average Hourly Earnings",
  "wage_threshold_amber": 0.4,
  "wage_threshold_red": 0.5,
  "consecutive_required": 2,
  "history_lookback_months": 12
}
```

### Default rules

```jsonc
[
  { "status": "dark_red", "formula": "consecutive_count >= consecutive_required", "label": "Wage-price spiral risk — {consecutive_count} consecutive months above {wage_threshold_red}%" },
  { "status": "red",      "formula": "value > wage_threshold_red",               "label": "Single hot print ({value}%)" },
  { "status": "amber",    "formula": "value > wage_threshold_amber",             "label": "Elevated but not critical ({value}%)" },
  { "status": "green",    "formula": "true",                                     "label": "Normal ({value}%)" }
]
```

### Alternative user configurations

**Acceleration mode**: user replaces the red rule with `pct_change(value, 1) > 0 AND value > wage_threshold_red` — only triggers when wages are both high and accelerating.

**Relative to CPI mode**: user adds a computed field `real_wage = value - cpi_mom` and triggers on `real_wage > 0.3` — only concerned when wages outpace prices.

**Dynamic threshold**: user sets `wage_threshold_red` to a formula reference like `avg(value, 12) + std_20` — the red line is one standard deviation above the trailing 12-month average. Adapts to the current wage growth regime.

### Panel-specific data context

```typescript
{
  value: number;              // Latest AHE MoM %
  prev_value: number;         // Previous month's AHE MoM %
  consecutive_count: number;  // Consecutive months above wage_threshold_red
  avg_12m: number;            // 12-month average AHE MoM
  cpi_mom: number;            // Latest CPI MoM (for real wage calc)
}
```

### Data source

- `EODHD:get_economic_events` with `country=US`, `start_date` = `history_lookback_months` ago → filter for `event_type_filter`
- Also pull CPI MoM and Real Earnings MoM for derived fields

### UI

- **Metric card**: latest MoM %, consecutive count, status pill.
- **Bar chart**: monthly bars colored by status. User-defined threshold rendered as a dashed horizontal line. If the user switches to dynamic threshold mode, the threshold line becomes a moving series.
- **Threshold editor**: numeric inputs for each threshold, dropdown for mode (absolute / dynamic / acceleration).

---

## Dashboard 5 — Diplomatic progress

### What it measures

Whether substantive diplomatic progress has occurred within a rolling window. Primarily a manually-scored indicator with automated news support.

### Default params (editable)

```jsonc
{
  "window_days": 30,
  "window_amber_pct": 50,
  "news_keywords": ["ceasefire", "Hormuz", "strait", "Iran", "diplomatic", "negotiations", "peace talks", "de-escalation"],
  "escalation_keywords": ["military escalation", "strike", "blockade", "retaliation", "mobilization"],
  "news_lookback_days": 30
}
```

### Default rules

```jsonc
[
  { "status": "red",   "formula": "days_elapsed >= window_days AND escalation_detected",    "label": "Window lapsed + escalation" },
  { "status": "red",   "formula": "days_elapsed >= window_days",                            "label": "Window lapsed, no progress" },
  { "status": "amber", "formula": "days_elapsed >= window_days * (window_amber_pct / 100)", "label": "{days_remaining} days remaining" },
  { "status": "green", "formula": "true",                                                  "label": "Within window" }
]
```

### Panel-specific data context

```typescript
{
  days_elapsed: number;          // Days since last user-set milestone
  days_remaining: number;        // window_days - days_elapsed
  escalation_detected: boolean;  // True if any escalation_keywords found in recent news
  progress_detected: boolean;    // True if any news_keywords found
}
```

### User customization

- **Window length**: configurable (not fixed at 30 days).
- **Keyword lists**: users add/remove diplomatic and escalation keywords.
- **Amber timing**: `window_amber_pct` controls when amber triggers (at 50% elapsed, 75%, etc.).
- **Milestone reset**: clicking "Mark milestone" resets the window start to today and persists to storage.

### Data source

- `EODHD:get_company_news` — search for `news_keywords` and `escalation_keywords`
- Window start date stored in `window.storage`

### UI

- **Metric card**: days elapsed / window length, status pill.
- **Countdown bar**: progress bar filling from green → amber → red as the window expires.
- **News feed**: last 10 matching headlines, diplomatic keywords highlighted green, escalation keywords highlighted red.
- **Reset button**: "Mark diplomatic milestone" resets the counter.
- **Manual override**: dropdown to force status, overriding the formula.

---

## Settings panel

A collapsible settings drawer accessible from a gear icon in the dashboard header.

### Global settings

| Setting | Type | Default |
|---------|------|---------|
| Auto-refresh interval | Dropdown | 5 min |
| Composite scoring method | Dropdown | Count of red panels |
| Composite "action needed" threshold | Number | 2 |

### Per-panel settings

Each panel has its own settings section containing:

1. **Ticker / data source selector** — dropdown or text input to change the underlying instrument or event type.
2. **Params table** — key-value editor for all `params`. Each row shows the param name, current value, and an inline edit field. Values can be numeric literals or references to data context fields (e.g. `ma200 * 1.15`).
3. **Rule editor** — ordered list of rules. Each rule shows its status color, formula, and label. Users can reorder (drag), edit formulas inline, add new rules, or delete rules. A "Test" button evaluates the formula against the current data context and shows the boolean result plus the resolved values of all referenced variables.
4. **Preset loader** — dropdown to load a preset library (Report defaults / MA-relative / Volatility-adjusted). Loading a preset overwrites the current params and rules for that panel only.

### Import / export

- **Export all**: downloads the complete configuration (all panel params + rules + global settings) as a single JSON file.
- **Import**: upload a JSON file to restore a saved configuration.
- **Share**: generates a base64-encoded URL parameter string so configs can be shared as links.

### Persistent storage keys

| Key | Scope | Contents |
|-----|-------|----------|
| `panic:config` | personal | Complete configuration: all panel params, rules, global settings |
| `panic:fed-override` | personal | `{status, note, date}` — manual Fed language status |
| `panic:diplo-milestone` | personal | `{date, note}` — last diplomatic milestone date |

---

## Composite threat level

### Default scoring

Count of panels at red or dark_red status → maps to threat level:

| Red count | Level | Color |
|-----------|-------|-------|
| 0 | Calm | green |
| 1 | Elevated | amber |
| ≥ user threshold (default 2) | High | orange |
| ≥ threshold + 1 | Severe | red |
| ≥ threshold + 2 | Crisis | dark red |

### Configurable composite

Users can change the composite from simple counting to **weighted scoring**:

```jsonc
{
  "composite_mode": "weighted",
  "weights": {
    "oil": 1.0,
    "breakeven": 1.0,
    "fed": 0.8,
    "wages": 1.0,
    "diplomacy": 0.5
  },
  "thresholds": {
    "elevated": 1.0,
    "high": 2.0,
    "severe": 3.0,
    "crisis": 4.0
  }
}
```

In weighted mode, each red panel contributes its weight to the total score. Users can de-emphasize panels they consider less reliable by lowering their weight.

---

## Layout

```
┌──────────────────────────────────────────────────────────┐
│  PANIC THERMOMETER        [auto-refresh ▼]  [⚙ settings]│
│  ════════════════════════════════════════════════════════ │
│  [▓▓▓▓▓▓▓▓▓▓░░░░░░░]  SEVERE  │  3/5 red               │
│  Calm  Elevated  High  Severe  Crisis                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────┐│
│  │ 1. OIL  │ │ 2. BKN  │ │ 3. FED  │ │ 4. WAGE │ │5.DPL││
│  │ {value} │ │ {value} │ │ {value} │ │ {value} │ │{val}││
│  │  [pill] │ │  [pill] │ │  [pill] │ │  [pill] │ │[pil]││
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────┘│
│                                                          │
├─────────────────────────┬────────────────────────────────┤
│  DASHBOARD 1            │  DASHBOARD 2                   │
│  Oil price duration     │  Inflation expectations        │
│  [line chart]           │  [dual-axis chart]             │
│  ───── user threshold   │  ───── user threshold(s)       │
│  [edit threshold ▼]     │  [edit threshold ▼]            │
├─────────────────────────┼────────────────────────────────┤
│  DASHBOARD 3            │  DASHBOARD 4                   │
│  Fed language tracker   │  Avg hourly earnings MoM       │
│  [FOMC timeline]        │  [bar chart]                   │
│  [headline scanner]     │  ───── user threshold          │
│  [keyword editor]       │  [edit threshold ▼]            │
│  [manual override ▼]    │                                │
├─────────────────────────┴────────────────────────────────┤
│  DASHBOARD 5 — Diplomatic progress                       │
│  [countdown bar]  [news feed]  [manual toggle]           │
│  [window length: {user-set} days]                        │
├──────────────────────────────────────────────────────────┤
│  MACRO DATA TABLE                                        │
│  Latest releases from EODHD economic calendar            │
│  [auto-populated from get_economic_events]               │
└──────────────────────────────────────────────────────────┘
```

### Responsive behavior

- **Desktop (>1024px)**: 2-column grid for dashboards 1–4, full-width for dashboard 5 and macro table.
- **Tablet (768–1024px)**: single column, all panels stacked.
- **Mobile (<768px)**: single column; charts switch to sparklines; metric cards scroll horizontally.

---

## Data refresh strategy

| Data type | Refresh interval | EODHD endpoint |
|-----------|-----------------|----------------|
| Price-based tickers (live) | User-configurable (default 5 min) | `get_live_price_data` |
| Price-based tickers (history) | Daily at market close | `get_historical_stock_prices` |
| Economic events | 1 hour | `get_economic_events` |
| News (Fed / geopolitical) | 30 min | Company news API |
| Michigan survey | On release (monthly) | `get_economic_events` |

Auto-refresh toggle in the top-right corner with options: Off / 1 min / 5 min / 15 min.

A "last updated" timestamp is shown beside each panel.

---

## EODHD API call map

```
Dashboard 1 (Oil)
├── get_historical_stock_prices(ticker=<user.ticker>, start_date=<user.lookback>)
└── get_live_price_data(ticker=<user.ticker>)

Dashboard 2 (Breakeven)
├── get_historical_stock_prices(ticker=<user.primary_ticker>, start_date=<user.lookback>)
├── get_live_price_data(ticker=<user.primary_ticker>)
└── get_economic_events(country="US") → filter <user.event_type_filter>

Dashboard 3 (Fed language)
├── Company news search for <user.news_search_tags>
└── get_economic_events(country="US") → filter FOMC dates

Dashboard 4 (Wages)
└── get_economic_events(country="US", start_date=<user.lookback>)
    → filter <user.event_type_filter>

Dashboard 5 (Diplomacy)
└── Company news search for <user.news_keywords> and <user.escalation_keywords>

Macro table
└── get_economic_events(country="US", start_date=7d_ago)
    → filter CPI, Core CPI, PCE, GDP, Michigan, Real Earnings
```

---

## Data Requirements

PT is a pre-fetch dashboard department. Data is fetched periodically and fed into the formula engine for threshold evaluation.

**Basic (department disabled without these):**

| Requirement | Type | Description |
|---|---|---|
| Historical prices | `historical_prices` | Historical daily OHLCV for oil proxy (BNO), TIP ETF, and computed indicators (MAs, ATR, streaks) |
| Stock quote | `stock_quote` | Real-time or delayed prices for dashboard panel updates |
| Economic events | `economic_events` | Economic calendar for wages (Average Hourly Earnings), inflation (Michigan survey), and FOMC dates |

**Advanced (features degrade gracefully if missing):**

| Requirement | Type | Description | Without It |
|---|---|---|---|
| Company news | `company_news` | News articles for Fed language keyword scanning and diplomatic progress tracking | Fed Language Tracker and Diplomatic Progress panels disabled; only Oil, Inflation, and Wage panels operational |

---

## Tech stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | React (`.jsx` artifact) | Renders inline in Claude; interactive |
| Charts | Chart.js 4.x via CDN | Lightweight, streams well |
| State | `useState` + `useReducer` | No localStorage in Claude artifacts |
| Styling | Tailwind utility classes + CSS variables | Matches Claude design system |
| Data | EODHD MCP via Anthropic API | Artifact calls Claude API with MCP servers |
| Persistence | `window.storage` (artifact storage API) | Persist config, manual overrides across sessions |
| Formula engine | Custom safe DSL parser | Sandboxed — no eval(), no arbitrary code execution |

---

## Formula engine implementation notes

### Parser architecture

The formula engine parses formula strings into an AST and evaluates them against the data context + params. It must **never** use `eval()` or `new Function()`.

Recommended approach:

1. **Tokenizer**: splits the formula string into tokens (identifiers, operators, numbers, parens, commas).
2. **Parser**: recursive descent parser that builds an AST from the token stream. Grammar supports comparison expressions, boolean combinators (`AND`/`OR`/`NOT`), function calls, and arithmetic (`+`, `-`, `*`, `/`).
3. **Evaluator**: walks the AST and resolves each node against the merged context (`{...dataContext, ...params}`). Function calls dispatch to a whitelist of built-in functions.

### Streak computation

The `streak_days` field requires special handling. The engine needs to know *what condition* defines "elevated" for the purpose of counting consecutive days. This is derived from the first `amber` rule's formula — the engine extracts the price-comparison portion and backtests it against history to compute the streak.

Alternatively, the user can define an explicit `streak_condition` param that the engine uses for counting:

```jsonc
{
  "streak_condition": "price > price_threshold"  // or "price > ma200 * 1.15"
}
```

The engine evaluates this condition against each historical bar (with the MA/ATR recomputed at each point) and counts backward from today until the condition is false.

### Validation

When a user edits a formula, the settings UI should:

1. Parse the formula immediately and show syntax errors inline.
2. Resolve all variable references against the current data context and highlight any undefined variables in red.
3. Evaluate the formula and show the current boolean result and the resolved values of all referenced variables (for debugging).
4. Show a "would trigger" preview — given the current data, which status level would this rule set produce?

---

## Implementation phases

### Phase 1 — Static dashboard with formula engine (React artifact)

Build the full layout and the formula engine with preset defaults loaded. Charts render with hardcoded snapshot data from the prototype. All five metric cards, charts, threshold editor UI, and composite bar. Goal: nail the formula engine UX and validate the DSL.

### Phase 2 — Live data via Anthropic API + EODHD MCP

Wire up each panel to call the Anthropic API with the EODHD MCP server. The artifact makes fetch calls to `api.anthropic.com/v1/messages` with `mcp_servers` pointing to `https://mcpv2.eodhd.dev/v2/mcp`. Parse MCP tool results, compute derived fields (MAs, ATR, streaks), populate data contexts, and evaluate formulas.

### Phase 3 — Auto-refresh + persistence + presets

Add the refresh timer. Persist full configuration (params + rules + manual overrides) to `window.storage`. Implement the three preset libraries. Add import/export JSON. Loading spinners per panel.

### Phase 4 — Alerts + historical playbook overlay

- Notification bar that triggers when the composite level changes.
- "Historical playbook" overlay showing what happened at similar indicator levels in 1973, 1990, and 2022 (reference data from the report).
- Optional: Anthropic API call to classify FOMC statement excerpts as dovish/neutral/hawkish using structured prompts, replacing keyword matching.

---

## Open questions

1. **Oil ticker**: `BZ.COMM` returns 404 on EODHD. `BNO.US` (ETF) tracks at ~$47 vs actual Brent at ~$65. Since the threshold is user-defined, the user can simply set it to the ETF-equivalent level — but a conversion factor param or ticker search UI would improve UX.
2. **5Y breakeven**: EODHD doesn't carry `T5YIE.INDX`. Michigan survey + TIP ETF is the best available proxy. Could supplement with a FRED API call if the user provides a key — this would be an optional data source toggle in the panel settings.
3. **Formula engine complexity vs. accessibility**: the DSL needs to be powerful enough for MA/ATR/percentile expressions but simple enough that non-developers can use the preset params without learning syntax. The settings UI should default to showing only the param value inputs (simple mode) with a "Show formulas" toggle for advanced users.
4. **Wage data availability**: EODHD economic events may not always include "Average Hourly Earnings MoM" as a distinct event type. The `event_type_filter` param lets the user switch to alternative event names like "Nonfarm Payrolls" or "Real Earnings".
5. **Streak backtest cost**: computing `streak_days` requires evaluating the streak condition against every bar in history. For MA-relative streaks, this means computing rolling MAs across the full lookback. O(n) for 6 months of daily data is fine, but could be slow if users set very long lookbacks with complex conditions.