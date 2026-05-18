# Equity Research — Stock Initiation Report Prompt Walkthrough

A complete annotated breakdown of every prompt fed to the model when generating a stock initiation report on the classic `ReportRunner` path. Each instruction block is paired with its purpose and the output it's meant to produce.

**Generated:** 2026-05-17

**Source files referenced:**
- System prompt entry: `packages/core/src/openlia/prompts/equity_research.yaml` (`report.system` slot, lines 25-43)
- Strictness rules: `packages/core/src/openlia/prompts/shared/report_schema_strictness.yaml.j2`
- Two-source discipline: `packages/core/src/openlia/prompts/shared/two_source_discipline.yaml.j2`
- Tool discovery: `packages/core/src/openlia/prompts/shared/tool_discovery.yaml.j2`
- Output discipline: `packages/core/src/openlia/prompts/shared/output_discipline.yaml.j2`
- User prompt: `packages/core/src/openlia/prompts/equity_research.yaml` (`stock_initiation.user`, lines 115-152)
- Framework JSON: `packages/core/src/openlia/reports/frameworks/stock_initiation.json`
- Style guide: `packages/core/src/openlia/reports/frameworks/stock_initiation_style_guide.md`

---

## Layer 1 — System prompt header

```
You are the Equity Research analyst drafting a professional report.
Follow the style guide below exactly. Fill the framework schema.
```

| What | Purpose | Expected output |
|------|---------|-----------------|
| Role framing + two imperatives | Sets persona (equity analyst, not a chat assistant), binds the model to two artifacts: the style guide and the schema. Single sentence so it doesn't crowd the cache prefix. | Output that reads as a research report, conformant to the schema. |

---

## Layer 2 — Style guide (`stock_initiation_style_guide.md`, ~389 lines)

The full style guide is interpolated. Key instruction blocks:

### 2A. Tone and voice

> "Authoritative but measured… use hedging ('we believe') for forward projections, direct language for facts… teaching posture in early sections, analytical in later sections… objectivity in descriptive sections, advocacy only in Investment Recommendation."

**Purpose:** Shifts voice across the report's arc. Initiation reports differ from event-driven updates — the analyst builds a case from scratch, not reacts.
**Expected output:** Section-aware tone — Company Overview reads as introduction; Investment Recommendation reads as conviction.

### 2B. Sentence structure

> "Front-load important info… 3-5 sentences per paragraph, one idea each… topic sentences… semicolons to chain data points."

**Purpose:** Bulge-bracket scannability — a reader skimming first sentences should reconstruct the narrative.
**Expected output:** Topic-sentence-driven paragraphs, dense data delivered via semicolons rather than fragmenting.

### 2C. What to avoid

> "No press release language. No lazy qualitative claims ('best-in-class', 'industry-leading') unless immediately substantiated with numbers. No symmetry for its own sake. No DCF worship."

**Purpose:** Forces every adjective to be load-bearing. The "industry-leading margins" → "industry-leading gross margins of 74.5%, 15ppts above the peer median" pattern is the discipline.
**Expected output:** Quantified adjectives or no adjectives.

### 2D. Per-section guidelines (2.1 – 2.13)

Each section has four annotated fields: **Purpose / Structure / Tone / Data integration**, plus **Do / Don't / Exemplar**. Highlights:

