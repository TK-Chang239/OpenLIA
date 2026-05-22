# Skill Doc: insurance_valuation_panel

**Helper:** `insurance_valuation_panel`
**Category:** SECTOR_INSURANCE
**Design ref:** planning/2026-05-22-helpers-design-sector-modules.md §6
**Token budget:** ~2000

---

## 1. Purpose

Compute the canonical insurance KPIs for P&C (property-casualty) and Life insurers.
Generic helpers fail on insurance: P/E ignores reserve adequacy and investment-portfolio mark-to-market; D/E is structurally misleading (insurance liabilities are not debt); GAAP book value misstates economic equity in both directions due to statutory capital differences and interest-rate marks on bond portfolios.

**Use this panel for:**
- Any GICS 4030 ticker (Insurance).
- Mandatory for initiations and quarterly update reports on any P&C or Life insurer.
- Optional for composite conglomerates with material insurance segments.

---

## 2. P&C vs Life: why different metrics

| Dimension | P&C Insurance | Life Insurance |
|---|---|---|
| Revenue driver | Premiums earned on short-tail/long-tail policies | Gross premiums; structured savings/protection products |
| Primary profitability metric | Combined ratio | Embedded value / VNB margin |
| Capital adequacy | RBC (US) / Solvency II (EU) / BCAR | Solvency II / RBC (life framework) |
| Dominant valuation multiple | P/TBV (tangible book) | P/EV (price-to-embedded-value) |
| Investment role | "Float" generates investment income offsetting underwriting cost | Asset/liability matching; longer-duration |
| Reserve risk | Loss development triangles; IBNR | Mortality, lapse, morbidity assumption risk |

---

## 3. P&C: Combined Ratio — the anchor metric

```
loss_ratio     = (losses_and_lae - prior_year_reserve_development) / premiums_earned
expense_ratio  = underwriting_expenses / premiums_earned
pd_ratio       = policyholder_dividends / premiums_earned          [usually 0 for stock insurers]
combined_ratio = loss_ratio + expense_ratio + pd_ratio
```

**Interpretation bands:**
- < 90%:    Excellent — specialty underwriting or favorable cat year.
- 90-100%:  Profitable — underwriting profit with investment income buffer.
- 100-105%: Marginal — breakeven underwriting; investment income required.
- 105-110%: Structural underwriting loss — pricing insufficient; watch for rate hardening.
- > 110%:   Distressed underwriting cycle — hard market typically follows.

**Combined ratio ex-cat:** subtract catastrophe losses from numerator. Ex-cat isolates underlying underwriting discipline from weather/event severity. Always lead narrative with ex-cat when cat losses are material (> 2% of premiums earned).

**Prior-year reserve development:**
- Negative (favorable): insurer reserved more than actual losses — conservative reserving.
- Positive (adverse): insurer reserved less than actual losses — pattern indicates under-reserving.

Multi-year adverse development is a tombstone-grade warning. The insurer's reported earnings were overstated; the liability is being recognized late. Report it explicitly in narrative. Single-year adverse development can be a one-off; three or more consecutive adverse years signals systemic reserve inadequacy.

Loss development triangles (LDT) from SEC filings give the full picture; the helper reports the disclosed net development number but recommends citing 10-K Part II LDT analysis when available.

**Reserve discounting:**
Under US GAAP (ASC 944), P&C reserves are reported at nominal (undiscounted) value for most lines except structured settlements. Under IFRS 17, reserves include explicit discount factors. Comparing US GAAP to IFRS 17 insurers on raw combined ratios overstates IFRS-based cost — note the standard in the output when known.

---

## 4. P&C: Float metrics (Berkshire framework)

**Float** = invested assets (or approximated as unearned premiums + loss reserves). The float is capital the insurer holds temporarily on behalf of policyholders and can invest for its own account.

```
float_equity_ratio    = invested_assets / book_equity_gaap
float_generation_cost = (combined_ratio - 1.0) * premiums_earned / invested_assets
                      [only when CR > 100%; equals 0 when CR <= 100%]
```

When combined ratio < 100%, the insurer is effectively paid to hold float — Berkshire Hathaway's structural advantage. When CR > 100%, float has a positive cost (but may still be worth holding if investment yields exceed that cost).

---

## 5. Life: Embedded Value (EV)

Embedded value is the actuarial fair value of a life insurer's equity:

```
EV = Adjusted Net Worth (ANW) + Value of In-Force Business (VIF)
ANW = statutory_capital - required_capital + adjustments
VIF = PV of future distributable profits from all in-force policies,
      discounted at the risk discount rate
```

When `embedded_value_disclosed` is provided (most EU insurers under IFRS 17 / EEV / MCEV publish this), use the disclosed figure — do not recompute. If not disclosed (most US GAAP insurers), `embedded_value_disclosed` returns null with a note.

**P/EV (Price to Embedded Value):** the primary Life insurance valuation multiple. P/EV > 1.5x is rich; P/EV < 1.0x is optically cheap but may reflect RBC / mortality assumption risk.

