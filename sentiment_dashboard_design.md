# Retail Sentiment Monitor Dashboard — Design & Logic

## Purpose

This document describes the design, data architecture, metric definitions, evidence pipeline, and visualization logic for a retail sentiment monitoring dashboard. The dashboard is built to track what retail investors are saying about specific stocks and topics, using data from EODHD financial APIs, the X (Twitter) API v2, and FMP Social Sentiment. It is designed to integrate into a Python-based multi-agent research stack as the output layer of a dedicated sentiment monitoring agent.

---

## Data Sources

### EODHD Financial APIs

Three endpoints feed the dashboard:

**`/api/sentiments`** — The primary sentiment data source. Returns daily aggregated sentiment per ticker with two key fields:
- `count`: number of news articles analyzed that day
- `normalized`: composite sentiment score scaled from -1 (extremely bearish) to +1 (extremely bullish)

EODHD's system analyzes news articles every minute from 10+ financial news sources, classifying mentions as positive or negative. The `normalized` score is the net ratio of positive to negative mentions. Data is grouped by ticker symbol and updated daily.

Example response structure:
```json
{
  "AAPL": [
    { "date": "2026-04-10", "count": 45, "normalized": 0.2835 },
    { "date": "2026-04-09", "count": 38, "normalized": 0.1920 }
  ]
}
```

**`/api/news`** — Raw news articles with titles, content, publication dates, and associated ticker symbols. Used for two purposes: (1) feeding articles into an LLM-based re-scoring pipeline for more nuanced sentiment classification than EODHD's built-in scoring, and (2) displaying evidence snapshots on the dashboard so users can trace a sentiment score back to its source material.

**`/api/news-word-weights`** — Returns a weighted list of the most significant words found in news articles about a ticker over a date range. Each word is scored by frequency and significance. This endpoint powers word cloud visualizations and narrative theme detection (e.g., tracking when "investigation" or "recall" overtakes "growth" or "revenue" in the discourse around a stock).

### X API v2

Two endpoints provide social media data:

**`/tweets/search/recent`** — Pulls tweets matching a cashtag query (e.g., `$TSLA`). Each tweet includes full `public_metrics` (likes, retweets, replies, quotes) which are used as engagement weights. High-engagement tweets shift the sentiment score more than low-engagement tweets. The `text` field is passed through an NLP classifier (Claude API or a local model) to assign a bullish/bearish/neutral label per tweet.

**`/tweets/counts/recent`** — Returns hourly tweet volume counts for a cashtag without pulling full tweet text. This is the most efficient way to compute buzz volume and social velocity at intraday resolution. EODHD's sentiment data is daily; the X counts endpoint fills the intraday gap.

### FMP Social Sentiment

**`/api/v4/historical/social-sentiment`** — Tracks mentions and sentiment across StockTwits, Reddit, Yahoo, and Twitter simultaneously. Returns hourly data points including:
- `stocktwitsPosts`, `twitterPosts`: post counts per platform
- `stocktwitsComments`, `twitterComments`: comment/reply counts
- `stocktwitsLikes`, `twitterLikes`: engagement counts
- `sentiment`: overall percentage of positive activity
- Absolute index (how much people are talking) and relative index (relative to previous day)

This provides cross-platform validation — when EODHD news sentiment, X social sentiment, and FMP social sentiment all agree, the signal is considered high-confidence.

---

## Dashboard Architecture

### Tab Structure

The dashboard is organized into five tabs, each serving a distinct analytical purpose:

1. **Overview** — At-a-glance health check. Shows metric summary cards, sentiment gauges, a 30-day sentiment-vs-price overlay chart, and a multi-ticker heat map. This is the default landing view.

2. **Metrics deep dive** — Detailed explanation and visualization of each individual metric. Includes formulas, chart types, and interpretive guidance. Designed for understanding *what* each metric measures and *how* it is calculated.

3. **Evidence snapshots** — Shows the raw evidence (news articles, tweets, word weights) that feed into the metrics. Demonstrates how adding or removing a single piece of evidence shifts the composite score. This makes the dashboard auditable.

