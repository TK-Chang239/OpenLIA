# Morning Briefing Style Guide

Style guide for LLM-generated morning briefing reports — daily market intelligence summaries delivered on a user-configured schedule, covering macro developments, regional news, market moves, sector activity, and individual stock events. Written to match the quality, density, and structure of bulge bracket morning notes (Goldman Sachs "Global Markets Daily", J.P. Morgan "Markets at a Glance", Morgan Stanley "Morning Comment", Citi "Morning Call").


## 1. Overall Writing Style

### Shared Conventions

Number formatting, currency/unit conventions, table formatting, and chart conventions follow the same rules defined in the Stock Update Style Guide (Section 1: Number Formatting and Citation, Section 3: Data Presentation Rules). Those rules apply identically here and are not repeated.

### Tone and Voice

- Urgent and time-efficient. The morning briefing is consumed in 5-10 minutes before the market opens. Every sentence must respect the reader's time. If a sentence does not help the reader make a decision today, cut it.
- Declarative, not speculative. State what happened, cite the figure, explain why it matters. Do not hedge with "could potentially impact" — say what it implies and let the data speak.
- Market-aware at all times. Every development is framed through the lens of "what does this mean for asset prices?" A political event is not reported as general news — it is reported as a catalyst that moved or will move specific markets.
- Consistent daily voice. The reader builds a habit around these reports. The structure, tone, and density should be nearly identical day to day. Surprise the reader with information, not with format changes.
- Neutral stance. Unlike earnings or equity research reports, the morning briefing does not advocate a position. It informs. Present both sides of a debate ("hawks argue X; doves counter with Y") and let the reader form their own view.

### Sentence Structure

- Front-load the market implication. "US 10Y yields rose 8bps to 4.52% after CPI surprised to the upside" — not "CPI came in higher than expected, which caused yields to rise."
- Use the overnight scaffold: "[Asset] [moved direction] [by how much] to [level] on [driver]." This is the fundamental unit of morning briefing prose. Examples: "S&P 500 futures fell 0.8% to 5,185 on the hotter CPI print", "USD/JPY rose 0.6% to 153.80 as the BOJ held rates steady."
- Keep bullets to one sentence each in summary sections. Two sentences maximum when the second adds essential context.
- Use numbered lists for sequential events: "(1) BOJ held rates at 0.25%; (2) Governor Ueda signaled patience on further hikes; (3) JPY weakened 0.4% against USD in immediate aftermath."
- Time-stamp everything. The reader needs to know when something happened relative to their market. Use timezone-aware references: "overnight", "in Asian trading", "European morning", "after the US close", with specific times for scheduled events.

### Transitions and Connectors

All transitions from the Stock Update Style Guide apply. Additional transitions specific to morning briefings:

- "Overnight," or "In Asian trading," to establish temporal context
- "The key event today is..." to flag the most important upcoming catalyst
- "This follows yesterday's..." to connect consecutive-day developments
- "Markets are pricing in..." to translate price action into expectations
- "The read-through for [asset/sector] is..." to connect a macro event to a specific market
- "Consensus expects..." before data releases to set the bar
- "The risk heading into [event] is..." to frame upcoming binary outcomes

### What to Avoid

All items from the Stock Update Style Guide (Section 1: What to Avoid) apply. Additional items specific to morning briefings:

- Narrative storytelling. The morning briefing is not a newspaper article. Do not build dramatic tension or use chronological narrative. Lead with the conclusion, support with data.
- Stale news. If a development was covered in the prior day's briefing and nothing new has happened, do not repeat it. State "no update" and move on.
- Opinion disguised as analysis. The morning briefing informs — it does not recommend. "The CPI print suggests the Fed will delay cuts" is analysis. "You should buy bonds ahead of the Fed meeting" is a recommendation and does not belong here.
- Overloading quiet days. Not every day has major news. On quiet days, the briefing should be shorter, not padded. A brief "Markets are quiet ahead of tomorrow's FOMC decision" is more valuable than three paragraphs of filler.
- Burying the calendar. Upcoming events are as important as what already happened. The Upcoming Preview section is not an afterthought.
- Timezone ambiguity. Never say "this morning" or "tonight" without specifying the timezone and market context. "In European morning trading" or "after the US close" are clear; "this morning" is not.


## 2. Per-Section Guidelines

### 2.1 Executive Summary

**Purpose:** Give the reader the full picture in 60 seconds. A reader who stops after this section should know the overnight direction, the key driver, the biggest risk, and what to watch today.

**Structure:** A key finding block with the top-line market call (1 sentence: risk-on / risk-off / mixed, with the primary driver), followed by 4-6 bullet points ordered by market impact.