- **2.1 Company Overview**: Single narrative paragraph (4-6 sentences) + metric cards block with 5-7 key facts. Don't start with founding history; lead with what the company is today. Expected: ~150-word intro + metric cards.
- **2.2 Industry Overview**: Industry definition + state + TAM sizing with 5y CAGR + projected growth + drivers. Combo or area chart showing market size over time.
- **2.3 Products and Services**: Per-product narrative framed around customer pain + revenue breakdown pie/donut + segment growth table.
- **2.4 Business Model**: Revenue model precisely identified (recurring vs. one-time, subscription vs. transaction); customer/supplier concentration flagged; unit economics tied to metrics.
- **2.5 Competitive Analysis**: Three parts — competitor profiles (1-2 sentences each), comparison table (3-5 peers × 6-8 dimensions), moat assessment using a recognized framework (network effects / switching costs / cost advantages / intangible assets / efficient scale).
- **2.6 Management Team**: Table (Name/Title/Background/Tenure) + qualitative assessment with insider ownership %, tenure, governance concerns.
- **2.7 Competitive Advantages and Weaknesses**: Two-column layout, 5-6 points per side, each with a supporting data point. End with single-sentence key finding.
- **2.8 Risk Analysis**: Industry / Operational / Financial risk subsections, 2-4 specific risks each. End with risk-level rating badge.
- **2.9 Historical Financial Data**: 5y balance sheet table + 5y income statement table with YoY growth rates + M&A discontinuity narrative + revenue/margin combo chart.
- **2.10 Financial Analysis**: Margin trends (table + line chart), financial health scorecard (current/quick/D-E/interest coverage/OCF ratios), peer efficiency comparison.
- **2.11 Financial Projections**: 3-year forecast table + 3-5 bullet assumptions + combo chart. "Bridge from current to projected" must be visible. Includes the rule against `$42,317.4mn` false precision — round to `$42.3bn`.
- **2.12 Valuation Analysis**: 2-3 valuation models (P/E, P/B, DCF, EV/EBITDA, PEG, SOTP) with Conservative/Base/Optimistic targets + historical P/E band chart + peer valuation table.
- **2.13 Investment Recommendation**: Rating badge headline + bull case + bear case + single-sentence key finding. Don't introduce new info here; synthesize the whole report.

### 2E. Data presentation rules

> "Initiation-specific table types: competitor comparison, management team, historical financials (5y), financial health scorecard, valuation scenarios (Conservative/Base/Optimistic), peer valuation."

**Purpose:** Standardizes the visual vocabulary so every initiation report carries the same scannable artifacts.
**Expected output:** Each named table type, populated.

### 2F. Cover page conventions

> "Rating badge, 12-month TP with upside %, current price + date, ticker, market cap, one-sentence thesis tagline, key forecast table (Rev/EPS/PE current + 2-3 forward), sector classification."

