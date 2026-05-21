# Equity Research v2.2 — Design Spec

**Date:** 2026-05-21
**Branch:** `feat/custom-templates-v2` (off `main@400b6346`)
**Supersedes:** [v2 design (2026-05-20)](2026-05-20-equity-research-v2-design.md). v2 is frozen; all implementation should reference this document.
**Driver:** v2 reframed the equity research department around an LLM-orchestrated pipeline replacing v1's deterministic Fact extraction. v2.2 sharpens that design after a second round of drilling: it splits the planner into two stages (research plan and model plan), adds a capability manifest as the single source of truth about engine version, replaces the silent "extras drop" behavior with an interactive clarifier that surfaces blocking warnings to the user, makes a Run Summary section mandatory in every report, adds a dev-mode Verification History section, expands the verifier issue taxonomy to 14 types, drops native .docx rendering in favor of HTML as canonical output (PDF/DOCX conversion remains in the existing download path), and adds a persistent cache for immutable documents (transcripts and investor-day data).
**Scope:** `packages/core/src/openlia/llm/runtime/report_v2/` (pipeline stages, capability manifest, cache, library helpers); `packages/core/src/openlia/reports/frameworks/` (`TemplateSpec` extensions); `packages/server/src/openlia_server/services/` (planner + clarifier + cache services); `packages/server/src/openlia_server/db/` (cached_documents table); `frontend/src/` (composer redesign, clarifier modal, run summary, verification history, cache admin).

---

## 1. The framing, in one paragraph

v2 took the equity research runner from deterministic Fact extraction to a planner-driven LLM pipeline; v2.2 keeps the same architectural intent but tightens the contract everywhere users, templates, or the engine itself can mislead each other. The planner is split: stage 3 declares research strands before any data is gathered, and stage 5 declares model components only after the research pool exists, so model plans are grounded in what was actually fetched. A capability manifest names every supported and unsupported feature in one file, read by both the clarifier (to surface notices and blocking warnings to the user) and the template loader (to strip reserved keys and emit notices). The clarifier becomes interactive: when it detects a request the engine cannot satisfy, it stops and asks the user to proceed without it, cancel and edit, or clarify what they meant. Every generated report ends with a mandatory Run Summary listing per-task outcomes; in dev mode a Verification History block follows with every verifier issue that was caught, including ones resolved by retry. Conditional sections are a single LLM-evaluated `trigger_when` field, evaluated at stage 7 against the same context for every section. The verifier issue taxonomy is a closed enum of 14 types in 5 categories, with deterministic detectors running before LLM detectors to limit cost. Required artifacts (template- and composer-declared) get resolved through explicit-then-derivable-then-default parameter resolution before model build attempts them. HTML is the canonical output; the existing v1 download button handles PDF and DOCX conversion. Immutable documents — transcripts and investor-day archives — are cached transparently inside the connector adapter so repeat runs of the same ticker hit cache rather than refetch. The price of all this flexibility, accumulated since v1, is the loss of typed-Fact freshness budgets and identity equations; freshness checks are not restored in v2.2 and remain backlog work.

---

## 2. Pipeline architecture (nine stages)

The pipeline that ran in v2 as eight stages is now nine. Planning splits into research planning (before gather) and model planning (after gather). All other stages remain in function but their inputs and outputs are tightened.

| # | Stage | LLM call? | Inputs | Outputs |
|---|---|---|---|---|
| 1 | Clarify | yes | composer_inputs + selected template + capability manifest | questions, blocking_warnings, notices, detected_intents |
| 2 | Read template | no (pure load) | template file | TemplateSpec; reserved-key notices |
| 3 | Research plan | yes (planner) | composer_inputs + TemplateSpec + clarifier answers + capability manifest | Plan.research_strands[], Plan.required_artifacts[] (frozen here from template + composer), section DAG |
| 4 | Gather | yes (per strand) | Plan.research_strands[] + connector adapters | ResearchPool (prose findings + citations + cache_metadata per strand) |
| 5 | Model plan | yes (model planner) | Plan.required_artifacts[] (frozen) + ResearchPool | Plan.optional_artifacts[] (added here) |
| 6 | Model build | yes (per artifact) | required + optional artifacts + library helpers | ModelArtifacts[]; resolved param provenance |
| 7 | Draft | yes (per section) | ResearchPool + ModelArtifacts + section DAG; trigger_when evaluated per conditional section | section blocks; skip banners for trigger-skipped sections |
| 8 | Verify | yes + deterministic | assembled draft + ResearchPool + ModelArtifacts + Plan | VerifierIssue[]; retry feedback into stage 7 |
| 9 | Assemble | no (renderer) | sections + citation manifest + run telemetry | HTML report with Sources, Run Summary, and (dev_mode) Verification History |

**Stage 1 — Clarify.** The clarifier reads composer_inputs + selected template + the capability manifest's `unsupported[].detect_in_prompt` patterns. It emits four outputs: clarifying form questions, blocking warnings (capability requests the engine cannot satisfy), passive notices (informational), and detected_intents (audit log). If blocking warnings exist, the run pauses in state `CLARIFY_AWAITING_USER`; the user must choose per-warning action (proceed_without / cancel_and_edit / clarify). The "clarify" action appends free text and re-runs the clarifier, up to 3 rounds total.