**Tone:** Maximum density, zero filler. Every word earns its place.

**Data integration:** Each bullet cites exactly 1-2 figures. The key finding block cites the dominant market move.

**Do:**
- Lead the key finding with the market regime: "Risk-off overnight as..."
- Order bullets by market impact, not by section order
- Cover at minimum: market direction + driver, top macro development, top single-name story (if any), today's key calendar event
- Use the overnight scaffold for market moves: "[Asset] [direction] [magnitude] on [driver]"

**Don't:**
- Start with "Good morning" or any greeting
- Include more than 6 bullets — this is a summary, not a section
- Repeat the same data point across multiple bullets
- Use vague characterizations: "markets were volatile" — say "S&P 500 futures swung in a 1.2% range overnight"

**Exemplar:**
"Risk-off overnight as January CPI of +0.4% MoM (vs +0.3% expected) pushed 10Y yields up 8bps to 4.52% and sent S&P 500 futures down 0.8%.

- US CPI surprised to the upside at +0.4% MoM, with core services ex-shelter running at the hottest pace since October; Fed funds futures now price only 2 cuts in 2026 vs 3 pre-print
- Nikkei fell 1.4% as USD/JPY strength pressured exporters; Hang Seng flat as China property stimulus offset global risk-off
- NVDA fell 2.3% after-hours despite an in-line Q4 beat, as Q1 gross margin guidance of 70.5% missed expectations of 71.2%
- Key event today: Fed Chair Powell's semi-annual testimony to the Senate Banking Committee at 10:00 AM ET — markets watching for any shift in the disinflation narrative post-CPI"


### 2.2 Global Macro

**Purpose:** Provide analytical context on the macroeconomic developments that are moving or will move markets.

**Structure:** Each user-configured topic gets a subsection with a bold topic label. Each subsection is 2-4 sentences. Metric cards for the 2-3 most impactful data points precede the text blocks.

**Tone:** Analytical and market-focused. Every macro development must be connected to its asset price implications.

**Data integration:** Economic data releases always use the triple comparison: actual vs consensus vs prior. Central bank actions cite the specific policy rate level and the vote split if available.

**Do:**
- For data releases, always show: actual, consensus, prior, and the market's immediate reaction
- For central bank actions, cite: rate decision, vote split, key forward guidance language, and the market reaction
- For geopolitical events, focus on the trade/sanctions/tariff implications and which assets or sectors are affected
- Connect macro events to specific asset price moves: "The hot CPI print pushed 10Y yields up 8bps and sent rate-sensitive sectors (XLU -1.2%, XLRE -0.9%) lower"
- On days with multiple data releases, rank by market impact and cover in that order

**Don't:**
- Report economic data without comparing to consensus
- Cover geopolitical developments without stating the market implication
- Include background explainers on what CPI or PMI measures — the reader is a professional investor
- Lead with the least important topic because it is first in the user's configured list

**Exemplar (data release):**
"**US CPI** — January CPI came in at +0.4% MoM (vs +0.3% expected, +0.3% prior), with core CPI at +0.3% (vs +0.2% expected). The overshoot was driven by shelter (+0.5% MoM) and transportation services (+1.0% MoM). Fed funds futures repriced aggressively, now implying only 38bps of cuts in 2026 vs 52bps pre-print. The 2Y yield jumped 11bps to 4.37%, the largest single-day move since December."

**Exemplar (geopolitical):**
"**US-China Trade** — The White House confirmed a new 25% tariff on Chinese semiconductor equipment exports, effective March 1. The scope is narrower than feared (excludes legacy chip equipment), but the immediate read-through is negative for ASML (-2.8% in Amsterdam) and Tokyo Electron (-3.1%). Chinese retaliatory measures are expected within the week; USTR has signaled willingness to negotiate exemptions for allied nations."


### 2.3 Country News

**Purpose:** Provide a region-by-region scan of the developments most relevant to the reader's configured countries.

**Structure:** Each country gets a subsection with the country name as a bold heading. 3-5 bullet points per country. A brief market snapshot (local index, currency, yield) precedes or follows the bullets.

**Tone:** Factual and concise. Country sections are scanned, not read deeply. Density is more important than narrative.

**Data integration:** Each country subsection includes: local equity index level and change, currency move vs USD, and 10Y government bond yield change. All figures include both absolute level and change.

**Do:**
- Lead each country with the most market-moving development, not the most "important" by news standards
- Include the local market snapshot (index, currency, yield) even on quiet days
- Distinguish policy signals from policy actions: "BOK signaled" vs "BOK cut rates by 25bps"
- Note if a development has read-through to other markets: "Taiwan's export orders data has read-through for global semiconductor demand"

