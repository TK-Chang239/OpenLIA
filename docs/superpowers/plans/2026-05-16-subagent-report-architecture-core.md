# Subagent Report Architecture — Core Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the core `SubagentReportRunner` pipeline (plan → eager fetch → sequential cheap-model subagents → flagship editor pass) behind a feature flag, with env-var-based model role configuration. Validates the architecture and hits the ≤$0.50/report target. DB migration + admin UI + setup wizard follow in a separate plan after validation.

**Architecture:** A new `SubagentReportRunner` orchestrator runs alongside the existing `ReportRunner`. Same SSE-event contract, same `_finalize_submit_payload` for assembly. Adds five new modules under `packages/core/src/openlia/llm/runtime/` (plan schema, section draft types, deterministic prior-section summarizer, subagent client, editor client, runner) plus two cacheable prompt partials and a new `report.subagent_planning` slot in `equity_research.yaml`.

**Tech Stack:** Python 3.13, Pydantic v2 (strict `extra="forbid"`), pytest+pytest-asyncio, ruff. uv for all package operations.

**Branch:** `feat/subagent-report-architecture` (already created on the merged main, commit `0d54264` carries the spec).

**Spec:** `docs/superpowers/specs/2026-05-16-subagent-report-architecture-design.md`

---

## Task 1: Plan schema types

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/plan_schema.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_plan_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_plan_schema.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from openlia.llm.runtime.plan_schema import DataPath, ReportPlan, SectionPlan


def _valid_section_plan(**overrides) -> dict:
    base = {
        "section_id": "company_overview",
        "title": "Company Overview",
        "narrative_goal": "Frame the business and its current position.",
        "key_questions": ["What does the company do?", "How does it make money?", "Who are key customers?"],
        "target_depth": "standard",
        "word_budget": 600,
        "data_paths": [
            {
                "tool_name": "eodhd__get_fundamentals_data",
                "tool_arguments": {"ticker": "MSFT.US"},
                "path": "General",
                "purpose": "Company background fields",
            }
        ],
        "cross_refs": [],
    }
    base.update(overrides)
    return base


def _valid_plan(**overrides) -> dict:
    base = {
        "company_thesis": "Microsoft is a mature franchise with cloud growth as the swing factor.",
        "sections": [_valid_section_plan()],
        "cross_section_themes": ["cloud growth", "AI capex pressure"],
    }
    base.update(overrides)
    return base


def test_minimal_plan_validates() -> None:
    plan = ReportPlan.model_validate(_valid_plan())
    assert plan.company_thesis.startswith("Microsoft")
    assert len(plan.sections) == 1
    assert plan.sections[0].section_id == "company_overview"


def test_section_id_uniqueness_enforced() -> None:
    bad = _valid_plan(sections=[_valid_section_plan(), _valid_section_plan()])
    with pytest.raises(ValidationError, match="unique"):
        ReportPlan.model_validate(bad)


def test_word_budget_range_enforced() -> None:
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(_valid_section_plan(word_budget=50))
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(_valid_section_plan(word_budget=3000))


def test_key_questions_min_three_max_six() -> None:
    too_few = _valid_section_plan(key_questions=["just one?", "and two"])
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(too_few)
    too_many = _valid_section_plan(key_questions=[f"q{i}" for i in range(7)])
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(too_many)


def test_cross_section_themes_min_two_max_four() -> None:
    with pytest.raises(ValidationError):
        ReportPlan.model_validate(_valid_plan(cross_section_themes=["only one"]))
    with pytest.raises(ValidationError):
        ReportPlan.model_validate(_valid_plan(cross_section_themes=[f"t{i}" for i in range(5)]))


def test_data_path_requires_exactly_one_source() -> None:
    with pytest.raises(ValidationError, match="one of"):
        DataPath.model_validate({"purpose": "x"})  # neither ref nor tool_name
    with pytest.raises(ValidationError, match="one of"):
        DataPath.model_validate(
            {
                "ref": "r_abc",
                "tool_name": "eodhd__get_fundamentals_data",
                "tool_arguments": {"ticker": "MSFT.US"},
                "purpose": "x",
            }
        )


def test_data_path_tool_requires_arguments() -> None:
    with pytest.raises(ValidationError, match="arguments"):
        DataPath.model_validate({"tool_name": "eodhd__get_fundamentals_data", "purpose": "x"})


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        ReportPlan.model_validate(_valid_plan(extra_field="nope"))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_plan_schema.py -v
```

Expected: FAIL (ImportError on `openlia.llm.runtime.plan_schema`)

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/plan_schema.py
"""Pydantic models for the report plan emitted by the flagship in the
planning phase of the subagent runner.

The flagship calls `plan_report` once. Its arguments — validated as
`ReportPlan` — drive eager fetching, per-section subagent dispatch, and
the editor pass.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataPath(_Strict):
    """A single data dependency for a section.

    Set EITHER ``ref`` (reference an existing payload from a prior data
    path in this plan) OR (``tool_name`` + ``tool_arguments``) to declare
    a new tool dispatch. Optional ``path`` slices into the result.
    """

    ref: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    path: str | None = None
    purpose: str

    @model_validator(mode="after")
    def _one_source_only(self) -> "DataPath":
        has_ref = self.ref is not None
        has_tool = self.tool_name is not None
        if has_ref == has_tool:
            raise ValueError("DataPath must set exactly one of `ref` or `tool_name`.")
        if has_tool and self.tool_arguments is None:
            raise ValueError("DataPath with `tool_name` must also set `tool_arguments`.")
        return self


class SectionPlan(_Strict):
    section_id: str
    title: str
    narrative_goal: str
    key_questions: Annotated[list[str], Field(min_length=3, max_length=6)]
    target_depth: Literal["brief", "standard", "deep"]
    word_budget: int = Field(ge=100, le=2000)
    data_paths: list[DataPath] = Field(default_factory=list)
    cross_refs: list[str] = Field(default_factory=list)


class ReportPlan(_Strict):
    company_thesis: str
    sections: Annotated[list[SectionPlan], Field(min_length=1)]
    cross_section_themes: Annotated[list[str], Field(min_length=2, max_length=4)]

    @model_validator(mode="after")
    def _section_ids_unique(self) -> "ReportPlan":
        ids = [s.section_id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Section IDs must be unique within a plan.")
        return self
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_plan_schema.py -v
```

Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/plan_schema.py packages/core/tests/test_llm/test_runtime/test_plan_schema.py
git commit -m "feat(subagent-runner): ReportPlan/SectionPlan/DataPath schema"
```

---

## Task 2: SectionDraft and PriorSection types

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/section_draft.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_section_draft.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_section_draft.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from openlia.llm.runtime.section_draft import OpenQuestion, PriorSection, SectionDraft


def test_minimal_draft_validates() -> None:
    d = SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": [{"type": "text", "content": "Microsoft is a software company."}],
            "citations_used": [],
            "word_count": 5,
            "open_questions": [],
        }
    )
    assert d.section_id == "company_overview"
    assert d.word_count == 5


def test_blocks_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        SectionDraft.model_validate(
            {
                "section_id": "x",
                "blocks": [],
                "citations_used": [],
                "word_count": 0,
                "open_questions": [],
            }
        )


def test_prior_section_key_facts_capped_at_five() -> None:
    with pytest.raises(ValidationError):
        PriorSection.model_validate(
            {
                "section_id": "x",
                "title": "X",
                "summary": "...",
                "key_facts_for_threading": [f"f{i}" for i in range(6)],
            }
        )


def test_open_question_shape() -> None:
    q = OpenQuestion.model_validate({"section_id": "risks", "question": "Pending FX exposure detail."})
    assert q.section_id == "risks"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_section_draft.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/section_draft.py
"""Pydantic models for subagent output.

A subagent returns a ``SectionDraft`` via a forced ``submit_section``
tool call. The orchestrator collapses each draft into a ``PriorSection``
summary that is passed to subsequent subagents for narrative threading.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenQuestion(_Strict):
    section_id: str
    question: str


class SectionDraft(_Strict):
    section_id: str
    blocks: Annotated[list[dict[str, Any]], Field(min_length=1)]
    citations_used: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)
    open_questions: list[str] = Field(default_factory=list)


class PriorSection(_Strict):
    section_id: str
    title: str
    summary: str
    key_facts_for_threading: Annotated[list[str], Field(min_length=0, max_length=5)] = Field(
        default_factory=list
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_section_draft.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/section_draft.py packages/core/tests/test_llm/test_runtime/test_section_draft.py
git commit -m "feat(subagent-runner): SectionDraft/PriorSection/OpenQuestion types"
```

---

## Task 3: Prior-section summarizer (deterministic, no LLM)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/prior_section_summarizer.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_prior_section_summarizer.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_prior_section_summarizer.py
from __future__ import annotations

from openlia.llm.runtime.prior_section_summarizer import summarize_section_draft
from openlia.llm.runtime.section_draft import SectionDraft


def _draft(blocks: list[dict]) -> SectionDraft:
    return SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": blocks,
            "citations_used": [],
            "word_count": sum(len(b.get("content", "").split()) for b in blocks if b.get("type") == "text"),
            "open_questions": [],
        }
    )


def test_summary_truncates_text_to_two_hundred_words() -> None:
    long_text = " ".join([f"word{i}" for i in range(500)])
    out = summarize_section_draft(_draft([{"type": "text", "content": long_text}]), title="Overview")
    assert out.section_id == "company_overview"
    assert out.title == "Overview"
    assert len(out.summary.split()) <= 200


def test_summary_includes_metric_card_bullets_as_threading_facts() -> None:
    blocks = [
        {"type": "text", "content": "Microsoft posted record revenue."},
        {
            "type": "metric_cards",
            "metrics": [
                {"label": "Revenue", "value": "$245B"},
                {"label": "Op margin", "value": "44%"},
                {"label": "EPS", "value": "$12.93"},
            ],
        },
    ]
    out = summarize_section_draft(_draft(blocks), title="Overview")
    joined = " ".join(out.key_facts_for_threading)
    assert "Revenue" in joined and "$245B" in joined
    assert len(out.key_facts_for_threading) <= 5


def test_summary_includes_chart_titles_as_threading_facts() -> None:
    blocks = [
        {"type": "text", "content": "Overview."},
        {
            "type": "line_chart",
            "title": "Revenue Trend FY21-FY25",
            "series": [{"name": "Revenue", "data": [1, 2, 3]}],
        },
    ]
    out = summarize_section_draft(_draft(blocks), title="Trends")
    assert any("Revenue Trend FY21-FY25" in fact for fact in out.key_facts_for_threading)


