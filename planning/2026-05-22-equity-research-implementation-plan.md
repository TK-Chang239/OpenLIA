# Equity Research v2.2 Helper Stack — Implementation Plan

**Date:** 2026-05-22
**Branch:** `feat/equity-research-engine-plan` (foundation); per-task branches downstream
**Status:** Sequencing plan for the 24-task backlog defined across the five design docs

---

## 0. Scope and prerequisites

This plan sequences the build of the equity research v2.2 helper stack. It assumes:

- The five design docs are accepted as the contract (see project root: `planning/2026-05-21-*` and `planning/2026-05-22-*`).
- Existing 6 library helpers (`peer_multiples_panel`, `dcf_valuation`, `commodity_exposure_tracker`, `budget_variance`, `business_investment`, `chart_builder`) plus `saas_metrics` are in `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/`. Three of those are slated for deprecation (`budget_variance`, `business_investment`, `ratio_calculator`); one for repurposing (`saas_metrics → saas_kpi_panel`); the rest stay and migrate to the new schema.
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
| 2 | Core analytics — Wave 0 helpers | #1, #6, #11, #12, #13, #14, #7, #21, #15, #23, #8 | 9-11 PRs | sector work |
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

**Acceptance:** registering a helper with `produces_artifacts=["nonexistent"]` fails at registration; cycle in producer/consumer graph fails registry boot; `capabilities.yaml` schema validates at boot; existing 7 helpers still register (via back-compat wrapper — see PR 0.2 for the full migration).

**Risk:** none meaningful; pure additive.

### PR 0.2 — Migrate existing 7 helpers to new schema

**Implements:** schema-and-skills doc §3.4 (projection rules), §8 (implementation order step 1)

**Files:** seven existing modules — `peer_multiples_panel`, `dcf_valuation`, `commodity_exposure_tracker`, `budget_variance`, `business_investment`, `chart_builder`, `saas_metrics` — each fills in `directory` / `selection` / `contract` sub-models; deletes the legacy `description`-only schema.

Note: `budget_variance`, `business_investment`, and `ratio_calculator` are slated for deprecation in PR 2.5. `saas_metrics` is slated for repurpose in PR 2.9. PR 0.2 still migrates all seven to the new schema as a holding step — deletion / repurpose happens in the named PR.

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

**Acceptance:** end-to-end test runs a synthetic helper pipeline → produces typed artifacts → applies overrides → materializes deterministic markdown → drafter sees sectioned prompt. All seven targeted unit tests pass.

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

## 4. Phase 2 — Wave 0 core analytics (9-11 PRs)

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

**Implements:** helpers-design doc §5 (DCF engine + cost of capital), §5.2 (mid-year convention), §5.3 (terminal value methods), §5.4 (sensitivity grid), §5.5 (tornado/scenario)

The dependency anchor for everything valuation-related.

**Helpers:** `cost_of_capital_builder`, `dcf_engine`, `sensitivity_grid_builder`, `tornado_diagram`, `scenario_weighting`
**Artifacts:** `dcf_base_valuation`, `cost_of_capital_panel`, `sensitivity_grid`, `tornado_diagram_render`, `scenario_weighted_value`
**skills.md:** `dcf_engine.md`, `cost_of_capital_builder.md`

**Reference data sourcing:** Damodaran tables for country risk premium, equity risk premium, beta by industry. This PR establishes the refresh mechanism — a script that pulls the published tables on demand and stores a versioned snapshot under `packages/core/src/openlia/data/reference/damodaran/`. Manual refresh cadence (quarterly) documented in the package README. License: tables are publicly published with attribution; verify attribution requirements before merge.

**Decision needed during this PR:** multimodal chart rendering approach (open question §12.3) — charts emitted by sensitivity_grid / tornado_diagram either as inline base64 PNG, attached file references, or markdown-table fallback. Pick one and commit it inside this PR.

**Acceptance:** mid-year convention configurable; terminal value supports both Gordon and McKinsey Key Value Driver per design §5.3; CAPM / Hamada / build-up methods all produce results; verifier rejects `terminal_growth > risk_free_rate`; Damodaran data refresh script runs in CI and produces a valid snapshot.

### PR 2.3 — Alternative valuation methodologies (backlog task #13)

**Implements:** helpers-design doc §5.6 (DDM family), §5.7 (justified multiples), §5.8 (SOTP)

**Helpers:** `ddm_family` (Gordon / multi-stage / H-model), `justified_multiples`, `sotp_builder`
**Artifacts:** `ddm_valuation`, `justified_multiple_panel`, `sotp_segment_valuation`
**skills.md:** `ddm_family.md`, `justified_multiples.md`, `sotp_builder.md`
**Acceptance:** each DDM variant validates against published textbook examples (1-2 per variant); justified-multiple formulas derived from g/ROE/payout per design §5.7; SOTP supports per-segment valuation method choice (DCF or comps) per design §5.8.

