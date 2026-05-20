# Stock Initiation Report Style Guide

Style guide for LLM-generated stock initiation reports — comprehensive, single-company deep-dives covering business, financials, competitive position, and valuation. Written to match the quality and conventions of bulge bracket equity research (Goldman Sachs, Morgan Stanley, J.P. Morgan, Citi, UBS).


## 1. Overall Writing Style

### Shared Conventions

Number formatting, currency/unit conventions, table formatting, and chart conventions follow the same rules defined in the Stock Update Style Guide (Section 1: Number Formatting and Citation, Section 3: Data Presentation Rules). Those rules apply identically here and are not repeated.

### Tone and Voice

- Authoritative but measured. Initiation reports are more deliberate than event-driven notes. The analyst is building a case from the ground up, not reacting to a catalyst.
- Information-aggregation only. OpenLIA reports surface what the market is saying with citations. Never speak in the first person about whether to buy a stock. First-person voice — "we believe", "we view", "in our view", "we recommend", "our base case", "our rating", "our target" — is FORBIDDEN throughout the report; the validator rejects it. Attribute every directional claim to a cited source using sourced-voice verbs ("JPMorgan rates", "consensus reflects", "management guided", "Bernstein argued", "Goldman flagged").
- Adopt a teaching posture in early sections (Company Overview through Business Model). The reader may be encountering this company for the first time. Explain the business clearly before analyzing it.
- Shift to analytical sourcing in later sections (Competitive Analysis through Analyst View). Analytical density rises; the voice remains third-person and cited.
- Maintain objectivity in descriptive sections. Competitive Analysis and Risk Analysis should present both sides. The Analyst View section reports the analyst consensus and bull/bear arguments observed in cited sources — it never authors an OpenLIA rating or price target.

### Sentence Structure

- Front-load important information. Put the conclusion or key figure first in each sentence, then the explanation or context.
- Keep paragraphs focused: one idea per paragraph, 3-5 sentences. Initiation reports are longer but should not feel dense — white space and clear structure carry the reader.
- Use topic sentences to anchor each paragraph. A reader skimming only the first sentence of each paragraph should get the full narrative.
- Use semicolons to connect related data points within a sentence rather than splitting into multiple sentences: "Revenue grew 18% YoY to $42.3bn; operating margin expanded 120bps to 31.2%."

### Transitions and Connectors

All transitions from the Stock Update Style Guide apply (Section 1: Transitions and Connectors). Additional transitions specific to initiation reports:

- "Putting this in context," to transition from description to analysis
- "The key question for investors is..." to frame the central debate
- "Sources cite [X] as the primary differentiator because..." to transition from competitive description to moat assessment
- "On balance," to summarize after a strengths-vs-weaknesses discussion
- "Consensus derives the target from..." to introduce the valuation methodology cited
- "Sources frame the investment case around..." to frame the analyst consensus narrative

### What to Avoid

All items from the Stock Update Style Guide (Section 1: What to Avoid) apply. Additional items specific to initiation reports:

- First-person voice anywhere in the report. "We believe", "we view", "we recommend", "in our view", "our base case", "our rating", "our target", "our DCF" all fail validation. Use sourced verbs ("consensus reflects", "JPMorgan rates", "management guided") instead.
- Company press release language. Restate facts in analytical terms — do not lift the company's own marketing copy, taglines, or mission statements (e.g., do not repeat a company slogan as if it were analytical content).
- Tombstone phrases. The following hedges (and any close variant) FAIL validation: "more assumption-heavy than the current fact set supports", "this is not a single target-setting exercise", "we cannot determine", "data not available", "data not provided", "unable to determine". If a specific fact you would cite is not in the manifest or facts slice, rewrite the sentence so it does not need that fact; do not announce the gap.
- Lazy qualitative claims: "strong management team", "best-in-class technology", "industry-leading margins" — unless immediately substantiated with data: "industry-leading gross margins of 74.5%, 15ppts above the peer median of 59.2%."
- Symmetry for its own sake. If the company has 5 clear strengths and 2 weaknesses, do not pad the weaknesses list to match. Present what is real.
- Excessive history. Company Overview should cover founding and milestones in 2-3 sentences, not a multi-paragraph corporate history. The reader is here for the investment case.
- DCF worship. Cite the deterministic DCF helper output; do not present a DCF as precise truth, and never re-derive it in prose. State the inputs and the sensitivity, then move on.


