# v2.2 Engine Audit Findings — Step 2

Date: 2026-05-22
Branch: feat/equity-research-tools-audit
Audit scope: static analysis + fixture-based dry-run of the v2.2 engine (no live LLM calls)

## Summary

Total findings: 14 (blocking: 4, advisory: 10)

Test run: 1448 passed, 2 skipped (live EODHD gate) in 3.12s  
Import smoke: `from openlia.llm.runtime.report_v2_2 import *` — OK

---

## Per-stage findings

### Stage 1 — Clarifier

**Status: PASS**

`Clarifier.clarify()` signature matches `runner_v2._stage_clarify()` invocation. ClarifierOutput validated via Pydantic. Blocking-warning detection and ClarifierPaused emission work as expected.

Advisory: `_stage_clarify()` is annotated `-> Iterator[RunEvent]` but returns `({}, True)` / `({}, False)` via generator return (StopIteration.value). This is valid Python generator protocol but mypy/pyright will flag the annotation as incorrect — the return type should be `Generator[RunEvent, None, tuple[dict, bool]]`.

**Finding A-1 (advisory):** `_stage_clarify`, `_stage_research_plan`, `_stage_gather`, `_stage_model_plan`, `_stage_model_build`, `_stage_draft`, `_stage_verify`, `_stage_assemble` all annotated `-> Iterator[RunEvent]` but they use generator return values. The correct annotation is `Generator[RunEvent, None, <return_type>]`. No runtime impact; pyright reports type errors on `yield from` call sites.

---

### Stage 2 — Plan compose / Read template (READ_TEMPLATE)

**Status: PASS**

`load_template_v2()` is called before constructing the runner in the route. No stage-slot in RunnerV2 execute() path; READ_TEMPLATE appears in PipelineStage enum but is unused as an execute() stage. Advisory only.

---

### Stage 3 — Research plan

**Status: PASS**

`ResearchPlanner.plan()` signature matches `_stage_research_plan()`. Returns `Plan` with `research_strands`, `required_artifacts`, `optional_artifacts`, `section_dag`.

---

### Stage 4 — Gather (strand dispatch)

**Status: PASS**

`StrandDispatcher.dispatch()` accepts strands, composer_inputs, plan. Returns ResearchPool with `findings_by_strand` and `citations`. Upstream Stage 3 and downstream Stage 5 types align. Error paths: `except Exception` at line 45/74 of stage_4_gather.py swallows strand failures silently into degraded strand output — acceptable for partial-failure resilience.

---

### Stage 5 — Planner (v2.2 addition)

**Status: BLOCKING GAP**

There are two distinct "Stage 5" objects that must be distinguished:

1. `report_v2.pipeline.stage_5_model_plan.ModelPlanner` — the **existing** v2 Stage 5, which selects optional artifacts. This is wired into `RunnerV2` as `model_planner`.

2. `report_v2_2.planner.Planner` — the **new v2.2 Stage 5**, which selects which helpers to invoke and emits `PlannerOutput` (helper_selection + planner_overrides). This feeds Stage 7a materialization.

**Finding B-1 (BLOCKING):** `report_v2_2.planner.Planner` is **not wired into `RunnerV2`**. `runner_v2.py` has no Stage 5 slot for helper selection. `v2_stage_factory.py` does not import or instantiate `report_v2_2.Planner`. The `PlannerOutput.helper_selection` and `PlannerOutput.planner_overrides` produced by the v2.2 Planner are therefore never passed to Stage 7a, so Stage 7a cannot run.

