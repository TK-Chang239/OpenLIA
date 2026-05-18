# Waved Report Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace both `ReportRunner` (classic) and `SubagentReportRunner` with a single `WavedReportRunner` that codifies "gather data first, then write" via six waves: baseline fetch → per-section pre-flight → facts compile → body write → synthesis write → deterministic pack.

**Architecture:** Writer model only fires in W4 and W5 and only emits Markdown (YAML frontmatter + body + typed fenced YAML blocks). Citations are first-class manifest entries built deterministically; facts are extracted via a named registry; the packer is the sole validator and owns all schema serialization. Rigid envelope fields (`cover.key_metrics`, `rail.*`) are filled by the packer directly from the facts pack — the writer never touches them.

**Tech Stack:** Python 3.13, Pydantic v2 (strict `extra="forbid"`), pytest+pytest-asyncio, ruff. uv for all package operations.

**Branch:** `feat/waved-report-runner` (create from `main` after `fix/report-strictness` lands)

**Spec:** `docs/superpowers/specs/2026-05-17-waved-report-runner-design.md`

---

## File structure

```
packages/core/src/openlia/llm/runtime/report_v2/
├── __init__.py
├── runner.py                  # WavedReportRunner — wave orchestration
├── types.py                   # ManifestEntry, Fact, SectionResult, WaveResult
├── manifest/
│   ├── __init__.py
│   ├── baseline.py            # W1: hard-coded per-report-type baseline fetches
│   ├── preflight.py           # W2: per-section pre-flight Haiku call
│   ├── aggregator.py          # W2: dedup + central execution
│   └── manifest.py            # numbered list, [N] resolution
├── facts/
│   ├── __init__.py
│   ├── registry.py            # @register_fact decorator + DAG resolver
│   ├── pack.py                # facts_pack compile + per-section slicing
│   └── extractors/
│       ├── __init__.py
│       ├── deterministic.py   # JSONPath/Pydantic extractors
│       ├── compute.py         # pure math extractors
│       ├── llm.py             # Haiku structured-output extractors
│       └── stock_initiation.py # registered facts for stock_initiation report type
├── sections/
│   ├── __init__.py
│   ├── dispatcher.py          # parallel dispatch + wave gate + terminal-state tracking
│   ├── prompts.py             # section writer prompt assembly (cache-ordered)
│   └── synthesis_hooks.py     # contract types
├── packer/
│   ├── __init__.py
│   ├── parser.py              # YAML frontmatter + Markdown body + fenced block parsing
│   ├── blocks/
│   │   ├── __init__.py
│   │   ├── registry.py        # block type registry (fence-tag → parser+validator+assembler)
│   │   ├── text.py            # text block
│   │   ├── table.py           # table block
│   │   ├── metric_cards.py    # metric_cards block
│   │   ├── key_finding.py     # key_finding block
│   │   ├── rating_badge.py
│   │   ├── pull_quote.py
│   │   ├── callout_grid.py
│   │   ├── timeline.py
│   │   ├── bullet_list.py
│   │   ├── comparison_split.py
│   │   ├── quote.py
│   │   ├── chart_line.py
│   │   ├── chart_bar.py
│   │   ├── chart_area.py
│   │   ├── chart_pie.py
│   │   ├── chart_combo.py
│   │   ├── chart_candlestick.py
│   │   ├── chart_waterfall.py
│   │   ├── chart_scatter.py
│   │   ├── chart_heatmap.py
│   │   ├── chart_treemap.py
│   │   └── group.py
│   ├── validator.py           # 5A: 5 semantic checks
│   ├── auto_repair.py         # soft fixes before declaring hard fail
│   └── assembler.py           # section files → ReportSchema, fills rigid slots from facts_pack
├── telemetry.py               # failure rates, sentinels, proposed_facts, latency, cost
└── frameworks/
    └── stock_initiation.facts.json  # section → list of registered fact names
```

Files to delete on cutover (Phase 8):
- `packages/core/src/openlia/llm/runtime/report.py`
- `packages/core/src/openlia/llm/runtime/subagent_runner.py`
- `packages/core/src/openlia/llm/runtime/subagent_client.py`
- `packages/core/src/openlia/llm/runtime/editor_client.py`
- `packages/core/src/openlia/llm/runtime/section_draft.py`
- `packages/core/src/openlia/llm/runtime/prior_section_summarizer.py`
- `packages/core/src/openlia/llm/runtime/plan_schema.py`
- `packages/core/src/openlia/prompts/shared/editor_role.yaml.j2`
- `packages/core/src/openlia/prompts/shared/section_subagent_role.yaml.j2`

---

## Phase outline

- **Phase 0** — Scaffolding (module skeleton, types, feature flag)
- **Phase 1** — Facts registry (decorators, DAG resolver, three extractor tiers)
- **Phase 2** — Manifest module (W1 baseline + W2 pre-flight + aggregator)
- **Phase 3** — Packer (parser + 22 block types + validator + auto-repair + assembler)
- **Phase 4** — Section dispatcher (prompts, parallel dispatch, wave gate, retry)
- **Phase 5** — Runner orchestration (wave wiring, SSE events, telemetry)
- **Phase 6** — Department wiring (feature flag, equity research integration)
- **Phase 7** — Structured diff + side-by-side validation
- **Phase 8** — Cutover + legacy deletion

Each phase ends in a green test suite and a commit. Phase 6 onwards requires a live LLM provider for end-to-end smoke; earlier phases use fixtures.

---

## Phase 0: Scaffolding

### Task 0.1: Create module skeleton

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/__init__.py`
- Create directory tree per the File structure section above

- [ ] **Step 1: Create the directory tree**

```bash
cd packages/core/src/openlia/llm/runtime
mkdir -p report_v2/{manifest,facts/extractors,sections,packer/blocks,frameworks}
touch report_v2/__init__.py
touch report_v2/{manifest,facts,facts/extractors,sections,packer,packer/blocks}/__init__.py
```

- [ ] **Step 2: Verify the tree exists**

Run: `find packages/core/src/openlia/llm/runtime/report_v2 -type d`
Expected: 8 directories listed.

- [ ] **Step 3: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2
git commit -m "feat(report_v2): scaffold module structure"
```

### Task 0.2: Shared types

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/types.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_types.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from openlia.llm.runtime.report_v2.types import (
    Fact,
    ManifestEntry,
    SectionResult,
    SectionTerminalState,
)


def test_manifest_entry_minimum() -> None:
    entry = ManifestEntry(
        id=1,
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/NET.US",
        raw_payload={"Highlights": {"MarketCapitalization": 30_200_000_000}},
        retrieved_at="2026-05-17T20:00:00Z",
    )
    assert entry.id == 1
    assert entry.provider == "eodhd"


def test_fact_default_provenance_empty_list_rejected() -> None:
    """Facts must carry at least one source_id — empty provenance is a bug."""
    with pytest.raises(ValidationError):
        Fact(name="current_price", value=89.43, source_ids=[], extractor="deterministic", depends_on=[])


def test_fact_with_union_provenance_from_compute() -> None:
    fact = Fact(
        name="revenue_cagr_3y",
        value=0.234,
        source_ids=[7, 8, 9],
        extractor="compute",
        depends_on=["revenue_annual"],
    )
    assert fact.source_ids == [7, 8, 9]


def test_section_result_terminal_states() -> None:
    assert SectionTerminalState.SUCCESS.value == "success"
    assert SectionTerminalState.DEGRADED.value == "degraded"
    assert SectionTerminalState.EXHAUSTED.value == "exhausted"


def test_section_result_records_attempts() -> None:
    result = SectionResult(
        section_id="industry_overview",
        state=SectionTerminalState.DEGRADED,
        attempts=2,
        markdown="---\n...",
        failed_attempts=["first try output", "second try output"],
        validation_errors=["word_count: 412 < 600", "uncited_number: 28%"],
    )
    assert result.attempts == 2
    assert len(result.failed_attempts) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_types.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/types.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


ExtractorTier = Literal["deterministic", "compute", "llm"]
ManifestKind = Literal["fetch", "search"]


class ManifestEntry(_Strict):
    """One source of truth, citable as [N] across the run."""

    id: int = Field(ge=1)
    kind: ManifestKind
    provider: str
    identifier: str  # tool name + args fingerprint, or search query
    raw_payload: Any
    retrieved_at: datetime | str


class Fact(_Strict):
    """A named, citation-tagged value produced by the registry."""

    name: str
    value: Any
    source_ids: list[int] = Field(min_length=1)
    extractor: ExtractorTier
    depends_on: list[str] = Field(default_factory=list)


