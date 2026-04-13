# Stock Initiation Report Style Guide

Style guide for LLM-generated stock initiation reports — comprehensive, single-company deep-dives covering business, financials, competitive position, and valuation. Written to match the quality and conventions of bulge bracket equity research (Goldman Sachs, Morgan Stanley, J.P. Morgan, Citi, UBS).


## 1. Overall Writing Style

### Shared Conventions

Number formatting, currency/unit conventions, table formatting, and chart conventions follow the same rules defined in the Stock Update Style Guide (Section 1: Number Formatting and Citation, Section 3: Data Presentation Rules). Those rules apply identically here and are not repeated.

### Tone and Voice

- Authoritative but measured. Initiation reports are more deliberate than event-driven notes. The analyst is building a case from the ground up, not reacting to a catalyst.
- Use hedging language judiciously: "we believe", "in our view", "we estimate" for forward projections. Use direct language for factual descriptions: "The company operates in three segments" (not "we believe the company operates in...").
- Adopt a teaching posture in early sections (Company Overview through Business Model). The reader may be encountering this company for the first time. Explain the business clearly before analyzing it.
- Shift to analytical and opinionated in later sections (Competitive Analysis through Investment Recommendation). By the time the reader reaches valuation, the tone should carry conviction.
- Maintain objectivity in descriptive sections. Competitive Analysis and Risk Analysis should present both sides. Reserve advocacy for the Investment Recommendation.

### Sentence Structure

- Front-load important information. Put the conclusion or key figure first in each sentence, then the explanation or context.
- Keep paragraphs focused: one idea per paragraph, 3-5 sentences. Initiation reports are longer but should not feel dense — white space and clear structure carry the reader.
- Use topic sentences to anchor each paragraph. A reader skimming only the first sentence of each paragraph should get the full narrative.
- Use semicolons to connect related data points within a sentence rather than splitting into multiple sentences: "Revenue grew 18% YoY to $42.3bn; operating margin expanded 120bps to 31.2%."

### Transitions and Connectors

All transitions from the Stock Update Style Guide apply (Section 1: Transitions and Connectors). Additional transitions specific to initiation reports:

- "Putting this in context," to transition from description to analysis
- "The key question for investors is..." to frame the central debate
- "We see [X] as the primary differentiator because..." to transition from competitive description to moat assessment
- "On balance," to summarize after a strengths-vs-weaknesses discussion
- "We derive our [price target/valuation] from..." to introduce the valuation methodology
- "The investment case rests on..." to frame the final recommendation

### What to Avoid

All items from the Stock Update Style Guide (Section 1: What to Avoid) apply. Additional items specific to initiation reports:

- Company press release language. Do not parrot the company's own marketing or mission statements. Restate facts in analytical terms.
- Lazy qualitative claims: "strong management team", "best-in-class technology", "industry-leading margins" — unless immediately substantiated with data: "industry-leading gross margins of 74.5%, 15ppts above the peer median of 59.2%."
- Symmetry for its own sake. If the company has 5 clear strengths and 2 weaknesses, do not pad the weaknesses list to match. Present what is real.
- Excessive history. Company Overview should cover founding and milestones in 2-3 sentences, not a multi-paragraph corporate history. The reader is here for the investment case.
- DCF worship. Do not present a DCF model as precise truth. Always state key assumptions and sensitivity: "Our DCF implies $142 per share, but the result is sensitive to the terminal growth rate assumption (a 50bps change in terminal growth shifts the value by ~$12)."


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
- State assumptions explicitly: "We assume Data Center revenue grows at 35% YoY in FY2027E, driven by Blackwell ramp and enterprise AI adoption"
- Compare to consensus where available: "Our FY2027E EPS of $5.42 is 8% above Bloomberg consensus of $5.02"
- Show the bridge from current to projected: what drives revenue growth, what drives margin change
- Include sensitivity: "Each 5ppt change in Data Center growth moves FY2027E EPS by approximately $0.40"

**Don't:**
- Present projections without stating assumptions — black-box forecasts have no credibility
- Show only EPS without the revenue-to-earnings build — the reader needs to see where growth comes from
- Project more than 3 years unless the business has unusual long-term visibility (infrastructure, backlog)
- Use unrealistic precision: "$42,317.4mn" is false precision for a forecast — round to "$42.3bn"


### 2.12 Valuation Analysis

**Purpose:** Derive a target price using appropriate methodologies and contextualize it against history and peers.

