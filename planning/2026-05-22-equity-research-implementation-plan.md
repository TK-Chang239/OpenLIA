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

**Files:**
- `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/__init__.py` — extend with sub-model `HelperSchema`, keep back-compat `description` field
- `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/categories.py` (new) — closed `Category` enum
- `packages/core/src/openlia/artifacts/__init__.py` (new) — `RenderableArtifact` base, `Fidelity` enum
- `packages/core/src/openlia/artifacts/registry.py` (new) — load `artifact_types.yaml`, expose `lookup(artifact_id) -> type[RenderableArtifact]`
- `packages/core/src/openlia/artifacts/artifact_types.yaml` (new) — seeded with placeholders for the 5-6 artifact types the existing helpers already produce
- Tests: registration validation (boot-time DAG), Category enum closure

**Acceptance:** registering a helper with `produces_artifacts=["nonexistent"]` fails at registration; cycle in producer/consumer graph fails registry boot; existing 6 helpers still register (via back-compat wrapper).

**Risk:** none meaningful; pure additive.

### PR 0.2 — Migrate existing 6 helpers + saas_metrics to new schema

**Files:** each helper module fills in `directory` / `selection` / `contract` sub-models; deletes the legacy `description`-only schema.

**Acceptance:** every existing helper has a `DirectoryEntry`, `SelectionGuidance` with non-empty `when_to_use` / `when_not_to_use`, and `MechanicalContract` with `produces_artifacts` populated. Registry boot-time DAG passes.

**Risk:** low. The migration is mechanical; tests already cover helper invocation.

### PR 0.3 — Stage 7a materialization

**Files:**
- `packages/core/src/openlia/llm/runtime/report_v2/section_plan.py` (new) — `SectionPlan`, `PlannerOverrides`, override resolver
- `packages/core/src/openlia/llm/runtime/report_v2/materialization.py` (new) — `materialize()` algorithm with dedup, back-references, canonical-site rule, orphan logging
- `packages/core/src/openlia/llm/runtime/report_v2/runner_v2.py` — insert Stage 7a between current Stage 6 and current Stage 7
- New verifier issue types: `block_artifact_too_large`, `block_plan_artifact_missing`, `block_section_plan_invalid`, `block_headline_missing_quantitative`
- Tests: each of the 7 test cases listed in §9 of the artifact-injection design doc

**Acceptance:** end-to-end test runs a synthetic helper pipeline → produces typed artifacts → applies overrides → materializes deterministic markdown → drafter sees sectioned prompt. All seven targeted unit tests pass.

**Risk:** medium. The materialization algorithm has real complexity (dedup + canonical-site ordering). Mitigate with the unit-test matrix.

### PR 0.4 — ToolDispatcher projection + template default loader

**Files:**
- `packages/core/src/openlia/llm/runtime/report_v2/tools/dispatcher.py` (new) — `project_l1`, `project_l1_5`, `project_l2`, `project_l3`
- `packages/core/src/openlia/llm/runtime/report_v2/templates/stock_initiation_v2/section_plan_defaults.yaml` (new) — first reference example, seeded with the 5-6 existing artifacts
- Wire dispatcher into Stage 3 (clarifier) + Stage 5 (planner) prompt assembly
- Tests: projection at each tier returns only that tier's fields; mistake of adding a field to wrong sub-model is caught by Pydantic

**Acceptance:** Stage 3 + Stage 5 planners receive L1 / L1.5 directly; L2 is loaded only after planner picks; L3 is on-demand.

**Risk:** low; planner stages already accept structured context.

**Phase 0 exit gate:** all four PRs merged; `feat/equity-research-engine-plan` rebased into a clean PR against main; end-to-end smoke run against existing `stock_initiation_v2` template produces a valid (but minimal) report through the new pipeline.

---

## 3. Phase 1 — Data spine (2 PRs)

**Goal:** EODHD adapter + FinanceToolkit integration provide the data and math primitives that ~80% of Wave 0 helpers depend on.

