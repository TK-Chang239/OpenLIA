# Macro Research — Connector-Requirement Relaxation + Coverage Preflight (design spec)

- **Date:** 2026-06-04
- **Status:** Approved design, pending implementation plan
- **Scope:** Implements §9 of `macro-research-llm-dashboard-redesign.md`
  ("Provider-agnostic resolution"): relax the `macro_research` department's
  connector requirements and surface a coverage indicator. In practice this
  means **completing the MR de-runnerization** the dashboard redesign started.
- **Builds on:** `macro-research-llm-dashboard-redesign.md` (the `report_dash_mr`
  engine; §9). Touches the department registry, health derivation, the
  wizard/runtime runner plumbing, and the MR settings UI.

## 1. Problem

Spec §9 calls for: `WEB_SEARCH` required (the macro backbone), `FINANCIAL`
optional (quotes + whatever indicators it has), `NEWS` optional — plus a
"coverage preflight" indicator. Today `macro_research` requires **both**
`FINANCIAL` and `WEB_SEARCH` (`departments/macro_research.py`).

But relaxing the category list **alone is a no-op**, because of a second,
independent gate. `departments/health.py` disables a department when
`requires_runner=True` **and** any need in its `<dept>.needs.yaml` lacks a
resolved `RunnerCallableSpec` row. MR still carries `requires_runner=True` and an
11-entry `macro_research.needs.yaml` — **leftovers from the old tiered model**.
The live engine no longer uses them: `report_dash_mr` resolves data through the
connector **dispatcher** (`dispatcher.in_department("macro_research")` +
`web_search`, the EU/MB pattern) via `mr_dash_run_service`, and never reads
`RunnerCallableSpec`/`load_needs`. So MR is gated on resolving 11 dead needs that
nothing consumes.

Therefore "relax MR's requirements" necessarily means **de-runnering MR**:
flip `requires_runner=False`, retire the dead needs file, and update the handful
of places that still treat MR as runner-bearing. Only then does the category
relaxation take effect.

## 2. Goals / non-goals

**Goals**
- MR is **active on `WEB_SEARCH` alone**; `FINANCIAL` and `NEWS` are optional.
- Remove the phantom runner-need gate for MR (it is not a runner department).
- Surface an honest **coverage indicator** for the active-but-partial case: an
  MR user who has `WEB_SEARCH` but no `FINANCIAL`/`NEWS` sees which tiles run on
  degraded sourcing and what adding a connector would buy.
- **Behavior-preserving for the engine:** no change to `report_dash_mr`, the
  dispatcher, the run service, the payloads, or the per-tile degradation already
  in the engine.

**Non-goals**
- No change to the MR engine, dispatcher, run service, scheduler, or payloads.
- No new "coverage" backend endpoint or canary aggregation (the moderate hint
  reuses existing dept-health data — see §4). No DB migration.
- The "WEB_SEARCH missing → disabled" case needs no new UI: the existing
  `DeptDisabledBanner` already renders the disabled reason. The coverage hint is
  specifically for the **active** state.
- Retail Sentiment stays runner-bearing and untouched (it becomes the canonical
  runner-dept example where tests previously used MR).

## 3. Part A — De-runner MR + relax categories

### 3.1 Department definition (`departments/macro_research.py`)
```python
required_categories = (Category.WEB_SEARCH,)
optional_categories = (Category.FINANCIAL, Category.NEWS)
required_any_of = ()
requires_runner = False
```
Update the docstring comment block (lines ~26-34) to state: WEB_SEARCH is the
required macro backbone; FINANCIAL/NEWS are optional (the engine falls back to
`web_search` for any value a connector does not cover); MR is dashboard-routed,
not a runner department.

### 3.2 Retire the dead needs file
Delete `departments/macro_research.needs.yaml`. With `requires_runner=False`:
- `health.py`'s runner branch is skipped for MR (no `load_needs` call).
- `runner_specs_service._hydrate_registry_caches()` already filters on
  `requires_runner`, so the live wizard stops proposing MR runner specs
  automatically.
