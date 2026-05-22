---
name: comparables_run
category: comparables
version: 0.1.0
produces_artifacts:
  - comparables_output
consumes_artifacts: []
---

# comparables_run — Comparable Companies Multiples Valuation

## Purpose

Runs a full comparable companies ("comps") multiples analysis for a subject company.
Given a ticker and optionally a pre-fetched fundamentals + market-data payload, the helper:
(1) builds a peer set of 5-10 comparable companies by GICS sub-industry, market-cap size band,
and geography; (2) computes TTM and NTM P/E, EV/EBITDA, EV/Sales, P/B, P/FCF, PEG, and EV/EBIT
multiples for the subject and each peer; (3) builds an EV bridge from first principles; and
(4) derives implied equity values per multiple and a blended valuation range.

## When to use

- Relative valuation section of an equity research initiation or update report.
- When you need a peer-anchored valuation range to triangulate with a DCF.
- When the user explicitly requests a "comps" or "peer multiples" analysis.
- As a data source for the football-field chart (one band per methodology).

## When NOT to use

- Intrinsic DCF-based valuation — use `dcf_valuation` instead.
- Pre-revenue or high-uncertainty businesses where comparables dominate but peers are scarce —
  consider `justified_multiples` (which derives fair multiples from fundamentals) or
  `rnpv_pipeline` (risk-adjusted NPV for pharma/biotech).
- REITs — use `reit_valuation_panel` (FFO/AFFO/NAV based, not earnings multiples).
- Banks — use `banks_sector_panel` (P/TBV, ROTCE, NIM based).

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `ticker` | `str` | Yes | Subject company ticker. |
| `peer_overrides` | `list[str] \| None` | No | Explicit peer list; bypasses GICS discovery when supplied. |
| `size_band` | `'mega'\|'large'\|'mid'\|'small'\|None` | No | Market-cap size bucket for peer filtering; inferred from subject market cap if omitted. |
| `geography` | `'us'\|'global'\|'ex_us'\|None` | No | Geography filter for peer discovery. |
| `fundamentals` | `dict \| None` | No | Pre-fetched `eodhd_fundamentals_output` shape. Discovery limited to `market_data.peers` when None. |
| `market_data` | `dict \| None` | No | Dict with `subject` and `peers` sub-dicts containing multiples and financial metrics (see Output section for `subject` field list). |
| `as_of` | `str \| None` | No | ISO date string for the computation timestamp; defaults to today. |

### `market_data.subject` expected fields

| Field | Type | Purpose |
|---|---|---|
| `market_cap` | `float` | Current market capitalisation (USD). |
| `total_debt` | `float` | Total debt (for EV bridge). |
| `cash` | `float` | Cash and equivalents (for EV bridge). |
| `minority_interest` | `float` | Minority interest (for EV bridge). |
| `preferred_stock` | `float` | Preferred stock (for EV bridge). |
| `ev_reported` | `float \| None` | Reported EV (for bridge delta check). |
| `eps_ttm` | `float \| None` | TTM EPS (for P/E implied value). |
| `ebitda_ttm` | `float \| None` | TTM EBITDA (for EV/EBITDA implied value). |
| `ebit_ttm` | `float \| None` | TTM EBIT (for EV/EBIT implied value). |
| `revenue_ttm` | `float \| None` | TTM revenue (for EV/Sales implied value). |
| `fcf_ttm` | `float \| None` | TTM free cash flow (for P/FCF implied value). |
| `book_value` | `float \| None` | Total book value of equity (for P/B implied value). |
| `shares_outstanding` | `float \| None` | Diluted shares outstanding (for equity-value conversion). |
| `pe_ttm` | `float \| None` | Subject's own TTM P/E. |
| `pe_ntm` | `float \| None` | Subject's own NTM P/E. |
| `ev_ebitda_ttm` | `float \| None` | Subject's own TTM EV/EBITDA. |
| `ev_ebitda_ntm` | `float \| None` | Subject's own NTM EV/EBITDA. |
| `ev_sales_ttm` | `float \| None` | Subject's own TTM EV/Sales. |
| `ev_sales_ntm` | `float \| None` | Subject's own NTM EV/Sales. |
| `pb` | `float \| None` | Subject's own P/B. |
| `pfcf_ttm` | `float \| None` | Subject's own TTM P/FCF. |
| `peg_ntm` | `float \| None` | Subject's own NTM PEG. |
| `ev_ebit_ttm` | `float \| None` | Subject's own TTM EV/EBIT. |

## Output

