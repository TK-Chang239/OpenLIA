# Retail Sentiment Department -- Sentiment Monitor Dashboard

Redesign of the Retail Sentiment department from a minimal 3-metric dashboard into a full sentiment monitoring platform with 12 metrics, 3 analytical tabs, evidence traceability, LLM-powered classification, and cross-source validation. Based on `sentiment_dashboard_design.md`.

> **Cross-reference note (2026-04-15):** Dashboard persistence is DB-backed per `database-design.md`: `rs_user_config` (per-user tab state, metric settings, filter presets, refresh interval), `rs_snapshots` (global point-in-time sentiment metric snapshots), and `rs_classification_log` (LLM classification audit trail). Watchlist integration uses the shared `watchlists`/`watchlist_items` tables.


## Department Identity

- **Name:** Retail Sentiment (RS)
- **Type:** Dashboard department (no chat interface)
- **Data access pattern:** Pre-fetch (code fetches data from configured providers, then metrics engine computes, LLM classifies and synthesizes)
- **Sidebar entry:** "Retail Sentiment" with the same icon and position as the current RS entry


## Twelve Metrics

| # | Metric | What It Answers | Category |
|---|--------|----------------|----------|
| 1 | Sentiment Score | What is the current mood? | Mood |
| 2 | Buzz Volume | How much are people talking? | Attention |
| 3 | Sentiment Momentum | Is mood improving or worsening? | Mood |
| 4 | Bull/Bear Ratio | How broad is the conviction? | Mood |
| 5 | Buzz-Sentiment Divergence | When should I be contrarian? | Signals |
| 6 | Social Velocity | Is attention accelerating? | Attention |
| 7 | Cross-Source Agreement | How much should I trust this signal? | Signals |
| 8 | Put/Call Sentiment Ratio | What are people betting with real money? | Signals |
| 9 | Short Interest Pressure | Is a squeeze building? | Signals |
| 10 | Narrative Concentration Index | Is the conversation dominated by one theme? | Attention |
| 11 | Institutional-Retail Sentiment Gap | Do analysts and retail agree? | Signals |
| 12 | Event Sensitivity Score | How reactive is the crowd to news? | Attention |


## Metric Definitions

### 1. Sentiment Score (Normalized)

**Formula:** `score = (positive_mentions - negative_mentions) / total_mentions`

**Data:** Financial provider sentiment endpoints (`normalized` field). For social media data, each post is classified by the NLP batch pipeline and the daily average is computed.

**Range:** -1 (extremely bearish) to +1 (extremely bullish). 0 = balanced opinion, not absence.

**Visualization:** Dual-axis line chart overlaying sentiment score against price change percentage.

**Interpretation:** Always compare against the stock's own historical range, not across stocks. A +0.2 for a typically calm stock is more significant than +0.2 for a volatile meme stock.

### 2. Buzz Volume (Mention Count)

**Formula:** `buzz_ratio = count(mentions_today) / avg(mentions_over_30d)`

Raw counts normalized by 30-day moving average so buzz is comparable across tickers.

**Data:** Financial provider sentiment count fields for news. Social media provider volume endpoints. Cross-platform social sentiment post counts.

**Visualization:** Bar chart with color coding: blue (at/below average), amber (1x-1.5x), red (above 1.5x). Dashed horizontal line at 30-day average.

**Interpretation:** Buzz spikes predict volatility (either direction), not direction. High buzz + positive sentiment = potential FOMO/crowding. High buzz + negative sentiment = panic.

### 3. Sentiment Momentum (Rate of Change)

**Formula:** `momentum = SMA(sentiment, N)_today - SMA(sentiment, N)_yesterday`

N is user-configurable (default 5 days). SMA smooths out single-day noise.

**Visualization:** Area chart with dual-fill: green above zero (improving), red below zero (deteriorating).

**Interpretation:** The most useful leading indicator. A stock can have negative sentiment but positive momentum (mood recovering). Momentum often leads price by 1-3 days.

### 4. Bull/Bear Ratio

**Formula:** `ratio = bullish_posts / (bullish_posts + bearish_posts)`

Neutral posts excluded.

**Data:** Derived from NLP classification of tweets and articles. Cross-platform social sentiment providers supply a pre-computed sentiment percentage as cross-check.

