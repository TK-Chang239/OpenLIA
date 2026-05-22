---
name: justified_multiples
category: alternative_valuation
version: 1.0.0
produces_artifacts:
  - justified_multiples_output
consumes_artifacts:
  - cost_of_capital_output
---

# justified_multiples — Fundamental-Derived Justified Trading Multiples

## Purpose

Derive the multiples a company *should* trade at given its fundamentals —
return on equity (ROE), long-run growth (g), dividend payout ratio, and cost
of equity (Re) — and compare those justified multiples against actual current
trading multiples. Answers the question: "Is this stock expensive because of
quality, or is it genuinely overvalued?" Pairs with `comparables.run` to
distinguish "cheap vs. peers" from "cheap vs. fundamentals."

## When to use

- Initiation and update reports: valuation triangulation alongside DCF and comps.
- Sector cross-company ranking: sort by justified-vs-actual spread to identify
  under- and over-rated names within a peer set.
- Post-results updates: when ROE, growth, or payout changes, the justified
  multiple shifts — use this helper to quantify the re-rating signal.
- When the question is "what P/E does a 15% ROE, 4% growth, 50% payout business deserve?"

## When NOT to use

- Pre-dividend or zero-payout companies where forward P/E derivation breaks down.
  Use `dcf_engine` or `comparables.run` instead.
- Companies where `g > ROE` — the sustainable-growth identity breaks down
  (implied payout is negative). The helper raises immediately; fix g or ROE inputs.
- EV/EBITDA for capital-intensive cyclicals mid-capex cycle — the approximation
  formula assumes stable capital structure; pass `capex_volatility_signal=True`
  to trigger the warning and prefer `dcf_engine`.
- As the sole valuation method: justified multiples anchor the *quality premium*
  but do not independently derive intrinsic value. Always pair with DCF or DDM.

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `cost_of_equity` | `float` | Yes | Re from `cost_of_capital_builder`. |
| `growth` | `float` | Yes | Long-run sustainable growth rate (g). Must be < Re and <= ROE. |
| `roe` | `float` | Yes | Return on equity. Required for P/B and forward P/E derivation. |
| `payout_ratio` | `float` | No | Dividend payout ratio. Derived from `1 - g/ROE` if not supplied. |
| `roic` | `float` | No | Return on invested capital. Informational for EV/EBITDA inputs. |
| `wacc` | `float` | No | WACC. Required for EV/EBITDA justified multiple. |
| `tax_rate` | `float` | No | Effective/marginal tax rate. Required for EV/EBITDA. |
| `reinvest_rate` | `float` | No | Reinvestment rate. Required for EV/EBITDA. |
| `capex_volatility_signal` | `bool` | No (False) | Set True if capital intensity is shifting — triggers capital-intensity warning on EV/EBITDA. |
| `current_multiples` | `dict` | No | Actual current multiples for spread computation. |
| `multiples_to_compute` | `list[str]` | No | Subset to compute; default: all four. |

## Methodology

### Forward P/E

```
forward_PE = payout / (Re - g)
```

Derived from the DDM identity: if P = D1 / (Re - g) and D1 = EPS * payout,
then P/EPS (forward P/E) = payout / (Re - g).

The payout ratio can be derived from the sustainable growth identity:
```
g = ROE * (1 - payout)  =>  payout = 1 - g/ROE
```

This imposes internal consistency: high growth forces low payout, which
correctly lowers the justified P/E.

### Trailing P/E

```
trailing_PE = payout * (1 + g) / (Re - g) = forward_PE * (1 + g)
```

### P/B (Price-to-Book)

```
PB = (ROE - g) / (Re - g)
```

Derived from `P = BV * (ROE - g) / (Re - g)`. Key insight:
- If ROE > Re: P/B > 1 (value creation above cost of equity).
- If ROE = Re: P/B = 1 regardless of growth (no excess returns).
- If ROE < Re: P/B < 1 (value destruction).

This is the cleanest expression of value creation: growth only adds value when
ROE > Re.

### EV/EBITDA (approximation — decision #17)

```
EV/EBITDA ≈ (1 - tax_rate) * (1 - reinvest_rate) / (WACC - g)
```

This is an approximation that holds when capital intensity is stable.
The exact derivation chains EV/IC = (ROIC - g) / (WACC - g) through
IC/EBITDA, but the IC/EBITDA ratio requires stable depreciation and tax
assumptions.

