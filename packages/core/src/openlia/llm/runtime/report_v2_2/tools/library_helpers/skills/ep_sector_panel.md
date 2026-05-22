---
name: ep_sector_panel
category: sector_energy
version: 1.0.0
produces_artifacts:
  - ep_sector_panel_output
consumes_artifacts: []
---

# ep_sector_panel — E&P Sector KPI Panel

## Purpose

Compute and synthesize five canonical metric blocks for any publicly-traded
exploration-and-production (E&P) company:

1. **Cash flow** — EBITDAX, DACF (Debt-Adjusted Cash Flow), per-unit netback.
2. **Per-unit economics** — realized price, royalties, lifting costs, netback, AISC per BOE.
3. **Capital efficiency** — F&D cost per BOE, recycle ratio, FCF, reinvestment rate.
4. **Reserves** — 1P proved reserves, RRR (organic and total), reserve life index, additions.
5. **Balance sheet** — Net Debt/EBITDAX (cycle-aware leverage lens).

Generic helpers systematically misprice E&P equities. P/E is distorted by DD&A volatility
(non-cash but large). Debt/EBITDA reads catastrophically at commodity price troughs and
reassuringly at peaks. EV/EBITDA ignores exploration spend economics. Book value of reserves
is cost-basis, not fair value. Use `ep_sector_panel` as the primary lens for any GICS 1010 name.

## When to use

- Initiating coverage on any oil/gas exploration and production company (GICS 1010).
- Writing a quarterly update after earnings release — anchor narrative on DACF/share,
  netback trends, and organic RRR, not on EPS or P/E.
- Evaluating per-barrel economics: netback, AISC, lifting costs.
- Assessing reserves quality: RRR, reserve life index, F&D cost per BOE.
- Cycle-aware balance sheet analysis: Net Debt/EBITDAX at current vs downside prices.

## When NOT to use

- **Royalty / streaming companies** (Franco-Nevada, Royal Gold, Wheaton Precious Metals) —
  no production costs or reserves replacement; use a stream-DCF instead.
- **LNG export terminals** (Cheniere Energy, Tellurian) — infrastructure / take-or-pay
  contract structures; use `dcf_engine`.
- **Integrated oil majors with dominant downstream/chemicals** — the E&P panel is
  upstream-segment only. Use SOTP; restrict this panel to the upstream segment via
  `segment_filter`.
- **Midstream MLPs** — distributable cash flow model; use `dcf_engine`.
- **Mining companies** (gold, copper) — AISC applies but semantics differ; use a
  mining-specific helper when available.

## EBITDAX vs EBITDA: why E&P adds back exploration

EBITDA is EBIT + DD&A. E&P analysts add a fifth add-back: **exploration expense (the X)**.

Exploration expense includes:
- Dry-hole costs (drilling a well that finds no commercial reserves)
- Seismic data acquisition and processing costs
- Geological and geophysical survey costs

Under **full-cost accounting** (most Canadian and some US small-caps), all exploration costs
are capitalized and amortized. Under **successful-efforts accounting** (US majors: XOM, CVX,
COP; IFRS reporters), dry-hole costs and certain G&G costs are expensed immediately.

EBITDAX normalizes across accounting methods: regardless of whether the company uses
full-cost or successful-efforts, adding back exploration expense puts all companies on the
same cash-margin basis. The logic: exploration spending is like capex — it buys the option
to find reserves — so it should be treated below the EBITDAX line alongside capex, not
as a current-period operating charge.

```
EBITDAX = Revenue
        - Royalties & Production Taxes
        - Lifting Costs (Operating Expenses)
        - Gathering, Processing, Transport
        - Cash G&A
        (DD&A is excluded — added back)
        (Exploration expense is excluded — added back)

DACF = EBITDAX - Cash Interest - Cash Taxes
     = cash available for capex, dividends, buybacks, deleveraging
```

DACF per share is the preferred E&P EPS analog. DD&A is volatile (reflects prior-cycle
capex decisions), non-cash, and varies by accounting method. DACF strips it out entirely.

## All-in Sustaining Cost (AISC)

AISC is a **mining convention** (World Gold Council Guidance Note, 2013/2018). It is
applied to gold, silver, and copper producers. For oil and gas, the analog concept
is the "all-in cash cost" or "all-in sustaining cost per BOE":