**Don't:**
- Report domestic political news that has no market implication
- Write more than 5 bullets per country — the reader needs a scan, not a deep dive
- Omit the market snapshot for a configured country, even if there is no news
- Cover a country not on the user's configured list unless a development there has global significance (in which case, cover it in Global Macro)

**Exemplar:**
"**Taiwan**
- TAIEX rose 0.6% to 20,845, outperforming the region, led by TSMC (+1.1%) on renewed AI server order visibility
- March export orders rose 18.3% YoY (vs +15.2% expected), driven by ICT (+28% YoY); the fifth consecutive month above expectations
- TWD strengthened 0.2% to 30.42 vs USD; 10Y government bond yield flat at 1.45%
- CBC Governor Yang reiterated that rate policy remains data-dependent; no change expected at the June meeting
- TSMC's board approved a NT$100bn capex increase for advanced packaging capacity, confirming the CoWoS supply tightness narrative"


### 2.4 Market News

**Purpose:** Provide a structured overnight performance summary and analytical context for each asset class the reader follows.

**Structure:** Metric cards for headline levels at the top. Each configured market gets a subsection with a bold label. For 4+ markets, include an overnight performance summary table before the narrative subsections.

**Tone:** Data-dense and mechanical for the performance summary; analytical for the narrative.

**Data integration:** Every market subsection states: current level, session change (% or bps), the driver, and any key technical levels.

**Overnight performance table (if 4+ markets):**
- Columns: Asset, Level, Change, Change %, Driver (one phrase)
- Rows: one per configured market, plus major indices
- Directional formatting: green for positive, red for negative

**Do:**
- For fixed income: always include 2Y, 10Y, 30Y yields, the 2s10s spread, and credit spreads (IG/HY OAS) if data is available
- For FX: include major pairs relevant to the user's country list (e.g., if Taiwan is configured, include USD/TWD)
- For commodities: cite front-month futures, not spot, and note the contract month
- State the driver explicitly — not "oil rose on supply concerns" but "WTI rose 1.8% to $78.40 after an EIA inventory draw of -4.2m barrels (vs -1.5m expected)"
- Note technical levels when an asset is near a significant support/resistance or moving average

**Don't:**
- List figures without the driver — the numbers alone are available on any terminal
- Speculate on where an asset is "heading" — state what happened and what the positioning data shows
- Use inconsistent units across markets (always bps for yields, % for equities and commodities, pips or % for FX)

**Exemplar (Fixed Income):**
"**Bonds / Fixed Income** — Yields rose across the curve after the CPI upside surprise. The 10Y climbed 8bps to 4.52%, the highest since November. The 2Y rose 11bps to 4.37%, steepening the 2s10s spread to +15bps from +8bps. IG credit spreads widened 3bps to OAS +92; HY widened 8bps to OAS +318. The move was primarily real-rate driven — 10Y TIPS breakevens were roughly flat at 2.35%, suggesting markets view the inflation overshoot as supply-side rather than demand-driven."


### 2.5 Sector News

**Purpose:** Surface the most actionable sector-level developments and contextualize relative performance.

**Structure:** Each configured sector gets a subsection with the sector name as a bold heading. 3-5 sentences per sector. If covering 3+ sectors, include a sector performance comparison table.

**Sector performance table (if 3+ sectors):**
- Columns: Sector, ETF/Index, Session Change, WTD Change, Primary Driver
- Directional formatting on change columns

**Tone:** Concise and actionable. Focus on what changed and what it means for positioning.

**Do:**
- Lead each sector with the most impactful development: regulatory action > M&A > earnings cluster > analyst calls > price action
- Cite the sector ETF or index performance relative to the broad market: "XLF -0.4% vs SPY -0.8%, outperforming by 40bps"
- Note earnings clusters: "4 of the top 10 semiconductor names report this week — see Upcoming Preview for dates"
- Flag notable analyst calls with the firm name and the specific action: "Goldman upgraded the European banks sector to Overweight, citing NII resilience"

**Don't:**
- List individual company moves in the Sector section — those belong in Stock News
- Cover sectors the user has not configured unless a development has broad market significance
- Write more than 5 sentences per sector — this section is a scan, not analysis

**Exemplar:**
"**Semiconductors** — SOX index rose 0.9% vs S&P flat, extending its outperformance to 3.2% WTD. The primary driver was TSMC's capex increase announcement (see Taiwan under Country News), which reinforced the advanced packaging capacity narrative. Morgan Stanley upgraded the sector to Overweight, citing 'underappreciated AI inference demand driving a second wave of semi capex'. Notable: ASML reports Thursday pre-market; consensus expects EUR 8.2bn in orders. Downside risk is the new US-China semiconductor equipment tariff (see Global Macro), though the scope appears narrower than the market initially feared."