| Field | Type | Description |
|---|---|---|
| `ticker` | `str` | Subject ticker echoed from input. |
| `peer_set` | `list[dict]` | Each dict: `{ticker, name, market_cap, selection_reason}`. |
| `ev_bridge` | `dict` | `{market_cap, total_debt, cash, minority_interest, preferred_stock, ev_computed, ev_reported, delta_pct, warning}`. |
| `multiples` | `dict` | Keyed by multiple name (e.g. `pe_ttm`); each value is `{ticker, min, p25, median, p75, max}`. |
| `implied_values` | `dict` | Keyed by multiple name; each value is `{at_median, at_p25_to_p75: [low, high]}` or `None`. |
| `blended_range` | `dict` | `{low, median, high, midpoint}` — synthesised across all valid per-multiple medians. |
| `as_of` | `str` | ISO date of the computation. |
| `applied_at` | `str` | ISO-8601 UTC timestamp of computation. |
| `warnings` | `list[str]` | Non-fatal conditions: missing inputs, EV delta warning, etc. |

## Methodology

### Peer set discovery

When `peer_overrides` is not supplied, the helper builds a peer set from two sources:

1. **fundamentals.General.Peers** — EODHD sometimes populates a pre-computed related-companies
   list. The helper extracts up to 10 tickers.
2. **market_data.peers** — any tickers provided in the caller-supplied peer data are merged in.

For each peer, a `selection_reason` string records which signals were used
(GICS sector label, size band, geography, data source).

If neither source yields peers, the output's `peer_set` is empty and a warning is added.
Supply `peer_overrides` or populate `market_data.peers` in that case.

**Size band thresholds:**

| Band | Market cap (USD bn) |
|---|---|
| `mega` | ≥ 200 |
| `large` | 10 – 200 |
| `mid` | 2 – 10 |
| `small` | < 2 |

### EV bridge

The helper computes EV from five components:

```
EV_computed = Market Cap + Total Debt - Cash + Minority Interest + Preferred Stock
```

When `ev_reported` is provided and `|EV_computed - EV_reported| / |EV_reported| > 2%`,
a warning is added to both `ev_bridge.warning` and the top-level `warnings` list.

**Common causes of a large delta:**
- Stale reported EV from data provider (not updated intraday).
- Operating lease right-of-use assets included in one measure but not the other
  (post-ASC 842 / IFRS 16 treatment varies by source).
- Off-balance-sheet items (e.g. unfunded pension obligations) in provider's EV.
- Currency rounding on multi-currency tickers.

**EV → equity bridge (for multiples that compute implied EV first):**

```
Equity = EV_implied - Net Debt   where Net Debt = Total Debt - Cash
```

Cash is subtracted once here; it is NOT added back after subtracting Net Debt.
This is the audit-corrected formula (helpers-design §9 item 11) that avoids
the double-counting bug present in some drafts.

### Multiple computation

For each of the 10 multiples (pe_ttm, pe_ntm, ev_ebitda_ttm, ev_ebitda_ntm, ev_sales_ttm,
ev_sales_ntm, pb, pfcf_ttm, peg_ntm, ev_ebit_ttm), the helper:

1. Collects peer values from `market_data.peers`.
2. Drops None and non-positive values (negative multiples are meaningless).
3. Requires at least 2 valid peer values to compute statistics; otherwise all stats are None.
4. Computes `min`, `p25`, `median`, `p75`, `max` using linear-interpolation percentiles.
5. Records the subject's own value in `multiples[key].ticker`.

### Combined range (blended valuation)

Per the audit-corrected methodology (comparables combined-range addendum, §3.1):

1. For each multiple, compute the implied equity value at the peer-set median multiple.
2. Collect all valid (non-None, positive) median-implied equity values across multiples.
3. `blended_range.low = min(median-implied values)`.
4. `blended_range.median = median(median-implied values)`.
5. `blended_range.high = max(median-implied values)`.
6. `blended_range.midpoint = (low + high) / 2`.

This synthesises across per-multiple **medians**, not across per-multiple lows/highs.
Combining lows-of-lows with highs-of-highs compounds peer-dispersion with methodology-
dispersion, producing an artificially wide band. The min/median/max of medians is the
football-field-style synthesis convention.

## Common pitfalls

- **Stale GICS classification**: EODHD `General.GicSector` lags corporate restructurings;
  a spinoff or M&A target may still be classified in the wrong sector. Use `peer_overrides`
  when GICS peer discovery produces clearly wrong peers.
- **EV reported by data provider includes off-balance-sheet items**: Provider EV may include
  underfunded pension liabilities or securitised receivables not in our bridge. The warning
  fires at 2% delta; investigate the cause before dismissing it.
- **TTM metrics for recent IPOs or spinoffs**: Companies with fewer than 4 full quarters
  since listing have partial TTM figures. The implied values will be distorted. Prefer NTM
  estimates for such companies.
