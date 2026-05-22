# Equity Research Helpers — Design Supplement (Valuation Engine, Decision, Forensic/Credit, Output)

**Date:** 2026-05-22
**Companion to:** `2026-05-21-equity-research-helpers-design.md`
**Status:** Design contract for the helpers an earlier audit found unscheduled. Required reading for PRs 2.2, 2.3, 2.4, 2.6, 2.7, 2.10 per impl plan §14.

---

## 1. Document purpose

The parent `helpers-design.md` covers valuation analytics (sensitivity, tornado, scenarios, reverse_dcf, football_field, waterfall), business quality (§4), risk + macro (§5), SaaS (§6), and LLM-orchestrated extraction (§7). It does **not** specify the core valuation engines themselves (DCF, DDM, justified multiples, SOTP), the decision layer that synthesizes valuations into a rating, the forensic/credit panels beyond Beneish, the 5-step DuPont decomposition, the debt-maturity ladder, or the `workbook_builder` helper that wraps the §2.5 `WorkbookTemplate` class.

This supplement closes those gaps. Every section here follows the parent doc's §1 conventions (registration pattern, exposure tiers, freshness/provenance, fail-soft policy, verifier hooks). Audit fixes already applied in the parent (helpers-design §9) are preserved; new audit-relevant decisions are flagged inline.

---

## 2. `cost_of_capital_builder`

**Purpose:** Build the cost of equity, cost of debt, and weighted-average cost of capital used by every absolute-valuation helper (DCF, DDM, justified multiples, SOTP, rNPV, REIT cap rate sanity, bank cost of equity, insurance EV discounting).

**Question answered:** What is the appropriate discount rate for this company's cash flows today, and what assumption set produced it?

**Report types:** Initiation (foundational), Update (refresh on rate moves), Sector (cross-company hurdle rates).

**Inputs:**
- `risk_free_rate` (float, required): typically 10-year Treasury yield from `eodhd_ust_yield_rates`
- `equity_risk_premium` (float, required): historical or implied; default = Damodaran current ERP for the ticker's primary listing country
- `country_risk_premium` (float, optional, default `0.0`): Damodaran CRP table for emerging-market exposure
- `country_risk_lambda` (float, optional, default `1.0`): exposure weight; 1.0 for domicile-only, lower for multinational
- `beta_source` (str, optional, default `"regression"`): `"regression"` (`statsmodels` OLS of stock vs. market index over `beta_window`) | `"industry"` (Damodaran industry beta + Hamada relevering) | `"manual"`
- `beta_window` (int, optional, default `60`): months for regression beta
- `unlevered_beta` (float, optional): for Hamada relevering when `beta_source="industry"`
- `target_debt_to_equity` (float, optional): for Hamada relevering and target capital structure
- `marginal_tax_rate` (float, required): effective rate is allowed but marginal is preferred; output records which was used
- `pretax_cost_of_debt` (float, required): from disclosed coupons (debt-maturity ladder, §12) or yield-to-maturity on bonds; spread-to-Treasury fallback for private debt
- `size_premium` (float, optional, default `0.0`): for build-up method; Ibbotson/Duff & Phelps size deciles
- `specific_risk_premium` (float, optional, default `0.0`): for private companies or distressed names
- `method` (str, required): `"capm"` | `"hamada"` | `"build_up"` | `"all"` (returns all three)

**Source:** `eodhd_ust_yield_rates` for `risk_free_rate`; `damodaran` reference snapshot for ERP / CRP / industry beta / unlevered beta; `eodhd_historical_stock_prices` + market index for regression beta; `eodhd_fundamentals` for marginal tax rate and debt schedule.

**Output:**
```json
{
  "method_used": "capm",
  "risk_free_rate": 0.043,
  "equity_risk_premium": 0.055,
  "country_risk_premium_applied": 0.0,
  "beta": {
    "value": 1.12,
    "source": "regression",
    "window_months": 60,
    "r_squared": 0.41,
    "unlevered_beta": 0.91,
    "relevered": false
  },
  "cost_of_equity": 0.1046,
  "pretax_cost_of_debt": 0.052,
  "marginal_tax_rate": 0.21,
  "after_tax_cost_of_debt": 0.0411,
  "capital_structure": {
    "equity_pct": 0.78,
    "debt_pct": 0.22,
    "source": "current_market_values"
  },
  "wacc": 0.0907,
  "alternative_methods": {
    "hamada": {"cost_of_equity": 0.0982, "wacc": 0.0856},
    "build_up": {"cost_of_equity": 0.1080, "wacc": 0.0930}
  },
  "narrative": "CAPM cost of equity 10.5% using a 60-month regression beta of 1.12 against the S&P 500 (R²=0.41). WACC 9.1% at the current market-value mix (78/22 equity/debt) with after-tax cost of debt 4.1%.",
  "data_as_of": "2026-05-21",
  "source_provenance": ["eodhd:ust_yields:2026-05-21", "damodaran:erp_2026q2"]
}
```

**Methodology:**

**CAPM:**
```
cost_of_equity = risk_free_rate + beta * equity_risk_premium + lambda * country_risk_premium
```

**Hamada relevering** (when `beta_source="industry"`):
```
beta_L = beta_U * [1 + (1 - tax_rate) * (D/E)]
```
Use industry unlevered beta (`beta_U`) and the target company's `D/E` to compute a relevered beta. The output records both `unlevered_beta` and the relevered value.

**Build-up:**
```
cost_of_equity = risk_free_rate + ERP + size_premium + specific_risk_premium
```
No beta input. Used for private companies, distressed names, or as a sanity check against CAPM.

**After-tax cost of debt:**
```
after_tax_cost_of_debt = pretax_cost_of_debt * (1 - marginal_tax_rate)
```

**WACC:**
```
WACC = (E/V) * cost_of_equity + (D/V) * after_tax_cost_of_debt
V = E + D  (market values; preferred stock added as third term if material)
```

**Capital structure source:** the default uses current market values of equity and debt. Allow `target` weights (post-LBO targets, management-stated capital structure) via input but record which was used.

**Edge cases:**
- Negative or NM equity (insolvent): refuse to return WACC; report cost_of_equity from build-up only with a structural-warning flag.
- Beta regression with low R² (< 0.20): emit a confidence flag; recommend industry beta + Hamada as an alternative.
- Non-US ticker with no Damodaran CRP entry: fall back to sovereign CDS spread + maturity match; otherwise raise.
- Multinational with significant foreign revenue: prefer revenue-weighted CRP via `country_risk_lambda` < 1.0 (e.g., 0.5 for half-US/half-EM); document the weighting in the narrative.

**Verifier hooks:**
- `block_shape`: numeric fields present and non-null when `method != "all"`.
- `numeric_inconsistency`: cost_of_equity ↔ beta ↔ ERP arithmetic reconciles in output.
- `temporal_ambiguous`: `risk_free_rate` and ERP must carry the same as-of date or within a 1-day tolerance.
- `block_terminal_growth_exceeds_rfr` (future): callers of cost_of_capital_builder feeding DCF must use `terminal_growth < risk_free_rate`; the verifier checks the combined contract.

---

## 3. `dcf_engine`

**Purpose:** Compute the absolute valuation of a company via discounted free cash flows. The institutional core of the valuation section.

**Question answered:** What is this company worth based on the cash flows it is expected to generate, discounted at its cost of capital?

**Report types:** Initiation (primary valuation), Update (post-results refresh), Sector (cross-company DCF triangulation).

**Inputs:**
- `revenue_path` (list[float], required): explicit forecast revenue, year 1 through year `N` (typically `N=5` or `N=10`)
- `operating_margin_path` (list[float], required): EBIT margin per year
- `tax_rate_path` (list[float] | float, required): per-year or constant
- `da_pct_of_revenue` (list[float] | float, required): D&A as % of revenue
- `capex_pct_of_revenue` (list[float] | float, required)
- `nwc_pct_of_revenue` (list[float] | float, required): working-capital intensity (ΔNWC derived)
- `cost_of_capital` (dict, required): output of `cost_of_capital_builder` (consumes `cost_of_capital_panel` artifact)
- `terminal_method` (str, required): `"perpetuity"` | `"exit_multiple"` | `"key_value_driver"`
- `terminal_growth` (float, required if `terminal_method != "exit_multiple"`)
- `terminal_exit_multiple` (float, required if `terminal_method == "exit_multiple"`): typically EV/EBITDA exit
- `terminal_roic` (float, optional, required if `terminal_method == "key_value_driver"`): expected reinvestment efficiency
- `mid_year_convention` (bool, optional, default `True`): discount at year `t - 0.5` rather than `t`
- `net_debt` (float, required): from balance sheet, current period
- `shares_outstanding` (float, required): diluted preferred for share-target work
- `non_operating_assets` (float, optional, default `0.0`): excess cash, equity investments at FV, etc.

**Source:** `cost_of_capital_panel` (consumes); `eodhd_fundamentals` for current net debt + shares; user-provided or AI-projected revenue/margin path.