4. **Insights & signals** — Translates metrics into actionable interpretations. Explains what each metric actually tells you in practical terms, and includes a reliability matrix scoring each metric on predictive strength and timeliness.

5. **Data architecture** — Documents the data pipeline from API calls through ingestion, NLP processing, metric computation, and dashboard rendering. Includes API field mappings and recommended chart types per metric.

### Ticker Selection

The overview tab includes a ticker selector with buttons for each watched stock. Switching tickers re-renders all overview charts and metric cards with that ticker's data. The ticker list is configurable and maps to the agent's watchlist.

---

## Metric Definitions

### 1. Sentiment Score (Normalized)

**What it measures:** The current market mood toward a stock, expressed as a single number.

**Formula:**
```
score = (positive_mentions - negative_mentions) / total_mentions
```

**Data source:** EODHD `/api/sentiments` → `normalized` field. For X API data, each tweet is classified by an NLP model and the daily average is computed.

**Range:** -1 (extremely bearish) to +1 (extremely bullish). A score near 0 means balanced opinion, not absence of opinion.

**Visualization:** Dual-axis line chart overlaying sentiment score against price change percentage. The overlay reveals divergences — when sentiment and price move in opposite directions, it often precedes a reversal.

**Interpretation caveats:** A +0.2 for AAPL (a stock with typically calm sentiment) is more significant than +0.2 for GME (a stock with naturally volatile sentiment). Always compare against the stock's own historical range, not across stocks.

### 2. Buzz Volume (Mention Count)

**What it measures:** How much people are talking about a stock, independent of whether they are bullish or bearish.

**Formula:**
```
buzz_ratio = count(mentions_today) / avg(mentions_over_30d)
```

The raw `count` from EODHD is normalized by dividing by the 30-day moving average. This makes buzz comparable across tickers — AAPL naturally has more mentions than PLTR, so raw counts mislead.

**Data source:** EODHD `/api/sentiments` → `count` field for news. X API `/tweets/counts/recent` → `tweet_count` for social. FMP → `stocktwitsPosts + twitterPosts` for cross-platform.

**Visualization:** Bar chart with color coding:
- Blue bars: volume at or below 30-day average (normal)
- Amber bars: volume 1x–1.5x average (elevated)
- Red bars: volume above 1.5x average (spike)

A dashed horizontal line marks the 30-day average for reference.

**What spikes mean:** Buzz spikes coincide with earnings announcements, product launches, regulatory news, or viral social media posts. High buzz predicts volatility (in either direction), not direction.

### 3. Sentiment Momentum (Rate of Change)

**What it measures:** Whether sentiment is improving or deteriorating, regardless of absolute level.

**Formula:**
```
momentum = SMA(sentiment, 5)_today - SMA(sentiment, 5)_yesterday
```

The 5-day simple moving average of the sentiment score is computed daily. Momentum is the daily change in this moving average. Using the SMA smooths out single-day noise.

**Visualization:** Area chart with dual-fill: green above zero (improving), red below zero (deteriorating). The fill makes the direction immediately obvious at a glance.

**Key insight:** A stock can have negative sentiment (-0.3) but positive momentum (sentiment was -0.5 yesterday). This means the mood is recovering. Momentum often leads price by 1–3 days because sentiment shifts before capital flows. This is the most useful leading indicator in the dashboard.

### 4. Bull/Bear Ratio

**What it measures:** The proportion of bullish versus bearish posts, independent of total volume.

**Formula:**
```
ratio = bullish_posts / (bullish_posts + bearish_posts)
```

Neutral posts are excluded from the calculation.

**Data source:** Derived from NLP classification of individual tweets (X API) and news articles (EODHD). FMP provides a pre-computed `sentiment` percentage field that serves as a cross-check.

**Visualization:** Stacked bar chart — green segment (bullish %) and red segment (bearish %) stacked to 100% per day. This immediately shows the proportion without needing to read numbers.

**Why it matters beyond sentiment score:** The ratio combined with buzz volume reveals conviction breadth:
- 90/10 ratio from 50 posts = concentrated enthusiasm (fragile, likely a few loud voices)
- 60/40 ratio from 5,000 posts = broad mild optimism (durable, widely held view)
- 50/50 ratio = genuine uncertainty or debate

