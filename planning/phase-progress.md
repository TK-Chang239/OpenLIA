# Equity Research v2.2 — Phase progress tracker

Living checklist. **Update this file as part of each PR merge.** A PR is not "done" until its row here is checked.

For PR row definitions, design-doc refs, and acceptance criteria, see `2026-05-22-equity-research-implementation-plan.md`.

**Design-doc status:** complete. The 7 design docs in `planning/README.md` cover every helper scheduled in this plan; §14 cross-reference in the impl plan resolves row-by-row (enforced by `test_cross_reference_sections_resolve_in_cited_docs`).

---

## Phase 0 — Foundation

Hard prerequisite for everything else. Phase 0 exit gate (smoke test on MSFT) must pass before Phase 1 starts.

- [x] **PR 0.1** — Schema sub-models + ArtifactType registry + `capabilities.yaml`
- [x] **PR 0.2** — Migrate existing 7 helpers to new schema
- [x] **PR 0.3** — Stage 7a materialization + 4 new verifier issue types
- [x] **PR 0.4** — ToolDispatcher projection + Stage 5 planner rewrite + skill-doc CI lint
- [x] **Phase 0 exit gate** — smoke test on MSFT through new pipeline passes

---

## Phase 1 — Data spine

- [x] **PR 1.1** — EODHD adapter + Connector pattern (resolve Form 4 build-blocker)
- [x] **PR 1.2** — FinanceToolkit integration
- [x] **Phase 1 exit gate** — MSFT + NESN.SW fetch via adapter

---

## Phase 2 — Wave 0 core analytics

- [x] **PR 2.1** — Comparables (task #1)
- [x] **PR 2.2** — DCF engine + cost of capital (tasks #12, #6)
- [x] **PR 2.3** — Alternative valuation (DDM family + justified multiples + SOTP) (task #13)
- [x] **PR 2.4** — Decision layer (task #14)
- [x] **PR 2.5** — Business quality + statement integrity + deprecation cleanup (task #7)
- [x] **PR 2.6** — Forensic + dividend safety (task #21)
- [x] **PR 2.7** — Credit + solvency + 5-step DuPont + debt-maturity ladder (task #15)
- [x] **PR 2.8** — Signal & context helpers (task #23)
- [x] **PR 2.9** — saas_kpi_panel repurpose (task #11)
- [x] **PR 2.10** — Workbook builder + remaining outputs (task #8)
- [x] **PR 2.11** — Risk / macro helpers — drawdown_panel + yield_curve_shape (helpers-design §5.1, §5.2)
- [x] **Phase 2 exit gate** — MSFT, NVDA, CAT, X all produce complete reports; all 18 verifier parent issue types reachable; tool-overhead ≤ 15k tokens

---

## Phase 3 — Wave 1 sector modules (parallelizable)

- [x] **PR 3.1** — Banks sector module (task #16) — exit test: JPM
- [x] **PR 3.2** — REITs sector module (task #17) — exit test: O
- [x] **PR 3.3** — Pharma / biotech rNPV (task #18) — exit test: VRTX
- [x] **PR 3.4** — Energy / E&P sector module (task #19) — exit test: XOM
- [x] **PR 3.5** — Insurance sector module (task #20) — exit test: CB
- [x] **Phase 3 exit gate** — All 5 sector reports produce; sector-KPIs non-None; tool-overhead ≤ 18k

---

## Phase 4 — Supporting libraries

- [x] **PR 4.1** — statsmodels narrow scope (task #4)
- [x] **PR 4.2** — claude-cookbooks pattern adoption (task #5)
- [x] **Phase 4 exit gate** — statsmodels regression + pdfplumber extraction sanity tests pass

---

## Phase 5 — GA polish (PR 5.x)

- [x] **PR 5.x** — Token-cost telemetry (Stage 7a/7b), helper count assertion test, skill-doc CI strictness flip, capabilities.yaml refresh, docs update
  - Telemetry module: `report_v2_2/telemetry.py` + wired into `materialize.py`
  - Phase 3 exit gate test: `test_phase_3_exit_gate.py` (113 helpers, category breakdown, 18 §6 helpers with skill docs)
  - Skill-doc CI: `test_skill_docs_presence.py` flipped to FAIL (not skip) for v2.2 registry
  - Capabilities: `report_v2_2/capabilities.yaml` created with full helper catalogue
  - `workbook_builder` skill_doc wired (was `None`; now `SkillDocRef(path="skills/workbook_builder.md", ...)`)

### Parked post-5.x (do not start without explicit go-ahead)

- [ ] Task #9 — Qualitative framework helpers
- [ ] Task #10 — Verifier process-quality extensions
- [ ] Task #22 — Wave 2 sector modules (Mining, Retail, Telecom, Semis, Airlines)

---

## Pre-GA full sweep

After Phase 3 closes:

- [ ] All 5 templates × 5 sector tickers = 25 reports succeed
- [ ] 4 Phase-2 tickers on `stock_initiation_v2` = 29 reports total
- [ ] No ticker fails to produce a complete report
- [ ] p95 token cost ≤ 1.5× per-phase budget
- [ ] Final helper count target: ~120 active helpers (rationalized from the ~178 in helper-stack §9 — see impl plan §16 for the per-phase breakdown)
- [ ] Final skill doc count: 18 skill docs (one per schema-and-skills §6 entry)
- [ ] Final verifier parent issue type count: 18 (14 existing + 4 from PR 0.3); detail-code count machine-tabulated separately, no closed-set invariant

---

## Update protocol

When merging a PR:

1. Check the box for that PR row.
2. If the PR completes a phase, run the phase exit gate locally and check the gate row.
3. If a PR diverged from the impl plan, also update `2026-05-22-equity-research-implementation-plan.md` to match reality (per coding standard #9).
4. If a PR added or removed helpers from the schema-and-skills §6 list, update the target count in this file's Pre-GA section.
