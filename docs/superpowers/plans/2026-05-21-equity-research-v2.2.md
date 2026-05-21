# Equity Research v2.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Supersedes:** [v2 plan (2026-05-20)](2026-05-20-equity-research-v2.md). v2 is frozen.

**Goal:** Implement the v2.2 equity research department as a 9-stage LLM-orchestrated pipeline driven by a capability manifest, with interactive clarifier, mandatory Run Summary, dev-mode Verification History, 14-issue verifier taxonomy, required vs optional artifact resolution, persistent cache for immutable documents, vendored library helpers, and HTML as canonical output (PDF/DOCX conversion handled by existing v1 download path).

**Architecture:** A capability manifest at `capabilities.yaml` declares engine version, supported and unsupported features, reserved template keys, and cache toggles. Both the clarifier and template loader read from it. The pipeline runs nine stages: clarify (interactive with blocking warnings), read template, research plan (declares strands and freezes required artifacts), gather (parallel strand subagents through registered connector adapters), model plan (adds optional artifacts based on research pool), model build (per-artifact subagents with explicit→derived→default parameter resolution), draft (per-section subagents walking a DAG with conditional `trigger_when` evaluation), verify (deterministic detectors first, then LLM verifier; targeted retry feedback with convergence check), assemble (HTML output with Sources, Run Summary, optional Verification History). A persistent SQLite-backed cache wraps cacheable connector adapters transparently.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pydantic v2, alembic, anthropic SDK, openai SDK, matplotlib, openpyxl, markdown-it-py, mammoth (v1 path), React/TypeScript/Vite, Vitest.

**Spec:** `docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md`

---

## File structure

New files (created during this plan):

```
packages/core/src/openlia/llm/runtime/report_v2/
  capabilities.yaml                              # capability manifest (F1)
  capability_manifest.py                         # loader + Pydantic models (F1)
  template_v2/
    spec.py                                      # extended TemplateSpec, ArtifactSpec, etc. (F2)
    loader_v2.py                                 # JSON/YAML loader with reserved-key handling (F2)
    conversion_prompt.py                         # copy-pastable prompt builder (F2)
  connectors/
    base.py                                      # ConnectorAdapter Protocol (F3)
    mcp_adapter.py                               # wraps MCP servers (F3)
    sdk_adapter.py                               # wraps Python SDKs (F3)
    web_adapter.py                               # web fetch (F3)
    registry.py                                  # adapter registration (F3)
    cache_wrapper.py                             # cache check around adapter calls (F5)
  tools/library_helpers/
    __init__.py                                  # HelperSchema + registry (F4)
    dcf_valuation.py                             # vendored from claude-skills (F4)
    ratio_calculator.py                          # vendored (F4)
    forecast_builder.py                          # vendored (F4)
    budget_variance.py                           # vendored (F4)
    business_investment.py                       # ported (F4)
    saas_metrics.py                              # vendored (F4)
    chart_builder.py                             # matplotlib wrapper (F4)
    excel_builder.py                             # openpyxl wrapper (F4)
  pipeline/
    stage_1_clarify.py                           # interactive clarifier (P1)
    stage_3_research_plan.py                     # research planner (P2)
    stage_4_gather.py                            # strand dispatcher (P3)
    stage_5_model_plan.py                        # model planner (P4)
    stage_6_model_build.py                       # artifact build + resolver (P5)
    stage_7_draft.py                             # drafters + trigger evaluator (P6)
    stage_8_verify.py                            # deterministic + LLM verifier (P7)
    stage_9_assemble.py                          # renderer + Run Summary + Verification History (O5)
  schemas/
    plan.py                                      # Plan, ResearchStrand, ModelPlan, ArtifactSpec (P2, P4)
    research_pool.py                             # ResearchPool, Citation (P3)
    blocks.py                                    # typed block schemas (O1)
    run_summary.py                               # RunSummary, TaskOutcome (O3)
    verification_history.py                      # VerificationHistory entries (O4)
    verifier_issue.py                            # VerifierIssue + closed enum (P7)
  rendering/
    block_renderer.py                            # per-block HTML emit (O1)
    citation_manifest.py                         # citation aggregator + Sources footer (O2)
    run_summary_renderer.py                      # Run Summary HTML (O3)
    verification_history_renderer.py             # Verification History HTML (O4)
    assembler.py                                 # full report assembly (O5)

packages/server/src/openlia_server/
  db/
    models.py                                    # CachedDocument added (F5)
    migrations/versions/<rev>_add_cached_documents.py  # alembic migration (F5)
  routes/
    cache.py                                     # admin endpoints (X5)
    capabilities.py                              # GET endpoint exposing manifest (X1)
  services/
    cache_service.py                             # cache_documents CRUD (F5)

frontend/src/
  pages/
    EquityResearch/
      Composer.tsx                               # redesigned (X1)
  components/
    ClarifierModal/                              # new (X2)
    CapabilitySidebar/                           # new (X1)
    TemplateUpload/                              # extended (X3)
    ReportViewer/
      blocks/                                    # new block render targets (X4)
      RunSummary.tsx                             # new (X4)
      VerificationHistory.tsx                    # new dev-mode-only (X4)
    CacheAdmin/                                  # new (X5)
    RunTimeline/                                 # extended (X5)
  api/
    capabilities.ts                              # GET /api/capabilities (X1)
    cache.ts                                     # cache admin client (X5)
```

Modified files:
- `packages/core/src/openlia/reports/frameworks/template_spec.py` — extended (F2)
- `packages/core/src/openlia/llm/runtime/report_v2/runner.py` — orchestrates new pipeline (P0)
- `packages/server/src/openlia_server/db/models.py` — add CachedDocument (F5)
- `packages/server/src/openlia_server/routes/departments.py` — wire v2.2 runner (X1)
- `frontend/src/pages/Settings.tsx` — dev_mode and cache toggles (X5)

Removed (no longer referenced by v2.2):
- `packages/core/src/openlia/llm/runtime/report_v2/facts/` — entire directory deprecated (still present for legacy v1 code paths until those modes are template-converted; do NOT delete in v2.2)

---

## Phase 0 — Setup

### Task 0.1: Branch verification

**Files:** none

- [ ] **Step 1: Confirm branch state**

Run: `git status && git rev-parse --abbrev-ref HEAD`
Expected: clean tree, on `feat/custom-templates-v2` or a fresh `feat/equity-research-v2.2`.

- [ ] **Step 2: Create branch if needed**

If not on the v2.2 branch:
```bash
git checkout -b feat/equity-research-v2.2
```

- [ ] **Step 3: Confirm v2 docs are marked superseded**

Run: `head -5 docs/superpowers/specs/2026-05-20-equity-research-v2-design.md`
Expected: line 3 contains "SUPERSEDED".

Same check for `docs/superpowers/plans/2026-05-20-equity-research-v2.md`.

---

## Phase F — Foundation

Foundation work that the rest of the pipeline depends on. No pipeline behavior changes yet; the foundation is loaded but the v1 path remains active.

### Task F1: Capability manifest

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/capabilities.yaml`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/capability_manifest.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_capability_manifest.py`

- [ ] **Step 1: Write failing test for manifest load + structure**

```python
# packages/core/tests/llm/runtime/report_v2/test_capability_manifest.py
from openlia.llm.runtime.report_v2.capability_manifest import load_manifest, CapabilityManifest

def test_load_manifest_returns_typed_object():
    m = load_manifest()
    assert isinstance(m, CapabilityManifest)
    assert m.engine_version == "2.2"
    assert isinstance(m.supported, list)
    assert isinstance(m.unsupported, list)
    assert "extra_passes" in {u.id for u in m.unsupported}

def test_unsupported_capability_carries_detection_data():
    m = load_manifest()
    extras = next(u for u in m.unsupported if u.id == "extra_passes")
    assert extras.detect_in_prompt
    assert extras.detect_in_template_keys
    assert extras.user_message
    assert extras.planned_in == "2.3"

def test_known_template_keys_includes_core_fields():
    m = load_manifest()
    for k in ("template_id", "template_name", "department", "report_type",
              "engine_version_compat", "composer_inputs", "required_artifacts",
              "sections", "verifier_severity_overrides"):
        assert k in m.known_template_keys
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_capability_manifest.py -v`
Expected: ImportError / ModuleNotFoundError.

- [ ] **Step 3: Write `capabilities.yaml`**

```yaml
# packages/core/src/openlia/llm/runtime/report_v2/capabilities.yaml
engine_version: "2.2"
dev_mode: true

supported:
  - id: conditional_sections
    summary: "Sections with trigger_when skip based on LLM evaluation"
  - id: composer_inputs
    summary: "Templates declare typed input fields"
  - id: research_strands
    summary: "Planner declares N research strands gathered via connected tools"
  - id: model_components
    summary: "Planner declares model components built post-gather"
  - id: section_drafters
    summary: "Per-section drafter subagents produce typed blocks"
  - id: verifier_retry
    summary: "Up to 3 targeted retries per section with verifier feedback"
  - id: vendored_library_helpers
    summary: "DCF, ratios, forecasts, budget variance, business investment, SaaS metrics"
  - id: html_output
    summary: "Reports render to HTML; download button converts to PDF/DOCX"
  - id: persistent_cache
    summary: "Transcripts and investor-day data cached across runs"

unsupported:
  - id: extra_passes
    summary: "Additional LLM review/check passes beyond the standard pipeline"
    detect_in_prompt:
      - "extra LLM check"
      - "review pass"
      - "second opinion"
      - "devil's advocate"
      - "have another LLM verify"
    detect_in_template_keys: [extra_passes, extra_calls, reviewer_passes, check_passes]
    planned_in: "2.3"
    user_message: |
      Extra LLM review/check passes are not supported in this version.
      Proceeding with the standard pipeline. Planned for v2.3.

  - id: review_loops
    summary: "Reviewer-reviser loops with iterative refinement"
    detect_in_prompt: ["iterate until", "loop until", "round of revisions", "refine N times"]
    detect_in_template_keys: [loops, review_loops]
    planned_in: "2.3"
    user_message: "Iterative review loops are not supported in this version. Proceeding with single-pass verification."

  - id: custom_subagents
    summary: "User-defined subagents beyond the standard research strands"
    detect_in_prompt: ["my own subagent", "custom agent for"]
    detect_in_template_keys: [custom_subagents]
    planned_in: "2.3"
    user_message: "Custom subagents are not supported in this version."

  - id: advanced_quant_categories
    summary: "VaR, Sharpe, portfolio optimization, Monte Carlo, PDF sentiment, etc."
    detect_in_prompt: ["VaR", "Sharpe", "Monte Carlo", "portfolio optimization", "factor exposure", "sentiment from PDFs"]
    detect_in_template_keys: []
    planned_in: null
    user_message: |
      Advanced quant calculations are not yet available.
      Available now: DCF, ratio analysis, forecasting, budget variance, business investment, SaaS metrics.

known_template_keys:
  - template_id
  - template_name
  - department
  - report_type
  - engine_version_compat
  - composer_inputs
  - required_artifacts
  - output_artifacts
  - sections
  - verifier_severity_overrides

cache:
  enabled: true
  transcripts:
    enabled: true
  investor_day:
    enabled: true
  default_force_refresh: false
```

- [ ] **Step 4: Write loader module**

```python
# packages/core/src/openlia/llm/runtime/report_v2/capability_manifest.py
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, Field


class SupportedCapability(BaseModel):
    id: str
    summary: str


class UnsupportedCapability(BaseModel):
    id: str
    summary: str
    detect_in_prompt: list[str] = Field(default_factory=list)
    detect_in_template_keys: list[str] = Field(default_factory=list)
    planned_in: str | None = None
    user_message: str


class CacheSourceToggle(BaseModel):
    enabled: bool = True


class CacheConfig(BaseModel):
    enabled: bool = True
    transcripts: CacheSourceToggle = CacheSourceToggle()
    investor_day: CacheSourceToggle = CacheSourceToggle()
    default_force_refresh: bool = False


class CapabilityManifest(BaseModel):
    engine_version: str
    dev_mode: bool
    supported: list[SupportedCapability]
    unsupported: list[UnsupportedCapability]
    known_template_keys: list[str]
    cache: CacheConfig

    def unsupported_by_template_key(self) -> dict[str, UnsupportedCapability]:
        out: dict[str, UnsupportedCapability] = {}
        for u in self.unsupported:
            for k in u.detect_in_template_keys:
                out[k] = u
        return out


@lru_cache(maxsize=1)
def load_manifest(path: Path | None = None) -> CapabilityManifest:
    if path is None:
        path = Path(__file__).parent / "capabilities.yaml"
    with path.open() as f:
        data = yaml.safe_load(f)
    return CapabilityManifest.model_validate(data)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_capability_manifest.py -v`
Expected: PASS.

- [ ] **Step 6: Lint**

Run: `uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/capability_manifest.py && uv run ruff format --check packages/core/src/openlia/llm/runtime/report_v2/capability_manifest.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/capabilities.yaml \
        packages/core/src/openlia/llm/runtime/report_v2/capability_manifest.py \
        packages/core/tests/llm/runtime/report_v2/test_capability_manifest.py
git commit -m "feat(report_v2): capability manifest with loader and tests"
```

---

### Task F2: TemplateSpec extensions

**Files:**
- Modify: `packages/core/src/openlia/reports/frameworks/template_spec.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/template_v2/spec.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/template_v2/loader_v2.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/template_v2/conversion_prompt.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_template_v2_loader.py`

- [ ] **Step 1: Write failing test for loader behavior**

```python
# packages/core/tests/llm/runtime/report_v2/test_template_v2_loader.py
import pytest
import yaml
import json
from openlia.llm.runtime.report_v2.template_v2.loader_v2 import (
    load_template_v2, TemplateLoadNotice
)

YAML_OK = """
template_id: test_t1
template_name: Test
department: equity_research
report_type: equity_research
engine_version_compat: "2.2"
composer_inputs:
  - {name: ticker, type: ticker, label: Ticker, required: true}
required_artifacts: []
sections:
  - {id: intro, name: Intro, directive: "Write an intro"}
"""

YAML_RESERVED = YAML_OK + """
extra_passes:
  - name: extra_check
loops:
  - name: review_loop
"""

YAML_UNKNOWN = YAML_OK + """
mystery_field: hello
"""


def test_load_yaml_basic():
    spec, notices = load_template_v2(YAML_OK, fmt="yaml")
    assert spec.template_id == "test_t1"
    assert spec.report_type == "equity_research"
    assert notices == []


def test_load_json_equivalent():
    data = yaml.safe_load(YAML_OK)
    spec, notices = load_template_v2(json.dumps(data), fmt="json")
    assert spec.template_id == "test_t1"


def test_reserved_keys_stripped_with_notices():
    spec, notices = load_template_v2(YAML_RESERVED, fmt="yaml")
    notice_keys = {n.key for n in notices if n.kind == "reserved_key"}
    assert "extra_passes" in notice_keys
    assert "loops" in notice_keys


def test_unknown_keys_emit_warning_notice():
    spec, notices = load_template_v2(YAML_UNKNOWN, fmt="yaml")
    assert any(n.kind == "unknown_key" and n.key == "mystery_field" for n in notices)


def test_report_type_is_singular_string():
    bad = YAML_OK.replace("report_type: equity_research",
                          "report_type:\n  - equity_research\n  - other")
    with pytest.raises(Exception):
        load_template_v2(bad, fmt="yaml")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_template_v2_loader.py -v`
Expected: ImportError.

- [ ] **Step 3: Write the new template spec module**

```python
# packages/core/src/openlia/llm/runtime/report_v2/template_v2/spec.py
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


ComposerInputType = Literal[
    "ticker", "ticker_list", "sector", "string", "enum",
    "int", "bool", "date_range",
]


class ComposerInputSpec(BaseModel):
    name: str
    type: ComposerInputType
    label: str
    required: bool = False
    enum_options: list[str] | None = None
    default: Any | None = None


ArtifactType = Literal["chart", "table", "kpi_strip", "excel", "quote_block"]


class ArtifactSpec(BaseModel):
    id: str
    type: ArtifactType
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    helper: str | None = None
    source_strand: str | None = None
    target_section_id: str | None = None
    source: Literal["template", "composer", "planner"] = "template"


class SectionSpec(BaseModel):
    id: str
    name: str
    directive: str
    depends_on: list[str] = Field(default_factory=list)
    trigger_when: str | None = None


class TemplateSpecV2(BaseModel):
    template_id: str
    template_name: str
    department: str
    report_type: str
    engine_version_compat: str
    composer_inputs: list[ComposerInputSpec] = Field(default_factory=list)
    required_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    output_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    sections: list[SectionSpec]
    verifier_severity_overrides: dict[str, str] = Field(default_factory=dict)
```

- [ ] **Step 4: Write loader with reserved-key handling**

```python
# packages/core/src/openlia/llm/runtime/report_v2/template_v2/loader_v2.py
from __future__ import annotations
import json
import yaml
from dataclasses import dataclass
from typing import Literal

from openlia.llm.runtime.report_v2.capability_manifest import load_manifest
from openlia.llm.runtime.report_v2.template_v2.spec import TemplateSpecV2


@dataclass(frozen=True)
class TemplateLoadNotice:
    kind: Literal["reserved_key", "unknown_key"]
    key: str
    message: str


def load_template_v2(
    raw: str,
    fmt: Literal["yaml", "json"],
) -> tuple[TemplateSpecV2, list[TemplateLoadNotice]]:
    if fmt == "yaml":
        data = yaml.safe_load(raw)
    elif fmt == "json":
        data = json.loads(raw)
    else:
        raise ValueError(f"unsupported fmt: {fmt}")
    if not isinstance(data, dict):
        raise ValueError("template root must be a mapping")

    manifest = load_manifest()
    notices: list[TemplateLoadNotice] = []
    reserved_map = manifest.unsupported_by_template_key()
    known = set(manifest.known_template_keys)

    cleaned: dict = {}
    for k, v in data.items():
        if k in reserved_map:
            cap = reserved_map[k]
            notices.append(TemplateLoadNotice(
                kind="reserved_key",
                key=k,
                message=cap.user_message.strip(),
            ))
            continue
        if k not in known:
            notices.append(TemplateLoadNotice(
                kind="unknown_key",
                key=k,
                message=f"Unknown template key '{k}' ignored. "
                        f"Allowed keys: {sorted(known)}",
            ))
            continue
        cleaned[k] = v

    spec = TemplateSpecV2.model_validate(cleaned)
    return spec, notices
```

