---
name: dcf_engine
category: dcf
version: 1.0.0
produces_artifacts:
  - dcf_output
consumes_artifacts:
  - cost_of_capital_output
---

# dcf_engine — Full FCFF-Based DCF Valuation Engine

## Purpose

Compute the absolute intrinsic equity value of a company via discounted free cash
flows to the firm (FCFF). Given explicit revenue and margin projections plus a
`cost_of_capital_builder` output, the engine projects per-period FCFF, discounts
at WACC using the mid-year convention (institutional default), and computes terminal
value via three methods: Gordon perpetuity growth, exit multiple, and McKinsey key
value driver.

Supersedes the `dcf_valuation` skeleton helper from PR 0.2, which remains registered
for backward compatibility but is deprecated.

## When to use

- Primary intrinsic valuation in an initiation or update report.
- When you have explicit revenue/margin/capex/D&A/NWC paths (from `forecast_builder`
  or analyst-supplied).
- When you need all three TV methods computed and compared.
- When sensitivity analysis over WACC x terminal growth is required (pair with
  `sensitivity_table` and `tornado_diagram`).

## When NOT to use

- Quick comparables analysis — use `comparables.run` instead.
- Dividend-paying names as primary valuation — use `ddm_family`.
- FCFE (equity FCF) basis — `dcf_engine` uses FCFF only. FCFE support is deferred.
- REITs — use `reit_valuation_panel` (AFFO/NAV).
- Banks — use `banks_sector_panel` (P/TBV / ROTCE).

## Required prior step

Always run `cost_of_capital_builder` first and pass its full output as `cost_of_capital`.
The engine reads `cost_of_capital["wacc"]` directly.

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `revenue_path` | `list[float]` | Yes | Explicit forecast revenues year 1..N. |
| `operating_margin_path` | `float \| list[float]` | Yes | EBIT margin per year or scalar. |
| `tax_rate_path` | `float \| list[float]` | Yes | Tax rate per year or scalar. |
| `da_pct_of_revenue` | `float \| list[float]` | Yes | D&A as fraction of revenue. |
| `capex_pct_of_revenue` | `float \| list[float]` | Yes | Capex as fraction of revenue. |
| `nwc_pct_of_revenue` | `float \| list[float]` | Yes | NWC intensity (used to compute delta NWC). |
| `cost_of_capital` | `dict` | Yes | Output from `cost_of_capital_builder`; must include `wacc`. |
| `terminal_method` | `str` | Yes | `perpetuity` / `exit_multiple` / `key_value_driver`. |
| `terminal_growth` | `float` | No (default 0.025) | Long-run FCFF growth rate. Must be < WACC. |
| `terminal_exit_multiple` | `float` | Conditional | EV/EBITDA exit multiple; required for `exit_multiple`. |
| `terminal_roic` | `float` | Conditional | Terminal ROIC; required for `key_value_driver`. |
| `mid_year_convention` | `bool` | No (default True) | Discount at t-0.5 vs. t. |
| `net_debt` | `float` | No (default 0) | Total debt minus cash for EV→equity bridge. |
| `shares_outstanding` | `float` | No (default 0) | Diluted shares for per-share value. |
| `non_operating_assets` | `float` | No (default 0) | Excess cash / investments to add to equity. |
| `current_price` | `float` | No | Current market price for upside computation. |
| `tv_pct_warn_threshold` | `float` | No (default 0.75) | TV/EV fraction above which a warning fires. |

## Methodology

### FCFF per year

```
EBIT_t       = revenue_t * operating_margin_t
NOPAT_t      = EBIT_t * (1 - tax_rate_t)
D&A_t        = revenue_t * da_pct_t
CapEx_t      = revenue_t * capex_pct_t
delta_NWC_t  = (revenue_t - revenue_{t-1}) * nwc_pct_t
FCFF_t       = NOPAT_t + D&A_t - CapEx_t - delta_NWC_t
```

Year-1 delta NWC uses 0 as the prior-year revenue base (no historical anchor
baked in). If you have a known prior-year revenue, prepend it conceptually or
pass the delta NWC explicitly via a pre-computed nwc_pct that already accounts
for the prior-year base.

### Mid-year convention (default)

```
discount_factor_t = 1 / (1 + WACC)^(t - 0.5)
```

Assumes cash flows arrive at the midpoint of each year rather than at year-end.
This is the institutional default for equity research. Use `mid_year_convention=False`
only when you need to match a valuation model that used end-of-period discounting.

### Terminal value — three methods

**Perpetuity (Gordon growth):**
```
TV_nominal = FCFF_N * (1 + g) / (WACC - g)
```
Constraint: g < WACC AND g <= risk_free_rate (verifier checks both).

**Exit multiple:**
```
TV_nominal = EBITDA_N * terminal_exit_multiple
```
Cross-check: the implied perpetuity growth from this TV is computed and flagged
if unreasonably high (implied_g >= WACC).

