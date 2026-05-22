---
name: price_target_blender
category: decision
version: 1.0.0
produces_artifacts:
  - price_target_blended
consumes_artifacts: []
---

# price_target_blender — Weighted Blend of Per-Methodology Price Targets

## Purpose

Combine two to six per-methodology price targets (DCF, DDM, comparables, SOTP,
justified multiples, analyst consensus) into a single blended price target with
explicit weights, dispersion statistics, and a confidence score. The blended target
feeds `expected_total_return`, `implied_upside_downside`, `rating_band_assigner`,
and `football_field_chart`.

## When to use

- After running two or more absolute/relative valuation helpers and needing a single PT.
- When the report methodology section requires a weighted-average price target.
- When you want an explicit confidence score to inform conviction in `rating_band_assigner`.
- As the upstream input to the full decision-layer chain.

## When NOT to use

- When only one methodology has been run — return that value directly; the blender
  adds no information over a single-method target.
- When probabilities are the correct weighting mechanism — use `scenario_weighting`
  instead (e.g., 60% base / 30% bear / 10% bull DCF scenario weighting).
- When you want to express a range rather than a point — output the `dispersion`
  field and pass min/max into `football_field_chart`.

## Required prior step

Run at least two of: `dcf_engine`, `ddm_family`, `comparables.run`, `sotp_builder`,
`justified_multiples`. Pass each helper's implied per-share value as a `value` entry.

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `methodology_targets` | `list[dict]` | Yes | List of {name, value, weight, source_artifact_id}. |
| `auto_weight` | `str` | No (default `"equal"`) | `"equal"` for 1/N weighting; `"none"` to use provided weights. |

### `methodology_targets` item schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `str` | Yes | Human-readable label, e.g. "DCF perpetuity". |
| `value` | `float \| None` | Yes | Implied per-share value. `None` = excluded and weights renormalized. |
| `weight` | `float \| None` | Conditional | Required when `auto_weight="none"`. Ignored when `auto_weight="equal"`. |
| `source_artifact_id` | `str \| None` | No | Upstream artifact ID for provenance. |

## Weight calibration by company quality

The mechanical equal-weight default (`auto_weight="equal"`) is the right starting
point. Override only when there is strong methodological rationale:

**High-quality compounders (ROIC >> WACC, long reinvestment runway):**
- DCF: 40–50% weight. Intrinsic value is well-defined when a long competitive moat
  can be modeled.
- Comparables: 30–40%. Use as a sanity check, not the anchor.
- DDM: 10–20% for dividend payers; 0% for non-payers.

**Cyclicals, commodities, capital-intensive businesses:**
- Comparables: 40–50%. Through-cycle multiples are a better anchor than terminal-
  value-heavy DCF.
- DCF: 30–40% with an exit-multiple terminal value (not perpetuity growth).
- SOTP: useful if the business has separable asset pools.

**Pre-revenue or high-uncertainty growth names:**
- DCF with explicit scenario weighting: 50–60%.
- Comparables on EV/Sales or EV/NTM revenue: 40–50%.
- DDM: not applicable.

**REITs, banks, insurance:**
- Sector-specific methodologies (`reit_valuation_panel`, `banks_sector_panel`,
  `insurance_ev_panel`) should dominate (60–80%).
- Generalist DCF / P/E comps can provide a cross-check at lower weights.

## Dispersion narrative

The blender computes `stdev` (population standard deviation over the live methods)
and `spread_pct_of_blended` (max–min / blended target).

When `spread_pct_of_blended > 0.50` (50%), the blender flags `high_dispersion`.
**Do not suppress this warning.** The drafter should explain in prose why methods
disagree so strongly (e.g., DCF is TV-heavy and sensitive to terminal growth;
comparables peers may have a premium structural growth rate relative to the subject).

When `stdev / blended < 0.05` (tight cluster), the confidence score is near 1.0
and conviction can be upgraded to `high` in `rating_band_assigner`.

## When to refuse a blend

Do not call `price_target_blender` if:
1. Only one methodology produced a valid (non-null) value — just use that value.
2. The methodologies are measuring different things that should not be averaged
   (e.g., an NAV estimate and a P/E-implied value for the same REIT — they are
   the same methodology from different angles, not independent methods).
3. The spread is so wide that the median is misleading — surface the range instead
   and let the reader interpret.

## Common pitfalls

1. **Passing confidence-score-as-weight without documentation.** If you use
   `auto_weight="none"` and derive weights from `conviction_score`, record the
   derivation in `source_artifact_id` or the narrative.

2. **Null-value DDM for a non-dividend payer included with a weight.** The blender
   drops null values and renormalizes, so the non-zero weight you assigned to DDM
   is silently redistributed. Always check the `weight_audit.reweighted` flag.

3. **Single dominant method.** A weight > 80% on any one method triggers a warning.
   If you genuinely believe one methodology is the only valid one, skip the blender.

## Output shape (key fields)

```json
{
  "blended_target": 113.7,
  "method_breakdown": [
    {"name": "DCF perpetuity", "value": 120, "weight": 0.50, "weighted_contribution": 60},
    {"name": "Comparables P/E", "value": 108, "weight": 0.50, "weighted_contribution": 54}
  ],
  "weight_audit": {"sum": 1.0, "auto_weight_applied": true, "methods_dropped": 0},
  "dispersion": {"min": 108, "max": 120, "stdev": 6.0, "spread_pct_of_blended": 0.105},
  "confidence_score": 0.67,
  "warnings": [],
  "narrative": "Blended price target $113.70 across 2 methods..."
}
```

## Related helpers

- **`dcf_engine`**: primary absolute valuation input.
- **`ddm_family`**: dividend-based valuation input for yield-paying names.
- **`comparables.run`**: relative valuation input; use `blended_range.median` as value.
- **`sotp_builder`**: segment-level valuation input.
- **`expected_total_return`**: consumes `blended_target` directly.
- **`football_field_chart`**: consumes min/median/max from `dispersion` + `blended_target`.
- **`rating_band_assigner`**: consumes `confidence_score` via `conviction_score` input.
