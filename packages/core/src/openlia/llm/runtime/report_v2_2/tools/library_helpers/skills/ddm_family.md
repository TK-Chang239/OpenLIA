---
name: ddm_family
category: alternative_valuation
version: 1.0.0
produces_artifacts:
  - ddm_output
consumes_artifacts:
  - cost_of_capital_output
---

# ddm_family — Dividend Discount Model Family

## Purpose

Value the equity of a dividend-paying company directly from its dividend stream.
Provides four DDM variants — Gordon (single-stage), two-stage, three-stage, and
H-model — under a single interface. Each variant targets a different growth profile.
An integrated sustainability check compares the assumed growth rate against what
the company's fundamentals can support without external financing.

## When to use

- Utilities, mature financials, and mature REITs where dividends are the dominant
  investor return mechanism and dividend policy is stable.
- Cross-check alongside DCF for any name that pays a meaningful dividend: the two
  models should produce similar implied values; large divergence signals a
  payout-ratio or growth-assumption mismatch worth investigating.
- Post-dividend-policy-change update reports: the DDM instantly quantifies the
  value impact of a cut or raise in payout.
- When the question is "what price does a yield-focused investor require?" rather
  than "what are the intrinsic cash flows worth?"

## When NOT to use

- Non-dividend payers — the helper raises immediately on zero or negative D0.
  Use `dcf_engine` (FCFF) as the primary approach.
- REITs as the primary valuation — use `reit_valuation_panel` (AFFO/NAV); DDM
  on REIT dividends is a cross-check only because AFFO, not GAAP net income, is
  the economically meaningful payout base.
- High-growth companies where reinvestment dominates and payout is very low (<20%).
  The DDM will severely understate value because the model only captures the
  distributed fraction of earnings.
- Companies with negative ROE or payout > 100% — the sustainability check will
  flag, and the growth assumption becomes unanchored. Prefer `dcf_engine`.

## Model selection guide

| Situation | Recommended variant |
|---|---|
| Mature company, stable dividend growth | `gordon` |
| Known high-growth phase, then converges to steady state | `two_stage` |
| Growth decelerates gradually but timing uncertain; smooth fade preferred | `h_model` |
| Growth decelerates in two distinct steps (e.g., post-investment phase + maturity) | `three_stage` |
| Want all four for sensitivity / narrative comparison | `all` |

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `current_dividend_per_share` | `float` | Yes | Most recent declared annual dividend (D0). |
| `cost_of_equity` | `float` | Yes | Re from `cost_of_capital_builder`. |
| `method` | `str` | Yes | `gordon` / `two_stage` / `three_stage` / `h_model` / `all`. |
| `gordon_growth` | `float` | No (0.025) | Constant perpetuity growth for Gordon model. |
| `stage1_growth` | `float` | Conditional | High-growth rate for two/three-stage and h_model fallback. |
| `stage1_years` | `int` | Conditional | Duration of high-growth phase for two/three-stage. |
| `stage2_growth` | `float` | No | Transition midpoint for three-stage (defaults to midpoint of stage1 and terminal). |
| `stage2_years` | `int` | Conditional | Transition duration for three-stage. |
| `terminal_growth` | `float` | No (0.025) | Stable perpetuity rate for two/three-stage and h_model. |
| `h_half_life` | `float` | Conditional | H value (years) for h_model. |
| `h_short_growth` | `float` | No | Short-run growth for h_model; falls back to `stage1_growth`. |
| `current_payout_ratio` | `float` | No | For sustainability check. |
| `current_roe` | `float` | No | For sustainability check. |
| `current_price` | `float` | No | For implied upside/downside. |

## Methodology

### Gordon growth (single-stage)

```
D1 = D0 * (1 + g)
P0 = D1 / (Re - g)
```

Constraint: `g < Re`. Raises ValueError immediately if violated.

### Two-stage

```
PV_explicit = sum_{t=1}^{N1}  D0 * (1 + g_high)^t / (1 + Re)^t

TV           = D_{N1} * (1 + g_stable) / (Re - g_stable)
PV_TV        = TV / (1 + Re)^{N1}

P0 = PV_explicit + PV_TV
```

### Three-stage

Stage 1 (years 1..N1): constant high growth `g_high`.
Stage 2 (years N1+1..N1+N2): linear fade — growth at step `i` is
```
g_i = g_high + (i / N2) * (g_stable - g_high)
```
Stage 3 (perpetuity from N1+N2+1): Gordon terminal value at `g_stable`.

Full PV is the sum of discounted dividends across all three stages plus the
discounted terminal value.

### H-model (Fuller-Hsia 1984)

