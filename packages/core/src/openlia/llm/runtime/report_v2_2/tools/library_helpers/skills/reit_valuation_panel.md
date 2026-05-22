---
name: reit_valuation_panel
category: sector_reits
version: 1.0.0
produces_artifacts:
  - reit_valuation_panel_output
consumes_artifacts: []
---

# reit_valuation_panel — REIT Valuation and KPI Panel

## Purpose

Compute and synthesize the four canonical REIT metric blocks for any publicly-traded
equity REIT or real estate operating company (REOC):

1. **Income** — FFO, AFFO, AFFO payout ratio, FFO/AFFO growth (QoQ, YoY).
2. **Valuation** — P/FFO, P/AFFO, NAV per share, applied cap rate, implied cap rate,
   premium/discount to NAV.
3. **Operating metrics** — same-store NOI growth, occupancy rate, WALT, re-leasing
   spreads, tenant concentration, lease expiration ladder.
4. **Balance sheet** — Net Debt/EBITDA, debt-to-assets, unsecured debt mix,
   interest coverage, weighted average debt maturity.

This panel is the institutional lens for equity REITs. GAAP earnings and P/E
systematically misprice REITs because real estate depreciation is not an economic
cost — buildings appreciate in value. Book value also understates fair value.
Do not use dcf_engine, ratio_calculator, or comparables_run as the primary
valuation lens for a REIT. FFO/AFFO and NAV are the only institutionally accepted
anchors.

## When to use

- Initiating coverage on any equity REIT or REOC (GICS 6010).
- Writing a quarterly update after earnings — anchor on FFO/AFFO trend and
  same-store NOI growth, not GAAP EPS or P/E.
- Computing NAV per share for a premium/discount analysis.
- Evaluating AFFO payout sustainability (is the dividend covered?).
- Cross-REIT cohort analysis: compare P/FFO, P/AFFO, and implied cap rates
  within a property-type peer group.

## When NOT to use

- **Mortgage REITs (mREITs)** — mREITs (AGNC, Annaly, NLY) are rate-sensitive
  financial intermediaries, not equity real estate owners. They use leverage on
  agency MBS; their "income" is spread income, not NOI. Use `banks_sector_panel`
  as the closest analog or refuse with a clear explanation. Never run an mREIT
  through this panel.
- **Banks / financials** — use `banks_sector_panel`.
- **Insurance** — use `insurance_valuation_panel`.
- **Royalty / streaming companies** — similar structure to externally-managed REITs
  but revenue is from royalty streams, not property; use DCF.
- **Generic industrials / tech** — use `dcf_engine` or `ratio_calculator`.

## FFO vs AFFO: definitions and institutional conventions

### FFO (Funds From Operations) — NAREIT definition

```
FFO = GAAP Net Income
    + real estate depreciation and amortization
    - gains on sales of real estate
    + losses on sales of real estate
    + impairment charges
```

FFO is the standardized NAREIT metric, published since 1991. The rationale: real
estate typically appreciates; therefore, adding back depreciation to net income
gives a truer picture of operating cash generation than GAAP earnings.

When a company discloses NAREIT FFO directly, compare it against the computed FFO.
If the difference exceeds 2%, raise a warning — potential one-time items or
non-standard adjustments may be present.

### AFFO (Adjusted FFO) — no single industry standard

AFFO refines FFO to capture maintenance capital and non-cash adjustments:

```
AFFO = FFO
     - recurring capex         (maintenance capex only; exclude development)
     - straight-line rent adj  (back out non-cash rent smoothing)
     + stock-based compensation (non-cash; institutional default: add back)
```

There is no single AFFO standard. Companies and analysts apply different
adjustments. The `reit_valuation_panel` records which adjustments were applied
so the result is auditable. Disclose the adjustment policy in the report narrative.

Key distinction on capex:
- **Recurring / maintenance capex**: roofs, HVAC replacements, parking-lot resurfacing —
  required to maintain current occupancy and NOI. Subtract from FFO for AFFO.
- **Development / growth capex**: new construction, acquisitions — invested to grow
  the portfolio. Do NOT subtract from FFO for AFFO.

If the company does not separately disclose maintenance vs development capex,
flag this in the narrative as a limitation. Some analysts use a fixed percentage
of gross assets (typically 1-2%) as a proxy.

### Payout ratio interpretation

| AFFO Payout Ratio | Classification |
|---|---|
| < 65% | Low — significant dividend growth headroom |
| 65–80% | Moderate — healthy cushion |
| 80–95% | High — limited growth; monitor carefully |
| > 95% | At risk — dividend cut likely without improvement |

The helper issues a warning at > 80%. At > 95%, the narrative must explicitly
address dividend sustainability and the financing path (equity issuance, asset sales).

## Cap rate sourcing (decision #15)

**The helper requires user-supplied cap rates. CBRE/JLL surveys require a
commercial subscription and cannot be hard-coded into the system.**

