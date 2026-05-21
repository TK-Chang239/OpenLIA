# Equity Research v2 — Design Spec

> **SUPERSEDED.** This design has been superseded by [Equity Research v2.2](2026-05-21-equity-research-v2.2-design.md), dated 2026-05-21. v2.2 changes the pipeline shape (two-stage planning), adds the capability manifest, interactive clarifier with blocking warnings, mandatory Run Summary, Verification History (dev mode), persistent cache, expanded verifier taxonomy, HTML output (drops native docx), and more. Retained here for historical reference. **Do not implement from this version.**

**Date:** 2026-05-20
**Branch:** `feat/custom-templates-v2` (off `main@400b6346`)
**Driver:** v1 of custom report templates (PRs 1–16, merged) made the runner template-agnostic and let users upload their own report templates. v2 reshapes the equity research department around two product moves: (i) collapse the three hardcoded modes into ordinary templates, and (ii) redesign the composer to accept a ticker plus a free-form prompt, fed into a planner-driven LLM pipeline that replaces deterministic facts extraction with parallel research subagents over the user's connected MCP tools.
**Scope:** `packages/core/src/openlia/llm/runtime/report_v2/` (planner, gather, model, draft, verify stages); `packages/core/src/openlia/reports/frameworks/` (`TemplateSpec` extensions); `packages/server/src/openlia_server/services/` (planner + clarifier services); `frontend/src/pages/EquityResearch/` (composer redesign).

---

## 1. The framing, in one paragraph

v1 lifted equity-research-flavored mechanics off the runner and onto the template side of the contract. v2 takes the next step: the runner stops being a deterministic facts-extractor + section-drafter and becomes an eight-stage LLM-orchestrated pipeline. A planner LLM reads (ticker, template, user prompt, optional clarifications) and emits a structured `Plan` declaring (a) which research strands to dispatch and what MCP/web tools each gets, (b) which model components to build with what assumptions, and (c) per-section drafting directives. Stage 4 dispatches the strands in parallel; each is a bounded subagent that fetches via the user's connected tools and returns prose findings plus citations. Stage 5 builds a quantitative `ModelArtifact` from the planner's declared components. Stage 6 drafts sections from the research pool plus the model artifact. Stage 7 runs surviving deterministic validators plus an LLM verifier that auto-retries failing sections. The price of this flexibility is the loss of v1's typed-Fact substrate (the freshness budgets, identity equations, and numeric-consistency checks lose their primary input), traded for the ability to run any template against any connected data source without per-template extraction code. Alongside the pipeline rewrite, the department's three modes (`stock_research`, `stock_initiation`, `sector_research`) demote to ordinary `TemplateSpec` entries in the registry, and the composer's input schema becomes template-declared so a sector-research template can ask for a sector input where a stock-initiation template asks for a ticker.

---

## 2. The eight-stage pipeline

| # | Stage | LLM? | Inputs | Outputs |
|---|---|---|---|---|
| 1 | Clarify | yes (clarifier) | composer_inputs + TemplateSpec | 0–N answered Q&A pairs |
| 2 | Read template | no | template_id | `TemplateSpec` |
| 3 | Plan | yes (planner) | composer_inputs + Q&A + TemplateSpec | `Plan` object |
| 4 | Gather data | yes (N parallel strand subagents) | `Plan.research_strands` | `research_pool` (prose + citations per strand) |
| 5 | Build model | yes (model-analyst) | `Plan.model_components` + research_pool | `ModelArtifact` (named slots) |
| 6 | Draft sections | yes (per-section subagents) | TemplateSpec.sections + research_pool + ModelArtifact + `Plan.drafting_directives` + helpers manifest | section markdown + citations |
| 7 | Verify | yes (LLM verifier) + deterministic survivors | assembled draft + research_pool + ModelArtifact + citations + `Plan.output_artifacts` | issue list; failures retry; N-fail → `DEGRADED` |
| 8 | Assemble | no | validated sections + citation pool | HTML/markdown final; PDF/`.docx` on-demand |

### 2.1 The `Plan` schema (load-bearing contract)

