# Equity Research Engine — Helpers Design Document

**Date:** 2026-05-21
**Status:** Design spec for external audit
**Companion to:** `planning/2026-05-21-equity-research-engine-helper-stack.md` (build plan)

---

## 0. Document purpose

This document specifies the design of every builder, adapter, and helper being built for the OpenLIA equity research engine. For each item it specifies:

- **Purpose** — the equity research question it answers
- **Inputs** — parameter schema with types, defaults, sources
- **Output schema** — return-value structure
- **Algorithm / Formula** — the actual math or processing steps
- **Edge cases / fallbacks** — behavior when inputs are missing or invalid
- **Verifier hooks** — what the Stage 8 verifier checks
- **Data source** — where each input originates

The intent is that an independent auditor (human or AI) can read this document standalone and verify that the implementations match the design.

---

## 1. Common conventions

### 1.1 Helper registration pattern

Every helper is a module under `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/` that:

1. Defines an `execute(**params) -> dict` function.
2. Defines a `SCHEMA: HelperSchema` module-level constant declaring required + optional params with type + description + derivation rules.
3. Calls `register_library_helper(name, execute, SCHEMA)` at import time.

The registry is read by the Stage 5 model planner to decide which helpers can satisfy `required_artifacts[]` and `optional_artifacts[]`.

### 1.2 Three-layer exposure

- **Layer 1**: helper category + one-line summary in `capabilities.yaml` (always loaded).
- **Layer 2**: full `HelperSchema` loaded only after planner selects the helper for a run.
- **Layer 3**: actual Python execution; LLM never sees implementation.

### 1.3 Data freshness and source provenance

Every helper output includes:
- `applied_at`: ISO-8601 timestamp of computation.
- `data_as_of`: latest data-point date used (typically the most-recent reporting period or last vendor-update date).
- `source_provenance`: list of citation IDs and helper-output IDs that fed this calculation.

The verifier checks that downstream prose citing a helper output references the same `applied_at` / `data_as_of` window.

### 1.4 Missing-data behavior

Default policy: **fail-soft with explicit flagging**. If a required input is missing:
- Return partial output with `status: "DEGRADED"`.
- Include `missing_inputs: [list]` in output.
- Verifier emits `required_param_unresolvable` only if `status: "FAILED"`.

Hard fail only when no meaningful output is possible (e.g., comparables with zero valid peers).

### 1.5 Verifier hooks (closed enum cross-reference)

Helper outputs feed the existing 14-issue verifier taxonomy:
- `required_param_unresolvable` — required input had no value, derivation, or default
- `helper_unavailable` — referenced helper category is deferred
- `numeric_inconsistency` — same metric appears with different values in different blocks
- `citation_missing` — claim from helper output not tied back to source
- `artifact_missing` — required artifact built but never embedded
- `block_shape` — output JSON malformed

