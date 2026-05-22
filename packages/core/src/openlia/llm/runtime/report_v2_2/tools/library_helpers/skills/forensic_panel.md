---
name: forensic_panel
category: forensic
version: 0.1.0
produces_artifacts:
  - forensic_panel_output
consumes_artifacts:
  - one_time_item_output
  - quality_of_earnings_output
  - sbc_intensity_output
---

# forensic_panel — Composite Forensic Concern Score

## Purpose

Aggregate four forensic sub-signals into a single 0-100 composite concern score
(higher = worse). The four signals are:

1. **One-time item intensity** (weight 25%) — based on pct_of_net_income from
   `one_time_item_identification`. Impairments, restructurings, gain/loss on sale.
2. **Accruals / QoE** (weight 30%) — accruals_pct_of_ni and Sloan ratio from
   `quality_of_earnings_panel`. High accruals signal earnings outrunning cash.
3. **SBC intensity** (weight 20%) — sbc_pct_revenue from `sbc_intensity`.
   SBC > 10% of revenue scores maximum on this component.
4. **Channel-stuffing signal** (weight 25%) — YoY change in AR/Revenue ratio.
   Rapid AR growth relative to revenue can signal stuffing or collection issues.

## Concern Levels

| Score | Level |
|---|---|
| 0-25 | low |
| 26-50 | moderate |
| 51-75 | elevated |
| 76-100 | high |

## Workflow

Always run constituent helpers before calling forensic_panel:

```
1. one_time_item_identification(...) -> one_time_output
2. quality_of_earnings_panel(...) -> qoe_output
3. sbc_intensity(...) -> sbc_output
4. forensic_panel(
       one_time_item_output=one_time_output,
       quality_of_earnings_output=qoe_output,
       sbc_intensity_output=sbc_output,
       ar_current=..., ar_prior=...,
       revenue_current=..., revenue_prior=...
   )
```

Pass any subset of the four inputs. Missing inputs default to 0 for that signal.
If all four are None/0, the composite score will be 0.

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `one_time_item_output` | `dict \| None` | No | Output from `one_time_item_identification`. |
| `quality_of_earnings_output` | `dict \| None` | No | Output from `quality_of_earnings_panel`. |
| `sbc_intensity_output` | `dict \| None` | No | Output from `sbc_intensity`. |
| `ar_current` | `float` | No | AR balance, current period. |
| `ar_prior` | `float` | No | AR balance, prior period. |
| `revenue_current` | `float` | No | Revenue, current period. |
| `revenue_prior` | `float` | No | Revenue, prior period. |

## Output

```json
{
  "composite_score": 42.3,
  "concern_level": "moderate",
  "signal_scores": {
    "one_time_items": 15.0,
    "accruals": 65.0,
    "sbc_intensity": 30.0,
    "channel_stuffing": 20.0
  },
  "signal_weights": {"one_time_items": 0.25, "accruals": 0.30, "sbc_intensity": 0.20, "channel_stuffing": 0.25},
  "signal_contributions": {"accruals": 19.5, ...},
  "top_signals": [
    {"signal": "accruals", "contribution": 19.5},
    {"signal": "channel_stuffing", "contribution": 5.0}
  ]
}
```

## When NOT to Use

- Individual signal investigation — call the constituent helper directly.
- Credit/solvency distress prediction — use `ft_altman_z_score`.
- Beneish M-Score (PR 2.6) — a separate multi-ratio model for earnings manipulation.
