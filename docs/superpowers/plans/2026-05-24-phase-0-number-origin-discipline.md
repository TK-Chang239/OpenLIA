# Phase 0: Number-Origin Discipline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it structurally impossible for the v2.3 equity-research engine to ship a number that isn't either a sourced fact, a computed fact, or an explicitly-labeled analyst estimate.

**Architecture:** Three coordinated changes. (1) Add `EstimateSource` as a fifth `Provenance` variant so judgment numbers have an honest origin type. (2) Let WRITE emit two new inline marker shapes — `{{DERIVE:...}}` for arithmetic over existing facts and `{{ESTIMATE:...}}` for analyst projections — which a deterministic mint step in `WriteStage` resolves into real `BundleFact` entries (`ComputedSource` and `EstimateSource` respectively) before VERIFY sees the body. (3) Add a deterministic `UNCITED_NUMBER` check in `VerifyStage._deterministic_checks` that flags any digit-bearing token outside an exempt set as `HIGH`, routing the section to rewrite. After this, every numeric in shipped output traces to a typed origin; the LLM has no way to type a naked number.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, uv. Files live under `packages/core/src/openlia/llm/runtime/report_v2_3/` and `packages/core/tests/test_runtime/test_report_v2_3/`.

**Population path decision (resolved):** Derived/estimated facts are minted **on-demand, mid-WRITE, deterministically from inline markers in the writer's body**. WRITE remains a single LLM call per mandate (no tool-loop), so the parallel-section model is preserved. A small in-stage cache dedups identical derivations across sections by fact_id. Rejected alternative: speculative COMPUTE-time emission would waste compute on facts no section cites and cannot mint estimates (which are inherently judgment formed at write-time).

---

## File Structure

**New files:**
- `packages/core/src/openlia/llm/runtime/report_v2_3/derivations.py` — pure derivation functions (`growth_rate`, `yoy_delta`, `ratio`) producing `BundleFact` with `ComputedSource`
- `packages/core/tests/test_runtime/test_report_v2_3/test_derivations.py`
- `packages/core/tests/test_runtime/test_report_v2_3/test_mint_inline_facts.py`
- `packages/core/tests/test_runtime/test_report_v2_3/test_uncited_number_check.py`

**Modified files:**
- `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py` — `EstimateSource` + `SourceType.ESTIMATE`, extended `Provenance` union, updated `render_citation`, new `DERIVE_RE` / `ESTIMATE_RE` regexes
- `packages/core/src/openlia/llm/runtime/report_v2_3/stages/write.py` — call `mint_inline_facts` between `client.write` and `_coerce_section`
- `packages/core/src/openlia/llm/runtime/report_v2_3/stages/verify.py` — add `_check_uncited_numbers` to `_deterministic_checks`
- `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — extend `WRITE_SYSTEM_PROMPT` with the three-marker grammar
- `packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py` — add `EstimateSource` round-trip + `render_citation` cases
- `packages/core/tests/test_runtime/test_report_v2_3/test_write_stage.py` — add end-to-end mint-during-write test
- `packages/core/tests/test_runtime/test_report_v2_3/test_verify_stage.py` — add uncited-number deterministic flag tests

---

## Task 1: Add `EstimateSource` to the schema

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py:77-82` (SourceType enum), `schemas.py:151-163` (add EstimateSource class + extend Provenance), `schemas.py:623-639` (render_citation)
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py`

- [ ] **Step 1: Write failing test for `SourceType.ESTIMATE` and `EstimateSource` round-trip**

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py`:

```python
from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    EstimateSource,
    SourceType,
    render_citation,
)


def test_estimate_source_round_trips_through_provenance_union():
    fact = BundleFact(
        id="upside_pct",
        label="Implied upside",
        value=0.10,
        unit="percent",
        source=EstimateSource(
            basis="projection from margin-expansion thesis",
            derived_from=[],
            stage="write",
        ),
    )
    # Pydantic discriminator routes on `type`; round-trip via JSON
    # proves the union accepts the new variant.
    dumped = fact.model_dump_json()
    restored = BundleFact.model_validate_json(dumped)
    assert isinstance(restored.source, EstimateSource)
    assert restored.source.type == SourceType.ESTIMATE
    assert restored.source.basis == "projection from margin-expansion thesis"


def test_render_citation_handles_estimate_source():
    fact = BundleFact(
        id="upside_pct",
        label="Implied upside",
        value=0.10,
        unit="percent",
        source=EstimateSource(
            basis="margin-expansion thesis",
            derived_from=[],
            stage="write",
        ),
    )
    assert render_citation(fact) == "Estimate: margin-expansion thesis."


def test_estimate_source_records_derived_from_when_supplied():
    fact = BundleFact(
        id="upside_to_target",
        label="Upside to target",
        value=0.15,
        unit="percent",
        source=EstimateSource(
            basis="target $120 vs current price",
            derived_from=["price_target", "px_last"],
            stage="write",
        ),
    )
    assert fact.source.derived_from == ["price_target", "px_last"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py -k "estimate" -v`
Expected: 3 ImportError / AttributeError failures — `EstimateSource` does not exist.

- [ ] **Step 3: Add `SourceType.ESTIMATE`**

In `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py`, modify the SourceType enum (currently lines 77-82):

```python
class SourceType(StrEnum):
    DATA_PROVIDER = "data_provider"  # EODHD / FMP — quantitative
    WEB = "web"  # qualitative / narrative
    FILING = "filing"  # 10-K, 10-Q, 8-K, etc.
    COMPUTED = "computed"  # derived from other facts
    ESTIMATE = "estimate"  # analyst judgment — explicit, no external source
```

- [ ] **Step 4: Add `EstimateSource` class and extend the `Provenance` union**

In `schemas.py`, immediately after the `ComputedSource` class (currently ends around line 160), add:

```python
class EstimateSource(BaseModel):
    """An explicit analyst estimate. No external provider produced this — it
    is judgment formed at write time. Made first-class so estimates do not
    masquerade as sourced facts and so the reader sees the distinction in
    the footnote."""

    type: Literal[SourceType.ESTIMATE] = SourceType.ESTIMATE
    basis: str = Field(
        ...,
        min_length=1,
        description="Short prose explaining why the analyst holds this view.",
    )
    derived_from: list[str] = Field(
        default_factory=list,
        description="Optional: fact_ids of measured/computed facts that informed "
        "the estimate. Empty when the estimate is pure thesis.",
    )
    stage: Literal["synthesize", "write"]


Provenance = (
    DataProviderSource | WebSource | FilingSource | ComputedSource | EstimateSource
)
```

- [ ] **Step 5: Update `render_citation` with the estimate case**

In `schemas.py`, modify `render_citation` (currently lines 623-639). Add the new branch after the `ComputedSource` branch and before the `raise TypeError`:

```python
def render_citation(fact: BundleFact) -> str:
    """Render a single footnote line from provenance. Format is owned here, so
    it is consistent everywhere."""
    s = fact.source
    if isinstance(s, DataProviderSource):
        stmt = f", {s.statement}" if s.statement else ""
        return f"{s.provider}{stmt} ({s.endpoint}), {s.period}."
    if isinstance(s, WebSource):
        pub = f"{s.publisher}. " if s.publisher else ""
        title = s.title or s.url
        return f"{pub}{title}. {s.url}"
    if isinstance(s, FilingSource):
        page = f", p. {s.page}" if s.page else ""
        return f"{s.company} {s.form_type} ({s.fiscal_period}){page}."
    if isinstance(s, ComputedSource):
        return f"Author calculation: {s.method}."
    if isinstance(s, EstimateSource):
        return f"Estimate: {s.basis}."
    raise TypeError(f"Unknown source type: {type(s)}")
```

