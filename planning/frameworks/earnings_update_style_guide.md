# Earnings Analysis Report Style Guide

Style guide for LLM-generated earnings analysis reports — structured post-earnings assessments that evaluate a company's quarterly results against consensus expectations, analyze the drivers, and update the investment thesis. Written to match the quality and conventions of bulge bracket sell-side earnings notes (Goldman Sachs, Morgan Stanley, J.P. Morgan, Citi).


## 1. Overall Writing Style

### Shared Conventions

Number formatting, currency/unit conventions, table formatting, chart conventions, and actuals-vs-estimates presentation follow the same rules defined in the Stock Update Style Guide (Section 1: Number Formatting and Citation, Section 3: Data Presentation Rules). Those rules apply identically here and are not repeated.

### Tone and Voice

- Reactive and time-sensitive. Earnings reports are event-driven — the analyst is delivering a verdict on fresh data, not building a thesis from scratch. Every sentence should reflect awareness that the reader wants to know "what just happened and what does it mean for my position."
- Lead with conclusions, support with data. The first sentence of every section should state the takeaway; supporting data follows. A reader who only reads opening sentences should get the full picture.
- Use "beat" and "miss" vocabulary freely but precisely. "Beat" means actual exceeded consensus or the analyst's own estimate. Always specify which benchmark: "beat consensus by 3.2%" or "came in 5% above our estimate."
- Quantify everything. Qualitative assessments ("strong quarter", "solid guidance") are only acceptable when immediately followed by the number: "a strong quarter with revenue 8% above consensus and EPS beating by $0.12."
- Maintain analytical distance from management narrative. Report what management said in indirect speech ("management expects", "the CEO noted"), then evaluate whether the data supports it. Do not parrot management talking points as conclusions.

### Sentence Structure

- Front-load the verdict in each sentence. "Revenue of $24.3bn beat consensus by 4.2%, driven by cloud services" — not "Cloud services contributed to revenue of $24.3bn, which beat consensus by 4.2%."
- Use the comparison scaffold pervasively: "actual figure (comparison to benchmark)." This is the fundamental unit of earnings analysis prose. Examples: "GM of 42.3% (+1.2ppts QoQ, +80bps above GSe)", "CapEx of $13.2bn (vs guidance midpoint of $12-14bn)."
- Keep sentences concise. Average 15-25 words. Longer sentences acceptable when presenting multi-part comparisons with semicolons.
- Use numbered takeaways for multi-topic analysis: "(1) IC substrate revenue grew 18% QoQ on AI demand; (2) BT substrate utilization held at 85%; (3) Management guided 1Q26 revenue down 12% QoQ due to seasonality."

### Transitions and Connectors

All transitions from the Stock Update Style Guide apply. Additional transitions specific to earnings reports:

- "The headline numbers mask..." to highlight a discrepancy between top-line results and underlying quality
- "Stripping out [one-time item]..." to normalize for non-recurring effects
- "The key debate heading into this print was..." to frame what the market was watching
- "Management addressed this directly, stating..." to introduce earnings call commentary
- "This quarter [strengthens/weakens] the thesis that..." to connect results to the investment case
- "The market's reaction suggests..." to interpret post-earnings price action

### What to Avoid

All items from the Stock Update Style Guide (Section 1: What to Avoid) apply. Additional items specific to earnings reports:

- Play-by-play recaps. Do not chronologically walk through the press release or prepared remarks. Organize by importance, not by source order.
- Double-counting. If a data point appears in the Key Financials table, do not restate the same number in prose unless adding new context (comparison, driver, implication).
- Anchoring to the wrong benchmark. If both the analyst's estimate and street consensus exist, specify which one the result is being compared to. Never say "beat estimates" without specifying whose.
- Treating management guidance as fact. Guidance is an input to the analysis, not the output. Evaluate it: is it conservative? Aggressive? What assumptions does it embed?
- Burying the miss. If the quarter was a miss, say so immediately. Do not lead with "results were mixed" when EPS missed by 15%.


## 2. Per-Section Guidelines

### 2.1 Quick Take

**Purpose:** Give the reader the full verdict in 10 seconds.

**Structure:** 1-3 sentences in a key finding block. Sentence 1: beat/miss/in-line verdict with the two most important figures. Sentence 2: the single biggest driver or surprise. Sentence 3 (optional): rating action and target price change if applicable.

**Tone:** Maximum conviction, maximum density. This is the most opinionated sentence in the report.

**Data integration:** Cite exactly 2-3 numbers — revenue vs consensus, EPS vs consensus, and one other key metric. No more.

