# Equity Research v2.2 — Execution Strategy (Steps 1 + 2)

**Date locked:** 2026-05-22
**Scope:** Full ~120 helpers; clean separation as `report_v2_2` runtime
**Out of scope (this run):** Step 3 live-report testing — deferred
**Stop condition:** Hard block on missing credential / external API / genuinely ambiguous spec → stop and surface

---

## 0. Locked decisions (16 of 17 from impl plan §12 + 1 cleanup)

| # | Decision | Locked answer |
|---|----------|---------------|
| 1 | Section count anywhere | **No hardcoded count**. Reads from `len(template.sections)`. PR 0.0 strips numerals from shared prompts. |
| 2 | Materialization issue enum | Reuse 18-parent `VerifierIssueType` + `detail_code` |
| 3 | Chart rendering | Plotly HTML (hover/zoom) + Markdown table fallback for drafter; no multimodal |
| 4 | Skill doc lint strictness | Warn during Phase 2, fail at Phase 2 exit gate |
| 5 | Citeline PoS license | Helper takes PoS as input; deferred (see #15) |
| 6 | Helper versioning | Add `deprecated_at_version: str \| None` field now; migration story deferred |
| 7 | L1.5 cache key | Session-scoped |
| 8 | ArtifactType live-reload | No — static registry rebuild on boot |
| 9 | Streaming materialization | No — batch full section_plan |
| 10 | Cross-report dedup | No — Phase 3 revisits |
| 11 | Drafter feedback loop | Not wired |
| 12 | Football-field weighting | Unweighted (min/median/max) |
| 13 | GICS prefix routing | Verify 2026 GICS codes at PR 0.4 |
| 14 | Pydantic artifact seed (PR 0.1) | Artifact types from migrated 7 helpers + 4 stage-7a core types |
| 15 | Reference data licensing | **Deferred** — helpers take reference data as input; no in-repo snapshots |
| 16 | `royalty_stack_analyzer` | Internal module of `rnpv_pipeline` |
| 17 | EV/EBITDA justified formula | Keep current + add `when_not_to_use` warning |

**Added PR 0.0 — Template flexibility cleanup.** Removes hardcoded template assumptions in shared prompts + runtime so v2.2 doesn't inherit them.

---

## 1. Branch + commit strategy

- Merge PR #153 (`feat/equity-research-engine-plan`) into `main`.
- Cut fresh `feat/equity-research-engine-impl` off `main`.
- **One commit per impl-plan PR row.** Each commit message uses the impl plan's PR title.
- **Runtime path:** new `packages/core/src/openlia/llm/runtime/report_v2_2/`. Imports from `report_v2` only where strictly reusable (shared event types, ReportRequest shape). Heavy mutations get copied + edited in v2_2.

---

## 2. PR 0.0 — Template flexibility cleanup (precursor)

Fix 6 blocking leaks + 2 stale comments so shared code is template-driven before v2.2 starts:

1. `reports/validator.py:20-45` — `_REQUIRED_RAIL_QUICK_STATS` → read from each template YAML's new `rail.required_quick_stats: [...]` key
2. `prompts/shared/editor_role.yaml.j2:10` — drop "All 14"
3. `prompts/shared/report_schema_strictness.yaml.j2:92-93` — read `min_words` per section from template
4. `prompts/shared/section_subagent_role.yaml.j2:20` — read `tolerance_pct` per section from template, default 20%
5. `prompts/shared/editor_role.yaml.j2:22` — read `expand_below_pct` per section, default 80%
6. `runtime/prior_section_summarizer.py:14-15` — read `threading.summary_word_cap` and `threading.facts_cap` from template, default 200/5
7. `subagent_runner.py:103` — comment cleanup
8. `subagent_runner.py:377` — comment cleanup

Backfill existing templates (`stock_initiation_v2.yaml`, `earnings_update_v2.yaml`, etc.) with the values they previously had hardcoded so v2 behavior is unchanged.

---

## 3. Upfront external library install

One batch via `uv add`:

```
financetoolkit statsmodels arch Riskfolio-Lib pdfplumber plotly \
eodhd quantstats scipy numpy-financial
```

If any fail to install → stop and surface. Do not substitute.

---

## 4. Step 1 — Implementation execution order

### Phase 0 — Foundations (PRs 0.0 → 0.4)

| PR | Title | Key deliverables |
|----|-------|------------------|
| 0.0 | Template flexibility cleanup | §2 above |
| 0.1 | Helper schema + ArtifactType registry + DAG validation | `schema.py`, `artifact_types.yaml` (seed), DAG validator at boot, `Category` enum (19), `VerifierIssueType` enum (18), `Fidelity` enum, `VerifierIssue` model with `detail_code` |
| 0.2 | Migrate 7 existing helpers into v2.2 schema | Wrap `comparables`, `chart_builder`, `commodity_exposure_tracker`, `saas_metrics`, `dcf_valuation` skeleton + 2 others |
| 0.3 | Stage 7a materialization + SectionPlan + verifier integration | `section_plan.py`, `materialize.py` (pure-Python), Stage 7b drafter prompt builder, verifier reads Pydantic |
| 0.4 | Stage 5 planner emit + template defaults + GICS routing | `planner.py` emits `helper_selection` + `PlannerOverrides`, `template_defaults.yaml`, GICS 2026 codes verified |

### Phase 1 — Data adapters (PRs 1.1 → 1.2)

| PR | Title | Helpers |
|----|-------|---------|
| 1.1 | EODHD adapter | ~18 wrappers around endpoints; fixtures for MSFT + NESN.SW |
| 1.2 | FinanceToolkit backend | ~15 ratio wrappers; ICE BofA spreads via FRED fetch |

### Phase 2 — Analytics core (PRs 2.1 → 2.11)

| PR | Title | Count |
|----|-------|-------|
| 2.1 | comparables suite + first skills.md | 3 |
| 2.2 | DCF + cost of capital + sensitivity/tornado/scenario/reverse_dcf | 7 |
| 2.3 | Alternative valuation (DDM, justified, SOTP) | 3 |
| 2.4 | Decision layer (blender, ETR, risk/reward, rating, football_field) | 6 |
| 2.5 | Business quality bundle (Group A) | 19 |
| 2.6 | Forensic + Altman + dividend safety + Beneish | 4 |
| 2.7 | Credit/solvency + DuPont + debt ladder | 3 |
| 2.8 | Signals (insider, MA, multiple trends) | 3 |
| 2.9 | SaaS KPIs (saas_metrics → saas_kpi_panel) | 1 |
| 2.10 | Output / workbook | 3 |
| 2.11 | Risk / macro (drawdown, yield curve) | 2 |

### Phase 3 — Sector modules (PRs 3.1 → 3.5)

JPM (banks), O (REITs), VRTX (pharma), XOM (E&P), CB (insurance).

### Phase 4 — Supporting libraries (PRs 4.1 → 4.2)

statsmodels (6 helpers), pdfplumber + cookbooks NLP (8 helpers).

### Phase 5 — GA polish

Token-cost telemetry, helper-count assertion, skill-doc CI flip warn → fail, README + capabilities.yaml refresh.

---

## 5. Per-PR template (every commit)

1. Read impl plan PR row + cited design-doc §N.
2. Write helper code under `report_v2_2/tools/library_helpers/<helper>.py`.
3. Register `HelperSchema` with `deprecated_at_version`, exposure tier, fidelity defaults.
4. For 18-list complex helpers: author `skills/<helper>.md` per schema-and-skills §7 template.
5. Write unit tests: contract, formulas, missing-data, verifier-hook.
6. `uv run ruff format . && uv run ruff check . && uv run pytest` all green.
7. Commit with impl plan PR title.
8. Update `planning/phase-progress.md`.

---

## 6. Step 1 self-audit

After all PRs land:
1. Registry boot: `list_helpers()` returns ~120
2. Per-phase helper count matches impl plan §16
3. All 18 schema-and-skills §6 helpers have `skills/<name>.md`
4. ArtifactType DAG validates without cycles
5. All 18 verifier parent types reachable via synthetic test
6. Doctest suite green (`test_planning_consistency.py`, `test_skill_docs_presence.py`)
7. Every §14 row has a corresponding commit
8. All 11 audit fixes from helpers-design §9 unit-tested
9. `pytest packages/core/tests/report_v2/` still green (v2 not regressed)

Failures → follow-up commits on same branch. Re-audit. Repeat until clean.

---

## 7. Step 2 — End-to-end engine audit

Static analysis + fixture-based dry-runs (no live LLM).

**Per-stage (1 → 9):** input/output type alignment, error paths, logging, cancellation propagation.

**Cross-stage:**
- Stage 5 → 7a: every `helper_selection` resolves
- Stage 7a → 7b: every section_plan fits token budget
- Stage 7b → 8: every drafter output parseable
- Stage 8 → 9: every verifier issue has `detail_code` or remediation
- Stage 9 → output: payload validates against `Report` Pydantic schema

**Cross-cutting:**
- Fidelity contract: every `ArtifactType` declares HEADLINE/SUMMARY/FULL
- Exposure tiers: every helper has L1/L1.5/L2 (and L3 for complex)
- Error catalog: typed exceptions, no bare `Exception`

**Output:** `planning/2026-05-22-v22-engine-audit-findings.md` with per-stage + cross-stage + cross-cutting findings, severity-ranked.

Execute remediation. Re-audit. Iterate to zero blocking gaps.

---

## 8. Hard-block surfaces

Stop and surface if:
- `uv add` fails for a required library
- A PyPI library version doesn't expose a function the design assumes
- A formula produces NaN/undefined at a boundary the test exercises
- A helper requires reference data (#15 deferred items) — block on that helper
- External API (EODHD, FRED) unreachable during fixture recording
- Genuine spec contradiction between design docs

When surfacing: state block, cited doc + line, what was tried, input needed.

---

## 9. End state

- Branch `feat/equity-research-engine-impl` with ~32 commits (one per PR + audit fixes)
- All tests green, ruff clean
- v2.2 engine boots end-to-end through fixture-based dry-run
- No live LLM call fired — Step 3 deferred
- PR opened for review