def test_table_block_contributes_first_row_summary() -> None:
    blocks = [
        {
            "type": "table",
            "title": "Comps",
            "headers": [{"key": "ticker", "label": "Ticker"}, {"key": "pe", "label": "P/E"}],
            "rows": [{"ticker": "MSFT", "pe": 35}, {"ticker": "GOOGL", "pe": 28}],
        }
    ]
    out = summarize_section_draft(_draft(blocks), title="Comps")
    joined = " ".join(out.key_facts_for_threading)
    assert "ticker" in joined and "pe" in joined
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_prior_section_summarizer.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/prior_section_summarizer.py
"""Deterministic summarizer that converts a SectionDraft into a
PriorSection. No LLM. Used by the subagent runner to pass threading
context forward to subsequent subagents.

Word-budget contract: ``summary`` truncated to 200 words.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.section_draft import PriorSection, SectionDraft

_SUMMARY_WORD_CAP = 200
_THREADING_FACTS_CAP = 5


def _truncate_words(text: str, cap: int = _SUMMARY_WORD_CAP) -> str:
    words = text.strip().split()
    if len(words) <= cap:
        return " ".join(words)
    return " ".join(words[:cap]) + "..."


def _metric_card_bullets(block: dict[str, Any]) -> list[str]:
    bullets = []
    for m in (block.get("metrics") or [])[:_THREADING_FACTS_CAP]:
        label = str(m.get("label", "")).strip()
        value = str(m.get("value", "")).strip()
        if label and value:
            bullets.append(f"{label}: {value}")
    return bullets


def _table_bullet(block: dict[str, Any]) -> str | None:
    headers = block.get("headers") or []
    rows = block.get("rows") or []
    if not headers or not rows:
        return None
    keys = [str(h.get("key", "")) for h in headers if isinstance(h, dict)]
    first_row = rows[0] if isinstance(rows[0], dict) else {}
    parts = [f"{k}={first_row.get(k)}" for k in keys[:3]]
    return f"table[{block.get('title', '')}]: " + ", ".join(parts)


def _chart_bullet(block: dict[str, Any]) -> str | None:
    title = block.get("title")
    if not title:
        return None
    return f"chart: {title}"


_CHART_TYPES = {
    "line_chart",
    "bar_chart",
    "area_chart",
    "pie_chart",
    "candlestick_chart",
    "waterfall_chart",
    "scatter_plot",
    "heatmap",
    "treemap",
    "combo_chart",
}


def summarize_section_draft(draft: SectionDraft, *, title: str) -> PriorSection:
    """Collapse a SectionDraft into a PriorSection.

    ``summary`` is built by concatenating TextBlock contents (in order)
    and truncating to 200 words. ``key_facts_for_threading`` is built by
    walking other block types and producing at most 5 short bullets.
    """
    text_parts: list[str] = []
    facts: list[str] = []

    for block in draft.blocks:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(str(block.get("content", "")))
        elif btype == "metric_cards":
            facts.extend(_metric_card_bullets(block))
        elif btype == "table":
            bullet = _table_bullet(block)
            if bullet:
                facts.append(bullet)
        elif btype in _CHART_TYPES:
            bullet = _chart_bullet(block)
            if bullet:
                facts.append(bullet)

    summary = _truncate_words(" ".join(text_parts).strip() or "(no narrative text)")
    return PriorSection(
        section_id=draft.section_id,
        title=title,
        summary=summary,
        key_facts_for_threading=facts[:_THREADING_FACTS_CAP],
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_prior_section_summarizer.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/prior_section_summarizer.py packages/core/tests/test_llm/test_runtime/test_prior_section_summarizer.py
git commit -m "feat(subagent-runner): deterministic prior-section summarizer"
```

---

## Task 4: Resolver role parameter + soft fallback

**Files:**
- Modify: `packages/core/src/openlia/llm/resolver.py` (add `role` parameter to `ResolveFn`/registry resolution)
- Test: `packages/core/tests/test_llm/test_resolver_role.py`

> **Before starting:** Run `grep -n "def resolve\|class.*Registry\|ModelRegistry" packages/core/src/openlia/llm/resolver.py | head -20` to anchor the current resolver signature. Adapt the changes below to match what exists.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_resolver_role.py
"""Resolver must accept a `role` parameter ('flagship' | 'subagent').

When `role="subagent"` is requested but no per-(department, role) pick is
configured, the resolver falls back to the flagship and emits a warning
event the caller can record."""
from __future__ import annotations

from typing import Any

import pytest

from openlia.llm.resolver import resolve_role
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel


def _resolved(ref: str) -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id=ref,
        model_ref=ref,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


class _FakePrefs:
    def __init__(self, picks: dict[tuple[str, str, str], str]) -> None:
        self._picks = picks  # (department_id, user_id, role) -> model_id

    def get_model_pick(self, *, department_id: str, user_id: str | None, role: str) -> str | None:
        return self._picks.get((department_id, user_id or "", role))


class _FakeRegistry:
    def resolve(self, model_id: str) -> ResolvedModel:
        return _resolved(model_id)


def test_explicit_role_pick_resolves() -> None:
    prefs = _FakePrefs({("equity_research", "u_1", "subagent"): "cheap-model"})
    out = resolve_role(
        department_id="equity_research",
        user_id="u_1",
        role="subagent",
        registry=_FakeRegistry(),
        prefs=prefs,
        server_defaults={},
        warn=lambda *a, **k: None,
    )
    assert out.model_ref == "cheap-model"


def test_subagent_falls_back_to_flagship_and_warns() -> None:
    warnings: list[tuple[str, str]] = []
    prefs = _FakePrefs({("equity_research", "u_1", "flagship"): "flagship-model"})
    out = resolve_role(
        department_id="equity_research",
        user_id="u_1",
        role="subagent",
        registry=_FakeRegistry(),
        prefs=prefs,
        server_defaults={},
        warn=lambda cat, msg: warnings.append((cat, msg)),
    )
    assert out.model_ref == "flagship-model"
    assert warnings == [("report.warning.subagent_unconfigured",
                         "Subagent model not configured; falling back to flagship.")]


def test_flagship_unconfigured_raises() -> None:
    from openlia.llm.exceptions import ModelNotConfiguredError

    prefs = _FakePrefs({})
    with pytest.raises(ModelNotConfiguredError):
        resolve_role(
            department_id="equity_research",
            user_id=None,
            role="flagship",
            registry=_FakeRegistry(),
            prefs=prefs,
            server_defaults={},
            warn=lambda *a, **k: None,
        )


def test_server_default_used_when_no_user_pick() -> None:
    prefs = _FakePrefs({})
    out = resolve_role(
        department_id="equity_research",
        user_id="u_1",
        role="subagent",
        registry=_FakeRegistry(),
        prefs=prefs,
        server_defaults={("equity_research", "subagent"): "default-cheap"},
        warn=lambda *a, **k: None,
    )
    assert out.model_ref == "default-cheap"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_resolver_role.py -v
```

Expected: FAIL (ImportError on `resolve_role`)

- [ ] **Step 3: Add `resolve_role` to resolver**

Append the following to `packages/core/src/openlia/llm/resolver.py`:

```python
# packages/core/src/openlia/llm/resolver.py — APPEND

from typing import Callable, Literal, Protocol

from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.types import ResolvedModel


Role = Literal["flagship", "subagent"]


class _SupportsModelPick(Protocol):
    def get_model_pick(
        self, *, department_id: str, user_id: str | None, role: Role
    ) -> str | None: ...


class _SupportsResolve(Protocol):
    def resolve(self, model_id: str) -> ResolvedModel: ...


WarnFn = Callable[[str, str], None]


def resolve_role(
    *,
    department_id: str,
    user_id: str | None,
    role: Role,
    registry: _SupportsResolve,
    prefs: _SupportsModelPick,
    server_defaults: dict[tuple[str, Role], str],
    warn: WarnFn,
) -> ResolvedModel:
    """Resolve the model to use for a (department, user, role).

    Order:
      1. Per-user pick from ``prefs``
      2. Server default from ``server_defaults``
      3. If ``role=='subagent'`` and nothing matched, fall back to
         flagship and call ``warn`` so the caller can emit a trace.
      4. Otherwise raise ``ModelNotConfiguredError``.
    """
    pick = prefs.get_model_pick(department_id=department_id, user_id=user_id, role=role)
    if pick:
        return registry.resolve(pick)

    default = server_defaults.get((department_id, role))
    if default:
        return registry.resolve(default)

    if role == "subagent":
        warn(
            "report.warning.subagent_unconfigured",
            "Subagent model not configured; falling back to flagship.",
        )
        return resolve_role(
            department_id=department_id,
            user_id=user_id,
            role="flagship",
            registry=registry,
            prefs=prefs,
            server_defaults=server_defaults,
            warn=warn,
        )

    raise ModelNotConfiguredError(department_id)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_resolver_role.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/resolver.py packages/core/tests/test_llm/test_resolver_role.py
git commit -m "feat(resolver): add role parameter with subagent soft fallback"
```

---

## Task 5: Cacheable prompt partials (subagent role + editor role)

**Files:**
- Create: `packages/core/src/openlia/prompts/shared/section_subagent_role.yaml.j2`
- Create: `packages/core/src/openlia/prompts/shared/editor_role.yaml.j2`
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts.py
"""Render the two new shared partials and verify they exist + carry
the required cache-friendly content (no per-turn interpolations)."""
from __future__ import annotations

from pathlib import Path

import openlia.prompts as prompts_pkg


def _read(name: str) -> str:
    p = Path(prompts_pkg.__file__).parent / "shared" / name
    return p.read_text()


def test_subagent_role_partial_describes_no_tools_contract() -> None:
    text = _read("section_subagent_role.yaml.j2")
    lower = text.lower()
    assert "no tools" in lower or "no other tools" in lower
    assert "submit_section" in text
    assert "open_questions" in text


def test_editor_role_partial_describes_final_assembly() -> None:
    text = _read("editor_role.yaml.j2")
    lower = text.lower()
    assert "submit_report" in text
    assert "thread" in lower or "weave" in lower or "narrative" in lower
    assert "cover" in lower


def test_partials_have_no_per_turn_interpolations() -> None:
    """Cache-friendly: nothing time/budget/request-specific in the bodies."""
    for name in ("section_subagent_role.yaml.j2", "editor_role.yaml.j2"):
        text = _read(name)
        assert "{{ current_date" not in text
        assert "{{ search_budget" not in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts.py -v
```

Expected: FAIL (FileNotFoundError on shared/section_subagent_role.yaml.j2)

- [ ] **Step 3: Create `section_subagent_role.yaml.j2`**

```jinja
{# packages/core/src/openlia/prompts/shared/section_subagent_role.yaml.j2 #}
You are a section writer for a financial research report. You write one
section at a time. You have no tools other than `submit_section`. All
data you need for this section is provided inline in the request.

## What you receive

- The company thesis the report is defending.
- The cross-section themes that thread the whole report.
- This section's plan: title, narrative_goal, key_questions, target
  depth, word_budget.
- The data your section needs, already fetched and keyed by
  `<ref>:<path>` (or `<ref>:` for the full payload).
- 200-word summaries of prior sections so you can thread without
  duplicating their content.

## What you must do

1. Answer every `key_question` the section plan asks.
2. Hit the `word_budget` within +/-20%. Underweight is rejected.
3. Cite every quantitative claim (numbers, dates, percentages) with a
   citation id you list in `citations_used`.
4. Reference cross-section themes where the section's content touches
   them — don't write the section as a standalone fragment.
5. If you find the provided data insufficient to answer a key question,
   add an entry to `open_questions` describing what's missing. Do NOT
   invent or estimate. Do NOT fall back to model knowledge.

## What you must NOT do

- Call any tool other than `submit_section`. No `read_payload`, no
  `web_search`, no data tools.
- Write the cover, the rail, or the meta_stats. Those are the editor's
  job.
- Add citations to the global citations list. List only the ids you
  reference; the editor merges.

## Output

Call `submit_section` exactly once with a SectionDraft payload.
EOL
```

- [ ] **Step 4: Create `editor_role.yaml.j2`**

```jinja
{# packages/core/src/openlia/prompts/shared/editor_role.yaml.j2 #}
You are the chief editor. You produce the final report payload by
composing the section drafts the subagents returned. You have no tools
other than `submit_report`.

## What you receive

- The company thesis.
- The cross-section themes the report must thread.
- All 14 section drafts (blocks verbatim) from the subagents.
- All accumulated `open_questions` from those subagents.
- The mode-specific cover instructions describing what cover.title,
  subtitle, tagline, tldr, and key_metrics should contain.

## Your responsibilities, in priority order

1. **Thread the narrative.** Weave the cross-section themes through
   TextBlocks. Add explicit cross-section references where helpful.
2. **Resolve open_questions.** Every accumulated open_question is
   either answered (using data from another section's blocks) or
   surfaced honestly as "no data available" — never silently dropped.
3. **Rebalance depth.** Expand thin sections (below 80% of their plan
   word_budget); trim bloated ones.
4. **Accuracy spot-check.** Cross-check quantitative claims in
   TextBlocks against the MetricCards/Tables in the same section. Fix
   mismatches.
5. **Compose the cover.** title, subtitle, tagline, tldr, key_metrics.
6. **Build the rail.** verdict (rating/target/upside), quick_stats,
   optional sparkline.

## What you must NOT do

- Call any tool other than `submit_report`.
- Reorder sections (the plan's order is final).
- Add new sections.
- Emit `meta_stats` (server-computed).

## Output

Call `submit_report` exactly once with the final report payload.
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/prompts/shared/section_subagent_role.yaml.j2 packages/core/src/openlia/prompts/shared/editor_role.yaml.j2 packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts.py
git commit -m "feat(prompts): section_subagent_role + editor_role partials"
```

---

## Task 6: Planning-phase prompt slot in equity_research.yaml

**Files:**
- Modify: `packages/core/src/openlia/prompts/equity_research.yaml` (add `report.subagent_planning` slot)
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_planning_slot.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_planning_slot.py
from __future__ import annotations

from openlia.llm.runtime.prompts import PromptLoader


def test_subagent_planning_slot_renders_for_equity_research() -> None:
    loader = PromptLoader()
    rendered = loader.render(
        "equity_research",
        "report.subagent_planning",
        style_guide="# Style\nProfessional.",
        framework_summary="Sections: company_overview, industry_overview, ... (14 total)",
        user_input="MSFT",
    )
    assert "plan_report" in rendered
    assert "key_questions" in rendered
    assert "word_budget" in rendered
    assert "cross_section_themes" in rendered
    assert "MSFT" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_planning_slot.py -v
```

Expected: FAIL (slot not found)

- [ ] **Step 3: Add the slot to `equity_research.yaml`**

Append to the `report:` block in `packages/core/src/openlia/prompts/equity_research.yaml` (after the existing `report.system` and `report.stock_initiation` keys, before `stock_update` or wherever the next slot starts):

```yaml
  subagent_planning: |
    You are planning a stock research report for {{ user_input }}.

    Call `plan_report` exactly once. The plan you emit drives the rest
    of the run: data is fetched up front, sections are drafted by
    section-writer subagents, and a final editor assembles everything.

    --- STYLE GUIDE ---
    {{ style_guide }}
    --- END STYLE GUIDE ---

    --- FRAMEWORK ---
    {{ framework_summary }}
    --- END FRAMEWORK ---

    Your plan must contain:
      - `company_thesis`: 2-3 sentences this report defends.
      - `cross_section_themes`: 2-4 narrative threads woven through
        the whole report.
      - `sections`: one entry per framework section, in render order.
        Each section has: `section_id`, `title`, `narrative_goal`,
        `key_questions` (3-6), `target_depth` (brief|standard|deep),
        `word_budget` (100-2000), `data_paths` (every data dependency
        declared up front), and `cross_refs` (other section_ids whose
        conclusions feed this one).

    Each `data_paths` entry either:
      - references an `ref` from a prior data_paths entry (in this plan),
      - or declares `tool_name` + `tool_arguments` for a new tool call.

    Declare data eagerly. Subagents have NO tools — they cannot
    fetch additional data. Anything you forget to plan becomes a
    `data not available` placeholder.
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_planning_slot.py -v
```

Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/equity_research.yaml packages/core/tests/test_llm/test_runtime/test_subagent_planning_slot.py
git commit -m "feat(prompts): equity_research.report.subagent_planning slot"
```

---

## Task 7: SubagentClient skeleton (calls model, parses SectionDraft)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/subagent_client.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_client.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_client.py
from __future__ import annotations

import pytest
from _fakes import FakeProvider, FakeProviderScript

from openlia.llm.runtime.plan_schema import SectionPlan
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.runtime.subagent_client import (
    SECTION_DRAFT_TOOL_NAME,
    SubagentClient,
    SubagentRequest,
)
from openlia.llm.types import ToolCall


def _valid_section_plan() -> SectionPlan:
    return SectionPlan.model_validate(
        {
            "section_id": "company_overview",
            "title": "Company Overview",
            "narrative_goal": "Frame the business.",
            "key_questions": ["q1", "q2", "q3"],
            "target_depth": "standard",
            "word_budget": 200,
            "data_paths": [],
            "cross_refs": [],
        }
    )


def _ok_draft_args(section_id: str, *, content: str, citations: list[str]) -> dict:
    return {
        "section_id": section_id,
        "blocks": [{"type": "text", "content": content}],
        "citations_used": citations,
        "word_count": len(content.split()),
        "open_questions": [],
    }


def _request() -> SubagentRequest:
    return SubagentRequest(
        role_prompt="ROLE",
        style_guide="STYLE",
        schema_strictness="STRICT",
        company_thesis="MSFT is a mature franchise.",
        cross_section_themes=["cloud growth", "AI capex"],
        this_section=_valid_section_plan(),
        fetched_data={},
        prior_section_summaries=[],
    )


@pytest.mark.asyncio
async def test_subagent_calls_model_with_no_tools_other_than_submit_section() -> None:
    ok = _ok_draft_args("company_overview", content=" ".join(["w"] * 200), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(turns=[("tool_calls", [ToolCall(id="c1", name=SECTION_DRAFT_TOOL_NAME, arguments=ok)])])
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert isinstance(draft, SectionDraft)
    assert draft.section_id == "company_overview"

    # No tools other than submit_section.
    req = provider.captured_requests[0]
    tool_names = {t.name for t in (req.tools or [])}
    assert tool_names == {SECTION_DRAFT_TOOL_NAME}
    # Force tool_choice == submit_section
    assert isinstance(req.tool_choice, dict) and "submit_section" in str(req.tool_choice)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/subagent_client.py
"""SubagentClient — runs one section through a cheap-model LLM.