- [ ] **Step 6: Verify the discriminator still works — `BundleFact.source` uses `Field(..., discriminator="type")`**

Read `schemas.py:196` to confirm. If the existing line is `source: Provenance = Field(..., discriminator="type")`, no change is needed — Pydantic re-routes on the extended union automatically because all variants carry distinct `type: Literal[...]` fields.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py -k "estimate" -v`
Expected: 3 passes.

- [ ] **Step 8: Run the full schema test file to confirm no regression**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py -v`
Expected: all previously-passing tests still pass; 3 new tests pass.

- [ ] **Step 9: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py
git commit -m "feat(report_v2_3): add EstimateSource as fifth Provenance variant"
```

---

## Task 2: Deterministic derivation library

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2_3/derivations.py`
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_derivations.py`

- [ ] **Step 1: Write failing tests for the three derivation primitives**

Create `packages/core/tests/test_runtime/test_report_v2_3/test_derivations.py`:

```python
"""Unit tests for the deterministic derivation library.

The library exists so writers cannot type naked arithmetic. Each function
takes BundleFacts, runs pure math, and emits a new BundleFact with a
ComputedSource derived_from chain the bundle validator will walk.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openlia.llm.runtime.report_v2_3.derivations import (
    DerivationError,
    growth_rate,
    ratio,
    yoy_delta,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    ComputedSource,
    DataProviderSource,
    SourceType,
)


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="FY2025",
        retrieved_at=datetime.now(UTC),
    )


def test_growth_rate_computes_pct_change_and_attaches_provenance():
    cur = BundleFact(id="rev_fy25", label="Revenue FY25", value=125.0, source=_src())
    prev = BundleFact(id="rev_fy24", label="Revenue FY24", value=100.0, source=_src())

    out = growth_rate(cur, prev, new_id="rev_growth_yoy", label="Revenue YoY")

    assert isinstance(out, BundleFact)
    assert out.id == "rev_growth_yoy"
    assert out.value == pytest.approx(0.25)
    assert out.unit == "percent"
    assert isinstance(out.source, ComputedSource)
    assert out.source.method == "growth_rate"
    assert out.source.derived_from == ["rev_fy25", "rev_fy24"]


def test_yoy_delta_emits_absolute_difference():
    cur = BundleFact(id="op_inc_fy25", label="Op income FY25", value=42.0, source=_src())
    prev = BundleFact(id="op_inc_fy24", label="Op income FY24", value=30.0, source=_src())

    out = yoy_delta(cur, prev, new_id="op_inc_yoy", label="Op income YoY")

    assert out.value == pytest.approx(12.0)
    assert out.source.method == "yoy_delta"
    assert out.source.derived_from == ["op_inc_fy25", "op_inc_fy24"]


def test_ratio_emits_numerator_over_denominator():
    num = BundleFact(id="gross_profit", label="Gross profit", value=60.0, source=_src())
    den = BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src())

    out = ratio(num, den, new_id="gross_margin", label="Gross margin")

    assert out.value == pytest.approx(0.60)
    assert out.source.method == "ratio"
    assert out.source.derived_from == ["gross_profit", "rev_ttm"]


def test_growth_rate_raises_on_zero_denominator():
    cur = BundleFact(id="x", label="x", value=10.0, source=_src())
    prev = BundleFact(id="y", label="y", value=0.0, source=_src())
    with pytest.raises(DerivationError):
        growth_rate(cur, prev, new_id="z", label="z")


def test_growth_rate_raises_on_non_numeric_input():
    cur = BundleFact(id="x", label="x", value="some_string", source=_src())
    prev = BundleFact(id="y", label="y", value=100.0, source=_src())
    with pytest.raises(DerivationError):
        growth_rate(cur, prev, new_id="z", label="z")


def test_ratio_raises_on_zero_denominator():
    num = BundleFact(id="x", label="x", value=10.0, source=_src())
    den = BundleFact(id="y", label="y", value=0.0, source=_src())
    with pytest.raises(DerivationError):
        ratio(num, den, new_id="z", label="z")
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_derivations.py -v`
Expected: ImportError — module does not exist.

- [ ] **Step 3: Implement `derivations.py`**

Create `packages/core/src/openlia/llm/runtime/report_v2_3/derivations.py`:

```python
"""Pure derivation primitives for writer-time arithmetic.

Writers must never type a calculated number. When a section needs a
derived value (YoY growth, margin, ratio), the writer emits a
``{{DERIVE:method|input_ids|new_id}}`` marker and the WriteStage mint
step calls into one of the functions here. Each returns a ``BundleFact``
carrying a ``ComputedSource`` with ``derived_from`` pointing at the
inputs — so the bundle validator's existing chain walk treats it
identically to any COMPUTE-time fact.

Add new methods here, not in stages or clients. The set is deliberately
small — these cover what writers actually claim in prose. Anything
bigger (DCF, comps, sensitivity) belongs in the valuation/ package,
where COMPUTE already runs it.
"""

from __future__ import annotations

from numbers import Real

from .schemas import BundleFact, ComputedSource


class DerivationError(RuntimeError):
    """Raised when a derivation cannot run — missing inputs, divide-by-zero,
    non-numeric facts. The mint step catches this and the section is routed
    back through WRITE with the failure surfaced."""


def _scalar(fact: BundleFact) -> float:
    if not isinstance(fact.value, Real) or isinstance(fact.value, bool):
        raise DerivationError(
            f"Fact '{fact.id}' is non-numeric (value={fact.value!r}); "
            "derivations require scalar numeric inputs."
        )
    return float(fact.value)


def growth_rate(
    current: BundleFact, prior: BundleFact, *, new_id: str, label: str
) -> BundleFact:
    """(current - prior) / prior. Returns a fraction (0.25 = 25%)."""
    cur_v = _scalar(current)
    prev_v = _scalar(prior)
    if prev_v == 0:
        raise DerivationError(
            f"growth_rate: prior value is zero for facts "
            f"({current.id}, {prior.id}); cannot divide."
        )
    return BundleFact(
        id=new_id,
        label=label,
        value=(cur_v - prev_v) / prev_v,
        unit="percent",
        source=ComputedSource(method="growth_rate", derived_from=[current.id, prior.id]),
    )


def yoy_delta(
    current: BundleFact, prior: BundleFact, *, new_id: str, label: str
) -> BundleFact:
    """current - prior. Absolute change in the input's unit."""
    cur_v = _scalar(current)
    prev_v = _scalar(prior)
    return BundleFact(
        id=new_id,
        label=label,
        value=cur_v - prev_v,
        unit=current.unit,
        source=ComputedSource(method="yoy_delta", derived_from=[current.id, prior.id]),
    )


def ratio(
    numerator: BundleFact, denominator: BundleFact, *, new_id: str, label: str
) -> BundleFact:
    """numerator / denominator. Returns a fraction; unit defaults to None
    so the formatter renders a clean number (caller may set 'percent' /
    'x' downstream if appropriate)."""
    num_v = _scalar(numerator)
    den_v = _scalar(denominator)
    if den_v == 0:
        raise DerivationError(
            f"ratio: denominator value is zero for facts "
            f"({numerator.id}, {denominator.id}); cannot divide."
        )
    return BundleFact(
        id=new_id,
        label=label,
        value=num_v / den_v,
        unit=None,
        source=ComputedSource(
            method="ratio", derived_from=[numerator.id, denominator.id]
        ),
    )


