# Subagent Report Architecture — Design

**Date:** 2026-05-16
**Status:** Draft — pending implementation plan
**Branch:** `feat/subagent-report-architecture`
**Related issue:** [#121](https://github.com/TK-Chang239/OpenLIA/issues/121) (cost driver investigation)
**Predecessor PR:** [#122](https://github.com/TK-Chang239/OpenLIA/pull/122) (initial cost + quality fixes)

---

## Problem

Equity-research report generation through the existing two-phase `ReportRunner` costs ~$1.50 per 14-section report and ships with notable quality issues:

- **"Data not available" placeholders** scattered through sections — the model gives up on data it failed to fetch on the first try and never returns
- **Inaccurate values** — numbers in TextBlocks sometimes disagree with the MetricCards/Tables in the same section
- **Weak narrative threading** — sections read like independent fragments; cross-cutting themes are not carried through
- **Thin analysis** — surface-level commentary on data points without interpretation
- **Uneven section depth** — some sections under-developed, others bloated

Cost analysis of run `r_f03c92dd8c30` confirmed two specific structural drivers behind the spend:

1. **Mid-loop tool registry expansion** — `request_additional_tools` called twice, invalidating the prompt cache mid-run
2. **Writing-phase redundant reads** — ~10 of 18 `read_payload` calls in the writing phase duplicated content the fetching phase had already loaded into history

PR #122 shipped surgical fixes (`FETCHING_MAX_OUTPUT_TOKENS`, drop tool after first use, citation footnote wiring, prompt caching enablement). Those landed cost in the ~$0.80-1.00 range. To reach ≤$0.50 *and* address the quality issues, the architecture itself needs to change.

## Goals

- **Cost ceiling:** ≤$0.50 per equity-research report (14 sections, standard depth)
- **Quality:** eliminate "data not available" gaps, tighten narrative threading, even out section depth, catch numeric inaccuracies
- **Backward compat:** existing `ReportRunner` and all other departments stay untouched; flag-gated rollout
- **Frontend stability:** no SSE event changes; existing report viewer renders the new pipeline's output unchanged

## Non-goals (deferred to v2)

- Parallel subagent execution (sequential is fine — time is not a constraint)
- Per-section model overrides (one subagent model per run)
- Subagent emergency `read_payload` escape hatch
- Plan caching across reports of the same ticker
- Editor's tool access to `read_payload` for emergency lookups
- Extending to non-equity-research report departments

---

## Architecture overview

A new `SubagentReportRunner` runs alongside the existing `ReportRunner`. Same `ReportRequest`/SSE-event contract, different internal flow:

```
ReportStart
  └─→ ReportPhase("planning")
      └─→ Flagship: forced plan_report tool call → ReportPlan (validated, 1 repair turn)
  └─→ ReportPhase("eager_fetch")
      └─→ Dispatcher: parallel batched fetch of every (tool, args) declared in the plan
                       deduped, materialized into a {ref:path → value} map
  └─→ ReportPhase("section_drafting")
      └─→ for each section in plan.sections (sequential):
            Subagent (cheap model, no tools): one short conversation
              context = role prompt + style + this section's plan + its data slice
                        + 200-word summaries of prior sections
              output = SectionDraft (blocks + word_count + open_questions)
            Orchestrator builds a deterministic 200-word summary of the draft
            yield ReportSectionComplete (streams to UI progressively)
  └─→ ReportPhase("editing")
      └─→ Flagship: forced submit_report tool call
              context = thesis + themes + all SectionDrafts + open_questions
              output = final ReportSchema (cover, sections, rail, citations)
  └─→ _finalize_submit_payload (existing: server fields + normalize + meta_stats)
  └─→ validate_report_payload (existing strict validator)
  └─→ ReportComplete
```

**Why this hits the targets:**

| Quality issue | How it's addressed |
|---|---|
| "Data not available" | Plan enumerates every data path upfront; orchestrator validates that each fetch returns a value before subagents start |
| Inaccurate values | Editor pass cross-checks TextBlock claims against MetricCards/Tables; subagent guardrail rejects uncited quantitative claims |
| Weak narrative threading | Plan declares `cross_section_themes`; subagents receive 200-word summaries of prior sections; editor threads themes explicitly |
| Thin analysis | Plan declares `key_questions` and `word_budget` per section; subagent guardrail rejects undersized output |
| Uneven section depth | `word_budget` enforced (±20%); editor expands underweight sections |

| Cost driver | How it's addressed |
|---|---|
| Redundant tool calls | Eager-fetch dedups by (tool, args); subagents have no tools (cannot re-fetch) |
| Growing conversation history | Per-subagent context is isolated; no monolithic 100K-token writing loop |
| Flagship on every turn | Subagents run on a user-chosen cheap model |
| Cache invalidation mid-run | No mid-loop tool list mutation in the subagent path |

---

## Section 1 — Plan schema

Pydantic models in `packages/core/src/openlia/llm/runtime/plan_schema.py`.

```python
class DataPath(BaseModel):
    """Either references an existing payload ref, or a tool call to fetch one."""
    ref: str | None = None              # existing payload ref (from a prior tool call in this plan)
    tool_name: str | None = None        # tool to dispatch (e.g., "eodhd__get_fundamentals_data")
    tool_arguments: dict | None = None  # arguments for the tool
    path: str | None = None             # JSON path inside the payload, or null for the whole thing
    purpose: str                        # 1-line explanation

    @model_validator
    def one_source(cls, v):
        # Exactly one of (ref) or (tool_name + tool_arguments) must be set
        ...

class SectionPlan(BaseModel):
    section_id: str                     # snake_case, must match a framework section_id
    title: str
    narrative_goal: str                 # 1-2 sentence thesis for this section
    key_questions: list[str] = Field(min_length=3, max_length=6)
    target_depth: Literal["brief", "standard", "deep"]
    word_budget: int = Field(ge=100, le=2000)  # enforced ±20% at draft time
    data_paths: list[DataPath]
    cross_refs: list[str] = []          # section_ids whose conclusions feed this one

class ReportPlan(BaseModel):
    company_thesis: str                 # 2-3 sentence top-level thesis
    sections: list[SectionPlan] = Field(min_length=1)
    cross_section_themes: list[str] = Field(min_length=2, max_length=4)

    @model_validator
    def section_ids_unique_and_in_framework(cls, v):
        # All section_ids must be unique AND must match a section in the requested framework
        ...
```

### Validation gates (runtime-enforced, before any subagent runs)

1. Pydantic schema validation (extra=forbid; word_budget range; key_questions count; etc.)
2. Every `section_id` exists in the framework loaded for `request.mode`
3. Every `DataPath.tool_name` (when set) is a registered tool the dispatcher can handle
4. Every `DataPath.ref` (when set) is either already known OR is produced by another `DataPath` earlier in the plan (topological check)

On validation failure: one repair turn with structured error feedback (same pattern as `submit_report` validation). On second failure: `ReportError` event emitted, run aborts.

---

## Section 2 — Subagent contract

`SubagentClient` in `packages/core/src/openlia/llm/runtime/subagent_client.py`.

### Request shape

```python
class SubagentRequest(BaseModel):
    # Cacheable prefix (identical across all subagents in a run; lives above cache_breakpoint):
    role_prompt: str                    # "You are a section writer. Output structured blocks. ..."
    style_guide: str                    # report-mode style guide (mode-specific, stable)
    schema_strictness: str              # the existing report_schema_strictness guide

    # Per-subagent (varies; lives below cache_breakpoint):
    company_thesis: str
    cross_section_themes: list[str]
    this_section: SectionPlan
    fetched_data: dict[str, Any]        # keys: f"{ref}:{path}" (or just f"{ref}:" for full payloads)
    prior_section_summaries: list[PriorSection]

class PriorSection(BaseModel):
    section_id: str
    title: str
    summary: str                        # ≤200 words
    key_facts_for_threading: list[str] = Field(min_length=0, max_length=5)
```

### Output shape

Returned via a forced `submit_section` tool call so the runtime gets structured output.

```python
class SectionDraft(BaseModel):
    section_id: str
    blocks: list[Block]                 # ReportSchema-valid blocks (existing type)
    citations_used: list[str]           # citation ids referenced in this section
    word_count: int                     # actual count across all TextBlocks
    open_questions: list[str] = []      # things flagged for editor attention
```

### Tools available to subagents

**None.** Strict no-tools enforcement. The plan is the contract. If the subagent needs data not in `fetched_data`, it MUST emit an `open_questions` entry; the editor handles it.

### Quality guardrails (enforced by SubagentClient, with 1 re-prompt budget)

1. `SectionDraft.word_count` is within ±20% of `this_section.word_budget`
2. Every quantitative claim (numbers, dates, percentages) in TextBlock content references a citation id in `citations_used` (existing `find_uncited_concrete_claims` walker, promoted to error for subagents)
3. `blocks` validates against the strict `ReportSchema` block models (extra=forbid)

On failure: one re-prompt with structured error feedback. On second failure: section ships with whatever was produced + an `open_questions` entry flagging it.

### Failure handling

| Failure | Handling |
|---|---|
| Subagent re-prompt budget exhausted | Section ships with last produced output + `open_questions` flag |
| Subagent provider error | One retry; then section replaced with a 1-line `text` block "Section pending" and editor pass flagged |
| Empty `fetched_data` for a non-empty `data_paths` declaration | Run aborts before subagents start (eager-fetch failed); flagship plan is re-emitted |

---

## Section 3 — Orchestration

`SubagentReportRunner` in `packages/core/src/openlia/llm/runtime/subagent_runner.py`.

### Run flow

The runner is an `AsyncIterator[SseEvent]` matching the existing `ReportRunner.run` signature. Phases emit `ReportPhase` events the frontend already understands.

```python
async def run(self, *, department_id, user_id, request) -> AsyncIterator[SseEvent]:
    yield ReportStart(...)

    yield ReportPhase(phase="planning")
    plan = await self._plan(department_id, user_id, request)  # 1 repair on failure, else ReportError

    yield ReportPhase(phase="eager_fetch")
    fetched_data = await self._eager_fetch(plan)              # dispatch_many with dedupe

    yield ReportPhase(phase="section_drafting")
    drafts: list[SectionDraft] = []
    prior_summaries: list[PriorSection] = []
    for section in plan.sections:
        request_obj = self._build_subagent_request(plan, section, fetched_data, prior_summaries)
        draft = await self._subagent.draft(request_obj)
        yield ReportSectionComplete(section_id=section.section_id, blocks=draft.blocks)
        drafts.append(draft)
        prior_summaries.append(self._summarize(draft))

    yield ReportPhase(phase="editing")
    final_payload = await self._editor.compose(plan, drafts, fetched_data)

    final_payload = _finalize_submit_payload(final_payload, ...)  # reused
    validated = validate_report_payload(final_payload)            # reused

    yield ReportComplete(report_id=report_id, schema=final_payload)
```

### Eager-fetch dedup

Walks every `SectionPlan.data_paths` and builds a deduped list of `(tool_name, frozenset(tool_arguments.items()))` keys. Each unique tool call dispatches once via `ToolDispatcher.dispatch_many`. Resulting refs are stored, and per-path slices are pre-computed for each `DataPath` so subagents receive resolved values.

Direct fix for the duplicate-read pattern from `r_f03c92dd8c30`.

### Prior-section summarizer

`packages/core/src/openlia/llm/runtime/prior_section_summarizer.py`. **Deterministic, no LLM.** Walks the SectionDraft's blocks:

- TextBlock content → strip-then-truncate to 200 words
- MetricCardsBlock → 5 bullets of `(label, value)`
- TableBlock → first row's keys + 1 representative row's values
- Chart blocks → 1 bullet per chart (title only)
- Other blocks → 1 bullet of `(type, summary)` if applicable

Output: `PriorSection(summary, key_facts_for_threading)`.

### Plan-failure escape

If plan validation fails twice (initial + 1 repair), the runner emits `ReportError` and aborts. No fallback to the classic `ReportRunner`. Abort is more honest than silent degradation; surfaces plan-quality issues for prompt tuning.

### Eager-fetch dispatch

Parallel via the existing `ToolDispatcher.dispatch_many`. EODHD rate-limiting is per-key; the dispatcher already handles backpressure.

### Section completion events

Emit `ReportSectionComplete` as each subagent returns (progressive UI streaming). The final edited `ReportComplete` event carries the editor's final ReportSchema. **Verify during implementation:** confirm the frontend either replaces section content on `ReportComplete` or that a pre-edit/post-edit visual diff is acceptable. If neither, hold `ReportSectionComplete` events until after editing.

### What stays the same

- All SSE event types
- `_finalize_submit_payload` (citation normalization + meta_stats)
- `validate_report_payload`, `enforce_required_rail`, `normalize_report`, `find_uncited_concrete_claims`
- All frontend report-rendering components

---

## Section 4 — Editor pass

`EditorClient` in `packages/core/src/openlia/llm/runtime/editor_client.py`. Flagship model. Forced `submit_report` tool call. Single source of the final `ReportSchema`.

### Responsibilities (priority order)

1. **Narrative threading** — weave `cross_section_themes` through TextBlocks; add explicit cross-section references ("as covered in §3").
2. **Address open_questions** — every accumulated `open_questions` entry either resolved (by quoting another section's data) or surfaced as "we don't have data on X" — never silently dropped.
3. **Depth rebalancing** — expand underweight sections (`word_count < 0.8 × word_budget`), trim bloated ones.
4. **Accuracy spot-check** — cross-check quantitative TextBlock claims against the section's MetricCards/Tables and the editor's view of `fetched_data`. Fix mismatches.
5. **Compose Cover** — `cover.title`, `cover.subtitle`, `cover.tagline`, `cover.tldr`, `cover.key_metrics` written here. Subagents do not write cover.
6. **Build Rail** — `verdict`, `quick_stats`, optional sparkline. Pulled from section data.

### Input shape

```python
class EditorRequest(BaseModel):
    # Cacheable prefix:
    role_prompt: str                    # "You are the chief editor. Produce the final ReportSchema. ..."
    style_guide: str                    # mode-specific
    schema_strictness: str              # the existing report_schema_strictness guide

    # Per-report:
    company_thesis: str
    cross_section_themes: list[str]
    section_drafts: list[SectionDraft]  # subagent outputs verbatim
    open_questions: list[OpenQuestion]  # (section_id, question) tuples
    framework_cover_instructions: str   # mode-specific cover.* field guidance
```

### Output

The editor's `submit_report` tool-call arguments ARE the final `submit_report` payload. Same payload contract used today. Same `_finalize_submit_payload` runs on the output (citation normalize → merge provider citations → stamp meta_stats).

### Tools available to editor

**None.** Same lock-down as subagents. The editor reasons over what's given.

### Repair budget

One re-prompt on `submit_report` validation failure (existing pattern). On second failure: existing `_apply_coercion_fallback` runs and `report.warning.coercion_applied` is emitted.

### Cost budget (soft target)

≤$0.20. If empirics show drift, v2 compresses subagent drafts into a flatter intermediate representation before the editor sees them.

---

## Section 5 — Model role configuration

### Two role keys per (department, user)

Today's resolver: `(department_id, user_id) → ResolvedModel`.
New resolver: `(department_id, user_id, role) → ResolvedModel` where `role ∈ {"flagship", "subagent"}`.

### Resolver fallback rules

```python
def resolve(*, department_id, user_id, role="flagship", model_id_override=None):
    if model_id_override:
        return _resolve_model_id(model_id_override)
    pick = user_prefs.get(department_id=department_id, user_id=user_id, role=role)
    if pick:
        return _resolve_model_id(pick)
    server_default = SERVER_ROLE_DEFAULTS.get((department_id, role))
    if server_default:
        return _resolve_model_id(server_default)
    if role == "subagent":
        emit("report.warning.subagent_unconfigured",
             "Subagent model not configured; falling back to flagship.")
        return resolve(department_id=department_id, user_id=user_id, role="flagship")
    raise ModelNotConfiguredError(department_id)
```

### Admin UI surface

In the existing Models settings page, each report department gets two model dropdowns side-by-side:

```
Equity Research
  Flagship model:  [ user-configured model dropdown ▾ ]
  Subagent model:  [ user-configured model dropdown ▾ ]
```

Both dropdowns list ALL models from providers the user has configured credentials for. No recommended pairings, no provider opinions, no hardcoded defaults — pure user choice.

An OpenAI-only user sees OpenAI options in both slots; an Anthropic-only user sees Anthropic options; mixed users see everything. A user who wants maximum quality may pick the same flagship for both; a user who wants minimum cost picks the cheapest available for subagent.

### Setup wizard impact

The Models step in the existing setup wizard asks for both flagship and subagent at install time when the subagent runner is enabled. Soft-fallback covers users who upgrade without picking a subagent.

### Database / API

- Migration: add `role TEXT NOT NULL DEFAULT 'flagship'` to the existing `user_prefs.report_model` table (or equivalent existing structure)
- API: extend the Models admin route to accept/return the `role` field; backward-compatible for callers that omit it (treated as `flagship`)

---

## Configuration surfaces

| Env var | Default | Purpose |
|---|---|---|
| `OPENLIA_USE_SUBAGENT_RUNNER` | `0` | Master flag — when 1, equity_research routes through new runner |
| `OPENLIA_DEFAULT_SUBAGENT_MODEL_ID` | (unset) | Server-wide fallback when no user prefs pick |
| `OPENLIA_SUBAGENT_REPROMPT_BUDGET` | `1` | Per-subagent re-prompt budget |
| `OPENLIA_EDITOR_MAX_OUTPUT_TOKENS` | `8192` | Cap on editor output |
| `OPENLIA_PLAN_REPAIR_TURNS` | `1` | Plan repair budget |

All tunable without code change.

---

## File layout

### New files

```
packages/core/src/openlia/llm/runtime/
  subagent_runner.py
  subagent_client.py
  editor_client.py
  plan_schema.py
  section_draft.py
  prior_section_summarizer.py

packages/core/src/openlia/prompts/
  shared/section_subagent_role.yaml.j2
  shared/editor_role.yaml.j2

packages/core/src/openlia/prompts/equity_research.yaml
  (new slot: report.subagent_planning — the system content used during the plan phase)

packages/core/tests/test_llm/test_runtime/
  test_plan_schema.py
  test_prior_section_summarizer.py
  test_subagent_client.py
  test_editor_client.py
  test_subagent_runner.py
```

### Modified files

- `packages/server/src/openlia_server/services/runtime.py` — route equity_research reports through `SubagentReportRunner` behind `OPENLIA_USE_SUBAGENT_RUNNER`
- `packages/core/src/openlia/llm/runtime/__init__.py` — export the new runner
- `packages/core/src/openlia/llm/resolver.py` — accept `role` parameter
- `packages/server/src/openlia_server/db/migrations/` — add `role` to user prefs table
- `packages/server/src/openlia_server/routes/` — Models admin route accepts/returns `role`
- `frontend/src/pages/settings/` (or equivalent) — render two dropdowns per report department
- `frontend/src/pages/setup/` (or equivalent) — wizard Models step extension

### Untouched

- Existing `ReportRunner` (classic) stays as the default path
- `_finalize_submit_payload`, `validate_report_payload`, `enforce_required_rail`, `normalize_report`, `find_uncited_concrete_claims`
- All other report departments (morning_briefing, earnings_update, etc.) continue using the classic runner
- All SSE event types
- Frontend report rendering

---

## Test plan (vertical slices, TDD)

| # | Slice | RED test |
|---|---|---|
| 1 | `plan_schema` validation | construct + validate; reject missing `narrative_goal`; reject duplicate `section_id`; reject `word_budget` out of range |
| 2 | `prior_section_summarizer` | feed a TextBlock + Table + Chart; assert word_count ≤200 |
| 3 | Resolver `role` parameter | resolve with role="subagent" returns a different model than role="flagship" when both are configured |
| 4 | Resolver soft fallback | when subagent role is unconfigured, returns flagship + emits warning event |
| 5 | `eager_fetch` dedup | feed a plan with 2 sections sharing a tool call; assert dispatcher called once |
| 6 | `subagent_client` no-tools | build a request, run through fake provider, assert `tools=None` in `LLMRequest` |
| 7 | `subagent_client` 1 re-prompt | fake returns invalid blocks turn 0, valid turn 1; assert one re-prompt + accept |
| 8 | `subagent_client` word_budget enforcement | fake returns underweight, then balanced; assert acceptance after 1 re-prompt |
| 9 | `subagent_client` uncited-claim enforcement | fake returns text with numbers but empty citations_used; assert re-prompt |
| 10 | `editor_client` final ReportSchema | fake editor returns valid payload; assert ReportSchema validates |
| 11 | `editor_client` 1 re-prompt + coercion fallback | fake fails twice; assert coercion runs and warning emits |
| 12 | `subagent_runner` happy path | full plan → 14 subagents → editor → ReportComplete |
| 13 | `subagent_runner` plan-invalid aborts | fake flagship returns malformed plan twice; assert `ReportError` |
| 14 | `subagent_runner` records `cached_input_tokens` | assert dev-event payload carries it for every LLM call across all phases |
| 15 | `subagent_runner` matches event contract | same SSE event sequence (modulo phase names) as `ReportRunner` for a 1-section report |

---

## Rollout plan

| Phase | Trigger | Action |
|---|---|---|
| v1 ship | This branch merges to main | Flag `OPENLIA_USE_SUBAGENT_RUNNER` defaults OFF. Existing behavior unchanged. |
| Validation | 3-5 live runs with flag ON for the author | Confirm cost ≤$0.50 and quality improvements visible in side-by-side comparison |
| Soft launch | Validation passes | Flip default ON for equity_research; document the new model-role pickers in the changelog |
| Expansion | Soft launch stable for a week | Consider extending to other report departments (earnings_update, morning_briefing) |
| v2 features | After expansion | Parallel subagent dispatch, per-section model overrides, editor `read_payload` escape, plan caching across reports |

---

## Open questions

None. All design decisions are locked. Implementation plan to follow via the writing-plans skill.

---

## Acceptance criteria (v1)

- [ ] `OPENLIA_USE_SUBAGENT_RUNNER=1` routes equity_research stock_initiation reports through `SubagentReportRunner` end-to-end
- [ ] A standard 14-section report generated with the flag ON has `meta_stats.tokens_used` and `cached_input_tokens` in dev events showing total cost ≤$0.50 at the user's configured pricing
- [ ] Spot-check of 3 live reports shows: no "data not available" placeholders for data the plan declared, narrative threading present across sections, even section depth (no section ≤50% of plan word_budget)
- [ ] All 15 tests in the test plan pass
- [ ] Existing `test_report.py` failures unchanged (no new regressions)
- [ ] Flag OFF: every existing report path generates identically to pre-merge (backward compat)