```
Plan {
  research_strands: list[{
    name: str
    purpose: str
    tools_allowed: list[str]      # MCP tool ids + "web_search"
    expected_artifacts: list[ArtifactSpec]
  }]
  model_components: list[{
    helper_id: str
    assumption_overrides: dict
  }]
  drafting_directives: {
    global_directive: str          # user's prompt + clarifications context
    per_section: dict[section_id, SectionDirective]   # optional per-section overrides
  }
  output_artifacts: list[{
    name: str
    type: "prose" | "table" | "chart"
    required: bool
    source: "strand" | "model" | "section"
  }]
}
```

`output_artifacts` is template-declared (the template says "I need a `guidance_trend` table from the transcript strand"); the planner echoes it into the plan; the verifier checks all required artifacts arrived.

### 2.2 Stage-by-stage notes

**Stage 1 — Clarify.** One-shot pre-plan only (no mid-run pauses). Clarifier LLM reads composer_inputs + the selected template and emits 0–N questions as a form (multiple-choice + free-text). User answers; answers attach to the planner's context. If 0 questions, the form is skipped entirely.

**Stage 3 — Plan.** Single LLM call. Output is the `Plan` JSON above, validated against schema. Planner sees the full TemplateSpec, the user's prompt, the answered Q&A, and a manifest of MCP tools the user has connected. Planner decides strand allocation (count, scope, tool subset per strand) — no fixed strand list.

**Stage 4 — Gather data.** Dispatcher spawns one async subagent per planner-declared strand, giving each its tool subset. Each subagent runs a multi-round tool-use loop (cap and per-strand telemetry). Outputs are prose findings keyed by strand, plus a shared citation pool. No typed Facts.

**Stage 5 — Build model.** Model-analyst subagent runs the planner-declared component list (`["three_scenario_forecast", "peer_multiples", "dcf"]` etc.) with the planner-supplied assumption overrides. Helpers come from the registry built in v1 PR 8. Output is a `ModelArtifact` with named slots populated by component outputs, each carrying its assumptions and source citations.

**Stage 6 — Draft sections.** Section subagents (one per section, parallel where dependencies permit) read: section brief, research pool slice, model artifact slice, helpers manifest, plus `Plan.drafting_directives.global_directive` appended to every section's prompt (the user's prompt threads everywhere). Trigger-gated sections (see §4.1) defer until their dependencies complete.

**Stage 7 — Verify.** Deterministic survivors: block-shape, tombstone phrases (template-extensible), year-label slip, citation manifest resolution. LLM verifier reads the assembled draft + research pool + model artifact + `Plan.output_artifacts` and emits structured issues `{issue_type, section_id, severity, evidence}`. Issues feed back into the section retry loop; N-fail (default 3) → `DEGRADED` terminal state with a banner.

**Stage 8 — Assemble.** Existing citation manifest + renderer. `.docx` rendered on-demand when the user clicks the download button (see §4.2).

---

## 3. Composer redesign + mode collapse

### 3.1 Composer

Composer input fields are **template-declared**. `TemplateSpec` carries a new field:

```
composer_inputs: list[{
  name: str
  type: "ticker" | "ticker_list" | "sector" | "string" | "enum" | "date_range" | "int"
  label: str
  required: bool
  validator_id: str | None       # ticker resolver, sector enum, etc.
  default: Any | None
}]
```

Composer reads the selected template's schema and renders fields dynamically. A single optional free-form `prompt` textbox always appears as the last input regardless of the template (the planner consumes it via `drafting_directives.global_directive`).

Default templates' `composer_inputs`:

- `stock_initiation`: `[ticker (required), prompt (optional)]`
- `stock_research`: `[ticker (required), prompt (optional)]`
- `sector_research`: `[sector (required), peer_tickers (optional list), prompt (optional)]`

User-uploaded templates declare via the v1 frontmatter convention.

### 3.2 Mode collapse

The department's three modes (`stock_research`, `stock_initiation`, `sector_research`) demote to ordinary `TemplateSpec` entries in the registry. The department's `report_type` enum is removed. The UI mode picker becomes a template picker that lists the three defaults plus any user-uploaded templates, grouped by source ("built-in", "mine", and later "shared").

This requires parallel TemplateSpec lifts for `stock_research` and `sector_research` (v1 PRs 2–7 did the equivalent for `stock_initiation`).

---

## 4. §8 features in scope

### 4.1 Conditional section dispatch (LLM trigger evaluator)

`SectionSpec` gains `trigger_when: str | None` (free-text condition) and `depends_on: list[section_id]`. When all `depends_on` sections complete, a small LLM call evaluates the condition against the concatenated dependency markdown and returns boolean. True → dispatch; false → render a skip banner and continue. No structured section-output schemas required.