- Any previously-approved MR `RunnerCallableSpec` rows simply become unused —
  the health check and engine never read them. **No migration** (orphaned rows
  are harmless; deleting them is not required).

### 3.3 Health derivation (`departments/health.py`)
No code change required — the runner branch is gated on `dept.requires_runner`.
After 3.1, MR's health depends only on `WEB_SEARCH` being validated. (Part B adds
two fields to `DepartmentHealth`; see §4.)

### 3.4 Runtime mode picker (`services/runtime.py`)
`select_runtime_mode` keys off `requires_runner` and is **not on MR's path** (MR
refreshes through the scheduler → `mr_dash` executor → `mr_dash_run_service`,
never `run_department`). Update only the docstring (lines ~619-624) to drop MR
from the "runner depts" list, so the picker's documented contract stays honest.

### 3.5 Frontend runner-bearing list
`frontend/src/api/departments.ts`: remove `"macro_research"` from
`RUNNER_BEARING_DEPARTMENTS` (leaving `["retail_sentiment"]`). `ReviewStep.tsx`
maps that list, so the wizard stops rendering an MR resolve panel automatically.
`RUNNER_DEPARTMENT_LABELS` (a full per-slug map) is left as-is.

## 4. Part B — Coverage preflight (moderate hint)

### 4.1 Expose optional + satisfied categories from dept-health
The frontend already gets `required_categories` from the dept-health
serialization but cannot tell which **optional** categories exist or which
categories are **currently satisfied**. Add both, minimally and additively:

- `departments/health.py`: add `satisfied_categories: list[Category]` to the
  `DepartmentHealth` dataclass, populated from the `validated_cats` set the check
  already computes.
- `services/dept_health.py` `serialize()`: add `optional_categories` (read from
  the registry, like `required_categories`) and `satisfied_categories`.
- `frontend/src/api/dept-health.ts`: add `optional_categories?: string[]` and
  `satisfied_categories?: string[]` to the `DepartmentHealth` type (optional, for
  back-compat with existing fixtures).

This is the single source of truth for the hint — no connectors cross-reference,
no new endpoint.

### 4.2 MR coverage hint (`MRSettingsPanel.tsx`)
Add a small coverage section to the MR page's settings panel, driven by the MR
`DepartmentHealth` row (`fetchDeptHealth` filtered to `macro_research`). For each
MR category, render its state and an honest one-line note:

| category | role | satisfied | missing |
| --- | --- | --- | --- |
| `web_search` | required — macro backbone | "Web search active" | (MR is disabled; `DeptDisabledBanner` covers it) |
| `financial` | optional | "Live quotes + indicators active" | "No financial connector — quote/indicator tiles use web search or show source-unavailable. Add one in Settings → Connectors." |
| `news` | optional | "Headlines active" | "No news connector — narrative-context tiles use web search." |

Derive each category's state from `required_categories` / `optional_categories` /
`satisfied_categories`. A stable `data-testid` (`mr-coverage`) anchors the view
test. Keep the existing T-card visual idiom; tone the missing-optional notes as
informational (not error).

## 5. Behavior preservation

- The MR engine, dispatcher, `mr_dash_run_service`, scheduler, cache, and every
  payload are **unchanged**. When a `FINANCIAL` connector is configured, the
  dispatcher still exposes its tools to MR (scoped by `in_department`); when it
  is not, the LLM falls back to `web_search` and tiles degrade per the existing
  engine behavior.
- No API contract changes except the two **additive** dept-health fields (§4.1).
- No DB migration.

## 6. Testing / blast radius

**Core**
- `tests/departments/test_health.py` — update the MR cases: MR requires only
  `WEB_SEARCH`; MR is **active without `FINANCIAL`**; MR is **not** gated on
  runner needs (now `requires_runner=False`). Add/keep a case asserting MR
  disabled without `WEB_SEARCH`. Cover `satisfied_categories` population.
- `tests/departments/test_department_artifacts.py` — if it asserts every
  `requires_runner` dept has a needs.yaml (and vice versa), update for MR.