- **Currency mismatch**: Peer multiples pulled from `market_data.peers` are assumed to be
  in the same currency unit as the subject. If peers trade on different exchanges in local
  currencies, the multiples themselves may be comparable (they are unit-less ratios), but
  implied equity values in absolute dollar terms require a currency adjustment before
  blending. A warning is not emitted automatically — validate currency consistency upstream.
- **Negative or near-zero denominators**: Subject EPS ≤ 0 means P/E implied value is None.
  Subject EBITDA ≤ 0 means EV/EBITDA is None. The blended range simply excludes those
  multiples rather than erroring. If too many multiples are excluded, the blended range
  may be dominated by a single methodology.
- **PEG implied equity not computed**: PEG converts to implied equity value only with
  explicit NTM EPS and growth estimates. The helper leaves `implied_values.peg_ntm = None`
  rather than making a noisy approximation.

## Examples

### Example 1 — Basic call with peer overrides

```python
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

h = get_helper("comparables_run")
result = h.impl(
    ticker="MSFT",
    peer_overrides=["GOOGL", "AAPL", "META", "AMZN", "ORCL"],
    market_data={
        "subject": {
            "market_cap": 3_000_000_000_000,
            "total_debt": 50_000_000_000,
            "cash": 80_000_000_000,
            "minority_interest": 0,
            "preferred_stock": 0,
            "ev_reported": 2_970_000_000_000,
            "eps_ttm": 11.45,
            "ebitda_ttm": 120_000_000_000,
            "revenue_ttm": 245_000_000_000,
            "shares_outstanding": 7_400_000_000,
            "pe_ttm": 36.0,
            "ev_ebitda_ttm": 24.8,
            "ev_sales_ttm": 12.1,
        },
        "peers": {
            "GOOGL": {"name": "Alphabet", "pe_ttm": 22.0, "ev_ebitda_ttm": 15.5, "ev_sales_ttm": 5.5},
            "AAPL":  {"name": "Apple",    "pe_ttm": 31.0, "ev_ebitda_ttm": 22.0, "ev_sales_ttm": 8.0},
            "META":  {"name": "Meta",     "pe_ttm": 25.0, "ev_ebitda_ttm": 17.0, "ev_sales_ttm": 6.5},
            "AMZN":  {"name": "Amazon",   "pe_ttm": 45.0, "ev_ebitda_ttm": 30.0, "ev_sales_ttm": 3.5},
            "ORCL":  {"name": "Oracle",   "pe_ttm": 28.0, "ev_ebitda_ttm": 18.0, "ev_sales_ttm": 7.0},
        },
    },
)
# result["blended_range"] -> {"low": ..., "median": ..., "high": ..., "midpoint": ...}
# result["multiples"]["pe_ttm"] -> {"ticker": 36.0, "min": 22.0, "p25": ..., "median": 28.0, ...}
# result["ev_bridge"]["warning"] -> None (delta < 2%)
```

### Example 2 — EV bridge warning fires

```python
result = h.impl(
    ticker="XYZ",
    peer_overrides=["A", "B"],
    market_data={
        "subject": {
            "market_cap": 1_000_000_000,
            "total_debt": 200_000_000,
            "cash": 50_000_000,
            "minority_interest": 0,
            "preferred_stock": 0,
            # Stale reported EV from data provider (5% higher than computed)
            "ev_reported": 1_260_000_000,
        },
        "peers": {
            "A": {"pe_ttm": 15.0},
            "B": {"pe_ttm": 18.0},
        },
    },
)
# ev_bridge.ev_computed = 1,000 + 200 - 50 = 1,150 M
# ev_bridge.ev_reported = 1,260 M
# delta_pct = |1150 - 1260| / 1260 = 8.7% > 2% -> warning fires
assert result["ev_bridge"]["warning"] is not None
```

### Example 3 — No peers, fallback to empty set

```python
result = h.impl(
    ticker="RARE",
    market_data={"subject": {"market_cap": 500_000_000}},
)
assert result["peer_set"] == []
assert any("No peers found" in w for w in result["warnings"])
assert result["blended_range"]["median"] is None
```

## Related helpers

- `justified_multiples` (PR 2.3) — derives fair multiples from fundamentals (g, ROE, payout);
  complements comparables by providing a fundamentally anchored benchmark multiple.
- `football_field_chart` (PR 2.4) — visual summary with one horizontal bar per methodology;
  consumes the `blended_range` from this helper as one input row.
- `historical_multiple_trends` (PR future) — shows how the subject's multiples have re-rated
  over time; pairs with comparables to assess premium/discount vs. history.
- `peer_set_panel` — detailed peer set construction logic (planned separate helper post-PR 2.1).