### 5. Buzz-Sentiment Divergence

**What it measures:** When buzz volume and sentiment move in opposite directions — the most actionable signal for contrarian analysis.

**Formula:**
```
divergence = z_score(buzz) - z_score(sentiment)
```

Both buzz and sentiment are z-scored (standardized) against their own 30-day history. The divergence is the difference between these z-scores.

**Interpretation:**
- **High positive divergence (> 2.0):** Lots of talk but negative tone. This is panic — people are selling and talking about it. Historically a mean-reversion buying opportunity.
- **High negative divergence (< -2.0):** Silence but improving tone. Smart money may be quietly accumulating while the crowd looks away. A stealth recovery signal.
- **Near zero:** Buzz and sentiment are moving together. No special signal.

**Visualization:** Bar chart where bars are colored by significance:
- Red bars: divergence > 1.0 (panic signal)
- Green bars: divergence < -1.0 (stealth recovery)
- Gray bars: divergence between -1.0 and 1.0 (normal)

### 6. Social Velocity

**What it measures:** The acceleration of mentions — not just whether volume is high, but whether it is growing faster than yesterday.

**Formula:**
```
velocity = (buzz_today - buzz_yesterday) / buzz_yesterday
```

**Data source:** X API `/tweets/counts/recent` (hourly resolution for intraday velocity) or EODHD `count` (daily resolution).

**What it catches:** Velocity fires before buzz peaks. A stock might have normal volume today (100 mentions) but velocity is +150% (yesterday was 40 mentions). By the time buzz hits 500 mentions, the velocity signal already fired two days ago. This is useful for catching trends before they peak.

---

## Evidence Pipeline

### How Raw Evidence Becomes a Metric Score

Each data point in the dashboard traces back to a concrete source. The pipeline follows three stages:

**Stage 1: Ingestion**
- EODHD APIs are polled on a daily schedule (via Python scheduler or cron). The `/api/sentiments` endpoint returns pre-scored daily data. The `/api/news` endpoint returns raw articles for optional re-scoring.
- X API is polled hourly. The `/tweets/counts/recent` endpoint provides volume data without needing to pull full text. The `/tweets/search/recent` endpoint pulls individual tweets for NLP classification during high-activity windows.
- FMP Social Sentiment is polled hourly for cross-platform validation data.

**Stage 2: NLP Classification**
- EODHD provides pre-computed sentiment scores, so no additional NLP is strictly required for the primary signal. However, for higher-fidelity analysis, raw article text from `/api/news` can be re-scored through Claude (via the Anthropic API) or a local classifier.
- Tweets from the X API require NLP classification. Each tweet's `text` field is classified as bullish, bearish, or neutral. The `public_metrics` (likes, retweets, replies, quotes) serve as engagement weights — a tweet with 2,000 likes contributes more to the daily sentiment than a tweet with 5 likes.
- Reply-to-like ratio (`replies / likes`) above 0.3 flags controversial posts, distinguishing genuine debate from one-sided enthusiasm.

**Stage 3: Metric Computation**
- A Pandas-based metrics engine computes all six derived metrics (sentiment, buzz, momentum, ratio, divergence, velocity) from the ingested and classified data.
- Each metric is computed per ticker per day (or per hour for intraday metrics).
- Cross-source agreement is checked: when EODHD, X, and FMP all agree on direction, the combined score uses a weighted average (EODHD 40%, X 35%, FMP 25%).

### Evidence Traceability

The dashboard provides evidence snapshots showing the specific articles and tweets that contributed to each day's score. The "Evidence snapshots" tab shows:

1. The source (e.g., "Reuters via EODHD", "X API cashtag")
2. A summary of the content
3. Its classification (bullish/bearish/neutral)
4. Its quantified impact on the composite score (e.g., "+0.13 to daily sentiment")
5. The raw API field values (e.g., `normalized: 0.35, count: 220`)

This makes the dashboard auditable — a user can always ask "why is the score what it is?" and trace it back to source evidence.

### Score Impact Walkthrough

