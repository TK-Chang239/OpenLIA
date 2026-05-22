---
name: sotp_builder
category: alternative_valuation
version: 1.0.0
produces_artifacts:
  - sotp_output
consumes_artifacts: []
---

# sotp_builder — Sum-of-the-Parts Valuation

## Purpose

Build a sum-of-the-parts valuation for conglomerates, holding companies, and
multi-segment businesses where each operating segment warrants its own valuation
method. Values each segment independently (EBITDA multiple, P/S, P/B, DCF, or
analyst-supplied), sums the segment enterprise values, applies corporate overhead
deduction and an optional conglomerate discount, then bridges to equity value by
deducting net debt and minority interest.

## When to use

- Initiation reports for conglomerates or holding companies.
- Post-restructuring updates (spin-off, acquisition, divestiture) where the
  segment mix has changed and segment-level multiples differ materially.
- When segments carry different growth/risk profiles — e.g., an industrial arm
  valued at 8x EBITDA alongside a software arm valued at 5x revenue.
- Activist or strategic scenario analysis involving segment monetization:
  SOTP is the floor value for a "break-up" case.

## When NOT to use

- Single-segment companies — direct `dcf_engine` or `comparables.run` is simpler
  and more transparent. The helper flags `single_segment: true` but runs anyway.
- Companies that do not disclose segment-level financials — segment EVs become
  unanchored and the SOTP precision is spurious.
- When all segments are in the same industry with similar growth/risk — comps or
  DCF applied at the consolidated level will produce equally reliable results with
  less structural complexity.
- As the only valuation: SOTP establishes a sum-of-parts anchor, not intrinsic
  value — always triangulate with DCF or comparables on the consolidated entity.

## Segment valuation methods

| Method | Computes | Notes |
|---|---|---|
| `ebitda_multiple` | `metric_value * multiple` | Refuses if metric_value < 0 (raises). |
| `peer_ps` | `revenue * ps_multiple` | Useful for high-growth segments with negative EBITDA. |
| `peer_pe` | `net_income * pe_multiple` | Equity multiple — ensure segment debt excluded from net_debt or bridge double-counts. |
| `book_value` | `book_value * multiple` | Regulated equity arms; default multiple 1.0. |
| `dcf` | `method_inputs["enterprise_value"]` | Run `dcf_engine` for the segment first; pass EV into method_inputs. |
| `user_supplied` | `method_inputs["value"]` | Analyst override; narrative cites source. |

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `segments` | `list[dict]` | Yes | List of segment definitions (see structure below). |
| `shares_outstanding` | `float` | Yes | Diluted shares for per-share computation. |
| `net_debt` | `float` | No (0) | Consolidated net debt (total_debt - cash). |
| `corporate_overhead` | `float` | No | Annual unallocated HQ cost (EBITDA basis). Capitalized at the overhead multiple. |
| `corporate_overhead_capitalization_multiple` | `float` | No (8.0) | Multiple applied to overhead to derive EV deduction. |
| `non_operating_assets` | `float` | No (0) | Equity-method investments, excess cash, real estate outside segments. |
| `minority_interest` | `float` | No (0) | Non-controlling interest at fair value. |
| `conglomerate_discount_pct` | `float` | No (0) | Empirical discount (Berger-Ofek 1995: 10-15%). |
| `tax_on_segment_sale` | `bool` | No (False) | Emit a friction warning if True. |
| `current_price` | `float` | No | For implied upside/downside. |

### Segment dict structure

```python
{
    "name": "Industrials",
    "valuation_method": "ebitda_multiple",   # required
    "metric_value": 28000.0,                 # EBITDA/revenue/book/NI depending on method
    "method_inputs": {"multiple": 8.5},      # method-specific
    "ownership_pct": 1.0,                    # default 1.0; 0.80 for 80%-owned subsidiary
    "control_premium_or_discount": None,     # e.g. 0.20 for 20% control premium
    "comparable_set": ["EMR", "PH", "ROK"],  # informational
}
```

## Methodology

### Per-segment EV

Each segment's raw EV is computed by its method (see table above), then adjusted:

```
segment_ev_adjusted = segment_ev_raw * ownership_pct * (1 + control_premium_or_discount)
```

Default ownership_pct = 1.0; default control_premium_or_discount = None (no adjustment).

### Corporate overhead deduction

Segments typically report EBITDA *excluding* unallocated corporate costs (e.g.,
group CEO, central finance, legal). The overhead must be capitalized and subtracted:

```
overhead_capitalized = corporate_overhead * corporate_overhead_capitalization_multiple
adjusted_sum_ev = sum_segment_ev - overhead_capitalized
```

### Conglomerate discount

The empirical literature (Berger & Ofek 1995) finds conglomerates typically trade
at a 10-15% discount to their SOTP value due to managerial inefficiency, cross-
subsidization, and investor preference for pure-play exposure.