**Do:**
- Lead with the verdict word ("beat", "missed", "in-line")
- State revenue and EPS vs consensus in the first sentence
- Include the investment action if the rating or target changes

**Don't:**
- Start with "Company X reported Q? results"
- Include more than 3 data points — this is a summary, not a table
- Hedge the verdict — pick a side

**Exemplar:**
"Revenue of $24.3bn and adj. EPS of $1.42 both beat consensus by 4% and 8% respectively, driven by better-than-expected cloud margins. Raising 12M TP to $185 (from $170) on higher 2026-27E earnings; maintain Buy."


### 2.2 Post-Earnings Market Reaction

**Purpose:** Document what happened in the market and why — separate the market's interpretation from the analyst's.

**Structure:** Metric cards for 3-4 headline reaction figures (stock price change, volume multiple, sector relative performance), followed by a text block interpreting the reaction.

**Tone:** Observational, not prescriptive. Report what the market did and hypothesize why, but do not claim the market is right or wrong.

**Data integration:** Post-earnings price move (specify after-hours or next-day open), volume as a multiple of the 20-day average, relative performance vs sector ETF or index, analyst rating changes within 24 hours.

**Do:**
- Specify the exact time frame of the price move (e.g., "after-hours", "at the next-day open")
- Compare volume to a specific baseline (20-day average)
- State what the market appears to be pricing in
- Note any disconnect between the results and the reaction (e.g., "beat but sold off")

**Don't:**
- Present the market reaction as validation of the results quality
- Omit the relative performance context
- Speculate beyond what the price action and volume data support

**Exemplar:**
"Shares fell 3.2% in after-hours trading despite the top- and bottom-line beat, on volume 2.8x the 20-day average. The sell-off appears driven by the 2H guidance cut, which overshadowed the quarterly outperformance. The stock underperformed the SOX index by 4.1ppts on the session."


### 2.3 Key Financials vs Consensus

**Purpose:** Present the scorecard — how did each major line item compare to expectations?

**Structure:** A structured comparison table as the primary element, followed by a brief Earnings Quality Notes text block.

**Table design:**
- Rows: Revenue, Gross Margin (%), Operating Income / OPM (%), EBITDA / EBITDA Margin (%), Adjusted EPS, FCF, plus 1-2 company-specific KPIs
- Columns: Actual, Consensus, Beat/Miss (%), Prior Quarter, QoQ (%), Year-Ago Quarter, YoY (%)
- Apply directional cell formatting (green for beats/positive changes, red for misses/negative changes)
- Show margin rows as percentages with ppt changes: "42.3% (+1.2ppts QoQ)"

**Earnings Quality Notes:** 2-4 sentences flagging:
- Non-recurring items and their impact on reported vs adjusted figures
- Significant non-GAAP adjustments (stock-based comp exclusion magnitude, restructuring charges)
- FCF-to-net-income conversion ratio (healthy >80%; flag if <60%)
- Unusual accrual or working capital items

**Do:**
- Include both QoQ and YoY comparisons for context
- Flag when adjusted and GAAP figures diverge significantly
- State which consensus source is used (Bloomberg, FactSet, or specify)

**Don't:**
- Present only the beat/miss without the absolute figures
- Omit the earnings quality assessment when there are material adjustments
- Mix currencies or units within the table


### 2.4 Operational Highlights and Drivers

**Purpose:** Explain the "why" behind the numbers — what drove the beats and misses?

**Structure:** Four subsections, each as bullet points:
- Beats and Positives (2-4 items): specific drivers with quantified contribution
- Misses and Negatives (2-3 items): with structural vs one-time assessment
- Watch Items (1-3 items): forward-looking signals not yet in numbers
- Segment/Geographic Breakdown: table with revenue and margin by segment

**Tone:** Analytical and specific. Every bullet must name a specific driver and quantify it.

**Data integration:** Each bullet cites at least one figure. Segment table shows revenue, growth rates, and margin for each segment.

**Do:**
- Distinguish structural drivers from one-time items explicitly ("one-time inventory benefit" vs "sustained demand improvement")
- Quantify contribution where possible: "AI server revenue contributed $2.1bn, up 42% YoY, accounting for 65% of the total revenue beat"
- In Watch Items, explain why the item matters for future quarters

**Don't:**
- List beats/misses without explaining the driver
- Use vague language: "strong performance in cloud" — specify what was strong and by how much
- Include more than 4 items per subsection — prioritize by materiality