**Key value driver (McKinsey):**
```
TV_nominal = NOPAT_{N+1} * (1 - g/ROIC) / (WACC - g)
```
Uses reinvestment rate = g / terminal_ROIC. Preferred when terminal ROIC differs
meaningfully from WACC (e.g., compounders with ROIC >> WACC).

### PV of terminal value

```
PV_TV = TV_nominal / (1 + WACC)^N
```

Uses end-of-period discounting for TV (institutional norm — TV represents the
value at year N looking forward, after all explicit-period cash flows have been
received).

### EV → equity bridge

```
equity_value = EV - net_debt + non_operating_assets
implied_per_share = equity_value / shares_outstanding_diluted
```

`net_debt = total_debt - cash` (caller's responsibility to compute correctly).
Do not add cash back separately.

## Common pitfalls

1. **Terminal growth >= WACC.** The engine raises a ValueError immediately. This
   is not a warning — the formula literally diverges. Common causes: passing
   nominal growth rates when the WACC was built with real rates, or using a
   too-optimistic perpetuity assumption. Fix: reduce terminal_growth or revisit
   WACC inputs.

2. **TV/EV > 75%.** When more than 75% of enterprise value comes from the terminal
   period, the valuation is highly sensitive to terminal assumptions. The engine
   emits a warning. The drafter must cite this warning and caveat the sensitivity
   analysis. If TV/EV > 85%, use tornado_diagram to show which terminal assumption
   is most impactful.

3. **Mid-year vs. end-year mismatch with comparables.** If your comps team uses
   end-year discounting, toggle `mid_year_convention=False` for consistency. Both
   conventions are valid — document which you used.

4. **D&A included in capex path.** Some models conflate D&A and maintenance capex.
   The engine expects them separately: `da_pct_of_revenue` for non-cash add-back,
   `capex_pct_of_revenue` for cash outflow. Double-check the source data.

5. **NWC intensity sign.** A positive `nwc_pct_of_revenue` means growing revenue
   requires more working capital (typical for most businesses — it's a cash drag).
   For asset-light or negative-working-capital businesses (like certain retailers
   or SaaS companies), pass a negative value; this will add to FCFF on revenue growth.

6. **EV bridge: net_debt vs. gross debt.** The bridge subtracts `net_debt`, which
   is `total_debt - cash`. If you pass gross debt, the per-share result will be
   understated. If you have a net-cash position (negative net_debt), the formula
   still holds — it correctly adds cash to equity value.

## Output shape (key fields)

```json
{
  "explicit_period_years": 5,
  "fcff_schedule": [
    {"year": 1, "revenue": ..., "ebit": ..., "nopat": ...,
     "da": ..., "capex": ..., "delta_nwc": ..., "fcff": ...,
     "discount_factor": ..., "pv_fcff": ...},
    ...
  ],
  "sum_pv_fcff": 92340,
  "terminal_value": {
    "method": "perpetuity",
    "terminal_growth": 0.025,
    "wacc": 0.0907,
    "terminal_value_nominal": 350000,
    "pv_terminal_value": 145900,
    "tv_pct_of_ev": 0.612,
    "all_methods": {
      "perpetuity": 350000,
      "exit_multiple": null,
      "key_value_driver": null
    }
  },
  "enterprise_value": 238240,
  "implied_equity_value": 222240,
  "implied_value_per_share": 120.13,
  "implied_upside_pct": 0.0871,
  "warnings": ["Terminal value is 61.2% of EV ..."],
  "narrative": "Implied $120/share vs current $110, +9% upside. ..."
}
```

## Worked example (round numbers)

**Inputs:**
- 3-year forecast: revenue = [100, 110, 121], op_margin = 0.20, tax = 0.21
- da_pct = 0.05, capex_pct = 0.08, nwc_pct = 0.10
- WACC = 0.10 (from cost_of_capital_builder), terminal_growth = 0.025
- net_debt = 50, shares = 10, current_price = 200

**Year 1 FCFF:**
```
EBIT   = 100 * 0.20 = 20
NOPAT  = 20 * 0.79  = 15.8
D&A    = 100 * 0.05 = 5
CapEx  = 100 * 0.08 = 8
dNWC   = (100 - 0) * 0.10 = 10  (year 1 vs. 0 base)
FCFF   = 15.8 + 5 - 8 - 10 = 2.8
```

**Year 3 FCFF (illustration):**
dNWC in year 3 = (121 - 110) * 0.10 = 1.1 (incremental working capital)

**Terminal value (year 3 FCFF = ~18.97):**
TV = 18.97 * 1.025 / (0.10 - 0.025) = 259.0

## Related helpers

- **`cost_of_capital_builder`**: must run first; output is passed as `cost_of_capital`.
- **`sensitivity_table`**: pair for WACC x terminal_growth grid.
- **`tornado_diagram`**: pair to rank which driver impacts valuation most.
- **`scenario_weighting`**: pair to combine bull/base/bear DCF outputs.
- **`reverse_dcf`**: invert the DCF to find market-implied growth rate.
- **`dcf_valuation`**: deprecated skeleton; still registered for backward compatibility.