Strict contract:
  - The model sees only `submit_section` as a tool. No `read_payload`,
    no `web_search`, no data tools.
  - Forced `tool_choice=submit_section`.
  - Output is parsed as `SectionDraft`.
  - Quality guardrails (word_budget, citation coverage, schema validity)
    enforced with at most ``reprompt_budget`` re-prompts.

Per-section context (request body) lives below a cache breakpoint marker;
the role prompt + style + strictness sit above so the prefix is cached
across all subagents in a single run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openlia.llm.adapters._content import CACHE_BREAKPOINT_MARKER
from openlia.llm.base import LLMProvider
from openlia.llm.runtime.plan_schema import SectionPlan
from openlia.llm.runtime.section_draft import PriorSection, SectionDraft
from openlia.llm.types import LLMRequest, Message, ToolSchema

SECTION_DRAFT_TOOL_NAME = "submit_section"


@dataclass(frozen=True)
class SubagentRequest:
    role_prompt: str
    style_guide: str
    schema_strictness: str
    company_thesis: str
    cross_section_themes: list[str]
    this_section: SectionPlan
    fetched_data: dict[str, Any]
    prior_section_summaries: list[PriorSection]


def _submit_section_tool() -> ToolSchema:
    return ToolSchema(
        name=SECTION_DRAFT_TOOL_NAME,
        description=(
            "Submit the section draft. Call exactly once with a SectionDraft "
            "payload: section_id, blocks (non-empty), citations_used, "
            "word_count, open_questions."
        ),
        parameters=SectionDraft.model_json_schema(),
    )


def _force_submit_section_choice(provider_kind: str) -> dict[str, Any]:
    if provider_kind == "anthropic":
        return {"type": "tool", "name": SECTION_DRAFT_TOOL_NAME}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [SECTION_DRAFT_TOOL_NAME],
            }
        }
    return {"type": "function", "function": {"name": SECTION_DRAFT_TOOL_NAME}}


def _system_prompt(req: SubagentRequest) -> str:
    return (
        f"{req.role_prompt}\n\n"
        f"{req.style_guide}\n\n"
        f"{req.schema_strictness}\n\n"
        f"{CACHE_BREAKPOINT_MARKER}\n"
    )


def _user_prompt(req: SubagentRequest) -> str:
    sp = req.this_section
    summaries = "\n\n".join(
        f"### Prior section {ps.section_id} — {ps.title}\n"
        f"{ps.summary}\n"
        f"Key facts: {', '.join(ps.key_facts_for_threading) if ps.key_facts_for_threading else '(none)'}"
        for ps in req.prior_section_summaries
    )
    data_blob = json.dumps(req.fetched_data, default=str, indent=2)
    return (
        f"## Company thesis\n{req.company_thesis}\n\n"
        f"## Cross-section themes\n- " + "\n- ".join(req.cross_section_themes) + "\n\n"
        f"## This section\n"
        f"section_id: {sp.section_id}\n"
        f"title: {sp.title}\n"
        f"narrative_goal: {sp.narrative_goal}\n"
        f"target_depth: {sp.target_depth}\n"
        f"word_budget: {sp.word_budget} (+/-20%)\n"
        f"key_questions:\n- " + "\n- ".join(sp.key_questions) + "\n\n"
        f"## Data available to this section\n```json\n{data_blob}\n```\n\n"
        f"## Prior section summaries\n{summaries or '(none — you are the first section)'}\n"
    )


class SubagentClient:
    def __init__(self, *, provider: LLMProvider, reprompt_budget: int = 1) -> None:
        self._provider = provider
        self._reprompt_budget = reprompt_budget

    async def draft(self, request: SubagentRequest) -> SectionDraft:
        system = _system_prompt(request)
        user = _user_prompt(request)
        messages = [Message(role="user", content=user)]
        tools = [_submit_section_tool()]
        tool_choice = _force_submit_section_choice(self._provider.kind)
        response = await self._provider.generate(
            LLMRequest(
                system=system,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=2048,
            )
        )
        # Pick the submit_section call.
        call = next((c for c in response.tool_calls if c.name == SECTION_DRAFT_TOOL_NAME), None)
        if call is None:
            raise ValueError("subagent returned no submit_section call")
        return SectionDraft.model_validate(call.arguments)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py -v
