---
name: cost_of_capital_builder
category: dcf
version: 1.0.0
produces_artifacts:
  - cost_of_capital_output
consumes_artifacts: []
---

# cost_of_capital_builder — Cost of Equity, Cost of Debt, and WACC

## Purpose

Compute the discount rate used by every absolute-valuation helper (DCF, DDM,
justified multiples, SOTP, rNPV). Supports three methodologies: CAPM, Hamada
relevering, and build-up. Exposes a full decomposition so the report drafter
can cite every component (risk-free rate, ERP, beta source, CRP, size premium).

## When to use

- Before calling `dcf_engine`, `ddm_family`, `justified_multiples`, or any helper
  that requires a WACC or cost of equity input.
- When updating the discount rate after a meaningful interest-rate move (the
  risk-free rate component changes).
- When a company's capital structure changes materially (deleveraging / LBO).
- Sector reports that compare hurdle rates across peers for relative risk context.

## When NOT to use

- Quick comparables-based valuation — WACC is not required for peer multiples.
- When `ft_capital_structure` already provides a WACC that is sufficient as a
  cross-check; avoid calling this helper twice for the same run unless you need
  the full narrative decomposition.

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `risk_free_rate` | `float` | Yes | 10-year Treasury yield in decimal form (e.g. 0.043 for 4.3%). |
| `equity_risk_premium` | `float` | Yes | ERP in decimal. Use Damodaran current estimate for the ticker's primary listing country. |
| `marginal_tax_rate` | `float` | Yes | Marginal corporate tax rate. Preferred over effective rate; document which was used. |
| `pretax_cost_of_debt` | `float` | Yes | Pre-tax cost of debt from coupon/par or YTM on traded bonds. |
| `equity_weight` | `float` | Yes | E/V — equity as fraction of total capital. |
| `debt_weight` | `float` | Yes | D/V — debt as fraction. Must sum with equity_weight to 1.0. |
| `method` | `str` | No (default `capm`) | `capm` / `hamada` / `build_up` / `all`. |
| `beta` | `float` | Conditional | Levered equity beta. Required for `capm` and `hamada`. |
| `unlevered_beta` | `float` | Conditional | Unlevered beta for Hamada from industry table. |
| `target_debt_to_equity` | `float` | No | D/E ratio. Derived from weights if not provided. |
| `country_risk_premium` | `float` | No (default 0) | Damodaran CRP for EM exposure. |
| `country_risk_lambda` | `float` | No (default 1.0) | CRP exposure weight (1.0 = full domicile, ~0.5 for half-US/half-EM). |
| `size_premium` | `float` | No (default 0) | Build-up method: Ibbotson/Duff & Phelps size decile premium. |
| `specific_risk_premium` | `float` | No (default 0) | Build-up: company-specific risk for private/distressed names. |
| `beta_r_squared` | `float` | No | Beta regression R². Below 0.20 triggers a low-confidence flag. |
| `capital_structure_source` | `str` | No (default `current_market_values`) | `current_market_values` or `target`. Recorded in output. |

## Methodology

### CAPM

```
cost_of_equity = risk_free_rate + beta * equity_risk_premium + lambda * country_risk_premium
```

Use when: beta is available from a 36–60 month regression against the relevant
index, R² is above 0.20, and the company is not private or distressed.

### Hamada relevering

When using an industry unlevered beta:

```
beta_L = beta_U * [1 + (1 - tax_rate) * (D/E)]
```

Then feed beta_L into CAPM. This strips out the company's current leverage from
peer betas (more stable) and re-applies the target leverage.

Tip: Use Hamada when the regression beta is noisy (R² < 0.20) or the company
recently changed its capital structure significantly.

### Build-up method

```
cost_of_equity = risk_free_rate + ERP + size_premium + specific_risk_premium
               + lambda * country_risk_premium
```

No beta input. Primary for private companies, early-stage growth, or when you
want a beta-free sanity check alongside CAPM.