**Visualization:** Stacked bar chart -- green (bullish %) and red (bearish %) stacked to 100% per day.

**Interpretation:** Ratio + buzz volume together reveal conviction breadth. 90/10 from 50 posts = fragile. 60/40 from 5,000 posts = durable. 50/50 = genuine uncertainty.

### 5. Buzz-Sentiment Divergence

**Formula:** `divergence = z_score(buzz) - z_score(sentiment)`

Both z-scored against their own 30-day history.

**Thresholds (user-configurable):**
- Positive divergence > 2.0: Panic signal (lots of talk, negative tone)
- Negative divergence < -2.0: Stealth recovery (silence, improving tone)
- Between -1.0 and 1.0: Normal

**Visualization:** Colored bar chart: red (divergence > 1.0), green (divergence < -1.0), gray (normal).

### 6. Social Velocity

**Formula:** `velocity = (buzz_today - buzz_yesterday) / buzz_yesterday`

**Data:** Social media provider hourly volume (intraday resolution) or financial provider sentiment count (daily resolution).

**Interpretation:** Velocity fires before buzz peaks. Useful for catching trends before they peak. Not charted continuously -- surfaces as alerts when velocity exceeds threshold.

### 7. Cross-Source Agreement Score

**Formula:** Check directional agreement across all configured data sources. Score = count of agreeing sources / total active sources.

**Cross-source weighted average (when all agree):** Financial provider 40%, social media 35%, cross-platform 25%. These weights are user-configurable in Settings.

**Visualization:** Badge showing "N/N sources agree" with color: green (all agree), amber (majority agree), red (split).

**Interpretation:** When all sources agree, signal reliability is 2-3x higher than any single source.

### 8. Put/Call Sentiment Ratio

**Formula:** `put_call_ratio = put_volume / call_volume`

**Data:** Options data from configured financial provider or Flashalpha options chain.

**Interpretation:** Compares what people say (social sentiment) vs what they bet (options). Bullish social sentiment + elevated put/call = crowd is hedging. Below 0.7 = bullish positioning. Above 1.0 = bearish positioning.

**Visualization:** Single value card with historical sparkline. Color: green (<0.7), gray (0.7-1.0), red (>1.0).

### 9. Short Interest Pressure

**Formula:** Two components: `short_pct = short_interest / shares_float` and `days_to_cover = short_interest / avg_daily_volume`

**Data:** Financial provider fundamentals data (short interest, shares outstanding, float).

**Interpretation:** High short interest (>10%) + improving sentiment momentum = squeeze potential. Days-to-cover above 5 = significant pressure.

**Visualization:** Dual value card showing both percentage and days-to-cover.

### 10. Narrative Concentration Index

**Formula:** `concentration = sum(top_3_word_weights) / sum(all_word_weights)`

**Data:** Financial provider word/narrative weight endpoints.

**Interpretation:** Top 3 words > 60% weight = concentrated narrative (fragile -- one counter-story can flip sentiment). Dispersed across many themes = more durable sentiment. Tracks narrative shifts over time (e.g., "growth" being overtaken by "investigation").

**Visualization:** Word cloud or treemap showing top themes. Concentration percentage as a sub-metric.

### 11. Institutional-Retail Sentiment Gap

**Formula:** `gap = analyst_consensus_normalized - retail_sentiment_score`

Analyst consensus mapped to -1 to +1 scale: strong sell = -1, sell = -0.5, hold = 0, buy = +0.5, strong buy = +1. Weighted by number of analysts.

**Data:** Analyst ratings from financial provider fundamentals. Retail sentiment from Metric 1.

**Interpretation:** Gap > 0.5 = analysts significantly more bullish than retail. Gap < -0.5 = analysts more bearish. Large gaps are historically informative -- institutional consensus tends to lead retail by weeks.

**Visualization:** Divergence bar showing analyst position vs retail position on a shared -1 to +1 axis.

### 12. Event Sensitivity Score

**Formula:** `sensitivity = stddev(sentiment_change on event_days) / stddev(sentiment_change on quiet_days)`

Event days = days with news articles or earnings releases for the ticker. Quiet days = everything else. Computed over a rolling 60-day window.

**Data:** Daily sentiment history (Metric 1), news article dates from financial provider, earnings dates from financial provider calendar.

