# Helper manifest classification (PR 8.0 deliverable)

Each existing helper in `packages/core/src/openlia/llm/runtime/report_v2/facts/helpers/` is classified
as either `simple` (signature inline in the manifest — no `get_helper_docs` inspect path needed) or
`complex` (one-liner in manifest; full doc lives at `doc_path`). The classification drives the PR 8a
registration and feeds the dogfood eval loop.

Rule of thumb:
- **simple** — pure passthrough math, no unit conventions to remember, signature is self-documenting
- **complex** — bounded inputs, unit conventions (percent vs fractional), multiple usage patterns, or
  combines outputs from other helpers

## Liquidity (`facts/helpers/liquidity.py`)

| Helper | Class | Reason |
|---|---|---|
| `net_cash` | simple | cash + ST investments − debt; one line of math |
| `current_ratio` | simple | current_assets / current_liabilities |
| `quick_ratio` | simple | (current_assets − inventory) / current_liabilities |
| `debt_to_equity` | simple | total_debt / equity |
| `interest_coverage` | simple | EBIT / interest_expense |
| `cash_runway_quarters` | simple | cash / quarterly burn |

## Returns (`facts/helpers/returns.py`)

| Helper | Class | Reason |
|---|---|---|
| `roe_ttm_computed` | simple | net_income / equity |
| `roic_ttm_computed` | simple | NOPAT / invested_capital |
| `fcf_yield_computed` | simple | FCF / market_cap |
| `fcf_margin` | simple | FCF / revenue |
| `margin_bridge` | complex | multi-period spread decomposition; benefits from worked example |

## Valuation (`facts/helpers/valuation.py`)

| Helper | Class | Reason |
|---|---|---|
| `peer_multiple_implied_range` | complex | which multiples, which percentiles, how to weight |
| `historical_pe_band` | complex | lookback window choice, σ-band conventions |
| `peg_ratio_correct` | complex | forward_eps_growth_pct in PERCENT units (rejects >200) |
| `dcf_intrinsic_value` | complex | bounded WACC [5,20%], TGR [0,4%], tax [0,40%], capex/rev [0,30%], path [5,10]y |
| `sum_of_parts` | complex | per-segment multiple assignment, holding-company haircut |
| `reverse_dcf` | complex | inverts the DCF — needs example of when to reach for it vs forward DCF |
| `football_field` | complex | combines outputs of peer_multiple, historical_pe, sourced sell-side |
| `sensitivity_grid` | complex | which two dimensions to vary, step size, base case |

## Forecast (`facts/helpers/forecast.py`)

| Helper | Class | Reason |
|---|---|---|
| `forecast_table` | complex | scenario assumption shape, growth-vs-margin path conventions |
| `actual_vs_consensus` | simple | line-by-line delta table |
| `consensus_vs_assumptions_table` | simple | pairs consensus row with assumption row |

## Working capital (`facts/helpers/working_capital.py`)

| Helper | Class | Reason |
|---|---|---|
| `cycle_days` | simple | DSO/DIO/DPO/CCC — all four returned together; standard formula |

## SaaS (`facts/helpers/saas.py`)

| Helper | Class | Reason |
|---|---|---|
| `rule_of_40` | simple | growth_pct + fcf_margin_pct |
| `nrr_trend` | simple | quarter-by-quarter NRR series |

## Distressed (`facts/helpers/distressed.py`)

| Helper | Class | Reason |
|---|---|---|
| `debt_maturity_wall` | complex | bucketing by year, ranking conventions |
| `recovery_waterfall` | complex | seniority ordering, recovery rate inputs |

## SBC dilution (`facts/helpers/sbc_dilution.py`)

| Helper | Class | Reason |
|---|---|---|
| `sbc_dilution_bridge` | complex | gross issuances minus buybacks; treasury method conventions |

---

## Summary

- **Simple (signature inline in manifest):** 14 helpers
- **Complex (one-liner + `get_helper_docs`):** 11 helpers
- **Total:** 25 helpers

This partition is the input to PR 8a's `@register_helper(..., complexity=...)` decorations.

## Dogfood eval loop (planned, runs externally)

The eval script lives at `planning/manifest-dogfood/eval.py` (scaffold below). It:

1. Loads the manifest strings the PR 8a registration emits.
2. Iterates over a fixture of ~20 real section briefs (drawn from existing equity reports + the
   Chinese 28-section sample).
3. For each brief, calls Claude (Anthropic SDK) with the prompt:
   > "Given this section brief, which helpers (if any) would you call? List by name with a
   > one-sentence justification."
4. Captures the model's selections and compares against the human-authored ground truth.
5. Reports disagreement, focusing on ambiguous cases between sibling helpers (the contrast-set
   rule from the design discussion).

The eval is not part of the test suite — it's interactive and requires an Anthropic API key.
Output drives iterative refinement of the `summary` and `use_when` hints before PR 8a freezes
the manifest content.