# Registry the mint step looks methods up in. Keep keys in sync with
# the DERIVE marker grammar documented in WRITE_SYSTEM_PROMPT.
DERIVATION_REGISTRY: dict[str, callable] = {
    "growth_rate": growth_rate,
    "yoy_delta": yoy_delta,
    "ratio": ratio,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_derivations.py -v`
Expected: 6 passes.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/derivations.py packages/core/tests/test_runtime/test_report_v2_3/test_derivations.py
git commit -m "feat(report_v2_3): add deterministic derivation primitives"
```

---

## Task 3: Add `DERIVE` / `ESTIMATE` regexes to schemas

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py:503-505` (placeholder regexes)
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py`

- [ ] **Step 1: Write failing tests for the new marker regexes**

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py`:

```python
from openlia.llm.runtime.report_v2_3.schemas import DERIVE_RE, ESTIMATE_RE


def test_derive_re_matches_three_pipe_separated_fields():
    body = "Revenue grew {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} year over year."
    matches = DERIVE_RE.findall(body)
    assert matches == [("growth_rate", "rev_fy25,rev_fy24", "rev_growth_yoy")]


def test_derive_re_rejects_uppercase_method_name():
    # Methods are lowercase identifiers; uppercase should not match.
    body = "X {{DERIVE:GROWTH_RATE|a,b|c}}"
    assert DERIVE_RE.findall(body) == []


def test_estimate_re_matches_four_pipe_separated_fields():
    body = (
        "We see {{ESTIMATE:upside_pct|0.10|percent|"
        "projection from margin-expansion thesis}} of upside."
    )
    matches = ESTIMATE_RE.findall(body)
    assert matches == [
        ("upside_pct", "0.10", "percent", "projection from margin-expansion thesis")
    ]


def test_estimate_re_accepts_empty_unit():
    body = "{{ESTIMATE:rating_score|7.5||composite of qual factors}}"
    matches = ESTIMATE_RE.findall(body)
    assert matches == [("rating_score", "7.5", "", "composite of qual factors")]


def test_estimate_re_accepts_negative_values():
    body = "{{ESTIMATE:downside_pct|-0.15|percent|bear case 12mo}}"
    matches = ESTIMATE_RE.findall(body)
    assert matches == [("downside_pct", "-0.15", "percent", "bear case 12mo")]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py -k "_re_" -v`
Expected: ImportError — DERIVE_RE / ESTIMATE_RE not defined.

- [ ] **Step 3: Add the regexes to `schemas.py`**

In `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py`, find the existing placeholder regex block (currently lines 503-505):

```python
CITE_RE = re.compile(r"\{\{CITE:([a-zA-Z0-9_]+)\}\}")
FIG_RE = re.compile(r"\{\{FIG:([a-zA-Z0-9_]+)\}\}")
```

Extend to:

```python
CITE_RE = re.compile(r"\{\{CITE:([a-zA-Z0-9_]+)\}\}")
FIG_RE = re.compile(r"\{\{FIG:([a-zA-Z0-9_]+)\}\}")

# Inline minting grammar — resolved by WriteStage before VERIFY sees the body.
# DERIVE: {{DERIVE:<method>|<input_fact_ids_csv>|<new_fact_id>}}
#   method ∈ DERIVATION_REGISTRY keys (lowercase identifiers).
#   input_fact_ids_csv is a comma-separated list of bundle fact_ids the
#     method consumes.
#   new_fact_id becomes the BundleFact.id of the resulting ComputedSource fact.
DERIVE_RE = re.compile(
    r"\{\{DERIVE:([a-z_]+)\|([a-zA-Z0-9_,]+)\|([a-zA-Z0-9_]+)\}\}"
)

# ESTIMATE: {{ESTIMATE:<new_fact_id>|<value>|<unit>|<basis>}}
#   new_fact_id becomes the BundleFact.id of the resulting EstimateSource fact.
#   value is a signed decimal (no thousands separator); unit may be empty.
#   basis is free prose with no '}}' (regex is non-greedy on '}').
ESTIMATE_RE = re.compile(
    r"\{\{ESTIMATE:([a-zA-Z0-9_]+)\|(-?\d+(?:\.\d+)?)\|([a-zA-Z_%]*)\|([^}]+?)\}\}"
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py -k "_re_" -v`
Expected: 5 passes.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py
git commit -m "feat(report_v2_3): add DERIVE and ESTIMATE marker regexes"
```

---

## Task 4: Mint helper — resolve DERIVE/ESTIMATE markers into BundleFacts

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_v2_3/stages/_mint.py`
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_mint_inline_facts.py`

- [ ] **Step 1: Write failing tests for `mint_inline_facts`**

Create `packages/core/tests/test_runtime/test_report_v2_3/test_mint_inline_facts.py`:

```python
"""Unit tests for the mint step that resolves DERIVE/ESTIMATE markers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    ComputedSource,
    DataProviderSource,
    EstimateSource,
    ResearchBundle,
    SectionMandate,
)
from openlia.llm.runtime.report_v2_3.stages._mint import MintError, mint_inline_facts


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="FY2025",
        retrieved_at=datetime.now(UTC),
    )


def _bundle() -> ResearchBundle:
    return ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_fy25": BundleFact(id="rev_fy25", label="Revenue FY25", value=125.0, source=_src()),
            "rev_fy24": BundleFact(id="rev_fy24", label="Revenue FY24", value=100.0, source=_src()),
        },
    )


def _mandate(section_id: str = "financials") -> SectionMandate:
    return SectionMandate(
        section_id=section_id,
        covers="financial line items",
        does_not_cover="overview",
        chart_ids=[],
        relevant_fact_ids=["rev_fy25", "rev_fy24"],
    )


def test_derive_marker_resolves_to_computed_fact_and_cite_marker():
    bundle = _bundle()
    body = "Revenue grew {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} YoY."

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert new_body == "Revenue grew {{CITE:rev_growth_yoy}} YoY."
    assert len(new_facts) == 1
    fact = new_facts[0]
    assert fact.id == "rev_growth_yoy"
    assert fact.value == pytest.approx(0.25)
    assert isinstance(fact.source, ComputedSource)
    assert fact.source.derived_from == ["rev_fy25", "rev_fy24"]


def test_estimate_marker_resolves_to_estimate_fact_and_cite_marker():
    bundle = _bundle()
    body = (
        "We see {{ESTIMATE:upside_pct|0.10|percent|projection from margin-expansion thesis}} "
        "of upside."
    )

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert new_body == "We see {{CITE:upside_pct}} of upside."
    assert len(new_facts) == 1
    fact = new_facts[0]
    assert fact.id == "upside_pct"
    assert fact.value == pytest.approx(0.10)
    assert fact.unit == "percent"
    assert isinstance(fact.source, EstimateSource)
    assert fact.source.basis == "projection from margin-expansion thesis"
    assert fact.source.stage == "write"


def test_repeated_identical_derive_dedupes_to_single_new_fact():
    bundle = _bundle()
    body = (
        "{{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} versus "
        "{{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} prior."
    )

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert new_body.count("{{CITE:rev_growth_yoy}}") == 2
    # Only one new fact even though the marker appeared twice.
    assert len(new_facts) == 1


def test_derive_marker_with_unknown_input_fact_raises_mint_error():
    bundle = _bundle()
    body = "X {{DERIVE:growth_rate|rev_fy25,rev_fy23|x}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "rev_fy23" in str(exc.value)


def test_derive_marker_with_unknown_method_raises_mint_error():
    bundle = _bundle()
    body = "X {{DERIVE:nonexistent_method|rev_fy25,rev_fy24|x}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "nonexistent_method" in str(exc.value)


def test_derive_marker_with_id_colliding_against_bundle_raises():
    bundle = _bundle()
    # rev_fy25 already exists with a different source — the LLM trying to
    # mint over it must fail loudly.
    body = "X {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_fy25}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "rev_fy25" in str(exc.value)


def test_mint_step_passes_through_body_with_no_markers_untouched():
    bundle = _bundle()
    body = "No markers here. Revenue {{CITE:rev_fy25}} stayed flat."
    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())
    assert new_body == body
    assert new_facts == []
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_mint_inline_facts.py -v`
Expected: ImportError — `stages._mint` does not exist.

- [ ] **Step 3: Implement the mint helper**

Create `packages/core/src/openlia/llm/runtime/report_v2_3/stages/_mint.py`:

```python
"""Resolve inline DERIVE/ESTIMATE markers into BundleFacts.

WriteStage calls into this between ``client.write`` and ``_coerce_section``.
Each resolved marker becomes a real BundleFact (ComputedSource for derive,
EstimateSource for estimate) that the engine adds to ``state.bundle`` and a
``{{CITE:<new_id>}}`` marker in the body. After this step runs, every
numeric claim a writer made traces to a typed origin, and VERIFY's
deterministic uncited-number check has nothing legitimate left to flag.

Dedup rule: if a marker's ``new_id`` is already present in the bundle and
the existing fact was minted by an identical call (same method + same
derived_from for derive; same basis + value for estimate), reuse it. If
the id exists with different content, raise — silent overwrite would
break the same-figure-everywhere invariant.
"""

from __future__ import annotations

import logging

from ..derivations import DERIVATION_REGISTRY, DerivationError
from ..schemas import (
    DERIVE_RE,
    ESTIMATE_RE,
    BundleFact,
    ComputedSource,
    EstimateSource,
    ResearchBundle,
    SectionMandate,
)

log = logging.getLogger(__name__)


class MintError(RuntimeError):
    """Raised when a marker cannot be resolved. Routed back through WRITE."""


def mint_inline_facts(
    body: str,
    bundle: ResearchBundle,
    mandate: SectionMandate,
) -> tuple[str, list[BundleFact]]:
    """Return (rewritten_body, new_facts).

    Walks DERIVE markers first, then ESTIMATE markers. Both are replaced
    by ``{{CITE:<new_id>}}`` in the returned body. ``new_facts`` carries
    every BundleFact the caller must add to ``state.bundle`` — caller is
    responsible for the insertion (matches the COMPUTE pattern of
    rebuilding the bundle via ResearchBundle constructor so the validator
    re-runs over the combined facts).
    """
    new_facts: list[BundleFact] = []
    seen_ids: set[str] = set()

    # 1) DERIVE
    def _derive_sub(m: "re.Match[str]") -> str:
        method_name, inputs_csv, new_id = m.group(1), m.group(2), m.group(3)
        input_ids = [s for s in inputs_csv.split(",") if s]
        if method_name not in DERIVATION_REGISTRY:
            raise MintError(
                f"DERIVE: unknown method '{method_name}' in section "
                f"'{mandate.section_id}'. Known: {sorted(DERIVATION_REGISTRY)}."
            )
        for fid in input_ids:
            if fid not in bundle.facts:
                raise MintError(
                    f"DERIVE: input fact '{fid}' not in bundle "
                    f"(section '{mandate.section_id}', method '{method_name}')."
                )
        # Dedup: same new_id minted earlier in this section.
        if new_id in seen_ids:
            return f"{{{{CITE:{new_id}}}}}"
        # Collision against pre-existing bundle fact.
        if new_id in bundle.facts:
            raise MintError(
                f"DERIVE: new_id '{new_id}' collides with an existing bundle fact "
                f"(section '{mandate.section_id}'). Pick a unique id."
            )
        try:
            fact = DERIVATION_REGISTRY[method_name](
                *[bundle.facts[fid] for fid in input_ids],
                new_id=new_id,
                label=_label_from_id(new_id),
            )
        except DerivationError as exc:
            raise MintError(
                f"DERIVE: {method_name} failed in section "
                f"'{mandate.section_id}': {exc}"
            ) from exc
        new_facts.append(fact)
        seen_ids.add(new_id)
        return f"{{{{CITE:{new_id}}}}}"

    body = DERIVE_RE.sub(_derive_sub, body)

    # 2) ESTIMATE
    def _estimate_sub(m: "re.Match[str]") -> str:
        new_id, value_str, unit, basis = m.group(1), m.group(2), m.group(3), m.group(4)
        value = float(value_str)
        if new_id in seen_ids:
            return f"{{{{CITE:{new_id}}}}}"
        if new_id in bundle.facts:
            raise MintError(
                f"ESTIMATE: new_id '{new_id}' collides with an existing bundle "
                f"fact (section '{mandate.section_id}'). Pick a unique id."
            )
        fact = BundleFact(
            id=new_id,
            label=_label_from_id(new_id),
            value=value,
            unit=unit or None,
            source=EstimateSource(
                basis=basis.strip(),
                derived_from=[],
                stage="write",
            ),
        )
        new_facts.append(fact)
        seen_ids.add(new_id)
        return f"{{{{CITE:{new_id}}}}}"

    body = ESTIMATE_RE.sub(_estimate_sub, body)

    return body, new_facts


def _label_from_id(fact_id: str) -> str:
    """fact_id 'rev_growth_yoy' -> 'Rev growth yoy'. Cheap, deterministic."""
    return fact_id.replace("_", " ").capitalize()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_mint_inline_facts.py -v`
Expected: 7 passes.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/stages/_mint.py packages/core/tests/test_runtime/test_report_v2_3/test_mint_inline_facts.py
git commit -m "feat(report_v2_3): mint helper resolves DERIVE/ESTIMATE markers"
```

---

## Task 5: Wire mint into WriteStage

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/stages/write.py:54-87` (run loop)
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_write_stage.py` (add cases)

- [ ] **Step 1: Write failing test for mint-during-write**

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_write_stage.py` (the file already has the `_bundle`, `_outline`, `_thesis`, `_state` helpers shown in the file — reuse them):

```python
from openlia.llm.runtime.report_v2_3.clients.writer import FakeWriterClient, WriterRequest
from openlia.llm.runtime.report_v2_3.schemas import (
    ComputedSource,
    EstimateSource,
    WrittenSection,
)


def test_write_stage_mints_derive_marker_into_computed_fact():
    state = _state(with_chart=False)
    # The fake writer emits a DERIVE marker the mint step must resolve.
    # rev_ttm (100.0) is already in the bundle; we need a second input,
    # so add a second fact to the bundle for this test.
    state.bundle.facts["rev_prior"] = BundleFact(
        id="rev_prior", label="Revenue prior", value=80.0, source=_src()
    )
    # Both mandates must reference rev_ttm/rev_prior so the WRITE coercer
    # does not strip the inputs of the derivation. The financials mandate
    # already does; widen it.
    state.thesis.mandates[1].relevant_fact_ids = ["rev_ttm", "gm", "rev_prior"]

    def responder(req: WriterRequest) -> WrittenSection:
        if req.section_mandate.section_id == "financials":
            return WrittenSection(
                section_id="financials",
                title="Financials",
                body=(
                    "Revenue grew "
                    "{{DERIVE:growth_rate|rev_ttm,rev_prior|rev_growth_yoy}} YoY."
                ),
            )
        return WrittenSection(
            section_id=req.section_mandate.section_id,
            title=req.section_mandate.section_id.title(),
            body="No numbers here.",
        )

    stage = WriteStage(FakeWriterClient(responder=responder))
    stage.run(state, StageContext())

    fin = next(s for s in state.sections if s.section_id == "financials")
    assert "{{DERIVE:" not in fin.body
    assert "{{CITE:rev_growth_yoy}}" in fin.body
    minted = state.bundle.facts["rev_growth_yoy"]
    assert isinstance(minted.source, ComputedSource)
    assert minted.source.derived_from == ["rev_ttm", "rev_prior"]


def test_write_stage_mints_estimate_marker_into_estimate_fact():
    state = _state(with_chart=False)

    def responder(req: WriterRequest) -> WrittenSection:
        if req.section_mandate.section_id == "overview":
            return WrittenSection(
                section_id="overview",
                title="Overview",
                body=(
                    "Moat {{CITE:moat}} supports "
                    "{{ESTIMATE:upside_pct|0.10|percent|"
                    "thesis-led margin expansion}} of upside."
                ),
            )
        return WrittenSection(
            section_id=req.section_mandate.section_id,
            title=req.section_mandate.section_id.title(),
            body="No numbers here.",
        )

    stage = WriteStage(FakeWriterClient(responder=responder))
    stage.run(state, StageContext())

    ov = next(s for s in state.sections if s.section_id == "overview")
    assert "{{ESTIMATE:" not in ov.body
    assert "{{CITE:upside_pct}}" in ov.body
    minted = state.bundle.facts["upside_pct"]
    assert isinstance(minted.source, EstimateSource)
    assert minted.source.basis == "thesis-led margin expansion"
    assert minted.source.stage == "write"


def test_write_stage_fails_loud_on_unknown_derive_input():
    state = _state(with_chart=False)

    def responder(req: WriterRequest) -> WrittenSection:
        return WrittenSection(
            section_id=req.section_mandate.section_id,
            title="T",
            body="{{DERIVE:growth_rate|missing_a,missing_b|x}}"
            if req.section_mandate.section_id == "financials"
            else "ok",
        )

    stage = WriteStage(FakeWriterClient(responder=responder))
    with pytest.raises(RuntimeError) as exc:
        stage.run(state, StageContext())
    assert "missing_a" in str(exc.value) or "missing_b" in str(exc.value)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_write_stage.py -k "mints or fails_loud" -v`
Expected: 3 failures — `{{DERIVE:...}}` markers passed through untouched (no mint step yet), or AttributeError on bundle missing the minted fact.

- [ ] **Step 3: Wire `mint_inline_facts` into `WriteStage.run`**

In `packages/core/src/openlia/llm/runtime/report_v2_3/stages/write.py`, modify the imports near the top:

```python
from ..schemas import (
    ChartSpec,
    ReportThesis,
    ResearchBundle,
    SectionMandate,
    VerifyIssue,
    WrittenSection,
)
from ..slots import V23Slot
from ..state import ReportState
from ._mint import MintError, mint_inline_facts
from .base import Stage, StageContext
```

Then modify `WriteStage.run` (currently lines 54-87). Insert the mint call between `self._client.write(request)` and `self._coerce_section(section, mandate)`. After all sections are minted, rebuild `state.bundle` so the validator re-runs over the combined facts (matches the COMPUTE pattern at `stages/compute.py:96-117`):

```python
    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        thesis = self._require_thesis(state)
        if state.bundle is None:
            raise RuntimeError("WRITE requires state.bundle.")

        prior_by_section: dict[str, WrittenSection] = {s.section_id: s for s in state.sections}
        critique_by_section: dict[str, list[VerifyIssue]] = (
            self._group_critique(state) if state.verify_result is not None else {}
        )
        chart_by_section: dict[str, list[ChartSpec]] = self._group_charts(thesis)

        new_sections: list[WrittenSection] = []
        minted_total: list[BundleFact] = []
        for mandate in thesis.mandates:
            relevant_facts = {
                fid: state.bundle.facts[fid]
                for fid in mandate.relevant_fact_ids
                if fid in state.bundle.facts
            }
            request = WriterRequest(
                section_mandate=mandate,
                thesis=thesis,
                language=state.language,
                length=state.length,
                relevant_facts=relevant_facts,
                assigned_charts=chart_by_section.get(mandate.section_id, []),
                prior_attempt=prior_by_section.get(mandate.section_id),
                critique=critique_by_section.get(mandate.section_id),
            )
            section = self._client.write(request)
            # Mint inline DERIVE/ESTIMATE markers BEFORE coercion so the
            # newly-minted CITE markers cannot be stripped (they will
            # always reference a fact_id we just added).
            new_body, new_facts = mint_inline_facts(section.body, state.bundle, mandate)
            if new_body != section.body:
                section = section.model_copy(update={"body": new_body})
            # Add minted facts to a buffer; we rebuild the bundle once at
            # the end so the model validator runs over the combined set.
            minted_total.extend(new_facts)
            # Temporarily extend bundle's view so subsequent sections can
            # dedup against this section's mints. ResearchBundle.add
            # raises on duplicate ids, which is the desired behavior.
            for fact in new_facts:
                state.bundle.add(fact)

            # Allow the just-minted facts through the mandate filter
            # before stripping out-of-mandate CITE markers.
            extended_mandate = mandate.model_copy(
                update={
                    "relevant_fact_ids": [
                        *mandate.relevant_fact_ids,
                        *[f.id for f in new_facts],
                    ]
                }
            )
            section = self._coerce_section(section, extended_mandate)
            new_sections.append(section)

        # Rebuild bundle once so the validator's derived_from chain check
        # runs over the combined facts (mirrors compute.py's pattern).
        if minted_total:
            state.bundle = ResearchBundle(
                tickers=state.bundle.tickers,
                facts=dict(state.bundle.facts),
            )

        state.sections = new_sections
        return state
```

Add `BundleFact` to the imports at the top of `write.py` (it currently imports `ChartSpec`, `ReportThesis`, `SectionMandate`, `VerifyIssue`, `WrittenSection` — extend with `BundleFact` and `ResearchBundle`).

- [ ] **Step 4: Run the new tests**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_write_stage.py -k "mints or fails_loud" -v`
Expected: 3 passes.

- [ ] **Step 5: Run the full write_stage test file to confirm no regression**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_write_stage.py -v`
Expected: all previously-passing tests still pass; 3 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/stages/write.py packages/core/tests/test_runtime/test_report_v2_3/test_write_stage.py
git commit -m "feat(report_v2_3): WriteStage mints DERIVE/ESTIMATE markers into bundle"
```

---

## Task 6: Deterministic `UNCITED_NUMBER` check in VERIFY

**Files:**
- Create: `packages/core/tests/test_runtime/test_report_v2_3/test_uncited_number_check.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/stages/verify.py:79-110` (`_deterministic_checks`)

- [ ] **Step 1: Write failing tests for the regex + exemptions**

Create `packages/core/tests/test_runtime/test_report_v2_3/test_uncited_number_check.py`:

```python
"""Unit tests for the deterministic UNCITED_NUMBER check.

The check runs in VERIFY's _deterministic_checks. Pre-VERIFY, the WRITE
mint step has already converted DERIVE/ESTIMATE markers into CITE
markers, so any digit-bearing token outside an exempt set is a real
fabrication and must route the section back to WRITE.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.schemas import (
    IssueKind,
    IssueSeverity,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.stages.verify import _check_uncited_numbers


def _ws(body: str, section_id: str = "s1") -> WrittenSection:
    return WrittenSection(section_id=section_id, title="T", body=body)


def test_passes_when_body_has_no_digits():
    issues = _check_uncited_numbers([_ws("Plain prose with no numbers at all.")])
    assert issues == []


def test_passes_when_every_number_is_inside_a_cite_marker():
    issues = _check_uncited_numbers(
        [_ws("Revenue {{CITE:rev_ttm}} grew {{CITE:rev_growth_yoy}} YoY.")]
    )
    assert issues == []


def test_passes_when_number_is_inside_a_fig_marker():
    issues = _check_uncited_numbers([_ws("See {{FIG:chart_3}} for the trend.")])
    assert issues == []


def test_flags_naked_dollar_amount_in_prose():
    issues = _check_uncited_numbers([_ws("Revenue of $60.9B last quarter.")])
    assert len(issues) == 1
    assert issues[0].kind == IssueKind.UNCITED_NUMBER
    assert issues[0].severity == IssueSeverity.HIGH
    assert "$60.9B" in issues[0].detail


def test_flags_naked_percentage_in_prose():
    issues = _check_uncited_numbers([_ws("Margins expanded 200 basis points.")])
    assert len(issues) == 1
    assert issues[0].kind == IssueKind.UNCITED_NUMBER


def test_flags_naked_multiple_token():
    issues = _check_uncited_numbers([_ws("Trades at 15x forward earnings.")])
    assert len(issues) == 1


def test_exempts_four_digit_year_alone():
    issues = _check_uncited_numbers([_ws("In 2025 the company restructured.")])
    assert issues == []


def test_exempts_fiscal_year_token():
    issues = _check_uncited_numbers([_ws("FY2025 results pending.")])
    assert issues == []


def test_exempts_ordinal_suffix():
    issues = _check_uncited_numbers(
        [_ws("Ranked 3rd in the segment and 12th overall.")]
    )
    assert issues == []


def test_exempts_quarter_token():
    issues = _check_uncited_numbers([_ws("Q3 results beat consensus.")])
    assert issues == []


def test_flags_naked_number_alongside_cited_one():
    issues = _check_uncited_numbers(
        [_ws("Revenue {{CITE:rev_ttm}} but margins fell to 18.5%.")]
    )
    assert len(issues) == 1
    assert "18.5" in issues[0].detail


def test_carries_section_id_through_to_issue():
    issues = _check_uncited_numbers(
        [_ws("Trades at 15x earnings.", section_id="valuation")]
    )
    assert issues[0].section_id == "valuation"


def test_reports_only_first_violation_per_section():
    # Avoid noise: a section with three naked numbers reports one issue
    # listing them rather than three issues. Keeps the rewrite prompt
    # focused.
    issues = _check_uncited_numbers(
        [_ws("Revenue $60B, margin 25%, trading at 12x.")]
    )
    assert len(issues) == 1
    detail = issues[0].detail
    assert "$60B" in detail
    assert "25%" in detail
    assert "12x" in detail
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_uncited_number_check.py -v`
Expected: ImportError — `_check_uncited_numbers` not defined.

- [ ] **Step 3: Implement `_check_uncited_numbers` and wire it in**

Modify `packages/core/src/openlia/llm/runtime/report_v2_3/stages/verify.py`. Add the regexes and helper at module level, and call from `_deterministic_checks`:

```python
"""VERIFY stage — last gate before ASSEMBLE.

Two layers of checks, cheap-to-expensive:

1. **Deterministic** (in Python, no LLM call):
   - `dangling_cite` — a `{{CITE:fact_id}}` whose fact_id is absent
     from the bundle. Should not happen in normal flow (PR5 WriteStage
     and PR4 SynthesizeStage both validate against this), but worth
     a defense-in-depth pass.
   - `broken_fig_ref` — a `{{FIG:chart_id}}` whose chart_id is absent
     from thesis.charts.
   - `uncited_number` — a digit-bearing token in body text that is
     not inside a CITE/FIG marker and not in the exempt set
     (years 1900-2099, fiscal-year tokens, ordinals, quarter tokens).
     After WRITE's mint step, every legitimate numeric should be a
     CITE marker; anything left is a fabrication.

2. **LLM-driven**: pass thesis + bundle + sections to the verifier
   client for coherence-level checks (`value_mismatch`,
   `cross_section_contradiction`, `redundancy`, `chart_text_mismatch`).
   The client returns a `VerifyResult`; we merge it with the
   deterministic findings into the final result on state.

The runner reads `state.verify_result.must_rewrite` and routes the
offending sections back to WRITE for one bounded retry.
"""

from __future__ import annotations

import re

from ..clients.verifier import VerifierClient, VerifierRequest
from ..schemas import (
    CITE_RE,
    FIG_RE,
    IssueKind,
    IssueSeverity,
    ReportThesis,
    ResearchBundle,
    VerifyIssue,
    VerifyResult,
    WrittenSection,
)
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext

# A digit-bearing token: optional leading $, then digits with optional
# decimal / thousands-comma, then optional magnitude or unit suffix.
# Examples matched: $60.9B, 1,200, 25%, 15x, 200, 18.5, 60.9, $1.2M.
_NUMERIC_TOKEN_RE = re.compile(
    r"\$?\d[\d,]*(?:\.\d+)?(?:[%xX]|[KkMmBbTt](?=\b|$))?"
)

# Token-level exempt patterns checked against the regex match in context.
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
_FY_RE = re.compile(r"^FY\d{2,4}$", re.IGNORECASE)
_QUARTER_RE = re.compile(r"^Q[1-4]$", re.IGNORECASE)
# Ordinal: the regex matches the digit prefix; we widen the lookahead to
# catch the suffix on the original body.
_ORDINAL_SUFFIX_RE = re.compile(r"(?:st|nd|rd|th)\b", re.IGNORECASE)


class VerifyStage(Stage):
    slot = V23Slot.VERIFY

    def __init__(self, client: VerifierClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        thesis = self._require_thesis(state)
        bundle = self._require_bundle(state)
        if not state.sections:
            raise RuntimeError("VERIFY requires state.sections from WRITE.")

        deterministic = _deterministic_checks(state.sections, thesis, bundle)

        request = VerifierRequest(
            raw_prompt=state.raw_prompt,
            language=state.language,
            thesis=thesis,
            bundle=bundle,
            sections=list(state.sections),
        )
        from_llm = self._client.verify(request)

        state.verify_result = VerifyResult(issues=[*deterministic, *from_llm.issues])
        return state

    @staticmethod
    def _require_thesis(state: ReportState) -> ReportThesis:
        if state.thesis is None:
            raise RuntimeError("VERIFY requires state.thesis from SYNTHESIZE.")
        return state.thesis

    @staticmethod
    def _require_bundle(state: ReportState) -> ResearchBundle:
        if state.bundle is None:
            raise RuntimeError("VERIFY requires state.bundle.")
        return state.bundle


def _deterministic_checks(
    sections: list[WrittenSection],
    thesis: ReportThesis,
    bundle: ResearchBundle,
) -> list[VerifyIssue]:
    """Walk every placeholder + every naked number; HIGH if integrity-violating."""
    bundle_fact_ids = set(bundle.facts.keys())
    chart_ids = {c.id for c in thesis.charts}

    issues: list[VerifyIssue] = []
    for section in sections:
        for fact_id in section.cited_fact_ids():
            if fact_id not in bundle_fact_ids:
                issues.append(
                    VerifyIssue(
                        section_id=section.section_id,
                        kind=IssueKind.DANGLING_CITE,
                        severity=IssueSeverity.HIGH,
                        detail=f"{{CITE:{fact_id}}} does not resolve in the bundle.",
                    )
                )
        for chart_id in section.figure_ids():
            if chart_id not in chart_ids:
                issues.append(
                    VerifyIssue(
                        section_id=section.section_id,
                        kind=IssueKind.BROKEN_FIG_REF,
                        severity=IssueSeverity.HIGH,
                        detail=f"{{FIG:{chart_id}}} does not match any chart spec.",
                    )
                )
    issues.extend(_check_uncited_numbers(sections))
    return issues


def _check_uncited_numbers(sections: list[WrittenSection]) -> list[VerifyIssue]:
    """Flag digit-bearing tokens that are neither inside a marker nor exempt.

    Strips CITE/FIG markers from a working copy of the body so the marker
    payloads cannot trigger the scan, then walks every numeric token in
    what remains and filters out the exempt classes (4-digit years,
    fiscal-year tokens, ordinals, quarter labels).
    """
    issues: list[VerifyIssue] = []
    for section in sections:
        stripped = FIG_RE.sub("", CITE_RE.sub("", section.body))
        violations: list[str] = []
        for match in _NUMERIC_TOKEN_RE.finditer(stripped):
            token = match.group(0)
            if _is_exempt(token, stripped, match.start(), match.end()):
                continue
            violations.append(token)
        if violations:
            joined = ", ".join(violations)
            issues.append(
                VerifyIssue(
                    section_id=section.section_id,
                    kind=IssueKind.UNCITED_NUMBER,
                    severity=IssueSeverity.HIGH,
                    detail=(
                        f"Numeric values not anchored to a fact: {joined}. "
                        f"Use {{{{CITE:<fact_id>}}}} for sourced numbers, "
                        f"{{{{DERIVE:<method>|<inputs>|<id>}}}} for derived numbers, "
                        f"or {{{{ESTIMATE:<id>|<value>|<unit>|<basis>}}}} for analyst judgment."
                    ),
                )
            )
    return issues


def _is_exempt(token: str, body: str, start: int, end: int) -> bool:
    # 4-digit year alone: "2025"
    if _YEAR_RE.match(token):
        return True
    # Fiscal-year token: the regex captures the digit tail of "FY2025";
    # widen the check by inspecting the two preceding characters in the body.
    if start >= 2 and body[start - 2 : start].upper() == "FY":
        return True
    # Quarter token: the regex captures the digit in "Q3"; check the prior char.
    if start >= 1 and body[start - 1].upper() == "Q":
        return True
    # Ordinal: the regex captures "3" in "3rd"; check the two trailing chars.
    if _ORDINAL_SUFFIX_RE.match(body[end : end + 3]):
        return True
    return False
```

- [ ] **Step 4: Run the new test file**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_uncited_number_check.py -v`
Expected: 12 passes.

- [ ] **Step 5: Add a VerifyStage integration test that exercises the full path**

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_verify_stage.py`:

```python
def test_verify_flags_uncited_number_through_deterministic_path():
    # Build the smallest possible state with a section that contains a
    # naked number. The LLM verifier client is faked to return no issues
    # so the deterministic UNCITED_NUMBER is the only finding.
    from openlia.llm.runtime.report_v2_3.clients.verifier import FakeVerifierClient
    from openlia.llm.runtime.report_v2_3.schemas import VerifyResult, WrittenSection

    state = _state()  # uses the file's existing _state helper
    state.sections = [
        WrittenSection(
            section_id="overview",
            title="Overview",
            body="Trades at 15x forward earnings.",
        )
    ]

    stage = VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[])))
    stage.run(state, StageContext())

    kinds = [i.kind for i in state.verify_result.issues]
    assert IssueKind.UNCITED_NUMBER in kinds
    assert state.verify_result.must_rewrite is True
```

If `FakeVerifierClient` does not yet exist in `clients/verifier.py`, this step requires adding a small fake (mirrors `FakeWriterClient` pattern at `clients/writer.py:54-75`). Inspect the file; add the fake there if missing:

```python
class FakeVerifierClient(VerifierClient):
    def __init__(self, result: VerifyResult) -> None:
        self._result = result
        self.calls: list[VerifierRequest] = []

    def verify(self, request: VerifierRequest) -> VerifyResult:
        self.calls.append(request)
        return self._result
```

- [ ] **Step 6: Run the verify_stage test file**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_verify_stage.py -v`
Expected: all previously-passing tests still pass; new test passes.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/stages/verify.py packages/core/tests/test_runtime/test_report_v2_3/test_uncited_number_check.py packages/core/tests/test_runtime/test_report_v2_3/test_verify_stage.py packages/core/src/openlia/llm/runtime/report_v2_3/clients/verifier.py
git commit -m "feat(report_v2_3): deterministic UNCITED_NUMBER check in VERIFY"
```

---

## Task 7: Teach the WRITE prompt the three-marker grammar

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` (WRITE_SYSTEM_PROMPT, around lines 650-700)

- [ ] **Step 1: Read the current WRITE prompt to understand its shape**

Read `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — locate `WRITE_SYSTEM_PROMPT` (search for the string). Skim the existing structure so the new grammar section slots in cleanly.

- [ ] **Step 2: Insert a "Number grammar" section into `WRITE_SYSTEM_PROMPT`**

Find the section of `WRITE_SYSTEM_PROMPT` that talks about CITE markers (currently mentions `{{CITE:fact_id}}` and footnote rendering). Replace that section with a unified three-marker grammar. The exact placement is right after the existing "Citing facts" / "Body structure" guidance and before the "Length budget" section.

Add this block (preserves positive phrasing per the project's `feedback_positive_prompts` memory):

```
Number grammar — every number in the body comes from one of three markers.
The engine resolves all three to {{CITE:<id>}} before VERIFY runs, so the
report's reader sees consistent footnotes; the deterministic check after
you write will reject any digit-bearing token outside these markers.

1. Cite an existing fact when the number already lives in the bundle:
     {{CITE:rev_ttm}}
   Use this whenever the bundle already carries the value you want to claim.

2. Derive a new fact from existing ones when the number is arithmetic
   over bundle facts (growth rates, YoY deltas, ratios):
     {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}}
   Grammar: {{DERIVE:<method>|<input_fact_ids_csv>|<new_fact_id>}}
   Methods available: growth_rate, yoy_delta, ratio.
   The engine runs the math, mints a ComputedSource fact at <new_fact_id>,
   and rewrites your marker to {{CITE:<new_fact_id>}}.

3. State an estimate when the number is analyst judgment with no
   underlying calculation — projections, scenario calls, view-driven
   targets:
     {{ESTIMATE:upside_pct|0.10|percent|projection from margin-expansion thesis}}
   Grammar: {{ESTIMATE:<new_fact_id>|<value>|<unit>|<basis>}}
   The engine mints an EstimateSource fact at <new_fact_id> with your
   basis text as the footnote, and rewrites your marker to
   {{CITE:<new_fact_id>}}. The footnote will render as
   "Estimate: <basis>." so the reader sees this is judgment, not a
   measured figure.

Exemptions (the deterministic check ignores these): 4-digit years
("2025"), fiscal-year tokens ("FY2025"), quarter labels ("Q3"), and
ordinals ("3rd"). Anything else with a digit needs one of the three
markers.

Worked example (showing all three):
  "Revenue {{CITE:rev_ttm}} grew
   {{DERIVE:growth_rate|rev_ttm,rev_prior|rev_growth_yoy}} year over year,
   and we see {{ESTIMATE:upside_pct|0.10|percent|
   margin expansion against current multiple}} of further upside."
```

- [ ] **Step 3: Run the LLM stage clients test file**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py -v`
Expected: all existing tests pass (the prompt is a string; nothing structural changed).

- [ ] **Step 4: Run the full v2.3 test suite as a regression check**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v`
Expected: all tests pass.

- [ ] **Step 5: Run ruff format + check on touched files**

Run: `uv run ruff format packages/core/src/openlia/llm/runtime/report_v2_3/ packages/core/tests/test_runtime/test_report_v2_3/ && uv run ruff check packages/core/src/openlia/llm/runtime/report_v2_3/ packages/core/tests/test_runtime/test_report_v2_3/`
Expected: format reports no changes (or only reformats); check reports no issues.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py
git commit -m "feat(report_v2_3): teach WRITE prompt the three-marker number grammar"
```

---

## Task 8: End-to-end integration test

**Files:**
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_number_origin_e2e.py`

- [ ] **Step 1: Write the integration test**

Create `packages/core/tests/test_runtime/test_report_v2_3/test_number_origin_e2e.py`:

```python
"""End-to-end: WRITE -> mint -> VERIFY pipeline preserves number-origin discipline.

Drives a single iteration of WriteStage followed by VerifyStage with a
fake writer that emits all three marker shapes, and asserts:
  - DERIVE/ESTIMATE markers are resolved into bundle facts of the
    correct Provenance variants
  - the post-WRITE body contains only {{CITE:...}} markers (no naked
    numbers, no DERIVE/ESTIMATE remnants)
  - VERIFY surfaces zero UNCITED_NUMBER issues
  - render_citation produces "Estimate: ..." for estimate facts and
    "Author calculation: ..." for computed facts
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.clients.verifier import (
    FakeVerifierClient,
    VerifierRequest,
)
from openlia.llm.runtime.report_v2_3.clients.writer import FakeWriterClient, WriterRequest
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    ComputedSource,
    DataProviderSource,
    EstimateSource,
    IssueKind,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    ValuationPlan,
    VerifyResult,
    WrittenSection,
    render_citation,
)
from openlia.llm.runtime.report_v2_3.stages import StageContext, VerifyStage, WriteStage
from openlia.llm.runtime.report_v2_3.state import ReportState


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="FY2025",
        retrieved_at=datetime.now(UTC),
    )