---

## 6. Life: VNB and VNB Margin

**New Business Value (VNB / NBV):** present value of expected future profits from policies written in the period, minus acquisition costs.

```
VNB_margin = VNB / Annual Premium Equivalent (APE)
APE        = regular_new_premiums + 10% * single_new_premiums   [industry convention]
```

VNB margin benchmarks:
- > 25%: excellent (Asia-Pacific protection-heavy mix or direct channel)
- 15-25%: strong (diversified Western Life)
- 5-15%: moderate (savings-heavy or high-acquisition-cost)
- < 5%:  weak; question pricing and mix

---

## 7. Solvency and capital adequacy

**US (NAIC RBC):**
- P&C: Company Action Level = 200% of Authorized Control Level. Below 200% triggers regulatory action.
- Life: similar framework; factors differ by asset class and product liability.
- Helper consumes `rbc_ratio_disclosed`; reports warning if < 200%.

**EU (Solvency II SCR):**
- SCR coverage = Own Funds / Solvency Capital Requirement.
- >= 150%: healthy buffer. 100-150%: modest; < 100%: breach — regulatory escalation.
- Helper consumes `solvency_ratio` from `insurance_specific`; warns if < 150%.

**A.M. Best BCAR:**
- Ratings: "Strongest", "Strong", "Adequate", "Fair", "Weak", "Very Weak".
- Helper surfaces the disclosed rating string; does not recompute BCAR.

When multiple capital metrics are available (global insurer with both US and EU entities), all are surfaced in the capital_adequacy block.

---

## 8. Book value and valuation multiples

P&C insurers trade primarily on P/TBV (price to tangible book value per share):
- 1.2-2.5x: normal range for large diversified P&C (Chubb, AIG, Travelers).
- > 2.5x: premium for consistent underwriting excellence (specialty insurers).
- < 1.0x: value territory, but usually signals reserve concerns or adverse development pattern.

Tangible BV strips goodwill (especially important for insurers that have done M&A) and intangibles. GAAP equity includes accumulated other comprehensive income (AOCI) from unrealized bond gains/losses — stripping AOCI is sometimes done to get "core" book in rate-rising environments when bond portfolios have large unrealized losses. The helper reports GAAP equity and tangible equity; the AOCI component is surfaced separately.

---

## 9. Common pitfalls

**Loss development triangles:** the 10-K Part II schedule discloses how prior-year reserves have run off. Always check the 10-year triangle when evaluating reserve adequacy. A favorable combined ratio propped up by positive prior-year development is lower quality than organic improvement.

**Prior-year development sign convention:** industry convention is negative = favorable (the insurer had excess reserves; releasing them improves current-year combined ratio). The helper follows this convention. Confirm sign from input data.

**Catastrophe re-loading:** reinsurance treaties reset annually. A clean cat year improves the combined ratio, but the underlying ex-cat ratio is what matters for sustainable earnings power. Always lead narrative with ex-cat when cat losses differ materially from long-run averages.

**Embedded value sensitivity:** EV is sensitive to the risk discount rate assumption. A 100bps increase in risk discount rate can reduce European Life insurer EV by 8-15%. When EV is the valuation anchor, disclose the discount rate assumption.

**Float cost vs investment yield:** a combined ratio of 103% does not necessarily destroy value if the investment yield on the float exceeds 3%. The float block computes cost but the ROE tells the net story.

**Mutual insurer refusal:** if `book_value_equity_gaap` is null or `shares_outstanding_diluted` is zero, per-share metrics cannot be computed. Mutual insurers have no equity shareholders. Return null for BVPS with a "mutual insurer — equity not applicable" note.

**Reinsurer conventions:** a reinsurer's combined ratio uses assumed premiums (not ceded). The helper does not reclassify; the user should ensure `premiums_earned` represents assumed premiums for reinsurers.

---

## 10. When not to use

- **Banks:** use `banks_sector_panel`. Insurance subsidiary of a bank holding company: use SOTP — bank panel for banking operations, insurance panel for insurance subsidiary.
- **Asset managers / brokerages:** use `dcf_engine` with appropriate margin structure.
- **Mutual insurers:** refuse; equity holder metrics are undefined.
- **Mortgage guaranty / bond insurance:** these are credit-risk vehicles; loss ratios behave differently (volatile, spike at defaults). Flag the sub-sector and recommend analyst review.

---

## 11. Output shape requirements

For `insurance_type = "pc"`: `pc` sub-object must be non-null; `life` is null.
For `insurance_type = "life"`: `life` sub-object must be non-null; `pc` is null.
For `insurance_type = "composite"`: both `pc` and `life` must be non-null.

`investment_portfolio`, `balance_sheet`, and `capital_adequacy` are present for all types.
`float_metrics` is present for `pc` and `composite` only (null for `life`).

Verifier checks: `combined_ratio = loss_ratio + expense_ratio + pd_ratio` within 0.1%; `tangible_book_value = book_equity_gaap - intangibles_and_goodwill`.