```

Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_client.py packages/core/tests/test_llm/test_runtime/test_subagent_client.py
git commit -m "feat(subagent-runner): SubagentClient skeleton with no-tools contract"
```

---

## Task 8: SubagentClient word_budget guardrail (1 re-prompt)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/subagent_client.py`
- Modify: `packages/core/tests/test_llm/test_runtime/test_subagent_client.py`

- [ ] **Step 1: Add the failing test**

Append to `test_subagent_client.py`:

```python
from openlia.llm.types import ToolCall as _ToolCall  # alias (already imported)


@pytest.mark.asyncio
async def test_subagent_reprompts_on_underweight_word_count() -> None:
    sp = _valid_section_plan()  # word_budget=200
    # Turn 0: half the budget (rejected). Turn 1: in range.
    underweight = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 80), citations=["c1"])
    inrange = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 200), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=underweight)]),
                ("tool_calls", [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=inrange)]),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert draft.word_count == 200
    assert len(provider.captured_requests) == 2
    # The reprompt turn must contain a tool result message naming the issue.
    second = provider.captured_requests[1].messages
    repair_msg = [m for m in second if m.role == "tool"]
    assert repair_msg and "word_count" in repair_msg[-1].content


@pytest.mark.asyncio
async def test_subagent_accepts_after_budget_exhausted() -> None:
    sp = _valid_section_plan()
    bad = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 50), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=bad)]),
                ("tool_calls", [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=bad)]),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    # Accept the last attempt with an open_question flag.
    assert any("word_count" in q for q in draft.open_questions)
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py -v
```

Expected: 2 new tests FAIL (no guardrail logic yet).

- [ ] **Step 3: Add the guardrail loop to SubagentClient.draft**

Replace `SubagentClient.draft` in `subagent_client.py` with:

```python
    async def draft(self, request: SubagentRequest) -> SectionDraft:
        system = _system_prompt(request)
        user = _user_prompt(request)
        messages: list[Message] = [Message(role="user", content=user)]
        tools = [_submit_section_tool()]
        tool_choice = _force_submit_section_choice(self._provider.kind)

        last_draft: SectionDraft | None = None
        last_call_id: str | None = None
        last_issues: list[str] = []

        for attempt in range(self._reprompt_budget + 1):
            response = await self._provider.generate(
                LLMRequest(
                    system=system,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=2048,
                )
            )
            call = next(
                (c for c in response.tool_calls if c.name == SECTION_DRAFT_TOOL_NAME), None
            )
            if call is None:
                raise ValueError("subagent returned no submit_section call")
            draft = SectionDraft.model_validate(call.arguments)
            issues = self._validate_draft(draft, request.this_section)
            if not issues:
                return draft
            last_draft = draft
            last_call_id = call.id
            last_issues = issues
            # If this was the last allowed attempt, fall through to flag.
            if attempt == self._reprompt_budget:
                break
            # Otherwise: append assistant + tool repair messages and loop.
            messages.append(
                Message(role="assistant", content="", tool_calls=[call])
            )
            messages.append(
                Message(
                    role="tool",
                    content=json.dumps({"issues": issues, "hint": "Fix and re-submit."}),
                    tool_call_id=call.id,
                )
            )

        # Accepted last attempt; flag the issues.
        assert last_draft is not None
        flagged_open = list(last_draft.open_questions)
        flagged_open.extend(f"[auto-flag] {i}" for i in last_issues)
        return last_draft.model_copy(update={"open_questions": flagged_open})

    def _validate_draft(
        self, draft: SectionDraft, sp: SectionPlan
    ) -> list[str]:
        issues: list[str] = []
        lo, hi = int(sp.word_budget * 0.8), int(sp.word_budget * 1.2)
        if not (lo <= draft.word_count <= hi):
            issues.append(
                f"word_count={draft.word_count} outside +/-20% of word_budget={sp.word_budget} "
                f"(allowed range {lo}-{hi})."
            )
        if draft.section_id != sp.section_id:
            issues.append(
                f"section_id={draft.section_id!r} does not match expected {sp.section_id!r}."
            )
        return issues
```

Note: leave room for additional guardrails (citation coverage, schema validity) — those land in Tasks 9 and 10 via additions to `_validate_draft`.

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_client.py packages/core/tests/test_llm/test_runtime/test_subagent_client.py
git commit -m "feat(subagent-runner): word_budget guardrail with 1 re-prompt"
```

---

## Task 9: SubagentClient citation-coverage guardrail

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/subagent_client.py`
- Modify: `packages/core/tests/test_llm/test_runtime/test_subagent_client.py`

- [ ] **Step 1: Add the failing test**

Append to `test_subagent_client.py`:

```python
@pytest.mark.asyncio
async def test_subagent_reprompts_on_uncited_numeric_claim() -> None:
    sp = _valid_section_plan()
    uncited = _ok_draft_args(
        sp.section_id,
        content="Revenue grew 12.5% YoY to $245B in FY25 " + " ".join(["w"] * 190),
        citations=[],
    )
    cited = _ok_draft_args(
        sp.section_id,
        content="Revenue grew 12.5% YoY to $245B in FY25 " + " ".join(["w"] * 190),
        citations=["c1"],
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=uncited)]),
                ("tool_calls", [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=cited)]),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert draft.citations_used == ["c1"]
    assert len(provider.captured_requests) == 2
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py::test_subagent_reprompts_on_uncited_numeric_claim -v
```

Expected: FAIL (no citation check yet).

- [ ] **Step 3: Extend `_validate_draft` with citation coverage**

Add to `_validate_draft` in `subagent_client.py`:

```python
import re

_NUMERIC_CLAIM_RE = re.compile(r"\b(\d+(?:[.,]\d+)*\s*%?|\$\s*\d+(?:[.,]\d+)*(?:[KMB])?)\b")


# inside SubagentClient._validate_draft, after the existing checks:
        has_numeric_claim = False
        for block in draft.blocks:
            if block.get("type") == "text":
                if _NUMERIC_CLAIM_RE.search(str(block.get("content", ""))):
                    has_numeric_claim = True
                    break
        if has_numeric_claim and not draft.citations_used:
            issues.append(
                "TextBlocks contain numeric claims (digits, percentages, "
                "$amounts) but citations_used is empty. Add citation ids."
            )
        return issues
```

(Hoist the `import re` to the top of the file alongside `import json`.)

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_client.py packages/core/tests/test_llm/test_runtime/test_subagent_client.py
git commit -m "feat(subagent-runner): citation-coverage guardrail"
```

---

## Task 10: SubagentClient schema-validity guardrail

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/subagent_client.py`
- Modify: `packages/core/tests/test_llm/test_runtime/test_subagent_client.py`

- [ ] **Step 1: Add the failing test**

Append to `test_subagent_client.py`:

```python
@pytest.mark.asyncio
async def test_subagent_reprompts_on_invalid_block_shape() -> None:
    sp = _valid_section_plan()
    bad_blocks = {
        "section_id": sp.section_id,
        "blocks": [{"type": "text", "content": " ".join(["w"] * 200)},
                   {"type": "line_chart", "title": "X"}],  # missing required `series`
        "citations_used": ["c1"],
        "word_count": 200,
        "open_questions": [],
    }
    fixed = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 200), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=bad_blocks)]),
                ("tool_calls", [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=fixed)]),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert all(b["type"] == "text" for b in draft.blocks)
    assert len(provider.captured_requests) == 2
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py::test_subagent_reprompts_on_invalid_block_shape -v
```

Expected: FAIL.

- [ ] **Step 3: Extend `_validate_draft` to validate each block against ReportSchema's strict block model**

Add at the top of `subagent_client.py`:

```python
from openlia.reports.validator import validate_report_payload
```

Inside `_validate_draft`, append before the final `return issues`:

```python
        # Strict per-block validation by passing a one-section dummy payload
        # through the existing validator. Cheaper than rebuilding block-level
        # discrimination here.
        dummy = {
            "cover": {"title": "x", "subtitle": "x", "tagline": "x"},
            "sections": [{"id": draft.section_id, "title": "x", "blocks": draft.blocks}],
            "schema_version": "2.0",
            "department": "equity_research",
            "generated_at": "2026-05-16T00:00:00+00:00",
        }
        try:
            validate_report_payload(dummy)
        except Exception as exc:
            issues.append(f"block schema invalid: {exc!s}")
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_client.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_client.py packages/core/tests/test_llm/test_runtime/test_subagent_client.py
git commit -m "feat(subagent-runner): block schema validity guardrail"
```

---

## Task 11: EditorClient (flagship, forced submit_report, 1 repair + coercion fallback)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/editor_client.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_editor_client.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_editor_client.py
from __future__ import annotations

import pytest
from _fakes import FakeProvider, FakeProviderScript

from openlia.llm.runtime.editor_client import EditorClient, EditorRequest, EDITOR_TOOL_NAME
from openlia.llm.runtime.section_draft import OpenQuestion, SectionDraft
from openlia.llm.types import ToolCall


def _draft(section_id: str, content: str) -> SectionDraft:
    return SectionDraft.model_validate(
        {
            "section_id": section_id,
            "blocks": [{"type": "text", "content": content}],
            "citations_used": ["c1"],
            "word_count": len(content.split()),
            "open_questions": [],
        }
    )


def _final_payload(title: str = "MSFT") -> dict:
    return {
        "cover": {"title": title, "subtitle": "Initiation", "tagline": "Constructive"},
        "sections": [
            {"id": "company_overview", "title": "Overview",
             "blocks": [{"type": "text", "content": "Overview body."}]}
        ],
    }


def _request() -> EditorRequest:
    return EditorRequest(
        role_prompt="ROLE",
        style_guide="STYLE",
        schema_strictness="STRICT",
        company_thesis="MSFT.",
        cross_section_themes=["t1", "t2"],
        section_drafts=[_draft("company_overview", "Overview body.")],
        open_questions=[OpenQuestion(section_id="x", question="q")],
        framework_cover_instructions="Cover fields: title, subtitle, tagline.",
    )


@pytest.mark.asyncio
async def test_editor_returns_final_payload_via_submit_report() -> None:
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())])
            ]
        )
    )
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    payload = await client.compose(_request())
    assert payload["cover"]["title"] == "MSFT"
    assert payload["sections"][0]["id"] == "company_overview"


@pytest.mark.asyncio
async def test_editor_repairs_once_on_validation_failure() -> None:
    bad = {"cover": {"title": "x", "subtitle": "y"}, "sections": []}  # missing tagline + empty sections
    good = _final_payload()
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=bad)]),
                ("tool_calls", [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=good)]),
            ]
        )
    )
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    payload = await client.compose(_request())
    assert payload["cover"]["title"] == "MSFT"
    assert len(provider.captured_requests) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_editor_client.py -v