**Purpose:** The cover is what a reader sees in 5 seconds — it must carry the verdict standalone.
**Expected output:** Cover with all 8 fields populated; "Initiate at Overweight, TP $185" framing (no "from/to" since there's no prior coverage).

---

## Layer 3 — Output discipline (`output_discipline.yaml.j2`)

```
- Follow the requested output format exactly. No extra commentary before or after.
- If the user asks for a report, fill the provided schema. Leave instruction-only fields empty.
- When data is missing, state it plainly. Do not fabricate numbers.
```

| Instruction | Purpose | Expected output |
|---|---|---|
| Format compliance | Suppresses meta-commentary ("Here is the report you asked for…"). Tool-only output. | Pure `submit_report` tool call, no prose chatter. |
| Fill schema, leave instructions empty | Tells the model the framework JSON's `instructions` fields are scaffolding, not content to copy back. | Submission contains real values, not the verbatim instruction strings. |
| State missing data plainly, don't fabricate | Anti-hallucination guardrail at the top level. | Honest "Data not available" rather than invented numbers. |

---

## Layer 4 — Schema strictness (`report_schema_strictness.yaml.j2`)

The most rule-heavy block. Each bullet is a defense against a specific past failure mode.

| # | Instruction (paraphrased) | Purpose | Expected output |
|---|---|---|---|
| S1 | `extra="forbid"` on every model — read the tool's parameter schema as the source of truth | Tells the model that drift in field names will be hard-rejected, not silently dropped | No unexpected keys in any payload |
| **S2 (F20)** | `citations` lives at root, not in rail. `meta_stats` is server-only. **WRONG / CORRECT JSON examples shown.** | This is the rail.citations regression fought twice — explicit example puts it ahead of model muscle-memory | `{cover, sections, rail:{verdict,quick_stats,sparkline}, citations:[…]}` shape |
| S3 | `cover.title`/`subtitle`/`tagline` required strings | Cover is the must-haves. Schema rejects empty cover. | Three populated strings minimum |
| S4 | Each section: `id` (snake_case) + `title` + non-empty `blocks` | Sections cannot ship as titles-only stubs | Real blocks per section |
| S5 | Do NOT emit `page_furniture`, `schema_version`, `department`, `generated_at` | Server-owned fields the model recurrently included | Absent from payload |
| S6 | Do NOT copy framework scaffolding (`instructions`, null placeholders) | Framework JSON is read-only context, not a template to mutate | No `"instructions": "..."` strings echoed back |
| S7 | Chart `options` = `{height, show_legend, show_grid}` ONLY. `height` is enum `small`/`medium`/`tall` (not pixels). | Recurring drift: model emits `height: 320` or `"note"` keys | Strict-shape options |
| S8 | `combo_chart.bar_series`/`line_series`: `{name, values: [float, ...]}`. Do NOT use `data`. | F4-era drift — model confuses combo with line chart series shape | Correct combo-series shape |
| S9 | Table `headers` = list of `{key, label}` objects, never plain strings | F3-era drift — plain string headers fail validation | Object headers |
| S10 | Metric `value`/`delta` are strings (`"12.3%"`, `"$1.23"`), not floats | Models default to numeric; schema requires strings for display formatting | Pre-formatted strings |
| S11 | `rail.sparkline.points` = list of `{x:float, y:float}` (min 2), not flat numeric arrays | Recurring drift — model emits `[120.5, 121.2]` | Object-pair array |
| S12 | `rail` has no `source_ids` field (sources live on each Metric child) | F3-era drift | No `source_ids` directly on rail |
| S13 | **Source attribution mandate**: every Metric, key_finding, pull_quote, quote, and quantitative cell must carry inline `[N]` brackets OR `source_ids: ["1","2",...]` | F2-era enforcement — the foundational citation discipline | Either inline brackets or populated source_ids on every quantitative block |
| S14 | `source_ids` are numeric strings (`"1"`, `"2"`), NOT `"c1"`/`"cite-1"`/raw provider body | F6/F6b drift fix — c-prefix translates server-side but model should learn | Numeric strings only |
| S15 | Chart blocks MUST contain real data. Empty `series`/`slices`/`bar_series` rejected. Omit the chart and explain in adjacent text. | F4 enforcement — no blank chart boxes | Either populated chart or no chart |
| S16 | "Data not available" requires a prior `web_search` for that specific data point | F5/F7 enforcement — kills lazy LLM punts | Earned, not reflexive, use of the phrase |
| S17 | NEVER submit a section whose entire content is one "data not available" line — ≥200 words of qualitative narrative even when quantitative data is missing | F7 enforcement | Substantive section even when numbers are missing |
| S18 | On validation failure, you receive errors as tool results — fix every listed field and re-submit the entire payload | Tells the model the repair contract (whole-report re-emission; the F20 instruction strengthens this for rail-specific failures) | Re-submit with all errors addressed |

---

## Layer 5 — Tool discovery (`tool_discovery.yaml.j2`)

| Block | Purpose | Expected output |
|---|---|---|
| **Toolset starts minimal**: `request_additional_tools`, `web_search`, utilities — no data tools loaded | Just-in-time discovery; keeps the tool list compact in the cache prefix. | Model calls `request_additional_tools` on turn 0 to load EODHD/FMP. |
| **`web_search` is not optional** — it's the canonical source for qualitative claims | Anchors the two-source discipline. | Model uses `web_search` when fetching qualitative context (industry state, recent news). |
| `request_additional_tools(reason, category_hint?)` — describe a concrete need; hints are `financial`/`news`/`web_search` | Forces specific reasons (better retrieval). | "NVDA quarterly income statements for the last 8 quarters" not "I need financials." |
| **Stub format**: large results return a `ref` + structural metadata + sample preview — call `read_payload(ref, path)` for real values | Cost-control on large payloads (10y daily OHLC). | Model uses stubs for routing, `read_payload` for any number quoted in the report. |
| **A stub is shape, not data** — never quote from samples | F4-era discipline — sample values are not real | No numbers extracted from stub samples. |
| `read_payload` path forms: `key.subkey`, `rows[0]`, `rows[0:5]`, `rows.column`, bracket-string for keys with punctuation | Documents the path mini-language including the fix for keys with spaces/dots/`%` | Correct path syntax; retry with bracket form on `parse error` before falling back. |
| **Writing phase**: continue calling `read_payload` for synthesis; call `submit_report` exactly once | Tells the model what's available in the writing phase (only `submit_report` + `read_payload`) | Exactly one `submit_report` per the runner's contract. |

---

## Layer 6 — Cache breakpoint sentinel

```
<!-- OPENLIA_CACHE_BREAKPOINT -->
```

**Purpose:** Anthropic adapter splits the system prompt at this marker for prompt caching. Everything ABOVE is the stable prefix (gets cached); everything below changes per-request (date, search budget, ticker conventions). This was moved here so two_source_discipline + temporal_anchor are below the cache line.
**Expected effect:** ~80%+ cache hit rate.

---

## Layer 7 — Temporal anchor

| Block | Purpose | Expected output |
|---|---|---|
| "Today is Sunday, May 17, 2026. Anchor every 'today', 'recent', 'as of' to this date — never to your training cutoff." | Prevents the model from grounding "recent" claims in stale knowledge. | Every relative date references 2026-05-17. |
| Built-in knowledge of prices/ratings/EPS/filings is months-to-years out of date — treat as hypothesis, not source of truth. Fetch or `web_search`. | Forces tool-grounding for time-sensitive facts. | "Data not available as of 2026-05-17" if neither tool yields it. |
| When `web_search` is in toolset, use it to verify recent events and ground "latest" / "YTD" / "this quarter" claims. | Specifies which class of claims gets web_search vs which gets provider tools. | Web for unstructured/breaking; providers for financials/filings. |

---

## Layer 8 — Two-source discipline (the longest single block)

| Block | Purpose | Expected output |
|---|---|---|
| **Provider tools = numerical truth**: valuation, ratios, performance attribution, technical signals, screening, calendar events, any claim involving specific prices/multiples/growth rates | Hard rule: numbers come from EODHD/FMP/Flashalpha, not web snippets | `[get_fundamentals_data(AAPL.US)]` brackets for numeric claims |
| **Web search = qualitative analysis**: industry structure, competitive landscape, business model, management commentary, regulatory context, recent strategic moves | Hard rule: prose narrative comes from search, never from training memory | `[Reuters, "title", date, url]` brackets for narrative claims |
| Provider `Description` blurbs are orientation only, NOT citations | Common drift: model paraphrases EODHD's company description and cites the EODHD tool call | No paraphrased provider blurbs as primary narrative |
| When both are needed (most cases): fetch numbers FIRST, then add context via search, then synthesize | Specifies order — search interprets, doesn't substitute | Numbers anchor; narrative explains |
| If provider data and search conflict on a value: trust the provider, flag the discrepancy | Often signals a corporate action or stale snapshot | Flagged value mismatches |
| **Web search MANDATED before writing**: industry_overview, products_and_services (narrative), business_model, competitive_analysis, management_team (assessment), risk_analysis, recent_developments, financial_projections (narrative), valuation_analysis (narrative) | Forces grounding for 9 of 14 sections | At least one dated web source loaded before authoring each |
| "no current sources found as of 2026-05-17" — do NOT fall back to memory | Hard refusal of memory-fallback citations | Section omits the claim if search yields nothing |
| Mixed claims: source each component separately ("revenue grew 8% [provider] driven by services strength [search]") | Forces compositional citation | Both brackets present on hybrid sentences |
| **Search budget: 8 web searches per report** | Cost cap on search volume | Prioritize mandated sections; before each search state in one line what you expect to find |
| **Citation format**: emit the full tuple every time. Server dedupes and assigns `[1]`, `[2]`. Don't pre-number. | Server-side dedup means model can be verbose; saves cognitive load | Full `[source, "title", date, url]` tuples inline |
| `read_payload(ref, path)` is NOT a source — cite the ORIGINAL tool call | Common drift documented as an anti-pattern | `[get_fundamentals_data(NVDA.US)]`, not `[read_payload(r_5e63_01, General)]` |
| Anti-patterns enumerated: vague claims, search for what providers cover, citing read_payload | Explicit gallery of failure modes | Avoidance of each |

---

## Layer 9 — EODHD ticker conventions

| Block | Purpose | Expected output |
|---|---|---|
| US: `.US` (AAPL → `AAPL.US`). Indices: `.INDX`. Commodities: `.COMM`. Forex: `.FOREX`. Crypto: `.CC`. Other exchanges: `.LSE`, `.TO`, `.HK`, `.TYO`, `.PA`. | Connector quirk — connector won't silently rewrite. | Tool calls use the correct suffix per asset type. |
| "If a tool returns 'symbol not found' on a bare ticker, retry with the EODHD suffix before falling back to `web_search`" | Defends against giving up too early on a ticker miss | Retry path documented |

---

## Layer 10 — User prompt (`stock_initiation.user`)

```
Generate a Stock Initiation Report for NET.

Apply these customizations:
- Enabled sections: all
- Custom sections: []
- Length preference: standard

Call data tools as needed to collect financials, analyst views,
recent news, and any other inputs the framework requests.
```

| Block | Purpose | Expected output |
|---|---|---|
| Mode declaration + ticker | The task statement. | Stock initiation for the given ticker. |
| Customizations (enabled/custom sections, length) | Per-user knobs from the Equity Research config UI. `enabled_sections: all` means the full 14. | Sections respect this filter. |
| "Call data tools as needed…" | Permission to escalate via `request_additional_tools`. | Tool calls in fetching phase. |

### F23 addendum

```
USE THE DATA YOU FETCHED. Every tool result … small payloads are
delivered inline … Extract real numbers from those inline payloads
into cover.key_metrics:
  - Stock Price → close from get_live_stock_prices …
  - Market Cap → most recent value from get_historical_market_capitalization_data …
  - Other metrics — pull from get_fundamentals_data.Highlights / Valuation …
Only write "No data available" when (a) you actually called the
relevant tool and got back empty/error, OR (b) you searched the web
and came up empty.
```

**Purpose:** Closes the regression where model wrote "No data available" for fields whose source payload was already in conversation.
**Expected output:** Cover key_metrics populated from inline EODHD data.

```
When you call submit_report, populate BOTH cover AND sections:
- cover.title, cover.subtitle, cover.tagline are REQUIRED strings.
- Each section needs id, title, and non-empty blocks.
```

**Purpose:** Belt-and-suspenders reminder of the two strict requirements that recurrently fail.
**Expected output:** Both populated.

---

## Layer 11 — Framework JSON (embedded in user prompt)

The whole `stock_initiation.json` is dumped under `--- FRAMEWORK ---`. The model reads three classes of instructions:

### 11A. `cover.instructions`

> "Title='Stock Initiation Report'. Subtitle is the full company name. Eyebrow is a short context line ('Stock Initiation · <date>'). Ticker is the symbol. Tagline is a one-sentence investment thesis. tldr is 1–3 short paragraphs… Key metrics: current stock price (with recent % change), market cap, P/E ratio, and 1–2 others most relevant."

**Purpose:** Fills the cover from a deterministic recipe.
**Expected output:** Cover with the seven fields populated per the recipe.

### 11B. Per-section `instructions` (14 sections)

Each section has its own paragraph-length brief. Examples:

- **company_overview**: "Concise profile: full name, ticker, year founded, HQ, main products/services, employee count. Narrative paragraph + metric cards block."
- **industry_overview**: "Industry definition + state (govt incentives/restrictions, drivers/constraints). Market sizing (TAM in $, 5y historical CAGR, projected growth + drivers, market size by target year). Combo or area chart showing historical+projected market size."
- **products_and_services**: "Per-product description framed around customer pain + revenue breakdown pie/donut + per-segment revenue and growth rates table."
- **business_model**: "Identify all stakeholders + value chain position + revenue model (subscription/transaction/licensing/etc.) + key business metrics (gross margin, customer count, ARPU, retention)."
- **competitive_analysis**: "Three areas: competitor profiles, comparison table across multiple dimensions with cell formatting highlighting where target leads/lags, moat assessment (network effects / switching costs / cost / intangibles / efficient scale)."
- **management_team**: "Executive profile table (name, title, background, tenure) + governance red flags (CFO turnover, related-party transactions, regulatory actions)."
- **competitive_advantages**: "Two-column group layout (strengths vs. weaknesses) across 6 dimensions: product, business model, sales/distribution, management, technology, financial position. End with key_finding net assessment."
- **risk_analysis**: "Three categories: Industry / Operational / Financial risks. Each as subsection with text block. Rating badge or key_finding summarizing overall risk level (Low/Moderate/High/Very High)."
- **recent_developments**: "Qualitative context from last ~30 days. Company-specific news, analyst actions, regulatory developments, sector/macro events. **Call web_search to gather sources** — structured tools don't cover this. Cite each item inline."
- **historical_financials**: "Fiscal year end + 5y balance sheet table + 5y income statement table (with YoY growth) + M&A discontinuity narrative + combo charts for revenue and margin trends."
- **financial_analysis**: "Margin ratios table + line chart + financial health ratios (current/quick/D-E/interest coverage/OCF ratios) + peer efficiency comparison (AR/inventory/AP days)."
- **financial_projections**: "3-year forecast (revenue, growth, op income, net income, EPS) + assumptions + combo chart + comparison to consensus where available."
- **valuation_analysis**: "Three areas: valuation models (P/E, P/B, DCF, EV/EBITDA depending on company type) with conservative/base/optimistic targets in a table; historical P/E trend line chart with current vs. mean; peer valuation comparison table."
- **investment_recommendation**: "Current stock price + date. Rating badge (Buy/Hold/Sell or Overweight/Equal/Underweight). Bull case 2-3 sentences, bear case 2-3 sentences. Target price, expected upside/downside. End with key_finding containing the single most important reason."

**Purpose:** Section-by-section recipe. Tightly coupled to the style guide's per-section Do/Don't lists in Layer 2 — the framework says WHAT to include; the style guide says HOW to write it.
**Expected output:** Section with the named structure, ratings, and tables.

### 11C. `rail.instructions`

> "rail.verdict REQUIRED: rating + optional previous_rating, target price, upside%, as_of date. rail.quick_stats REQUIRED to include ALL of: 'Market Cap', 'Sector', 'Exchange', '52W Range', 'ADTV (3mo)', 'P/E (fwd)' (case-insensitive). rail.sparkline: 60-day daily close points labeled 'Last 60 days'."

**Purpose:** Right-rail sidebar must carry a hard-coded contract for the renderer. Without these labels, the rail looks empty.
**Expected output:** Rail with verdict + 6 named quick_stats + sparkline.

### 11D. `web_search_budget_default: 10`

**Purpose:** Per-framework override of the global default. Layer 8 quotes 8 (the request-level override won earlier); this default applies if the request doesn't override.
**Expected output:** Up to 10 web searches.

---

## What the model does NOT see in the writing phase

- Anthropic-style separate tool-result messages from the fetching phase are visible (they're regular conversation turns).
- The `submit_report` tool's input JSON Schema is implicitly visible because the tool is bound to the model (provider injects the schema definition). It's the strict source of truth that Layer 4 keeps referring to.
- There's no system-prompt-level mention of read_payload sub-stubs being scoped per-ref (that's in Layer 5).
- There's no per-section repair tool — repair is whole-report.

---

## Cross-reference: which fix touched which layer

| Layer | Affected by |
|---|---|
| Layer 4 (Schema strictness) | F3, F5, F6b, F7, F20 |
| Layer 8 (Two-source discipline) | F8 |
| Layer 10 (User prompt) | F17 (planner only, subagent path), F23 |
| Layer 11 (Framework JSON) | (no F-level fixes; framework content is stable) |
| Server-side post-processing (not in prompt) | F1, F2, F4, F6, F21, F22 |
| Runtime configuration (not in prompt) | F9, F11, F13, F14, F19 |
| Subagent client behavior (not in prompt) | F10, F12, F15, F16, F18 |