**Server**
- `tests/test_services/test_runtime_entry.py` — the
  `select_runtime_mode("macro_research") == "deterministic"` assertion switches to
  `retail_sentiment` (the remaining runner dept).
- `tests/test_dept_health.py` / `tests/test_dept_health_api.py` — update MR
  cases; assert the new serialized `optional_categories` / `satisfied_categories`.
- `tests/e2e/test_python_lib_runner_activation.py` — this exercises a runner dept
  going disabled→active by resolving needs; migrate its example from
  `macro_research` to `retail_sentiment`.
- `tests/e2e/test_wizard_happy_path.py` — drop `macro_research` from the
  `("macro_research", "retail_sentiment")` runner loop.
- The seeded resolver/proposal unit tests (`test_runner_specs_dept_service.py`,
  `test_routes_runner_specs_dept.py`, `test_resolver_save_flow.py`,
  `test_override_wins_upgrade.py`, `test_resolver_redesign_e2e.py`) use
  `set_dept_needs_for_testing({"macro_research": [...]})` with **synthetic** needs
  — they treat `"macro_research"` as a label and do **not** depend on MR's real
  `requires_runner` flag or needs file. **No change required.** (Verified.)

**Frontend**
- `api/departments.ts` — drop MR from `RUNNER_BEARING_DEPARTMENTS`; update any
  test asserting its contents.
- `setup/steps/__tests__/` (DeptResolvePanel, FirstRunSummary) and
  `components/sidebar/Sidebar.test.tsx` / `dept-health` store tests — update any
  that assume MR is runner-bearing.
- New: an `MRSettingsPanel` view test for the `mr-coverage` section (satisfied
  and missing-optional states).
- `dept-health.ts` type fields added (no behavior change).

**Verification commands** (server full suite hangs on SSE — run targeted dirs):
- `uv run ruff check . && uv run ruff format --check .`
- `uv run pytest packages/core/tests/departments packages/server/tests/test_services packages/server/tests/test_dept_health.py packages/server/tests/test_dept_health_api.py packages/server/tests/e2e -q`
- `cd frontend && npx tsc --noEmit && npx vitest run src/pages/departments/macro_research src/api src/setup src/components/sidebar`

## 7. Build order

1. **Core de-runner:** `macro_research.py` (categories + `requires_runner=False`
   + docstring); delete `macro_research.needs.yaml`; update `test_health.py` +
   `test_department_artifacts.py`. Verify core departments tests.
2. **Dept-health fields:** add `satisfied_categories` to `DepartmentHealth` +
   `serialize()` `optional_categories`/`satisfied_categories`; update
   `test_dept_health*`. Verify.
3. **Server runner-plumbing:** `runtime.py` docstring; migrate
   `test_runtime_entry.py` + the two e2e tests to `retail_sentiment`. Verify
   server targeted dirs.
4. **Frontend runner list + types:** `departments.ts`, `dept-health.ts`; fix
   affected frontend tests. `tsc` + targeted vitest.
5. **Frontend coverage hint:** `MRSettingsPanel.tsx` `mr-coverage` section +
   view test. `tsc` + vitest.
6. **Full verification:** ruff + targeted pytest + targeted vitest.

## 8. Decisions on record

- **Clean de-runner, not a hack** — MR is genuinely a dashboard department, not a
  runner; `requires_runner=False` + delete the dead needs file. The redesign
  started this; this spec finishes it. (Relaxing categories alone is a no-op.)
- **`retail_sentiment` becomes the canonical runner-dept example** in the tests
  and e2e that previously used MR. The seeded resolver unit tests are unaffected
  (synthetic `"macro_research"` label).
- **Moderate coverage hint, reusing dept-health** — add two additive fields
  (`optional_categories`, `satisfied_categories`); render an MR-specific coverage
  section in `MRSettingsPanel`. No new endpoint, no canary aggregation.
- **No migration** — orphaned MR `RunnerCallableSpec` rows are harmless.
- **Engine untouched** — per-tile degradation already exists; this is gating +
  a hint only.
