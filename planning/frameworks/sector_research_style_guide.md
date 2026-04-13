# Sector Research Report Style Guide

Style guide for LLM-generated sector research reports, derived from 13 professional investment bank research reports (Morgan Stanley, KGI Securities). Covers semiconductors, semiconductor equipment, IT hardware, robotics/physical AI, space, and internet sectors.


## 1. Overall Writing Style

### Tone and Voice
- Authoritative and thesis-driven. Sector reports assert a view on an entire industry; the tone is more assertive than single-stock reports.
- Use first-person plural confidently: "we believe", "in our view", "our view is that", "we estimate", "we forecast". Reserve stronger language for high-conviction points: "It's becoming clear to us that..."
- Analytical and forward-looking. Sector reports spend more time on forward projections and structural arguments than backward-looking results.
- Conversational is acceptable for thematic pieces. MS Foundation notes occasionally use informal framing: "Are bearings a commodity? Yes. But we are going to need many tens of billions of them."

### Sentence Structure
- Front-load conclusions. Put the investment implication first, then the supporting data.
- Longer paragraphs are acceptable in sector reports compared to stock updates. Dense analytical paragraphs of 5-8 sentences are common, especially in Thesis and Drivers sections.
- Use bullet points liberally for multi-point arguments. Sector reports typically have more bulleted content than stock-specific reports.
- Use em-dashes for parenthetical clarification: "Memory (NAND and DRAM) — a key cost component for servers, storage arrays, PCs, smartphones, etc. — is in the midst of a pricing 'supercycle'."

### Number Formatting and Citation
- Cite data inline: "spot NAND and DRAM prices — key components in hardware devices — up 50% and 300% in the last 6 months"
- Use parenthetical comparisons: "(up 26% year over year)", "(vs. +90% over the course of 12 months in the last cycle)"
- Market sizing: "$25 trillion of combined robot revenues by 2050", "CAGR of 13%"
- Capacity/volume data: "225/320kwpm to 278/355kwpm", "~6.7k satellites in orbit"
- Use "~" for approximations: "~200mn bearings ($827mn) in 2025"
- Use "E" or "e" for estimates: "2027E", "FY26e", "CY26"
- Use "x" for multiples: "~17x Price/Sales (FY24e)", "34x larger"
- Use "mn" for millions, "bn" for billions: "$136bn", "$733.5m"
- Percentage points: "60bps Y/Y", "+1.5ppt"
- Growth rates with direction: "+23%/+27%", "up 13% y/y"

### Transitions and Connectors
- "Big picture," or "Big picture:" to frame the overarching conclusion
- "Net net," to summarize after multiple data points
- "For context:" to introduce supporting data
- "In this note, we..." to state what the report covers
- "That said," to introduce counterpoints
- "The key risk is that..." to transition to risk discussion
- "How do we play [X] from here?" to transition to stock implications
- "Stock expressions?" as a direct transition to investable names

### What to Avoid
- Promotional language ("revolutionary", "game-changing", "incredible")
- Generic claims without data ("the sector is growing rapidly" without a growth rate)
- Repeating the same thesis statement in different words across sections
- Excessive hedging that dilutes the thesis (sector reports should be conviction-driven)
- Paragraph-long sentences; break complex arguments into bullet points


## 2. Per-Section Guidelines

### 2.1 Sector Thesis / Key Takeaway

**Purpose:** State the sector investment thesis and its implication for stock positioning.

**Structure:** Two common formats:
- Format A (MS Idea/Global Insight): A dense opening paragraph stating the thesis, followed by bullet points with numbered supporting arguments. The Key Takeaways box is prominent.
- Format B (KGI Industry Report): An executive summary with numbered points followed by a short investment recommendation paragraph.

**Tone:** Most confident of all sections. Sector theses are asserted, not hedged.

**Data integration:** Cite 2-3 headline figures that anchor the thesis. Market sizing data, growth rates, or cycle-defining metrics.

**Do:**
- Lead with the investment conclusion: what should investors do
- Include the 1-2 most powerful data points
- State which stocks benefit or are at risk
- Be specific about the sector view (Attractive/In-Line/Cautious)

**Don't:**
- Start with "In this report, we analyze..." or "This note covers..."
- List more than 6 key takeaways
- Bury the conclusion after background description

**Exemplar (MS, IT Hardware Global Insight):**
"We are in an unprecedented memory cycle, with spot NAND and DRAM prices — key components in hardware devices — up 50% and 300% in the last 6 months. History tells us these cyclical memory 'supercycles' begin to play out via gross margin and multiple compression 6+ months after costs first increase. We model Global OEM/ODM gross margins down a median 60bps Y/Y, in 2026 vs. Street up ~10bps Y/Y. MSe now 11% below CY26 Consensus EPS across coverage."
-- This works because: quantified thesis ("50% and 300%"), historical framing ("history tells us"), specific divergence from consensus ("60bps down vs. Street up 10bps"), clear investment implication.