The dashboard includes a horizontal bar chart showing how each piece of evidence additively shifts the composite score. For example:

| Evidence | Impact |
|----------|--------|
| Baseline score | +0.22 |
| + Delivery beat (Reuters) | +0.13 |
| + NHTSA probe (Bloomberg) | -0.27 |
| + Bull tweet (FinTwit, 45K followers) | +0.02 |
| + Bear thread (analyst) | -0.03 |
| = Final composite | +0.07 |

This decomposition shows that the final score is not a black box — it is the sum of identifiable, traceable evidence contributions.

---

## Visualization Logic

### Chart Type Selection

Each metric maps to a specific chart type chosen for maximum readability:

| Metric | Chart Type | Why This Chart |
|--------|-----------|----------------|
| Sentiment score | Dual-axis line (sentiment + price) | Shows correlation and divergence between mood and market |
| Buzz volume | Bar chart with MA line | Bars make volume spikes visually obvious; MA provides baseline |
| Momentum | Area chart (green/red fill) | Fill color makes direction instantly visible without reading numbers |
| Bull/bear ratio | Stacked bar to 100% | Proportion is the point; stacking to 100% eliminates absolute volume |
| Divergence | Colored bar chart | Color encodes significance (red = panic, green = stealth recovery) |
| Social velocity | Not charted separately | Velocity is a derived trigger; surfaces as alerts, not continuous chart |
| Multi-ticker comparison | Bubble heat map | Matrix view (tickers × time) enables cross-stock comparison at a glance |
| Word themes | Word cloud / treemap | From EODHD `/api/news-word-weights`; reveals narrative shifts |
| Metric reliability | Bubble scatter | Axes are predictive strength and timeliness; bubble size = data volume |

### Gauge Displays

Two arc gauges sit at the top of the overview tab:
- **Sentiment gauge:** Maps the -1 to +1 sentiment score onto a 180° arc. Red on the left, amber in the middle, green on the right. The arc fill shows current position at a glance.
- **Momentum gauge:** Maps the -0.3 to +0.3 momentum range onto a similar arc. Shows whether sentiment is improving (right side) or deteriorating (left side).

Gauges are rendered via HTML Canvas to allow smooth gradient fills. They update when the ticker selection changes.

### Color System