**Cold start:** Requires ~30 days of sentiment history per ticker. Before that, shows "Insufficient data (N/30 days collected)."

**Interpretation:** Score 1.0 = crowd reacts equally regardless of news. Score 3.0+ = highly reactive crowd (momentum traders). Low sensitivity = conviction holders.

**Visualization:** Single value card with color: green (<1.5, steady), amber (1.5-3.0, moderate), red (>3.0, reactive).


## Page-Level Structure

### Layout

RS is a tabbed dashboard with 3 primary tabs, a ticker selector, and a help button.

```
+----------------------------------------------------------------+
|  Retail Sentiment                [Auto-refresh v]  [Settings]   |
|----------------------------------------------------------------|
|  [Overview *] [Evidence] [Insights]                             |
|----------------------------------------------------------------|
|  [All] [AAPL *] [TSLA] [NVDA] [GME]  [Import Portfolio] [+ Add]|
|----------------------------------------------------------------|
|  AAPL - Apple Inc.  ·  Last updated: 2 min ago                  |
|                                                                 |
|                    (active tab content)                          |
|                                                                 |
|                                                    [?]          |
+----------------------------------------------------------------+
```

### Page Header

| Element | Detail |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Retail Sentiment" -- `text-xl font-semibold text-[--color-text-primary]`, left-aligned, `pl-6` |
| Auto-refresh dropdown | Right of header; options: Off / 30 min / 1 hr; `text-sm text-[--color-text-secondary]` |
| Settings button | Right of header, `pr-6`; outline style matching other departments; opens Settings panel |

### Tab Bar

| Element | Detail |
|---|---|
| Container | `flex items-center gap-1 px-6 bg-[--color-bg-base] border-b border-[--color-border-subtle]` |
| Tab | `px-4 py-2.5 text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:text-[--color-text-primary]`; active: `text-[--color-text-primary] font-medium border-b-2 border-[--color-text-primary]` |
| Default active tab | Overview |

### Ticker Selector

| Element | Detail |
|---|---|
| Container | `flex items-center gap-2 px-6 py-2 border-b border-[--color-border-subtle] overflow-x-auto` |
| Ticker pill | `px-3 py-1 rounded-full text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] border border-[--color-border-subtle]`; active: `bg-[--color-surface-active] text-[--color-text-primary] font-medium` |
| "All" pill | First position. When active, Overview shows multi-ticker heat map instead of single-ticker tiered layout |
| "Import from Portfolio" button | `text-sm text-[--color-accent-primary]`; imports all tickers from Portfolio page, skips duplicates; confirmation toast: "Added N tickers from Portfolio (M already monitored, skipped)" |
| "+ Add" pill | Last position; `text-sm text-[--color-accent-primary] border border-dashed border-[--color-accent-primary]`; opens search popover |
| Remove ticker | Hover pill to reveal `x` (12px); click removes from watchlist |
| Large watchlist warning | When adding the 21st ticker, amber toast: "Large watchlists increase LLM classification costs. Current estimated cost per refresh: $X.XX" |

### Ticker Header

| Element | Detail |
|---|---|
| Ticker symbol | `text-lg font-semibold text-[--color-text-primary]` |
| Company name | `text-base text-[--color-text-secondary]`, after em dash |
| Last updated | `text-sm text-[--color-text-tertiary]` |
| Refresh button | Inline `rotate-cw` icon (14px); spins during refresh |

### Help Button (Metrics Deep Dive)

| Element | Detail |
|---|---|
| Position | Fixed, bottom-right corner, `bottom-4 right-4` |
| Style | `w-8 h-8 rounded-full bg-[--color-bg-elevated] border border-[--color-border-subtle] shadow-sm` |
| Icon | `?` character, `text-sm text-[--color-text-secondary]` |
| Action | Opens the Metrics Deep Dive panel as a full-height drawer from the right (width: 480px) |
| Panel content | Educational content explaining each metric: formula, data source, chart type, interpretation guide, caveats. Scrollable. Close button at top-right. |


## Overview Tab

### Single Ticker View (specific ticker selected)

**Headline Tier:** 4 large metric cards in a `grid-cols-4` layout. These are the first-check metrics:

| Card | Large Value | Status Label |
|---|---|---|
| Sentiment Score | Score value colored by sentiment (green/red/gray) | "Positive" / "Neutral" / "Negative" |
| Momentum (5D) | Momentum value colored by direction | "Improving" / "Flat" / "Deteriorating" |
| Divergence | Divergence z-score | "Panic signal" / "Stealth recovery" / "No signal" |
| Cross-Source Agreement | "N/N" count | "All sources agree" / "Majority agree" / "Sources split" |

Card style: `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4`. Section label at top (`text-xs uppercase`), large value below (`text-2xl font-semibold`), status bar or label at bottom.

**Compact Tier:** 8 smaller metric cards in a `grid-cols-4` layout (2 rows of 4). These are the detail metrics:

| Row 1 | Row 2 |
|---|---|
| Buzz Volume | Short Interest Pressure |
| Bull/Bear Ratio | Narrative Concentration |
| Social Velocity | Institutional-Retail Gap |
| Put/Call Ratio | Event Sensitivity |

Card style: smaller than headline -- `bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-md] p-3`. Section label (`text-xs`), medium value (`text-lg font-medium`), sub-label (`text-xs text-[--color-text-tertiary]`).

**Charts Section:** Below the metric tiers.

1. *Sentiment vs Price overlay* -- Dual-axis line chart. Left axis: sentiment score (-1 to +1, blue line). Right axis: price change % (green line). Time period selector: 7D / 30D / 90D. Chart.js with `y` and `y1` axes.

2. *Buzz Volume bars* -- Bar chart with 30-day MA line. Color coding: blue (normal), amber (elevated), red (spike).

3. *Momentum area chart* -- Area chart with green fill above zero, red fill below zero.

Charts in a vertical stack, each in its own card container.

### All Tickers View ("All" selected)

**Multi-Ticker Heat Map:** Matrix grid with tickers as rows, key metrics as columns. Cell color encodes the metric state (green/amber/red/gray). Columns: Sentiment, Momentum, Divergence, Cross-Source, Buzz, Bull/Bear Ratio.

Each row also shows: ticker symbol, company name (truncated), sparkline of sentiment trend (last 7 days), active signal count badge.

Clicking a ticker row switches to that ticker's single-ticker view.

**Summary cards above the heat map:** Total tickers monitored, tickers with active signals, overall market mood (average sentiment across watchlist).


## Evidence Tab

### Metric Filter Bar

Dropdown or pill selector at the top. Options: All Metrics + each of the 12 individual metrics. Default: "Sentiment Score." Selecting a metric filters the evidence feed to show only items that contributed to that metric's value.

### Score Impact Decomposition

Horizontal bar chart showing how each evidence item shifts the selected metric's composite score. Baseline on left, each item adds (green bar segment) or subtracts (red bar segment), final composite on right.

Only shown when a specific metric is selected (hidden in "All Metrics" view).

### Evidence Feed

Reverse-chronological list of evidence items for the selected ticker and metric. Each item:

| Element | Detail |
|---|---|
| Source badge | Colored pill: provider name (e.g., "EODHD News", "X/Twitter", "FMP Social") |
| Headline/text | Truncated to 2 lines, expandable on click |
| Classification badge | Bullish (green) / Bearish (red) / Neutral (gray) |
| Impact value | Quantified impact on the selected metric (e.g., "+0.13") |
| Engagement metrics | For social posts: likes, retweets, replies. For news: source publication name |
| Timestamp | Relative time ("2h ago") or absolute date |

Pagination: 20 items per page, "Load more" at bottom.

In "All" ticker mode: evidence grouped by ticker with collapsible headers.


## Insights Tab

### Active Signals Section

Cards for metrics currently in a notable state. Each card:

| Element | Detail |
|---|---|
| Signal name | Metric name + signal type (e.g., "Divergence -- Panic Signal") |
| What's happening | One-line description of the current reading |
| Why it matters | One-line explanation of historical significance |
| Historical hit rate | e.g., "72% of similar signals preceded a reversal within 5 days" |
| Suggested interpretation | Actionable framing (not investment advice) |
| Color | Red card border for bearish signals, green for bullish, amber for caution |

If no signals active: muted message "No active signals -- all metrics within normal range."

