# Stock Update Report Style Guide

Style guide for LLM-generated stock update reports, derived from 34 professional investment bank research notes (Goldman Sachs, Morgan Stanley, Citi, HSBC, Daiwa, GF Securities). Covers Taiwan tech, US semis/tech, shipping, textiles, and utilities.


## 1. Overall Writing Style

### Tone and Voice
- Direct and confident. Lead with conclusions, support with data.
- Use hedging language naturally but sparingly: "we believe", "in our view", "we expect", "we estimate". Reserve stronger language ("we are confident") for high-conviction points.
- Never promotional or speculative. Every claim must have supporting data inline.
- Analytical, not narrative. Prioritize information density over readability.

### Sentence Structure
- Front-load the important information in each sentence. Put the conclusion or key figure first, then the explanation.
- Keep sentences concise. Average 15-25 words. Longer sentences are acceptable when presenting multi-part data comparisons.
- Use semicolons to connect related data points within a sentence rather than splitting into multiple sentences.

### Number Formatting and Citation
- Cite data inline in prose, not in separate callouts: "4Q25 revenue of NT$47,775m (+23% QoQ, +129% YoY) was in-line with our estimate."
- Show percentage changes in parentheses after the figure: "$68.1bn (up 19.5% q/q and 73.5% y/y)"
- Use parentheses for negative changes: "(-22% QoQ)" or "down 22% QoQ"
- Use ppts for margin changes: "-0.5ppt", "+1.5ppt QoQ"
- Mark forward estimates with "E" suffix: "2027E", "FY26E"
- Use "vs." for comparisons: "vs. GSe of NT$9,304m", "vs. consensus at $66.1bn"
- Use "mn" or "m" for millions, "bn" for billions: "NT$45bn", "$68.1bn", "NT$9,304m"
- Use "x" for multiples: "15.4x 2027E P/E", "0.7x P/B"
- Standard deviations: "2.3x STDV above the past upcycle average"

### Transitions and Connectors
- "Net net," to summarize after multiple data points
- "Overall," to provide summary assessment
- "Looking into [year]," for forward outlook
- "We attribute [result] to [cause]"
- "This aligns with our view that..."
- "We expect [this] to continue/accelerate driven by..."

### What to Avoid
- Promotional language ("exciting", "tremendous", "game-changing")
- Filler phrases ("it is worth noting that", "importantly")
- Repeating the same data point in different formats
- Vague claims without data ("strong growth", "solid results" without numbers)
- Excessive caveats that dilute the thesis


## 2. Per-Section Guidelines

### 2.1 Investment Thesis / Key Takeaway

**Purpose:** State the investment conclusion and the single most important reason behind it.

**Structure:** One of two formats depending on report trigger:
- Format A (GS/Citi style): A single dense paragraph (4-8 sentences) that weaves together the event, key data, and investment implication. Rating and price target stated at the end.
- Format B (MS/Daiwa style): A 2-3 sentence introductory thesis, followed by bullet points under "Key Takeaways" listing the 4-6 most important findings.

**Tone:** Most confident of all sections. Lead with the conclusion.

**Data integration:** Cite the 1-2 most impactful data points inline. Include the rating, price target, and key valuation metric.

**Do:**
- Lead with the investment implication, not the event description
- Include the rating action and price target in the thesis
- Cite the single most surprising or impactful data point

**Don't:**
- Start with "The company reported..." or "We attended..."
- List more than 6 bullet points in Key Takeaways format
- Bury the conclusion at the end of the paragraph

**Exemplar (GS, AVC earnings):**
"AVC's 4Q25 revenue and GM are in line with our estimate and Bloomberg consensus, and the opex ratio of 5.8% is better than our estimate, leading 4Q25 OP income to grow at +191% YoY, or 6% ahead of our estimates. We are positive on AVC's earnings growth, supported by (1) shipments growth of GPU and ASIC AI servers, along with the rising liquid cooling penetration rate, driving AVC's liquid cooling components shipments growth, (2) increasing adoption rate of ultra-thin VC in consumer electronics... Maintain Buy with 12M TP raised to NT$2,259 (21.2x 2027E P/E vs. +23% NI YoY on avg. in 2027-28E)."
-- This works because: thesis-first, specific data inline, numbered drivers, rating+PT+methodology in one sentence.

**Exemplar (Citi, Hon Hai earnings):**
"Despite non-operating loss and higher tax rate dragging its 4Q25 earnings, Hon Hai's 4Q25 operating profit of NT$85.6bn (up 21% QoQ and 33% YoY) were ahead of Citi's and consensus estimate by 14% and 9% respectively. Hon Hai's 4Q25 OPM of 3.3% was better than expected. Management is optimistic on AI demand strong growth trend and looking for remaining solid consumer electronics demand thanks to its higher exposure to high-end smartphones. We maintain Buy."
-- This works because: acknowledges the negative before pivoting to the positive, specific figures vs estimates, clear conclusion.


### 2.2 Event Analysis

**Purpose:** Explain what happened and why it matters for the stock.

**Structure:** 2-4 paragraphs or numbered takeaways. Each covers one aspect of the event with supporting data.