Colors encode meaning consistently across all charts:
- **Blue (#378ADD):** Sentiment score line (neutral data channel)
- **Green (#639922):** Price, bullish bars, positive momentum fill, stealth recovery
- **Red (#E24B4A):** Bearish bars, negative momentum fill, panic divergence
- **Amber (#EF9F27):** Buzz volume bars (elevated but not directional), neutral zones
- **Purple (#7F77DD):** Combined/composite scores, cross-source agreement
- **Gray (#888780):** Neutral, baseline, insufficient data

Colors are applied through CSS variables and adapt to light/dark mode.

---

## Insights Framework

### What Each Metric Actually Tells You

The dashboard is designed to answer six distinct questions:

1. **"What is the current mood?"** → Sentiment score. But alone it lacks context — always compare against the stock's own historical range.

2. **"How much attention is there?"** → Buzz volume. High buzz alone predicts volatility, not direction. Low buzz with positive sentiment = quiet institutional conviction. High buzz with positive sentiment = potential FOMO/crowding.

3. **"Is the mood improving or worsening?"** → Momentum. The most useful leading indicator. Sentiment turning from -0.3 to -0.1 is still negative, but momentum is positive — the mood is recovering. This often leads price by 1-3 days.

4. **"How broad is the conviction?"** → Bull/bear ratio + buzz volume together. A 90/10 ratio from 50 posts is fragile. A 60/40 ratio from 5,000 posts is durable.

5. **"When should I be contrarian?"** → Divergence. When buzz spikes but sentiment falls, the crowd is panicking — often a buying opportunity. When buzz drops but sentiment rises, smart money is quietly accumulating.

6. **"How much should I trust this signal?"** → Cross-source agreement. When EODHD, X, and FMP all agree, the signal is 2-3x more reliable than any single source.

### Signal Reliability

Not all metrics are equally useful. The dashboard includes a reliability matrix scoring each metric on two dimensions:

- **Predictive strength (0-10):** Does this metric actually forecast price moves? Based on historical backtesting.
- **Timeliness (0-10):** How early does the signal fire before the price move?

Estimated scores based on academic literature and practitioner experience:

| Metric | Predictive Strength | Timeliness |
|--------|-------------------|------------|
| Divergence | 8 | 6 |
| Cross-source agreement | 9 | 5 |
| Momentum | 7 | 8 |
| Sentiment score | 6 | 5 |
| Bull/bear ratio | 5 | 4 |
| Buzz volume | 3 | 7 |

Divergence and cross-source agreement have the highest predictive strength. Momentum and buzz have the highest timeliness (earliest signals). No single metric excels on both dimensions — they complement each other.

---

## Integration with Agent Stack

### Agent Architecture

The sentiment monitoring agent operates as one of four specialized agents in the research stack:

```
┌──────────────────┐     ┌──────────────────┐
│  EODHD APIs      │────▶│  Ingestion Agent  │
│  /sentiments     │     │  (Python/schedule)│
│  /news           │     └────────┬─────────┘
│  /news-word-wts  │              │
└──────────────────┘              ▼
                          ┌──────────────────┐
┌──────────────────┐      │  NLP Classifier   │
│  X API v2        │─────▶│  (Claude API or   │
│  /search/recent  │      │   local model)    │
│  /counts/recent  │      └────────┬─────────┘
└──────────────────┘              │
                                  ▼
┌──────────────────┐      ┌──────────────────┐
│  FMP Social      │─────▶│  Metrics Engine   │
│  /social-sentiment│     │  (Pandas + numpy) │
└──────────────────┘      └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  Dashboard UI     │
                          │  (Streamlit/React)│
                          └──────────────────┘
```

### YAML Prompt Configuration

The sentiment agent's behavior is defined in a YAML file within the `prompts/` directory. Key configuration fields:

```yaml
agent: sentiment_monitor
watchlist:
  - TSLA.US
  - NVDA.US
  - AAPL.US
  - 2330.TW  # TSMC for Taiwan market coverage

scoring_weights:
  eodhd_news: 0.40
  x_social: 0.35
  fmp_social: 0.25

alert_thresholds:
  divergence_z_score: 2.0
  momentum_crossover: true
  buzz_spike_multiplier: 2.5

schedule:
  eodhd_poll: "daily 06:00 UTC"
  x_poll: "hourly"
  fmp_poll: "hourly"

output:
  format: "json"
  destination: "data/sentiment/"
  dashboard: "streamlit"
```

### Output Schema

The metrics engine outputs a JSON object per ticker per day that the dashboard consumes:

```json
{
  "ticker": "TSLA",
  "date": "2026-04-13",
  "sentiment_score": 0.35,
  "buzz_volume": 220,
  "buzz_ratio": 1.8,
  "momentum_5d": 0.042,
  "bull_bear_ratio": 0.68,
  "divergence_z": 1.2,
  "social_velocity": 0.45,
  "cross_source_agreement": true,
  "combined_weighted_score": 0.42,
  "evidence_summary": [
    {
      "source": "eodhd_news",
      "headline": "Tesla Q1 deliveries beat estimates",
      "classification": "bullish",
      "impact": 0.13
    }
  ]
}
```

---

## Future Enhancements

1. **Word cloud visualization** using EODHD `/api/news-word-weights` to show narrative themes and track how they shift over time.
2. **Intraday sentiment resolution** by combining X API hourly counts with live price data for real-time divergence detection.
3. **Backtesting module** to validate metric thresholds (e.g., "does buying when divergence > 2.0 actually yield positive returns over 5 days?").
4. **Taiwan market coverage** using EODHD's support for TWSE tickers (e.g., 2330.TW for TSMC) with Chinese-language NLP for local news sources.
5. **Alert system** that fires notifications (Slack, email, or Telegram) when key thresholds are breached (divergence spike, momentum crossover, buzz anomaly).
6. **Engagement-weighted scoring refinements** — further tuning of how X API `public_metrics` weight individual tweets, potentially using follower count tiers and account age as credibility filters.