Signal trigger thresholds (all user-configurable in Settings):
- Divergence z-score > 2.0 or < -2.0
- Momentum crossover (sign change)
- Buzz spike > 1.5x average
- Social velocity > 100% day-over-day
- Cross-source disagreement
- Short interest > 10% of float
- Institutional-retail gap > 0.5
- Put/call ratio > 1.2 or < 0.5
- Narrative concentration > 60%
- Event sensitivity > 3.0

### Narrative Synthesis

LLM-generated paragraph tying active signals together. Updated whenever the signal set changes. Shows LLM model used and timestamp. If no signals active, shows a brief "quiet market" summary for the selected ticker.

### Reliability Matrix

Bubble scatter chart (Chart.js). X-axis: predictive strength (0-10). Y-axis: timeliness (0-10). Bubble size: current data volume for that metric. All 12 metrics plotted.

Static reference positions (metric characteristics, not dynamic data):

| Metric | Predictive Strength | Timeliness |
|---|---|---|
| Divergence | 8 | 6 |
| Cross-Source Agreement | 9 | 5 |
| Momentum | 7 | 8 |
| Sentiment Score | 6 | 5 |
| Bull/Bear Ratio | 5 | 4 |
| Buzz Volume | 3 | 7 |
| Put/Call Ratio | 7 | 6 |
| Short Interest | 6 | 3 |
| Institutional-Retail Gap | 7 | 4 |
| Social Velocity | 4 | 9 |
| Narrative Concentration | 5 | 5 |
| Event Sensitivity | 4 | 3 |

Hovering a bubble shows metric name and current value.


## Metrics Deep Dive Panel

Opened by the `?` button at bottom-right. Full-height drawer from the right, 480px wide. Scrollable.

For each of the 12 metrics:
- Name and category (Mood / Attention / Signals)
- Formula with explanation of each variable
- Data source(s)
- Chart type used and why
- Interpretation guide: what high/low values mean
- Caveats and limitations
- Cross-reference: which other metrics complement this one

Close button at top-right of the drawer.


## Data Pipeline

### Data Requirements

**Basic (department disabled without these):**

| Requirement | What It Enables |
|---|---|
| Sentiment scores per ticker (pre-computed daily) | Metrics 1, 3, 5 |
| News articles with ticker association | NLP classification, evidence feed |
| Historical stock prices | Divergence (price component), event sensitivity |

**Advanced (features degrade gracefully if missing):**

| Requirement | What It Enables | Without It |
|---|---|---|
| Social media post text + engagement metrics | Engagement-weighted sentiment, bull/bear ratio, social velocity | Metrics 4, 6 show "No social data configured" and are grayed out |
| Cross-platform social sentiment | Cross-source agreement (3-source) | Agreement uses only available sources (e.g., 2/2) |
| Options data (put/call volume) | Put/call ratio | Metric 8 disabled |
| Short interest data | Short interest pressure | Metric 9 disabled |
| Analyst ratings/consensus | Institutional-retail gap | Metric 11 disabled |
| Word/narrative weights | Narrative concentration | Metric 10 disabled |

The setup wizard checks these requirements against configured providers and informs the user which metrics are available. Disabled metrics appear grayed out with a note explaining which provider capability is needed.

### Provider-Agnostic Fetch Rates

Fetch rates are defined by data type, not by provider name. The data provider system resolves which configured provider fulfills each type at runtime.

| Data Type | Interval |
|---|---|
| Sentiment scores (pre-computed) | Daily |
| News articles (raw text) | Hourly |
| Word/narrative weights | Daily |
| Social media post volume | Hourly |
| Social media post text (for NLP) | Hourly |
| Cross-platform social sentiment | Hourly |
| Options data (put/call) | Daily |
| Short interest | Daily |
| Analyst ratings/consensus | On change |
| Historical prices (for divergence) | Auto-refresh interval |

### NLP Classification Pipeline

**Batch LLM classification:** Raw articles and social posts are bundled (configurable batch size, default 30 items per call) and classified in a single LLM call.

**Prompt template** (`packages/core/src/openlia/prompts/retail_sentiment_classify.yaml`):
- System context: financial sentiment classifier role
- Input: JSON array of items, each with `id`, `source`, `text`, `engagement_metrics`
- Required output schema (strict): JSON array where each item has:
  - `id`: string (matching input)
  - `classification`: enum ("bullish" | "bearish" | "neutral")
  - `confidence`: float (0-1)
  - `key_phrases`: array of strings (phrases that drove the classification)