**Structure:** Three parts. (1) Valuation models: apply 2-3 appropriate methods (P/E, P/B, DCF, EV/EBITDA, PEG, sum-of-parts) depending on the company type. For each, show the inputs and the resulting target price in a table. Derive conservative, base, and optimistic targets. (2) Historical P/E trend: a line chart showing the stock's trailing or forward P/E over 5+ years with the current level marked, plus the mean and +/- 1 standard deviation bands. (3) Peer valuation comparison: a table showing P/E, P/B, EV/EBITDA, and other relevant multiples for the target company vs. 3-5 peers.

**Tone:** Precise and transparent. Show the math. Valuation is the section readers scrutinize most — every number must be traceable.

**Data integration:** Valuation conventions follow the same rules defined in the Stock Update Style Guide (Section 2.5: Valuation and Price Target) and the Sector Research Style Guide (Section 2.7: Valuation). The core principle is the same across all three modes: state the methodology, show the multiple, identify the metric it applies to, reference the historical range, and state the implied upside/downside.

**Do:**
- Show the math explicitly: "Base case TP of $185 = 32x FY2027E EPS of $5.78"
- Justify the multiple: "32x is in line with the 5-year average forward P/E of 31x and reflects the company's above-average earnings growth profile (3-year EPS CAGR of 28%)"
- Present a valuation range, not a single point: conservative / base / optimistic with different multiple or growth assumptions
- Cross-check with PEG: "At our base case TP, the stock trades at a PEG of 1.1x, which we view as reasonable for this growth profile"
- Include a sensitivity table showing how the TP changes with different multiple and earnings assumptions

**Don't:**
- Present a DCF as the sole methodology — it is too sensitive to terminal assumptions to stand alone
- Use a methodology that doesn't fit the company: P/B for an asset-light SaaS company, P/E for a pre-profit company
- Ignore what the market is currently pricing: if the stock trades at 45x and your target assumes 32x, explain why de-rating should occur
- Present a target without upside/downside from the current price


### 2.13 Investment Recommendation

**Purpose:** Deliver the final verdict — does the analysis support buying, holding, or selling?

**Structure:** Four components. (1) Rating and target price headline: stated prominently using a rating badge. (2) Bull case summary: 2-3 sentences stating the key upside scenarios and the implied bull-case target price. (3) Bear case summary: 2-3 sentences stating the key downside scenarios and the implied bear-case target price. (4) Key finding: a single sentence distilling the most important reason for the recommendation.

**Tone:** Most opinionated section in the report. This is where the analyst stakes a position. Be confident, but acknowledge the range of outcomes.

**Data integration:** The recommendation should synthesize the entire report: reference the thesis, the competitive position, the financial projections, and the valuation. The target price should match the valuation section. The bull/bear cases should reference specific risks and catalysts from earlier sections.

**Do:**
- Lead with the rating and target price: "We initiate coverage of NVDA with an Overweight rating and a 12-month price target of $185, implying 22% upside from the current price of $152"
- State the bull and bear cases with specific target prices: "Bull case ($230): AI capex accelerates beyond our base case; Bear case ($120): cyclical slowdown in data center spending"
- Reference the key drivers from earlier in the report — this section should feel like a conclusion, not a new argument
- End with a single-sentence key finding that a reader can take away without reading anything else

**Don't:**
- Introduce new information in the recommendation section — everything here should have been established earlier
- Hedge the recommendation to the point of meaninglessness: "We rate the stock Buy but note significant risks" without ranking them
- Omit the target price, upside/downside, or key valuation metric
- Provide a recommendation that contradicts the analysis (e.g., a Buy rating when the valuation section shows the stock is overvalued)


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
- Rating badge (Buy/Hold/Sell or Overweight/Equal-weight/Underweight) displayed prominently
- 12-month price target with upside/downside % from current price
- Current share price with date
- Ticker and exchange
- Market cap (dual currency where applicable)
- One-sentence investment thesis tagline
- Key forecast table: Revenue, EPS, P/E for current year + 2-3 forward years (estimates marked with "E")
- Sector, sub-industry classification
- Report date

### Initiation vs. Update Covers
- Initiation covers are more comprehensive than update covers. They include the full forecast table and sector classification because the reader has no prior context.
- Initiation covers do not show "from/to" changes on ratings or targets (there is no prior to compare to). State the rating and target as new: "Initiate at Overweight, TP $185."
- Include free float % and 3-month ADTV for institutional readers evaluating liquidity.
