# Retail Sentiment Department Spec

## Page Overview

The Retail Sentiment Department (RS) provides a 12-metric sentiment monitoring dashboard that aggregates data from financial providers, social media APIs, and cross-platform sentiment sources. Users build a watchlist of tickers and monitor retail investor sentiment through three analytical tabs: Overview (metrics at a glance), Evidence (source traceability), and Insights (actionable signals with LLM synthesis).

RS is a dashboard department -- there is no chat interface.

Full design spec: `planning/specs/systems/retail-sentiment-dashboard-design.md`

## Functions

1. **12 Sentiment Metrics**: Sentiment Score, Buzz Volume, Sentiment Momentum, Bull/Bear Ratio, Buzz-Sentiment Divergence, Social Velocity, Cross-Source Agreement, Put/Call Sentiment Ratio, Short Interest Pressure, Narrative Concentration Index, Institutional-Retail Sentiment Gap, Event Sensitivity Score. Metrics that lack required data from configured providers are automatically disabled.
2. **Three Analytical Tabs**: Overview (tiered metric cards + charts), Evidence (metric-filtered evidence feed + score impact decomposition), Insights (active signal alerts + LLM narrative synthesis + reliability matrix).
3. **Watchlist Management**: Users add/remove tickers, import from Portfolio page, and monitor sentiment per ticker or across all tickers via a heat map.
4. **Batch LLM Classification**: News articles and social posts are classified as bullish/bearish/neutral in batch LLM calls with a structured prompt template enforcing a fixed JSON output schema.
5. **Cross-Source Validation**: When multiple data sources agree on sentiment direction, signal reliability increases. Configurable source weights.
6. **Metrics Deep Dive**: Educational panel (opened by ? button at bottom-right) explaining each metric's formula, data source, chart type, and interpretation.

---

## User Interface Design

### Layout

RS uses a tabbed dashboard with 3 primary tabs and a ticker selector.

```
+----------------------------------------------------------------+
|  Retail Sentiment                [Auto-refresh v]  [Settings]   |
|----------------------------------------------------------------|
|  [Overview *] [Evidence] [Insights]                             |
|----------------------------------------------------------------|
|  [All] [AAPL *] [TSLA] [NVDA]  [Import Portfolio] [+ Add]     |
|----------------------------------------------------------------|
|  AAPL - Apple Inc.  ·  Last updated: 2 min ago                  |
|                                                                 |
|                    (active tab content)                          |
|                                                                 |
|                                                    [?]          |
+----------------------------------------------------------------+
```

---

### Page Header

| Element | Detail |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Retail Sentiment" -- `text-xl font-semibold text-[--color-text-primary]`, `pl-6` |
| Auto-refresh dropdown | Right of header; options: Off / 30 min / 1 hr; `text-sm text-[--color-text-secondary]` |
| Settings button | Right of header, `pr-6`; outline style matching other departments; opens Settings panel |

---

### Tab Bar

| Element | Detail |
|---|---|
| Container | `flex items-center gap-1 px-6 bg-[--color-bg-base] border-b border-[--color-border-subtle]` |
| Tab | `px-4 py-2.5 text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:text-[--color-text-primary]`; active: `text-[--color-text-primary] font-medium border-b-2 border-[--color-text-primary]` |
| Default active tab | Overview |

---

### Ticker Selector

| Element | Detail |
|---|---|
| Container | `flex items-center gap-2 px-6 py-2 border-b border-[--color-border-subtle] overflow-x-auto` |
| Ticker pill | `px-3 py-1 rounded-full text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] border border-[--color-border-subtle]`; active: `bg-[--color-surface-active] text-[--color-text-primary] font-medium` |
| "All" pill | First position; shows multi-ticker heat map when active |
| "Import from Portfolio" button | `text-sm text-[--color-accent-primary]`; imports tickers from Portfolio page, skips duplicates |
| "+ Add" pill | Last position; dashed border; opens search popover |
| Remove ticker | Hover to reveal `x` (12px) |
| Large watchlist warning | Amber toast at 21+ tickers with estimated cost per refresh |

---

### Overview Tab