The user must provide cap_rate_assumptions at runtime. Common approaches:

1. **Direct entry from broker survey**: "CBRE Q1 2026 Industrial cap rates: 4.5–5.0%"
   — pass `{"industrial": 0.047}` as the midpoint.
2. **Green Street Advisors**: publishes sector-level implied cap rates from REIT
   share prices; best for cross-checking.
3. **Transaction comps**: recent comparable-property sales disclose cap rates
   in 10-K/10-Q supplementals; average recent transactions for the property type.
4. **Disclosed REIT valuations**: some REITs disclose independent property
   appraisals; use the appraised-value implied cap rate.

When reporting NAV, always disclose the cap rate source in the narrative:
"Applied 5.5% blended cap rate (analyst estimate; CBRE Q1 2026 industrial
survey midpoint)."

### Cap rate norms by property type (approximate ranges; verify with current data)

| Property Type | Approximate Cap Rate Range |
|---|---|
| Industrial / logistics | 4.0–5.5% |
| Self-storage | 4.5–5.5% |
| Data center | 4.0–5.5% |
| Residential (apartment) | 4.5–6.0% |
| Net-lease retail (triple-net) | 5.0–6.5% |
| Healthcare / medical office | 5.5–6.5% |
| Suburban office | 6.5–8.5% |
| Lodging / hospitality | 7.0–9.0%+ |

Office and lodging carry higher cap rates (lower valuations per dollar of NOI)
because of structural headwinds (remote work) and cyclicality respectively.
Industrial and data centers carry lower cap rates (higher valuations) because of
strong long-term demand and rent growth.

## NAV methodology

```
Implied Real Estate Value = NOI_annualized / applied_cap_rate
Equity NAV = Implied RE Value + Cash - Total Debt - Preferred Equity
NAV per share = Equity NAV / Diluted Shares Outstanding

Premium / Discount to NAV = Current Price / NAV per share - 1
```

NAV is the dominant long-term valuation anchor for REITs. REITs trading at a
discount to NAV can be attractive if the discount reflects market sentiment rather
than structural problems. REITs at a premium typically have sector tailwinds or
a development pipeline the market is pricing above book.

**Implied cap rate cross-check:**
```
Implied Cap Rate = NOI_annualized / (Market Cap + Total Debt + Preferred - Cash)
                = NOI_annualized / Enterprise Value
```

If the implied cap rate is meaningfully higher than the market (per CBRE/JLL),
the REIT is trading at a discount to NAV. If it is lower, it is at a premium.
Always report both the applied cap rate (for NAV) and the implied cap rate
(what the market is currently pricing in).

## Leverage norms

```
Net Debt / EBITDA:   target < 6x for investment-grade REITs; > 7x triggers warning
Debt / Gross Assets: < 40% conservative; > 55% aggressive
Unsecured Debt Mix:  higher unsecured debt pct = better balance sheet flexibility
Interest Coverage:   > 3x comfortable; < 2x concerning
```

Debt-to-equity is not used for REITs (same reason as banks — balance sheet structure
differs fundamentally from industrial companies). Use Net Debt/EBITDA and
Debt-to-Gross-Assets instead.

## Common pitfalls

### 1. Industrial REITs vs Office REITs vs Retail REITs

Property type drives everything: cap rate, rental growth, lease structure, and
operating risk. Do not use a blended cap rate across property types without
verifying the segment NOI mix.

- **Industrial (PLD, EXR)**: low cap rates, 3-5 year leases with mark-to-market
  at renewal, high re-leasing spreads (20-50% in recent cycles). Same-store NOI
  can be strong even with moderate occupancy because rent growth offsets.
- **Office (BXP, VNO)**: high cap rates post-2020 due to remote-work headwinds,
  long leases (5-10 years), often negative re-leasing spreads in gateway cities.
  Occupancy is a key leading indicator.
- **Retail (O, SPG)**: triple-net leases (tenant pays operating costs) yield lower
  cap rates for net-lease (O, NNN) vs strip centers vs malls. Tenant credit quality
  and lease expiration ladder matter more than raw occupancy.

### 2. External vs internal management

Externally-managed REITs (managed by a sponsor, with fees paid out) trade at a
NAV discount because fee leakage to the manager reduces distributable income.
The management fee is often structured as a % of assets + % of income, creating
a misalignment of interests (growth in AUM benefits the manager regardless of
per-share value creation). Flag in narrative.

### 3. Development pipeline

A REIT with a significant development pipeline will report lower current NOI
relative to asset value — development assets earn no NOI while under construction.
NAV should add the estimated stabilized value of the pipeline (NOI at stabilization /
cap rate, minus remaining construction cost). If the developer's supplemental
does not disclose this, NAV is understated. Flag as a limitation.

### 4. Straight-line rent

GAAP requires rent income to be recognized on a straight-line basis over the lease
term. For a 10-year lease with rent steps, year 1 revenue is higher than actual cash
received, and later years are lower. Straight-line rent adjustments must be subtracted
in AFFO to reflect actual cash flows. Large straight-line rent adjustments relative
to FFO inflate reported FFO quality.

