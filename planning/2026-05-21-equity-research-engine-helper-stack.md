# Equity Research Engine — Helper Stack Build Plan

**Date:** 2026-05-21
**Status:** Active build plan
**Branch convention:** `feat/<task-slug>` off main

This document captures the agreed plan for the OpenLIA equity research engine's tool / library / helper stack, the architectural decisions that govern how helpers are exposed to LLMs, and the task list driving the build.

It supersedes the deleted `planning/equity-research-tools-audit.md` from the same date.

---

## 1. Architecture decisions

### 1.1 Three-layer exposure model (confirmed)

Helpers are exposed to the LLM in three layers, scaling the eventual ~75-helper surface without blowing context windows:

- **Layer 1 — Capability index** (~1k tokens, always loaded). 14 category names + one-line summaries in `capabilities.yaml`. Read by clarifier, planner, and template loader.
- **Layer 2 — Per-run helper schemas** (~3-5k tokens, loaded per run after planner selects). Full `HelperSchema` blobs (params, types, derivations) for helpers the planner picked.
- **Layer 3 — Execution** (zero LLM tokens). Pure Python; LLM never sees implementation code.

Prompt caching keeps Layer 1 cached across sessions and Layer 2 cached across all 9 stages of a single run.

### 1.2 Drafter helper access — Option B (prebuilt only) for now

Stage 7 drafter consumes pre-built artifacts only — no ad-hoc tool-use during drafting. The Stage 3 + Stage 5 planners decide everything upfront. Trade-off accepted: lower flexibility for surprising prompts, in exchange for predictability and verifier simplicity.

Revisit later if specific use cases demand mid-draft tool calls.

### 1.3 Data-source tagging (parked)

Whether helpers should be tagged by their data source (so the gather stage queues data fetches accordingly) — deferred pending real run experience.

---

## 2. External libraries

### 2.1 Incorporated

| Library | License | Role | Task |
|---|---|---|---|
| EODHD (via MCP) | Vendor | Data spine — fundamentals, prices, options, UST curve, macro indicators, sentiment, news, screener, technicals, marketplace partners (Praams, Illio, Investverte) | #2 |
| FinanceToolkit (JerBouma) | MIT | Pure-Python financial math — 50+ ratios, DCF, WACC, DuPont, Altman Z, BSM+Greeks, VaR (4 distributions), Sharpe/alpha/beta | #3 |
| statsmodels | BSD-3 | Statistical inference, narrowed scope — OLS, multi-factor regression, VIF, correlation, t-test, F-test | #4 |
| pdfplumber | MIT | PDF table extraction fallback (when multimodal LLM extraction misses structured tables) | #5 |
| openpyxl | MIT | Excel workbook generation (already in code; will be extended) | #5, #8 |
| matplotlib | PSF | Chart rendering (already in code; will be extended) | #6 |
| Anthropic Claude API | Vendor | LLM orchestration + multimodal PDF ingestion + structured JSON output | #5 + cross-cutting |
| claude-cookbooks patterns | MIT | Pattern reference (not a runtime dep) — adapted into our helpers | #5 |

### 2.2 Explicitly rejected

| Library | Reason |
|---|---|
| OpenBB Platform | AGPL blocker for commercial deployment |
| PyMuPDF | AGPL blocker |
| FinancePy | GPL blocker |
| QuantLib | Fixed-income, irrelevant for equity research |
| Riskfolio-Lib / PyPortfolioOpt / quantstats / ffn / empyrical / pyfolio | Portfolio analytics — separate department from equity research |
| arch (GARCH) | Academic for single-name research |
| FinBERT variants (ProsusAI, yiyanghkust, ModernBERT) | LLM with structured output beats it for our use case |
| pandas-ta | Original repo deleted; only hobbyist fork remains |
| TA-Lib | EODHD already pre-computes technicals |
| mplfinance / seaborn | Matplotlib sufficient |
| fredapi / wbgapi | EODHD macro is sufficient |
| finvizfinance / simfin | EODHD screener wins |
| camelot | Pdfplumber sufficient unless tables fail |
| XlsxWriter | openpyxl sufficient |
| yfinance | Emergency fallback only; EODHD is the spine |
| py_vollib | Deprecated by upstream |
| vaderSentiment | LLM beats it; not finance-tuned |
| fundamentalanalysis | Legacy; folded into FinanceToolkit |
| Simply Wall Street | Paid commercial product, not a library |