### PR 2.4 — Decision layer (backlog task #14)

**Implements:** helpers-design doc §7 (decision layer) — blender, ETR, risk/reward, rating bands

**Helpers:** `price_target_blender`, `expected_total_return`, `risk_reward_calculator`, `implied_upside_downside`, `rating_band_assigner`
**Artifacts:** `price_target_consensus`, `etr_panel`, `risk_reward_panel`, `rating_recommendation`
**skills.md:** `price_target_blender.md`, `rating_band_assigner.md`
**Acceptance:** blender weights surfaced as configurable per design §7.1; ratings explainable (why-this-rating string included in artifact) per design §7.4; ETR formula matches design §7.2 (capital return + dividend yield, with horizon).

### PR 2.5 — Business quality + statement integrity (backlog task #7)

**Implements:** helpers-design doc §4 (business quality + statement integrity), §4.2 (Sloan accruals — level form), §4.17 (Piotroski with ΔROA), §6.2 (ROIIC), §6.3 (economic profit), §6.4 (operating leverage), §6.5 (capitalized R&D), §6.7 (guidance_tracker), §6.8 (accruals_pct_of_ni)

**Helpers:** Piotroski F-score, Dechow-Dichev accrual quality, Sloan accruals, earnings persistence, ROIIC, economic profit, operating leverage, capitalized R&D, guidance_tracker, accruals_pct_of_ni
**Artifacts:** `business_quality_panel`, `statement_integrity_panel`
**skills.md:** `statement_integrity_bundle.md`

**Audit fixes to apply (from helpers-design §9):**
- Sloan accruals: use the **level** measure `Accruals_t / avg_TA_t` (not first-difference `(Accruals_t − Accruals_{t-1}) / avg_TA`).
- Piotroski F-score: include canonical `Δ ROA > 0` signal (ROA improved YoY); drop the redundant `NI > 0` (already covered by `ROA > 0`).
- Economic profit base: use **avg IC** (matches ROIC denominator) — not period-end IC.
- ROIIC timing: **contemporaneous** (`ΔNOPAT_t / ΔIC_t`), not lagged.
- Operating leverage: make parens explicit in the formula to avoid ambiguity.
- Capitalized R&D denominator: clarify to `(Capitalized + Expensed)`.
- Accruals % of NI: renamed to `accruals_pct_of_ni`; drop `+Capex` term (capex is investing, not accruals).
- `guidance_tracker` label rename: `beat_within_range` → `beat_modest`. Credibility scoring documented as a heuristic, not a hard metric.

**Cleanup:** deprecate and remove `budget_variance.py`, `business_investment.py`, `ratio_calculator.py`. Their schemas were migrated in PR 0.2; this PR deletes the files and any test fixtures that referenced them.

### PR 2.6 — Forensic + dividend safety (backlog task #21)

**Implements:** helpers-design doc §4.4 (Beneish M-score), §4.5 (Altman Z variants), §4.6 (dividend coverage + sustainability)