## 2. Per-Section Guidelines

### 2.1 Company Overview

**Purpose:** Orient the reader — who is this company and why does it matter?

**Structure:** A single narrative paragraph (4-6 sentences) introducing the company, followed by a metric cards block with 5-7 key facts. The narrative should read as a professional summary, not a Wikipedia entry.

**Tone:** Neutral and informative. No investment opinion yet — this section establishes facts.

**Data integration:** Key figures inline: market cap, revenue, employee count, founding year. Focus on scale and positioning, not growth rates (those come later).

**Do:**
- Lead with what the company does and where it sits in its industry: "NVIDIA designs and sells accelerated computing platforms — GPUs, networking, and software — serving data center, gaming, and automotive markets."
- Include the exchange, ticker, and market cap early
- Mention the company's position in its industry: "#1 in discrete GPU market share with ~80% share"
- Keep it to one paragraph plus metric cards — this is a summary, not a biography

**Don't:**
- Start with the founding story ("Founded in 1993 by Jensen Huang..."). Lead with what the company is today. History is a supporting detail.
- Include investment opinion or forward-looking statements
- List every product line or subsidiary — save the details for Products and Services

**Exemplar:**
"NVIDIA Corporation (NVDA, Nasdaq, market cap $2.8tn) is the dominant designer of graphics processing units and accelerated computing platforms, serving data center, gaming, professional visualization, and automotive markets. The company holds an estimated ~80% share of the discrete GPU market and ~90%+ share in AI training accelerators, positioning it as the primary hardware beneficiary of the generative AI buildout. Headquartered in Santa Clara, CA, NVIDIA employs approximately 32,000 people globally. FY2026 (Jan) revenue reached $130.5bn, up 114% YoY."
-- This works because: what the company does (first sentence), why it matters (market share), scale (revenue and employees), all in four sentences.


### 2.2 Industry Overview

**Purpose:** Establish the industry context — how big is the opportunity and what shapes it?

**Structure:** Two distinct parts. (1) Industry definition and current state: 1-2 paragraphs describing the industry, its drivers, and its constraints. Include regulatory or policy factors where material. (2) Market sizing: TAM in dollars, historical CAGR (5 years), projected CAGR (3-5 years forward), and the drivers behind projected growth. Support with a chart showing historical and projected market size.

**Tone:** Factual and data-driven. Cite sources for all market size figures.

**Data integration:** Market sizing is the core of this section. Every claim must have a number and a source: "The global semiconductor market reached $627bn in 2024 (SIA), up 21% YoY, and is projected to reach $1tn by 2030 (CAGR of ~8%)."

**Do:**
- Cite the source for every market figure: "(IDC)", "(Gartner)", "(company filings)", "(SIA)"
- Compare the company's growth to its industry's growth to foreshadow positioning
- Note structural changes: "The shift from CPU to GPU-centric computing is restructuring the $627bn semiconductor TAM"
- Include a chart showing market size over time

**Don't:**
- Present market size without a growth trajectory
- Copy the company's own TAM estimates uncritically — cross-reference with independent sources
- Spend more than one paragraph on industry history before getting to current data


### 2.3 Products and Services

**Purpose:** Explain what the company sells, why customers buy it, and how revenue breaks down.

**Structure:** Two parts. (1) Product descriptions: one paragraph per major product line or segment, explaining the customer pain point, how the product addresses it, and what differentiates it from alternatives. (2) Revenue breakdown: a pie or donut chart showing segment mix, plus a table with per-segment revenue and growth rates.

**Tone:** Clear and explanatory. Assume the reader has not used the product. Avoid jargon without explanation.

**Data integration:** Revenue per segment (dollars and % of total), segment growth rates, and unit volumes or pricing where relevant.