### 2.6 Stock News

**Purpose:** Provide a per-name scan of material developments for each stock on the user's watchlist (Portfolio).

**Structure:** Each configured stock gets a subsection with the ticker and company name as a bold heading. 2-4 sentences per stock. Stocks with earnings releases get metric cards for EPS/revenue actual vs consensus and the after-hours move.

**Tone:** Fast and factual. The reader wants to know what happened and the immediate implication. Not a mini-research note.

**Do:**
- Lead with the most material development: earnings > guidance change > analyst action > corporate event > no news
- For earnings releases: always cite EPS and revenue actual vs consensus, the after-hours/pre-market move, and the single biggest driver of the beat or miss
- For analyst actions: cite the firm, the rating change, the new target, and the reasoning in one sentence
- If no material news: state "No material overnight developments" and note the next catalyst with its date
- Group "no news" names together at the end rather than interspersing them

**Don't:**
- Write a research note — the morning briefing covers what happened, not what the stock is worth
- Omit the stock price move on a day with news
- Cover stocks not on the user's configured list unless a development has sector-wide read-through (in which case, mention it in Sector News)
- Repeat information already covered in Sector News or Country News — reference the other section instead

**Exemplar (earnings):**
"**NVDA (NVIDIA)** — Q4 revenue of $22.1bn (+8% QoQ, +265% YoY) beat consensus of $20.6bn by 7%. Adj. EPS of $5.16 beat by 4%. Data center revenue of $18.4bn was the standout. However, Q1 gross margin guidance of 70.5% missed the 71.2% consensus, driving a 2.3% after-hours decline on 3.1x average volume. The margin miss appears driven by Blackwell ramp costs; management expects normalization by Q3."

**Exemplar (no news):**
"**AAPL (Apple)** — No material overnight developments. Next catalyst: Q2 earnings on May 1 (consensus: EPS $1.58, revenue $94.2bn). Trading at 28.5x fwd P/E, in line with 5Y average."


### 2.7 Upcoming Preview

**Purpose:** Ensure the reader knows every market-moving event in the next 1-3 trading days. This section is as important as what already happened.

**Structure:** Three subsections: (1) Today's Calendar as a table, (2) This Week Ahead as bullet points, (3) Portfolio Watch as a table (if Reference Portfolio is enabled).

**Today's Calendar table:**
- Columns: Time (with timezone), Event, Consensus/Expected, Prior, Significance (High/Medium/Low)
- Sort by time
- Bold rows for High significance events
- Include: economic data releases, central bank speakers (with topic if known), earnings releases (with consensus EPS and revenue), major corporate events, geopolitical scheduled events

**Tone:** Purely informational. No analysis in the calendar table — let the data speak. Brief analytical context goes in the Week Ahead bullets only.

**Do:**
- Include the time and timezone for every scheduled event
- For economic data, show consensus estimate and prior reading
- For earnings, show consensus EPS and revenue
- For central bank speakers, note the topic and whether a Q&A is expected
- Flag binary risk events explicitly: "FOMC decision is a binary event — markets pricing 85% probability of hold"
- In Portfolio Watch, connect portfolio holdings to upcoming catalysts

**Don't:**
- Omit low-significance events from the table — the reader decides what matters to them
- Forget to include events from the user's configured countries (e.g., BOK rate decision if Korea is configured)
- List events without consensus or prior figures when they are available
- Omit the Portfolio Watch subsection when Reference Portfolio is enabled, even if no portfolio holdings have near-term catalysts (state "No portfolio holdings have scheduled catalysts in the next 5 trading days")