**Single ticker selected:** Headline tier (4 large cards: Sentiment, Momentum, Divergence, Cross-Source) + Compact tier (8 smaller cards: Buzz, Bull/Bear, Velocity, Put/Call, Short Interest, Narrative, Institutional Gap, Event Sensitivity) + Charts (sentiment vs price overlay, buzz bars, momentum area chart).

**"All" selected:** Multi-ticker heat map (tickers x key metrics) with sparklines and signal count badges. Click a row to switch to that ticker.

See design spec sections "Overview Tab" for full detail.

---

### Evidence Tab

Metric filter bar at top (select which metric to trace). Score impact decomposition chart showing how each evidence item shifts the selected metric. Reverse-chronological evidence feed with source badges, NLP classification, impact values, and engagement metrics.

See design spec section "Evidence Tab" for full detail.

---

### Insights Tab

Active signal alert cards (only metrics in notable state). LLM narrative synthesis tying signals together. Reliability matrix bubble scatter (predictive strength vs timeliness for all 12 metrics).

See design spec section "Insights Tab" for full detail.

---

### Help Button (Metrics Deep Dive)

Fixed `?` button at bottom-right. Opens a 480px drawer with educational content for each metric: formula, data source, chart type, interpretation guide, caveats.

---

### States

| State | Visual Treatment |
|---|---|
| **Empty watchlist** | Centered empty state: `Eye` icon + "Nothing to monitor yet" + "Add Ticker" button |
| **Loading (initial)** | Skeleton placeholders for metric cards and charts |
| **Loading (refresh)** | Subtle loading indicator; existing data remains visible |
| **Data available** | Full dashboard rendered |
| **NLP running** | Pulsing indicator; "Classifying N items..." label |
| **Metric disabled** | Card grayed out with note about required provider capability |
| **Cold start (event sensitivity)** | "Insufficient data (N/30 days collected)" |
| **Stale data** | Amber timestamp when data exceeds staleness threshold |
| **Error** | Inline error below affected section + retry link |

---

### Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | 4-column tiers, full charts |
| Tablet (768-1024px) | 2-column tiers; charts full width |
| Mobile (<768px) | Single column; ticker pills scroll horizontally; Deep Dive drawer becomes full-screen overlay |

---

## Page Settings

All configuration is accessed via the Settings panel in the page header. There is no Report Settings modal -- RS does not generate reports.

## Report Framework

Not applicable. RS is a dashboard department and does not generate text reports.

## Data Requirements

RS is a pre-fetch dashboard department. Data is fetched periodically from financial and social media providers, classified via batch LLM calls, and fed into the metrics computation engine.

**Basic (department disabled without these):**

| Requirement | Type | Description |
|---|---|---|
| Stock quote | `stock_quote` | Current price and daily change for ticker display and event sensitivity correlation |
| Company news | `company_news` | News articles for batch LLM sentiment classification and narrative analysis |
| Social sentiment | `social_sentiment` | Social media posts and engagement data (tweets, volume, likes, retweets) for buzz and sentiment metrics |

**Advanced (features degrade gracefully if missing):**

| Requirement | Type | Description | Without It |
|---|---|---|---|
| Historical prices | `historical_prices` | Price history for sentiment vs price overlay charts and Event Sensitivity Score | Overview charts lack price overlay; Event Sensitivity Score metric disabled |
| Options data | `options_data` | Put/call ratio data for sentiment-adjusted options analysis | Put/Call Sentiment Ratio metric disabled |
| Short interest | `short_interest` | Short interest and days-to-cover data | Short Interest Pressure metric disabled |
| Institutional holdings | `institutional_holdings` | Institutional flow and positioning data | Institutional-Retail Sentiment Gap metric disabled |

Note: Metrics that lack required data from configured providers are automatically disabled with a note explaining the required provider capability. See the full design spec for detailed per-metric data source mappings.

## Configurations

- NLP classification: Batch LLM calls with structured prompt template
- Data sources: Provider-agnostic (EODHD, FMP, Flashalpha, X API, or any configured provider)
- Metrics engine: Pandas-based computation for all 12 metrics