- No extra fields, no prose outside the JSON structure

**Error handling:** If the response doesn't match the schema, retry once. If still malformed, fall back to neutral classification for unparseable items and log the error.

**Engagement weighting:** After classification, each item's contribution to the daily composite is weighted by engagement metrics. A tweet with 2,000 likes contributes more than one with 5 likes. Reply-to-like ratio above 0.3 flags controversial posts.

### Metric Computation

Python metrics engine (Pandas-based) computes all 12 metrics per ticker per day (or per hour for intraday metrics). Cross-source agreement checked when multiple sources are available.

### Insights Generation

Separate LLM call from NLP classification. Triggered when the active signal set changes. Prompt template (`retail_sentiment_insights.yaml`) receives the current signal states and generates a narrative synthesis paragraph.


## Settings Panel

Collapsible drawer or modal, same pattern as MR.

### Global Settings

| Setting | Type | Default |
|---|---|---|
| Auto-refresh interval | Dropdown: Off / 30 min / 1 hr | 1 hr |
| NLP classification model | Dropdown (user's configured LLMs) | Default LLM |
| Batch size for NLP | Numeric input | 30 |
| Cross-source weights | Three numeric inputs (sum to 100%) | Financial 40% / Social 35% / Cross-platform 25% |
| Estimated cost per refresh | Display only (computed) | -- |

### Metric Settings

| Setting | Type | Default |
|---|---|---|
| Divergence z-score threshold | Numeric input | 2.0 |
| Buzz spike multiplier | Numeric input | 1.5x |
| Momentum window | Dropdown: 3D / 5D / 10D | 5D |
| Short interest squeeze threshold | Numeric input | 10% |
| Institutional gap significance | Numeric input | 0.5 |
| Put/call bullish/bearish thresholds | Two numeric inputs | 0.7 / 1.0 |
| Narrative concentration fragility threshold | Numeric input | 60% |
| Event sensitivity reactivity threshold | Numeric input | 3.0 |

### Per-Metric Toggles

List of all 12 metrics, each with an on/off toggle. If a metric's data requirement isn't met by configured providers, it shows as disabled with a note (e.g., "Requires options data -- configure a provider with options support"). Users can also manually hide metrics they don't want to see.

### Watchlist Management

- Current watchlist with remove buttons
- "Import from Portfolio" button
- "+ Add Ticker" search


## Visual Design System

Same OpenLIA design system as all other departments (CSS variables, Tailwind utilities).

### Color Semantics

| Color | Semantic Role | CSS Variable or Hex |
|---|---|---|
| Green | Bullish, positive, improving, recovery | `--color-feedback-success` / `#639922` (badge: `#EAF3DE` bg, `#3B6D11` text) |
| Red | Bearish, negative, deteriorating, panic | `--color-feedback-error` / `#E24B4A` (badge: `#FCEBEB` bg, `#A32D2D` text) |
| Amber | Elevated buzz, caution, notable gap | `#EF9F27` (badge: `#FAEEDA` bg, `#854F0B` text) |
| Blue | Sentiment line, informational | `#378ADD` (badge: `#E6F1FB` bg, `#0C447C` text) |
| Purple | Composite, cross-source agreement | `#7F77DD` (badge: `#EEEDFE` bg, `#3C3489` text) |
| Gray | Neutral, no signal, insufficient data | `--color-text-tertiary` |

### Shared Components (reused from other departments)

| Component | Pattern |
|---|---|
| Status badge | `inline-flex gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full` with dot |
| Card hierarchy | Card / sub-card / colored callout (3 levels, same as MR) |
| Typography scale | Section labels (11px uppercase), body (13px), metric values (18-24px) |

### RS-Specific Components

| Component | Used In |
|---|---|
| Gauge arc (HTML Canvas) | Overview headline tier (sentiment + momentum) |
| Heat map matrix | Overview "All" view |
| Score impact bar | Evidence tab decomposition |
| Reliability bubble scatter | Insights tab |
| Word cloud / treemap | Narrative concentration detail |
| Evidence item row | Evidence tab feed |
| Signal alert card | Insights tab active signals |


## States

| State | Visual Treatment |
|---|---|
| Empty watchlist | Full-page empty state: `Eye` icon (40px) + "Nothing to monitor yet" + "Add a ticker to start tracking retail sentiment" + accent "Add Ticker" button |
| Loading (initial) | Skeleton placeholders for metric cards and charts |
| Loading (refresh) | Subtle loading indicator; existing data remains visible |
| Data available | Full dashboard rendered |
| NLP classification running | Pulsing indicator on header; "Classifying N items..." label |
| Stale data (>staleness threshold) | Amber timestamp: "Data is N hours old" |
| Metric disabled (missing data) | Card grayed out with note: "Requires [capability] -- configure a provider" |
| Cold start (event sensitivity) | Card shows "Insufficient data (N/30 days collected)" with progress indicator |
| Error | Inline error below affected section + retry link |


## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Full layout; 4-column headline tier, 4-column compact tier, charts full width |
| Tablet (768-1024px) | 2-column tiers; charts full width; ticker pills wrap |
| Mobile (<768px) | Single column; all cards stacked; charts reduced height; ticker pills scroll horizontally; Metrics Deep Dive drawer becomes full-screen overlay |


## Integration with OpenLIA Architecture

### Core Layer (`packages/core/`)

- `departments/retail_sentiment.py` -- Department class. No HTTP dependencies.
- `departments/retail_sentiment/metrics.py` -- Computation for all 12 metrics (Pandas-based).
- `departments/retail_sentiment/classifier.py` -- Batch NLP classification logic: prompt building, response parsing, retries, fallback.
- `departments/retail_sentiment/schemas.py` -- Pydantic models for metric data, evidence items, NLP classification results, insight signals.
- `prompts/retail_sentiment_classify.yaml` -- Prompt template for batch NLP classification with strict JSON output schema.
- `prompts/retail_sentiment_insights.yaml` -- Prompt template for narrative synthesis generation.

### Server Layer (`packages/server/`)

- `routes/retail_sentiment.py` -- REST endpoints: GET metrics per ticker, GET evidence feed, GET active signals, POST trigger refresh, GET/PUT settings.
- `services/retail_sentiment.py` -- Orchestration: scheduled data fetching, NLP batch calls, metric computation, signal detection, insight generation.
- Background scheduler: manages periodic data ingestion and NLP classification based on configured refresh interval.

### Frontend (`frontend/`)

- `pages/RetailSentiment.tsx` -- Page component with tab navigation (Overview / Evidence / Insights).
- `pages/RetailSentiment/OverviewTab.tsx` -- Tiered metric layout + charts.
- `pages/RetailSentiment/EvidenceTab.tsx` -- Metric-filtered evidence feed + impact decomposition.
- `pages/RetailSentiment/InsightsTab.tsx` -- Active signals + narrative synthesis + reliability matrix.
- `pages/RetailSentiment/MetricsDeepDive.tsx` -- Help panel (drawer).
- `components/RetailSentiment/` -- MetricCard, GaugeArc, HeatMap, ScoreImpactBar, ReliabilityScatter, EvidenceItem, SignalCard, WordCloud.


## Non-Goals (v1)

- Chat interface or conversational interaction
- Report generation, PDF/DOCX export
- Real-time streaming (SSE) -- polling at configured interval is sufficient
- Backtesting module for validating metric thresholds against historical returns
- Intraday sentiment resolution below hourly granularity
- Alert/notification system (Slack, email, Telegram) for signal triggers
- Taiwan market or non-English NLP classification


## Open Questions

1. **X API v2 access and cost:** X API access tiers vary significantly. The Basic tier ($100/month) limits tweet pulls. Need to verify which tier is required for the hourly volume the dashboard needs, and whether the user can configure their own API key.
2. **FMP social sentiment endpoint availability:** The `/api/v4/historical/social-sentiment` endpoint may require a specific FMP plan. Need to verify during implementation.
3. **NLP classification accuracy:** Batch classification of 30 items per call may reduce accuracy vs per-item classification. Need to test and potentially adjust batch size or add a confidence threshold below which items are re-classified individually.
4. **Reliability matrix calibration:** The predictive strength and timeliness scores are estimated from academic literature. Should these be calibrated with actual backtesting data in a future version?
5. **Engagement weighting formula:** The exact formula for converting likes/retweets/follower count into a contribution weight needs to be defined during implementation. The design doc suggests it but doesn't specify the function.