class SectionTerminalState(str, Enum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    EXHAUSTED = "exhausted"


class SectionResult(_Strict):
    section_id: str
    state: SectionTerminalState
    attempts: int = Field(ge=1)
    markdown: str | None = None
    failed_attempts: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    synthesis_hooks: dict[str, Any] | None = None

    @field_validator("markdown")
    @classmethod
    def _markdown_required_unless_exhausted(cls, v: str | None, info: Any) -> str | None:
        state = info.data.get("state")
        if state == SectionTerminalState.EXHAUSTED:
            return v
        if v is None or not v.strip():
            raise ValueError("markdown required for success/degraded states")
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_types.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/types.py packages/core/tests/test_llm/test_runtime/test_report_v2/
git commit -m "feat(report_v2): shared types — ManifestEntry, Fact, SectionResult"
```

### Task 0.3: Feature flag

**Files:**
- Modify: `packages/core/src/openlia/config.py` (add `report_v2_enabled: bool = False` to settings)
- Test: `packages/core/tests/test_config.py` (extend existing config test)

- [ ] **Step 1: Locate the config module**

Run: `grep -n "class.*Settings" packages/core/src/openlia/config.py`
Expected: A `Settings` or `OpenLIAConfig` Pydantic class location.

- [ ] **Step 2: Write the failing test**

```python
# packages/core/tests/test_config.py — add to existing file
def test_report_v2_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("OPENLIA_REPORT_V2_ENABLED", raising=False)
    from openlia.config import load_config
    cfg = load_config()
    assert cfg.report_v2_enabled is False


def test_report_v2_flag_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_REPORT_V2_ENABLED", "true")
    from openlia.config import load_config
    cfg = load_config()
    assert cfg.report_v2_enabled is True
```

- [ ] **Step 3: Add the field to config**

Add `report_v2_enabled: bool = Field(default=False, alias="OPENLIA_REPORT_V2_ENABLED")` to the settings class. Mirror the pattern of an existing boolean flag in the file.

- [ ] **Step 4: Run the config tests**

Run: `uv run pytest packages/core/tests/test_config.py -v`
Expected: PASS including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/config.py packages/core/tests/test_config.py
git commit -m "feat(config): add report_v2_enabled feature flag (default off)"
```

---

## Phase 1: Facts registry

The registry is the contract for cross-section consistency. It must be standalone-testable with fixture payloads — no LLM required at this phase.

### Task 1.1: Registry core + decorator

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/facts/registry.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_registry.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.facts.registry import (
    FactRegistry,
    register_fact,
)
from openlia.llm.runtime.report_v2.types import Fact


def test_register_and_retrieve_deterministic() -> None:
    reg = FactRegistry()

    @reg.register("dummy_price", tier="deterministic", depends_on=[])
    def _extract(payloads, facts):
        return Fact(
            name="dummy_price",
            value=42.0,
            source_ids=[1],
            extractor="deterministic",
            depends_on=[],
        )

    entry = reg.get("dummy_price")
    assert entry.name == "dummy_price"
    assert entry.tier == "deterministic"
    assert entry.depends_on == []


def test_duplicate_registration_rejected() -> None:
    reg = FactRegistry()

    @reg.register("x", tier="deterministic", depends_on=[])
    def _a(payloads, facts):
        return Fact(name="x", value=1, source_ids=[1], extractor="deterministic")

    with pytest.raises(ValueError, match="already registered"):
        @reg.register("x", tier="compute", depends_on=[])
        def _b(payloads, facts):
            return Fact(name="x", value=2, source_ids=[1], extractor="compute")


def test_unknown_dependency_rejected_at_get_resolution_order() -> None:
    reg = FactRegistry()

    @reg.register("downstream", tier="compute", depends_on=["does_not_exist"])
    def _f(payloads, facts):
        return Fact(name="downstream", value=0, source_ids=[1], extractor="compute")

    with pytest.raises(ValueError, match="unknown dependency"):
        reg.resolution_order(["downstream"])


def test_resolution_order_respects_dag() -> None:
    reg = FactRegistry()

    @reg.register("a", tier="deterministic", depends_on=[])
    def _a(payloads, facts):
        return Fact(name="a", value=1, source_ids=[1], extractor="deterministic")

    @reg.register("b", tier="compute", depends_on=["a"])
    def _b(payloads, facts):
        return Fact(name="b", value=2, source_ids=[1], extractor="compute")

    @reg.register("c", tier="compute", depends_on=["a", "b"])
    def _c(payloads, facts):
        return Fact(name="c", value=3, source_ids=[1], extractor="compute")

    order = reg.resolution_order(["c"])
    assert order == ["a", "b", "c"]


def test_resolution_order_dedupes_shared_deps() -> None:
    reg = FactRegistry()

    @reg.register("shared", tier="deterministic", depends_on=[])
    def _s(payloads, facts):
        return Fact(name="shared", value=1, source_ids=[1], extractor="deterministic")

    @reg.register("x", tier="compute", depends_on=["shared"])
    def _x(payloads, facts):
        return Fact(name="x", value=1, source_ids=[1], extractor="compute")

    @reg.register("y", tier="compute", depends_on=["shared"])
    def _y(payloads, facts):
        return Fact(name="y", value=1, source_ids=[1], extractor="compute")

    order = reg.resolution_order(["x", "y"])
    assert order.count("shared") == 1
    assert order.index("shared") < order.index("x")
    assert order.index("shared") < order.index("y")


def test_cycle_detection() -> None:
    reg = FactRegistry()

    @reg.register("p", tier="compute", depends_on=["q"])
    def _p(payloads, facts):
        return Fact(name="p", value=0, source_ids=[1], extractor="compute")

    @reg.register("q", tier="compute", depends_on=["p"])
    def _q(payloads, facts):
        return Fact(name="q", value=0, source_ids=[1], extractor="compute")

    with pytest.raises(ValueError, match="cycle"):
        reg.resolution_order(["p"])


def test_global_default_registry_singleton() -> None:
    from openlia.llm.runtime.report_v2.facts.registry import default_registry

    @register_fact("globally_registered", tier="deterministic", depends_on=[])
    def _f(payloads, facts):
        return Fact(name="globally_registered", value=0, source_ids=[1], extractor="deterministic")

    assert "globally_registered" in default_registry.names()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_registry.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/registry.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.types import ExtractorTier, Fact

ExtractorFn = Callable[[Any, Any], Fact]


@dataclass(frozen=True)
class RegistryEntry:
    name: str
    tier: ExtractorTier
    depends_on: list[str]
    fn: ExtractorFn


class FactRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(
        self,
        name: str,
        *,
        tier: ExtractorTier,
        depends_on: list[str],
    ) -> Callable[[ExtractorFn], ExtractorFn]:
        if name in self._entries:
            raise ValueError(f"fact {name!r} already registered")

        def deco(fn: ExtractorFn) -> ExtractorFn:
            self._entries[name] = RegistryEntry(
                name=name, tier=tier, depends_on=list(depends_on), fn=fn
            )
            return fn

        return deco

    def get(self, name: str) -> RegistryEntry:
        return self._entries[name]

    def names(self) -> list[str]:
        return list(self._entries.keys())

    def resolution_order(self, requested: list[str]) -> list[str]:
        """Topological sort with dedup. Raises on unknown deps or cycles."""
        order: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(n: str) -> None:
            if n in visited:
                return
            if n in visiting:
                raise ValueError(f"cycle detected at {n!r}")
            if n not in self._entries:
                raise ValueError(f"unknown dependency: {n!r}")
            visiting.add(n)
            for d in self._entries[n].depends_on:
                visit(d)
            visiting.remove(n)
            visited.add(n)
            order.append(n)

        for n in requested:
            visit(n)
        return order


default_registry = FactRegistry()


def register_fact(
    name: str,
    *,
    tier: ExtractorTier,
    depends_on: list[str],
) -> Callable[[ExtractorFn], ExtractorFn]:
    """Module-level decorator for the default registry."""
    return default_registry.register(name, tier=tier, depends_on=depends_on)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_registry.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/facts/registry.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_registry.py
git commit -m "feat(report_v2/facts): registry + DAG resolver"
```

### Task 1.2: Facts pack compiler

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/facts/pack.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_pack.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_pack.py
from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.pack import FactsPack, PayloadView, compile_pack
from openlia.llm.runtime.report_v2.facts.registry import FactRegistry
from openlia.llm.runtime.report_v2.types import Fact, ManifestEntry


def _entry(id: int, identifier: str, payload: dict) -> ManifestEntry:
    return ManifestEntry(
        id=id,
        kind="fetch",
        provider="eodhd",
        identifier=identifier,
        raw_payload=payload,
        retrieved_at="2026-05-17T20:00:00Z",
    )


def test_compile_single_deterministic_fact() -> None:
    reg = FactRegistry()

    @reg.register("market_cap", tier="deterministic", depends_on=[])
    def _mc(payloads: PayloadView, facts) -> Fact:
        mc = payloads.by_identifier("get_fundamentals_data/NET.US")["Highlights"]["MarketCapitalization"]
        return Fact(
            name="market_cap",
            value=mc,
            source_ids=[payloads.manifest_id_for("get_fundamentals_data/NET.US")],
            extractor="deterministic",
        )

    manifest = [
        _entry(1, "get_fundamentals_data/NET.US", {"Highlights": {"MarketCapitalization": 30_200_000_000}}),
    ]
    pack = compile_pack(registry=reg, manifest=manifest, requested_facts=["market_cap"])
    assert pack.get("market_cap").value == 30_200_000_000
    assert pack.get("market_cap").source_ids == [1]


def test_compile_compute_inherits_union_of_sources() -> None:
    reg = FactRegistry()

    @reg.register("revenue_y1", tier="deterministic", depends_on=[])
    def _r1(payloads, facts):
        return Fact(name="revenue_y1", value=100, source_ids=[1], extractor="deterministic")

    @reg.register("revenue_y3", tier="deterministic", depends_on=[])
    def _r3(payloads, facts):
        return Fact(name="revenue_y3", value=180, source_ids=[2], extractor="deterministic")

    @reg.register("revenue_cagr_2y", tier="compute", depends_on=["revenue_y1", "revenue_y3"])
    def _c(payloads, facts):
        v1 = facts["revenue_y1"].value
        v3 = facts["revenue_y3"].value
        return Fact(
            name="revenue_cagr_2y",
            value=(v3 / v1) ** 0.5 - 1,
            source_ids=sorted({*facts["revenue_y1"].source_ids, *facts["revenue_y3"].source_ids}),
            extractor="compute",
        )

    manifest = [_entry(1, "rev_y1", {}), _entry(2, "rev_y3", {})]
    pack = compile_pack(registry=reg, manifest=manifest, requested_facts=["revenue_cagr_2y"])
    assert pack.get("revenue_cagr_2y").source_ids == [1, 2]


def test_slice_for_section_returns_only_requested_names() -> None:
    reg = FactRegistry()
    for n in ["a", "b", "c"]:
        @reg.register(n, tier="deterministic", depends_on=[])
        def _f(payloads, facts, _name=n):
            return Fact(name=_name, value=1, source_ids=[1], extractor="deterministic")

    pack = compile_pack(
        registry=reg,
        manifest=[_entry(1, "x", {})],
        requested_facts=["a", "b", "c"],
    )
    sliced = pack.slice_for(["a", "c"])
    assert set(sliced.keys()) == {"a", "c"}


def test_slice_for_unknown_fact_raises() -> None:
    reg = FactRegistry()

    @reg.register("known", tier="deterministic", depends_on=[])
    def _f(payloads, facts):
        return Fact(name="known", value=1, source_ids=[1], extractor="deterministic")

    pack = compile_pack(registry=reg, manifest=[_entry(1, "x", {})], requested_facts=["known"])
    try:
        pack.slice_for(["unknown"])
    except KeyError as e:
        assert "unknown" in str(e)
    else:
        raise AssertionError("expected KeyError")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_pack.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/pack.py
from __future__ import annotations

from dataclasses import dataclass

from openlia.llm.runtime.report_v2.facts.registry import FactRegistry
from openlia.llm.runtime.report_v2.types import Fact, ManifestEntry


class PayloadView:
    """Indexed view over the manifest, exposed to extractor functions."""

    def __init__(self, manifest: list[ManifestEntry]) -> None:
        self._by_identifier: dict[str, ManifestEntry] = {e.identifier: e for e in manifest}

    def by_identifier(self, identifier: str):
        return self._by_identifier[identifier].raw_payload

    def manifest_id_for(self, identifier: str) -> int:
        return self._by_identifier[identifier].id

    def has(self, identifier: str) -> bool:
        return identifier in self._by_identifier


@dataclass
class FactsPack:
    facts: dict[str, Fact]

    def get(self, name: str) -> Fact:
        return self.facts[name]

    def slice_for(self, names: list[str]) -> dict[str, Fact]:
        out: dict[str, Fact] = {}
        for n in names:
            if n not in self.facts:
                raise KeyError(n)
            out[n] = self.facts[n]
        return out


def compile_pack(
    *,
    registry: FactRegistry,
    manifest: list[ManifestEntry],
    requested_facts: list[str],
) -> FactsPack:
    order = registry.resolution_order(requested_facts)
    payloads = PayloadView(manifest)
    facts: dict[str, Fact] = {}
    for name in order:
        entry = registry.get(name)
        fact = entry.fn(payloads, facts)
        if fact.name != name:
            raise ValueError(f"extractor for {name!r} returned fact named {fact.name!r}")
        facts[name] = fact
    return FactsPack(facts=facts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_pack.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/facts/pack.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_pack.py
git commit -m "feat(report_v2/facts): pack compiler with DAG-ordered extraction"
```

### Task 1.3: Deterministic extractors for stock_initiation

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/deterministic.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/stock_initiation.py` (registration site)
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_deterministic.py`

- [ ] **Step 1: Capture a real EODHD fundamentals payload fixture**

Save a known-shape fixture (truncated to relevant keys) at `packages/core/tests/fixtures/report_v2/eodhd_fundamentals_net.json`. Use an existing fixture if one exists in `packages/core/tests/fixtures/` — check first:

Run: `find packages/core/tests/fixtures -name '*fundament*' -o -name 'eodhd*'`

If none exists, create a minimal one:

```json
{
  "General": {
    "Code": "NET", "Name": "Cloudflare, Inc.", "Sector": "Technology",
    "Industry": "Software—Infrastructure", "Exchange": "NYSE"
  },
  "Highlights": {
    "MarketCapitalization": 30200000000,
    "PERatio": 142.1,
    "EPSEstimateCurrentYear": 0.84,
    "DividendYield": 0
  },
  "Financials": {
    "Income_Statement": {
      "yearly": {
        "2024-12-31": {"totalRevenue": "1670000000", "grossProfit": "1290000000"},
        "2023-12-31": {"totalRevenue": "1297000000", "grossProfit": "1010000000"},
        "2022-12-31": {"totalRevenue": "975200000", "grossProfit": "734000000"},
        "2021-12-31": {"totalRevenue": "656400000", "grossProfit": "508000000"},
        "2020-12-31": {"totalRevenue": "431100000", "grossProfit": "330000000"}
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_deterministic.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import FactRegistry
from openlia.llm.runtime.report_v2.types import ManifestEntry

FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "report_v2" / "eodhd_fundamentals_net.json"


def _load_fundamentals_manifest() -> list[ManifestEntry]:
    payload = json.loads(FIXTURE.read_text())
    return [
        ManifestEntry(
            id=1,
            kind="fetch",
            provider="eodhd",
            identifier="get_fundamentals_data/NET.US",
            raw_payload=payload,
            retrieved_at="2026-05-17T20:00:00Z",
        )
    ]


def _registry_with_stock_initiation_facts() -> FactRegistry:
    from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401  triggers registration
    from openlia.llm.runtime.report_v2.facts.registry import default_registry
    return default_registry


@pytest.mark.parametrize(
    "fact_name,expected",
    [
        ("market_cap", 30_200_000_000),
        ("pe_ratio_ttm", 142.1),
        ("sector", "Technology"),
        ("company_name", "Cloudflare, Inc."),
    ],
)
def test_deterministic_extractors_pull_from_fixture(fact_name: str, expected) -> None:
    reg = _registry_with_stock_initiation_facts()
    pack = compile_pack(registry=reg, manifest=_load_fundamentals_manifest(), requested_facts=[fact_name])
    assert pack.get(fact_name).value == expected
    assert pack.get(fact_name).source_ids == [1]


def test_revenue_annual_returns_five_year_series() -> None:
    reg = _registry_with_stock_initiation_facts()
    pack = compile_pack(registry=reg, manifest=_load_fundamentals_manifest(), requested_facts=["revenue_annual"])
    series = pack.get("revenue_annual").value
    assert len(series) == 5
    assert series[-1] == 1_670_000_000
    assert series[0] == 431_100_000
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_deterministic.py -v`
Expected: FAIL — extractors don't exist yet.

- [ ] **Step 4: Write the deterministic extractor helpers**

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/deterministic.py
"""Deterministic JSONPath-style extractors. Stateless helpers; the
register_fact decorations live in the per-report-type module
(e.g. stock_initiation.py) so importing this module has no side effects."""
from __future__ import annotations

from typing import Any


def pluck(payload: Any, *path: str) -> Any:
    """Walk a nested dict path, raising KeyError with full breadcrumb on miss."""
    cur = payload
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            raise KeyError(f"missing key {'.'.join(path)!r} (failed at {key!r})")
        cur = cur[key]
    return cur


def pluck_or_none(payload: Any, *path: str) -> Any:
    try:
        return pluck(payload, *path)
    except KeyError:
        return None


def yearly_series(payload: Any, *, statement: str, field: str, n_years: int = 5) -> list[float]:
    """Extract last-N-years series from EODHD income/balance/cashflow shape."""
    yearly = pluck(payload, "Financials", statement, "yearly")
    sorted_dates = sorted(yearly.keys())[-n_years:]
    return [float(yearly[d][field]) for d in sorted_dates]
```

- [ ] **Step 5: Write the stock_initiation registrations**

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/stock_initiation.py
"""Registered facts for the stock_initiation report type.

Importing this module triggers registration with the default_registry.
"""
from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.extractors.deterministic import (
    pluck,
    yearly_series,
)
from openlia.llm.runtime.report_v2.facts.registry import register_fact
from openlia.llm.runtime.report_v2.types import Fact

_FUNDAMENTALS = "get_fundamentals_data"


@register_fact("market_cap", tier="deterministic", depends_on=[])
def market_cap(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="market_cap",
        value=pluck(payload, "Highlights", "MarketCapitalization"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("pe_ratio_ttm", tier="deterministic", depends_on=[])
def pe_ratio_ttm(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="pe_ratio_ttm",
        value=pluck(payload, "Highlights", "PERatio"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("sector", tier="deterministic", depends_on=[])
def sector(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="sector",
        value=pluck(payload, "General", "Sector"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("company_name", tier="deterministic", depends_on=[])
def company_name(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="company_name",
        value=pluck(payload, "General", "Name"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("revenue_annual", tier="deterministic", depends_on=[])
def revenue_annual(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="revenue_annual",
        value=yearly_series(payload, statement="Income_Statement", field="totalRevenue"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


def _find_fundamentals_identifier(payloads) -> str:
    """Find the manifest identifier for a fundamentals fetch (ticker-agnostic)."""
    for candidate in list(payloads._by_identifier.keys()):  # noqa: SLF001
        if candidate.startswith(_FUNDAMENTALS + "/"):
            return candidate
    raise KeyError(f"no manifest entry starting with {_FUNDAMENTALS!r}")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_deterministic.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/ packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_deterministic.py packages/core/tests/fixtures/report_v2/
git commit -m "feat(report_v2/facts): deterministic extractors for stock_initiation"
```

### Task 1.4: Compute extractors

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/compute.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/stock_initiation.py` (add compute-tier registrations)
- Test: extend `test_extractors_deterministic.py` or new file `test_extractors_compute.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_compute.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.registry import default_registry
from openlia.llm.runtime.report_v2.types import ManifestEntry

FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "report_v2" / "eodhd_fundamentals_net.json"


def _manifest() -> list[ManifestEntry]:
    payload = json.loads(FIXTURE.read_text())
    return [ManifestEntry(
        id=1, kind="fetch", provider="eodhd",
        identifier="get_fundamentals_data/NET.US",
        raw_payload=payload, retrieved_at="2026-05-17T20:00:00Z",
    )]


def test_revenue_cagr_3y_computed_correctly() -> None:
    pack = compile_pack(registry=default_registry, manifest=_manifest(), requested_facts=["revenue_cagr_3y"])
    # 2021 → 2024 revenue: 656.4M → 1670M, CAGR = (1670/656.4)^(1/3) - 1 = 0.365 approx
    assert pack.get("revenue_cagr_3y").value == pytest.approx(0.365, abs=0.005)


def test_revenue_cagr_3y_inherits_source_from_revenue_annual() -> None:
    pack = compile_pack(registry=default_registry, manifest=_manifest(), requested_facts=["revenue_cagr_3y"])
    assert pack.get("revenue_cagr_3y").source_ids == [1]
    assert pack.get("revenue_cagr_3y").extractor == "compute"


def test_gross_margin_ttm_uses_latest_year() -> None:
    pack = compile_pack(registry=default_registry, manifest=_manifest(), requested_facts=["gross_margin_ttm"])
    # 2024: 1290/1670 = 0.7725
    assert pack.get("gross_margin_ttm").value == pytest.approx(0.7725, abs=0.001)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_compute.py -v`
Expected: FAIL — compute extractors not registered.

- [ ] **Step 3: Write compute helpers**

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/compute.py
"""Pure-Python compute extractors. Operate on already-extracted facts, no payload access."""
from __future__ import annotations


def cagr(series: list[float], years: int) -> float:
    if len(series) < years + 1:
        raise ValueError(f"need {years + 1} points for {years}-year CAGR, got {len(series)}")
    start = series[-(years + 1)]
    end = series[-1]
    return (end / start) ** (1 / years) - 1


def union_source_ids(*facts) -> list[int]:
    ids: set[int] = set()
    for f in facts:
        ids.update(f.source_ids)
    return sorted(ids)
```

- [ ] **Step 4: Add compute registrations to stock_initiation**

Append to `stock_initiation.py`:

```python
from openlia.llm.runtime.report_v2.facts.extractors.compute import cagr, union_source_ids


@register_fact("revenue_cagr_3y", tier="compute", depends_on=["revenue_annual"])
def revenue_cagr_3y(payloads, facts) -> Fact:
    series = facts["revenue_annual"].value
    return Fact(
        name="revenue_cagr_3y",
        value=cagr(series, years=3),
        source_ids=union_source_ids(facts["revenue_annual"]),
        extractor="compute",
        depends_on=["revenue_annual"],
    )


@register_fact("gross_profit_annual", tier="deterministic", depends_on=[])
def gross_profit_annual(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="gross_profit_annual",
        value=yearly_series(payload, statement="Income_Statement", field="grossProfit"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("gross_margin_ttm", tier="compute", depends_on=["revenue_annual", "gross_profit_annual"])
def gross_margin_ttm(payloads, facts) -> Fact:
    rev = facts["revenue_annual"].value[-1]
    gp = facts["gross_profit_annual"].value[-1]
    return Fact(
        name="gross_margin_ttm",
        value=gp / rev,
        source_ids=union_source_ids(facts["revenue_annual"], facts["gross_profit_annual"]),
        extractor="compute",
        depends_on=["revenue_annual", "gross_profit_annual"],
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/ -v`
Expected: PASS — all tests including the new compute ones.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/ packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_compute.py
git commit -m "feat(report_v2/facts): compute extractors (CAGR, margins)"
```

### Task 1.5: LLM extractor scaffolding (mock-backed)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/llm.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_llm.py`

The LLM extractor wraps a structured-output call against a small per-fact schema. At this phase we test with a mock; real provider wiring happens in Phase 5.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_llm.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.report_v2.facts.extractors.llm import llm_extract
from openlia.llm.runtime.report_v2.types import Fact


@pytest.mark.asyncio
async def test_llm_extract_calls_provider_with_schema_and_returns_fact() -> None:
    mock_provider = AsyncMock()
    mock_provider.structured_output.return_value = {"peer_tickers": ["AKAM", "FSLY", "NET"]}

    fact = await llm_extract(
        provider=mock_provider,
        fact_name="peer_set",
        prompt="Identify peer companies for Cloudflare in the CDN/edge space.",
        output_schema={"type": "object", "properties": {"peer_tickers": {"type": "array", "items": {"type": "string"}}}},
        source_ids=[1, 3],
    )
    assert fact.name == "peer_set"
    assert fact.value == {"peer_tickers": ["AKAM", "FSLY", "NET"]}
    assert fact.source_ids == [1, 3]
    assert fact.extractor == "llm"
    mock_provider.structured_output.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_llm.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/llm.py
"""LLM-tier extractor — wraps a structured-output call against a small per-fact schema.

The provider protocol is intentionally narrow: structured_output(prompt, schema) -> dict.
Phase 5 wires this to the real provider; Phase 1 tests use AsyncMock.
"""
from __future__ import annotations

from typing import Any, Protocol

from openlia.llm.runtime.report_v2.types import Fact


class StructuredOutputProvider(Protocol):
    async def structured_output(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


async def llm_extract(
    *,
    provider: StructuredOutputProvider,
    fact_name: str,
    prompt: str,
    output_schema: dict[str, Any],
    source_ids: list[int],
) -> Fact:
    value = await provider.structured_output(prompt=prompt, schema=output_schema)
    return Fact(
        name=fact_name,
        value=value,
        source_ids=sorted(set(source_ids)),
        extractor="llm",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_llm.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/llm.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_llm.py
git commit -m "feat(report_v2/facts): llm extractor scaffolding (mock-backed)"
```

### Task 1.6: Per-report-type facts JSON

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/frameworks/stock_initiation.facts.json`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_framework.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_framework.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.registry import default_registry


FACTS_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "src" / "openlia" / "llm" / "runtime" / "report_v2"
    / "frameworks" / "stock_initiation.facts.json"
)


def test_facts_file_exists_and_is_valid_json() -> None:
    data = json.loads(FACTS_PATH.read_text())
    assert "sections" in data
    assert isinstance(data["sections"], dict)


def test_every_referenced_fact_is_registered() -> None:
    data = json.loads(FACTS_PATH.read_text())
    registered = set(default_registry.names())
    referenced: set[str] = set()
    for section_id, fact_names in data["sections"].items():
        referenced.update(fact_names)
    unknown = referenced - registered
    assert not unknown, f"facts referenced but not registered: {sorted(unknown)}"


def test_cover_section_includes_key_metrics_facts() -> None:
    data = json.loads(FACTS_PATH.read_text())
    cover = set(data["sections"]["cover"])
    assert {"market_cap", "pe_ratio_ttm", "company_name"}.issubset(cover)


@pytest.mark.parametrize(
    "section_id",
    [
        "company_overview", "industry_overview", "products_and_services",
        "business_model", "management_team", "historical_financials",
        "financial_analysis", "financial_projections", "valuation_analysis",
        "competitive_analysis", "recent_developments",
        "competitive_advantages_and_weaknesses", "risk_analysis",
        "investment_recommendation", "cover",
    ],
)
def test_every_framework_section_declares_facts(section_id: str) -> None:
    data = json.loads(FACTS_PATH.read_text())
    assert section_id in data["sections"], f"missing facts list for {section_id}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_framework.py -v`
Expected: FAIL — file missing.

- [ ] **Step 3: Write the facts JSON**

```json
{
  "report_type": "stock_initiation",
  "sections": {
    "cover": ["company_name", "sector", "market_cap", "pe_ratio_ttm"],
    "company_overview": ["company_name", "sector", "market_cap"],
    "industry_overview": ["sector"],
    "products_and_services": ["company_name"],
    "business_model": ["company_name", "revenue_cagr_3y", "gross_margin_ttm"],
    "management_team": ["company_name"],
    "historical_financials": ["revenue_annual", "gross_profit_annual", "revenue_cagr_3y", "gross_margin_ttm"],
    "financial_analysis": ["revenue_cagr_3y", "gross_margin_ttm"],
    "financial_projections": ["revenue_annual", "revenue_cagr_3y"],
    "valuation_analysis": ["market_cap", "pe_ratio_ttm", "revenue_cagr_3y"],
    "competitive_analysis": ["sector"],
    "recent_developments": ["company_name"],
    "competitive_advantages_and_weaknesses": ["sector", "gross_margin_ttm"],
    "risk_analysis": ["sector", "revenue_cagr_3y"],
    "investment_recommendation": ["company_name", "market_cap", "pe_ratio_ttm", "revenue_cagr_3y"]
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_framework.py -v`
Expected: PASS (4 + parametrized 15 = 19 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/frameworks/stock_initiation.facts.json packages/core/tests/test_llm/test_runtime/test_report_v2/test_facts_framework.py
git commit -m "feat(report_v2/frameworks): stock_initiation facts declarations per section"
```

### Phase 1 acceptance

- All facts tests green: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/ -v`
- Lint clean: `uv run ruff check packages/core/src/openlia/llm/runtime/report_v2/`
- Registry has the deterministic + compute extractors stock_initiation references; LLM extractor scaffolding ready for Phase 5 wiring; per-report-type facts JSON parses and every referenced fact resolves.

---

## Phase 2: Manifest module

### Task 2.1: Manifest container

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/manifest/manifest.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_manifest.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.types import ManifestEntry


def _entry(provider: str, identifier: str, payload=None) -> dict:
    return {
        "kind": "fetch",
        "provider": provider,
        "identifier": identifier,
        "raw_payload": payload or {},
        "retrieved_at": "2026-05-17T20:00:00Z",
    }


def test_append_assigns_monotonic_ids() -> None:
    m = Manifest()
    a = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    b = m.append(**_entry("eodhd", "get_holders/NET.US"))
    assert a.id == 1
    assert b.id == 2


def test_append_dedupes_by_identifier_returns_existing() -> None:
    m = Manifest()
    a = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    b = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    assert a.id == b.id == 1
    assert len(m.entries) == 1


def test_resolve_known_marker() -> None:
    m = Manifest()
    e = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    assert m.resolve(e.id) is e


def test_resolve_unknown_marker_raises() -> None:
    m = Manifest()
    with pytest.raises(KeyError):
        m.resolve(99)


def test_as_prompt_list_renders_compact_form() -> None:
    m = Manifest()
    m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    m.append(**_entry("websearch", "edge platform market TAM 2025"))
    rendered = m.as_prompt_list()
    assert "[1] eodhd/get_fundamentals_data/NET.US" in rendered
    assert "[2] websearch/edge platform market TAM 2025" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_manifest.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/manifest/manifest.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.types import ManifestEntry, ManifestKind


@dataclass
class Manifest:
    entries: list[ManifestEntry] = field(default_factory=list)
    _by_identifier: dict[str, ManifestEntry] = field(default_factory=dict)

    def append(
        self,
        *,
        kind: ManifestKind,
        provider: str,
        identifier: str,
        raw_payload: Any,
        retrieved_at: Any,
    ) -> ManifestEntry:
        if identifier in self._by_identifier:
            return self._by_identifier[identifier]
        entry = ManifestEntry(
            id=len(self.entries) + 1,
            kind=kind,
            provider=provider,
            identifier=identifier,
            raw_payload=raw_payload,
            retrieved_at=retrieved_at,
        )
        self.entries.append(entry)
        self._by_identifier[identifier] = entry
        return entry

    def resolve(self, marker_id: int) -> ManifestEntry:
        if not (1 <= marker_id <= len(self.entries)):
            raise KeyError(f"manifest id {marker_id} out of range (1..{len(self.entries)})")
        return self.entries[marker_id - 1]

    def as_prompt_list(self) -> str:
        return "\n".join(
            f"[{e.id}] {e.provider}/{e.identifier}" for e in self.entries
        )

    def __len__(self) -> int:
        return len(self.entries)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_manifest.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/manifest/manifest.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_manifest.py
git commit -m "feat(report_v2/manifest): manifest container with dedup and [N] resolution"
```

### Task 2.2: W1 baseline fetch catalog

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/manifest/baseline.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_baseline.py`

The baseline fetcher is per-report-type. For `stock_initiation`, it enumerates the ~12 always-required calls. Each call is dispatched via a tool dispatcher (interface defined; real wiring in Phase 5).

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_baseline.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.report_v2.manifest.baseline import (
    BaselineCall,
    BASELINE_STOCK_INITIATION,
    run_baseline,
)


def test_baseline_catalog_has_expected_calls() -> None:
    names = {(c.provider, c.tool) for c in BASELINE_STOCK_INITIATION}
    assert ("eodhd", "get_fundamentals_data") in names
    assert ("eodhd", "get_holders") in names
    assert ("eodhd", "get_insider_transactions") in names
    assert ("eodhd", "get_historical_prices") in names
    assert ("eodhd", "get_live_prices") in names
    assert ("news", "recent_news") in names
    assert len(BASELINE_STOCK_INITIATION) >= 10


@pytest.mark.asyncio
async def test_run_baseline_dispatches_each_call_in_parallel() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: {"called": f"{provider}.{tool}", "args": args}
    catalog = [
        BaselineCall(provider="eodhd", tool="get_fundamentals_data", args={"ticker": "NET.US"}),
        BaselineCall(provider="eodhd", tool="get_holders", args={"ticker": "NET.US"}),
    ]
    manifest = await run_baseline(catalog=catalog, dispatcher=dispatcher)
    assert len(manifest) == 2
    assert manifest.entries[0].identifier == "get_fundamentals_data/NET.US"
    assert manifest.entries[1].identifier == "get_holders/NET.US"
    assert dispatcher.dispatch.await_count == 2


@pytest.mark.asyncio
async def test_run_baseline_skips_failed_calls_records_in_telemetry() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = [
        {"ok": True},
        RuntimeError("provider down"),
    ]
    catalog = [
        BaselineCall(provider="eodhd", tool="get_fundamentals_data", args={"ticker": "NET.US"}),
        BaselineCall(provider="eodhd", tool="get_holders", args={"ticker": "NET.US"}),
    ]
    manifest = await run_baseline(catalog=catalog, dispatcher=dispatcher)
    assert len(manifest) == 1
    assert manifest.entries[0].identifier == "get_fundamentals_data/NET.US"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_baseline.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/manifest/baseline.py
"""W1: hard-coded baseline fetches per report type."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest


class ToolDispatcher(Protocol):
    async def dispatch(self, provider: str, tool: str, args: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class BaselineCall:
    provider: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)

    def identifier(self) -> str:
        ticker = self.args.get("ticker") or self.args.get("query") or ""
        return f"{self.tool}/{ticker}" if ticker else self.tool


BASELINE_STOCK_INITIATION: tuple[BaselineCall, ...] = (
    BaselineCall("eodhd", "get_live_prices", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_fundamentals_data", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_historical_market_cap", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_historical_prices", {"ticker": "{ticker}", "lookback": "60d"}),
    BaselineCall("eodhd", "get_historical_prices_long", {"ticker": "{ticker}", "lookback": "5y"}),
    BaselineCall("eodhd", "get_income_statement", {"ticker": "{ticker}", "years": 5}),
    BaselineCall("eodhd", "get_balance_sheet", {"ticker": "{ticker}", "years": 5}),
    BaselineCall("eodhd", "get_cash_flow", {"ticker": "{ticker}", "years": 5}),
    BaselineCall("eodhd", "get_earnings_trends", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_holders", {"ticker": "{ticker}"}),
    BaselineCall("eodhd", "get_insider_transactions", {"ticker": "{ticker}"}),
    BaselineCall("news", "recent_news", {"ticker": "{ticker}", "lookback_days": 30}),
)


def materialize(catalog: tuple[BaselineCall, ...], *, ticker: str) -> list[BaselineCall]:
    """Substitute the {ticker} placeholder in args."""
    out: list[BaselineCall] = []
    for c in catalog:
        args = {k: (v.replace("{ticker}", ticker) if isinstance(v, str) else v) for k, v in c.args.items()}
        out.append(BaselineCall(provider=c.provider, tool=c.tool, args=args))
    return out


async def run_baseline(
    *,
    catalog: list[BaselineCall],
    dispatcher: ToolDispatcher,
) -> Manifest:
    """Dispatch every baseline call in parallel. Failed calls are skipped (telemetry handles it)."""

    async def _one(call: BaselineCall) -> tuple[BaselineCall, Any]:
        try:
            result = await dispatcher.dispatch(call.provider, call.tool, call.args)
            return call, result
        except Exception:
            return call, None

    results = await asyncio.gather(*(_one(c) for c in catalog))
    manifest = Manifest()
    now = datetime.now(timezone.utc).isoformat()
    for call, payload in results:
        if payload is None:
            continue
        manifest.append(
            kind="fetch",
            provider=call.provider,
            identifier=call.identifier(),
            raw_payload=payload,
            retrieved_at=now,
        )
    return manifest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_baseline.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/manifest/baseline.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_baseline.py
git commit -m "feat(report_v2/manifest): W1 baseline fetch catalog for stock_initiation"
```

### Task 2.3: W2 pre-flight schema and call

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/manifest/preflight.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_preflight.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_preflight.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.manifest.preflight import (
    PreflightDeclaration,
    PreflightFetch,
    PreflightSearch,
    run_section_preflight,
)


def _empty_manifest() -> Manifest:
    return Manifest()


@pytest.mark.asyncio
async def test_preflight_returns_structured_declaration() -> None:
    provider = AsyncMock()
    provider.structured_output.return_value = {
        "searches": [{"query": "cloudflare edge market share 2025", "intent": "TAM context"}],
        "fetches": [],
        "proposed_facts": ["edge_platform_tam"],
    }
    decl = await run_section_preflight(
        provider=provider,
        section_id="industry_overview",
        section_brief="Frame the edge / CDN industry.",
        manifest=_empty_manifest(),
        known_fact_names=["market_cap", "sector"],
    )
    assert isinstance(decl, PreflightDeclaration)
    assert decl.section_id == "industry_overview"
    assert decl.searches[0].query == "cloudflare edge market share 2025"
    assert decl.proposed_facts == ["edge_platform_tam"]


@pytest.mark.asyncio
async def test_preflight_provider_called_with_section_brief_and_existing_manifest() -> None:
    provider = AsyncMock()
    provider.structured_output.return_value = {"searches": [], "fetches": [], "proposed_facts": []}
    manifest = _empty_manifest()
    manifest.append(
        kind="fetch", provider="eodhd",
        identifier="get_fundamentals_data/NET.US",
        raw_payload={}, retrieved_at="2026-05-17T20:00:00Z",
    )
    await run_section_preflight(
        provider=provider,
        section_id="financial_analysis",
        section_brief="Analyze 5y financials.",
        manifest=manifest,
        known_fact_names=["revenue_annual", "market_cap"],
    )
    call_kwargs = provider.structured_output.await_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "financial_analysis" in prompt
    assert "Analyze 5y financials" in prompt
    assert "[1] eodhd/get_fundamentals_data/NET.US" in prompt
    assert "revenue_annual" in prompt  # known facts listed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_preflight.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/manifest/preflight.py
"""W2: per-section pre-flight call.

A tiny structured-output call per section. Declares searches + fetches + proposed_facts.
No facts are added at runtime; proposed_facts is telemetry-only.
"""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflightSearch(_Strict):
    query: str
    intent: str


class PreflightFetch(_Strict):
    provider: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class PreflightDeclaration(_Strict):
    section_id: str
    searches: list[PreflightSearch] = Field(default_factory=list)
    fetches: list[PreflightFetch] = Field(default_factory=list)
    proposed_facts: list[str] = Field(default_factory=list)


PREFLIGHT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["searches", "fetches", "proposed_facts"],
    "properties": {
        "searches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query", "intent"],
                "properties": {
                    "query": {"type": "string"},
                    "intent": {"type": "string"},
                },
            },
        },
        "fetches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["provider", "tool", "args"],
                "properties": {
                    "provider": {"type": "string"},
                    "tool": {"type": "string"},
                    "args": {"type": "object"},
                },
            },
        },
        "proposed_facts": {"type": "array", "items": {"type": "string"}},
    },
}


class StructuredOutputProvider(Protocol):
    async def structured_output(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


_PROMPT_TEMPLATE = """You are the pre-flight planner for section {section_id}.

SECTION BRIEF:
{section_brief}

ALREADY-FETCHED MANIFEST:
{manifest_list}

REGISTERED FACT NAMES YOU CAN ASSUME ARE COMPUTED:
{known_facts}

Declare what additional data you need to write this section well.
Output JSON with three fields:
- searches: web search queries (with brief intent labels)
- fetches: structured tool calls (provider, tool, args)
- proposed_facts: NEW fact names you think should exist but aren't in the registered list above.
  These are telemetry-only — they will NOT be added at runtime. Use this to signal gaps.

Be specific. Do not declare data you already have."""


async def run_section_preflight(
    *,
    provider: StructuredOutputProvider,
    section_id: str,
    section_brief: str,
    manifest: Manifest,
    known_fact_names: list[str],
) -> PreflightDeclaration:
    prompt = _PROMPT_TEMPLATE.format(
        section_id=section_id,
        section_brief=section_brief,
        manifest_list=manifest.as_prompt_list() or "(empty)",
        known_facts="\n".join(f"- {n}" for n in sorted(known_fact_names)),
    )
    raw = await provider.structured_output(prompt=prompt, schema=PREFLIGHT_OUTPUT_SCHEMA)
    return PreflightDeclaration.model_validate({"section_id": section_id, **raw})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_preflight.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/manifest/preflight.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_preflight.py
git commit -m "feat(report_v2/manifest): W2 per-section pre-flight call"
```

### Task 2.4: W2 aggregator + central executor

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/manifest/aggregator.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_aggregator.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_aggregator.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.report_v2.manifest.aggregator import (
    AggregatedWork,
    aggregate_declarations,
    execute_aggregated,
)
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.manifest.preflight import (
    PreflightDeclaration,
    PreflightFetch,
    PreflightSearch,
)


def test_aggregate_dedupes_identical_searches() -> None:
    decls = [
        PreflightDeclaration(section_id="a", searches=[PreflightSearch(query="edge market 2025", intent="x")], fetches=[]),
        PreflightDeclaration(section_id="b", searches=[PreflightSearch(query="edge market 2025", intent="y")], fetches=[]),
    ]
    agg = aggregate_declarations(decls)
    assert len(agg.searches) == 1
    assert {"a", "b"} == set(agg.search_intents["edge market 2025"])


def test_aggregate_dedupes_identical_fetches_by_provider_tool_args() -> None:
    decls = [
        PreflightDeclaration(section_id="a", fetches=[PreflightFetch(provider="eodhd", tool="get_x", args={"ticker": "NET.US"})]),
        PreflightDeclaration(section_id="b", fetches=[PreflightFetch(provider="eodhd", tool="get_x", args={"ticker": "NET.US"})]),
        PreflightDeclaration(section_id="c", fetches=[PreflightFetch(provider="eodhd", tool="get_x", args={"ticker": "AAPL.US"})]),
    ]
    agg = aggregate_declarations(decls)
    assert len(agg.fetches) == 2


def test_proposed_facts_collected_per_section_for_telemetry() -> None:
    decls = [
        PreflightDeclaration(section_id="industry_overview", proposed_facts=["edge_tam"]),
        PreflightDeclaration(section_id="competitive_analysis", proposed_facts=["edge_tam", "peer_revenue_growth"]),
    ]
    agg = aggregate_declarations(decls)
    assert agg.proposed_facts["industry_overview"] == ["edge_tam"]
    assert set(agg.proposed_facts["competitive_analysis"]) == {"edge_tam", "peer_revenue_growth"}


@pytest.mark.asyncio
async def test_execute_aggregated_dispatches_and_extends_manifest() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: {"r": f"{tool}-{args}"}
    websearch = AsyncMock()
    websearch.search.side_effect = lambda query: [{"title": f"hit for {query}", "url": "https://x"}]

    agg = AggregatedWork(
        searches=["edge market 2025"],
        search_intents={"edge market 2025": ["a"]},
        fetches=[("eodhd", "get_x", {"ticker": "NET.US"})],
        proposed_facts={},
    )
    manifest = Manifest()
    manifest.append(kind="fetch", provider="eodhd", identifier="baseline/x", raw_payload={}, retrieved_at="t")
    await execute_aggregated(work=agg, manifest=manifest, dispatcher=dispatcher, websearch=websearch)
    assert len(manifest) == 3  # 1 baseline + 1 fetch + 1 search
    identifiers = [e.identifier for e in manifest.entries]
    assert "get_x/NET.US" in identifiers
    assert "edge market 2025" in identifiers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_aggregator.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/manifest/aggregator.py
"""W2 aggregator: dedupe pre-flight declarations across sections, then execute centrally."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from openlia.llm.runtime.report_v2.manifest.baseline import ToolDispatcher
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.manifest.preflight import PreflightDeclaration


class WebSearchProvider(Protocol):
    async def search(self, query: str) -> list[dict[str, Any]]: ...


@dataclass
class AggregatedWork:
    searches: list[str]
    search_intents: dict[str, list[str]]   # query -> [section_ids that asked]
    fetches: list[tuple[str, str, dict[str, Any]]]  # (provider, tool, args)
    proposed_facts: dict[str, list[str]]   # section_id -> [fact_names]


def _fetch_key(provider: str, tool: str, args: dict[str, Any]) -> str:
    import json
    return f"{provider}::{tool}::{json.dumps(args, sort_keys=True)}"


def aggregate_declarations(declarations: list[PreflightDeclaration]) -> AggregatedWork:
    searches: dict[str, list[str]] = {}
    fetches_keyed: dict[str, tuple[str, str, dict[str, Any]]] = {}
    proposed: dict[str, list[str]] = {}

    for d in declarations:
        for s in d.searches:
            searches.setdefault(s.query, []).append(d.section_id)
        for f in d.fetches:
            key = _fetch_key(f.provider, f.tool, f.args)
            fetches_keyed.setdefault(key, (f.provider, f.tool, f.args))
        if d.proposed_facts:
            proposed[d.section_id] = list(d.proposed_facts)

    return AggregatedWork(
        searches=list(searches.keys()),
        search_intents=searches,
        fetches=list(fetches_keyed.values()),
        proposed_facts=proposed,
    )


async def execute_aggregated(
    *,
    work: AggregatedWork,
    manifest: Manifest,
    dispatcher: ToolDispatcher,
    websearch: WebSearchProvider,
) -> Manifest:
    now = datetime.now(timezone.utc).isoformat()

    async def _do_fetch(provider: str, tool: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any], Any]:
        try:
            payload = await dispatcher.dispatch(provider, tool, args)
        except Exception:
            payload = None
        return provider, tool, args, payload

    async def _do_search(query: str) -> tuple[str, Any]:
        try:
            results = await websearch.search(query)
        except Exception:
            results = None
        return query, results

    fetch_tasks = [_do_fetch(p, t, a) for (p, t, a) in work.fetches]
    search_tasks = [_do_search(q) for q in work.searches]
    fetch_results = await asyncio.gather(*fetch_tasks) if fetch_tasks else []
    search_results = await asyncio.gather(*search_tasks) if search_tasks else []

    for provider, tool, args, payload in fetch_results:
        if payload is None:
            continue
        ticker_part = args.get("ticker") or args.get("query") or ""
        identifier = f"{tool}/{ticker_part}" if ticker_part else tool
        manifest.append(kind="fetch", provider=provider, identifier=identifier,
                        raw_payload=payload, retrieved_at=now)
    for query, results in search_results:
        if results is None:
            continue
        manifest.append(kind="search", provider="websearch", identifier=query,
                        raw_payload=results, retrieved_at=now)
    return manifest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_aggregator.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/manifest/aggregator.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_aggregator.py
git commit -m "feat(report_v2/manifest): W2 aggregator + central executor"
```

### Phase 2 acceptance

- All manifest tests green: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/ -v`
- Lint clean.
- Manifest module supports W1 baseline + W2 pre-flight + central dedup execution end-to-end (with mocked providers).

---

## Phase 3: Packer

The packer parses each section's Markdown file into structured pieces, runs semantic validation, applies soft fixes, and assembles the final `ReportSchema`. The block catalog maps 1:1 to the existing `ReportSchema` block types — no new block design.

### Task 3.1: Section file parser

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/parser.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_parser.py`

A section file looks like:

```markdown
---
section_id: industry_overview
title: Industry Overview
sources_used: [1, 3, 7]
synthesis_hooks: {thesis_contribution: "...", bull_case_inputs: ["..."], bear_case_inputs: ["..."]}
---

## Industry Overview

The edge platform market reached $24.6B in 2025 [12]...

```chart:combo
type: combo
title: TAM
series: [...]
sources: [12]
```

More prose...
```

The parser yields a `ParsedSection` with frontmatter, ordered "segments" (text or fenced block), and the raw `[N]` markers found in prose.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_parser.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment,
    ParsedSection,
    TextSegment,
    parse_section_file,
)


SECTION_FILE = '''---
section_id: industry_overview
title: Industry Overview
sources_used: [1, 3, 7]
word_count_target: 600
synthesis_hooks:
  thesis_contribution: "Edge platform TAM expanding 22% CAGR."
  bull_case_inputs:
    - "Edge compute market 28% CAGR through 2028 [12]"
  bear_case_inputs:
    - "Hyperscalers compressing CDN margins [3]"
---

## Industry Overview

The edge market reached $24.6B in 2025 [12]. Cloudflare commands a meaningful share [3].

```chart:combo
type: combo
title: Edge TAM
series:
  - {name: "Market size ($B)", values: [10, 15, 24.6]}
sources: [12]
```

Continuing analysis [7].
'''


def test_parse_extracts_frontmatter() -> None:
    parsed = parse_section_file(SECTION_FILE)
    assert isinstance(parsed, ParsedSection)
    assert parsed.frontmatter["section_id"] == "industry_overview"
    assert parsed.frontmatter["title"] == "Industry Overview"
    assert parsed.frontmatter["sources_used"] == [1, 3, 7]
    assert parsed.frontmatter["synthesis_hooks"]["thesis_contribution"].startswith("Edge")


def test_parse_segments_preserve_reading_order() -> None:
    parsed = parse_section_file(SECTION_FILE)
    assert len(parsed.segments) == 3
    assert isinstance(parsed.segments[0], TextSegment)
    assert isinstance(parsed.segments[1], FencedBlockSegment)
    assert isinstance(parsed.segments[2], TextSegment)
    assert parsed.segments[1].block_type == "chart:combo"


def test_parse_extracts_citation_markers_from_text() -> None:
    parsed = parse_section_file(SECTION_FILE)
    text_markers = [m for s in parsed.segments if isinstance(s, TextSegment) for m in s.citation_ids]
    assert 12 in text_markers
    assert 3 in text_markers
    assert 7 in text_markers


def test_parse_fenced_block_yaml_decoded() -> None:
    parsed = parse_section_file(SECTION_FILE)
    chart = parsed.segments[1]
    assert isinstance(chart, FencedBlockSegment)
    assert chart.data["title"] == "Edge TAM"
    assert chart.data["series"][0]["values"] == [10, 15, 24.6]
    assert chart.data["sources"] == [12]


def test_parse_missing_frontmatter_raises() -> None:
    bad = "## Just a body\n\nNo frontmatter here."
    with pytest.raises(ValueError, match="frontmatter"):
        parse_section_file(bad)


def test_parse_malformed_fence_yaml_raises_with_block_index() -> None:
    bad = '''---
section_id: x
title: X
sources_used: []
---

## Body

```table
title: ok
columns: this is not valid yaml: [it has, a colon issue, in: structure
```
'''
    with pytest.raises(ValueError, match="block 0"):
        parse_section_file(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_parser.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the parser**

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/parser.py
"""Parse a section Markdown file into frontmatter + ordered segments."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_FENCE_RE = re.compile(r"^```([\w:]+)\n(.*?)\n```", re.DOTALL | re.MULTILINE)
_CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass
class TextSegment:
    text: str
    citation_ids: list[int] = field(default_factory=list)


@dataclass
class FencedBlockSegment:
    block_type: str
    data: dict[str, Any]


Segment = TextSegment | FencedBlockSegment


@dataclass
class ParsedSection:
    frontmatter: dict[str, Any]
    segments: list[Segment]


def parse_section_file(content: str) -> ParsedSection:
    fm_match = _FRONTMATTER_RE.match(content.lstrip())
    if not fm_match:
        raise ValueError("missing or malformed frontmatter")

    frontmatter = yaml.safe_load(fm_match.group(1)) or {}
    body = fm_match.group(2)

    segments: list[Segment] = []
    cursor = 0
    block_index = 0
    for m in _FENCE_RE.finditer(body):
        if m.start() > cursor:
            text = body[cursor:m.start()].strip()
            if text:
                segments.append(_text_segment(text))
        block_type = m.group(1)
        raw = m.group(2)
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"block {block_index} ({block_type}): malformed YAML: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"block {block_index} ({block_type}): YAML must be a mapping")
        segments.append(FencedBlockSegment(block_type=block_type, data=data))
        cursor = m.end()
        block_index += 1
    if cursor < len(body):
        tail = body[cursor:].strip()
        if tail:
            segments.append(_text_segment(tail))

    return ParsedSection(frontmatter=frontmatter, segments=segments)


def _text_segment(text: str) -> TextSegment:
    ids = [int(x) for x in _CITATION_RE.findall(text)]
    return TextSegment(text=text, citation_ids=ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_parser.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/parser.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_parser.py
git commit -m "feat(report_v2/packer): section file parser (frontmatter + segments)"
```

### Task 3.2: Block type registry

The block catalog maps a fenced-block tag (e.g. `chart:combo`) to:
1. The `ReportSchema` block class to instantiate.
2. A YAML-shape validator (Pydantic model with `extra="forbid"`).
3. An assembler function that builds the final block instance.

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/registry.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_block_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_block_registry.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.packer.blocks.registry import (
    BlockRegistry,
    register_block,
    default_block_registry,
)


def test_register_and_lookup() -> None:
    reg = BlockRegistry()

    def _assemble(data, manifest_resolver):
        return {"type": "x", "value": data["v"]}

    reg.register("x", assembler=_assemble, schema={"type": "object", "required": ["v"]})
    entry = reg.get("x")
    assert entry.assembler is _assemble


def test_unknown_block_returns_none() -> None:
    reg = BlockRegistry()
    assert reg.get("unknown") is None


def test_default_registry_has_text_table_chart_combo() -> None:
    from openlia.llm.runtime.report_v2.packer.blocks import text  # noqa: F401
    from openlia.llm.runtime.report_v2.packer.blocks import table  # noqa: F401
    from openlia.llm.runtime.report_v2.packer.blocks import chart_combo  # noqa: F401

    assert default_block_registry.get("text") is not None
    assert default_block_registry.get("table") is not None
    assert default_block_registry.get("chart:combo") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_block_registry.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the registry**

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/registry.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BlockEntry:
    tag: str
    assembler: Callable[..., Any]
    schema: dict[str, Any] | None = None


class BlockRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, BlockEntry] = {}

    def register(self, tag: str, *, assembler: Callable[..., Any], schema: dict[str, Any] | None = None) -> None:
        if tag in self._entries:
            raise ValueError(f"block tag {tag!r} already registered")
        self._entries[tag] = BlockEntry(tag=tag, assembler=assembler, schema=schema)

    def get(self, tag: str) -> BlockEntry | None:
        return self._entries.get(tag)

    def tags(self) -> list[str]:
        return list(self._entries.keys())


default_block_registry = BlockRegistry()


def register_block(tag: str, *, assembler: Callable[..., Any], schema: dict[str, Any] | None = None) -> None:
    default_block_registry.register(tag, assembler=assembler, schema=schema)
```

- [ ] **Step 4: Run test to verify it passes (registry only — block modules added in next tasks)**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_block_registry.py::test_register_and_lookup -v`
Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_block_registry.py::test_unknown_block_returns_none -v`
Expected: PASS (other test will pass after Tasks 3.3–3.5).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/registry.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_block_registry.py
git commit -m "feat(report_v2/packer): block type registry"
```

### Task 3.3: TextBlock and TableBlock assemblers

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/text.py`
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/table.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_text_table.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_text_table.py
from __future__ import annotations

from openlia.llm.runtime.report_v2.packer.blocks import text, table  # noqa: F401 trigger registration
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.reports.schema import TableBlock, TextBlock


def _resolver(citation_ids):
    return [f"c{i}" for i in citation_ids]


def test_text_assembler_produces_textblock_with_resolved_citations() -> None:
    entry = default_block_registry.get("text")
    block = entry.assembler(
        data={"markdown": "Edge platform reached $24.6B [12]."},
        citation_ids=[12],
        manifest_resolver=_resolver,
    )
    assert isinstance(block, TextBlock)
    assert block.markdown == "Edge platform reached $24.6B [12]."
    assert block.source_ids == ["c12"]


def test_table_assembler_builds_tableblock() -> None:
    entry = default_block_registry.get("table")
    data = {
        "title": "Revenue 5y",
        "columns": [{"key": "year", "label": "Year"}, {"key": "rev", "label": "Revenue ($B)"}],
        "rows": [
            {"cells": {"year": "2024", "rev": "1.67"}},
            {"cells": {"year": "2023", "rev": "1.30"}},
        ],
        "sources": [1],
    }
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, TableBlock)
    assert block.title == "Revenue 5y"
    assert len(block.rows) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_text_table.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the text block**

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/text.py
from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import TextBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TextBlock:
    return TextBlock(
        type="text",
        markdown=data["markdown"],
        source_ids=manifest_resolver(citation_ids),
    )


register_block("text", assembler=_assemble, schema={
    "type": "object",
    "required": ["markdown"],
    "properties": {"markdown": {"type": "string"}},
})
```

- [ ] **Step 4: Write the table block**

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/table.py
from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import TableBlock, TableHeader


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TableBlock:
    headers = [TableHeader(**h) for h in data["columns"]]
    sources = list(data.get("sources", []))
    return TableBlock(
        type="table",
        title=data.get("title"),
        columns=headers,
        rows=data["rows"],
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("table", assembler=_assemble, schema={
    "type": "object",
    "required": ["columns", "rows"],
})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_text_table.py -v`
Expected: PASS.

Also re-run block registry test:
Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_block_registry.py -v`
Expected: First two PASS; `test_default_registry_has_text_table_chart_combo` still FAILS on `chart:combo` (Task 3.4 fixes).

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/text.py packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/table.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_text_table.py
git commit -m "feat(report_v2/packer): text and table block assemblers"
```

### Task 3.4: Chart block assemblers (line, bar, area, pie, combo, candlestick, waterfall, scatter, heatmap, treemap)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/chart_line.py`
- Create: same pattern for `chart_bar.py`, `chart_area.py`, `chart_pie.py`, `chart_combo.py`, `chart_candlestick.py`, `chart_waterfall.py`, `chart_scatter.py`, `chart_heatmap.py`, `chart_treemap.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_charts.py`

- [ ] **Step 1: Write the failing test (one parametrized test per chart type)**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_charts.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.packer.blocks import (
    chart_line, chart_bar, chart_area, chart_pie, chart_combo,
    chart_candlestick, chart_waterfall, chart_scatter, chart_heatmap, chart_treemap,
)  # noqa: F401 trigger registration
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.reports.schema import (
    AreaChartBlock, BarChartBlock, CandlestickBlock, ComboChartBlock,
    HeatmapBlock, LineChartBlock, PieChartBlock, ScatterBlock,
    TreemapBlock, WaterfallBlock,
)


def _resolver(citation_ids):
    return [f"c{i}" for i in citation_ids]


CHART_CASES = [
    ("chart:line", LineChartBlock, {
        "title": "T", "x_axis": {"label": "Year"}, "y_axis": {"label": "Rev"},
        "series": [{"name": "Revenue", "values": [1, 2, 3]}],
        "labels": ["2022", "2023", "2024"],
    }),
    ("chart:bar", BarChartBlock, {
        "title": "T", "x_axis": {"label": "Year"}, "y_axis": {"label": "Rev"},
        "series": [{"name": "Revenue", "values": [1, 2, 3]}],
        "labels": ["2022", "2023", "2024"],
    }),
    ("chart:area", AreaChartBlock, {
        "title": "T", "x_axis": {"label": "Year"}, "y_axis": {"label": "Rev"},
        "series": [{"name": "Revenue", "values": [1, 2, 3]}],
        "labels": ["2022", "2023", "2024"],
    }),
    ("chart:pie", PieChartBlock, {
        "title": "T", "segments": [{"label": "A", "value": 60}, {"label": "B", "value": 40}],
    }),
    ("chart:combo", ComboChartBlock, {
        "title": "T", "x_axis": {"label": "Year"}, "y_axis_left": {"label": "Rev"},
        "y_axis_right": {"label": "Margin"},
        "series": [
            {"name": "Revenue", "kind": "bar", "values": [1, 2, 3]},
            {"name": "Margin", "kind": "line", "values": [0.1, 0.12, 0.13]},
        ],
        "labels": ["2022", "2023", "2024"],
    }),
]


@pytest.mark.parametrize("tag,cls,data", CHART_CASES)
def test_chart_assembler_returns_expected_class(tag, cls, data) -> None:
    data = {**data, "sources": [1]}
    entry = default_block_registry.get(tag)
    assert entry is not None, f"{tag} not registered"
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, cls)
    assert block.source_ids == ["c1"]
```

- [ ] **Step 2: Write each chart module**

For each chart type, the module shape is:

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/chart_line.py
from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import LineChartBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> LineChartBlock:
    sources = list(data.get("sources", []))
    payload = {k: v for k, v in data.items() if k != "sources"}
    return LineChartBlock(
        type="chart_line",
        **payload,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block("chart:line", assembler=_assemble)
```

Mirror this pattern for the other nine chart types. The `type` literal for each follows the existing schema discriminator (e.g. `chart_bar`, `chart_area`, `chart_pie`, `chart_combo`, `chart_candlestick`, `chart_waterfall`, `chart_scatter`, `chart_heatmap`, `chart_treemap`).

For `chart_combo`, the `series` items have a `kind` key that maps to the existing `ComboSeries.kind` literal — pass through unchanged.

For `chart_treemap`, recursive node handling — accept the YAML shape directly and let Pydantic's `TreemapNode.model_rebuild()` handle it.

- [ ] **Step 3: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_charts.py -v`
Expected: PASS for all 5 parametrized cases; extend coverage to the remaining 5 chart types by adding more parametrize entries before committing.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/chart_*.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_charts.py
git commit -m "feat(report_v2/packer): chart block assemblers (10 chart types)"
```

### Task 3.5: Remaining non-chart blocks

**Files:**
- Create: one module per block under `packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/`:
  - `metric_cards.py` (`metric_cards` tag → `MetricCardsBlock`)
  - `key_finding.py` (`key_finding` tag → `KeyFindingBlock`)
  - `rating_badge.py` (`rating_badge` tag → `RatingBadgeBlock`)
  - `pull_quote.py` (`pull_quote` tag → `PullQuoteBlock`)
  - `callout_grid.py` (`callout_grid` tag → `CalloutGridBlock`)
  - `timeline.py` (`timeline` tag → `TimelineBlock`)
  - `bullet_list.py` (`bullet_list` tag → `BulletListBlock`)
  - `comparison_split.py` (`comparison_split` tag → `ComparisonSplitBlock`)
  - `quote.py` (`quote` tag → `QuoteBlock`)
  - `group.py` (`group` tag → `GroupBlock` — recursive: assembles nested blocks via the same registry)
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_remaining.py`

- [ ] **Step 1: Write the parametrized failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_remaining.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.packer.blocks import (
    metric_cards, key_finding, rating_badge, pull_quote, callout_grid,
    timeline, bullet_list, comparison_split, quote, group,
)  # noqa: F401
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.reports.schema import (
    BulletListBlock, CalloutGridBlock, ComparisonSplitBlock, GroupBlock,
    KeyFindingBlock, MetricCardsBlock, PullQuoteBlock, QuoteBlock,
    RatingBadgeBlock, TimelineBlock,
)


def _resolver(citation_ids):
    return [f"c{i}" for i in citation_ids]


CASES = [
    ("metric_cards", MetricCardsBlock, {
        "metrics": [{"label": "MCap", "value": "$30.2B"}, {"label": "P/E", "value": "142x"}],
    }),
    ("key_finding", KeyFindingBlock, {
        "label": "Bull case",
        "headline": "Edge TAM expanding 22% CAGR",
        "summary": "The market is growing fast",
    }),
    ("rating_badge", RatingBadgeBlock, {
        "label": "Buy", "tone": "positive",
    }),
    ("pull_quote", PullQuoteBlock, {
        "quote": "Cloudflare is the future of edge.",
        "attribution": "John Analyst",
    }),
    ("callout_grid", CalloutGridBlock, {
        "items": [{"title": "A", "body": "alpha"}, {"title": "B", "body": "beta"}],
    }),
    ("timeline", TimelineBlock, {
        "events": [
            {"date": "2024-01-01", "title": "X", "body": "happened"},
        ],
    }),
    ("bullet_list", BulletListBlock, {
        "items": ["one", "two"],
    }),
    ("comparison_split", ComparisonSplitBlock, {
        "columns": [
            {"title": "Bull", "items": ["edge growth"]},
            {"title": "Bear", "items": ["AWS pressure"]},
        ],
    }),
    ("quote", QuoteBlock, {
        "body": "Long-form pull quote about the company.",
        "attribution": "CEO of NET",
    }),
]


@pytest.mark.parametrize("tag,cls,data", CASES)
def test_remaining_block_assembler(tag, cls, data) -> None:
    data = {**data, "sources": [1]}
    entry = default_block_registry.get(tag)
    assert entry is not None, f"{tag} not registered"
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, cls)


def test_group_recursively_assembles_nested_blocks() -> None:
    data = {
        "columns": 2,
        "blocks": [
            {"type": "text", "data": {"markdown": "left"}, "sources": [1]},
            {"type": "metric_cards", "data": {"metrics": [{"label": "A", "value": "1"}]}, "sources": [2]},
        ],
    }
    entry = default_block_registry.get("group")
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, GroupBlock)
    assert len(block.blocks) == 2
```

- [ ] **Step 2: Write each block module**

Each non-recursive block follows the text/table pattern: extract `sources` → resolve → pass remaining keys through to the Pydantic class. Use the schema's `type` literal for the discriminator.

For `group`, the nested `blocks` list contains items with `{type, data, sources}` shape. The group assembler walks each, looks up `type` in `default_block_registry`, calls its assembler, collects the results.

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/group.py
from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import (
    default_block_registry, register_block,
)
from openlia.reports.schema import GroupBlock


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> GroupBlock:
    child_blocks = []
    for item in data["blocks"]:
        entry = default_block_registry.get(item["type"])
        if entry is None:
            raise ValueError(f"unknown nested block type {item['type']!r}")
        child = entry.assembler(
            data=item["data"],
            citation_ids=item.get("sources", []),
            manifest_resolver=manifest_resolver,
        )
        child_blocks.append(child)
    return GroupBlock(type="group", columns=data["columns"], blocks=child_blocks)


register_block("group", assembler=_assemble)
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_remaining.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/blocks/ packages/core/tests/test_llm/test_runtime/test_report_v2/test_blocks_remaining.py
git commit -m "feat(report_v2/packer): remaining 10 block assemblers (metric_cards, key_finding, ..., group)"
```

### Task 3.6: Semantic validator (5A)

The five checks from the spec. Each check is a pure function returning a list of structured findings.

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/validator.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_validator.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_validator.py
from __future__ import annotations

from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment, ParsedSection, TextSegment,
)
from openlia.llm.runtime.report_v2.packer.validator import (
    ValidationFinding,
    cross_section_numeric_consistency,
    fetched_but_unused,
    quantitative_claim_near_citation,
    tombstone_regex,
    validate_section,
    word_count_minimum,
)


def _text(s: str, citation_ids=None) -> TextSegment:
    return TextSegment(text=s, citation_ids=citation_ids or [])


def _parsed(segments) -> ParsedSection:
    return ParsedSection(
        frontmatter={"section_id": "x", "title": "X", "sources_used": [], "word_count_target": 600},
        segments=list(segments),
    )


def test_word_count_minimum_passes_at_or_above_70pct() -> None:
    parsed = _parsed([_text(" ".join(["word"] * 420))])
    findings = word_count_minimum(parsed, target=600)
    assert findings == []


def test_word_count_minimum_flags_below_70pct() -> None:
    parsed = _parsed([_text(" ".join(["word"] * 300))])
    findings = word_count_minimum(parsed, target=600)
    assert len(findings) == 1
    assert findings[0].check == "word_count_minimum"
    assert "300" in findings[0].detail


def test_tombstone_regex_flags_no_data_available() -> None:
    parsed = _parsed([_text("The data is great but No Data Available for the rest.")])
    findings = tombstone_regex(parsed)
    assert len(findings) == 1
    assert findings[0].check == "tombstone_regex"


def test_tombstone_regex_silent_when_clean() -> None:
    parsed = _parsed([_text("All metrics shown above are sourced.")])
    findings = tombstone_regex(parsed)
    assert findings == []


def test_quantitative_claim_near_citation_flags_uncited_number() -> None:
    parsed = _parsed([_text("Revenue grew 23% in fiscal 2024.")])
    findings = quantitative_claim_near_citation(parsed)
    assert any(f.check == "quantitative_claim_near_citation" for f in findings)


def test_quantitative_claim_near_citation_silent_when_cited() -> None:
    parsed = _parsed([_text("Revenue grew 23% in fiscal 2024 [3].", citation_ids=[3])])
    findings = quantitative_claim_near_citation(parsed)
    assert findings == []


def test_fetched_but_unused_flags_facts_never_referenced_in_prose_or_blocks() -> None:
    parsed = _parsed([_text("The company exists.")])
    findings = fetched_but_unused(
        parsed,
        facts_slice={"market_cap": object(), "revenue_cagr_3y": object()},
    )
    # If we ever surface "market_cap" or "revenue_cagr_3y" as keywords in prose, this passes.
    # Here neither appears, so both flag.
    names = {f.detail.split(":")[1].strip() for f in findings}
    assert {"market_cap", "revenue_cagr_3y"}.issubset(names)


def test_cross_section_numeric_consistency_flags_mismatched_claims() -> None:
    sec_a = _parsed([_text("Revenue CAGR 3y of 23.4% over the period [1].", citation_ids=[1])])
    sec_a.frontmatter["section_id"] = "financial_analysis"
    sec_b = _parsed([_text("Revenue CAGR 3y of 24.7% across the projection [1].", citation_ids=[1])])
    sec_b.frontmatter["section_id"] = "valuation_analysis"

    findings = cross_section_numeric_consistency([sec_a, sec_b])
    assert any(f.check == "cross_section_numeric_consistency" for f in findings)


def test_validate_section_runs_all_five_checks() -> None:
    parsed = _parsed([_text("Tiny.")])
    findings = validate_section(parsed, facts_slice={}, target_word_count=600)
    checks = {f.check for f in findings}
    assert "word_count_minimum" in checks
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_validator.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the validator**

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/validator.py
"""Semantic validation (5A). Five enumerated checks."""
from __future__ import annotations

import re
from dataclasses import dataclass

from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment, ParsedSection, TextSegment,
)


@dataclass(frozen=True)
class ValidationFinding:
    check: str
    section_id: str
    detail: str
    severity: str = "error"   # "error" hard-fails; "warning" telemetry-only


_TOMBSTONE_RE = re.compile(
    r"\b(no data available|n/?a|tbd|data not provided|unable to determine|data unavailable)\b",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|bn|b|m|k|x|usd|\$)?\b", re.IGNORECASE)
_CITATION_RE = re.compile(r"\[(\d+)\]")

# Words considered "close enough" to a number for citation proximity.
_CITATION_PROXIMITY_TOKENS = 12


def _section_id(parsed: ParsedSection) -> str:
    return parsed.frontmatter.get("section_id", "?")


def _prose_text(parsed: ParsedSection) -> str:
    return " ".join(s.text for s in parsed.segments if isinstance(s, TextSegment))


def word_count_minimum(parsed: ParsedSection, *, target: int) -> list[ValidationFinding]:
    prose = _prose_text(parsed)
    n = len(prose.split())
    if n < int(target * 0.7):
        return [ValidationFinding(
            check="word_count_minimum",
            section_id=_section_id(parsed),
            detail=f"section word count {n} below 70% of target {target}",
        )]
    return []


def tombstone_regex(parsed: ParsedSection) -> list[ValidationFinding]:
    findings = []
    for seg in parsed.segments:
        if isinstance(seg, TextSegment) and _TOMBSTONE_RE.search(seg.text):
            findings.append(ValidationFinding(
                check="tombstone_regex",
                section_id=_section_id(parsed),
                detail="tombstone phrase in prose",
            ))
    return findings


def quantitative_claim_near_citation(parsed: ParsedSection) -> list[ValidationFinding]:
    findings = []
    for seg in parsed.segments:
        if not isinstance(seg, TextSegment):
            continue
        tokens = seg.text.split()
        for i, tok in enumerate(tokens):
            if not _NUMBER_RE.fullmatch(tok.strip(".,;:")):
                continue
            window_start = max(0, i - _CITATION_PROXIMITY_TOKENS)
            window_end = min(len(tokens), i + _CITATION_PROXIMITY_TOKENS + 1)
            window = " ".join(tokens[window_start:window_end])
            if not _CITATION_RE.search(window):
                findings.append(ValidationFinding(
                    check="quantitative_claim_near_citation",
                    section_id=_section_id(parsed),
                    detail=f"numeric claim {tok!r} without nearby citation",
                ))
                break  # one finding per text segment is enough
    return findings


def fetched_but_unused(parsed: ParsedSection, *, facts_slice: dict) -> list[ValidationFinding]:
    """Flag facts handed to the section that never appear in prose or block YAML.

    Crude check: the fact name (with underscores → spaces) must appear in prose or in any block's YAML dump.
    """
    import json
    prose = _prose_text(parsed).lower()
    block_dumps = " ".join(
        json.dumps(s.data).lower() for s in parsed.segments if isinstance(s, FencedBlockSegment)
    )
    haystack = prose + " " + block_dumps
    findings = []
    for name in facts_slice:
        needle = name.replace("_", " ").lower()
        if needle not in haystack and name.lower() not in haystack:
            findings.append(ValidationFinding(
                check="fetched_but_unused",
                section_id=_section_id(parsed),
                detail=f"fact in slice but not referenced: {name}",
                severity="warning",
            ))
    return findings


_NUMERIC_CLAIM_RE = re.compile(
    r"\b([\w\s-]{3,40}?)\s+of\s+(\d+(?:[.,]\d+)?\s*%?)",
    re.IGNORECASE,
)


def cross_section_numeric_consistency(sections: list[ParsedSection]) -> list[ValidationFinding]:
    """Extract <subject> of <number> claims across sections; flag mismatched values for same subject."""
    by_subject: dict[str, list[tuple[str, str]]] = {}
    for s in sections:
        sid = _section_id(s)
        for seg in s.segments:
            if not isinstance(seg, TextSegment):
                continue
            for m in _NUMERIC_CLAIM_RE.finditer(seg.text):
                subject = " ".join(m.group(1).lower().split())
                value = m.group(2).replace(" ", "").rstrip("%")
                by_subject.setdefault(subject, []).append((sid, value))

    findings = []
    for subject, entries in by_subject.items():
        seen_values = {v for _, v in entries}
        if len(seen_values) > 1:
            findings.append(ValidationFinding(
                check="cross_section_numeric_consistency",
                section_id=",".join(sid for sid, _ in entries),
                detail=f"subject {subject!r}: conflicting values {sorted(seen_values)}",
            ))
    return findings


def validate_section(
    parsed: ParsedSection,
    *,
    facts_slice: dict,
    target_word_count: int,
) -> list[ValidationFinding]:
    return [
        *word_count_minimum(parsed, target=target_word_count),
        *tombstone_regex(parsed),
        *quantitative_claim_near_citation(parsed),
        *fetched_but_unused(parsed, facts_slice=facts_slice),
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_validator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/validator.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_validator.py
git commit -m "feat(report_v2/packer): 5A semantic validator (5 checks)"
```

### Task 3.7: Auto-repair

Soft fixes applied before declaring a hard fail. Examples:
- Fuzzy block-tag matching (`combo_chart` → `chart:combo`).
- Inline-citation tuple migration (legacy `(c1, c2)` → `[1] [2]`).
- Missing optional `sources` list → defaulted to `[]`.

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/auto_repair.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_auto_repair.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_auto_repair.py
from __future__ import annotations

from openlia.llm.runtime.report_v2.packer.auto_repair import (
    RepairOutcome,
    repair_section,
)


SECTION_WITH_BAD_TAG = '''---
section_id: x
title: X
sources_used: [1]
---

## Body

Some prose [1].

```combo_chart
title: T
series: [{name: a, values: [1,2,3]}]
```
'''


def test_repair_renames_known_tag_typos() -> None:
    outcome = repair_section(SECTION_WITH_BAD_TAG, known_tags=["chart:combo", "text", "table"])
    assert isinstance(outcome, RepairOutcome)
    assert "```chart:combo" in outcome.markdown
    assert "combo_chart" not in outcome.markdown
    assert outcome.fixes_applied == ["rename_block_tag: combo_chart -> chart:combo"]


def test_repair_leaves_unknown_tags_alone_and_records_warning() -> None:
    src = SECTION_WITH_BAD_TAG.replace("combo_chart", "definitely_not_a_block")
    outcome = repair_section(src, known_tags=["chart:combo", "text", "table"])
    assert "definitely_not_a_block" in outcome.markdown
    assert outcome.warnings != []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_auto_repair.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/auto_repair.py
"""Soft fixes applied before declaring a hard fail."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


@dataclass
class RepairOutcome:
    markdown: str
    fixes_applied: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_FENCE_TAG_RE = re.compile(r"^```([\w:]+)$", re.MULTILINE)


def repair_section(markdown: str, *, known_tags: list[str]) -> RepairOutcome:
    out = RepairOutcome(markdown=markdown)
    out = _rename_block_tags(out, known_tags=known_tags)
    return out


def _rename_block_tags(outcome: RepairOutcome, *, known_tags: list[str]) -> RepairOutcome:
    new_md = outcome.markdown
    known = set(known_tags)
    used = set(_FENCE_TAG_RE.findall(new_md))
    for tag in used:
        if tag in known:
            continue
        match = difflib.get_close_matches(tag, known_tags, n=1, cutoff=0.7)
        if match:
            new_md = re.sub(rf"^```{re.escape(tag)}$", f"```{match[0]}", new_md, flags=re.MULTILINE)
            outcome.fixes_applied.append(f"rename_block_tag: {tag} -> {match[0]}")
        else:
            outcome.warnings.append(f"unknown_block_tag: {tag}")
    outcome.markdown = new_md
    return outcome
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_auto_repair.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/auto_repair.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_auto_repair.py
git commit -m "feat(report_v2/packer): auto-repair soft fixes (fuzzy tag rename)"
```

### Task 3.8: Assembler (sections → ReportSchema, rigid-slot population from facts)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/packer/assembler.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_assembler.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_assembler.py
from __future__ import annotations

from datetime import datetime

from openlia.llm.runtime.report_v2.facts.pack import FactsPack
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.packer.blocks import text  # noqa: F401 trigger registration
from openlia.llm.runtime.report_v2.packer.assembler import assemble_report
from openlia.llm.runtime.report_v2.types import Fact, SectionResult, SectionTerminalState
from openlia.reports.schema import ReportSchema


_SECTION_FILE = '''---
section_id: company_overview
title: Company Overview
sources_used: [1]
synthesis_hooks:
  thesis_contribution: "Strong franchise"
  bull_case_inputs: []
  bear_case_inputs: []
---

## Company Overview

Cloudflare is a leading edge platform provider [1].
'''


def _manifest_with_fundamentals() -> Manifest:
    m = Manifest()
    m.append(
        kind="fetch", provider="eodhd",
        identifier="get_fundamentals_data/NET.US",
        raw_payload={"Highlights": {"MarketCapitalization": 30_200_000_000}},
        retrieved_at="2026-05-17T20:00:00Z",
    )
    return m


def _facts_pack_with_cover_metrics() -> FactsPack:
    return FactsPack(facts={
        "company_name": Fact(name="company_name", value="Cloudflare, Inc.", source_ids=[1], extractor="deterministic"),
        "sector": Fact(name="sector", value="Technology", source_ids=[1], extractor="deterministic"),
        "market_cap": Fact(name="market_cap", value=30_200_000_000, source_ids=[1], extractor="deterministic"),
        "pe_ratio_ttm": Fact(name="pe_ratio_ttm", value=142.1, source_ids=[1], extractor="deterministic"),
    })


def test_assemble_produces_valid_reportschema() -> None:
    sections = [SectionResult(
        section_id="company_overview",
        state=SectionTerminalState.SUCCESS,
        attempts=1,
        markdown=_SECTION_FILE,
    )]
    schema = assemble_report(
        manifest=_manifest_with_fundamentals(),
        facts_pack=_facts_pack_with_cover_metrics(),
        sections=sections,
        department="equity_research",
        ticker="NET.US",
        generated_at=datetime(2026, 5, 17, 20, 0, 0),
    )
    assert isinstance(schema, ReportSchema)
    assert schema.cover.ticker == "NET.US"
    assert schema.cover.title == "Cloudflare, Inc."


def test_assemble_fills_cover_key_metrics_from_facts_pack() -> None:
    schema = assemble_report(
        manifest=_manifest_with_fundamentals(),
        facts_pack=_facts_pack_with_cover_metrics(),
        sections=[SectionResult(
            section_id="company_overview", state=SectionTerminalState.SUCCESS,
            attempts=1, markdown=_SECTION_FILE,
        )],
        department="equity_research",
        ticker="NET.US",
        generated_at=datetime(2026, 5, 17, 20, 0, 0),
    )
    labels = {m.label for m in schema.cover.key_metrics}
    assert "Market Cap" in labels
    assert "P/E (TTM)" in labels
    # Verify it was packer-filled, not writer-emitted — value precisely matches facts pack
    mc = next(m for m in schema.cover.key_metrics if m.label == "Market Cap")
    assert "30.2" in mc.value


def test_assemble_citations_built_from_manifest() -> None:
    schema = assemble_report(
        manifest=_manifest_with_fundamentals(),
        facts_pack=_facts_pack_with_cover_metrics(),
        sections=[SectionResult(
            section_id="company_overview", state=SectionTerminalState.SUCCESS,
            attempts=1, markdown=_SECTION_FILE,
        )],
        department="equity_research",
        ticker="NET.US",
        generated_at=datetime(2026, 5, 17, 20, 0, 0),
    )
    assert len(schema.citations) == 1
    assert schema.citations[0].id == "c1"
    assert "fundamentals" in (schema.citations[0].title or "").lower() or schema.citations[0].source == "eodhd"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_assembler.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the assembler**

```python
# packages/core/src/openlia/llm/runtime/report_v2/packer/assembler.py
"""Assemble parsed section files + facts pack + manifest into a strict ReportSchema."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from openlia.llm.runtime.report_v2.facts.pack import FactsPack
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment, ParsedSection, TextSegment, parse_section_file,
)
from openlia.llm.runtime.report_v2.types import SectionResult, SectionTerminalState
from openlia.reports.schema import (
    Block, Citation, Cover, Metric, ReportSchema, Section,
)


def _resolve_marker_to_cid(manifest: Manifest):
    def resolver(citation_ids: list[int]) -> list[str]:
        return [f"c{m}" for m in citation_ids if 1 <= m <= len(manifest.entries)]
    return resolver


def _segment_to_block(seg, *, manifest_resolver) -> Block | None:
    if isinstance(seg, TextSegment):
        entry = default_block_registry.get("text")
        return entry.assembler(
            data={"markdown": seg.text},
            citation_ids=seg.citation_ids,
            manifest_resolver=manifest_resolver,
        )
    if isinstance(seg, FencedBlockSegment):
        entry = default_block_registry.get(seg.block_type)
        if entry is None:
            return None
        sources = seg.data.get("sources", [])
        return entry.assembler(
            data=seg.data,
            citation_ids=sources,
            manifest_resolver=manifest_resolver,
        )
    return None


def _format_market_cap(value: float) -> str:
    if value >= 1e12: return f"${value / 1e12:.2f}T"
    if value >= 1e9: return f"${value / 1e9:.1f}B"
    if value >= 1e6: return f"${value / 1e6:.0f}M"
    return f"${value:.0f}"


def _build_cover(facts_pack: FactsPack, *, ticker: str) -> Cover:
    name = facts_pack.facts.get("company_name")
    sector = facts_pack.facts.get("sector")
    mcap = facts_pack.facts.get("market_cap")
    pe = facts_pack.facts.get("pe_ratio_ttm")
    metrics: list[Metric] = []
    if mcap is not None:
        metrics.append(Metric(
            label="Market Cap", value=_format_market_cap(mcap.value),
            source_ids=[f"c{i}" for i in mcap.source_ids],
        ))
    if pe is not None and pe.value is not None:
        metrics.append(Metric(
            label="P/E (TTM)", value=f"{pe.value:.1f}x",
            source_ids=[f"c{i}" for i in pe.source_ids],
        ))
    return Cover(
        title=name.value if name else ticker,
        subtitle=sector.value if sector else "",
        ticker=ticker,
        tagline="Equity Research Initiation",
        tldr=[],
        key_metrics=metrics,
    )


def _build_citations(manifest: Manifest) -> list[Citation]:
    out = []
    for e in manifest.entries:
        title = e.identifier if e.kind == "fetch" else f"Search: {e.identifier}"
        out.append(Citation(id=f"c{e.id}", title=title, source=e.provider))
    return out


def assemble_report(
    *,
    manifest: Manifest,
    facts_pack: FactsPack,
    sections: list[SectionResult],
    department: str,
    ticker: str,
    generated_at: datetime,
) -> ReportSchema:
    resolver = _resolve_marker_to_cid(manifest)
    schema_sections: list[Section] = []
    for sec in sections:
        if sec.state == SectionTerminalState.EXHAUSTED or not sec.markdown:
            continue
        parsed = parse_section_file(sec.markdown)
        blocks = []
        for seg in parsed.segments:
            block = _segment_to_block(seg, manifest_resolver=resolver)
            if block is not None:
                blocks.append(block)
        schema_sections.append(Section(
            id=parsed.frontmatter["section_id"],
            title=parsed.frontmatter["title"],
            blocks=blocks,
        ))

    return ReportSchema(
        schema_version="2.0",
        department=department,
        generated_at=generated_at,
        cover=_build_cover(facts_pack, ticker=ticker),
        sections=schema_sections,
        citations=_build_citations(manifest),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_assembler.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/packer/assembler.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_assembler.py
git commit -m "feat(report_v2/packer): assembler — sections → ReportSchema with rigid-slot fill"
```

### Phase 3 acceptance

- All packer tests green: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/ -v`
- Lint clean.
- Packer parses Markdown section files, assembles into strict `ReportSchema`, fills cover.key_metrics directly from facts pack, runs all 5 semantic checks, and applies soft auto-repair fixes.

---

## Phase 4: Section dispatcher

### Task 4.1: Section prompt assembly (cache-ordered)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/sections/prompts.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_section_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_section_prompts.py
from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.pack import FactsPack
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.sections.prompts import (
    assemble_body_section_prompt,
    assemble_synthesis_section_prompt,
)
from openlia.llm.runtime.report_v2.types import Fact


def _facts_slice() -> dict:
    return {
        "market_cap": Fact(name="market_cap", value=30_200_000_000, source_ids=[1], extractor="deterministic"),
        "sector": Fact(name="sector", value="Technology", source_ids=[1], extractor="deterministic"),
    }


def _manifest() -> Manifest:
    m = Manifest()
    m.append(kind="fetch", provider="eodhd", identifier="get_fundamentals_data/NET.US",
             raw_payload={}, retrieved_at="t")
    m.append(kind="search", provider="websearch", identifier="edge market 2025",
             raw_payload=[], retrieved_at="t")
    return m


def test_body_prompt_orders_cached_prefix_before_dynamic() -> None:
    parts = assemble_body_section_prompt(
        system_role="You are a section writer.",
        style_guide="Use neutral institutional tone.",
        framework_brief="Section: industry_overview. Cover TAM, growth, key players.",
        manifest=_manifest(),
        facts_slice=_facts_slice(),
        word_target=600,
    )
    # Stable prefix (across runs) precedes variable prefix (manifest, facts).
    sys_idx = parts.find("You are a section writer")
    style_idx = parts.find("neutral institutional")
    brief_idx = parts.find("industry_overview")
    manifest_idx = parts.find("[1] eodhd")
    facts_idx = parts.find("market_cap")
    word_idx = parts.find("Word target")
    assert sys_idx < style_idx < brief_idx < manifest_idx < facts_idx < word_idx


def test_synthesis_prompt_includes_hooks_after_framework_brief() -> None:
    hooks_bundle = (
        "industry_overview:\n"
        "  thesis_contribution: Edge market expanding fast\n"
        "  bull_case_inputs: [Market 28% CAGR [12]]\n"
    )
    parts = assemble_synthesis_section_prompt(
        system_role="You are a synthesis writer.",
        style_guide="Sharpen the thesis.",
        framework_brief="Section: investment_recommendation.",
        manifest=_manifest(),
        synthesis_hooks_bundle=hooks_bundle,
        facts_slice=_facts_slice(),
        word_target=400,
    )
    fw_idx = parts.find("investment_recommendation")
    hooks_idx = parts.find("industry_overview:")
    assert fw_idx < hooks_idx


def test_facts_slice_renders_with_citation_tags() -> None:
    parts = assemble_body_section_prompt(
        system_role="x", style_guide="y", framework_brief="z",
        manifest=_manifest(), facts_slice=_facts_slice(), word_target=500,
    )
    assert "market_cap" in parts
    assert "sources: [1]" in parts or "[1]" in parts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_section_prompts.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/sections/prompts.py
"""Section prompt assembly. Cache-ordered: stable across runs → stable within run → per-section dynamic."""
from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.pack import FactsPack  # noqa: F401
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.types import Fact


def _format_facts_slice(facts_slice: dict[str, Fact]) -> str:
    lines = []
    for name, f in facts_slice.items():
        sources = ", ".join(str(s) for s in f.source_ids)
        lines.append(f"  {name}: {f.value!r} (sources: [{sources}])")
    return "\n".join(lines) if lines else "  (none)"


_OUTPUT_FORMAT_REMINDER = """Output format: Markdown file.
- YAML frontmatter with: section_id, title, sources_used (list of [N] manifest ids you cite), synthesis_hooks (only for body sections)
- Markdown body for prose; use [N] inline markers to cite manifest entries
- Typed fenced YAML blocks for structured exhibits: ```table, ```chart:combo, ```metric_cards, ```key_finding, ```bullet_list, ```comparison_split, ```quote, ```timeline, ```pull_quote, ```rating_badge, ```callout_grid, ```chart:line, ```chart:bar, ```chart:area, ```chart:pie, ```chart:candlestick, ```chart:waterfall, ```chart:scatter, ```chart:heatmap, ```chart:treemap, ```group
- Each block carries a `sources: [N, ...]` list of manifest ids
- Do not invent citations; only cite [N] markers that resolve to entries in the manifest above.
"""


def assemble_body_section_prompt(
    *,
    system_role: str,
    style_guide: str,
    framework_brief: str,
    manifest: Manifest,
    facts_slice: dict[str, Fact],
    word_target: int,
) -> str:
    return "\n\n".join([
        system_role,
        f"STYLE GUIDE:\n{style_guide}",
        f"FRAMEWORK SECTION BRIEF:\n{framework_brief}",
        f"MANIFEST (citable as [N]):\n{manifest.as_prompt_list()}",
        f"FACTS FOR THIS SECTION:\n{_format_facts_slice(facts_slice)}",
        f"Word target: {word_target}",
        _OUTPUT_FORMAT_REMINDER,
    ])


def assemble_synthesis_section_prompt(
    *,
    system_role: str,
    style_guide: str,
    framework_brief: str,
    manifest: Manifest,
    synthesis_hooks_bundle: str,
    facts_slice: dict[str, Fact],
    word_target: int,
) -> str:
    return "\n\n".join([
        system_role,
        f"STYLE GUIDE:\n{style_guide}",
        f"FRAMEWORK SECTION BRIEF:\n{framework_brief}",
        f"MANIFEST (citable as [N]):\n{manifest.as_prompt_list()}",
        f"SYNTHESIS HOOKS FROM BODY SECTIONS:\n{synthesis_hooks_bundle}",
        f"FACTS FOR THIS SECTION:\n{_format_facts_slice(facts_slice)}",
        f"Word target: {word_target}",
        _OUTPUT_FORMAT_REMINDER,
    ])
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_section_prompts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/sections/prompts.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_section_prompts.py
git commit -m "feat(report_v2/sections): cache-ordered prompt assembly (body + synthesis)"
```

### Task 4.2: Synthesis hooks bundle

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/sections/synthesis_hooks.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_synthesis_hooks.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_synthesis_hooks.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.sections.synthesis_hooks import (
    SynthesisHook,
    SynthesisHooksBundle,
    extract_hooks_from_section_result,
)
from openlia.llm.runtime.report_v2.types import SectionResult, SectionTerminalState


_SECTION_WITH_HOOKS = '''---
section_id: industry_overview
title: Industry Overview
sources_used: [1, 12]
synthesis_hooks:
  thesis_contribution: "Edge platform TAM expanding."
  bull_case_inputs:
    - "Market 28% CAGR [12]"
  bear_case_inputs:
    - "Hyperscalers compressing margins [3]"
---

## Body

Prose here.
'''


def test_extract_hooks_returns_typed_hook() -> None:
    result = SectionResult(
        section_id="industry_overview",
        state=SectionTerminalState.SUCCESS,
        attempts=1,
        markdown=_SECTION_WITH_HOOKS,
    )
    hook = extract_hooks_from_section_result(result)
    assert hook.section_id == "industry_overview"
    assert hook.thesis_contribution.startswith("Edge")
    assert hook.bull_case_inputs == ["Market 28% CAGR [12]"]
    assert hook.bear_case_inputs == ["Hyperscalers compressing margins [3]"]


def test_extract_hooks_missing_returns_none() -> None:
    result = SectionResult(
        section_id="x", state=SectionTerminalState.EXHAUSTED, attempts=2, markdown=None,
    )
    assert extract_hooks_from_section_result(result) is None


def test_bundle_renders_compact_for_synthesis_prompt() -> None:
    hooks = [
        SynthesisHook(
            section_id="industry_overview",
            thesis_contribution="Edge expanding",
            bull_case_inputs=["28% CAGR [12]"],
            bear_case_inputs=["Hyperscaler pressure [3]"],
        ),
        SynthesisHook(
            section_id="financial_analysis",
            thesis_contribution="Revenue growth strong",
            bull_case_inputs=["23% CAGR 3y [1]"],
            bear_case_inputs=[],
        ),
    ]
    bundle = SynthesisHooksBundle(hooks=hooks)
    rendered = bundle.render()
    assert "industry_overview:" in rendered
    assert "Edge expanding" in rendered
    assert "financial_analysis:" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_synthesis_hooks.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/sections/synthesis_hooks.py
from __future__ import annotations

from dataclasses import dataclass, field

from openlia.llm.runtime.report_v2.packer.parser import parse_section_file
from openlia.llm.runtime.report_v2.types import SectionResult


@dataclass
class SynthesisHook:
    section_id: str
    thesis_contribution: str
    bull_case_inputs: list[str] = field(default_factory=list)
    bear_case_inputs: list[str] = field(default_factory=list)


@dataclass
class SynthesisHooksBundle:
    hooks: list[SynthesisHook]

    def render(self) -> str:
        lines = []
        for h in self.hooks:
            lines.append(f"{h.section_id}:")
            lines.append(f"  thesis_contribution: {h.thesis_contribution}")
            lines.append(f"  bull_case_inputs: {h.bull_case_inputs}")
            lines.append(f"  bear_case_inputs: {h.bear_case_inputs}")
            lines.append("")
        return "\n".join(lines).strip()


def extract_hooks_from_section_result(result: SectionResult) -> SynthesisHook | None:
    if not result.markdown:
        return None
    parsed = parse_section_file(result.markdown)
    raw = parsed.frontmatter.get("synthesis_hooks")
    if not raw:
        return None
    return SynthesisHook(
        section_id=result.section_id,
        thesis_contribution=raw.get("thesis_contribution", ""),
        bull_case_inputs=list(raw.get("bull_case_inputs") or []),
        bear_case_inputs=list(raw.get("bear_case_inputs") or []),
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_synthesis_hooks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/sections/synthesis_hooks.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_synthesis_hooks.py
git commit -m "feat(report_v2/sections): synthesis hooks extraction + bundle rendering"
```

### Task 4.3: Section dispatcher (parallel write + retry + terminal state)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/sections/dispatcher.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_dispatcher.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.report_v2.packer.validator import ValidationFinding
from openlia.llm.runtime.report_v2.sections.dispatcher import (
    SectionDispatch,
    dispatch_sections,
)
from openlia.llm.runtime.report_v2.types import SectionTerminalState


GOOD_MD = '''---
section_id: company_overview
title: Company Overview
sources_used: [1]
---

## Company Overview

The company exists [1]. ''' + " ".join(["word"] * 500) + '''
'''

TINY_MD = '''---
section_id: company_overview
title: Company Overview
sources_used: [1]
---

## Body

Tiny.
'''


def _validator_factory(*, fail_on_attempt):
    calls = {"n": 0}

    def _validate(parsed, *, facts_slice, target_word_count):
        calls["n"] += 1
        if calls["n"] <= fail_on_attempt:
            return [ValidationFinding(check="word_count_minimum", section_id="x", detail="too short")]
        return []
    return _validate


@pytest.mark.asyncio
async def test_dispatch_single_section_success() -> None:
    writer = AsyncMock()
    writer.write.return_value = GOOD_MD
    dispatch = SectionDispatch(
        section_id="company_overview",
        prompt="...",
        target_word_count=600,
        facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch],
        writer=writer,
        validator=lambda p, **kw: [],
        max_retries=1,
        known_block_tags=["text", "table"],
    )
    assert len(results) == 1
    assert results[0].state == SectionTerminalState.SUCCESS
    assert results[0].attempts == 1


@pytest.mark.asyncio
async def test_dispatch_retries_with_structured_error_then_succeeds() -> None:
    writer = AsyncMock()
    writer.write.side_effect = [TINY_MD, GOOD_MD]
    validator = _validator_factory(fail_on_attempt=1)
    dispatch = SectionDispatch(
        section_id="company_overview", prompt="...", target_word_count=600, facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch], writer=writer, validator=validator,
        max_retries=1, known_block_tags=["text"],
    )
    assert results[0].state == SectionTerminalState.DEGRADED
    assert results[0].attempts == 2


