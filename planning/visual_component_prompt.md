# Visual-component prompt — equity research v2

Snapshot of every string the WavedReportRunner v2 sends to the section writer about how to assemble visual blocks (charts, tables, callouts, etc.). Two layers: a cache-stable header shared by every section, and a per-section brief naming the preferred exhibit families for that section.

Source of truth:
- Header: `packages/core/src/openlia/llm/runtime/report_v2/sections/prompts.py` (constant `_OUTPUT_FORMAT_REMINDER`)
- Per-section briefs: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` (constant `_SECTION_BRIEFS`)

Regenerate this file after edits:

```
uv run python -c "from openlia.llm.runtime.report_v2.sections.prompts import _OUTPUT_FORMAT_REMINDER; print(_OUTPUT_FORMAT_REMINDER)"
uv run python -c "from openlia.llm.runtime.report_v2.runner import DEFAULT_BRIEFS; [print(f'### {k}\n{v}\n') for k,v in DEFAULT_BRIEFS.items()]"
```

---

## 1. Cached header (every section sees this verbatim)

```
CRITICAL OUTPUT FORMAT — your response must be the section file content EXACTLY in this shape, with no preamble, no markdown code fences, no explanations before or after:

---
section_id: <the section_id from your brief>
title: <Human Readable Title>
sources_used: [<list of [N] manifest ids you cite in this section>]
synthesis_hooks:
  thesis_contribution: "<one sentence>"
  bull_case_inputs:
    - "<bullet with [N] citation marker>"
  bear_case_inputs:
    - "<bullet with [N] citation marker>"
---

## <Section Title>

<your prose here, with [N] inline citation markers>

```chart:bar
title: ...
sources: [N]
```

<more prose>

YOUR RESPONSE MUST:
- Start with `---` on its very first line (no leading whitespace, no preamble, no code fences)
- End immediately after the last word of your final prose paragraph or fenced block (no trailing explanation, no closing code fence)
- Use exactly `---` (three hyphens on a line by themselves) to open AND close the YAML frontmatter
- Include the `synthesis_hooks` mapping (NOT a list — a single object)

Output format details:
- YAML frontmatter with: section_id, title, sources_used (list of [N] manifest ids you cite), synthesis_hooks (only for body sections)
- Markdown body for prose; use [N] inline markers to cite manifest entries
- Typed fenced YAML blocks for structured exhibits: ```table, ```chart:combo, ```metric_cards, ```key_finding, ```bullet_list, ```comparison_split, ```quote, ```timeline, ```pull_quote, ```rating_badge, ```callout_grid, ```chart:line, ```chart:bar, ```chart:area, ```chart:pie, ```chart:candlestick, ```chart:waterfall, ```chart:scatter, ```chart:heatmap, ```chart:treemap, ```group, ```text
- Each block carries a `sources: [N, ...]` list of manifest ids
- Do not invent citations; only cite [N] markers that resolve to entries in the manifest above.

Body sections MUST include a `synthesis_hooks` mapping in the frontmatter with EXACTLY this shape (a single object, not a list):

  synthesis_hooks:
    thesis_contribution: "One sentence on what this section contributes to the investment thesis."
    bull_case_inputs:
      - "Bullet point with [N] citation marker"
    bear_case_inputs:
      - "Bullet point with [N] citation marker"

Do NOT wrap `synthesis_hooks` in a list. There is ONE hook per section.

YAML safety: if any string value contains a colon (`:`), wrap the value in double quotes. Example:
  title: "Industry Overview: Network Security and Edge"
  (NOT: title: Industry Overview: Network Security and Edge)
This applies to title, eyebrow, tagline, thesis_contribution, and any other free-form string in the frontmatter.

CHART BLOCK SHAPES — use these exact field names and shapes:

```chart:bar
title: "Revenue by segment"
categories: ["Segment A", "Segment B", "Segment C"]
series:
  - name: "FY2024 Revenue"
    values: [120, 85, 50]
sources: [1, 3]
```