```
AISC per BOE = (Lifting Costs + Royalties + Maintenance Capex + G&A) / Annual BOE
```

This measures the cash cost to sustain current production rate — i.e., the floor price
below which maintenance production becomes uneconomical.

- AISC < $25/BOE: best-in-class (Permian Tier 1 operators, Saudi Aramco upstream)
- AISC $25–$40/BOE: competitive mid-cost
- AISC > $50/BOE: high-cost; economically challenged at $60 WTI floor

Note: AISC as formally defined by the World Gold Council (for gold ounces) includes
reclamation costs and employee share-based compensation. The E&P adaptation here
omits reclamation and SBC; it focuses on cash costs to sustain the barrel.

## Netback per BOE

Netback is the most-cited E&P metric. It answers: "how much cash does this barrel earn
before capital spending?"

```
Netback = Realized Oil/Gas/NGL Revenue
        - Royalties & Production Taxes
        - Lifting Costs
        - Gathering, Processing, Transport
        - Cash G&A
        (per BOE produced)
```

Positive netback at $60 WTI means the well pays for itself operationally; it does not
mean it earns a return on capital. For return-on-capital analysis, use recycle ratio.

**Basin-specific netback norms:**
- Permian Basin (Midland/Delaware): $30–$45/BOE at $80 WTI — premier basin, world-class
  cost structure, high oil cut (70–80%), minimal transport premium
- Bakken (Williston): $22–$35/BOE — good oil cut but wider WTI-Bakken differential
  ($3–$8/bbl depending on pipeline capacity) and higher lifting costs in cold climate
- Marcellus / Utica (dry gas): $2–$6/MCFE — very low lifting cost but low realized price;
  gas economics are highly sensitive to Henry Hub basis differentials
- Canadian Oil Sands: $15–$25/BOE — high lifting cost, wide WCS-WTI differential ($10–$20)
- Eagle Ford (liquids-rich): $28–$38/BOE — strong NGL cut improves realized price

Do not compare Permian netbacks to Bakken or Marcellus netbacks directly without
adjusting for oil/gas mix and transportation basis.

## F&D Cost and Recycle Ratio

**Finding & Development (F&D) cost** measures capital efficiency in finding new reserves:

```
F&D Cost per BOE = (Growth Capex + Acquisition Capex) / (Organic Reserves Added + Acquisition Reserves)
```

Best-in-class F&D:
- Premier Permian operators: < $10/BOE
- Strong shale: $10–$15/BOE
- Average conventional: $15–$20/BOE
- Capital-inefficient: > $20/BOE

**Recycle ratio** = netback per BOE / F&D cost per BOE

This is the cash-return-on-finding-capital ratio:
- > 2.5x: top-decile capital efficiency
- 1.5–2.5x: healthy; creating value
- 1.0–1.5x: marginal; barely covering cost of finding
- < 1.0x: capital-destructive at current prices

A recycle ratio below 1.0x means the company earns less per BOE produced than it spends
finding that BOE — a value-destruction signal that requires a price-deck improvement or
cost reduction to reverse.

## Organic RRR: the reserves health signal

**Reserves Replacement Ratio (RRR)**:
```
Organic RRR = (Organic Reserves Added + Revisions) / Annual Production
Total RRR   = (Organic + Acquisitions + Revisions) / Annual Production
```

- Organic RRR > 1.0: replacing production from the drill bit — sustainable organic growth
- Organic RRR 0.8–1.0: modest reserve drawdown; manageable if temporary
- Organic RRR < 0.8: material production decline trajectory — flag in narrative
- Organic RRR < 0.5 for multiple years: structural reserve depletion signal

Total RRR can be > 1.0 via acquisitions even when organic RRR is below 1.0. Always report
both; the organic number is the purest measure of drilling capital efficiency.

**Reserve Life Index (RLI)** = Proved Reserves / Annual Production (years):
- 10–15 years: typical shale/unconventional operators
- 15–25 years: diversified conventional/shale mix
- > 25 years: large conventional or heavy oil (long-life assets)
- < 8 years: short-life unconventional; growth capex required to sustain production

## Net Debt / EBITDAX: cycle-aware leverage