@pytest.mark.asyncio
async def test_dispatch_exhaustion_returns_terminal_state() -> None:
    writer = AsyncMock()
    writer.write.return_value = TINY_MD
    validator = _validator_factory(fail_on_attempt=99)
    dispatch = SectionDispatch(
        section_id="company_overview", prompt="...", target_word_count=600, facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch], writer=writer, validator=validator,
        max_retries=1, known_block_tags=["text"],
    )
    assert results[0].state == SectionTerminalState.EXHAUSTED
    assert results[0].attempts == 2
    assert len(results[0].failed_attempts) == 2


@pytest.mark.asyncio
async def test_dispatch_runs_sections_in_parallel() -> None:
    writer = AsyncMock()
    writer.write.return_value = GOOD_MD
    dispatches = [
        SectionDispatch(section_id=f"s{i}", prompt="x", target_word_count=600, facts_slice={})
        for i in range(5)
    ]
    results = await dispatch_sections(
        dispatches=dispatches, writer=writer, validator=lambda p, **kw: [],
        max_retries=1, known_block_tags=["text"],
    )
    assert len(results) == 5
    assert writer.write.await_count == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_dispatcher.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/sections/dispatcher.py
"""Parallel section writer dispatch with per-section retry and terminal-state tracking."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from openlia.llm.runtime.report_v2.packer.auto_repair import repair_section
from openlia.llm.runtime.report_v2.packer.parser import parse_section_file
from openlia.llm.runtime.report_v2.packer.validator import ValidationFinding
from openlia.llm.runtime.report_v2.types import (
    Fact, SectionResult, SectionTerminalState,
)


class SectionWriter(Protocol):
    async def write(self, prompt: str) -> str: ...


@dataclass
class SectionDispatch:
    section_id: str
    prompt: str
    target_word_count: int
    facts_slice: dict[str, Fact]


def _format_errors(findings: list[ValidationFinding]) -> str:
    return "\n".join(f"- {f.check}: {f.detail}" for f in findings)


async def _dispatch_one(
    *,
    d: SectionDispatch,
    writer: SectionWriter,
    validator: Callable[..., list[ValidationFinding]],
    max_retries: int,
    known_block_tags: list[str],
) -> SectionResult:
    attempts = 0
    failed_attempts: list[str] = []
    last_errors: list[ValidationFinding] = []
    prompt = d.prompt

    while attempts <= max_retries:
        attempts += 1
        raw = await writer.write(prompt)
        repair = repair_section(raw, known_tags=known_block_tags)
        markdown = repair.markdown
        try:
            parsed = parse_section_file(markdown)
        except ValueError as e:
            last_errors = [ValidationFinding(check="parse_error", section_id=d.section_id, detail=str(e))]
            failed_attempts.append(raw)
            if attempts <= max_retries:
                prompt = f"{d.prompt}\n\nPREVIOUS ATTEMPT FAILED PARSE:\n{e}\n\nRe-emit the section."
                continue
            return SectionResult(
                section_id=d.section_id, state=SectionTerminalState.EXHAUSTED,
                attempts=attempts, failed_attempts=failed_attempts,
                validation_errors=[f.detail for f in last_errors],
            )

        errors = [f for f in validator(parsed, facts_slice=d.facts_slice, target_word_count=d.target_word_count) if f.severity == "error"]
        if not errors:
            state = SectionTerminalState.SUCCESS if attempts == 1 and not repair.fixes_applied else SectionTerminalState.DEGRADED
            return SectionResult(
                section_id=d.section_id, state=state, attempts=attempts,
                markdown=markdown, failed_attempts=failed_attempts,
                validation_errors=[],
            )

        failed_attempts.append(raw)
        last_errors = errors
        if attempts <= max_retries:
            prompt = (
                f"{d.prompt}\n\nYOUR PREVIOUS ATTEMPT FAILED VALIDATION:\n"
                f"{_format_errors(errors)}\n\nRe-emit the section. Address each error explicitly."
            )

    return SectionResult(
        section_id=d.section_id, state=SectionTerminalState.EXHAUSTED,
        attempts=attempts, failed_attempts=failed_attempts,
        validation_errors=[f.detail for f in last_errors],
    )


async def dispatch_sections(
    *,
    dispatches: list[SectionDispatch],
    writer: SectionWriter,
    validator: Callable[..., list[ValidationFinding]],
    max_retries: int,
    known_block_tags: list[str],
) -> list[SectionResult]:
    tasks = [
        _dispatch_one(
            d=d, writer=writer, validator=validator,
            max_retries=max_retries, known_block_tags=known_block_tags,
        )
        for d in dispatches
    ]
    return await asyncio.gather(*tasks)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_dispatcher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/sections/dispatcher.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_dispatcher.py
git commit -m "feat(report_v2/sections): parallel dispatch + per-section retry + terminal state"
```

### Phase 4 acceptance

- All dispatcher tests green: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/ -v`
- Lint clean.
- Section dispatcher runs N sections in parallel, retries with structured error context on validation fail, terminates in success/degraded/exhausted state.

---

## Phase 5: Runner orchestration

### Task 5.1: Telemetry hooks

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/telemetry.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_telemetry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_telemetry.py
from __future__ import annotations

from openlia.llm.runtime.report_v2.telemetry import ReportTelemetry, WaveTimings
from openlia.llm.runtime.report_v2.types import SectionResult, SectionTerminalState


def test_telemetry_records_section_outcomes() -> None:
    t = ReportTelemetry()
    t.record_section(SectionResult(section_id="a", state=SectionTerminalState.SUCCESS, attempts=1, markdown="..."))
    t.record_section(SectionResult(section_id="b", state=SectionTerminalState.DEGRADED, attempts=2, markdown="..."))
    t.record_section(SectionResult(section_id="c", state=SectionTerminalState.EXHAUSTED, attempts=2, failed_attempts=["x", "y"]))

    snap = t.snapshot()
    assert snap["section_states"]["success"] == 1
    assert snap["section_states"]["degraded"] == 1
    assert snap["section_states"]["exhausted"] == 1
    assert snap["sections"]["a"]["attempts"] == 1
    assert snap["sections"]["c"]["state"] == "exhausted"


def test_telemetry_records_proposed_facts_per_section() -> None:
    t = ReportTelemetry()
    t.record_proposed_facts("industry_overview", ["edge_tam"])
    t.record_proposed_facts("competitive_analysis", ["peer_revenue_growth", "edge_tam"])
    snap = t.snapshot()
    assert snap["proposed_facts"]["industry_overview"] == ["edge_tam"]
    assert "peer_revenue_growth" in snap["proposed_facts"]["competitive_analysis"]


def test_telemetry_records_wave_timings_in_ms() -> None:
    t = ReportTelemetry()
    t.record_wave("W1_baseline", duration_ms=320)
    t.record_wave("W4_body", duration_ms=42000)
    snap = t.snapshot()
    assert snap["wave_ms"]["W1_baseline"] == 320
    assert snap["wave_ms"]["W4_body"] == 42000


def test_telemetry_records_search_sentinels() -> None:
    t = ReportTelemetry()
    t.record_search_sentinel("industry_overview", "edge platform market share 2026")
    snap = t.snapshot()
    assert "industry_overview" in snap["search_sentinels"]
    assert "edge platform market share 2026" in snap["search_sentinels"]["industry_overview"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_telemetry.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/telemetry.py
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.types import SectionResult


@dataclass
class WaveTimings:
    durations_ms: dict[str, int] = field(default_factory=dict)


@dataclass
class ReportTelemetry:
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    section_states: Counter = field(default_factory=Counter)
    proposed_facts: dict[str, list[str]] = field(default_factory=dict)
    wave_timings: WaveTimings = field(default_factory=WaveTimings)
    search_sentinels: dict[str, list[str]] = field(default_factory=dict)
    auto_repair_fixes: Counter = field(default_factory=Counter)

    def record_section(self, result: SectionResult) -> None:
        self.sections[result.section_id] = {
            "state": result.state.value,
            "attempts": result.attempts,
            "validation_errors": list(result.validation_errors),
        }
        self.section_states[result.state.value] += 1

    def record_proposed_facts(self, section_id: str, fact_names: list[str]) -> None:
        if fact_names:
            self.proposed_facts.setdefault(section_id, []).extend(fact_names)

    def record_wave(self, wave_name: str, *, duration_ms: int) -> None:
        self.wave_timings.durations_ms[wave_name] = duration_ms

    def record_search_sentinel(self, section_id: str, query: str) -> None:
        self.search_sentinels.setdefault(section_id, []).append(query)

    def record_auto_repair(self, fix_label: str) -> None:
        self.auto_repair_fixes[fix_label] += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "sections": dict(self.sections),
            "section_states": dict(self.section_states),
            "proposed_facts": dict(self.proposed_facts),
            "wave_ms": dict(self.wave_timings.durations_ms),
            "search_sentinels": dict(self.search_sentinels),
            "auto_repair_fixes": dict(self.auto_repair_fixes),
        }
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_telemetry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/telemetry.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_telemetry.py
git commit -m "feat(report_v2/telemetry): per-wave timings, section states, proposed_facts"
```

### Task 5.2: WavedReportRunner (orchestrate all 6 waves)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/runner.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner.py`

The runner wires all six waves together with SSE emission and telemetry capture. The 11 body and 4 synthesis section ids are constants resolved per report type.

- [ ] **Step 1: Write the failing test (end-to-end with fully mocked providers)**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.packer.blocks import (  # noqa: F401
    text, table, chart_combo, metric_cards, key_finding, bullet_list,
    comparison_split, quote, group,
)
from openlia.llm.runtime.report_v2.runner import WavedReportRunner

FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "report_v2" / "eodhd_fundamentals_net.json"


def _good_section_md(section_id: str) -> str:
    body = " ".join(["word"] * 500) + " [1]."
    return f'''---
section_id: {section_id}
title: {section_id.replace("_", " ").title()}
sources_used: [1]
synthesis_hooks:
  thesis_contribution: "Strong thesis"
  bull_case_inputs: ["Growth case [1]"]
  bear_case_inputs: ["Risk case [1]"]
---

## {section_id}

{body}
'''


@pytest.mark.asyncio
async def test_runner_end_to_end_minimal() -> None:
    fundamentals = json.loads(FIXTURE.read_text())
    dispatcher = AsyncMock()
    dispatcher.dispatch.side_effect = lambda provider, tool, args: fundamentals if tool == "get_fundamentals_data" else {"ok": True}
    websearch = AsyncMock()
    websearch.search.return_value = []
    preflight_provider = AsyncMock()
    preflight_provider.structured_output.return_value = {"searches": [], "fetches": [], "proposed_facts": []}
    writer = AsyncMock()
    writer.write.side_effect = lambda prompt: _good_section_md(_extract_section_id(prompt))

    runner = WavedReportRunner(
        report_type="stock_initiation",
        ticker="NET.US",
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=writer,
        synthesis_writer=writer,
    )
    report = await runner.run()

    assert report.schema.cover.ticker == "NET.US"
    assert report.telemetry.snapshot()["section_states"]["success"] >= 11
    assert len(report.schema.sections) == 15  # 11 body + 4 synthesis


def _extract_section_id(prompt: str) -> str:
    for line in prompt.splitlines():
        if "Section:" in line:
            return line.split("Section:")[1].split(".")[0].strip().lower().replace(" ", "_")
    if "industry_overview" in prompt: return "industry_overview"
    return "company_overview"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the runner**

```python
# packages/core/src/openlia/llm/runtime/report_v2/runner.py
"""WavedReportRunner — orchestrates six waves end-to-end."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from typing import Any

