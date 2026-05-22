# Equity Research v2.2 Helper Stack — Implementation Plan

**Date:** 2026-05-22
**Branch:** `feat/equity-research-engine-plan` (foundation); per-task branches downstream
**Status:** Sequencing plan for the 24-task backlog defined across the five design docs

---

## 0. Scope and prerequisites

This plan sequences the build of the equity research v2.2 helper stack. It assumes:

- The five design docs are accepted as the contract (see project root: `planning/2026-05-21-*` and `planning/2026-05-22-*`).
- Existing 8 library helpers in `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/`: `budget_variance`, `business_investment`, `chart_builder`, `dcf_valuation`, `excel_builder`, `forecast_builder`, `ratio_calculator`, `saas_metrics`. Three are slated for deprecation in PR 2.5 (`budget_variance`, `business_investment`, `ratio_calculator`); one for repurposing in PR 2.9 (`saas_metrics → saas_kpi_panel`); the rest stay. All 8 migrate to the new schema in PR 0.2.
- Stage 8 verifier is already wired (commit `597c5281` on main).

Out of scope here:
- Skill docs for non-complex helpers (covered by their structured `SelectionGuidance` cards instead).
- Wave 2 sector modules (parked under task #22).
- Qualitative framework helpers (parked under task #9).

---

## 1. Phase overview

Six phases. Phase 0 is hard prerequisite for everything else; Phases 1-2 unblock most of Phases 3-5.

| Phase | Theme | Tasks | Rough PR count | Blocks |
|---|---|---|---|---|
| 0 | Foundation — schema, registry, materialization | (no backlog task — new) | 4 PRs | everything |
| 1 | Data spine | #2, #3 | 2 PRs | Phases 2-5 |
| 2 | Core analytics — Wave 0 helpers | #1, #6, #11, #12, #13, #14, #7, #21, #15, #23, #8 + risk/macro split | 11 PRs (PR 2.1-2.11) | sector work |
| 3 | Sector modules — Wave 1 | #16, #17, #18, #19, #20 | 5 PRs | none |
| 4 | Supporting libraries | #4, #5 | 2 PRs | none |
| 5 | Future / parked | #9, #10, #22 | deferred | n/a |

---

## 2. Phase 0 — Foundation (4 PRs)

**Goal:** the schema, registry, and materialization stage exist and are wired through the runner before any helper logic lands. No helper task starts until Phase 0 is merged.

### PR 0.1 — Schema sub-models + ArtifactType registry

**Implements:** schema-and-skills doc §2 (ArtifactType registry), §3 (sub-model schema), §4 (boot validation), §5 (verifier coherence); artifact-injection doc §2 (RenderableArtifact base, Fidelity enum)

**Files:**
- `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/__init__.py` — extend with sub-model `HelperSchema`, keep back-compat `description` field
- `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/categories.py` (new) — closed `Category` enum
- `packages/core/src/openlia/artifacts/__init__.py` (new) — `RenderableArtifact` base, `Fidelity` enum
- `packages/core/src/openlia/artifacts/registry.py` (new) — load `artifact_types.yaml`, expose `lookup(artifact_id) -> type[RenderableArtifact]`
- `packages/core/src/openlia/artifacts/artifact_types.yaml` (new) — seeded with placeholders for the artifact types the existing helpers already produce
- `packages/core/src/openlia/llm/runtime/report_v2/capabilities.yaml` (new) — L1 capability index: 14 category names + one-line summaries; source-of-truth file the dispatcher's `project_l1` reads
- Tests: registration validation (boot-time DAG), Category enum closure, capabilities.yaml shape

**Acceptance:** registering a helper with `produces_artifacts=["nonexistent"]` fails at registration; cycle in producer/consumer graph fails registry boot; `capabilities.yaml` schema validates at boot; existing 7 helpers still register (via back-compat wrapper — see PR 0.2 for the full migration); `Category` enum exposes all 19 entries (schema-and-skills §3.1) including `risk_macro`, `saas_kpis`, `llm_nlp`, `output`, `adapter` — registering a helper with a category string outside the enum raises `ValueError` at import time.

**Risk:** none meaningful; pure additive.

### PR 0.2 — Migrate existing 8 helpers to new schema

**Implements:** schema-and-skills doc §3.4 (projection rules), §8 (implementation order step 1)

**Files:** eight existing modules — `budget_variance`, `business_investment`, `chart_builder`, `dcf_valuation`, `excel_builder`, `forecast_builder`, `ratio_calculator`, `saas_metrics` — wrapped under `report_v2_2/tools/library_helpers/` with new `HelperSchema` (each declares `directory` / `selection` / `contract`). Implementations import from `report_v2/` (no duplication). The earlier plan referenced `peer_multiples_panel` and `commodity_exposure_tracker` — those do NOT exist as files in the v2 runtime, so they are dropped from PR 0.2 scope. `peer_multiples_panel` is built fresh in PR 2.1 (comparables suite); `commodity_exposure_tracker` is built in PR 2.11.

Note: `budget_variance`, `business_investment`, and `ratio_calculator` are slated for deprecation in PR 2.5. `saas_metrics` is slated for repurpose in PR 2.9. PR 0.2 still migrates all eight to the new schema as a holding step — deletion / repurpose happens in the named PR.

**Acceptance:** every existing helper has a `DirectoryEntry`, `SelectionGuidance` with non-empty `when_to_use` / `when_not_to_use`, and `MechanicalContract` with `produces_artifacts` populated. Registry boot-time DAG passes.

**Risk:** low. The migration is mechanical; tests already cover helper invocation.

### PR 0.3 — Stage 7a materialization

**Implements:** artifact-injection doc §1 (pipeline placement), §3 (SectionPlan schema), §4 (template defaults + overrides), §5 (materialization algorithm), §8 (verifier integration), §9 (testing strategy)

**Files:**
- `packages/core/src/openlia/llm/runtime/report_v2/section_plan.py` (new) — `SectionPlan`, `PlannerOverrides`, override resolver
- `packages/core/src/openlia/llm/runtime/report_v2/materialization.py` (new) — `materialize()` algorithm with dedup, back-references, canonical-site rule, orphan logging
- `packages/core/src/openlia/llm/runtime/report_v2/runner_v2.py` — insert Stage 7a between current Stage 6 and current Stage 7
- New verifier issue types: `block_artifact_too_large`, `block_plan_artifact_missing`, `block_section_plan_invalid`, `block_headline_missing_quantitative`
- Tests: each of the 7 test cases listed in §9 of the artifact-injection design doc

**Decision needed during this PR:** whether to expand the closed 14-type verifier enum to 18 or introduce a materialization sub-enum (open question §12.2). Pick one and commit it inside this PR.

**Acceptance:** end-to-end test runs a synthetic helper pipeline → produces typed artifacts → applies overrides → materializes deterministic markdown → drafter sees sectioned prompt. All seven targeted unit tests pass. **Stage 6 contract update:** runner_v2 Stage 6 emits `dict[ArtifactId, RenderableArtifact]` (typed Pydantic instances keyed by artifact_id) rather than free-form dicts; Stage 7a consumes that map directly. Verifier reads `helper.return_type` (introspected at registration) per schema-and-skills §5 — no second `shape_hint` lookup.

**Risk:** medium. The materialization algorithm has real complexity (dedup + canonical-site ordering). Mitigate with the unit-test matrix.

### PR 0.4 — ToolDispatcher projection + planner behavior + skill-doc CI lint

**Implements:** schema-and-skills doc §1 (four-tier exposure), §3.4 (projection methods), §6 (skills.md list); artifact-injection doc §4 (template defaults + planner overrides)

**Files:**
- `packages/core/src/openlia/llm/runtime/report_v2/tools/dispatcher.py` (new) — `project_l1`, `project_l1_5`, `project_l2`, `project_l3`
- `packages/core/src/openlia/llm/runtime/report_v2/templates/stock_initiation_v2/section_plan_defaults.yaml` (new) — first reference example, seeded with the existing artifacts
- `packages/core/src/openlia/llm/runtime/report_v2/stages/stage_3_clarifier.py` — update to surface L1 capability summary when asking the user what they want
- `packages/core/src/openlia/llm/runtime/report_v2/stages/stage_5_planner.py` — update output schema to emit `helper_selection: list[str]` (drives L2 load) and `section_plan_overrides: PlannerOverrides` (drives materialization). Planner sees L1.5 directly, not full schemas.
- `.github/workflows/ci.yml` — add skill-doc lint job that diffs `skills/<helper>.md` frontmatter (`produces_artifacts`, `consumes_artifacts`) against the helper's registered `MechanicalContract` and fails the build on mismatch
- Tests: projection at each tier returns only that tier's fields; mistake of adding a field to wrong sub-model caught by Pydantic; planner emits valid override deltas; clarifier surfaces correct L1 content

**Acceptance:** Stage 3 + Stage 5 planners receive L1 / L1.5 directly; L2 is loaded only after planner picks; L3 is on-demand. Stage 5 emits both helper selection and section_plan overrides as structured output. Skill-doc CI lint passes on the (so far empty) skills directory and rejects a synthetic mismatched skill doc in test.

**Risk:** medium. Stage 5 prompt rewrite is real prompt-engineering work — output-schema changes need careful prompt iteration. Mitigate with golden-output tests for 3-4 representative user prompts.

**Phase 0 exit gate:** all four PRs merged; `feat/equity-research-engine-plan` rebased into a clean PR against main; end-to-end smoke run against existing `stock_initiation_v2` template produces a valid (but minimal) report through the new pipeline.

---

## 3. Phase 1 — Data spine (2 PRs)

**Goal:** EODHD adapter + FinanceToolkit integration provide the data and math primitives that ~80% of Wave 0 helpers depend on.

### PR 1.1 — EODHD adapter + connector pattern (backlog task #2)

**Implements:** helper-stack doc §1.1 (data-source tagging stub), §2.1 (EODHD as data spine); connector adapter pattern (`mcp/sdk/web/cache_wrapper`) referenced in helper-stack doc

**Files:**
- `packages/core/src/openlia/data/connector_base.py` (new) — abstract `Connector` interface with `mcp`, `sdk`, `web`, `cache_wrapper` adapter subtypes; standard error envelope; cache key derivation
- `packages/core/src/openlia/data/eodhd/` (new package) — typed wrappers per EODHD endpoint, built on `Connector` adapter pattern
- Each wrapper registers as a `register_library_helper` entry with `data_dependencies=["eodhd.<endpoint>"]`
- `packages/core/src/openlia/data/sec_edgar/` (new package, **conditional**) — only created if Form 4 fallback is needed (see build-blocker below)
- **Build-blocker resolution required in this PR:** confirm whether `eodhd_insider_transactions` returns raw Form 4 codes (P/S/A/M/F/G/C/D/X) or only a coarse buy/sell flag.
  - If EODHD returns raw codes: PR 2.8 unblocked, no fallback needed.
  - If EODHD returns only buy/sell: scope SEC EDGAR Form 4 adapter inside this PR (insider_signal_panel cannot do code-filtering without raw codes; helper degrades materially otherwise).

**Acceptance:** all EODHD endpoints currently called from anywhere in the codebase now flow through the adapter; legacy direct-call sites removed; one integration test per endpoint using recorded fixtures; connector base class has at least two implementations (EODHD MCP + at minimum one other — could be the SEC EDGAR fallback if triggered).

**Risk:** medium. EODHD MCP endpoints may have rate/quota constraints not yet stress-tested. SEC EDGAR fallback adds scope if triggered.

### PR 1.2 — FinanceToolkit integration (backlog task #3)

**Files:**
- `packages/core/src/openlia/data/finance_toolkit/` (new) — thin wrappers that translate FinanceToolkit's `Toolkit` API into helper-registry-compatible functions
- ~15 helpers registered: ratios (PE, PB, EV/EBITDA, ROE, ROIC, etc.), Altman Z, DuPont 3-step, Sharpe, WACC, etc.

**Acceptance:** FinanceToolkit-backed helpers can be invoked through the registry; result Pydantic models match `RenderableArtifact` contract; license check confirmed MIT before merge.

**Risk:** low. FinanceToolkit is a stable library; integration is wrapping.

**Phase 1 exit gate:** Wave 0 helpers can fetch EODHD data and call FinanceToolkit math without writing custom integration code.

---

## 4. Phase 2 — Wave 0 core analytics (11 PRs)

**Goal:** the analytic backbone of an institutional initiation report. Tackle in dependency order. Each PR introduces helpers + their `section_plan_defaults.yaml` entries + their skills.md (where listed).

### PR 2.1 — Comparables (backlog task #1)

**Implements:** helpers-design doc §3 (comparables) including §3.1 (combined-range), §3.2 (peer-set construction), §3.3 (NM handling)

Comparables is the entry point because (a) it's a documented gap and (b) many downstream helpers (historical multiple trends, football field chart, justified multiples) reference its artifacts.

**Helpers:** `comparables.run`, `peer_set_builder`, `football_field_chart`
**Artifacts:** `peer_multiple_panel`, `implied_price_range`, `football_field_render`
**skills.md:** `comparables.md`

**Audit fixes to apply (from helpers-design §9):**
- EV → equity bridge: `implied_equity_value = implied_ev − net_debt` (do NOT add cash back; net_debt already includes the cash subtraction). Verifier asserts the formula.
- Combined range methodology: min / median / max of per-multiple medians. Do NOT use min-of-lows to max-of-highs (compounds dispersion).
- NM handling for loss-making periods: skip the multiple from the panel; do not coerce to zero or infinity.

**Acceptance:** runs against 5 test tickers across 3 sectors (tech, value/cyclical, financials); combined-range methodology matches design doc §3.1; EV → equity bridge audit-fix unit-tested; NM handling test with a synthetic loss-making peer.

### PR 2.2 — DCF engine + cost of capital (backlog tasks #12, #6)

**Implements:** supplement §2 (`cost_of_capital_builder`), supplement §3 (`dcf_engine` including mid-year convention, three TV methods, EV→equity bridge); helpers-design §3.2 (`sensitivity_table`), §3.3 (`tornado_diagram`), §3.4 (`scenario_weighting`), §3.5 (`reverse_dcf`).

The dependency anchor for everything valuation-related.

**Helpers:** `cost_of_capital_builder`, `dcf_engine`, `sensitivity_grid_builder`, `tornado_diagram`, `scenario_weighting`
**Artifacts:** `dcf_base_valuation`, `cost_of_capital_panel`, `sensitivity_grid`, `tornado_diagram_render`, `scenario_weighted_value`
**skills.md:** `dcf_engine.md`, `cost_of_capital_builder.md`

**Reference data sourcing:** Damodaran tables for country risk premium, equity risk premium, beta by industry. This PR establishes the refresh mechanism — a script that pulls the published tables on demand and stores a versioned snapshot under `packages/core/src/openlia/data/reference/damodaran/`. Manual refresh cadence (quarterly) documented in the package README. License: tables are publicly published with attribution; verify attribution requirements before merge.

**Decision needed during this PR:** multimodal chart rendering approach (open question §12.3) — charts emitted by sensitivity_grid / tornado_diagram either as inline base64 PNG, attached file references, or markdown-table fallback. Pick one and commit it inside this PR.

**Acceptance:** mid-year convention configurable; terminal value supports both Gordon and McKinsey Key Value Driver per design §5.3; CAPM / Hamada / build-up methods all produce results; verifier rejects `terminal_growth > risk_free_rate`; Damodaran data refresh script runs in CI and produces a valid snapshot.

### PR 2.3 — Alternative valuation methodologies (backlog task #13)

**Implements:** supplement §4 (`ddm_family` — Gordon / two-stage / three-stage / H-model with sustainable-growth check), §5 (`justified_multiples` — forward P/E from payout/(Re-g), P/B from (ROE-g)/(Re-g), EV/EBITDA approximation), §6 (`sotp_builder` — per-segment method, corporate-overhead capitalization, conglomerate discount, tax-on-segment-sale option).

**Helpers:** `ddm_family`, `justified_multiples`, `sotp_builder`
**Artifacts:** `ddm_valuation`, `justified_multiple_panel`, `sotp_segment_valuation`
**skills.md:** `ddm_family.md`, `justified_multiples.md`, `sotp_builder.md`
**Acceptance:** each DDM variant validates against published textbook examples (1-2 per variant); justified-multiple formulas derived from g/ROE/payout per supplement §5; SOTP supports per-segment valuation method choice (EBITDA multiple, DCF, P/S, book value, user-supplied) per supplement §6.

### PR 2.4 — Decision layer (backlog task #14)

**Implements:** supplement §7 (decision layer, five helpers jointly): §7.1 `price_target_blender`, §7.2 `expected_total_return`, §7.3 `risk_reward_calculator`, §7.4 `implied_upside_downside`, §7.5 `rating_band_assigner`. Also picks up helpers-design §3.6 `football_field_chart` outputs (decision-layer's blended PT feeds into the football field).

**Helpers:** `price_target_blender`, `expected_total_return`, `risk_reward_calculator`, `implied_upside_downside`, `rating_band_assigner`, `football_field_chart`
**Artifacts:** `price_target_consensus`, `etr_panel`, `risk_reward_panel`, `rating_recommendation`, `football_field_render`
**skills.md:** `price_target_blender.md`, `rating_band_assigner.md`
**Acceptance:** blender weights surfaced as configurable per supplement §7.1; ratings explainable (why-this-rating string in artifact) per supplement §7.5; ETR formula matches supplement §7.2 (capital return + dividend yield × horizon factor); rating bands default to {BUY +15% ETR, ADD +7%, HOLD ±5%, REDUCE -5%, SELL -15%} with risk/reward filter; football_field consumes outputs from PR 2.2 + PR 2.3 + comparables (PR 2.1).

### PR 2.5 — Business quality + statement integrity (backlog task #7)

**Implements:** helpers-design doc §4 (business quality / capital allocation) — all of §4.1 through §4.20 **except** §4.18 (beneish_m_score, shipped in PR 2.6). Audit fixes from §9 apply.

Scope is large enough that PR 2.5 may execute as 2-3 internal commits sequenced by panel grouping, but the §11 PR count treats it as one logical PR.

**Helpers (19 total — one per helpers-design §4.x except §4.18):**

Group A — return / value-creation panels (§4.1-§4.2):
- `roic_panel` (§4.1) — ROIC, ROIIC, economic profit, ROIC-WACC spread
- `quality_of_earnings_panel` (§4.2) — Sloan accruals, accruals_pct_of_ni, capitalized R&D %, composite quality score

Group B — capital allocation + shareholder return panels (§4.3, §4.7, §4.8, §4.15, §4.16):
- `capital_allocation_history` (§4.3)
- `fcf_conversion_track_record` (§4.7)
- `total_shareholder_yield` (§4.8)
- `sbc_intensity` (§4.15)
- `cap_table_dilution` (§4.16)

Group C — earnings / estimates panels (§4.4, §4.5, §4.10, §4.11, §4.12, §4.13, §4.14):
- `earnings_surprise_tracker` (§4.4)
- `analyst_revision_momentum` (§4.5)
- `one_time_item_identification` (§4.10)
- `organic_vs_inorganic_growth` (§4.11)
- `currency_neutral_growth` (§4.12)
- `margin_trajectory_regression` (§4.13)
- `operating_leverage_analysis` (§4.14)

Group D — statement integrity / fundamental quality panels (§4.6, §4.9, §4.17, §4.19, §4.20):
- `common_size_statements` (§4.6)
- `cross_statement_validation` (§4.9)
- `piotroski_f_score` (§4.17)
- `cash_conversion_cycle` (§4.19)
- `sustainable_growth_rate` (§4.20)

**Artifacts:** `roic_panel`, `quality_of_earnings_panel`, `business_quality_panel` (aggregator), `statement_integrity_panel` (aggregator), plus one artifact per individual helper above.
**skills.md:** `statement_integrity_bundle.md` (covers Piotroski + Dechow-Dichev + accrual quality interpretation)

**Audit fixes to apply (from helpers-design §9; covers items 3, 5, 6, 7, plus "Additional corrections"):**
- Sloan accruals (§4.2): use the **level** measure `Accruals_t / avg_TA_t` (not first-difference).
- Piotroski F-score (§4.17): include canonical `Δ ROA > 0` signal; drop redundant `NI > 0`.
- Economic profit base (§4.1): use **avg IC** (matches ROIC denominator) — not period-end IC.
- ROIIC timing (§4.1): **contemporaneous** (`ΔNOPAT_t / ΔIC_t`), not lagged. Near-zero ΔIC → null with reason; negative ΔIC → sign-flip warning.
- Operating leverage (§4.14): parenthesization explicit; sign-divergence cases flagged not dropped.
- Capitalized R&D % (§4.2): denominator = `(Capitalized + Expensed)`.
- accruals_pct_of_ni (§4.2): formula `(NI − CFO) / NI` (no `+Capex` term).
- NOPAT calculation (§4.1): explicit `use_adjusted_ebit` flag; default GAAP EBIT × (1 − tax_rate); records which path used.
- Invested capital (§4.1): `Total_Equity + Total_Debt − Cash` (operating leases included post-ASC 842 / IFRS 16); all cash netted; applied identically across ROIC / ROIIC / EP.
- Currency-neutral growth (§4.12): explicit output recording disclosed-vs-derived path.

**Cleanup:** deprecate and remove `budget_variance.py`, `business_investment.py`, `ratio_calculator.py`. Their schemas were migrated in PR 0.2; this PR deletes the files and any test fixtures that referenced them.

### PR 2.6 — Forensic + dividend safety (backlog task #21)

**Implements:** helpers-design §4.18 (`beneish_m_score`); supplement §8 (`altman_z_variants` — Z, Z', Z", EM Z" with variant-misapplication guard); supplement §9 (`dividend_safety_panel` — payout ratios, coverage, streak history, stress test, classification bands).

**Helpers:** `beneish_m_score`, `altman_z_variants`, `dividend_safety_panel`, plus a `forensic_panel` aggregator that composes Beneish + Altman + Sloan accruals (from PR 2.5 `quality_of_earnings_panel`)
**Artifacts:** `forensic_panel`, `dividend_safety_panel`
**skills.md:** `forensic_panel.md`
**Acceptance:** Beneish 8-variable formula matches helpers-design §4.18; each Altman variant validates against published threshold tables per supplement §8; `dividend_safety_panel` stress test exposes shock-pct as configurable input per supplement §9.

### PR 2.7 — Credit + solvency + 5-step DuPont (backlog task #15)

**Implements:** supplement §10 (`credit_solvency_panel` — interest-coverage variants, fixed-charge coverage, leverage ratios, Damodaran rating proxy with disclaimer hook), §11 (`five_step_dupont` — tax burden × interest burden × operating margin × asset turnover × equity multiplier; high-vs-low-quality ROE change attribution), §12 (`debt_maturity_ladder` — year-by-year principal + WAC + WAM, refi-wall detection, refi stress test).

**Helpers:** `credit_solvency_panel`, `five_step_dupont`, `debt_maturity_ladder`. `altman_z_variants` consumed from PR 2.6 (shared infrastructure).
**Artifacts:** `credit_solvency_panel`, `dupont_decomposition`, `debt_maturity_ladder`
**Acceptance:** 5-step DuPont decomposes ROE per supplement §11 with the ΔROE additive decomposition; refi wall triggers at ≥25% of total debt or ≥50% of TTM EBIT in a single year per supplement §12; Damodaran rating-proxy mapping pinned to a versioned snapshot.

### PR 2.8 — Signal & context helpers (backlog task #23)

**Implements:** signals-addendum doc §1 (insider_signal_panel), §2 (moving_average_panel), §3 (historical_multiple_trends)

**Helpers:** `insider_signal_panel`, `moving_average_panel`, `historical_multiple_trends`
**Artifacts:** `insider_signal`, `ma_panel`, `historical_multiple_trends`
**skills.md:** `insider_signal_panel.md`, `historical_multiple_trends.md`

**Audit fixes / explicit behavior (from signals-addendum):**
- `insider_signal_panel`: filter raw Form 4 codes P/S/A/M/F/G/C/D/X per addendum §1.2; role-weight transactions (CEO/CFO > VP > other officer > director per addendum §1.3); detect clusters via rolling-window threshold per addendum §1.4; strip 10b5-1 plan transactions or annotate them separately per addendum §1.5; asymmetric weighting (insider buys carry more signal than sells) per addendum §1.6.
- `moving_average_panel`: emit MA regimes (above/below 50d, 100d, 200d) per addendum §2.2; crossovers must be volume-confirmed per addendum §2.3; 200d stretch z-score per addendum §2.4. Reused as a valuation-trend smoother via `series_kind="multiple"` parameter (addendum §2.5).
- `historical_multiple_trends`: current multiple vs own 1Y/3Y/5Y/10Y history (addendum §3.2); re-rating slope via OLS on time series (addendum §3.3); optional sector overlay (addendum §3.4); NM handling for loss-making periods (addendum §3.5) — same convention as comparables.

**Build-blocker:** assumes PR 1.1 has resolved the Form 4 code question. If SEC EDGAR fallback was triggered, `insider_signal_panel` consumes that connector instead.

### PR 2.9 — saas_kpi_panel repurpose (backlog task #11)

**Implements:** helpers-design doc §6.1 (SaaS KPI panel)

**Helpers:** `saas_kpi_panel` (replaces `saas_metrics.py`)
**Artifacts:** `saas_kpi_panel`

**Audit fix to apply (from helpers-design §9):**
- Magic Number formula: `net_new_ARR / S&M_prior_Q` (no `×4`). ARR is already annualized; multiplying by 4 double-annualizes.

**Acceptance:** input schema is quarterly (not monthly); supports ARR/NRR/GRR/Magic Number with corrected formula per audit fix; rule-of-40, CAC payback, LTV/CAC included per design §6.1.

### PR 2.10 — Workbook builder + remaining outputs (backlog task #8)

**Implements:** helpers-design §2.5 `WorkbookTemplate` class (infrastructure); supplement §13 `workbook_builder` (helper wrapper around the class — sheet inventory, embed_charts, save flow). Also picks up helpers-design §3.7 `waterfall_chart`. Note that `football_field_chart` (§3.6) ships with PR 2.4 (decision layer) rather than here, because it consumes blended-PT output.

**Helpers:** `workbook_builder`, `waterfall_chart`, plus any remaining chart / table helpers
**Artifacts:** `workbook_render`, `waterfall_render`
**skills.md:** `workbook_builder.md`
**Acceptance:** produces a multi-sheet xlsx (Cover / Assumptions / DCF / Sensitivity / Scenarios / Comparables / SOTP / Cost of Capital / Decision / Forensic / Credit at minimum) with cross-sheet named ranges per supplement §13; file size ≤ 10MB; verifier `block_artifact_too_large` does not fire on the bundled output.

### PR 2.11 — Risk / macro helpers (backlog tasks #8 spillover, #4 prep)

**Implements:** helpers-design §5.1 `drawdown_panel`, §5.2 `yield_curve_shape`. (§5.3 `commodity_exposure_tracker` already exists; it migrates to the new schema in PR 0.2.)

**Helpers:** `drawdown_panel`, `yield_curve_shape`
**Artifacts:** `drawdown_panel`, `yield_curve_shape`
**Category:** `risk_macro`
**Acceptance:** `drawdown_panel` returns max-drawdown, time-to-recovery, calmar ratio per design §5.1; `yield_curve_shape` returns 2s/10s, 3m/10y, NY-Fed recession-prob per design §5.2. Both unit-tested with synthetic series.

**Dependency note (statsmodels):** `drawdown_panel` is pure cumulative-max math — no statsmodels needed. `yield_curve_shape`'s recession-probability output **consumes the NY-Fed disclosed value** (`get_macro_indicator` from EODHD), it does not re-fit the probit model in-process. So PR 2.11 has no hard dependency on PR 4.1 (statsmodels). If a future iteration wants to fit the probit locally, move PR 4.1 forward and add an ordering constraint to §9.

**Risk:** low; both are mechanical computations against existing EODHD endpoints.

**Phase 2 exit gate:** `stock_initiation_v2` template can run end-to-end against a tech ticker (MSFT, NVDA) and a value/cyclical ticker (CAT, X) and produce a complete report through Stage 7b. All 18 Stage 8 verifier parent issue types testable (14 original + 4 from PR 0.3); detail codes per schema-and-skills §5.1 tracked supplementally.

---

## 5. Phase 3 — Sector modules — Wave 1 (5 PRs, parallelizable)

Each sector PR is independent of the others. Can be tackled in any order or in parallel.

| PR | Task | Helpers / artifacts | Design-doc reference |
|---|---|---|---|
| 3.1 | #16 Banks | `banks_sector_panel` (NIM / CET1 / RoTCE / efficiency / NCO / deposit beta / credit-cycle phasing), `loan_loss_provision_analysis` (sub-helper) | sector-modules §2 |
| 3.2 | #17 REITs | `reit_valuation_panel` (FFO / AFFO / NAV / same-store NOI / property-type cap rate), `cap_rate_analysis` (sub-helper) | sector-modules §3 |
| 3.3 | #18 Pharma | `rnpv_pipeline`, `royalty_stack_analyzer` | sector-modules §4 |
| 3.4 | #19 Energy / E&P | `ep_sector_panel` (EBITDAX / DACF / netback per BOE / RRR / reserve-life index / commodity-price scenarios; AISC for metals variant) | sector-modules §5 |
| 3.5 | #20 Insurance | `insurance_valuation_panel` (P&C combined ratio + ex-cat split + PY-development; Life embedded value + VNB; capital-adequacy regime selection) | sector-modules §6 |

**PR 3.3 (Pharma) — reference data sourcing:** Citeline 2024 stage-PoS table (P1→P2=47%, P2→P3=28%, P3→NDA=55%, NDA→Approval=92%) lives at `packages/core/src/openlia/data/reference/citeline/stage_pos_2024.yaml`. Refresh cadence: annual at Citeline release. Source attribution: Citeline 2024 industry data. Verify license terms before commit; if license-restricted, store hash + external link only and require user-supplied PoS values at runtime.

**PR 3.4 (Energy/E&P) — AISC formula:** World Gold Council Guidance Note formula. Source URL pinned in the helper's docstring.

Each sector PR adds a sector-specific template (`stock_initiation_banks_v2`, etc.) with its own `section_plan_defaults.yaml`.

**Phase 3 exit gate:** at least one ticker per sector produces a complete sector-specific report.

---

## 6. Phase 4 — Supporting libraries (2 PRs)

### PR 4.1 — statsmodels narrow scope (backlog task #4)

OLS, multi-factor regression, VIF, correlation, t/F tests. Each registers as a separate library helper with `data_dependencies` declaring its inputs.

### PR 4.2 — claude-cookbooks pattern adoption + LLM-orchestrated helpers (backlog task #5)

**Implements:** helpers-design §2.4 `pdf_ingest`, §7 all LLM-orchestrated helpers.

**Helpers (8 total):**
- `pdf_ingest` (§2.4) — pdfplumber + camelot fallback table extraction
- `transcript_tone_analysis` (§7.1) — earnings-call transcript polarity / hedging metrics
- `tone_shift_qoq` (§7.2) — QoQ delta in tone vs prior calls
- `mda_extraction` (§7.3) — structured extraction of MD&A drivers, headwinds, tailwinds
- `risk_factors_extraction` (§7.4) — structured extraction of 10-K risk factor items with novelty flags
- `forward_looking_statements` (§7.5) — extracts forward statements with confidence flags
- `guidance_tracker` (§7.6) — beat/miss tracking with corrected `beat_modest` label (audit fix #8 below)
- `customer_concentration_extraction` (§7.7) — top-N customer disclosures from 10-K item 1

**Category:** `llm_nlp` for §7 helpers; `adapter` for `pdf_ingest`.

**Audit fix from helpers-design §9:**
- `guidance_tracker` (§7.6): `beat_within_range` → `beat_modest`; credibility scoring relabeled as "guidance accuracy heuristic" and marked opinionated, not neutral track-record.

**Acceptance:** each LLM-orchestrated helper has at least one happy-path test with a recorded transcript / filing fixture and one extraction-failure test (low-confidence return). `pdf_ingest` extracts a known table from a fixture PDF. License check: MIT.

**Phase 4 exit gate:** statistical inference and PDF fallback are available to helpers in Phases 2 and 3 that need them (some Phase 3 helpers may need backports if scheduled out of order).

---

## 7. Phase 5 — Parked

| Task | Why parked |
|---|---|
| #9 Qualitative framework helpers | Builds on quantitative foundation; meaningful only after Phase 2 lands |
| #10 Verifier process-quality extensions | Best designed after observing real verifier behavior in Phase 2-3 runs |
| #22 Wave 2 sector modules (Mining, Retail, Telecom, Semis, Airlines) | Demand-driven; add as users need them |

---

## 8. Cross-cutting requirements per PR

Every PR in Phases 1-4 must include:

1. **Schema migration:** new helpers use the four-tier sub-model schema; no legacy `description`-only entries.
2. **Artifact registry update:** new ArtifactType entries land in `artifact_types.yaml` with their Pydantic model.
3. **Section plan defaults:** any new artifact that should appear in `stock_initiation_v2` updates `section_plan_defaults.yaml`. Sector PRs maintain their own template defaults.
4. **Tests:** at minimum one happy-path test per helper, plus one failure case (bad input, missing dependency, verifier-triggering output).
5. **skills.md authored:** if the helper is on the 18-helper skills list, `skills/<name>.md` is part of the same PR.
6. **No `description`-field fallback for new helpers:** `purpose` / `when_to_use` / `when_not_to_use` are required.

---

## 9. Sequencing constraints

| Constraint | Reason |
|---|---|
| Phase 0 before everything | Schema and ArtifactType registry are the contracts everything else binds to |
| PR 1.1 before PR 2.8 | Signal helpers need EODHD insider/MA data |
| PR 1.2 before PR 2.5, 2.6, 2.7 | FinanceToolkit provides the math primitives (Altman, DuPont, Piotroski) these PRs use |
| PR 2.2 before PR 2.3, 2.4 | DCF artifacts feed DDM / Justified Multiples comparison + Decision layer |
| PR 2.1 before PR 2.4 | Comparables artifacts feed the Decision layer's blender weights |
| PR 2.1 before PR 2.8 | Historical multiple trends pairs with comparables |
| PR 2.6 before PR 2.7 | Altman variants share infrastructure (§14 row); building 2.7 first would force a refactor when 2.6 lands |
| PR 2.2 before PR 2.10 | football_field_chart consumes DCF + comps valuation artifacts shipped in 2.2 |
| Phase 2 before Phase 3 | Sector modules build on the analytic primitives (DCF, comps, statement integrity) |

Phases 3 and 4 are parallelizable internally; PRs within those phases have no inter-dependencies.

---

## 10. Risk register

| Risk | Mitigation |
|---|---|
| EODHD insider data lacks raw Form 4 codes | Fallback SEC EDGAR adapter scoped during PR 1.1; signal helper degrades gracefully without raw codes |
| FinanceToolkit license drift (MIT → something else) | License pin in `pyproject.toml`; CI check on every PR |
| Materialization complexity bugs (canonical-site, dedup) | Full 7-case unit test matrix in PR 0.3; smoke test in Phase 0 exit gate |
| Verifier issue type explosion | Cap at the closed 14 + 4 new ones; reuse before adding new |
| Skill doc drift from schema (skill says X, schema says Y) | CI lint that diffs skill doc frontmatter `produces_artifacts` against schema |
| Sector PRs blocked on Wave 0 helper bugs surfaced late | Phase 2 exit gate runs against 2 tickers minimum before Phase 3 starts |

---

## 11. Estimated PR / scope total

- Phase 0: 4 PRs
- Phase 1: 2 PRs
- Phase 2: 11 PRs (2.1 through 2.11, including the new 2.11 risk/macro split)
- Phase 3: 5 PRs
- Phase 4: 2 PRs
- **Total: ~24 PRs** to complete Waves 0 + 1

Sector module PRs (Phase 3) and supporting library PRs (Phase 4) are parallelizable, so wall-clock time is shorter than sequential PR count suggests.

---

## 12. Open decisions still pending

These don't block Phase 0 but each has a designated resolution PR:

1. **`stock_initiation_v2` actual section list:** the 12-section template in code vs. the 14-section claim in prompts doc (observation #8589). Reconcile during PR 0.4 — count + names from the template file are the source of truth.
2. **Verifier issue-enum vs sub-enum for materialization issues:** decide during PR 0.3.
3. **Multimodal chart rendering:** decide during PR 2.2 (first chart-heavy helper).
4. **Skill doc CI lint strictness:** lint is implemented in PR 0.4; strictness level (warn vs fail) gets finalized once a real skill doc exists, deferred to PR 2.1 (first skills.md authored).
5. **Citeline 2024 PoS table license:** if redistribution restricted, the rNPV helper falls back to user-supplied PoS values. Decide during PR 3.3.
6. **Helper versioning** (schema-and-skills §9): `HelperSchema.version` is bumped on contract changes but no migration story is defined. Defer until first real version bump.
7. **L1.5 cache key strategy** (schema-and-skills §9): sessionId-scoped vs. global cache depends on multi-user company-mode behavior. Defer to deployment task.
8. **Artifact-type live-reload** (schema-and-skills §9): adding a new ArtifactType currently requires registry rebuild. Acceptable for v2.2; revisit if dynamic helper loading becomes a need.
9. **Streaming materialization** (artifact-injection §11): can Stage 7a stream markdown to the drafter chunk-by-chunk, or must it batch the full section_plan? Defer until token-cost data from Phase 2 informs the call.
10. **Cross-report dedup** (artifact-injection §11): can artifacts computed for ticker A be cached and reused for ticker B in a sector batch? Defer to Phase 3 sector-batch design.
11. **Drafter feedback loop** (artifact-injection §11): does the drafter ever request a higher fidelity than the planner allocated? If yes, how is that wired? Defer to first observed need.
12. **Football-field methodology weighting** (helpers-design §9 item 9, marked OPEN): currently unweighted (min/median/max of per-multiple medians). Confidence weighting is a defensible future addition. Decide during PR 2.10 (which ships the football_field_chart helper).
13. **GICS prefix routing verification** (sector-modules §7): the codes used (4010 banks; 4020 financials; 4030 insurance; 6010 REITs; 3520 pharma; 1010 E&P) must be verified against current GICS taxonomy. Decide during PR 0.4 (Stage 5 planner wiring); a mistake here causes sector panels to fail to auto-route on real tickers.
14. **Pydantic artifact inventory** (PR 0.1 seed for `artifact_types.yaml`): no single inventory exists of which artifact types are populated at registry boot vs added per-helper-PR. Decide during PR 0.1 — list the seed set; subsequent PRs append.
15. **Reference data licensing** (Damodaran, Citeline, CBRE, ICE BofA): each is publisher-restricted. The decision on whether to ship a snapshot in-repo, store a hash-pointer + external link, or require user-supplied values is per-source and should be made before the PR is in flight. Decide per-source: Damodaran in PR 2.2, Citeline in PR 3.3, CBRE in PR 3.2, ICE BofA in PR 1.2.
16. **`royalty_stack_analyzer` standalone vs internal-only** (sector-modules §4): currently described as a sub-helper of `rnpv_pipeline`. Decide during PR 3.3 whether it registers as its own helper or stays a code module.
17. **EV/EBITDA justified-multiple formula** (supplement §5): admittedly approximate when capital intensity shifts. Decide during PR 2.3 whether to tighten via the McKinsey EV/IC × IC/EBITDA derivation, or to add an explicit `when_not_to_use` pointing the planner away from this multiple for capital-shifting names.

---

## 13. What happens after Phase 5

This plan covers Waves 0 + 1. Wave 2 (#22 sector modules + #9 qualitative + #10 verifier process-quality) is intentionally out of scope until real-run feedback informs priorities. The expected loop after Phase 3:

1. Run reports against ~50 tickers across all 5 Wave-1 sectors.
2. Capture verifier failure modes, drafter wandering patterns, and user complaints.
3. Use those to scope Wave 2 (more sectors? more verifier rules? qualitative framework primitives?).

The branch shipped to main at end of Phase 3 is the v2.2 GA cut. Wave 2 work happens on subsequent branches.

---

## 14. Design-doc cross-reference

Every PR cites the specific design-doc sections it implements. This table makes the binding machine-checkable — `test_planning_consistency.py` verifies that each cited `§N` resolves to a real section heading in the cited doc.

**Two companion design docs supplement helpers-design.md** for content that was missing in the initial design:

- `2026-05-22-helpers-design-supplement.md` — DCF engine, cost-of-capital, DDM family, justified multiples, SOTP, decision layer, Altman variants, dividend safety, credit/solvency, 5-step DuPont, debt-maturity ladder, workbook_builder helper
- `2026-05-22-helpers-design-sector-modules.md` — Banks, REITs, Pharma, Energy/E&P, Insurance panels

Both docs are now landed (Commits 2 and 3 of this branch). Every `§N` citation in the table below resolves to a real section heading; the doctest `test_cross_reference_sections_resolve_in_cited_docs` enforces this.

| Design doc | Sections | Implementing PR(s) |
|---|---|---|
| **helper-stack** | §1 architecture decisions | PR 0.1, PR 0.3, PR 0.4 |
| helper-stack | §2 external libraries | PR 1.1 (EODHD), PR 1.2 (FinanceToolkit), PR 4.1 (statsmodels), PR 4.2 (pdfplumber + cookbooks) |
| **schema-and-skills** | §1 four-tier exposure | PR 0.1, PR 0.4 |
| schema-and-skills | §2 ArtifactType registry + DAG validation | PR 0.1 |
| schema-and-skills | §3 schema (closed enums, sub-models, registration, projection) | PR 0.1 (§3.1-§3.3), PR 0.4 (§3.4) |
| schema-and-skills | §4 boot-time validation | PR 0.1 |
| schema-and-skills | §5 output validation flow (verifier coherence) | PR 0.1 (verifier reads runtime Pydantic) |
| schema-and-skills | §6 18-helper skills.md list | PR 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 2.10, 3.1-3.5 (per-PR) |
| schema-and-skills | §7 skills.md template | PR 2.1 (first skills.md authored) |
| **artifact-injection** | §1 pipeline placement (Stage 7a/7b) | PR 0.3 |
| artifact-injection | §2 fidelity contract on ArtifactType | PR 0.1 |
| artifact-injection | §3 SectionPlan schema | PR 0.3 |
| artifact-injection | §4 template defaults + planner overrides | PR 0.3 (resolver), PR 0.4 (Stage 5 emit + template defaults yaml) |
| artifact-injection | §5 materialization algorithm | PR 0.3 |
| artifact-injection | §6 drafter prompt structure (Stage 7b) | PR 0.3 |
| artifact-injection | §8 verifier integration | PR 0.3 |
| artifact-injection | §9 testing strategy | PR 0.3 |
| **helpers-design** | §1 common conventions (registration, exposure, freshness, missing-data, verifier hooks) | PR 0.1, PR 0.4 |
| helpers-design | §2.1 EODHD adapter | PR 1.1 |
| helpers-design | §2.2 FinanceToolkit adapter | PR 1.2 |
| helpers-design | §2.3 statsmodels adapter | PR 4.1 |
| helpers-design | §2.4 pdf_ingest | PR 4.2 |
| helpers-design | §2.5 WorkbookTemplate class (infrastructure) | PR 2.10 |
| helpers-design | §3.1 comparables | PR 2.1 |
| helpers-design | §3.2 sensitivity_table | PR 2.2 |
| helpers-design | §3.3 tornado_diagram | PR 2.2 |
| helpers-design | §3.4 scenario_weighting | PR 2.2 |
| helpers-design | §3.5 reverse_dcf | PR 2.2 |
| helpers-design | §3.6 football_field_chart | PR 2.4 |
| helpers-design | §3.7 waterfall_chart | PR 2.10 |
| helpers-design | §4.1 roic_panel | PR 2.5 |
| helpers-design | §4.2 quality_of_earnings_panel | PR 2.5 |
| helpers-design | §4.3 capital_allocation_history | PR 2.5 |
| helpers-design | §4.4 earnings_surprise_tracker | PR 2.5 |
| helpers-design | §4.5 analyst_revision_momentum | PR 2.5 |
| helpers-design | §4.6 common_size_statements | PR 2.5 |
| helpers-design | §4.7 fcf_conversion_track_record | PR 2.5 |
| helpers-design | §4.8 total_shareholder_yield | PR 2.5 |
| helpers-design | §4.9 cross_statement_validation | PR 2.5 |
| helpers-design | §4.10 one_time_item_identification | PR 2.5 |
| helpers-design | §4.11 organic_vs_inorganic_growth | PR 2.5 |
| helpers-design | §4.12 currency_neutral_growth | PR 2.5 |
| helpers-design | §4.13 margin_trajectory_regression | PR 2.5 |
| helpers-design | §4.14 operating_leverage_analysis | PR 2.5 |
| helpers-design | §4.15 sbc_intensity | PR 2.5 |
| helpers-design | §4.16 cap_table_dilution | PR 2.5 |
| helpers-design | §4.17 piotroski_f_score | PR 2.5 |
| helpers-design | §4.18 beneish_m_score | PR 2.6 |
| helpers-design | §4.19 cash_conversion_cycle | PR 2.5 |
| helpers-design | §4.20 sustainable_growth_rate | PR 2.5 |
| helpers-design | §5.1 drawdown_panel | PR 2.11 |
| helpers-design | §5.2 yield_curve_shape | PR 2.11 |
| helpers-design | §5.3 commodity_exposure_tracker (existing helper, schema migration only) | PR 0.2 |
| helpers-design | §6.1 saas_kpi_panel | PR 2.9 |
| helpers-design | §7.1 transcript_tone_analysis | PR 4.2 |
| helpers-design | §7.2 tone_shift_qoq | PR 4.2 |
| helpers-design | §7.3 mda_extraction | PR 4.2 |
| helpers-design | §7.4 risk_factors_extraction | PR 4.2 |
| helpers-design | §7.5 forward_looking_statements | PR 4.2 |
| helpers-design | §7.6 guidance_tracker | PR 4.2 |
| helpers-design | §7.7 customer_concentration_extraction | PR 4.2 |
| helpers-design | §8 verifier hooks summary | PR 0.3 |
| helpers-design | §9 audit resolutions (11 fixes) | PR 2.1 (EV bridge, combined range), PR 2.5 (Sloan, Piotroski ΔROA, ROIIC, economic profit, op leverage, capitalized R&D, accruals_pct_of_ni), PR 2.9 (Magic Number), PR 4.2 (guidance_tracker label) |
| **supplement** | §2 cost_of_capital_builder | PR 2.2 |
| supplement | §3 dcf_engine | PR 2.2 |
| supplement | §4 ddm_family | PR 2.3 |
| supplement | §5 justified_multiples | PR 2.3 |
| supplement | §6 sotp_builder | PR 2.3 |
| supplement | §7 decision layer (blender, ETR, risk/reward, rating bands) | PR 2.4 |
| supplement | §8 altman_z_variants | PR 2.6 |
| supplement | §9 dividend_safety_panel | PR 2.6 |
| supplement | §10 credit_solvency_panel | PR 2.7 |
| supplement | §11 five_step_dupont | PR 2.7 |
| supplement | §12 debt_maturity_ladder | PR 2.7 |
| supplement | §13 workbook_builder helper | PR 2.10 |
| supplement | §14 aggregator artifacts (forensic_panel + statement_integrity_panel) | PR 2.5, PR 2.6 |
| **sector-modules** | §2 Banks panel | PR 3.1 |
| sector-modules | §3 REITs panel | PR 3.2 |
| sector-modules | §4 Pharma rNPV pipeline | PR 3.3 |
| sector-modules | §5 Energy / E&P panel | PR 3.4 |
| sector-modules | §6 Insurance panel | PR 3.5 |
| **signals-addendum** | §1 insider_signal_panel | PR 2.8 |
| signals-addendum | §2 moving_average_panel | PR 2.8 |
| signals-addendum | §3 historical_multiple_trends | PR 2.8 |

If a row above has no PR assignment, that's a design-doc requirement we haven't scheduled. As of this revision, every row resolves once Commits 2 and 3 land the two pending docs.

---

## 15. Smoke-test plan

Each phase exit gate requires a smoke test against a defined ticker set. Test execution is non-LLM (uses recorded fixtures and golden-output comparison) where possible; LLM-driven steps use a fixed seed / temperature=0 where the model supports it.

### 15.1 Phase 0 exit gate

**Tickers:** MSFT only (single representative tech name).
**Template:** `stock_initiation_v2`.
**Assertions:**
- Pipeline runs end-to-end through all 9 stages (incl. 7a/7b split)
- Registry boot succeeds; capabilities.yaml resolves
- Stage 5 planner emits a valid `helper_selection` + `PlannerOverrides`
- Stage 7a produces deterministic markdown (re-run yields byte-identical output)
- Stage 7b drafter receives the materialized prompt and produces non-empty section bodies
- Stage 8 verifier completes (failures or successes both acceptable; the test asserts the verifier ran, not that it passed)

### 15.2 Phase 1 exit gate

**Tickers:** MSFT + 1 non-US ticker (e.g., NESN.SW) to exercise EODHD exchange handling.
**Assertions:**
- EODHD adapter pulls fundamentals, prices, dividends for both tickers via recorded fixtures
- FinanceToolkit-backed ratio helpers return non-None results for both
- Connector base class instantiated for at least 2 connector types

### 15.3 Phase 2 exit gate

**Ticker set (4 names):** MSFT (large-cap tech growth), NVDA (high-multiple growth), CAT (industrial cyclical), X (deep-cyclical value).
**Assertions:**
- All 4 produce a complete report through Stage 7b
- All 18 Stage 8 verifier parent issue types are reachable (at least one synthetic case per parent type, even if no real production case fires). Detail-code coverage tracked supplementally per schema-and-skills §5.1.
- All 11 audit fixes are unit-tested with explicit assertions
- Token cost per report is ≤ 15k for tool-related overhead (validates artifact-injection redesign projection)

### 15.4 Phase 3 exit gate

**Ticker set (1 per sector):** JPM (banks), O (REIT — Realty Income), VRTX (pharma — Vertex), XOM (E&P), CB (insurance — Chubb).
**Assertions:**
- Each sector PR's template produces a complete sector-specific report
- Sector-specific KPIs are non-None (NIM for JPM, FFO for O, rNPV for VRTX, EBITDAX for XOM, combined ratio for CB)
- Token cost per sector report is ≤ 18k (sector modules slightly larger than generic)

### 15.5 Phase 4 exit gate

**Sanity-only:** statsmodels-backed regression on a synthetic dataset returns expected coefficients; pdfplumber extracts a known table from a fixture PDF.

### 15.6 Pre-GA full sweep

After Phase 3, before declaring v2.2 GA: run all 5 templates × all 5 sector tickers = 25 reports, plus the 4 Phase-2 tickers on `stock_initiation_v2` = 29 total. Capture verifier issue rates and token-cost distributions. GA blocker if either (a) any ticker fails to produce a complete report or (b) p95 token cost > 1.5× the per-phase budget.

---

## 16. Target tracking

**Final helper count target:** ~120 active helpers (Wave 0 + Wave 1) at end of Phase 3. Tracked via `len(list_helpers())` in a Phase-3-exit-gate test.

Breakdown:
- Existing (migrated in PR 0.2): 8
- Phase 1 adapter wrappers: ~33 (EODHD ~18 + FinanceToolkit ~15)
- Phase 2 analytics: ~54 (comparables 3, DCF/COC 7, alt valuation 3, decision 6, business quality 19, forensic 4, credit 3, signals 3, saas 1, workbook/output 3, risk-macro 2)
- Phase 3 sector panels + sub-helpers: ~10
- Phase 4 supporting libs: ~14 (statsmodels 6 + cookbooks 8)
- **Total: ~119**

The earlier ~178 figure in `helper-stack §9` was an aspirational pre-PR-rationalization decomposition; the impl plan's per-PR scopes consolidate many one-metric helpers into multi-metric panels.

**Skill doc count target:** 18 skill docs authored, one per helper on the schema-and-skills doc §6 list. Tracked via a CI test that counts `skills/*.md` files and matches against the registry's `skill_doc` references.

**Verifier issue type count:** 14 (existing closed enum) + 4 (from PR 0.3) = **18 parent issue types** reachable. Tracked via Phase 2 exit gate assertion. Detail codes (per schema-and-skills §5.1) are an open vocabulary that rides inside the closed parent enum; supplement and sector-modules introduce ~21 detail codes which are aggregated separately and reported in a supplementary telemetry table — not part of the closed-set invariant or gate counts.
