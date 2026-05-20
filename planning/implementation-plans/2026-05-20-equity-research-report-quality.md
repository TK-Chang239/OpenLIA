# Equity Research Report Quality — Improvement Plan

**Date:** 2026-05-20
**Branch:** `feat/equity-research-report-improvements`
**Driver:** Sell-side analyst review of the NVDA stock-initiation report shipped from the current `stock_initiation` framework.
**Scope:** `packages/core/src/openlia/llm/runtime/report_v2/{frameworks,facts,sections}`, `packages/core/src/openlia/reports/frameworks/stock_initiation*`, manifest packer, and report validators.

---

## 1. The reviewer's verdict, in one paragraph

The reviewer's bottom line: *"This is not an initiation report. It is a descriptive company profile with citations."* No rating, no price target, no earnings model, no comps, and the Data Center revenue figure — the single most important number in an NVDA thesis — is wrong by a fiscal year and ~$78B. They classified it as "not lettable on the floor."

The feedback has three layers: (A) material factual errors, (B) shallow analysis, (C) crucial content missing entirely. Each layer maps cleanly onto a root cause in our pipeline.

---

## 2. Root causes (what's actually broken in the code)

| # | Root cause | Where it lives | Example failure from the review |
|---|------------|----------------|--------------------------------|
| RC1 | LLM invents segment mix because no deterministic segment facts exist | `facts/extractors/stock_initiation.py` registers `revenue_annual` total but no `segment_revenue_*` | "$115.2B Data Center, 87.7% of latest FY" — that's FY2025 dollars stapled onto FY2026 ($215.9B) headline. |
| RC2 | The deterministic consensus rating and mean PT (already extracted from EODHD) are buried in a body section rather than headlined on the cover; the style guide simultaneously asks the LLM to invent its own rating, which is the wrong direction | `reports/frameworks/stock_initiation.json` `investment_recommendation` correctly forbids LLM advocacy but doesn't surface the consensus prominently; style guide §2.13 still asks for LLM-authored rating/PT | "No rating and no price target. This is the headline failure." Resolved by *surfacing the sourced consensus prominently*, not by letting the LLM author one. |
| RC3 | Facts slice is too narrow — no forward EPS, no segment revenue, no FCF/capex, no ROE/ROIC, no SBC, no buyback, no beta, no consensus next-quarter guide | `frameworks/stock_initiation.facts.json` (≈25 facts); peer multiples but no peer absolute sizes | "Projections section contains zero projections… omits the company's own next-quarter guide." "There are no comps. The peer table contains NVIDIA and nothing else." |
| RC4 | No fresh-catalyst research outside `recent_developments` — `web_search` budget is 10, used only by that one section | `stock_initiation.json` `web_search_budget_default: 10` | GTC 2026 (Mar 16–19) and the Rubin platform/$1T cumulative-demand figure are entirely absent from a report dated May 2026. |
| RC5 | No post-generation cross-section reconciliation: each section LLM runs independently and there is no validator on numeric consistency or arithmetic | section dispatcher writes one file per section; no global numeric audit | "TTM operating margin of 65.0% is fabricated." "PEG = 45.5 ÷ 100 = 0.455, not 0.68." "FY2026 / FY2025 labelling incoherent." |
| RC6 | Cover hero carries verdict but rail with 52W range / ADTV / forward P/E renders at the bottom; many readers see it as the *last* page | rail rendering position in the report viewer | "Structure is backwards. The Cover [hero] which contains the 52-week range, volume, and price sits at the end of the document." |
| RC7 | Prose enforces citation proximity but not numeric correctness — LLM can quote a fabricated number and cite a real source | `sections/prompts.py` `_OUTPUT_FORMAT_REMINDER` only checks for `[N]` markers, not value-vs-fact equality | "65% TTM op margin" cited to filings that show 60.4%; "Cash $10.6B" while marketable securities take true liquidity past $40B. |
| RC8 | No staleness or corporate-events awareness — the runner blindly trusts whatever the vendor feed returns and the report timestamps the current date even when the underlying fundamentals are 12 months old, with no check that material corporate events (Chapter 11, M&A, fresh-start accounting, splits, delisting) have happened since the data was fetched | manifest packer has no `data_as_of` field per fact; no event-class scanner that gates the run | The WOLF report dated 2026-05-19 was built on May 2025 data and never mentions Wolfspeed's June 2025 Chapter 11 filing or September 2025 emergence that wiped out ~95–97% of the old equity. *"Putting a $24 HOLD on a post-bankruptcy shell is the kind of error that ends careers and gets the firm sued."* |
| RC9 | No cross-section arithmetic reconciliation — sections can carry contradictory headline numbers (rating + target + current price + market cap + share count don't have to agree) | each section writes independently; no global identity-equation check before render | CRM: $330 PT at "+32% upside" requires ~$250 share price, but the $141.9B market cap on ~818M shares implies ~$173 — the upside is actually ~+90%. WOLF: HOLD rating with target *below* the implied current price (-9%) is mathematically a SELL. NVDA: 65% TTM operating margin in prose vs 60.4% in the income-statement table. |
| RC10 | Chart and exhibit blocks render even when their data shape is broken — single-row peer tables, single-dot scatters, value-less waterfalls, fiscal-year axes labelled "Year 1 / Year 2 / TTM/Late", components that don't reconcile to 100%, redundant pies that disagree with each other | block packers (`packer/blocks/*.py`) have no minimum-data-quality gates; no axis-label fallback rule; no waterfall sum check; no duplicate-exhibit suppression | CRM "Peer Multiples Matrix" = 1 row. NVDA "P/E vs growth" scatter = 1 dot labelled "SUPPLIED DATA POINT". NVDA margin waterfall has a Cost-of-Revenue bar floating *above* 100% of revenue. NVDA ships *two* DC segment-mix pies that disagree with each other (88/9/2/1 vs 87.9/8.7/1.4/1.3/0.7). "Sub-10%" rendered as a red "-10%". |
| RC11 | One framework for every name — SaaS, semis, and distressed companies all run through the same generic stock_initiation framework, missing the metrics each industry actually trades on, and missing the entire concept of a distressed-mode template | `stock_initiation.facts.json` + `stock_initiation.json` are single-flavor | CRM (SaaS) has no cRPO/RPO, no NRR, no Rule of 40, no billings, no SBC dilution bridge — the metrics the entire CRM debate runs on. NVDA (semis) has no quantified customer concentration, no China/export-control revenue exposure in dollars, no Blackwell ASP/volume, no purchase commitments. WOLF (distressed) is praised for "best-in-peer 9.8% 3-year revenue CAGR" and "premium growth status" *while in bankruptcy*. |

A subset of issues are pure data-source gaps that no amount of better prompting will close: GTC announcements, hyperscaler capex commentary, export-control dollar exposure, 10-K customer-concentration disclosures, insider 10b5-1 sales, short interest, **post-bankruptcy capital structure**, **post-emergence share counts**, **debt maturity schedules**. Those need to be **fetched and packed into the manifest**, not coaxed out of the LLM.

---

## 3. Workstreams

The work splits cleanly into ten workstreams. Order matters: the *report-blocking* gates (WS10 data freshness, WS3-B material-events scanner) ship first — anything else done while WOLF-class staleness is still possible would be dangerous. Helpers (WS7) and facts expansion (WS2) come next; then the validator (WS4) prevents regression; chart gates (WS8), industry-mode specialization (WS9), and sourced-only consensus surfacing (WS1) close out content quality.

### WS1 — Make the deterministic consensus the headline; force every bull/bear point to carry a source citation (RC2)

**Reversal from the prior draft.** The LLM does not author its own rating or price target. The product position is: OpenLIA surfaces **what the market is saying**, with citations, and never speaks in the first person about whether to buy a stock. The reviewer's "no rating, no PT" complaint is real, but the fix is not LLM advocacy — it is making the *deterministic* consensus rating, the *deterministic* mean target, and *sourced* upgrade/downgrade flow visible and prominent.

The current `analyst_view` section is directionally correct (no LLM-authored rating, no LLM-authored target) but it is buried in the body of the report and the bull/bear case lacks specificity. The fix is structural prominence + tighter sourcing rules.

Files to edit:
- `packages/core/src/openlia/reports/frameworks/stock_initiation.json` — section `investment_recommendation` (rename to `analyst_view` consistently): keep the prohibition on LLM advocacy, but require the section to lead with three deterministic blocks already populated by the runner: (a) `rating_badge` showing the consensus rating from `analyst_consensus_rating` (Strong Buy / Buy / Hold / Sell / Strong Sell), (b) `metric_cards` showing mean / high / low / N analysts target band from `analyst_target_mean`, `analyst_target_high`, `analyst_target_low`, `analyst_count`, plus implied upside from `consensus_upside_pct`, (c) a `chart:bar` of `analyst_rating_distribution` (Strong Buy → Strong Sell counts).
- Same section, add a fourth deterministic block: **recent rating changes table.** Built by a new helper that scans `get_company_news` results + the catalyst-pack output (WS3) for upgrade / downgrade / PT-change events and extracts rows: Date, Firm, Action (Upgrade/Downgrade/Initiate/Reiterate/PT Change), From → To, Target Price. Each row carries its source `[N]` citation. If no events surfaced in the period, the table is omitted — never fabricated.
- Bull/bear `comparison_split` rules tightened: every left-column item is an **argument observed in a cited source** (analyst note, management commentary on earnings call, news article, regulatory filing). Every right-column item is the same on the bear side. Every item carries an inline `[N]` citation. Items that read like the LLM's own opinion ("we believe…", "in our view…", "our base case…") fail validation. The acceptable surface verbs are: `JPMorgan rates`, `consensus reflects`, `management guided`, `the company disclosed`, `Bernstein argued`, etc.
- `valuation_analysis` section: deterministic math, sourced conclusions. The LLM does **not** choose a target multiple or a target price. Instead, it presents three blocks driven by deterministic helpers (WS7): (a) **peer-multiple implied range** — applies the peer median P/E and EV/EBITDA to the subject's `eps_ttm`, `pe_ratio_forward` consensus EPS, and `ebitda_ttm`, returning a high/median/low implied price; (b) **historical P/E band** — current P/E vs 5-year mean and ±1σ, from a deterministic helper; (c) **sourced sell-side range** — high / mean / low analyst PT from `analyst_target_high`, `analyst_target_mean`, `analyst_target_low`, plus a note on the spread. The prose interprets the three ranges side-by-side: "Peer-multiple implied range is $X–$Y; the historical P/E band suggests fair value of $Z; the sell-side range is $A–$B (mean $C)." It does **not** synthesise these into a single OpenLIA target.
- `packages/core/src/openlia/reports/frameworks/stock_initiation_style_guide.md` — rewrite §2.12 (Valuation) and §2.13 (Investment Recommendation) so they match the no-LLM-advocacy stance. The current style guide telling the LLM to write `"We initiate coverage of NVDA with an Overweight rating and a 12-month price target of $185"` is removed. Replace with explicit examples of the sourced-only voice: `"Consensus reflects a Buy rating with a mean 12-month target of $185, implying 22% upside [c1]. The bull case observed in Goldman's May 12 note centres on…"`.
- Cover: `rating_badge` on the hero is populated from `analyst_consensus_rating` (deterministic). `target_price` on the hero is `analyst_target_mean` (deterministic). Upside % is `consensus_upside_pct` (deterministic). The cover never carries an OpenLIA-authored verdict.

Acceptance: the next NVDA run shows the deterministic consensus rating + mean PT on the cover, surfaces a recent-rating-changes table built from cited news in the analyst_view section, and the bull/bear case items every carry an `[N]` citation and use sourced-voice verbs. The validator in WS4 rejects any first-person advocacy phrasing.

### WS2 — Expand the facts slice so the LLM doesn't have to guess (RC1, RC3)

Every fabricated number in the review traces to a fact that *wasn't* in the slice. Add deterministic extractors for everything the style guide and section briefs already reference but currently get fabricated.

New facts to register in `facts/extractors/stock_initiation.py` and wire into `frameworks/stock_initiation.facts.json`:

**Segment / business-model facts (closes the FY mix bug):**
- `segment_revenue_latest` — dict of segment name → dollars for the *same* fiscal year as `revenue_annual[-1]`. Source: EODHD `SegmentBreakdown` if present; otherwise leave null and the LLM is told to drop the pie chart rather than fabricate.
- `segment_revenue_yoy` — segment dollar series so the report can show growth, not just mix.
- `fiscal_year_end_latest` — the actual date string for `revenue_annual[-1]`; every prose section is required to label years using this string (see WS4 validator).
- `segment_share_latest` — derived percentages so the LLM doesn't compute them.

**Capital structure and returns:**
- `cash_and_short_term_investments_annual` — fixes the "$10.6B cash" understatement; combines `cash` + `shortTermInvestments`.
- `total_debt_annual` — already there, but add `net_cash_annual` = cash+ST investments − total debt.
- `free_cash_flow_annual`, `operating_cash_flow_annual`, `capex_annual` from the cash flow statement.
- `roe_ttm`, `roic_ttm`, `roa_ttm`.
- `sbc_annual` (stock-based comp) — major for NVDA, drives GAAP/non-GAAP gap.
- `buyback_authorization`, `dividend_per_share_annual`, `dividend_yield`.
- `beta`, `shares_outstanding`, `float_shares`, `short_interest_pct`.

**Forward consensus (closes the "no projections" bug):**
- `consensus_revenue_fy_next`, `consensus_revenue_fy_next_plus_one`, `consensus_revenue_fy_next_plus_two`.
- `consensus_eps_fy_next`, `consensus_eps_fy_next_plus_one`, `consensus_eps_fy_next_plus_two`.
- `consensus_revenue_growth_fy_next`, `consensus_eps_growth_fy_next`.
- `next_quarter_revenue_guide_midpoint`, `next_quarter_revenue_guide_low`, `next_quarter_revenue_guide_high` — pulled from `get_upcoming_earnings` / management commentary when available.

**Peer absolute sizes (closes the "comps table is just NVDA" bug):**
- `peer_market_cap`, `peer_revenue_ttm`, `peer_revenue_cagr_3y` (already there), `peer_net_margin_ttm`, `peer_operating_margin_ttm`, `peer_fcf_yield`.
- Peer list must be non-empty for an initiation; if the manifest packer cannot resolve at least two peers, the runner should fail loudly rather than ship a single-row peer table.

**Forward valuation:**
- `pe_ratio_forward` (already there) — extend with `ev_to_ebitda_forward`, `ev_to_sales_forward`, `fcf_yield`.

The manifest packer (`runtime/report_v2/packer/`) also needs to fetch the corresponding EODHD endpoints (`get_earnings_trends`, `get_upcoming_earnings`, `get_company_news`) for the subject ticker on every stock-initiation run, not just when a section asks for them.

Acceptance: the facts slice for a stock-initiation pack contains, at minimum, the union of the lists above. Each new fact has a unit test in `packages/core/tests/llm/runtime/report_v2/facts/`.

### WS3 — Fresh-catalyst pipeline *and* material-events gate (RC4, RC8)

Two responsibilities, now joined in one workstream because the second one is structurally the same pipeline as the first — both are "scan public sources for events the vendor feed doesn't surface and pack them into the manifest before body sections run."

**Part A — fresh-catalyst pack (RC4, unchanged direction).** Pre-section pass that fetches `get_company_news` + targeted web searches for GTC / product announcements, customer-concentration disclosures, hyperscaler capex prints, sovereign-AI announcements, export-control changes. Results packed into the manifest as ordinary citable entries; body sections cite them like any other source.

**Part B — material-events gate (RC8, new).** The same pipeline scans for **report-blocking corporate events** that, if found, change the report's structure (or stop it from running):

- **Chapter 11 / Chapter 7 filing** in the last 36 months.
- **Emergence from bankruptcy / fresh-start accounting** in the last 36 months.
- **Going-private transaction** (announced or completed).
- **All-stock or large cash M&A** where the target ceases to be an independent issuer.
- **Delisting** or trading-halt status.
- **Reverse / forward stock split** more recent than the latest available fundamentals.
- **Reverse merger / SPAC combination** post the latest available fundamentals.
- **Material restatement** of recent financials.

For every event class, the scanner pulls candidates from `get_company_news`, EDGAR (8-K item codes 1.03 bankruptcy, 2.01 acquisitions, 5.01 change in control, 5.03 charter changes, 8.01 other events), and targeted web searches for terms like *"<ticker> chapter 11"*, *"<ticker> fresh-start accounting"*, *"<ticker> emerged from bankruptcy"*. Each hit is timestamped and confidence-scored.

**Gate behaviour.** If a confirmed event is detected **after** the `data_as_of` date of the subject's fundamentals (see WS10), the runner refuses to render the standard stock-initiation report and emits one of two outcomes:

1. *Hard block.* For Chapter 11 / 7, fresh-start emergence, going-private, delisting, or material restatement: the runner fails with a structured error pointing at the event, and the user is offered either (a) re-run after a vendor data refresh, or (b) switch to the distressed-mode template (WS9).
2. *Warning banner.* For splits, reverse mergers, and recent M&A close: the runner proceeds but injects a deterministic banner block at the top of the report citing the event and flagging that figures may straddle the discontinuity.

For an event detected *before* `data_as_of`, the scanner still packs the event into the manifest so body sections cover it, but does not block the run.

Recommendation: build Part A and Part B in the same module — `runtime/report_v2/scanners/` — sharing the news/EDGAR/web fetch layer. Time-box Part B's event taxonomy to the seven classes above; expand later if needed.

Acceptance: (a) a May 2026 NVDA report mentions GTC 2026 and the Rubin platform somewhere in the body, with citations resolving to manifest entries the catalyst pack fetched. (b) Attempting to run a stock-initiation report for WOLF against May 2025 fundamentals on 2026-05-19 fails with a clear bankruptcy-detected error, surfaces the June 2025 filing and September 2025 emergence as evidence, and offers the distressed-mode template as the rerun option. **A run that misses a Chapter 11 filing is a P0 bug, not a quality miss.**

### WS4 — Numeric reconciliation validator (RC5, RC9)

A post-section validator that runs after all section files are written but before the report is rendered. It does **five** things:

1. **Year-label consistency.** Every section that mentions "FY20XX" must use a year that matches `fiscal_year_end_latest` or a year in `revenue_years`. Any mismatch fails the section and triggers a regenerate.
2. **Numeric ↔ fact equality.** Every quantitative figure in prose (≥4 chars or matching common ratio patterns) must match a manifest fact value within 1.0% tolerance, OR be derivable from manifest values via a small set of allowed operations (sum, ratio, growth %). If a number cannot be matched, the section is sent back with the specific number and the closest fact value attached to the retry prompt.
3. **Arithmetic spot-check.** For named ratios the report cites (PEG, EV/EBITDA, gross-to-operating margin spread), the validator recomputes from inputs and rejects if the cited result disagrees by >0.5%.
4. **Cross-section identity equations (RC9).** Eight equations must hold across the whole report, computed once from the deterministic facts and the consensus rating/PT, then checked against everything the prose says:
   - `current_price × shares_outstanding ≈ market_cap` (within 2% — small rounding allowed).
   - `(consensus_target_mean − current_price) / current_price ≈ consensus_upside_pct` (within 0.5pp).
   - `revenue_ttm × operating_margin_ttm ≈ operating_income_ttm` (within 0.5%).
   - Every prose mention of operating margin agrees with `operating_margin_ttm` within 0.5pp.
   - Every prose mention of current price uses the same value (within 1%).
   - Every prose mention of market cap uses the same value (within 1%).
   - **Rating ↔ upside coherence.** If `consensus_rating ∈ {Buy, Strong Buy}` and `consensus_upside_pct < 0`, OR `consensus_rating ∈ {Sell, Strong Sell}` and `consensus_upside_pct > 0`, surface a warning block on the cover ("Consensus rating implies upside but mean target is below current price — likely data lag") rather than render the contradiction silently. A target *below* current price with anything stronger than Hold fails the run.
   - Every projection-table figure agrees with the `forecast_table` helper output (WS7) within 0.5%.
5. **Date-stamp coverage (RC8 link).** Every section that cites a headline figure (revenue, margin, cash, debt, market cap, share count) must reference a `data_as_of` date that is no older than the per-fact freshness budget defined in WS10. Sections that cite stale figures without a "data as of <date>" annotation fail.

This is the single most leveraged piece of work in the plan: it converts a class of LLM errors from "ship anyway" to "regenerate." It also creates a structured trail of what each section claimed vs what the facts say, which is invaluable for future debugging.

Files: new module `runtime/report_v2/validators/numeric_consistency.py`; integrated into `runner.py` after section write, before manifest finalisation.

Acceptance: feeding the validator the existing reports flags every numbered defect in the reviewer's note — the CRM $330/+32%/$141.9B contradiction, the WOLF $3.30B vs $3.13 × shares mismatch, the WOLF HOLD-with-negative-upside contradiction, NVDA's 65% op margin vs 60.4% income-statement table, the broken PEG, the FY label slips on both CRM and WOLF, and the "increases that are decreases" balance-sheet sentences. Validator output is a structured list of failures with section, number, expected fact, and tolerance — not a free-text complaint.

### WS5 — Cover and rail placement (RC6)

The consensus rating, mean PT, and implied upside belong on the first page. The market-data strip (52W range, ADTV, forward P/E) belongs in the rail *next to* the cover, not at the document tail. None of these are LLM-authored — they come from the deterministic facts in WS2.

Two changes:
- Move the rail's `quick_stats` rendering to render adjacent to the cover hero rather than as a tail card. This is a frontend report-renderer change in `frontend/src/components/report/` — keep server-side structure unchanged.
- Cover hero adds `consensus_rating`, `consensus_target_mean`, and `consensus_upside_pct` fields, all populated from the deterministic facts emitted by the runner (no LLM authorship). The badge component renders the rating; an upside chip renders the mean PT and percent move from current price. Source citation on every field points back to the AnalystRatings manifest entry.

Acceptance: the first thing a reader sees is the deterministic consensus rating + mean PT + upside %, with the market-data context on the same page. 52W range / ADTV / volume are no longer the last thing in the document. No first-person OpenLIA verdict anywhere on the cover.

### WS6 — Style-guide and framework wording cleanup

Minor but worth doing in the same branch:

- Drop or rewrite the "Avoid press-release marketing language" example so the LLM stops emitting NVIDIA's tagline.
- Add an explicit prohibition on tombstone phrases like "more assumption-heavy than the current fact set supports" — the analyst's job is to make the assumptions, not to refuse to.
- Rewrite the section briefs for `business_model`, `products_and_services`, and `historical_financials` to require the prose to *cite the segment-revenue facts by name* (forcing the LLM to use them rather than reconstruct from memory).
- Remove the "Recent Developments" section's permission to lean on cached "last 12 months" content — it must be the **last 30 days only**; anything older than 30 days belongs in `historical_financials` discontinuities or `recent_developments` only if it has ongoing market consequence.

### WS7 — Deterministic financial helpers (RC7, and the math-correctness backbone for WS1 / WS2 / WS4)

The reviewer's most damaging errors — 65% TTM operating margin, PEG of 0.68x from 45.5 ÷ 100, "$5.20.1B ÷ 44.8x ≈ 45.5x" — are all LLM arithmetic. The fix is: **the LLM never computes a number that ends up in the report.** Every ratio, projection, sensitivity, and implied price is computed by a Python helper module, registered as a fact, and the LLM's only job is to cite the fact and write prose around it.

This workstream is the structural backbone that makes WS1 sourced-only, WS2 data-rich, and WS4 enforceable. It belongs in a new module: `runtime/report_v2/facts/helpers/`.

**Helpers to ship:**

*Liquidity and leverage:*
- `net_cash(cash, short_term_investments, long_term_investments, total_debt) -> Fact` — closes the "$10.6B cash" understatement bug; returns net cash and the full breakdown.
- `current_ratio`, `quick_ratio`, `debt_to_equity`, `interest_coverage` — exposed as deterministic facts so the Financial Analysis section just cites them.
- `cash_runway_quarters(cash_and_st_investments, ttm_operating_cash_burn)` — only emits when OCF is negative; otherwise None.

*Profitability and returns:*
- `roe_ttm(net_income_ttm, average_equity)` — uses average of beginning and ending equity, not a point estimate.
- `roic_ttm(nopat, average_invested_capital)` — NOPAT and invested-capital computed within the helper so the conventions are stable.
- `roa_ttm`, `fcf_yield(fcf_ttm, market_cap)`, `fcf_margin(fcf_ttm, revenue_ttm)`.
- `margin_bridge(prior_margins, current_margins) -> dict` — returns the period-over-period spread per margin line (gross, operating, net) so the Financial Analysis section can show a real bridge instead of fabricating one.

*Valuation:*
- `peer_multiple_implied_range(subject_eps, subject_ebitda, peer_pe_dict, peer_ev_ebitda_dict) -> dict` — applies peer median, 25th-percentile, and 75th-percentile multiples to subject inputs; returns implied prices at each percentile and the spread. This replaces the LLM's "pick a multiple, multiply" step entirely.
- `historical_pe_band(daily_pe_series, current_pe, window_years=5) -> dict` — returns mean, ±1σ, current percentile, and z-score.
- `peg_ratio(forward_pe, forward_eps_growth_pct) -> float` — single-purpose helper specifically because the reviewer caught the LLM using trailing revenue CAGR. The helper requires forward EPS growth as input and refuses to run on a revenue input. Returns None when inputs are missing rather than emitting a wrong number.
- `dcf_intrinsic_value(forward_revenue_path, ebit_margin_path, tax_rate, capex_pct_of_revenue, change_in_nwc_pct_of_revenue_change, terminal_growth, wacc, shares_outstanding) -> dict` — returns intrinsic value per share, equity value, enterprise value, and a sensitivity grid (terminal growth × WACC). The LLM only chooses the inputs (with stated bounds enforced by the helper: WACC in [5%, 20%], terminal growth in [0%, 4%], etc.); the helper does all math. The valuation section cites the helper output directly.
- `sum_of_parts(segment_revenue_dict, segment_multiple_dict) -> dict` — for multi-segment names where SOTP is more honest than a single multiple.

*Forecast and sensitivity:*
- `forecast_table(history, consensus, growth_assumptions) -> dict` — takes the consensus revenue/EPS path from `consensus_revenue_fy_next*` facts plus the analyst's named growth assumptions (each tagged with a source citation), and produces the 3-year forward table. The LLM writes the *narrative* around assumptions; the table itself is the helper's output. The "Financial Projections section contains zero projections" complaint is closed by *the helper always emitting a table*, not by trusting the LLM to remember to include one.
- `sensitivity_grid(base_inputs, sweep_dim_a, sweep_dim_b) -> dict[str, dict]` — generic two-dimensional sweep, used by the valuation section to show "EPS × P/E → implied price" grids.
- `actual_vs_consensus(consensus_eps_fy_next, our_eps_assumption) -> dict` — emits the comparison row the style guide already asks for.

*Working-capital cycle:*
- `cycle_days(receivables, inventory, payables, revenue, cogs) -> dict` — DSO, DIO, DPO, and cash conversion cycle from raw line items so the Financial Analysis efficiency-comparison table doesn't depend on the LLM doing four divisions correctly.

*New helpers added on second-batch feedback:*
- `reverse_dcf(current_price, shares_outstanding, current_fcf, wacc, terminal_growth) -> dict` — solves for the implied FCF growth rate the market is currently pricing in. Used by Valuation prose: *"At the current $173 share, the market is pricing in 11.4% FCF CAGR for the next decade against a consensus that models 13%."* Addresses CRM reviewer ask for an explicit "what's priced in" reverse-DCF.
- `football_field(method_outputs_dict) -> dict` — takes a dict keyed by methodology (`peer_pe`, `peer_ev_ebitda`, `dcf_base`, `dcf_bull`, `dcf_bear`, `historical_pe_band`, `sell_side_range`) where each value is `{low, mid, high}`, returns the data shape needed by a horizontal-bar exhibit overlaying all ranges with the current price as a vertical line. This is the chart the reviewer named explicitly in all three notes.
- `rule_of_40(revenue_growth_pct, fcf_margin_pct) -> float` — single-number SaaS health metric. Helper rejects requests for companies whose facts slice doesn't carry both inputs.
- `nrr_trend(prior_period_arr, current_period_arr_from_same_cohort) -> float` — dollar-based net revenue retention. Only emitted when the facts slice carries the cohort numbers; SaaS-mode only (WS9).
- `sbc_dilution_bridge(beginning_shares, sbc_issuances, buybacks_in_shares, ending_shares) -> dict` — reconciles share count change and reports SBC as a % of revenue and a % of FCF. Addresses CRM reviewer ask.
- `debt_maturity_wall(debt_tranches_with_dates) -> dict` — returns aggregated principal due per future year, used by Risk Analysis for leveraged or post-restructuring names.
- `recovery_waterfall(pre_petition_capital_structure, plan_of_reorganization_recoveries) -> dict` — for distressed mode; shows pre-petition claim → post-emergence recovery per claim class.
- `cash_runway_quarters(cash_and_st_investments, ttm_operating_cash_burn)` — *(also listed above; flagged explicitly for distressed mode where it is the headline metric)*.
- `consensus_vs_assumptions_table(consensus_facts, named_assumptions) -> dict` — accepts the analyst's named growth assumptions (each tagged with a source citation), renders them next to consensus, and flags any divergence above a configurable threshold. Drives the Projections section table.

**Integration plan.** Each helper is registered with the `register_fact` decorator just like the existing extractors (`compute` tier). The dispatcher exposes the resulting facts to whichever section's facts slice references them. The helpers themselves are unit-tested with golden inputs/outputs in `packages/core/tests/llm/runtime/report_v2/facts/helpers/` — these are pure Python with no LLM dependency, so coverage should be high (~95%) and tests are cheap.

**Prompt-side enforcement.** The section briefs for Valuation, Financial Analysis, and Financial Projections are rewritten to enumerate *which helper-derived facts must be cited*. Example for Valuation: *"Cite `peer_multiple_implied_range_pe`, `peer_multiple_implied_range_ev_ebitda`, `historical_pe_band`, and `dcf_intrinsic_value` by name in your prose. Do not perform multiplication, division, or growth calculations yourself — every numeric claim must come from one of the listed facts."* The WS4 validator enforces this: any prose number that isn't traceable to a fact value is rejected.

**Cost.** Helpers are pure Python and run on the server; they add zero LLM token cost. They reduce token cost overall because the LLM stops producing arithmetic the validator would reject. The cost is engineering time — roughly two weeks of focused work for the helper set listed above plus tests.

Acceptance: regenerating the NVDA report with WS1–WS4 disabled but WS7 enabled and the section prompts pointed at the helper facts produces a Financial Analysis section, Financial Projections section, and Valuation section in which every quantitative claim resolves to a helper-emitted Fact. The reviewer's "65% op margin," "PEG = 0.68x from 45.5÷100," and "no projections" complaints are all closed by helpers alone, before the validator even runs.

### WS8 — Chart and exhibit quality gates (RC10)

The reviewer's chart complaints reduce to a small number of structural defects each block packer can refuse at render time. The fix is gates inside `runtime/report_v2/packer/blocks/`, not better prompting.

**Block-level gates (refuse to render rather than ship a broken exhibit):**

- **`table`** — if rows count < the type's minimum (peer-comparison tables: ≥3 peers; comp-set tables: ≥3 names; historical financials: ≥3 years), the packer raises and the section is sent back with a directive to either gather more facts or drop the exhibit. *No more single-row "Peer Multiples Matrix."*
- **`chart:scatter`** — if `points` count < 3, refuse. *No more single-dot "P/E vs growth" scatters labelled "SUPPLIED DATA POINT."*
- **`chart:bar` / `chart:line` / `chart:area` / `chart:combo`** — every series must have a non-null `values` array, every value must have a sourced fact in the manifest, and `categories` must use **real date or fiscal-year labels** from the manifest — packers reject placeholder strings like `Year 1`, `Year 2`, `TTM/Late`. The packer's date formatter has a fallback to the subject's `fiscal_year_end_latest` and `revenue_years` facts; it never invents axis labels.
- **`chart:waterfall`** — components must sum to the stated totals within 0.5%. The packer recomputes the closing total from `items` and refuses if it doesn't equal the declared `total` row. Negative `Cost of Revenue` cannot push the running balance above 100% of starting revenue — a sign-check rule in the packer prevents this directly.
- **`chart:pie` / `chart:treemap`** — segments must sum to 100% within 1%. Block IDs are tagged with what the pie represents (e.g., `segment_mix:FY2026`); the report's section dispatcher refuses to render two pies with the same purpose tag, eliminating NVDA's two-mutually-inconsistent-pies bug.
- **All chart blocks** — `data_labels: true` is the default for blocks ≤ 8 data points. Bars with no values fail to render.
- **`metric_cards` and `key_finding`** — the formatter that renders a delta as red/negative must read the *sign* of the number, not the string. The "sub-10%" rendering as "-10%" bug is a string-vs-number formatting bug; fix in the cell formatter, not in prose.

**Section-level exhibit deduplication.** A section that emits two exhibits with the same `purpose_tag` (e.g., two `segment_mix` charts) has the second one stripped before render. Sections that emit zero exhibits when the brief required one are sent back.

**LLM-side prompt change.** Section briefs are rewritten to make exhibit data shape explicit: "If you cannot gather ≥3 peers, **drop** the peer-multiples table; do not emit a one-row table." This avoids the LLM trying anyway and getting rejected.

Files: extend each block packer in `runtime/report_v2/packer/blocks/` with a `validate_shape(block) -> Optional[ValidationError]` method; runner calls it before serialization.

Acceptance: feeding the existing CRM, NVDA, and WOLF reports through the WS8 packer gates rejects: the CRM single-row peer table, the NVDA single-dot scatter, the NVDA double-pie segment mix, the NVDA waterfall with Cost-of-Revenue above 100%, the CRM/NVDA bridge waterfalls with no data labels, and the NVDA margin-trend "Year 1 … TTM/Late" axis. Each rejection comes back as a structured error pointing at the specific defect.

### WS9 — Industry-mode specialization (RC11)

One framework can't serve SaaS, semis, and distressed companies equally well. Introduce three modes that share the base `stock_initiation` framework and override the facts slice, section briefs, and required exhibits.

**Mode selection.** The runner inspects the subject's `Industry` and `Sector` facts plus the WS3-B material-events scanner and chooses one of:

- `stock_initiation.saas` — for software / cloud / SaaS classifications.
- `stock_initiation.semis` — for semiconductor / hardware classifications.
- `stock_initiation.distressed` — for any name flagged by the material-events scanner as having had Chapter 11, fresh-start emergence, going-concern qualified audit opinion, or 30%+ negative TTM revenue growth with negative free cash flow. Distressed mode is sticky for 24 months post-emergence.
- `stock_initiation.generic` — current behaviour, default for everything else.

Modes are picked deterministically and shown to the user; the user can override the choice if the classification is wrong.

**Per-mode additions.**

*`stock_initiation.saas`:*
- Facts: `current_rpo`, `cRPO`, `cRPO_growth_yoy`, `billings_ttm`, `nrr_dollar_based`, `rule_of_40_score`, `gaap_vs_non_gaap_operating_margin_gap`, `sbc_pct_of_revenue`, `buyback_dollars_annual`, `agentic_or_ai_arr` (where disclosed).
- Required exhibits: cRPO-growth trend, FCF-margin trend, Rule-of-40 trend, SBC dilution bridge, dated catalyst calendar (next print, user conference, monetization milestones).
- Section emphasis: Business Model gets a paragraph on the segment-revenue split with explicit growth and attach-rate framing. Risk Analysis gets a seat-rationalization downside scenario tied to the macro cycle.

*`stock_initiation.semis`:*
- Facts: `customer_concentration_top1_pct`, `customer_concentration_top5_pct`, `geographic_revenue_split` (US / China / Rest of World), `china_export_control_exposure_dollars`, `inventory_dollars`, `purchase_commitments_dollars`, `book_to_bill`, `gross_margin_guidance_next_q`.
- Required exhibits: customer-concentration stacked bar, geographic revenue split, gross-margin-bridge waterfall, hyperscaler-capex tracker (industry-level), inventory and purchase-commitment trend.
- Section emphasis: Risk Analysis gets a dedicated China / export-control sub-section with the dollar exposure quantified. Industry Overview adds the hyperscaler-capex chart as a required exhibit.

*`stock_initiation.distressed`:*
- **Completely different cover.** Solvency-first: cash + ST investments, total debt, net debt, cash-runway quarters, next debt maturity wall, going-concern audit-opinion status, post-emergence float (if applicable). No growth bragging. No PEG. No "premium growth status" language.
- Facts: `cash_burn_ttm`, `debt_maturity_schedule`, `covenant_status`, `post_emergence_share_count`, `fresh_start_accounting_date`, `pre_petition_capital_structure`, `recovery_per_claim_class`, `dip_facility_details`.
- Required exhibits: debt-maturity wall, cash-runway chart, recovery waterfall, EV/Sales or EV/EBITDA peer comparison (**not P/E** — for distressed names trough P/E is meaningless and the reviewer called this out specifically on WOLF), share-price chart that spans through the *current* date (not stale).
- Section emphasis: thesis is framed as "equity is a call option on the post-bankruptcy enterprise"; valuation is sum-of-parts or asset-based; growth-mode framing is explicitly forbidden in the style guide for this mode.

Files: split `stock_initiation.json` and `stock_initiation.facts.json` into a base + four mode overlays; runner picks the right overlay at startup. Add a `report_mode_overrides/` directory.

Acceptance: WOLF re-run against current-as-of fundamentals classifies into `stock_initiation.distressed`, produces a debt-maturity wall and a recovery waterfall, uses EV/Sales rather than trough P/E for peer comparison, and contains zero "premium growth" framing. CRM re-run classifies into `stock_initiation.saas`, ships a cRPO trend, a Rule-of-40 row, and an SBC dilution bridge. NVDA re-run classifies into `stock_initiation.semis`, surfaces customer-concentration and China-exposure facts with dollar values, and adds the hyperscaler-capex tracker.

### WS10 — Primary-source reconciliation and freshness budgets (RC8, foundation under WS3-B and WS4 item 5)

The reviewer's most damning observation across all three notes: *"Single-vendor data with no sanity-checking. Everything keys off one feed (eodhd). No one cross-checked it against the 10-K/press releases, which is exactly how the WOLF staleness and the CRM fiscal-year slip got through."*

Two changes.

**A. Stamp every fact with `data_as_of` and a `source_tier`.**

Each Fact gains two new fields:
- `data_as_of`: the date of the data the Fact was derived from (e.g., the most recent filing date the vendor returned for fundamentals; the price-snapshot date for `current_price`).
- `source_tier`: `vendor` (EODHD), `primary_filing` (10-K / 10-Q / 8-K / press release), or `derived` (computed from other facts).

The manifest packer surfaces both fields in the manifest entry so prose can cite them and the renderer can display "Data as of <date>" badges on tables.

**B. Per-fact freshness budgets.**

Each Fact class has a maximum age in days. Examples:
- `current_price`, `pe_ratio_ttm`, `market_cap`: 7 days.
- Quarterly facts (`revenue_q`, `eps_q`): 100 days (i.e., latest available quarter must be no older than ~one quarter + buffer).
- Annual facts (`revenue_annual`, `eps_annual`): 380 days (latest fiscal year must be within ~13 months — one year + grace for late filers).
- Consensus facts (`consensus_revenue_*`, `consensus_eps_*`): 14 days.
- Analyst ratings (`analyst_consensus_rating`, `analyst_target_mean`): 30 days.

If any fact exceeds its budget, the runner refuses to render the report and surfaces "stale data" with the offending fact, its `data_as_of`, and the budget. The user can either refresh the vendor data or override the gate with explicit acknowledgement.

**C. Primary-source reconciliation pass (optional but recommended).**

For a configurable subset of headline facts (`revenue_annual[-1]`, `operating_income_annual[-1]`, `eps_annual[-1]`, `shares_outstanding`, `cash_annual[-1]`, `total_debt_annual[-1]`), the runner pulls the most recent 10-K filing text via EDGAR and runs a simple OCR + regex extraction (or LLM-extraction with a tight prompt) to confirm the vendor value. Disagreements above 1% flag a reconciliation warning that the analyst_view section is required to acknowledge: *"EODHD reported revenue of $X; the 10-K filed <date> reported $Y. Using the 10-K value."*

This is the most expensive new piece of work, so ship it as opt-in for the first iteration and only on the top 1,000 names by market cap. Expand once the false-positive rate is known.

Files: `runtime/report_v2/types.py` extend `Fact` with `data_as_of` / `source_tier`; new module `runtime/report_v2/reconciliation/`; new validator pass tied into WS4 item 5.

Acceptance: every Fact in a regenerated report carries a `data_as_of`. The runner refuses to ship a WOLF report against May 2025 fundamentals on a 2026-05-19 timestamp without an explicit user override and a "STALE DATA" cover banner. Reconciliation finds the CRM fiscal-year slip (vendor labelled the FY2022 number as FY2021) by comparing the 10-K filing date to the vendor's `fiscal_year_end` field.

---

## 4. Phasing

Nine PRs, sized so each is reviewable on its own. Order has been re-sequenced to put the *report-blocking* gates (WS3-B material-events scanner, WS10 freshness budgets) first — shipping any quality improvements while WOLF-class staleness bugs are still possible would be dangerous:

| PR | Workstream | Why this order |
|----|-----------|---------------|
| P1 | WS10 (data freshness + `data_as_of` on every Fact) | Block staleness *before* anything else ships. After P1, no report can quietly use 12-month-old data. |
| P2 | WS3-B (material-events gate) | With freshness in place, add the corporate-events scanner. After P2, a Chapter 11 filing cannot slip through. |
| P3 | WS2 (facts expansion) | Now safe to broaden the data surface — staleness and bankruptcy gates are guarding it. |
| P4 | WS7 (deterministic helpers) | Stand on top of P3's expanded facts. Math correctness becomes a property of the pipeline, not the model. |
| P5 | WS8 (chart and exhibit quality gates) | Cheapest large quality win; packer-level rejections need no prompt iteration. Ship in parallel with P4 if capacity. |
| P6 | WS1 (sourced-only consensus surfacing) + WS6 (style cleanup) + WS9 (industry-mode specialization) | Now the framework can point sections at helper-derived facts, sourced rating/PT data, *and* the correct industry overlay. |
| P7 | WS4 (validator) | Run it on P6 output first to confirm it catches the historical CRM / NVDA / WOLF bugs as regression tests. |
| P8 | WS3-A (catalyst pack — fresh-catalyst news) | Now that staleness is fixed and the validator catches arithmetic, the catalyst pack is purely additive. |
| P9 | WS5 (rail/cover placement) | Pure rendering; ship last so QA isn't conflated with content changes. |

Each PR ships with regenerated CRM, NVDA, and WOLF reports plus a one-page diff vs the previous version, so the quality lift is visible across all three reviewed names.

---

## 5. Risks and open questions

- **EODHD data completeness.** Several of the new facts (`SegmentBreakdown`, segment yoy, peer absolute sizes, `next_quarter_revenue_guide_*`) may not be reliably present for every name. The facts framework already returns `null` cleanly; the question is how many of the proposed exhibits *gracefully degrade* vs being core to an initiation. Recommendation: segment revenue and forward consensus are core (block the report if missing); SBC / buyback / short interest are nice-to-have (omit silently).
- **DCF input bounds.** Resolved: the `dcf_intrinsic_value` helper in WS7 owns the math and enforces input ranges. The LLM still chooses inputs (revenue growth path, terminal growth, WACC) within those bounds and tags each with a citation to where the assumption is supported (consensus growth rate, a sourced WACC, etc.). The helper output is the canonical valuation number; the LLM does not re-derive it in prose.
- **Sourced-rating coverage.** WS1 depends on EODHD AnalystRatings being populated for the subject ticker. For smaller-cap names or international tickers where AnalystRatings is sparse, the cover and analyst_view section omit the consensus block entirely rather than fabricate one. Open question: should the report runner refuse to initiate coverage of a name with zero analyst coverage, or ship a "no analyst coverage available" badge? Default to the badge; flag for product review.
- **Catalyst pack scope creep.** Option B is a meaningful new pipeline stage. Time-box it; if it isn't materially better than Option A after a week of iteration, ship Option A and revisit.
- **Validator false positives.** Numeric reconciliation is harsh — small rounding can fail a section. The tolerance band (1.0% / 0.5%) is a starting guess. Tune on the existing NVDA report corpus before turning the validator into a blocking gate.
- **Helper test surface.** Each WS7 helper needs golden-value tests. Easy for ratios; harder for DCF and historical P/E band which depend on time-series inputs. Plan: ship the simple helpers (ratios, margin bridge, peer-multiple range) first; gate DCF and band helpers behind a richer test fixture.
- **Material-events false negatives.** WS3-B is only as good as the news + EDGAR + web-search scan. A confirmed bankruptcy that the scanner misses leaves the WOLF failure mode intact. Mitigations: (a) ship a manual override flag the user can set on a per-ticker basis ("treat as distressed"); (b) keep the scanner's seven event classes tight and well-tested rather than chasing every edge case; (c) document the scanner's recall on a labelled corpus of historical Chapter 11s before turning it into a hard gate.
- **Material-events false positives.** Hard-blocking the runner on a vendor-data hit for an event the user knows didn't actually happen is annoying. The override flow must be one click. Operationally, false positives are far less costly than false negatives — bias toward over-blocking.
- **Industry-mode misclassification.** A SaaS-mode framework rendered for a hardware company is jarring. Show the chosen mode prominently on the cover ("Initiation report — SaaS specialization"), make the override one click, and keep mode selection deterministic + auditable.
- **EDGAR rate limits + parsing cost for WS10-C.** Pulling 10-Ks through EDGAR is fine for low volume but rate-limited; LLM-extraction of headline figures from 10-K text costs tokens. Ship reconciliation as opt-in / sampled before defaulting it on.
- **Chart-gate scope creep.** Each block type has its own minimum-shape rules. Resist the urge to write twenty different validators; ship the six gates listed in WS8 first (peer-table-min-rows, scatter-min-points, no-placeholder-axes, waterfall-sum-check, pie-sum-check, data-labels-default) and revisit only after the regeneration shows new defects.

---

## 6. Definition of done

The branch is not done until **all three** of the reviewed reports (CRM, NVDA, WOLF) regenerate to the standards below, not just NVDA.

**Universal requirements (every report):**

1. Lead with the **deterministic consensus** rating, the mean analyst PT, and the implied upside/downside vs the current price — on the cover, never in prose, never first-person.
2. Show three deterministic-helper-derived valuation ranges side-by-side via the `football_field` exhibit: peer-multiple implied range, historical P/E band (or EV/Sales band for distressed), and sell-side high/mean/low. Present each as data; do not synthesise into a single OpenLIA target.
3. Present a 3-year forward revenue / EPS / margin forecast emitted by the `forecast_table` helper, that explicitly cites the consensus mean and either matches it or attaches a cited reason for any named growth assumption that diverges.
4. Use one consistent fiscal-year label across every section, matching the company's actual fiscal calendar. Charts use real fiscal-year axes — never "Year 1 / Year 2 / TTM/Late."
5. Carry a peer-multiples table with **at least three** real peers populated on the metrics appropriate to the industry mode. Single-row peer tables and single-dot scatters cannot ship — packers refuse them.
6. Carry a recent-rating-changes table in the analyst_view section that surfaces upgrade/downgrade/PT-change events from the last 90 days, each row sourced. Bull and bear case items every carry an inline `[N]` citation and use sourced-voice verbs ("Goldman argues", "management guided", "Bernstein flagged") — no first-person voice anywhere.
7. Pass the numeric consistency validator with zero unresolved discrepancies. Every quantitative figure in prose traces to a Fact emitted by an extractor or helper, not LLM arithmetic. The eight cross-section identity equations in WS4 item 4 all hold.
8. Every Fact carries a `data_as_of` and a `source_tier`. No fact in the report exceeds its freshness budget. Stale-data hard-block is on by default; bypassing it requires explicit user override and a cover banner.
9. Render the rating and market-data strip on the first page, not the last.
10. Chart-quality gates pass: no single-row peer tables, no single-dot scatters, no value-less waterfalls, no waterfalls that don't sum to their declared totals, no duplicate exhibits with the same purpose tag.

**Report-specific bars:**

11. *CRM* — classifies into `stock_initiation.saas`. Ships cRPO actuals + growth trend, NRR, Rule of 40, SBC dilution bridge, dated catalyst calendar. Headline numbers reconcile: market cap, current price, share count, target, and upside % all agree. Fiscal-year labels match the 10-K. Peer table covers MSFT, ORCL, SAP, ADBE, NOW, HUBS, INTU, WDAY (whichever subset the facts slice resolves).
12. *NVDA* — classifies into `stock_initiation.semis`. Mentions GTC 2026 / Rubin in the body, with citations resolving to catalyst-pack manifest entries. Quantifies customer concentration and China / export-control revenue exposure in dollars. Ships a hyperscaler-capex tracker exhibit. Operating margin is one number (60.4%, sourced) everywhere. PEG is computed via the helper or omitted; the broken `45.5 ÷ 100` derivation is gone.
13. *WOLF* — classifies into `stock_initiation.distressed`. Cover leads with solvency: cash + ST investments, total debt, cash-runway quarters, next debt maturity. Mentions the June 2025 Chapter 11 filing and September 2025 emergence as front-and-center facts, not as a footnote. Uses EV/Sales or EV/EBITDA — never trough P/E — for peer comparison. Share-price chart spans through the current date with the bankruptcy gap visible. Zero "premium growth status" or growth-CAGR-bragging framing. Equity is framed as a call option on the post-emergence enterprise.

If a reviewer can read the regenerated CRM, NVDA, and WOLF notes side by side and reach any of the conclusions *"this is not an initiation report"*, *"the target and upside don't reconcile"*, or *"this would mislead a client and expose the firm"*, the work is not done.
