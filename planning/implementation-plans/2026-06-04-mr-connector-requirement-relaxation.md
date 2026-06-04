# MR Connector-Requirement Relaxation + Coverage Preflight — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Macro Research active on `WEB_SEARCH` alone (FINANCIAL/NEWS optional) by completing its de-runnerization, and surface an honest source-coverage hint — without touching the MR engine.

**Architecture:** Flip `macro_research` to `requires_runner=False` + relax its categories; delete the dead `macro_research.needs.yaml`; migrate the tests that used MR as the canonical runner-dept example to `retail_sentiment`. Add two additive dept-health fields (`optional_categories`, `satisfied_categories`) and render an `mr-coverage` section in `MRSettingsPanel` from them.

**Tech Stack:** Python 3, `uv`, `ruff`, `pytest`; React/TS, `npx tsc`, `npx vitest`. Reference: design spec `planning/specs/systems/macro-research-connector-requirement-relaxation-design.md`.

**Environment notes:** Run Python via `uv run` (if a `~/.cache/uv` "Operation not permitted" sandbox error appears, retry that command with the Bash tool's `dangerouslyDisableSandbox: true`). The full `packages/server` pytest suite hangs on SSE — run only the targeted dirs given here. Run `npx tsc`/`npx vitest` from `frontend/`.

---

## File Structure

- **Modify** `packages/core/src/openlia/departments/macro_research.py` — categories + `requires_runner=False` + comment.
- **Delete** `packages/core/src/openlia/departments/macro_research.needs.yaml`.
- **Modify** `packages/core/src/openlia/departments/health.py` — add `satisfied_categories` to `DepartmentHealth` + populate it.
- **Modify** `packages/server/src/openlia_server/services/dept_health.py` — `serialize()` emits `optional_categories` + `satisfied_categories`.
- **Modify** `packages/server/src/openlia_server/services/runtime.py` — `select_runtime_mode` docstring only.
- **Modify** `frontend/src/api/departments.ts` — drop MR from `RUNNER_BEARING_DEPARTMENTS`.
- **Modify** `frontend/src/api/dept-health.ts` — add two optional type fields.
- **Modify** `frontend/src/pages/departments/macro_research/MRSettingsPanel.tsx` — `mr-coverage` section.
- **Tests:** `test_health.py`, `test_department_artifacts.py`, `test_dept_health.py`, `test_runtime_entry.py`, `e2e/test_python_lib_runner_activation.py`, `e2e/test_wizard_happy_path.py`, MRSettingsPanel view test, plus any frontend runner-bearing test fixups.

---

## Task 1: Core de-runner + needs retirement

**Files:**
- Modify: `packages/core/src/openlia/departments/macro_research.py`
- Delete: `packages/core/src/openlia/departments/macro_research.needs.yaml`
- Modify: `packages/core/tests/departments/test_health.py`
- Modify: `packages/core/tests/departments/test_department_artifacts.py`

- [ ] **Step 1: Relax categories + flip `requires_runner` in `macro_research.py`**

Replace the comment block + the three category class-vars + `requires_runner` (currently lines ~26-39) with:
```python
    # Connector dependencies (spec §9). WEB_SEARCH is the required macro
    # backbone; the engine falls back to native web_search for any value a
    # connector does not cover. FINANCIAL (live quotes + whatever indicators it
    # exposes) and NEWS are optional. MR is dashboard-routed (report_dash_mr via
    # the connector dispatcher), NOT a runner department.
    required_categories: ClassVar[tuple[Category, ...]] = (Category.WEB_SEARCH,)
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.FINANCIAL,
        Category.NEWS,
    )
    required_any_of: ClassVar[tuple[tuple[Category, ...], ...]] = ()

    # Runtime behavior: dashboard engine, no deterministic runner / needs.
    requires_runner: ClassVar[bool] = False
    disable_runtime_routing: ClassVar[bool] = False
```

- [ ] **Step 2: Delete the dead needs file**

```bash
git rm packages/core/src/openlia/departments/macro_research.needs.yaml
```

- [ ] **Step 3: Migrate the MR runner block in `test_health.py` to Retail Sentiment**

Replace the entire "Runner-bearing dept (Macro Research)" block — the comment header plus the four tests `test_runner_dept_disabled_with_unresolved_need`, `test_runner_dept_active_when_all_needs_resolved`, `test_runner_dept_specs_for_other_dept_do_not_count`, `test_runner_dept_disabled_lists_both_missing_categories_and_unresolved_needs` (currently lines ~82-135) — with this Retail-Sentiment version (drops the now-redundant "active" test, which the existing `test_runner_dept_rs_active_...` already covers):

```python
# ---------------------------------------------------------------------------
# Runner-bearing dept (Retail Sentiment) — requires_runner=True with needs
# ---------------------------------------------------------------------------


def test_runner_dept_disabled_with_unresolved_need():
    dept = RetailSentimentDepartment()
    needs = load_needs(dept.name)
    assert needs, "RetailSentiment needs.yaml must declare at least one need"

    connectors = [
        _Conn(category=cat, status=ConnectorStatus.VALIDATED) for cat in dept.required_categories
    ]
    # Resolve all but the first need.
    specs = [_Spec(department_id=dept.name, need_id=n.id) for n in needs[1:]]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "disabled"
    assert health.unresolved_needs == [needs[0].id]
    assert needs[0].id in health.reason


def test_runner_dept_specs_for_other_dept_do_not_count():
    dept = RetailSentimentDepartment()
    needs = load_needs(dept.name)
    connectors = [
        _Conn(category=cat, status=ConnectorStatus.VALIDATED) for cat in dept.required_categories
    ]
    # Specs reference a different dept — must not satisfy RS needs.
    specs = [_Spec(department_id="macro_research", need_id=n.id) for n in needs]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "disabled"
    assert health.unresolved_needs == [n.id for n in needs]


def test_runner_dept_disabled_lists_both_missing_categories_and_unresolved_needs():
    dept = RetailSentimentDepartment()
    needs = load_needs(dept.name)
    health = check_dept_health(dept, validated_connectors=[], runner_specs=[])
    assert health.status == "disabled"
    assert Category.FINANCIAL in health.missing_categories
    assert health.unresolved_needs == [n.id for n in needs]
    assert "Missing required categories" in health.reason
    assert "Unresolved needs" in health.reason
```

- [ ] **Step 4: Rewrite the two MR category tests in `test_health.py`**

Replace `test_macro_research_requires_financial_and_web_search` (currently lines ~217-220) and `test_macro_research_disabled_without_web_search_connector` (currently lines ~257-264) with:
```python
def test_macro_research_requires_only_web_search():
    dept = MacroResearchDepartment()
    assert dept.required_categories == (Category.WEB_SEARCH,)
    assert Category.FINANCIAL in dept.optional_categories
    assert Category.NEWS in dept.optional_categories
    assert dept.requires_runner is False


def test_macro_research_active_with_web_search_only():
    dept = MacroResearchDepartment()
    connectors = [_Conn(category=Category.WEB_SEARCH, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"
    assert health.unresolved_needs == []


def test_macro_research_disabled_without_web_search_connector():
    dept = MacroResearchDepartment()
    # FINANCIAL alone is no longer enough — WEB_SEARCH is the one required category.
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "disabled"
    assert Category.WEB_SEARCH in health.missing_categories
```
(`load_needs` is still imported/used by the Retail-Sentiment tests, so leave the import.)

- [ ] **Step 5: Drop the MR branch from the drift helper in `test_department_artifacts.py`**

MR no longer has runner code/needs. In `_runner_need_ids_for` remove the `macro_research` branch (currently lines ~70-78), leaving only the `retail_sentiment` branch and the trailing `return set()`. Then remove the now-unused helper `_t1_requirement_to_need_id` (currently ~lines 45-59) and the now-unused `from openlia.macro_research.dashboards import DASHBOARDS` import (line ~14). The parametrized `test_needs_yaml_present_when_runner_required` will now assert MR has **no** needs.yaml (correct after Step 2), and the drift tests early-return for MR (empty referenced/declared).

- [ ] **Step 6: Verify core**

Run: `uv run pytest packages/core/tests/departments -q`
Expected: PASS. If `test_department_artifacts` still fails for MR, re-check Step 5 (a leftover MR reference in the drift helper or a dangling import).

- [ ] **Step 7: Lint + commit**
```bash
uv run ruff check packages/core/src/openlia/departments/macro_research.py packages/core/tests/departments/test_health.py packages/core/tests/departments/test_department_artifacts.py
uv run ruff format packages/core/src/openlia/departments/macro_research.py packages/core/tests/departments/test_health.py packages/core/tests/departments/test_department_artifacts.py
git add -A
git commit -m "feat(macro-research): de-runner MR; require only web_search, financial/news optional"
```

---

## Task 2: Dept-health `optional_categories` + `satisfied_categories`

**Files:**
- Modify: `packages/core/src/openlia/departments/health.py`
- Modify: `packages/server/src/openlia_server/services/dept_health.py`
- Modify: `packages/core/tests/departments/test_health.py`
- Modify: `packages/server/tests/test_dept_health.py`

- [ ] **Step 1: Add `satisfied_categories` to `DepartmentHealth` (`health.py`)**

In the `DepartmentHealth` dataclass, add after `unsatisfied_any_of`:
```python
    satisfied_categories: list[Category] = field(default_factory=list)
```
(`field` is already imported.) In `check_dept_health`, compute once after `validated_cats` is built:
```python
    satisfied_categories = sorted(validated_cats)
```
and pass `satisfied_categories=satisfied_categories` in **both** the active and the disabled `return DepartmentHealth(...)` calls.

- [ ] **Step 2: Emit the two fields from `serialize()` (`services/dept_health.py`)**

In `serialize()`, after `required_cats`/`any_of` are derived from the registry, add an optional-categories read:
```python
        optional_cats = [c.value for c in getattr(dept, "optional_categories", ())]
```
(initialize `optional_cats: list[str] = []` next to `required_cats` for the `dept is None` path), and add both keys to the returned dict:
```python
        "optional_categories": optional_cats,
        "satisfied_categories": [c.value for c in health.satisfied_categories],
```

- [ ] **Step 3: Core test for `satisfied_categories`**

Add to `test_health.py`:
```python
def test_satisfied_categories_lists_validated_categories():
    dept = MacroResearchDepartment()
    connectors = [
        _Conn(category=Category.WEB_SEARCH, status=ConnectorStatus.VALIDATED),
        _Conn(category=Category.NEWS, status=ConnectorStatus.FAILED),
    ]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert Category.WEB_SEARCH in health.satisfied_categories
    assert Category.NEWS not in health.satisfied_categories
```

- [ ] **Step 4: Update the serialize test (`test_dept_health.py`)**

In `test_serialize_macro_research_shows_web_search_required` (currently ~line 104), `financial` is now optional. Replace the body's assertions with:
```python
    blob = dept_health.serialize(h)
    assert blob["required_categories"] == ["web_search"]
    assert "financial" in blob["optional_categories"]
    assert "news" in blob["optional_categories"]
    assert blob["satisfied_categories"] == []
```
(The `DepartmentHealth(...)` constructed in that test omits `satisfied_categories`; the new default makes that valid and serializes to `[]`.)

- [ ] **Step 5: Verify + lint + commit**
```bash
uv run pytest packages/core/tests/departments/test_health.py packages/server/tests/test_dept_health.py -q
uv run ruff check packages/core/src/openlia/departments/health.py packages/server/src/openlia_server/services/dept_health.py packages/core/tests/departments/test_health.py packages/server/tests/test_dept_health.py
uv run ruff format packages/core/src/openlia/departments/health.py packages/server/src/openlia_server/services/dept_health.py packages/core/tests/departments/test_health.py packages/server/tests/test_dept_health.py
git add -A
git commit -m "feat(dept-health): expose optional_categories + satisfied_categories"
```

---

## Task 3: Server runner-plumbing (docstring + runtime/e2e tests)

**Files:**
- Modify: `packages/server/src/openlia_server/services/runtime.py`
- Modify: `packages/server/tests/test_services/test_runtime_entry.py`
- Modify: `packages/server/tests/e2e/test_python_lib_runner_activation.py`
- Modify: `packages/server/tests/e2e/test_wizard_happy_path.py`

- [ ] **Step 1: Fix the `select_runtime_mode` docstring (`runtime.py`)**

In the docstring (currently ~line 619), change `requires_runner=True` depts (Macro Research, Retail Sentiment)` to name only Retail Sentiment, and move Macro Research to the chat/dashboard list note. No code change.

- [ ] **Step 2: Update `test_runtime_entry.py`**

- In `test_select_mode_deterministic_default_for_runner_dept`, delete the `macro_research` assertion line; keep the `retail_sentiment` line.
- In `test_select_mode_rejects_chat_on_runner_dept`, change both `department_id="macro_research"` to `department_id="retail_sentiment"`.

- [ ] **Step 3: Retarget the runner-activation e2e to Retail Sentiment**

In `test_python_lib_runner_activation.py`, retarget the scenario from `macro_research` to `retail_sentiment` (RS is the remaining runner dept; required category FINANCIAL, need `social_posts`). Concretely:
- `fake_need`: `id="social_posts"`, `shape="list[dict]"`, keep a simple param (or `parameters=[]`).
- `set_dept_needs_for_testing({"retail_sentiment": [fake_need]})` and `set_dept_categories_for_testing({"retail_sentiment": ({Category.FINANCIAL}, set())})`.
- `_fake_load_needs`: return `[fake_need]` when `dept_id == "retail_sentiment"`.
- **Remove** the WEB_SEARCH connector block (lines ~120-141) — RS does not require WEB_SEARCH; the single FINANCIAL connector covers its category gate.
- The disabled-check: `health["retail_sentiment"]["status"] == "disabled"` and `["unresolved_needs"] == ["social_posts"]`.
- The proposed spec + approve: `department_id="retail_sentiment"`, `need_id="social_posts"`, `shape="list[dict]"`.
- Final: `health["retail_sentiment"]["status"] == "active"`.
- Update the module docstring/comments to say Retail Sentiment.

- [ ] **Step 4: Drop MR from the wizard-happy-path runner loop**

In `test_wizard_happy_path.py` (~line 109), change `for runner_dept in ("macro_research", "retail_sentiment"):` to `for runner_dept in ("retail_sentiment",):`.

- [ ] **Step 5: Verify server targeted dirs**

Run: `uv run pytest packages/server/tests/test_services/test_runtime_entry.py packages/server/tests/test_dept_health_api.py packages/server/tests/e2e/test_python_lib_runner_activation.py packages/server/tests/e2e/test_wizard_happy_path.py -q`
Expected: PASS. `test_dept_health_api.py` uses hand-built synthetic `DepartmentHealth` fixtures keyed to `"macro_research"` and should still pass (its assertions read the fixture values, not the registry); if any assertion reads a now-changed registry value, update it to match (e.g. MR `required_categories` is now `["web_search"]`).

- [ ] **Step 6: Lint + commit**
```bash
uv run ruff check packages/server/src/openlia_server/services/runtime.py packages/server/tests/test_services/test_runtime_entry.py packages/server/tests/e2e/test_python_lib_runner_activation.py packages/server/tests/e2e/test_wizard_happy_path.py
uv run ruff format packages/server/src/openlia_server/services/runtime.py packages/server/tests/test_services/test_runtime_entry.py packages/server/tests/e2e/test_python_lib_runner_activation.py packages/server/tests/e2e/test_wizard_happy_path.py
git add -A
git commit -m "test(macro-research): retarget runner-dept examples from MR to retail_sentiment"
```

---

## Task 4: Frontend runner list + dept-health types

**Files:**
- Modify: `frontend/src/api/departments.ts`
- Modify: `frontend/src/api/dept-health.ts`

- [ ] **Step 1: Drop MR from `RUNNER_BEARING_DEPARTMENTS` (`departments.ts`)**

Change the array to:
```ts
export const RUNNER_BEARING_DEPARTMENTS: readonly DepartmentSlug[] = [
  "retail_sentiment",
] as const;
```
(Leave `RUNNER_DEPARTMENT_LABELS` — it is a full per-slug map.)

- [ ] **Step 2: Add the two optional fields to the `DepartmentHealth` type (`dept-health.ts`)**

In the `DepartmentHealth` interface add:
```ts
  optional_categories?: string[];
  satisfied_categories?: string[];
```

- [ ] **Step 3: Fix affected frontend tests**

Run from `frontend/`: `npx vitest run src/setup src/components/sidebar src/api src/store`
Any test asserting `macro_research` is runner-bearing (candidates: `src/setup/steps/__tests__/DeptResolvePanel.test.tsx`, `src/setup/steps/__tests__/FirstRunSummary.test.tsx`, `src/components/sidebar/Sidebar.test.tsx`, `src/store/__tests__/dept-health.test.ts`, and any `departments` test) must drop that expectation — MR no longer appears in `RUNNER_BEARING_DEPARTMENTS` / the Review resolve panels. Update each failing assertion to match the single-entry (`retail_sentiment`) list.

- [ ] **Step 4: Typecheck + commit**
```bash
cd frontend && npx tsc --noEmit
```
```bash
git add -A
git commit -m "feat(frontend): drop MR from runner-bearing depts; add dept-health coverage fields"
```

---

## Task 5: MR coverage hint in `MRSettingsPanel`

**Files:**
- Modify: `frontend/src/pages/departments/macro_research/MRSettingsPanel.tsx`
- Test: `frontend/src/pages/departments/macro_research/__tests__/MRSettingsPanel.test.tsx` (create if absent; otherwise extend)

- [ ] **Step 1: Add the dept-health fetch + coverage section**

Add the import near the top:
```tsx
import { fetchDeptHealth, type DepartmentHealth } from "../../../api/dept-health";
```
Add a module-level notes map (above the component):
```tsx
const MR_COVERAGE: Record<string, { label: string; satisfied: string; missing: string }> = {
  web_search: {
    label: "Web search",
    satisfied: "Macro backbone active.",
    missing: "Required — without it Macro Research is disabled.",
  },
  financial: {
    label: "Financial",
    satisfied: "Live quotes and indicators active.",
    missing:
      "Optional — quote/indicator tiles fall back to web search or show source-unavailable. Add one in Settings, Connectors.",
  },
  news: {
    label: "News",
    satisfied: "Headlines active.",
    missing: "Optional — narrative-context tiles fall back to web search.",
  },
};
```
Inside the component, add state + effect:
```tsx
  const [coverage, setCoverage] = useState<DepartmentHealth | null>(null);
  useEffect(() => {
    fetchDeptHealth()
      .then((rows) =>
        setCoverage(rows.find((r) => r.department_id === "macro_research") ?? null),
      )
      .catch(() => setCoverage(null));
  }, []);
```
Render a new section (place it right after the `mr-settings-runnow-section`):
```tsx
      {coverage ? (
        <section className="space-y-3" data-testid="mr-coverage">
          <h3 className="text-sm font-medium text-[--color-text-primary]">Source coverage</h3>
          <ul className="space-y-2">
            {(["web_search", "financial", "news"] as const).map((cat) => {
              const note = MR_COVERAGE[cat];
              const satisfied = coverage.satisfied_categories?.includes(cat) ?? false;
              return (
                <li
                  key={cat}
                  data-testid={`mr-coverage-${cat}`}
                  className="text-xs text-[--color-text-secondary]"
                >
                  <span className="font-medium text-[--color-text-primary]">{note.label}</span>
                  {" — "}
                  <span
                    className={
                      satisfied
                        ? "text-[--color-feedback-success]"
                        : "text-[--color-text-secondary]"
                    }
                  >
                    {satisfied ? "active" : "not configured"}
                  </span>
                  {". "}
                  {satisfied ? note.satisfied : note.missing}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
```

- [ ] **Step 2: View test**

Add/extend `MRSettingsPanel.test.tsx`. Mock `../../../api/dept-health`'s `fetchDeptHealth` to resolve to a single MR row with `required_categories: ["web_search"]`, `optional_categories: ["financial", "news"]`, `satisfied_categories: ["web_search"]` (and the other MR api calls mocked as the existing test does — mirror the existing mock setup for `getConfig`/`runAssessment`/etc.). Assert:
```tsx
expect(await screen.findByTestId("mr-coverage")).toBeInTheDocument();
expect(screen.getByTestId("mr-coverage-web_search")).toHaveTextContent("active");
expect(screen.getByTestId("mr-coverage-financial")).toHaveTextContent("not configured");
expect(screen.getByTestId("mr-coverage-financial")).toHaveTextContent("fall back to web search");
```

- [ ] **Step 3: Typecheck + test + commit**
```bash
cd frontend && npx tsc --noEmit && npx vitest run src/pages/departments/macro_research
```
```bash
git add -A
git commit -m "feat(macro-research): source-coverage hint in MR settings panel"
```

---

## Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Python lint + targeted suites**
```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest packages/core/tests/departments packages/server/tests/test_services packages/server/tests/test_dept_health.py packages/server/tests/test_dept_health_api.py packages/server/tests/e2e -q
```
Expected: all PASS, lint clean.

- [ ] **Step 2: Frontend typecheck + targeted vitest**
```bash
cd frontend && npx tsc --noEmit && npx vitest run src/pages/departments/macro_research src/api src/setup src/components/sidebar src/store
```
Expected: all PASS.

- [ ] **Step 3: Sanity — MR active on WEB_SEARCH alone**

Confirm via the core suite (`test_macro_research_active_with_web_search_only` from Task 1) that MR is active with only a validated WEB_SEARCH connector and no runner specs. No separate command needed if Step 1 passed.

- [ ] **Step 4: Final commit (if any lint/format fixups were needed)**
```bash
git add -A && git commit -m "chore(macro-research): lint/format pass for connector-requirement relaxation" || echo "nothing to commit"
```

---

## Post-implementation amendments

(Record any divergence here as it is executed — e.g. additional frontend tests that referenced MR as runner-bearing, or any `test_dept_health_api.py` fixture that needed a registry-value fix.)