### PR 1.1 — EODHD adapter (backlog task #2)

**Files:**
- `packages/core/src/openlia/data/eodhd/` (new package) — typed wrappers per EODHD endpoint
- Each wrapper registers as a `register_library_helper` entry with `data_dependencies=["eodhd.<endpoint>"]`
- **Build-blocker resolution:** confirm whether `eodhd_insider_transactions` returns raw Form 4 codes (P/S/A/M/F/G/C/D/X) or only buy/sell flag. If only buy/sell: open a follow-up to source raw codes from SEC EDGAR.

**Acceptance:** all EODHD endpoints currently called from anywhere in the codebase now flow through the adapter; legacy direct-call sites removed; one integration test per endpoint using recorded fixtures.

**Risk:** medium. EODHD MCP endpoints may have rate/quota constraints not yet stress-tested.

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

Comparables is the entry point because (a) it's a documented gap and (b) many downstream helpers (historical multiple trends, football field chart, justified multiples) reference its artifacts.

**Helpers:** `comparables.run`, `peer_set_builder`, `football_field_chart`
**Artifacts:** `peer_multiple_panel`, `implied_price_range`, `football_field_render`
**skills.md:** `comparables.md`
**Acceptance:** runs against 5 test tickers across 3 sectors; combined-range methodology matches design doc §3.1 (min/median/max of per-multiple medians).

### PR 2.2 — DCF engine + cost of capital (backlog tasks #12, #6)

The dependency anchor for everything valuation-related.

**Helpers:** `cost_of_capital_builder`, `dcf_engine`, `sensitivity_grid_builder`, `tornado_diagram`, `scenario_weighting`
**Artifacts:** `dcf_base_valuation`, `cost_of_capital_panel`, `sensitivity_grid`, `tornado_diagram_render`, `scenario_weighted_value`
**skills.md:** `dcf_engine.md`, `cost_of_capital_builder.md`
**Acceptance:** mid-year convention configurable; terminal value supports both Gordon and McKinsey Key Value Driver; CAPM / Hamada / build-up methods all produce results; verifier rejects `terminal_growth > risk_free_rate`.

### PR 2.3 — Alternative valuation methodologies (backlog task #13)

**Helpers:** `ddm_family` (Gordon / multi-stage / H-model), `justified_multiples`, `sotp_builder`
**Artifacts:** `ddm_valuation`, `justified_multiple_panel`, `sotp_segment_valuation`
**skills.md:** `ddm_family.md`, `justified_multiples.md`, `sotp_builder.md`
**Acceptance:** each DDM variant validates against published textbook examples (1-2 per variant).

### PR 2.4 — Decision layer (backlog task #14)

**Helpers:** `price_target_blender`, `expected_total_return`, `risk_reward_calculator`, `implied_upside_downside`, `rating_band_assigner`
**Artifacts:** `price_target_consensus`, `etr_panel`, `risk_reward_panel`, `rating_recommendation`
**skills.md:** `price_target_blender.md`, `rating_band_assigner.md`
**Acceptance:** blender weights are surfaced as configurable; ratings explainable (why-this-rating string included in artifact).

### PR 2.5 — Business quality + statement integrity (backlog task #7)

**Helpers:** Piotroski F-score, Dechow-Dichev accrual quality, Sloan accruals (level, not first-difference per audit fix), earnings persistence, ROIIC, economic profit (avg IC base per audit fix)
**Artifacts:** `business_quality_panel`, `statement_integrity_panel`
**skills.md:** `statement_integrity_bundle.md`
**Cleanup:** deprecate and remove `budget_variance.py`, `business_investment.py`, `ratio_calculator.py`

### PR 2.6 — Forensic + dividend safety (backlog task #21)