from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import default_registry
from openlia.llm.runtime.report_v2.manifest.aggregator import (
    aggregate_declarations, execute_aggregated,
)
from openlia.llm.runtime.report_v2.manifest.baseline import (
    BASELINE_STOCK_INITIATION, materialize, run_baseline,
)
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.manifest.preflight import run_section_preflight
from openlia.llm.runtime.report_v2.packer.assembler import assemble_report
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.llm.runtime.report_v2.packer.validator import validate_section
from openlia.llm.runtime.report_v2.sections.dispatcher import (
    SectionDispatch, dispatch_sections,
)
from openlia.llm.runtime.report_v2.sections.prompts import (
    assemble_body_section_prompt, assemble_synthesis_section_prompt,
)
from openlia.llm.runtime.report_v2.sections.synthesis_hooks import (
    SynthesisHooksBundle, extract_hooks_from_section_result,
)
from openlia.llm.runtime.report_v2.telemetry import ReportTelemetry
from openlia.llm.runtime.report_v2.types import SectionResult
from openlia.reports.schema import ReportSchema


BODY_SECTIONS_STOCK_INITIATION = (
    "company_overview", "industry_overview", "products_and_services",
    "business_model", "management_team", "historical_financials",
    "financial_analysis", "financial_projections", "valuation_analysis",
    "competitive_analysis", "recent_developments",
)