def test_number_origin_discipline_holds_through_write_and_verify():
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_fy25": BundleFact(id="rev_fy25", label="Revenue FY25", value=125.0, source=_src()),
            "rev_fy24": BundleFact(id="rev_fy24", label="Revenue FY24", value=100.0, source=_src()),
        },
    )
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="financials", title="Financials")],
    )
    thesis = ReportThesis(
        language=Language.EN,
        central_argument="Growth durable.",
        key_takeaways=["beat", "raise"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="rev_fy25", display="$125.0M")],
        mandates=[
            SectionMandate(
                section_id="financials",
                covers="financial line items",
                does_not_cover="overview",
                chart_ids=[],
                relevant_fact_ids=["rev_fy25", "rev_fy24"],
            )
        ],
        charts=[],
    )
    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    state.bundle = bundle
    state.outline = outline
    state.thesis = thesis

    def responder(req: WriterRequest) -> WrittenSection:
        return WrittenSection(
            section_id="financials",
            title="Financials",
            body=(
                "Revenue {{CITE:rev_fy25}} grew "
                "{{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} YoY, "
                "and we see {{ESTIMATE:upside_pct|0.10|percent|"
                "margin expansion against current multiple}} of upside."
            ),
        )

    WriteStage(FakeWriterClient(responder=responder)).run(state, StageContext())

    body = state.sections[0].body
    assert "{{DERIVE:" not in body
    assert "{{ESTIMATE:" not in body
    assert body.count("{{CITE:") == 3
    assert "rev_fy25" in body
    assert "rev_growth_yoy" in body
    assert "upside_pct" in body

    minted_derived = state.bundle.facts["rev_growth_yoy"]
    assert isinstance(minted_derived.source, ComputedSource)
    assert render_citation(minted_derived) == "Author calculation: growth_rate."

    minted_estimate = state.bundle.facts["upside_pct"]
    assert isinstance(minted_estimate.source, EstimateSource)
    assert render_citation(minted_estimate) == (
        "Estimate: margin expansion against current multiple."
    )

    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(
        state, StageContext()
    )

    uncited = [
        i for i in state.verify_result.issues if i.kind == IssueKind.UNCITED_NUMBER
    ]
    assert uncited == []
    assert state.verify_result.must_rewrite is False
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_number_origin_e2e.py -v`
Expected: 1 pass.

- [ ] **Step 3: Run the full v2.3 test suite to confirm no regression**

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v`
Expected: all tests pass.

