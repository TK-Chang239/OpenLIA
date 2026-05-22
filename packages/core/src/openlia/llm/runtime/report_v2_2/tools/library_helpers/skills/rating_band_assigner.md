---
name: rating_band_assigner
category: decision
version: 1.0.0
produces_artifacts:
  - rating_assignment
consumes_artifacts: []
---

# rating_band_assigner — ETR + R/R to Rating Recommendation

## Purpose

Map expected total return (ETR) and risk/reward ratio (R/R) to a formal rating
recommendation (BUY / OUTPERFORM / HOLD / UNDERPERFORM / SELL) with a conviction
modifier (high / medium / low) and an explanatory narrative.

This is the terminal step in the decision-layer chain:
`price_target_blender` → `expected_total_return` + `risk_reward_calculator`
→ **`rating_band_assigner`**

## When to use

- After computing ETR via `expected_total_return` and R/R via `risk_reward_calculator`.
- Whenever the report requires a formal rating with a conviction level.
- When the house methodology has different band thresholds — supply `rating_bands_config`.

## When NOT to use

- Without ETR and R/R from the other decision helpers — the rating will be
  mechanically correct but analytically hollow.
- As a portfolio-level aggregator — this helper is single-stock only.

## Default rating bands

| Rating | ETR threshold | R/R threshold | Notes |
|---|---|---|---|
| BUY | ETR >= +15% | R/R >= 1.5x | Both conditions required. |
| OUTPERFORM | ETR >= +5% | R/R >= 1.2x | Both conditions required. BUY checked first. |
| HOLD | -5% <= ETR < +7% | — | No R/R requirement; ETR range catch-all. |
| UNDERPERFORM | ETR < -5% | R/R < 1.5x | Both conditions required. |
| SELL | ETR < -15% | — | ETR alone sufficient. Also: R/R < 0.8x AND ETR < 0. |

Evaluation order: SELL → BUY → OUTPERFORM → UNDERPERFORM → HOLD (default).

## Calibration for user-supplied risk tolerance

Pass `rating_bands_config` to adjust thresholds for house style:

```json
{
  "buy":          {"etr_min": 0.20, "rr_min": 2.0},
  "outperform":   {"etr_min": 0.10, "rr_min": 1.5},
  "hold":         {"etr_min": -0.05, "etr_max": 0.10},
  "underperform": {"etr_max": -0.05, "rr_max": 1.5},
  "sell_etr":     {"etr_max": -0.20},
  "sell_rr":      {"rr_max": 0.7, "etr_max": 0.0}
}
```

Each sub-key is optional; omit any you don't want to override (defaults apply).

## Conviction modifier logic

Conviction is a heuristic, not a hard threshold. It informs the reader about
confidence in the rating, not whether to act on it.

| Conviction | Condition |
|---|---|
| high | `conviction_score >= 0.65` AND `R/R >= 2.0` AND `dispersion CV <= 15%` |
| low | `conviction_score < 0.35` OR `R/R < 1.0` OR `dispersion CV > 15%` |
| medium | all other cases |

Where `dispersion CV = dispersion_stdev / blended_target` (only when both are supplied).

Supply `conviction_score` from `price_target_blender.confidence_score`:
```
conviction_score = price_target_blender_output["confidence_score"]
```

Or compute it from other signals: Piotroski F-score, DCF TV concentration, business
quality panel, insider transaction direction. The helper treats it as an opinionated
input — it does not derive conviction internally.

## When to override the mechanical mapping with judgment

The bands are a heuristic framework, not an infallible rule. Override when:

1. **The company is undergoing a structural change** (spin-off, regulatory event,
   management transition) that makes near-term ETR a poor proxy for investment merit.
   Document the override in the report's risk section.

2. **The R/R threshold is met but on a very small base** — e.g., upside 16%, downside
   8%, ratio 2.0x but both are small absolute movements. In this case, a BUY is
   mathematically correct but the conviction should be medium, not high.

3. **Industry convention differs from the default bands** — some sectors (pharma binary
   catalysts, cyclicals at trough) use wider ETR bands. Use `rating_bands_config` to
   align.

4. **ETR is computed on a longer-than-12-month horizon** — use the annualized ETR
   (`annualized_etr_pct` from `expected_total_return`) rather than raw ETR for the
   band comparison when horizon > 18 months.

## Why the bands are not a hard rule

The rating bands encode a useful starting point for organizing the investment case,
not a binding commitment. An analyst with high conviction that a name is fundamentally
mispriced can assign a BUY at 12% ETR if the risk/reward is sufficiently asymmetric
and the conviction evidence is strong. The `rating_bands_config` parameter exists
precisely to allow this calibration.

The verifier will flag `SELL` with ETR > +10% or `BUY` with ETR < 0 as an internal
inconsistency — these combinations indicate either a band misconfiguration or an
override that should be documented in `why_this_rating`.

## Output shape (key fields)

```json
{
  "rating": "BUY",
  "conviction": "high",
  "expected_total_return_pct": 0.18,
  "risk_reward_ratio": 2.5,
  "conviction_score": 0.72,
  "why_this_rating": "ETR +18% exceeds +15% BUY threshold; R/R 2.5x clears 1.5x minimum; conviction 0.72.",
  "narrative": "BUY-rated (high conviction). ETR +18% over 12-month horizon. R/R 2.5x.",
  "alternative_ratings_considered": [],
  "warnings": []
}
```

## Related helpers

- **`expected_total_return`**: produces `expected_total_return_pct` required here.
- **`risk_reward_calculator`**: produces `risk_reward_ratio` required here.
- **`price_target_blender`**: produces `confidence_score` to pass as `conviction_score`.
- **`implied_upside_downside`**: lightweight alternative when only PT + bear case exist;
  its `risk_reward_ratio` output can feed this helper directly.
