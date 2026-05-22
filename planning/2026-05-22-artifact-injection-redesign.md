# Artifact-Injection Redesign for Stage 7 Drafter

**Date:** 2026-05-22
**Branch:** `feat/equity-research-engine-plan`
**Status:** Design contract for the Stage 7a materialization step + Stage 7b drafter

---

## 0. Purpose

Defines how helper-produced artifacts are projected into the drafter prompt. Replaces the implicit "concatenate all artifacts as JSON" default that would cost ~10-20k tokens per report. After redesign: ~6-9k tokens per report through markdown rendering, fidelity tiering, deduplication, and section-aware injection.

Confirmed design choices:
- **A2** — markdown-only at the drafter; verifier consumes Pydantic models separately
- **B3** — tiered fidelity (`headline` / `summary` / `full`) with cross-section deduplication
- **C3** — template defaults overridden by Stage 5 planner per run
- **Standalone** — artifact materialization is its own pipeline stage with its own tests

---

## 1. Pipeline placement

Insert artifact materialization as **Stage 7a**, drafting becomes **Stage 7b**. Avoids renumbering existing stages and keeps verifier at Stage 8.

```
Stage 5 (planner) → produces section_plan (with optional overrides)
Stage 6 (helper execution) → produces typed artifacts keyed by artifact_id
Stage 7a (materialization, NEW) → renders artifacts to sectioned markdown
Stage 7b (drafter) → composes prose around the sectioned markdown
Stage 8 (verifier) → unchanged; reads Pydantic models from Stage 6, prose from Stage 7b
```

Stage 7a is pure-Python, deterministic, and zero LLM calls. Its correctness is testable in isolation.

---

## 2. Fidelity contract on `ArtifactType`

Each `ArtifactType` registered in `artifact_types.yaml` must declare a Pydantic model that implements `to_markdown(level: Fidelity) -> str`. The closed `Fidelity` enum:

```python
from enum import Enum


class Fidelity(str, Enum):
    HEADLINE = "headline"   # ~30-80 tokens. One-liner with the key number.
    SUMMARY = "summary"     # ~200-400 tokens. Compact table / chart caption.
    FULL = "full"           # ~800-2000 tokens. Complete artifact.
```

### 2.1 Base interface

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel


class RenderableArtifact(BaseModel, ABC):
    """All ArtifactType Pydantic models inherit from this."""

    artifact_id: str  # set by helper at construction; matches artifact_types.yaml key

    @abstractmethod
    def to_markdown(self, level: Fidelity) -> str:
        """Render at the requested fidelity. Must respect token budget."""
        ...

    def estimated_tokens(self, level: Fidelity) -> int:
        """Rough estimate used by materialization for budgeting/validation."""
        return len(self.to_markdown(level)) // 4  # ~4 chars per token heuristic
```

### 2.2 Token budgets (enforced)

Materialization validates rendered output against a budget table. Helpers whose `to_markdown` overflows the budget at any level fail boot or surface a verifier issue at runtime.

| Level | Soft budget | Hard cap | Action on overflow |
|---|---|---|---|
| `headline` | 80 tokens | 120 tokens | warn; truncate at hard cap |
| `summary` | 400 tokens | 600 tokens | warn; truncate at hard cap |
| `full` | 2000 tokens | 3000 tokens | verifier issue `block_artifact_too_large` |

Hard caps exist so a runaway artifact can't blow the prompt; soft budgets exist to flag drift in code review.

### 2.3 Rendering conventions

- **Tables:** GitHub-flavored markdown, no inline HTML. Numeric columns right-aligned via `---:`.
- **Charts:** rendered as image links with a caption — `![DCF sensitivity](artifact:dcf_sensitivity_grid)`. The drafter sees the caption; the actual image is attached separately if the LLM call supports multimodal input.
- **Multi-section artifacts** (e.g., `comparables.run` which produces both a peer table and an implied range): each output gets its own `artifact_id` in `produces_artifacts`. Materialization renders them independently.
- **Headline rule:** every `headline` must contain at least one quantitative anchor. "DCF analysis completed" is not a headline; "DCF fair value = $312 (range $260-$365)" is.

---

## 3. `section_plan` schema

The contract that flows from Stage 5 planner into Stage 7a materialization.

```python
from pydantic import BaseModel


