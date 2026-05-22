---
name: banks_sector_panel
category: sector_banks
version: 1.0.0
produces_artifacts:
  - banks_sector_panel_output
consumes_artifacts: []
---

# banks_sector_panel — Institutional Bank KPI Panel

## Purpose

Compute and synthesize the five canonical bank metric blocks for any publicly-traded
commercial bank, savings institution, or bank holding company:

1. **Profitability** — NIM, RoTCE, ROA, ROE, efficiency ratio, fee income mix.
2. **Capital adequacy** — CET1, Tier 1, Total Capital, leverage ratio; buffer vs regulatory minimum.
3. **Credit quality** — NCO rate, NPL ratio, ACL coverage, LLP build/release.
4. **Liquidity / funding** — loan-to-deposit ratio, wholesale funding mix, deposit cost.
5. **Credit-cycle phase** — expansion / mid_cycle_normalizing / early_deterioration / stress / recovery.

This panel is the institutional lens for banks. Generic helpers systematically misprice bank
equities: P/E ignores capital adequacy; debt/equity is structurally meaningless when deposits
are liabilities; EV/EBITDA is inapplicable because bank "revenue" is net interest income, not
gross revenue with separable costs. Do not use dcf_engine, ratio_calculator, or comparables_run
as the primary lens for a bank.

## When to use

- Initiating coverage on any bank, bank holding company, or savings institution (GICS 4010–4020).
- Writing a quarterly update after earnings release — anchor narrative on NIM trend, RoTCE,
  and CET1 buffer, not on EPS or P/E.
- Evaluating capital adequacy: CET1 buffer vs minimum plus any G-SIB surcharge.
- Detecting credit cycle inflection: NCO rate trend, LLP provisioning trajectory, ACL coverage.
- Cross-bank cohort analysis (sector report): compare NIM, efficiency ratio, RoTCE across peers.

## When NOT to use

- **Insurance companies** — use `insurance_valuation_panel`. Insurance liabilities are reserve
  obligations, not deposits; combined ratio replaces efficiency ratio; embedded value replaces RoTCE.
- **REITs** — use `reit_valuation_panel`. Real estate depreciation makes GAAP earnings meaningless;
  FFO/AFFO and NAV are the institutional anchors.
- **Asset managers (BlackRock, T. Rowe Price)** — no lending book, no NIM; use `dcf_engine`
  with fee-revenue projections.
- **Broker-dealers (pure trading desks)** — NIM exists but is not the primary driver; use
  `dcf_engine` supplemented by segment ROE analysis.
- **Development finance institutions / central banks** — institutional metrics do not apply.

## Bank-specific accounting context

### CECL (Current Expected Credit Loss — US GAAP ASC 326)

Post-2020 US banks use CECL (forward-looking) rather than the old incurred-loss model.
Under CECL, the Allowance for Credit Losses (ACL) reflects lifetime expected losses at
origination, not just losses already incurred. This means:

- ACL builds in a recession *before* charge-offs materialise (leading indicator, not coincident).
- LLP (loan-loss provision) in a recovery period may be *negative* (reserve release, boosting NI).
- The ACL / NPL coverage ratio can exceed 2x–3x because the numerator includes forward-looking
  reserves beyond current NPLs.
- IFRS 9 (non-US) uses a similar three-stage ECL model. For non-US banks, ACL behaviour is
  comparable but stage-designation rules differ.

Always note in narrative whether the bank is on CECL (US) or IFRS 9 (non-US) when discussing ACL.

### AOCI (Accumulated Other Comprehensive Income)

Rising interest rates cause unrealized losses on Available-for-Sale bond portfolios (AFS),
flowing through AOCI and reducing GAAP book equity. CET1 for large US banks (Category I–III)
includes AOCI, so a large unrealized-loss AOCI can mechanically suppress CET1 ratio without
reflecting any credit or operational deterioration.

- For large US banks subject to Category I–III capital rules: CET1 is AOCI-inclusive.
- For community banks (< $100B) using the Community Bank Leverage Ratio (CBLR) framework:
  AOCI is excluded from the CBLR numerator by election.
- Always cross-check AOCI sensitivity in narrative when rates have moved significantly.

