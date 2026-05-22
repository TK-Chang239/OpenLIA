---
name: statement_integrity_bundle
category: statement_integrity
version: 0.1.0
produces_artifacts:
  - statement_integrity_bundle_output
consumes_artifacts:
  - altman_z_variants_output
  - beneish_m_score_output
  - cross_statement_validation_output
  - one_time_item_output
---

# statement_integrity_bundle

Also documented as: `statement_integrity_panel` (design supplement §14 alias).
Both names refer to this helper; the registered name is `statement_integrity_bundle`
per the 18-list in schema-and-skills §6 (#15).

## Purpose

Compose four forensic sub-panels into a single 0-100 statement integrity score
(higher = better integrity). The bundle provides a unified drafter-facing view of:

1. **Altman Z variants** (weight 25%) — point-in-time bankruptcy/distress risk
2. **Beneish M-score** (weight 30%) — earnings manipulation probability
3. **Cross-statement validation** (weight 25%) — IS/BS/CFS coherence
4. **One-time item identification** (weight 20%) — non-recurring item distortion

## When to Use This Bundle vs. Individual Helpers

Use the **bundle** when:
- Writing an initiation or update report and a single integrity section is needed.
- All four sub-panels have already been materialized and aggregation adds value.
- The section plan specifies `statement_integrity_bundle_output` as the artifact.

Use **individual helpers** when:
- Deep forensic investigation of a single signal (e.g., TATA is the highest Beneish driver).
- Only one signal is relevant (e.g., dividend-safety name with no manipulation concern).
- A prior bundle run flagged a specific concern and the drafter needs detail.

## Composite Scoring Methodology

### Component scores (0-100, higher = better integrity)

| Component | Score logic |
|---|---|
| `altman_z` | safe → 90; gray → 55; distress → 15; missing → 50 |
| `beneish` | no_signal → 85; likely_manipulator → 15; missing → 50 |
| `cross_statement` | 0 flags → 90; 1 flag → 65; 2+ flags → 30; missing → 50 |
| `one_time_items` | < 5% of NI → 90; 5-20% → 65; > 20% → 30; missing → 50 |

### Composite formula

```
composite = 0.25 * altman_score
          + 0.30 * beneish_score
          + 0.25 * cross_statement_score
          + 0.20 * one_time_item_score
```

### Classification bands

| Score | Classification |
|---|---|
| 75-100 | high_integrity |
| 50-74 | moderate_integrity |
| 0-49 | low_integrity |

Weights and bands are opinionated. Treat the output as an advisory signal, not a
hard verdict. Narrative must use conditional language: "multiple integrity signals
suggest investigation" rather than "avoid this name."

## Common False Positives

1. **High Beneish M, legitimate growth spike**: Rapid organic growth raises SGI and
   DSRI without manipulation. Always check whether the revenue-to-AR ratio movement
   is consistent with business model (e.g., SaaS billing cycles, seasonality).

2. **Altman Z in gray zone for asset-light tech**: Z uses Sales/TA; low asset base
   inflates the ratio but this is structural. Use Z" (non-manufacturer variant) for
   tech companies, not Z.

3. **Cross-statement flag from IFRS 16 adoption**: Operating lease capitalization
   changes retained-earnings reconciliation. One-period flags at IFRS 16 adoption
   year are expected; mark as structural if repeatable.

4. **One-time items from acquisition accounting**: M&A-related amortization and
   purchase-price adjustments inflate the non-recurring item score. Distinguish
   recurring-nature PPA amortization from true one-time restructuring.

## Workflow

Always run constituent helpers before calling the bundle:

```
1. altman_result = altman_z_variants(
       working_capital=..., retained_earnings=..., ebit=...,
       book_value_equity=..., book_value_total_liabilities=...,
       total_assets=..., variant="z_double_prime", sales=None
   )

2. beneish_result = beneish_m_score(
       accounts_receivable_t=..., accounts_receivable_t1=...,
       revenue_t=..., revenue_t1=...,
       gross_profit_t=..., gross_profit_t1=...,
       ...all 20 inputs...
   )

3. csv_result = cross_statement_validation(
       net_income=..., retained_earnings=..., ...
   )

4. oti_result = one_time_item_identification(
       items=[...]
   )

5. bundle = statement_integrity_bundle(
       altman_z_output=altman_result,
       beneish_m_output=beneish_result,
       cross_statement_output=csv_result,
       one_time_item_output=oti_result,
   )
```

All four inputs are optional. Missing inputs default to a neutral score of 50.
The composite degrades gracefully: a three-panel bundle is valid if one helper
could not be run (e.g., market cap unavailable for Altman Z).

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `altman_z_output` | `dict \| None` | No | Output from `altman_z_variants`. |
| `beneish_m_output` | `dict \| None` | No | Output from `beneish_m_score`. |
| `cross_statement_output` | `dict \| None` | No | Output from `cross_statement_validation`. |
| `one_time_item_output` | `dict \| None` | No | Output from `one_time_item_identification`. |

## Output

```json
{
  "composite_statement_integrity_score": 72,
  "classification": "moderate_integrity",
  "component_scores": {
    "altman_z": 55.0,
    "beneish": 85.0,
    "cross_statement": 90.0,
    "one_time_items": 65.0
  },
  "component_weights": {
    "altman_z": 0.25,
    "beneish": 0.30,
    "cross_statement": 0.25,
    "one_time_items": 0.20
  },
  "top_concerns": [
    "Altman Z in gray zone (score 2.45)"
  ],
  "warnings": [
    "[beneish] TATA uses NI - CFO proxy (modern convention). ..."
  ]
}
```

## Interpretation Guide

- **high_integrity (75+)**: No bankruptcy signal, no manipulation signal, statements
  reconcile, one-time items < 5% of NI. Proceed with standard analysis.
- **moderate_integrity (50-74)**: At least one signal warrants investigation. Identify
  the lowest component score and drill into that helper's full output.
- **low_integrity (< 50)**: Multiple signals. Flag in the report summary. Use the
  `top_concerns` list to prioritize. Recommend auditor review in the risks section.

## Artifact Fidelity Guidelines

At HEADLINE fidelity, surface only the composite score and classification.
At SUMMARY fidelity, include the four component scores.
At FULL fidelity, include all component scores, top concerns, and pass through
sub-panel narratives via their own `to_markdown(FULL)` renders.