class SectionArtifactRef(BaseModel):
    artifact_id: str           # must exist in this run's Stage 6 output map
    fidelity: Fidelity         # requested level for THIS section
    note: str | None = None    # optional planner annotation, ignored by renderer


class SectionPlan(BaseModel):
    section_id: str            # e.g. "valuation_dcf"
    title: str                 # e.g. "Discounted Cash Flow Valuation"
    artifacts: list[SectionArtifactRef]
    drafter_brief: str | None = None  # 1-2 sentences guiding the drafter for this section


class ReportSectionPlan(BaseModel):
    template_id: str                # e.g. "stock_initiation_v2"
    sections: list[SectionPlan]     # ordered; drafter renders in this order
    overrides_applied: list[str] = []  # which planner overrides were applied (for audit)
```

`ReportSectionPlan` is the single hand-off contract. Stage 6 only needs to ensure every `artifact_id` referenced exists in its output map; missing references surface as a Stage 7a precondition failure (verifier issue `block_plan_artifact_missing`).

---

## 4. Template defaults + planner overrides

### 4.1 Template default

Each report template ships a `section_plan_defaults.yaml`:

```yaml
# packages/core/.../templates/stock_initiation_v2/section_plan_defaults.yaml
template_id: stock_initiation_v2
sections:
  - section_id: executive_summary
    title: Executive Summary
    artifacts:
      - { artifact_id: dcf_base_valuation,       fidelity: headline }
      - { artifact_id: peer_multiple_panel,      fidelity: headline }
      - { artifact_id: price_target_consensus,   fidelity: headline }

  - section_id: investment_thesis
    title: Investment Thesis
    artifacts:
      - { artifact_id: business_quality_panel,   fidelity: summary }
      - { artifact_id: growth_drivers,           fidelity: summary }

  - section_id: valuation_dcf
    title: Discounted Cash Flow Valuation
    artifacts:
      - { artifact_id: dcf_base_valuation,       fidelity: full }
      - { artifact_id: sensitivity_grid,         fidelity: full }
      - { artifact_id: cost_of_capital_panel,    fidelity: summary }

  - section_id: valuation_comps
    title: Relative Valuation
    artifacts:
      - { artifact_id: peer_multiple_panel,      fidelity: full }
      - { artifact_id: historical_multiple_trends, fidelity: summary }
      - { artifact_id: football_field_chart,     fidelity: full }

  # ...
```

Template defaults are the predictable baseline. Without any planner override, the same template always renders the same sections at the same fidelity levels.

### 4.2 Planner override

Stage 5 planner emits a delta, not a full plan:

```python
class SectionPlanOverride(BaseModel):
    section_id: str
    operation: Literal["add", "remove", "change_fidelity", "add_brief"]
    artifact_id: str | None = None     # required for add/remove/change_fidelity
    fidelity: Fidelity | None = None   # required for add/change_fidelity
    drafter_brief: str | None = None   # required for add_brief


class PlannerOverrides(BaseModel):
    template_id: str
    overrides: list[SectionPlanOverride]
    rationale: str  # planner's stated reason; preserved in run trace for audit
```

Example: user asks "compare valuation to peers heavily." Planner emits:

```yaml
template_id: stock_initiation_v2
overrides:
  - { section_id: valuation_dcf, operation: change_fidelity, artifact_id: dcf_base_valuation, fidelity: summary }
  - { section_id: valuation_comps, operation: change_fidelity, artifact_id: historical_multiple_trends, fidelity: full }
  - { section_id: valuation_comps, operation: add_brief,
      drafter_brief: "User prompt requested heavy peer comparison emphasis." }
rationale: "User requested emphasis on relative valuation over absolute DCF."
```

### 4.3 Override resolver

Stage 7a's first job is to apply overrides to the template default in declaration order:

```python
def resolve_section_plan(
    template_defaults: ReportSectionPlan,
    overrides: PlannerOverrides | None,
) -> ReportSectionPlan:
    plan = template_defaults.model_copy(deep=True)
    if overrides is None:
        return plan
    applied = []
    for ov in overrides.overrides:
        section = next((s for s in plan.sections if s.section_id == ov.section_id), None)
        if section is None:
            raise PlanResolutionError(f"override references unknown section {ov.section_id!r}")
        _apply_override(section, ov)
        applied.append(_describe(ov))
    plan.overrides_applied = applied
    return plan