**Exemplar (Today's Calendar row):**
| 10:00 AM ET | Fed Chair Powell Senate Testimony | -- | -- | **High** |
| 10:00 AM ET | JOLTS Job Openings (Dec) | 8.75M | 8.10M | Medium |
| AMC | AMZN Q4 Earnings | EPS $1.48, Rev $187.3bn | -- | **High** |

**Exemplar (Week Ahead bullet):**
"Thursday: ECB rate decision (consensus: hold at 3.75%). The key watch is the updated staff projections — if the 2026 inflation forecast is revised below 2.0%, it strengthens the case for a June cut. EUR/USD and European bank equities are the primary instruments to watch."


## 3. Data Presentation Rules

### Shared Rules

Table formatting, chart conventions, actuals-vs-estimates presentation, and currency/unit conventions follow the Stock Update Style Guide (Section 3: Data Presentation Rules). Those rules apply identically here and are not repeated.

### Morning Briefing-Specific Table Types

**Overnight performance summary table (Section 2.4):**
- Columns: Asset, Level, Change, Change %, Driver
- Directional cell formatting: green for positive, red for negative
- One row per configured market plus major equity indices
- Sort by asset class grouping: equities, fixed income, FX, commodities, crypto

**Sector performance comparison table (Section 2.5):**
- Columns: Sector, ETF/Index, Session Change, WTD Change, Primary Driver
- Directional formatting on change columns
- Sort by session change (best to worst) to surface relative strength/weakness

**Today's Calendar table (Section 2.7):**
- Columns: Time, Event, Consensus/Expected, Prior, Significance
- Sort by time, ascending
- Bold row styling for High significance events
- Use "--" for fields where data is not applicable (e.g., no consensus for a Fed speech)

**Portfolio Watch table (Section 2.7):**
- Columns: Ticker, Event, Date, What to Watch
- Sort by date, ascending
- "What to Watch" is one phrase describing the key question (e.g., "Margin guidance after cost inflation commentary")

### Morning Briefing-Specific Charts

Charts are used sparingly in morning briefings — the report prioritizes text density and scannability over visualization. Include charts only when they convey information more efficiently than text.

- Overnight equity index heatmap: regional equity performance (Asia, Europe, US futures) as a color-coded grid, useful when covering 3+ regions
- Yield curve snapshot: US Treasury yield curve (1M to 30Y) with overlay showing prior-day curve for visual comparison of steepening/flattening
- Sector relative performance bar chart: horizontal bar chart showing session change by sector ETF, sorted best to worst, useful when covering 5+ sectors


## 4. Cover Page Conventions

### Shared Rules

Cover page layout conventions follow the Stock Update Style Guide (Section 4: Cover Page Conventions). The morning briefing cover follows the same structure with these adaptations:

- Title: "Morning Briefing"
- Subtitle: Full date (e.g., "Thursday, April 10, 2026")
- Schedule label: "Pre-Market" or "Post-Market" (or custom user label)
- Tagline: One sentence capturing the dominant overnight theme. Lead with the market direction and the driver: "Risk-off overnight as Treasury yields spike to 4.85% on hot CPI; Asia and Europe futures down 1-2%" — not "Markets had a mixed session."
- Key metrics: 6-8 headline market levels (S&P 500, Nasdaq, Dow, 10Y yield, VIX, DXY, WTI, Gold) with directional change indicators (%, bps)
- Stats panel: report date, schedule label, timezone, markets covered, coverage sections active, generation timestamp


## 5. Handling Dynamic Sections

### User-Configured Content

Unlike equity research or earnings reports that have a fixed subject (a single company), the morning briefing's content scope is configured by the user. The framework sections are fixed, but the topics within each section are dynamic.

**When a section has no configured topics (e.g., user unchecked "Sector News"):** The section is omitted entirely from the report. Do not generate placeholder content.

**When a section has configured topics but no material news:** Generate the section with a brief note: "No material developments overnight for the configured [markets/sectors/stocks]. Key upcoming catalyst: [next relevant event]."

**When a configured topic has sub-notes (user's detailed instructions):** Prioritize covering the specific angles the user requested. For example, if the user configured "War" under Global Macro with a note "Focus on Ukraine-Russia grain corridor and Red Sea shipping disruptions", prioritize those specific angles over general conflict coverage.

**Custom Sections:** If the user has configured custom sections, generate them after the standard sections. Each custom section follows the general morning briefing tone and conventions. The section description provided by the user serves as the instruction for what to cover.

### Report Length Calibration

Morning briefings should be concise enough for a 5-10 minute read. Approximate target lengths by section:

| Section | Target Length |
|---------|--------------|
| Executive Summary | 4-6 bullets, ~150 words |
| Global Macro | 2-4 sentences per topic, ~100-200 words per topic |
| Country News | 3-5 bullets per country, ~100-150 words per country |
| Market News | 3-5 sentences per market, ~100-150 words per market |
| Sector News | 3-5 sentences per sector, ~80-120 words per sector |
| Stock News | 2-4 sentences per stock, ~60-100 words per stock |
| Upcoming Preview | Calendar table + 3-5 week-ahead bullets, ~200-300 words total |

On quiet days with minimal developments, sections should be shorter than these targets, not padded. On heavy news days (FOMC, major earnings cluster, geopolitical shock), the Executive Summary and Global Macro sections may expand to 1.5x the target, but other sections should remain disciplined.