```

Expected: FAIL (ImportError).

- [ ] **Step 3: Write the implementation**

```python
# packages/core/src/openlia/llm/runtime/editor_client.py
"""EditorClient — runs the final assembly pass.

Flagship model. Forced `submit_report` tool call. Strict ReportSchema
validation via the existing validator. One repair attempt on validation
failure; further failures are returned as-is for the caller to apply
its existing coercion fallback.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from openlia.llm.adapters._content import CACHE_BREAKPOINT_MARKER
from openlia.llm.base import LLMProvider
from openlia.llm.runtime.section_draft import OpenQuestion, SectionDraft
from openlia.llm.types import LLMRequest, Message, ToolSchema
from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload

EDITOR_TOOL_NAME = "submit_report"


@dataclass(frozen=True)
class EditorRequest:
    role_prompt: str
    style_guide: str
    schema_strictness: str
    company_thesis: str
    cross_section_themes: list[str]
    section_drafts: list[SectionDraft]
    open_questions: list[OpenQuestion]
    framework_cover_instructions: str


# Server-controlled fields the editor must not emit; mirrors the
# stripping the classic runner does for its submit_report schema.
_SERVER_CONTROLLED = frozenset({"schema_version", "department", "generated_at", "page_furniture", "meta_stats"})


def _submit_report_tool() -> ToolSchema:
    schema = copy.deepcopy(ReportSchema.model_json_schema())
    props = schema.get("properties", {})
    for f in _SERVER_CONTROLLED:
        props.pop(f, None)
    required = schema.get("required") or []
    schema["required"] = [r for r in required if r not in _SERVER_CONTROLLED]
    schema["properties"] = props
    return ToolSchema(
        name=EDITOR_TOOL_NAME,
        description="Submit the final report. Call exactly once with cover + sections.",
        parameters=schema,
    )


def _force_submit_report_choice(provider_kind: str) -> dict[str, Any]:
    if provider_kind == "anthropic":
        return {"type": "tool", "name": EDITOR_TOOL_NAME}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [EDITOR_TOOL_NAME],
            }
        }
    return {"type": "function", "function": {"name": EDITOR_TOOL_NAME}}


def _system_prompt(req: EditorRequest) -> str:
    return (
        f"{req.role_prompt}\n\n"
        f"{req.style_guide}\n\n"
        f"{req.schema_strictness}\n\n"
        f"{CACHE_BREAKPOINT_MARKER}\n"
    )


def _user_prompt(req: EditorRequest) -> str:
    drafts_blob = json.dumps([d.model_dump() for d in req.section_drafts], default=str, indent=2)
    open_blob = json.dumps([q.model_dump() for q in req.open_questions], default=str, indent=2)
    return (
        f"## Company thesis\n{req.company_thesis}\n\n"
        f"## Cross-section themes\n- " + "\n- ".join(req.cross_section_themes) + "\n\n"
        f"## Section drafts (verbatim from subagents)\n```json\n{drafts_blob}\n```\n\n"
        f"## Open questions\n```json\n{open_blob}\n```\n\n"
        f"## Cover instructions\n{req.framework_cover_instructions}\n"
    )


class EditorClient:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        repair_budget: int = 1,
        max_output_tokens: int = 8192,
    ) -> None:
        self._provider = provider
        self._repair_budget = repair_budget
        self._max_output_tokens = max_output_tokens

    async def compose(self, request: EditorRequest) -> dict[str, Any]:
        system = _system_prompt(request)
        messages: list[Message] = [Message(role="user", content=_user_prompt(request))]
        tools = [_submit_report_tool()]
        tool_choice = _force_submit_report_choice(self._provider.kind)
        last_payload: dict[str, Any] | None = None
        last_error: str | None = None
        for attempt in range(self._repair_budget + 1):
            response = await self._provider.generate(
                LLMRequest(
                    system=system,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self._max_output_tokens,
                )
            )
            call = next((c for c in response.tool_calls if c.name == EDITOR_TOOL_NAME), None)
            if call is None:
                raise ValueError("editor returned no submit_report call")
            payload = (
                call.arguments if isinstance(call.arguments, dict) else {}
            )
            try:
                validate_report_payload(_stamped(copy.deepcopy(payload)))
                return payload
            except Exception as exc:
                last_payload = payload
                last_error = str(exc)
                if attempt == self._repair_budget:
                    break
                messages.append(Message(role="assistant", content="", tool_calls=[call]))
                messages.append(
                    Message(
                        role="tool",
                        content=json.dumps({"error": last_error, "hint": "Fix and re-submit."}),
                        tool_call_id=call.id,
                    )
                )
        # Repair exhausted — return the last attempt; caller will coerce.
        assert last_payload is not None
        return last_payload


def _stamped(payload: dict[str, Any]) -> dict[str, Any]:
    """Stamp the server-controlled fields so validation succeeds without
    triggering "missing required" errors that aren't the editor's job."""
    payload.setdefault("schema_version", "2.0")
    payload.setdefault("department", "equity_research")
    payload.setdefault("generated_at", "2026-01-01T00:00:00+00:00")
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_editor_client.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/editor_client.py packages/core/tests/test_llm/test_runtime/test_editor_client.py
git commit -m "feat(subagent-runner): EditorClient with 1-repair budget"
```

---

## Task 12: SubagentReportRunner skeleton + planning phase

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/subagent_runner.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_runner_planning.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_runner_planning.py
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript

from openlia.llm.runtime.events import ReportError, ReportPhase, ReportStart
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.subagent_runner import (
    PLAN_REPORT_TOOL_NAME,
    SubagentReportRunner,
)
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True, tool_calling=True, structured_output=True, max_output_tokens=8192
        ),
        overrides={},
    )


def _resolve(*, department_id, user_id, registry, role="flagship", model_id_override=None):
    return _resolved()


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    (root / "shared").mkdir(parents=True)
    (root / "shared" / "output_discipline.yaml.j2").write_text("")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              subagent_planning: |
                Plan for {{ user_input }} via plan_report.
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
            """
        )
    )
    return root


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(
        json.dumps({"title": "Stock Initiation", "sections": [
            {"id": "company_overview", "title": "Overview", "instructions": "..."}
        ]})
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


def _valid_plan_args() -> dict:
    return {
        "company_thesis": "MSFT thesis.",
        "cross_section_themes": ["t1", "t2"],
        "sections": [
            {
                "section_id": "company_overview",
                "title": "Overview",
                "narrative_goal": "Frame the business.",
                "key_questions": ["q1", "q2", "q3"],
                "target_depth": "standard",
                "word_budget": 200,
                "data_paths": [],
                "cross_refs": [],
            }
        ],
    }


@pytest.mark.asyncio
async def test_planning_phase_emits_phase_event_and_validates_plan(
    prompts_root: Path, frameworks_root: Path
) -> None:
    plan_call = ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=_valid_plan_args())
    provider = FakeProvider(script=FakeProviderScript(turns=[("tool_calls", [plan_call])]))
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: provider,
        subagent_provider_factory=lambda r: provider,  # unused here
        report_id_factory=lambda: "r_plan",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)
        # Stop after planning phase to focus this test.
        if len(events) >= 3:
            break
    types = [type(e).__name__ for e in events]
    assert types[0] == "ReportStart"
    assert any(isinstance(e, ReportPhase) and e.phase == "planning" for e in events)


@pytest.mark.asyncio
async def test_planning_invalid_then_repair_succeeds(
    prompts_root: Path, frameworks_root: Path
) -> None:
    bad = {"company_thesis": "", "cross_section_themes": [], "sections": []}
    good = ToolCall(id="p1", name=PLAN_REPORT_TOOL_NAME, arguments=_valid_plan_args())
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=bad)]),
                ("tool_calls", [good]),
            ]
        )
    )
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: provider,
        subagent_provider_factory=lambda r: provider,
        report_id_factory=lambda: "r_repair",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)
        if len(events) >= 3:
            break
    # Two calls to the provider (initial + 1 repair).
    assert len(provider.captured_requests) >= 2


@pytest.mark.asyncio
async def test_planning_invalid_twice_emits_report_error(
    prompts_root: Path, frameworks_root: Path
) -> None:
    bad = {"company_thesis": "", "cross_section_themes": [], "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=bad)]),
                ("tool_calls", [ToolCall(id="p1", name=PLAN_REPORT_TOOL_NAME, arguments=bad)]),
            ]
        )
    )
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: provider,
        subagent_provider_factory=lambda r: provider,
        report_id_factory=lambda: "r_abort",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)
    assert any(isinstance(e, ReportError) for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_planning.py -v
```

Expected: FAIL (ImportError).

- [ ] **Step 3: Write the planning-phase skeleton**

```python
# packages/core/src/openlia/llm/runtime/subagent_runner.py
"""SubagentReportRunner — plan + eager fetch + subagents + editor.

This file ships in vertical slices: Task 12 implements the planning
phase only. Tasks 13-15 add eager fetch, section drafting, and the
editor pass.
"""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import AsyncIterator, Callable
from importlib import resources
from pathlib import Path
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.events import (
    ReportError,
    ReportPhase,
    ReportStart,
    SseEvent,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ToolSchema,
)

PLAN_REPORT_TOOL_NAME = "plan_report"


ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _plan_report_tool() -> ToolSchema:
    return ToolSchema(
        name=PLAN_REPORT_TOOL_NAME,
        description=(
            "Emit the report plan. Call exactly once with a ReportPlan: "
            "company_thesis, cross_section_themes (2-4), sections."
        ),
        parameters=ReportPlan.model_json_schema(),
    )


def _force_plan_choice(provider_kind: str) -> dict[str, Any]:
    if provider_kind == "anthropic":
        return {"type": "tool", "name": PLAN_REPORT_TOOL_NAME}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [PLAN_REPORT_TOOL_NAME],
            }
        }
    return {"type": "function", "function": {"name": PLAN_REPORT_TOOL_NAME}}


def _default_frameworks_root() -> Path:
    return Path(str(resources.files("openlia.reports.frameworks")))


def _load_framework(frameworks_root: Path, mode: str) -> dict[str, Any]:
    path = frameworks_root / f"{mode}.json"
    return json.loads(path.read_text())


def _load_style_guide(frameworks_root: Path, mode: str) -> str:
    path = frameworks_root / f"{mode}_style_guide.md"
    return path.read_text() if path.exists() else ""


def _framework_summary(framework: dict[str, Any]) -> str:
    sections = framework.get("sections", []) or []
    lines = [f"- {s.get('id')}: {s.get('title')}" for s in sections]
    return "Sections (render order):\n" + "\n".join(lines)


def _section_ids_in_framework(framework: dict[str, Any]) -> set[str]:
    return {str(s.get("id")) for s in (framework.get("sections") or [])}


class SubagentReportRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        tools: ToolDispatcher,
        resolve: ResolveFn,
        registry: Any,
        flagship_provider_factory: ProviderFactory,
        subagent_provider_factory: ProviderFactory,
        report_id_factory: Callable[[], str] | None = None,
        frameworks_root: Path | None = None,
        plan_repair_turns: int = 1,
    ) -> None:
        self._prompts = prompts
        self._tools = tools
        self._resolve = resolve
        self._registry = registry
        self._flagship_factory = flagship_provider_factory
        self._subagent_factory = subagent_provider_factory
        self._report_id_factory = report_id_factory or (lambda: f"r_{uuid.uuid4().hex[:12]}")
        self._frameworks_root = frameworks_root or _default_frameworks_root()
        self._plan_repair_turns = plan_repair_turns

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
    ) -> AsyncIterator[SseEvent]:
        report_id = self._report_id_factory()
        yield ReportStart(report_id=report_id, department_id=department_id, mode=request.mode)

        framework = _load_framework(self._frameworks_root, request.mode)
        style_guide = _load_style_guide(self._frameworks_root, request.mode)

        yield ReportPhase(report_id=report_id, phase="planning")

        # Resolve flagship for planning.
        resolved = self._resolve(
            department_id=department_id, user_id=user_id, registry=self._registry, role="flagship"
        )
        flagship = self._flagship_factory(resolved)

        planning_system = self._prompts.render(
            department_id, "report.subagent_planning",
            style_guide=style_guide,
            framework_summary=_framework_summary(framework),
            user_input=request.user_input,
        )
        plan_or_err = await self._run_planning(
            flagship=flagship,
            system=planning_system,
            framework=framework,
        )
        if isinstance(plan_or_err, ReportError):
            yield plan_or_err
            return

        # Plan validated. Eager fetch + drafting + editing land in later tasks.
        # For now: this slice ends after planning.
        return

    async def _run_planning(
        self,
        *,
        flagship: LLMProvider,
        system: str,
        framework: dict[str, Any],
    ) -> ReportPlan | ReportError:
        tools = [_plan_report_tool()]
        tool_choice = _force_plan_choice(flagship.kind)
        messages: list[Message] = [
            Message(role="user", content="Plan this report now.")
        ]
        last_err: str | None = None
        valid_section_ids = _section_ids_in_framework(framework)
        for attempt in range(self._plan_repair_turns + 1):
            response = await flagship.generate(
                LLMRequest(
                    system=system,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=4096,
                )
            )
            call = next(
                (c for c in response.tool_calls if c.name == PLAN_REPORT_TOOL_NAME), None
            )
            if call is None:
                last_err = "flagship did not call plan_report"
            else:
                try:
                    plan = ReportPlan.model_validate(call.arguments)
                    # Cross-check section_ids against framework.
                    unknown = [s.section_id for s in plan.sections if s.section_id not in valid_section_ids]
                    if unknown:
                        raise ValueError(f"unknown section_ids: {unknown}")
                    return plan
                except Exception as exc:
                    last_err = str(exc)
            if attempt == self._plan_repair_turns:
                break
            # Append assistant + repair tool message.
            if call is not None:
                messages.append(Message(role="assistant", content="", tool_calls=[call]))
                messages.append(
                    Message(
                        role="tool",
                        content=json.dumps({"error": last_err, "hint": "Fix the plan and re-submit."}),
                        tool_call_id=call.id,
                    )
                )
        return ReportError(report_id="r_pending", code="plan_invalid", message=str(last_err or "plan invalid"))
```

> **NOTE:** The `ReportError(report_id="r_pending", ...)` placeholder will be passed the real `report_id` from the caller in a follow-up step inside Task 14 when we wire end-to-end flow. For now the test only asserts the *type*, not the id.

- [ ] **Step 4: Run tests, verify pass**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_planning.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_runner.py packages/core/tests/test_llm/test_runtime/test_subagent_runner_planning.py
git commit -m "feat(subagent-runner): planning phase with 1 repair turn"
```

---

## Task 13: Eager fetch with dedup

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/subagent_runner.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_runner_eager_fetch.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_runner_eager_fetch.py
from __future__ import annotations

import pytest

from openlia.llm.runtime.plan_schema import DataPath, ReportPlan, SectionPlan
from openlia.llm.runtime.subagent_runner import dedupe_data_paths


def _section(section_id: str, data_paths: list[dict]) -> SectionPlan:
    return SectionPlan.model_validate(
        {
            "section_id": section_id,
            "title": section_id,
            "narrative_goal": "g",
            "key_questions": ["a", "b", "c"],
            "target_depth": "standard",
            "word_budget": 200,
            "data_paths": data_paths,
            "cross_refs": [],
        }
    )


def test_dedupe_identical_tool_calls_across_sections() -> None:
    fund_path_a = {
        "tool_name": "eodhd__get_fundamentals_data",
        "tool_arguments": {"ticker": "MSFT.US"},
        "purpose": "income",
        "path": "Financials.Income_Statement.yearly",
    }
    fund_path_b = {
        "tool_name": "eodhd__get_fundamentals_data",
        "tool_arguments": {"ticker": "MSFT.US"},
        "purpose": "balance",
        "path": "Financials.Balance_Sheet.yearly",
    }
    plan = ReportPlan.model_validate(
        {
            "company_thesis": "x",
            "cross_section_themes": ["t1", "t2"],
            "sections": [
                _section("a", [fund_path_a]).model_dump(),
                _section("b", [fund_path_b]).model_dump(),
            ],
        }
    )
    unique_calls = dedupe_data_paths(plan)
    # Tool dispatch is keyed by (tool_name, frozenset(args.items())). Two
    # paths sharing the same tool+args produce ONE dispatch entry, with both
    # paths attached for later slicing.
    assert len(unique_calls) == 1
    call = unique_calls[0]
    assert call.tool_name == "eodhd__get_fundamentals_data"
    assert call.tool_arguments == {"ticker": "MSFT.US"}
    paths = [dp.path for dp in call.attached]
    assert "Financials.Income_Statement.yearly" in paths
    assert "Financials.Balance_Sheet.yearly" in paths


def test_dedupe_distinct_tool_calls() -> None:
    plan = ReportPlan.model_validate(
        {
            "company_thesis": "x",
            "cross_section_themes": ["t1", "t2"],
            "sections": [
                _section("a", [{
                    "tool_name": "eodhd__get_fundamentals_data",
                    "tool_arguments": {"ticker": "MSFT.US"}, "purpose": "x"}]).model_dump(),
                _section("b", [{
                    "tool_name": "eodhd__get_fundamentals_data",
                    "tool_arguments": {"ticker": "AAPL.US"}, "purpose": "y"}]).model_dump(),
            ],
        }
    )
    unique = dedupe_data_paths(plan)
    assert len(unique) == 2
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_eager_fetch.py -v
```

Expected: FAIL (ImportError on `dedupe_data_paths`).

- [ ] **Step 3: Add the helper to subagent_runner.py**

Append to `subagent_runner.py`:

```python
from dataclasses import dataclass, field

from openlia.llm.runtime.plan_schema import DataPath


@dataclass
class UniqueToolCall:
    tool_name: str
    tool_arguments: dict[str, Any]
    attached: list[DataPath] = field(default_factory=list)


def dedupe_data_paths(plan: ReportPlan) -> list[UniqueToolCall]:
    """Walk every section's data_paths, dedupe by (tool_name, args),
    return one ``UniqueToolCall`` per distinct dispatch. Each entry's
    ``attached`` list holds every DataPath that wanted that ref so the
    caller can later slice the result by ``path`` and assign each subagent
    its own slice."""
    by_key: dict[tuple[str, frozenset[tuple[str, Any]]], UniqueToolCall] = {}
    for section in plan.sections:
        for dp in section.data_paths:
            if dp.tool_name is None:
                continue  # `ref`-only paths resolve against earlier dispatches
            key = (dp.tool_name, frozenset((dp.tool_arguments or {}).items()))
            entry = by_key.setdefault(
                key,
                UniqueToolCall(tool_name=dp.tool_name, tool_arguments=dp.tool_arguments or {}),
            )
            entry.attached.append(dp)
    return list(by_key.values())
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_eager_fetch.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_runner.py packages/core/tests/test_llm/test_runtime/test_subagent_runner_eager_fetch.py
git commit -m "feat(subagent-runner): dedupe_data_paths helper"
```

---

## Task 14: SubagentReportRunner full end-to-end (eager fetch + drafting + editor)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/subagent_runner.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_runner_e2e.py`

- [ ] **Step 1: Write the failing test (happy path)**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_runner_e2e.py
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript

from openlia.llm.runtime.events import ReportComplete, ReportPhase, ReportSectionComplete
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.subagent_runner import (
    PLAN_REPORT_TOOL_NAME,
    SubagentReportRunner,
)
from openlia.llm.runtime.subagent_client import SECTION_DRAFT_TOOL_NAME
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True, tool_calling=True, structured_output=True, max_output_tokens=8192
        ),
        overrides={},
    )