**Exemplar (KGI, Semiconductor Specialty Chemicals):**
"We initiate coverage on the semiconductor specialty chemicals industry. As process nodes advance, transistor architecture grows more complex, and advanced packaging penetration rises, per-wafer consumable usage and chemical specification upgrades will drive structural growth. Furthermore, under TSMC's supply chain localization push, domestic suppliers will benefit from market share expansion, exhibiting growth momentum above the industry average."
-- This works because: thesis-first structure, three numbered drivers, specific investment recommendations with target prices at the end.


### 2.2 Industry Overview and Market Sizing

**Purpose:** Establish what the industry is and quantify the opportunity.

**Structure:** 1-3 paragraphs of narrative followed by 1-2 charts showing market sizing or growth trajectory. For sector initiations, include a brief industry primer before the data.

**Tone:** Informative and factual. More explanatory than other sections since the reader may not be familiar with the sector.

**Data integration:** Heavy use of market size figures, CAGRs, and volume data. Cite sources explicitly: "according to SIA", "per Gartner estimates", "based on IFR data."

**Do:**
- Quantify the market with specific dollar figures and growth rates
- Compare growth rates to relevant benchmarks: "semiconductor materials CAGR of 13%, above silicon wafer shipment growth of 6%"
- Include a primer for emerging/niche sectors
- Cite industry data sources

**Don't:**
- Present market sizing without a growth trajectory
- Use vague sizing ("a large and growing market")
- Spend more than 2 paragraphs on background before getting to data

**Exemplar (MS, Robotics Bearings):**
"In our Morgan Stanley Global Robot Model, we estimate: Number of bearings for robotics sold rising from ~200mn ($827mn) in 2025 to 1.1bn ($4.5bn) in 2030, 15.2bn ($86.8bn) in 2040, and 40.6bn ($255bn) in 2050."
-- This works because: specific bottom-up model with multiple time horizons, both units and dollar values.


### 2.3 Key Drivers and Trends

**Purpose:** Explain the 3-5 forces shaping the sector and driving the investment thesis.

**Structure:** Numbered takeaways or bullet points, each 2-4 sentences. Each driver covers: what is happening, the quantified impact, and why it matters.

**Tone:** Analytical with conviction. Each driver should clearly support or challenge the thesis.

**Data integration:** Every driver must have at least one supporting data point. Use inline citations.

**Do:**
- Number or bullet each driver for scanability
- Link each driver back to the investment thesis
- Include industry expert or management commentary in indirect speech
- Quantify each driver: "N2 capacity doubling from 40k to 100k wafers in 2026"

**Don't:**
- List drivers without explaining their investment significance
- Mix micro (company-specific) and macro (industry-wide) drivers without distinguishing
- Present more than 5 major drivers

**Exemplar (MS, Semiconductor Equipment Idea):**
"Numbers go higher & higher (again). It's only been 1 month since we last raised numbers and our 2026/2027 numbers have come up 12%/33% since mid-Sep. Our revisions are as follows: 1) DRAM: DRAM WFE is being pulled forward at an unprecedented pace, and we are increasing our 2026/2027 greenfield wafer capacity additions from 225/320kwpm to 278/355kwpm. 2) NAND: Capacity expansion plans at Kioxia/SanDisk and YMTC are set to accelerate meaningfully over the next four quarters. 3) Foundry/Logic: Our 2026 revisions are more modest; however, we see significant upside risk to our 2027 TSMC capex forecast of $59bn."
-- This works because: numbered drivers, specific revision figures, forward-looking with quantified expectations.


### 2.4 Market Data and Analysis

**Purpose:** Provide the quantitative evidence supporting the thesis.

**Structure:** Data-heavy with charts and tables interspersed with analytical commentary. Group data by sub-segment or geography.

**Tone:** Factual and precise. Let the data drive the narrative.

**Data integration:** This is the most data-dense section. Every claim should have a number. Present actuals vs. estimates and vs. historical norms.

**Do:**
- Present data with full context: actual, vs. estimate, vs. historical average
- Group by sub-segment: "By geography: Asia Pacific (+90.8%), China (+61.9%), Americas (+47.4%)"
- Use historical comparisons as anchors: "vs. +90% over 12 months in the last cycle"
- Include 2-4 exhibits with source attribution