**Helpers:** Beneish M-score, Altman Z variants (Z, Z', Z", EM Z"), dividend coverage, dividend payout sustainability
**Artifacts:** `forensic_panel`, `dividend_safety_panel`
**skills.md:** `forensic_panel.md`

### PR 2.7 — Credit + solvency + 5-step DuPont (backlog task #15)

**Helpers:** Altman variants (shared infra with PR 2.6), 5-step DuPont, interest coverage variants, debt-maturity ladder
**Artifacts:** `credit_solvency_panel`, `dupont_decomposition`, `debt_maturity_ladder`

### PR 2.8 — Signal & context helpers (backlog task #23)

**Helpers:** `insider_signal_panel`, `moving_average_panel`, `historical_multiple_trends`
**Artifacts:** `insider_signal`, `ma_panel`, `historical_multiple_trends`
**skills.md:** `insider_signal_panel.md`, `historical_multiple_trends.md`
**Build-blocker:** assumes PR 1.1 has resolved the Form 4 code question.

### PR 2.9 — saas_kpi_panel repurpose (backlog task #11)

**Helpers:** `saas_kpi_panel` (replaces `saas_metrics.py`)
**Artifacts:** `saas_kpi_panel`
**Acceptance:** input schema is quarterly (not monthly); supports ARR/NRR/GRR/Magic Number with corrected formula per audit fix (no `×4`).

### PR 2.10 — Workbook builder + remaining outputs (backlog task #8)

**Helpers:** `workbook_builder`, remaining chart / table helpers
**Artifacts:** `workbook_render`
**skills.md:** `workbook_builder.md`
**Acceptance:** produces a multi-sheet xlsx with cross-sheet formulas, formatted to a published convention.

**Phase 2 exit gate:** `stock_initiation_v2` template can run end-to-end against a tech ticker (MSFT, NVDA) and a value/cyclical ticker (CAT, X) and produce a complete report through Stage 7b. All 14 Stage 8 verifier issue types testable.

---

## 5. Phase 3 — Sector modules — Wave 1 (5 PRs, parallelizable)

Each sector PR is independent of the others. Can be tackled in any order or in parallel.

| PR | Task | Helpers / artifacts |
|---|---|---|
| 3.1 | #16 Banks | `banks_sector_panel` (NIM / CET1 / ROTCE / efficiency / NCO), `loan_loss_provision_analysis` |
| 3.2 | #17 REITs | `reit_valuation_panel` (FFO / AFFO / NAV / same-store NOI), `cap_rate_analysis` |
| 3.3 | #18 Pharma | `rnpv_pipeline` (Citeline 2024 PoS table embedded), `royalty_stack_analyzer` |
| 3.4 | #19 Energy / E&P | `ep_sector_panel` (EBITDAX, DACF, netback, reserves replacement, AISC variant) |
| 3.5 | #20 Insurance | `insurance_valuation_panel` (combined ratio, embedded value, P&C vs Life) |

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

These don't block Phase 0 but should be resolved before they're needed:

1. **`stock_initiation_v2` template's actual section list:** the 12-section template in code vs. the 14-section claim in prompts doc (observation #8589). Reconcile during PR 0.4.
2. **Verifier issue-enum vs sub-enum for materialization issues:** materialization adds 4 new issue types; either expand the closed 14-type enum to 18 or introduce a sub-enum. Decide during PR 0.3.
3. **Multimodal chart rendering:** how charts attach to the drafter call. Decide during PR 2.2 (first chart-heavy helper).
4. **Skill doc CI lint:** how strict is the frontmatter vs schema check. Decide during PR 0.4.

---

## 13. What happens after Phase 5

This plan covers Waves 0 + 1. Wave 2 (#22 sector modules + #9 qualitative + #10 verifier process-quality) is intentionally out of scope until real-run feedback informs priorities. The expected loop after Phase 3:

1. Run reports against ~50 tickers across all 5 Wave-1 sectors.
2. Capture verifier failure modes, drafter wandering patterns, and user complaints.
3. Use those to scope Wave 2 (more sectors? more verifier rules? qualitative framework primitives?).

The branch shipped to main at end of Phase 3 is the v2.2 GA cut. Wave 2 work happens on subsequent branches.