```
post_discount_ev = adjusted_sum_ev * (1 - conglomerate_discount_pct)
```

Default is 0% (no discount). Applying a discount requires a rationale (narrative
should state which historical or current comparable conglomerates were used to
calibrate the discount).

### Equity bridge

```
implied_equity_value = post_discount_ev + non_operating_assets - net_debt - minority_interest
implied_value_per_share = implied_equity_value / shares_outstanding
```

### Concentration ratio

```
concentration_ratio = max(segment_ev / sum_segment_ev for all segments)
```

If concentration_ratio > 70%, a warning is emitted: at this level the SOTP
result is almost entirely driven by one segment, making the multi-segment
structure redundant.

## Common pitfalls

1. **Negative-EBITDA segment with EBITDA multiple.** The helper raises immediately.
   Use `book_value`, `dcf`, or `user_supplied` for loss-making segments.

2. **Peer_pe double-counts segment debt.** `peer_pe` computes equity value, not EV.
   If the segment's debt is included in consolidated `net_debt`, it will be
   subtracted twice in the equity bridge. Either (a) exclude the segment's
   allocated debt from `net_debt`, or (b) use `ebitda_multiple` or `dcf` which
   return EV directly.

3. **Missing corporate overhead.** If segment EBITDAs are reported net of
   allocated corporate costs, do not pass `corporate_overhead` separately —
   it is already subtracted. Check the notes to segment reporting to confirm
   whether overhead allocation is included.

4. **Conglomerate discount calibration.** The Berger-Ofek discount is an empirical
   average; some conglomerates with strong segment fit (e.g., same-industry
   verticals) may warrant 0-5% rather than 10-15%. Do not apply 10% mechanically;
   cite comparable conglomerates and their observed discount/premium.

5. **Segment count > 10.** The helper warns at this threshold. Each segment adds
   an estimate error; 10+ segments can compound errors significantly. Consolidate
   smaller segments under "Other" if they represent < 5% of total EV individually.

6. **Non-operating assets vs. segment EV.** Equity-method investments, excess
   real estate, or pension assets are often *outside* segment-reported EBITDA.
   Pass them via `non_operating_assets`, not as a segment with a `book_value`
   method — this makes their inclusion explicit in the equity bridge.

## Output shape (key fields)

```json
{
  "segment_values": [
    {"name": "Industrials", "valuation_method": "ebitda_multiple",
     "metric_value": 28000, "multiple_used": 8.5, "segment_ev": 238000, "pct_of_gross_ev": 0.70},
    {"name": "Software",    "valuation_method": "peer_ps",
     "metric_value": 12000, "multiple_used": 6.5, "segment_ev": 78000,  "pct_of_gross_ev": 0.23}
  ],
  "sum_segment_ev": 340000,
  "corporate_overhead_deduction": 18800,
  "adjusted_sum_ev": 321200,
  "conglomerate_discount_pct": 0.10,
  "conglomerate_discount_amount": 32120,
  "post_discount_ev": 289080,
  "net_debt": 42000,
  "implied_equity_value": 248580,
  "implied_value_per_share": 99.43,
  "concentration_ratio": 0.70,
  "warnings": ["Top segment 'Industrials' represents 70% of gross SOTP EV..."],
  "narrative": "SOTP: 2 segments, gross EV 340,000..."
}
```

## Worked example

```python
result = execute(
    segments=[
        {"name": "Segment A", "valuation_method": "ebitda_multiple",
         "metric_value": 100.0, "method_inputs": {"multiple": 8.0}},
        {"name": "Segment B", "valuation_method": "peer_ps",
         "metric_value": 50.0,  "method_inputs": {"multiple": 3.0}},
        {"name": "Segment C", "valuation_method": "book_value",
         "metric_value": 30.0,  "method_inputs": {"multiple": 1.0}},
    ],
    shares_outstanding=10.0,
    net_debt=50.0,
)
# Gross EV = 800 + 150 + 30 = 980
# No overhead, no discount
# equity_value = 980 - 50 = 930
# per_share = 930 / 10 = 93.0
assert abs(result["implied_value_per_share"] - 93.0) < 0.01
```

## Related helpers

- **`dcf_engine`**: use for segments where a full FCFF build is warranted; pass
  `enterprise_value` from its output into `method_inputs`.
- **`comparables.run`**: derive EBITDA multiples, P/S multiples, and P/B for each
  segment from peer sets; pass as `method_inputs`.
- **`cost_of_capital_builder`**: needed if any segment uses the DCF method.
- **`price_target_blender`**: blend SOTP-implied price with DCF and comps into a
  single equity price target.
- **`reit_valuation_panel`**: for REIT segments inside a conglomerate, use NAV/AFFO
  methodology; pass the result as `user_supplied`.