SYNTHESIS_SECTIONS_STOCK_INITIATION = (
    "competitive_advantages_and_weaknesses",
    "risk_analysis",
    "investment_recommendation",
    "cover",
)

DEFAULT_WORD_TARGETS = {sid: 600 for sid in BODY_SECTIONS_STOCK_INITIATION} | {
    "competitive_advantages_and_weaknesses": 500,
    "risk_analysis": 500,
    "investment_recommendation": 400,
    "cover": 250,
}

DEFAULT_BRIEFS = {sid: f"Section: {sid}. Write a substantive analytical section." for sid in
                  (*BODY_SECTIONS_STOCK_INITIATION, *SYNTHESIS_SECTIONS_STOCK_INITIATION)}


@dataclass
class ReportRunOutput:
    schema: ReportSchema
    telemetry: ReportTelemetry


class WavedReportRunner:
    def __init__(
        self,
        *,
        report_type: str,
        ticker: str,
        dispatcher,
        websearch,
        preflight_provider,
        body_writer,
        synthesis_writer,
        system_role: str = "You are an equity research section writer.",
        style_guide: str = "Institutional tone, precise, cited.",
        max_retries: int = 1,
    ) -> None:
        assert report_type == "stock_initiation", "only stock_initiation supported in v1"
        self.report_type = report_type
        self.ticker = ticker
        self.dispatcher = dispatcher
        self.websearch = websearch
        self.preflight_provider = preflight_provider
        self.body_writer = body_writer
        self.synthesis_writer = synthesis_writer
        self.system_role = system_role
        self.style_guide = style_guide
        self.max_retries = max_retries
        self.telemetry = ReportTelemetry()

    def _load_facts_framework(self) -> dict[str, list[str]]:
        path = (
            resources.files("openlia.llm.runtime.report_v2.frameworks")
            / "stock_initiation.facts.json"
        )
        return json.loads(path.read_text())["sections"]

    async def run(self) -> ReportRunOutput:
        framework = self._load_facts_framework()

        # W1
        t0 = time.monotonic()
        manifest = await run_baseline(
            catalog=materialize(BASELINE_STOCK_INITIATION, ticker=self.ticker),
            dispatcher=self.dispatcher,
        )
        self.telemetry.record_wave("W1_baseline", duration_ms=int((time.monotonic() - t0) * 1000))

        all_sections = (*BODY_SECTIONS_STOCK_INITIATION, *SYNTHESIS_SECTIONS_STOCK_INITIATION)

        # W2
        t0 = time.monotonic()
        import asyncio
        known_facts = default_registry.names()
        preflights = await asyncio.gather(*(
            run_section_preflight(
                provider=self.preflight_provider,
                section_id=sid,
                section_brief=DEFAULT_BRIEFS[sid],
                manifest=manifest,
                known_fact_names=known_facts,
            )
            for sid in all_sections
        ))
        for d in preflights:
            if d.proposed_facts:
                self.telemetry.record_proposed_facts(d.section_id, d.proposed_facts)
        work = aggregate_declarations(preflights)
        await execute_aggregated(work=work, manifest=manifest,
                                  dispatcher=self.dispatcher, websearch=self.websearch)
        self.telemetry.record_wave("W2_preflight", duration_ms=int((time.monotonic() - t0) * 1000))

        # W3
        t0 = time.monotonic()
        requested = sorted({n for names in framework.values() for n in names})
        pack = compile_pack(registry=default_registry, manifest=manifest.entries, requested_facts=requested)
        self.telemetry.record_wave("W3_facts", duration_ms=int((time.monotonic() - t0) * 1000))

        # W4: body
        t0 = time.monotonic()
        body_dispatches = [
            SectionDispatch(
                section_id=sid,
                prompt=assemble_body_section_prompt(
                    system_role=self.system_role,
                    style_guide=self.style_guide,
                    framework_brief=DEFAULT_BRIEFS[sid],
                    manifest=manifest,
                    facts_slice=pack.slice_for(framework[sid]),
                    word_target=DEFAULT_WORD_TARGETS[sid],
                ),
                target_word_count=DEFAULT_WORD_TARGETS[sid],
                facts_slice=pack.slice_for(framework[sid]),
            )
            for sid in BODY_SECTIONS_STOCK_INITIATION
        ]
        body_results = await dispatch_sections(
            dispatches=body_dispatches, writer=self.body_writer, validator=validate_section,
            max_retries=self.max_retries, known_block_tags=default_block_registry.tags(),
        )
        for r in body_results:
            self.telemetry.record_section(r)
        self.telemetry.record_wave("W4_body", duration_ms=int((time.monotonic() - t0) * 1000))

        # W5: synthesis (gated on body terminal state — body_results are already terminal)
        t0 = time.monotonic()
        hooks = [h for h in (extract_hooks_from_section_result(r) for r in body_results) if h is not None]
        bundle = SynthesisHooksBundle(hooks=hooks).render()
        synth_dispatches = [
            SectionDispatch(
                section_id=sid,
                prompt=assemble_synthesis_section_prompt(
                    system_role=self.system_role,
                    style_guide=self.style_guide,
                    framework_brief=DEFAULT_BRIEFS[sid],
                    manifest=manifest,
                    synthesis_hooks_bundle=bundle,
                    facts_slice=pack.slice_for(framework[sid]),
                    word_target=DEFAULT_WORD_TARGETS[sid],
                ),
                target_word_count=DEFAULT_WORD_TARGETS[sid],
                facts_slice=pack.slice_for(framework[sid]),
            )
            for sid in SYNTHESIS_SECTIONS_STOCK_INITIATION
        ]
        synth_results = await dispatch_sections(
            dispatches=synth_dispatches, writer=self.synthesis_writer, validator=validate_section,
            max_retries=self.max_retries, known_block_tags=default_block_registry.tags(),
        )
        for r in synth_results:
            self.telemetry.record_section(r)
        self.telemetry.record_wave("W5_synthesis", duration_ms=int((time.monotonic() - t0) * 1000))

        # W6: pack
        t0 = time.monotonic()
        all_results = list(body_results) + list(synth_results)
        schema = assemble_report(
            manifest=manifest, facts_pack=pack, sections=all_results,
            department="equity_research", ticker=self.ticker,
            generated_at=datetime.now(timezone.utc),
        )
        self.telemetry.record_wave("W6_pack", duration_ms=int((time.monotonic() - t0) * 1000))

        return ReportRunOutput(schema=schema, telemetry=self.telemetry)
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/runner.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner.py
git commit -m "feat(report_v2/runner): WavedReportRunner — six-wave orchestration"
```

### Phase 5 acceptance

- Full runner test green with mocked providers: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner.py -v`
- All 60+ tests in `test_report_v2/` pass.
- Lint clean.