### 4.2 `.docx` output (parallel native renderer, on-demand)

Each block type in the rendering pipeline gains a `render_docx` method using `python-docx`, alongside its existing `render_html`. The report viewer shows a "Download as `.docx`" button that triggers rendering on click — no pre-render cost. Charts render as embedded images.

**Constraint:** Block-type catalog stays a fixed runtime registry. New block types require parallel `render_docx` methods. Acceptable since block types are rendering atoms, not template-scoped.

### 4.3 Transcript time-series strand (pure-strand, prose + table)

No new persistent transcript store. Planner allocates a transcript-research strand when the template's `composer_inputs` includes a `transcript_window` field (e.g., last N quarters). Strand uses whatever transcript-fetching MCP/web tools the user has connected. Strand emits prose findings plus a structured table per the template's `output_artifacts` spec (e.g., a `guidance_trend` table with template-declared columns).

**Constraint:** Requires a connected transcript tool. Without one, the strand returns "transcript data unavailable" and dependent sections trigger-skip or render gracefully.

### 4.4 Investor-Day archive strand (pure-strand, prose + table)

Same shape as the transcript strand. Planner allocates an "investor-day history" strand; subagent fetches via connected MCP/web. No persistent archive — each run re-fetches. Strand emits prose plus a comparison table per template's `output_artifacts` spec.

**Constraint:** Depends on connected tools and on web sources retaining historical investor-day announcements (often paywalled or delisted).

---

## 5. Hardcoding audit (what is fixed by design vs. what is template-driven)

**Fixed by design (the runtime OS):**

- The 8-stage pipeline structure
- The `Plan` schema (planner output contract)
- The `TemplateSpec` schema itself (the surface templates fill in)
- Block-type catalog (rendering atoms: paragraph, table, chart, citation)
- Surviving deterministic validators (block-shape, year-label, citation manifest)
- Helper registry (templates compose; new helpers require code — see deferred items §7)

**Template-driven (no hardcoded assumptions about scope):**

- Composer input fields (no ticker assumption)
- Section list, briefs, voice, trigger conditions, dependencies
- Output artifact schemas (table/chart shapes per template)
- Research strand count, scope, tool allocation (planner-decided, template-influenced)
- Model components built and their assumptions
- Tombstone phrase set (universal floor; templates may extend)
- Material event classes / catalyst classes (v1 work, lives in templates)
- Industry overlays (v1 work, lives in templates)

---

## 6. Out of scope for v2

**Subsumed by v2 design (no separate work):**

| Item | Why |
|---|---|
| §8 Mode B sub-agent review pass | Q9 LLM verifier is already a separate-context review pass |
| §8 Industry-level facts entity | Research-notes pool covers industry findings as a strand |
| §8 Deep per-peer KSF facts | Same — peer findings flow as strand prose |

**Ruled out by design choice:**

| Item | Why |
|---|---|
| Mid-run AskUserQuestion | Q10=A picks one-shot pre-plan clarifier only |
| Persistent transcript store | Q17=A picks pure-strand handling; no storage layer |
| Persistent investor-day archive | Q18=A picks pure-strand handling; no storage layer |
| Structured KPI extraction / time-series typed Facts | Strand outputs are prose + ad-hoc tables only |

**Deferred from v1 §7, still deferred:**

| Item | Reason |
|---|---|
| User-defined helpers | Security / review surface |
| Multiple report types per one template | One `TemplateSpec` = one shape |
| Template sharing / marketplace | Cross-user permissions out of scope |
| Template version history | Each save overwrites |

---

## 7. PR sequencing (high-level)

Three phases. Each PR within a phase is shippable on its own; phases can interleave where independent. Detailed PR scoping happens in the implementation plan.

### Phase 1 — Foundation

| PR | Scope |
|---|---|
| F1 | Extend `TemplateSpec` with `composer_inputs`, `output_artifacts`, `trigger_when`, `depends_on`, `model_components`. Pure additive. |
| F2 | Composer redesign — dynamic field rendering from selected template's `composer_inputs`. Default templates keep ticker-only path. |
| F3 | Mode collapse PR 1 — `stock_research` TemplateSpec loader. |
| F4 | Mode collapse PR 2 — `sector_research` TemplateSpec loader. Department `report_type` enum removed; UI mode picker becomes template picker. |