### Tangible Common Equity (TCE)

```
TCE = common equity - goodwill - other intangibles
RoTCE = net income / average TCE   [annualized]
```

RoTCE is the institutional gold standard for bank profitability — it strips goodwill and
intangibles that arose from acquisitions, so it reflects the true return on deployed capital.
For any bank with material acquisition goodwill (most large-cap US banks), RoTCE diverges
meaningfully from ROE and is the number to anchor narrative on. Report both, but headline RoTCE.

## Regulatory minimum context

### Basel III / Basel IV (global)

The standard CET1 minimum under Basel III is:

| Component | Minimum |
|---|---|
| Pillar 1 minimum | 4.5% |
| Capital conservation buffer | 2.5% |
| Combined minimum (default) | **7.0%** |
| Counter-cyclical buffer (0–2.5%, varies by jurisdiction) | Add on top |
| G-SIB surcharge (1–3.5%, by bucket) | Add on top |

Pass `regulatory_min_cet1` to the helper to reflect jurisdiction-specific or G-SIB-specific
minimums. Common values:

- Community bank (US, no G-SIB surcharge): 7.0%
- JPMorgan / Bank of America / Citigroup (Bucket 4, US G-SIBs): ~9.5–10.5%
- Goldman Sachs / Morgan Stanley (Bucket 3): ~9.0–9.5%
- UK large banks (PRA): 7.0% + bank-specific PRA buffer + countercyclical buffer

### Buffer adequacy interpretation

| CET1 Buffer vs Min | Label |
|---|---|
| ≥ 300 bps | comfortable |
| 150–299 bps | modest |
| 0–149 bps | tight |
| < 0 bps | below minimum — regulatory action expected |

A "tight" buffer (< 150 bps) warrants a mandatory warning in the report narrative.
A CET1 within 100 bps of minimum triggers the helper's warning flag.

## RoTCE vs ROE: narrative discipline

Report ROE as a secondary context figure. Anchor narrative on RoTCE. Use this language:

- "RoTCE of 17.5%, well above cost of equity (est. 11–12%), implies ~1.5x tangible book
  creation per year."
- "ROE of 14.2% (vs 17.5% RoTCE) reflects $12B goodwill from prior acquisitions."

Never anchor the headline bank profitability statement on ROE alone.

## Credit-cycle phasing

The helper uses a heuristic rule-set on NCO rate and LLP YoY change:

| Phase | Signal |
|---|---|
| mid_cycle_normalizing | NCO flat or modestly rising; LLP YoY < 20% |
| early_deterioration | NCO rising > 10% QoQ; LLP YoY > 50% |
| stress | NCO surging > 20% QoQ; LLP YoY > 100% |
| recovery | NCO falling > 10% QoQ; LLP releasing (negative YoY) |
| unknown | Insufficient data |

This is a heuristic, not a structural model. For a full credit-cycle assessment, supplement
with the macro-credit overlay from `yield_curve_shape` and `fred_macro_pull` (e.g., unemployment
trend, senior loan officer survey tightening index).

## NCO surge warning

When NCO rate increases > 20% quarter-over-quarter, the helper emits a warning.
In the report narrative, contextualize whether the surge is:
- Portfolio-specific (one-off commercial real estate or C&I credit) — manageable.
- Broad-based across consumer and commercial segments — potential systemic stress signal.
- Seasonal (Q1 charge-offs typically higher for consumer credit) — check historical pattern.

## Common pitfalls

### 1. Large-bank NIM vs community-bank NIM

Large banks (JPM, BAC, WFC) have substantial non-loan earning assets (securities portfolios,
interbank lending, derivatives). NIM is computed on all earning assets, not just loans.
A community bank with a simpler balance sheet (mostly loans + deposits) will typically show
higher NIM (3.5–4.5%) than a diversified universal bank (2.5–3.0%). Do not compare them
directly without contextualizing the earning-asset mix.

### 2. UCBH / SVB-style concentration risk

A bank with high loan concentration in a single sector (e.g., tech startups, CRE offices,
crypto) will show normal aggregate NCO and NIM metrics right up until the sector stresses.
Aggregate panel metrics are lagging indicators in this scenario. For concentrated portfolios,
look at segment-level NPL disclosures in the 10-Q/10-K rather than the panel's aggregate
credit metrics.