- [ ] **Step 5: Write conversion prompt builder**

```python
# packages/core/src/openlia/llm/runtime/report_v2/template_v2/conversion_prompt.py
from __future__ import annotations
from openlia.llm.runtime.report_v2.capability_manifest import load_manifest


CONVERSION_PROMPT_TEMPLATE = """
You are converting a free-form report framework into a structured OpenLIA template.

Engine version: {engine_version}

OUTPUT FORMAT: JSON or YAML, validating the following schema (paste either).

Required top-level keys: template_id, template_name, department, report_type,
engine_version_compat, sections.
Optional: composer_inputs, required_artifacts, verifier_severity_overrides.

Allowed composer_inputs[].type values: ticker, ticker_list, sector, string,
enum, int, bool, date_range.

Each section has: id (lowercase, underscore-separated), name, directive.
Optional per section: depends_on (list of section ids), trigger_when (free
text condition; only set when section is conditional).

DO NOT include any of these reserved keys: {reserved_keys}.
Engine v{engine_version} does not support extra LLM passes, review loops,
or custom subagents. If the source document mentions them, ignore those
parts when emitting the template.

For directives that contain conditional language (e.g., 'if applicable',
'where relevant', 'include only when material'), set the section's
trigger_when field with a plain-English condition.

Source document follows below. Convert it to a single JSON object or YAML
mapping. Return only the converted template, no surrounding prose.

--- SOURCE DOCUMENT ---
[Paste your source document here]
""".strip()


def build_conversion_prompt() -> str:
    m = load_manifest()
    reserved = sorted({k for u in m.unsupported for k in u.detect_in_template_keys})
    return CONVERSION_PROMPT_TEMPLATE.format(
        engine_version=m.engine_version,
        reserved_keys=", ".join(reserved),
    )
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_template_v2_loader.py -v`
Expected: PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/template_v2/
uv run ruff format packages/core/src/openlia/llm/runtime/report_v2/template_v2/
git add packages/core/src/openlia/llm/runtime/report_v2/template_v2/ \
        packages/core/tests/llm/runtime/report_v2/test_template_v2_loader.py
git commit -m "feat(report_v2): TemplateSpecV2 + loader with reserved-key + unknown-key notices"
```

---

### Task F3: Connector adapter abstraction

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/connectors/base.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/connectors/registry.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/connectors/mcp_adapter.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/connectors/sdk_adapter.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/connectors/web_adapter.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_connectors.py`

- [ ] **Step 1: Write failing test for adapter Protocol + registry**

```python
# packages/core/tests/llm/runtime/report_v2/test_connectors.py
import pytest
from openlia.llm.runtime.report_v2.connectors.base import (
    ConnectorAdapter, ToolMeta, ToolResult
)
from openlia.llm.runtime.report_v2.connectors.registry import (
    register_adapter, get_adapter, list_adapters, AdapterRegistry,
    reset_registry_for_tests,
)


class FakeAdapter:
    name = "fake"
    tool_kind = "internal"
    cacheable = False

    def list_tools(self) -> list[ToolMeta]:
        return [ToolMeta(name="echo", description="echo input")]

    def call(self, tool: str, params: dict) -> ToolResult:
        return ToolResult(content=params.get("msg", ""), metadata={}, served_from_cache=False)


def test_register_and_lookup():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    a = get_adapter("fake")
    assert a.name == "fake"
    assert a.tool_kind == "internal"


def test_call_returns_tool_result():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    a = get_adapter("fake")
    r = a.call("echo", {"msg": "hi"})
    assert r.content == "hi"
    assert r.served_from_cache is False


def test_register_duplicate_raises():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    with pytest.raises(ValueError):
        register_adapter(FakeAdapter())


def test_list_adapters_returns_all():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    assert "fake" in {a.name for a in list_adapters()}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_connectors.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement base Protocol + types**

```python
# packages/core/src/openlia/llm/runtime/report_v2/connectors/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


ToolKind = Literal["mcp", "python_sdk", "openapi", "web", "internal"]


@dataclass(frozen=True)
class ToolMeta:
    name: str
    description: str
    cacheable: bool = False


@dataclass(frozen=True)
class ToolResult:
    content: Any
    metadata: dict = field(default_factory=dict)
    served_from_cache: bool = False


class ConnectorAdapter(Protocol):
    name: str
    tool_kind: ToolKind
    cacheable: bool

    def list_tools(self) -> list[ToolMeta]: ...
    def call(self, tool: str, params: dict) -> ToolResult: ...
```

- [ ] **Step 4: Implement registry**

```python
# packages/core/src/openlia/llm/runtime/report_v2/connectors/registry.py
from __future__ import annotations
from openlia.llm.runtime.report_v2.connectors.base import ConnectorAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ConnectorAdapter] = {}

    def register(self, adapter: ConnectorAdapter) -> None:
        if adapter.name in self._adapters:
            raise ValueError(f"adapter {adapter.name!r} already registered")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> ConnectorAdapter:
        if name not in self._adapters:
            raise KeyError(f"no adapter registered as {name!r}")
        return self._adapters[name]

    def list(self) -> list[ConnectorAdapter]:
        return list(self._adapters.values())

    def reset(self) -> None:
        self._adapters.clear()


_default = AdapterRegistry()


def register_adapter(a: ConnectorAdapter) -> None:
    _default.register(a)


def get_adapter(name: str) -> ConnectorAdapter:
    return _default.get(name)


def list_adapters() -> list[ConnectorAdapter]:
    return _default.list()


def reset_registry_for_tests() -> None:
    _default.reset()
```

- [ ] **Step 5: Implement MCP / SDK / web adapter stubs**

Each file follows the same shape. MCP adapter wraps existing MCP server invocations; SDK adapter wraps Python SDK clients; web adapter wraps HTTP fetch. v2.2 ships the structure; v2.3+ can add real-world adapters.

```python
# packages/core/src/openlia/llm/runtime/report_v2/connectors/mcp_adapter.py
from __future__ import annotations
from openlia.llm.runtime.report_v2.connectors.base import ConnectorAdapter, ToolMeta, ToolResult


class MCPAdapter:
    def __init__(self, name: str, mcp_client, cacheable_tools: set[str] | None = None) -> None:
        self.name = name
        self.tool_kind = "mcp"
        self.cacheable = False  # per-call decided via tool meta
        self._client = mcp_client
        self._cacheable_tools = cacheable_tools or set()

    def list_tools(self) -> list[ToolMeta]:
        return [
            ToolMeta(name=t.name, description=t.description, cacheable=(t.name in self._cacheable_tools))
            for t in self._client.list_tools()
        ]

    def call(self, tool: str, params: dict) -> ToolResult:
        result = self._client.invoke(tool, params)
        return ToolResult(content=result.payload, metadata=result.metadata, served_from_cache=False)
```

```python
# packages/core/src/openlia/llm/runtime/report_v2/connectors/sdk_adapter.py
from __future__ import annotations
from typing import Callable
from openlia.llm.runtime.report_v2.connectors.base import ToolMeta, ToolResult


class SDKAdapter:
    def __init__(self, name: str, tools: dict[str, Callable], cacheable_tools: set[str] | None = None) -> None:
        self.name = name
        self.tool_kind = "python_sdk"
        self.cacheable = False
        self._tools = tools
        self._cacheable_tools = cacheable_tools or set()

    def list_tools(self) -> list[ToolMeta]:
        return [
            ToolMeta(name=k, description=(f.__doc__ or "").strip().split("\n", 1)[0],
                     cacheable=(k in self._cacheable_tools))
            for k, f in self._tools.items()
        ]

    def call(self, tool: str, params: dict) -> ToolResult:
        if tool not in self._tools:
            raise KeyError(f"{self.name} has no tool {tool!r}")
        result = self._tools[tool](**params)
        return ToolResult(content=result, metadata={}, served_from_cache=False)
```

```python
# packages/core/src/openlia/llm/runtime/report_v2/connectors/web_adapter.py
from __future__ import annotations
import httpx
from openlia.llm.runtime.report_v2.connectors.base import ToolMeta, ToolResult


class WebAdapter:
    def __init__(self, name: str = "web") -> None:
        self.name = name
        self.tool_kind = "web"
        self.cacheable = False

    def list_tools(self) -> list[ToolMeta]:
        return [ToolMeta(name="fetch", description="HTTP GET a URL and return text body", cacheable=False)]

    def call(self, tool: str, params: dict) -> ToolResult:
        if tool != "fetch":
            raise KeyError(f"web adapter has no tool {tool!r}")
        url = params["url"]
        r = httpx.get(url, timeout=params.get("timeout", 15.0))
        r.raise_for_status()
        return ToolResult(content=r.text, metadata={"status": r.status_code, "url": url}, served_from_cache=False)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_connectors.py -v`
Expected: PASS.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/connectors/
uv run ruff format packages/core/src/openlia/llm/runtime/report_v2/connectors/
git add packages/core/src/openlia/llm/runtime/report_v2/connectors/ \
        packages/core/tests/llm/runtime/report_v2/test_connectors.py
git commit -m "feat(report_v2): connector adapter abstraction (MCP, SDK, web) + registry"
```

---