```chart:line
title: "Revenue trend"
categories: ["2020", "2021", "2022", "2023", "2024"]
series:
  - name: "Revenue ($M)"
    values: [100, 120, 145, 180, 220]
x_label: "Year"
y_label: "Revenue ($M)"
sources: [1]
```

```chart:area
title: "Cumulative growth"
categories: ["2020", "2021", "2022", "2023", "2024"]
series:
  - name: "Customers (M)"
    values: [1.2, 1.8, 2.5, 3.4, 4.6]
sources: [1]
```

```chart:scatter
title: "Growth vs valuation"
series:
  - name: "Peers"
    points:
      - {x: 12.5, y: 30.1}
      - {x: 18.3, y: 42.6}
      - {x: 24.0, y: 55.0}
x_label: "Revenue growth %"
y_label: "EV/Sales"
sources: [1]
```

```chart:combo
title: "Revenue vs margin"
categories: ["2020", "2021", "2022", "2023", "2024"]
bar_series:
  - name: "Revenue ($B)"
    values: [0.43, 0.65, 0.97, 1.30, 1.67]
line_series:
  - name: "Gross margin (%)"
    values: [76, 77, 75, 77, 77]
sources: [1]
```

CHART SERIES KEY — every series in bar/line/area/combo uses ``values: [n, n, n]`` (a flat list of numbers aligned to ``categories``). Scatter uses ``points: [{x, y}, ...]``.

EXHIBIT SELECTION — choose the block type that matches the data SHAPE.

- Single value (one number with a label) fits ``metric_cards`` or ``key_finding``.
- One metric over time fits ``chart:line`` or ``chart:area``.
- Two correlated metrics over time (e.g., revenue + margin %) fit ``chart:combo``.
- Composition or share of a whole fits ``chart:pie``, ``chart:treemap``, or stacked ``chart:bar`` once the categorical axis has three or more items.
- Ranked items where the ranking itself is the message fit ``chart:bar`` horizontal, up to eight rows.
- Events or catalysts in time order fit ``timeline``.
- Two-sided framings (bull/bear, pros/cons, strengths/weaknesses, before/after) fit ``comparison_split``.
- Three to six concept callouts (pillars, drivers, frameworks, product families) fit ``callout_grid``.
- Multi-row, multi-column structured data (KPIs, peer matrices, officer rosters) fit ``table``.
- Notable attributed lines fit ``quote`` (third-party) or ``pull_quote`` (editorial).

VARIETY — aim for three to five distinct exhibit families across the report and keep ``chart:bar`` to a minority of the chart blocks. The framework brief names the preferred exhibits for this specific section; start from that list.

OWNERSHIP — each metric or breakdown has a natural home section. When a peer section already owns an exhibit (e.g., ``historical_financials`` owns the revenue trend), other sections reference it in prose and pick a different exhibit family for their own data.

```metric_cards
metrics:
  - label: "Market Cap"
    value: "$69.83B"
  - label: "P/E (TTM)"
    value: "245x"
    delta: "+12%"
    delta_direction: "up"
sources: [1]
```

```key_finding
content: "Revenue grew at a 30% CAGR over 2020-2024, outpacing the peer median of 18%."
sources: [1, 3]
```

```pull_quote
text: "Our platform is becoming the system of record for the AI-native enterprise."
attribution: "Bill McDermott, CEO"
source: "Q4 2024 earnings call"
timestamp: "2025-01-29"
sources: [2]
```

```callout_grid
columns: 3
items:
  - eyebrow: "Pillar 1"
    title: "Workflow automation"
    description: "Now serves as the system of record across IT, HR, and customer service."
  - eyebrow: "Pillar 2"
    title: "AI integration"
    description: "Generative-AI co-pilots embedded into every workflow surface."
  - eyebrow: "Pillar 3"
    title: "Industry verticals"
    description: "Pre-packaged solutions for telecom, banking, and public sector."
sources: [1]
```