```
Net Debt / EBITDAX = (Total Debt - Cash) / EBITDAX (trailing 12 months)
```

Leverage thresholds:
- < 1.0x: well-capitalized through the cycle; can sustain dividends/buybacks at downside prices
- 1.0–2.0x: typical mid-cycle; manageable with commodity price support
- > 2.0x: stressed at investment-grade target; the helper triggers a warning here for IG-rated issuers
- > 2.5x: challenged at downturn prices; often requires equity issuance or asset sales
- > 4.0x: distressed; covenant risk

The critical insight: at commodity price peaks, debt/EBITDAX looks fine even for
over-leveraged companies. The cycle-aware check is Net Debt / DACF at downside prices
(use the scenario_economics block's FCF-at-$60 as a stress reference).

## Full-cost vs successful-efforts accounting

**Successful-efforts (SE):** Used by US majors (XOM, CVX, COP) and most IFRS reporters.
- Dry-hole costs expensed immediately through P&L
- Seismic and G&G costs generally expensed
- Only successful well completion costs capitalized
- Results in higher exploration expense, lower asset base

**Full-cost (FC):** Used by many Canadian companies and some US small-caps.
- All exploration costs capitalized in a single cost pool
- Pool amortized over total reserves (depletion)
- No dry-hole expensing through P&L
- Results in higher assets, lower exploration expense, potentially higher earnings

EBITDAX normalizes across both methods by adding back exploration expense (SE companies
show high exploration expense; FC companies show near-zero, so there is little to add back).
DD&A is higher for SE companies per BOE (because the asset base is lower but depletion rates
are applied to actual proved reserves). This is a common source of apparent EBITDA differences
between companies using different accounting methods — always verify before comparing.

## Common pitfalls

### 1. Permian vs Bakken cost comparison

Permian operators (Pioneer, Diamondback, Coterra Permian acreage) show world-class netbacks
because: (1) high oil cut (75–85%), (2) low water handling costs on mature acreage, (3)
minimal transport premium vs WTI. Bakken operators (Continental, Chord Energy) face:
(1) higher water handling costs, (2) WTI-Bakken differentials, (3) colder-climate lifting cost.
Do not compare Permian lifting costs to Bakken lifting costs without noting the structural
difference. A "low-cost" Bakken operator is not directly comparable to a "high-cost" Permian.

### 2. Hedging vs commodity risk

A company with 60% of next-12-month production hedged at $75 WTI looks like it has low
commodity risk. But:
- Post-hedge-roll period (months 13+): fully exposed to spot
- Mark-to-market losses on hedges if spot rises above hedge price reduce book equity
- Over-hedging at low prices locks in losses

The `hedging` block in the output captures hedged %, hedge price vs spot, and MTM value.
In narrative: note that hedging protects near-term cash flow but does not eliminate
long-cycle commodity exposure. A company hedged at $65 in a $90 market is a
"value transfer" story — good downside protection but capped upside.

### 3. Revisions: positive vs negative

Reserve revisions flow through organic RRR. Negative revisions (downward) are common when:
- Commodity prices fall below SEC reference price (PV10 economic limit)
- Well performance underperforms type curves (especially in new basins)
- Regulatory changes restrict development drilling

Large negative revisions (> 15% of proved reserves) are a red flag. Positive revisions
typically come from: better-than-expected well performance, price increases (oil > SEC
reference price), or infrastructure improvement enabling previously sub-economic acreage.

### 4. Production unit ambiguity

Verify units before passing inputs:
- BOE/d (barrels of oil equivalent per day): standard US convention; 1 BOE = 6 MCF gas
- MBOE/d (thousand BOE per day): large operators (XOM, CVX)
- MMBOE/d (million BOE per day): reserved for the largest majors
- MCFE/d (thousand cubic feet equivalent per day): gas-focused reporters

The helper uses BOE/d as the standard unit. Pass annual_boe_per_day in BOE, not MBOE.

### 5. Gas conversion: 6:1 vs BTU-equivalent

The conventional 6:1 ratio (6 MCF = 1 BOE by energy content) understates the economic
value of gas when gas prices are high relative to oil. Some operators use a BTU-equivalent
ratio (5.8:1 or 6.0:1 depending on gas BTU content). The helper uses 6:1 by convention.
When reporting gas-weighted operators (Cabot, EQT, Range Resources), note that BOE
conversion is a volumetric energy metric, not a price-equivalent metric.

## Cycle phase classification

The helper classifies cycle phase from netback per BOE and current WTI:

| Phase | Netback | WTI |
|---|---|---|
| late_cycle | >= $30/BOE | >= $80 |
| mid_cycle | >= $20/BOE | >= $60 |
| early_cycle | >= $10/BOE | >= $50 |
| trough | < $10 or WTI < $50 | any |

This is a heuristic. For a full cycle assessment, supplement with the macro overlay
from `fred_macro_pull` (Baker Hughes rig count, DUC inventory, WTI contango/backwardation).

## Warning triggers

1. **Negative netback at WTI > $60** — structural cost problem or material one-off.
   In narrative: identify which cost line is anomalous (water handling? transportation
   differential? G&A allocation?).

2. **Organic RRR < 100%** — production drawdown. In narrative: is this intentional
   (capital discipline, shareholder return focus) or structural (declining acreage quality)?
   Check reserve life index — if RLI > 12 years, short-term RRR < 100% is acceptable.
   If RLI < 8 years, sub-100% RRR signals depletion risk.

3. **Net Debt/EBITDAX > 2x (IG-rated companies)** — balance sheet stress at downside.
   In narrative: stress-test using FCF-at-$60 from scenario block. If FCF is negative
   at $60, the company cannot deleverage at a $60 oil price environment.

4. **AISC > $50/BOE** — high-cost operator. In narrative: identify the highest-cost
   component and context (is this a legacy heavy oil asset being wound down? new basin
   with first-year high costs? structural issue?).

## Example: Mid-size Permian E&P (illustrative)

```python
result = ep_sector_panel.execute(
    ticker="PXD",
    financials={
        "revenue": 6_200,
        "royalties_and_production_taxes": 720,
        "operating_costs": 840,
        "gathering_processing_transport": 310,
        "cash_g_and_a": 190,
        "interest_expense": 110,
        "dd_a_on_oil_gas_properties": 1_850,
        "exploration_expense": 80,
        "cash_taxes": 950,
        "capex_maintenance": 1_100,
        "capex_growth": 1_600,
        "net_debt": 2_800,
    },
    production_data={
        "boe_per_day": 700_000,
        "oil_pct": 0.74,
        "gas_pct": 0.20,
        "ngl_pct": 0.06,
    },
    reserves_data={
        "proved_reserves_boe": 2_800_000_000,
        "proved_developed_reserves_boe": 1_960_000_000,
        "reserves_added_organic_boe": 270_000_000,
        "reserves_added_acquisitions_boe": 0,
        "reserves_added_revisions_boe": -15_000_000,
    },
    commodity_prices={"wti_current": 78.0},
    as_of="2026-Q1",
)
```

Key outputs (illustrative):
- `netback_per_boe`: ~$28–32/BOE (Permian tier-1 range at $78 WTI)
- `ebitdax`: ~$4,140M (revenue - royalties - opex - gathering - G&A)
- `dacf`: ~$3,080M (EBITDAX - interest - taxes)
- `organic_rrr_pct`: ~0.989 (slightly below 100% — modest drawdown)
- `reserve_life_index_years`: ~10.9 years
- `net_debt_to_ebitdax`: ~0.68x (well-capitalized)
- `cycle_phase`: "mid_cycle"
- `composite_ep_health_score`: ~72/100

## Related helpers

- **`dcf_engine`**: use for royalty companies, LNG infrastructure, or steady-state large
  majors where free cash flow predictability makes DCF more appropriate than cycle metrics.
- **`sotp_builder`**: for integrated majors — upstream E&P panel (this helper) for the
  upstream segment, DCF for downstream/chemicals/renewables.
- **`comparables_run`**: for cross-E&P cohort comparison on EV/DACF, EV/BOE multiples.
- **`cost_of_capital_builder`**: for WACC inputs to a DCF on steady-state E&P names.
- **`fred_macro_pull`**: supplement with WTI forward curve, rig count trend, inventory data.
- **`yield_curve_shape`**: macro credit overlay for leverage-stressed E&P names.