**Tone:** Analytical and factual. Present management commentary in indirect speech ("management expects...", "the company guided...").

**Data integration:** Heavy inline citations. Every claim about results includes the figure, the comparison (QoQ/YoY), and the benchmark (vs estimate/consensus).

**Do:**
- Use numbered takeaways for multi-topic events: "(1) IC substrate growth... (2) BT substrate demand... (3) Price adjustments..."
- Quote management where impactful: "Management targets a return to 20-30% YoY revenue growth in 2H26"
- Compare actuals to estimates explicitly: "6% ahead of our estimates", "vs. GSe/consensus of NT$2.00/NT$1.93"

**Don't:**
- Describe the event without analyzing its significance
- Use more than 5 numbered takeaways
- Include management commentary without contextualizing it

**Exemplar (GS, Silergy earnings):**
"4Q25 core ops inline. Silergy hosted its 4Q25 analyst meeting on Mar 13. 4Q25 revenue was NT$5,392mn (+13.2% QoQ, 5.5% YoY), which came in 7%/5% above GSe/Bloomberg on stronger auto and consumer demand. In terms of margins, 4Q25 GM of 51.2% (up 0.9ppts) was slightly above GSe and largely inline with consensus, supported by more favorable product mix with higher auto revenue contribution. However, 4Q25 Opex ratio of 37.0% was higher vs. GSe/consensus of 35.5%/36.6% on continued investment in R&D and sales & marketing expense for new product ramp. Net net, 4Q25 EPS was NT$2.09, slightly higher vs. GSe/consensus of NT$2.00/NT$1.93."
-- This works because: dense data presentation, every figure compared to estimates, explains both beats and misses with reasons.


### 2.3 Financial Results Summary

**Purpose:** Present key financial figures in a structured, scannable format.

**Structure:** A comparison table followed by a 2-3 sentence narrative highlighting what stood out.

**Table format (GS pattern, most common):**
- Columns: Prior period, Sequential period, Current period, QoQ change, YoY change, Analyst estimate, Actual vs Estimate, Consensus, Actual vs Consensus
- Rows: Revenue, Gross Profit, Operating Profit, Net Income, then Margins (GM, OPM, NM)

**Data integration:** Use directional formatting: green/positive for beats, red/negative for misses. Show margin changes in percentage points (ppts).

**Do:**
- Show both QoQ and YoY changes for every line item
- Show actual vs both house estimate and consensus
- Express margin changes in ppts, not %

**Don't:**
- Show only the company's numbers without estimates comparison
- Include more than 8 line items in the summary table
- Omit the margin rows

**Exemplar (GS, Hon Hai result snapshot):**
A table showing 4Q24, 3Q25, 4Q25, QoQ, YoY, GS estimate, Act/GS, Consensus, Act/Cons for Revenue/GP/OP/NI and GM/OPM/NM. Followed by narrative: "4Q25 OPM sustained 3.3%; Net income lower than expected due to GM dilution and higher tax rate."


### 2.4 Estimate Revisions

**Purpose:** Show how forward estimates change and explain what drives the revision.

**Structure:** A revision table showing Old vs New estimates with % change, followed by 2-3 sentence explanation of what drove the revision.

**Table format:**
- Rows: Revenue, Gross Profit (or GM %), Operating Profit (or OPM %), Net Income, EPS
- Columns: For each forecast year (2-3 years): Old, New, Diff %
- Show margin assumptions as separate rows

**Data integration:** Use directional formatting on Diff % column. Explain the revision driver in 1-2 sentences: "mainly on higher AI server liquid cooling components shipments estimates" or "reflecting product mix changes and a higher tax rate."

**Do:**
- Show 2-3 years of forward estimates
- Compare to consensus where available: "Our 2026-27e EPS estimates are still 14% and 4% below consensus"
- State the specific driver of the revision

**Don't:**
- Show revisions without explaining the driver
- Include more than 3 years of forecasts
- Show only EPS without revenue/margin context

**Exemplar (Daiwa, Eclat):**
"We raise our 2026-27E EPS by 2-3%, mainly on our more aggressive gross margin assumptions." Paired with a table showing Previous/New/Change for Revenue, Gross Profit, GPM, Operating Profit, OPM, Net Profit, EPS.


### 2.5 Valuation and Price Target

**Purpose:** State the target price and show the valuation math.

**Structure:** 2-3 sentences stating: (1) the target price, (2) the methodology and inputs, (3) the implied upside/downside and historical context.

**Valuation methodologies commonly used:**
- Forward P/E: "Our TP of NT$1,818 is based on 22x forward-year EPS (2027E). Our target P/E is derived from the correlation between P/E and EPS growth of its peers."
- P/B: "Our TP implies 0.7x 2026e P/B, justified based on pricing environment expectations."
- Residual Income: "Base case, residual income model. Key assumptions include a cost of equity of 9.2% (beta of 1.0, equity risk premium of 8.7%), medium-term growth rate of 11%, terminal growth rate of 3%."
- Standard deviation from historical: "Based on 15.4x 2027E P/E, which is 2.3x STDV higher than the past upcycle average P/E (10.3x)."