**Don't:**
- Present data without analytical framing
- Mix units within a comparison (don't compare m/m to y/y without labeling)
- Include more than 4-5 exhibits in this section alone

**Exemplar (MS, Semiconductors Weekly):**
"January Semiconductor Industry Association billings data came in above our estimates and seasonality for broad markets: Overall: Sales were down 4.9% m/m, above our estimate of -15.7% and above the 10-yr average change of -9.8%. 3-month y/y growth accelerated from 37.1% to 44.8%, and one month y/y growth was 58.2%. By geography: Asia Pacific (+90.8%) was followed by China (+61.9%), The Americas (+47.4%), and Europe (+37.9%), while Japan was flat (-0.5%)."
-- This works because: actual vs. estimate vs. historical average, multiple time comparisons, geographic breakdown, all inline.


### 2.5 Competitive Landscape and Value Chain

**Purpose:** Map who the players are and where value accrues in the sector.

**Structure:** Two sub-sections: competitive landscape (who) and value chain (where). For competitive landscape, use a summary exhibit or table. For value chain, use narrative with a flow diagram if applicable.

**Tone:** Objective and comparative. Avoid picking favorites outside the stock recommendations section.

**Data integration:** Market share data, funding figures for private companies, supply chain concentration metrics.

**Do:**
- Quantify market concentration: "top 6 global manufacturers represent >50% of the market"
- Include private companies and startups alongside public names
- Flag supply chain concentration risks: "potentially >90% of the critical components supply chain is controlled by China"
- Identify picks-and-shovels plays

**Don't:**
- List companies without competitive context
- Omit private companies in emerging sectors (they often define the competitive landscape)
- Present a value chain without identifying where pricing power or bottlenecks exist

**Exemplar (MS, Robotics Bearings):**
"Key stats on the global bearings market: According to SKF, the top 6 global manufacturers represent >50% of the global roller market (Chinese manufacturers representing ~25%). ~40% of the market is dedicated to industrial equipment OEMs, ~30% to auto, and ~30% to distribution. Stock expressions? JTEKT, NSK, NTN, RBC Bearings, Regal Rexnord, Schaeffler, SKF, Timken."
-- This works because: quantified concentration, segment breakdown, direct transition to investable names.


### 2.6 Company Analysis and Stock Implications

**Purpose:** Connect the sector thesis to specific stock recommendations.

**Structure:** For broad sector notes: summary peer comparison table followed by 1-2 paragraph write-ups per key rating change. For focused notes: deeper individual company analysis. Always include a table.

**Tone:** Actionable and specific. State the rating action, target price, and key reason clearly.

**Data integration:** Per-company financial metrics (EPS, P/E, margins) in a comparison table. Target prices with methodology stated inline.

**Do:**
- State rating actions clearly: "Downgrading DELL to Underweight with new $110 Price Target"
- Show a peer comparison table with key metrics across all covered companies
- For each rating change, cite the 1-2 specific reasons from the sector thesis
- Separate "most vulnerable" vs. "most insulated" when the thesis creates divergent impacts

**Don't:**
- List stock recommendations without connecting to the sector thesis
- Present company-specific analysis that contradicts the sector view without explaining why
- Include more than 3 paragraphs per company in a multi-stock sector note

**Exemplar (MS, IT Hardware):**
"US Hardware OEMs: We believe DELL and HPQ are 'most-vulnerable' amongst the US OEMs given higher DRAM exposure, more cautious recent channel checks, and lower operating margins vs. peers, while PSTG and AAPL are 'most insulated' amongst the group given differentiated business models and/or more software mix."
-- This works because: clear segmentation (vulnerable vs. insulated), specific reasons per stock, comparative framing.

**Exemplar (KGI, Semiconductor Specialty Chemicals):**
"We initiate Shin-Etsu Chemical (4749 TT, NT$920, Buy) with a target price of NT$1,260, assigning a 50x P/E (vs. historical range of 30-80x) on 2027E EPS. Investment preference: Shin-Etsu > TPEC > San Fu Chemical, based on valuation and operational structure."
-- This works because: rating with target price and methodology, ranking with rationale.


### 2.7 Valuation

**Purpose:** Show the valuation math and context for the sector and key stocks.

**Structure:** 1-2 paragraphs per valuation approach, plus a peer valuation table. For sector notes with multiple stocks, the table is the centerpiece.

**Tone:** Precise and mathematical. Show the work.

**Data integration:** Multiples, historical ranges, peer comparisons, and scenario-based targets.

**Do:**
- State the methodology explicitly: "based on 50x 2027E P/E (vs. historical range of 30-80x)"
- Compare to historical range or cycle context: "23x through-cycle EPS of $30.00 vs. trailing 9-year average of $6.33"
- Include cross-stock relative valuation: "trades at a discount to peers (target multiple ~3x below LAM)"
- Show a comprehensive peer valuation table

**Don't:**
- State target prices without showing how they were derived
- Apply the same multiple to all companies without justification
- Omit the implied upside/downside percentage

**Exemplar (MS, Semiconductor Equipment):**
"Instate AMAT as Top Pick within US SPE. We revise up estimates for AMAT, LAM, and KLA to reflect our WFE update, which brings our FY27 EPS up by 3-4%, and as we leave our target multiples unchanged our PTs come up by the same magnitude. The stock continues to trade at a discount to peers (target multiple ~3x below LAM and ~5x below KLA), despite our expectation that the company will outperform WFE growth."
-- This works because: relative valuation argument, specific discount quantified, catalyst identified.


### 2.8 Risks

**Purpose:** Identify specific risks to the sector thesis.

**Structure:** 3-5 risks as numbered or bulleted items, each 1-2 sentences.

**Tone:** Balanced. Acknowledge what could go wrong without undermining the thesis.

**Do:**
- Include timing risk: "we could be too early on our call"
- Be specific: name the risk and quantify it if possible
- Include upside risks if the thesis is bearish
- Distinguish sector risks from stock-specific risks

**Don't:**
- List generic macro risks without sector specificity
- Include more than 5 risks
- Write multi-paragraph risk descriptions

**Exemplar (MS, IT Hardware):**
"As for risks, we see three. First, we could be too early on our call, as it took 6-12 months for gross margins to begin contracting after memory prices surged back in 2016-2018, and thus this thesis might not play out until later in 1H26. That said, we'd rather be early than late. Second, we could see mitigation actions and/or tariff relief. Third, a faster-than-expected memory price stabilization."
-- This works because: numbered, specific, includes timing acknowledgment, addresses the counter-argument.

**Exemplar (KGI, Semiconductor Specialty Chemicals):**
"Product certification delays; advanced process wafer loading below expectations."
-- This works because: two specific, sector-relevant risks in concise format.


## 3. Data Presentation Rules

### Tables
- Peer comparison tables are the hallmark of sector reports. Always include: ticker, rating, target price, market cap, and 2-3 years of key financial metrics (EPS, P/E, margins)
- Use consistent units within a table
- Mark estimates with "E" or "F" suffix: "2027E", "2026F"
- Include both local currency and USD for market cap where applicable
- Sort by investment preference or market cap

### Charts
- Market sizing charts: area or bar chart showing historical and projected market size
- Supply/demand charts: overlay supply and demand trends or pricing data
- Cycle comparison charts: overlay current cycle data against historical cycles
- Geographic or segment breakdown: stacked bar charts
- P/E band charts or historical valuation range for sector stocks
- Source attribution on every exhibit: "Source: SIA, Morgan Stanley Research"
- Number exhibits sequentially: "Exhibit 1:", "Exhibit 2:"

### Actuals vs. Estimates
- Standard format: "actual (vs. estimate and vs. historical average)"
- Example: "Sales were down 4.9% m/m, above our estimate of -15.7% and above the 10-yr average change of -9.8%"
- Use "above/below" for directional context, "vs." for neutral comparison
- Show both house estimate and consensus where available

### Currency and Unit Conventions
- Use local currency for company-specific data: NT$ for Taiwan, HK$ for Hong Kong, US$ for US
- Use USD for market-level data unless the market is local
- Dual currency for market cap: "NT$2,687mn / US$2,687mn"
- Use k/mn/bn consistently: "kwpm" (thousand wafers per month), "$136bn"
- Growth rates: "+23% y/y", "CAGR of 13%"


## 4. Cover Page Conventions

### Key Information Displayed
- Sector name and region
- Report type badge (Foundation, Idea, Update, Global Insight, Industry Report)
- Industry view rating (Attractive/In-Line/Cautious) where applicable
- Key analyst name(s)
- Report date
- Key changes summary table (rating and price target changes)
- Headline subtitle summarizing the thesis

### Sector Reports vs. Stock Reports
- Sector covers emphasize the industry view and multiple stock changes, not a single stock
- "What's Changed" table is prominent when ratings change: columns for From/To on rating and price target
- Key statistics may include: sector market size, growth rate, number of companies covered
- For sector initiations: peer comparison table may appear on the cover

### Report Type Distinctions
- **Foundation**: Deep-dive, long-form. Often introduces a new thematic concept. Cover has a longer subtitle and list of related reading.
- **Idea**: Investment argument for a specific sector view. Cover leads with the thesis and key recommendation.
- **Update**: Regular data check-in. Cover shows the latest data point and its significance.
- **Global Insight**: Cross-regional analysis with multiple rating changes. Cover has a prominent "What's Changed" table.
- **Industry Report**: Traditional sector initiation. Cover has a peer comparison table with ratings and target prices.