**Do:**
- Frame each product around the customer problem it solves, not just its technical features
- Quantify each segment: "Data Center segment contributed $104.1bn (79.7% of total revenue), up 142% YoY"
- Note where one segment is disproportionately driving growth or margin
- Include a revenue mix visualization

**Don't:**
- List product features without explaining why they matter to customers
- Describe products the company has discontinued or that contribute <5% of revenue
- Use the company's marketing names without explaining what they are: "Hopper architecture" requires context


### 2.4 Business Model

**Purpose:** Explain how the company makes money and the economics of its model.

**Structure:** A narrative explanation (2-3 paragraphs) describing the revenue model, key stakeholder relationships, and where the company sits in its value chain. Support with metric cards showing key business economics: gross margin, customer count or ARPU, retention rate, capex intensity, or other model-defining metrics.

**Tone:** Analytical. This section bridges description and analysis — not just what the company does, but why the economic model works (or doesn't).

**Data integration:** Margins, unit economics, customer concentration, contract structure, pricing model. Every claim about the business model should be supported by a financial metric.

**Do:**
- Identify the revenue model precisely: recurring vs. one-time, subscription vs. transaction, licensing vs. product
- Flag customer or supplier concentration risk: "Apple represents an estimated ~15% of TSMC's revenue"
- Note high-margin vs. low-margin segments and how mix is shifting
- Explain any platform or ecosystem dynamics: lock-in, switching costs, developer ecosystems

**Don't:**
- Describe the business model in abstract terms without tying to financials
- Confuse revenue recognition with actual business dynamics (e.g., upfront license revenue vs. ongoing relationship)
- Omit the supply side — who the company depends on matters as much as who it sells to


### 2.5 Competitive Analysis

**Purpose:** Map the competitive landscape, compare the company to peers, and assess the durability of its position.

**Structure:** Three parts. (1) Competitor profiles: 1-2 sentences per major competitor. (2) Comparison table: a structured table comparing the target company against 3-5 competitors across 6-8 dimensions (market share, revenue, growth, margins, geographic presence, key differentiators). (3) Moat assessment: a 1-2 paragraph analysis of competitive advantages using a recognized framework (network effects, switching costs, cost advantages, intangible assets, efficient scale).

**Tone:** Objective in description, opinionated in moat assessment. The comparison table is factual; the moat assessment is the analyst's judgment call.

**Data integration:** Market share data (with source), revenue and margin comparisons, R&D spend as % of revenue, patent counts or other IP metrics where relevant.

**Do:**
- Be specific about market share: "NVIDIA holds ~90%+ of the AI training accelerator market; AMD has gained share to ~5-8% with MI300X"
- Use the comparison table to let data speak — highlight cells where the target company leads or lags
- Name the moat and defend it with evidence: "Switching costs are high because CUDA has 4.5mn+ developers trained on the platform"
- Acknowledge competitive threats honestly

**Don't:**
- Claim a company has a moat without substantiation
- Compare only on dimensions where the target company wins — include dimensions where it lags
- Ignore private or emerging competitors that could disrupt the market


### 2.6 Management Team

**Purpose:** Assess whether the people running the company are capable of executing the strategy.

**Structure:** A table with columns for Name, Title, Background (education and prior roles), and Tenure. Follow with 1-2 paragraphs of qualitative assessment: notable achievements, concerns about governance, insider ownership, compensation alignment.

**Tone:** Factual for the profiles, analytical for the assessment. Management evaluation is inherently subjective — anchor opinions in observable data (tenure, insider ownership, track record on capital allocation).

**Data integration:** Insider ownership %, executive tenure, compensation structure, prior company performance under their leadership.

**Do:**
- Note insider ownership: "CEO holds ~3.5% of shares outstanding, aligning interests with shareholders"
- Flag governance concerns specifically: frequent CFO turnover, related-party transactions, dual-class share structures
- Note the bench — is succession planned or is the company a key-man risk?
- Keep profiles to 1-2 sentences per executive

**Don't:**
- List every C-suite member if they are not material to the investment thesis
- Write paragraph-length biographies — a table is more scannable
- Express personal opinions about executives — tie assessments to observable data


### 2.7 Competitive Advantages and Weaknesses

**Purpose:** Summarize the net competitive position with a structured strengths-vs-weaknesses assessment.

**Structure:** A two-column layout: advantages on the left, disadvantages on the right. Assess across 5-6 dimensions: product/technology, business model, sales/distribution, management, financial position, and (where relevant) brand or ecosystem. End with a one-sentence key finding summarizing the net position.

**Tone:** Balanced and direct. State advantages confidently; state weaknesses without hedging.

**Data integration:** Each point should have a supporting data point. "High customer concentration risk: top 5 customers account for an estimated ~50% of revenue" rather than just "customer concentration risk."

**Do:**
- Be specific and concise: one line per advantage or weakness, with a data point
- Ensure each dimension is addressed on both sides where relevant (a company can have both a technology advantage and a technology weakness in different areas)
- End with a clear net assessment: "On balance, competitive advantages outweigh weaknesses, underpinned by the CUDA ecosystem's switching costs and dominant market share in AI training"

**Don't:**
- List more than 5-6 points per side — this is a summary, not a repetition of Competitive Analysis
- Pad the weaker side to create false balance
- Use generic language: "good management" is not an advantage; "CEO with 30-year tenure and 15% CAGR in shareholder returns over that period" is


### 2.8 Risk Analysis

**Purpose:** Identify and categorize the key risks to the investment thesis.

**Structure:** Three sub-sections corresponding to the three risk categories: Industry Risks, Operational Risks, and Financial Risks. Each category has 2-4 specific risks, each stated in 1-2 sentences. End with an overall risk rating (Low / Moderate / High / Very High) justified in one sentence.

**Tone:** Measured and specific. Name each risk precisely and, where possible, quantify the potential impact. Do not sensationalize, but do not minimize.

**Data integration:** Quantify risks where possible: "A 10% tariff on imported components would reduce gross margin by an estimated 150-200bps based on current supply chain mix." Reference regulatory filings, litigation disclosures, or debt covenants where applicable.

**Do:**
- Use the "slower/faster-than-expected [specific driver]" format from the Stock Update Style Guide where applicable
- Flag concentration risks: customer, supplier, geographic, product
- For financial risks, cite specific metrics: debt-to-equity, interest coverage, cash runway in quarters
- Include risk probability and severity where you can justify an estimate

**Don't:**
- List generic risks that apply to every company ("macroeconomic slowdown", "competitive pressure")
- Include risks that are already priced in without saying so
- Write paragraph-length risk descriptions — keep each risk to 1-2 sentences
- Assign a risk rating without justification


### 2.9 Historical Financial Data

**Purpose:** Present 5 years of financial history as the foundation for forward analysis.

**Structure:** Three components. (1) A 5-year balance sheet summary table: total assets, total liabilities, shareholders' equity, cash, total debt, and 2-3 other material line items. (2) A 5-year income statement summary table: revenue, gross profit, operating income, net income, EPS, with YoY growth rates. Apply directional cell formatting to growth rates. (3) A narrative paragraph (2-3 sentences) noting any M&A, divestitures, or accounting changes that caused discontinuities. Support with a combo chart showing revenue bars and margin trend lines.

**Tone:** Factual. This section presents data, not opinion. Let directional formatting and trend lines communicate the story.

**Data integration:** All figures should be sourced from company filings. Use the most recent fiscal year's currency. Mark any restated figures.

**Do:**
- Show growth rates alongside absolute figures in the income statement table
- Flag discontinuities: "FY2024 revenue includes a $4.2bn contribution from the Activision acquisition closed Jan 2024"
- Use consistent units within each table (don't mix millions and billions)
- Include a revenue and margin trend chart

**Don't:**
- Present raw data without growth rates — the reader needs to see the trajectory
- Omit per-share data (EPS, DPS) — these are what investors trade on
- Go beyond 5 years unless a longer history is needed to show a full cycle
- Editorialize in this section — save analysis for the next section


### 2.10 Financial Analysis

**Purpose:** Analyze the financials — what do the numbers tell us about the business quality?

**Structure:** Three parts. (1) Profitability analysis: margin ratios (gross, operating, net, EBITDA) over time, presented in a table and line chart. Identify trends and inflection points. (2) Financial health: current ratio, quick ratio, debt-to-equity, interest coverage, operating cash flow / current liabilities, OCF / net income. Assess solvency and liquidity in 2-3 sentences. (3) Efficiency comparison: a peer comparison table showing receivables turnover days, inventory turnover days, and payables turnover days vs. 3-5 competitors.

**Tone:** Analytical. This is where the analyst adds value — the raw data was in the prior section; this section interprets it. State what the numbers mean for the investment case.

**Data integration:** Ratios should be calculated from the historical data and presented with trends. Peer comparisons should use the same fiscal period for all companies.

**Do:**
- Explain what's driving margin trends: "Gross margin expanded 540bps over FY2022-2026, primarily driven by mix shift toward higher-margin Data Center revenue (79.7% of FY2026 vs. 56.4% in FY2022)"
- Benchmark ratios against peers and against the company's own history
- Flag any red flags in financial health: deteriorating interest coverage, negative OCF, growing receivables misaligned with revenue growth
- State whether the balance sheet supports the company's growth plans

**Don't:**
- Repeat the raw numbers from the prior section without analysis
- Present ratios without interpretation — every ratio should have a "so what"
- Ignore cash flow quality — a company can report net income while hemorrhaging cash


### 2.11 Financial Projections

**Purpose:** Present a 3-year forward forecast with explicit assumptions.

**Structure:** A forecast table showing Revenue, Revenue Growth, Operating Income, OPM%, Net Income, and EPS for each of the next 3 fiscal years. Below the table, state the key assumptions driving the forecast in 3-5 bullet points. Support with a combo chart showing projected revenue bars and margin overlay. If consensus estimates are available, show a comparison row.

**Tone:** Forward-looking and transparent about assumptions. Projections are the analyst's best judgment, not certainty — state assumptions clearly so the reader can disagree and adjust.

**Data integration:** All projections should flow logically from the analysis in prior sections. Revenue growth should be consistent with industry growth + market share assumptions. Margin assumptions should be consistent with mix shift and operating leverage dynamics discussed earlier.

**Do:**
- Cite consensus directly using deterministic facts: "Consensus reflects FY+1 revenue of $X (N analysts, mean of `consensus_revenue_fy_next`) and FY+1 EPS of $Y [c1]."
- State each named growth driver with a sourced anchor: "Bernstein attributes the Data Center growth to Blackwell ramp [c3]"; "management guided gross margin to 73–74% on the Q1 call [c5]."
- Show the bridge from current to projected by citing the `forecast_table` helper fact, not by re-deriving the math in prose
- Compare consensus paths to disclosed company guidance ranges where available

**Don't:**
- Present projections without stating assumptions — black-box forecasts have no credibility
- Show only EPS without the revenue-to-earnings build — the reader needs to see where growth comes from
- Project more than 3 years unless the business has unusual long-term visibility (infrastructure, backlog)
- Use unrealistic precision: "$42,317.4mn" is false precision for a forecast — round to "$42.3bn"


### 2.12 Valuation Analysis

**Purpose:** Present three deterministic-helper-derived valuation ranges side-by-side. OpenLIA does NOT synthesize them into a single price target.

**Structure:** Three required blocks plus a football_field exhibit. (1) Peer-multiple implied range: a `metric_cards` or `table` rendering the helper fact `peer_multiple_implied_range` (low / median / high implied prices from peer P/E and EV/EBITDA percentiles). (2) Historical P/E band: a `chart:line` rendering the helper fact `historical_pe_band` (mean, +/- 1 sigma, current percentile). (3) Sourced sell-side range: a `metric_cards` rendering `analyst_target_high`, `analyst_target_mean`, `analyst_target_low`, and `analyst_count`. In addition, a `football_field` exhibit overlaying the three ranges on a single horizontal-bar chart with the current price as a vertical reference line.

**Tone:** Precise, transparent, and third-person. Every number traces to a helper-emitted Fact. Do not perform multiplication, division, or growth calculations in prose — cite the helper output.

**Data integration:** All numeric claims cite a Fact by name. The prose presents the three ranges side-by-side, then stops; it does NOT pick a target multiple, derive an OpenLIA target, or rank one methodology over another.

**Do:**
- Cite helper facts by name: "The peer-multiple implied range is $X–$Y (low–high quartile P/E applied to consensus FY+1 EPS) [c1]. The historical P/E band suggests fair value of $Z at the 5-year mean and $W at +1 sigma [c2]. The sell-side range from N analysts is $A–$B with mean $C [c3]."
- Present the football_field exhibit so the reader can visually compare ranges
- Note where the three ranges agree or diverge: "All three ranges overlap in the $X–$Y region; the sell-side mean sits at the high end of the peer-multiple range."
- Cross-check sell-side dispersion: "The spread between high and low analyst targets is $X, indicating wide disagreement on the FY+1 earnings path."

**Don't:**
- Synthesize the three ranges into a single OpenLIA target or recommendation — present them side-by-side and stop
- Author a "base case TP" or "12-month price target" in OpenLIA voice — this is not a target-setting exercise; consensus owns the target
- Use first-person voice anywhere in this section ("we", "our", "in our view") — the validator rejects it
- Perform arithmetic in prose — every multiple/price product must come from a helper fact
- Use P/E for a distressed name — distressed mode (industry overlay) substitutes EV/Sales and EV/EBITDA bands

**Exemplar (sourced voice, no first person, no OpenLIA target):**
> "Consensus reflects a Buy rating with a mean 12-month target of $185, implying 22% upside [c1]. The peer-multiple implied range, applying peer median forward P/E (32x) and EV/EBITDA (22x) to consensus FY+1 EPS and EBITDA, yields a range of $164–$203 [c2]. The historical P/E band sits at $158 mean / $192 at +1 sigma based on the last five years of trailing P/E [c3]. Goldman's May 12 note centres the bull case on data-center mix continuing to outpace gaming through FY+2 [c4]."


### 2.13 Analyst View

**Purpose:** Aggregate what the analyst community is currently saying about the stock, with citations. OpenLIA never authors its own rating or price target — this section reflects the sell-side and management commentary the runner gathered.

**Structure:** The section leads with four deterministic, server-built blocks in this order: (1) `rating_badge` populated from `analyst_consensus_rating`; (2) `metric_cards` populated from `analyst_target_mean`, `analyst_target_high`, `analyst_target_low`, `analyst_count`, and `consensus_upside_pct`; (3) `chart:bar` populated from `analyst_rating_distribution` (Strong Buy → Strong Sell counts). (4) A `table` of recent rating changes in the last 90 days (Date, Firm, Action, From → To, Target Price) built from cited news, each row carrying an inline `[N]` citation. If no rating-change events surfaced in the last 90 days, OMIT this table — never fabricate rows. Then a `comparison_split` of Bull-case vs Bear-case arguments, every item carrying an `[N]` citation and a sourced verb. Close with a 3-4 sentence prose paragraph summarizing the consensus, with citations.

**Tone:** Third-person, cited, neutral. The analyst's job in this section is curation, not advocacy.

**Data integration:** Every quantitative claim is a Fact pre-built by the server. The recent-rating-changes table is sourced from `web_search`/`get_company_news`. The bull/bear items are sourced from analyst notes, earnings call commentary, regulatory filings, and news entries packed in the manifest.

**Do:**
- Use sourced-voice verbs: "JPMorgan rates Buy [c12]", "consensus reflects a Hold rating with mean target $X [c1]", "Bernstein argued the China export-control headwind has been over-discounted [c8]", "management guided FY+1 revenue to $X at the midpoint on the Q1 call [c5]", "Goldman flagged a Blackwell supply constraint [c9]", "Barclays raised its FY+1 EPS to $Y [c11]".
- Cite every bull/bear item and every recent-rating-changes row
- Quote the consensus tally explicitly: "N analysts cover the stock; X Buy, Y Hold, Z Sell."
- Drop the recent-rating-changes table entirely if no events surfaced in the last 90 days — never fabricate a row

**Don't:**
- Author a rating or price target in OpenLIA voice anywhere in this section
- Use first-person voice ("we", "our", "in our view", "we recommend", "our rating", "our target") — the validator rejects it
- Hedge the consensus with OpenLIA opinion ("consensus is Buy but we think this is too aggressive") — report what the consensus says and stop
- Pad bull/bear items beyond what cited sources actually support

**Exemplar (sourced voice, no advocacy):**
> "Consensus reflects a Buy rating with a mean 12-month target of $185 across 42 analysts (33 Buy, 7 Hold, 2 Sell), implying 22% upside from the current $152 [c1]. In the last 30 days, Goldman raised its target to $215 from $200 citing accelerated Blackwell adoption [c4]; Bernstein reiterated Buy with a $195 target after Q1 [c8]. Bulls cite management's guidance for FY+1 revenue at the high end of consensus [c5]; bears flag a potential China export-control extension that JPMorgan estimates would reduce data-center revenue by ~$8bn [c12]."


## 3. Data Presentation Rules

### Shared Conventions

Table formatting, chart conventions, actuals-vs-estimates presentation, and currency/unit rules follow the same standards defined in the Stock Update Style Guide (Section 3) and the Sector Research Style Guide (Section 3). Those rules apply identically here and are not repeated.

### Initiation-Specific Table Types

Initiation reports use several table types not found in the other two modes:

- **Competitor comparison table**: 6-8 columns comparing the target company against 3-5 peers. Include: company name, ticker, market cap, revenue, revenue growth, gross margin, operating margin, and 1-2 sector-specific metrics. Use directional cell formatting to highlight where the target company leads or lags.
- **Management team table**: Name, Title, Background (education + prior roles), Tenure. Keep background to one sentence.
- **Historical financials tables**: 5-year balance sheet and income statement. Always include growth rates and margin percentages as derived rows. Use directional formatting on growth rates.
- **Financial health scorecard**: Current ratio, quick ratio, D/E, interest coverage, OCF/CL, OCF/NI — compare to thresholds and flag concerning values.
- **Valuation scenario table**: Conservative / Base / Optimistic columns, with rows for methodology, key assumption, implied target price, and implied upside/downside.
- **Peer valuation table**: P/E, P/B, EV/EBITDA, PEG for the target company and 3-5 peers on the same fiscal year basis.

### Chart Types

In addition to the chart types shared across modes:
- **Revenue composition chart** (pie/donut): segment mix for the most recent fiscal year
- **Revenue and margin trend chart** (combo): revenue bars with gross/operating/net margin lines overlaid, covering 5 historical + 3 projected years
- **Historical P/E band chart**: stock's forward P/E over 5+ years with mean and +/- 1 SD bands
- **Peer margin comparison** (grouped bar): comparing gross and operating margins across competitors


## 4. Cover Page Conventions

### Key Information Displayed
- Consensus rating badge populated from `analyst_consensus_rating` (deterministic, server-built — never authored by OpenLIA)
- Mean analyst 12-month target price from `analyst_target_mean` with implied upside/downside from `consensus_upside_pct`
- Current share price with date
- Ticker and exchange
- Market cap (dual currency where applicable)
- One-sentence neutral framing tagline — describes what the report covers, NOT what to do about the stock. No "Buy", "Sell", "Overweight", "Initiate at" language.
- Key forecast table: Revenue, EPS, P/E for current year + 2-3 forward years (estimates marked with "E")
- Sector, sub-industry classification
- Report date

### Initiation Cover Conventions
- The cover surfaces the deterministic consensus rating, mean PT, and implied upside as the headline — the first thing a reader sees is what the market is saying, with citations resolving to the AnalystRatings manifest entry.
- OpenLIA does NOT author its own rating or target on the cover. There is no "Initiate at Overweight" or "We rate Buy" language anywhere on the cover. Exemplar tagline: "Stock initiation note covering business model, financials, and the sell-side consensus on $TICKER."
- Include free float % and 3-month ADTV for institutional readers evaluating liquidity.