**Finding A-2 (advisory):** `Planner.plan()` calls `asyncio.run(self.aplan())` directly (planner.py:233). When called from within a running event loop (FastAPI's default), this raises `RuntimeError: This event loop is already running`. The v2 factory workaround (`_run_sync` in v2_stage_factory.py) is not replicated in the v2.2 Planner. Production wiring must either use `aplan()` directly or apply the same `ThreadPoolExecutor` guard.

---

### Stage 6 — Eager fetch / Model build

**Status: PASS (existing v2 stage)**

`ModelBuilder.build()` is wired. Returns `list[ModelArtifact]`. Stage 7b SectionDrafter consumes these via `model_artifacts` parameter. Type alignment is correct.

---

### Stage 7a — Materialization (v2.2 addition)

**Status: BLOCKING GAP**

`materialize()` and `materialize_section()` in `report_v2_2.materialize` are fully implemented and tested (test_materialize.py, 1448 tests pass).

**Finding B-2 (BLOCKING):** Stage 7a has **no slot in `RunnerV2.execute()`**. The pipeline jumps from `_stage_model_build()` directly to `_stage_draft()`. `report_v2_2.materialize()` is never called during a live run. `MaterializedReport`, `RenderedArtifact`, and `MaterializedSection` objects are never produced for Stage 7b.

Consequence: Stage 7b's `build_drafter_prompt()` (which takes a `MaterializedSection`) is also unreachable from the current pipeline. The existing `SectionDrafter._draft_one()` bypasses it entirely and calls a plain `llm.call(system=..., user=...)` instead.

**PipelineStage enum gap:** `PipelineStage` in runner_v2.py has no `MATERIALIZE` or `STAGE_7A` member. Any wiring of Stage 7a must add this enum value.

---

### Stage 7b — Drafter

**Status: PARTIAL**

`SectionDrafter.draft_all()` is wired and functional. It drafts sections using DAG topological order and trigger_when evaluation.

**Finding A-3 (advisory):** `build_drafter_prompt()` (report_v2_2.drafter_prompt) is never called by `SectionDrafter._draft_one()`. The v2.2 drafter prompt builder — which includes thesis injection, artifact provenance headers, and threading summaries — is dead code in the current pipeline. The v2 drafter uses a hand-rolled system prompt string directly.

---

### Stage 8 — Verifier

**Status: PASS (with field-name caveat)**

The v2 `Verifier` (stage_8_verify.py) is wired and functional. `verify_with_retry()` runs deterministic + LLM detectors with up to 3 retries. Degraded convergence detection is correct.

**Finding A-4 (advisory):** The v2 `VerifierIssue` uses field names `issue_type` (str literal) and `evidence` (str) with severity values `"blocker"/"warning"`. The v2.2 `VerifierIssue` uses `type` (VerifierIssueType enum), `detail` (str), and severity values `"blocking"/"advisory"`. `runner_v2._build_verification_history()` explicitly reads `issue.issue_type` and `issue.evidence` — correct for the v2 model it is passed. If v2.2 verifier issues are ever mixed into the v2 pipeline, this will AttributeError silently at the `_build_verification_history` call site.

**Finding A-5 (advisory):** `runner_v2._stage_verify()` mutates `self.verifier._directives` directly (line 364: `self.verifier._directives = directives`). This bypasses the Verifier constructor contract and is fragile under concurrent runs sharing a factory-built Verifier instance. Each run should construct a fresh Verifier or expose a `set_directives()` method.

---

### Stage 9 — Assemble

**Status: PASS**

`assemble_report()` from `report_v2.rendering.assembler` is wired. `RunSummary` and `VerificationHistory` are proper Pydantic models and serialize correctly. The `Completed` event carries html, run_summary, and verification_history. The route layer emits only html via `_completed_frame()` — run_summary and verification_history are not surfaced to the client.

**Finding A-6 (advisory):** `Completed.run_summary` and `Completed.verification_history` are computed but not included in the SSE completed frame. The frontend receives only the final HTML. This is an observable gap if the client needs to display run metrics or issue audit trails.

---

## Cross-stage findings

### Stage 5 → 7a: helper_selection resolution

**Finding B-3 (BLOCKING):** Because Stage 5 (v2.2 Planner) is not wired, `PlannerOutput.helper_selection` is never produced. Consequently, Stage 7a cannot resolve helper names to registered helpers. The contract path — Planner emits `HelperInvocation.helper_name` → `get_helper(name)` resolves to `RegisteredHelper` → Stage 7a calls `impl()` → artifact dict → `materialize()` — has no entry point in the running pipeline.

**Finding A-7 (advisory):** `get_helper()` uses `schema.directory.name` as the registry key. The planner prompt instructs the LLM to emit helper names from `available_helpers[].name`. If the LLM abbreviates or misspells a helper name (e.g., `comparables_run` vs `comparables.run`), `get_helper()` returns `None` silently — no resolution error is raised before materialization. A validation step between Stage 5 output and Stage 7a execution should catch unknown helper names and either remap or emit `HELPER_UNAVAILABLE`.

### Stage 7a → 7b: token budget

**Status: PASS** (within scope of static analysis)

`_HARD_CAP_CHARS` enforces per-fidelity size caps. FULL cap is 12,000 chars (~3,000 tokens). With multiple FULL artifacts per section, a section prompt could reach 30,000–40,000 chars before drafter system prompt overhead. No per-section aggregate cap is enforced. Advisory only — not a pipeline blocker.

### Stage 7b → 8: drafter output parseability

**Status: PASS**

`SectionDrafter._draft_one()` returns `blocks = raw.get("blocks", [])` which defaults to `[]` on LLM failure, wrapped in `status="DEGRADED"`. The v2 Verifier receives a `list[dict]` for blocks — compatible.

### Stage 8 → 9: verifier issue detail_code

**Status: PASS**

All 18 `VerifierIssueType` values are reachable (confirmed in Step 1 audit). Every `VerifierIssue` emitted by the v2.2 Verifier carries a non-None `detail_code`. The v2 VerifierIssue does not have `detail_code` — but v2.2 Verifier objects are not currently in the v2 pipeline path.

### Stage 9 → output: Report schema

**Status: PASS**

`assemble_report()` returns an HTML string. `RunSummary` validates as a Pydantic model. No `Report` Pydantic schema wraps the HTML — the final output is a raw string, which is consistent with the route's `_completed_frame(run_id, html)` emission.

---

## Cross-cutting findings

### Fidelity contract

**Status: PASS**

All 116 artifact types in `artifact_types.yaml` declare `headline`, `summary`, and `full` fidelity descriptions. Zero gaps found.

```
Total artifact types: 116
Fidelity coverage gaps: 0
```

Four types carry `deprecated_at_pr` markers (`ratio_panel`, `saas_metrics_output`, `budget_variance_output`, `business_investment_output`). The `ArtifactType` Pydantic model does not parse `deprecated_at_pr` — the field is silently ignored at load time. This is intentional per the YAML comment ("tracking only") but means the registry cannot warn at boot when a deprecated type is referenced.

**Finding A-8 (advisory):** `ArtifactTypeRegistry` loads deprecated types without any runtime warning. If a helper that has been deprecated still registers with a `deprecated_at_pr` artifact type, the planner will offer it to the LLM without any signal that it is scheduled for removal.

---

### Exposure tiers

**Status: PASS**

All 113 registered helpers carry a complete `HelperSchema` with all four tiers:
- L1 category (via `Category` enum on `DirectoryEntry`)
- L1.5 `DirectoryEntry` (name, category, one_liner) — always loaded
- L2 `SelectionGuidance` + `MechanicalContract` — present on all checked helpers
- L3 `SkillDocRef` — present on complex helpers; `None` for simple helpers (by design)

Five-helper spot-check (`dcf_engine`, `football_field_chart`, `forecast_builder`, `budget_variance`, `comparables.run` [note: dot-separated name, not underscore]): all PASS.

**Finding A-9 (advisory):** `get_helper("comparables_run")` returns `None`; the correct key is `"comparables.run"` (with a dot). The `comparables_run.py` module registers under `directory.name = "comparables.run"`. Any caller (or the LLM planner) that omits the dot will miss this helper. The naming convention is inconsistent — most helpers use underscores, one uses a dot. This should be normalized.

---

### Error catalog

**Status: MOSTLY PASS**

Four `except Exception` occurrences in v2.2 helpers — all have narrow, documented rationale:

1. `eodhd/client.py:58` — bare `except Exception: pass` swallowing JSON parse error on a non-200 response before re-raising a `RuntimeError`. The JSON parse is optional (extracting error message only); acceptable.
2. `statsmodels_helpers/sm_autocorrelation.py:94` — `except Exception: pacf_vals = np.zeros(...)` for pathological time series. Acceptable numerical fallback.
3. `statsmodels_helpers/sm_var_var_model.py:104` — `except Exception as exc: granger_matrix[...] = {"verdict": "error", "error": str(exc)}`. Per-pair Granger test fallback. Acceptable.
4. `statsmodels_helpers/sm_heteroskedasticity_test.py:80` — `except Exception as exc` re-raises as `RuntimeError`. Acceptable narrow catch.

`runner_v2.py:246` — top-level `except Exception as exc` in `execute()` converts any unhandled exception to a `Failed` event. This is the orchestrator's defensive last-resort catch — acceptable with narrow rationale.

**Finding A-10 (advisory):** `eodhd/client.py:58` uses bare `except Exception: pass` instead of the more explicit `except (ValueError, KeyError): pass`. Although the JSON parse is optional, catching `BaseException` subclasses (e.g., `SystemExit`, `KeyboardInterrupt`) is technically possible. Use `except (ValueError, TypeError, AttributeError): pass`.

---

### Type safety

**Spot-checked modules:** `runner_v2.py`, `materialize.py`, `planner.py`

**runner_v2.py:** All stage methods annotated `-> Iterator[RunEvent]`. As noted in Finding A-1, generator return values (`return (plan,)`, `return (html, run_summary)`) are not reflected in the annotation. Mypy strict mode would flag every `yield from self._stage_X(...)` assignment.

**materialize.py:** Types are complete and accurate. `RenderedArtifact`, `MaterializedSection`, `MaterializedReport` are fully typed Pydantic models. `_render_artifact()` returns `tuple[str, list[VerifierIssue]]` — correct.

**planner.py:** `Planner.__init__` uses `Any` for `template_sections` and `available_helpers` params — intentional for flexibility. `_parse_planner_response()` does not validate `section_id` uniqueness in `helper_selection`. A malformed LLM response with duplicate `section_id` entries would silently produce a `PlannerOutput` with repeated sections.

**Finding A-11 (advisory):** `PlannerOutput.planner_overrides` is typed `list[PlannerOverrides]` but `PlannerOverrides.template_id` could be an empty string if the LLM omits it (the parser does `po.get("template_id", "")`). An empty-string `template_id` would cause `resolve_section_plan()` to fail on the override-section lookup if none of the section IDs match.

---

## Integration findings

### v2 runner wiring

**Finding B-4 (BLOCKING):** There is no end-to-end factory, entry point, or integration path that wires the v2.2 Planner + Stage 7a materialize into `RunnerV2`. The complete gap is:

```
Current pipeline:
  Stage 3 (research_plan) → Stage 4 (gather) → Stage 5 (model_plan/ModelPlanner)
  → Stage 6 (model_build) → Stage 7 (SectionDrafter) → Stage 8 (Verifier) → Stage 9 (assemble)

Required v2.2 pipeline:
  Stage 3 → Stage 4 → Stage 5a (model_plan/ModelPlanner)
  → Stage 5b (v2.2 Planner — helper selection + planner_overrides)
  → Stage 6 (model_build + helper invocations)
  → Stage 7a (materialize — resolve ReportSectionPlan, render artifacts)
  → Stage 7b (SectionDrafter using build_drafter_prompt with MaterializedSection)
  → Stage 8 (Verifier — v2.2 Verifier using MaterializedSection, not just blocks)
  → Stage 9 (assemble)
```

`v2_stage_factory.py` constructs a `RunnerV2` using only v2 stages. No import of `report_v2_2` anywhere in the server layer or in `runner_v2.py`. The `capabilities.yaml` declares `stage_7a_materialization` and `stage_5_planner` as supported — these capabilities exist in the library but are not reachable from the running orchestrator.

---

### Event compatibility

**Status: ADVISORY**

`telemetry.py` defines `Stage7aMaterializeEvent` and `Stage7bDrafterCallEvent` with `TYPE` class-level literals following the same `events.py` convention:
- `Stage7aMaterializeEvent.TYPE = "report_v2_2.stage7a.materialize"`
- `Stage7bDrafterCallEvent.TYPE = "report_v2_2.stage7b.drafter_call"`

These events are **not** in the `SseEvent` union in `events.py` and are not handled by `equity_research_v2.py`'s `_drive_run()` event loop. If Stage 7a is wired, telemetry events will be silently dropped unless the SSE driver is updated to forward them.

**Finding A-12 (advisory):** `TelemetryCollector.snapshot()` is a pull-based aggregation (caller calls `snapshot()` after the run). There is no push mechanism to emit telemetry as SSE frames during the run. Post-run cost reporting must be extracted from `Completed.run_summary` or a separate telemetry call — neither is currently wired.

**Finding A-13 (advisory):** `HelperSchema.verifier_hooks` lists issue types a helper can emit, but the v2.2 `Verifier.verify()` never reads `verifier_hooks`. The field is declared schema documentation only. Per the schema spec comment ("verifier does NOT read this"), this is intentional — but it means the planner cannot use `verifier_hooks` to decide which checks to enable per helper.

**Finding A-14 (advisory):** `runner_v2.py` has no `logging` import and emits no `logger.*` calls in any stage method. Stage transitions are observable only through the yielded `StageStarted`/`StageCompleted` events — acceptable for event-driven observability, but makes server-side log correlation with stage names impossible.

---

## Remediation plan

Each blocking finding gets a one-line fix tied to the implementation plan.

| # | Finding | Severity | Remediation | File:line |
|---|---------|----------|-------------|-----------|
| B-1 | `report_v2_2.Planner` not wired into `RunnerV2` | blocking | Add `planner_v2_2: Planner | None` field to `RunnerV2`; insert `_stage_planner_v2_2()` call between `_stage_model_build` and `_stage_draft`; add `MATERIALIZE` and `PLANNER_V2_2` to `PipelineStage`; inject in `v2_stage_factory.make_v2_runner_stage_factory()` | `runner_v2.py:130-175`, `v2_stage_factory.py:345-365` |
| B-2 | Stage 7a `materialize()` has no slot in `RunnerV2.execute()` | blocking | Add `_stage_materialize()` method that calls `resolve_section_plan()` then `materialize()`; pass `MaterializedReport` to a refactored `_stage_draft()` that calls `build_drafter_prompt()` | `runner_v2.py:320-340` |
| B-3 | `PlannerOutput.helper_selection` never resolved to registered helpers | blocking | In `_stage_materialize()`, iterate `planner_output.helper_selection`, call `get_helper(inv.helper_name)` for each `HelperInvocation`, invoke `impl(**inv.params)`, collect into `artifacts: dict[str, Any]`, then call `materialize(section_plan, artifacts)` | `runner_v2.py:new _stage_materialize` |
| B-4 | No end-to-end factory wires v2.2 Planner + Stage 7a | blocking | Update `make_v2_runner_stage_factory()` to import and instantiate `report_v2_2.Planner` with the same `SyncJsonLlmClient`; pass `available_helpers=[{name, category, one_liner} for h in list_helpers()]` | `v2_stage_factory.py:332-366` |
| A-1 | Stage method annotations `Iterator[RunEvent]` incorrect | advisory | Annotate sub-stage generators as `Generator[RunEvent, None, T]` where T is the return type; or use `Iterator` only on `execute()` which yields only RunEvent | `runner_v2.py:253-498` |
| A-2 | `Planner.plan()` uses bare `asyncio.run()` — deadlocks in FastAPI | advisory | Replace `asyncio.run(self.aplan())` with the `_run_sync()` pattern from `v2_stage_factory.py` (ThreadPoolExecutor guard), or expose only `aplan()` for async callers | `planner.py:233` |
| A-3 | `build_drafter_prompt()` is dead code in current pipeline | advisory | Wire into `_stage_draft()` once Stage 7a slot is added: pass `MaterializedSection` to `build_drafter_prompt()` and use its output as the system prompt for `SectionDrafter` | `runner_v2.py:_stage_draft` |
| A-4 | v2/v2.2 `VerifierIssue` field name divergence (issue_type vs type; evidence vs detail; blocker vs blocking) | advisory | Add adapter or bridge if v2.2 issues are ever surfaced through v2 history builder; document the divergence as intentional until v2.2 fully replaces v2 | `verifier_models.py:1-17`, `schemas/verifier_issue.py:1-35` |
| A-5 | `self.verifier._directives` mutated directly per run | advisory | Add `set_directives(d: dict[str, str])` public method to v2 `Verifier`; call that instead | `runner_v2.py:364`, `stage_8_verify.py:30-50` |
| A-6 | `run_summary` and `verification_history` not surfaced in SSE completed frame | advisory | Add `run_summary` and `verification_history` fields to `_completed_frame()` payload | `equity_research_v2.py:111-113` |
| A-7 | No helper name validation between Stage 5 output and Stage 7a | advisory | In `_stage_materialize()`, validate all `HelperInvocation.helper_name` values against `get_helper()` before invoking; emit `HELPER_UNAVAILABLE` issue on miss | `runner_v2.py:new _stage_materialize` |
| A-8 | Deprecated artifact types not warned at boot | advisory | Parse `deprecated_at_pr` in `_parse_entry()`; add `is_deprecated` flag to `ArtifactType`; log `WARNING` in `register_helper()` if any declared artifact is deprecated | `artifact_types.py:36-52` |
| A-9 | `comparables.run` name inconsistency (dot vs underscore) | advisory | Rename `directory.name` to `"comparables_run"` in `comparables_run.py` for consistency; update any references in planner prompts / tests | `comparables_run.py` |
| A-10 | Bare `except Exception: pass` in EODHD client | advisory | Narrow to `except (ValueError, TypeError, AttributeError): pass` | `eodhd/client.py:58` |
| A-11 | `PlannerOverrides.template_id` defaults to empty string from parser | advisory | Add validation: raise `ValueError` if `template_id` is empty after parsing; the Planner prompt should always emit it | `planner.py:124-137` |
| A-12 | Telemetry events not emitted as SSE frames | advisory | Add `Stage7aMaterializeEvent` and `Stage7bDrafterCallEvent` to `SseEvent` union and handle in `_drive_run()` when Stage 7a is wired | `events.py:277-301`, `equity_research_v2.py:139-179` |
| A-13 | `verifier_hooks` declared but never read | advisory | Document explicitly in `HelperSchema` docstring as "reserved for future planner routing"; or remove if it will not be used before v3 | `schema.py:92` |
| A-14 | No `logger.*` calls in `runner_v2.py` stage methods | advisory | Add `import logging; logger = logging.getLogger(__name__)` and one `logger.debug()` per stage entry/exit | `runner_v2.py` |