```timeline
title: "Recent catalysts"
events:
  - when: "2024-Q3"
    what: "Launched Now Assist AI suite across all workflows"
    impact: "Lifted ARR guidance by 2 percentage points"
    impact_tag: {label: "Beat", tone: "positive"}
  - when: "2024-11"
    what: "Acquired Element AI for $230M"
    impact: "Adds NLP and computer-vision research talent"
  - when: "2025-Q1"
    what: "Reorganized go-to-market into industry-aligned squads"
```

```chart:pie
title: "Revenue mix by geography"
segments:
  - label: "North America"
    value: 65
  - label: "EMEA"
    value: 22
  - label: "APAC"
    value: 13
donut: true
sources: [1]
```

```chart:waterfall
title: "FY24 revenue bridge ($M)"
items:
  - label: "FY23 revenue"
    value: 8971
    type: "total"
  - label: "Existing customer expansion"
    value: 1645
    type: "increase"
  - label: "New logos"
    value: 882
    type: "increase"
  - label: "Churn"
    value: -220
    type: "decrease"
  - label: "FY24 revenue"
    value: 11278
    type: "total"
sources: [1]
```

```table
title: "Peer multiples"
headers:
  - {key: "company", label: "Company"}
  - {key: "pe", label: "P/E (TTM)", align: "right"}
  - {key: "growth", label: "Rev growth %", align: "right"}
rows:
  - {company: "ServiceNow", pe: "56.6x", growth: "23%"}
  - {company: "Workday", pe: "44.1x", growth: "16%"}
  - {company: "Salesforce", pe: "28.9x", growth: "11%"}
sources: [1, 2]
```

```bullet_list
items:
  - "Backlog of $20.6B at the end of Q4, up 26% year on year"
  - "Net retention rate of 124%, the highest in the peer set"
  - "Operating cash flow margin expanded 220 basis points"
tone: "positive"
```

```quote
text: "We see ==durable acceleration== in subscription bookings."
speaker: "Gina Mastantuono"
role: "CFO, ServiceNow"
timestamp: "Q4 2024 earnings call"
tag: {label: "Guidance", tone: "positive"}
sources: [3]
```

```rating_badge
rating: "BUY"
previous_rating: "HOLD"
change_date: "2026-05-18"
```

```comparison_split
left:
  title: "Bull Case"
  tone: "positive"
  items:
    - "Edge network expansion accelerates [1]"
    - "Workers platform monetization ramps [2]"
right:
  title: "Bear Case"
  tone: "negative"
  items:
    - "Multiple compression risk at current valuation [3]"
    - "Hyperscaler competition intensifies [4]"
```

If you cannot construct a valid chart block with these exact field names, use a `table` or `metric_cards` block instead. DO NOT invent alternate chart field names like `data: {labels, values}` — they will be rejected.

CITATION PROXIMITY RULE: every quantitative figure in prose (revenue, margins, percentages, dollar amounts, ratios, growth rates, counts) MUST have an inline [N] citation marker within ~10 words of the figure. Bare numbers without nearby citations will fail validation. Years (e.g., "2024", "founded in 2009") are NOT quantitative figures and do not need citations.

NEVER USE TOMBSTONE LANGUAGE. The following phrases (and any close variant) will fail validation and waste your retry budget:
  - "no data available"
  - "data not provided"
  - "data unavailable"
  - "N/A" or "n/a" (as standalone prose)
  - "TBD"
  - "unable to determine"