**Helpers:** Beneish M-score, Altman Z variants (Z, Z', Z", EM Z"), dividend coverage, dividend payout sustainability
**Artifacts:** `forensic_panel`, `dividend_safety_panel`
**skills.md:** `forensic_panel.md`
**Acceptance:** Beneish 8-variable formula matches design §4.4; each Altman variant validates against published threshold tables.

### PR 2.7 — Credit + solvency + 5-step DuPont (backlog task #15)

**Implements:** helpers-design doc §4.7 (credit + solvency expansion), §4.8 (5-step DuPont), §4.9 (debt-maturity ladder)

**Helpers:** Altman variants (shared infra with PR 2.6), 5-step DuPont, interest coverage variants, debt-maturity ladder
**Artifacts:** `credit_solvency_panel`, `dupont_decomposition`, `debt_maturity_ladder`
**Acceptance:** 5-step DuPont decomposes ROE into operating margin × asset turnover × interest burden × tax burden × financial leverage per design §4.8; debt-maturity ladder bins by year out 10y + lump-sum tail.

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

**Implements:** helpers-design doc §8 (workbook builder + remaining outputs)

**Helpers:** `workbook_builder`, remaining chart / table helpers
**Artifacts:** `workbook_render`
**skills.md:** `workbook_builder.md`
**Acceptance:** produces a multi-sheet xlsx with cross-sheet formulas, formatted to a published convention per design §8.2.

**Phase 2 exit gate:** `stock_initiation_v2` template can run end-to-end against a tech ticker (MSFT, NVDA) and a value/cyclical ticker (CAT, X) and produce a complete report through Stage 7b. All 14 Stage 8 verifier issue types testable.

---

## 5. Phase 3 — Sector modules — Wave 1 (5 PRs, parallelizable)

Each sector PR is independent of the others. Can be tackled in any order or in parallel.

| PR | Task | Helpers / artifacts | Design-doc reference |
|---|---|---|---|
| 3.1 | #16 Banks | `banks_sector_panel` (NIM / CET1 / ROTCE / efficiency / NCO), `loan_loss_provision_analysis` | helpers-design §10.1 |
| 3.2 | #17 REITs | `reit_valuation_panel` (FFO / AFFO / NAV / same-store NOI), `cap_rate_analysis` | helpers-design §10.2 |
| 3.3 | #18 Pharma | `rnpv_pipeline`, `royalty_stack_analyzer` | helpers-design §10.3 |
| 3.4 | #19 Energy / E&P | `ep_sector_panel` (EBITDAX, DACF, netback, reserves replacement, AISC variant) | helpers-design §10.4 |
| 3.5 | #20 Insurance | `insurance_valuation_panel` (combined ratio, embedded value, P&C vs Life) | helpers-design §10.5 |

**PR 3.3 (Pharma) — reference data sourcing:** Citeline 2024 stage-PoS table (P1→P2=47%, P2→P3=28%, P3→NDA=55%, NDA→Approval=92%) lives at `packages/core/src/openlia/data/reference/citeline/stage_pos_2024.yaml`. Refresh cadence: annual at Citeline release. Source attribution: Citeline 2024 industry data. Verify license terms before commit; if license-restricted, store hash + external link only and require user-supplied PoS values at runtime.

**PR 3.4 (Energy/E&P) — AISC formula:** World Gold Council Guidance Note formula. Source URL pinned in the helper's docstring.

Each sector PR adds a sector-specific template (`stock_initiation_banks_v2`, etc.) with its own `section_plan_defaults.yaml`.

**Phase 3 exit gate:** at least one ticker per sector produces a complete sector-specific report.

---

## 6. Phase 4 — Supporting libraries (2 PRs)

### PR 4.1 — statsmodels narrow scope (backlog task #4)

OLS, multi-factor regression, VIF, correlation, t/F tests. Each registers as a separate library helper with `data_dependencies` declaring its inputs.

### PR 4.2 — claude-cookbooks pattern adoption (backlog task #5)

PDF table extraction fallback (pdfplumber), structured classification helpers, RAG patterns for filing search. License: MIT.

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
- Phase 2: 10 PRs (9-11 range)
- Phase 3: 5 PRs
- Phase 4: 2 PRs
- **Total: ~23 PRs** to complete Waves 0 + 1

Sector module PRs (Phase 3) and supporting library PRs (Phase 4) are parallelizable, so wall-clock time is shorter than sequential PR count suggests.

---

## 12. Open decisions still pending

These don't block Phase 0 but each has a designated resolution PR:

1. **`stock_initiation_v2` actual section list:** the 12-section template in code vs. the 14-section claim in prompts doc (observation #8589). Reconcile during PR 0.4 — count + names from the template file are the source of truth.
2. **Verifier issue-enum vs sub-enum for materialization issues:** decide during PR 0.3.
3. **Multimodal chart rendering:** decide during PR 2.2 (first chart-heavy helper).
4. **Skill doc CI lint strictness:** lint is implemented in PR 0.4; strictness level (warn vs fail) gets finalized once a real skill doc exists, deferred to PR 2.1 (first skills.md authored).
5. **Citeline 2024 PoS table license:** if redistribution restricted, the rNPV helper falls back to user-supplied PoS values. Decide during PR 3.3.

---

## 13. What happens after Phase 5

This plan covers Waves 0 + 1. Wave 2 (#22 sector modules + #9 qualitative + #10 verifier process-quality) is intentionally out of scope until real-run feedback informs priorities. The expected loop after Phase 3:

1. Run reports against ~50 tickers across all 5 Wave-1 sectors.
2. Capture verifier failure modes, drafter wandering patterns, and user complaints.
3. Use those to scope Wave 2 (more sectors? more verifier rules? qualitative framework primitives?).

The branch shipped to main at end of Phase 3 is the v2.2 GA cut. Wave 2 work happens on subsequent branches.

---

## 14. Design-doc cross-reference

Every PR cites the specific design-doc sections it implements. This table makes the binding machine-checkable in code review — if a PR description doesn't reference at least one section in the table below, the PR is incomplete.

| Design doc | Sections | Implementing PR(s) |
|---|---|---|
| **helper-stack** | §1.1 four-tier exposure | PR 0.1, PR 0.4 |
| helper-stack | §1.2 Option B drafter (prebuilt-only) | PR 0.3 (implicit — no ad-hoc tool calls wired) |
| helper-stack | §1.3 data-source tagging stub | PR 0.1 (`data_dependencies` field), PR 1.1 (`Connector` adapter) |
| helper-stack | §2 external libraries | PR 1.1 (EODHD), PR 1.2 (FinanceToolkit), PR 4.1 (statsmodels), PR 4.2 (pdfplumber) |
| helper-stack | §4.1 ratio_calculator deprecation | PR 0.2 (schema migration holding step), PR 2.5 (delete file) |
| helper-stack | §4.1 budget_variance / business_investment deprecation | PR 0.2 then PR 2.5 |
| helper-stack | §4.1 saas_metrics repurpose | PR 0.2 then PR 2.9 |
| helper-stack | §6 task table (24 tasks) | Phases 1-5 collectively |
| **schema-and-skills** | §1 four-tier exposure | PR 0.1, PR 0.4 |
| schema-and-skills | §2 ArtifactType registry + DAG validation | PR 0.1 |
| schema-and-skills | §3.1 closed enums | PR 0.1 |
| schema-and-skills | §3.2 sub-model split | PR 0.1 |
| schema-and-skills | §3.3 registration with return type | PR 0.1 |
| schema-and-skills | §3.4 projection rules | PR 0.4 |
| schema-and-skills | §4 boot-time validation | PR 0.1 |
| schema-and-skills | §5 output validation flow | PR 0.1 (verifier reads runtime Pydantic) |
| schema-and-skills | §6 18-helper skills.md list | PR 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 2.10, 3.1-3.5 (per-PR) |
| schema-and-skills | §7 skills.md template | PR 2.1 (first skills.md authored) |
| **artifact-injection** | §1 pipeline placement (Stage 7a/7b) | PR 0.3 |
| artifact-injection | §2 RenderableArtifact + Fidelity | PR 0.1 |
| artifact-injection | §3 SectionPlan schema | PR 0.3 |
| artifact-injection | §4 template defaults + planner overrides | PR 0.3 (resolver), PR 0.4 (Stage 5 emit + template defaults yaml) |
| artifact-injection | §5 materialization algorithm | PR 0.3 |
| artifact-injection | §6 drafter prompt structure | PR 0.3 |
| artifact-injection | §8 verifier integration | PR 0.3 |
| artifact-injection | §9 testing strategy | PR 0.3 |
| **helpers-design** | §3 comparables (incl. §3.1 combined range, §3.2 peer-set, §3.3 NM handling) | PR 2.1 |
| helpers-design | §4 business quality + statement integrity | PR 2.5 |
| helpers-design | §4.4 Beneish M-score | PR 2.6 |
| helpers-design | §4.5 Altman Z variants | PR 2.6, PR 2.7 (shared infra) |
| helpers-design | §4.6 dividend safety | PR 2.6 |
| helpers-design | §4.7 credit + solvency | PR 2.7 |
| helpers-design | §4.8 5-step DuPont | PR 2.7 |
| helpers-design | §4.9 debt-maturity ladder | PR 2.7 |
| helpers-design | §5 DCF engine + cost of capital | PR 2.2 |
| helpers-design | §5.6 DDM family | PR 2.3 |
| helpers-design | §5.7 justified multiples | PR 2.3 |
| helpers-design | §5.8 SOTP | PR 2.3 |
| helpers-design | §6.1 SaaS KPI panel | PR 2.9 |
| helpers-design | §6.2-6.8 business-quality formulas | PR 2.5 |
| helpers-design | §7 decision layer | PR 2.4 |
| helpers-design | §8 workbook builder + remaining outputs | PR 2.10 |
| helpers-design | §9 audit fix resolutions (11 fixes) | PR 2.1 (EV bridge, combined range), PR 2.5 (Sloan, Piotroski, ROIIC, economic profit, op leverage, capitalized R&D, accruals_pct_of_ni, guidance_tracker), PR 2.9 (Magic Number) |
| helpers-design | §10 sector modules | PR 3.1-3.5 |
| **signals-addendum** | §1 insider_signal_panel (incl. Form 4 codes, role weighting, clustering, 10b5-1, asymmetric weights) | PR 2.8 |
| signals-addendum | §2 moving_average_panel | PR 2.8 |
| signals-addendum | §3 historical_multiple_trends | PR 2.8 |

If a row above has no PR assignment, that's a design-doc requirement we haven't scheduled. As of this revision, every row resolves.

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
- All 14 Stage 8 verifier issue types are reachable (at least one synthetic case per issue type, even if no real production case fires)
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

**Final helper count target:** ~178 active helpers (Wave 0 + Wave 1) at end of Phase 3. Tracked via `len(list_helpers())` in a Phase-3-exit-gate test.

**Skill doc count target:** 18 skill docs authored, one per helper on the schema-and-skills doc §6 list. Tracked via a CI test that counts `skills/*.md` files and matches against the registry's `skill_doc` references.

**Verifier issue type count:** 14 (existing closed enum) + 4 (from PR 0.3) = 18 issue types reachable. Tracked via Phase 2 exit gate assertion.