**Exemplar (Beat item):**
"Cloud services revenue of $8.7bn (+31% YoY) beat consensus by 6%, driven by accelerating enterprise AI workload migration. Management noted new customer cohort growth of 23% QoQ, the fastest pace in 8 quarters."

**Exemplar (Watch Item):**
"Management disclosed a new partnership with [Company] for edge AI deployment, expected to generate revenue starting 2H26. No financial targets were provided, but the TAM opportunity could be material — we will monitor for sizing in the next call."


### 2.5 Forward Guidance

**Purpose:** Evaluate what management expects next and whether it is credible.

**Structure:** A guidance comparison table as the primary element, followed by a Guidance Quality Assessment text block.

**Table design:**
- Rows: Next Quarter Revenue, Next Quarter EPS, Full Year Revenue, Full Year GM, Full Year EPS, CapEx, other guided metrics
- Columns: New Guidance (range or midpoint), Prior Guidance, Change, Street Consensus, vs Street
- Directional formatting on Change and vs-Street columns
- If guidance is a range, show "midpoint (low-high)": "$24.5bn ($24.0-25.0bn)"

**Guidance Quality Assessment:** 3-5 sentences evaluating:
- Guidance vs consensus: above/below/in-line, magnitude of gap
- Management's historical guide-and-beat pattern: "Management has beaten its own revenue guidance in 7 of the last 8 quarters by an average of 2.3%"
- Key embedded assumptions: FX, commodity prices, product launch timing, macro
- Whether the guidance implies acceleration or deceleration from the just-reported quarter

**Do:**
- Always compare guidance to consensus, not just to prior guidance
- Cite management's historical accuracy if data is available
- Note whether guidance implies a sequential step-up or step-down and why

**Don't:**
- Accept guidance at face value without assessing credibility
- Omit the comparison to street expectations
- Present a wide guidance range without discussing where within the range is most likely

**Exemplar:**
"FY26 revenue guidance of $98-102bn (midpoint $100bn) is 3% above current consensus of $97.1bn. Management has beaten its own annual guidance in each of the past 4 years by an average of 4.2%, suggesting the guide may again prove conservative. The guidance assumes stable FX at current rates and no material change in the macro environment."


### 2.6 Earnings Call Key Points

**Purpose:** Distill the information edge from the live call — what did management say beyond the press release?

**Structure:** Three subsections:
- Management Commentary: 2-3 sentences each for CEO outlook, CFO financial explanations, and strategic announcements
- Q&A Highlights: 3-5 bullet points, each one exchange
- Tone Assessment: small 4-row table

**Tone:** Report in indirect speech ("management stated", "the CEO indicated"), then add analytical judgment on the tone separately.

**Management Commentary guidelines:**
- Separate the CEO's qualitative vision from the CFO's financial specifics
- Flag any strategic announcements (M&A, restructuring, capital allocation changes, new product launches)
- Use indirect speech, not direct quotes — unless a specific phrase is particularly revealing

**Q&A guidelines:**
- Select the 3-5 exchanges that revealed new information not in prepared remarks
- Format: topic label + management's response in one sentence
- Prioritize questions about forward-looking items, margin trajectory, competitive dynamics, and capital allocation

**Tone Assessment table:**
- Overall Tone: Optimistic / Neutral / Cautious / Defensive
- Confidence Level: Strong / Moderate / Low
- vs Prior Quarter: More Positive / Similar / More Cautious
- Specific Risk Flags: Yes (describe) / No

**Do:**
- Prioritize Q&A exchanges that moved the stock or revealed new information
- Note when management deflected or gave non-answers on important topics
- Compare tone to the prior quarter's call explicitly

**Don't:**
- Transcribe long passages — distill to the informational core
- Present all Q&A exchanges — only the 3-5 most material
- Conflate management optimism with factual strength of the quarter

**Exemplar (Q&A bullet):**
"On AI server margins: management acknowledged near-term gross margin dilution of 200-300bps from liquid cooling components but expects normalization by 2H26 as manufacturing yields improve and volume scales. This aligns with our estimate of margin recovery in the back half."


### 2.7 Risk Assessment

**Purpose:** Identify the specific risks that could push the stock above or below the base case, updated for the latest quarter's data.

**Structure:** Two subsections (Upside Risks, Downside Risks) each as bullet points, followed by a key finding block with the net risk skew.

**Tone:** Specific and grounded in the quarter's data. Each risk should connect to something revealed or reinforced by this earnings report.

