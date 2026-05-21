# Equity Research v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the equity research department around (a) an eight-stage LLM-orchestrated pipeline (clarify → read template → plan → gather → model → draft → verify → assemble), (b) a composer that accepts a template-declared input schema plus a free-form prompt, and (c) the collapse of `stock_research` / `stock_initiation` / `sector_research` modes into ordinary `TemplateSpec` entries.

**Architecture:** A planner LLM converts (user inputs, template, optional clarifications) into a structured `Plan` containing research-strand specs, model components, and drafting directives. Parallel strand subagents fetch via the user's connected MCP/web tools and emit prose findings plus citations (no typed Facts). A model-analyst subagent builds a `ModelArtifact` from planner-declared components. Section subagents draft from the research pool + model artifact. A hybrid verifier (deterministic survivors + LLM verifier) auto-retries failing sections.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pydantic v2, anthropic SDK, openai SDK, mammoth, python-docx, React/TypeScript/Vite.

**Spec:** `docs/superpowers/specs/2026-05-20-equity-research-v2-design.md`

---

## Phase 0 — Setup

### Task 0: Branch + worktree setup

**Files:** none (already on `feat/custom-templates-v2`)

- [ ] **Step 1: Confirm branch**

Run: `git status && git rev-parse --abbrev-ref HEAD`
Expected: clean tree, `feat/custom-templates-v2`

- [ ] **Step 2: Confirm spec exists**

Run: `ls docs/superpowers/specs/2026-05-20-equity-research-v2-design.md`
Expected: file present.

---

## Phase 1 — Foundation

Foundation PRs extend `TemplateSpec`, redesign the composer to read its input schema, and lift the remaining two default templates (`stock_research` and `sector_research`) so all three modes are demoted to templates. Nothing in Phase 1 changes runtime behavior — it expands the surface so Phase 2 has a target to write against.

---

### Task F1: Extend `TemplateSpec` with v2 fields

**Files:**
- Modify: `packages/core/src/openlia/reports/frameworks/template_spec.py`
- Test: `packages/core/tests/frameworks/test_template_spec_v2.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/frameworks/test_template_spec_v2.py`:

```python
from openlia.reports.frameworks.template_spec import (
    TemplateSpec,
    SectionSpec,
    ComposerInputSpec,
    OutputArtifactSpec,
    ModelComponentSpec,
)


def test_composer_inputs_default_empty():
    spec = TemplateSpec(name="t", body_sections=[], synthesis_sections=[])
    assert spec.composer_inputs == []


def test_composer_inputs_validate_type():
    spec = TemplateSpec(
        name="t",
        body_sections=[],
        synthesis_sections=[],
        composer_inputs=[
            ComposerInputSpec(name="ticker", type="ticker", label="Ticker", required=True),
            ComposerInputSpec(name="window", type="int", label="Window (quarters)", required=False, default=4),
        ],
    )
    assert spec.composer_inputs[0].type == "ticker"
    assert spec.composer_inputs[1].default == 4


def test_output_artifacts_default_empty():
    spec = TemplateSpec(name="t", body_sections=[], synthesis_sections=[])
    assert spec.output_artifacts == []


def test_section_spec_trigger_and_depends():
    section = SectionSpec(
        id="ext1",
        title="Extension",
        brief="brief",
        trigger_when="scorecard rating below three stars",
        depends_on=["scorecard"],
    )
    assert section.trigger_when == "scorecard rating below three stars"
    assert section.depends_on == ["scorecard"]


def test_model_component_with_assumptions():
    c = ModelComponentSpec(helper_id="dcf", assumption_overrides={"wacc": 0.12})
    assert c.assumption_overrides["wacc"] == 0.12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/frameworks/test_template_spec_v2.py -v`
Expected: ImportError on the v2 names (`ComposerInputSpec`, `OutputArtifactSpec`, `ModelComponentSpec`) or AttributeError on the new fields.

- [ ] **Step 3: Implement schema additions**

Edit `packages/core/src/openlia/reports/frameworks/template_spec.py` to add:

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


ComposerInputType = Literal[
    "ticker", "ticker_list", "sector", "string", "enum", "date_range", "int", "bool"
]


class ComposerInputSpec(BaseModel):
    name: str
    type: ComposerInputType
    label: str
    required: bool = False
    validator_id: str | None = None
    default: Any = None
    enum_values: list[str] | None = None
    help_text: str | None = None


ArtifactType = Literal["prose", "table", "chart"]
ArtifactSource = Literal["strand", "model", "section"]


class OutputArtifactSpec(BaseModel):
    name: str
    type: ArtifactType
    required: bool = False
    source: ArtifactSource
    description: str | None = None
    schema_hint: dict[str, Any] | None = None   # e.g. {"columns": ["quarter", "guidance", "actual"]}


class ModelComponentSpec(BaseModel):
    helper_id: str
    assumption_overrides: dict[str, Any] = Field(default_factory=dict)
```

Then add to `SectionSpec`:

```python
class SectionSpec(BaseModel):
    # ...existing fields...
    trigger_when: str | None = None
    depends_on: list[str] = Field(default_factory=list)
```

And to `TemplateSpec`:

```python
class TemplateSpec(BaseModel):
    # ...existing fields...
    composer_inputs: list[ComposerInputSpec] = Field(default_factory=list)
    output_artifacts: list[OutputArtifactSpec] = Field(default_factory=list)
    model_components: list[ModelComponentSpec] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/frameworks/test_template_spec_v2.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run full report_v2 suite**

Run: `uv run pytest packages/core/tests/ -q`
Expected: no regressions — all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/reports/frameworks/template_spec.py \
        packages/core/tests/frameworks/test_template_spec_v2.py
git commit -m "feat(templates): extend TemplateSpec with v2 fields (composer_inputs, output_artifacts, trigger_when, depends_on, model_components)"
```

**Risk:** Pure additive. Defaults make every existing template valid without modification.

---

### Task F2: Composer dynamic field rendering

**Files:**
- Modify: `frontend/src/pages/EquityResearch/Composer.tsx`
- Create: `frontend/src/components/templates/DynamicInputField.tsx`
- Create: `frontend/src/components/templates/__tests__/DynamicInputField.test.tsx`
- Modify: `packages/server/src/openlia_server/routes/reports.py` (accept new payload shape)
- Test: `packages/server/tests/test_reports_composer_inputs.py` (new)

- [ ] **Step 1: Write the frontend test**

Create `frontend/src/components/templates/__tests__/DynamicInputField.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { DynamicInputField } from "../DynamicInputField";

const tickerSpec = { name: "ticker", type: "ticker", label: "Ticker", required: true };
const intSpec = { name: "window", type: "int", label: "Window", required: false, default: 4 };
const enumSpec = { name: "stance", type: "enum", label: "Stance", required: false, enum_values: ["bull","bear","neutral"] };

test("ticker field renders text input with validator hint", () => {
  render(<DynamicInputField spec={tickerSpec} value="" onChange={() => {}} />);
  expect(screen.getByLabelText(/Ticker/)).toBeInTheDocument();
});

test("int field renders numeric input with default", () => {
  render(<DynamicInputField spec={intSpec} value={4} onChange={() => {}} />);
  expect(screen.getByDisplayValue("4")).toBeInTheDocument();
});

test("enum field renders select with options", () => {
  render(<DynamicInputField spec={enumSpec} value="" onChange={() => {}} />);
  enumSpec.enum_values!.forEach(v => expect(screen.getByText(v)).toBeInTheDocument());
});