---

## Phase 6: Department wiring

### Task 6.1: Provider adapter for body and synthesis writers

The dispatcher expects a `writer.write(prompt) -> str` interface. Wire to the existing LLM provider abstraction.

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/writers.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_writers.py`

- [ ] **Step 1: Locate the existing provider abstraction**

Run: `grep -n "class.*LLMProvider\|class.*Provider" packages/core/src/openlia/llm/base.py packages/core/src/openlia/llm/types.py | head`
Expected: `LLMProvider` (or equivalent) abstract base.

- [ ] **Step 2: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_writers.py
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.report_v2.writers import (
    ProviderSectionWriter,
    ProviderStructuredOutput,
)


@pytest.mark.asyncio
async def test_provider_section_writer_calls_provider_chat_returns_text() -> None:
    provider = AsyncMock()
    provider.complete.return_value = "## section ..."
    writer = ProviderSectionWriter(provider=provider, model="claude-sonnet-4-6")
    out = await writer.write(prompt="hello")
    assert out == "## section ..."


@pytest.mark.asyncio
async def test_provider_structured_output_calls_provider_with_schema() -> None:
    provider = AsyncMock()
    provider.complete_json.return_value = {"searches": [], "fetches": [], "proposed_facts": []}
    so = ProviderStructuredOutput(provider=provider, model="claude-haiku-4-5-20251001")
    out = await so.structured_output(prompt="declare needs", schema={"type": "object"})
    assert out == {"searches": [], "fetches": [], "proposed_facts": []}
```

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/writers.py
"""Adapter classes connecting the dispatcher's SectionWriter / StructuredOutputProvider
protocols to the existing LLM provider abstraction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderSectionWriter:
    """Body / synthesis writer backed by an LLMProvider.

    Uses provider.complete(prompt, model) — text-only output, no tools.
    """
    provider: Any
    model: str

    async def write(self, prompt: str) -> str:
        return await self.provider.complete(prompt=prompt, model=self.model)


@dataclass
class ProviderStructuredOutput:
    """Pre-flight & LLM-tier fact extractor backed by an LLMProvider.

    Uses provider.complete_json(prompt, model, schema).
    """
    provider: Any
    model: str

    async def structured_output(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return await self.provider.complete_json(prompt=prompt, model=self.model, schema=schema)
```

If the existing provider's method names differ (e.g. `chat_completion`, `generate`), adjust the adapter calls to match. The interface seam is the adapter — keep the dispatcher and pre-flight protocol-agnostic.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_writers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/writers.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_writers.py
git commit -m "feat(report_v2/writers): provider-backed SectionWriter + StructuredOutput adapters"
```

### Task 6.2: Equity research department integration behind the feature flag

**Files:**
- Modify: `packages/core/src/openlia/departments/equity_research.py` (route to `WavedReportRunner` when `config.report_v2_enabled is True`)
- Test: `packages/core/tests/test_departments/test_equity_research_report_v2_routing.py`

- [ ] **Step 1: Read the existing department file**

Run: `grep -n "def generate_report\|ReportRunner\|SubagentReportRunner" packages/core/src/openlia/departments/equity_research.py`
Expected: A method (likely `generate_report` or `run_report`) that instantiates the runner.

- [ ] **Step 2: Write the failing test**

```python
# packages/core/tests/test_departments/test_equity_research_report_v2_routing.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_equity_research_uses_waved_runner_when_flag_on(monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_REPORT_V2_ENABLED", "true")
    from openlia.departments.equity_research import EquityResearchDepartment

    with patch("openlia.departments.equity_research.WavedReportRunner") as mock_runner_cls:
        instance = mock_runner_cls.return_value
        instance.run = AsyncMock()
        dept = EquityResearchDepartment(config=None, provider=AsyncMock(), data_provider=AsyncMock())
        await dept.generate_report(ticker="NET.US")
        mock_runner_cls.assert_called_once()


@pytest.mark.asyncio
async def test_equity_research_uses_legacy_runner_when_flag_off(monkeypatch) -> None:
    monkeypatch.delenv("OPENLIA_REPORT_V2_ENABLED", raising=False)
    from openlia.departments.equity_research import EquityResearchDepartment

    with patch("openlia.departments.equity_research.ReportRunner") as mock_classic, \
         patch("openlia.departments.equity_research.WavedReportRunner") as mock_waved:
        mock_classic.return_value.run = AsyncMock()
        dept = EquityResearchDepartment(config=None, provider=AsyncMock(), data_provider=AsyncMock())
        await dept.generate_report(ticker="NET.US")
        assert mock_classic.called
        assert not mock_waved.called
```

- [ ] **Step 3: Modify the department to dispatch based on the flag**

```python
# packages/core/src/openlia/departments/equity_research.py — sketch of the change
from openlia.config import load_config
from openlia.llm.runtime.report_v2.runner import WavedReportRunner
from openlia.llm.runtime.report_v2.writers import (
    ProviderSectionWriter, ProviderStructuredOutput,
)


class EquityResearchDepartment:
    ...

    async def generate_report(self, *, ticker: str, **kwargs):
        cfg = load_config()
        if cfg.report_v2_enabled:
            runner = WavedReportRunner(
                report_type="stock_initiation",
                ticker=ticker,
                dispatcher=self._tool_dispatcher,
                websearch=self._websearch_provider,
                preflight_provider=ProviderStructuredOutput(
                    provider=self.provider, model=cfg.report_v2_preflight_model or "claude-haiku-4-5-20251001",
                ),
                body_writer=ProviderSectionWriter(
                    provider=self.provider, model=cfg.report_v2_body_model or "claude-sonnet-4-6",
                ),
                synthesis_writer=ProviderSectionWriter(
                    provider=self.provider, model=cfg.report_v2_synthesis_model or "claude-sonnet-4-6",
                ),
            )
            return await runner.run()
        # legacy path:
        runner = ReportRunner(...)
        return await runner.run()
```

You will likely also need to extend `config.py` with `report_v2_body_model`, `report_v2_synthesis_model`, `report_v2_preflight_model` env-var-backed fields. Add them with sensible defaults (per the example above).

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_departments/test_equity_research_report_v2_routing.py -v`
Expected: PASS.

Also re-run the full department test suite to confirm nothing regressed:
Run: `uv run pytest packages/core/tests/test_departments/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/equity_research.py packages/core/src/openlia/config.py packages/core/tests/test_departments/test_equity_research_report_v2_routing.py
git commit -m "feat(equity_research): route to WavedReportRunner when report_v2_enabled"
```

### Task 6.3: SSE event emission from runner

The classic runner emits SSE events (`report.start`, `report.phase`, `report.section_complete`, `report.complete`, `report.error`). The waved runner must emit the same events so the frontend renders unchanged.

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` (accept an SSE emitter callback)
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner_sse.py`

- [ ] **Step 1: Locate the existing event types**

Run: `grep -n "class.*Event\|ReportStart\|ReportPhase\|ReportComplete" packages/core/src/openlia/llm/runtime/events.py`

- [ ] **Step 2: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner_sse.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from openlia.llm.runtime.events import ReportComplete, ReportPhase, ReportStart
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.packer.blocks import (  # noqa: F401
    text, table, chart_combo, metric_cards, key_finding, bullet_list,
    comparison_split, quote, group,
)
from openlia.llm.runtime.report_v2.runner import WavedReportRunner

FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "report_v2" / "eodhd_fundamentals_net.json"


def _good_md(sid: str) -> str:
    body = " ".join(["word"] * 500) + " [1]."
    return f"---\nsection_id: {sid}\ntitle: {sid}\nsources_used: [1]\nsynthesis_hooks:\n  thesis_contribution: t\n  bull_case_inputs: []\n  bear_case_inputs: []\n---\n\n## {sid}\n\n{body}\n"


@pytest.mark.asyncio
async def test_runner_emits_lifecycle_events_in_order() -> None:
    events = []

    async def emit(ev):
        events.append(ev)

    fundamentals = json.loads(FIXTURE.read_text())
    dispatcher = AsyncMock(); dispatcher.dispatch.return_value = fundamentals
    websearch = AsyncMock(); websearch.search.return_value = []
    preflight = AsyncMock(); preflight.structured_output.return_value = {"searches": [], "fetches": [], "proposed_facts": []}
    writer = AsyncMock(); writer.write.side_effect = lambda prompt: _good_md("company_overview")

    runner = WavedReportRunner(
        report_type="stock_initiation", ticker="NET.US",
        dispatcher=dispatcher, websearch=websearch, preflight_provider=preflight,
        body_writer=writer, synthesis_writer=writer, sse_emitter=emit,
    )
    await runner.run()
    kinds = [type(e).__name__ for e in events]
    assert kinds[0] == "ReportStart"
    assert kinds[-1] == "ReportComplete"
    phase_names = [e.phase for e in events if isinstance(e, ReportPhase)]
    assert "baseline" in phase_names
    assert "preflight" in phase_names
    assert "writing" in phase_names
    assert "synthesis" in phase_names
    assert "pack" in phase_names
```

- [ ] **Step 3: Extend the runner**

Add an `sse_emitter: Callable[[Any], Awaitable[None]] | None = None` parameter to `WavedReportRunner.__init__`. After each wave boundary, emit a `ReportPhase`. At the very start emit `ReportStart`. At the very end emit `ReportComplete`. Use the existing event classes from `openlia.llm.runtime.events`.

If a wave raises, catch and emit `ReportError`, then re-raise.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner_sse.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/runner.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_runner_sse.py
git commit -m "feat(report_v2/runner): SSE event emission across wave boundaries"
```

### Task 6.4: End-to-end smoke test against a live provider (manual)

This task is a manual checkpoint, not an automated test. Establish that the new runner produces a real report against a real provider on a real ticker.

- [ ] **Step 1: Verify env is configured**

```bash
echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" | head -c 20
echo "EODHD_API_TOKEN=$EODHD_API_TOKEN" | head -c 20
```

Both should be non-empty.

- [ ] **Step 2: Run a one-off smoke**

```bash
OPENLIA_REPORT_V2_ENABLED=true uv run python -m openlia.scripts.smoke_report_v2 --ticker NET.US --department equity_research
```

If `scripts/smoke_report_v2.py` doesn't exist, write a small ~30 line script that:
1. Loads config
2. Instantiates `EquityResearchDepartment` with real provider + data adapter
3. Calls `generate_report(ticker=...)`
4. Pretty-prints the resulting `ReportSchema` summary (section ids, citation count, cover key_metrics, telemetry snapshot)

- [ ] **Step 3: Inspect the output**

Confirm:
- 15 sections present (11 body + 4 synthesis)
- `cover.key_metrics` populated with actual values (no "No Data Available")
- citations array non-empty
- telemetry snapshot shows wave timings and any degraded/exhausted sections

- [ ] **Step 4: Commit any smoke script created**

```bash
git add packages/core/src/openlia/scripts/smoke_report_v2.py
git commit -m "chore(report_v2): smoke test script for live-provider validation"
```

### Phase 6 acceptance

- Feature flag routes between classic and waved runner.
- Manual smoke against `NET.US` produces a valid 15-section `ReportSchema` with populated `cover.key_metrics` and citations.
- All automated tests green.

---

## Phase 7: Structured diff + side-by-side validation

### Task 7.1: Structured diff utility

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2/diff.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_report_v2/test_diff.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_report_v2/test_diff.py
from __future__ import annotations

from datetime import datetime

from openlia.llm.runtime.report_v2.diff import diff_reports
from openlia.reports.schema import Citation, Cover, Metric, ReportSchema, Section, TextBlock


def _report(*, section_count: int, citation_count: int, market_cap_value: str) -> ReportSchema:
    return ReportSchema(
        schema_version="2.0",
        department="equity_research",
        generated_at=datetime(2026, 5, 17),
        cover=Cover(
            title="X", subtitle="Y", tagline="Z",
            key_metrics=[Metric(label="Market Cap", value=market_cap_value)],
        ),
        sections=[
            Section(
                id=f"s{i}", title=f"S{i}",
                blocks=[TextBlock(type="text", markdown=f"Body of s{i}.", source_ids=["c1"])],
            )
            for i in range(section_count)
        ],
        citations=[Citation(id=f"c{i+1}", title=f"Source {i+1}") for i in range(citation_count)],
    )


def test_diff_identical_reports_is_clean() -> None:
    a = _report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    b = _report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    d = diff_reports(a, b)
    assert d["section_count"]["match"] is True
    assert d["citation_count"]["match"] is True
    assert d["cover_metric_values"]["match"] is True


def test_diff_reports_section_count_mismatch_flagged() -> None:
    a = _report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    b = _report(section_count=14, citation_count=12, market_cap_value="$30.2B")
    d = diff_reports(a, b)
    assert d["section_count"]["match"] is False
    assert d["section_count"]["classic"] == 15
    assert d["section_count"]["waved"] == 14


def test_diff_reports_cover_metric_value_drift_flagged() -> None:
    a = _report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    b = _report(section_count=15, citation_count=12, market_cap_value="$32.0B")
    d = diff_reports(a, b)
    assert d["cover_metric_values"]["match"] is False
    assert "Market Cap" in d["cover_metric_values"]["mismatches"]


def test_diff_word_counts_within_tolerance_match_otherwise_flagged() -> None:
    a = _report(section_count=2, citation_count=2, market_cap_value="$30.2B")
    a.sections[0].blocks = [TextBlock(type="text", markdown=" ".join(["w"] * 500), source_ids=["c1"])]
    b = _report(section_count=2, citation_count=2, market_cap_value="$30.2B")
    b.sections[0].blocks = [TextBlock(type="text", markdown=" ".join(["w"] * 480), source_ids=["c1"])]  # within 20%
    d = diff_reports(a, b)
    assert d["section_word_counts"]["match"] is True

    b.sections[0].blocks = [TextBlock(type="text", markdown=" ".join(["w"] * 200), source_ids=["c1"])]  # outside 20%
    d = diff_reports(a, b)
    assert d["section_word_counts"]["match"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_diff.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/report_v2/diff.py
"""Structured diff between two ReportSchema instances (classic vs waved)."""
from __future__ import annotations

from typing import Any

from openlia.reports.schema import (
    BulletListBlock, ComparisonSplitBlock, KeyFindingBlock, PullQuoteBlock,
    QuoteBlock, ReportSchema, TextBlock,
)


_WORD_COUNT_TOLERANCE = 0.20


def _section_word_count(section) -> int:
    n = 0
    for b in section.blocks:
        if isinstance(b, TextBlock):
            n += len(b.markdown.split())
        elif isinstance(b, KeyFindingBlock):
            n += len((b.summary or "").split())
        elif isinstance(b, PullQuoteBlock):
            n += len(b.quote.split())
        elif isinstance(b, QuoteBlock):
            n += len(b.body.split())
        elif isinstance(b, BulletListBlock):
            for item in b.items:
                n += len(str(item).split())
        elif isinstance(b, ComparisonSplitBlock):
            for col in b.columns:
                for it in col.items:
                    n += len(str(it).split())
    return n


def _cover_metric_map(report: ReportSchema) -> dict[str, str]:
    return {m.label: m.value for m in report.cover.key_metrics}


def diff_reports(classic: ReportSchema, waved: ReportSchema) -> dict[str, Any]:
    out: dict[str, Any] = {}

    out["section_count"] = {
        "match": len(classic.sections) == len(waved.sections),
        "classic": len(classic.sections),
        "waved": len(waved.sections),
    }

    out["citation_count"] = {
        "match": len(classic.citations) == len(waved.citations),
        "classic": len(classic.citations),
        "waved": len(waved.citations),
    }

    cm_a, cm_b = _cover_metric_map(classic), _cover_metric_map(waved)
    mismatches = {k: (cm_a.get(k), cm_b.get(k)) for k in set(cm_a) | set(cm_b)
                  if cm_a.get(k) != cm_b.get(k)}
    out["cover_metric_values"] = {
        "match": not mismatches,
        "mismatches": mismatches,
    }

    wc_match = True
    wc_per_section: dict[str, dict[str, int]] = {}
    by_id_a = {s.id: s for s in classic.sections}
    by_id_b = {s.id: s for s in waved.sections}
    shared_ids = set(by_id_a) & set(by_id_b)
    for sid in shared_ids:
        wa = _section_word_count(by_id_a[sid])
        wb = _section_word_count(by_id_b[sid])
        wc_per_section[sid] = {"classic": wa, "waved": wb}
        if wa == 0 and wb == 0:
            continue
        denom = max(wa, wb)
        if abs(wa - wb) / denom > _WORD_COUNT_TOLERANCE:
            wc_match = False
    out["section_word_counts"] = {"match": wc_match, "per_section": wc_per_section}

    return out
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_report_v2/test_diff.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2/diff.py packages/core/tests/test_llm/test_runtime/test_report_v2/test_diff.py
git commit -m "feat(report_v2/diff): structured diff between classic and waved reports"
```

### Task 7.2: Side-by-side run script

**Files:**
- Create: `packages/core/src/openlia/scripts/side_by_side_report_diff.py`

This is a CLI script (no tests). It runs both runners on the same ticker, computes the diff, persists both outputs, and prints a summary.

- [ ] **Step 1: Write the script**

```python
# packages/core/src/openlia/scripts/side_by_side_report_diff.py
"""Run classic and waved runners side-by-side on the same ticker.