**Do:**
- Make every risk specific to this company and connect it to the quarter's data
- Use the pattern: "Faster/slower-than-expected [specific driver], as suggested by [data point from this quarter]"
- Limit to 2-3 upside and 3-4 downside risks
- State the net risk skew explicitly in the key finding block

**Don't:**
- List generic macro or sector risks without company-specific grounding
- Include more than 7 total risks
- Present risks without connecting them to the current quarter's signals

**Exemplar (Downside risk):**
"Gross margin compression if the product mix continues to shift toward lower-margin AI server configurations. This quarter's GM decline of 120bps QoQ was attributed to mix; if AI server revenue grows to 40%+ of total (from 28% currently), structural margin pressure could intensify."


### 2.8 Investment Thesis Check

**Purpose:** Explicitly link the quarter's results to the reasons for owning or avoiding the stock.

**Structure:** A thesis pillar table (3-5 rows) with columns for Pillar, Status, and Commentary. Followed by a 2-3 sentence summary and a rating badge block.

**Thesis pillar table:**
- Each row names a pillar of the investment case (e.g., "AI revenue ramp", "Margin expansion via mix shift", "Market share gains in enterprise")
- Status: Strengthened / Unchanged / Weakened
- Commentary: one sentence citing the specific data point from this quarter

**Summary:** 2-3 sentences stating whether the overall thesis is intact, which pillars moved, and the resulting rating/target price action.

**Do:**
- Derive thesis pillars from the core investment case, not from this quarter's surprises
- Assign status based on the data, not management's characterization
- State the rating action clearly: "Maintain Buy", "Downgrade to Hold", "Raise target to $X"
- Show the rating badge with the target price

**Don't:**
- Include more than 5 pillars — this should be the 3-5 most important reasons to own the stock
- Mark everything as "Unchanged" when the quarter had clear signals
- Omit the rating and target price conclusion

**Exemplar (table row):**
| AI server revenue ramp | Strengthened | AI server revenue grew 42% YoY to $2.1bn, ahead of our $1.8bn estimate, confirming the adoption curve is steeper than modeled |


## 3. Data Presentation Rules

### Shared Rules

Table formatting, chart conventions, actuals-vs-estimates presentation, and currency/unit conventions follow the Stock Update Style Guide (Section 3: Data Presentation Rules). Those rules apply identically here and are not repeated.

### Earnings-Specific Table Types

**Financial scorecard table (Section 2.3):**
- Mandatory comparison columns: Actual, Consensus, Beat/Miss %, Prior Quarter, QoQ %, Year-Ago Quarter, YoY %
- Green/red directional formatting on Beat/Miss and growth columns
- Margin rows show absolute value and ppt change: "42.3% (+1.2ppts QoQ)"
- Bottom border separates financial metrics from KPI metrics

**Guidance comparison table (Section 2.5):**
- Columns: New Guidance, Prior Guidance, Change, Street Consensus, vs Street
- Show ranges as "midpoint (low-high)"
- Directional formatting on Change and vs-Street columns

**Thesis check table (Section 2.8):**
- Columns: Thesis Pillar, Status, Commentary
- Status uses color coding: Strengthened (green), Unchanged (neutral), Weakened (red)
- Commentary is one concise sentence per row

**Tone assessment table (Section 2.6):**
- 4 rows, 2 columns (Dimension, Assessment)
- No numerical data — qualitative assessments only
- Keep compact; no cell formatting needed

### Earnings-Specific Charts

- Quarterly revenue trend (bar chart) with consensus estimate overlay (line) for the last 8 quarters
- EPS actual vs consensus (grouped bar chart) for the last 6-8 quarters to show beat/miss pattern
- Segment revenue contribution (stacked bar or pie chart) showing mix shift over time
- Margin trend (line chart) for GM, OPM, and NPM over the last 8 quarters


## 4. Cover Page Conventions

### Shared Rules

Cover page layout conventions follow the Stock Update Style Guide (Section 4: Cover Page Conventions). The earnings report cover follows the same structure with these adaptations:

- Title: "Earnings Analysis Report"
- Subtitle: Company name
- Ticker: Stock ticker symbol
- Reporting period: Quarter and fiscal year (e.g., "Q1 FY2026")
- Tagline: One sentence leading with the verdict, not the event. "Revenue and EPS beat on AI server strength; raising TP to $185, maintain Buy" — not "Company reported Q1 FY2026 results."
- Key metrics: stock price (with post-earnings % change), EPS actual vs consensus, revenue actual vs consensus, rating
- Stats panel: market cap, reporting period, release date, earnings call date/time, fiscal year end, sector, exchange