If a specific fact you would like to cite is not in the manifest or facts slice, REWRITE the sentence so it does not need that fact. Use what IS available, frame qualitatively, or omit the point entirely. Manifest entries and the facts slice are your ONLY source of truth — write to their strengths, not around their gaps. A shorter, factually grounded section beats a complete section padded with disclaimers.
```

---

## 2. Per-section briefs

Each section receives the header above plus the single brief below as its `framework_brief` argument.

### `company_overview`

> Section: company_overview. Cover ticker, sector, headquarters, headcount, founding date, key milestones, and core value proposition. Preferred exhibits: ``metric_cards`` for headline stats (market cap, P/E, revenue scale, headcount), ``key_finding`` for the positioning one-liner, ``pull_quote`` for the mission or CEO line.

### `industry_overview`

> Section: industry_overview. Describe market size, growth, structure, and where the company sits. Preferred exhibits: ``chart:pie`` or ``chart:treemap`` for market share or segmentation, ``chart:bar`` for player ranking once there are three or more competitors, ``callout_grid`` for market segments, ``table`` for TAM/SAM/SOM.

### `products_and_services`

> Section: products_and_services. Walk through product families, pricing, and customer types. Preferred exhibits: ``callout_grid`` with eyebrow + description for each product or module family, ``table`` for a feature matrix, ``bullet_list`` for a tight list of capabilities.

### `business_model`

> Section: business_model. Cover revenue model, unit economics, moats, and distribution. Preferred exhibits: ``callout_grid`` for revenue pillars, ``chart:pie`` for revenue mix when disclosed, ``comparison_split`` for the model vs. its nearest alternative, ``key_finding``.

### `management_team`

> Section: management_team. Profile the C-suite and board with named individuals. Preferred exhibits: ``table`` for the officer and director list with role + background, ``key_finding`` for notable hires or departures.

### `historical_financials`

> Section: historical_financials. Show revenue, profitability, cash, and balance-sheet trends. Preferred exhibits: ``chart:combo`` for revenue bars plus a margin line across multiple years, ``chart:line`` for a single-metric trend, ``table`` for the multi-period KPI grid.

### `financial_analysis`

> Section: financial_analysis. Decompose margins, capital efficiency, and ratios. Preferred exhibits: ``chart:line`` for margin trends, ``table`` for KPIs vs. peers, ``waterfall_chart`` for a revenue or EBITDA bridge, ``key_finding``.

### `financial_projections`

> Section: financial_projections. Forward look on revenue, margins, FCF. Preferred exhibits: ``chart:line`` for the 3-5 year projection curve, ``chart:combo`` for revenue + growth %, ``table`` for assumptions plus outputs.

### `valuation_analysis`

> Section: valuation_analysis. Multiples, DCF, peer comp. Preferred exhibits: ``table`` for the peer multiples matrix, ``chart:scatter`` for P/E vs. growth, ``comparison_split`` for bull / base / bear cases, ``waterfall_chart`` for a DCF bridge.

### `competitive_analysis`

> Section: competitive_analysis. Name competitors and quantify where the company stands. Preferred exhibits: ``comparison_split`` for subject vs. top rival, ``table`` for a feature or share matrix. Peer revenue ranking is owned by ``industry_overview`` — reference it in prose here and use a different exhibit family.

### `recent_developments`

> Section: recent_developments. Catalysts and news flow in the last twelve months. Preferred exhibits: ``timeline`` with dated events and ``impact_tag`` annotations whenever you have at least three dated events, ``key_finding`` for the single most important development, ``bullet_list`` for a tight catalog when dates are not available.

### `competitive_advantages_and_weaknesses`

> Section: competitive_advantages_and_weaknesses. Preferred exhibits: ``comparison_split`` for strengths (left tone positive) vs. weaknesses (right tone negative), ``callout_grid`` for moats by type, ``key_finding`` for the durable advantage.

### `risk_analysis`

> Section: risk_analysis. Preferred exhibits: ``callout_grid`` for risk categories (market, regulatory, execution, financial), ``comparison_split`` for controlled vs. uncontrolled risks, ``timeline`` for known risk events.

### `investment_recommendation`

> Section: investment_recommendation. Preferred exhibits: ``rating_badge`` for the BUY/HOLD/SELL call with ``previous_rating`` and ``change_date``, ``metric_cards`` for price target / upside / time horizon, ``pull_quote`` for the one-sentence thesis.

### `cover`

> Section: cover. Headline summary. Preferred content: a tldr list of 3-5 short bullets and ``key_metrics`` (the server already populates market cap and P/E). The cover renders best as text and metrics; leave exhibit blocks to the body sections.