Future verifier extensions (task #10): `source_tier_insufficient`, `temporal_ambiguous`, `confidence_missing`, `comparability_mismatch`, `numeric_ungrounded`.

---

## 2. Adapter / infrastructure designs

### 2.1 EODHD adapter (task #2)

**Purpose:** Bridge EODHD MCP endpoints into the v2.2 helper system. Each EODHD endpoint becomes a registered helper that returns normalized data the planner can pass to downstream helpers.

**Approach:** Thin wrapper layer at `library_helpers/eodhd_adapter.py` (plus per-endpoint submodules). Each wrapper:
1. Calls the EODHD MCP tool with structured params.
2. Normalizes response shape (vendor uses inconsistent field names across endpoints — e.g., `marketCapitalization` vs. `market_cap` vs. `MarketCapitalization`).
3. Adds `source_provenance` + `data_as_of` fields.
4. Returns a typed dict with snake_case field names.

**Helpers exposed:**

| Helper name | Wraps EODHD tool | Normalized output |
|---|---|---|
| `eodhd_ratios` | `get_fundamentals_data` (Valuation + Highlights sections) | `{pe_ttm, pe_forward, pb_mrq, ps_ttm, ev_ebitda, ev_revenue, peg, roe_ttm, roa_ttm, gross_margin, op_margin_ttm, net_margin, eps_basic, eps_diluted, bvps, dividend_yield, beta, market_cap, enterprise_value}` |
| `eodhd_statements` | `get_fundamentals_data` (Financials sections) | Normalized income statement, balance sheet, cash flow with consistent line-item keys across periods |
| `eodhd_technicals` | `get_technical_indicators` | Per-indicator time series — RSI, MACD, BB, ATR, ADX, SMA, EMA, stochastic, OBV |
| `eodhd_yield_curve` | `get_ust_yield_rates` + `_bill_rates` + `_real_yield_rates` + `_long_term_rates` | `{date, 1m, 3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y, real_5y, real_10y, real_30y}` time series |
| `eodhd_options_chain` | `get_us_options_contracts` + `_eod` | List of contracts with strike, expiry, bid, ask, IV, volume, OI, Greeks (when delivered) |
| `eodhd_macro_indicators` | `get_macro_indicator` | Per-country macro series (GDP, CPI, PPI, unemployment, NFP) |
| `eodhd_economic_events` | `get_economic_events` | Calendar of releases with consensus + actual |
| `eodhd_sentiment` | `get_sentiment_data` | Daily sentiment score per ticker |
| `eodhd_news_word_weights` | `get_news_word_weights` | Topic salience weights |
| `eodhd_company_news` | `get_company_news` | News feed with timestamps + sources |
| `eodhd_screener` | `stock_screener` | Filter-based screen results |
| `eodhd_insider_transactions` | `get_insider_transactions` | Insider buy/sell history with role + share count |
| `eodhd_earnings_trends` | `get_earnings_trends` | Per-quarter consensus + revisions + analyst estimates |
| `eodhd_historical_dividends` | `get_historical_dividends` | Dividend history |
| `eodhd_historical_market_cap` | `get_historical_market_cap` | Market cap time series |
| `praams_risk_scoring` | `mp_praams_risk_scoring_by_ticker` | Multi-dimensional risk score |
| `praams_equity_snapshot` | `mp_praams_report_equity_by_ticker` | Comprehensive equity report |
| `praams_smart_screener` | `mp_praams_smart_screener_equity` | Smart screening with composite scores |
| `illio_risk_insights` | `mp_illio_risk_insights` | Risk metric breakdown |
| `illio_performance_insights` | `mp_illio_performance_insights` | Performance attribution |

**Normalization rules:**
- Currency: all monetary values returned in reporting currency (per company's filing). Helper output includes `reporting_currency` field.
- Time anchors: `period_end_date` always ISO-8601 (YYYY-MM-DD).
- Missing fields: vendor returns `null` or omits → adapter returns `None` (not `0` or empty string).
- Multi-currency tickers: adapter respects the exchange suffix (`.US`, `.LSE`, etc.) and pulls in correct base currency.

**Caching:**
EODHD adapter integrates with the existing `cache_wrapper.py` at `report_v2/connectors/`. Immutable data (filed financials for completed periods) cached indefinitely; mutable data (latest market cap, last price) cached with short TTL configurable per template.

---

### 2.2 FinanceToolkit adapter (task #3)

**Purpose:** Bridge `JerBouma/FinanceToolkit` (MIT) financial math into v2.2 helpers. Swap Toolkit's default FMP/yfinance data source for OpenLIA-supplied normalized data from the EODHD adapter.

**Approach:**

Toolkit's constructor accepts user-supplied DataFrames:

```python
from financetoolkit import Toolkit

toolkit = Toolkit(
    tickers=["AAPL"],
    historical=ohlc_df,
    balance=balance_df,
    income=income_df,
    cash=cash_df,
    risk_free_rate=rf_rate,
    benchmark_ticker="SPY",
)
```

The adapter at `library_helpers/financetoolkit_adapter.py`:
1. Receives normalized statement data from `eodhd_statements` helper.
2. Transforms to pandas DataFrames matching Toolkit's expected column names (mapping table in adapter).
3. Constructs a `Toolkit` instance per ticker per run (cached for the run duration).
4. Invokes Toolkit module methods and returns normalized output.

**Helpers exposed:**

| Helper name | Toolkit method | Output |
|---|---|---|
| `ft_ratios` | `Toolkit.ratios.collect_all_ratios()` | Dict of 50+ ratios incl. DuPont, Altman Z, liquidity, leverage, profitability, efficiency, valuation |
| `ft_dcf` | `Toolkit.models.get_intrinsic_valuation()` | DCF intrinsic value per share + assumptions echo |
| `ft_wacc` | `Toolkit.models.get_weighted_average_cost_of_capital()` | WACC per period with components (Re, Rd, tax, D/E) |
| `ft_enterprise_value_breakdown` | `Toolkit.models.get_enterprise_value_breakdown()` | EV breakdown (mkt cap + debt − cash − minority interest) |
| `ft_options_bsm` | `Toolkit.options.collect_black_scholes_model()` | BSM call/put price + IV + Greeks for given S, K, r, t, σ |
| `ft_greeks` | `Toolkit.options.collect_first_order_greeks()` + `_second_order` + `_third_order` | Delta, gamma, vega, theta, rho, charm, vanna, etc. |
| `ft_var` | `Toolkit.risk.get_value_at_risk()` with `distribution=` arg | VaR for historical / Gaussian / Student-t / Cornish-Fisher |
| `ft_performance_panel` | `Toolkit.performance.collect_all_metrics()` | Sharpe, alpha, beta, Fama-French factor correlations |
| `ft_fixedincome_benchmarks` | `Toolkit.fixedincome.get_corporate_bond_yields()` | ICE BofA corporate bond yields by credit rating |
| `ft_economics` | `Toolkit.economics.get_economic_indicators()` | 60+ countries: CPI, GDP, unemployment, 3M + 10Y rates |

**License header:** Each module file preserves Toolkit attribution per MIT requirements.

**Drift detection:** Run-time sanity check — for the few ratios that both EODHD and FinanceToolkit produce (P/E, ROE, ROA, margins), the verifier compares them. Mismatch beyond a configurable threshold (default 2%) emits a `numeric_inconsistency` warning so the user can investigate (typically a TTM-window or restatement difference).

---

### 2.3 statsmodels adapter (task #4, narrowed)

**Purpose:** Expose a deliberately narrow subset of statsmodels capabilities — only what equity research actually uses.

**Approach:** Thin wrapper at `library_helpers/statsmodels_adapter.py`. Each helper takes pandas Series / DataFrame input and returns a JSON-serializable result.

**Helpers exposed:**

#### `ols_regression`

**Inputs:**
- `y` (Series, required): dependent variable
- `X` (DataFrame, required): independent variables
- `hac_lag` (int, optional, default `None`): if set, use Newey-West HAC standard errors with this lag length

**Output:**
```json
{
  "coefficients": {"var_name": value, ...},
  "std_errors": {"var_name": value, ...},
  "p_values": {"var_name": value, ...},
  "t_statistics": {"var_name": value, ...},
  "r_squared": float,
  "adj_r_squared": float,
  "f_statistic": float,
  "f_p_value": float,
  "n_obs": int,
  "method": "OLS" or "OLS_HAC"
}
```

**Algorithm:** `sm.OLS(y, sm.add_constant(X)).fit()` or `.fit(cov_type='HAC', cov_kwds={'maxlags': hac_lag})`.

**Use cases:**
- Margin trend over N quarters (y = margin, X = time index)
- Returns vs. factor exposure (y = returns, X = factor returns)
- Revenue growth vs. macro driver (y = revenue growth, X = GDP growth)

#### `multi_factor_regression`

Special case of OLS with explicit factor naming. Input: returns series + factor series (e.g., Mkt-Rf, SMB, HML, MOM, RMW, CMA). Output: factor loadings (betas) + alpha + R².

#### `vif_check`

**Input:** DataFrame of independent variables.
**Output:** `{"var_name": vif_value}` per variable. VIF > 10 flagged as multicollinearity concern.
**Algorithm:** `statsmodels.stats.outliers_influence.variance_inflation_factor`.

#### `correlation_matrix`

**Input:** DataFrame.
**Output:** `{"pearson": {"a_b": value}, "spearman": {"a_b": value}, "p_values": {...}}` with significance flagging.

#### `t_test_means`

**Inputs:** Two samples (lists or Series), `paired: bool`.
**Output:** `{"t_statistic", "p_value", "df", "mean_diff", "ci_95"}`.
**Algorithm:** `scipy.stats.ttest_rel` or `ttest_ind`.

#### `f_test`

**Inputs:** Two samples.
**Output:** F-statistic + p-value for equality of variances.

---

### 2.4 pdf_ingest helper (task #5)

**Purpose:** Replace planned pdfplumber/camelot/Tesseract pipeline with Claude API multimodal PDF upload as the primary path.

**Approach:**

1. Helper accepts a PDF URL or bytes.
2. If URL, fetch into bytes via `requests` (or via cache if previously seen — `cache_wrapper.py`).
3. Construct an Anthropic API messages call with `content=[{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64(bytes)}}, {"type": "text", "text": EXTRACTION_PROMPT}]`.
4. Use JSON-mode (`response_format: {"type": "json_object"}`) to constrain output to the extraction schema below.
5. If multimodal extraction confidence is low (model returns `extraction_quality: "low"` in self-assessment), fall back to pdfplumber for structured table extraction on that page range.

**Extraction prompt schema (JSON-mode output):**

```json
{
  "metadata": {
    "filing_type": "10-K | 10-Q | 8-K | S-1 | 20-F | proxy | earnings_deck | investor_day | sell_side_research | other",
    "company_name": "...",
    "ticker": "...",
    "filing_date": "YYYY-MM-DD",
    "period_end_date": "YYYY-MM-DD",
    "reporting_currency": "USD"
  },
  "sections": [
    {
      "title": "MD&A | Risk Factors | Financial Statements | ...",
      "page_range": [start, end],
      "text": "extracted prose",
      "key_claims": ["..."]
    }
  ],
  "tables": [
    {
      "title": "Income Statement | Balance Sheet | Cash Flow | Segment | ...",
      "page": int,
      "headers": ["..."],
      "rows": [["..."]],
      "units": "USD millions | thousands | etc."
    }
  ],
  "extraction_quality": "high | medium | low",
  "extraction_notes": "any caveats"
}
```

**Output:** Normalized `DocumentExtract` schema usable by Stage 4 (Gather) research strands.

**Caching:** Identical PDF (same SHA-256) cached indefinitely. Re-extraction triggered only on schema-version bump.

**Edge cases:**
- PDF > 100 pages: chunked into 32-page segments; outputs merged with section continuity tracking
- Scanned (image-only) PDF: multimodal handles natively; no OCR step needed
- Encrypted PDF: returns FAILED with reason; user prompted to provide decrypted version

---

### 2.5 WorkbookTemplate class (task #8)

**Purpose:** Structured multi-sheet xlsx workbook generator following financial-modeling convention every analyst recognizes.

**Approach:**

Class at `library_helpers/workbook_template.py` wrapping openpyxl.

**Sheet structure (template):**

1. **Cover** — company name, ticker, report date, currency, sources legend
2. **Inputs** — composer inputs (ticker, time horizon, assumptions), all in one sheet so users can edit
3. **Assumptions** — DCF assumptions (WACC, terminal growth, margin trajectory, capex %), each with a named range
4. **Model** — projected income statement / balance sheet / cash flow with cross-sheet formulas (`='Assumptions'!WACC` style)
5. **Outputs** — DCF result table, sensitivity, comparables, scenario weighting, embedded charts (PNG via openpyxl image insertion)
6. **Citations** — references list

**Named-range convention:**
- All inputs in Assumptions tab get named ranges: `WACC`, `TerminalGrowth`, `Year1RevenueGrowth`, etc.
- Model tab formulas reference named ranges, not cells
- User editing an assumption auto-propagates through model

**Conditional formatting:**
- Margin trajectory cells: data bars green-to-red based on value
- Variance cells (actual vs. budget/prior): icon set (green up arrow if better, red down if worse)
- Outlier ratios: red highlight if outside benchmark range

**Charts embedded:**
- Football-field PNG in Outputs tab
- Waterfall (revenue bridge) PNG in Outputs tab
- Margin trajectory line chart (native Excel chart, drawn from Model tab data)

**API:**

```python
wb = WorkbookTemplate(company_name="Apple", ticker="AAPL", currency="USD", report_date="2026-05-21")
wb.set_inputs(ticker="AAPL", horizon_years=5, ...)
wb.set_assumptions(wacc=0.085, terminal_growth=0.025, margin_trajectory=[0.30, 0.31, 0.32, 0.32, 0.32])
wb.build_model(historical_statements=eodhd_statements_output)
wb.embed_outputs(dcf=dcf_output, comparables=comparables_output, sensitivity=sensitivity_output, scenarios=scenarios_output)
wb.embed_chart("football_field", png_bytes=football_field_chart_output.png)
wb.embed_chart("revenue_bridge", png_bytes=waterfall_chart_output.png)
xlsx_bytes = wb.to_bytes()
```

**Edge cases:**
- Empty assumption: leave cell blank with comment "ENTER VALUE"
- Missing historical period: column header marked "N/A"; downstream formulas use `IFERROR(..., "")`

---

## 3. Custom helpers — Valuation (tasks #1, #6)

### 3.1 `comparables` (task #1)

**Purpose:** Apply peer-multiples to subject company financials to derive implied valuation range.

**Question answered:** What is this company worth based on what investors pay for similar companies?

**Inputs:**
- `subject` (dict, required): `{eps_ttm, ebitda_ttm, revenue_ttm, book_value, net_debt, cash, shares_outstanding}`
- `peers` (list[dict], required): each peer is `{ticker, pe_ttm, ev_ebitda, ev_sales, pb}` — None for unavailable multiples
- `multiples_to_use` (list[str], optional, default `["pe", "ev_ebitda", "ev_sales", "pb"]`)
- `outlier_method` (str, optional, default `"iqr"`): `"iqr"` | `"stdev"` | `"none"`
- `outlier_threshold` (float, optional, default `1.5` for IQR, `3.0` for stdev)
- `min_peers_required` (int, optional, default `3`)

**Source:** subject inputs from `eodhd_ratios` + `eodhd_statements`; peers from `eodhd_screener` or template-declared peer list.

**Output:**
```json
{
  "peer_cohort_used": ["AAPL", "MSFT", "GOOGL"],
  "peer_cohort_excluded": [{"ticker": "X", "reason": "outlier_iqr", "metric": "pe_ttm", "value": 250.0}],
  "implied_per_multiple": {
    "pe": {
      "peer_values": {"AAPL": 28.5, "MSFT": 32.1, ...},
      "min": 24.0,
      "p25": 27.0,
      "median": 30.5,
      "mean": 30.8,
      "p75": 33.0,
      "max": 36.0,
      "stdev": 3.2,
      "subject_metric_value": 6.50,
      "subject_metric_label": "EPS TTM",
      "implied_equity_per_share": {"low": 156.0, "median": 198.25, "high": 234.0},
      "implied_equity_value": {"low": 2_500_000_000, "median": 3_172_000_000, "high": 3_744_000_000}
    },
    "ev_ebitda": {
      ...,
      "implied_ev": {"low": ..., "median": ..., "high": ...},
      "implied_equity_value": {"low": implied_ev_low - net_debt, ...}
    },
    "ev_sales": {...},
    "pb": {...}
  },
  "combined_implied_range": {
    "low": ...,
    "median": ...,
    "high": ...,
    "methodology": "min, median, and max of the per-multiple medians across multiples used"
  },
  "warnings": ["..."],
  "applied_at": "2026-05-21T19:40:00Z",
  "data_as_of": "2026-05-20"
}
```

**Algorithm:**

1. **Validate inputs.** Require subject.eps_ttm (for P/E), .ebitda_ttm (for EV/EBITDA), .revenue_ttm (for EV/Sales), .book_value (for P/B). If any required field for a requested multiple is `None`, that multiple is skipped with a warning.

2. **For each multiple in `multiples_to_use`:**
   a. Collect peer values: drop peers with `None` for that multiple.
   b. **Outlier filter:**
      - IQR method (default): Q1 = 25th percentile, Q3 = 75th percentile, IQR = Q3 − Q1. Exclude values outside `[Q1 − outlier_threshold × IQR, Q3 + outlier_threshold × IQR]`.
      - Stdev method: Exclude values outside `[mean − outlier_threshold × stdev, mean + outlier_threshold × stdev]`.
      - None: no filter.
   c. **Check min_peers_required** after filter. If fewer remain, emit warning and skip this multiple.
   d. Compute min, p25, median, mean, p75, max, stdev of remaining peer values.

3. **Apply to subject:**

   For P/E:
   ```
   implied_per_share_low = pe_min × subject.eps_ttm
   implied_per_share_median = pe_median × subject.eps_ttm
   implied_per_share_high = pe_max × subject.eps_ttm
   implied_equity_value_low = implied_per_share_low × subject.shares_outstanding
   ```

   For EV/EBITDA:
   ```
   implied_ev_low = ev_ebitda_min × subject.ebitda_ttm
   implied_equity_value_low = implied_ev_low − subject.net_debt
   ```
   (EV → equity bridge: `Equity = EV − net_debt`. Define `net_debt = total_debt − cash` once upstream from `subject` inputs and apply consistently. Do NOT add cash again — net_debt already nets it out.)

   For EV/Sales:
   ```
   implied_ev_low = ev_sales_min × subject.revenue_ttm
   implied_equity_value_low = implied_ev_low − subject.net_debt
   ```

   For P/B:
   ```
   implied_equity_value_low = pb_min × subject.book_value
   ```

4. **Combined range** (across all multiples used):
   - `low = min(implied_equity_value_median across multiples)`
   - `median = median(implied_equity_value_median across multiples)`
   - `high = max(implied_equity_value_median across multiples)`

   (We synthesize across the per-multiple **medians**, not the per-multiple lows and highs. Combining lows-of-lows with highs-of-highs would compound peer dispersion and methodology dispersion, producing an artificially wide band. The min/median/max of medians is the football-field-style synthesis convention.)

**Edge cases:**
- Subject EPS ≤ 0: P/E excluded; multiple-specific warning emitted ("Subject is unprofitable on TTM basis; P/E methodology not applicable").
- Subject EBITDA ≤ 0: EV/EBITDA excluded.
- Subject book value ≤ 0: P/B excluded.
- All peers have None for a multiple: that multiple skipped, warning.
- Fewer than `min_peers_required` peers after outlier filter: that multiple skipped with `peer_cohort_excluded` populated.
- Currency mismatch between subject and peers: warning emitted (peer multiples may need conversion); not fixed automatically.

**Verifier hooks:**
- `block_shape`: output must include `combined_implied_range` with non-null low/median/high if at least one multiple succeeded
- `numeric_inconsistency`: combined_implied_range numbers in prose must match output
- `required_param_unresolvable`: if no multiple succeeded (e.g., unprofitable + negative book value), emit FAILED

---

### 3.2 `sensitivity_table` (task #6)

**Purpose:** Compute DCF (or any valuation output) over a grid of driver values to show how the valuation responds to assumption changes.

**Question answered:** How sensitive is the valuation to changes in key assumptions?

**Inputs:**
- `base_artifact` (dict, required): output from `dcf_valuation` or comparable helper containing base assumptions + output
- `driver_axes` (list[dict], required, 1 or 2 entries):
  - `name`: e.g., `"wacc"`, `"terminal_growth"`, `"fcf_margin_y5"`
  - `values`: list of values to evaluate, e.g., `[0.07, 0.075, 0.08, 0.085, 0.09]`
- `output_metric` (str, optional, default `"value_per_share_perpetuity"`): which DCF output to track

**Source:** base_artifact typically from `dcf_valuation` (existing) or `ft_dcf`.

**Output:**

For 1-way sensitivity:
```json
{
  "axis": {"name": "wacc", "values": [0.07, 0.075, 0.08, 0.085, 0.09]},
  "output_metric": "value_per_share_perpetuity",
  "base_value": 150.0,
  "results": [180.0, 165.0, 150.0, 138.0, 128.0],
  "delta_from_base": [30.0, 15.0, 0.0, -12.0, -22.0],
  "delta_pct_from_base": [20.0, 10.0, 0.0, -8.0, -14.67]
}
```

For 2-way:
```json
{
  "axis_rows": {"name": "wacc", "values": [0.07, 0.08, 0.09]},
  "axis_cols": {"name": "terminal_growth", "values": [0.02, 0.025, 0.03]},
  "output_metric": "value_per_share_perpetuity",
  "base_value": 150.0,
  "grid": [
    [185.0, 195.0, 207.0],
    [148.0, 156.0, 166.0],
    [122.0, 128.0, 135.0]
  ],
  "delta_pct_grid": [...]
}
```

**Algorithm:**

1. Extract base assumptions from `base_artifact`.
2. For each combination of driver values:
   a. Override the driver in the assumption dict.
   b. Re-run the DCF (or referenced valuation method) with override.
   c. Extract `output_metric` value.
3. Build grid (1D for 1-way, 2D for 2-way).
4. Compute deltas vs. base.

**Edge cases:**
- Driver not in DCF assumption schema: raise ValueError.
- Driver value causes DCF to fail (e.g., terminal_growth >= wacc): cell marked as `null` with reason `"invalid: g >= WACC"`.
- > 2 driver_axes: raise ValueError (3D sensitivity not supported).

**Verifier hooks:**
- `block_shape`: grid dimensions must match axis lengths
- `numeric_inconsistency`: base_value in grid must match `base_artifact.output_metric` value

---

### 3.3 `tornado_diagram` (task #6)

**Purpose:** Rank drivers by their impact on valuation; produces a tornado chart input.

**Question answered:** Which assumptions most affect the valuation?

**Inputs:**
- `base_artifact` (dict, required): DCF output
- `drivers` (list[dict], required): each is `{name, low_value, high_value}` (e.g., `{name: "wacc", low_value: 0.07, high_value: 0.10}`)
- `output_metric` (str, optional, default `"value_per_share_perpetuity"`)

**Output:**
```json
{
  "base_value": 150.0,
  "output_metric": "value_per_share_perpetuity",
  "drivers": [
    {"name": "wacc", "low_value": 0.07, "low_output": 185.0, "high_value": 0.10, "high_output": 120.0, "swing": 65.0, "swing_pct": 43.3},
    {"name": "terminal_growth", "low_value": 0.02, "low_output": 138.0, "high_value": 0.03, "high_output": 165.0, "swing": 27.0, "swing_pct": 18.0},
    ...
  ],
  "drivers_ranked": ["wacc", "terminal_growth", "fcf_margin", ...]
}
```

**Algorithm:**

1. For each driver, run sensitivity at low and high value (re-using `sensitivity_table` internally).
2. Compute swing = |high_output − low_output| and swing_pct = swing / base_value × 100.
3. Sort drivers descending by swing.
4. Return ranked list with all values.

**Edge cases:** Same as `sensitivity_table`.

---

### 3.4 `scenario_weighting` (task #6)

**Purpose:** Run DCF (or any valuation) under bear / base / bull scenarios with explicit probability weights; compute probability-weighted expected value.

**Question answered:** What's the probability-weighted intrinsic value?

**Inputs:**
- `base_artifact` (dict, required): DCF base output
- `scenarios` (list[dict], required): each is `{name, probability, assumption_overrides: {wacc: ..., terminal_growth: ..., ...}}`. Probabilities must sum to 1.0 (validated; tolerance 0.001).
- `output_metric` (str, optional, default `"value_per_share_perpetuity"`)

**Output:**
```json
{
  "scenarios": [
    {"name": "bear", "probability": 0.25, "output_value": 95.0, "weighted_value": 23.75, "key_overrides": {"wacc": 0.10, "terminal_growth": 0.015}},
    {"name": "base", "probability": 0.50, "output_value": 150.0, "weighted_value": 75.0, "key_overrides": {}},
    {"name": "bull", "probability": 0.25, "output_value": 210.0, "weighted_value": 52.5, "key_overrides": {"wacc": 0.075, "terminal_growth": 0.03, "fcf_margin": 0.35}}
  ],
  "expected_value": 151.25,
  "base_value": 150.0,
  "asymmetry_score": 1.10,
  "interpretation": "slightly skewed upside"
}
```

**Algorithm:**

1. Validate probabilities sum to 1.0 ± 0.001.
2. For each scenario, apply assumption overrides to base and run DCF.
3. `weighted_value_i = output_value_i × probability_i`
4. `expected_value = sum(weighted_value_i)`
5. **Asymmetry score** = `(bull_value − base_value) / (base_value − bear_value)`. > 1 means upside is larger than downside in absolute terms.
6. **Interpretation:**
   - asymmetry_score > 1.5: "skewed upside"
   - 0.66 < asymmetry_score ≤ 1.5: "balanced"
   - asymmetry_score ≤ 0.66: "skewed downside"

**Edge cases:**
- Probabilities don't sum to 1: raise ValueError.
- Single scenario: emit warning ("scenario_weighting expects ≥ 2 scenarios").

---

### 3.5 `reverse_dcf` (task #6)

**Purpose:** Given a current market price + base assumptions for WACC and one other driver, solve for the implied growth rate (or terminal multiple) the market is pricing in.

**Question answered:** What does the current market price imply about long-term growth?

**Inputs:**
- `current_price_per_share` (float, required): market price
- `subject` (dict, required): `{shares_outstanding, base_revenue_or_fcf, net_debt, cash}`
- `wacc` (float, required): assumed discount rate
- `solve_for` (str, optional, default `"terminal_growth"`): `"terminal_growth"` | `"explicit_period_growth"` | `"exit_multiple"`
- `projection_years` (int, optional, default `10`)
- `other_assumptions` (dict, optional): margin trajectory, capex %, etc.

**Output:**
```json
{
  "current_price_per_share": 150.0,
  "solve_for": "terminal_growth",
  "wacc_assumed": 0.085,
  "implied_value": 0.027,
  "interpretation": "Market implies 2.7% perpetual growth after Year 10, given 8.5% WACC.",
  "comparison": {
    "consensus_long_term_growth": 0.05,
    "delta": -0.023,
    "verdict": "Market is pricing more conservatively than consensus long-term growth."
  },
  "sensitivity_around_solution": [
    {"wacc": 0.08, "implied_terminal_growth": 0.022},
    {"wacc": 0.085, "implied_terminal_growth": 0.027},
    {"wacc": 0.09, "implied_terminal_growth": 0.032}
  ]
}
```

**Algorithm:**

1. Construct a DCF function that takes the unknown (terminal_growth, explicit_growth, or exit_multiple) as a parameter and returns implied equity value per share.
2. Use root-finding (`scipy.optimize.brentq`) to find the unknown value that makes implied_equity_value_per_share == current_price_per_share.
3. Search bounds:
   - For terminal_growth: [-0.05, wacc − 0.001]
   - For explicit_growth: [-0.20, 0.50]
   - For exit_multiple: [3, 50] (EV/EBITDA range)
4. If root-finding fails to converge (function doesn't cross target value in search bounds): return FAILED with reason.
5. Run sensitivity around the solution (±50bp on WACC) to show robustness.
6. Compare against consensus long-term growth (from `eodhd_earnings_trends` if available) for interpretation.

**Edge cases:**
- Current price below any possible implied value at search-bound max: implied growth would need to be negative; flag as "market prices a decline."
- Function non-monotonic over search range: emit warning; use lowest root found.

---

### 3.6 `football_field_chart` (task #6)

**Purpose:** Synthesis chart showing valuation range from multiple methodologies side by side.

**Question answered:** How does this stock compare across all valuation methods, and where does the current price fall?

**Inputs:**
- `methodologies` (list[dict], required): each is `{name, low, median, high, source_artifact_id}`. Examples: DCF perpetuity, DCF exit-multiple, P/E peer, EV/EBITDA peer, EV/Sales peer, SOTP if applicable, 52w high/low, analyst target.
- `current_price` (float, required)
- `consensus_target_price` (float, optional)
- `currency` (str, optional, default `"USD"`)

**Output:**
```json
{
  "block_type": "chart",
  "chart_type": "football_field",
  "image_format": "svg | png_base64",
  "image_data": "...",
  "methodologies_summary": [
    {"name": "DCF perpetuity", "low": 120, "median": 150, "high": 185, "weight": null},
    {"name": "P/E peer (TTM)", "low": 130, "median": 165, "high": 200, "weight": null},
    ...
  ],
  "current_price": 150.0,
  "current_price_position": "median of range",
  "median_of_medians": 158.0,
  "verdict": "Trading near median of all methodologies."
}
```

**Algorithm:**

1. Sort methodologies by median value (or by an explicit order if provided).
2. Render horizontal bars: y-axis = methodology names, x-axis = price.
3. Each bar spans [low, high]; median marked with a tick.
4. Current price marked as vertical line.
5. Consensus target (if given) marked as second vertical line, dashed.
6. Currency unit shown on x-axis.

Returns either SVG (inline) or PNG (base64) per `output_format` directive in template.

---

### 3.7 `waterfall_chart` (task #6)

**Purpose:** Multi-step bridge visualization — FY-to-FY revenue/EPS/FCF bridge, decomposed into drivers.

**Question answered:** What drove the change from period A to period B?

**Inputs:**
- `starting_value` (float, required): value at start
- `starting_label` (str, required): e.g., `"FY24 Revenue"`
- `drivers` (list[dict], required): each is `{label, delta, color_hint}` (e.g., `{label: "Pricing", delta: 250, color_hint: "positive"}` or `{label: "FX headwind", delta: -120, color_hint: "negative"}`)
- `ending_label` (str, required): e.g., `"FY25 Revenue"`

**Output:**
```json
{
  "block_type": "chart",
  "chart_type": "waterfall",
  "image_format": "svg",
  "image_data": "...",
  "summary": {
    "starting_value": 10_000,
    "ending_value": 11_200,
    "total_change": 1_200,
    "total_change_pct": 12.0,
    "positive_drivers": [{"label": "Volume", "delta": 800}, ...],
    "negative_drivers": [{"label": "FX", "delta": -120}, ...]
  }
}
```

**Algorithm:**

1. Validate ending_value = starting_value + sum(deltas) ± tolerance.
2. Render bars: bar 1 = starting_value (full height), then per-driver "floating" bars showing positive (green) or negative (red) deltas, finally ending bar (full height).
3. Connector lines between bars.
4. Each driver labeled with magnitude + sign.

---

## 4. Custom helpers — Business quality / capital allocation (task #7)

### 4.1 `roic_panel`

**Purpose:** Multi-year ROIC, ROCE, ROIIC, and ROIC-WACC spread (economic profit).

**Question answered:** Does this company create value above its cost of capital, and how does that change over time?

**Inputs:**
- `historical_statements` (list[dict], required): N years of income, balance sheet, cash flow (from `eodhd_statements`)
- `wacc` (float, required or derivable): cost of capital
- `tax_rate` (float, optional, default 0.21): for NOPAT calc if effective tax rate not derivable from statements

**Source:** statements from EODHD; WACC from `ft_wacc` or composer-provided.

**Output:**
```json
{
  "periods": ["FY21", "FY22", "FY23", "FY24", "FY25"],
  "roic": [0.18, 0.20, 0.22, 0.21, 0.23],
  "roce": [0.15, 0.16, 0.17, 0.16, 0.18],
  "roiic": [null, 0.30, 0.45, 0.10, 0.50],
  "wacc": [0.085, 0.085, 0.090, 0.095, 0.085],
  "roic_wacc_spread": [0.095, 0.115, 0.130, 0.115, 0.145],
  "economic_profit_dollars": [...],
  "verdict": "Company has consistently generated returns above WACC for 5 years; widening spread suggests deepening competitive advantage.",
  "data_as_of": "2025-12-31"
}
```

**Algorithm:**

**NOPAT** (Net Operating Profit After Tax):
```
NOPAT = Operating_Income × (1 − effective_tax_rate)
```
If effective_tax_rate not derivable from statements (tax_expense / pre_tax_income), use input `tax_rate`.

**Operating Income source — explicit choice:** the helper accepts an optional `use_adjusted_ebit` flag (default `False`). When `True`, the helper consumes adjusted EBIT from `one_time_item_identification` (task #7) — stripping impairments, restructuring, M&A costs, and other one-time items the user opted to exclude. When `False`, uses reported GAAP EBIT. The output explicitly records which was used so downstream prose can cite "ROIC (GAAP)" vs. "ROIC (adjusted)".

**Invested Capital** (operating definition, applied identically in ROIC, ROIIC, and Economic Profit):
```
Invested_Capital = Total_Equity + Total_Debt − Cash_and_Equivalents
```
**Explicit treatment choices:**
- **Operating leases (post-ASC 842 / IFRS 16):** included in `Total_Debt` when companies report operating lease liabilities on the balance sheet. This matches modern institutional practice but inflates IC vs. pre-2019 historical comparisons. Output flags `operating_leases_included: true/false` per period.
- **Cash netting:** all cash and equivalents are netted (not just excess cash). Identifying excess cash requires a working-capital target that's hard to defend across companies. Output flags `cash_netting: "all_cash"` to be explicit.
- **Minority interest, goodwill:** not deducted; included in invested capital as part of equity / asset base.

Manual adjustment may be needed for unusual structures (large non-operating asset holdings, dual-class capital).

**ROIC:**
```
ROIC = NOPAT / Average Invested Capital
       (average = (IC_start + IC_end) / 2)
```

**ROCE** (Return on Capital Employed):
```
ROCE = EBIT / (Total Assets − Current Liabilities)
```

**ROIIC** (Return on Incremental Invested Capital, contemporaneous convention):
```
ROIIC_t = (NOPAT_t − NOPAT_{t-1}) / (Invested_Capital_t − Invested_Capital_{t-1})
```
Numerator and denominator both span period t-1 → t (contemporaneous, not lagged). First period has no ROIIC (returns null).

**Edge cases for ROIIC:**
- `ΔIC_t ≈ 0` (denominator near zero, threshold ±1% of IC_{t-1}): ROIIC reported as `null` with reason `"insufficient incremental capital deployed"` to avoid explosive or sign-flipped values.
- `ΔIC_t < 0` (capital base shrunk via buybacks > capex + WC growth): ROIIC reported with explicit sign-flip warning; interpreted as "returns generated despite (or because of) capital release" — flagged in narrative not silently negative.

**ROIC-WACC spread:**
```
spread_t = ROIC_t − WACC_t
```

**Economic profit (dollars):**
```
Economic_Profit_t = NOPAT_t − WACC_t × Average_Invested_Capital_t
                  ≡ (ROIC_t − WACC_t) × Average_Invested_Capital_t
```
Uses **average invested capital** (same base as ROIC), not ending IC. This ensures `EP = spread × capital` reconciles cleanly to NOPAT under the existing ROIC definition.

**Verdict generator:** LLM call given the time series + structured prompt to summarize trend (improving / deteriorating / consistent) + relative magnitude.

**Edge cases:**
- Operating income negative: ROIC negative; reported but flagged.
- Invested capital negative (rare; possible for high-leverage companies post-buyback): mark as N/A with reason.
- WACC not provided and no `ft_wacc` available: emit `required_param_unresolvable`.

---

### 4.2 `quality_of_earnings_panel`

**Purpose:** Composite earnings-quality diagnostic from accruals + cash flow alignment + R&D treatment.

**Question answered:** Are reported earnings of high quality (cash-backed, durable) or low quality (accrual-heavy, one-time inflated)?

**Inputs:** Historical statements (3-5 years).

**Output:**
```json
{
  "periods": ["FY21", ..., "FY25"],
  "sloan_accruals_ratio": [0.05, 0.04, 0.06, 0.08, 0.05],
  "ocf_to_ni": [1.15, 1.20, 1.10, 0.95, 1.18],
  "accruals_pct_of_ni": [0.12, 0.10, 0.15, 0.20, 0.13],
  "capitalized_rd_pct": [0.0, 0.0, 0.05, 0.08, 0.10],
  "deferred_tax_movement": [...],
  "restructuring_addbacks": [...],
  "overall_quality_score": 0.78,
  "quality_classification": "high | moderate | low",
  "flags": ["Capitalized R&D rose from 5% to 10% in FY24-25; may inflate margins."]
}
```

**Algorithm:**

**Sloan accruals ratio** (Sloan 1996):
```
Accruals_t = NI_t − CFO_t
Sloan_Accruals_Ratio_t = Accruals_t / Average_Total_Assets_t
                       (avg = (TA_start + TA_end) / 2)
```
This is the **level** of accruals scaled by average total assets, not the YoY change. Higher absolute value = more accrual-driven earnings = lower quality. Threshold: > 0.10 is concerning per the broader Sloan literature.

**Caveat:** Sloan's original 1996 measure is balance-sheet derived (Δnon-cash working capital − depreciation). We use the cash-flow proxy `NI − CFO`, which is widely accepted in modern usage but worth flagging in helper output.

**OCF / NI:**
```
OCF_to_NI_t = CFO_t / NI_t
```
< 1.0 means earnings exceed cash; ideally ≥ 1.0 (some industries naturally above due to D&A).

**Accruals as % of earnings (was: "non-cash earnings %"):**
```
Accruals_Pct_of_NI = (NI − CFO) / NI
```
High % = accounting-driven earnings. **Note:** The previous formula `(NI − CFO + Capex) / NI` was algebraically equivalent to `1 − FCF/NI` (cash conversion), which conflates capex (a capital-allocation choice) with accruals (an earnings-quality measure). `fcf_to_ni` in §4.7 already covers cash conversion; this metric is now purely about accrual intensity, with capex excluded.

**Capitalized R&D % (share of total R&D capitalized):**
```
Capitalized_RD_Pct = Capitalized_RD / (Capitalized_RD + Expensed_RD)
```
From cash flow statement (investing activities) and income statement. Denominator is **total R&D spend** (capitalized + expensed), so the ratio is the *capitalized share* of total R&D. Companies with rising capitalization shift expense out of the P&L, inflating margins.

**Deferred tax movement:** YoY change in deferred tax liability. Large swings suggest aggressive timing.

**Restructuring add-backs:** Sum of "restructuring", "impairment", "M&A costs" line items per period.

**Overall quality score** (composite):
```
score = w_1 × (1 − |sloan_accruals|/0.20) + w_2 × min(ocf_to_ni, 1.5)/1.5 + w_3 × (1 − accruals_pct_of_ni) + w_4 × (1 − capitalized_rd_pct/0.20)
```
Weights default: [0.30, 0.30, 0.20, 0.20]. Score ∈ [0, 1].

**Classification:**
- score ≥ 0.75: "high"
- 0.50 ≤ score < 0.75: "moderate"
- score < 0.50: "low"

**Flags:** auto-generated when any single metric crosses its threshold or shows sharp YoY change.

---

### 4.3 `capital_allocation_history`

**Purpose:** 5-year breakdown of how the company deployed operating cash flow.

**Question answered:** Where does this company's cash actually go?

**Inputs:** Historical statements (5 years).

**Output:**
```json
{
  "periods": ["FY21", ..., "FY25"],
  "ocf_total": [...],
  "uses": {
    "capex": [...],
    "rd": [...],
    "buybacks": [...],
    "dividends": [...],
    "ma_net": [...],
    "debt_paydown": [...],
    "other": [...]
  },
  "uses_pct_of_ocf": {...},
  "avg_pct_of_ocf_5y": {
    "capex": 0.25,
    "rd": 0.15,
    "buybacks": 0.30,
    "dividends": 0.15,
    "ma_net": 0.10,
    "debt_paydown": 0.05
  },
  "narrative_summary": "30% of cash returned to shareholders via buybacks (highest single bucket); 25% reinvested in capex.",
  "buyback_efficiency": {
    "total_buybacks_5y": 50_000_000_000,
    "avg_buyback_price_estimate": 145.0,
    "current_price": 150.0,
    "efficiency_verdict": "Buybacks executed at average price 3% below current — value-accretive."
  }
}
```

**Algorithm:**

For each period, classify cash flow statement items:
- **Capex**: from CFI, "purchase of property/equipment" + "capitalized R&D"
- **R&D expense**: from income statement (note: this is *expensed* R&D, separate from capitalized)
- **Buybacks**: from CFF, "purchase of treasury stock" + "repurchase of common stock" — positive number (outflow)
- **Dividends**: from CFF, "dividends paid"
- **M&A net**: from CFI, "acquisitions" − "divestitures" (net outflow)
- **Debt paydown**: from CFF, "repayment of debt" − "issuance of debt" (positive = net paydown)
- **Other**: residual

`pct_of_ocf` = bucket / CFO (capping at 1.0 per bucket; if total > 1.0, means deficit funded by debt).

`avg_pct_of_ocf_5y` = mean of pct_of_ocf across periods.

**Buyback efficiency:**
```
avg_buyback_price_estimate_t = buybacks_t / shares_repurchased_t
(from share count rollforward in equity)
weighted_avg_buyback_price = sum(buybacks_t) / sum(shares_repurchased_t)
efficiency_verdict:
  - if weighted_avg_buyback_price < current_price by > 5%: "value-accretive"
  - if within ±5%: "neutral"
  - if > current_price by > 5%: "value-destructive"
```

**Edge cases:**
- Negative CFO in a period: percentages reported as N/A for that period; absolute dollars still shown.
- Shares repurchased not disclosed at period level: estimate from share count rollforward; flag with caveat.

---

### 4.4 `earnings_surprise_tracker`

**Purpose:** 8-quarter beat/miss/inline tracking for EPS + revenue.

**Question answered:** Has this company consistently beaten, missed, or met expectations?

**Inputs:** From `eodhd_earnings_trends` — consensus + actual per quarter.

**Output:**
```json
{
  "quarters": ["Q1 FY24", ..., "Q4 FY25"],
  "eps": [
    {"quarter": "Q1 FY24", "consensus": 1.45, "actual": 1.52, "surprise_pct": 4.83, "verdict": "beat"},
    ...
  ],
  "revenue": [
    {"quarter": "Q1 FY24", "consensus": 25.1, "actual": 24.8, "surprise_pct": -1.20, "verdict": "miss"},
    ...
  ],
  "summary": {
    "eps_beat_rate_8q": 0.875,
    "eps_avg_surprise_pct": 3.2,
    "revenue_beat_rate_8q": 0.625,
    "revenue_avg_surprise_pct": 1.1,
    "consistency_score": 0.75,
    "narrative": "Beats EPS consistently; revenue performance more mixed."
  }
}
```

**Algorithm:**

For each quarter:
```
surprise_pct = (actual − consensus) / |consensus| × 100
verdict:
  - surprise_pct > 2%: "beat"
  - −2% ≤ surprise_pct ≤ 2%: "inline"
  - surprise_pct < −2%: "miss"
```

**Summary:**
- `beat_rate_8q = count(verdict == "beat") / 8`
- `avg_surprise_pct = mean(surprise_pct)`
- `consistency_score = 1 − stdev(surprise_pct) / mean(|surprise_pct|)` (clamped to [0, 1])

**Edge cases:** Consensus = 0 (rare); surprise_pct = N/A.

---

### 4.5 `analyst_revision_momentum`

**Purpose:** Track upgrades, downgrades, and target-price changes over rolling windows.

**Question answered:** Is consensus shifting up or down on this name?

**Inputs:** From `eodhd_earnings_trends` revisions history.

**Output:**
```json
{
  "window_30d": {
    "upgrades": 3,
    "downgrades": 1,
    "no_change": 12,
    "net_revision": 2,
    "target_price_avg_change_pct": 4.5,
    "eps_estimate_avg_change_pct": 2.1
  },
  "window_60d": {...},
  "window_90d": {...},
  "momentum_signal": "positive | neutral | negative",
  "narrative": "Net 5 upgrades over 90 days; target price up 8% on average. Strong positive revision momentum."
}
```

**Algorithm:**

For each window (30d / 60d / 90d):
- Count rating actions: upgrade, downgrade, reiterate (no-change).
- Compute avg change in target price across all revisions: `mean((new_target − old_target) / old_target)`.
- Compute avg change in EPS estimate.
- `net_revision = upgrades − downgrades`.

**Momentum signal:**
- net_revision_90d ≥ +3 and target_price_change > 2%: "positive"
- net_revision_90d ≤ −3 or target_price_change < −2%: "negative"
- else: "neutral"

---

### 4.6 `common_size_statements`

**Purpose:** Express income statement, balance sheet, and cash flow as percentages of revenue (or assets, for BS).

**Question answered:** How do line items scale, and how does cost structure change over time?

**Inputs:** Historical statements (3-5 years).

**Output:**
```json
{
  "periods": ["FY21", ..., "FY25"],
  "income_statement_common_size": {
    "revenue": [1.00, 1.00, 1.00, 1.00, 1.00],
    "cogs": [-0.55, -0.54, -0.53, -0.52, -0.51],
    "gross_profit": [0.45, 0.46, 0.47, 0.48, 0.49],
    "sga": [-0.20, -0.20, -0.19, -0.18, -0.18],
    "rd": [-0.08, -0.09, -0.10, -0.10, -0.11],
    "operating_income": [0.17, 0.17, 0.18, 0.20, 0.20],
    "net_income": [0.13, 0.14, 0.15, 0.16, 0.16]
  },
  "balance_sheet_common_size_pct_assets": {...},
  "cash_flow_common_size_pct_revenue": {...},
  "trends": {
    "gross_margin_trend": "+100 bps over 5 years, steadily expanding",
    "rd_intensity_trend": "+300 bps over 5 years, rising investment"
  }
}
```

**Algorithm:**
- Each line item divided by base (revenue for IS + CFS, total assets for BS).
- Trend annotation: linear fit slope × 5 years × 100 = bps over period.

---

### 4.7 `fcf_conversion_track_record`

**Purpose:** Multi-year FCF/EBITDA and FCF/NI conversion rates with trend.

**Question answered:** Does this company convert paper earnings into cash?

**Inputs:** Historical statements.

**Output:**
```json
{
  "periods": ["FY21", ..., "FY25"],
  "fcf": [...],
  "ebitda": [...],
  "ni": [...],
  "fcf_to_ebitda": [0.65, 0.70, 0.68, 0.72, 0.75],
  "fcf_to_ni": [1.05, 1.10, 1.08, 1.15, 1.18],
  "avg_fcf_to_ebitda_5y": 0.70,
  "avg_fcf_to_ni_5y": 1.11,
  "volatility": {"fcf_to_ebitda_stdev": 0.04, "fcf_to_ni_stdev": 0.05},
  "verdict": "High and stable cash conversion; FCF consistently exceeds NI driven by D&A timing."
}
```

**Algorithm:**

```
FCF = CFO − Capex
FCF_to_EBITDA = FCF / EBITDA
FCF_to_NI = FCF / NI
```

Trend = OLS slope across periods.

---

### 4.8 `total_shareholder_yield`

**Purpose:** (Dividends + Buybacks) / Market Cap, multi-year.

**Question answered:** What's the company's total cash return to shareholders as a yield?

**Inputs:** Historical statements + historical market cap (from `eodhd_historical_market_cap`).

**Output:**
```json
{
  "periods": ["FY21", ..., "FY25"],
  "dividend_yield": [0.005, 0.005, 0.006, 0.005, 0.006],
  "buyback_yield": [0.020, 0.025, 0.018, 0.022, 0.030],
  "total_shareholder_yield": [0.025, 0.030, 0.024, 0.027, 0.036],
  "avg_5y": 0.0284,
  "trend": "rising"
}
```

**Algorithm:**

```
Dividend_Yield_t = Total_Dividends_Paid_t / Market_Cap_t (using avg or end-of-period)
Buyback_Yield_t = Net_Buybacks_t / Market_Cap_t
Total_Shareholder_Yield = Dividend_Yield + Buyback_Yield
```

Net buybacks = buybacks − stock issued (avoid double-counting SBC issuance).

---

### 4.9 `cross_statement_validation`

**Purpose:** Sanity-check internal consistency of financial statements.

**Question answered:** Do the three statements tie out? Are there indications of restatement or data error?

**Inputs:** Historical statements.

**Output:**
```json
{
  "periods": ["FY21", ..., "FY25"],
  "checks": {
    "cf_ties_to_bs_cash_movement": [
      {"period": "FY25", "calculated": 1500, "reported": 1505, "delta": 5, "pass": true}
    ],
    "ni_ties_to_retained_earnings_movement": [...],
    "depreciation_in_cf_ties_to_ppe_movement": [...],
    "share_count_rollforward": [...]
  },
  "flags": [
    "Retained earnings rolloward FY23 has $50M unexplained gap — possible restatement of prior period."
  ]
}
```

**Algorithm:**

**Check 1: Cash flow ties to balance sheet cash movement**
```
calculated_movement = CFO + CFI + CFF + fx_effect_on_cash
reported_movement = Cash_BS_end − Cash_BS_start
delta = calculated_movement − reported_movement
pass = |delta| < tolerance (default $1M or 0.5% of cash, whichever is greater)
```

**Check 2: Net income ties to retained earnings movement**
```
calculated_movement = NI − Dividends_Paid − Buybacks_Charged_to_RE + Stock_Issuance_Above_Par + Other_Equity_Adjustments
reported_movement = RE_BS_end − RE_BS_start
delta = calculated_movement − reported_movement
pass = |delta| < tolerance
```

**Check 3: Depreciation in CF ties to PP&E movement**
```
implied_ppe_end = PPE_start + Capex_CFI − Depreciation_CF − Asset_Sales − Impairments
delta = implied_ppe_end − PPE_BS_end
pass = |delta| < tolerance
```

**Check 4: Share count rollforward**
```
implied_shares_end = Shares_start + Stock_Issued_SBC + Stock_Issued_Other − Shares_Repurchased
delta = implied_shares_end − Shares_BS_end
pass = |delta| < tolerance (e.g., 0.1% of shares)
```

**Flags generated** when any check fails or shows growing delta YoY (indicating accumulating error).

---

### 4.10 `one_time_item_identification`

**Purpose:** Build GAAP-to-adjusted earnings bridge by identifying non-recurring items.

**Question answered:** What's the company's clean earnings power excluding one-offs?

**Inputs:** Historical statements + (optional) MD&A text from `mda_extraction`.

**Output:**
```json
{
  "periods": ["FY24", "FY25"],
  "gaap_ni": [5000, 5500],
  "one_time_items": [
    {"period": "FY24", "label": "Impairment of goodwill", "amount": 800, "category": "impairment", "source": "income_statement_line_item"},
    {"period": "FY24", "label": "Restructuring charges", "amount": 200, "category": "restructuring", "source": "income_statement_line_item"},
    {"period": "FY25", "label": "Legal settlement (one-time)", "amount": 150, "category": "legal", "source": "mda_extraction"},
    {"period": "FY25", "label": "M&A transaction costs", "amount": 100, "category": "ma_costs", "source": "income_statement_line_item"}
  ],
  "adjustments_total_per_period": {"FY24": 1000, "FY25": 250},
  "adjusted_ni": [6000, 5750],
  "adjusted_eps_diluted": [4.50, 4.30]
}
```

**Algorithm:**

Two-source approach:

**A. Deterministic scan of statements** — line items containing these keywords (or known schema fields if EODHD provides them):
- `restructuring`, `impairment`, `goodwill_impairment`
- `gain_on_sale`, `loss_on_disposal`
- `litigation_charge`, `legal_settlement`
- `ma_transaction_costs`, `acquisition_costs`
- `pension_adjustment`
- `tax_settlement`

**B. LLM-assisted scan of MD&A** — calls `mda_extraction` (task #5) and prompts the LLM to identify management-noted one-time items not in standard line items.

Each item is tax-affected at the period's effective tax rate (if applicable). Pre-tax items adjusted to after-tax.

```
Adjusted_NI_t = GAAP_NI_t + sum(items_t × (1 − tax_rate))
Adjusted_EPS_t = Adjusted_NI_t / shares_outstanding_diluted_t
```

**Edge cases:**
- LLM unavailable (no API key): skip source B; emit warning that MD&A items were not extracted.
- Item already non-cash (e.g., impairment): no tax adjustment.

---

### 4.11 `organic_vs_inorganic_growth`

**Purpose:** Decompose total revenue growth into organic (same-business) and inorganic (acquired) components.

**Question answered:** How much of the growth is from organic operations vs. acquisitions?

**Inputs:** Historical statements + segment data + (optional) MD&A extraction for acquisition disclosures.

**Output:**
```json
{
  "periods": ["FY24", "FY25"],
  "total_growth_pct": [0.15, 0.20],
  "organic_growth_pct": [0.08, 0.12],
  "inorganic_growth_pct": [0.07, 0.08],
  "acquisitions_in_period": [
    {"period": "FY24", "target": "Acquired Co", "deal_size": 5_000, "revenue_contribution_estimated": 700}
  ],
  "currency_effect_pct": [-0.02, 0.01],
  "true_organic_constant_currency_pct": [0.10, 0.11]
}
```

**Algorithm:**

If company discloses organic growth directly (common for multinationals):
- Pull disclosed organic growth via `mda_extraction`.

Otherwise, estimate:
```
Inorganic_Growth_Pct_t = (Revenue_from_acquisitions_in_year_t) / Revenue_{t-1}
Organic_Growth_Pct_t = Total_Growth_Pct_t − Inorganic_Growth_Pct_t
```

Revenue from acquisitions estimated from disclosed deal data (target's annualized revenue at close).

Currency effect from disclosed constant-currency growth in MD&A; if not disclosed, estimate via:
```
Currency_Effect_t = Reported_Growth_t − Constant_Currency_Growth_t
```

True organic constant-currency = Total − Inorganic − Currency_Effect.

**Edge cases:** No M&A disclosed in period: inorganic = 0; organic = total. Currency effect = 0 for domestic companies.

---

### 4.12 `currency_neutral_growth`

**Purpose:** Calculate constant-currency growth for multinational companies.

**Inputs:** Total reported growth + currency effect (from company disclosure) OR raw segment data with FX rates.

**Output:**
```json
{
  "periods": ["FY24", "FY25"],
  "reported_growth_pct": [0.15, 0.20],
  "currency_effect_pct": [-0.03, 0.02],
  "constant_currency_growth_pct": [0.18, 0.18]
}
```

**Algorithm:**

```
Constant_Currency_Growth = Reported_Growth − Currency_Effect
```

If raw segment data available with FX rates: recompute prior-year revenue at current-year FX rates and recalculate growth.

---

### 4.13 `margin_trajectory_regression`

**Purpose:** Linear regression of margins over time to quantify trend.

**Inputs:** Quarterly or annual gross/operating/EBITDA/net margins (N periods).

**Output:**
```json
{
  "margin_type": "operating",
  "periods": ["Q1 FY23", ..., "Q4 FY25"],
  "values": [0.18, 0.19, 0.20, ...],
  "slope_per_period": 0.005,
  "slope_per_year_annualized": 0.020,
  "r_squared": 0.85,
  "p_value": 0.001,
  "trend_classification": "improving | stable | deteriorating",
  "sustainability_score": 0.78,
  "stdev": 0.012
}
```

**Algorithm:**

Uses `ols_regression` (task #4) on margin time series vs. time index.

```
slope_per_year_annualized = slope_per_period × periods_per_year
trend_classification:
  - slope > 0.002 (200 bps/year) AND p_value < 0.10: "improving"
  - slope < −0.002 AND p_value < 0.10: "deteriorating"
  - otherwise: "stable"
sustainability_score = R² × (1 − stdev / |mean(values)|)  # clamped [0, 1]
```

---

### 4.14 `operating_leverage_analysis`

**Purpose:** Compute operating leverage (% change in operating income / % change in revenue) per quarter.

**Output:**
```json
{
  "quarters": [...],
  "revenue_growth_pct": [...],
  "op_income_growth_pct": [...],
  "operating_leverage": [...],
  "avg_leverage": 1.8,
  "interpretation": "1% revenue growth historically yields 1.8% operating income growth — moderate operating leverage."
}
```

**Algorithm:**

```
Operating_Leverage_t = ((OpInc_t − OpInc_{t-1}) / OpInc_{t-1})
                     ÷
                       ((Revenue_t − Revenue_{t-1}) / Revenue_{t-1})

  = OpInc_growth_pct_t / Revenue_growth_pct_t
```

**Negative-growth handling (audit clarification):** Compute the ratio for all periods, including those where revenue or operating income declined. Sign-flip cases (revenue down, op income up — or vice versa) are flagged explicitly as `sign_divergence: true` with narrative explanation, since downturn deleverage is the entire reason to look at operating leverage. Do not silently drop these periods; they carry the most analytical signal.

---

### 4.15 `sbc_intensity`

**Purpose:** Share-based compensation as % of revenue, multi-quarter trend.

**Output:**
```json
{
  "quarters": [...],
  "sbc_dollars": [...],
  "revenue": [...],
  "sbc_pct_revenue": [0.08, 0.085, 0.09, 0.10, 0.11],
  "trend": "rising",
  "avg_last_4q": 0.10,
  "benchmark_vs_peers": "above_median",
  "narrative": "SBC has risen from 8% to 11% of revenue over 5 quarters — increasing dilution pressure on shareholders."
}
```

---

### 4.16 `cap_table_dilution`

**Purpose:** Decompose diluted share count growth YoY.

**Output:**
```json
{
  "periods": ["FY24", "FY25"],
  "diluted_shares_start": [1000, 1020],
  "diluted_shares_end": [1020, 1050],
  "decomposition": {
    "sbc_issuance": [25, 30],
    "secondary_offerings": [0, 5],
    "ma_issuance": [10, 0],
    "buybacks_offset": [-15, -5]
  },
  "net_dilution_pct": [0.02, 0.0294]
}
```

**Algorithm:**

Source decomposition from cash flow statement (CFF) line items:
- SBC issuance: from "stock-based compensation" in CFO (added back) cross-referenced with equity rollforward
- Secondary offerings: from CFF "proceeds from issuance of common stock"
- M&A issuance: from CFI/CFF "stock issued for acquisitions"
- Buybacks: from CFF "repurchase of common stock" (counted as negative dilution)

Reconciliation: `sbc + secondary + ma − buybacks = end − start` ± rounding.

---

### 4.17 `piotroski_f_score`

**Purpose:** 9-criterion fundamentals quality score (Piotroski 2000).

**Output:**
```json
{
  "score": 7,
  "max_score": 9,
  "criteria": {
    "profitability_roa_positive": 1,
    "profitability_delta_roa_positive": 1,
    "profitability_cfo_positive": 1,
    "profitability_cfo_gt_ni": 1,
    "leverage_lt_debt_decreased": 0,
    "leverage_current_ratio_increased": 1,
    "leverage_no_new_shares_issued": 1,
    "operating_efficiency_gross_margin_increased": 1,
    "operating_efficiency_asset_turnover_increased": 0
  },
  "interpretation": "Score of 7/9 indicates strong fundamentals improvement YoY."
}
```

**Algorithm:**

Each criterion = 1 if true, 0 if false. These are the canonical 9 Piotroski (2000) signals — note `Δ ROA > 0` is a distinct signal from `ROA > 0` (the latter tests the sign; the former tests improvement).

**Profitability (4 criteria):**
1. ROA > 0 in current year (NI / total assets)
2. **Δ ROA > 0** (ROA improved YoY: `ROA_t > ROA_{t-1}`)
3. CFO > 0 in current year
4. CFO > NI (earnings quality — accruals signal)

**Leverage / Liquidity / Source of Funds (3 criteria):**
5. Long-term debt / Total assets has decreased YoY
6. Current ratio has increased YoY
7. No new shares issued in current year (diluted shares ≤ shares prior)

**Operating Efficiency (2 criteria):**
8. Gross margin has increased YoY
9. Asset turnover (revenue / total assets) has increased YoY

Sum = F-score. Range [0, 9]. Score ≥ 7 = strong; ≤ 3 = weak.

**Note:** Earlier draft had `NI > 0` as a separate criterion, which is redundant with `ROA > 0` (since total assets are always positive, `NI > 0 ⟺ ROA > 0`). Corrected to `Δ ROA > 0` per Piotroski's original specification.

---

### 4.18 `beneish_m_score`

**Purpose:** Earnings manipulation red-flag detector (Beneish 1999).

**Output:**
```json
{
  "m_score": -2.85,
  "threshold": -1.78,
  "verdict": "below threshold; no manipulation signal",
  "components": {
    "DSRI": 1.05,
    "GMI": 0.95,
    "AQI": 1.02,
    "SGI": 1.20,
    "DEPI": 1.00,
    "SGAI": 0.98,
    "LVGI": 1.05,
    "TATA": 0.04
  }
}
```

**Algorithm:**

8-input model. For each, compute ratio of current to prior year:

1. **DSRI** (Days Sales Receivable Index) = `(AR_t / Revenue_t) / (AR_{t-1} / Revenue_{t-1})`
2. **GMI** (Gross Margin Index) = `Gross_Margin_{t-1} / Gross_Margin_t` (note: inverted)
3. **AQI** (Asset Quality Index) = `(1 − (Current_Assets + PPE) / Total_Assets)_t / same_{t-1}`
4. **SGI** (Sales Growth Index) = `Revenue_t / Revenue_{t-1}`
5. **DEPI** (Depreciation Index) = `(Depreciation_{t-1} / (Depreciation_{t-1} + PPE_{t-1})) / (Depreciation_t / (Depreciation_t + PPE_t))`
6. **SGAI** (Sales, General & Admin Index) = `(SGA_t / Revenue_t) / (SGA_{t-1} / Revenue_{t-1})`
7. **LVGI** (Leverage Index) = `(Total_Debt_t / Total_Assets_t) / (Total_Debt_{t-1} / Total_Assets_{t-1})`
8. **TATA** (Total Accruals to Total Assets) = `(NI − CFO)_t / Total_Assets_t`
   - **Methodology caveat:** This is the common modern cash-flow proxy. Beneish's original 1999 TATA uses a balance-sheet working-capital-delta construction: `(ΔCA − ΔCash − ΔCL + ΔSTD − Depreciation) / TA`. The `NI − CFO` proxy is widely accepted in modern usage but should be flagged in output so an auditor can cross-check against the original specification if material to a thesis.

**M-score formula:**
```
M_score = −4.84 + 0.92 × DSRI + 0.528 × GMI + 0.404 × AQI + 0.892 × SGI + 0.115 × DEPI − 0.172 × SGAI + 4.679 × TATA − 0.327 × LVGI
```

**Threshold:** M-score > −1.78 indicates potential manipulation; below = clean signal.

---

### 4.19 `cash_conversion_cycle`

**Purpose:** Working capital cycle = DSO + DIO − DPO.

**Output:**
```json
{
  "periods": ["FY21", ..., "FY25"],
  "dso": [45, 47, 48, 50, 52],
  "dio": [60, 62, 65, 68, 70],
  "dpo": [35, 36, 38, 38, 40],
  "ccc": [70, 73, 75, 80, 82],
  "trend": "lengthening",
  "narrative": "Cash conversion cycle has extended by 12 days over 5 years — working capital intensity is increasing."
}
```

**Algorithm:**

```
DSO = Accounts_Receivable_end / Revenue × 365
DIO = Inventory_end / COGS × 365
DPO = Accounts_Payable_end / COGS × 365
CCC = DSO + DIO − DPO
```

Trend classification via OLS slope.

**Methodology caveat (recorded in output):** uses **period-end** balances and **total revenue / total COGS**. Textbook-purist version uses **average balances** and (for DSO) **credit sales only** / (for DPO) **purchases only**. The simpler version is appropriate for trend analysis where the noise from end-of-period balance vs. average is typically much smaller than the year-over-year change. Output includes `methodology: "period_end_total_revenue"` flag so prose can cite the convention.

---

### 4.20 `sustainable_growth_rate`

**Purpose:** Sustainable growth rate = ROE × retention ratio. Sanity check vs. consensus growth.

**Output:**
```json
{
  "roe": 0.20,
  "payout_ratio": 0.30,
  "retention_ratio": 0.70,
  "sustainable_growth_rate": 0.14,
  "consensus_long_term_growth": 0.10,
  "delta": 0.04,
  "verdict": "Company can sustain 14% growth from internal cash flow, above consensus 10%. Growth assumptions appear conservative or company has excess capital for buybacks."
}
```

**Algorithm:**

```
Payout_Ratio = Dividends_Paid / NI
Retention_Ratio = 1 − Payout_Ratio
Sustainable_Growth_Rate = ROE × Retention_Ratio
```

**Methodology caveat (recorded in output):** Uses the standard simple form `ROE × b`. If ROE is computed on ending equity, this slightly understates SGR because retained earnings haven't fully earned a return yet. The Higgins variant `ROE × b / (1 − ROE × b)` exists for the leverage-constant version, but the simple form is the conventional starting point in equity research. Output flags `methodology: "simple_roe_x_retention"` so prose can cite the convention.

Compare to consensus from `eodhd_earnings_trends` long-term growth field.

---

## 5. Custom helpers — Risk + macro (task #8)

### 5.1 `drawdown_panel`

**Purpose:** Drawdown series, max drawdown, duration, recovery time.

**Inputs:** Daily or weekly price series.

**Output:**
```json
{
  "price_series_start": "2020-01-01",
  "price_series_end": "2026-05-21",
  "drawdown_series": [...],
  "max_drawdown": -0.45,
  "max_drawdown_peak_date": "2021-11-15",
  "max_drawdown_trough_date": "2022-10-12",
  "max_drawdown_duration_days": 331,
  "recovery_date": "2024-03-08",
  "recovery_duration_days": 513,
  "currently_in_drawdown": false,
  "current_drawdown": -0.05,
  "all_drawdowns_gt_10pct": [
    {"peak": "2021-11-15", "trough": "2022-10-12", "recovery": "2024-03-08", "depth": -0.45, "duration_days": 331, "recovery_days": 513}
  ]
}
```

**Algorithm:**

```
running_max_t = max(price_0, ..., price_t)
drawdown_t = (price_t − running_max_t) / running_max_t
max_drawdown = min(drawdown_t)
max_drawdown_peak_date = date where running_max was set just before the trough
max_drawdown_trough_date = date of min drawdown
recovery_date = first date after trough where price >= running_max_at_peak
duration_days = trough_date − peak_date
recovery_days = recovery_date − trough_date (or null if not recovered)
```

All drawdowns > 10%: identify each peak-trough-recovery triplet where depth ≥ 10%.

---

### 5.2 `yield_curve_shape`

**Purpose:** Compute key yield-curve shape signals.

**Inputs:** Daily UST curve from `eodhd_yield_curve` (latest snapshot or time series).

**Output:**
```json
{
  "as_of": "2026-05-21",
  "10y_2y_spread_bps": 45,
  "10y_3m_spread_bps": 80,
  "5y_2y_spread_bps": 25,
  "30y_10y_spread_bps": 30,
  "inverted": false,
  "days_since_last_inversion": 245,
  "curve_slope_bps_per_year": 12,
  "curvature_score": 0.15,
  "classification": "upward sloping, modestly steep"
}
```

**Algorithm:**

```
10y_2y_spread = yield_10y − yield_2y (in basis points × 100)
10y_3m_spread = yield_10y − yield_3m
inverted = 10y_2y_spread < 0  # most-cited recession indicator
curve_slope = OLS slope on (maturity_years, yield)
curvature = (yield_2y + yield_30y) / 2 − yield_10y  # belly shape
```

Days since last inversion: rolling check over the historical curve series.

Classification:
- 10y_2y > 100 bps: "steep upward"
- 30 ≤ 10y_2y ≤ 100: "modestly upward"
- 0 ≤ 10y_2y < 30: "flat"
- 10y_2y < 0: "inverted"

---

### 5.3 `commodity_exposure_tracker`

**Purpose:** Track correlation between subject company's revenue/margin and a relevant commodity price series.

**Inputs:**
- `subject_metric_series` (Series, required): revenue or margin per quarter
- `commodity_series` (Series, required): commodity price per quarter (or month, averaged)
- `commodity_name` (str, required): e.g., "WTI Oil", "Henry Hub Gas", "Copper LME"

**Output:**
```json
{
  "commodity": "WTI Oil",
  "correlation_pearson": 0.78,
  "correlation_spearman": 0.72,
  "lag_correlation_max": {"lag_quarters": 1, "correlation": 0.85},
  "regression_slope": 0.012,
  "interpretation": "Strong positive correlation with WTI; revenue tends to track oil prices with 1-quarter lag. Each $10 WTI move corresponds to ~12% revenue change."
}
```

**Algorithm:**

Uses `correlation_matrix` (task #4) on the two series + lagged versions (lags 0-4 quarters).

Regression slope from `ols_regression` of subject_metric on commodity_price.

---

## 6. Custom helpers — SaaS KPIs (task #11)

### 6.1 `saas_kpi_panel`

**Purpose:** Quarterly SaaS KPI synthesis from disclosed metrics.

**Question answered:** What's this SaaS company's health on the metrics investors track?

**Inputs (all optional except as noted; graceful degradation):**
- `arr_current` (float, required)
- `arr_prior_year` (float, optional): for YoY growth
- `arr_prior_quarter` (float, optional): for sequential growth
- `revenue_growth_rate` (float, optional): for Rule of 40
- `fcf_margin` (float, optional): for Rule of 40
- `nrr` (float, optional): Net Revenue Retention (decimal, e.g., 1.18 for 118%)
- `grr` (float, optional): Gross Revenue Retention
- `new_arr_this_quarter` (float, optional): for Magic Number
- `sm_spend_prior_quarter` (float, optional): for Magic Number
- `ltv` (float, optional)
- `cac` (float, optional)
- `cac_payback_months` (float, optional)
- `customer_count_current` (int, optional)
- `customer_count_prior_year` (int, optional)
- `gross_margin` (float, optional): for unit-economics framing

**Output:**
```json
{
  "as_of": "2026-Q1",
  "arr": {
    "current": 1_200_000_000,
    "yoy_growth_pct": 0.32,
    "qoq_growth_pct": 0.07,
    "disclosed": true
  },
  "rule_of_40": {
    "value": 50,
    "components": {"revenue_growth": 32, "fcf_margin": 18},
    "classification": "healthy",
    "threshold": 40,
    "disclosed": true
  },
  "nrr": {"value": 1.18, "classification": "strong", "threshold_healthy": 1.10, "disclosed": true},
  "grr": {"value": 0.95, "classification": "strong", "threshold_healthy": 0.90, "disclosed": true},
  "implied_churn_rate": {"value": 0.05, "calculation": "1 - GRR", "disclosed": false},
  "magic_number": {"value": 1.05, "classification": "efficient", "calculation": "net_new_ARR_this_quarter / S&M_prior_quarter (no ×4 — ARR is already annualized)", "disclosed": false},
  "ltv_cac": {"value": 3.2, "classification": "healthy", "threshold_healthy": 3.0, "disclosed": true},
  "cac_payback_months": {"value": 18, "classification": "moderate", "disclosed": true},
  "customer_count": {"current": 5000, "yoy_growth_pct": 0.20, "disclosed": true},
  "narrative": "...",
  "disclosure_completeness": 0.85
}
```

**Algorithm:**

```
ARR_YoY_Growth = (ARR_current − ARR_prior_year) / ARR_prior_year
ARR_QoQ_Growth = (ARR_current − ARR_prior_quarter) / ARR_prior_quarter

Rule_of_40 = revenue_growth_rate × 100 + fcf_margin × 100  # both as percentages
  - classification: ≥ 50 "excellent", 40-49 "healthy", 30-39 "acceptable", < 30 "weak"

Magic_Number = net_new_ARR_this_quarter / sm_spend_prior_quarter
  - classification: > 1.0 "efficient", 0.5-1.0 "moderate", < 0.5 "inefficient"
  - NO ×4 annualization: ARR is already an annualized recurring revenue figure
  - net_new_ARR = ARR_current_quarter − ARR_prior_quarter (sequential)
  - The original Scale Venture formula uses a QUARTERLY revenue delta in the
    numerator with a ×4 annualizer: (Rev_Q − Rev_Q-1) × 4 / S&M_prior_Q.
    That formula is mathematically equivalent ONLY when ARR ≈ revenue × 4.
    Since this helper takes net-new ARR directly as input, no multiplier is applied.

LTV_CAC = ltv / cac
  - classification: > 3.0 "healthy", 1.5-3.0 "moderate", < 1.5 "weak"

NRR classification: > 1.20 "best in class", 1.10-1.20 "strong", 1.00-1.10 "stable", < 1.00 "shrinking"

GRR classification: > 0.95 "strong", 0.90-0.95 "moderate", < 0.90 "weak"

Implied_Churn_Rate = 1 − GRR (when GRR disclosed)
```

**Disclosure completeness:** ratio of metrics with `disclosed: true` out of all metrics in the panel.

**Narrative:** LLM call summarizing strengths + weaknesses from the panel.

---

## 7. LLM-orchestrated helpers (task #5)

These helpers use the Anthropic API with JSON-mode structured output. The "algorithm" is the prompt design + output schema.

### 7.1 `transcript_tone_analysis`

**Purpose:** Analyze earnings-call transcript tone per speaker.

**Inputs:**
- `transcript_text` (str, required) or `transcript_pdf_extract` (from `pdf_ingest`)
- `speakers_list` (list[str], optional): if known, otherwise auto-detect

**Output schema (JSON-mode):**
```json
{
  "ticker": "...",
  "quarter": "Q1 FY26",
  "date": "2026-04-15",
  "speakers": [
    {
      "name": "CEO Jane Doe",
      "role": "management",
      "tone": "confident | cautious | hedging | defensive",
      "evidence_quotes": ["..."],
      "hedging_language_count": 3,
      "forward_looking_count": 8
    },
    {
      "name": "Analyst John Smith (Morgan Stanley)",
      "role": "analyst",
      "tone": "constructive | challenging | neutral",
      "evidence_quotes": ["..."]
    }
  ],
  "prepared_remarks_tone": "confident",
  "qa_tone": "slightly cautious",
  "prepared_vs_qa_tone_differential": "QA more cautious than prepared remarks",
  "hedging_language_themes": ["uncertainty about Q2", "macroeconomic concerns"],
  "extraction_quality": "high"
}
```

**Prompt design:**

```
You are analyzing an earnings call transcript. For each speaker, classify their tone using these categories:
- Management tones: confident | cautious | hedging | defensive
- Analyst tones: constructive | challenging | neutral

Detect hedging language (phrases like "we expect", "we believe", "subject to", "may", "could", "depending on"). Count occurrences per speaker.

Identify forward-looking statements (statements about future periods).

Compare prepared-remarks tone vs. Q&A tone — note any differential.

Provide 2-3 evidence quotes per speaker supporting your tone classification.

Output as JSON matching the schema. Quote text exactly; do not paraphrase.
```

---

### 7.2 `tone_shift_qoq`

**Purpose:** Compare current transcript tone to prior transcript; detect shifts.

**Inputs:** Current quarter transcript + prior quarter transcript.

**Output:**
```json
{
  "current_quarter": "Q1 FY26",
  "prior_quarter": "Q4 FY25",
  "overall_tone_shift": "more cautious | unchanged | more confident",
  "key_shifts": [
    {
      "speaker_role": "CEO",
      "topic": "Q2 outlook",
      "shift_direction": "more cautious",
      "evidence_current": "...",
      "evidence_prior": "..."
    }
  ],
  "hedging_language_change_pct": 0.20,
  "narrative": "CEO struck noticeably more cautious tone on Q2 outlook compared to prior quarter."
}
```

---

### 7.3 `mda_extraction`

**Purpose:** Extract MD&A section from 10-K/10-Q with structured analysis.

**Inputs:** `pdf_extract` (from `pdf_ingest`) or raw text.

**Output:**
```json
{
  "company": "...",
  "period": "...",
  "mda_text": "...",
  "key_drivers_mentioned": [
    {"driver": "Cloud services growth", "direction": "positive", "evidence_quote": "..."}
  ],
  "key_headwinds_mentioned": [
    {"headwind": "FX impact on European revenue", "magnitude_quote": "...", "estimated_impact": "$200M"}
  ],
  "management_outlook_statements": ["..."],
  "non_gaap_reconciliation_mentions": ["..."],
  "segment_commentary": [
    {"segment": "Cloud", "growth_rate_disclosed": 0.32, "narrative": "..."}
  ]
}
```

---

### 7.4 `risk_factors_extraction`

**Purpose:** Extract Item 1A Risk Factors from 10-K with categorization.

**Output:**
```json
{
  "total_risk_count": 28,
  "risks": [
    {
      "title": "Dependence on advertising revenue",
      "category": "operational",
      "text_excerpt": "...",
      "first_appeared_year": "FY22",
      "language_changed_from_prior_year": true,
      "language_change_summary": "Added reference to specific advertiser concentration this year"
    }
  ],
  "categories_breakdown": {
    "operational": 8,
    "financial": 5,
    "governance": 2,
    "macro": 4,
    "regulatory": 6,
    "competitive": 3
  },
  "new_risks_this_year": [...],
  "removed_risks_from_prior_year": [...]
}
```

**Categories (closed enum):** operational, financial, governance, macro, regulatory, competitive.

YoY change detection requires both current and prior 10-K.

---

### 7.5 `forward_looking_statements`

**Purpose:** Extract forward-looking statements from filings or transcripts with qualifiers.

**Output:**
```json
{
  "source": "earnings_call | 10-Q | 10-K | press_release",
  "statements": [
    {
      "text": "We expect Q2 revenue to be in the range of $1.2B to $1.25B.",
      "category": "guidance | outlook | risk_factor_qualifier | strategic_statement",
      "confidence_indicator": "high | moderate | low",
      "qualifiers": ["expect", "subject to macroeconomic conditions"],
      "time_horizon": "Q2 FY26",
      "metric": "revenue",
      "value_range": [1_200_000_000, 1_250_000_000]
    }
  ]
}
```

---

### 7.6 `guidance_tracker`

**Purpose:** Build guidance-issued vs. guidance-actual track record over 8 quarters.

**Inputs:** Multi-quarter transcripts (8 prior) + actual results per period.

**Output:**
```json
{
  "quarters_analyzed": 8,
  "guidance_track_record": [
    {
      "guidance_quarter": "Q1 FY25",
      "guidance_for_period": "Q2 FY25",
      "guidance_issued": {"revenue_low": 1100, "revenue_high": 1150, "eps_low": 1.40, "eps_high": 1.45},
      "actual_results": {"revenue": 1130, "eps": 1.48},
      "verdict": "beat_modest | beat_large | within_range | miss"
    }
  ],
  "summary": {
    "beat_rate": 0.625,
    "miss_rate": 0.125,
    "within_range_rate": 0.250,
    "avg_revenue_surprise_pct": 1.2,
    "guidance_accuracy_heuristic": 0.78,
    "narrative": "Management has delivered above or within guidance 87.5% of the time over 8 quarters — high guidance accuracy."
  }
}
```

**Algorithm:**

For each guidance issuance, find matching actuals from `eodhd_earnings_trends`. Compare against guidance range:
- `beat_modest`: actual > guidance_high but by ≤ 5% (conservative guide, narrow beat)
- `beat_large`: actual > guidance_high by > 5% (significant beat above range)
- `within_range`: guidance_low ≤ actual ≤ guidance_high
- `miss`: actual < guidance_low

**Guidance accuracy heuristic** (note: this is an opinionated equity-research heuristic, not a neutral track-record metric):
- Weighted score where `within_range` = 1.0, `beat_modest` = 1.0, `beat_large` = 0.7, `miss` = 0.
- The 0.7 weight for `beat_large` reflects the **judgment** that chronic large beats indicate sandbagging — management deliberately guides low to ensure beats, which obscures the true business trajectory.
- Users who disagree (e.g., prefer reward-the-beat framing) can override the weights via helper params.

The output narrative explicitly distinguishes "guidance accuracy" (in-range delivery) from "management credibility on outlook" (the broader judgment), since the latter incorporates the heuristic above.

---

### 7.7 `customer_concentration_extraction`

**Purpose:** Extract customer concentration disclosures from 10-K.

**Output:**
```json
{
  "disclosed": true,
  "top_customer_pct_of_revenue": 0.18,
  "top_3_customers_pct": 0.35,
  "top_10_customers_pct": 0.60,
  "named_customers": ["Customer A", "Customer B"],
  "geographic_concentration_pct_by_region": {"Americas": 0.55, "EMEA": 0.25, "APAC": 0.20},
  "industry_concentration_pct_by_industry": {"financial_services": 0.30, "technology": 0.25, ...},
  "source_quote": "...",
  "risk_framing": "moderate | high | low"
}
```

Risk framing thresholds:
- top_customer > 10%: "high"
- top_3 > 30%: "high"
- otherwise: "moderate" or "low"

---

## 8. Verifier hooks summary

Each helper output type triggers the following verifier checks (existing 14-issue closed enum):

| Helper | Primary checks |
|---|---|
| `comparables` | `block_shape` (combined_implied_range present); `numeric_inconsistency` (numbers in prose match) |
| `sensitivity_table` | `block_shape` (grid dimensions); `numeric_inconsistency` (base_value matches base artifact) |
| `tornado_diagram` | `block_shape` (drivers ranked) |
| `scenario_weighting` | `block_shape` (probabilities sum to 1.0); `factual_inconsistency` (scenario rationale matches probabilities) |
| `reverse_dcf` | `numeric_inconsistency` (implied growth in prose matches output) |
| `football_field_chart` | `artifact_missing` (chart block must embed) |
| `roic_panel` | `numeric_inconsistency`; `citation_missing` (claims sourced) |
| `quality_of_earnings_panel` | `numeric_inconsistency`; `factual_inconsistency` (interpretive flags need citation) |
| `capital_allocation_history` | `numeric_inconsistency` |
| `earnings_surprise_tracker` | `numeric_inconsistency`; `temporal_ambiguous` (period anchors required) |
| `analyst_revision_momentum` | `temporal_ambiguous` (window size must be specified in prose) |
| `cross_statement_validation` | `factual_inconsistency` (flagged discrepancies must be discussed if section references the data) |
| All LLM-driven helpers (task #5) | `tombstone` (no generic claims); `citation_missing` (quotes must be sourced); `extraction_quality` field flags low-quality runs |

Future verifier extensions (task #10) — additional issue types:
- `source_tier_insufficient` — helper outputs feeding high-stakes claims must trace to PRIMARY-tier sources
- `temporal_ambiguous` — every period reference must be unambiguous
- `confidence_missing` — thesis drivers must carry HIGH/MED/LOW confidence
- `comparability_mismatch` — cross-company helper outputs must match FY conventions
- `numeric_ungrounded` — numbers in prose must trace to helper output, citation, or same-section derivation

---

## 9. Audit resolutions and remaining open questions

This section was updated 2026-05-21 after external audit. Items 1-11 below were the original open questions; resolutions are recorded inline.

### Resolved by audit

1. **Outlier filter default (IQR 1.5×) in `comparables`** — **RESOLVED: keep.** Appropriate for 5-15 peer sets; stdev-based filtering is unstable at small n.

2. **DCF terminal value method** — **RESOLVED: keep.** `dcf_valuation` exposes both perpetuity and exit-multiple. `reverse_dcf` defaults to terminal_growth. Matches institutional convention.

3. **Sloan accruals ratio threshold (0.10)** — **RESOLVED: keep threshold; base measure corrected** (§4.2). Previously, the implementation took a first-difference (`(Accruals_t − Accruals_{t-1}) / avg_TA`) which is "accruals acceleration," not Sloan's level measure. Now reads `Accruals_t / avg_TA_t`. Threshold > 0.10 concerning is consistent with Sloan literature.

4. **Beneish M-score threshold (−1.78)** — **RESOLVED: keep.** Audit confirmed −1.78 is correct for the 8-variable model (−2.22 is the 5-variable cutoff). Sector adjustment is a refinement, not a correction.

5. **Operating leverage exclusion of negative-growth periods** — **RESOLVED: include with sign-flip flag** (§4.14). Downturn deleverage is the entire reason to compute operating leverage; silent exclusion would discard the most analytically valuable signal.

6. **NOPAT calculation in ROIC** — **RESOLVED: explicit `use_adjusted_ebit` flag** (§4.1). Default is reported GAAP EBIT × (1 − effective_tax_rate); when set, consumes adjusted EBIT from `one_time_item_identification`. Output records which was used.

7. **Invested Capital definition** — **RESOLVED: explicit treatment recorded in output** (§4.1). `Total_Equity + Total_Debt − Cash`. Operating leases included in `Total_Debt` (post-ASC 842 / IFRS 16). All cash netted (no excess-cash heuristic). Applied identically across ROIC, ROIIC, EP.

8. **Magic Number formula** — **CORRECTED** (§6.1). The original draft `(ΔARR × 4) / S&M_prior_Q` double-annualized ARR. Corrected to `net_new_ARR / S&M_prior_Q` (no ×4) since ARR is already an annualized figure.

9. **Football-field methodology weighting** — **OPEN.** Currently unweighted (min/median/max of per-multiple medians). Confidence weighting (DCF higher weight than multiples for high-quality businesses) is a defensible future addition but not currently exposed.

10. **Currency neutral growth direction convention** — **RESOLVED: explicit in output**. `Constant_Currency_Growth = Reported_Growth − Currency_Effect`. When company-disclosed, use disclosure directly. Output records which path was taken.

11. **EV→equity bridge in `comparables` (audit item, not previously open)** — **CORRECTED** (§3.1). Original formula `EV − net_debt + cash` double-counted cash. Corrected to `Equity = EV − net_debt` with `net_debt = total_debt − cash` defined once upstream.

### Additional corrections from audit

- **Piotroski F-score** (§4.17): removed redundant `NI > 0` signal (equivalent to `ROA > 0`); restored canonical `Δ ROA > 0` signal so all 9 distinct Piotroski criteria are present.
- **Non-cash earnings %** (§4.2): renamed to `accruals_pct_of_ni` and changed formula from `(NI − CFO + Capex)/NI` (which conflates capex with accruals) to `(NI − CFO)/NI` (pure accruals).
- **Capitalized R&D %** (§4.2): denominator clarified to `(Capitalized + Expensed)` so the ratio is the capitalized share of total R&D, not a ratio that can exceed 1.
- **Economic profit base** (§4.1): now uses **average invested capital** (same as ROIC) instead of ending IC, so `EP = NOPAT − WACC × avg_IC ≡ spread × avg_IC` reconciles cleanly.
- **ROIIC timing** (§4.1): contemporaneous convention (`ΔNOPAT_t / ΔIC_t`) instead of the original lagged form. Edge cases for near-zero/negative ΔIC documented.
- **Operating leverage formula** (§4.14): parenthesization made explicit to prevent left-to-right misinterpretation.
- **Comparables combined range** (§3.1): algorithm changed from min-of-lows / max-of-highs to min/median/max of per-multiple medians, matching the stated methodology and producing a less artificially-wide band.
- **guidance_tracker labels** (§7.6): `beat_within_range` renamed to `beat_modest` (since the actual is *above* the range, not within); credibility scoring relabeled as "guidance accuracy heuristic" and explicitly marked as an opinionated judgment rather than neutral track-record metric.

### Caveats added to output

- DSO/DIO/DPO methodology: period-end + total revenue / total COGS (vs. purist average balances + credit sales / purchases only)
- Sustainable growth rate methodology: simple `ROE × b` (vs. Higgins leverage-constant variant)
- Beneish TATA methodology: `(NI − CFO) / TA` cash-flow proxy (vs. Beneish original working-capital-delta construction)

---

## 10. References

- v2.2 design spec: `docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md`
- v2.2 implementation plan: `docs/superpowers/plans/2026-05-21-equity-research-v2.2.md`
- Build plan: `planning/2026-05-21-equity-research-engine-helper-stack.md`
- Existing helpers: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/`
- Sloan, R. G. (1996). "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?"
- Piotroski, J. D. (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers"
- Beneish, M. D. (1999). "The Detection of Earnings Manipulation"
- Mauboussin, M., & Rappaport, A. (2001). "Expectations Investing"