**Warning fires when `capex_volatility_signal=True`:**
> "When capital intensity (capex/EBITDA) is shifting materially, this
> formula is approximate. Prefer DCF for capital-intensive cyclicals."

Detail code: `g_exceeds_re` (if g >= Re, raises immediately).

### Spread computation

```
spread_pct = (actual - justified) / justified
```

Verdict bands:
- `|spread| < 5%` — "in line"
- `5% <= |spread| < 20%` — "modest premium/discount"
- `20% <= |spread| < 50%` — "material premium/discount"
- `|spread| >= 50%` — "extreme premium/discount"

## Common pitfalls

1. **g >= Re raises immediately.** Justified multiple formulas diverge. Common
   cause: using a nominal growth rate of 8% but a real-rate-based Re of 7%.
   Check that both are in the same terms (nominal vs. nominal, real vs. real).

2. **g > ROE raises immediately.** The sustainable-growth identity implies
   negative payout, which is economically nonsensical. Fix: either reduce g
   (long-run growth cannot indefinitely exceed return on equity) or verify
   the ROE figure is forward-looking rather than a depressed historical year.

3. **P/B justified < 1 does not mean P/B = 0.** When ROE < Re, justified P/B
   is between 0 and 1. This is not a valuation floor — the company could be
   worth less than book if losses continue. The justified multiple is the
   value-neutral anchor, not a downside bound.

4. **Forward P/E vs. trailing P/E choice.** Use forward P/E when comparing
   against consensus NTM estimates. Use trailing P/E when the company's
   forward estimates are unreliable (distressed names, cyclical trough).
   The two multiples differ by `(1 + g)` — for a 4% growth company they are
   nearly identical; for a 20% growth name the gap matters.

5. **EV/EBITDA approximation for banks or REITs.** Banks have no EBITDA
   (interest expense is revenue, not cost). REITs use AFFO. Do not apply
   EV/EBITDA justified multiples to these sectors; use sector-specific panels.

6. **Spread sign convention.** `spread_pct > 0` means the stock trades at a
   *premium* to its justified multiple (actual > justified). A premium can be
   legitimate if the market prices in future ROE improvement not yet in the
   fundamentals input — or it can be genuine overvaluation. Never mechanically
   read positive spread as a short signal.

## Output shape (key fields)

```json
{
  "fundamentals_used": {"cost_of_equity": 0.10, "growth": 0.04, "roe": 0.15, "payout_ratio": 0.733},
  "justified_multiples": {
    "forward_pe": {"value": 14.67, "formula": "payout / (Re - g) = 0.733 / 0.06"},
    "trailing_pe": {"value": 15.25, "formula": "payout * (1 + g) / (Re - g)"},
    "pb":          {"value": 1.83,  "formula": "(ROE - g) / (Re - g) = 0.11 / 0.06"},
    "ev_ebitda":   {"value": null,  "reason": "Insufficient inputs..."}
  },
  "actual_multiples": {"forward_pe": 16.0, "pb": 2.10},
  "spreads": {
    "forward_pe": {"justified": 14.67, "actual": 16.0, "spread_pct": 0.091, "verdict": "modest premium"},
    "pb":         {"justified": 1.83,  "actual": 2.10, "spread_pct": 0.148, "verdict": "modest premium"}
  },
  "warnings": [],
  "narrative": "Justified forward P/E: 14.7x. Justified P/B: 1.83x. ..."
}
```

## Worked example — P/E and P/B

```python
# payout = 0.5, Re = 10%, g = 4%
result = execute(
    cost_of_equity=0.10,
    growth=0.04,
    roe=0.15,
    payout_ratio=0.50,
)
# forward_PE = 0.50 / (0.10 - 0.04) = 0.50 / 0.06 = 8.33
assert abs(result["justified_multiples"]["forward_pe"]["value"] - 8.33) < 0.01
# P/B = (0.15 - 0.04) / (0.10 - 0.04) = 0.11 / 0.06 = 1.833
assert abs(result["justified_multiples"]["pb"]["value"] - 1.833) < 0.01
```

## Related helpers

- **`cost_of_capital_builder`**: must run first; Re and WACC from its output.
- **`comparables.run`**: actual peer multiples; pass `current_multiples` from its output.
- **`ddm_family`**: uses the same growth and payout assumptions to compute absolute value.
- **`dcf_engine`**: absolute valuation as primary; justified multiples as triangulation check.
- **`price_target_blender`**: combine justified-multiple-implied prices with DCF and DDM outputs.