def _resolve(*, department_id, user_id, registry, role="flagship", model_id_override=None):
    return _resolved()


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    (root / "shared").mkdir(parents=True)
    (root / "shared" / "output_discipline.yaml.j2").write_text("")
    (root / "shared" / "section_subagent_role.yaml.j2").write_text("ROLE")
    (root / "shared" / "editor_role.yaml.j2").write_text("EDITOR")
    (root / "shared" / "report_schema_strictness.yaml.j2").write_text("STRICT")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              subagent_planning: |
                Plan for {{ user_input }} via plan_report. style={{ style_guide }} fw={{ framework_summary }}
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
            """
        )
    )
    return root


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(
        json.dumps({"title": "Stock Initiation", "sections": [
            {"id": "company_overview", "title": "Overview", "instructions": "..."}
        ]})
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


def _plan_args() -> dict:
    return {
        "company_thesis": "MSFT thesis.",
        "cross_section_themes": ["t1", "t2"],
        "sections": [
            {
                "section_id": "company_overview",
                "title": "Overview",
                "narrative_goal": "g",
                "key_questions": ["q1", "q2", "q3"],
                "target_depth": "standard",
                "word_budget": 200,
                "data_paths": [],
                "cross_refs": [],
            }
        ],
    }


def _section_draft_args(content: str) -> dict:
    return {
        "section_id": "company_overview",
        "blocks": [{"type": "text", "content": content}],
        "citations_used": ["c1"],
        "word_count": len(content.split()),
        "open_questions": [],
    }


def _editor_args() -> dict:
    return {
        "cover": {"title": "MSFT", "subtitle": "Initiation", "tagline": "Constructive"},
        "sections": [{"id": "company_overview", "title": "Overview",
                      "blocks": [{"type": "text", "content": "Final body."}]}],
    }


@pytest.mark.asyncio
async def test_runner_end_to_end_happy_path(
    prompts_root: Path, frameworks_root: Path
) -> None:
    flagship = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=_plan_args())]),
                ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=_editor_args())]),
            ]
        )
    )
    subagent = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(
                    id="s0",
                    name=SECTION_DRAFT_TOOL_NAME,
                    arguments=_section_draft_args(" ".join(["w"] * 200)),
                )]),
            ]
        )
    )
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: flagship,
        subagent_provider_factory=lambda r: subagent,
        report_id_factory=lambda: "r_e2e",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)

    types = [type(e).__name__ for e in events]
    assert "ReportStart" in types
    assert "ReportComplete" in types
    phases = [e.phase for e in events if isinstance(e, ReportPhase)]
    assert phases == ["planning", "eager_fetch", "section_drafting", "editing"]
    section_done = [e for e in events if isinstance(e, ReportSectionComplete)]
    assert len(section_done) == 1
    assert section_done[0].section_id == "company_overview"
    final = [e for e in events if isinstance(e, ReportComplete)][-1]
    assert final.schema["cover"]["title"] == "MSFT"
    assert final.schema["department"] == "equity_research"
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_e2e.py -v
```

Expected: FAIL (runner returns after planning phase).

- [ ] **Step 3: Extend the runner with eager fetch + drafting + editor wiring**

Replace the `run` method in `subagent_runner.py` with:

```python
    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
    ) -> AsyncIterator[SseEvent]:
        from openlia.llm.runtime.editor_client import (  # local import to avoid cycles
            EditorClient,
            EditorRequest,
            EDITOR_TOOL_NAME,
        )
        from openlia.llm.runtime.events import (
            ReportComplete,
            ReportSectionComplete,
        )
        from openlia.llm.runtime.prior_section_summarizer import summarize_section_draft
        from openlia.llm.runtime.section_draft import OpenQuestion, PriorSection, SectionDraft
        from openlia.llm.runtime.subagent_client import (
            SECTION_DRAFT_TOOL_NAME,
            SubagentClient,
            SubagentRequest,
        )

        report_id = self._report_id_factory()
        yield ReportStart(report_id=report_id, department_id=department_id, mode=request.mode)

        framework = _load_framework(self._frameworks_root, request.mode)
        style_guide = _load_style_guide(self._frameworks_root, request.mode)

        yield ReportPhase(report_id=report_id, phase="planning")
        resolved_flag = self._resolve(
            department_id=department_id, user_id=user_id, registry=self._registry, role="flagship"
        )
        flagship = self._flagship_factory(resolved_flag)
        planning_system = self._prompts.render(
            department_id, "report.subagent_planning",
            style_guide=style_guide,
            framework_summary=_framework_summary(framework),
            user_input=request.user_input,
        )
        plan_or_err = await self._run_planning(
            flagship=flagship, system=planning_system, framework=framework,
        )
        if isinstance(plan_or_err, ReportError):
            yield ReportError(report_id=report_id, code=plan_or_err.code, message=plan_or_err.message)
            return
        plan = plan_or_err

        yield ReportPhase(report_id=report_id, phase="eager_fetch")
        fetched_data = await self._eager_fetch(plan)

        yield ReportPhase(report_id=report_id, phase="section_drafting")
        resolved_sub = self._resolve(
            department_id=department_id, user_id=user_id, registry=self._registry, role="subagent"
        )
        subagent_provider = self._subagent_factory(resolved_sub)
        subagent = SubagentClient(provider=subagent_provider)
        prior_summaries: list[PriorSection] = []
        drafts: list[SectionDraft] = []
        sections_by_id = {s.section_id: s for s in plan.sections}
        for section in plan.sections:
            section_data = self._slice_for_section(section, fetched_data)
            req = SubagentRequest(
                role_prompt=self._prompts.render_partial("shared/section_subagent_role.yaml.j2")
                if hasattr(self._prompts, "render_partial") else "",
                style_guide=style_guide,
                schema_strictness="",
                company_thesis=plan.company_thesis,
                cross_section_themes=list(plan.cross_section_themes),
                this_section=section,
                fetched_data=section_data,
                prior_section_summaries=list(prior_summaries),
            )
            draft = await subagent.draft(req)
            drafts.append(draft)
            yield ReportSectionComplete(
                report_id=report_id, section_id=section.section_id, blocks=draft.blocks
            )
            prior_summaries.append(
                summarize_section_draft(draft, title=sections_by_id[section.section_id].title)
            )

        yield ReportPhase(report_id=report_id, phase="editing")
        editor = EditorClient(provider=flagship, repair_budget=1, max_output_tokens=8192)
        open_qs: list[OpenQuestion] = [
            OpenQuestion(section_id=d.section_id, question=q)
            for d in drafts for q in d.open_questions
        ]
        editor_payload = await editor.compose(
            EditorRequest(
                role_prompt="",  # cacheable bits loaded via prompts later
                style_guide=style_guide,
                schema_strictness="",
                company_thesis=plan.company_thesis,
                cross_section_themes=list(plan.cross_section_themes),
                section_drafts=drafts,
                open_questions=open_qs,
                framework_cover_instructions=str(framework.get("cover", {}).get("instructions", "")),
            )
        )

        from openlia.llm.runtime.report import _finalize_submit_payload
        from datetime import UTC, datetime

        finalized = _finalize_submit_payload(
            editor_payload,
            department_id=department_id,
            generated_at=datetime.now(UTC),
            provider_citations=[],
            model_id=resolved_flag.model_ref,
            total_input_tokens=0,
            total_output_tokens=0,
            web_search_count=0,
        )
        from openlia.reports.validator import validate_report_payload

        validate_report_payload(finalized)
        yield ReportComplete(report_id=report_id, schema=finalized)

    async def _eager_fetch(self, plan: ReportPlan) -> dict[str, Any]:
        """Dispatch every unique tool call from the plan, resolve every
        DataPath into a flat ``{"<ref-or-tool>:<path>": value}`` map."""
        from openlia.llm.runtime.payload_path import apply_path  # existing helper

        results: dict[str, Any] = {}
        unique = dedupe_data_paths(plan)
        for entry in unique:
            # Build a synthetic ToolCall and dispatch.
            from openlia.llm.types import ToolCall as _TC
            call = _TC(
                id=f"eager_{uuid.uuid4().hex[:6]}",
                name=entry.tool_name,
                arguments=dict(entry.tool_arguments),
            )
            res_list = await self._tools.dispatch_many(
                department_id="equity_research",
                calls=[call],
            )
            res = res_list[0]
            payload = res.payload
            for dp in entry.attached:
                key = f"{entry.tool_name}({json.dumps(entry.tool_arguments, sort_keys=True)}):{dp.path or ''}"
                value = payload if dp.path is None else apply_path(payload, dp.path)
                results[key] = value
        return results

    def _slice_for_section(
        self, section: Any, fetched_data: dict[str, Any]
    ) -> dict[str, Any]:
        slice_out: dict[str, Any] = {}
        for dp in section.data_paths:
            if dp.tool_name is None:
                continue
            key = f"{dp.tool_name}({json.dumps(dp.tool_arguments, sort_keys=True)}):{dp.path or ''}"
            if key in fetched_data:
                slice_out[key] = fetched_data[key]
        return slice_out
```

> **Note on shared partials:** the role prompts are loaded with empty strings in this slice to keep the test fixture-friendly. Task 15 wires the production loader to read `section_subagent_role.yaml.j2` and `editor_role.yaml.j2` so the cacheable prefix is real in production.

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_e2e.py -v
```

Expected: PASS (1 test).

- [ ] **Step 5: Run the broader suite to check no regressions**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/ -q
```

Expected: existing pre-existing failures unchanged; new tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_runner.py packages/core/tests/test_llm/test_runtime/test_subagent_runner_e2e.py
git commit -m "feat(subagent-runner): end-to-end plan→fetch→draft→edit pipeline"
```

---

## Task 15: Wire shared prompt partials into the runner

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/subagent_runner.py`
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts_loaded.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts_loaded.py
"""The runner must load section_subagent_role.yaml.j2 and editor_role.yaml.j2
as the cacheable role prompts passed to SubagentClient and EditorClient."""
from __future__ import annotations

from pathlib import Path

import openlia.prompts as prompts_pkg

from openlia.llm.runtime.subagent_runner import (
    load_section_subagent_role,
    load_editor_role,
)


def test_load_section_subagent_role_returns_partial_content() -> None:
    text = load_section_subagent_role()
    assert "submit_section" in text
    # Confirm we are reading from the shipped partials directory.
    p = Path(prompts_pkg.__file__).parent / "shared" / "section_subagent_role.yaml.j2"
    assert p.read_text().strip().startswith(text.strip()[:40])


def test_load_editor_role_returns_partial_content() -> None:
    text = load_editor_role()
    assert "submit_report" in text
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts_loaded.py -v
```

Expected: FAIL (ImportError).

- [ ] **Step 3: Add the loaders and wire them into `run`**

Add to `subagent_runner.py`:

```python
import openlia.prompts as _prompts_pkg


def load_section_subagent_role() -> str:
    p = Path(_prompts_pkg.__file__).parent / "shared" / "section_subagent_role.yaml.j2"
    return p.read_text()


def load_editor_role() -> str:
    p = Path(_prompts_pkg.__file__).parent / "shared" / "editor_role.yaml.j2"
    return p.read_text()
```

Update the `SubagentRequest` and `EditorRequest` construction inside `run` to pass:
- `role_prompt=load_section_subagent_role()` for subagents
- `role_prompt=load_editor_role()` for the editor

Also wire `schema_strictness` to read `shared/report_schema_strictness.yaml.j2` content via the same pattern.

- [ ] **Step 4: Run test, verify pass + re-run e2e**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts_loaded.py packages/core/tests/test_llm/test_runtime/test_subagent_runner_e2e.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_runner.py packages/core/tests/test_llm/test_runtime/test_subagent_runner_prompts_loaded.py
git commit -m "feat(subagent-runner): load shared role partials into requests"
```

---

## Task 16: Cached-tokens telemetry plumbed through subagent phases

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/subagent_runner.py` (add trace emission of `llm.call.done` per LLM call with `cached_input_tokens`)
- Test: `packages/core/tests/test_llm/test_runtime/test_subagent_runner_telemetry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_subagent_runner_telemetry.py
"""Every LLM call the subagent runner makes must emit an llm.call.done
trace event carrying cached_input_tokens, matching the contract the
classic ReportRunner now follows."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent
import json

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript

from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.subagent_client import SECTION_DRAFT_TOOL_NAME
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME
from openlia.llm.runtime.subagent_runner import (
    PLAN_REPORT_TOOL_NAME,
    SubagentReportRunner,
)
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel, ToolCall


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake", provider_id="p1", model_id="m1", model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True, max_output_tokens=8192),
        overrides={},
    )