- [ ] **Step 4: Final lint**

Run: `uv run ruff check packages/core/src/openlia/llm/runtime/report_v2_3/ packages/core/tests/test_runtime/test_report_v2_3/`
Expected: no issues.

- [ ] **Step 5: Commit**

```bash
git add packages/core/tests/test_runtime/test_report_v2_3/test_number_origin_e2e.py
git commit -m "test(report_v2_3): e2e number-origin discipline through WRITE+VERIFY"
```

---

## Self-Review Notes

- **Spec coverage:** Every philosophy requirement from the conversation has a task — `EstimateSource` (Task 1), derivations (Task 2), inline marker regex (Task 3), mint helper (Task 4), WriteStage wiring (Task 5), deterministic UNCITED_NUMBER check (Task 6), prompt update (Task 7), e2e proof (Task 8). The "on-demand mid-WRITE minting" population-path decision is implemented (Task 5) and the alternative (speculative COMPUTE emission) is explicitly rejected in the architecture header.
- **No placeholders:** every code step shows complete code. Regexes, exemption logic, mint helper, and the prompt grammar are fully spelled out — no "implement appropriate error handling" or "similar to Task N" deferrals.
- **Type consistency:** `EstimateSource(basis, derived_from, stage)` shape is identical in every test. `DERIVATION_REGISTRY` key names (`growth_rate`, `yoy_delta`, `ratio`) match between Task 2 (definition), Task 3 (regex `[a-z_]+`), Task 4 (mint test), Task 7 (prompt). `mint_inline_facts` signature matches between Task 4 (definition) and Task 5 (wiring call site).

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-24-phase-0-number-origin-discipline.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