```

Override failures (unknown section, malformed delta, fidelity escalation past `full`) are hard errors at Stage 7a, surfaced before any rendering happens.

---

## 5. Materialization algorithm

```python
def materialize(
    section_plan: ReportSectionPlan,
    artifacts: dict[str, RenderableArtifact],  # from Stage 6
) -> str:
    # Step 1: precondition check
    referenced_ids = {ref.artifact_id for s in section_plan.sections for ref in s.artifacts}
    missing = referenced_ids - artifacts.keys()
    if missing:
        raise MaterializationError(f"section_plan references {missing}, not in Stage 6 output")

    # Step 2: highest-fidelity-wins per artifact_id (B3 dedup)
    highest = _highest_fidelity_per_artifact(section_plan)
    #   e.g. dcf_base_valuation appears at HEADLINE (exec) and FULL (val_dcf) → FULL

    # Step 3: render per-section, dedup with back-references
    rendered_sites: dict[str, str] = {}  # artifact_id -> anchor of canonical render
    out = []
    for section in section_plan.sections:
        out.append(f"\n## {section.title}\n")
        if section.drafter_brief:
            out.append(f"_Brief: {section.drafter_brief}_\n")

        for ref in section.artifacts:
            art = artifacts[ref.artifact_id]
            anchor = f"#{section.section_id}__{ref.artifact_id}"

            if ref.artifact_id not in rendered_sites:
                # First and canonical site. Render at highest fidelity needed anywhere.
                canonical_level = highest[ref.artifact_id]
                out.append(f'<a id="{anchor.lstrip("#")}"></a>\n')
                out.append(art.to_markdown(canonical_level))
                rendered_sites[ref.artifact_id] = anchor
                out.append("\n")
            else:
                # Subsequent site. Back-reference to canonical.
                canonical = rendered_sites[ref.artifact_id]
                if ref.fidelity == highest[ref.artifact_id]:
                    out.append(f"_See [{ref.artifact_id}]({canonical}) above._\n")
                else:
                    # Lower fidelity wanted here; emit a headline as a recap.
                    out.append(art.to_markdown(Fidelity.HEADLINE))
                    out.append(f"_Full detail: [{ref.artifact_id}]({canonical}) above._\n")
                out.append("\n")

    return "".join(out)
```

### 5.1 Canonical-site rule

The **first section in document order** that requests an artifact becomes the canonical site, and it renders at the **highest fidelity any section requests**. Later sections back-reference. This keeps the executive summary lean (later sections "borrow up" to the full-fidelity copy in the body).

### 5.2 Headline recap for lower-fidelity duplicates

If a later section asked for a `headline` of an artifact that's already rendered at `full` earlier, we don't pretend it isn't there — we emit a one-line recap pointing back. Avoids the bad UX of the drafter thinking it has nothing to say.

### 5.3 Orphan artifact policy

Artifacts produced in Stage 6 but referenced by no section in the resolved `section_plan` are **dropped silently** but logged to the run trace. Rationale: helpers may produce auxiliary artifacts (e.g., `cost_of_capital_panel` as a sub-artifact of DCF) that the template doesn't need exposed. Verifier sees the full Stage 6 output map, so dropped artifacts still get shape-validated.

---

## 6. Drafter prompt structure (Stage 7b)

The materialized output is what the drafter sees, plus a small system frame:

```
You are drafting <template_id> for <ticker>. Each section below contains
the artifacts you must base your prose on. Render exactly the sections
shown, in order, with this structure:

  ## Section Title
  <your prose, grounded in the artifact rendered below>
  <render of the artifact, verbatim>

Rules:
  - Do not invent numbers not present in artifacts.
  - For back-referenced artifacts (`See ... above`), assume the reader
    has already seen the canonical site; cite by section, not by
    re-stating the full data.
  - Headlines anchor the section thesis; full artifacts support detail.