### Phase 2 — Pipeline buildout

| PR | Scope |
|---|---|
| P1 | `Plan` schema + planner LLM stage. Planner runs; downstream stages still on v1 facts path behind a feature flag. |
| P2 | Clarify stage — one-shot pre-plan clarifier + form UI. |
| P3 | Gather stage rebuild — parallel strand subagents replacing `facts/pack.py`. Per-template `gather_mode: legacy | strands` flag for safe migration. |
| P4 | Build-model stage — model-analyst subagent + `ModelArtifact` schema. |
| P5 | Draft adaptation — section subagents read `research_pool` + `ModelArtifact` instead of facts slices. |
| P6 | Verify stage rebuild — LLM verifier + retry feedback + new `DEGRADED` reasons. |
| P7 | Conditional dispatch — `trigger_when` + LLM trigger evaluator wired into the dispatcher. |

### Phase 3 — Output + strand templates

| PR | Scope |
|---|---|
| O1 | `.docx` renderer — per-block `render_docx` methods + report-viewer download button. |
| O2 | Default templates' `composer_inputs` + `output_artifacts` declarations updated to use the new surface. |
| O3 | Default template additions: investor-day-history strand on stock_initiation; transcript-trend strand on stock_initiation or a new earnings-deep-dive default template. |

**Total: ~14 PRs.** Phase 1 must land before Phase 2 starts. Phase 3 can start mid-Phase-2 in parallel. Each PR ships with its own tests and a regression check.

---

## 8. Backward compatibility

- Existing reports rendered pre-v2 stay readable — their stored markdown + citation manifest are unchanged.
- `POST /api/reports` continues to accept `report_type` but resolves it to a template id via a thin compatibility shim removed after Phase 1.
- Existing tests against `stock_initiation` typed-Fact behaviors will be deleted in P3 along with the legacy gather path. The "identical-output" smoke from v1 no longer applies once the pipeline switches to strands.
- The new pipeline is opt-in via `gather_mode: strands` at the template level during P3–P6; default templates flip to strands in P5 once the model + draft stages stabilize.

---

## 9. Testing strategy

- **Per-stage unit tests.** Planner output validation against the `Plan` schema; strand subagent dispatch with mock tools; model-analyst component execution; section subagent prompt assembly; verifier issue emission and retry feedback.
- **End-to-end smoke per default template.** stock_initiation / stock_research / sector_research each generate a coherent report against a fixed ticker with the new pipeline. No identical-output requirement (typed Facts are gone); coherence is verified by the LLM verifier + manual review.
- **Custom-template smoke.** A minimal user-uploaded template (3 sections, 2 strands, 1 model component) generates a non-crashing report.
- **Trigger-skip test.** A template with a `trigger_when` condition that should fire false produces a skipped-section banner; one that fires true produces section prose.
- **Verifier retry test.** A section deliberately failing one verifier check retries successfully on the second pass; a section failing three times lands in `DEGRADED`.
- **`.docx` round-trip test.** A rendered report opens cleanly in Word with editable tables and embedded charts.

---

## 10. Success criteria

The initiative is done when:

- The equity research department exposes one runner, one template picker, and a single composer whose input fields adapt to the selected template's `composer_inputs`.
- The eight-stage pipeline runs end-to-end against all three default templates with the strands gather mode enabled.
- Users can write a free-form prompt alongside a ticker selection; the prompt threads into every section via `drafting_directives.global_directive`.
- A user-uploaded template with `composer_inputs`, `output_artifacts`, `trigger_when`, and `model_components` declarations produces a non-crashing report.
- `.docx` download works for any report.
- The LLM verifier surfaces real issues against deliberately-broken section drafts and the retry loop resolves them where resolvable.

---

## 11. Open implementation questions for the plan stage

These are deferred to the implementation plan, not the design:

- The detailed planner prompt (system message + JSON schema validation pattern).
- The detailed clarifier prompt and the question-type UI primitives.
- The strand-subagent base prompt template (how it instructs the subagent to format findings + citations).
- The verifier prompt (issue taxonomy and severity rubric).
- The MCP-tool manifest format the planner reads (likely an extension of the existing connectors_service).
- The `composer_inputs` validator registry — which built-in validators ship (ticker resolver already exists; sector enum is new).