```
P0 = D0 * (1 + g_L) / (Re - g_L)   [stable component]
   + D0 * H * (g_S - g_L) / (Re - g_L)   [excess-growth component]
```

Where:
- `g_L` = long-run (terminal) growth
- `g_S` = short-run (current) growth
- `H` = half-life of decay (in years)

Captures linear decay from `g_S` to `g_L` over `2H` years. Simpler than
two/three-stage discrete phases; preferred when stage timing is uncertain but
a smooth convergence is plausible. The "H premium" is directly visible as the
second term.

### Sustainability check

```
sustainable_growth = ROE * (1 - payout_ratio)
gap = g_assumed - sustainable_growth
```

If `gap > 0`, growth exceeds what retained earnings can sustain — external
financing or payout compression would be needed. Reported as a narrative flag;
not a hard block (some companies legitimately grow dividends faster for a period
via buybacks-then-pay-out cycling or temporary leverage).

If `payout_ratio > 1.0`: dividends exceed earnings; flag as unsustainable.
If `ROE < 0`: sustainability formula is meaningless; recommend DCF as primary.

## Common pitfalls

1. **g >= Re causes an immediate raise.** If `stage1_growth >= Re` in the
   two-stage model, the discounting of explicit-period dividends is technically
   valid but numerically unusual; the verifier rejects `terminal_growth >= Re`.
   Check that your cost of equity from `cost_of_capital_builder` is calibrated
   for the same period as your growth assumptions.

2. **Three-stage transition grows to Re boundary.** When transitioning from a
   high `g_high` down to `g_stable`, each step in the transition is checked
   against `Re`. If `g_high` is very close to `Re` and the transition is short,
   intermediate steps can still exceed `Re`. Increase `stage2_years` or reduce
   `g_high` to avoid this.

3. **H-model does not enforce growth > 0.** If `g_short < g_long`, the excess
   component is negative — representing a company with short-run growth *below*
   its long-run rate (rare but mathematically valid). Interpret carefully.

4. **DDM only values distributed earnings.** For a company that pays only 20% of
   earnings as dividends, the DDM represents 20% of the total value creation.
   The P/E implied by DDM on a 20% payout name will be much lower than the DCF
   implied value — this is expected, not an error.

5. **REIT dividend vs. AFFO.** REITs pay dividends from AFFO, not GAAP net income.
   Passing GAAP EPS as the base and checking `payout_ratio` against GAAP net income
   will produce wrong sustainability results. Use AFFO-based payout for sustainability
   and route primary valuation to `reit_valuation_panel`.

6. **Using "all" method without comparing results.** `method="all"` is designed
   for narrative triangulation. If the four models produce very different outputs,
   the discrepancy is analytically valuable — report it, don't silently pick the
   most optimistic one.

## Output shape (key fields)

```json
{
  "method_used": "two_stage",
  "primary_model": "two_stage",
  "current_dividend": 4.20,
  "cost_of_equity": 0.085,
  "price_per_share": 87.20,
  "pv_breakdown": {
    "stage1_explicit": 20.50,
    "stage2_terminal": 66.70
  },
  "stages": [
    {"label": "stage1_high_growth", "years": "1-5", "growth_rate": 0.07, "dividends": [...]},
    {"label": "stage2_perpetuity",  "years": "6-perpetuity", "growth_rate": 0.025, ...}
  ],
  "sustainability": {
    "growth_assumed": 0.07,
    "payout_ratio": 0.65,
    "roe": 0.187,
    "sustainable_growth": 0.0655,
    "gap": 0.0045,
    "sustainable": false,
    "warnings": ["Growth assumption 7.0% exceeds sustainable rate 6.5%..."]
  },
  "alternative_methods": null,
  "implied_upside_pct": 0.111,
  "warnings": [...],
  "narrative": "..."
}
```

## Example — Gordon model

```python
result = execute(
    current_dividend_per_share=2.00,
    cost_of_equity=0.09,
    method="gordon",
    gordon_growth=0.04,
)
# P0 = 2.00 * 1.04 / (0.09 - 0.04) = 2.08 / 0.05 = 41.60
assert abs(result["price_per_share"] - 41.60) < 0.01
```

## Related helpers

- **`cost_of_capital_builder`**: must run first; output `cost_of_equity` field is the Re input.
- **`dcf_engine`**: FCFF-based alternative; use as primary for non-dividend payers or high-reinvestment names.
- **`justified_multiples`**: derives P/E and P/B from the same growth and payout assumptions.
- **`reit_valuation_panel`**: AFFO-based primary valuation for REITs; DDM is the cross-check.
- **`price_target_blender`**: combine DDM output with DCF and comps into a single blended target.