### 3. Broker-dealer efficiency ratio

Goldman Sachs and Morgan Stanley have large broker-dealer / trading operations alongside
their bank charters. Their efficiency ratios (60–70%) look worse than commercial banks
(50–55%) because their "revenues" include volatile trading gains and underwriting fees that
have inherently higher associated costs. Do not compare Goldman's efficiency ratio to JPM's
consumer bank efficiency ratio as a like-for-like. Use segment-specific efficiency ratios
from the 10-K when available.

### 4. Interest income timing: FTE vs GAAP

Many banks report NIM on a fully tax-equivalent (FTE) basis in supplemental disclosures,
adding back the tax benefit on municipal bonds. GAAP NIM is lower. The helper uses GAAP
inputs by default. Note in narrative if the source uses FTE vs GAAP.

### 5. Annualization of quarterly figures

NIM, NCO rate, ROA, and RoTCE must be annualized when computed from quarterly data.
The helper assumes `financials` inputs are already on an annualized or full-period basis
(i.e., the caller annualizes before passing quarterly figures, or passes TTM values).
If quarterly data is passed raw, scale NIM and NCO by 4 before passing, or confirm
the provenance metadata indicates the figures are quarterly.

## Example: JPMorgan Q1 2026 (round numbers)

```python
result = banks_sector_panel.execute(
    ticker="JPM",
    financials={
        "interest_income": 24_800,
        "interest_expense": 11_200,
        "avg_earning_assets": 2_500_000,
        "non_interest_income": 18_900,
        "non_interest_expense": 22_200,
        "net_income": 14_500,
        "avg_total_assets": 3_850_000,
        "avg_common_equity": 310_000,
        "avg_tangible_common_equity": 235_000,
        "cet1_ratio": 0.151,
        "tier1_ratio": 0.168,
        "total_capital_ratio": 0.190,
        "leverage_ratio": 0.072,
        "net_charge_offs": 2_250,
        "avg_loans": 1_320_000,
        "total_loans": 1_340_000,
        "nonperforming_loans": 9_650,
        "allowance_for_credit_losses": 24_800,
        "loan_loss_provision": 3_300,
        "loan_loss_provision_prior_year": 2_870,
        "total_deposits": 2_320_000,
    },
    as_of="2026-Q1",
    regulatory_min_cet1=0.09,   # JPM G-SIB surcharge included
)
```

Key outputs:
- `net_interest_margin_pct`: ~0.0054 (NIM ~54bps annualized on $2.5T earning assets — note:
  this reflects avg_earning_assets of $2.5T; for per-loan NIM use avg_loans as denominator)
- `rotce_pct`: ~0.197 (19.7%)
- `efficiency_ratio_pct`: ~0.520 (52%)
- `cet1_buffer_vs_minimum`: 0.061 (610bps over 9% G-SIB minimum)
- `buffer_adequacy`: "comfortable"
- `nco_rate_pct`: ~0.0017 (17bps annualized)
- `credit_cycle_phase`: "mid_cycle_normalizing"

## Example: BAC community-bank subsidiary (stress scenario)

Pass `regulatory_min_cet1=0.07` for non-G-SIB community banks. If CET1 = 6.5%,
buffer = -0.5% → `buffer_adequacy` = "below_minimum_regulatory_action_expected",
and a warning fires. The narrative must address this explicitly — the spec requires
that CET1 below minimum is a mandatory narrative topic.

## Related helpers

- **`insurance_valuation_panel`**: use for P&C / Life insurers — combined ratio, embedded value.
- **`reit_valuation_panel`**: use for REITs — FFO/AFFO, NAV.
- **`dcf_engine`**: use for asset managers, brokerages, fintechs.
- **`yield_curve_shape`**: supplement with macro credit overlay (10Y-2Y spread, inversion signal).
- **`comparables_run`**: for cross-bank P/TBV and P/RoTCE multiples comparison.
- **`cost_of_capital_builder`**: for cost-of-equity implied by the RoTCE vs required-return gap.