### 5. Hospitality / lodging REITs

Lodging REITs (HST, RLJ) have no leases — they operate hotels directly or under
management agreements. Same-store NOI is replaced by RevPAR (revenue per available
room) as the operating metric. The panel's lease-based metrics (WALT, tenant
concentration, lease expiry ladder) are not applicable. RevPAR is highly seasonal;
always compare TTM or trailing 12 months, not a single quarter.

### 6. Newly listed REITs

If the REIT has < 4 quarters of history, same-store NOI is not meaningful (not enough
history to isolate same-store properties). Report only FFO/AFFO + occupancy + NAV
with a "limited same-store history" caveat.

## P/FFO and P/AFFO interpretation

| P/FFO Range | Typical Context |
|---|---|
| < 12x | Deep discount; check for structural problems |
| 12–16x | Fair value for most property types |
| 16–20x | Premium; requires above-average growth |
| > 20x | Growth-priced or sector tailwind premium |

P/AFFO is the more conservative multiple (AFFO strips maintenance capex and
non-cash adjustments). For REITs with high capex (malls, hotels) the P/AFFO
premium over P/FFO is meaningful.

## Examples

### Realty Income (O) — triple-net retail

```python
result = reit_valuation_panel.execute(
    ticker="O",
    financials={
        "net_income": 380,
        "real_estate_depreciation": 540,
        "gains_on_sales": 25,
        "recurring_capex": 65,
        "straight_line_rent_adj": 18,
        "stock_based_comp": 6,
        "dividends_paid": 663,
        "shares_outstanding": 855,
        "market_cap": 7218,        # ~$8.45/share × 855M shares
        "current_price": 8.45,
        "total_debt": 5800,
        "cash_and_equivalents": 285,
        "noi_annualized": 2880,
        "ebitda": 1500,
        "interest_expense": 280,
        "same_store_noi_current": 720,
        "same_store_noi_prior_year": 695,
        "occupancy_rate": 0.988,
        "walt_years": 9.1,
    },
    cap_rate_assumptions={"blended": 0.055},
)
```

Key outputs:
- `income.ffo`: 895 (380 + 540 - 25)
- `affo.affo`: 818 (895 - 65 - 18 + 6)
- `affo.affo_payout_ratio`: ~0.81 → warning fires (>80%)
- `valuation.nav_per_share`: ~$8.86 (NAV = 2880/0.055 + 285 - 5800 = 7,070; /855)
- `valuation.premium_discount_to_nav_pct`: ~-0.046 (~5% discount)
- `operating_metrics.same_store_noi_growth_pct`: ~0.036 (+3.6%)

### Prologis (PLD) — industrial

```python
result = reit_valuation_panel.execute(
    ticker="PLD",
    financials={
        "net_income": 1200,
        "real_estate_depreciation": 1800,
        "gains_on_sales": 50,
        "recurring_capex": 120,
        "straight_line_rent_adj": 80,
        "dividends_paid": 2400,
        "shares_outstanding": 900,
        "current_price": 105.0,
        "market_cap": 94500,
        "total_debt": 25000,
        "cash_and_equivalents": 1800,
        "noi_annualized": 6000,
        "ebitda": 5200,
        "interest_expense": 900,
        "same_store_noi_current": 1400,
        "same_store_noi_prior_year": 1200,
        "occupancy_rate": 0.965,
        "releasing_spread_pct": 0.68,   # 68% re-leasing spreads (mark-to-market)
    },
    cap_rate_assumptions={"industrial": 0.046},
)
```

- `valuation.nav_per_share`: 6000/0.046 = $130,435M real estate value;
  + $1,800M cash - $25,000M debt = $107,235M NAV equity; / 900M shares = $119.15
- Premium/discount: 105/119.15 - 1 ≈ -11.9% discount to NAV
- Industrial 68% re-leasing spreads signal strong embedded rent growth in the portfolio.

### Extra Space Storage (EXR) — self-storage

Self-storage REITs have short-term leases (month-to-month), so WALT is not a
meaningful metric. Occupancy and street rates are the key operating signals.
Pass `walt_years=None` and note in narrative that EXR uses month-to-month leases.

## Related helpers

- **`banks_sector_panel`**: use for banks and bank holding companies.
- **`insurance_valuation_panel`**: use for P&C and Life insurers.
- **`dcf_engine`**: for non-REIT real estate operating companies where NOI-based
  valuation is less applicable (e.g., homebuilders, real estate services).
- **`comparables_run`**: for cross-REIT P/FFO and P/AFFO multiples comparison.
- **`debt_maturity_ladder`**: supplement balance sheet block with a full
  year-by-year debt maturity schedule and refinancing-wall detection.
- **`dividend_safety`**: for a detailed dividend sustainability check on REITs
  with borderline AFFO payout ratios.