test("required field emits validation error when empty on blur", () => {
  const onChange = jest.fn();
  render(<DynamicInputField spec={tickerSpec} value="" onChange={onChange} />);
  fireEvent.blur(screen.getByLabelText(/Ticker/));
  expect(screen.getByText(/required/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend test to verify failure**

Run: `cd frontend && npm test -- DynamicInputField`
Expected: import errors / file not found.

- [ ] **Step 3: Implement `DynamicInputField`**

Create `frontend/src/components/templates/DynamicInputField.tsx`:

```tsx
import React, { useState } from "react";

export type ComposerInputSpec = {
  name: string;
  type: "ticker" | "ticker_list" | "sector" | "string" | "enum" | "date_range" | "int" | "bool";
  label: string;
  required: boolean;
  default?: unknown;
  enum_values?: string[];
  help_text?: string;
};

type Props = {
  spec: ComposerInputSpec;
  value: unknown;
  onChange: (v: unknown) => void;
};

export function DynamicInputField({ spec, value, onChange }: Props) {
  const [touched, setTouched] = useState(false);
  const showError = touched && spec.required && (value === "" || value == null);

  switch (spec.type) {
    case "ticker":
    case "string":
    case "sector":
      return (
        <label>
          {spec.label}{spec.required ? " *" : ""}
          <input type="text"
                 value={(value as string) ?? ""}
                 onChange={e => onChange(e.target.value)}
                 onBlur={() => setTouched(true)} />
          {showError && <span className="error">required</span>}
          {spec.help_text && <small>{spec.help_text}</small>}
        </label>
      );
    case "ticker_list":
      return (
        <label>
          {spec.label}{spec.required ? " *" : ""}
          <input type="text"
                 placeholder="NVDA, AMD, INTC"
                 value={Array.isArray(value) ? value.join(", ") : ""}
                 onChange={e => onChange(e.target.value.split(",").map(s => s.trim()).filter(Boolean))} />
        </label>
      );
    case "int":
      return (
        <label>
          {spec.label}
          <input type="number"
                 value={(value as number) ?? (spec.default as number) ?? 0}
                 onChange={e => onChange(Number(e.target.value))} />
        </label>
      );
    case "enum":
      return (
        <label>
          {spec.label}
          <select value={(value as string) ?? ""} onChange={e => onChange(e.target.value)}>
            <option value="">--</option>
            {(spec.enum_values ?? []).map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
      );
    case "bool":
      return (
        <label>
          <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} />
          {spec.label}
        </label>
      );
    case "date_range":
      return (
        <label>
          {spec.label}
          <input type="text" placeholder="YYYY-MM-DD..YYYY-MM-DD"
                 value={(value as string) ?? ""}
                 onChange={e => onChange(e.target.value)} />
        </label>
      );
    default:
      return null;
  }
}
```

- [ ] **Step 4: Run frontend test to verify it passes**

Run: `cd frontend && npm test -- DynamicInputField`
Expected: 4 passed.

- [ ] **Step 5: Wire `Composer.tsx` to render dynamic fields**

Modify `frontend/src/pages/EquityResearch/Composer.tsx`. The composer must:
- Fetch the selected template's `composer_inputs` via the existing `GET /api/templates/{id}` endpoint.
- Render one `DynamicInputField` per spec, in declaration order.
- Always render a free-form `prompt` textarea as the last field, independent of the template.
- Build the submit payload as `{ template_id, composer_inputs: { ...keyed by name }, prompt }`.
- Block submit until all required fields are non-empty.

Replace the existing ticker-only input section with:

```tsx
const [inputs, setInputs] = useState<Record<string, unknown>>({});
const [prompt, setPrompt] = useState("");

// ...effect to load template.composer_inputs into local state...

return (
  <form onSubmit={onSubmit}>
    {template.composer_inputs.map(spec => (
      <DynamicInputField
        key={spec.name}
        spec={spec}
        value={inputs[spec.name] ?? spec.default}
        onChange={v => setInputs(prev => ({ ...prev, [spec.name]: v }))}
      />
    ))}
    <label>
      Notes / focus (optional)
      <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={4} />
    </label>
    <button type="submit" disabled={!allRequiredFilled()}>Generate report</button>
  </form>
);
```

- [ ] **Step 6: Write the backend test for the new payload shape**

Create `packages/server/tests/test_reports_composer_inputs.py`:

```python
import pytest
from fastapi.testclient import TestClient
from openlia_server.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_create_report_accepts_composer_inputs(client, authed_headers, default_template_id):
    body = {
        "template_id": default_template_id,
        "composer_inputs": {"ticker": "NVDA"},
        "prompt": "focus on AMD comparison",
    }
    r = client.post("/api/reports", json=body, headers=authed_headers)
    assert r.status_code == 202
    assert "report_id" in r.json()


def test_create_report_rejects_missing_required_input(client, authed_headers, default_template_id):
    body = {"template_id": default_template_id, "composer_inputs": {}, "prompt": ""}
    r = client.post("/api/reports", json=body, headers=authed_headers)
    assert r.status_code == 422
    assert "ticker" in r.text  # required input missing
```

- [ ] **Step 7: Run backend test to verify failure**

Run: `uv run pytest packages/server/tests/test_reports_composer_inputs.py -v`
Expected: 422 not returned OR endpoint doesn't accept the new shape — test fails.

- [ ] **Step 8: Update `routes/reports.py` to accept the new payload**

Modify the `POST /api/reports` handler. New request model:

```python
class CreateReportRequest(BaseModel):
    template_id: str
    composer_inputs: dict[str, Any] = Field(default_factory=dict)
    prompt: str = ""
    # legacy back-compat (removed in F4):
    ticker: str | None = None
    report_type: str | None = None
```

In the handler:
1. Resolve `template = registry.get(template_id)`.
2. For each `spec in template.composer_inputs`: if `spec.required` and `spec.name not in composer_inputs`, raise 422 with `{ "field": spec.name, "message": "required" }`.
3. Pass `(composer_inputs, prompt)` into the runner's create-run service.
4. If `ticker` legacy field is present, translate it to `composer_inputs["ticker"]` (warn-log; remove in F4).

- [ ] **Step 9: Run backend test to verify it passes**

Run: `uv run pytest packages/server/tests/test_reports_composer_inputs.py -v`
Expected: 2 passed.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/templates/DynamicInputField.tsx \
        frontend/src/components/templates/__tests__/DynamicInputField.test.tsx \
        frontend/src/pages/EquityResearch/Composer.tsx \
        packages/server/src/openlia_server/routes/reports.py \
        packages/server/tests/test_reports_composer_inputs.py
git commit -m "feat(composer): dynamic input fields driven by template.composer_inputs"
```

**Risk:** Existing single-ticker submissions still work via the legacy `ticker` field. Frontend changes are contained to the composer.

---

### Task F3: `stock_research` TemplateSpec loader

**Files:**
- Create: `packages/core/src/openlia/reports/frameworks/loaders/stock_research.py`
- Create: `packages/core/src/openlia/reports/frameworks/stock_research_briefs.md`
- Modify: `packages/core/src/openlia/reports/frameworks/registry.py`
- Test: `packages/core/tests/frameworks/test_stock_research_loader.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/frameworks/test_stock_research_loader.py`:

```python
from openlia.reports.frameworks.registry import default_registry
from openlia.reports.frameworks.loaders import stock_research  # noqa: registers


def test_stock_research_in_registry():
    spec = default_registry.get("stock_research")
    assert spec.name
    assert len(spec.body_sections) > 0
    assert len(spec.synthesis_sections) > 0


def test_stock_research_composer_inputs():
    spec = default_registry.get("stock_research")
    names = {i.name for i in spec.composer_inputs}
    assert "ticker" in names
    ticker_input = next(i for i in spec.composer_inputs if i.name == "ticker")
    assert ticker_input.required
    assert ticker_input.type == "ticker"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/frameworks/test_stock_research_loader.py -v`
Expected: `KeyError: stock_research` from the registry.

- [ ] **Step 3: Identify the current stock_research source**

Look at where the existing `stock_research` mode lives. Likely in `packages/server/src/openlia_server/services/equity_research_runner.py` or `equity_research_config.py` or `equity_research_templates.py`. Find:
- Section list (body + synthesis)
- Per-section briefs
- Word targets
- Style guide / system role overrides (if any)

Run: `grep -rn "stock_research" packages/core/ packages/server/`

- [ ] **Step 4: Create the loader file**

Create `packages/core/src/openlia/reports/frameworks/loaders/stock_research.py`:

```python
from pathlib import Path

from openlia.reports.frameworks.registry import default_registry
from openlia.reports.frameworks.template_spec import (
    TemplateSpec,
    SectionSpec,
    ComposerInputSpec,
)
from openlia.reports.frameworks.loaders._brief_parser import parse_briefs


_BRIEFS_PATH = Path(__file__).parent.parent / "stock_research_briefs.md"


def load_stock_research_template() -> TemplateSpec:
    briefs = parse_briefs(_BRIEFS_PATH.read_text())
    body_section_ids = [
        # copy from existing stock_research config
    ]
    synthesis_section_ids = [
        # copy from existing stock_research config
    ]
    return TemplateSpec(
        name="Stock Research (Quick Look)",
        global_preface="...",
        body_sections=[SectionSpec(id=sid, title=briefs[sid].title, brief=briefs[sid].body) for sid in body_section_ids],
        synthesis_sections=[SectionSpec(id=sid, title=briefs[sid].title, brief=briefs[sid].body) for sid in synthesis_section_ids],
        composer_inputs=[
            ComposerInputSpec(name="ticker", type="ticker", label="Ticker", required=True, validator_id="ticker_resolver"),
        ],
        default_word_targets={...},     # copy from existing
        style_guide="...",              # copy from existing
        system_role="You are an equity research analyst writing a quick-look note.",
    )


default_registry.register("stock_research", load_stock_research_template)
```

- [ ] **Step 5: Author `stock_research_briefs.md`**

Create `packages/core/src/openlia/reports/frameworks/stock_research_briefs.md` mirroring the format used by `stock_initiation_briefs.md`. Section briefs are copied verbatim from the existing inline definitions; each section starts with `## <section_id>`.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/frameworks/test_stock_research_loader.py -v`
Expected: 2 passed.

- [ ] **Step 7: Smoke test — generate a stock_research report via the existing runner**

Run: `uv run pytest packages/core/tests/ -k "stock_research" -q`
Expected: existing stock_research tests still pass with the loader resolving via the registry.

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/openlia/reports/frameworks/loaders/stock_research.py \
        packages/core/src/openlia/reports/frameworks/stock_research_briefs.md \
        packages/core/src/openlia/reports/frameworks/registry.py \
        packages/core/tests/frameworks/test_stock_research_loader.py
git commit -m "feat(templates): stock_research TemplateSpec loader (mode collapse PR 1)"
```

**Risk:** Medium. Equivalent to v1 PR 2 for stock_initiation. Existing imports referencing `stock_research`-flavored constants need to be redirected to the loader. Grep before merging.

---

### Task F4: `sector_research` TemplateSpec loader + `report_type` enum removal

**Files:**
- Create: `packages/core/src/openlia/reports/frameworks/loaders/sector_research.py`
- Create: `packages/core/src/openlia/reports/frameworks/sector_research_briefs.md`
- Modify: `packages/core/src/openlia/reports/frameworks/registry.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` (drop `report_type` enum check)
- Modify: `packages/server/src/openlia_server/routes/reports.py` (drop legacy `report_type` translation from F2)
- Modify: `frontend/src/pages/EquityResearch/Composer.tsx` (mode picker → template picker)
- Test: `packages/core/tests/frameworks/test_sector_research_loader.py` (new)
- Test: `packages/core/tests/runtime/test_runner_report_type_removed.py` (new)

- [ ] **Step 1: Write the failing test for the loader**

Create `packages/core/tests/frameworks/test_sector_research_loader.py`:

```python
from openlia.reports.frameworks.registry import default_registry
from openlia.reports.frameworks.loaders import sector_research  # noqa


def test_sector_research_in_registry():
    spec = default_registry.get("sector_research")
    assert spec.name


def test_sector_research_composer_inputs():
    spec = default_registry.get("sector_research")
    names = {i.name for i in spec.composer_inputs}
    assert "sector" in names
    sector_input = next(i for i in spec.composer_inputs if i.name == "sector")
    assert sector_input.required
    assert sector_input.type == "sector"

    assert "peer_tickers" in names
    peer_input = next(i for i in spec.composer_inputs if i.name == "peer_tickers")
    assert peer_input.type == "ticker_list"
```

- [ ] **Step 2: Write the failing test for `report_type` removal**

Create `packages/core/tests/runtime/test_runner_report_type_removed.py`:

```python
import inspect
from openlia.llm.runtime.report_v2 import runner


def test_runner_no_report_type_parameter():
    sig = inspect.signature(runner.WavedReportRunner.__init__)
    assert "report_type" not in sig.parameters, "report_type should be removed; templates are resolved by template_id only"
```

- [ ] **Step 3: Run both tests to verify failure**

Run: `uv run pytest packages/core/tests/frameworks/test_sector_research_loader.py packages/core/tests/runtime/test_runner_report_type_removed.py -v`
Expected: KeyError on loader test; AssertionError on runner test.

- [ ] **Step 4: Create the loader (same pattern as F3)**

Create `packages/core/src/openlia/reports/frameworks/loaders/sector_research.py` and the briefs markdown alongside, mirroring F3 but using sector-research section IDs and composer_inputs:

```python
composer_inputs=[
    ComposerInputSpec(name="sector", type="sector", label="Sector", required=True, validator_id="sector_enum"),
    ComposerInputSpec(name="peer_tickers", type="ticker_list", label="Peer tickers (optional)", required=False),
],
```

- [ ] **Step 5: Remove `report_type` from `runner.py`**

In `packages/core/src/openlia/llm/runtime/report_v2/runner.py`:
- Drop the `report_type` parameter from `WavedReportRunner.__init__`.
- The runner already accepts `template: TemplateSpec | None` (added in v1 PR 1). The new entry point is `template_id` → `registry.get(template_id)` resolved by the caller (the server's create-run service).

- [ ] **Step 6: Update server routes/reports.py**

In `routes/reports.py`, remove the legacy `report_type` field from `CreateReportRequest` and any back-compat translation added in F2. The endpoint now requires `template_id`.

If old clients still call with `report_type`, return 410 Gone with `{"error": "report_type removed; submit template_id"}`.

- [ ] **Step 7: Frontend mode picker → template picker**

In `frontend/src/pages/EquityResearch/Composer.tsx`:
- Remove the mode dropdown (stock_initiation / stock_research / sector_research).
- Replace with a `TemplatePicker` component that lists templates from `GET /api/templates` grouped by source (`built-in`, `mine`).
- Built-in group seeds with `stock_initiation`, `stock_research`, `sector_research` (server-side: these are always returned as built-ins for every user).

- [ ] **Step 8: Run all the tests**

Run: `uv run pytest packages/core/tests/ packages/server/tests/ -q`
Expected: all pass.

Run: `cd frontend && npm test -- Composer`
Expected: composer tests pass.

- [ ] **Step 9: Commit**

```bash
git add packages/core/src/openlia/reports/frameworks/loaders/sector_research.py \
        packages/core/src/openlia/reports/frameworks/sector_research_briefs.md \
        packages/core/src/openlia/reports/frameworks/registry.py \
        packages/core/src/openlia/llm/runtime/report_v2/runner.py \
        packages/server/src/openlia_server/routes/reports.py \
        frontend/src/pages/EquityResearch/Composer.tsx \
        packages/core/tests/frameworks/test_sector_research_loader.py \
        packages/core/tests/runtime/test_runner_report_type_removed.py
git commit -m "feat(templates): sector_research loader + remove report_type enum (mode collapse complete)"
```

**Risk:** High. Drops the public `report_type` API field. Verify no external integrations rely on it before merging.

---

## Phase 2 — Pipeline buildout

Phase 2 builds the new eight-stage runtime alongside the existing facts pipeline. Each stage lands behind a feature flag so we can validate against the default templates incrementally and flip to the new path in P5–P6 when the chain is stable.

---

### Task P1: `Plan` schema + planner LLM stage

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/planner.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/plan_types.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` (call planner when flag set)
- Create: `packages/server/src/openlia_server/services/planner_service.py`
- Test: `packages/core/tests/runtime/test_planner.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/runtime/test_planner.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.plan_types import Plan, ResearchStrand
from openlia.llm.runtime.report_v2.planner import Planner
from openlia.reports.frameworks.registry import default_registry


@pytest.fixture
def stub_llm_returns():
    plan_json = {
        "research_strands": [
            {"name": "financials", "purpose": "pull income/balance/cashflow",
             "tools_allowed": ["mcp__eodhd__get_fundamentals_data"],
             "expected_artifacts": []},
            {"name": "news", "purpose": "recent material news",
             "tools_allowed": ["mcp__eodhd__get_company_news", "web_search"],
             "expected_artifacts": []},
        ],
        "model_components": [
            {"helper_id": "three_scenario_forecast", "assumption_overrides": {}},
        ],
        "drafting_directives": {"global_directive": "Focus on AMD comparison.", "per_section": {}},
        "output_artifacts": [],
    }
    return AsyncMock(return_value=json.dumps(plan_json))


@pytest.mark.asyncio
async def test_planner_emits_valid_plan(stub_llm_returns):
    planner = Planner(llm_call=stub_llm_returns)
    template = default_registry.get("stock_initiation")
    plan = await planner.run(
        template=template,
        composer_inputs={"ticker": "NVDA"},
        prompt="Focus on AMD comparison.",
        clarifications=[],
        available_tools=["mcp__eodhd__get_fundamentals_data", "mcp__eodhd__get_company_news", "web_search"],
    )
    assert isinstance(plan, Plan)
    assert len(plan.research_strands) == 2
    assert plan.research_strands[0].name == "financials"
    assert plan.drafting_directives.global_directive == "Focus on AMD comparison."


@pytest.mark.asyncio
async def test_planner_rejects_unavailable_tool(stub_llm_returns):
    # Planner returns a tool not in available_tools — should raise
    bad_plan = json.dumps({
        "research_strands": [{"name": "x", "purpose": "y", "tools_allowed": ["mcp__nonexistent"], "expected_artifacts": []}],
        "model_components": [],
        "drafting_directives": {"global_directive": "", "per_section": {}},
        "output_artifacts": [],
    })
    llm = AsyncMock(return_value=bad_plan)
    planner = Planner(llm_call=llm)
    with pytest.raises(ValueError, match="unavailable tool"):
        await planner.run(
            template=default_registry.get("stock_initiation"),
            composer_inputs={"ticker": "NVDA"},
            prompt="",
            clarifications=[],
            available_tools=["web_search"],
        )
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_planner.py -v`
Expected: ImportError on `Plan` / `Planner`.

- [ ] **Step 3: Define `Plan` types**

Create `packages/core/src/openlia/llm/runtime/report_v2/plan_types.py`:

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class ResearchStrand(BaseModel):
    name: str
    purpose: str
    tools_allowed: list[str]
    expected_artifacts: list[str] = Field(default_factory=list)


class ModelComponentPlan(BaseModel):
    helper_id: str
    assumption_overrides: dict[str, Any] = Field(default_factory=dict)


class SectionDirective(BaseModel):
    skip: bool = False
    emphasis: str | None = None
    word_target_override: int | None = None


class DraftingDirectives(BaseModel):
    global_directive: str = ""
    per_section: dict[str, SectionDirective] = Field(default_factory=dict)


class OutputArtifactPlan(BaseModel):
    name: str
    type: Literal["prose", "table", "chart"]
    required: bool = False
    source: Literal["strand", "model", "section"]


class Plan(BaseModel):
    research_strands: list[ResearchStrand]
    model_components: list[ModelComponentPlan]
    drafting_directives: DraftingDirectives
    output_artifacts: list[OutputArtifactPlan]
```

- [ ] **Step 4: Implement `Planner`**

Create `packages/core/src/openlia/llm/runtime/report_v2/planner.py`:

```python
import json
from typing import Awaitable, Callable

from openlia.llm.runtime.report_v2.plan_types import Plan
from openlia.reports.frameworks.template_spec import TemplateSpec


PLANNER_SYSTEM = """You are a research planner for equity research reports.
You output a JSON Plan that downstream stages execute. The Plan must:
- Allocate research strands across the available tools (one strand per concern: financials, news, peers, macro, etc.)
- Declare model components to compute (from the helper registry)
- Pass the user's prompt verbatim into drafting_directives.global_directive
- Echo the template's required output_artifacts into the plan
Return a single JSON object matching the Plan schema. No prose around it."""


PLANNER_USER_TMPL = """TEMPLATE: {template_name}
SECTIONS: {section_ids}
TEMPLATE-DECLARED OUTPUT ARTIFACTS: {template_artifacts}

USER COMPOSER INPUTS: {composer_inputs}
USER PROMPT: {prompt}
CLARIFICATIONS: {clarifications}

AVAILABLE TOOLS: {available_tools}

Produce the Plan JSON."""


class Planner:
    def __init__(self, llm_call: Callable[[str, str], Awaitable[str]]):
        # llm_call(system_prompt, user_prompt) -> raw JSON string
        self._llm = llm_call

    async def run(
        self,
        template: TemplateSpec,
        composer_inputs: dict,
        prompt: str,
        clarifications: list[dict],
        available_tools: list[str],
    ) -> Plan:
        user_prompt = PLANNER_USER_TMPL.format(
            template_name=template.name,
            section_ids=[s.id for s in template.body_sections + template.synthesis_sections],
            template_artifacts=[a.model_dump() for a in template.output_artifacts],
            composer_inputs=composer_inputs,
            prompt=prompt,
            clarifications=clarifications,
            available_tools=available_tools,
        )
        raw = await self._llm(PLANNER_SYSTEM, user_prompt)
        plan_data = json.loads(raw)
        plan = Plan(**plan_data)
        self._validate_tools(plan, available_tools)
        return plan

    @staticmethod
    def _validate_tools(plan: Plan, available_tools: list[str]) -> None:
        available = set(available_tools)
        for strand in plan.research_strands:
            for tool in strand.tools_allowed:
                if tool not in available:
                    raise ValueError(f"unavailable tool in plan: {tool} (strand: {strand.name})")
```

- [ ] **Step 5: Create the server-side service wrapper**

Create `packages/server/src/openlia_server/services/planner_service.py` that constructs a `Planner` with the configured anthropic/openai client and the user's connected MCP tools.

- [ ] **Step 6: Wire runner.py behind a feature flag**

In `runner.py`:

```python
self._use_planner_pipeline = getattr(template, "_use_planner_pipeline", False) or self.config.use_planner_pipeline
```

When `_use_planner_pipeline=True`, call `Planner` and stash the result on the run context for later stages. Otherwise, run the v1 facts path unchanged.

- [ ] **Step 7: Run tests**

Run: `uv run pytest packages/core/tests/runtime/test_planner.py -v`
Expected: 2 passed.

Run: `uv run pytest packages/core/tests/ -q`
Expected: no regressions.

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/planner.py \
        packages/core/src/openlia/llm/runtime/report_v2/plan_types.py \
        packages/core/src/openlia/llm/runtime/report_v2/runner.py \
        packages/server/src/openlia_server/services/planner_service.py \
        packages/core/tests/runtime/test_planner.py
git commit -m "feat(runtime): Plan schema + planner LLM stage (flagged off)"
```

**Risk:** Low — entirely behind a flag.

---

### Task P2: Clarify stage

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/clarifier.py`
- Create: `packages/server/src/openlia_server/routes/clarifier.py`
- Create: `packages/server/src/openlia_server/services/clarifier_service.py`
- Create: `frontend/src/components/templates/ClarifierModal.tsx`
- Modify: `frontend/src/pages/EquityResearch/Composer.tsx` (open modal on submit)
- Test: `packages/core/tests/runtime/test_clarifier.py` (new)
- Test: `packages/server/tests/test_clarifier_route.py` (new)

- [ ] **Step 1: Write the failing core test**

Create `packages/core/tests/runtime/test_clarifier.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.clarifier import Clarifier, ClarifyingQuestion
from openlia.reports.frameworks.registry import default_registry


@pytest.mark.asyncio
async def test_clarifier_emits_questions():
    llm = AsyncMock(return_value=json.dumps({
        "questions": [
            {"id": "q1", "type": "enum", "label": "Investment horizon?",
             "enum_values": ["short", "medium", "long"], "required": True, "why": "Sets analyst tone."},
            {"id": "q2", "type": "text", "label": "Specific risks to emphasize?", "required": False, "why": "..."},
        ]
    }))
    clarifier = Clarifier(llm_call=llm)
    questions = await clarifier.run(
        template=default_registry.get("stock_initiation"),
        composer_inputs={"ticker": "NVDA"},
        prompt="bull case on AI demand",
    )
    assert len(questions) == 2
    assert questions[0].id == "q1"
    assert questions[0].type == "enum"


@pytest.mark.asyncio
async def test_clarifier_emits_no_questions_when_clear():
    llm = AsyncMock(return_value=json.dumps({"questions": []}))
    clarifier = Clarifier(llm_call=llm)
    questions = await clarifier.run(
        template=default_registry.get("stock_initiation"),
        composer_inputs={"ticker": "NVDA"},
        prompt="full initiation, no specific asks",
    )
    assert questions == []
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_clarifier.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `Clarifier`**

Create `packages/core/src/openlia/llm/runtime/report_v2/clarifier.py`:

```python
import json
from typing import Awaitable, Callable, Literal
from pydantic import BaseModel, Field

from openlia.reports.frameworks.template_spec import TemplateSpec


class ClarifyingQuestion(BaseModel):
    id: str
    type: Literal["text", "enum", "int", "bool"]
    label: str
    required: bool = False
    enum_values: list[str] | None = None
    why: str | None = None


class Clarification(BaseModel):
    id: str
    answer: str | int | bool | None


CLARIFIER_SYSTEM = """You are a research clarifier. Given a report template, the user's composer inputs, and their free-form prompt,
emit 0-N clarifying questions that materially change how the report should be researched or written.
Skip questions whose answer is implicit. Limit to at most 5. Each question has id, type (text/enum/int/bool), label, required, why.
Return JSON: {"questions": [...]}"""


class Clarifier:
    def __init__(self, llm_call: Callable[[str, str], Awaitable[str]]):
        self._llm = llm_call

    async def run(
        self,
        template: TemplateSpec,
        composer_inputs: dict,
        prompt: str,
    ) -> list[ClarifyingQuestion]:
        user_msg = (
            f"TEMPLATE: {template.name}\n"
            f"SECTIONS: {[s.id for s in template.body_sections + template.synthesis_sections]}\n"
            f"USER INPUTS: {composer_inputs}\n"
            f"USER PROMPT: {prompt}\n"
        )
        raw = await self._llm(CLARIFIER_SYSTEM, user_msg)
        data = json.loads(raw)
        return [ClarifyingQuestion(**q) for q in data.get("questions", [])]
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest packages/core/tests/runtime/test_clarifier.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write the route test**

Create `packages/server/tests/test_clarifier_route.py`:

```python
from fastapi.testclient import TestClient
from openlia_server.app import create_app


def test_clarifier_endpoint_returns_questions(authed_headers, monkeypatch):
    monkeypatch.setattr(
        "openlia_server.services.clarifier_service.run_clarifier",
        lambda *a, **kw: [{"id": "q1", "type": "text", "label": "?", "required": False}],
    )
    client = TestClient(create_app())
    r = client.post("/api/clarify", json={
        "template_id": "stock_initiation",
        "composer_inputs": {"ticker": "NVDA"},
        "prompt": "AMD comparison focus",
    }, headers=authed_headers)
    assert r.status_code == 200
    assert len(r.json()["questions"]) == 1
```

- [ ] **Step 6: Implement the route**

Create `packages/server/src/openlia_server/routes/clarifier.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openlia_server.services.clarifier_service import run_clarifier
from openlia_server.middleware.auth import get_current_user


router = APIRouter()


class ClarifyRequest(BaseModel):
    template_id: str
    composer_inputs: dict
    prompt: str


@router.post("/api/clarify")
async def clarify(req: ClarifyRequest, user=Depends(get_current_user)):
    questions = await run_clarifier(req.template_id, req.composer_inputs, req.prompt, user=user)
    return {"questions": [q.model_dump() if hasattr(q, "model_dump") else q for q in questions]}
```

And the service `services/clarifier_service.py` that resolves the template, instantiates `Clarifier` with the configured LLM client, runs it, returns the question list.

Register the router in `app.py`.

- [ ] **Step 7: Run route test**

Run: `uv run pytest packages/server/tests/test_clarifier_route.py -v`
Expected: 1 passed.

- [ ] **Step 8: Build `ClarifierModal.tsx`**

Create `frontend/src/components/templates/ClarifierModal.tsx`. The modal:
- Renders one input per question using `DynamicInputField` (text/enum/int/bool map to existing field types).
- Collects answers into `Record<string, unknown>`.
- "Continue" button submits answers; "Skip" button submits empty answers.
- Disables Continue until all `required` questions have answers.

- [ ] **Step 9: Wire composer**

Modify `Composer.tsx` so that on submit:
1. Call `POST /api/clarify` with `{template_id, composer_inputs, prompt}`.
2. If `questions.length > 0`, open `ClarifierModal` with the questions.
3. On modal continue, call `POST /api/reports` with `{template_id, composer_inputs, prompt, clarifications: {qid: answer}}`.

- [ ] **Step 10: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/clarifier.py \
        packages/server/src/openlia_server/routes/clarifier.py \
        packages/server/src/openlia_server/services/clarifier_service.py \
        frontend/src/components/templates/ClarifierModal.tsx \
        frontend/src/pages/EquityResearch/Composer.tsx \
        packages/core/tests/runtime/test_clarifier.py \
        packages/server/tests/test_clarifier_route.py
git commit -m "feat(runtime): one-shot pre-plan clarifier + modal"
```

**Risk:** Low — clarifier is opt-in via the composer flow; no runner-side changes yet.

---

### Task P3: Gather stage — parallel strand subagent dispatch

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/gather/__init__.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/gather/dispatcher.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/gather/strand_subagent.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/gather/research_pool.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` (call gather behind flag)
- Test: `packages/core/tests/runtime/test_gather.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/runtime/test_gather.py`:

```python
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.plan_types import Plan, ResearchStrand, DraftingDirectives
from openlia.llm.runtime.report_v2.gather.dispatcher import GatherDispatcher
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool, StrandResult


@pytest.mark.asyncio
async def test_dispatch_runs_strands_in_parallel():
    # Each "strand" returns a fixed StrandResult; dispatcher must collect all.
    async def fake_strand_runner(strand, tools):
        return StrandResult(
            strand_name=strand.name,
            findings_prose=f"findings for {strand.name}",
            citations=[],
            telemetry={"rounds": 1},
        )
    dispatcher = GatherDispatcher(run_strand=fake_strand_runner, tool_registry={"web_search": object()})
    plan = Plan(
        research_strands=[
            ResearchStrand(name="financials", purpose="...", tools_allowed=["web_search"]),
            ResearchStrand(name="news", purpose="...", tools_allowed=["web_search"]),
        ],
        model_components=[],
        drafting_directives=DraftingDirectives(),
        output_artifacts=[],
    )
    pool = await dispatcher.run(plan)
    assert isinstance(pool, ResearchPool)
    assert set(pool.results.keys()) == {"financials", "news"}


@pytest.mark.asyncio
async def test_one_strand_failure_does_not_sink_pool():
    async def fake_strand_runner(strand, tools):
        if strand.name == "news":
            raise RuntimeError("news source unavailable")
        return StrandResult(strand_name=strand.name, findings_prose="ok", citations=[], telemetry={})
    dispatcher = GatherDispatcher(run_strand=fake_strand_runner, tool_registry={"web_search": object()})
    plan = Plan(
        research_strands=[
            ResearchStrand(name="financials", purpose="...", tools_allowed=["web_search"]),
            ResearchStrand(name="news", purpose="...", tools_allowed=["web_search"]),
        ],
        model_components=[],
        drafting_directives=DraftingDirectives(),
        output_artifacts=[],
    )
    pool = await dispatcher.run(plan)
    assert "financials" in pool.results
    assert "news" in pool.failures
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_gather.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `ResearchPool` and `StrandResult`**

Create `packages/core/src/openlia/llm/runtime/report_v2/gather/research_pool.py`:

```python
from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.types import Citation


@dataclass
class StrandResult:
    strand_name: str
    findings_prose: str
    citations: list[Citation]
    telemetry: dict[str, Any]


@dataclass
class ResearchPool:
    results: dict[str, StrandResult] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)   # strand_name -> error message
```

- [ ] **Step 4: Implement the dispatcher**

Create `packages/core/src/openlia/llm/runtime/report_v2/gather/dispatcher.py`:

```python
import asyncio
import logging
from typing import Awaitable, Callable

from openlia.llm.runtime.report_v2.plan_types import Plan, ResearchStrand
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool, StrandResult


log = logging.getLogger(__name__)


class GatherDispatcher:
    def __init__(
        self,
        run_strand: Callable[[ResearchStrand, dict], Awaitable[StrandResult]],
        tool_registry: dict,
    ):
        self._run_strand = run_strand
        self._tools = tool_registry

    async def run(self, plan: Plan) -> ResearchPool:
        pool = ResearchPool()
        coros = [self._run_one(s) for s in plan.research_strands]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for strand, result in zip(plan.research_strands, results):
            if isinstance(result, Exception):
                log.warning("strand %s failed: %s", strand.name, result)
                pool.failures[strand.name] = str(result)
            else:
                pool.results[strand.name] = result
        return pool

    async def _run_one(self, strand: ResearchStrand) -> StrandResult:
        tools = {name: self._tools[name] for name in strand.tools_allowed if name in self._tools}
        return await self._run_strand(strand, tools)
```

- [ ] **Step 5: Implement the strand subagent**

Create `packages/core/src/openlia/llm/runtime/report_v2/gather/strand_subagent.py` that runs a multi-round tool-use loop with the strand's allocated tools, accumulates citations, and returns a `StrandResult`. System prompt:

```
You are a research strand subagent. Your purpose: {strand.purpose}.
Use the provided tools to gather concrete findings. After each tool call, reason about what you have and what gap remains.
When you have enough to satisfy your purpose, output:

```
FINDINGS:
<prose findings, citing tool results as [^N]>

CITATIONS:
[^1]: <source>
[^2]: <source>
```

Round cap: 8. If you hit it, output what you have.
```

Stop conditions: `FINDINGS:` block produced, or max-rounds hit, or tool error budget exceeded. Parse the structured output into `StrandResult`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest packages/core/tests/runtime/test_gather.py -v`
Expected: 2 passed.

- [ ] **Step 7: Wire runner.py behind the planner-pipeline flag**

In `runner.py`, when `_use_planner_pipeline=True`: after `Plan` is built, instantiate `GatherDispatcher` with the configured strand subagent runner and the user's connected MCP tools (from `connectors_service`), call `dispatcher.run(plan)`, stash the `ResearchPool` on the run context.

Do NOT remove the legacy facts path yet. Both paths coexist behind the flag.

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/gather/ \
        packages/core/src/openlia/llm/runtime/report_v2/runner.py \
        packages/core/tests/runtime/test_gather.py
git commit -m "feat(runtime): parallel strand gather dispatcher (flagged off)"
```

**Risk:** Medium — coordinating async subagents over user-installed MCP tools is the most likely place for runtime instability. Mitigation: failure isolation per strand; legacy path untouched.

---

### Task P4: Build-model stage — model-analyst subagent

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/model_builder.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/model_artifact.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/runner.py`
- Test: `packages/core/tests/runtime/test_model_builder.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/runtime/test_model_builder.py`:

```python
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.plan_types import Plan, ModelComponentPlan, DraftingDirectives
from openlia.llm.runtime.report_v2.model_builder import ModelBuilder
from openlia.llm.runtime.report_v2.model_artifact import ModelArtifact
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool, StrandResult


@pytest.mark.asyncio
async def test_model_builder_runs_declared_components_only():
    called = []
    async def fake_helper_runner(helper_id, args, research_pool):
        called.append(helper_id)
        return {"value": 1.0, "assumptions": args, "citations": []}
    builder = ModelBuilder(run_helper=fake_helper_runner)
    plan = Plan(
        research_strands=[],
        model_components=[
            ModelComponentPlan(helper_id="three_scenario_forecast", assumption_overrides={"horizon_years": 3}),
            ModelComponentPlan(helper_id="dcf", assumption_overrides={"wacc": 0.12}),
        ],
        drafting_directives=DraftingDirectives(),
        output_artifacts=[],
    )
    pool = ResearchPool(results={"financials": StrandResult("financials", "...", [], {})})
    artifact = await builder.run(plan, pool)
    assert isinstance(artifact, ModelArtifact)
    assert set(called) == {"three_scenario_forecast", "dcf"}
    assert "three_scenario_forecast" in artifact.slots
    assert artifact.slots["dcf"]["assumptions"]["wacc"] == 0.12
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_model_builder.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `ModelArtifact`**

Create `packages/core/src/openlia/llm/runtime/report_v2/model_artifact.py`:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelArtifact:
    slots: dict[str, Any] = field(default_factory=dict)         # helper_id -> result
    failures: dict[str, str] = field(default_factory=dict)      # helper_id -> error message
```

- [ ] **Step 4: Implement `ModelBuilder`**

Create `packages/core/src/openlia/llm/runtime/report_v2/model_builder.py`:

```python
import asyncio
import logging
from typing import Awaitable, Callable

from openlia.llm.runtime.report_v2.plan_types import Plan
from openlia.llm.runtime.report_v2.model_artifact import ModelArtifact
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool


log = logging.getLogger(__name__)


class ModelBuilder:
    def __init__(self, run_helper: Callable[[str, dict, ResearchPool], Awaitable[dict]]):
        self._run = run_helper

    async def run(self, plan: Plan, pool: ResearchPool) -> ModelArtifact:
        artifact = ModelArtifact()
        coros = [self._run_one(c.helper_id, c.assumption_overrides, pool) for c in plan.model_components]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for component, result in zip(plan.model_components, results):
            if isinstance(result, Exception):
                log.warning("helper %s failed: %s", component.helper_id, result)
                artifact.failures[component.helper_id] = str(result)
            else:
                artifact.slots[component.helper_id] = result
        return artifact

    async def _run_one(self, helper_id: str, args: dict, pool: ResearchPool) -> dict:
        return await self._run(helper_id, args, pool)
```

The `run_helper` callback is supplied by the runner and bridges to the v1 helper registry (`tools/registry.py`). Each helper receives the `ResearchPool` so it can extract its inputs from the prose findings; helpers that need typed numeric inputs may either (a) parse them from research pool prose using a small LLM extraction call, or (b) accept them via `args` if the planner pre-computed them.

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/core/tests/runtime/test_model_builder.py -v`
Expected: 1 passed.

- [ ] **Step 6: Wire runner.py**

After `GatherDispatcher` completes, instantiate `ModelBuilder` with a helper-runner that resolves helpers from the v1 registry. Stash the `ModelArtifact` on the run context.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/model_builder.py \
        packages/core/src/openlia/llm/runtime/report_v2/model_artifact.py \
        packages/core/src/openlia/llm/runtime/report_v2/runner.py \
        packages/core/tests/runtime/test_model_builder.py
git commit -m "feat(runtime): model-analyst stage + ModelArtifact (flagged off)"
```

**Risk:** Medium — helper inputs are loose under the research-notes pipeline. Worth a per-helper audit to confirm which helpers can run on (args + pool) without typed Facts.

---

### Task P5: Draft adaptation — section subagents read pool + artifact

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/sections/dispatcher.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/sections/prompts.py`
- Test: `packages/core/tests/runtime/test_section_dispatch_v2.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/runtime/test_section_dispatch_v2.py`:

```python
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.sections.dispatcher import dispatch_section_v2
from openlia.llm.runtime.report_v2.plan_types import Plan, DraftingDirectives
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool, StrandResult
from openlia.llm.runtime.report_v2.model_artifact import ModelArtifact
from openlia.reports.frameworks.template_spec import SectionSpec


@pytest.mark.asyncio
async def test_section_prompt_includes_global_directive_and_pool_and_artifact():
    captured_prompt = {}
    async def fake_section_llm(system, user):
        captured_prompt["system"] = system
        captured_prompt["user"] = user
        return "## Section\nbody text"
    section = SectionSpec(id="overview", title="Overview", brief="describe the company")
    pool = ResearchPool(results={"financials": StrandResult("financials", "revenue $50B", [], {})})
    artifact = ModelArtifact(slots={"three_scenario_forecast": {"neutral": [50, 55, 60]}})
    plan = Plan(
        research_strands=[],
        model_components=[],
        drafting_directives=DraftingDirectives(global_directive="focus on AMD comparison"),
        output_artifacts=[],
    )
    await dispatch_section_v2(section, plan, pool, artifact, llm_call=fake_section_llm)
    assert "focus on AMD comparison" in captured_prompt["user"]
    assert "revenue $50B" in captured_prompt["user"]
    assert "three_scenario_forecast" in captured_prompt["user"]
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_section_dispatch_v2.py -v`
Expected: ImportError on `dispatch_section_v2`.

- [ ] **Step 3: Implement v2 prompt assembly**

Add to `packages/core/src/openlia/llm/runtime/report_v2/sections/prompts.py`:

```python
from openlia.llm.runtime.report_v2.plan_types import Plan
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool
from openlia.llm.runtime.report_v2.model_artifact import ModelArtifact
from openlia.reports.frameworks.template_spec import SectionSpec


def assemble_section_prompt_v2(
    section: SectionSpec,
    plan: Plan,
    pool: ResearchPool,
    artifact: ModelArtifact,
) -> str:
    pool_block = "\n\n".join(
        f"### Strand: {name}\n{result.findings_prose}"
        for name, result in pool.results.items()
    )
    artifact_block = "\n\n".join(
        f"### {helper_id}\n{value}"
        for helper_id, value in artifact.slots.items()
    )
    parts = [
        f"# Section: {section.title}",
        "",
        "## Brief",
        section.brief,
        "",
        "## User Directive",
        plan.drafting_directives.global_directive or "(none)",
        "",
        "## Research Pool",
        pool_block or "(empty)",
        "",
        "## Model Artifact",
        artifact_block or "(empty)",
    ]
    per_section = plan.drafting_directives.per_section.get(section.id)
    if per_section and per_section.emphasis:
        parts += ["", "## Per-Section Emphasis", per_section.emphasis]
    return "\n".join(parts)
```

- [ ] **Step 4: Implement v2 dispatch**

Add to `packages/core/src/openlia/llm/runtime/report_v2/sections/dispatcher.py`:

```python
from openlia.llm.runtime.report_v2.sections.prompts import assemble_section_prompt_v2


async def dispatch_section_v2(section, plan, pool, artifact, llm_call):
    system = "You are a research section writer."
    user = assemble_section_prompt_v2(section, plan, pool, artifact)
    return await llm_call(system, user)
```

The full v2 dispatcher also keeps the per-section retry loop from v1 — wrap `llm_call` with the same `_retry_with_feedback` wrapper used today.

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/core/tests/runtime/test_section_dispatch_v2.py -v`
Expected: 1 passed.

- [ ] **Step 6: Wire runner.py**

When `_use_planner_pipeline=True`, the body+synthesis dispatch loops call `dispatch_section_v2` instead of `dispatch_section` (the v1 facts-driven path).

- [ ] **Step 7: End-to-end smoke against `stock_initiation`**

Flip the flag on for a single test run against `stock_initiation` for AAPL with a stub LLM (or against the real LLM in a CI-skipped integration test). Confirm a non-crashing report.

Run: `uv run pytest packages/core/tests/runtime/test_e2e_planner_pipeline.py -v -k aapl_stock_initiation`
Expected: passes (or marked `xfail` until verifier lands in P6 if assembly fails).

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/sections/ \
        packages/core/src/openlia/llm/runtime/report_v2/runner.py \
        packages/core/tests/runtime/test_section_dispatch_v2.py
git commit -m "feat(runtime): section dispatch reads research pool + model artifact"
```

**Risk:** High — this is the bridge between Phase 2's new stages and the existing renderer. Identical-output smoke is no longer applicable; coherence is verified manually for the first run.

---

### Task P6: Verify stage rebuild

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/verifier/__init__.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/verifier/llm_verifier.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/validators/numeric_consistency.py` (delete the v1 typed-Fact checks that no longer apply)
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/types.py` (new `DEGRADED_VERIFIER_FAIL` terminal state)
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` (wire verifier + retry feedback)
- Create: `packages/server/src/openlia_server/services/verifier_service.py`
- Test: `packages/core/tests/runtime/test_verifier.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/runtime/test_verifier.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.verifier.llm_verifier import LLMVerifier, VerifierIssue
from openlia.llm.runtime.report_v2.plan_types import Plan, DraftingDirectives, OutputArtifactPlan
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool, StrandResult
from openlia.llm.runtime.report_v2.model_artifact import ModelArtifact


@pytest.mark.asyncio
async def test_verifier_returns_no_issues_when_clean():
    llm = AsyncMock(return_value=json.dumps({"issues": []}))
    v = LLMVerifier(llm_call=llm)
    plan = Plan(research_strands=[], model_components=[], drafting_directives=DraftingDirectives(), output_artifacts=[])
    issues = await v.run(draft_markdown="...", plan=plan, pool=ResearchPool(), artifact=ModelArtifact())
    assert issues == []


@pytest.mark.asyncio
async def test_verifier_flags_missing_required_artifact():
    llm = AsyncMock(return_value=json.dumps({"issues": [
        {"issue_type": "missing_artifact", "section_id": None, "severity": "high",
         "evidence": "Required artifact 'guidance_trend' not present in draft"}
    ]}))
    v = LLMVerifier(llm_call=llm)
    plan = Plan(
        research_strands=[], model_components=[],
        drafting_directives=DraftingDirectives(),
        output_artifacts=[OutputArtifactPlan(name="guidance_trend", type="table", required=True, source="strand")],
    )
    issues = await v.run(draft_markdown="(empty)", plan=plan, pool=ResearchPool(), artifact=ModelArtifact())
    assert len(issues) == 1
    assert issues[0].issue_type == "missing_artifact"


@pytest.mark.asyncio
async def test_verifier_issues_route_to_affected_section_for_retry():
    llm = AsyncMock(return_value=json.dumps({"issues": [
        {"issue_type": "uncited_claim", "section_id": "overview", "severity": "high",
         "evidence": "Claim 'revenue grew 40%' has no citation."}
    ]}))
    v = LLMVerifier(llm_call=llm)
    plan = Plan(research_strands=[], model_components=[], drafting_directives=DraftingDirectives(), output_artifacts=[])
    issues = await v.run(draft_markdown="...", plan=plan, pool=ResearchPool(), artifact=ModelArtifact())
    by_section = {i.section_id: i for i in issues}
    assert "overview" in by_section
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_verifier.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `LLMVerifier`**

Create `packages/core/src/openlia/llm/runtime/report_v2/verifier/llm_verifier.py`:

```python
import json
from typing import Awaitable, Callable, Literal
from pydantic import BaseModel

from openlia.llm.runtime.report_v2.plan_types import Plan
from openlia.llm.runtime.report_v2.gather.research_pool import ResearchPool
from openlia.llm.runtime.report_v2.model_artifact import ModelArtifact


Severity = Literal["low", "medium", "high"]
IssueType = Literal[
    "uncited_claim", "cross_section_disagreement", "missing_artifact",
    "scenario_incoherent", "hallucination_suspected",
]


class VerifierIssue(BaseModel):
    issue_type: IssueType
    section_id: str | None
    severity: Severity
    evidence: str


VERIFIER_SYSTEM = """You are a research-report verifier. Given:
- the draft markdown
- the research pool (per-strand findings + citations)
- the model artifact (computed model components)
- the plan's required output artifacts

Surface issues. Categories:
  - uncited_claim: a numeric or factual claim in the draft has no supporting citation.
  - cross_section_disagreement: two sections disagree on the same number or claim.
  - missing_artifact: a required output_artifact is absent from the draft.
  - scenario_incoherent: bull/base/bear scenarios contradict each other or the model artifact.
  - hallucination_suspected: a claim cannot be traced to research pool or model artifact.

Tag each issue with section_id when applicable, severity (low/medium/high), and evidence (one sentence quoting or pointing to the offending passage).
Return JSON: {"issues": [...]}. Empty list if clean."""


class LLMVerifier:
    def __init__(self, llm_call: Callable[[str, str], Awaitable[str]]):
        self._llm = llm_call

    async def run(
        self,
        draft_markdown: str,
        plan: Plan,
        pool: ResearchPool,
        artifact: ModelArtifact,
    ) -> list[VerifierIssue]:
        user = (
            "## DRAFT\n" + draft_markdown +
            "\n\n## RESEARCH POOL\n" + self._pool_block(pool) +
            "\n\n## MODEL ARTIFACT\n" + self._artifact_block(artifact) +
            "\n\n## REQUIRED ARTIFACTS\n" + json.dumps([a.model_dump() for a in plan.output_artifacts])
        )
        raw = await self._llm(VERIFIER_SYSTEM, user)
        data = json.loads(raw)
        return [VerifierIssue(**i) for i in data.get("issues", [])]

    @staticmethod
    def _pool_block(pool: ResearchPool) -> str:
        return "\n\n".join(f"### {name}\n{r.findings_prose}" for name, r in pool.results.items())

    @staticmethod
    def _artifact_block(artifact: ModelArtifact) -> str:
        return "\n\n".join(f"### {h}\n{v}" for h, v in artifact.slots.items())
```

- [ ] **Step 4: Delete obsoleted v1 validators**

In `packages/core/src/openlia/llm/runtime/report_v2/validators/numeric_consistency.py`:
- Remove `_check_identity_equations` (typed Facts gone).
- Remove `_check_first_person` (replaced by per-section voice flag in v1 PR 5 — confirm it remains usable as-is or remove if it depended on typed Facts).
- Keep `_check_numeric_not_in_facts` only if it still has substrate — under research-notes-only, it may degrade or be removed.
- Keep `_check_year_labels` (template-agnostic).

Run grep to find call sites and delete the dead wiring.

- [ ] **Step 5: Add `DEGRADED_VERIFIER_FAIL` terminal state**

In `packages/core/src/openlia/llm/runtime/report_v2/types.py`:

```python
class SectionTerminalState(Enum):
    # ...existing...
    DEGRADED_VERIFIER_FAIL = "degraded_verifier_fail"
```

- [ ] **Step 6: Wire verifier into the runner**

In `runner.py`, after all sections complete:

```python
issues = await self._verifier.run(draft, plan, pool, artifact)
critical_by_section = self._group_critical_issues(issues)
for section_id, section_issues in critical_by_section.items():
    if self._retry_count[section_id] < self._max_verifier_retries:
        await self._redispatch_section(section_id, feedback=section_issues)
    else:
        self._mark_terminal(section_id, SectionTerminalState.DEGRADED_VERIFIER_FAIL)
```

`_max_verifier_retries = 3` by default. Redispatch passes the verifier issues as feedback to the section subagent.

- [ ] **Step 7: Run tests**

Run: `uv run pytest packages/core/tests/runtime/test_verifier.py packages/core/tests/runtime/ -q`
Expected: verifier tests pass; remaining runtime tests pass.

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/verifier/ \
        packages/core/src/openlia/llm/runtime/report_v2/validators/numeric_consistency.py \
        packages/core/src/openlia/llm/runtime/report_v2/types.py \
        packages/core/src/openlia/llm/runtime/report_v2/runner.py \
        packages/core/tests/runtime/test_verifier.py
git commit -m "feat(runtime): hybrid verifier (deterministic survivors + LLM verifier) with retry feedback"
```

**Risk:** High — this PR also deletes v1 validators that depended on typed Facts. Verify each removal against grep + the existing test suite before merging.

---

### Task P7: Conditional dispatch — `trigger_when` + LLM trigger evaluator

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/triggers/__init__.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/triggers/trigger_evaluator.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/sections/dispatcher.py` (call evaluator before dispatch)
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` (track section completion for `depends_on`)
- Test: `packages/core/tests/runtime/test_trigger_evaluator.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/runtime/test_trigger_evaluator.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.triggers.trigger_evaluator import TriggerEvaluator


@pytest.mark.asyncio
async def test_trigger_true_dispatches():
    llm = AsyncMock(return_value=json.dumps({"fire": True, "reason": "Scorecard says 2 stars."}))
    e = TriggerEvaluator(llm_call=llm)
    fire = await e.evaluate(
        condition="scorecard rating below three stars",
        dependency_markdown={"scorecard": "Final rating: ★★"},
    )
    assert fire is True


@pytest.mark.asyncio
async def test_trigger_false_skips():
    llm = AsyncMock(return_value=json.dumps({"fire": False, "reason": "Scorecard says 4 stars."}))
    e = TriggerEvaluator(llm_call=llm)
    fire = await e.evaluate(
        condition="scorecard rating below three stars",
        dependency_markdown={"scorecard": "Final rating: ★★★★"},
    )
    assert fire is False
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_trigger_evaluator.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `TriggerEvaluator`**

Create `packages/core/src/openlia/llm/runtime/report_v2/triggers/trigger_evaluator.py`:

```python
import json
from typing import Awaitable, Callable


TRIGGER_SYSTEM = """You evaluate a free-text trigger condition against the markdown of one or more dependency sections.
Output JSON: {"fire": true|false, "reason": "<one sentence>"}.
Be conservative: fire only when the condition is clearly satisfied."""


class TriggerEvaluator:
    def __init__(self, llm_call: Callable[[str, str], Awaitable[str]]):
        self._llm = llm_call

    async def evaluate(self, condition: str, dependency_markdown: dict[str, str]) -> bool:
        deps_block = "\n\n".join(f"### {name}\n{md}" for name, md in dependency_markdown.items())
        user = f"CONDITION: {condition}\n\nDEPENDENCY SECTIONS:\n{deps_block}"
        raw = await self._llm(TRIGGER_SYSTEM, user)
        data = json.loads(raw)
        return bool(data.get("fire", False))
```

- [ ] **Step 4: Wire into the dispatcher**

In `sections/dispatcher.py`, before dispatching each section:

```python
if section.trigger_when:
    deps = {sid: completed_sections[sid] for sid in section.depends_on if sid in completed_sections}
    if not deps and section.depends_on:
        # depends_on not yet complete — defer this section
        defer(section)
        continue
    fire = await trigger_evaluator.evaluate(section.trigger_when, deps)
    if not fire:
        record_skip(section, reason="trigger_when evaluated false")
        continue
```

The runner becomes responsible for tracking `completed_sections: dict[section_id, markdown]` and ordering dispatch so `depends_on` are satisfied before evaluation.

- [ ] **Step 5: Add a test that triggers gate dispatch in the runner**

Add a fixture template with a section that has `trigger_when: "x"` and `depends_on: ["dep"]`. Stub `TriggerEvaluator` to return False. Run a full pipeline. Assert the gated section appears as a skip-banner block in the rendered output and the dependency section ran normally.

- [ ] **Step 6: Run tests**

Run: `uv run pytest packages/core/tests/runtime/test_trigger_evaluator.py packages/core/tests/runtime/ -q`
Expected: trigger tests pass; other runtime tests still pass.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/triggers/ \
        packages/core/src/openlia/llm/runtime/report_v2/sections/dispatcher.py \
        packages/core/src/openlia/llm/runtime/report_v2/runner.py \
        packages/core/tests/runtime/test_trigger_evaluator.py
git commit -m "feat(runtime): trigger_when + LLM trigger evaluator for conditional sections"
```

**Risk:** Medium. Dispatch order with `depends_on` introduces partial ordering; ensure no deadlocks (a template with a `depends_on` cycle should fail at template-load time with a clear error).

---

## Phase 3 — Output + strand templates

### Task O1: `.docx` renderer (parallel native + on-demand)

**Files:**
- Create: `packages/core/src/openlia/reports/render/docx_renderer.py`
- Modify: each block file in `packages/core/src/openlia/reports/render/blocks/*.py` to add a `render_docx` method
- Create: `packages/server/src/openlia_server/routes/docx.py`
- Modify: `frontend/src/pages/Reports/ReportViewer.tsx` (download button)
- Test: `packages/core/tests/render/test_docx.py` (new)

- [ ] **Step 1: Audit existing block types**

Run: `ls packages/core/src/openlia/reports/render/blocks/`
Note each block file (paragraph, heading, table, chart, citation, etc.). Each needs a `render_docx` method.

- [ ] **Step 2: Write the failing test**

Create `packages/core/tests/render/test_docx.py`:

```python
import io
from docx import Document
from openlia.reports.render.docx_renderer import render_report_to_docx
from openlia.reports.render.blocks import ParagraphBlock, HeadingBlock, TableBlock


def test_paragraph_renders_to_docx():
    blocks = [HeadingBlock(level=1, text="Title"), ParagraphBlock(text="Hello world")]
    buf = io.BytesIO()
    render_report_to_docx(blocks, buf)
    buf.seek(0)
    doc = Document(buf)
    assert doc.paragraphs[0].text == "Title"
    assert doc.paragraphs[1].text == "Hello world"


def test_table_renders_to_docx():
    blocks = [TableBlock(headers=["Q", "Rev"], rows=[["Q1", "$50B"], ["Q2", "$55B"]])]
    buf = io.BytesIO()
    render_report_to_docx(blocks, buf)
    buf.seek(0)
    doc = Document(buf)
    table = doc.tables[0]
    assert table.cell(0, 0).text == "Q"
    assert table.cell(1, 1).text == "$50B"
```

- [ ] **Step 3: Run test to verify failure**

Run: `uv run pytest packages/core/tests/render/test_docx.py -v`
Expected: ImportError on `render_report_to_docx`.

- [ ] **Step 4: Add `python-docx` dependency**

Run: `uv add python-docx`

- [ ] **Step 5: Implement `docx_renderer.py`**

Create `packages/core/src/openlia/reports/render/docx_renderer.py`:

```python
from typing import BinaryIO
from docx import Document
from openlia.reports.render.blocks import Block


def render_report_to_docx(blocks: list[Block], output: BinaryIO) -> None:
    doc = Document()
    for block in blocks:
        block.render_docx(doc)
    doc.save(output)
```

- [ ] **Step 6: Add `render_docx` to each block type**

For each block file in `blocks/`, add a `render_docx(self, doc)` method.

`ParagraphBlock`:
```python
def render_docx(self, doc):
    doc.add_paragraph(self.text)
```

`HeadingBlock`:
```python
def render_docx(self, doc):
    doc.add_heading(self.text, level=self.level)
```

`TableBlock`:
```python
def render_docx(self, doc):
    table = doc.add_table(rows=1 + len(self.rows), cols=len(self.headers))
    for col, header in enumerate(self.headers):
        table.cell(0, col).text = header
    for row_idx, row in enumerate(self.rows, start=1):
        for col, value in enumerate(row):
            table.cell(row_idx, col).text = str(value)
```

`ChartBlock`:
```python
def render_docx(self, doc):
    # render chart to PNG bytes via existing matplotlib path
    png = self._render_png()
    doc.add_picture(io.BytesIO(png))
```

`CitationBlock`:
```python
def render_docx(self, doc):
    p = doc.add_paragraph()
    p.add_run(f"[{self.ref_id}] ").bold = True
    p.add_run(self.text)
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest packages/core/tests/render/test_docx.py -v`
Expected: 2 passed.

- [ ] **Step 8: Add the server route**

Create `packages/server/src/openlia_server/routes/docx.py`:

```python
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openlia.reports.render.docx_renderer import render_report_to_docx
from openlia_server.services.reports import load_report_blocks
from openlia_server.middleware.auth import get_current_user


router = APIRouter()


@router.get("/api/reports/{report_id}/download.docx")
async def download_docx(report_id: str, user=Depends(get_current_user)):
    blocks = await load_report_blocks(report_id, user=user)
    if blocks is None:
        raise HTTPException(404)
    buf = io.BytesIO()
    render_report_to_docx(blocks, buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.docx"'},
    )
```

Register the router in `app.py`.

- [ ] **Step 9: Add the download button to ReportViewer.tsx**

In `frontend/src/pages/Reports/ReportViewer.tsx`, add:

```tsx
<a href={`/api/reports/${reportId}/download.docx`} download>
  Download as .docx
</a>
```

Place alongside the existing PDF download.

- [ ] **Step 10: Commit**

```bash
git add packages/core/src/openlia/reports/render/docx_renderer.py \
        packages/core/src/openlia/reports/render/blocks/ \
        packages/server/src/openlia_server/routes/docx.py \
        frontend/src/pages/Reports/ReportViewer.tsx \
        packages/core/tests/render/test_docx.py \
        pyproject.toml uv.lock
git commit -m "feat(render): .docx output via per-block render_docx, on-demand download"
```

**Risk:** Low. New code; existing renderer untouched.

---

### Task O2: Default templates declare `composer_inputs` + `output_artifacts`

**Files:**
- Modify: `packages/core/src/openlia/reports/frameworks/loaders/stock_initiation.py`
- Modify: `packages/core/src/openlia/reports/frameworks/loaders/stock_research.py`
- Modify: `packages/core/src/openlia/reports/frameworks/loaders/sector_research.py`
- Test: `packages/core/tests/frameworks/test_default_templates_v2_surface.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/frameworks/test_default_templates_v2_surface.py`:

```python
import pytest
from openlia.reports.frameworks.registry import default_registry
from openlia.reports.frameworks.loaders import stock_initiation, stock_research, sector_research  # noqa


@pytest.mark.parametrize("template_id", ["stock_initiation", "stock_research", "sector_research"])
def test_template_has_composer_inputs(template_id):
    spec = default_registry.get(template_id)
    assert len(spec.composer_inputs) > 0


def test_stock_initiation_has_transcript_window_input():
    spec = default_registry.get("stock_initiation")
    names = {i.name for i in spec.composer_inputs}
    assert "transcript_window" in names


def test_stock_initiation_declares_guidance_trend_artifact():
    spec = default_registry.get("stock_initiation")
    artifact_names = {a.name for a in spec.output_artifacts}
    assert "guidance_trend" in artifact_names
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/frameworks/test_default_templates_v2_surface.py -v`
Expected: failures on `transcript_window` / `guidance_trend` absence.

- [ ] **Step 3: Add declarations to `stock_initiation.py`**

In the loader:

```python
composer_inputs=[
    ComposerInputSpec(name="ticker", type="ticker", label="Ticker", required=True, validator_id="ticker_resolver"),
    ComposerInputSpec(name="transcript_window", type="int", label="Transcript window (quarters)", required=False, default=4),
],
output_artifacts=[
    OutputArtifactSpec(
        name="guidance_trend",
        type="table",
        required=False,
        source="strand",
        schema_hint={"columns": ["quarter", "guidance", "actual", "delta"]},
    ),
],
```

- [ ] **Step 4: Add to `stock_research.py`**

```python
composer_inputs=[
    ComposerInputSpec(name="ticker", type="ticker", label="Ticker", required=True, validator_id="ticker_resolver"),
],
```

- [ ] **Step 5: Add to `sector_research.py`**

```python
composer_inputs=[
    ComposerInputSpec(name="sector", type="sector", label="Sector", required=True, validator_id="sector_enum"),
    ComposerInputSpec(name="peer_tickers", type="ticker_list", label="Peer tickers (optional)", required=False),
],
output_artifacts=[
    OutputArtifactSpec(name="peer_comparison", type="table", required=False, source="strand",
                      schema_hint={"columns": ["ticker", "market_cap", "revenue_ttm", "growth_ttm"]}),
],
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest packages/core/tests/frameworks/test_default_templates_v2_surface.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/reports/frameworks/loaders/ \
        packages/core/tests/frameworks/test_default_templates_v2_surface.py
git commit -m "feat(templates): default templates declare composer_inputs + output_artifacts"
```

**Risk:** Low — pure config additions.

---

### Task O3: Investor-Day + transcript strand support on default templates

**Files:**
- Modify: `packages/core/src/openlia/reports/frameworks/loaders/stock_initiation.py` (add output_artifacts for investor_day_comparison)
- Update: `packages/core/src/openlia/reports/frameworks/stock_initiation_briefs.md` (sections that reference these strands' findings get prose updates)
- Test: `packages/core/tests/runtime/test_planner_allocates_special_strands.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/runtime/test_planner_allocates_special_strands.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock
from openlia.llm.runtime.report_v2.planner import Planner
from openlia.reports.frameworks.registry import default_registry


@pytest.mark.asyncio
async def test_planner_allocates_transcript_strand_when_window_provided():
    plan_json = {
        "research_strands": [
            {"name": "transcripts", "purpose": "last 4 quarters earnings calls",
             "tools_allowed": ["mcp__transcripts__get"], "expected_artifacts": ["guidance_trend"]},
        ],
        "model_components": [],
        "drafting_directives": {"global_directive": "", "per_section": {}},
        "output_artifacts": [{"name": "guidance_trend", "type": "table", "required": False, "source": "strand"}],
    }
    llm = AsyncMock(return_value=json.dumps(plan_json))
    planner = Planner(llm_call=llm)
    plan = await planner.run(
        template=default_registry.get("stock_initiation"),
        composer_inputs={"ticker": "NVDA", "transcript_window": 4},
        prompt="",
        clarifications=[],
        available_tools=["mcp__transcripts__get"],
    )
    assert any(s.name == "transcripts" for s in plan.research_strands)
    assert any(a.name == "guidance_trend" for a in plan.output_artifacts)
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest packages/core/tests/runtime/test_planner_allocates_special_strands.py -v`
Expected: fails because no `investor_day_comparison` artifact is declared on `stock_initiation`.

- [ ] **Step 3: Add `investor_day_comparison` artifact to stock_initiation**

In `stock_initiation.py` loader, append to `output_artifacts`:

```python
OutputArtifactSpec(
    name="investor_day_comparison",
    type="table",
    required=False,
    source="strand",
    schema_hint={"columns": ["target_year", "stated_target", "actual_outcome", "hit_miss"]},
),
```

- [ ] **Step 4: Update briefs to reference the artifacts**

In `stock_initiation_briefs.md`, find the section that discusses management track record / guidance discipline. Add prose like:

> When `investor_day_comparison` is present in the artifact pool, embed it directly under the discussion of management's prior commitments. Cite each row.

> When `guidance_trend` is present, embed it under the earnings-call section and discuss the directional trend.

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/core/tests/runtime/test_planner_allocates_special_strands.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/reports/frameworks/loaders/stock_initiation.py \
        packages/core/src/openlia/reports/frameworks/stock_initiation_briefs.md \
        packages/core/tests/runtime/test_planner_allocates_special_strands.py
git commit -m "feat(templates): stock_initiation declares investor_day_comparison + transcript_trend artifacts"
```

**Risk:** Low — additive surface; strands only run when planner allocates them and the user has matching tools connected.

---

## Phase 4 — Validation pass

After all PRs land, run the validation sweep end-to-end before declaring v2 done.

### Task V1: End-to-end smoke per default template

- [ ] **Step 1: Enable the planner pipeline flag globally**

In a feature-flag config or env: `OPENLIA_PIPELINE=planner`.

Run: `OPENLIA_PIPELINE=planner uv run openlia serve`

- [ ] **Step 2: stock_initiation smoke**

Submit a `stock_initiation` report against AAPL with prompt "focus on services revenue trajectory". Confirm: report generates, all sections present, services-revenue thread visible.

- [ ] **Step 3: stock_research smoke**

Submit against MSFT with prompt "quick-look read on AI infra spend". Confirm: report generates, quick-look section shape.

- [ ] **Step 4: sector_research smoke**

Submit against sector "Semiconductors" with peer_tickers [NVDA, AMD, INTC, TSM]. Confirm: report generates, peer-comparison table appears.

- [ ] **Step 5: Custom template smoke**

Upload a minimal user template with 3 sections, 2 strands declared, 1 model component. Run against any ticker. Confirm: report generates, no crashes.

### Task V2: Trigger-skip test

- [ ] **Step 1: Upload a template with `trigger_when` on one section**

Section A computes a "rating". Section B has `trigger_when: "rating below 3 stars"` and `depends_on: ["A"]`.

- [ ] **Step 2: Run twice**

Run with a ticker that yields a high rating (B should skip with banner) and a ticker that yields a low rating (B should fire).

### Task V3: `.docx` round-trip

- [ ] **Step 1: Generate a report**
- [ ] **Step 2: Download `.docx` from the report viewer**
- [ ] **Step 3: Open in Word and confirm**
  - Headings present with correct levels
  - Tables editable
  - Charts visible as images
  - Citations rendered as paragraphs

---

## Self-review

**Spec coverage check:**

- Section 1 (eight-stage pipeline) — Tasks P1 (plan) + P2 (clarify) + P3 (gather) + P4 (model) + P5 (draft) + P6 (verify). Assemble stage is unchanged from v1. ✓
- Section 2.1 (Plan schema) — Task P1. ✓
- Section 3.1 (composer redesign) — Tasks F1 + F2. ✓
- Section 3.2 (mode collapse) — Tasks F3 + F4. ✓
- Section 4.1 (conditional dispatch) — Task P7. ✓
- Section 4.2 (`.docx` output) — Task O1. ✓
- Section 4.3 (transcript strand) — Tasks O2 + O3. ✓
- Section 4.4 (investor-day strand) — Tasks O2 + O3. ✓
- Section 5 (hardcoding audit) — Embedded in F1's schema additions + planner-allocated strands in P1. ✓
- Section 6 (out of scope) — No tasks needed (explicitly excluded). ✓
- Section 7 (PR sequencing) — Mirrors Phase 1/2/3 here. ✓
- Section 8 (backward compatibility) — Legacy `ticker` field in F2; removed in F4. ✓
- Section 9 (testing strategy) — Per-PR tests + V1/V2/V3 sweep. ✓
- Section 10 (success criteria) — Phase 4 validation pass covers all criteria. ✓
- Section 11 (open implementation questions) — Planner/clarifier/verifier prompts written inline in P1/P2/P6. MCP-tool manifest is read from existing `connectors_service` (referenced in P1 and P3). Composer-inputs validator registry: ticker resolver exists; sector enum stubbed in F4 with the option to harden later. ✓

**Placeholder scan:** No "TBD" / "TODO" / "fill in details" strings. Two intentional `# copy from existing` markers in F3/F4 loader stubs — these direct the engineer to grep the existing source for the constants to lift. Acceptable for a lift PR.

**Type consistency check:**

- `ComposerInputSpec` shape matches between F1 (definition), F2 (consumed by route), and F3/F4 (used by loaders). ✓
- `Plan` shape matches between P1 (definition) and P3/P4/P5/P6/P7 (consumers). ✓
- `ResearchPool` / `StrandResult` shapes match between P3 (definition) and P4/P5/P6 (consumers). ✓
- `ModelArtifact.slots` access pattern (`artifact.slots[helper_id]`) matches between P4 (definition) and P5/P6 (consumers). ✓
- `VerifierIssue` shape matches between P6 (definition) and the retry-feedback consumer in `runner.py` (also P6). ✓
- `SectionTerminalState.DEGRADED_VERIFIER_FAIL` added in P6 and only referenced in P6. ✓

No type drift found.