def _resolve(*, department_id, user_id, registry, role="flagship", model_id_override=None):
    return _resolved()


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    (root / "shared").mkdir(parents=True)
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              subagent_planning: |
                Plan via plan_report. {{ user_input }} {{ style_guide }} {{ framework_summary }}
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
            """
        )
    )
    return root


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(json.dumps({
        "title": "Stock Initiation",
        "sections": [{"id": "company_overview", "title": "Overview", "instructions": "..."}]
    }))
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


@pytest.mark.asyncio
async def test_runner_emits_cached_input_tokens_for_every_llm_call(
    prompts_root: Path, frameworks_root: Path
) -> None:
    plan_args = {
        "company_thesis": "thesis", "cross_section_themes": ["t1", "t2"],
        "sections": [{
            "section_id": "company_overview", "title": "Overview",
            "narrative_goal": "g", "key_questions": ["q1", "q2", "q3"],
            "target_depth": "standard", "word_budget": 200,
            "data_paths": [], "cross_refs": [],
        }],
    }
    draft = {
        "section_id": "company_overview",
        "blocks": [{"type": "text", "content": " ".join(["w"] * 200)}],
        "citations_used": ["c1"], "word_count": 200, "open_questions": [],
    }
    editor = {
        "cover": {"title": "X", "subtitle": "Y", "tagline": "Z"},
        "sections": [{"id": "company_overview", "title": "Overview",
                      "blocks": [{"type": "text", "content": "Final body."}]}],
    }

    flagship = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=plan_args)]),
        ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=editor)]),
    ]))
    subagent = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="s0", name=SECTION_DRAFT_TOOL_NAME, arguments=draft)]),
    ]))

    traces: list[tuple[str, str, dict | None]] = []
    def recorder(cat: str, msg: str, payload: dict | None) -> None:
        traces.append((cat, msg, payload))

    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve, registry=object(),
        flagship_provider_factory=lambda r: flagship,
        subagent_provider_factory=lambda r: subagent,
        report_id_factory=lambda: "r_tel",
        frameworks_root=frameworks_root,
        trace=recorder,
    )
    async for _ in runner.run(
        department_id="equity_research", user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        pass

    done_events = [t for t in traces if t[0] == "llm.call.done"]
    # 3 LLM calls: planning + 1 subagent + 1 editor.
    assert len(done_events) == 3
    for _, _, payload in done_events:
        assert payload is not None
        assert "cached_input_tokens" in payload
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_telemetry.py -v
```

Expected: FAIL (no trace recorder hooked into runner).

- [ ] **Step 3: Add `trace` parameter to `SubagentReportRunner` and emit events around each LLM call**

In `subagent_runner.py`:

1. Add `trace: Callable[[str, str, dict[str, Any] | None], None] | None = None` to `__init__`; store as `self._trace = trace or (lambda *a, **k: None)`.
2. Wrap each `flagship.generate(...)` and `subagent.draft(...)` and `editor.compose(...)` call site to emit `llm.call.done` after with:

```python
self._trace(
    "llm.call.done",
    f"<phase> ({tool_name})",
    {
        "report_id": report_id,
        "phase": "<planning|drafting|editing>",
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cached_input_tokens": response.cached_input_tokens,
    },
)
```

For phases inside `SubagentClient.draft` and `EditorClient.compose`, the cleanest approach is to accept an optional `on_done: Callable[[LLMResponse], None] | None = None` parameter on those clients and have them invoke it for each call, then let the runner pass a closure that emits the trace. Add the parameter; update both clients; pipe through.

(Concretely: extend `SubagentClient.__init__` and `EditorClient.__init__` with `on_done: Callable | None = None`. Inside `draft`/`compose`, after each `response = await self._provider.generate(...)`, call `self._on_done(response)` if not None.)

- [ ] **Step 4: Run test, verify pass + re-run earlier tests**

```bash
uv run pytest packages/core/tests/test_llm/test_runtime/test_subagent_runner_telemetry.py packages/core/tests/test_llm/test_runtime/test_subagent_client.py packages/core/tests/test_llm/test_runtime/test_editor_client.py packages/core/tests/test_llm/test_runtime/test_subagent_runner_e2e.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/subagent_runner.py packages/core/src/openlia/llm/runtime/subagent_client.py packages/core/src/openlia/llm/runtime/editor_client.py packages/core/tests/test_llm/test_runtime/test_subagent_runner_telemetry.py
git commit -m "feat(subagent-runner): emit llm.call.done with cached_input_tokens"
```

---

## Task 17: Export the new runner from runtime package

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/__init__.py`

- [ ] **Step 1: Confirm the existing exports list**

```bash
grep -n "^from\|^__all__" packages/core/src/openlia/llm/runtime/__init__.py | head -20
```

- [ ] **Step 2: Add the export**

Append (or insert alphabetically) to `packages/core/src/openlia/llm/runtime/__init__.py`:

```python
from openlia.llm.runtime.subagent_runner import SubagentReportRunner

__all__ = list(globals().get("__all__", [])) + ["SubagentReportRunner"]
```

(Adapt to whatever export idiom the existing file uses — replace this paragraph's snippet if `__all__` is already curated.)

- [ ] **Step 3: Smoke-import**

```bash
uv run python -c "from openlia.llm.runtime import SubagentReportRunner; print(SubagentReportRunner)"
```

Expected: prints the class.

- [ ] **Step 4: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/__init__.py
git commit -m "feat(subagent-runner): export SubagentReportRunner from package"
```

---

## Task 18: Server routing behind feature flag

**Files:**
- Modify: `packages/server/src/openlia_server/services/runtime.py`
- Test: `packages/server/tests/test_subagent_routing.py`

> **Before starting:** Run `grep -n "ReportRunner\|department_id\|equity_research" packages/server/src/openlia_server/services/runtime.py | head -20` to find the exact site where the classic `ReportRunner` is instantiated.

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_subagent_routing.py
"""When OPENLIA_USE_SUBAGENT_RUNNER=1 AND request.department_id is
equity_research, the runtime service must instantiate
SubagentReportRunner. Otherwise classic ReportRunner."""
from __future__ import annotations

import os

import pytest

from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.subagent_runner import SubagentReportRunner

from openlia_server.services.runtime import select_report_runner_class


def test_default_returns_classic_runner_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENLIA_USE_SUBAGENT_RUNNER", raising=False)
    cls = select_report_runner_class(department_id="equity_research")
    assert cls is ReportRunner


def test_flag_on_for_equity_research_returns_subagent_runner_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENLIA_USE_SUBAGENT_RUNNER", "1")
    cls = select_report_runner_class(department_id="equity_research")
    assert cls is SubagentReportRunner


def test_flag_on_for_other_department_returns_classic_runner_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENLIA_USE_SUBAGENT_RUNNER", "1")
    cls = select_report_runner_class(department_id="earnings_update")
    assert cls is ReportRunner
```

- [ ] **Step 2: Run test, confirm it fails**

```bash
uv run pytest packages/server/tests/test_subagent_routing.py -v
```

Expected: FAIL (ImportError on `select_report_runner_class`).

- [ ] **Step 3: Add the selector function and use it at the runner-construction site**

Add to `packages/server/src/openlia_server/services/runtime.py`:

```python
import os

from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.subagent_runner import SubagentReportRunner


def select_report_runner_class(*, department_id: str):
    if (
        os.environ.get("OPENLIA_USE_SUBAGENT_RUNNER") == "1"
        and department_id == "equity_research"
    ):
        return SubagentReportRunner
    return ReportRunner
```

Then locate the existing `ReportRunner(...)` instantiation in this file and replace it with:

```python
runner_cls = select_report_runner_class(department_id=request.department_id)
if runner_cls is SubagentReportRunner:
    runner = SubagentReportRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        flagship_provider_factory=provider_factory,
        subagent_provider_factory=provider_factory,
        report_id_factory=report_id_factory,
        trace=trace,
    )
else:
    runner = ReportRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        provider_factory=provider_factory,
        skill_registry=skill_registry,
        frameworks_root=frameworks_root,
        report_id_factory=report_id_factory,
    )
```

(Adapt the constructor arguments to match the existing `ReportRunner` instantiation — the exact set of kwargs depends on what the current file passes. The key insight: when subagent flag is on, swap the class and pass `flagship_provider_factory` + `subagent_provider_factory` instead of a single `provider_factory`. The cheap-model resolution is handled inside the runner via the resolver's `role` parameter.)

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest packages/server/tests/test_subagent_routing.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Run the server-side test suite to check no regressions**

```bash
uv run pytest packages/server/tests/ -q
```

Expected: only pre-existing failures (if any).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services/runtime.py packages/server/tests/test_subagent_routing.py
git commit -m "feat(server): route equity_research through SubagentReportRunner behind flag"
```

---

## Validation (not a TDD task — manual smoke after all tasks land)

After Task 18, perform the following manual validation. Do NOT commit any code from this step.

- [ ] Set env vars for a smoke run:

```bash
export OPENLIA_DEV_MODE=1
export OPENLIA_USE_SUBAGENT_RUNNER=1
export OPENLIA_DEFAULT_SUBAGENT_MODEL_ID="<your cheapest configured model id>"
```

- [ ] Restart the server:

```bash
pkill -9 -f "openlia serve" || true
sleep 1
OPENLIA_DEV_MODE=1 OPENLIA_USE_SUBAGENT_RUNNER=1 OPENLIA_DEFAULT_SUBAGENT_MODEL_ID="<id>" uv run openlia serve > /tmp/openlia-serve.log 2>&1 &
sleep 4
tail -3 /tmp/openlia-serve.log
```

- [ ] Generate one equity_research stock_initiation report through the UI.

- [ ] Pull the run's dev events and check:

```bash
RUN=$(grep '"category": "report.request"' ~/.openlia/dev-events.jsonl | tail -1 | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['payload']['report_id'])")
echo "Run: $RUN"
grep "$RUN" ~/.openlia/dev-events.jsonl | grep '"category": "llm.call.done"' | python3 -c "
import json, sys
total_in = total_cached = total_out = 0
for line in sys.stdin:
    p = json.loads(line)['payload']
    total_in += p.get('input_tokens', 0) or 0
    total_cached += p.get('cached_input_tokens', 0) or 0
    total_out += p.get('output_tokens', 0) or 0
print(f'input={total_in:,} cached={total_cached:,} (hit={total_cached/total_in*100 if total_in else 0:.0f}%) output={total_out:,}')
"
```

- [ ] Compare totals against the spec's ≤$0.50 target at your configured model pricing.

- [ ] Spot-check the rendered report in the UI for: no "data not available", visible narrative threading, even section depth, footnotes present.

If all four checks pass, the architecture is validated. The follow-up plan (DB migration + admin UI + setup wizard) can then proceed.

---

## Spec coverage self-review

Cross-checking the spec at `docs/superpowers/specs/2026-05-16-subagent-report-architecture-design.md`:

| Spec section | Implementation task(s) |
|---|---|
| §1 Plan schema | Task 1 |
| §2 Subagent contract (request/output/no-tools/guardrails/failures) | Tasks 2, 7-10 |
| §3 Orchestration (planning, eager-fetch, drafting, editor, summarizer) | Tasks 12-15 |
| §4 Editor pass (responsibilities, request/output, tools, repair) | Task 11 |
| §5 Model role configuration (resolver fallback) | Task 4 |
| §5 Admin UI surface | **Deferred to follow-up plan (out of scope)** |
| Configuration surfaces (env vars) | Task 18 (server routing reads them) |
| File layout | Tasks 1-17 create exactly the spec's new files |
| Test plan (15 vertical slices) | All 15 slices covered across Tasks 1-16 |
| Rollout plan v1 | Task 18 (default OFF behind env flag) + Validation section |

All in-scope spec sections are covered by a task. No type/method-name drift between tasks. No placeholders.

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-05-16-subagent-report-architecture-core.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