[materialized markdown follows]
```

No tool schemas. No raw JSON. No helper docs. The drafter's working set is just the materialized prompt.

---

## 7. Token cost projection

Worst-case current naive baseline (no redesign): ~18k tokens of artifact payload.

After redesign:

| Stage | Cost | Notes |
|---|---|---|
| Headlines across all sections (~12 artifacts × ~60 tokens avg) | ~0.7k | One per section appearance, but dedup keeps it small |
| Summaries (~6 artifacts × ~300 tokens avg) | ~1.8k | Mostly in supporting sections |
| Full renders (~5 artifacts × ~1.5k tokens avg) | ~7.5k | One per artifact, at canonical site only |
| Back-references and section frames | ~0.3k | Cheap |
| Section headers + drafter briefs | ~0.4k | |
| **Total** | **~10.7k** | Conservative; aggressive dedup can push to ~6-9k |

Net savings vs. naive: **~40-60% reduction**. Bigger savings come from templates that repeat artifacts across many sections.

---

## 8. Verifier integration

New verifier issue types (added to the closed 14-issue enum or as a new sub-enum, TBD with #10):

| Issue | Detection point | Cause |
|---|---|---|
| `block_artifact_too_large` | Stage 7a render | Rendered output exceeds hard cap for its fidelity |
| `block_plan_artifact_missing` | Stage 7a precondition | section_plan references an artifact not in Stage 6 output |
| `block_section_plan_invalid` | Stage 7a override resolution | Override references unknown section / malformed delta |
| `block_headline_missing_quantitative` | Stage 7a render | A `headline` render produced no numeric anchor |

Stage 8 verifier consumes both the Pydantic models (shape) and the materialized markdown (prose grounding). Stage 7a hands both forward.

---

## 9. Testing strategy

Stage 7a is pure-Python and deterministic. Test coverage:

1. **Override resolver:** apply each override operation, verify section state.
2. **Dedup:** same artifact in 3 sections at headline/summary/full → renders once at full, two back-references.
3. **Canonical-site ordering:** artifact first requested at `summary` in section A and at `full` in section B → renders at `full` in A (highest anywhere), back-reference in B.
4. **Orphan handling:** Stage 6 produces artifact X, section_plan ignores X → not rendered, logged.
5. **Token budgets:** synthetic artifact that exceeds hard cap → raises `block_artifact_too_large`.
6. **Precondition:** section_plan references unknown artifact → raises `block_plan_artifact_missing` before rendering starts.
7. **Headline quantitative check:** synthetic artifact with non-numeric headline → raises `block_headline_missing_quantitative`.

No LLM calls in this stage means tests run in milliseconds.

---

## 10. Implementation order

This is foundation work that needs to land before any Wave 0 helper task that produces non-trivial artifacts (so #1, #6, #12 all benefit).

1. **`Fidelity` enum + `RenderableArtifact` base class** in `openlia.artifacts`.
2. **`SectionPlan` / `PlannerOverrides` / resolver** in `openlia_server.services.section_plan`.
3. **`materialize()` algorithm** in `openlia_server.services.materialization`.
4. **First-template default** (`stock_initiation_v2`) as the reference example.
5. **Wire into RunnerV2** as Stage 7a between Stage 6 (helper execution) and Stage 7b (drafter).
6. **Verifier issue types** added in coordination with task #10.

Per-template `section_plan_defaults.yaml` files are authored alongside the helpers that populate them — each new helper task that produces a new ArtifactType also updates the relevant template defaults.

---

## 11. Open questions parked for later

- **Streaming materialization:** for very large reports, can we materialize section-by-section and stream to a per-section drafter call? Defer until we hit context-window pressure.
- **Multimodal artifact handling:** charts as image attachments vs. embedded markdown. Defer until first chart-heavy helper lands (likely #6).
- **Cross-report dedup:** if a user runs the same report twice with the same artifacts, can we reuse prior renders? Caching question; defer to deployment.
- **Drafter feedback loop:** if the drafter notes "this headline is misleading," should it be able to request a fidelity bump? Would re-introduce Option-A-style ad-hoc tool use; explicitly deferred per Option B.
