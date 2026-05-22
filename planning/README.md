# Planning docs — entry point

This folder contains the design and implementation contracts for OpenLIA. Many docs live here, but they aren't equal in load-bearing weight. Use this file to find what you actually need to read.

---

## If you're about to build a helper for the equity research v2.2 engine

**Read in this exact order:**

1. **`2026-05-22-equity-research-implementation-plan.md` — first, every time.** Find your PR row. Read the design-doc sections it cites in §14. Apply the audit fixes listed in your PR row. Satisfy the cross-cutting requirements in §8.
2. **`2026-05-21-equity-research-helpers-design.md`** — pull the formula and logic for your helper from the cited sections. This is the source of truth for what each helper computes. 11 external-audit fixes already applied here.
3. **`2026-05-21-helpers-design-signals-addendum.md`** — only if your PR builds insider / moving-average / historical-multiple-trends helpers.
4. **`2026-05-21-helper-schema-and-skills.md`** — the universal schema contract. Every helper conforms. Sub-models (DirectoryEntry / SelectionGuidance / MechanicalContract / SkillDocRef), ArtifactType registry, DAG validation, 18-helper skills.md list.
5. **`2026-05-22-artifact-injection-redesign.md`** — the Stage 7a materialization contract. Every artifact you produce must implement `RenderableArtifact.to_markdown(level)` at three fidelities.
6. **`2026-05-21-equity-research-engine-helper-stack.md`** — high-level plan: which libraries we use, which we rejected (AGPL/GPL), helper rationalization decisions.

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