**Data integration:** Always state the exact multiple, the metric it's applied to, and what the resulting TP is. Reference historical range or peer comparison.

**Do:**
- State the valuation methodology explicitly
- Show the math: multiple x metric = target price
- Reference how the target multiple compares to historical average or peer range
- State the implied upside/downside percentage

**Don't:**
- State a target price without showing how it was derived
- Use vague phrases like "we believe the stock deserves a premium"
- Apply valuation methods without stating the inputs

**Exemplar (Daiwa, Lotes):**
"We reaffirm our Buy (1) rating and raise our 12M TP to TWD3,000 (from TWD2,000), based on a higher PER of 26x (from 18x; the high end of its past-5-year range of 10-28x) applied to our 1-year forward EPS, to factor in the new growth opportunities. Our 2025-28E EPS CAGR of 31% implies a PEG of 0.84x at our TP, which we consider undemanding."
-- This works because: old and new TP, methodology, multiple with historical range context, PEG ratio validation.


### 2.6 Bull / Bear / Base Scenarios

**Purpose:** Frame the range of outcomes and the assumptions behind each.

**Structure:** Three scenarios, each with 2-3 sentences stating the conditions and the implied target price.

**Note:** This section is most consistently present in Morgan Stanley reports (as "Risk Reward"). Goldman Sachs, Citi, and Daiwa typically do not present structured bull/bear/base scenarios but instead list upside/downside risks. When generating this section, follow the MS Risk Reward format.

**Do:**
- State a specific target price for each scenario
- State the key assumption that distinguishes each scenario
- Show the implied upside/downside from current price
- Keep each scenario to 2-3 bullet points

**Don't:**
- Make the bear case unrealistically mild or the bull case unrealistically aggressive
- Use identical drivers across scenarios (each should have distinct assumptions)
- Omit the target price from any scenario

**Exemplar (MS, Hon Hai Risk Reward):**
Bull case NT$406 (+88%): "Servers should be the key growth driver in 2026, with increasing demand from CSP clients and strong AI server demand. We believe iPhone assembly revenue should increase YoY, driven by iPhone replacement demand in 2026."
Base case NT$290 (+34%): Residual income model with cost of equity 8.5%, medium-term growth 13%, terminal growth 3%.
Bear case implied by consensus PT distribution floor.


### 2.7 Risks

**Purpose:** Identify specific, actionable risks tied to the investment thesis.

**Structure:** 3-5 risks as a numbered list or bullet points. Each risk is 1-2 sentences.

**Two common formats:**
- GS: "Key downside risks: (1) Slower-than-expected PC demand recovery, (2) Slower-than-expected ABF substrates pricing upgrading outlook, and (3) Slower-than-expected AI server PCB market share loss progress."
- MS: Separate "Risks to Upside" and "Risks to Downside" bullet lists.

**Do:**
- Make risks specific to this company and thesis, not generic
- Use the format "slower/faster-than-expected [specific driver]"
- Prioritize by likelihood and impact
- Keep to 3-5 risks maximum

**Don't:**
- List generic risks ("macro slowdown", "competition") without specificity
- Include more than 5 risks
- Write paragraph-length risk descriptions


## 3. Data Presentation Rules

### Tables
- Always include comparison columns (vs estimate, vs consensus, QoQ, YoY)
- Use consistent units within a table (don't mix NT$m and NT$bn)
- Mark estimates with "E" suffix in column headers: "12/26E", "FY2027E"
- Show margin rows as percentages with ppt changes

### Charts (when applicable)
- Monthly/quarterly revenue trend charts with YoY growth overlay
- Forward P/E band charts showing historical range
- Price performance chart vs index (dual axis)
- Earnings revision trend

### Actuals vs Estimates Presentation
- Standard format: "actual figure (beat/miss amount vs estimate)"
- Example: "NT$12,610m, 2% above our estimate of NT$12,362m"
- Use "in-line", "slightly above/below", "ahead of", "missed by"

### Currency and Unit Conventions
- State the currency explicitly on first use, then abbreviate
- Use local currency for the primary market: NT$ for Taiwan, W for Korea, US$ for US
- Dual currency for market cap: "NT$698.0bn / $21.9bn"
- Growth rates as percentages with direction: "+23% YoY", "-18% MoM"


## 4. Cover Page Conventions

### Key Information Displayed
- Rating badge (Buy/Neutral/Sell or Overweight/Equal-weight/Underweight)
- 12-month price target with upside/downside %
- Current share price with date
- Ticker and exchange
- Market cap (dual currency)
- Key forecast table: Revenue, EBITDA, EPS, P/E for current + 2-3 forward years
- Analyst name(s) and contact info

### Rating and Target Price Display
- Rating prominently displayed (GS: colored badge, MS: text label, Citi: large text)
- Target price with "from/to" when changed: "NT$1,000.00 (from NT$950.00)"
- Upside percentage calculated from current price

### Key Metrics Selection
- Always include: Market cap, EV, 3m ADTV
- Always include: Revenue, EPS, P/E for 3+ years
- Sector-relevant: P/B for financials/cyclicals, EV/EBITDA for capital-intensive, Dividend yield for income stocks