### 2.3 Conditional adds (revisit when triggered)

| Library | Trigger condition |
|---|---|
| QuantLib | Fixed-income templates ship (swap pricing, bond duration from cashflows, vol surfaces) |
| TA-Lib | EODHD technicals fall short for a template |
| fredapi / wbgapi | Macro template needs FRED/World Bank specifics |
| camelot | pdfplumber tables fail on critical filings |
| plotly | Frontend interactivity is added to the React UI |
| WeasyPrint | HTML→PDF quality needs to improve |
| FinBERT | LLM batch sentiment cost becomes prohibitive at volume |

---

## 3. Tools we are building ourselves (infrastructure)

| Tool | Purpose | Task |
|---|---|---|
| EODHD adapter | Wraps EODHD MCP endpoints as `HelperRegistration` entries with `HelperSchema` | #2 |
| FinanceToolkit adapter | Bridges Toolkit's constructor to OpenLIA's normalized statement data; exposes Toolkit modules as helpers | #3 |
| statsmodels adapter | Thin wrapper exposing only the 6 narrowed helpers | #4 |
| pdf_ingest helper | Wraps Claude API multimodal PDF upload + JSON-mode extraction | #5 |
| excel_builder extensions | Multi-sheet workbook, embedded formulas, conditional formatting, named ranges, chart embedding | #5, #8 |
| comparables.py | Peer-multiples math with EV→equity bridge, outlier filtering | #1 |
| WorkbookTemplate class | Structured Inputs / Assumptions / Model / Outputs workbook | #8 |

---

## 4. Existing infrastructure (from PR #151)

Already in code, do not re-implement:

- `HelperRegistration` / `HelperSchema` / `register_library_helper` registry pattern
- Connector adapter pattern (mcp / sdk / web / cache_wrapper) at `report_v2/connectors/`
- 9-stage RunnerV2 orchestrator with clarifier pause/resume
- Capability manifest pattern (`capabilities.yaml`)
- Citation manifest with `[c:id]` markers + Sources footer
- Run Summary + Verification History blocks
- Stage 8 verifier with 14-issue closed enum
- Template Spec V2 with composer_inputs, required_artifacts, sections DAG, trigger_when

Existing implemented helpers (see §4.1 for rationalization):

- `dcf_valuation.py` — full DCF with sensitivity grid — **KEEP**
- `forecast_builder.py` — driver-based revenue / EBIT / cash forecasts — **KEEP**
- `ratio_calculator.py` — 20 ratios with hardcoded benchmark strings — **DEPRECATE** (§4.1.1)
- `budget_variance.py` — internal-budget variance analysis — **DEPRECATE** (§4.1.2)
- `business_investment.py` — internal capex NPV/IRR/payback — **DEPRECATE** (§4.1.3)
- `saas_metrics.py` — monthly SaaS unit economics — **REPURPOSE** as `saas_kpi_panel` (§4.1.4)
- `chart_builder.py` — basic matplotlib charts — **KEEP**, extend via #6 specialized charts
- `excel_builder.py` — basic openpyxl workbooks — **KEEP**, extend via #8 WorkbookTemplate

### 4.1 Existing helper rationalization

PR #151 vendored a general `alirezarezvani/claude-skills` financial-analyst bundle that conflated **internal-finance tools** (`budget_variance`, `business_investment`, monthly-granularity SaaS metrics) with **external-research tools** (DCF, ratios, forecasts). For an equity research engine specifically, the internal-finance helpers don't apply — researchers don't see internal budgets, monthly MRR, or capex approval workflows. Four of the eight existing helpers need to change.

#### 4.1.1 `ratio_calculator.py` — DEPRECATE