**Stage 2 — Read template.** Mechanical parse with side-effect notices: the template loader strips reserved keys (per capability manifest's `detect_in_template_keys`), emits a `TemplateLoadNotice` per stripped key, and validates the remaining shape against the `TemplateSpec` schema.

**Stage 3 — Research plan.** The planner LLM emits a `Plan` with `research_strands[]` (each strand named by purpose with declared tool scope) and `required_artifacts[]` (template-declared plus composer-prompt-parsed). The section DAG is derived from `SectionSpec.depends_on`. Composer-derived artifact requests get best-guess parameters; misparses surface in the Run Summary, not in a clarification round.

**Stage 4 — Gather.** Each strand dispatches a bounded subagent with a tool whitelist drawn from the registered connectors. Returns prose findings plus structured citations into the ResearchPool. Connectors are tool-agnostic adapters: MCP, Python SDK, OpenAPI/HTTP, web fetch — all expose the same `call(name, params)` shape to the strand. Cacheable tools (transcripts, investor-day data) route through the cache layer transparently; the strand subagent does not see cache logic.

**Stage 5 — Model plan.** Reads the now-populated ResearchPool. The model planner inspects what was actually gathered and decides which `optional_artifacts[]` to schedule for build. Required artifacts from stage 3 are immutable here — the model planner cannot drop them.

**Stage 6 — Model build.** Per-artifact subagents dispatched in parallel. Each artifact resolves parameters through the explicit-then-derivable-then-default path, calls the assigned library helper, returns a typed ModelArtifact. Required artifacts that fail surface as FAILED in the Run Summary; optional artifacts that fail are dropped silently.

**Stage 7 — Draft.** Per-section subagents walk the section DAG in topological order. Before dispatching each conditional section's drafter, the trigger evaluator (small LLM call) reads the section's `trigger_when`, the markdown of completed predecessor sections, the research pool index, and the model artifacts index; it returns `{fire: bool, reason: str}`. Sections that fire dispatch a drafter that produces typed blocks (prose, table, kpi_strip, chart, quote_block, citation_footer). Sections that don't fire render a skip banner.

**Stage 8 — Verify.** Deterministic detectors run first (block_shape, tombstone, year_slip, citation_unresolved, citation_orphaned, artifact_missing, required_param_unresolvable, helper_unavailable). The LLM verifier runs only against sections that passed deterministic checks, emitting citation_missing, content_too_sparse, directive_unmet, factual_inconsistency, numeric_inconsistency, and incoherent_prose issues. Issues with severity Blocker feed back into the section's drafter for retry. Convergence check: same `(section_id, issue_type)` repeating in two consecutive retries → DEGRADED early.

**Stage 9 — Assemble.** Renderer collects per-section block lists, builds the citation manifest (deduplicated, numbered by first appearance), assembles HTML with `<section>` wrappers, appends the Sources block, appends the Run Summary block (always), and appends the Verification History block (only when `capabilities.yaml: dev_mode=true`).

---

## 3. Capability manifest

A single YAML file at `packages/core/src/openlia/llm/runtime/report_v2/capabilities.yaml` declares engine version and feature surface. Both the clarifier prompt construction and the template loader read from it. No drift, single place to update on version bumps.

Structure:

```yaml
engine_version: "2.2"
dev_mode: true                # controls Verification History visibility in reports

supported:
  - id: <capability_id>
    summary: <one line>

unsupported:
  - id: <capability_id>
    summary: <one line>
    detect_in_prompt: [<seed phrases for LLM semantic matching>]
    detect_in_template_keys: [<frontmatter keys to strip + notice on>]
    planned_in: <version string or null>
    user_message: <text shown to user via clarifier blocking warning or template-load notice>

known_template_keys: [<allowed frontmatter keys; loader emits warning for unknowns>]

citation_freshness_defaults: ~   # null in v2.2; freshness budgets are not restored

cache:
  enabled: true
  transcripts: {enabled: true}
  investor_day: {enabled: true}
  default_force_refresh: false
```

The clarifier system prompt is built by injecting the rendered manifest. The template loader iterates `detect_in_template_keys` to strip and emit `TemplateLoadNotice` per stripped key, and iterates `known_template_keys` to emit `unknown_key` warnings for any frontmatter key outside the allowlist.

The composer page also reads the manifest to render a "What this version supports" sidebar so users see capabilities before they write their prompt.

---

## 4. Template architecture

### 4.1 Format and intake

Templates are uploaded as JSON or YAML. Users with source documents in other formats (Markdown, .docx) run a copy-pastable conversion prompt (provided as a button in the upload UI) in their own Claude/ChatGPT/Gemini and paste the JSON/YAML result back. This avoids brittle docx parsing on our side and concentrates LLM brittleness in the user's local LLM where they can iterate.

### 4.2 Schema additions (over v2)

```python
class TemplateSpec(BaseModel):
    template_id: str
    template_name: str
    department: str
    report_type: str                                 # SINGLE value; v2.2 locks one report type per template
    engine_version_compat: str                       # e.g., "2.2"
    composer_inputs: list[ComposerInputSpec]         # template-declared, typed fields
    required_artifacts: list[ArtifactSpec]           # template-declared; MUST attempt
    sections: list[SectionSpec]
    output_artifacts: list[ArtifactSpec]             # alias for required_artifacts; see §6
    verifier_severity_overrides: dict[str, str] = {} # issue_type -> severity override
    # (no extra_passes, loops, custom_subagents, etc. — reserved keys, stripped on load)

class ComposerInputSpec(BaseModel):
    name: str
    type: Literal["ticker", "ticker_list", "sector", "string", "enum",
                  "int", "bool", "date_range"]
    label: str
    required: bool
    enum_options: list[str] | None = None
    default: Any | None = None

class SectionSpec(BaseModel):
    id: str
    name: str
    directive: str
    depends_on: list[str] = []
    trigger_when: str | None = None                  # free-text condition, LLM-evaluated at stage 7
```

### 4.3 One report type per template (locked)

Each template produces exactly one report shape. No variants, no branches, no bundles within a single template. Variation across runs comes from `composer_inputs` (changing content) and `trigger_when` (changing section presence), not from the template branching into different output shapes. Multi-department templates, template inheritance, and template bundles are deferred to v2.3+.

---

## 5. Composer

### 5.1 Inputs

Per-template composer inputs are dynamically rendered from `TemplateSpec.composer_inputs` (typed fields). All composers also accept a free-text prompt for arbitrary elaboration. The free-text prompt feeds the clarifier and planner directly.

### 5.2 Capability sidebar

Reads `capabilities.yaml` and renders supported / unsupported lists alongside the form. Users see the engine's surface before writing a prompt, reducing the chance they request unsupported features.

### 5.3 Cache override

`force_cache_refresh: bool = False` checkbox in advanced section. When true, the run bypasses cache for all cacheable tools.

---

## 6. Artifact pipeline

### 6.1 Schema

```python
class ArtifactSpec(BaseModel):
    id: str
    type: Literal["chart", "table", "kpi_strip", "excel", "quote_block"]
    description: str
    parameters: dict = {}                            # passed through to helper
    helper: str | None = None                        # explicit name or planner-picked
    source_strand: str | None = None                 # draw from this strand if set
    target_section_id: str | None = None             # placement; planner picks if null
    source: Literal["template", "composer", "planner"]
```

### 6.2 Three artifact sources

- Template-declared (`TemplateSpec.required_artifacts[]`) — MUST attempt.
- Composer-parsed (planner parses free-text prompt) — added to `required_artifacts[]` at stage 3, MUST attempt.
- Planner-proposed (`ModelPlan.optional_artifacts[]`) — added at stage 5 based on research pool, build if data supports.

### 6.3 Helper parameter resolution

Each vendored library helper exports a `HelperSchema` with per-parameter type, default, derivation rule, and required flag. At stage 6:

1. Merge explicit params from `ArtifactSpec.parameters`.
2. For each missing required param with a derivation rule, run a resolver LLM call against the research pool.
3. For each remaining missing param, use the helper's default.
4. If any required param is still unresolved → FAIL the artifact with a clear remediation message in Notes.
5. Pass resolved params to `helper.execute()`. Record full provenance.

The Run Summary echoes the resolved params (defaults + derivations) so the user can verify what was actually used.

### 6.4 Library helpers (vendored)

From `alirezarezvani/claude-skills` (MIT, attribution preserved in file headers), vendored into `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/`:

- `dcf_valuation.py` (DCF with optional sensitivity grid)
- `ratio_calculator.py` (liquidity, leverage, profitability, efficiency ratios)
- `forecast_builder.py` (revenue/EBIT/cash forecasts; deterministic + scenario)
- `budget_variance.py` (variance analysis vs budget)
- `business_investment.py` (ported from SKILL.md prose math)
- `saas_metrics.py` (CAC, LTV, payback, quick ratio, unit economics)

Categories deferred to v2.3+ (registered as "not yet implemented"):

- Quant finance (VaR, Sharpe, Sortino, Black-Scholes)
- Portfolio optimization
- Time-series analysis
- Statistical inference
- Macro indicators / FX
- Screener / factor screening
- Risk metrics
- NLP (sentiment, NER)
- PDF parsing

When a `required_artifact` references a deferred category, the artifact lands as FAILED in the Run Summary with `helper_category_unavailable`.

For chart and Excel output: `matplotlib` (charts as inline SVG or PNG) and `openpyxl` (Excel attachments) are picked as defaults. User can override later.

---

## 7. Conditional sections

A section is conditional iff its `trigger_when` field is non-null. All evaluation happens at stage 7, immediately before the section's drafter would dispatch. The evaluator is a single LLM call with uniform context across all sections:

```
Condition: {section.trigger_when}
Composer inputs: {composer_inputs JSON}
Predecessor sections (depends_on):
  {section_id: completed markdown OR "<SKIPPED: reason>"}
Research pool index: {strand_id: one-line summary}
Model artifacts index: {artifact_id: one-line description}
Return JSON: {fire: bool, reason: str}
```

True → dispatch drafter. False → render skip banner: `> **{section_name}** — skipped\n> {reason}` (HTML: blockquote with `.skip-banner` class).

Cascade behavior: predecessor skips surface as `<SKIPPED: reason>` in successor evaluator context. No auto-cascade — the template author opts in via condition text if they want that semantics.

Evaluator failure (malformed JSON, LLM error) → `fire=true` (fail-open). The choice favors completeness over correctness here because the worst outcome is rendering a section that should have been skipped, which the user can re-run to fix.

Conditionality is template-declared only. The planner cannot add or remove `trigger_when` at run time.

---

## 8. Verifier issue taxonomy

Closed enum, 14 issue types in 5 categories. Severity defaults below are starting points; templates may override via `verifier_severity_overrides`.

### Structural (deterministic)

- `block_shape` (Blocker) — block JSON malformed (table missing headers, empty prose).
- `tombstone` (Blocker) — boilerplate phrases ("I cannot", "[placeholder]", "TODO", "as an AI") via extensible regex.
- `year_slip` (Blocker) — year reference inconsistent with `retrieved_at` of cited source.

### Citation

- `citation_missing` (Blocker, LLM) — factual claim without a `[c:id]` marker.
- `citation_unresolved` (Blocker, deterministic) — marker references an ID not in the research pool.
- `citation_orphaned` (Warning, deterministic) — citation in pool never embedded; pool hygiene only.

### Coverage

- `artifact_missing` (Blocker, deterministic) — required artifact built but never embedded in any section.
- `content_too_sparse` (Blocker, LLM) — non-conditional section produced too little content given the directive.
- `directive_unmet` (Blocker, LLM) — section content does not address one or more directive points.

### Quality

- `factual_inconsistency` (Blocker, LLM) — claim contradicts another in the report or the cited source.
- `numeric_inconsistency` (Blocker, LLM) — same metric appears with different values in multiple blocks. **v1 → v2.2 loss**: was deterministic via typed-Fact substrate; now LLM-driven only and less reliable for any specific known fact.
- `incoherent_prose` (Warning, LLM) — disjointed, tangential, domain-term misuse.

### Artifact-build

- `required_param_unresolvable` (Blocker, deterministic) — required helper param had no explicit value, no derivation match, no default.
- `helper_unavailable` (Blocker, deterministic) — required artifact references unimplemented helper category.

### Detector ordering

Deterministic detectors run first on a section. If any deterministic Blocker fires, the LLM verifier does not run on that section — the section retries until deterministic passes, then the LLM verifier runs. This limits verifier LLM cost on sections that have basic structural problems.

### Issue schema

```python
class VerifierIssue(BaseModel):
    issue_type: Literal[<the 14 strings above>]
    section_id: str | None              # null for whole-report issues
    severity: Literal["blocker", "warning"]
    evidence: str
    suggested_fix: str | None
    detector: Literal["deterministic", "llm"]
```

---

## 9. Retry policy

Targeted retries with structured feedback at every stage that can fail, not blind retries.

| Stage | Failure | Feedback passed on retry |
|---|---|---|
| 4 Gather | Strand subagent crashes / returns empty | Error message; retry once; second fail → strand marked `failed` |
| 5 Model plan | Invalid `ModelPlan` schema | Pydantic validation errors; retry once; second fail → no optional artifacts |
| 6 Model build | Analyst subagent crash / artifact malformed | Error trace, helper name, partial output if any; retry once; second fail → artifact FAILED |
| 7 Draft | Drafter returns empty / unparseable | "Previous draft returned no content / parse error: {detail}"; retry once |
| 8 Verify → re-draft | Verifier issues fire | Full `VerifierIssue[]` filtered to that section, with `suggested_fix` where verifier proposed one; retry up to 3x → DEGRADED |

Drafter retry prompt:

```
Previous draft of {section_id} failed verification with these issues:
{for each issue}
  - [{severity}] {issue_type}: {evidence}
    Suggested fix: {suggested_fix or "none"}
{end}
Address each issue and re-produce the section.
```

**Convergence check.** Track `(section_id, issue_type)` across verifier retries. If the same pair recurs in two consecutive attempts → fast-fail to DEGRADED with reason `loop_did_not_converge`. The outer cap of 3 retries still applies.

---

## 10. Output

### 10.1 HTML primary

Canonical pipeline output is HTML. PDF and DOCX downloads route through the existing v1 download button (HTML → PDF via `weasyprint` or equivalent; HTML → DOCX via `pandoc` or equivalent). Native per-block .docx rendering (proposed in v2 Q16) is dropped; `python-docx` is removed from runtime deps.

### 10.2 Block render contract

Each typed block exposes `render_html() -> str`. Block types:

- `prose` — drafter produces markdown internally; renderer converts to HTML via `markdown-it` or `python-markdown`.
- `table` — `{headers, rows, caption}` → `<table class="report-table">`.
- `kpi_strip` — `{cells: [{label, value, unit, delta}]}` → `<div class="kpi-strip">`.
- `chart` — matplotlib SVG (preferred) or PNG base64 → inline `<svg>` or `<img>`.
- `quote_block` — `{quote, source, citation_id}` → `<blockquote class="source-quote">`.
- `citation_footer` — assembled at render time, `<ol class="citations">`.
- `skip_banner` — `{section_name, reason}` → `<blockquote class="skip-banner">`.
- `degraded_banner` — `{section_name, reason, issue_list}` → `<blockquote class="degraded-banner">`.
- `excel_attachment` — file reference → `<a class="attachment" download>` with preview row count.

### 10.3 Citation rendering (preserved from v1)

Drafters embed `[c:<citation_id>]` markers in prose, tables, captions, KPI cells, and quotes. Renderer scans all blocks, assigns display numbers by first-appearance order, deduplicates (same source cited N times = one footer entry with N backlinks), and emits inline `<sup><a>` links plus an aggregated `<ol class="citations">` Sources section at the bottom of the report.

### 10.4 Section ordering

1. Template-declared sections (with skip / degraded banners as applicable)
2. Sources
3. Run Summary
4. Verification History (only when `dev_mode=true`)

### 10.5 Run Summary (mandatory)

Schema:

```python
class TaskOutcome(BaseModel):
    task_type: Literal[
        "clarification", "research_strand", "model_component",
        "section_draft", "trigger_eval", "verification", "output_render"
    ]
    task_name: str
    status: Literal["OK", "SKIPPED", "DEGRADED", "FAILED"]
    notes: str | None = None
    duration_ms: int

class RunSummary(BaseModel):
    engine_version: str
    template_id: str
    template_name: str
    composer_inputs: dict
    outcomes: list[TaskOutcome]
    unsupported_requests_dismissed: list[str]       # user proceeded past these in clarifier
    unsupported_requests_slipped: list[str]         # not caught until run-time
    total_duration_ms: int
    total_token_cost: int | None
    cache_stats: dict                                # hits / misses / bytes per source_type
```

Detection points for `unsupported_requests_slipped[]`:

1. Planner — emits `slipped_request` log entry for any composer intent it cannot map to a supported tool/library/section type.
2. Model build — `helper_category_unavailable` issue → recorded.
3. Verifier — persistent `directive_unmet` issues that trace back to an unsupported capability → recorded.

The Run Summary block is included in PDF/DOCX downloads (it is the final section of the report content).

### 10.6 Verification History (dev mode)

Visible only when `capabilities.yaml: dev_mode=true`. Aggregates every verifier issue raised during the run including ones resolved by retry. Schema:

```python
class VerificationHistoryEntry(BaseModel):
    issue: VerifierIssue
    raised_at_round: int                # 0 = initial verification, 1+ = retry rounds
    final_resolution: Literal[
        "resolved", "persisted_degraded", "persisted_failed", "still_open"
    ]
    resolved_in_round: int | None

class VerificationHistory(BaseModel):
    entries: list[VerificationHistoryEntry]
    total_issues_raised: int
    resolved_on_first_retry: int
    resolved_on_subsequent_retry: int
    persisted_to_degraded: int
    warnings_open: int
```

Rendered as a status-tinted table (resolved=green, degraded=red, warning_open=yellow, persisted_failed=red-bold). Telemetry persists regardless of dev_mode display — `repo_item.verification_history` JSONB always populated.

---

## 11. Extras rejection policy

The previously-proposed extra-pass extension surface (custom reviewer LLMs, review loops, custom subagents) is **not in v2.2 scope**. Detection happens in two places:

- **Clarifier (composer prompt).** When the clarifier detects intent matching `capabilities.yaml: unsupported[].detect_in_prompt` patterns, it emits a `CapabilityWarning` and pauses the run for user action.
- **Template loader (frontmatter keys).** When the loader sees `extra_passes`, `extra_calls`, `loops`, `review_loops`, `custom_subagents`, `reviewer_passes`, `check_passes`, or any other reserved key, it strips the key and emits a `TemplateLoadNotice` (yellow banner in upload UI).

Reserved keys are documented future-work slots so v2.3+ implementation drops in cleanly. The schema is named; the behavior is just "rejected with notice" in v2.2.

---

## 12. Persistent cache

### 12.1 Scope

Caches **transcripts** and **investor-day documents**. Other source types (live quotes, news, estimates, fundamentals) not cached in v2.2; see §17 for rationale.

### 12.2 Storage

SQLite table `cached_documents` in `packages/server/src/openlia_server/db/`. Works for both personal and company modes.

Schema:

```python
class CachedDocument(SQLAlchemy model):
    cache_key: str (PK, UNIQUE)             # "tegus:NVDA:2026Q1" or "eodhd:investor_day:NVDA:2026-03-15"
    source: str                              # adapter id
    document_id: str                         # opaque identifier from source
    ticker: str | None                       # indexed
    fiscal_period: str | None                # "2026Q1", "FY2026"; nullable
    content_text: str
    raw_metadata: dict                       # JSON
    original_retrieved_at: datetime
    cached_at: datetime
    bytes_size: int
```

Index on `(ticker, fiscal_period)`.

### 12.3 Where the cache check lives

Inside the connector adapter wrapper, not strand subagent code. Every cacheable tool routes through the wrapper transparently:

```
adapter.call(tool, params):
  if tool.cacheable:
    key = build_cache_key(tool, params)
    hit = cached_documents.get(key)
    if hit and not force_refresh:
      emit cache.hit
      return hit.content_text + hit.raw_metadata, served_from_cache=True
    else:
      result = tool.execute(params)
      cached_documents.upsert(key, result, ...)
      emit cache.miss
      return result, served_from_cache=False
  else:
    tool.execute(params)
```

Cacheable flag declared per registered tool. v2.2 pre-flags transcript tools and the investor-day fetcher. Adding more later = one flag flip.

### 12.4 TTL and invalidation

No automatic TTL — cached documents are immutable. Manual invalidation:

- Per-run `force_cache_refresh: bool = False` in composer inputs.
- Per-tool template override: `tools_to_refresh: [<tool_name>]`.
- Admin endpoint: `DELETE /api/cache/documents?ticker=X` for manual eviction.

### 12.5 Citation and freshness

Citations from cached content carry `retrieved_at = original_retrieved_at` (honest about real fetch date) plus `served_from_cache: bool = True` flag for telemetry. The visible Sources footer does not advertise cache status to the reader.

Freshness budgets are not restored in v2.2 (see §17). Cache does not weaken the freshness story because there is no freshness story in v2.2.

### 12.6 Run Summary cache stats

```
Cache:
  Transcripts: 4 hit / 1 miss (saved ~18k tokens, ~12s)
  Investor day: 1 hit / 0 miss (saved ~6k tokens, ~3s)
  Total cache savings this run: ~24k tokens, ~15s
```

---

## 13. UI surfaces

Concrete UI deltas across the frontend. Reuses v1 components where possible.

### 13.1 Composer page (`frontend/src/pages/<Department>/Composer`)

- Free-text prompt input alongside template selection and `composer_inputs` form fields.
- Dynamic form renderer for `composer_inputs` typed fields (ticker, ticker_list, sector, string, enum, int, bool, date_range) with per-type validation.
- "What this version supports" sidebar fed by `capabilities.yaml`. Two collapsible lists with `planned_in` annotations on the unsupported side.
- `force_cache_refresh` checkbox under an Advanced section.
- Template selector shows `report_type` label per template.

### 13.2 Clarifier modal (`frontend/src/components/ClarifierModal`)

New component. Renders when SSE event `clarifier.warnings_pending` fires.

- Warning panel above the clarifying questions; one row per `CapabilityWarning` with three buttons (Proceed without it / Cancel & Edit / Clarify).
- "Clarify" expands an inline text input.
- Round counter (`Round X of 3`) in the title. After round 3, "Clarify" button is hidden.
- Submit disabled until every warning has an action chosen.
- New run state badge: `CLARIFY_AWAITING_USER`.

### 13.3 Template upload / review (`frontend/src/components/TemplateUpload`)

- Reserved-keys banner (yellow): "Template declared `extra_passes`. Not supported in v2.2; ignored."
- Unknown-key warning (yellow) for any frontmatter key outside `capabilities.yaml: known_template_keys`.
- Conditional-language suggestion (blue): "Section X's directive contains 'if applicable.' Consider adding `trigger_when:`." with one-click add affordance.
- File format support: accept `.yaml`, `.yml`, `.json`.
- "Convert your doc to a template" button → copies a self-contained conversion prompt the user runs in their own LLM and pastes the result back.
- Preview pane shows parsed composer_inputs, required_artifacts, sections (conditional ones highlighted), helper picks per artifact.

### 13.4 Report viewer (`frontend/src/components/ReportViewer`)

- New block render targets: table, kpi_strip, chart (inline SVG or PNG), quote_block, excel_attachment.
- New section types: Run Summary (always), Verification History (dev_mode).
- Status-tinted cells in the Run Summary outcomes table (OK / SKIPPED / DEGRADED / FAILED).
- Reused from v1 PR 15: skip banner component, degraded banner component, citation footnote + Sources footer pattern.
- Footer carries `engine_version` from the manifest.

### 13.5 Run telemetry (`frontend/src/components/RunTimeline`)

- Stage count 8 → 9 (two-stage planning split).
- Per-strand subagent rows under Gather.
- Per-artifact build rows under Model Build.
- Per-section drafter rows under Draft.
- New events surfaced inline: `clarifier.warnings_pending`, `clarifier.notices`, `extras_rejected`, `cache.hit | miss | write`, `trigger_evaluated`, `artifact.attempted | completed | failed`, `verifier.issue_raised | resolved | persisted`, `slipped_request`.

### 13.6 Settings (`frontend/src/pages/Settings`)

- `dev_mode` toggle (controls Verification History visibility in reports). Default ON in v2.2.
- Cache toggles: global enable, per-source-type (transcripts, investor_day).
- Engine version display (read-only, from manifest).

### 13.7 Cache admin panel (`frontend/src/components/CacheAdmin`)

New panel.

- Cache stats: total entries, total bytes, hit rate (last 30 days).
- Per-ticker breakdown: count of cached docs, last access.
- "Clear cache for ticker X" → calls `DELETE /api/cache/documents?ticker=X`.
- "Clear all" with confirmation.

### 13.8 Repo / Reports list (`frontend/src/pages/Repo`)

- Each card shows engine_version badge plus status counts ("8 OK / 2 DEGRADED").
- Tooltip on hover: Run Summary preview.
- Filter: by engine_version (for users with reports across versions during v1 → v2.2 transition).

### 13.9 Download button

No UI change. Backend verification task (`O2-verify-download-path`) confirms HTML input is accepted by existing PDF/DOCX converters (likely already true; if not, swap to `weasyprint` + `pandoc`).

---

## 14. Connectors and tools

### 14.1 Connector abstraction (generalized over v2)

Connectors are not MCP-only. The runtime registers adapters of multiple kinds — MCP servers, Python SDKs (e.g., for EODHD's official Python client), OpenAPI/HTTP backends, web fetch. All adapters expose the same shape:

```python
class ConnectorAdapter(Protocol):
    name: str
    tool_kind: Literal["mcp", "python_sdk", "openapi", "web", "internal"]
    cacheable: bool
    def list_tools(self) -> list[ToolMeta]
    def call(self, tool: str, params: dict) -> ToolResult
```

Strand subagents see tool names as `<adapter>.<tool>` (e.g., `eodhd.get_fundamentals_data`), not `mcp__eodhd__get_fundamentals_data`. The mapping from this user-facing name to the underlying invocation is the adapter's responsibility.

### 14.2 Existing tools

EODHD and TWSE MCP servers continue to work (their adapters wrap the existing MCP invocation). Additional Python SDK adapters can be registered post-v2.2 without core changes.

---

## 15. Locked decisions reference (one-line summaries)

- Pipeline split into 9 stages (research plan + model plan are separate).
- Capability manifest at `capabilities.yaml` drives clarifier and template loader.
- Clarifier interactive: blocking warnings with 3 actions (proceed_without / cancel_and_edit / clarify), max 3 clarification rounds.
- Extras (extra passes, review loops, custom subagents) rejected with notice; reserved keys named for future versions.
- Conditional sections: single `trigger_when` field, LLM-evaluated at stage 7, uniform context for all sections, fail-open on evaluator error.
- Verifier issue taxonomy: closed enum, 14 types, 5 categories, deterministic-first detector ordering.
- Retry policy: targeted feedback at every stage; verifier convergence check; max 3 retries → DEGRADED.
- Artifacts: required (template + composer, MUST attempt) vs optional (planner-proposed, best-effort); helper param resolution explicit > derivable > default.
- Library helpers: 6 vendored from claude-skills (DCF, ratios, forecasts, budget variance, business investment, SaaS metrics); 11 categories deferred.
- Output: HTML primary; PDF/DOCX via existing v1 download path; native docx dropped.
- Citations: v1 inline-footnote + bottom-Sources pattern preserved.
- Run Summary: mandatory final section; status taxonomy OK / SKIPPED / DEGRADED / FAILED.
- Verification History: dev-mode-only section after Run Summary; full audit of every issue including resolved.
- Cache: transcripts + investor-day, SQLite-backed, in adapter wrapper layer, no TTL, manual + per-run force-refresh.
- Freshness budgets: not restored in v2.2.
- One report type per template (no variants / branches / bundles).

---

## 16. Acknowledged losses vs v1

| Capability | v1 | v2.2 |
|---|---|---|
| Typed-Fact substrate | YES (extractors per template) | GONE (research-notes-only) |
| Per-fact freshness budgets | YES (deterministic, hard-block) | GONE (not restored) |
| `oldest_data_as_of` banner | YES | GONE |
| Identity equations / deterministic numeric_consistency | YES | DEGRADED (LLM-driven only) |
| Per-tool extractor code | YES (per mode) | GONE (replaced by templates) |
| Hardcoded report modes | 3 (stock_research, stock_initiation, sector_research) | NONE (all are templates) |
| Native .docx renderer | Proposed in v2 Q16 | NOT IMPLEMENTED (HTML primary, converted on download) |

Net: v2.2 trades v1's deterministic-but-narrow correctness guarantees for template-flexibility and capability surface. Coverage is broader (every template gets the same pipeline; any connected data source works) but reliability for any specific known fact is lower.

---

## 17. Out of scope and deferred

For v2.3+ backlog:

- Freshness signals in v2 pipeline (drop the v1 typed-Fact approach; design something LLM-friendly).
- Extra-pass extension surface (custom reviewer LLMs, review loops, custom subagents).
- Template variants, bundles, inheritance / mixins.
- Distributed cache (Redis) and cross-user shared cache in company mode.
- Caching of news, fundamentals, consensus estimates (immutability and freshness windows need design work).
- Library helpers categories 4–11, 13 (quant finance, portfolio, time-series, stats, macro, screener, risk, NLP, PDF parsing) — user will pick libraries later.
- Deterministic `numbers_to_check[]` template field that re-introduces a deterministic numeric_consistency check for explicitly-declared metrics.
- Cache size cap / LRU eviction (manual cleanup endpoint covers v2.2 needs).
- Cache admin panel beyond the minimal MVP (size charts, per-ticker time series).

---

## 18. PR sequencing (high-level)

Four phases. The detailed PR list with tasks lives in the implementation plan at `docs/superpowers/plans/2026-05-21-equity-research-v2.2.md`.

**Phase F — Foundation.**
F1: Capability manifest + loader + clarifier prompt construction.
F2: TemplateSpec extensions (composer_inputs, required_artifacts, ArtifactSpec, trigger_when, verifier_severity_overrides).
F3: Connector adapter abstraction (generalize MCP → registered adapters).
F4: Library helpers vendored from claude-skills + `HelperSchema` + helper registry.
F5: Cache subsystem (CachedDocument model, alembic migration, adapter wrapper).

**Phase P — Pipeline.**
P1: Stage 1 Clarifier — interactive flow with blocking warnings + clarification re-run loop.
P2: Stage 3 Research planner LLM + Plan schema (research_strands, required_artifacts frozen, section DAG).
P3: Stage 4 Gather — strand subagent dispatch through adapter wrapper.
P4: Stage 5 Model planner + ModelPlan schema (optional_artifacts).
P5: Stage 6 Model build — per-artifact subagents + parameter resolver.
P6: Stage 7 Drafter — per-section subagents + trigger evaluator + skip banners.
P7: Stage 8 Verifier — deterministic detectors + LLM verifier + retry feedback + convergence check.

**Phase O — Output.**
O1: HTML block renderers (prose, table, kpi_strip, chart, quote_block, excel_attachment).
O2: Citation manifest assembler + Sources footer + verify-download-path (HTML accepted by existing converters).
O3: Run Summary assembly + rendering.
O4: Verification History assembly + rendering (dev_mode-gated).
O5: Stage 9 Assemble — section ordering, footer, engine_version metadata.

**Phase X — UI.**
X1: Composer redesign (free-text prompt, capability sidebar, dynamic composer_inputs form, force_cache_refresh).
X2: Clarifier modal component (blocking warnings, three actions, clarification loop, round counter).
X3: Template upload review (notices, JSON support, conversion-prompt button, conditional suggestion).
X4: Report viewer block render targets + Run Summary + Verification History components.
X5: Cache admin panel + settings toggles + repo list status counts.

**Phase V — Validation.**
V1: Per-stage unit tests.
V2: End-to-end smoke per default template (stock_initiation, stock_research, sector_research; all template-converted).
V3: Multi-ticker smoke against AI-infra basket.

Total: ~22 PRs across 5 phases. v2 was 14 PRs; v2.2 adds 8 PRs net (capability manifest, blocking clarifier, run summary, verification history, cache, library helpers, model planner split, helper resolver) and removes 1 PR (native docx).

---

## 19. Testing strategy

- **Per-stage unit tests.** Capability manifest loader; template loader stripping reserved keys; clarifier output schema; planner Plan schema validation; strand subagent with mock adapter; model planner ModelPlan schema; helper schema + resolver param provenance; drafter prompt assembly; trigger evaluator; verifier deterministic + LLM detectors; retry loop with convergence check; cache hit/miss; HTML block renderers.
- **End-to-end smoke per default template.** Three legacy modes converted to templates; each generates a coherent report against a fixed ticker. No identical-output requirement (typed Facts are gone); coherence verified by LLM verifier plus manual review.
- **Clarifier interactive flow.** Composer prompt with known unsupported intent surfaces blocking warning; each of three actions produces the expected downstream state.
- **Trigger-skip test.** Template with trigger_when fires false → skip banner; fires true → section prose.
- **Verifier retry test.** Section deliberately failing one verifier check resolves on retry round 1; section failing three times lands DEGRADED; section with same `(section_id, issue_type)` pair across two consecutive rounds fast-fails to DEGRADED.
- **Cache test.** Same ticker run twice: second run hits cache for transcripts; force_cache_refresh=true bypasses.
- **Run Summary test.** Every status type (OK / SKIPPED / DEGRADED / FAILED) renders in the outcomes table; `unsupported_requests_dismissed` and `unsupported_requests_slipped` lists populate correctly.
- **Verification History test.** Issues resolved by retry appear with `final_resolution=resolved`; persisted issues appear with `final_resolution=persisted_degraded`. `dev_mode=false` hides the section.

---

## 20. Success criteria

- All locked decisions in §15 implemented.
- All three legacy modes converted to default templates that run through the new pipeline and produce reports without crash.
- A user-uploaded JSON/YAML template with `composer_inputs`, `required_artifacts`, `trigger_when` declarations produces a non-crashing report.
- A composer prompt requesting an unsupported feature surfaces a blocking warning in the clarifier and the user can resolve it three ways (proceed / cancel / clarify).
- A run of the same ticker twice shows cache hits in the Run Summary on the second run.
- Run Summary appears on every report; Verification History appears when `dev_mode=true`.
- HTML report converts to PDF and DOCX via existing v1 download paths without manual intervention.

---

## 21. Open questions

- Final `weasyprint` vs `pandoc` choice for HTML → PDF and HTML → DOCX in the download path (likely both, but verification task O2 confirms).
- Whether `markdown-it-py` or `python-markdown` is the right markdown-to-HTML renderer for prose blocks (lean toward `markdown-it-py` for spec compliance).
- Resolver LLM model tier for parameter derivation (probably the cheap tier — same as trigger evaluator).
- Whether the `slipped_request` detection in §10.5 needs a dedicated LLM call or can piggy-back on the verifier (probably piggy-back via a new verifier issue type in a later version).

These are implementation-time decisions; none block the plan.