### After-tax cost of debt

```
after_tax_rd = pretax_cost_of_debt * (1 - marginal_tax_rate)
```

### WACC

```
WACC = (E/V) * cost_of_equity + (D/V) * after_tax_rd
```

Capital structure weights: default uses current market values. Post-LBO or
management-stated targets can be passed via `equity_weight` / `debt_weight`
with `capital_structure_source="target"`.

## Common pitfalls

1. **Double-counting CRP.** If the ERP source (e.g., Damodaran implied ERP) already
   includes a global risk adjustment, set `country_risk_premium=0` to avoid
   double-counting. The Damodaran mature-market ERP does NOT include CRP; the
   total-market ERP may already embed it. Check the source.

2. **Using effective tax rate instead of marginal.** The after-tax debt shield
   should use the marginal rate (the rate at which the next dollar is taxed), not
   the effective rate, which blends in prior-year credits and deferred items.
   Pass `marginal_tax_rate` accordingly and document the choice in the narrative.

3. **Low-R² beta.** Regression betas with R² < 0.20 carry high standard errors.
   The helper flags this and recommends industry beta + Hamada. If you proceed
   with a noisy beta, note it in the narrative and test sensitivity to an industry
   beta alternative.

4. **Current vs. target weights.** Book-value weights understate equity value for
   profitable companies and overstate it for distressed ones. Always use
   market-value weights. If the company is in transition (post-merger, mid-deleveraging),
   set `capital_structure_source="target"` and supply the forward target weights.

5. **Negative equity / insolvency.** When equity_weight ≤ 0 the helper returns
   cost-of-equity from build-up only and sets WACC to None. The output includes
   a structural-warning flag. The drafter should note this and prefer an
   asset-based or recovery-scenario valuation.

## Output

```json
{
  "method_used": "capm",
  "risk_free_rate": 0.043,
  "equity_risk_premium": 0.055,
  "country_risk_premium_applied": 0.0,
  "beta": {
    "value": 1.12,
    "unlevered_beta": 0.91,
    "relevered": false,
    "window_months": 60,
    "r_squared": 0.41
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
  "alternative_methods": null,
  "narrative": "CAPM cost of equity 10.5% beta 1.12 (R²=0.41) WACC 9.1% ...",
  "warnings": [],
  "data_as_of": "2026-05-22"
}
```

When `method="all"`, the `alternative_methods` field contains hamada and build_up results.

## Examples

### Typical large-cap US stock

```python
result = cost_of_capital_builder.execute(
    risk_free_rate=0.043,
    equity_risk_premium=0.055,
    marginal_tax_rate=0.21,
    pretax_cost_of_debt=0.052,
    equity_weight=0.78,
    debt_weight=0.22,
    method="capm",
    beta=1.12,
    beta_r_squared=0.41,
)
# result["wacc"] ~ 0.0907
```

### Emerging-market company with Hamada

```python
result = cost_of_capital_builder.execute(
    risk_free_rate=0.043,
    equity_risk_premium=0.055,
    marginal_tax_rate=0.28,
    pretax_cost_of_debt=0.072,
    equity_weight=0.60,
    debt_weight=0.40,
    method="hamada",
    unlevered_beta=0.85,        # Damodaran EM consumer sector
    country_risk_premium=0.035, # Brazil CRP
    country_risk_lambda=0.80,   # 80% EM revenue
)
```

## Related helpers

- **`dcf_engine`**: consumes cost_of_capital_output directly (pass the full dict as `cost_of_capital`).
- **`ddm_family`**: uses `cost_of_equity` from this output.
- **`justified_multiples`**: uses both `cost_of_equity` and `wacc`.
- **`ft_capital_structure`**: FinanceToolkit-derived WACC; use as a cross-check, not a replacement.
- **`reverse_dcf`**: uses `fixed_wacc` from this output to solve for implied growth.