**Decision:** Remove after the EODHD adapter (#2) and FinanceToolkit adapter (#3) land.

**Rationale:**

| Concern | Detail |
|---|---|
| Vendor-validated profitability + valuation | EODHD `get_fundamentals_data` pre-computes ROE, ROA, margins, P/E, P/B, P/S, EV/EBITDA, PEG with consistent TTM windows and exchange-rate handling. Ad-hoc filing-data calc drifts from vendor-published numbers users check against. |
| Liquidity + leverage + efficiency superset | FinanceToolkit's ratios module covers all 10 ratios (current, quick, cash, D/E, interest coverage, DSCR, asset turn, inventory turn, receivables turn, DSO) plus more, with battle-tested formulas. |
| Drift risk | Maintaining two parallel ratio implementations causes verifier confusion about canonical source and number-mismatch issues in reports. |
| Benchmark strings not retained | The hardcoded benchmark interpretation strings ("Excellent — significantly above peers", etc.) use generic thresholds that don't match industry-specific institutional benchmarks. The LLM produces better contextual narrative from the numbers themselves. |

**Migration steps (executed at end of #3):**

1. Confirm EODHD adapter exposes equivalent helpers for profitability + valuation ratios.
2. Confirm FinanceToolkit adapter exposes equivalent helpers for liquidity + leverage + efficiency ratios.
3. Update any template references to `ratio_calculator` to use the new helpers.
4. Delete `ratio_calculator.py` and its test file.
5. Remove the registration call from `library_helpers/__init__.py`.

#### 4.1.2 `budget_variance.py` — DEPRECATE

**Decision:** Remove at end of task #7.

**Rationale:** Internal CFO tool comparing actuals to internal budget per line item with materiality flags. Equity researchers don't have access to companies' internal budgets. The relevant external comparisons are:

- Actuals vs. **consensus estimates** → `earnings_surprise_tracker` (task #7)
- Actuals vs. **management guidance** → `guidance_tracker` (task #5)
- Actuals vs. **prior year** → trivial growth calc, no helper needed

**Migration steps (executed at end of #7):**

1. Confirm `earnings_surprise_tracker` is landed and registered.
2. Confirm `guidance_tracker` is landed (task #5).
3. Update any template references to `budget_variance` to use the new helpers.
4. Delete `budget_variance.py` and its test file.
5. Remove the registration call from `library_helpers/__init__.py`.

#### 4.1.3 `business_investment.py` — DEPRECATE

**Decision:** Remove at end of task #7.

**Rationale:** Internal capital-budgeting tool with NPV, IRR, payback, ROI, and qualitative scoring (strategic fit, risk, reversibility, cash flow impact) for evaluating an investment decision. Equity researchers don't evaluate internal capex approval workflows. Where research touches incremental-investment math:

- **ROIIC** (return on incremental invested capital) → `roic_panel` (task #7)
- DCF treatment of major announced capex → handled directly by `dcf_valuation`

**Migration steps (executed at end of #7):**

1. Confirm `roic_panel` is landed and exposes ROIIC.
2. Update any template references to `business_investment` to use `roic_panel`.
3. Delete `business_investment.py` and its test file.
4. Remove the registration call from `library_helpers/__init__.py`.

#### 4.1.4 `saas_metrics.py` — REPURPOSE as `saas_kpi_panel`

**Decision:** Rebuild as `saas_kpi_panel` taking quarterly disclosed metrics; remove the old `saas_metrics` registration. Tracked as task #11.

**Rationale:** The current `saas_metrics.py` is designed for **internal SaaS CFO** use — monthly MRR, churned customer count, monthly S&M spend, monthly cohort modeling. These are not disclosed publicly at that granularity. Equity research for SaaS companies cites quarterly disclosed KPIs instead:

- **ARR** + growth (YoY, sequential)
- **NRR** (Net Retention Rate) — typically disclosed
- **GRR** (Gross Retention Rate) — sometimes disclosed
- **Magic Number** = (ΔARR × 4) / prior-quarter S&M spend
- **Rule of 40** = revenue growth % + FCF margin %
- **LTV / CAC** — sometimes disclosed
- **CAC payback** — sometimes disclosed
- **Customer count + growth**
- **Implied churn rate** (from NRR + GRR when both disclosed)

**Migration steps (executed in task #11):**

1. Build `saas_kpi_panel.py` with the quarterly-input schema above.
2. Add tests covering happy path + missing-input graceful degradation (NRR-only, ARR-only).
3. Update any template references to `saas_metrics` to use `saas_kpi_panel`.
4. Delete `saas_metrics.py` and its test file.
5. Remove the old registration call from `library_helpers/__init__.py`.

---

## 5. Helpers we are designing

Organized by analytic concern. Every helper registered with `HelperSchema` so the planner can declare it as a `required_artifact`.

### 5.1 Valuation deliverables

| Helper | Source | Notes |
|---|---|---|
| `comparables` | Task #1 custom | Peer-multiples implied range with EV→equity bridge |
| `sensitivity_table` | Task #6 custom | 1-way + 2-way DCF sensitivity grids |
| `tornado_diagram` | Task #6 custom | Driver-importance ranking |
| `scenario_weighting` | Task #6 custom | Bear / base / bull with probability weights |
| `reverse_dcf` | Task #6 custom | Market-implied growth solver (Mauboussin anchor) |
| `football_field_chart` | Task #6 custom | Multi-method valuation range visual |
| `waterfall_chart` | Task #6 custom | FY-to-FY revenue / EPS / FCF bridges |
| `dcf_valuation` | Existing | Full DCF with terminal value (perpetuity + exit-multiple) |
| `ft_dcf` / `ft_wacc` / `ft_enterprise_value` | Task #3 (FinanceToolkit) | Alternative implementations |

### 5.2 Business quality / capital allocation

| Helper | Source | Notes |
|---|---|---|
| `roic_panel` | Task #7 custom | ROIC, ROCE, ROIIC, ROIC-WACC spread |
| `quality_of_earnings_panel` | Task #7 custom | Sloan accruals, OCF/NI, capitalized R&D, deferred tax, restructuring add-backs |
| `capital_allocation_history` | Task #7 custom | 5y breakdown of cash uses |
| `earnings_surprise_tracker` | Task #7 custom | 8-quarter beat/miss/inline + magnitude |
| `analyst_revision_momentum` | Task #7 custom | 30/60/90-day revision counts |
| `total_shareholder_yield` | Task #7 custom | (divs + buybacks) / mkt cap |
| `fcf_conversion_track_record` | Task #7 custom | FCF/EBITDA, FCF/NI by year |

### 5.3 Statement integrity

| Helper | Source | Notes |
|---|---|---|
| `cross_statement_validation` | Task #7 custom | CF ties to BS movement; NI ties to retained earnings |
| `one_time_item_identification` | Task #7 custom | GAAP-to-adjusted bridge |
| `organic_vs_inorganic_growth` | Task #7 custom | M&A decomposition |
| `currency_neutral_growth` | Task #7 custom | Constant-currency calc |
| `common_size_statements` | Task #7 custom | Statements as % of revenue (or assets) |

### 5.4 Trend + earnings quality

| Helper | Source | Notes |
|---|---|---|
| `margin_trajectory_regression` | Task #7 custom | Slope + R² over N quarters |
| `operating_leverage_analysis` | Task #7 custom | % change op income / % change revenue |
| `sbc_intensity` | Task #7 custom | SBC as % of revenue, multi-quarter |
| `cap_table_dilution` | Task #7 custom | Share count growth decomposed |

### 5.5 Forensic + foundational ratios

| Helper | Source | Notes |
|---|---|---|
| `piotroski_f_score` | Task #7 custom | 9-criterion quality score |
| `beneish_m_score` | Task #7 custom | 8-input earnings-manipulation detector |
| `cash_conversion_cycle` | Task #7 custom | DSO + DIO − DPO |
| `sustainable_growth_rate` | Task #7 custom | g = ROE × retention |

### 5.6 Risk + macro context

| Helper | Source | Notes |
|---|---|---|
| `drawdown_panel` | Task #8 custom | Series, max, duration, recovery time |
| `yield_curve_shape` | Task #8 custom | 10Y-2Y, 10Y-3M, inversion flag, slope decomposition |
| `commodity_exposure_tracker` | Task #8 custom | Per-template commodity correlation |

### 5.7 Output deliverable

| Helper | Source | Notes |
|---|---|---|
| `WorkbookTemplate` | Task #8 custom | Multi-sheet xlsx with embedded formulas + charts |

### 5.8 LLM-driven NLP

| Helper | Source | Notes |
|---|---|---|
| `pdf_ingest` | Task #5 cookbooks | Multimodal PDF → structured JSON |
| `transcript_tone_analysis` | Task #5 cookbooks | Per-speaker tone, hedging, prep vs Q&A |
| `tone_shift_qoq` | Task #5 cookbooks | QoQ tone-shift with evidence |
| `mda_extraction` | Task #5 cookbooks | MD&A section + drivers/headwinds |
| `risk_factors_extraction` | Task #5 cookbooks | Categorized risks + YoY change |
| `forward_looking_statements` | Task #5 cookbooks | With qualifiers + confidence |
| `guidance_tracker` | Task #5 cookbooks | Guidance vs. actuals + credibility |
| `customer_concentration_extraction` | Task #5 cookbooks | Top-customer disclosures |

### 5.9 EODHD adapter-exposed helpers (task #2)

- `eodhd_ratios` — pre-computed multiples, margins, ROA/ROE
- `eodhd_technicals` — RSI, MACD, BB, ATR, ADX, MAs, stochastic, OBV
- `eodhd_yield_curve` — UST bills + notes + real + long-term
- `eodhd_options_chain`
- `eodhd_macro_indicators`
- `eodhd_sentiment` + `eodhd_news_word_weights`
- `eodhd_screener`
- `praams_smart_screener`
- `praams_risk_scoring` + `illio_risk_insights` + `illio_performance`
- `praams_equity_snapshot`
- `eodhd_insider_transactions`
- `eodhd_earnings_trends`

### 5.10 FinanceToolkit adapter-exposed helpers (task #3)

- `ft_ratios` (50+ ratios incl DuPont, Altman Z)
- `ft_dcf`, `ft_wacc`, `ft_enterprise_value`
- `ft_options_bsm`, `ft_greeks`
- `ft_var` (historical, Gaussian, Student-t, Cornish-Fisher)
- `ft_performance` (Sharpe, alpha, beta, Fama-French correlations)
- `ft_fixedincome_benchmarks` (ICE BofA by credit rating)
- `ft_economics` (60+ countries)

### 5.11 statsmodels adapter-exposed helpers (task #4, narrowed)

- `ols_regression` (with Newey-West HAC option)
- `multi_factor_regression`
- `vif_check`
- `correlation_matrix` (Pearson + Spearman)
- `t_test_means`
- `f_test`

---

## 6. Active task list

**Wave 0 — Foundation + existing-helper rationalization:**

| # | Task | Status | Depends on |
|---|---|---|---|
| 1 | Build `comparables.py` library helper | pending | — |
| 2 | EODHD coverage audit + adapter for v2.2 helpers | pending | — |
| 3 | FinanceToolkit integration as v2.2 helper backend (incl. `ratio_calculator` deprecation) | pending | #2 |
| 4 | statsmodels integration (narrow scope) as v2.2 helper backend | pending | — |
| 5 | claude-cookbooks pattern adoption (PDF multimodal, xlsx, NLP helpers) | pending | — (benefits from #2) |
| 6 | DCF deliverable + valuation visual helpers bundle | pending | #1, #12 |
| 7 | Business quality + statement integrity helpers bundle (incl. `budget_variance` + `business_investment` deprecations) | pending | #2, #3 |
| 8 | Structured multi-sheet workbook builder + remaining output helpers | pending | #6, #7 |
| 11 | Repurpose `saas_metrics.py` → `saas_kpi_panel` (quarterly disclosed metrics) | pending | — |

**Wave 1 — Institutional valuation + sector breadth (from external audit, 2026-05-21):**

| # | Task | Status | Depends on |
|---|---|---|---|
| 12 | DCF engine institutional mechanics + cost-of-capital build (CAPM/Hamada/CRP/mid-year/McKinsey KVD) | pending | — |
| 13 | Alternative valuation methodologies (DDM family + Justified Multiples + SOTP + RI for financials) | pending | #12 |
| 14 | Decision layer — price target blender + ETR + risk/reward + rating bands | pending | #12, #13 |
| 15 | Credit + solvency expansion + Altman variants + 5-step DuPont | pending | — |
| 16 | Banks sector module | pending | #2 |
| 17 | REITs sector module | pending | #2 |
| 18 | Pharma / biotech rNPV sector module | pending | #2, #5 |
| 19 | Energy / E&P sector module | pending | #2, #5 |
| 20 | Insurance sector module (P&C + Life) | pending | #2, #5 |
| 21 | Forensic additions + dividend safety analysis | pending | #2, #4, #7 |

**Future (parked):**

| # | Task | Status | Depends on |
|---|---|---|---|
| 9 | [FUTURE] Qualitative framework helpers + sector research helpers | parked | post-Wave-1 |
| 10 | [FUTURE] Verifier process-quality enforcement extensions | parked | post-Wave-1 |
| 22 | [FUTURE] Wave 2 sector modules (Mining, Retail, Telecom, Semis, Airlines) | parked | post-Wave-1 |

### 6.1 Dependency graph

```
#1 comparables ─────────────┐
                            ├─► #6 DCF deliverables ─┐
                            │                        │
#2 EODHD adapter ──┬──► #3 FinanceToolkit            ├─► #8 Workbook + outputs
                   │       │                         │
                   │       └──► #7 Business quality ─┘
                   │
                   └──► (testing data for #5, #6, #7)

#4 statsmodels narrow ─── independent
#5 cookbooks patterns ─── benefits from #2 for testing data
```

### 6.2 Suggested execution order

1. **#2 EODHD adapter** — unlocks #3, #5, #7
2. **#1 comparables** + **#4 statsmodels** + **#5 cookbooks patterns** — independent, can run in parallel after / alongside #2
3. **#3 FinanceToolkit** — after #2 lands
4. **#7 Business quality** — after #2 and #3
5. **#6 DCF deliverables** — after #1
6. **#8 Workbook + outputs** — after #6 and #7

---

## 7. Future tasks (parked)

These are documented for visibility but not started until the active tasks land and produce real reports that reveal where the next quality lift is needed.

### 7.1 Task #9 — Qualitative framework helpers

**Status:** Parked.

**Why parked:** The current plan is ~95% quantitative-precision. Without forcing functions, LLM narrative defaults to generic claims ("strong moat", "growth opportunity", "experienced management"). Framework helpers force specificity by requiring the LLM to fill structured schemas with citations. But the deterministic foundation has to exist first; qualitative analysis on unfounded numbers is worse than no analysis.

**Frameworks to encode:**

- `porter_five_forces` — score each force HIGH/MED/LOW with evidence
- `moat_taxonomy` — Morningstar 5-type (network effects, intangible assets, cost advantage, switching costs, efficient scale)
- `tam_sam_som` — three numbers with sources + methodology
- `industry_lifecycle_classifier` — intro / growth / maturity / decline with implications
- `pricing_power_test` — "Can it raise prices?" with evidence
- `bull_bear_thesis_structurer` — parallel cases with 3 specific drivers each
- `catalyst_framework` — categorize by horizon (0-3M / 3-12M / 12M+) and type
- `risk_taxonomy` — operational / financial / governance / macro / regulatory / competitive
- `mauboussin_expectations` — wraps reverse DCF with structured narrative
- `management_quality_panel` — capital allocation track record, guidance accuracy, ownership, comp alignment
- `ksf_identification` — Key Success Factors per industry with subject scoring
- `customer_supplier_concentration_synthesis` — risk framing

**Revisit when:** at least one v2.2 stock-initiation template has run end-to-end and the gap between produced output and institutional-quality research is visible in real examples.

### 7.2 Task #10 — Verifier process-quality enforcement extensions

**Status:** Parked. Pairs with #9 since both extend the verifier surface.

**New issue types and detectors:**

- `source_tier_insufficient` — high-stakes claims relying on tertiary sources only
- `temporal_ambiguous` — multi-period claims without time anchor (TTM / FY1 / FY2 / specific fiscal period)
- `confidence_missing` — thesis drivers without HIGH/MEDIUM/LOW confidence tag
- `comparability_mismatch` — cross-company / cross-period comparisons without same FY end + accounting standard
- Generic-claim tombstone — extend tombstone regex to flag "strong management" without specific evidence, "competitive moat" without moat-type, etc.
- `numeric_ungrounded` — numbers in prose without citation, helper output, or explicit same-section derivation
- Pre-mortem section directive — `thesis_driver` and `valuation` sections must answer "What would have to be true for this not to play out?"

**Revisit:** alongside or after #9.

---

## 8. What is dropped from the build

To prevent scope creep and keep the helper catalog tight, these were explicitly cut:

### 8.1 Academic / textbook valuation (not cited in real research)
- Residual income model
- Adjusted Present Value (APV)
- LBO modeling (PE/M&A research, not equity)
- Real options
- Liquidation value (distressed templates only)
- Replacement cost / Tobin's Q

### 8.2 Portfolio / quant tools (separate department from equity research)
- VaR / CVaR / Expected Shortfall (portfolio risk; single-stock VaR not meaningful)
- Sortino / Treynor / Information Ratio / Calmar / Sterling / Omega (portfolio metrics)
- Markowitz mean-variance optimization
- Black-Litterman
- Risk parity / HRP / HERC
- Efficient frontier construction
- Rebalancing logic
- Tracking error
- Herfindahl concentration index
- Stress tests (portfolio level)

### 8.3 Time-series quant (academic for equity research)
- ARIMA / SARIMAX / Holt-Winters forecasting helpers
- GARCH / EGARCH / TGARCH
- Cointegration (Engle-Granger, Johansen)
- VAR / VECM
- Granger causality
- Pairs trading / spread mean-reversion
- ADF / KPSS stationarity tests

### 8.4 Fixed-income (not equity)
- IRS / CDS valuation
- Bond duration / convexity from cashflows
- Zero-curve bootstrapping
- Vol surfaces / smile / skew construction
- Binomial / American option pricing
- IV solver from scratch

### 8.5 Stats academia (statsmodels stays available but no helpers)
- Survival analysis (Kaplan-Meier, Cox)
- Mixed effects / GEE / panel data
- Markov switching, dynamic factor models
- Bayesian inference / MCMC
- Imputation (MICE)
- Mediation analysis
- GMM

### 8.6 Academic macro / FX
- PPP / REER
- Covered / uncovered interest parity
- FCI / CLI composite indicators
- FX cross-rate / triangular arbitrage
- TIPS breakeven inflation (conditional — bring back if needed)

### 8.7 Idea-generation tools (not equity research)
- Composite multi-factor Z-scores
- Magic Formula (Greenblatt)
- O'Shaughnessy strategies
- Piotroski-as-screen (already covered by Piotroski F helper)

### 8.8 NLP / decoration
- Topic modeling (LDA / BERTopic)
- Document clustering
- Sankey, treemap, violin, KDE charts
- Pivot tables in Excel
- Monte Carlo simulation (rare in equity research; numpy.random if ever needed)

---

## 9. Final helper count

When all active tasks (#1-#8) land:

**Wave 0 (foundation):**

| Source | Helper count |
|---|---|
| Existing in code (PR #151), after §4.1 rationalization | 4 kept (DCF, forecast_builder, chart_builder, excel_builder) + 1 repurposed (saas_kpi_panel via task #11). `ratio_calculator`, `budget_variance`, `business_investment` deprecated. |
| EODHD adapter (#2) | ~12 helpers |
| FinanceToolkit adapter (#3) | ~8 helpers |
| statsmodels adapter (#4, narrowed) | 6 helpers |
| Cookbooks patterns (#5) | 8 helpers |
| Custom valuation deliverables (#1, #6) | 7 helpers |
| Custom business quality + integrity (#7) | 20 helpers |
| Custom output + risk/macro (#8) | 4 helpers (incl. WorkbookTemplate class) |
| **Wave 0 subtotal** | **~69 helpers** |

**Wave 1 (institutional valuation + sector breadth, from audit):**

| Source | Helper count |
|---|---|
| DCF engine + cost-of-capital (#12) | 12 helpers (engine extensions + CAPM/Hamada/cost-of-debt/CRP/normalized-earnings) |
| Alternative valuation (#13) | 11 helpers (DDM family ×4 + justified multiples ×5 + SOTP + RI) |
| Decision layer (#14) | 5 helpers (price target blender, ETR, risk/reward, implied upside/downside, rating bands) |
| Credit + Altman + DuPont (#15) | 11 helpers (4 Altman variants + interest coverage suite + net debt/EBITDA + fixed charge + defensive interval + debt maturity wall + 5-step DuPont) |
| Banks (#16) | 14 helpers |
| REITs (#17) | 13 helpers |
| Pharma rNPV (#18) | 5 helpers |
| Energy / E&P (#19) | 14 helpers |
| Insurance (#20) | 11 helpers (P&C + Life) |
| Forensic + dividend safety (#21) | 10 helpers (Dechow-Dichev + channel stuffing + deferred revenue + dividend coverage + safety + growth + payout multi-base + net buyback + sustainable growth + aristocrats flag) |
| **Wave 1 subtotal** | **~106 helpers** |

**Combined Wave 0 + Wave 1 active: ~175 helpers.**

**Wave 2 future (#22): ~32 sector helpers** (Mining 7 + Retail 7 + Telecom 6 + Semis 4 + Airlines 8).
**Other future (#9 + #10): ~18 qualitative-framework + sector-research helpers + ~7 verifier issue types.**

With three-layer exposure, the LLM never sees more than ~10-15 helper schemas per run; planner picks from the catalog based on prompt + template + capability manifest. The scale of the catalog doesn't inflate per-run context cost.

With three-layer exposure, the LLM never sees more than ~10-15 helper schemas per run; the planner picks based on prompt + template + capability manifest.

---

## 10. Open decisions deferred

- **Data-source tagging on helpers** — held for later (see §1.3)
- **PyMuPDF commercial license vs. pdfplumber-only** — go with pdfplumber only; revisit if filing parsing quality forces it
- **plotly add for frontend interactivity** — tied to frontend roadmap, not the helper stack
- **Drafter ad-hoc tool-use (Option A)** — revisit if prebuilt-only proves too rigid for custom user prompts

---

## 11. External audit expansion (2026-05-21, post-initial-design)

After initial commit, an external audit identified three major gap areas:

1. **DCF projection engine plumbing** (CAPM build, Hamada relevering, mid-year convention, McKinsey Key Value Driver terminal value)
2. **Sector-specific KPI modules** (banks, REITs, insurance, E&P, pharma, mining, retail, airlines, telecom, semis) — required for credible coverage of ~40% of the S&P 500
3. **Decision layer** (price target blending, expected total return, risk/reward, rating bands) — the missing output that converts analysis into a recommendation

Adopted in Wave 1 (tasks #12-#21):
- All of #1 (DCF mechanics)
- All of #3 (decision layer)
- 5 Wave 1 sector modules: Banks, REITs, Pharma rNPV, Energy/E&P, Insurance (audit's Wave 1)
- DDM family + justified multiples + SOTP (promoted from conditional)
- Altman Z variants (Z, Z', Z", EM Z") with auto-select
- Credit + solvency expansion
- 5-step DuPont
- Dechow-Dichev accrual quality + channel stuffing + deferred revenue
- Dividend safety analysis

Deferred to Wave 2 (task #22):
- Mining, Retail, Telecom, Semis, Airlines sector modules

Pushed back on (kept earlier cut decision):
- Sortino / Treynor / Information Ratio / Calmar / Modigliani M² / upside-downside capture — portfolio metrics; single-name equity research rarely cites these. Reconsider only if OpenLIA spins up a portfolio department.
- Merton/KMV Distance to Default — useful for credit-sensitive coverage; not table-stakes for equity research.
- Build-up cost of equity — private/illiquid only; not in OpenLIA's coverage scope.
- BCG growth-share matrix, sector rotation — decorative; LLM narrates equivalents without a forcing function.

Audit also confirmed several earlier decisions:
- IQR 1.5× outlier filter in comparables: keep
- Beneish M-score threshold −1.78 for 8-variable model: keep
- NOPAT calculation: clarified via `use_adjusted_ebit` flag in task #12

## 12. References

- v2.2 design spec: `docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md`
- v2.2 implementation plan: `docs/superpowers/plans/2026-05-21-equity-research-v2.2.md`
- Existing library helpers code: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/`
- Existing capability manifest: `packages/core/src/openlia/llm/runtime/report_v2/capabilities.yaml`
- Stage 8 verifier 14-issue closed enum: defined in v2.2 design spec §8
- Prior superseded audit (deleted): `planning/equity-research-tools-audit.md`
