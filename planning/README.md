# Planning docs — entry point

This folder contains the design and implementation contracts for OpenLIA. Many docs live here, but they aren't equal in load-bearing weight. Use this file to find what you actually need to read.

---

## If you're about to build a helper for the equity research v2.2 engine

**Read in this exact order:**

1. **`2026-05-22-equity-research-implementation-plan.md` — first, every time.** Find your PR row. Read the design-doc sections it cites in §14. Apply the audit fixes listed in your PR row. Satisfy the cross-cutting requirements in §8.
2. **`2026-05-21-equity-research-helpers-design.md`** — pull the formula and logic for your helper from the cited sections. Source of truth for §3 valuation analytic helpers, §4.1-§4.20 business-quality helpers, §5.1-§5.3 risk/macro helpers, §6.1 SaaS KPI, and §7.1-§7.7 LLM-orchestrated helpers. 11 external-audit fixes already applied.
3. **`2026-05-22-helpers-design-supplement.md`** — companion to helpers-design. Source of truth for DCF engine, cost-of-capital builder, DDM family, justified multiples, SOTP, decision layer (blender / ETR / risk-reward / rating bands), Altman variants, dividend safety, credit/solvency, 5-step DuPont, debt-maturity ladder, and the workbook_builder helper. **Required for PRs 2.2, 2.3, 2.4, 2.6, 2.7, 2.10.**
4. **`2026-05-22-helpers-design-sector-modules.md`** — source of truth for Banks, REITs, Pharma rNPV, Energy / E&P, and Insurance sector panels. **Required for PRs 3.1-3.5.**
5. **`2026-05-21-helpers-design-signals-addendum.md`** — only if your PR builds insider / moving-average / historical-multiple-trends helpers (PR 2.8).
6. **`2026-05-21-helper-schema-and-skills.md`** — the universal schema contract. Every helper conforms. Sub-models (DirectoryEntry / SelectionGuidance / MechanicalContract / SkillDocRef), ArtifactType registry, DAG validation, 19-entry `Category` enum, 18-helper skills.md list.
7. **`2026-05-22-artifact-injection-redesign.md`** — the Stage 7a materialization contract. Every artifact you produce must implement `RenderableArtifact.to_markdown(level)` at three fidelities.
8. **`2026-05-21-equity-research-engine-helper-stack.md`** — high-level plan: which libraries we use, which we rejected (AGPL/GPL), helper rationalization decisions.

---

## How we work — Option B (just-in-time per-helper design)

**The rule: detailed code-design for each helper happens in the helper's own PR, not upfront.**

What's already designed (the universal contract, set in stone):
- Schema sub-models — every helper conforms
- ArtifactType registry + DAG validation — every artifact registers
- Fidelity contract (`to_markdown(level)` at 3 levels with token caps)
- Section_plan + materialization (Stage 7a)
- Per-helper formulas + logic in `helpers-design.md`

What's deferred to the build-time PR:
- Pydantic field names and types for the artifact
- Function signature and body
- `to_markdown(level)` rendering logic at each fidelity
- skills.md body (only for the 18 complex helpers)
- Tests
- section_plan_defaults.yaml entries

**Why this works:** the universal contract enforces structural uniformity, so helpers built three months apart still fit together. The formulas in `helpers-design.md` are already audited (11 fixes applied). New code-design upfront would just drift from the code that eventually gets written.

**What you should NOT do:**
- Write a separate detailed code-design doc for your helper before implementing
- Skip the schema sub-model contract because "your case is special"
- Add fields to the schema's wrong sub-model (Pydantic catches this, but please don't try)
- Forget the audit fixes listed in your PR row

---

## Phase tracking

See `phase-progress.md` for the current build state — which PRs are merged, which are blocked, which exit gates have passed.

---

## v2.2 engine runtime docs

| File | Purpose |
|---|---|
| `packages/core/src/openlia/llm/runtime/report_v2_2/capabilities.yaml` | Engine capabilities + full helper catalogue (113 helpers, 18 skill docs) |
| `packages/core/src/openlia/llm/runtime/report_v2_2/telemetry.py` | Token-cost telemetry — Stage 7a materialize events + Stage 7b drafter call events |
| `packages/core/src/openlia/llm/runtime/report_v2_2/tools/library_helpers/skills/` | Skill docs for the 18 complex helpers (§6) |
| `packages/core/tests/test_llm/test_runtime/test_report_v2_2/test_phase_3_exit_gate.py` | Phase 3 exit gate: helper count (113), category breakdown, all 18 §6 helpers registered with skill docs |
| `packages/core/tests/test_skill_docs_presence.py` | Skill-doc CI: strict FAIL (not skip) for any §6 complex helper in v2.2 registry without skill_doc wired |

---

## Other docs in this folder (not related to v2.2 helper work)

| File | Purpose |
|---|---|
| `PLAN.md` | Full architecture description, deployment modes, data sources, installation |
| `projectStructure.md` | Detailed directory layout with design rules |
| `specs/` | Per-page UI and feature specs |
| `audits/` | Past audit findings |
| `dev-backlog/` | Loose backlog items |
| `implementation-plans/` | Older feature implementation plans (pre-2026-05) |
| `GAPS.md` | Cross-cutting gap log |
| `deferred-tasks-2026-04-24.md` | Tasks deferred from a past cycle |
| `visual_component_prompt.md` | Prompt template for visual components |
| `manifest-dogfood/` | Manifest dogfood scratchpad |

If you're working on UI, frontend, or non-equity-research backend, those are your relevant docs. The 6 dated 2026-05-21 / 2026-05-22 docs above are the equity research v2.2 engine plan.
