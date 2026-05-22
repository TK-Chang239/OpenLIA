# Equity Research Helpers — Sector Modules Design (Wave 1)

**Date:** 2026-05-22
**Companion to:** `2026-05-21-equity-research-helpers-design.md` (generic stack) and `2026-05-22-helpers-design-supplement.md` (cross-sector valuation engines)
**Status:** Design contract for the five Wave-1 sector modules. Required reading for PRs 3.1-3.5 per impl plan §14.

---

## 1. Document purpose

Wave 1 sectors cover the institutional sub-universes where generic helpers (DCF, comparables, P/E) systematically misprice value. Each sector panel here defines the sector-specific KPIs, valuation lenses, and verifier rules that allow a report to be coherent on Banks, REITs, Pharma, Energy / E&P, and Insurance names.

Every sector panel follows the parent doc's §1 conventions (registration, exposure tiers, freshness/provenance, fail-soft policy). Each panel:

- Registers under a sector-specific `Category` (e.g. `sector_banks`).
- Produces a single primary artifact (`banks_sector_panel`, etc.) plus optional sub-artifacts (loan-loss analysis, royalty stack, etc.).
- Carries a required `skills/<panel>.md` doc per schema-and-skills §6 (entries #9-#13).
- Defines a sector-specific Stage 5 planner heuristic: when the user's ticker resolves to a primary GICS code in {Banks: 4010..., REITs: 6010..., Pharma: 3520..., E&P: 1010..., Insurance: 4030...}, the sector panel is auto-included in the plan unless overridden.

Wave 2 sectors (Mining, Retail, Telecom, Semis, Airlines) are out of scope here — task #22, parked.

---

## 2. Banks sector module — `banks_sector_panel`

**Purpose:** Compute and synthesize the institutional metrics for a bank: net interest margin, regulatory capital, return on tangible common equity, efficiency ratio, net charge-offs, loan-loss provisioning, and credit-quality trajectory. Generic helpers fail badly on banks (P/E ignores capital adequacy; debt/equity is meaningless when deposits are liabilities; EV/EBITDA is structurally inapplicable).

**Question answered:** What is this bank's profitability, capital adequacy, credit quality, and operating efficiency, in the metrics regulators and equity holders actually use?

**Report types:** Initiation (mandatory for any bank), Update (post-quarterly release), Sector (cross-bank cohort).

**Inputs:**
- `ticker` (str, required)
- `as_of_date` (date, required)
- `bank_data_source` (str, optional, default `"eodhd_praams_bank"`): `"eodhd_praams_bank"` (preferred — pre-normalized bank statements) | `"eodhd_fundamentals"` (fallback — generic statements with bank-specific field mapping applied)
- `regulatory_regime` (str, optional, default `"basel_iii"`): `"basel_iii"` | `"basel_iv"` | `"us_camels"` | `"prra_uk"` etc. — drives which capital ratios are required
- `peer_set` (list[str], optional): for cross-bank context

**Source:** primary is EODHD Praams Bank endpoints (`get_mp_praams_bank_balance_sheet_by_ticker`, `get_mp_praams_bank_income_statement_by_ticker`). Fall back to `eodhd_fundamentals` if Praams unavailable; the fallback path requires a bank-statement-field-mapping table in `data/reference/bank_field_map.yaml`.

**Output:**
```json
{
  "ticker": "JPM",
  "as_of": "2026-03-31",
  "profitability": {
    "net_interest_income": 23800,
    "non_interest_income": 18900,
    "total_revenue": 42700,
    "net_interest_margin_pct": 0.0270,
    "fee_income_pct_of_revenue": 0.443,
    "net_income": 14500,
    "rotce_pct": 0.197,
    "roa_pct": 0.0118,
    "roe_pct": 0.155,
    "efficiency_ratio_pct": 0.520
  },
  "capital_adequacy": {
    "cet1_ratio_pct": 0.151,
    "tier1_ratio_pct": 0.168,
    "total_capital_ratio_pct": 0.190,
    "leverage_ratio_pct": 0.072,
    "slr_pct": 0.063,
    "cet1_buffer_vs_minimum": 0.061,
    "regulatory_minimum_cet1": 0.090,
    "buffer_adequacy": "comfortable"
  },
  "credit_quality": {
    "loan_loss_reserve_to_loans": 0.0185,
    "nco_rate_annualized": 0.0048,
    "nonperforming_loans_pct": 0.0072,
    "ldr": 0.578,
    "coverage_ratio_reserves_to_npl": 2.57,
    "loan_loss_provision_quarter": 1900,
    "loan_loss_provision_yoy_change_pct": 0.150,
    "credit_cycle_position": "mid_cycle_normalizing"
  },
  "loan_mix": {
    "commercial_pct": 0.42,
    "consumer_pct": 0.35,
    "real_estate_pct": 0.18,
    "other_pct": 0.05
  },
  "deposit_mix": {
    "non_interest_bearing_pct": 0.30,
    "interest_bearing_pct": 0.55,
    "wholesale_pct": 0.15,
    "deposit_cost_pct": 0.0185,
    "deposit_beta": 0.42
  },
  "trends_5y": {
    "nim_pct":         [0.0238, 0.0212, 0.0195, 0.0240, 0.0270],
    "cet1_ratio_pct":  [0.135, 0.140, 0.142, 0.148, 0.151],
    "rotce_pct":       [0.155, 0.170, 0.165, 0.180, 0.197],
    "efficiency_ratio_pct": [0.560, 0.545, 0.540, 0.530, 0.520]
  },
  "narrative": "JPM Q1: NIM 270bps (+30bps YoY on asset repricing); RoTCE 19.7% well ahead of cost of capital; CET1 15.1% with 610bps buffer over 9.0% minimum. NCO 48bps (+5bps YoY) reflects normalization, not credit stress. Efficiency 52.0% — sustained discipline.",
  "warnings": [],
  "data_as_of": "2026-03-31",
  "source_provenance": ["eodhd:praams_bank_income_statement:JPM:Q1-2026"]
}
```

**Methodology:**

**Profitability metrics:**
```
net_interest_income      = interest_income - interest_expense
total_revenue            = net_interest_income + non_interest_income
net_interest_margin      = net_interest_income / average_earning_assets   [annualized]
fee_income_pct_of_revenue = non_interest_income / total_revenue
efficiency_ratio         = non_interest_expense / total_revenue           [lower is better]
roa                      = NI / average_total_assets                       [annualized]
roe                      = NI / average_common_equity                      [annualized]
rotce                    = NI / average_tangible_common_equity             [annualized — the institutional gold standard]
```

Tangible common equity = common equity − goodwill − other intangibles. RoTCE strips out balance-sheet accounting noise; for any bank with material acquisition goodwill (most large banks), RoTCE is the metric to anchor narrative on, not ROE.

**Capital adequacy (Basel III defaults):**
```
cet1_ratio                  = CET1_capital / risk_weighted_assets
tier1_ratio                 = Tier1_capital / RWA
total_capital_ratio         = (Tier1 + Tier2) / RWA
leverage_ratio              = Tier1_capital / total_leverage_exposure       [unweighted]
slr (supplementary leverage)= Tier1 / SLR_exposure                           [US GSIBs only]
cet1_buffer_vs_minimum      = cet1_ratio - regulatory_minimum_cet1
```

Minimum CET1 = 4.5% Pillar 1 + 2.5% conservation buffer + 0-2.5% counter-cyclical + 1-3.5% G-SIB surcharge. Helper looks up the GSIB tier per ticker from a maintained reference (`data/reference/gsib_tiers.yaml`); default Pillar 1 + conservation = 7.0%; add G-SIB surcharge per tier if applicable.

Buffer adequacy interpretation:
- buffer >= 300 bps → "comfortable"
- buffer 150-300 bps → "modest"
- buffer 0-150 bps → "tight"
- buffer < 0 → "below minimum — regulatory action expected"

**Credit quality:**
```
loan_loss_reserve_to_loans = allowance_for_loan_losses / total_loans         [reserve adequacy]
nco_rate_annualized         = net_charge_offs / average_loans                [annualized]
nonperforming_loans_pct     = NPL / total_loans                              [delinquency]
ldr (loan-to-deposit ratio) = total_loans / total_deposits                   [liquidity & growth lens]
coverage_ratio              = allowance / NPL                                [defense vs known bad loans]
loan_loss_provision_quarter = current-quarter LLP
loan_loss_provision_yoy_change_pct = LLP_t / LLP_{t-4} - 1
```

Credit-cycle classification (heuristic):
- NCO trending flat at low levels AND LLP yoy modest → "mid_cycle_normalizing" (current default for most US large banks)
- NCO rising materially AND LLP yoy > 50% → "early_deterioration"
- NCO peak AND reserves building rapidly → "stress"
- NCO falling AND reserves releasing → "recovery"

**Deposit dynamics:**
```
deposit_cost_pct = interest_expense_on_deposits / average_interest_bearing_deposits   [annualized]
deposit_beta     = Δdeposit_cost / Δfed_funds_rate    [over a defined hiking cycle, e.g. 2022-2024]
```

Deposit beta is calculated only when there's a clean hiking-cycle reference period; otherwise null with reason "insufficient rate-cycle data."

**Loan-loss provisioning (CECL / IFRS 9 lens):**
The helper distinguishes between specific-event provisions (a particular credit deteriorated) and macro-driven provisions (forecast adjustments). When both `current_quarter_provisions` and `macro_assumption_change_disclosed` are available in the Praams feed, the panel separates the two. Otherwise reports total provision only.

**Edge cases:**
- Insurance subsidiary of a bank holding company (e.g., MetLife's old structure): use the bank-only consolidated figures if disclosed; otherwise reject with a "mixed-business — use SOTP" verdict.
- Non-US bank with no Praams coverage: fallback path uses `eodhd_fundamentals` + bank field-mapping table. NIM and efficiency are computable; RWA / CET1 require regulatory disclosures and may be null with reason.
- Bank holding company with material non-bank operations (e.g., Goldman, Morgan Stanley with large IB/Trading): efficiency_ratio is still computable but the narrative should treat it as a "broker-dealer" lens rather than commercial-bank lens.

**Verifier hooks:**
- `block_shape`: profitability, capital_adequacy, credit_quality sub-objects all present.
- `block_cet1_below_minimum`: cet1_ratio < regulatory_minimum_cet1 surfaces as a structural warning, not blocking — but mandatory in narrative.
- `numeric_inconsistency`: NIM × avg earning assets = NII; RoTCE × TCE = NI.
- `temporal_ambiguous`: all KPIs must carry quarter-end date; "annualized" must be explicit when applicable.

**Skill doc (`skills/banks_sector_panel.md`):** required per schema-and-skills §6 #10. Covers regulatory-regime selection, when CET1 buffer is "comfortable" by GSIB tier, RoTCE-vs-ROE narrative discipline, credit-cycle phasing, why generic helpers (P/E, debt/equity, EV/EBITDA) misprice banks.

---

## 3. REITs sector module — `reit_valuation_panel`

**Purpose:** Compute the REIT-specific metrics that anchor REIT valuation: Funds From Operations (FFO), Adjusted FFO (AFFO), Net Asset Value (NAV), same-store NOI, implied cap rate, occupancy, debt to gross assets, payout from AFFO. Generic helpers fail on REITs — earnings include depreciation that is not economic, so P/E is meaningless; book value understates real-estate fair value, so P/B understates economic equity.

**Question answered:** What is this REIT worth in the metrics REIT investors actually use, and what is the implied cap rate at the current price?

**Report types:** Initiation (mandatory for any REIT or REOC), Update (post-quarterly), Sector (REIT cohort by property type).

**Inputs:**
- `ticker` (str, required)
- `as_of_date` (date, required)
- `gaap_net_income` (float, required)
- `real_estate_depreciation` (float, required): the largest single FFO adjustment
- `gains_on_real_estate_sales` (float, required): subtracted from NI in FFO derivation
- `impairment_charges` (float, optional, default `0.0`): added back
- `recurring_capex` (float, required): for AFFO; "recurring" excludes development capex
- `straight_line_rent_adjustment` (float, optional, default `0.0`): subtracted from FFO for AFFO
- `stock_based_comp` (float, optional, default `0.0`): treatment configurable — institutional convention adds back to AFFO; some methods do not
- `nareit_ffo_disclosed` (float, optional): use disclosed NAREIT FFO if available; otherwise compute
- `real_estate_at_fair_value` (float, optional): from third-party appraisal or analyst estimate; for NAV
- `real_estate_at_book` (float, required): from balance sheet
- `gross_real_estate_assets` (float, required): for cap rate denominator
- `same_store_noi_current_period` (float, required)
- `same_store_noi_prior_year_period` (float, required)
- `total_noi_annualized` (float, required): for cap rate
- `total_debt` (float, required)
- `preferred_equity` (float, optional, default `0.0`)
- `cash_and_equivalents` (float, required)
- `shares_outstanding_diluted` (float, required)
- `current_price` (float, required)
- `dividends_paid_ttm` (float, required)
- `property_type` (str, required): `"office" | "retail" | "industrial" | "residential" | "lodging" | "healthcare" | "data_center" | "self_storage" | "specialty" | "diversified"` — drives sector cap-rate norms

**Source:** EODHD fundamentals + supplemental REIT disclosures (REITs file 10-K Supplements with property-by-property NOI). Use `pdf_ingest` on the most recent supplemental when EODHD doesn't carry NAV inputs.

**Output:**
```json
{
  "ticker": "O",
  "as_of": "2026-03-31",
  "ffo": {
    "gaap_net_income": 380,
    "+ real_estate_depreciation": 540,
    "- gains_on_real_estate_sales": 25,
    "+ impairment_charges": 0,
    "ffo": 895,
    "ffo_per_share_diluted": 1.05,
    "nareit_ffo_disclosed": 895,
    "ffo_matches_disclosed": true
  },
  "affo": {
    "ffo": 895,
    "- recurring_capex": 65,
    "- straight_line_rent_adjustment": 18,
    "+ stock_based_comp": 6,
    "affo": 818,
    "affo_per_share_diluted": 0.96,
    "affo_payout_ratio": 0.812
  },
  "same_store_noi": {
    "current": 720,
    "prior_year": 695,
    "growth_pct": 0.036,
    "growth_trend_5y_pct": [0.028, 0.030, 0.029, 0.040, 0.036]
  },
  "occupancy": {
    "current_pct": 0.988,
    "trend_4q_pct": [0.985, 0.987, 0.989, 0.988]
  },
  "nav": {
    "implied_cap_rate_at_current_price_pct": 0.0560,
    "applied_cap_rate_pct": 0.055,
    "applied_cap_rate_source": "property-type-weighted CBRE survey 2026Q1",
    "implied_real_estate_value": 13090,
    "+ cash_and_equivalents": 285,
    "- total_debt": 5800,
    "- preferred_equity": 0,
    "nav_equity": 7575,
    "shares_outstanding_diluted": 855,
    "nav_per_share": 8.86,
    "current_price_per_share": 8.45,
    "price_to_nav_pct": -0.046
  },
  "leverage": {
    "debt_to_gross_assets_pct": 0.385,
    "debt_to_ebitda": 5.2,
    "secured_debt_pct_of_total_debt": 0.18,
    "wam_years_debt": 6.5
  },
  "narrative": "Realty Income Q1: FFO/share $1.05 (in line); AFFO/share $0.96 with 81% payout (sustainable for triple-net retail). Same-store NOI +3.6% YoY, in line with 5-yr trend. NAV ~$8.86/share at applied 5.5% cap (CBRE retail survey) vs $8.45 current = ~5% discount to NAV.",
  "warnings": [],
  "data_as_of": "2026-03-31"
}
```

**Methodology:**

**FFO (NAREIT definition):**
```
FFO = GAAP_NI
    + real_estate_depreciation_and_amortization
    - gains_on_real_estate_sales
    + impairment_charges
    (- gains on debt extinguishment if material — institutional refinement)
```

**AFFO (no industry-standard formula; helper documents which adjustments applied):**
```
AFFO = FFO
     - recurring_capex                       [maintaining the asset; growth capex not deducted]
     - straight_line_rent_adjustment         [back out non-cash rent smoothing]
     + stock_based_comp                      [add back — non-cash; configurable per output flag]
     (- amortization of lease incentives — refinement)
```

Output records which adjustments were applied so the AFFO line is auditable. Some analysts treat SBC as a real expense (do not add back); institutional default here is to add back.

**Per-share variants:**
```
ffo_per_share_diluted  = ffo / shares_outstanding_diluted
affo_per_share_diluted = affo / shares_outstanding_diluted
affo_payout_ratio      = dividends_paid_ttm / affo_ttm                       [most common payout lens for REITs]
```

Payout interpretation:
- AFFO payout < 0.75: cushion to grow dividend
- 0.75-0.95: tight; growth limited
- > 0.95: at risk; common before a cut

**Same-store NOI growth:**
```
same_store_noi_growth = current_period / prior_year_same_period - 1
```
"Same-store" means properties owned for the full comparison period (so growth isn't inflated by acquisitions). REITs disclose this directly in supplements; the helper consumes the disclosure rather than recomputing.

**Occupancy:** also disclosed directly; the helper provides trend formatting.

**Cap rate and NAV:**

```
implied_cap_rate_at_price = total_NOI_annualized / (market_cap + net_debt + preferred)
                          = total_NOI_annualized / current_EV
```

Applied cap rate (for NAV):
```
applied_cap_rate = property-type-weighted survey median (CBRE / JLL / Green Street)
implied_real_estate_value = total_NOI_annualized / applied_cap_rate
nav_equity = implied_real_estate_value + cash + other_assets_at_fv - total_debt - preferred
nav_per_share = nav_equity / shares_outstanding_diluted
price_to_nav_pct = current_price / nav_per_share - 1
```

Cap-rate source: maintain reference snapshot at `data/reference/reit_cap_rates/cbre_survey_<period>.yaml` with property-type cells. Refresh quarterly. License: CBRE survey is published quarterly; verify attribution requirements before commit.

For multi-property-type REITs: weighted by NOI mix. The panel computes the weights from the REIT's disclosed segment NOI when available.

**Leverage:**
```
debt_to_gross_assets = total_debt / gross_real_estate_assets        [REIT-specific lens; D/E meaningless]
debt_to_ebitda       = total_debt / EBITDA                          [generic cross-check]
secured_debt_pct     = secured_mortgage_debt / total_debt           [structural quality]
wam_years_debt       = weighted-average maturity from debt-maturity-ladder helper (§12 of supplement)
```

Debt-to-gross-assets below 40% is conservative for most property types; above 55% is aggressive. Lodging and specialty often run higher; net-lease retail often lower.

**Edge cases:**
- REOC (real estate operating company, e.g., Brookfield BPY): same metrics apply but report as REOC; NAV is the dominant lens because depreciation accounting is even further from economic reality.
- Externally-managed REIT (advisor fees paid to a sponsor): adjust AFFO for management-fee structure; flag in narrative — externally-managed REITs often trade at NAV discount due to fee leakage.
- Newly-IPO'd REIT (< 4 quarters): same-store NOI undefined; report only FFO/AFFO + occupancy + NAV with a "limited history" caveat.
- Hospitality / lodging REITs: same-store NOI is highly seasonal; the helper requires 4 trailing quarters minimum and reports same-store on a trailing-12 basis rather than YoY single quarter.
- Mortgage REIT (mREIT): refuse — mREITs are not real-estate equity REITs; they're rate-sensitive financial intermediaries with their own metric stack. Recommend `banks_sector_panel` as the closest analog or refuse with a clear error.

**Verifier hooks:**
- `block_shape`: ffo, affo, same_store_noi, nav sub-objects all present.
- `block_ffo_disclosure_mismatch`: when `nareit_ffo_disclosed` is provided and our computed FFO differs > 2%, raise a warning issue.
- `block_payout_high`: `affo_payout_ratio > 0.95` surfaces as a dividend-safety advisory issue.
- `numeric_inconsistency`: FFO formula reconciles from inputs; NAV bridge reconciles.
- `temporal_ambiguous`: all KPIs carry quarter-end date; "trailing" metrics carry explicit window.

**Skill doc (`skills/reit_valuation_panel.md`):** required per schema-and-skills §6 #11. Covers FFO/AFFO adjustment policy (what to add back, what not), NAV cap-rate sourcing, why P/E is meaningless for REITs, externally-managed REIT discount norm, mREIT exclusion.

---

## 4. Pharma / biotech sector module — `rnpv_pipeline` + supporting helpers

**Purpose:** Compute risk-adjusted net present value (rNPV) of a pharmaceutical / biotech pipeline. Each clinical-stage asset has a probability of success (PoS) by stage and a peak-sales potential at launch; the helper aggregates per-asset rNPV across the pipeline, sums to enterprise value, and bridges to per-share value.

**Question answered:** What is this pharma's pipeline worth, asset-by-asset, after risk-adjustment for clinical attrition?

**Report types:** Initiation (mandatory for any name with >25% of value in pipeline), Update (post-trial readout), Sector (cross-company asset benchmarking).

**Inputs:**
- `assets` (list[dict], required): each asset is:
  ```
  {
    "name": "BCMA-CAR-T",
    "indication": "Multiple Myeloma 4L+",
    "stage": "phase_2",
    "modality": "cell_therapy",
    "stage_pos_override": null,             # default uses Citeline 2024 by-stage-by-modality
    "peak_sales_year": 2031,
    "peak_sales_value": 1800,
    "launch_year": 2028,
    "ramp_curve": "standard",               # "standard" (3-year ramp to peak), "fast" (1y), "slow" (5y)
    "patent_expiry_year": 2042,
    "post_loe_decay": 0.65,                 # erosion to 35% of peak in first generics year
    "royalty_burden_pct": 0.05,              # royalty-out to partners; reduces our revenue
    "gross_margin": 0.85,
    "rd_remaining_to_launch": 850,          # cumulative R&D spend through launch
    "milestone_payments_received": 200,     # cash from collaborators upon stage progression
    "ownership_pct": 1.00                    # for co-developed assets
  }
  ```
- `cost_of_capital` (float, required): typically 11-13% for development-stage biotech; lower for diversified pharma
- `cash_and_equivalents` (float, required)
- `total_debt` (float, required)
- `shares_outstanding_diluted` (float, required)
- `commercial_assets_value` (float, optional, default `0.0`): NPV of already-marketed products (computed via DCF separately and supplied here)
- `terminal_year` (int, optional, default `2045`): end of cash flows beyond which residual is zero
- `pos_table_source` (str, optional, default `"citeline_2024"`): source for stage-by-stage PoS

**Source:** PoS table from `data/reference/citeline/stage_pos_2024.yaml`. Asset-level inputs from analyst entry (most pharma helpers require analyst-provided peak sales and launch dates); supplement with SEC filings via `pdf_ingest` for stage transitions and patent expiries.

**PoS table (Citeline 2024 by stage; modality refinement in skill doc):**
```yaml
preclinical:        0.066     # 6.6% probability of eventual approval
phase_1:            0.107
phase_2:            0.227
phase_3:            0.553
nda_bla:            0.851
approved:           1.000
```

**Output:**
```json
{
  "pipeline_assets": [
    {
      "name": "BCMA-CAR-T",
      "stage": "phase_2",
      "stage_pos": 0.227,
      "peak_sales": 1800,
      "risk_adjusted_revenue_npv": 612,
      "risk_adjusted_ebit_npv": 425,
      "rd_npv_deduction": 720,
      "milestones_received_npv": 175,
      "rnpv_contribution": -120,
      "interpretation": "negative rNPV — Phase 2 PoS (22.7%) does not yet support remaining $850M R&D burden; risk skewed to readout"
    },
    {
      "name": "Asset_2",
      "stage": "phase_3",
      "stage_pos": 0.553,
      "rnpv_contribution": 1850
    }
  ],
  "pipeline_rnpv": 3450,
  "commercial_assets_value": 6800,
  "total_enterprise_value": 10250,
  "net_cash_or_debt": 850,
  "equity_value": 11100,
  "shares_outstanding_diluted": 145,
  "value_per_share": 76.55,
  "current_price": 62.30,
  "implied_upside_pct": 0.229,
  "value_concentration": {
    "top_asset_pct_of_rnpv": 0.54,
    "top_3_assets_pct_of_rnpv": 0.92,
    "binary_event_risk": "high — 54% of pipeline value in single Phase 3 readout"
  },
  "pos_table_used": "citeline_2024",
  "narrative": "rNPV: pipeline $3.45B + commercial $6.8B = $10.25B EV; + $850M net cash = $11.1B equity = $77/share, +23% vs $62 current. Concentration is high: 54% of pipeline value in BCMA-CAR-T Phase 3 readout — sized as a high-conviction binary.",
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Per-asset rNPV:**

Step 1 — Build revenue stream from launch:
```
revenue_year_t = ramp_multiplier(t - launch_year) * peak_sales * (1 - royalty_burden_pct) * ownership_pct

ramp_multiplier(years_since_launch):
  standard: [0.10, 0.40, 0.80, 1.00, 1.00, ...]    # 3-year ramp
  fast:     [0.65, 1.00, 1.00, ...]
  slow:     [0.05, 0.15, 0.35, 0.65, 0.90, 1.00, ...]
```

Step 2 — Apply post-LoE decay:
```
for years >= patent_expiry_year:
  revenue_year_t = peak_sales * post_loe_decay * decay_curve(years_past_loe)
  decay_curve: 1.0 in year 1, 0.50 in year 2, 0.30 in year 3, 0.20 in year 4, 0.15 thereafter
```

Step 3 — Convert revenue to EBIT:
```
ebit_year_t = revenue_year_t * gross_margin - estimated_post_launch_opex
```
For initial implementations, approximate post-launch opex as 35% of peak revenue throughout the commercial period; the helper exposes `post_launch_opex_pct_of_peak` as a configurable input.

Step 4 — Tax-effect:
```
nopat_year_t = ebit_year_t * (1 - effective_tax_rate)
```

Step 5 — Discount each year-t cash flow to present:
```
pv_revenue_t = nopat_year_t / (1 + cost_of_capital)^(t - current_year)
```

Step 6 — Risk-adjust:
```
risk_adjusted_revenue_npv = stage_pos * sum_t(pv_revenue_t)
```

Step 7 — Subtract remaining R&D, risk-adjusted:
```
rd_npv_deduction = pv(rd_remaining_to_launch)        # discounted at COC over expected years to launch
                  # NOT risk-adjusted — the spend happens whether the asset succeeds or fails
```

Step 8 — Add milestone receipts:
```
milestones_received_npv = pv(milestone_payments_received)    # if upfront / already-received, no discount
```

Step 9 — Per-asset rNPV:
```
rnpv_contribution = risk_adjusted_revenue_npv + milestones_received_npv - rd_npv_deduction
```

A negative rNPV is informative — it tells the user that the current stage's PoS does not yet justify the remaining R&D spend. That's normal for Phase 2 assets pre-data; the value comes from the option (Phase 3 PoS jumps to 55%).

**Pipeline-level aggregation:**
```
pipeline_rnpv = sum_assets(rnpv_contribution)
total_ev      = pipeline_rnpv + commercial_assets_value
equity_value  = total_ev + net_cash - total_debt
value_per_share = equity_value / shares_outstanding_diluted
```

**Value concentration metrics:** sort assets by `|rnpv_contribution|` descending; report top-1 and top-3 share of total pipeline rNPV. Concentration > 50% in a single binary event → "high binary risk" narrative.

**Royalty stack analysis (`royalty_stack_analyzer` sub-helper):**

For assets with complex royalty obligations (in-licenses paid out + out-licenses received), build:
```
royalty_obligations_out (paid to others):  list of {asset, royalty_pct, tiers, threshold}
royalty_streams_in (received from others): same
net_royalty_drag_per_asset: gross sales - royalties out + royalties in
```
Most published peak-sales figures are gross; the helper applies royalty stacks to derive net-to-company revenue.

**Edge cases:**
- Preclinical assets (PoS ~6.6%): rNPV is almost always negative; helper reports but excludes from any "value-driver" narrative.
- Approved drug with declining sales (mature on-market): not a pipeline asset; should be in `commercial_assets_value` as a DCF, not run through rNPV.
- Biosimilar / generic competition modeling: post_loe_decay curve is configurable per asset; biologics typically retain 60-70% in first year of biosim entry vs 30% for small-molecule generics.
- Single-asset biotech (no commercial): rNPV is the entire equity value; per-share is fully exposed to that asset's outcome — narrative must say so explicitly.
- Royalty-pharma model (e.g., Royalty Pharma): not pipeline rNPV; use a stream-DCF instead. The helper refuses with a "royalty-pharma — use stream_dcf" message.

**Verifier hooks:**
- `block_shape`: per-asset rnpv_contribution computed; pipeline_rnpv = sum.
- `block_pos_outside_range`: PoS values outside [0, 1] rejected.
- `block_stage_not_in_table`: asset stage not in PoS table → reject with "stage not in pos_table_source" message.
- `numeric_inconsistency`: pipeline rNPV = sum of per-asset; equity bridge reconciles.
- `concentration_warning`: `top_asset_pct_of_rnpv > 0.50` surfaces in narrative.
- `temporal_ambiguous`: every peak_sales, launch_year, patent_expiry_year explicit in output.

**Skill doc (`skills/rnpv_pipeline.md`):** required per schema-and-skills §6 #9. Covers PoS table selection by modality (Citeline 2024 base table is for small molecule; cell/gene therapy and oncology have meaningfully different rates), ramp curve selection by asset class, when to refuse (royalty-pharma, single-product mature with no pipeline → use plain DCF), narrative discipline (binary risk language, never overstate Phase 2 readouts).

---

## 5. Energy / E&P sector module — `ep_sector_panel`

**Purpose:** Compute exploration-and-production (E&P) sector metrics: EBITDAX, discretionary cash flow (DACF), netback per BOE, all-in sustaining cost (AISC) where applicable, reserves replacement ratio, finding & development cost, recycle ratio, decline curves. Generic helpers fail on E&P — depreciation is non-cash but commodity revenue is volatile so EBITDA understates real cyclicality; book value of reserves is not fair value; debt/EBITDA reads catastrophically at oil-price troughs and looks fine at peaks.

**Question answered:** What are this E&P's per-barrel economics, capital efficiency, reserves life, and through-cycle profitability?

**Report types:** Initiation (mandatory for any oil/gas E&P), Update (post-quarterly + commodity-price moves), Sector (cross-basin / cross-company cohort).

**Inputs:**
- `ticker` (str, required)
- `as_of_date` (date, required)
- `production_boe_per_day` (float, required): total daily production, energy-equivalent barrels
- `production_oil_pct` (float, required): oil share of total BOE (drives revenue mix vs gas)
- `production_gas_pct` (float, required)
- `production_ngl_pct` (float, optional, default `0.0`)
- `revenue` (float, required)
- `royalties_and_production_taxes` (float, required)
- `operating_costs` (float, required): "lifting costs" — labor, power, water, well services
- `gathering_processing_transport` (float, required)
- `cash_g_and_a` (float, required)
- `interest_expense` (float, required)
- `da_excluding_dd_a_on_oil_gas` (float, optional, default `0.0`): non-oil-gas D&A
- `dd_a_on_oil_gas_properties` (float, required): the largest E&P expense
- `exploration_expense` (float, required): for EBITDAX add-back
- `cash_taxes` (float, required)
- `capex_maintenance` (float, required): "maintenance" = capex required to hold production flat
- `capex_growth` (float, required)
- `proved_reserves_boe` (float, required): total 1P
- `proved_developed_reserves_boe` (float, optional)
- `reserves_added_organic_boe` (float, required): from extensions, discoveries, revisions
- `reserves_added_acquisitions_boe` (float, optional, default `0.0`)
- `reserves_added_revisions_boe` (float, required): can be negative
- `commodity_price_realizations` (dict, required): {wti_avg, brent_avg, henry_hub_avg, realized_oil, realized_gas, realized_ngl}
- `commodity_price_assumptions_forward` (dict, optional): for forward-cycle modeling

**Source:** EODHD fundamentals + 10-K reserves disclosures via `pdf_ingest` (proved reserves and reserve-life are not in standard fundamentals feeds).

**Output:**
```json
{
  "ticker": "XOM",
  "as_of": "2026-03-31",
  "production": {
    "boe_per_day": 4280,
    "oil_pct": 0.62,
    "gas_pct": 0.30,
    "ngl_pct": 0.08,
    "yoy_growth_pct": 0.032
  },
  "per_unit_economics": {
    "realized_price_per_boe": 64.50,
    "royalties_per_boe": 8.20,
    "lifting_costs_per_boe": 9.80,
    "gathering_processing_per_boe": 3.50,
    "g_and_a_per_boe": 2.10,
    "netback_per_boe": 40.90,
    "ebitdax_margin_pct": 0.634
  },
  "cash_flow": {
    "revenue": 32500,
    "royalties_and_production_taxes": 4120,
    "operating_costs": 4940,
    "gathering_processing_transport": 1764,
    "cash_g_and_a": 1058,
    "interest_expense": 380,
    "ebitdax": 20618,
    "exploration_expense": 580,
    "ebitda": 20038,
    "ebit": 8158,
    "dacf": 19638
  },
  "capital_efficiency": {
    "capex_maintenance": 6800,
    "capex_growth": 3200,
    "fcf_maintenance": 12838,
    "fcf_total": 9638,
    "reinvestment_rate_pct": 0.485,
    "fd_cost_per_boe": 12.50,
    "recycle_ratio": 3.27
  },
  "reserves": {
    "proved_reserves_boe": 18200,
    "proved_developed_pct": 0.71,
    "reserves_added_organic": 1810,
    "reserves_added_acquisitions": 0,
    "reserves_added_revisions": -120,
    "reserve_life_index_years": 11.65,
    "reserves_replacement_ratio_pct": 1.085,
    "organic_rrr_pct": 1.090
  },
  "balance_sheet": {
    "net_debt": 8500,
    "net_debt_to_ebitdax": 0.41,
    "net_debt_to_dacf": 0.43
  },
  "scenario_economics": {
    "current_oil_price": 78,
    "breakeven_oil_price": 41,
    "fcf_at_60": 6200,
    "fcf_at_80": 11200,
    "fcf_at_100": 16500
  },
  "narrative": "XOM Q1: 4.3 MBOE/d production, 62% oil; netback $41/BOE; DACF $19.6B; capex $10B (68% maintenance); recycle ratio 3.3x at $12.50/BOE F&D — top-decile capital efficiency. 1.08x organic RRR with 11.7-year reserve life. Net debt 0.41× EBITDAX — well-capitalized through cycle.",
  "warnings": [],
  "data_as_of": "2026-03-31"
}
```

**Methodology:**

**Per-unit economics (most important block; the institutional E&P lens):**
```
realized_price_per_boe = (oil_realized * oil_volume + gas_realized * gas_volume_in_boe + ngl_realized * ngl_volume) / total_boe
                       = revenue / total_boe        [identity check]

royalties_per_boe       = royalties_and_production_taxes / total_boe_produced
lifting_costs_per_boe   = operating_costs / total_boe_produced
gathering_per_boe       = gathering_processing_transport / total_boe_produced
g_and_a_per_boe         = cash_g_and_a / total_boe_produced

netback_per_boe         = realized_price - royalties - lifting - gathering - g_and_a
                        [this is the cash margin per barrel; the headline number for E&P quality]
```

Netback by basin / asset is the most-cited E&P metric. For multi-basin operators, the helper accepts an optional `production_by_basin` input and emits per-basin netbacks; otherwise reports consolidated.

**EBITDAX (the E&P-specific EBITDA variant):**
```
EBITDAX = EBIT + DD&A_oil_and_gas + non_oil_gas_D&A + exploration_expense
        = revenue
        - royalties_and_production_taxes
        - operating_costs
        - gathering_processing_transport
        - cash_g_and_a
        (- exploration expense added back via the X term)
```

EBITDAX adds back exploration because exploration is treated like capex by most institutional analysts — it's spending to find reserves, not a current-period operating cost. The metric is convention; non-E&P names should not use it.

**DACF (discretionary cash flow):**
```
DACF = EBITDAX - cash_interest - cash_taxes
     = the cash available to fund capex + dividends + buybacks + balance sheet
```

DACF / share is preferred over EPS for E&P given non-cash DD&A volatility.

**Reinvestment rate:**
```
reinvestment_rate = (capex_maintenance + capex_growth) / DACF
```
Below 50%: returning cash to shareholders; 50-90%: balanced; above 90%: re-investing for growth; above 100%: outspending — financed by balance sheet or hedging.

**Reserves replacement and reserve life:**
```
total_reserves_added = organic_added + acquisitions_added + revisions
reserves_replacement_ratio = total_reserves_added / annual_production
organic_rrr                = (organic_added + revisions) / annual_production    [excludes M&A]
reserve_life_index         = proved_reserves / annual_production               [years]
```

Institutional standard: organic RRR > 100% means the company is replacing what it produces from drilling, not just buying reserves. Reserve life 10-15 years is typical for shale; 20+ for conventional onshore; lower (8-10) for unconventional gas.

**Finding & development cost (F&D):**
```
fd_cost_per_boe = (capex_growth + acquisitions_capex - proceeds_from_dispositions)
                  / (organic_reserves_added + acquisitions_reserves_added)
```
Best-in-class F&D is < $10/BOE for premier shale operators; > $20/BOE indicates capital-inefficient drilling.

**Recycle ratio:**
```
recycle_ratio = netback_per_boe / fd_cost_per_boe
```
> 2.5x: top-decile; 1.5-2.5x: healthy; < 1.5x: capital-destructive at current prices.

**All-in sustaining cost (AISC):**

AISC is a *mining* convention (World Gold Council 2013, refined 2018) widely applied to gold/silver/copper producers; less applied to oil/gas. When `commodity_class == "metals"` (configurable input), helper emits AISC instead of netback:
```
AISC = cash_operating_costs + royalties + by-product_credits + capex_maintenance + sustaining_overhead - by-product_revenue
     (per ounce / pound, depending on metal)
```
Detailed AISC formula source: World Gold Council Guidance Note pinned in skill doc.

**Scenario economics (commodity sensitivity):**
```
For each scenario oil_price in {current, 60, 80, 100, 120}:
   reprice oil revenue based on scenario_price
   recompute EBITDAX, FCF
   report sensitivity at current cost structure
```

Breakeven oil price: solve for `oil_price_breakeven` such that `FCF_maintenance = 0`.

**Leverage lens (cycle-aware):**
```
net_debt_to_ebitdax = net_debt / ebitdax_ttm
net_debt_to_dacf    = net_debt / dacf_ttm
```
Below 1x: well-capitalized through cycle; 1-2x: typical mid-cycle; > 2.5x: stressed at downturn prices; > 4x: distressed.

**Edge cases:**
- Integrated oil major (XOM, CVX, BP, Shell): the E&P panel is the upstream-segment lens only; the helper accepts a `segment_filter` input to restrict to upstream. Downstream / chemicals / renewables have their own DCF.
- Pure-gas producer: netback $/MCF is reported instead of $/BOE (gas is 1/6 of an oil-energy barrel; the helper converts both ways and labels clearly).
- Royalty / streaming companies (Franco-Nevada, Royal Gold): refuse — no production costs, no reserves replacement; use stream-DCF.
- LNG export terminals (Cheniere, Tellurian): refuse for the E&P side — they're infrastructure plays; reference `infrastructure_panel` (out-of-scope Wave 2).
- Heavy oil / oil-sands (Cenovus, Suncor): netbacks have a wider spread (Western Canadian Select vs WTI differential); helper requires `realized_oil` to be the actual realized differential-adjusted price.

**Verifier hooks:**
- `block_shape`: per_unit_economics, cash_flow, reserves, balance_sheet, scenario_economics all present.
- `block_negative_netback`: netback < 0 with `current_oil_price > 60` triggers warning issue (suggests a structural cost problem or a one-off).
- `block_rrr_below_one`: organic RRR < 1.0 for multiple years → flag as "production decline" in narrative.
- `numeric_inconsistency`: per-unit metrics × total BOE = aggregate cash flow line items.
- `temporal_ambiguous`: every per-unit metric labeled with the realization period.

**Skill doc (`skills/ep_sector_panel.md`):** required per schema-and-skills §6 #12. Covers EBITDAX-not-EBITDA convention, AISC for metals only, basin-specific netback norms (Permian vs Bakken vs Marcellus), integrated-major segment filtering, recycle-ratio interpretation, when to switch to DCF (steady-state names like Royal Dutch Shell post-portfolio-pivot).

---

## 6. Insurance sector module — `insurance_valuation_panel`

**Purpose:** Compute insurance-specific metrics that are required to evaluate P&C and Life insurers: combined ratio (P&C), embedded value (Life), book value per share with stat-vs-GAAP reconciliation, premium growth, expense ratio, loss ratio, investment yield, reserve adequacy, catastrophe reinsurance attachment. Generic helpers fail on insurance — P/E ignores reserve adequacy and investment-portfolio mark-to-market; D/E is structurally misleading (insurance liabilities are not debt); book value misstates economic equity in both directions.

**Question answered:** What are this insurer's underwriting profitability, capital adequacy, and economic earnings, in the metrics insurance investors actually use — and does the answer differ for P&C and Life?

**Report types:** Initiation (mandatory for any insurance name), Update (post-quarter + post-cat event), Sector (cross-insurer cohort).

**Inputs:**
- `ticker` (str, required)
- `as_of_date` (date, required)
- `insurance_segment_mix` (str, required): `"pc"` | `"life"` | `"both"` (panel runs both sub-blocks for "both")
- For P&C:
  - `premiums_written` (float, required)
  - `premiums_earned` (float, required)
  - `losses_and_lae` (float, required): losses and loss adjustment expense
  - `underwriting_expenses` (float, required)
  - `policyholder_dividends` (float, optional, default `0.0`)
  - `prior_year_reserve_development` (float, optional, default `0.0`): negative = favorable
  - `catastrophe_losses_disclosed` (float, optional)
  - `reinsurance_recoverable` (float, optional)
- For Life:
  - `gross_premiums` (float, required)
  - `net_premiums` (float, required)
  - `benefits_and_claims_paid` (float, required)
  - `change_in_reserves` (float, required)
  - `embedded_value_disclosed` (float, optional): some Life insurers disclose EV directly (EU IFRS 17 names)
  - `vif_disclosed` (float, optional): value of in-force business
  - `new_business_value_disclosed` (float, optional): VNB
  - `apv_assumptions` (dict, optional): override discount / lapse / mortality assumptions for EV
- Common:
  - `invested_assets` (float, required)
  - `investment_income` (float, required)
  - `net_realized_gains_losses` (float, optional, default `0.0`)
  - `book_value_equity_gaap` (float, required)
  - `book_value_equity_stat` (float, optional): statutory accounting; for US insurers
  - `intangibles_and_goodwill` (float, required)
  - `accumulated_oci` (float, optional): for unrealized investment gain/loss
  - `shares_outstanding_diluted` (float, required)
  - `current_price` (float, required)

**Source:** `eodhd_fundamentals`; insurance-specific lines from supplemental statutory filings via `pdf_ingest` (statutory data is filed quarterly with state regulators but not always in fundamental feeds).

**Output:**
```json
{
  "ticker": "CB",
  "segment_mix": "pc",
  "as_of": "2026-03-31",
  "pc": {
    "premiums_written": 12800,
    "premiums_earned": 12300,
    "premium_growth_yoy_pct": 0.072,
    "loss_ratio_pct": 0.605,
    "expense_ratio_pct": 0.275,
    "combined_ratio_pct": 0.880,
    "combined_ratio_ex_cat_pct": 0.842,
    "prior_year_development": -120,
    "underwriting_profit": 1476,
    "catastrophe_load_pct": 0.038,
    "reinsurance_dependence": "low — ~7% net premiums ceded"
  },
  "life": null,
  "investment_portfolio": {
    "invested_assets": 145000,
    "investment_income": 3800,
    "investment_yield_pct": 0.0262,
    "net_realized_gains_losses": 85,
    "duration_years": 5.4,
    "duration_gap_disclosed_years": -0.6
  },
  "balance_sheet": {
    "book_value_equity_gaap": 28500,
    "book_value_equity_stat": null,
    "tangible_book_value": 24200,
    "accumulated_oci": -1200,
    "shares_outstanding_diluted": 412,
    "book_value_per_share_gaap": 69.17,
    "tangible_book_value_per_share": 58.74,
    "price_to_book_gaap_pct": 1.55,
    "price_to_tangible_book_pct": 1.83
  },
  "capital_adequacy": {
    "bcar_disclosed": "A.M. Best 'Strongest'",
    "rbc_ratio_disclosed_pct": null,
    "solvency_ii_scr_ratio_pct": null
  },
  "narrative": "Chubb Q1: combined 88.0% (ex-cat 84.2%); $14.8B premiums written +7.2% YoY; favorable PY development $120M. Investment yield 2.62% on $145B float. BVPS GAAP $69, P/BV 1.55x; tangible BVPS $59, P/TBV 1.83x. A.M. Best Strongest capital.",
  "warnings": [],
  "data_as_of": "2026-03-31"
}
```

**Methodology:**

**P&C combined ratio (the institutional anchor):**
```
loss_ratio        = (losses_and_lae - prior_year_reserve_development) / premiums_earned
expense_ratio     = underwriting_expenses / premiums_earned                          [some methods use premiums_written]
policyholder_dividend_ratio = policyholder_dividends / premiums_earned
combined_ratio    = loss_ratio + expense_ratio + policyholder_dividend_ratio
combined_ratio_ex_cat = combined_ratio - (catastrophe_losses / premiums_earned)
underwriting_profit = premiums_earned * (1 - combined_ratio)
```

Combined ratio interpretation:
- < 90%: excellent underwriting (rare; mostly specialty insurers)
- 90-100%: profitable underwriting
- 100-105%: marginal — relying on investment income for overall profitability
- > 105%: structural underwriting loss
- > 110%: distressed underwriting cycle

Catastrophe load is the cat losses share of premiums; isolating ex-cat combined separates underlying underwriting discipline from cyclical event severity.

**Prior-year reserve development:**

PY development (negative = favorable, positive = adverse) is the most important "underlying" signal. The helper reports raw + as % of premiums earned. Multi-year adverse development is a tombstone-grade red flag (the insurer was under-reserving) and a verifier hook surfaces it.

**Investment yield:**
```
investment_yield = investment_income / average_invested_assets   [annualized; book yield, not market yield]
```

Book yield is the annual income on the portfolio at amortized cost; market yield (yield-to-maturity at current market prices) is often higher in a rising-rate environment and informs forward investment income, but is conventionally not reported in headline KPI tables.

**Embedded value (Life — IFRS 17 convergence):**

For Life insurers, the most important valuation lens is embedded value (EV), defined as:
```
EV = Adjusted_Net_Worth + Value_of_In-Force_Business (VIF)
   = (statutory_capital - required_capital + adjustments) + PV_of_future_distributable_profits_from_existing_policies
```

When `embedded_value_disclosed` is provided, the helper uses it directly. When `apv_assumptions` are supplied, the helper recomputes VIF (this is a complex actuarial calculation; the helper's recompute mode is documented as approximate and recommends consuming disclosed EV when available).

**New business value (VNB):**
```
VNB = PV of distributable profits from policies sold in the period - acquisition_costs
```
VNB / new_business_premiums = "new business margin" — analogous to underwriting margin for P&C.

**Book value / tangible book value:**
```
book_value_equity_gaap = total_equity_per_balance_sheet
tangible_book_value    = book_value_equity_gaap - intangibles_and_goodwill
book_value_per_share   = book_value_equity_gaap / shares_outstanding_diluted
tangible_book_per_share = tangible_book_value / shares_outstanding_diluted
price_to_book          = current_price / book_value_per_share
```

P/TBV is the dominant institutional multiple for P&C (large insurers trade in a 1.2-2.5× P/TBV band depending on combined ratio and growth). P/EV is dominant for Life.

**Capital adequacy:**

Insurance capital ratios are regulator-specific:
- US P&C: NAIC RBC ratio (Risk-Based Capital) — 200%+ is healthy; below 200% triggers regulatory action
- US Life: similar RBC framework with different factors
- EU: Solvency II SCR coverage — 150%+ healthy; below 100% breach
- Bermuda: BSCR
- A.M. Best: BCAR rating "Strongest" / "Strong" / "Adequate" — common rating-agency proxy

The helper consumes disclosed metrics; if multiple are disclosed (e.g., a global insurer with NAIC + Solvency II), surfaces all in the output. Where none disclosed, reports the rating-agency capital category if available.

**Edge cases:**
- Specialty insurer with concentration risk (catastrophe reinsurance, terrorism, cyber): combined ratio can swing 30+ points in cat years; the helper reports trailing 5-year average combined alongside current.
- Mutual insurer (no equity): refuse — no per-share metrics; equity holders don't exist.
- Reinsurance company: same metrics apply but with "ceded" reversed; the helper accepts `entity_type="reinsurer"` and inverts ceded/assumed conventions.
- Life insurer with no EV disclosure (US GAAP names): VNB can be approximated from premiums × disclosed new-business margin if disclosed; otherwise embedded_value field returns null with reason.
- Multi-line composite (Chubb, Allianz): runs both P&C and Life sub-blocks; net values flow into a combined valuation summary.

**Verifier hooks:**
- `block_shape`: For P&C: pc sub-object present with combined_ratio. For Life: life sub-object present with embedded_value or VIF.
- `block_combined_ratio_extreme`: combined_ratio > 1.15 surfaces as a structural warning, mandatory narrative discussion.
- `block_adverse_py_development_pattern`: prior-year development positive AND consistent over multiple periods → tombstone-grade warning about reserve adequacy.
- `numeric_inconsistency`: combined ratio = loss + expense + dividend ratios; book value bridge reconciles.
- `block_negative_book_value`: GAAP equity negative → refuse to compute per-share metrics; surface as structural impairment.

**Skill doc (`skills/insurance_valuation_panel.md`):** required per schema-and-skills §6 #13. Covers P&C vs Life metric differences, why P/TBV is the P&C anchor and P/EV the Life anchor, prior-year-development interpretation (favorable vs adverse signaling), capital-adequacy regime selection, combined-ratio ex-cat convention, refusing on mutual / non-equity structures.

---

## 7. Sector planner integration

Each sector module registers a `Stage 5 planner heuristic` that auto-includes the panel when the ticker's primary GICS code matches:

```yaml
# data/reference/sector_routing.yaml
banks:
  category: sector_banks
  panel: banks_sector_panel
  trigger_gics_prefixes: ["4010", "4015", "4020"]    # Banks, Diversified Financials, Insurance excluded
  template: stock_initiation_banks_v2
reits:
  category: sector_reits
  panel: reit_valuation_panel
  trigger_gics_prefixes: ["6010"]                     # Real Estate
  template: stock_initiation_reits_v2
pharma:
  category: sector_pharma
  panel: rnpv_pipeline
  trigger_gics_prefixes: ["3520"]                     # Pharma, biotech, life sciences tools
  template: stock_initiation_pharma_v2
  conditional: "pipeline_pct_of_value > 0.25"        # only when pipeline-driven, not pure commercial
ep:
  category: sector_energy
  panel: ep_sector_panel
  trigger_gics_prefixes: ["1010"]                     # Energy
  template: stock_initiation_ep_v2
insurance:
  category: sector_insurance
  panel: insurance_valuation_panel
  trigger_gics_prefixes: ["4030"]                     # Insurance
  template: stock_initiation_insurance_v2
```

The planner consults this table during Stage 5 and adds the sector panel + sector template to the run plan automatically. User can override with explicit "skip sector module" instruction.

---

## 8. Cross-sector contract requirements

Every Wave-1 sector panel must:

1. **Register with sector-specific Category** (e.g., `sector_banks`) — closed-set enforced by schema-and-skills §3.1.
2. **Produce a single primary artifact** (`banks_sector_panel`, `reit_valuation_panel`, etc.) registered in `artifact_types.yaml` with its Pydantic shape.
3. **Implement RenderableArtifact.to_markdown(level)** at HEADLINE / SUMMARY / FULL fidelities per artifact-injection §2. Hard caps apply (HEADLINE ≤ 120 tokens; SUMMARY ≤ 600; FULL ≤ 3000).
4. **Ship a skills.md** under `skills/<panel>.md` per schema-and-skills §6 entries #9-#13.
5. **Define a sector-specific template** (`stock_initiation_<sector>_v2.yaml`) with a `section_plan_defaults.yaml` that includes the sector panel as a SUMMARY-fidelity headline artifact.
6. **Register Stage 5 routing rule** in `data/reference/sector_routing.yaml`.
7. **Add at least 1 ticker per sector to the Phase 3 smoke-test set** per impl plan §15.4 (JPM banks, O REITs, VRTX pharma, XOM E&P, CB insurance).

---

## 9. Verifier hook compatibility

| Sector | New verifier issues? | Existing closed-enum coverage |
|---|---|---|
| Banks | no | `block_cet1_below_minimum` is a variant of `block_shape` warning |
| REITs | no | `block_ffo_disclosure_mismatch`, `block_payout_high` are variants of `numeric_inconsistency` |
| Pharma | no | `block_pos_outside_range`, `block_stage_not_in_table` are variants of `block_shape` |
| E&P | no | `block_negative_netback`, `block_rrr_below_one` are variants of `block_shape` (warning) |
| Insurance | no | `block_combined_ratio_extreme`, `block_adverse_py_development_pattern`, `block_negative_book_value` are variants of `block_shape` and `tombstone` |

No new verifier issue types are required. The existing 14 + 4 closed enum from impl plan §16 remains the full set.

---

## 10. References

- Banks: Basel III framework documents; A. Saunders, "Financial Institutions Management"; Fed CCAR and DFAST methodology documents
- REITs: NAREIT FFO/AFFO definitions; CBRE / JLL / Green Street cap-rate surveys; Linneman, "Real Estate Finance and Investments"
- Pharma: Citeline (formerly Informa) clinical-stage probability-of-success tables; DiMasi et al., "The Price of Innovation"
- Energy/E&P: World Gold Council Guidance Note (AISC, 2013/2018); Society of Petroleum Engineers "Petroleum Resources Management System"
- Insurance: NAIC RBC framework; Solvency II SCR Standard Formula; IFRS 17 / IFRS 4; A.M. Best BCAR methodology
- Sector-specific accounting: FASB ASC 944 (Insurance), ASC 932 (E&P), ASC 942 (Banks), ASC 970/972 (Real Estate)