Usage: uv run python -m openlia.scripts.side_by_side_report_diff --ticker NET.US
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from openlia.departments.equity_research import EquityResearchDepartment
from openlia.llm.runtime.report_v2.diff import diff_reports


async def _run(ticker: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    os.environ["OPENLIA_REPORT_V2_ENABLED"] = "false"
    dept = EquityResearchDepartment._make_default()  # adjust to actual factory
    classic = await dept.generate_report(ticker=ticker)

    os.environ["OPENLIA_REPORT_V2_ENABLED"] = "true"
    dept2 = EquityResearchDepartment._make_default()
    waved_output = await dept2.generate_report(ticker=ticker)
    waved = waved_output.schema if hasattr(waved_output, "schema") else waved_output

    (out_dir / f"{ticker}_classic.json").write_text(classic.model_dump_json(indent=2))
    (out_dir / f"{ticker}_waved.json").write_text(waved.model_dump_json(indent=2))

    diff = diff_reports(classic, waved)
    (out_dir / f"{ticker}_diff.json").write_text(json.dumps(diff, indent=2, default=str))
    print(json.dumps(diff, indent=2, default=str))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--out", default="./report_diff_output")
    args = p.parse_args()
    asyncio.run(_run(ticker=args.ticker, out_dir=Path(args.out)))


if __name__ == "__main__":
    main()
```

`EquityResearchDepartment._make_default()` is illustrative — adapt to the actual factory or wiring you have for instantiating the department with real provider + data adapter. If none exists, refactor as part of this task.

- [ ] **Step 2: Run the script on a single ticker**

```bash
uv run python -m openlia.scripts.side_by_side_report_diff --ticker NET.US --out /tmp/report_diff_run1
```

Confirm:
- Two JSON files written
- Diff JSON written
- Summary printed to stdout

- [ ] **Step 3: Commit the script**

```bash
git add packages/core/src/openlia/scripts/side_by_side_report_diff.py
git commit -m "chore(report_v2): side-by-side runner diff script"
```

### Task 7.3: Run the diff across a smoke ticker set

This is a manual judgment checkpoint, not an automated test.

- [ ] **Step 1: Pick 3–5 tickers spanning sectors**

Suggested: `NET.US` (software), `MSFT.US` (mega-cap), `XOM.US` (energy), `JPM.US` (financials), `TSLA.US` (volatile).

- [ ] **Step 2: Run side-by-side on each**

```bash
for T in NET.US MSFT.US XOM.US JPM.US TSLA.US; do
  uv run python -m openlia.scripts.side_by_side_report_diff --ticker $T --out /tmp/diff_$T
done
```

- [ ] **Step 3: Inspect diffs**

For each ticker, verify:
- `section_count` matches (both runners produced 15 sections)
- `citation_count` is comparable (within ±20% — waved runner's manifest may differ slightly from classic's tool-call list)
- `cover_metric_values` matches in label set and values are within rounding tolerance
- `section_word_counts` are within ±20% per section

Document findings. If any class of mismatch repeats across tickers, file an issue against `feat/waved-report-runner` before defaulting the flag.

### Phase 7 acceptance

- Diff utility tests green.
- 3–5 ticker side-by-side runs complete with no class of mismatch repeating across tickers.
- Documented in a brief commit message or PR comment.

---

## Phase 8: Cutover + legacy deletion

### Task 8.1: Flip the default

**Implementation note (2026-05-18):** The flag is not in `config.py`; it
is read directly from the environment in
`packages/server/src/openlia_server/services/runtime.py` by
`select_report_runner_class`. The flip happens there.

**Files:**
- Modify: `packages/server/src/openlia_server/services/runtime.py`
- Modify: `packages/server/tests/test_services/test_runtime_v2_routing.py`
- Modify: `packages/server/tests/test_subagent_routing.py`

- [ ] **Step 1: Invert the env check**

In `select_report_runner_class`, change from opt-in (`== "true"`) to
opt-out: unset / empty / anything other than `{false,0,no,off}` selects
`WavedReportRunnerHost` for `equity_research`.

- [ ] **Step 2: Update tests**

- `test_runtime_v2_routing.py`: rename the no-flag case from
  `test_flag_off_equity_research_returns_report_runner` to
  `test_flag_unset_equity_research_defaults_to_waved` and assert
  `WavedReportRunnerHost`. The `=false` case keeps asserting
  `ReportRunner`.
- `test_subagent_routing.py`: the two tests that previously relied on
  v2 being off by default must now set
  `OPENLIA_REPORT_V2_ENABLED=false` explicitly.

- [ ] **Step 3: Run all tests**

Run: `uv run pytest packages/server/tests/`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/services/runtime.py \
        packages/server/tests/test_services/test_runtime_v2_routing.py \
        packages/server/tests/test_subagent_routing.py
git commit -m "feat(report_v2): flip default to on for equity_research"
```

Landed as commit `1704a37` on `fix/report-strictness`, 2026-05-18.

### Task 8.2: Stabilization window

This is a calendar checkpoint, not a code change. Wait 5–7 days after the previous commit lands on `main` and is exercised in production-equivalent traffic.

- [ ] **Step 1: Monitor telemetry**

Every day in the window, check:
- Per-section degradation rate (should be < 5% per section)
- Per-section exhaustion rate (should be < 1% per section)
- Wave latency P95 (W4 < 90s, W5 < 30s)
- Cost per report (should be ≤ classic baseline)

- [ ] **Step 2: If a regression appears**

Roll back the flag default (revert Task 8.1's commit), file a follow-up issue, do NOT proceed to deletion.

- [ ] **Step 3: If telemetry is stable**

Proceed to Task 8.3.

### Task 8.3: Delete legacy runners

**Files to delete:**
- `packages/core/src/openlia/llm/runtime/report.py`
- `packages/core/src/openlia/llm/runtime/subagent_runner.py`
- `packages/core/src/openlia/llm/runtime/subagent_client.py`
- `packages/core/src/openlia/llm/runtime/editor_client.py`
- `packages/core/src/openlia/llm/runtime/section_draft.py`
- `packages/core/src/openlia/llm/runtime/prior_section_summarizer.py`
- `packages/core/src/openlia/llm/runtime/plan_schema.py`
- `packages/core/src/openlia/prompts/shared/editor_role.yaml.j2`
- `packages/core/src/openlia/prompts/shared/section_subagent_role.yaml.j2`
- All associated test files under `packages/core/tests/test_llm/test_runtime/`

- [ ] **Step 1: Find every import of the doomed modules**

Run: `git grep -l "from openlia.llm.runtime.report import\|from openlia.llm.runtime import report\|from openlia.llm.runtime.subagent_runner\|from openlia.llm.runtime.subagent_client\|from openlia.llm.runtime.editor_client\|from openlia.llm.runtime.section_draft\|from openlia.llm.runtime.prior_section_summarizer\|from openlia.llm.runtime.plan_schema"`

Expected: A list of files. Each one needs either deletion or refactoring.

- [ ] **Step 2: Refactor or delete each importer**

In `equity_research.py`, remove the legacy `ReportRunner` import and the `if/else` branch — keep only the `WavedReportRunner` path. The feature flag check can be removed entirely (or kept as a kill switch for one more cycle).

- [ ] **Step 3: Delete the legacy files and their tests**

```bash
git rm packages/core/src/openlia/llm/runtime/report.py
git rm packages/core/src/openlia/llm/runtime/subagent_runner.py
git rm packages/core/src/openlia/llm/runtime/subagent_client.py
git rm packages/core/src/openlia/llm/runtime/editor_client.py
git rm packages/core/src/openlia/llm/runtime/section_draft.py
git rm packages/core/src/openlia/llm/runtime/prior_section_summarizer.py
git rm packages/core/src/openlia/llm/runtime/plan_schema.py
git rm packages/core/src/openlia/prompts/shared/editor_role.yaml.j2
git rm packages/core/src/openlia/prompts/shared/section_subagent_role.yaml.j2
# Also remove their test files:
git rm packages/core/tests/test_llm/test_runtime/test_report_*.py 2>/dev/null || true
git rm packages/core/tests/test_llm/test_runtime/test_subagent_*.py 2>/dev/null || true
git rm packages/core/tests/test_llm/test_runtime/test_editor_*.py 2>/dev/null || true
git rm packages/core/tests/test_llm/test_runtime/test_plan_schema.py 2>/dev/null || true
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest packages/core/tests/ -v`
Expected: PASS. Any failure indicates a leftover importer or a stale fixture.

- [ ] **Step 5: Lint clean**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(report_v2): delete classic + subagent runners post-cutover"
```

### Task 8.4: Optional flag removal

If you want to remove the `report_v2_enabled` flag entirely (it has no remaining branch to control):

- [ ] **Step 1: Remove the field from `config.py`** and its test.
- [ ] **Step 2: Remove the `cfg.report_v2_enabled` check from `equity_research.py`** (already removed in Task 8.3 most likely).
- [ ] **Step 3: Run tests and lint.**
- [ ] **Step 4: Commit.**

```bash
git add -A
git commit -m "chore(config): drop report_v2_enabled flag (no remaining branch)"
```

### Phase 8 acceptance

- Flag flipped on by default; stabilization window passed without rollback.
- Legacy runner modules and their tests deleted; codebase compiles and tests pass.
- (Optional) Feature flag removed entirely.

---

## Self-review

This is the planner's checklist run against the spec after the plan is complete.

### Spec coverage

| Spec section | Tasks that implement it |
|---|---|
| Wave architecture overview | Phase 5 (runner.py orchestrates W1–W6) |
| W1 baseline fetch | Tasks 2.1, 2.2 |
| W2 per-section pre-flight | Task 2.3 |
| W2 aggregator + central executor | Task 2.4 |
| W3 facts compile (registry, 3 tiers, DAG) | Tasks 1.1–1.5, 1.6 (framework facts JSON) |
| W4 body write (parallel) | Task 4.3 (dispatcher), Task 5.2 (runner wiring) |
| W5 synthesis write (gated on body terminal state) | Task 5.2 (runner uses body_results which are terminal before synthesis dispatches) |
| W6 pack (parser, validator, auto-repair, assembler) | Tasks 3.1–3.8 |
| Per-section retry (1 retry, structured error) | Task 4.3 |
| Section terminal state (success/degraded/exhausted) | Tasks 0.2, 4.3 |
| Cache-ordered prompt assembly | Task 4.1 |
| `synthesis_hooks` contract | Task 4.2 |
| Citation provenance union | Tasks 1.4 (union helper) + 1.5 (LLM extractor inherits) |
| Rigid schema slots filled by packer from facts pack | Task 3.8 |
| Telemetry (sentinels, proposed_facts, latency, repair counts) | Task 5.1 |
| SSE event emission | Task 6.3 |
| Migration: structured diff | Tasks 7.1, 7.2 |
| Cutover + legacy deletion | Tasks 8.1, 8.3 |

### Placeholder scan

No "TBD" / "TODO" / "implement later" / "fill in details" appear in any task body. Each step that writes code shows the actual code.

The smoke script (`smoke_report_v2.py`) and side-by-side script (`side_by_side_report_diff.py`) are described at the level of intent + a working sketch; the developer adapts the factory call to the actual `EquityResearchDepartment` instantiation pattern. Acceptable because the wiring depends on existing department factory shape that wasn't enumerated in the spec.

### Type consistency

- `SectionResult.state` is `SectionTerminalState` (enum with `SUCCESS/DEGRADED/EXHAUSTED`) — used consistently across Tasks 0.2, 4.3, 5.2, 6.3, 8.x.
- `Fact.source_ids: list[int]` — used consistently across all extractor tasks (1.3, 1.4, 1.5) and the packer (3.8).
- `ManifestEntry.id: int` (1-indexed) — manifest container, baseline, aggregator, parser citation markers all aligned.
- Block registry assembler signature `(*, data, citation_ids, manifest_resolver)` — text, table, charts, remaining blocks all use the same kwargs.
- `validate_section(parsed, *, facts_slice, target_word_count)` — used by dispatcher in 4.3 and runner in 5.2.

### Scope check

The plan is one cohesive replacement project, decomposed into 8 phases that each end in a green test suite and a commit. Phases 1–5 can be implemented without a live LLM (all fixtures + mocks). Phase 6 introduces the live integration. Phases 7–8 are validation and cutover.

Total tasks: 28 (numbered) + 4 phase-acceptance checkpoints + 3 manual validation checkpoints. Reasonable for a ~6-week project at one engineer.

---




