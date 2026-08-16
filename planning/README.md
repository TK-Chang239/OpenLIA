# Planning docs — entry point

This folder contains the design and implementation contracts for OpenLIA. Many docs live here, but they aren't equal in load-bearing weight. Use this file to find what you actually need to read.

> **Reconciled 2026-08-16 (audit Stage 4).** The equity-research engine is now **v3, a single-model tool-use loop** — it is the *sole* equity-research engine. The v1 / v2 / v2.2 / v2.3 engines were **removed** (PRs #220/#222); only `report_v2_3/{schemas.py, research/, templates/}` survives as a **shared library** for v3 and Earnings Update. The old v2.2-helper build guide that used to open this file is now in [Archived / historical](#archived--historical-engines-removed) at the bottom — do not follow it for live work. CLAUDE.md's "Equity Research Engine" section is the authoritative summary.

---

## Start here (current, load-bearing)

| Doc | Read it when |
|---|---|
| `../CLAUDE.md` (§ *Equity Research Engine*) | Any equity-research work — the authoritative statement of what engine is live and what's shared. |
| `PLAN.md` | You need the full architecture, deployment modes (personal / company), data sources, installation. |
| `projectStructure.md` | You need the directory layout and the boundary rules (core / server / frontend). |
| `specs/pages/` | You're building or changing a page — one spec per department page plus Portfolio / Repo / Settings / Setup wizard. |
| `specs/components/` | You're touching a shared component (sidebar, chat interface, file viewer, report thumbnail, …). |
| `specs/systems/` | You need a cross-cutting system contract (data provider, report rendering, macro dashboards). |
| `GAPS.md` | You want the cross-cutting gap log (verify entries against code — some are stale). |
| `dev-backlog/` | You're picking up a loose backlog item. |
| `audits/` and `../docs/audit-2026-08-16.md` | You want past audit findings and the current staged remediation plan. |

---

## The live engines (where the code is)

The generation engines all live under `packages/core/src/openlia/llm/runtime/`:

| Engine | Directory | Department | Spec / reference |
|---|---|---|---|
| **Equity Research (sole ER engine)** | `report_v3/` | Equity Research | `2026-05-27-equity-research-v3-single-model-spec.md` (shipped); page spec at `specs/pages/departments/EquityResearchV3PageSpec.md` |
| Earnings Update v2 | `report_eu/` | Earnings Update | fork of v3; `specs/pages/departments/EarningsUpdatePageSpec.md` |
| Morning Briefing | `report_mb/` | Morning Briefing | fork of `report_eu`; `specs/pages/departments/MorningBriefingsPageSpec.md` |
| Macro Research (dashboard) | `report_dash_mr/` | Macro Research | `specs/pages/departments/MacroResearchPageSpec.md` |
| Retail Sentiment (dashboard) | `report_dash_rs/` | Retail Sentiment | sibling of `report_dash_mr`; `specs/pages/departments/RetailSentimentPageSpec.md` |

**Shared library (not an engine):** `report_v2_3/` retains only `schemas.py`, `research/`, and `templates/` — imported by v3 and Earnings Update. Its old 8-stage pipeline engine is gone; do not reintroduce it.

**Legacy, kept on purpose:** the generic `runtime/report.py` / `subagent_runner.py` / `reports/` engine and the v1 `reports` table are **not** equity-specific — Morning Briefing and the legacy `earnings_update` route still use them. Keep them.

Server routes for v3 live at `packages/server/src/openlia_server/routes/departments/equity_research_v3.py` + `services/v3_*`; frontend at `frontend/src/pages/departments/EquityResearchV3.tsx` + `components/equity-research-v3/`.

---

## Phase tracking

`phase-progress.md` is a **superseded** tracker for the removed v2.2-era equity-research engine — kept for history only, not a live checklist. There is no active phase tracker for v3 (it shipped); use the audit plan (`../docs/audit-2026-08-16.md`) for current work.

---

## Other docs in this folder

| File | Purpose |
|---|---|
| `PLAN.md` | Full architecture description, deployment modes, data sources, installation |
| `projectStructure.md` | Detailed directory layout with design rules |
| `specs/` | Per-page UI + feature specs, shared-component specs, cross-cutting system specs |
| `audits/` | Past audit findings |
| `dev-backlog/` | Loose backlog items |
| `implementation-plans/` | Older feature implementation plans (pre-2026-05) |
| `GAPS.md` | Cross-cutting gap log |
| `deferred-tasks-2026-04-24.md` | Tasks deferred from a past cycle |
| `visual_component_prompt.md` | Prompt template for visual components |
| `manifest-dogfood/` | Manifest dogfood scratchpad |

---

## Archived / historical (engines removed)

> **Everything below documents the v1 / v2 / v2.2 / v2.3 equity-research engines, which were REMOVED (PRs #220/#222). It is retained only so historical PRs and design decisions stay legible. Do NOT follow any of it as a build guide — the code, files, and tests it references no longer exist.**

### v2.2 helper build guide (dead — do not follow)

This folder used to open with a step-by-step guide for "building a helper for the equity research v2.2 engine." That engine is gone. The 6 dated 2026-05-21 / 2026-05-22 design docs it pointed at (`2026-05-22-equity-research-implementation-plan.md`, `2026-05-21-equity-research-helpers-design.md`, `2026-05-22-helpers-design-supplement.md`, `2026-05-22-helpers-design-sector-modules.md`, `2026-05-21-helpers-design-signals-addendum.md`, `2026-05-21-helper-schema-and-skills.md`, `2026-05-22-artifact-injection-redesign.md`, `2026-05-21-equity-research-engine-helper-stack.md`) remain on disk as history but describe a helper stack, universal schema contract, and just-in-time per-helper PR workflow ("Option B") that no live code implements.

### v2.2 engine runtime docs (paths no longer exist)

The table below used to point implementers at the v2.2 engine's runtime files. **Every path is deleted** (verified 2026-08-16 — the whole `report_v2_2/` module was removed in PR #220). Listed only so old references resolve to an explanation:

| Former file | Was |
|---|---|
| `packages/core/src/openlia/llm/runtime/report_v2_2/capabilities.yaml` | Engine capabilities + helper catalogue — **deleted** |
| `packages/core/src/openlia/llm/runtime/report_v2_2/telemetry.py` | Token-cost telemetry — **deleted** |
| `packages/core/src/openlia/llm/runtime/report_v2_2/tools/library_helpers/skills/` | Skill docs for the complex helpers — **deleted** |
| `packages/core/tests/test_llm/test_runtime/test_report_v2_2/test_phase_3_exit_gate.py` | Phase 3 exit gate test — **deleted** |
| `packages/core/tests/test_skill_docs_presence.py` | Skill-doc CI presence test — **deleted** |

For anything current, use [Start here](#start-here-current-load-bearing) and [The live engines](#the-live-engines-where-the-code-is) above.