**Output:**
```json
{
  "explicit_period_years": 10,
  "fcff_schedule": [
    {"year": 1, "revenue": 100000, "ebit": 20000, "tax": 4200, "da": 6000, "capex": 7500, "delta_nwc": 1500, "fcff": 12800, "discount_factor": 0.9559, "pv_fcff": 12235},
    {"year": 2, "...": "..."}
  ],
  "sum_pv_fcff": 92340,
  "terminal_value": {
    "method": "perpetuity",
    "terminal_fcff_year_n_plus_one": 22500,
    "terminal_growth": 0.025,
    "wacc": 0.0907,
    "terminal_value_nominal": 350000,
    "pv_terminal_value": 145900,
    "tv_pct_of_ev": 0.612
  },
  "enterprise_value": 238240,
  "net_debt": 18500,
  "non_operating_assets": 2500,
  "implied_equity_value": 222240,
  "shares_outstanding_diluted": 1850,
  "implied_value_per_share": 120.13,
  "current_price": 110.50,
  "implied_upside_pct": 0.0871,
  "sensitivity": null,
  "assumption_echo": {
    "operating_margin_terminal_year": 0.22,
    "capex_pct_terminal_year": 0.075,
    "implied_terminal_roic": 0.234
  },
  "narrative": "Implied $120/share vs current $110, +9% upside. Terminal value is 61% of EV — typical for a high-quality compounder. Implied terminal ROIC 23% reconciles with current operating returns.",
  "warnings": [],
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**FCFF (Free Cash Flow to Firm) per year:**
```
EBIT_t = Revenue_t * operating_margin_t
NOPAT_t = EBIT_t * (1 - tax_rate_t)
FCFF_t = NOPAT_t + D&A_t - CapEx_t - ΔNWC_t
       = Revenue_t * op_margin_t * (1 - tax_rate_t)
       + Revenue_t * da_pct_t
       - Revenue_t * capex_pct_t
       - (Revenue_t - Revenue_{t-1}) * nwc_pct_t
```

**Discount factor (mid-year convention default):**
```
discount_factor_t = 1 / (1 + WACC) ^ (t - 0.5)   if mid_year_convention
                  = 1 / (1 + WACC) ^ t           otherwise
PV_FCFF_t = FCFF_t * discount_factor_t
```

Mid-year convention matters: full-year discounting assumes cash arrives on Dec 31, which understates PV. Mid-year is the institutional default. Output records which was used.

**Terminal value, three methods:**

*Perpetuity (Gordon):*
```
TV_nominal = FCFF_{N+1} / (WACC - g)
           = FCFF_N * (1 + g) / (WACC - g)
```
Constraint: `g < WACC` AND `g <= risk_free_rate` (verifier rejects violations). Long-run earnings growth cannot exceed long-run nominal GDP growth, proxied by the risk-free rate.

*Exit multiple:*
```
TV_nominal = EBITDA_N * terminal_exit_multiple
```
Cross-check: the implied perpetuity growth from this TV (`g_implied = WACC - FCFF_{N+1}/TV_nominal`) must satisfy the same `g < WACC` constraint. Verifier surfaces if implied `g` is unreasonable.

*Key Value Driver (McKinsey):*
```
TV_nominal = NOPAT_{N+1} * (1 - g / terminal_ROIC) / (WACC - g)
```
Imposes the constraint that perpetuity growth requires reinvestment at the terminal ROIC. Cleanest theoretical formulation; flag preferred when `terminal_roic` differs materially from `WACC` (otherwise it collapses to perpetuity).

**PV of terminal value:**
```
PV_TV = TV_nominal * 1 / (1 + WACC) ^ N
      (or N - 0.5 if mid-year convention applied symmetrically; pick a convention and stick with it)