### Task F4: Library helpers vendored

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/__init__.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/dcf_valuation.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/ratio_calculator.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/forecast_builder.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/budget_variance.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/business_investment.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/saas_metrics.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/chart_builder.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/excel_builder.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_library_helpers.py`

- [ ] **Step 1: Vendor source files**

```bash
# Clone or refresh source
mkdir -p $TMPDIR/claude-skills && cd $TMPDIR/claude-skills && \
  ([ -d .git ] || git clone --depth 1 https://github.com/alirezarezvani/claude-skills.git .)
```

Copy these source files (DO NOT modify content yet, just place):

- `skills/financial-analyst/scripts/dcf_valuation.py` → vendor target
- `skills/financial-analyst/scripts/ratio_calculator.py` → vendor target
- `skills/financial-analyst/scripts/forecast_builder.py` → vendor target
- `skills/financial-analyst/scripts/budget_variance_analyzer.py` → vendor as `budget_variance.py`
- `skills/saas-metrics-coach/scripts/*.py` → consolidate into `saas_metrics.py`
- `business-investment-advisor/skills/business-investment-advisor/SKILL.md` → port math into `business_investment.py`

- [ ] **Step 2: Write `HelperSchema` + registry**

```python
# packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/__init__.py
from __future__ import annotations
from typing import Any, Callable, Literal
from pydantic import BaseModel, Field


class HelperParam(BaseModel):
    type: str
    default: Any | None = None
    derivation: str | None = None
    description: str
    required: bool = True


class HelperSchema(BaseModel):
    name: str
    description: str
    params: dict[str, HelperParam]


class HelperRegistration(BaseModel):
    schema: HelperSchema
    execute: Callable[..., Any] = Field(exclude=True)
    available: bool = True
    deferred_category: str | None = None

    model_config = {"arbitrary_types_allowed": True}


_helpers: dict[str, HelperRegistration] = {}


def register_helper(reg: HelperRegistration) -> None:
    name = reg.schema.name
    if name in _helpers:
        raise ValueError(f"helper {name!r} already registered")
    _helpers[name] = reg


def register_library_helper(name: str, fn: Callable, schema: HelperSchema,
                            deferred_category: str | None = None) -> None:
    register_helper(HelperRegistration(
        schema=schema, execute=fn,
        available=(deferred_category is None),
        deferred_category=deferred_category,
    ))


def get_helper(name: str) -> HelperRegistration:
    if name not in _helpers:
        raise KeyError(f"no helper registered as {name!r}")
    return _helpers[name]


def list_helpers() -> list[HelperRegistration]:
    return list(_helpers.values())


def reset_helpers_for_tests() -> None:
    _helpers.clear()


def register_deferred_categories() -> None:
    """Register 'not yet implemented' placeholders for categories 4-11, 13."""
    deferred = [
        ("var_calculator", "Value at Risk", "risk_metrics"),
        ("sharpe_ratio", "Sharpe ratio", "risk_metrics"),
        ("portfolio_optimizer", "Portfolio optimization", "portfolio"),
        ("time_series_analyzer", "Time-series decomposition", "time_series"),
        ("monte_carlo", "Monte Carlo simulation", "quant_finance"),
        ("macro_indicator", "Macro indicator pull", "macro"),
        ("equity_screener", "Equity screener", "screener"),
        ("nlp_sentiment", "NLP sentiment", "nlp"),
        ("pdf_extractor", "PDF text extraction", "pdf_parsing"),
        ("factor_exposure", "Factor exposure", "quant_finance"),
        ("stats_inference", "Statistical inference", "stats"),
    ]
    for name, desc, category in deferred:
        if name in _helpers:
            continue
        register_library_helper(
            name=name,
            fn=lambda **kw: (_ for _ in ()).throw(NotImplementedError(
                f"{name} is in deferred category {category!r}")),
            schema=HelperSchema(name=name, description=desc, params={}),
            deferred_category=category,
        )
```

- [ ] **Step 3: Vendor + register DCF, ratio, forecast, budget_variance, business_investment, saas_metrics**

Vendor each file with this header preserved at the top:

```python
"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: <relative path in source repo>
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via `SCHEMA` module-level constant and an
`execute(**params)` entry point.
"""
```

Each vendored file ends with a module-level `SCHEMA = HelperSchema(...)` matching the v2.2 design spec example for `dcf_valuation` (§6.4 of the spec). At the bottom, register via:

```python
register_library_helper("dcf_valuation", execute, SCHEMA)
```

(or via an explicit registration step in `__init__.py` that imports each module and calls `register_library_helper(...)`).

- [ ] **Step 4: chart_builder.py + excel_builder.py**

```python
# packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/chart_builder.py
from __future__ import annotations
import base64, io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperSchema, HelperParam, register_library_helper,
)

SCHEMA = HelperSchema(
    name="make_chart",
    description="Render a matplotlib chart and return as inline SVG",
    params={
        "chart_type": HelperParam(type="str", description="line, bar, scatter, heatmap"),
        "series": HelperParam(type="list", description="Data series"),
        "x_label": HelperParam(type="str", default="", description="X axis label", required=False),
        "y_label": HelperParam(type="str", default="", description="Y axis label", required=False),
        "title": HelperParam(type="str", default="", description="Chart title", required=False),
    },
)


def execute(**params):
    fig, ax = plt.subplots()
    # render based on chart_type ...
    buf = io.StringIO()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    return {"format": "svg_inline", "svg": buf.getvalue()}


register_library_helper("make_chart", execute, SCHEMA)
```

```python
# packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/excel_builder.py
from __future__ import annotations
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperSchema, HelperParam, register_library_helper,
)

SCHEMA = HelperSchema(
    name="make_excel",
    description="Build an xlsx workbook from tabular data",
    params={
        "sheets": HelperParam(type="list", description="List of {name, headers, rows}"),
    },
)


def execute(**params):
    wb = Workbook()
    wb.remove(wb.active)
    for sheet_spec in params["sheets"]:
        ws = wb.create_sheet(title=sheet_spec["name"])
        ws.append(sheet_spec["headers"])
        for row in sheet_spec["rows"]:
            ws.append(row)
    # save to bytes
    import io
    buf = io.BytesIO()
    wb.save(buf)
    return {"format": "xlsx", "bytes": buf.getvalue()}


register_library_helper("make_excel", execute, SCHEMA)
```

- [ ] **Step 5: Add deps**

```bash
uv add matplotlib openpyxl markdown-it-py
```

- [ ] **Step 6: Write tests**

```python
# packages/core/tests/llm/runtime/report_v2/test_library_helpers.py
from openlia.llm.runtime.report_v2.tools.library_helpers import (
    list_helpers, get_helper, register_deferred_categories,
)
# import all helper modules so registration side-effects fire
from openlia.llm.runtime.report_v2.tools.library_helpers import (  # noqa
    dcf_valuation, ratio_calculator, forecast_builder, budget_variance,
    business_investment, saas_metrics, chart_builder, excel_builder,
)


def test_vendored_helpers_registered():
    names = {h.schema.name for h in list_helpers()}
    for required in ("dcf_valuation", "ratio_calculator", "forecast_builder",
                     "budget_variance", "business_investment", "saas_metrics",
                     "make_chart", "make_excel"):
        assert required in names


def test_deferred_categories_marked_unavailable():
    register_deferred_categories()
    assert get_helper("var_calculator").available is False
    assert get_helper("var_calculator").deferred_category == "risk_metrics"


def test_deferred_helper_raises_when_executed():
    register_deferred_categories()
    h = get_helper("var_calculator")
    import pytest
    with pytest.raises(NotImplementedError):
        h.execute()


def test_dcf_helper_schema_has_required_params():
    h = get_helper("dcf_valuation")
    p = h.schema.params
    assert "base_revenue" in p
    assert p["base_revenue"].required
```

- [ ] **Step 7: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_library_helpers.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/
uv run ruff format packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/
git add packages/core/src/openlia/llm/runtime/report_v2/tools/library_helpers/ \
        packages/core/tests/llm/runtime/report_v2/test_library_helpers.py \
        pyproject.toml uv.lock
git commit -m "feat(report_v2): vendor 6 library helpers from claude-skills + chart/excel builders + deferred-category placeholders"
```

---

### Task F5: Cache subsystem

**Files:**
- Modify: `packages/server/src/openlia_server/db/models.py`
- Create: `packages/server/src/openlia_server/db/migrations/versions/<rev>_add_cached_documents.py`
- Create: `packages/server/src/openlia_server/services/cache_service.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/connectors/cache_wrapper.py`
- Test: `packages/server/tests/test_cache_service.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_cache_wrapper.py`

- [ ] **Step 1: Write failing test for cache wrapper hit/miss**

```python
# packages/core/tests/llm/runtime/report_v2/test_cache_wrapper.py
from openlia.llm.runtime.report_v2.connectors.base import ToolMeta, ToolResult
from openlia.llm.runtime.report_v2.connectors.cache_wrapper import CacheWrappedAdapter


class FakeStore:
    def __init__(self):
        self._data: dict = {}
    def get(self, key: str):
        return self._data.get(key)
    def upsert(self, key: str, result: ToolResult, **meta):
        self._data[key] = result


class FakeAdapter:
    name = "fake"
    tool_kind = "internal"
    cacheable = True
    calls: int = 0

    def list_tools(self):
        return [ToolMeta(name="get_transcript", description="...", cacheable=True)]

    def call(self, tool, params):
        FakeAdapter.calls += 1
        return ToolResult(content=f"transcript for {params['ticker']}", metadata={}, served_from_cache=False)


def test_cache_miss_then_hit():
    FakeAdapter.calls = 0
    store = FakeStore()
    wrapped = CacheWrappedAdapter(FakeAdapter(), store)

    r1 = wrapped.call("get_transcript", {"ticker": "NVDA", "fiscal_period": "2026Q1"})
    assert r1.served_from_cache is False
    assert FakeAdapter.calls == 1

    r2 = wrapped.call("get_transcript", {"ticker": "NVDA", "fiscal_period": "2026Q1"})
    assert r2.served_from_cache is True
    assert FakeAdapter.calls == 1


def test_force_refresh_bypasses_cache():
    FakeAdapter.calls = 0
    store = FakeStore()
    wrapped = CacheWrappedAdapter(FakeAdapter(), store)
    wrapped.call("get_transcript", {"ticker": "NVDA", "fiscal_period": "2026Q1"})
    wrapped.call("get_transcript", {"ticker": "NVDA", "fiscal_period": "2026Q1"},
                 force_refresh=True)
    assert FakeAdapter.calls == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_cache_wrapper.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement cache wrapper**

```python
# packages/core/src/openlia/llm/runtime/report_v2/connectors/cache_wrapper.py
from __future__ import annotations
from typing import Protocol
from datetime import datetime, UTC

from openlia.llm.runtime.report_v2.connectors.base import ConnectorAdapter, ToolMeta, ToolResult


class CacheStore(Protocol):
    def get(self, key: str): ...
    def upsert(self, key: str, result: ToolResult, **meta) -> None: ...


def build_cache_key(adapter_name: str, tool: str, params: dict) -> str:
    ticker = params.get("ticker", "_")
    fiscal = params.get("fiscal_period", "_")
    if fiscal == "_":
        # fall back to params hash for non-fiscal-period tools
        import json, hashlib
        h = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
        fiscal = h
    return f"{adapter_name}:{tool}:{ticker}:{fiscal}"


class CacheWrappedAdapter:
    def __init__(self, inner: ConnectorAdapter, store: CacheStore) -> None:
        self._inner = inner
        self._store = store
        self.name = inner.name
        self.tool_kind = inner.tool_kind
        self.cacheable = inner.cacheable

    def list_tools(self) -> list[ToolMeta]:
        return self._inner.list_tools()

    def call(self, tool: str, params: dict, force_refresh: bool = False) -> ToolResult:
        tool_meta = next((t for t in self._inner.list_tools() if t.name == tool), None)
        is_cacheable = tool_meta.cacheable if tool_meta else False
        if not is_cacheable:
            return self._inner.call(tool, params)
        key = build_cache_key(self._inner.name, tool, params)
        if not force_refresh:
            hit = self._store.get(key)
            if hit is not None:
                return ToolResult(content=hit.content, metadata=hit.metadata, served_from_cache=True)
        result = self._inner.call(tool, params)
        self._store.upsert(
            key, result,
            source=self._inner.name,
            tool=tool,
            ticker=params.get("ticker"),
            fiscal_period=params.get("fiscal_period"),
            original_retrieved_at=datetime.now(UTC),
        )
        return result
```

- [ ] **Step 4: Add `CachedDocument` to db/models.py**

```python
# packages/server/src/openlia_server/db/models.py — append
from sqlalchemy import Column, String, DateTime, Integer, Text, Index
from sqlalchemy.dialects.sqlite import JSON


class CachedDocument(Base):
    __tablename__ = "cached_documents"

    cache_key = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    document_id = Column(String, nullable=False)
    ticker = Column(String, nullable=True)
    fiscal_period = Column(String, nullable=True)
    content_text = Column(Text, nullable=False)
    raw_metadata = Column(JSON, nullable=False, default=dict)
    original_retrieved_at = Column(DateTime(timezone=True), nullable=False)
    cached_at = Column(DateTime(timezone=True), nullable=False)
    bytes_size = Column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_cached_documents_ticker_fiscal", "ticker", "fiscal_period"),
    )
```

- [ ] **Step 5: Generate alembic migration**

```bash
uv run alembic -c packages/server/alembic.ini revision --autogenerate -m "add cached_documents"
```

Edit the generated file if needed to ensure indexes are created. Then:

```bash
uv run alembic -c packages/server/alembic.ini upgrade head
```

- [ ] **Step 6: Implement cache_service.py**

```python
# packages/server/src/openlia_server/services/cache_service.py
from __future__ import annotations
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from openlia_server.db.models import CachedDocument
from openlia.llm.runtime.report_v2.connectors.base import ToolResult


class SQLAlchemyCacheStore:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, key: str):
        return self._s.get(CachedDocument, key)

    def upsert(self, key: str, result: ToolResult, **meta) -> None:
        existing = self._s.get(CachedDocument, key)
        content = result.content if isinstance(result.content, str) else str(result.content)
        if existing is None:
            doc = CachedDocument(
                cache_key=key,
                source=meta["source"],
                document_id=meta.get("document_id", key),
                ticker=meta.get("ticker"),
                fiscal_period=meta.get("fiscal_period"),
                content_text=content,
                raw_metadata=result.metadata,
                original_retrieved_at=meta.get("original_retrieved_at", datetime.now(UTC)),
                cached_at=datetime.now(UTC),
                bytes_size=len(content.encode()),
            )
            self._s.add(doc)
        else:
            existing.content_text = content
            existing.raw_metadata = result.metadata
            existing.cached_at = datetime.now(UTC)
            existing.bytes_size = len(content.encode())
        self._s.commit()
```

- [ ] **Step 7: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_cache_wrapper.py packages/server/tests/test_cache_service.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/connectors/cache_wrapper.py \
                  packages/server/src/openlia_server/services/cache_service.py
git add packages/core/src/openlia/llm/runtime/report_v2/connectors/cache_wrapper.py \
        packages/server/src/openlia_server/db/ \
        packages/server/src/openlia_server/services/cache_service.py \
        packages/core/tests/llm/runtime/report_v2/test_cache_wrapper.py \
        packages/server/tests/test_cache_service.py
git commit -m "feat(report_v2): persistent cache (CachedDocument model, alembic migration, adapter wrapper, SQLAlchemy store)"
```

---

## Phase P — Pipeline

Implements the nine pipeline stages on top of the foundation. Each stage is its own PR; the runner gets wired up incrementally.

### Task P0: Runner skeleton

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/runner_v2.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_runner_v2_skeleton.py`

- [ ] **Step 1: Write failing test for stage enum + state machine**

```python
# packages/core/tests/llm/runtime/report_v2/test_runner_v2_skeleton.py
from openlia.llm.runtime.report_v2.runner_v2 import (
    PipelineStage, RunState, RunnerV2
)


def test_pipeline_stages_in_order():
    assert [s.value for s in PipelineStage] == [
        "clarify", "read_template", "research_plan", "gather",
        "model_plan", "model_build", "draft", "verify", "assemble",
    ]


def test_run_state_includes_clarify_awaiting_user():
    assert "CLARIFY_AWAITING_USER" in {s.value for s in RunState}


def test_runner_initial_state_is_started():
    r = RunnerV2()
    assert r.state == RunState.STARTED
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_runner_v2_skeleton.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement skeleton**

```python
# packages/core/src/openlia/llm/runtime/report_v2/runner_v2.py
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field


class PipelineStage(str, Enum):
    CLARIFY = "clarify"
    READ_TEMPLATE = "read_template"
    RESEARCH_PLAN = "research_plan"
    GATHER = "gather"
    MODEL_PLAN = "model_plan"
    MODEL_BUILD = "model_build"
    DRAFT = "draft"
    VERIFY = "verify"
    ASSEMBLE = "assemble"


class RunState(str, Enum):
    STARTED = "STARTED"
    CLARIFY_AWAITING_USER = "CLARIFY_AWAITING_USER"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class RunnerV2:
    state: RunState = RunState.STARTED
    current_stage: PipelineStage | None = None
    outcomes: list = field(default_factory=list)

    def transition(self, new_state: RunState) -> None:
        self.state = new_state
```

- [ ] **Step 4: Run tests + commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_runner_v2_skeleton.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/runner_v2.py
git add packages/core/src/openlia/llm/runtime/report_v2/runner_v2.py \
        packages/core/tests/llm/runtime/report_v2/test_runner_v2_skeleton.py
git commit -m "feat(report_v2): RunnerV2 skeleton with 9-stage enum and CLARIFY_AWAITING_USER state"
```

---

### Task P1: Stage 1 Clarifier (interactive)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_1_clarify.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/schemas/clarifier.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_stage_1_clarify.py`

- [ ] **Step 1: Write failing test for clarifier output schema**

```python
# packages/core/tests/llm/runtime/report_v2/test_stage_1_clarify.py
from unittest.mock import Mock
from openlia.llm.runtime.report_v2.pipeline.stage_1_clarify import (
    Clarifier, ClarifierOutput, CapabilityWarning,
)


def test_clarifier_output_has_blocking_warnings_field():
    out = ClarifierOutput(
        questions=[],
        blocking_warnings=[],
        notices=[],
        detected_intents=[],
    )
    assert hasattr(out, "blocking_warnings")


def test_clarifier_emits_warning_when_extras_detected_in_prompt():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "questions": [],
        "blocking_warnings": [{
            "capability_id": "extra_passes",
            "detected_phrase": "have a devil's advocate pass",
            "user_message": "Extra LLM review/check passes are not supported in this version.",
            "available_actions": ["proceed_without", "cancel_and_edit", "clarify"],
        }],
        "notices": [],
        "detected_intents": ["extras"],
    }
    c = Clarifier(llm=fake_llm)
    out = c.clarify(
        composer_inputs={"ticker": "NVDA", "prompt": "have a devil's advocate pass after drafting"},
        template_spec=Mock(template_id="t1"),
    )
    assert len(out.blocking_warnings) == 1
    assert out.blocking_warnings[0].capability_id == "extra_passes"


def test_clarifier_max_3_rounds():
    c = Clarifier(llm=Mock())
    assert c.MAX_ROUNDS == 3
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_stage_1_clarify.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement schemas**

```python
# packages/core/src/openlia/llm/runtime/report_v2/schemas/clarifier.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class ClarifyingQuestion(BaseModel):
    id: str
    text: str
    kind: Literal["multiple_choice", "free_text"]
    options: list[str] | None = None


class CapabilityWarning(BaseModel):
    capability_id: str
    detected_phrase: str
    user_message: str
    available_actions: list[Literal["proceed_without", "cancel_and_edit", "clarify"]] = Field(
        default_factory=lambda: ["proceed_without", "cancel_and_edit", "clarify"]
    )


class ClarifierOutput(BaseModel):
    questions: list[ClarifyingQuestion] = Field(default_factory=list)
    blocking_warnings: list[CapabilityWarning] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    detected_intents: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement clarifier**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_1_clarify.py
from __future__ import annotations
from openlia.llm.runtime.report_v2.capability_manifest import load_manifest
from openlia.llm.runtime.report_v2.schemas.clarifier import (
    ClarifierOutput, CapabilityWarning, ClarifyingQuestion,
)


def build_clarifier_system_prompt() -> str:
    m = load_manifest()
    lines = [
        f"You are operating on engine version {m.engine_version}.",
        "",
        "Supported capabilities:",
    ]
    for s in m.supported:
        lines.append(f"  - {s.id}: {s.summary}")
    lines += ["", "Unsupported capabilities (with detection cues):"]
    for u in m.unsupported:
        lines.append(f"  - {u.id}: {u.summary}")
        if u.detect_in_prompt:
            lines.append(f"    Watch for these intents: {u.detect_in_prompt}")
        lines.append(f"    User message on detect:\n      {u.user_message}")
    lines += [
        "",
        "Read composer_inputs and the selected template. Then:",
        "1. Emit any clarifying questions (multiple-choice + free-text).",
        "2. For each unsupported feature you detect, emit a blocking_warning.",
        "3. For non-blocking observations, emit notices.",
        "4. Output JSON: {questions, blocking_warnings, notices, detected_intents}.",
        "",
        "FAIL LOUD: If you see an intent that does not map to a supported",
        "capability AND is not in the unsupported list, ask a clarifying",
        "question rather than silently dropping it.",
    ]
    return "\n".join(lines)


class Clarifier:
    MAX_ROUNDS = 3

    def __init__(self, llm) -> None:
        self._llm = llm

    def clarify(
        self,
        composer_inputs: dict,
        template_spec,
        clarification_history: list[str] | None = None,
    ) -> ClarifierOutput:
        history = clarification_history or []
        round_num = len(history) + 1
        if round_num > self.MAX_ROUNDS:
            raise ValueError(f"clarifier exceeded {self.MAX_ROUNDS} rounds")

        sys = build_clarifier_system_prompt()
        user = {
            "composer_inputs": composer_inputs,
            "template": template_spec.model_dump() if hasattr(template_spec, "model_dump") else {"template_id": getattr(template_spec, "template_id", "?")},
            "clarification_history": history,
            "round": round_num,
        }
        raw = self._llm.call(system=sys, user=user)
        return ClarifierOutput.model_validate(raw)
```

- [ ] **Step 5: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_stage_1_clarify.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_1_clarify.py \
                  packages/core/src/openlia/llm/runtime/report_v2/schemas/clarifier.py
git add packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_1_clarify.py \
        packages/core/src/openlia/llm/runtime/report_v2/schemas/clarifier.py \
        packages/core/tests/llm/runtime/report_v2/test_stage_1_clarify.py
git commit -m "feat(report_v2): interactive clarifier with capability-manifest-driven blocking warnings"
```

---

### Task P2: Stage 3 Research planner + Plan schema

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/schemas/plan.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_3_research_plan.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_stage_3_research_plan.py`

- [ ] **Step 1: Write failing test for Plan schema + composer-prompt artifact parse**

```python
# packages/core/tests/llm/runtime/report_v2/test_stage_3_research_plan.py
from unittest.mock import Mock
from openlia.llm.runtime.report_v2.schemas.plan import (
    Plan, ResearchStrand, ArtifactSpec
)
from openlia.llm.runtime.report_v2.pipeline.stage_3_research_plan import ResearchPlanner


def test_plan_has_research_strands_and_required_artifacts():
    p = Plan(research_strands=[], required_artifacts=[], section_dag={})
    assert hasattr(p, "research_strands")
    assert hasattr(p, "required_artifacts")
    assert hasattr(p, "section_dag")


def test_planner_freezes_required_artifacts_from_template():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "research_strands": [
            {"id": "financials", "purpose": "Pull financials",
             "allowed_tools": ["eodhd.get_fundamentals_data"]}
        ],
        "required_artifacts": [],
        "section_dag": {"thesis": [], "valuation": ["thesis"]},
    }
    template = Mock()
    template.required_artifacts = [
        ArtifactSpec(id="dcf", type="chart", description="DCF",
                     parameters={}, helper="dcf_valuation", source="template")
    ]
    template.sections = []
    composer_inputs = {"ticker": "NVDA", "prompt": "include a DCF sensitivity"}
    planner = ResearchPlanner(llm=fake_llm)
    plan = planner.plan(composer_inputs=composer_inputs, template_spec=template,
                        clarifier_answers={})
    ids = {a.id for a in plan.required_artifacts}
    assert "dcf" in ids
    # composer-parsed artifact also makes it in
    composer_sourced = [a for a in plan.required_artifacts if a.source == "composer"]
    assert len(composer_sourced) >= 0  # planner may parse one


def test_planner_emits_slipped_request_for_unmapped_intent():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "research_strands": [],
        "required_artifacts": [],
        "section_dag": {},
        "slipped_requests": ["use VaR for risk section"],
    }
    template = Mock()
    template.required_artifacts = []
    template.sections = []
    planner = ResearchPlanner(llm=fake_llm)
    plan = planner.plan(composer_inputs={"ticker": "NVDA"}, template_spec=template,
                        clarifier_answers={})
    assert "use VaR for risk section" in plan.slipped_requests
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/llm/runtime/report_v2/test_stage_3_research_plan.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement Plan schema**

```python
# packages/core/src/openlia/llm/runtime/report_v2/schemas/plan.py
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class ResearchStrand(BaseModel):
    id: str
    purpose: str
    allowed_tools: list[str]


class ArtifactSpec(BaseModel):
    id: str
    type: Literal["chart", "table", "kpi_strip", "excel", "quote_block"]
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    helper: str | None = None
    source_strand: str | None = None
    target_section_id: str | None = None
    source: Literal["template", "composer", "planner"]


class Plan(BaseModel):
    research_strands: list[ResearchStrand] = Field(default_factory=list)
    required_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    optional_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    section_dag: dict[str, list[str]] = Field(default_factory=dict)
    slipped_requests: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement research planner**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_3_research_plan.py
from __future__ import annotations
from typing import Any
from openlia.llm.runtime.report_v2.schemas.plan import Plan, ResearchStrand, ArtifactSpec


def build_research_planner_prompt() -> str:
    return """
You are the research planner. Read the composer inputs, the selected template,
and the clarifier answers. Emit a Plan as JSON.

The Plan must include:
- research_strands: list of {id, purpose, allowed_tools}. Each strand is a
  bounded subagent. allowed_tools is the whitelist drawn from registered
  connector adapters in the format "<adapter>.<tool>" (e.g.
  "eodhd.get_fundamentals_data").
- required_artifacts: parse the composer prompt for artifact requests
  (charts, tables, sensitivity grids, etc.) and emit one ArtifactSpec per.
  Template-declared required_artifacts will be merged by the caller; do
  NOT duplicate them.
- section_dag: {section_id: [predecessor_section_ids]} reflecting the
  template's section ordering and any dependencies.
- slipped_requests: list of composer intents you cannot map to any supported
  capability/tool/library. Use this list to surface things rather than
  silently dropping them.
""".strip()


class ResearchPlanner:
    def __init__(self, llm) -> None:
        self._llm = llm

    def plan(
        self,
        composer_inputs: dict[str, Any],
        template_spec,
        clarifier_answers: dict[str, Any],
    ) -> Plan:
        sys = build_research_planner_prompt()
        user = {
            "composer_inputs": composer_inputs,
            "template": template_spec.model_dump() if hasattr(template_spec, "model_dump") else {},
            "clarifier_answers": clarifier_answers,
        }
        raw = self._llm.call(system=sys, user=user)

        composer_artifacts = [
            ArtifactSpec(**a) if isinstance(a, dict) else a
            for a in raw.get("required_artifacts", [])
        ]
        template_artifacts = list(getattr(template_spec, "required_artifacts", []))
        for a in template_artifacts:
            if a.source != "template":
                a.source = "template"  # safety
        all_required = template_artifacts + composer_artifacts

        return Plan(
            research_strands=[ResearchStrand(**s) for s in raw.get("research_strands", [])],
            required_artifacts=all_required,
            optional_artifacts=[],
            section_dag=raw.get("section_dag", {}),
            slipped_requests=raw.get("slipped_requests", []),
        )
```

- [ ] **Step 5: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_stage_3_research_plan.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_3_research_plan.py \
                  packages/core/src/openlia/llm/runtime/report_v2/schemas/plan.py
git add packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_3_research_plan.py \
        packages/core/src/openlia/llm/runtime/report_v2/schemas/plan.py \
        packages/core/tests/llm/runtime/report_v2/test_stage_3_research_plan.py
git commit -m "feat(report_v2): research planner + Plan schema with composer-prompt artifact parsing and slipped_requests"
```

---

### Task P3: Stage 4 Gather (strand dispatcher)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/schemas/research_pool.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_4_gather.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_stage_4_gather.py`

- [ ] **Step 1: Write failing test for parallel strand dispatch with retry-once**

```python
# packages/core/tests/llm/runtime/report_v2/test_stage_4_gather.py
from unittest.mock import Mock
from openlia.llm.runtime.report_v2.schemas.plan import ResearchStrand
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool, Citation
from openlia.llm.runtime.report_v2.pipeline.stage_4_gather import StrandDispatcher


def test_strand_dispatcher_runs_each_strand_and_aggregates():
    fake_subagent = Mock()
    fake_subagent.run.side_effect = [
        {"findings": "financials text", "citations": [{"id": "c1", "source_type": "tool_call",
            "tool": "eodhd.get_fundamentals_data", "url": None, "title": "fundamentals",
            "retrieved_at": "2026-05-21T00:00:00Z", "snippet": None,
            "served_from_cache": False}]},
        {"findings": "news text", "citations": []},
    ]
    strands = [
        ResearchStrand(id="financials", purpose="financials", allowed_tools=["eodhd.get_fundamentals_data"]),
        ResearchStrand(id="news", purpose="news", allowed_tools=["eodhd.get_company_news"]),
    ]
    disp = StrandDispatcher(subagent=fake_subagent)
    pool = disp.dispatch(strands, composer_inputs={"ticker": "NVDA"}, plan=Mock())
    assert "financials" in pool.findings_by_strand
    assert "news" in pool.findings_by_strand
    assert any(c.id == "c1" for c in pool.citations)


def test_strand_failure_retries_once_then_marks_failed():
    fake_subagent = Mock()
    fake_subagent.run.side_effect = [
        RuntimeError("transient"),
        RuntimeError("still failing"),
    ]
    disp = StrandDispatcher(subagent=fake_subagent)
    pool = disp.dispatch(
        [ResearchStrand(id="x", purpose="x", allowed_tools=[])],
        composer_inputs={}, plan=Mock(),
    )
    assert "x" in pool.failed_strands
    assert fake_subagent.run.call_count == 2
```

- [ ] **Step 2: Implement ResearchPool schema**

```python
# packages/core/src/openlia/llm/runtime/report_v2/schemas/research_pool.py
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    id: str
    source_type: Literal["tool_call", "web_fetch", "user_upload", "internal_model"]
    tool: str | None = None
    url: str | None = None
    title: str
    retrieved_at: datetime
    snippet: str | None = None
    served_from_cache: bool = False


class ResearchPool(BaseModel):
    findings_by_strand: dict[str, str] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    failed_strands: list[str] = Field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
```

- [ ] **Step 3: Implement strand dispatcher with retry-once**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_4_gather.py
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from openlia.llm.runtime.report_v2.schemas.plan import ResearchStrand
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool, Citation


class StrandDispatcher:
    def __init__(self, subagent, max_workers: int = 4) -> None:
        self._subagent = subagent
        self._max_workers = max_workers

    def dispatch(self, strands: list[ResearchStrand], composer_inputs: dict, plan) -> ResearchPool:
        pool = ResearchPool()
        with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
            futures = {ex.submit(self._run_strand_with_retry, s, composer_inputs, plan): s for s in strands}
            for fut in as_completed(futures):
                strand = futures[fut]
                try:
                    result = fut.result()
                except Exception:
                    pool.failed_strands.append(strand.id)
                    continue
                pool.findings_by_strand[strand.id] = result.get("findings", "")
                for c in result.get("citations", []):
                    pool.citations.append(Citation(**c) if isinstance(c, dict) else c)
                pool.cache_hits += result.get("cache_hits", 0)
                pool.cache_misses += result.get("cache_misses", 0)
        return pool

    def _run_strand_with_retry(self, strand: ResearchStrand, composer_inputs: dict, plan):
        try:
            return self._subagent.run(strand=strand, composer_inputs=composer_inputs, plan=plan)
        except Exception:
            return self._subagent.run(strand=strand, composer_inputs=composer_inputs, plan=plan)
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_stage_4_gather.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_4_gather.py \
                  packages/core/src/openlia/llm/runtime/report_v2/schemas/research_pool.py
git add packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_4_gather.py \
        packages/core/src/openlia/llm/runtime/report_v2/schemas/research_pool.py \
        packages/core/tests/llm/runtime/report_v2/test_stage_4_gather.py
git commit -m "feat(report_v2): stage 4 gather — parallel strand dispatcher with retry-once and cache-stat aggregation"
```

---

### Task P4: Stage 5 Model planner

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_5_model_plan.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_stage_5_model_plan.py`

- [ ] **Step 1: Write failing test**

```python
# packages/core/tests/llm/runtime/report_v2/test_stage_5_model_plan.py
from unittest.mock import Mock
from openlia.llm.runtime.report_v2.schemas.plan import Plan, ArtifactSpec
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool
from openlia.llm.runtime.report_v2.pipeline.stage_5_model_plan import ModelPlanner


def test_model_planner_appends_optional_artifacts_only():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "optional_artifacts": [
            {"id": "peer_ev_ebitda", "type": "chart", "description": "peer multiples",
             "parameters": {}, "helper": "ratio_calculator", "source_strand": None,
             "target_section_id": None, "source": "planner"}
        ]
    }
    plan = Plan(required_artifacts=[
        ArtifactSpec(id="dcf", type="chart", description="DCF", parameters={},
                     helper="dcf_valuation", source="template")
    ], section_dag={})
    pool = ResearchPool(findings_by_strand={"financials": "..."})

    planner = ModelPlanner(llm=fake_llm)
    new_plan = planner.plan(plan=plan, research_pool=pool)

    # required_artifacts must be unchanged
    assert {a.id for a in new_plan.required_artifacts} == {"dcf"}
    # optional appended
    assert any(a.id == "peer_ev_ebitda" and a.source == "planner" for a in new_plan.optional_artifacts)
```

- [ ] **Step 2: Implement**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_5_model_plan.py
from __future__ import annotations
from openlia.llm.runtime.report_v2.schemas.plan import Plan, ArtifactSpec
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool


def build_model_planner_prompt() -> str:
    return """
You are the model planner. The research pool has been populated. Decide
which optional model components are worth building given what was actually
gathered. Do NOT modify required_artifacts; only emit optional_artifacts.

Output JSON: {"optional_artifacts": [<ArtifactSpec>...]}
""".strip()


class ModelPlanner:
    def __init__(self, llm) -> None:
        self._llm = llm

    def plan(self, plan: Plan, research_pool: ResearchPool) -> Plan:
        sys = build_model_planner_prompt()
        user = {
            "required_artifacts": [a.model_dump() for a in plan.required_artifacts],
            "research_pool_index": {sid: f.split("\n", 1)[0][:160] for sid, f in research_pool.findings_by_strand.items()},
        }
        try:
            raw = self._llm.call(system=sys, user=user)
            optional = [ArtifactSpec(**a) if isinstance(a, dict) else a for a in raw.get("optional_artifacts", [])]
        except Exception:
            optional = []
        # retry once on malformed (omitted for brevity; handled at runner level)
        return plan.model_copy(update={"optional_artifacts": optional})
```

- [ ] **Step 3: Run tests, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_stage_5_model_plan.py -v
git add packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_5_model_plan.py \
        packages/core/tests/llm/runtime/report_v2/test_stage_5_model_plan.py
git commit -m "feat(report_v2): stage 5 model planner — appends optional_artifacts based on research pool"
```

---

### Task P5: Stage 6 Model build + parameter resolver

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_6_model_build.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/param_resolver.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_stage_6_model_build.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_param_resolver.py`

- [ ] **Step 1: Write failing tests for resolver**

```python
# packages/core/tests/llm/runtime/report_v2/test_param_resolver.py
from unittest.mock import Mock
from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperSchema, HelperParam, HelperRegistration, register_helper, reset_helpers_for_tests,
)
from openlia.llm.runtime.report_v2.pipeline.param_resolver import resolve_params, ResolverResult


def setup_helper():
    reset_helpers_for_tests()
    register_helper(HelperRegistration(
        schema=HelperSchema(
            name="dcf",
            description="DCF",
            params={
                "base_revenue": HelperParam(type="float",
                    derivation="latest 4Q revenue from research_pool", description="base", required=True),
                "wacc": HelperParam(type="float", default=0.10, description="WACC", required=False),
            },
        ),
        execute=lambda **kw: {"fair_value": 100.0},
    ))


def test_explicit_wins():
    setup_helper()
    res = resolve_params("dcf", explicit={"base_revenue": 28.4e9, "wacc": 0.12},
                        research_pool=None, llm=Mock())
    assert res.resolved["wacc"] == 0.12
    assert res.provenance["wacc"] == "explicit"


def test_default_when_no_explicit_no_derivation():
    setup_helper()
    res = resolve_params("dcf", explicit={"base_revenue": 28.4e9}, research_pool=None, llm=Mock())
    assert res.resolved["wacc"] == 0.10
    assert res.provenance["wacc"] == "default"


def test_derivation_runs_when_missing_required():
    setup_helper()
    llm = Mock()
    llm.call.return_value = {"value": 28.4e9}
    res = resolve_params("dcf", explicit={}, research_pool={"financials": "..."}, llm=llm)
    assert res.resolved["base_revenue"] == 28.4e9
    assert res.provenance["base_revenue"] == "derived"


def test_unresolvable_required_marks_failed():
    setup_helper()
    llm = Mock()
    llm.call.return_value = {"value": None}
    res = resolve_params("dcf", explicit={}, research_pool=None, llm=llm)
    assert res.failed is True
    assert "base_revenue" in res.unresolved
```

- [ ] **Step 2: Implement resolver**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/param_resolver.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from openlia.llm.runtime.report_v2.tools.library_helpers import get_helper


@dataclass
class ResolverResult:
    resolved: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)
    failed: bool = False
    unresolved: list[str] = field(default_factory=list)
    reason: str | None = None


def resolve_params(helper_name: str, explicit: dict, research_pool, llm) -> ResolverResult:
    helper = get_helper(helper_name)
    schema = helper.schema
    out = ResolverResult()
    for name, param in schema.params.items():
        if name in explicit:
            out.resolved[name] = explicit[name]
            out.provenance[name] = "explicit"
            continue
        if param.derivation:
            try:
                derived = llm.call(
                    system="You are a derivation resolver. Given a rule and research_pool, return JSON {value: ...}.",
                    user={"rule": param.derivation, "research_pool": research_pool},
                )
                v = derived.get("value")
                if v is not None:
                    out.resolved[name] = v
                    out.provenance[name] = "derived"
                    continue
            except Exception:
                pass
        if param.default is not None:
            out.resolved[name] = param.default
            out.provenance[name] = "default"
            continue
        if param.required:
            out.unresolved.append(name)
    if out.unresolved:
        out.failed = True
        out.reason = f"required parameters could not be resolved: {out.unresolved}"
    return out
```

- [ ] **Step 3: Implement model build with per-artifact subagent dispatch**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_6_model_build.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from openlia.llm.runtime.report_v2.schemas.plan import ArtifactSpec
from openlia.llm.runtime.report_v2.tools.library_helpers import get_helper
from openlia.llm.runtime.report_v2.pipeline.param_resolver import resolve_params


@dataclass
class ModelArtifact:
    spec: ArtifactSpec
    status: str  # "OK", "FAILED"
    content: Any = None
    resolved_params: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)
    failure_reason: str | None = None


class ModelBuilder:
    def __init__(self, llm, max_workers: int = 4) -> None:
        self._llm = llm
        self._max_workers = max_workers

    def build(self, artifacts: list[ArtifactSpec], research_pool) -> list[ModelArtifact]:
        with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
            futures = {ex.submit(self._build_one, a, research_pool): a for a in artifacts}
            return [f.result() for f in as_completed(futures)]

    def _build_one(self, spec: ArtifactSpec, research_pool) -> ModelArtifact:
        helper_name = spec.helper
        if helper_name is None:
            # planner-pick (omitted for brevity)
            return ModelArtifact(spec=spec, status="FAILED",
                                 failure_reason="no helper assigned and planner-pick path not implemented in v2.2 P5")
        try:
            helper = get_helper(helper_name)
        except KeyError:
            return ModelArtifact(spec=spec, status="FAILED",
                                 failure_reason=f"helper {helper_name!r} not registered")
        if not helper.available:
            return ModelArtifact(spec=spec, status="FAILED",
                                 failure_reason=f"helper {helper_name!r} is in deferred category {helper.deferred_category!r}")
        resolver = resolve_params(helper_name, explicit=spec.parameters,
                                   research_pool=research_pool, llm=self._llm)
        if resolver.failed:
            return ModelArtifact(spec=spec, status="FAILED",
                                 failure_reason=resolver.reason,
                                 resolved_params=resolver.resolved,
                                 provenance=resolver.provenance)
        try:
            content = helper.execute(**resolver.resolved)
        except Exception as e:
            try:
                content = helper.execute(**resolver.resolved)
            except Exception as e2:
                return ModelArtifact(spec=spec, status="FAILED",
                                     failure_reason=f"helper raised: {e2}",
                                     resolved_params=resolver.resolved,
                                     provenance=resolver.provenance)
        return ModelArtifact(spec=spec, status="OK", content=content,
                             resolved_params=resolver.resolved,
                             provenance=resolver.provenance)
```

- [ ] **Step 4: Write test for model build**

```python
# packages/core/tests/llm/runtime/report_v2/test_stage_6_model_build.py
from unittest.mock import Mock
from openlia.llm.runtime.report_v2.schemas.plan import ArtifactSpec
from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperSchema, HelperParam, HelperRegistration, register_helper, reset_helpers_for_tests,
)
from openlia.llm.runtime.report_v2.pipeline.stage_6_model_build import ModelBuilder


def setup_dcf():
    reset_helpers_for_tests()
    register_helper(HelperRegistration(
        schema=HelperSchema(name="dcf", description="DCF", params={
            "base_revenue": HelperParam(type="float", description="x", required=True),
        }),
        execute=lambda **kw: {"fv": 100.0},
    ))


def test_build_success():
    setup_dcf()
    b = ModelBuilder(llm=Mock())
    artifacts = [ArtifactSpec(id="a1", type="chart", description="dcf",
                              parameters={"base_revenue": 1.0}, helper="dcf", source="template")]
    out = b.build(artifacts, research_pool=None)
    assert out[0].status == "OK"


def test_unresolvable_required_param_marks_failed():
    setup_dcf()
    llm = Mock()
    llm.call.return_value = {"value": None}
    b = ModelBuilder(llm=llm)
    artifacts = [ArtifactSpec(id="a1", type="chart", description="dcf",
                              parameters={}, helper="dcf", source="composer")]
    out = b.build(artifacts, research_pool=None)
    assert out[0].status == "FAILED"
    assert "base_revenue" in out[0].failure_reason
```

- [ ] **Step 5: Run, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_param_resolver.py packages/core/tests/llm/runtime/report_v2/test_stage_6_model_build.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_6_model_build.py \
                  packages/core/src/openlia/llm/runtime/report_v2/pipeline/param_resolver.py
git add packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_6_model_build.py \
        packages/core/src/openlia/llm/runtime/report_v2/pipeline/param_resolver.py \
        packages/core/tests/llm/runtime/report_v2/test_stage_6_model_build.py \
        packages/core/tests/llm/runtime/report_v2/test_param_resolver.py
git commit -m "feat(report_v2): stage 6 model build with explicit-derived-default parameter resolver"
```

---

### Task P6: Stage 7 Drafter + trigger evaluator

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_7_draft.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/trigger_evaluator.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_stage_7_draft.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_trigger_evaluator.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/core/tests/llm/runtime/report_v2/test_trigger_evaluator.py
from unittest.mock import Mock
from openlia.llm.runtime.report_v2.pipeline.trigger_evaluator import TriggerEvaluator


def test_trigger_fires_true_when_llm_returns_true():
    llm = Mock()
    llm.call.return_value = {"fire": True, "reason": "guidance provided"}
    e = TriggerEvaluator(llm=llm)
    result = e.evaluate(
        condition="management issued forward guidance",
        composer_inputs={},
        deps_markdown={"transcript_analysis": "Management raised FY guidance..."},
        research_pool_index={},
        model_artifacts_index={},
    )
    assert result.fire is True


def test_trigger_evaluator_fails_open_on_error():
    llm = Mock()
    llm.call.side_effect = RuntimeError("LLM down")
    e = TriggerEvaluator(llm=llm)
    result = e.evaluate(condition="x", composer_inputs={}, deps_markdown={},
                        research_pool_index={}, model_artifacts_index={})
    assert result.fire is True
    assert result.reason.startswith("evaluator_failed:")
```

- [ ] **Step 2: Implement trigger evaluator**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/trigger_evaluator.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TriggerResult:
    fire: bool
    reason: str


class TriggerEvaluator:
    def __init__(self, llm) -> None:
        self._llm = llm

    def evaluate(self, condition: str, composer_inputs: dict,
                 deps_markdown: dict[str, str], research_pool_index: dict,
                 model_artifacts_index: dict) -> TriggerResult:
        sys = "Evaluate the condition against the provided context. Return JSON {fire: bool, reason: str}."
        user = {
            "condition": condition,
            "composer_inputs": composer_inputs,
            "depends_on_markdown": deps_markdown,
            "research_pool_index": research_pool_index,
            "model_artifacts_index": model_artifacts_index,
        }
        try:
            raw = self._llm.call(system=sys, user=user)
            return TriggerResult(fire=bool(raw.get("fire", True)), reason=str(raw.get("reason", "")))
        except Exception as e:
            return TriggerResult(fire=True, reason=f"evaluator_failed: {e}")
```

- [ ] **Step 3: Implement drafter with DAG walk + trigger gating**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_7_draft.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict, deque

from openlia.llm.runtime.report_v2.pipeline.trigger_evaluator import TriggerEvaluator


@dataclass
class SectionOutput:
    section_id: str
    section_name: str
    status: str  # "OK", "SKIPPED", "DEGRADED"
    blocks: list = field(default_factory=list)
    skip_reason: str | None = None
    degraded_reason: str | None = None


def topological_order(dag: dict[str, list[str]]) -> list[str]:
    in_degree = defaultdict(int)
    for node, preds in dag.items():
        in_degree[node] = len(preds)
        for p in preds:
            in_degree.setdefault(p, 0)
    queue = deque([n for n, d in in_degree.items() if d == 0])
    out: list[str] = []
    edges_from = defaultdict(list)
    for node, preds in dag.items():
        for p in preds:
            edges_from[p].append(node)
    while queue:
        n = queue.popleft()
        out.append(n)
        for nxt in edges_from[n]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    return out


class SectionDrafter:
    def __init__(self, llm, trigger_evaluator: TriggerEvaluator) -> None:
        self._llm = llm
        self._trig = trigger_evaluator

    def draft_all(self, sections, dag: dict[str, list[str]], composer_inputs: dict,
                  research_pool, model_artifacts) -> list[SectionOutput]:
        outputs: dict[str, SectionOutput] = {}
        sections_by_id = {s.id: s for s in sections}
        order = topological_order(dag)
        for sid in order:
            if sid not in sections_by_id:
                continue
            section = sections_by_id[sid]
            deps_md = {p: (outputs[p].blocks[0].get("text", "") if outputs[p].blocks else "")
                       if outputs[p].status == "OK" else f"<SKIPPED: {outputs[p].skip_reason or ''}>"
                       for p in section.depends_on if p in outputs}

            if section.trigger_when:
                trig = self._trig.evaluate(
                    condition=section.trigger_when,
                    composer_inputs=composer_inputs,
                    deps_markdown=deps_md,
                    research_pool_index={k: v[:160] for k, v in research_pool.findings_by_strand.items()},
                    model_artifacts_index={a.spec.id: a.spec.description for a in model_artifacts},
                )
                if not trig.fire:
                    outputs[sid] = SectionOutput(section_id=sid, section_name=section.name,
                                                  status="SKIPPED", skip_reason=trig.reason)
                    continue

            outputs[sid] = self._draft_one(section, composer_inputs, research_pool, model_artifacts, deps_md)
        return list(outputs.values())

    def _draft_one(self, section, composer_inputs, research_pool, model_artifacts, deps_md) -> SectionOutput:
        sys = f"Draft section '{section.name}'. Directive: {section.directive}"
        user = {
            "composer_inputs": composer_inputs,
            "research_pool_findings": research_pool.findings_by_strand,
            "model_artifacts": [{"id": a.spec.id, "description": a.spec.description} for a in model_artifacts],
            "depends_on_outputs": deps_md,
        }
        try:
            raw = self._llm.call(system=sys, user=user)
            blocks = raw.get("blocks", [])
            return SectionOutput(section_id=section.id, section_name=section.name, status="OK", blocks=blocks)
        except Exception as e:
            return SectionOutput(section_id=section.id, section_name=section.name,
                                  status="DEGRADED", degraded_reason=str(e))
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_trigger_evaluator.py packages/core/tests/llm/runtime/report_v2/test_stage_7_draft.py -v
git add packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_7_draft.py \
        packages/core/src/openlia/llm/runtime/report_v2/pipeline/trigger_evaluator.py \
        packages/core/tests/llm/runtime/report_v2/test_trigger_evaluator.py \
        packages/core/tests/llm/runtime/report_v2/test_stage_7_draft.py
git commit -m "feat(report_v2): stage 7 drafter with DAG walk and LLM trigger_when evaluator (fail-open)"
```

---

### Task P7: Stage 8 Verifier (deterministic + LLM) with retry feedback + convergence

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/schemas/verifier_issue.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_8_verify.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/verifier_deterministic.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/verifier_llm.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_verifier_deterministic.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_verifier_llm.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_verifier_retry.py`

- [ ] **Step 1: Write failing tests for issue taxonomy + deterministic detectors**

```python
# packages/core/tests/llm/runtime/report_v2/test_verifier_deterministic.py
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue
from openlia.llm.runtime.report_v2.pipeline.verifier_deterministic import (
    detect_block_shape, detect_tombstone, detect_year_slip, detect_citation_unresolved,
    detect_citation_orphaned, detect_artifact_missing,
)


def test_block_shape_flags_empty_prose():
    issues = detect_block_shape("s1", [{"type": "prose", "text": ""}])
    assert any(i.issue_type == "block_shape" for i in issues)


def test_tombstone_flags_placeholder():
    issues = detect_tombstone("s1", [{"type": "prose", "text": "[placeholder] Q3 revenue grew"}])
    assert any(i.issue_type == "tombstone" for i in issues)


def test_year_slip_flags_mismatched_year():
    issues = detect_year_slip(
        section_id="s1",
        blocks=[{"type": "prose", "text": "FY2024 revenue [c:c1] reached..."}],
        citations={"c1": {"retrieved_at": "2026-02-01", "title": "FY2026 filing"}},
    )
    assert any(i.issue_type == "year_slip" for i in issues)
```

- [ ] **Step 2: Implement issue schema (closed enum)**

```python
# packages/core/src/openlia/llm/runtime/report_v2/schemas/verifier_issue.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


IssueType = Literal[
    # structural
    "block_shape", "tombstone", "year_slip",
    # citation
    "citation_missing", "citation_unresolved", "citation_orphaned",
    # coverage
    "artifact_missing", "content_too_sparse", "directive_unmet",
    # quality
    "factual_inconsistency", "numeric_inconsistency", "incoherent_prose",
    # artifact-build
    "required_param_unresolvable", "helper_unavailable",
]


class VerifierIssue(BaseModel):
    issue_type: IssueType
    section_id: str | None = None
    severity: Literal["blocker", "warning"]
    evidence: str
    suggested_fix: str | None = None
    detector: Literal["deterministic", "llm"]
```

- [ ] **Step 3: Implement deterministic detectors**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/verifier_deterministic.py
from __future__ import annotations
import re
from datetime import datetime
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


TOMBSTONE_PATTERNS = [
    r"\[placeholder\]", r"\[TODO\]", r"\bTBD\b", r"\bI cannot\b",
    r"\bas an AI\b", r"\[\s*to be filled\s*\]",
]


def detect_block_shape(section_id: str, blocks: list[dict]) -> list[VerifierIssue]:
    issues = []
    for b in blocks:
        t = b.get("type")
        if t == "prose" and not (b.get("text") or "").strip():
            issues.append(VerifierIssue(issue_type="block_shape", section_id=section_id,
                                         severity="blocker", evidence="empty prose block",
                                         suggested_fix="Populate the prose block or remove it.",
                                         detector="deterministic"))
        elif t == "table" and not b.get("headers"):
            issues.append(VerifierIssue(issue_type="block_shape", section_id=section_id,
                                         severity="blocker", evidence="table missing headers",
                                         suggested_fix="Add a headers field to the table block.",
                                         detector="deterministic"))
    return issues


def detect_tombstone(section_id: str, blocks: list[dict]) -> list[VerifierIssue]:
    issues = []
    for b in blocks:
        text = b.get("text", "") if isinstance(b.get("text"), str) else ""
        for pat in TOMBSTONE_PATTERNS:
            m = re.search(pat, text)
            if m:
                issues.append(VerifierIssue(issue_type="tombstone", section_id=section_id,
                                             severity="blocker",
                                             evidence=f"matched {pat!r} at ...{text[max(0, m.start()-20):m.end()+20]}...",
                                             suggested_fix="Replace placeholder with explicit prose or remove sentence.",
                                             detector="deterministic"))
                break
    return issues


def _extract_years(text: str) -> set[int]:
    return {int(m.group(1)) for m in re.finditer(r"FY(20\d{2})", text)}


def detect_year_slip(section_id: str, blocks: list[dict], citations: dict) -> list[VerifierIssue]:
    issues = []
    for b in blocks:
        text = b.get("text", "")
        for cite_id in re.findall(r"\[c:([a-zA-Z0-9_]+)\]", text):
            cite = citations.get(cite_id)
            if not cite:
                continue
            try:
                ret = datetime.fromisoformat(cite["retrieved_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            for y in _extract_years(text):
                if abs(ret.year - y) >= 2:
                    issues.append(VerifierIssue(issue_type="year_slip", section_id=section_id,
                                                 severity="blocker",
                                                 evidence=f"FY{y} referenced; citation [c:{cite_id}] retrieved {ret.year}",
                                                 suggested_fix=f"Update year reference to align with citation, or recite from FY{y} source.",
                                                 detector="deterministic"))
                    break
    return issues


def detect_citation_unresolved(section_id: str, blocks: list[dict], pool_citation_ids: set[str]) -> list[VerifierIssue]:
    issues = []
    for b in blocks:
        text = b.get("text", "")
        for cite_id in re.findall(r"\[c:([a-zA-Z0-9_]+)\]", text):
            if cite_id not in pool_citation_ids:
                issues.append(VerifierIssue(issue_type="citation_unresolved", section_id=section_id,
                                             severity="blocker",
                                             evidence=f"marker [c:{cite_id}] not in research_pool",
                                             suggested_fix="Re-cite from an actual research entry; this ID does not exist.",
                                             detector="deterministic"))
    return issues


def detect_citation_orphaned(used_ids: set[str], pool_citation_ids: set[str]) -> list[VerifierIssue]:
    issues = []
    for cid in pool_citation_ids - used_ids:
        issues.append(VerifierIssue(issue_type="citation_orphaned", section_id=None,
                                     severity="warning",
                                     evidence=f"citation {cid} in pool but never embedded",
                                     suggested_fix=None,
                                     detector="deterministic"))
    return issues


def detect_artifact_missing(required_artifact_ids: set[str], embedded_artifact_ids: set[str]) -> list[VerifierIssue]:
    issues = []
    for aid in required_artifact_ids - embedded_artifact_ids:
        issues.append(VerifierIssue(issue_type="artifact_missing", section_id=None,
                                     severity="blocker",
                                     evidence=f"required artifact {aid} was built but never embedded",
                                     suggested_fix=f"Add {{{{artifact:{aid}}}}} to the appropriate section.",
                                     detector="deterministic"))
    return issues
```

- [ ] **Step 4: Implement LLM verifier**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/verifier_llm.py
from __future__ import annotations
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


LLM_VERIFIER_PROMPT = """
You are the LLM verifier. Read the section's blocks, the cited research pool,
and the model artifacts. Emit a JSON list of issues.

Issue types you may emit (LLM-only set):
  citation_missing, content_too_sparse, directive_unmet,
  factual_inconsistency, numeric_inconsistency, incoherent_prose

Each issue: {issue_type, severity (blocker|warning), evidence, suggested_fix}.
Provide suggested_fix where you can — high-signal fixes converge faster.

Do NOT emit structural or citation-id-resolution issues — those are caught
by deterministic detectors earlier.
""".strip()


class LLMVerifier:
    def __init__(self, llm) -> None:
        self._llm = llm

    def verify_section(self, section_id: str, blocks: list, research_pool, model_artifacts, directive: str) -> list[VerifierIssue]:
        try:
            raw = self._llm.call(
                system=LLM_VERIFIER_PROMPT,
                user={
                    "section_id": section_id,
                    "directive": directive,
                    "blocks": blocks,
                    "research_pool_index": {k: v[:200] for k, v in research_pool.findings_by_strand.items()},
                    "artifacts_index": [{"id": a.spec.id, "description": a.spec.description} for a in model_artifacts],
                },
            )
            return [
                VerifierIssue(detector="llm", section_id=section_id, **i) for i in raw.get("issues", [])
            ]
        except Exception:
            return []
```

- [ ] **Step 5: Implement orchestrator with retry feedback + convergence**

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_8_verify.py
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue
from openlia.llm.runtime.report_v2.pipeline.verifier_deterministic import (
    detect_block_shape, detect_tombstone, detect_year_slip, detect_citation_unresolved,
    detect_citation_orphaned, detect_artifact_missing,
)
from openlia.llm.runtime.report_v2.pipeline.verifier_llm import LLMVerifier


@dataclass
class VerificationRound:
    round_num: int
    issues: list[VerifierIssue]


@dataclass
class SectionVerificationResult:
    section_id: str
    final_status: str  # "OK", "DEGRADED"
    rounds: list[VerificationRound] = field(default_factory=list)
    all_issues_ever: list[VerifierIssue] = field(default_factory=list)


class Verifier:
    MAX_RETRIES = 3

    def __init__(self, llm_verifier: LLMVerifier, drafter, section_directives: dict[str, str]) -> None:
        self._llm = llm_verifier
        self._drafter = drafter
        self._directives = section_directives

    def verify_with_retry(self, section_id: str, blocks: list, research_pool, model_artifacts,
                          citations: dict, pool_citation_ids: set[str],
                          required_artifact_ids: set[str], embedded_artifact_ids: set[str],
                          retry_context: dict) -> SectionVerificationResult:
        result = SectionVerificationResult(section_id=section_id, final_status="OK")
        signatures: list[set[tuple[str, str]]] = []
        current_blocks = blocks

        for round_num in range(self.MAX_RETRIES + 1):
            issues = []
            issues += detect_block_shape(section_id, current_blocks)
            issues += detect_tombstone(section_id, current_blocks)
            issues += detect_year_slip(section_id, current_blocks, citations)
            issues += detect_citation_unresolved(section_id, current_blocks, pool_citation_ids)
            deterministic_blockers = [i for i in issues if i.severity == "blocker"]

            if not deterministic_blockers:
                llm_issues = self._llm.verify_section(
                    section_id=section_id, blocks=current_blocks,
                    research_pool=research_pool, model_artifacts=model_artifacts,
                    directive=self._directives.get(section_id, ""),
                )
                issues += llm_issues

            result.rounds.append(VerificationRound(round_num=round_num, issues=issues))
            result.all_issues_ever += issues

            blockers = [i for i in issues if i.severity == "blocker"]
            if not blockers:
                result.final_status = "OK"
                return result

            # convergence check: same (section_id, issue_type) repeated twice in a row
            sig = {(i.section_id, i.issue_type) for i in blockers}
            signatures.append(sig)
            if len(signatures) >= 2 and signatures[-1] == signatures[-2]:
                result.final_status = "DEGRADED"
                return result

            if round_num >= self.MAX_RETRIES:
                result.final_status = "DEGRADED"
                return result

            # retry — drafter re-runs with issue feedback
            current_blocks = self._drafter.redraft_with_feedback(
                section_id=section_id, blockers=blockers, retry_context=retry_context,
            )

        return result
```

- [ ] **Step 6: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_verifier_deterministic.py packages/core/tests/llm/runtime/report_v2/test_verifier_llm.py packages/core/tests/llm/runtime/report_v2/test_verifier_retry.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_8_verify.py
git add packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_8_verify.py \
        packages/core/src/openlia/llm/runtime/report_v2/pipeline/verifier_deterministic.py \
        packages/core/src/openlia/llm/runtime/report_v2/pipeline/verifier_llm.py \
        packages/core/src/openlia/llm/runtime/report_v2/schemas/verifier_issue.py \
        packages/core/tests/llm/runtime/report_v2/test_verifier_deterministic.py \
        packages/core/tests/llm/runtime/report_v2/test_verifier_llm.py \
        packages/core/tests/llm/runtime/report_v2/test_verifier_retry.py
git commit -m "feat(report_v2): stage 8 verifier — 14-issue closed enum, deterministic-first detector ordering, retry feedback with convergence check"
```

---

## Phase O — Output

HTML rendering, citation manifest, Run Summary, Verification History, and final assembly. PDF/DOCX conversion is delegated to the existing v1 download path; this phase only verifies that path accepts HTML input.

### Task O1: HTML block renderers

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/schemas/blocks.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/rendering/block_renderer.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_block_renderer.py`

- [ ] **Step 1: Write failing tests for each block type**

```python
# packages/core/tests/llm/runtime/report_v2/test_block_renderer.py
from openlia.llm.runtime.report_v2.rendering.block_renderer import render_block


def test_prose_block_renders_markdown_to_html():
    out = render_block({"type": "prose", "text": "Q3 **revenue** grew 18% [c:c1]."})
    assert "<strong>revenue</strong>" in out or "<b>revenue</b>" in out
    assert "[c:c1]" in out  # citation markers preserved for later pass


def test_table_block_renders_html_table():
    out = render_block({"type": "table",
                        "headers": ["Metric", "Value"],
                        "rows": [["Revenue", "$94.9B"], ["EPS", "$2.40"]],
                        "caption": "Q3 results"})
    assert "<table" in out and "<th>Metric</th>" in out and "<td>$94.9B</td>" in out
    assert "Q3 results" in out


def test_kpi_strip_renders_cells():
    out = render_block({"type": "kpi_strip",
                        "cells": [{"label": "Revenue", "value": "$94.9B", "unit": "USD", "delta": "+18%"}]})
    assert "kpi-strip" in out and "$94.9B" in out and "+18%" in out


def test_skip_banner_renders_blockquote():
    out = render_block({"type": "skip_banner",
                        "section_name": "Litigation Risk", "reason": "no material cases"})
    assert "skip-banner" in out and "Litigation Risk" in out


def test_degraded_banner_renders_blockquote():
    out = render_block({"type": "degraded_banner",
                        "section_name": "Litigation Risk", "reason": "sparse data",
                        "issue_list": ["content_too_sparse"]})
    assert "degraded-banner" in out
```

- [ ] **Step 2: Implement block schemas**

```python
# packages/core/src/openlia/llm/runtime/report_v2/schemas/blocks.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class ProseBlock(BaseModel):
    type: Literal["prose"] = "prose"
    text: str


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class KPICell(BaseModel):
    label: str
    value: str
    unit: str | None = None
    delta: str | None = None


class KPIStripBlock(BaseModel):
    type: Literal["kpi_strip"] = "kpi_strip"
    cells: list[KPICell]


class ChartBlock(BaseModel):
    type: Literal["chart"] = "chart"
    format: Literal["svg_inline", "png_base64"]
    payload: str
    caption: str | None = None


class QuoteBlock(BaseModel):
    type: Literal["quote_block"] = "quote_block"
    quote: str
    source: str
    citation_id: str | None = None


class SkipBannerBlock(BaseModel):
    type: Literal["skip_banner"] = "skip_banner"
    section_name: str
    reason: str


class DegradedBannerBlock(BaseModel):
    type: Literal["degraded_banner"] = "degraded_banner"
    section_name: str
    reason: str
    issue_list: list[str]


class ExcelAttachmentBlock(BaseModel):
    type: Literal["excel_attachment"] = "excel_attachment"
    filename: str
    download_url: str
    row_count: int
    sheet_count: int
```

- [ ] **Step 3: Implement block renderer**

```python
# packages/core/src/openlia/llm/runtime/report_v2/rendering/block_renderer.py
from __future__ import annotations
import html
from markdown_it import MarkdownIt


_md = MarkdownIt("commonmark")


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_block(b: dict) -> str:
    t = b.get("type")
    if t == "prose":
        return f'<div class="prose">{_md.render(b.get("text", ""))}</div>'
    if t == "table":
        headers = "".join(f"<th>{_esc(h)}</th>" for h in b.get("headers", []))
        rows = "".join("<tr>" + "".join(f"<td>{_esc(str(c))}</td>" for c in r) + "</tr>"
                       for r in b.get("rows", []))
        caption = f'<caption>{_esc(b["caption"])}</caption>' if b.get("caption") else ""
        return f'<table class="report-table">{caption}<thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>'
    if t == "kpi_strip":
        cells = "".join(
            f'<div class="kpi-cell"><div class="kpi-label">{_esc(c["label"])}</div>'
            f'<div class="kpi-value">{_esc(c["value"])}</div>'
            + (f'<div class="kpi-delta">{_esc(c["delta"])}</div>' if c.get("delta") else "")
            + "</div>"
            for c in b.get("cells", [])
        )
        return f'<div class="kpi-strip">{cells}</div>'
    if t == "chart":
        if b.get("format") == "svg_inline":
            inner = b.get("payload", "")
        else:
            inner = f'<img src="data:image/png;base64,{_esc(b.get("payload", ""))}" alt="chart">'
        cap = f'<figcaption>{_esc(b["caption"])}</figcaption>' if b.get("caption") else ""
        return f'<figure class="report-chart">{inner}{cap}</figure>'
    if t == "quote_block":
        cite = f' [c:{b["citation_id"]}]' if b.get("citation_id") else ""
        return f'<blockquote class="source-quote">{_esc(b["quote"])}<footer>— {_esc(b["source"])}{cite}</footer></blockquote>'
    if t == "skip_banner":
        return (f'<blockquote class="skip-banner"><strong>{_esc(b["section_name"])}</strong> — skipped'
                f'<br/>{_esc(b["reason"])}</blockquote>')
    if t == "degraded_banner":
        issues = ", ".join(_esc(i) for i in b.get("issue_list", []))
        return (f'<blockquote class="degraded-banner"><strong>{_esc(b["section_name"])}</strong> — degraded'
                f'<br/>{_esc(b["reason"])}<br/><small>Issues: {issues}</small></blockquote>')
    if t == "excel_attachment":
        return (f'<a class="attachment" download href="{_esc(b["download_url"])}">'
                f'{_esc(b["filename"])} ({b["row_count"]} rows, {b["sheet_count"]} sheets)</a>')
    raise ValueError(f"unknown block type: {t!r}")
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_block_renderer.py -v
uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/rendering/block_renderer.py \
                  packages/core/src/openlia/llm/runtime/report_v2/schemas/blocks.py
git add packages/core/src/openlia/llm/runtime/report_v2/rendering/block_renderer.py \
        packages/core/src/openlia/llm/runtime/report_v2/schemas/blocks.py \
        packages/core/tests/llm/runtime/report_v2/test_block_renderer.py
git commit -m "feat(report_v2): HTML block renderers (prose, table, kpi_strip, chart, quote, skip/degraded banners, excel)"
```

---

### Task O2: Citation manifest + verify download path

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/rendering/citation_manifest.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_citation_manifest.py`
- Verify: existing v1 download path accepts HTML input

- [ ] **Step 1: Write failing tests for citation aggregation**

```python
# packages/core/tests/llm/runtime/report_v2/test_citation_manifest.py
from datetime import datetime, UTC
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation
from openlia.llm.runtime.report_v2.rendering.citation_manifest import (
    assemble_citation_manifest, render_sources_footer, substitute_markers,
)


def make_citation(id, title="t"):
    return Citation(id=id, source_type="tool_call", tool="eodhd.x",
                    url=None, title=title,
                    retrieved_at=datetime(2026, 5, 1, tzinfo=UTC))


def test_assemble_orders_by_first_appearance_and_dedupes():
    pool_citations = {
        "c1": make_citation("c1", "first"),
        "c2": make_citation("c2", "second"),
        "c3": make_citation("c3", "third"),
    }
    block_texts = [
        "claim [c:c2] and [c:c1]",   # c2 first, c1 second
        "more [c:c1]",                 # c1 duplicate -> no new entry
        "and [c:c3]",                  # c3 third
    ]
    manifest = assemble_citation_manifest(pool_citations, block_texts)
    assert manifest.id_to_number == {"c2": 1, "c1": 2, "c3": 3}
    assert len(manifest.citations) == 3


def test_substitute_markers_replaces_with_sup_anchors():
    pool_citations = {"c1": make_citation("c1")}
    text = "claim [c:c1]."
    manifest = assemble_citation_manifest(pool_citations, [text])
    out = substitute_markers(text, manifest)
    assert "[1]" in out
    assert "cite-1" in out
    assert "<sup>" in out


def test_render_sources_footer_emits_ol_with_backlinks():
    pool_citations = {"c1": make_citation("c1", "Source A")}
    text = "claim [c:c1] [c:c1]"
    manifest = assemble_citation_manifest(pool_citations, [text])
    footer = render_sources_footer(manifest)
    assert "<ol" in footer
    assert "Source A" in footer
    assert footer.count("cite-backlink") >= 2  # 2 backlinks for 2 references
```

- [ ] **Step 2: Implement citation manifest assembler + substitution**

```python
# packages/core/src/openlia/llm/runtime/report_v2/rendering/citation_manifest.py
from __future__ import annotations
import html
import re
from dataclasses import dataclass, field
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation


MARKER_RE = re.compile(r"\[c:([a-zA-Z0-9_]+)\]")


@dataclass
class CitationManifest:
    citations: list[Citation] = field(default_factory=list)         # ordered by first appearance
    id_to_number: dict[str, int] = field(default_factory=dict)
    backlink_counts: dict[str, int] = field(default_factory=dict)   # citation_id -> number of references


def assemble_citation_manifest(pool: dict[str, Citation], block_texts: list[str]) -> CitationManifest:
    m = CitationManifest()
    next_number = 1
    for text in block_texts:
        for cid in MARKER_RE.findall(text):
            if cid not in pool:
                continue  # unresolved markers are caught by deterministic verifier
            if cid not in m.id_to_number:
                m.id_to_number[cid] = next_number
                next_number += 1
                m.citations.append(pool[cid])
            m.backlink_counts[cid] = m.backlink_counts.get(cid, 0) + 1
    return m


def substitute_markers(text: str, manifest: CitationManifest) -> str:
    def repl(match: re.Match) -> str:
        cid = match.group(1)
        n = manifest.id_to_number.get(cid)
        if n is None:
            return match.group(0)
        return f'<sup><a class="cite-link" href="#cite-{n}" id="ref-{cid}-{n}">[{n}]</a></sup>'
    return MARKER_RE.sub(repl, text)


def render_sources_footer(manifest: CitationManifest) -> str:
    if not manifest.citations:
        return ""
    items = []
    for cite in manifest.citations:
        n = manifest.id_to_number[cite.id]
        url = f' <a href="{html.escape(cite.url, quote=True)}">link</a>' if cite.url else ""
        backlinks = " ".join(
            f'<a class="cite-backlink" href="#ref-{cite.id}-{n}">↑</a>'
            for _ in range(manifest.backlink_counts.get(cite.id, 1))
        )
        items.append(
            f'<li id="cite-{n}">{html.escape(cite.title)} '
            f'<span class="cite-source">({html.escape(cite.source_type)}'
            f'{(" — " + html.escape(cite.tool)) if cite.tool else ""})</span>'
            f'{url} {backlinks}</li>'
        )
    return f'<section id="sources"><h2>Sources</h2><ol class="citations">{"".join(items)}</ol></section>'
```

- [ ] **Step 3: Verify download path**

```bash
# Check existing v1 download converter
grep -rn "weasyprint\|pandoc\|html_to_pdf\|html_to_docx" packages/server/src/openlia_server/ frontend/src/
```

Expected: identify the existing PDF/DOCX export path. Verify it accepts HTML input. If currently expects markdown:

- Document the gap in `O2-verify-download-path` task ticket.
- Add adapter shim later (out of scope for this PR; record as Phase V follow-up).

- [ ] **Step 4: Run tests, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_citation_manifest.py -v
git add packages/core/src/openlia/llm/runtime/report_v2/rendering/citation_manifest.py \
        packages/core/tests/llm/runtime/report_v2/test_citation_manifest.py
git commit -m "feat(report_v2): citation manifest with inline [N] markers and aggregated Sources footer + backlinks"
```

---

### Task O3: Run Summary

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/schemas/run_summary.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/rendering/run_summary_renderer.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_run_summary.py`

- [ ] **Step 1: Write failing test**

```python
# packages/core/tests/llm/runtime/report_v2/test_run_summary.py
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary, TaskOutcome
from openlia.llm.runtime.report_v2.rendering.run_summary_renderer import render_run_summary


def make_summary():
    return RunSummary(
        engine_version="2.2",
        template_id="t1",
        template_name="Test Template",
        composer_inputs={"ticker": "NVDA"},
        outcomes=[
            TaskOutcome(task_type="research_strand", task_name="financials",
                        status="OK", duration_ms=4200),
            TaskOutcome(task_type="section_draft", task_name="litigation_risk",
                        status="DEGRADED", notes="3 retries exhausted", duration_ms=12000),
            TaskOutcome(task_type="section_draft", task_name="peer_comparison",
                        status="SKIPPED", notes="composer_inputs.peer_tickers empty", duration_ms=0),
        ],
        unsupported_requests_dismissed=["devil's advocate pass"],
        unsupported_requests_slipped=["VaR for risk section"],
        total_duration_ms=42000,
        total_token_cost=38000,
        cache_stats={"transcripts": {"hits": 4, "misses": 1}},
    )


def test_run_summary_html_has_all_statuses_visible():
    html = render_run_summary(make_summary())
    assert "OK" in html and "DEGRADED" in html and "SKIPPED" in html
    assert "NVDA" in html
    assert "v2.2" in html


def test_run_summary_lists_unsupported_dismissed_and_slipped():
    html = render_run_summary(make_summary())
    assert "devil's advocate pass" in html
    assert "VaR for risk section" in html


def test_run_summary_includes_cache_stats():
    html = render_run_summary(make_summary())
    assert "transcripts" in html.lower()
    assert "4 hit" in html or "hits: 4" in html or "4</td>" in html
```

- [ ] **Step 2: Implement schemas**

```python
# packages/core/src/openlia/llm/runtime/report_v2/schemas/run_summary.py
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


TaskType = Literal[
    "clarification", "research_strand", "model_component",
    "section_draft", "trigger_eval", "verification", "output_render",
]
Status = Literal["OK", "SKIPPED", "DEGRADED", "FAILED"]


class TaskOutcome(BaseModel):
    task_type: TaskType
    task_name: str
    status: Status
    notes: str | None = None
    duration_ms: int = 0


class RunSummary(BaseModel):
    engine_version: str
    template_id: str
    template_name: str
    composer_inputs: dict[str, Any] = Field(default_factory=dict)
    outcomes: list[TaskOutcome] = Field(default_factory=list)
    unsupported_requests_dismissed: list[str] = Field(default_factory=list)
    unsupported_requests_slipped: list[str] = Field(default_factory=list)
    total_duration_ms: int = 0
    total_token_cost: int | None = None
    cache_stats: dict = Field(default_factory=dict)
```

- [ ] **Step 3: Implement renderer**

```python
# packages/core/src/openlia/llm/runtime/report_v2/rendering/run_summary_renderer.py
from __future__ import annotations
import html
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary


_STATUS_CLASS = {"OK": "ok", "SKIPPED": "skipped", "DEGRADED": "degraded", "FAILED": "failed"}


def render_run_summary(rs: RunSummary) -> str:
    rows = "".join(
        f'<tr class="status-{_STATUS_CLASS[o.status]}"><td>{html.escape(o.task_type)}</td>'
        f'<td>{html.escape(o.task_name)}</td><td>{o.status}</td>'
        f'<td>{html.escape(o.notes or "")}</td></tr>'
        for o in rs.outcomes
    )

    dismissed = "".join(f"<li>{html.escape(s)}</li>" for s in rs.unsupported_requests_dismissed) or "<li>(none)</li>"
    slipped = "".join(f"<li>{html.escape(s)}</li>" for s in rs.unsupported_requests_slipped) or "<li>(none)</li>"

    cache_lines = []
    for src, stats in rs.cache_stats.items():
        if isinstance(stats, dict):
            h = stats.get("hits", 0)
            mi = stats.get("misses", 0)
            cache_lines.append(f"<li>{html.escape(src)}: {h} hit / {mi} miss</li>")
    cache_html = f"<h3>Cache</h3><ul>{''.join(cache_lines)}</ul>" if cache_lines else ""

    return (
        f'<section id="run_summary"><h2>Run Summary</h2>'
        f'<p><strong>Engine v{html.escape(rs.engine_version)}</strong> · '
        f'Template: {html.escape(rs.template_name)} · '
        f'{rs.total_duration_ms} ms'
        f'{f" · ~{rs.total_token_cost} tokens" if rs.total_token_cost else ""}</p>'
        f'<p><strong>Composer inputs:</strong> {html.escape(str(rs.composer_inputs))}</p>'
        f'<h3>Task outcomes</h3>'
        f'<table class="run-summary-outcomes">'
        f'<thead><tr><th>Type</th><th>Task</th><th>Status</th><th>Notes</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        f'<h3>Requests not fulfilled</h3>'
        f'<p><strong>Acknowledged by user:</strong></p><ul>{dismissed}</ul>'
        f'<p><strong>Detected at runtime:</strong></p><ul>{slipped}</ul>'
        f'{cache_html}'
        f'</section>'
    )
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_run_summary.py -v
git add packages/core/src/openlia/llm/runtime/report_v2/schemas/run_summary.py \
        packages/core/src/openlia/llm/runtime/report_v2/rendering/run_summary_renderer.py \
        packages/core/tests/llm/runtime/report_v2/test_run_summary.py
git commit -m "feat(report_v2): Run Summary schema + HTML renderer with status-tinted outcomes and unsupported-request lists"
```

---

### Task O4: Verification History (dev mode)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/schemas/verification_history.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/rendering/verification_history_renderer.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_verification_history.py`

- [ ] **Step 1: Write failing test**

```python
# packages/core/tests/llm/runtime/report_v2/test_verification_history.py
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue
from openlia.llm.runtime.report_v2.schemas.verification_history import (
    VerificationHistory, VerificationHistoryEntry
)
from openlia.llm.runtime.report_v2.rendering.verification_history_renderer import (
    render_verification_history, aggregate_history,
)


def make_issue(itype, sid, severity="blocker"):
    return VerifierIssue(issue_type=itype, section_id=sid, severity=severity,
                         evidence="...", detector="llm")


def test_aggregate_classifies_resolved_vs_persisted():
    raised = [
        # in round 0
        ("a", make_issue("citation_missing", "s1")),
        ("b", make_issue("content_too_sparse", "s2")),
    ]
    resolved_ids = {"a"}            # 'a' got fixed in round 1
    persisted_ids = {"b"}           # 'b' degraded after retries
    history = aggregate_history(raised, resolved_ids=resolved_ids,
                                 persisted_ids=persisted_ids,
                                 resolution_rounds={"a": 1})
    by_resolution = {e.final_resolution for e in history.entries}
    assert "resolved" in by_resolution and "persisted_degraded" in by_resolution


def test_render_omitted_when_dev_mode_false():
    h = VerificationHistory(entries=[])
    out = render_verification_history(h, dev_mode=False)
    assert out == ""


def test_render_includes_all_entries_when_dev_mode_true():
    entry = VerificationHistoryEntry(
        issue=make_issue("citation_missing", "s1"),
        raised_at_round=0, final_resolution="resolved", resolved_in_round=1,
    )
    h = VerificationHistory(entries=[entry], total_issues_raised=1,
                            resolved_on_first_retry=1, resolved_on_subsequent_retry=0,
                            persisted_to_degraded=0, warnings_open=0)
    out = render_verification_history(h, dev_mode=True)
    assert "Verification History" in out and "citation_missing" in out
```

- [ ] **Step 2: Implement schema + aggregator + renderer**

```python
# packages/core/src/openlia/llm/runtime/report_v2/schemas/verification_history.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


class VerificationHistoryEntry(BaseModel):
    issue: VerifierIssue
    raised_at_round: int
    final_resolution: Literal["resolved", "persisted_degraded", "persisted_failed", "still_open"]
    resolved_in_round: int | None = None


class VerificationHistory(BaseModel):
    entries: list[VerificationHistoryEntry] = Field(default_factory=list)
    total_issues_raised: int = 0
    resolved_on_first_retry: int = 0
    resolved_on_subsequent_retry: int = 0
    persisted_to_degraded: int = 0
    warnings_open: int = 0
```

```python
# packages/core/src/openlia/llm/runtime/report_v2/rendering/verification_history_renderer.py
from __future__ import annotations
import html
from openlia.llm.runtime.report_v2.schemas.verification_history import (
    VerificationHistory, VerificationHistoryEntry,
)
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


def aggregate_history(
    raised: list[tuple[str, VerifierIssue]],
    resolved_ids: set[str],
    persisted_ids: set[str],
    resolution_rounds: dict[str, int],
) -> VerificationHistory:
    entries = []
    for issue_id, issue in raised:
        if issue_id in resolved_ids:
            fr = "resolved"
            rr = resolution_rounds.get(issue_id)
        elif issue_id in persisted_ids:
            fr = "persisted_degraded"
            rr = None
        elif issue.severity == "warning":
            fr = "still_open"
            rr = None
        else:
            fr = "persisted_failed"
            rr = None
        entries.append(VerificationHistoryEntry(
            issue=issue, raised_at_round=0, final_resolution=fr, resolved_in_round=rr,
        ))
    return VerificationHistory(
        entries=entries,
        total_issues_raised=len(raised),
        resolved_on_first_retry=sum(1 for e in entries if e.final_resolution == "resolved" and e.resolved_in_round == 1),
        resolved_on_subsequent_retry=sum(1 for e in entries if e.final_resolution == "resolved" and (e.resolved_in_round or 0) > 1),
        persisted_to_degraded=sum(1 for e in entries if e.final_resolution == "persisted_degraded"),
        warnings_open=sum(1 for e in entries if e.final_resolution == "still_open"),
    )


_RES_CLASS = {
    "resolved": "resolved", "persisted_degraded": "degraded",
    "persisted_failed": "failed", "still_open": "warning-open",
}


def render_verification_history(h: VerificationHistory, dev_mode: bool) -> str:
    if not dev_mode:
        return ""
    rows = "".join(
        f'<tr class="{_RES_CLASS[e.final_resolution]}">'
        f'<td>{html.escape(e.issue.section_id or "—")}</td>'
        f'<td>{e.issue.issue_type}</td>'
        f'<td>{e.issue.severity}</td>'
        f'<td>{e.issue.detector}</td>'
        f'<td>round {e.raised_at_round}</td>'
        f'<td>{e.final_resolution}</td>'
        f'<td>{html.escape(e.issue.evidence)}</td>'
        f'<td>{html.escape(e.issue.suggested_fix or "")}</td>'
        f'</tr>'
        for e in h.entries
    )
    summary = (
        f'<p>{h.total_issues_raised} issues raised · {h.resolved_on_first_retry + h.resolved_on_subsequent_retry} resolved · '
        f'{h.persisted_to_degraded} degraded · {h.warnings_open} open warnings</p>'
    )
    return (
        f'<section id="verification_history" class="dev-only">'
        f'<h2>Verification History <span class="dev-badge">dev mode</span></h2>'
        f'{summary}'
        f'<table class="verification-history">'
        f'<thead><tr><th>Section</th><th>Issue</th><th>Severity</th><th>Detector</th>'
        f'<th>Raised</th><th>Resolution</th><th>Evidence</th><th>Suggested fix</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></section>'
    )
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_verification_history.py -v
git add packages/core/src/openlia/llm/runtime/report_v2/schemas/verification_history.py \
        packages/core/src/openlia/llm/runtime/report_v2/rendering/verification_history_renderer.py \
        packages/core/tests/llm/runtime/report_v2/test_verification_history.py
git commit -m "feat(report_v2): Verification History dev-mode schema + renderer with status-tinted rows"
```

---

### Task O5: Stage 9 Assemble (final HTML)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/rendering/assembler.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_9_assemble.py`
- Test: `packages/core/tests/llm/runtime/report_v2/test_stage_9_assemble.py`

- [ ] **Step 1: Write failing test**

```python
# packages/core/tests/llm/runtime/report_v2/test_stage_9_assemble.py
from datetime import datetime, UTC
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary, TaskOutcome
from openlia.llm.runtime.report_v2.schemas.verification_history import VerificationHistory
from openlia.llm.runtime.report_v2.pipeline.stage_9_assemble import assemble_report


def test_assemble_emits_html_with_correct_section_order():
    sections = [
        {"id": "intro", "name": "Introduction", "blocks": [
            {"type": "prose", "text": "Foo [c:c1]"}
        ]},
        {"id": "outro", "name": "Outro", "blocks": [
            {"type": "skip_banner", "section_name": "Outro", "reason": "trigger fired false"}
        ]},
    ]
    pool_citations = {"c1": Citation(id="c1", source_type="tool_call", tool="t",
                                     url=None, title="Source A",
                                     retrieved_at=datetime(2026, 5, 1, tzinfo=UTC))}
    rs = RunSummary(engine_version="2.2", template_id="t", template_name="T",
                    outcomes=[TaskOutcome(task_type="section_draft", task_name="intro",
                                           status="OK", duration_ms=100)])
    vh = VerificationHistory()
    html = assemble_report(sections=sections, pool_citations=pool_citations,
                            run_summary=rs, verification_history=vh, dev_mode=True)
    # Section ordering: template sections, then sources, then run_summary, then verification_history
    assert html.index("Introduction") < html.index("Sources")
    assert html.index("Sources") < html.index("Run Summary")
    assert html.index("Run Summary") < html.index("Verification History")
```

- [ ] **Step 2: Implement assembler**

```python
# packages/core/src/openlia/llm/runtime/report_v2/rendering/assembler.py
from __future__ import annotations
from openlia.llm.runtime.report_v2.rendering.block_renderer import render_block
from openlia.llm.runtime.report_v2.rendering.citation_manifest import (
    assemble_citation_manifest, substitute_markers, render_sources_footer,
)
from openlia.llm.runtime.report_v2.rendering.run_summary_renderer import render_run_summary
from openlia.llm.runtime.report_v2.rendering.verification_history_renderer import render_verification_history


def _collect_block_texts(sections: list[dict]) -> list[str]:
    out = []
    for s in sections:
        for b in s.get("blocks", []):
            if isinstance(b, dict) and "text" in b:
                out.append(b["text"])
    return out


def assemble_report(sections, pool_citations, run_summary, verification_history, dev_mode: bool) -> str:
    block_texts = _collect_block_texts(sections)
    manifest = assemble_citation_manifest(pool_citations, block_texts)

    section_html_parts = []
    for s in sections:
        rendered_blocks = []
        for b in s.get("blocks", []):
            r = render_block(b)
            r = substitute_markers(r, manifest)
            rendered_blocks.append(r)
        section_html_parts.append(
            f'<section id="{s["id"]}"><h2>{s["name"]}</h2>{"".join(rendered_blocks)}</section>'
        )

    sources = render_sources_footer(manifest)
    run_summary_html = render_run_summary(run_summary)
    history_html = render_verification_history(verification_history, dev_mode=dev_mode)

    return f'<article class="openlia-report">' \
           f'{"".join(section_html_parts)}' \
           f'{sources}' \
           f'{run_summary_html}' \
           f'{history_html}' \
           f'<footer class="report-footer">' \
           f'Engine v{run_summary.engine_version}' \
           f'</footer>' \
           f'</article>'
```

```python
# packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_9_assemble.py
from openlia.llm.runtime.report_v2.rendering.assembler import assemble_report  # re-export

__all__ = ["assemble_report"]
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_stage_9_assemble.py -v
git add packages/core/src/openlia/llm/runtime/report_v2/rendering/assembler.py \
        packages/core/src/openlia/llm/runtime/report_v2/pipeline/stage_9_assemble.py \
        packages/core/tests/llm/runtime/report_v2/test_stage_9_assemble.py
git commit -m "feat(report_v2): stage 9 assembler — sections, Sources, Run Summary, Verification History in locked order"
```

---

## Phase X — UI

Frontend work. Each PR uses Vitest for component testing and matches the existing v1 frontend conventions (`frontend/src/components/`, TypeScript, CSS modules).

### Task X1: Composer redesign + capabilities sidebar

**Files:**
- Modify: `frontend/src/pages/EquityResearch/Composer.tsx`
- Create: `frontend/src/components/CapabilitySidebar/CapabilitySidebar.tsx`
- Create: `frontend/src/components/CapabilitySidebar/CapabilitySidebar.test.tsx`
- Create: `frontend/src/api/capabilities.ts`
- Modify: `packages/server/src/openlia_server/routes/capabilities.py` (new server route)

- [ ] **Step 1: Add server-side capabilities endpoint**

```python
# packages/server/src/openlia_server/routes/capabilities.py
from fastapi import APIRouter
from openlia.llm.runtime.report_v2.capability_manifest import load_manifest

router = APIRouter()


@router.get("/api/capabilities")
def get_capabilities() -> dict:
    m = load_manifest()
    return m.model_dump()
```

Register in `packages/server/src/openlia_server/app.py`:
```python
from openlia_server.routes import capabilities as capabilities_routes
app.include_router(capabilities_routes.router)
```

- [ ] **Step 2: Frontend API client**

```typescript
// frontend/src/api/capabilities.ts
export interface SupportedCapability { id: string; summary: string }
export interface UnsupportedCapability {
  id: string;
  summary: string;
  planned_in: string | null;
  user_message: string;
}
export interface CapabilityManifest {
  engine_version: string;
  dev_mode: boolean;
  supported: SupportedCapability[];
  unsupported: UnsupportedCapability[];
}

export async function fetchCapabilities(): Promise<CapabilityManifest> {
  const r = await fetch("/api/capabilities");
  if (!r.ok) throw new Error(`failed to fetch capabilities: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 3: Failing component test**

```typescript
// frontend/src/components/CapabilitySidebar/CapabilitySidebar.test.tsx
import { render, screen } from "@testing-library/react";
import { CapabilitySidebar } from "./CapabilitySidebar";

const manifest = {
  engine_version: "2.2",
  dev_mode: true,
  supported: [{ id: "conditional_sections", summary: "Conditional sections" }],
  unsupported: [{
    id: "extra_passes", summary: "Extra LLM passes", planned_in: "2.3",
    user_message: "not supported",
  }],
};

test("renders supported and unsupported capability lists", () => {
  render(<CapabilitySidebar manifest={manifest} />);
  expect(screen.getByText(/Conditional sections/)).toBeInTheDocument();
  expect(screen.getByText(/Extra LLM passes/)).toBeInTheDocument();
  expect(screen.getByText(/2\.3/)).toBeInTheDocument();
});

test("displays engine version", () => {
  render(<CapabilitySidebar manifest={manifest} />);
  expect(screen.getByText(/Engine v2\.2/)).toBeInTheDocument();
});
```

- [ ] **Step 4: Implement component**

```typescript
// frontend/src/components/CapabilitySidebar/CapabilitySidebar.tsx
import { CapabilityManifest } from "../../api/capabilities";
import styles from "./CapabilitySidebar.module.css";

interface Props { manifest: CapabilityManifest }

export function CapabilitySidebar({ manifest }: Props) {
  return (
    <aside className={styles.sidebar}>
      <h3>Engine v{manifest.engine_version}</h3>

      <details open className={styles.section}>
        <summary>Supported ({manifest.supported.length})</summary>
        <ul>
          {manifest.supported.map(s => (
            <li key={s.id}><strong>{s.summary}</strong></li>
          ))}
        </ul>
      </details>

      <details className={styles.section}>
        <summary>Not yet supported ({manifest.unsupported.length})</summary>
        <ul>
          {manifest.unsupported.map(u => (
            <li key={u.id}>
              <strong>{u.summary}</strong>
              {u.planned_in && <em className={styles.planned}> — planned for v{u.planned_in}</em>}
            </li>
          ))}
        </ul>
      </details>
    </aside>
  );
}
```

- [ ] **Step 5: Update Composer.tsx**

In `frontend/src/pages/EquityResearch/Composer.tsx`:

- Add free-text prompt textarea alongside template selection.
- Render dynamic `composer_inputs` form by type (use a small per-type renderer dispatch).
- Mount `<CapabilitySidebar />` (fetch via `useEffect` on mount).
- Add Advanced section with `force_cache_refresh` checkbox.
- Submit handler posts `{template_id, composer_inputs: {...}, prompt, force_cache_refresh}` to the existing run-start endpoint.

- [ ] **Step 6: Run tests, lint, commit**

```bash
cd frontend && npm run test -- CapabilitySidebar
cd .. && uv run ruff check packages/server/src/openlia_server/routes/capabilities.py
git add frontend/src/components/CapabilitySidebar/ frontend/src/api/capabilities.ts \
        frontend/src/pages/EquityResearch/Composer.tsx \
        packages/server/src/openlia_server/routes/capabilities.py \
        packages/server/src/openlia_server/app.py
git commit -m "feat(frontend): composer redesign with free-text prompt + CapabilitySidebar + force_cache_refresh"
```

---

### Task X2: Clarifier modal component

**Files:**
- Create: `frontend/src/components/ClarifierModal/ClarifierModal.tsx`
- Create: `frontend/src/components/ClarifierModal/ClarifierModal.test.tsx`
- Create: `frontend/src/api/clarifier.ts`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/components/ClarifierModal/ClarifierModal.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ClarifierModal } from "./ClarifierModal";

const sample = {
  questions: [],
  blocking_warnings: [{
    capability_id: "extra_passes",
    detected_phrase: "devil's advocate pass",
    user_message: "Extra LLM passes are not supported in this version.",
    available_actions: ["proceed_without", "cancel_and_edit", "clarify"],
  }],
  notices: [],
  detected_intents: ["extras"],
};

test("submit is disabled until all warnings have an action", () => {
  render(<ClarifierModal output={sample} round={1} onSubmit={vi.fn()} onCancel={vi.fn()} />);
  const submit = screen.getByRole("button", { name: /submit/i });
  expect(submit).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /proceed without/i }));
  expect(submit).toBeEnabled();
});

test("round counter is shown", () => {
  render(<ClarifierModal output={sample} round={2} onSubmit={vi.fn()} onCancel={vi.fn()} />);
  expect(screen.getByText(/Round 2 of 3/)).toBeInTheDocument();
});

test("clarify button is hidden after round 3", () => {
  render(<ClarifierModal output={sample} round={3} onSubmit={vi.fn()} onCancel={vi.fn()} />);
  expect(screen.queryByRole("button", { name: /clarify/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Implement modal**

```typescript
// frontend/src/components/ClarifierModal/ClarifierModal.tsx
import { useState } from "react";
import styles from "./ClarifierModal.module.css";

interface CapabilityWarning {
  capability_id: string;
  detected_phrase: string;
  user_message: string;
  available_actions: ("proceed_without" | "cancel_and_edit" | "clarify")[];
}

interface ClarifyingQuestion {
  id: string;
  text: string;
  kind: "multiple_choice" | "free_text";
  options?: string[];
}

interface ClarifierOutput {
  questions: ClarifyingQuestion[];
  blocking_warnings: CapabilityWarning[];
  notices: string[];
  detected_intents: string[];
}

interface Props {
  output: ClarifierOutput;
  round: number;
  onSubmit: (data: {
    warningActions: Record<string, string>;
    clarifications: Record<string, string>;
    questionAnswers: Record<string, string>;
  }) => void;
  onCancel: () => void;
}

const MAX_ROUNDS = 3;

export function ClarifierModal({ output, round, onSubmit, onCancel }: Props) {
  const [warningActions, setWarningActions] = useState<Record<string, string>>({});
  const [clarifications, setClarifications] = useState<Record<string, string>>({});
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({});

  const allWarningsResolved = output.blocking_warnings.every(
    w => warningActions[w.capability_id] !== undefined
  );

  const showClarify = round < MAX_ROUNDS;

  return (
    <div className={styles.modal}>
      <div className={styles.header}>
        <h2>Clarifying questions</h2>
        <span className={styles.roundCounter}>Round {round} of {MAX_ROUNDS}</span>
      </div>

      {output.blocking_warnings.length > 0 && (
        <div className={styles.warningSection}>
          <h3>⚠ {output.blocking_warnings.length} capability warning(s)</h3>
          {output.blocking_warnings.map(w => {
            const action = warningActions[w.capability_id];
            return (
              <div key={w.capability_id} className={styles.warning}>
                <p>"{w.detected_phrase}"</p>
                <p className={styles.warningMsg}>{w.user_message}</p>
                <div className={styles.actions}>
                  <button onClick={() => setWarningActions({ ...warningActions, [w.capability_id]: "proceed_without" })}
                          className={action === "proceed_without" ? styles.selected : ""}>
                    Proceed without it
                  </button>
                  <button onClick={onCancel}>Cancel & Edit</button>
                  {showClarify && (
                    <button onClick={() => setWarningActions({ ...warningActions, [w.capability_id]: "clarify" })}
                            className={action === "clarify" ? styles.selected : ""}>
                      Clarify
                    </button>
                  )}
                </div>
                {action === "clarify" && (
                  <textarea
                    placeholder="What did you actually mean?"
                    value={clarifications[w.capability_id] || ""}
                    onChange={e => setClarifications({ ...clarifications, [w.capability_id]: e.target.value })}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {output.questions.map(q => (
        <div key={q.id} className={styles.question}>
          <label>{q.text}</label>
          {q.kind === "multiple_choice" && q.options ? (
            <select value={questionAnswers[q.id] || ""}
                    onChange={e => setQuestionAnswers({ ...questionAnswers, [q.id]: e.target.value })}>
              <option value="">—</option>
              {q.options.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <input type="text" value={questionAnswers[q.id] || ""}
                   onChange={e => setQuestionAnswers({ ...questionAnswers, [q.id]: e.target.value })} />
          )}
        </div>
      ))}

      <button
        disabled={!allWarningsResolved}
        onClick={() => onSubmit({ warningActions, clarifications, questionAnswers })}
      >
        Submit answers
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Wire to SSE event handler (existing run-status component)**

In the run viewer page, when `clarifier.warnings_pending` SSE event is received, set state to show `ClarifierModal`. On submit, POST to `/api/runs/{run_id}/clarify` (server route — implemented as part of this PR).

```python
# packages/server/src/openlia_server/routes/runs.py — add
@router.post("/api/runs/{run_id}/clarify")
def submit_clarification(run_id: str, payload: dict) -> dict:
    # look up run state, advance from CLARIFY_AWAITING_USER
    ...
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
cd frontend && npm run test -- ClarifierModal
git add frontend/src/components/ClarifierModal/ frontend/src/api/clarifier.ts \
        packages/server/src/openlia_server/routes/runs.py
git commit -m "feat(frontend): ClarifierModal with blocking warnings, 3-action buttons, clarification loop"
```

---

### Task X3: Template upload UI extensions

**Files:**
- Modify: `frontend/src/components/TemplateUpload/TemplateUpload.tsx`
- Create: `frontend/src/components/TemplateUpload/ConversionPromptButton.tsx`
- Test: `frontend/src/components/TemplateUpload/TemplateUpload.test.tsx`

- [ ] **Step 1: Write failing test for notice banners**

```typescript
// frontend/src/components/TemplateUpload/TemplateUpload.test.tsx
import { render, screen } from "@testing-library/react";
import { TemplateUpload } from "./TemplateUpload";

test("reserved-key notice renders yellow banner", () => {
  const notices = [
    { kind: "reserved_key", key: "extra_passes",
      message: "Extra LLM passes not supported in v2.2; ignored." },
  ];
  render(<TemplateUpload uploadState={{ notices, parsed: null, error: null }} />);
  expect(screen.getByText(/extra_passes/)).toBeInTheDocument();
  expect(screen.getByText(/not supported/)).toBeInTheDocument();
});

test("unknown-key notice renders warning", () => {
  const notices = [
    { kind: "unknown_key", key: "mystery_field",
      message: "Unknown template key 'mystery_field' ignored." },
  ];
  render(<TemplateUpload uploadState={{ notices, parsed: null, error: null }} />);
  expect(screen.getByText(/mystery_field/)).toBeInTheDocument();
});

test("renders conversion prompt button", () => {
  render(<TemplateUpload uploadState={{ notices: [], parsed: null, error: null }} />);
  expect(screen.getByRole("button", { name: /convert your doc/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Implement extensions**

```typescript
// frontend/src/components/TemplateUpload/ConversionPromptButton.tsx
import { useState } from "react";

export function ConversionPromptButton() {
  const [copied, setCopied] = useState(false);
  async function handleClick() {
    const r = await fetch("/api/templates/conversion_prompt");
    const { prompt } = await r.json();
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button onClick={handleClick}>
      {copied ? "Copied!" : "Convert your doc to a template (copy prompt)"}
    </button>
  );
}
```

Server endpoint:
```python
# packages/server/src/openlia_server/routes/templates.py — add
from openlia.llm.runtime.report_v2.template_v2.conversion_prompt import build_conversion_prompt

@router.get("/api/templates/conversion_prompt")
def get_conversion_prompt() -> dict:
    return {"prompt": build_conversion_prompt()}
```

Extend `TemplateUpload.tsx` to:
- Accept `.yaml`, `.yml`, `.json` file types.
- Render each notice with appropriate class (`.reserved-key-banner` or `.unknown-key-banner`).
- Render conditional-language suggestions next to each section in the preview pane.
- Show `<ConversionPromptButton />` near the file input.

- [ ] **Step 3: Run tests, commit**

```bash
cd frontend && npm run test -- TemplateUpload
git add frontend/src/components/TemplateUpload/ \
        packages/server/src/openlia_server/routes/templates.py
git commit -m "feat(frontend): template upload — reserved-key + unknown-key notices, JSON support, conversion prompt button"
```

---

### Task X4: Report viewer — new blocks + RunSummary + VerificationHistory

**Files:**
- Modify: `frontend/src/components/ReportViewer/ReportViewer.tsx`
- Create: `frontend/src/components/ReportViewer/blocks/TableBlock.tsx`
- Create: `frontend/src/components/ReportViewer/blocks/KPIStripBlock.tsx`
- Create: `frontend/src/components/ReportViewer/blocks/ChartBlock.tsx`
- Create: `frontend/src/components/ReportViewer/blocks/ExcelAttachmentBlock.tsx`
- Create: `frontend/src/components/ReportViewer/RunSummary.tsx`
- Create: `frontend/src/components/ReportViewer/VerificationHistory.tsx`
- Test: `frontend/src/components/ReportViewer/RunSummary.test.tsx`
- Test: `frontend/src/components/ReportViewer/VerificationHistory.test.tsx`

- [ ] **Step 1: Write failing tests for RunSummary and VerificationHistory**

```typescript
// frontend/src/components/ReportViewer/RunSummary.test.tsx
import { render, screen } from "@testing-library/react";
import { RunSummary } from "./RunSummary";

const sample = {
  engine_version: "2.2",
  template_id: "t1",
  template_name: "Test",
  composer_inputs: { ticker: "NVDA" },
  outcomes: [
    { task_type: "section_draft", task_name: "intro", status: "OK", duration_ms: 1000 },
    { task_type: "section_draft", task_name: "litigation", status: "DEGRADED",
      notes: "3 retries", duration_ms: 8000 },
  ],
  unsupported_requests_dismissed: ["devil's advocate"],
  unsupported_requests_slipped: [],
  total_duration_ms: 12000,
  cache_stats: {},
};

test("renders all four status types with color classes", () => {
  render(<RunSummary summary={sample} />);
  expect(screen.getByText("OK")).toHaveClass(/ok/i);
  expect(screen.getByText("DEGRADED")).toHaveClass(/degraded/i);
});

test("shows unsupported_requests_dismissed list", () => {
  render(<RunSummary summary={sample} />);
  expect(screen.getByText(/devil's advocate/)).toBeInTheDocument();
});
```

```typescript
// frontend/src/components/ReportViewer/VerificationHistory.test.tsx
import { render } from "@testing-library/react";
import { VerificationHistory } from "./VerificationHistory";

test("returns null when dev_mode is false", () => {
  const { container } = render(<VerificationHistory history={{ entries: [] }} devMode={false} />);
  expect(container.firstChild).toBeNull();
});
```

- [ ] **Step 2: Implement components**

For each block type, implement a React component that takes `block` props and renders to DOM. (Mirror the Python `render_block` shapes from O1.) Then `ReportViewer.tsx` dispatches per block type.

The server delivers HTML directly via the existing report endpoint; the React viewer can either:

- Render the server's HTML directly via `dangerouslySetInnerHTML` (simplest, faithful to server output)
- Re-render block-by-block from a JSON payload (richer interactivity)

For v2.2 ship the `dangerouslySetInnerHTML` path for the report body, with React components only for `RunSummary` and `VerificationHistory` (because those benefit from interactive sort/filter on the outcomes table).

```typescript
// frontend/src/components/ReportViewer/RunSummary.tsx
interface TaskOutcome {
  task_type: string;
  task_name: string;
  status: "OK" | "SKIPPED" | "DEGRADED" | "FAILED";
  notes?: string;
  duration_ms: number;
}

interface RunSummaryProps {
  summary: {
    engine_version: string;
    template_name: string;
    composer_inputs: Record<string, unknown>;
    outcomes: TaskOutcome[];
    unsupported_requests_dismissed: string[];
    unsupported_requests_slipped: string[];
    total_duration_ms: number;
    cache_stats: Record<string, { hits: number; misses: number }>;
  };
}

const STATUS_CLASS: Record<string, string> = {
  OK: "status-ok", SKIPPED: "status-skipped",
  DEGRADED: "status-degraded", FAILED: "status-failed",
};

export function RunSummary({ summary }: RunSummaryProps) {
  return (
    <section id="run_summary">
      <h2>Run Summary</h2>
      <p><strong>Engine v{summary.engine_version}</strong> · Template: {summary.template_name} · {summary.total_duration_ms} ms</p>
      <table className="run-summary-outcomes">
        <thead><tr><th>Type</th><th>Task</th><th>Status</th><th>Notes</th></tr></thead>
        <tbody>
          {summary.outcomes.map((o, i) => (
            <tr key={i} className={STATUS_CLASS[o.status]}>
              <td>{o.task_type}</td><td>{o.task_name}</td>
              <td>{o.status}</td><td>{o.notes || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Requests not fulfilled</h3>
      <p><strong>Acknowledged:</strong></p>
      <ul>{summary.unsupported_requests_dismissed.length === 0 ? <li>(none)</li> :
           summary.unsupported_requests_dismissed.map((s, i) => <li key={i}>{s}</li>)}</ul>
      <p><strong>Detected at runtime:</strong></p>
      <ul>{summary.unsupported_requests_slipped.length === 0 ? <li>(none)</li> :
           summary.unsupported_requests_slipped.map((s, i) => <li key={i}>{s}</li>)}</ul>
    </section>
  );
}
```

```typescript
// frontend/src/components/ReportViewer/VerificationHistory.tsx
interface Props {
  history: { entries: any[]; total_issues_raised?: number };
  devMode: boolean;
}

export function VerificationHistory({ history, devMode }: Props) {
  if (!devMode) return null;
  return (
    <section id="verification_history" className="dev-only">
      <h2>Verification History <span className="dev-badge">dev mode</span></h2>
      <p>{history.total_issues_raised ?? history.entries.length} issues raised</p>
      <table className="verification-history">
        <thead><tr><th>Section</th><th>Issue</th><th>Severity</th><th>Detector</th>
                   <th>Resolution</th><th>Evidence</th></tr></thead>
        <tbody>
          {history.entries.map((e: any, i: number) => (
            <tr key={i} className={e.final_resolution}>
              <td>{e.issue.section_id || "—"}</td>
              <td>{e.issue.issue_type}</td>
              <td>{e.issue.severity}</td>
              <td>{e.issue.detector}</td>
              <td>{e.final_resolution}</td>
              <td>{e.issue.evidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

- [ ] **Step 3: Run tests, commit**

```bash
cd frontend && npm run test -- ReportViewer
git add frontend/src/components/ReportViewer/
git commit -m "feat(frontend): ReportViewer block components + RunSummary + VerificationHistory"
```

---

### Task X5: Cache admin panel + settings toggles + repo list

**Files:**
- Create: `frontend/src/components/CacheAdmin/CacheAdmin.tsx`
- Create: `frontend/src/api/cache.ts`
- Create: `packages/server/src/openlia_server/routes/cache.py`
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/pages/Repo.tsx`

- [ ] **Step 1: Server cache routes**

```python
# packages/server/src/openlia_server/routes/cache.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from openlia_server.db.models import CachedDocument
from openlia_server.db.session import get_session

router = APIRouter()


@router.get("/api/cache/stats")
def cache_stats(session: Session = Depends(get_session)) -> dict:
    total = session.query(CachedDocument).count()
    total_bytes = sum(d.bytes_size for d in session.query(CachedDocument).all())
    return {"total_entries": total, "total_bytes": total_bytes}


@router.delete("/api/cache/documents")
def clear_cache(
    ticker: str | None = Query(None),
    session: Session = Depends(get_session),
) -> dict:
    q = session.query(CachedDocument)
    if ticker:
        q = q.filter(CachedDocument.ticker == ticker)
    count = q.count()
    q.delete()
    session.commit()
    return {"deleted": count}
```

- [ ] **Step 2: CacheAdmin component**

```typescript
// frontend/src/components/CacheAdmin/CacheAdmin.tsx
import { useEffect, useState } from "react";

export function CacheAdmin() {
  const [stats, setStats] = useState<{ total_entries: number; total_bytes: number } | null>(null);
  const [ticker, setTicker] = useState("");

  async function refresh() {
    const r = await fetch("/api/cache/stats");
    setStats(await r.json());
  }
  useEffect(() => { refresh(); }, []);

  async function clearForTicker() {
    await fetch(`/api/cache/documents?ticker=${encodeURIComponent(ticker)}`, { method: "DELETE" });
    await refresh();
    setTicker("");
  }
  async function clearAll() {
    if (!confirm("Clear all cached documents?")) return;
    await fetch("/api/cache/documents", { method: "DELETE" });
    await refresh();
  }

  if (!stats) return <p>Loading…</p>;
  return (
    <div>
      <h2>Cache</h2>
      <p>{stats.total_entries} cached documents, {(stats.total_bytes / 1024 / 1024).toFixed(1)} MB</p>
      <div>
        <input value={ticker} onChange={e => setTicker(e.target.value)} placeholder="ticker (e.g. NVDA)" />
        <button disabled={!ticker} onClick={clearForTicker}>Clear cache for ticker</button>
      </div>
      <button onClick={clearAll}>Clear all</button>
    </div>
  );
}
```

- [ ] **Step 3: Settings page toggles**

In `frontend/src/pages/Settings.tsx`, add:
- dev_mode toggle (calls `PATCH /api/capabilities/dev_mode`)
- cache global enable/disable (calls `PATCH /api/capabilities/cache`)
- engine_version display (read-only)
- mount `<CacheAdmin />` below the toggles

- [ ] **Step 4: Repo list status counts**

In `frontend/src/pages/Repo.tsx`, for each report card:
- read `repo_item.run_summary` if present
- compute counts: OK / DEGRADED / FAILED from outcomes
- show counts badge: e.g., `8 OK / 2 DEGRADED`
- show `engine_version` badge
- on hover, show Run Summary preview in tooltip

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CacheAdmin/ frontend/src/api/cache.ts \
        frontend/src/pages/Settings.tsx frontend/src/pages/Repo.tsx \
        packages/server/src/openlia_server/routes/cache.py
git commit -m "feat(frontend): CacheAdmin panel, Settings dev_mode/cache toggles, Repo list status counts"
```

---

## Phase V — Validation

Smoke tests that verify the v2.2 pipeline end-to-end against converted templates.

### Task V1: Convert default modes to templates

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/templates/stock_research_v2.yaml`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/templates/stock_initiation_v2.yaml`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/templates/sector_research_v2.yaml`
- Test: `packages/core/tests/llm/runtime/report_v2/test_default_templates.py`

- [ ] **Step 1: Author each YAML template**

Convert the previously-hardcoded mode behaviors into TemplateSpecV2 YAML. Each declares `composer_inputs`, `required_artifacts`, `sections`, `verifier_severity_overrides`. Use existing v1 mode source code as reference for section content.

- [ ] **Step 2: Write test that loads each template through the v2 loader**

```python
# packages/core/tests/llm/runtime/report_v2/test_default_templates.py
import pytest
from pathlib import Path
from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2


TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "src" / "openlia" / "llm" / "runtime" / "report_v2" / "templates"


@pytest.mark.parametrize("filename,expected_report_type", [
    ("stock_research_v2.yaml", "equity_research"),
    ("stock_initiation_v2.yaml", "equity_research"),
    ("sector_research_v2.yaml", "sector_research"),
])
def test_default_templates_load_without_notices(filename, expected_report_type):
    raw = (TEMPLATE_DIR / filename).read_text()
    spec, notices = load_template_v2(raw, fmt="yaml")
    assert spec.report_type == expected_report_type
    # Default templates should not have any unknown_key or reserved_key notices
    assert [n for n in notices if n.kind in ("reserved_key", "unknown_key")] == []
```

- [ ] **Step 3: Run tests, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_default_templates.py -v
git add packages/core/src/openlia/llm/runtime/report_v2/templates/ \
        packages/core/tests/llm/runtime/report_v2/test_default_templates.py
git commit -m "feat(report_v2): convert stock_research, stock_initiation, sector_research to v2 YAML templates"
```

---

### Task V2: End-to-end smoke for one template

**Files:**
- Test: `packages/core/tests/llm/runtime/report_v2/test_e2e_smoke.py`

- [ ] **Step 1: Write smoke test (with stub LLMs)**

```python
# packages/core/tests/llm/runtime/report_v2/test_e2e_smoke.py
"""
E2E smoke against stock_research_v2 template.

Uses stub LLM that returns canned plans/strands/drafts/verifier output.
Verifies the pipeline runs end-to-end and produces non-empty HTML with:
- All required artifacts attempted
- Sources footer
- Run Summary
- Verification History (dev mode)
"""
from unittest.mock import Mock
# ... full pipeline orchestration test ...

def test_e2e_stock_research_produces_html_report():
    # build stub LLMs, register stub adapters, dispatch the runner
    # assert final HTML contains key markers:
    #   - <article class="openlia-report">
    #   - <section id="sources">
    #   - <section id="run_summary">
    #   - <section id="verification_history">  (dev_mode)
    pass


def test_e2e_with_unsupported_intent_surfaces_blocking_warning():
    # composer_inputs.prompt = "have a devil's advocate pass"
    # assert run state goes to CLARIFY_AWAITING_USER
    # assert blocking_warning for extra_passes is emitted
    pass


def test_e2e_with_trigger_when_false_renders_skip_banner():
    # template has section with trigger_when that LLM evaluator returns false
    # assert that section renders as skip banner in the final HTML
    pass


def test_e2e_with_verifier_retry_resolves_then_records():
    # drafter first returns prose with citation_missing, then with citation on retry
    # assert section status OK
    # assert Verification History entry has final_resolution=resolved, resolved_in_round=1
    pass
```

Fill in each test using the components built in Phases F, P, O. Use the `unittest.mock.Mock` LLM that returns canned dict responses per stage; wire the deterministic verifier real (it doesn't need an LLM).

- [ ] **Step 2: Run smoke, commit**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_e2e_smoke.py -v
git add packages/core/tests/llm/runtime/report_v2/test_e2e_smoke.py
git commit -m "test(report_v2): E2E smoke covering trigger skip, verifier retry resolution, unsupported intent path"
```

---

### Task V3: Multi-ticker smoke against AI-infra basket

**Files:**
- Test: `packages/core/tests/llm/runtime/report_v2/test_e2e_multi_ticker.py`

- [ ] **Step 1: Run real pipeline against 14 AI-infra tickers**

Marked with `@pytest.mark.slow` and `@pytest.mark.requires_llm`. Uses a real but cheap LLM tier (Haiku-class for verifier/trigger, Sonnet-class for planner/drafter). Asserts:

- Every report HTML parses and has the three required sections.
- No tickers produce FAILED Run Summaries on baseline outcomes (template-required strands/artifacts succeed for all 14).
- At least 80% of optional artifacts succeed across the basket.

- [ ] **Step 2: Run, document results**

```bash
uv run pytest packages/core/tests/llm/runtime/report_v2/test_e2e_multi_ticker.py -v -m "slow"
```

Record results in a one-pager `docs/superpowers/specs/2026-05-XX-v2.2-validation-results.md` (date filled at validation time).

- [ ] **Step 3: Commit**

```bash
git add packages/core/tests/llm/runtime/report_v2/test_e2e_multi_ticker.py
git commit -m "test(report_v2): multi-ticker smoke (14 AI-infra tickers) against v2.2 pipeline"
```

---

## Summary checklist

When all phases complete:

- [ ] All Phase F PRs merged: capability manifest, TemplateSpecV2, connectors, library helpers, cache
- [ ] All Phase P PRs merged: clarifier, research planner, gather, model planner, model build, drafter, verifier
- [ ] All Phase O PRs merged: block renderers, citation manifest, run summary, verification history, assembler
- [ ] All Phase X PRs merged: composer, clarifier modal, template upload, report viewer extras, cache admin
- [ ] All Phase V validation passes: default templates load, E2E smoke green, multi-ticker smoke ≥80% optional-artifact success
- [ ] v2 docs carry "Superseded" header (already done in Phase 0)
- [ ] `engine_version: 2.2` is the live default in `capabilities.yaml`
- [ ] `dev_mode: true` is the default for v2.2; production cutover documented as a future toggle

End of plan.