```
Convention default: mid-year for explicit FCFF, end-of-year for TV (institutional norm; the TV represents the value AT year N looking forward).

**Enterprise value:**
```
EV = sum(PV_FCFF) + PV_TV
```

**EV → equity bridge (matches comparables §3.1 audit-fix #11):**
```
equity_value = EV - net_debt + non_operating_assets
implied_value_per_share = equity_value / shares_outstanding_diluted
```
Do not add cash back separately; `net_debt = total_debt - cash` already nets it.

**Edge cases:**
- `terminal_growth >= WACC`: refuse to compute TV; raise with explicit message.
- `terminal_growth > risk_free_rate`: warn but compute; record warning in output.
- Negative explicit-period FCFF (growth investments): allowed; PV will be lower, possibly negative, with all weight on TV. Flag `tv_pct_of_ev > 0.85` as concerning.
- `shares_outstanding_diluted == 0` (pre-IPO): return EV only; share-level metrics return `null`.
- Net debt is negative (net cash position): `equity = EV + |net_debt|`; same formula, negative net_debt simply flips the sign of the subtraction.

**Verifier hooks:**
- `block_shape`: `fcff_schedule` length matches input forecast length; TV present.
- `block_terminal_growth`: TV method's `g` constraint satisfied; `g >= WACC` rejected.
- `numeric_inconsistency`: per-year FCFF reconciles with sum(PV_FCFF); EV = sum(PV_FCFF) + PV_TV.
- `block_tv_pct_high`: warning issue when `tv_pct_of_ev > 0.85` (extreme TV dependence). Not a hard reject; flagged for narrative caveats.
- `temporal_ambiguous`: data_as_of must propagate to forecasted figures (forward-looking with explicit base date).

**Skill doc (`skills/dcf_engine.md`):** required per schema-and-skills §6 #1. Covers method choice, terminal-value gotchas, mid-year convention, sensitivity grid integration, and the EV→equity audit-fix rule.

---

## 4. `ddm_family`

**Purpose:** Value the equity of a dividend-paying company directly from its dividend stream. Primary for utilities, mature financials, mature REITs as a cross-check on AFFO-based valuation, and any name where dividends are the dominant return mechanism.

**Question answered:** What is this stock worth based on the dividends it actually pays, under a defensible growth and discount assumption?

**Report types:** Initiation (dividend-driven names), Update (post-dividend-policy change), Sector (cross-company dividend valuation).

**Inputs:**
- `current_dividend_per_share` (float, required): most recent declared annual dividend
- `cost_of_equity` (float, required): from `cost_of_capital_builder`
- `method` (str, required): `"gordon"` | `"two_stage"` | `"three_stage"` | `"h_model"` | `"all"`
- `gordon_growth` (float, required if method uses Gordon)
- `stage1_growth` (float, required if method != gordon): high-growth phase
- `stage1_years` (int, required if method != gordon)
- `stage2_growth` (float, required if method == three_stage): transition phase
- `stage2_years` (int, required if method == three_stage)
- `terminal_growth` (float, required if method != gordon): perpetuity rate after final stage
- `h_half_life` (int, required if method == h_model): half-life of growth decay
- `current_payout_ratio` (float, optional): used for sustainability check
- `current_roe` (float, optional): used for sustainability check

**Source:** `eodhd_historical_dividends`, `eodhd_fundamentals` (ROE, payout); cost of equity from `cost_of_capital_builder`.

**Output:**
```json
{
  "method_used": "two_stage",
  "current_dividend": 4.20,
  "cost_of_equity": 0.085,
  "stages": [
    {"years": "1-5", "growth_rate": 0.07, "dividends": [4.49, 4.81, 5.14, 5.50, 5.89]},
    {"years": "6-perpetuity", "growth_rate": 0.025, "first_dividend": 6.04}
  ],
  "sum_pv_explicit_dividends": 20.50,
  "terminal_value": {
    "year_n_dividend_plus_1": 6.04,
    "method": "gordon",
    "growth": 0.025,
    "tv_nominal": 100.7,
    "pv_tv": 66.7
  },
  "implied_value_per_share": 87.20,
  "current_price": 78.50,
  "implied_upside_pct": 0.111,
  "sustainability": {
    "implied_sustainable_growth": 0.0653,
    "current_payout_ratio": 0.65,
    "current_roe": 0.187,
    "sustainable_growth_gap": -0.0047,
    "verdict": "growth assumption modestly above sustainable rate; modest payout reduction or ROE compression would absorb the gap"
  },
  "alternative_methods": null,
  "narrative": "Two-stage DDM yields $87/share vs current $79, +11%. Stage-1 growth 7% for 5 years, fading to 2.5% perpetuity. Sustainable growth check shows the 7% phase is modestly ahead of (1-payout)*ROE = 6.5%.",
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Gordon (single-stage):**
```
P0 = D1 / (Re - g)
   = current_dividend * (1 + g) / (Re - g)
```
Requires `g < Re`. Refuse if violated.

**Two-stage:**
```
PV_explicit = sum over t=1..N1 of D_t / (1 + Re)^t,  where D_t = current_div * (1 + stage1_g)^t
PV_terminal = D_{N1+1} / (Re - terminal_g) / (1 + Re)^N1,  where D_{N1+1} = D_{N1} * (1 + terminal_g)
P0 = PV_explicit + PV_terminal
```

**Three-stage:**
```
Stage 1: years 1..N1 with stage1_g
Stage 2: years N1+1..N1+N2 with stage2_g (transition)
Stage 3: perpetuity from year N1+N2+1 with terminal_g
PV is computed by integrating PV across the three stages.
```

**H-model (Fuller-Hsia 1984):**
```
P0 = D0 * (1 + g_L) / (Re - g_L)  +  D0 * H * (g_S - g_L) / (Re - g_L)

where g_L = long-run (terminal) growth
      g_S = short-run (current) growth
      H   = half-life of the decay (h_half_life)
```
Captures linear decay of growth from `g_S` to `g_L` over `2H` years. Smoother than discrete stages; preferred when growth deceleration is plausible but stage timing is uncertain.

**Sustainability check** (applied to all methods):
```
sustainable_growth = ROE * (1 - payout_ratio)
gap = stage1_growth - sustainable_growth
```
If `gap > 0`, the dividend growth assumption exceeds what fundamentals support without external financing — narrative should call this out. The check is reported, not a hard block; some companies legitimately grow dividends through buybacks-then-pay-out cycles, but the gap should always be visible.

**Edge cases:**
- Zero current dividend: refuse Gordon and H-model; require initiation dividend year for two/three-stage.
- Dividend cut in history: report DDM with a confidence-low flag; recommend FCF-based valuation as primary.
- `payout_ratio > 1.0` (dividends exceed earnings): mark as unsustainable; sustainability check returns negative `sustainable_growth`.
- Negative ROE: same — sustainability check is meaningless; flag and recommend FCF-based valuation.
- Required Re < stage1_growth: refuse the stage; recommend a longer fade or H-model with longer half-life.

**Verifier hooks:**
- `block_shape`: dividend schedule present for chosen method.
- `block_growth_exceeds_discount`: `g >= Re` in any phase rejected.
- `numeric_inconsistency`: sum of stage PVs + terminal PV = implied_value_per_share.
- `sustainability_warning` (output-level flag, not blocking): gap > 0 surfaces in narrative.

**Skill doc (`skills/ddm_family.md`):** required per schema-and-skills §6 #4. Covers method selection (when to use which), sustainability gotchas, REIT-specific notes (use AFFO panel for REITs; DDM is cross-check only).

---

## 5. `justified_multiples`

**Purpose:** Derive the multiples a company *should* trade at given its fundamentals (ROE, growth, payout, cost of equity), and compare against actual current multiples. Pairs with `comparables.run` to distinguish "cheap vs. peers" from "cheap vs. fundamentals."

**Question answered:** Given this company's profitability, growth, and risk, what P/E, P/B, EV/EBITDA, etc. is it justified to trade at — and how does that compare to where it actually trades?

**Report types:** Initiation (valuation triangulation), Update (post-results), Sector (cross-company justified-vs-actual spread).

**Inputs:**
- `cost_of_equity` (float, required)
- `growth` (float, required): sustainable / long-run growth rate
- `roe` (float, required): for P/B and forward P/E derivation
- `payout_ratio` (float, optional): for P/E; derivable from ROE and growth (`payout = 1 - g/ROE`)
- `roic` (float, optional): for EV/EBITDA / EV/IC justification
- `wacc` (float, optional): for EV multiples
- `current_multiples` (dict, optional): actual current P/E, P/B, EV/EBITDA from `comparables` artifact or `eodhd_ratios`
- `multiples_to_compute` (list[str], optional, default `["forward_pe", "trailing_pe", "pb", "ev_ebitda"]`)

**Source:** `cost_of_capital_panel` (consumes), `eodhd_fundamentals` (ROE, payout, ROIC), `comparables` artifact (for current_multiples).

**Output:**
```json
{
  "fundamentals_used": {
    "cost_of_equity": 0.0907,
    "growth": 0.045,
    "roe": 0.245,
    "payout_ratio": 0.816,
    "roic": 0.188,
    "wacc": 0.0907
  },
  "justified_multiples": {
    "forward_pe": {"value": 17.78, "formula": "payout / (Re - g) = 0.816 / 0.0457"},
    "trailing_pe": {"value": 18.58, "formula": "payout * (1 + g) / (Re - g)"},
    "pb":         {"value": 4.27,  "formula": "(ROE - g) / (Re - g) = 0.200 / 0.0457"},
    "ev_ebitda":  {"value": 12.5,  "formula": "derived from ROIC, WACC, g — see methodology"}
  },
  "actual_multiples": {
    "forward_pe": 19.20, "trailing_pe": 20.50, "pb": 4.80, "ev_ebitda": 13.1
  },
  "spreads": {
    "forward_pe":   {"actual_minus_justified_pct": 0.080,  "verdict": "modest premium to fundamentals"},
    "pb":           {"actual_minus_justified_pct": 0.124,  "verdict": "premium to fundamentals; consistent with ROE quality"},
    "ev_ebitda":    {"actual_minus_justified_pct": 0.048,  "verdict": "in line"}
  },
  "narrative": "On fundamentals (ROE 24.5%, growth 4.5%, COE 9.1%), justified forward P/E is ~18x. The stock trades at 19x, an 8% premium that reconciles with its high-quality return profile.",
  "warnings": [],
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Forward P/E (constant-growth Gordon variant):**
```
forward_PE = payout / (Re - g) = (1 - g/ROE) / (Re - g)
```
The right-hand form derives `payout` from sustainable growth identity `g = ROE * (1 - payout)` → `payout = 1 - g/ROE`. Imposes consistency: high growth requires low payout, which the formula captures automatically.

**Trailing P/E:**
```
trailing_PE = payout * (1 + g) / (Re - g)
            = forward_PE * (1 + g)
```

**P/B:**
```
PB = (ROE - g) / (Re - g)
```
Derived from `P = BV * (ROE - g) / (Re - g)`. ROE above Re produces P/B > 1; below produces P/B < 1. Pure measure of value creation: if ROE = Re, P/B = 1 regardless of growth.

**EV/EBITDA (from invested capital and ROIC):**
```
EV/IC = (ROIC - g) / (WACC - g)
EV/EBITDA can be derived by relating IC to EBITDA via the depreciation rate and tax rate:
EV/EBITDA = EV/IC * IC/EBITDA = EV/IC * (1 / (EBITDA_margin * Sales/IC))
```
Simpler practical approximation when capital intensity is stable:
```
EV/EBITDA ≈ (1 - tax_rate) * (ROIC - g) / (WACC - g) / depreciation_rate_of_IC
```
The helper computes this only when `roic`, `wacc`, depreciation rate (from `roic_panel`), and tax rate are all available; otherwise returns `null` with reason "insufficient inputs for EV/EBITDA justified multiple — supply ROIC / WACC / depreciation."

**Spread computation:**
```
spread_pct = (actual - justified) / justified
```
Verdict bands (configurable):
- `|spread| < 0.05` → "in line"
- `0.05 <= spread < 0.20` → "premium to fundamentals" (or "discount to fundamentals" for negative)
- `spread >= 0.20` → "material premium" (or discount)
- `spread > 0.50` → "extreme premium" (or discount) — narrative should call out

**Edge cases:**
- `g >= Re`: refuse, same as DDM constraint.
- `ROE < g` for P/B: produces negative justified P/B — flag as "growth cannot exceed return on equity" and refuse.
- `payout < 0` (negative implied payout, i.e., `g > ROE`): same — sustainable growth identity violated.
- Missing `current_multiples`: still emit justified multiples; spreads field returns null with reason.

**Verifier hooks:**
- `block_growth_exceeds_re`: `g >= Re` rejected.
- `block_growth_exceeds_roe`: `g > ROE` rejected for P/B and forward P/E.
- `numeric_inconsistency`: justified multiples reconcile with their formulas; spreads reconcile with actual − justified.

**Skill doc (`skills/justified_multiples.md`):** required per schema-and-skills §6 #5. Covers when justified > actual reads as undervalued vs structural problem, when EV/EBITDA approximation is reliable, pairing with comparables.

---

## 6. `sotp_builder`

**Purpose:** Sum-of-the-parts valuation. Value each operating segment at an appropriate per-segment method (DCF, comps, or peer multiples), sum the segment values, deduct net debt, and produce a consolidated equity value. Required for conglomerates, holding companies, and any multi-segment business where segments have materially different growth, margins, or risk profiles.

**Question answered:** What is this business worth if I value each operating segment independently and then add it up?

**Report types:** Initiation (conglomerates), Update (post-segment-restructuring), Sector (holding companies).

**Inputs:**
- `segments` (list[dict], required): each segment is:
  ```
  {
    "name": "Industrials",
    "revenue_or_ebitda": 28000,
    "metric_kind": "ebitda",                        # "ebitda" | "revenue" | "ebit" | "fcff" | "operating_income"
    "valuation_method": "ebitda_multiple",          # "ebitda_multiple" | "dcf" | "peer_pe" | "peer_ps" | "book_value" | "user_supplied"
    "method_inputs": {"multiple": 8.5},             # method-specific; for "dcf" pass a nested DCF input dict; for "user_supplied" pass {"value": 50000}
    "comparable_set": ["EMR", "PH", "ROK", "ITW"],  # optional, informational for the narrative
    "growth_rate": 0.04,
    "margin": 0.18
  }
  ```
- `corporate_overhead` (float, optional, default `0.0`): unallocated corporate cost; subtracted from segment-sum EV via a capitalized-overhead estimate
- `corporate_overhead_capitalization_multiple` (float, optional, default `8.0`): capitalize overhead at `overhead * multiple` (typical: EV/EBITDA peer of overhead's nature)
- `non_operating_assets` (float, optional, default `0.0`): equity-method investments at fair value, excess cash above operating need, real estate not used in operations
- `net_debt` (float, required): consolidated, current period
- `minority_interest` (float, optional, default `0.0`): non-controlling interest at fair value
- `shares_outstanding_diluted` (float, required)
- `conglomerate_discount_pct` (float, optional, default `0.0`): empirical 10-15% from Berger & Ofek (1995); apply as a deduction from SOTP equity value
- `tax_on_segment_sale` (bool, optional, default `False`): if true, applies an implied tax on segment EV uplift over book

**Source:** segment-level revenue/EBITDA from `eodhd_fundamentals` segment data; DCF inputs from upstream `dcf_engine` calls; comparable multiples from `comparables` artifacts; `cost_of_capital_panel` for any embedded DCFs.

**Output:**
```json
{
  "segments": [
    {
      "name": "Industrials",
      "metric_kind": "ebitda",
      "metric_value": 28000,
      "valuation_method": "ebitda_multiple",
      "multiple_used": 8.5,
      "segment_ev": 238000,
      "pct_of_total_ev": 0.585,
      "comparable_set": ["EMR", "PH", "ROK", "ITW"]
    },
    {
      "name": "Software",
      "metric_kind": "revenue",
      "metric_value": 12000,
      "valuation_method": "peer_ps",
      "multiple_used": 6.5,
      "segment_ev": 78000,
      "pct_of_total_ev": 0.192
    },
    {
      "name": "Finance arm",
      "metric_kind": "book_value",
      "metric_value": 24000,
      "valuation_method": "book_value",
      "multiple_used": 1.0,
      "segment_ev": 24000,
      "pct_of_total_ev": 0.059
    }
  ],
  "sum_segment_ev": 340000,
  "corporate_overhead_deduction": 18800,
  "adjusted_sum_ev": 321200,
  "conglomerate_discount_pct": 0.10,
  "conglomerate_discount_amount": 32120,
  "post_discount_ev": 289080,
  "non_operating_assets": 5000,
  "net_debt": 42000,
  "minority_interest": 3500,
  "implied_equity_value": 248580,
  "shares_outstanding_diluted": 2500,
  "implied_value_per_share": 99.43,
  "current_price": 88.20,
  "implied_upside_pct": 0.127,
  "narrative": "SOTP: Industrials $238B (8.5× EBITDA) drives 59% of EV. Software $78B at 6.5× sales reflects high-growth premium. Finance arm at book value $24B reflects regulated-equity convention. After $19B overhead capitalization and 10% conglomerate discount, equity value $249B = $99/share, +13% vs $88 current.",
  "warnings": ["Tax-on-segment-sale not applied; estimated $4-8B drag if monetized at current values"],
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Per-segment EV:**
- `ebitda_multiple`: `segment_ev = ebitda * multiple`
- `peer_pe` (rare for segment; used for finance-arm-style segments where NI is the reported metric): `segment_ev = ni * pe`. Note this is an *equity* multiple — for SOTP consistency, convert to EV by adding the segment's allocated net debt if disclosed; otherwise treat as an equity-only contribution and net-debt accounting must subtract segment-specific debt only.
- `peer_ps`: `segment_ev = revenue * ps_multiple`
- `dcf`: spawn a nested `dcf_engine` call with `method_inputs` as the DCF parameters; segment EV = output `enterprise_value`
- `book_value`: `segment_ev = book_value * multiple` (multiple usually 1.0 for regulated equity; can exceed 1.0 for high-ROE banking/insurance arms)
- `user_supplied`: `segment_ev = method_inputs["value"]` (analyst override; narrative records the source)

**Corporate overhead deduction:**
```
overhead_capitalized = corporate_overhead * corporate_overhead_capitalization_multiple
```
Subtracted from `sum_segment_ev` because segment EBITDAs typically exclude allocated corporate cost.

**Conglomerate discount:**
```
post_discount_ev = (sum_segment_ev - overhead_capitalized) * (1 - conglomerate_discount_pct)
```
Default 0%; activists / value investors typically apply 10-15% (Berger-Ofek 1995). Document the rationale in narrative when > 0.

**Equity bridge:**
```
implied_equity_value = post_discount_ev + non_operating_assets - net_debt - minority_interest
```

**Tax on segment sale (advanced):** if `tax_on_segment_sale = True`, compute the implied capital gain on each segment relative to its book value, apply marginal tax, and subtract from `implied_equity_value`. This is a hidden-friction adjustment that activist investors model when proposing spin-offs.

**Edge cases:**
- Segment-level EBITDA reconciles to consolidated EBITDA (after corporate overhead): the helper checks this and warns on a > 5% gap (likely an inter-segment elimination or misallocation).
- Negative-EBITDA segment: cannot use EBITDA multiple; must use book value, DCF, or user_supplied. The helper refuses an EBITDA multiple on a loss-making segment.
- Single-segment company (degenerate SOTP): equivalent to a single-method valuation; the helper still runs but flags `single_segment: true` in output for narrative clarity.
- Segment count > 10: flag in output; SOTP becomes spurious-precision territory.

**Verifier hooks:**
- `block_shape`: every segment has `name`, `valuation_method`, `metric_value`, computed `segment_ev`.
- `block_negative_ebitda_with_multiple`: a segment with negative EBITDA assigned an EBITDA multiple is rejected.
- `numeric_inconsistency`: `sum_segment_ev` matches sum of segments; equity bridge reconciles.
- `consolidated_ebitda_drift`: segment EBITDA sum + corporate overhead vs reported consolidated EBITDA > 5% triggers warning.

**Skill doc (`skills/sotp_builder.md`):** required per schema-and-skills §6 #6. Covers when SOTP is the primary lens (conglomerates, multi-region with different growth profiles, holding companies), conglomerate-discount calibration, hidden frictions (tax-on-sale, dyssynergies, deal costs).

---

## 7. Decision layer — `price_target_blender`, `expected_total_return`, `risk_reward_calculator`, `implied_upside_downside`, `rating_band_assigner`

The decision layer synthesizes valuations from §3-§6 + comparables into a single price target, total-return expectation, and rating recommendation. Five helpers, designed jointly because they consume each other's outputs.

### 7.1 `price_target_blender`

**Purpose:** Combine multiple per-methodology price targets into a single blended price target with explicit weights.

**Inputs:**
- `methodology_targets` (list[dict], required): each `{"name", "value", "weight", "source_artifact_id"}`
  ```
  [{"name": "DCF perpetuity",    "value": 120, "weight": 0.40, "source_artifact_id": "dcf_base_valuation"},
   {"name": "DCF exit-multiple", "value": 115, "weight": 0.10, "source_artifact_id": "dcf_exit_multiple"},
   {"name": "Comparables P/E",   "value": 108, "weight": 0.20, "source_artifact_id": "implied_price_range"},
   {"name": "Comparables EV/EBITDA", "value": 112, "weight": 0.20, "source_artifact_id": "implied_price_range"},
   {"name": "DDM",               "value": 105, "weight": 0.10, "source_artifact_id": "ddm_valuation"}]
  ```
- `auto_weight` (str, optional, default `"none"`): `"none"` (use provided weights) | `"equal"` (overrides to equal) | `"confidence"` (weights by per-methodology confidence score from each source artifact)

**Output:**
```json
{
  "blended_target": 113.7,
  "method_breakdown": [...],
  "weight_audit": {"sum": 1.00, "auto_weight_applied": false},
  "dispersion": {"min": 105, "max": 120, "stdev": 5.8, "spread_pct_of_blended": 0.132},
  "narrative": "Blended price target $114, ranging $105-$120 across methods (13% spread). DCF perpetuity 40% weight; comparables 40%; DDM 10%; exit-multiple sanity 10%."
}
```

**Methodology:**
```
blended_target = sum(weight_i * value_i)
```
Require `sum(weights) ≈ 1.0` (within 1% rounding tolerance). Normalize and warn if input violates.

**Edge cases:**
- One method dominant (weight > 0.80): warn — single-method PT, the blender is structural overhead.
- Methods disagree extremely (max-min > 50% of blended): flag `high_dispersion` warning in narrative.
- Some methods return null (e.g., DDM on a non-dividend payer): they're dropped from the average and weights are renormalized; output records the reweighting.

**Verifier hooks:** `numeric_inconsistency`: blended target = weighted average; `weight_sum_drift`: |sum - 1| > 0.01 rejected.

**Skill doc (`skills/price_target_blender.md`):** required per schema-and-skills §6 #7. Covers weight calibration by company quality (high-quality compounders → DCF higher weight; cyclicals → comps higher weight), dispersion narrative, when to refuse a blend.

### 7.2 `expected_total_return`

**Purpose:** Combine capital return (price target ÷ current price) with dividend yield to produce expected total return over a stated horizon.

**Inputs:**
- `price_target` (float, required)
- `current_price` (float, required)
- `forward_dividend_yield` (float, required): from `dividend_safety_panel` or `eodhd_fundamentals`
- `horizon_months` (int, optional, default `12`)

**Output:**
```json
{
  "current_price": 88.20,
  "price_target": 113.70,
  "capital_return_pct": 0.289,
  "forward_dividend_yield": 0.022,
  "horizon_months": 12,
  "expected_total_return_pct": 0.311,
  "annualized_etr_pct": 0.311
}
```

**Methodology:**
```
capital_return_pct = price_target / current_price - 1
expected_total_return_pct = capital_return_pct + forward_dividend_yield * (horizon_months / 12)
annualized_etr_pct = (1 + ETR) ^ (12 / horizon_months) - 1
```

**Edge cases:**
- Negative dividend yield (impossible) or yield > 0.20 (extreme): warn and require explicit verification.
- Horizon > 24 months: annualization smooths to a long-run figure; output records both raw and annualized.

**Verifier hooks:** `numeric_inconsistency`: ETR reconciles with capital_return + dividend.

### 7.3 `risk_reward_calculator`

**Purpose:** Compute the asymmetric reward-to-risk ratio: upside to bull case vs downside to bear case.

**Inputs:**
- `current_price` (float, required)
- `bull_case_price` (float, required): typically from upside scenario in DCF or top comparable multiple
- `bear_case_price` (float, required): from downside scenario or bottom comparable multiple

**Output:**
```json
{
  "current_price": 88.20,
  "bull_case": 130.0,
  "bear_case": 65.0,
  "upside_pct": 0.474,
  "downside_pct": -0.263,
  "risk_reward_ratio": 1.80,
  "verdict": "favorable: 1.8x upside-to-downside; bull case offers $42 reward vs $23 downside"
}
```

**Methodology:**
```
upside_pct = bull_case / current_price - 1
downside_pct = bear_case / current_price - 1
risk_reward_ratio = upside_pct / |downside_pct|
```

**Verdict bands:**
- `>= 3.0`: very favorable
- `2.0 - 3.0`: favorable
- `1.5 - 2.0`: positive
- `1.0 - 1.5`: marginal
- `< 1.0`: unfavorable

**Edge cases:**
- `bear_case >= current_price`: downside_pct positive; ratio undefined; flag as "no downside identified — check bear case rigor."
- `bull_case <= current_price`: upside_pct negative; flag as "no upside identified."

**Verifier hooks:** `numeric_inconsistency`: ratio reconciles with upside / |downside|.

### 7.4 `implied_upside_downside`

**Purpose:** Generate bull / base / bear cases by perturbing key DCF or comp assumptions, returning explicit case values for use by `risk_reward_calculator` and `scenario_weighting`.

**Inputs:**
- `base_artifact` (dict, required): DCF output or comparables `implied_price_range` artifact
- `scenarios` (list[dict], required): per-case driver shocks; e.g.,
  ```
  [{"name": "bull", "shocks": {"revenue_growth_path[0]": "+0.03", "operating_margin_terminal": "+0.02"}},
   {"name": "base", "shocks": {}},
   {"name": "bear", "shocks": {"revenue_growth_path[0]": "-0.03", "operating_margin_terminal": "-0.02"}}]
  ```

**Output:**
```json
{
  "base_case_price": 120,
  "scenario_outputs": [
    {"name": "bull", "price": 145, "drivers": {...}},
    {"name": "base", "price": 120, "drivers": {...}},
    {"name": "bear", "price": 92,  "drivers": {...}}
  ],
  "narrative": "Bull $145 (margin terminal 24%, revenue +8%); base $120; bear $92 (margin 20%, revenue +2%)."
}
```

**Methodology:** for each scenario, apply shocks to the base assumption set and re-run the underlying valuation (DCF or comparables-implied multiple). The shock syntax `"+0.03"` is interpreted as additive to the base assumption, `"*1.10"` as multiplicative, `"=0.22"` as override.

**Edge cases:** an invalid shock (driver not in the assumption schema) produces a `null` for that scenario with reason. Scenario without `name="base"` is allowed but warned.

### 7.5 `rating_band_assigner`

**Purpose:** Map expected total return + risk/reward + conviction inputs to a rating recommendation with an explanatory string.

**Inputs:**
- `expected_total_return_pct` (float, required)
- `risk_reward_ratio` (float, required)
- `conviction_score` (float, optional, default `0.5`): 0-1 scale; can be informed by `comparables` dispersion, DCF TV concentration, business-quality panels
- `rating_bands_config` (dict, optional): configurable thresholds; defaults below

**Default rating bands:**
```
BUY:    ETR >= +0.15 AND risk_reward >= 1.5
ADD:    ETR >= +0.07 AND risk_reward >= 1.2
HOLD:   -0.05 <= ETR < +0.07
REDUCE: ETR < -0.05 AND risk_reward < 1.5
SELL:   ETR < -0.15 OR (risk_reward < 0.8 AND ETR < 0)
```

**Output:**
```json
{
  "rating": "BUY",
  "expected_total_return_pct": 0.311,
  "risk_reward_ratio": 1.80,
  "conviction_score": 0.72,
  "why_this_rating": "ETR 31% exceeds +15% BUY threshold; risk/reward 1.8x clears 1.5x minimum; conviction 0.72 supports the recommendation. Primary risk: terminal value is 61% of EV — single-asset concentration in DCF.",
  "alternative_ratings_considered": [],
  "narrative": "BUY-rated. Asymmetric setup with 1.8x upside vs downside and 31% ETR over a 12-month horizon."
}
```

**Methodology:** evaluate the bands in order. `conviction_score` is documented as a heuristic, not a hard threshold (per schema-and-skills §6 #8 audit-fix style — opinionated, not neutral).

**Verifier hooks:** `block_rating_internal_inconsistency`: a BUY with `ETR < 0` rejected (band logic violated); same for SELL with `ETR > +0.10`.

**Skill doc (`skills/rating_band_assigner.md`):** required per schema-and-skills §6 #8. Covers calibration to user-supplied risk tolerance, when to override the mechanical mapping with judgment, why the bands are not a hard rule.

---

## 8. `altman_z_variants`

**Purpose:** Compute Altman Z-score in all four published variants (Z public manufacturing, Z' private, Z" non-manufacturers, EM Z" emerging-markets sovereign-overlay), producing a credit-quality classification and a per-input contribution table for explainability.

**Question answered:** Where on the bankruptcy-risk spectrum does this company sit, in the variant most appropriate to its structure and geography?

**Report types:** Initiation (credit context), Update (post-results), Sector (cross-company distress mapping).

**Inputs:**
- `working_capital` (float, required)
- `retained_earnings` (float, required)
- `ebit` (float, required)
- `market_value_equity` (float, required for Z; nullable for Z' which uses book equity)
- `book_value_equity` (float, required for Z' and Z")
- `book_value_total_liabilities` (float, required)
- `sales` (float, required for Z and Z'; not used by Z" and EM Z")
- `total_assets` (float, required)
- `variant` (str, required): `"z"` | `"z_prime"` | `"z_double_prime"` | `"em_z_double_prime"` | `"all"`

**Source:** `eodhd_fundamentals` for all inputs; `eodhd_historical_market_cap` for `market_value_equity`.

**Output:**
```json
{
  "variant_used": "z",
  "components": {
    "working_capital_to_ta":      {"value": 0.18, "weight": 1.2, "contribution": 0.216},
    "retained_earnings_to_ta":    {"value": 0.42, "weight": 1.4, "contribution": 0.588},
    "ebit_to_ta":                 {"value": 0.13, "weight": 3.3, "contribution": 0.429},
    "mv_equity_to_tl":            {"value": 2.85, "weight": 0.6, "contribution": 1.710},
    "sales_to_ta":                {"value": 0.95, "weight": 1.0, "contribution": 0.950}
  },
  "z_score": 3.89,
  "classification": "safe",
  "thresholds_used": {"distress": 1.81, "gray_upper": 2.99},
  "alternative_variants": null,
  "narrative": "Altman Z = 3.89 (safe zone, threshold 2.99). MV/TL contributes most (1.71 of 3.89); retained-earnings/TA at 0.42 reflects long history of accumulated profitability.",
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Z (public manufacturing, Altman 1968):**
```
Z = 1.2 * (WC/TA) + 1.4 * (RE/TA) + 3.3 * (EBIT/TA) + 0.6 * (MV_E / BV_TL) + 1.0 * (Sales/TA)
distress: Z < 1.81; gray: 1.81 - 2.99; safe: Z > 2.99
```

**Z' (private manufacturer, Altman 1983):** replaces market value with book equity:
```
Z' = 0.717 * (WC/TA) + 0.847 * (RE/TA) + 3.107 * (EBIT/TA) + 0.420 * (BV_E / BV_TL) + 0.998 * (Sales/TA)
distress: Z' < 1.23; gray: 1.23 - 2.90; safe: Z' > 2.90
```

**Z" (non-manufacturer, Altman 1995):** drops Sales/TA (industry-dependent and non-comparable across non-manufacturing sectors):
```
Z" = 6.56 * (WC/TA) + 3.26 * (RE/TA) + 6.72 * (EBIT/TA) + 1.05 * (BV_E / BV_TL)
distress: Z" < 1.10; gray: 1.10 - 2.60; safe: Z" > 2.60
```

**EM Z" (emerging-markets adjustment, Altman 1995):** adds a 3.25 constant for sovereign overlay:
```
EM_Z" = 3.25 + 6.56 * (WC/TA) + 3.26 * (RE/TA) + 6.72 * (EBIT/TA) + 1.05 * (BV_E / BV_TL)
distress: EM_Z" < 1.10 + 3.25 = 4.35; gray: 4.35 - 5.85; safe: > 5.85
(or equivalently use the same Z" thresholds against EM_Z" - 3.25)
```

**Variant selection guidance:**
- Public manufacturer (developed market) → `z`
- Private manufacturer → `z_prime`
- Public non-manufacturer (banks excluded — they have specialized credit models) → `z_double_prime`
- Emerging-market issuer (any non-manufacturer) → `em_z_double_prime`
- Banks: do NOT use Altman — use bank-specific credit (CET1, NCO, see sector-modules §2)

**Edge cases:**
- Negative working capital, retained earnings, or equity: produces a negative contribution; not an error. Frequent in distressed names — that's the point of the model.
- Sales/TA extreme (> 5 for asset-light services): inflates Z; flag in narrative; consider Z" instead.
- Market value not available (recent IPO with limited history): refuse Z; default to Z'.
- Insurance/financials: refuse all; recommend sector-specific credit panels.

**Verifier hooks:**
- `block_shape`: all components present; Z reconciles with weighted sum.
- `block_variant_misapplied`: applying Z to a bank or insurer is rejected (use sector panel).
- `numeric_inconsistency`: contribution_i = weight_i × value_i; sum reconciles.

---

## 9. `dividend_safety_panel`

**Purpose:** Assess whether the current dividend is sustainable from earnings and cash flow under base and stress conditions, and characterize the dividend history (streak, growth rate, cut history).

**Question answered:** Is this dividend safe, modestly at risk, or distressed? At what scenario does it get cut?

**Report types:** Initiation (income names), Update (post-policy-change), Sector (yield-focused screens).

**Inputs:**
- `historical_dividends` (Series, required): from `eodhd_historical_dividends`
- `historical_net_income` (Series, required): from `eodhd_fundamentals`
- `historical_free_cash_flow` (Series, required): from `eodhd_fundamentals`
- `historical_ebitda` (Series, required)
- `historical_interest_expense` (Series, required): for fixed-charge coverage variant
- `current_dividend_per_share` (float, required): annualized
- `current_shares_outstanding` (float, required)
- `current_price` (float, required): for yield computation
- `stress_scenario_pct` (float, optional, default `-0.25`): NI / FCF shock for stress test

**Source:** `eodhd_historical_dividends`, `eodhd_fundamentals`.

**Output:**
```json
{
  "current_dividend_annualized": 4.20,
  "current_yield": 0.0478,
  "current_payout_ratios": {
    "of_net_income": 0.55,
    "of_free_cash_flow": 0.61,
    "of_ebitda_minus_interest": 0.32
  },
  "coverage_ratios": {
    "ni_to_dividends": 1.82,
    "fcf_to_dividends": 1.64,
    "ebitda_minus_interest_to_dividends": 3.12
  },
  "history": {
    "years_paid_unbroken": 22,
    "years_grown_unbroken": 18,
    "cut_count_10y": 0,
    "cagr_dividends_5y": 0.077,
    "cagr_dividends_10y": 0.063
  },
  "stress_test": {
    "shock_pct": -0.25,
    "implied_stressed_ni_payout": 0.733,
    "implied_stressed_fcf_payout": 0.813,
    "verdict_at_shock": "covered_with_buffer"
  },
  "classification": "safe",
  "narrative": "Dividend safe: 55% of NI, 61% of FCF, 22-year unbroken streak, 18-year growth streak. At -25% NI shock, payout rises to 73% — still covered.",
  "warnings": [],
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Payout ratios:**
```
payout_of_ni   = dividends / NI
payout_of_fcf  = dividends / FCF
payout_of_ebitda_minus_interest = dividends / (EBITDA - interest)
```
EBITDA-minus-interest is included as a structurally sound coverage measure for highly levered names where NI payout looks fine only because interest is masking cash-flow strain.

**Coverage ratios (reciprocals of payout):**
```
coverage = NI / dividends, FCF / dividends, etc.
```
Coverage > 2x is healthy; 1-2x is tight; < 1x is unsustainable.

**Streak metrics:**
- `years_paid_unbroken`: count from most recent dividend back to first gap.
- `years_grown_unbroken`: count back to first year of dividend decline (year-over-year basis, annualized).
- `cut_count_10y`: count of YoY annual-dividend decreases in trailing 10 years.

**Growth rates:**
```
CAGR_n = (D_T / D_{T-n}) ^ (1/n) - 1
```
Use point-to-point CAGR (not OLS slope) for the streak metric; supplement with OLS slope as a stability indicator.

**Stress test:**
```
stressed_ni = ni * (1 + shock_pct)
stressed_payout = dividends / stressed_ni
```
Verdict bands:
- `stressed_payout < 0.70`: "covered_with_buffer"
- `0.70 - 0.95`: "tight_under_stress"
- `0.95 - 1.20`: "at_risk_under_stress"
- `> 1.20`: "breach_under_stress"

**Classification (composite):**
- `safe`: all three current payouts < 0.70, streak >= 10 years, stress < 0.95
- `moderate`: payout 0.70-0.85 OR streak 5-9 years OR stress 0.95-1.20
- `at_risk`: payout 0.85-1.00 OR cut in trailing 10 years OR stress 1.20+
- `distressed`: payout > 1.00 OR cut in trailing 3 years

**Edge cases:**
- Negative NI in current period: payout_of_ni is meaningless; fall back to FCF and EBITDA-minus-interest; classification cannot be "safe" with negative NI.
- Just-initiated dividend (years_paid_unbroken < 3): classification cannot exceed "moderate"; no track record.
- Special dividends in history: exclude from streak and CAGR computation if flagged in `historical_dividends`; otherwise streaks are artificially extended.

**Verifier hooks:**
- `block_shape`: all payout ratios present; streak fields populated.
- `numeric_inconsistency`: coverage × payout ≈ 1.0 for each pair.
- `numeric_ungrounded` (future): any "safe" / "at risk" claim in prose must trace to the classification field.

---

## 10. `credit_solvency_panel`

**Purpose:** Cross-section of credit-quality ratios — interest coverage variants, fixed-charge coverage, debt-to-EBITDA, debt-to-equity — with multi-year trends and peer-relative context where available. Complements `altman_z_variants` (point-in-time distress probability) with leverage and coverage trajectories.

**Question answered:** How leveraged is this balance sheet, how well does cash flow cover fixed obligations, and how have those measures evolved?

**Report types:** Initiation (credit framing), Update (post-results), Sector (cross-company leverage comparison).

**Inputs:**
- `historical_ebit` (Series, required, ≥ 4 years)
- `historical_ebitda` (Series, required)
- `historical_capex` (Series, required): for `EBITDA - CapEx` variant
- `historical_interest_expense` (Series, required)
- `historical_operating_lease_expense` (Series, optional, default zeros): for fixed-charge coverage; post-ASC 842 / IFRS 16 the lease liability is in debt, but lease expense ≠ interest, so it's added back here
- `historical_total_debt` (Series, required): includes operating-lease liability post-ASC 842
- `historical_cash` (Series, required)
- `historical_total_equity` (Series, required)
- `historical_total_assets` (Series, required)

**Source:** `eodhd_fundamentals`.

**Output:**
```json
{
  "current_period": {
    "interest_coverage_ebit": 8.42,
    "interest_coverage_ebitda": 11.15,
    "interest_coverage_ebitda_minus_capex": 7.10,
    "fixed_charge_coverage": 5.85,
    "debt_to_ebitda": 1.82,
    "debt_to_equity": 0.45,
    "debt_to_capital": 0.31,
    "net_debt_to_ebitda": 1.21,
    "cash_coverage": 12.85
  },
  "five_year_trends": {
    "interest_coverage_ebit":       [10.2, 9.8, 9.1, 8.7, 8.42],
    "debt_to_ebitda":               [1.55, 1.62, 1.70, 1.78, 1.82],
    "...": "..."
  },
  "trend_interpretation": {
    "interest_coverage_ebit": "moderate deterioration: -1.78x over 5 years; remains comfortably above 3x institutional minimum",
    "debt_to_ebitda": "modest releveraging: +0.27x; consistent with growth investment"
  },
  "credit_quality_classification": "investment_grade_strong",
  "implied_rating_proxy": "A- / BBB+",
  "narrative": "Interest coverage 8.4x EBIT, comfortably above 3x distress threshold. Debt/EBITDA 1.8x has crept up from 1.6x five years ago but remains investment-grade. Fixed-charge coverage 5.9x reflects modest operating-lease burden.",
  "warnings": [],
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Coverage variants:**
```
interest_coverage_ebit                  = EBIT / interest
interest_coverage_ebitda                = EBITDA / interest
interest_coverage_ebitda_minus_capex    = (EBITDA - CapEx) / interest    [free-cash variant]
fixed_charge_coverage                   = (EBIT + operating_lease) / (interest + operating_lease)
cash_coverage                           = (EBIT + D&A) / interest        [same as EBITDA / interest]
```
`interest_coverage_ebitda_minus_capex` is the strictest, used by rating agencies for capital-intensive names. Coverage < 1 means cash from operations after maintenance capex cannot service interest — a hard distress signal.

**Leverage ratios:**
```
debt_to_ebitda     = total_debt / EBITDA
net_debt_to_ebitda = (total_debt - cash) / EBITDA
debt_to_equity     = total_debt / total_equity
debt_to_capital    = total_debt / (total_debt + total_equity)
```

**Implied-rating proxy** (Damodaran-style mapping, simplified):
```
interest_coverage_ebit >= 12.5 AND debt/ebitda < 1.0           -> AAA
8.5 - 12.5            AND 1.0 - 1.5                              -> AA
6.5 - 8.5             AND 1.5 - 2.0                              -> A
4.5 - 6.5             AND 2.0 - 3.0                              -> BBB
3.0 - 4.5             AND 3.0 - 4.0                              -> BB
1.5 - 3.0             AND 4.0 - 5.0                              -> B
< 1.5                 OR  debt/ebitda > 5                        -> CCC or below
```
The mapping uses the *worse* of the two ratios. Pin the table source to Damodaran's rating-mapping reference and refresh quarterly. Output records both the table version and the worse-driver.

**Trend interpretation:**
- Linear OLS slope over the available window.
- Verbal bands: "improving" / "stable" / "modest deterioration" / "material deterioration" based on slope size relative to current level.

**Edge cases:**
- Negative EBIT or EBITDA: coverage variants return null with reason "negative EBITDA — interest cannot be covered from operations." Classification → distressed.
- Zero or negative interest expense (cash-rich, no debt): coverage is infinite — return string `"infinite"` and skip ratio interpretation.
- Total equity negative (insolvent on book basis): debt-to-equity is negative and meaningless; mark as `"book_insolvent"` in classification.

**Verifier hooks:**
- `block_shape`: all 9 current-period ratios present (with null where structurally meaningless).
- `numeric_inconsistency`: net_debt = total_debt - cash; debt_to_capital = debt/(debt+equity).
- `block_rating_proxy_disclaimer`: any prose claiming a "rating" must include "(proxy — not an actual rating)."

---

## 11. `five_step_dupont`

**Purpose:** Decompose ROE into its five fundamental drivers — tax burden, interest burden, operating margin, asset turnover, equity multiplier — so the source of ROE moves and the trade-off between leverage and operating quality are explicit.

**Question answered:** Where does this company's ROE come from, and how has the composition changed?

**Report types:** Initiation (return-on-capital deep dive), Update (post-results), Sector (cross-company composition).

**Inputs:**
- `historical_net_income` (Series, required, ≥ 5 years)
- `historical_ebt` (Series, required): pre-tax income
- `historical_ebit` (Series, required)
- `historical_sales` (Series, required)
- `historical_total_assets` (Series, required): for asset turnover
- `historical_total_equity` (Series, required): for equity multiplier

**Source:** `eodhd_fundamentals`.

**Output:**
```json
{
  "decomposition": {
    "tax_burden":         [0.79, 0.78, 0.79, 0.80, 0.79],
    "interest_burden":    [0.92, 0.91, 0.91, 0.92, 0.92],
    "operating_margin":   [0.225, 0.218, 0.224, 0.230, 0.232],
    "asset_turnover":     [0.88, 0.86, 0.87, 0.90, 0.92],
    "equity_multiplier":  [2.32, 2.41, 2.45, 2.40, 2.38],
    "roe":                [0.336, 0.328, 0.345, 0.367, 0.371]
  },
  "current_period": {
    "tax_burden": 0.79, "interest_burden": 0.92, "operating_margin": 0.232,
    "asset_turnover": 0.92, "equity_multiplier": 2.38, "roe": 0.371
  },
  "five_year_change_in_roe": {
    "total": 0.035,
    "drivers": {
      "operating_margin":   0.011,
      "asset_turnover":     0.015,
      "equity_multiplier":  0.005,
      "tax_burden":         0.001,
      "interest_burden":    0.003
    },
    "interpretation": "ROE +3.5 pts over 5y; ~70% driven by operating-margin and asset-turnover improvement (high-quality drivers); leverage contributes only 0.5 pts."
  },
  "narrative": "Five-step DuPont: ROE 37.1% built on 23.2% operating margin × 92% asset turnover × 2.38x leverage × tax/interest burdens. ROE improvement over 5 years is high-quality (margin + turnover, not leverage).",
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Identity:**
```
ROE = (NI / EBT) × (EBT / EBIT) × (EBIT / Sales) × (Sales / Total Assets) × (Total Assets / Equity)
    = tax_burden × interest_burden × operating_margin × asset_turnover × equity_multiplier
```

Each factor's range and quality interpretation:
- `tax_burden = NI/EBT`: typically 0.65-0.85; lower = higher tax drag; multinationals near 0.80-0.85 with low effective rates
- `interest_burden = EBT/EBIT`: typically 0.85-0.99; lower = more interest drag; below 0.80 is concerning
- `operating_margin = EBIT/Sales`: the only "quality" margin in the identity; the others are structural
- `asset_turnover = Sales/TA`: industry-dependent; software ~0.5, distributors ~2.5; trend matters more than absolute level
- `equity_multiplier = TA/Equity`: leverage. Higher = more risk. Should be interpreted against `debt/equity` from `credit_solvency_panel`.

**Five-year change decomposition** (additive approximation):
```
ΔROE ≈ ROE × [
   Δtax_burden/tax_burden  +
   Δinterest_burden/interest_burden  +
   Δoperating_margin/operating_margin  +
   Δasset_turnover/asset_turnover  +
   Δequity_multiplier/equity_multiplier
]
```
Equivalent multiplicative decomposition uses log differences. The output reports per-driver contribution in absolute ROE points; the sum reconciles to total ΔROE with small residual.

**Interpretation lens:**
- ROE improvement driven by `equity_multiplier` ↑: low-quality (leverage-juiced)
- ROE improvement driven by `operating_margin` ↑ or `asset_turnover` ↑: high-quality (operating-driven)
- ROE held up by `tax_burden` falling (effective rate rising): unsustainable; tax rates float
- ROE held up by `interest_burden` falling: deleveraging — good if margin and turnover are stable

**Edge cases:**
- Negative NI or EBT or EBIT: one or more factors are negative; ROE is negative; flag and provide per-factor values without interpretation.
- Negative equity (book insolvent): `equity_multiplier` is negative and meaningless; refuse to compute.
- Sales = 0 (development-stage): refuse; return null with reason.

**Verifier hooks:**
- `block_shape`: all 5 factors present per period.
- `numeric_inconsistency`: product of 5 factors = ROE within 0.5% tolerance.
- `block_negative_equity`: refused with explicit reason.

---

## 12. `debt_maturity_ladder`

**Purpose:** Render a year-by-year schedule of debt principal coming due, with weighted-average coupons and refinancing-risk flags. Critical for any leveraged name and for credit-quality narratives that depend on liquidity over the next 1-3 years.

**Question answered:** What does this company owe, when, and at what cost? Is there a refinancing wall?

**Report types:** Initiation (credit deep dive for any name with material debt), Update (post-refi event), Sector (cyclical names entering downturn).

**Inputs:**
- `debt_instruments` (list[dict], required): each:
  ```
  {"name": "5.25% senior notes 2028", "principal": 2500, "coupon": 0.0525, "maturity": "2028-04-15", "kind": "bond" | "loan" | "lease", "currency": "USD"}
  ```
  Source: `eodhd_fundamentals` debt schedule where disclosed; supplement with 10-K Note "Long-term debt" extraction via `pdf_ingest` if the EODHD schedule is incomplete.
- `as_of_date` (date, required)
- `refi_rate_shock` (float, optional, default `+0.02`): for stress test on cost-of-capital under elevated refi rate
- `current_pretax_cost_of_debt` (float, optional): from `cost_of_capital_builder`

**Output:**
```json
{
  "as_of": "2026-05-21",
  "ladder": [
    {"year": 2026, "principal_due": 350, "avg_coupon": 0.045, "instruments": ["Revolver", "3.5% sr notes 2026"]},
    {"year": 2027, "principal_due": 0,   "avg_coupon": null, "instruments": []},
    {"year": 2028, "principal_due": 2500, "avg_coupon": 0.0525, "instruments": ["5.25% sr notes 2028"]},
    {"year": 2029, "principal_due": 1200, "avg_coupon": 0.048, "instruments": ["..."]},
    {"year": 2030, "principal_due": 800,  "avg_coupon": 0.052, "instruments": ["..."]},
    {"year": "2031+", "principal_due": 4500, "avg_coupon": 0.058, "instruments": ["..."]}
  ],
  "weighted_avg_coupon": 0.0532,
  "weighted_avg_maturity_years": 5.8,
  "refi_wall": {
    "detected": true,
    "year": 2028,
    "principal_at_wall": 2500,
    "pct_of_total_debt": 0.265
  },
  "refi_stress_test": {
    "shock_bps": 200,
    "incremental_annual_interest": 50,
    "incremental_interest_pct_of_ebit": 0.025,
    "implied_new_cost_of_debt": 0.0725
  },
  "narrative": "Debt ladder: $350M due 2026 (manageable); $2.5B refi wall in 2028 (26% of total debt). At +200bps refi spread, incremental annual interest $50M, ~2.5% drag on EBIT.",
  "warnings": ["Refi wall concentrated in 2028 — monitor 2027 issuance activity"],
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

**Per-year aggregation:**
```
principal_due_year_t = sum of principal of instruments maturing in year t
avg_coupon_year_t    = principal-weighted average coupon of those instruments
```

Bucket years 1-5 individually; group year 6+ into `"6-10"`; group year 11+ into `"11+"` (deep tail). For the per-year detail, instruments list contains the human-readable names so the narrative can call out specific bonds.

**Weighted-average maturity:**
```
WAM = sum_i (principal_i × years_to_maturity_i) / sum_i principal_i
```

**Weighted-average coupon:**
```
WAC = sum_i (principal_i × coupon_i) / sum_i principal_i
```

**Refi wall detection:**
A wall is flagged when any single year has principal >= 25% of total debt or >= 50% of trailing 12-month EBIT. The threshold is the more conservative of the two. Output records which threshold triggered.

**Refi stress test:**
```
incremental_interest = principal_at_wall × shock_bps / 10000
implied_new_cost_of_debt = current_pretax_cost_of_debt + shock_bps / 10000
incremental_interest_pct_of_ebit = incremental_interest / current_ebit
```

**Edge cases:**
- No disclosed maturity schedule (private company, very small public): refuse to compute; recommend `pdf_ingest` on the most recent 10-K Note "Long-term debt."
- All debt floating-rate revolvers: WAM is short; flag in narrative that effective duration is governed by the credit agreement, not stated maturity.
- Convertible bonds: convert maturity is often the conversion date, not the stated maturity. Annotate conversion-eligible bonds separately if flagged in the input.
- Foreign-currency debt: convert principal to reporting currency at as-of-date FX; warn that FX-hedge status changes the effective cost.

**Verifier hooks:**
- `block_shape`: ladder covers years 1-5 individually + 6-10 bucket + 11+ bucket.
- `numeric_inconsistency`: sum of principal across ladder rows = total debt; WAM and WAC reconcile from per-row inputs.
- `temporal_ambiguous`: every principal_due figure must carry the as-of date.

---

## 13. `workbook_builder` (helper)

**Purpose:** Helper interface around the `WorkbookTemplate` class (helpers-design §2.5). Produces a multi-sheet xlsx workbook with cover, assumptions, valuation outputs, sensitivities, scenarios, comparables, and embedded charts — following an institutional financial-modeling convention every analyst recognizes.

**Question answered:** Render the full report's quantitative content as a downloadable spreadsheet.

**Report types:** Initiation (always), Update (optional), Sector (one-pager-per-name).

**Inputs:**
- `company_name` (str, required)
- `ticker` (str, required)
- `currency` (str, required): reporting currency
- `report_date` (date, required)
- `dcf_artifact` (dict, required): from `dcf_engine`
- `comparables_artifact` (dict, required): from `comparables.run`
- `sensitivity_artifact` (dict, optional): from `sensitivity_table`
- `scenarios_artifact` (dict, optional): from `scenario_weighting`
- `cost_of_capital_artifact` (dict, optional): from `cost_of_capital_builder`
- `sotp_artifact` (dict, optional): from `sotp_builder`
- `decision_artifact` (dict, optional): rating + price target + ETR from decision-layer helpers
- `additional_panels` (list[dict], optional): any other artifacts to embed as sheets (forensic, credit, dividend safety)
- `output_path` (str, required): where to write the .xlsx

**Output:**
```json
{
  "file_path": "/runs/2026-05-21/MSFT_initiation.xlsx",
  "sheets_written": [
    "Cover", "Assumptions", "DCF", "Sensitivity", "Scenarios",
    "Comparables", "SOTP", "Cost of Capital", "Decision", "Forensic", "Credit"
  ],
  "file_size_kb": 145,
  "narrative": "Workbook produced at /runs/2026-05-21/MSFT_initiation.xlsx — 11 sheets, 145KB.",
  "data_as_of": "2026-05-21"
}
```

**Methodology:**

Wraps the §2.5 `WorkbookTemplate` class. The helper's job is to:

1. Instantiate `WorkbookTemplate(company_name, ticker, currency, report_date)`.
2. Call `wb.add_dcf(dcf_artifact)` — writes DCF schedule + assumptions + per-year FCFF + TV breakdown to a "DCF" sheet with named ranges.
3. Call `wb.add_comparables(comparables_artifact)` — peer table + statistical summary + combined-range methodology to "Comparables" sheet.
4. Call `wb.add_sensitivity(sensitivity_artifact)` if present — 2-D grid to "Sensitivity" sheet with conditional formatting.
5. Call `wb.add_scenarios(scenarios_artifact)` if present — bull/base/bear with probabilities to "Scenarios" sheet.
6. Call `wb.add_sotp(sotp_artifact)` if present.
7. Call `wb.add_decision(decision_artifact)` if present.
8. Iterate `additional_panels` and call `wb.add_panel(panel)` for each.
9. Call `wb.embed_charts()` — render any chart artifacts as PNGs via openpyxl image insertion.
10. Call `wb.save(output_path)`.

The class handles formatting conventions (number formats by metric type, bold totals, color-coded scenario rows, frozen panes on the cover sheet).

**Edge cases:**
- Missing optional artifacts: sheets are simply omitted; cover sheet's TOC reflects what was written.
- Write path not writable: raise with explicit message; do not silently fall back.
- File-size cap (>10MB): warn; suggests reducing embedded chart resolution.

**Verifier hooks:**
- `block_shape`: `file_path` returned and exists after run.
- `block_artifact_too_large` (existing artifact-injection §8 issue): if the workbook is bundled into the report payload, > 10MB rejected.

**Skill doc (`skills/workbook_builder.md`):** required per schema-and-skills §6 #18. Covers sheet-naming convention, formula authoring rules (Excel cells reference named ranges, not raw cells), chart embedding gotchas, when to skip the workbook (atomic ratio reports don't need one).

---

## 14. Aggregator artifacts — `forensic_panel` and `statement_integrity_panel`

The impl plan PRs 2.5 and 2.6 ship two aggregator artifacts that compose constituent helper outputs into a single drafter-facing panel. Their per-constituent helpers are designed in §8 (Altman), helpers-design §4.18 (Beneish), §4.2 (quality_of_earnings), §4.17 (Piotroski), etc.; the aggregator shape is designed here.

### 14.1 `forensic_panel` (PR 2.6)

```python
class ForensicPanel(RenderableArtifact):
    """Composite forensic-quality view: bankruptcy risk + earnings manipulation + accruals quality."""
    altman: AltmanZArtifact          # from supplement §8 (altman_z_variants)
    beneish: BeneishMScoreArtifact   # from helpers-design §4.18
    sloan_accruals: SloanAccrualsView  # projected from quality_of_earnings_panel (helpers-design §4.2)
    composite_classification: Literal[
        "no_red_flags", "single_advisory", "multiple_advisory",
        "single_distress_signal", "multiple_distress_signals"
    ]
    composite_score: float            # 0-1; weighted blend documented below
    narrative: str                    # ~3-5 sentences synthesizing the three sub-views
    warnings: list[str]
    data_as_of: date
```

`composite_classification` decision table:

| Altman | Beneish M | Sloan | Composite |
|---|---|---|---|
| safe | low (M < -1.78) | low (< 0.05) | no_red_flags |
| gray | low | low or moderate | single_advisory |
| safe or gray | moderate (-1.78 to -1.0) | moderate | single_advisory |
| any | high (M > -1.0) | moderate or high | multiple_advisory |
| distress | low | low | single_distress_signal |
| distress | moderate or high | moderate or high | multiple_distress_signals |
| safe or gray | low | high (> 0.10) | single_advisory |

`composite_score` formula (advisory only — not a hard verdict):
```
composite_score = 0.40 * altman_distress_proximity
                + 0.35 * beneish_manipulation_proximity
                + 0.25 * sloan_proximity_to_threshold
```
Each sub-score normalized to [0, 1] where 1 = closer to distress / manipulation / low quality. Weights documented as opinionated.

**to_markdown fidelities:**
- HEADLINE: classification + composite_score in one line (≤ 120 tokens)
- SUMMARY: classification + per-sub-helper headline numbers (Altman variant + Z, Beneish M, Sloan ratio) + 1-line narrative (≤ 600 tokens)
- FULL: classification + composite_score + per-sub-helper full output blocks via their own to_markdown(FULL) + 3-5 sentence synthesis narrative (≤ 3000 tokens, hard cap; may require dropping older trend years if exceeded)

### 14.2 `statement_integrity_panel` (PR 2.5)

```python
class StatementIntegrityPanel(RenderableArtifact):
    """Composite financial-statement-integrity view: cross-statement reconciliation + accrual quality + Piotroski."""
    piotroski: PiotroskiArtifact            # from helpers-design §4.17
    cross_statement_validation: CrossStatementValidationArtifact  # from helpers-design §4.9
    accrual_quality_view: AccrualQualityView  # projected from quality_of_earnings_panel
    composite_classification: Literal[
        "high_integrity", "high_integrity_with_caveats",
        "moderate_integrity", "low_integrity"
    ]
    narrative: str
    warnings: list[str]
    data_as_of: date
```

`composite_classification` rules:
- `high_integrity`: Piotroski >= 7, no cross-statement discrepancies, Sloan accruals < 0.05
- `high_integrity_with_caveats`: Piotroski >= 6 with one ≥ -1pt deterioration, OR Sloan 0.05-0.10
- `moderate_integrity`: Piotroski 4-5, OR Sloan 0.10-0.15, OR a single cross-statement discrepancy
- `low_integrity`: Piotroski < 4, OR Sloan > 0.15, OR multiple cross-statement discrepancies

No composite numeric score; the classification carries the synthesis. The constituent helpers retain their own scores.

**to_markdown fidelities:** mirror the forensic_panel structure (HEADLINE classification, SUMMARY per-sub-helper headline + 1-line narrative, FULL constituent expansions + synthesis).

### 14.3 Common conventions for aggregator artifacts

1. **Composition, not duplication:** the aggregator stores typed references to constituent artifacts (already materialized by Stage 7a). It does not re-render the underlying numbers; `to_markdown(level)` delegates to each sub-artifact's own renderer.
2. **Highest-fidelity-wins still applies:** if both the aggregator and a constituent (e.g. `altman` standalone) appear in the section_plan, the higher-fidelity rendering wins; the constituent in the aggregator is replaced by a back-reference per artifact-injection §5.
3. **Classification is opinionated:** all composite classifications are heuristics documented in the helper's `skills.md`. The narrative must use conditional language ("multiple advisory signals — investigate") rather than verdict language ("avoid this name").
4. **Artifact IDs:** `forensic_panel`, `statement_integrity_panel`. Both register in `artifact_types.yaml` (PR 0.1).

---

## 15. Verifier-hook coverage map

| Helper | New verifier hook needed? | Existing closed-enum coverage |
|---|---|---|
| cost_of_capital_builder | no | `block_shape`, `numeric_inconsistency`, `temporal_ambiguous` |
| dcf_engine | no (uses existing `block_terminal_growth`) | + `block_tv_pct_high` (advisory) |
| ddm_family | no | `block_growth_exceeds_discount` (variant of `block_terminal_growth`) |
| justified_multiples | no | `block_growth_exceeds_re`, `block_growth_exceeds_roe` (variants) |
| sotp_builder | no | `block_negative_ebitda_with_multiple` (variant of `block_shape`) |
| price_target_blender | no | `weight_sum_drift` (variant of `numeric_inconsistency`) |
| rating_band_assigner | no | `block_rating_internal_inconsistency` (variant of `block_shape`) |
| altman_z_variants | no | `block_variant_misapplied` (variant of `block_shape`) |
| dividend_safety_panel | no | existing hooks |
| credit_solvency_panel | no | `block_rating_proxy_disclaimer` (variant of `tombstone`) |
| five_step_dupont | no | existing hooks |
| debt_maturity_ladder | no | existing hooks |
| workbook_builder | no | existing artifact-injection hooks |

All new helpers fit within the existing 14 + 4 closed verifier issue enum (14 from initial design + 4 from PR 0.3 materialization). No additional issue types needed.

---

## 16. References

- Altman, E. (1968). "Financial Ratios, Discriminant Analysis, and the Prediction of Corporate Bankruptcy"
- Altman, E. (1983, 1995, 2017). Z-variant publications including emerging-markets adjustment
- Berger, P. G., & Ofek, E. (1995). "Diversification's Effect on Firm Value" — conglomerate discount
- Damodaran, A. Published cost of capital data, country risk premium tables, industry beta tables
- Fuller, R. J., & Hsia, C-C. (1984). "A Simplified Common Stock Valuation Model" — H-model
- Hamada, R. (1972). "The Effect of the Firm's Capital Structure on the Systematic Risk of Common Stocks"
- McKinsey & Company. "Valuation: Measuring and Managing the Value of Companies" — key value driver formula
- Modigliani, F., & Miller, M. (1958, 1963). Capital structure and cost of capital
