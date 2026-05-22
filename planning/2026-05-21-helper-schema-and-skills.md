# Helper Schema and Skills Documentation Design

**Date:** 2026-05-21
**Branch:** `feat/equity-research-engine-plan`
**Status:** Design contract for the v2.2 equity research engine library_helper registry

---

## 0. Purpose

Defines the formal `HelperSchema` shape that all ~178 library helpers must register with, the four-tier exposure model that controls what the LLM sees at each stage, the closed `ArtifactType` registry that makes the helper-to-helper graph machine-resolvable, and the list of ~18 helpers that warrant full `skills.md` documentation beyond the structured schema.

This document supersedes the schema notes in §1 of `planning/2026-05-21-equity-research-engine-helper-stack.md`.

---

## 1. Four-tier exposure model (corrected)

The previously documented "three-layer" model was undercounted. With `skill_doc` loaded on demand, there are actually four LLM-visible tiers plus execution.

| Tier | What | Always loaded? | Tokens (typical) |
|---|---|---|---|
| **L1** | Category index — 14 categories + one-liners | yes, cached across sessions | ~1k |
| **L1.5** | Helper directory — ~178 helper one-liners + category tag | yes, cached across sessions | ~12-18k (cached → ~1-2k effective) |
| **L2** | Selection guidance + mechanical contract for planner-picked helpers | per run, cached across stages | ~5-8k for ~12 picked helpers |
| **L3** | Skill docs — full `skills.md` for complex helpers, opt-in per helper | on demand, only when planner requests | ~1.5-3k per loaded skill |
| **L4** | Execution — Python | never | 0 |

Honest layer count matters because the team has to reason about projection rules — each tier corresponds to a distinct sub-model in the schema, not a comment block.

---

## 2. `ArtifactType` registry

The biggest schema gap in the prior draft was the absence of inter-helper artifact dependencies. The planner currently has to infer that `sensitivity_table` consumes a `dcf_base_valuation` from prose. That inference is unreliable and untestable.

### 2.1 Closed registry

Artifact types live in a separate YAML registry, not as free strings inside helper schemas:

```yaml
# artifact_types.yaml
dcf_base_valuation:
  description: "DCF intrinsic value with FCF schedule and discount factors"
  shape_module: "openlia.artifacts.DCFValuationArtifact"

peer_multiple_panel:
  description: "Peer-set multiples table with statistical summary"
  shape_module: "openlia.artifacts.PeerMultiplePanelArtifact"

implied_price_range:
  description: "Valuation-implied price range across methodologies"
  shape_module: "openlia.artifacts.ImpliedPriceRangeArtifact"

sensitivity_grid:
  description: "2-D sensitivity table over two assumption axes"
  shape_module: "openlia.artifacts.SensitivityGridArtifact"

# ...one entry per artifact type in the system
```

Each entry binds an artifact ID to its Pydantic model. The verifier introspects the model for shape checks; the planner uses the ID for graph resolution.

### 2.2 Boot-time DAG validation

At registry boot, for every registered helper, the dispatcher checks:

1. Every entry in `consumes_artifacts` exists in `artifact_types.yaml`.
2. Every entry in `produces_artifacts` exists in `artifact_types.yaml`.
3. For every consumer artifact, at least one producer helper exists somewhere in the registry.

Boot fails loudly if any check fails. Catches "`sensitivity_table` references `dcf_valuation` that nobody produces" before any run starts.

---

## 3. Schema definition

### 3.1 Closed enums

```python
from enum import Enum
from typing import Literal


class Category(str, Enum):
    COMPARABLES = "comparables"
    DCF = "dcf"
    ALTERNATIVE_VALUATION = "alternative_valuation"
    DECISION = "decision"
    BUSINESS_QUALITY = "business_quality"
    STATEMENT_INTEGRITY = "statement_integrity"
    CREDIT_SOLVENCY = "credit_solvency"
    FORENSIC = "forensic"
    SIGNALS = "signals"
    SECTOR_BANKS = "sector_banks"
    SECTOR_REITS = "sector_reits"
    SECTOR_PHARMA = "sector_pharma"
    SECTOR_ENERGY = "sector_energy"
    SECTOR_INSURANCE = "sector_insurance"
    # 14 closed entries; verifier rejects helpers with categories outside this set


OutputType = Literal[
    "table", "scalar", "series", "chart", "panel", "workbook", "structured_object"
]
```

Final 14-entry `Category` enum will mirror the audit taxonomy exactly. New helpers cannot drift into ad-hoc category strings.

### 3.2 Sub-models — one per tier

```python
from pydantic import BaseModel
from typing import Any


class HelperParam(BaseModel):
    type: str
    default: Any | None = None
    derivation: str | None = None
    description: str
    required: bool = True


class HelperOutput(BaseModel):
    """Documentation for the drafter.

    Verifier does NOT read this — shape validation uses runtime Pydantic
    introspection on the helper's return type annotation. This field is
    explicitly documentation-only to avoid a second parallel type system.
    """
    name: str
    type: OutputType
    description: str


class HelperExample(BaseModel):
    call: dict[str, Any]
    result_shape: str
    notes: str | None = None


class DirectoryEntry(BaseModel):
    """Tier L1.5 — always loaded. Keep cheap (~80-120 tokens per helper)."""
    name: str
    category: Category
    one_liner: str  # ~10-15 words; what it does at a glance


class SelectionGuidance(BaseModel):
    """Tier L2 — loaded when the planner picks helpers in this category."""
    purpose: str  # 1-2 sentences
    when_to_use: list[str]  # 2-4 bullets
    when_not_to_use: list[str]  # 2-4 bullets, with redirects to neighbors


class MechanicalContract(BaseModel):
    """Tier L2 — loaded with SelectionGuidance. The machine-checkable contract."""
    params: dict[str, HelperParam]
    outputs: list[HelperOutput]
    example: HelperExample | None = None
    produces_artifacts: list[str]  # ArtifactType IDs from artifact_types.yaml
    consumes_artifacts: list[str]  # ArtifactType IDs from artifact_types.yaml
    data_dependencies: list[str] = []  # External data sources, e.g. ["eodhd.fundamentals"]


class SkillDocRef(BaseModel):
    """Tier L3 — pointer to skills/<name>.md, loaded on demand."""
    path: str  # e.g. "skills/dcf_engine.md"
    estimated_tokens: int  # planner uses this to budget L3 loads


class HelperSchema(BaseModel):
    """Composes the four-tier contract.

    Each sub-model maps to exactly one projection tier. The dispatcher
    serializes by sub-object name, not by remembering which fields belong
    where. Adding a field under the wrong sub-model is a compile-time
    structural error, not a silent token leak.
    """
    directory: DirectoryEntry
    selection: SelectionGuidance
    contract: MechanicalContract
    skill_doc: SkillDocRef | None = None
    version: str = "1.0"
```

### 3.3 Registration with explicit return type

The verifier needs a machine-checkable return shape. Pydantic models registered alongside the function fill that role — the schema's `outputs` field stays documentation-only.

```python
class HelperRegistration(BaseModel):
    helper_schema: HelperSchema
    execute: Callable[..., Any] = Field(exclude=True)
    return_type: type[BaseModel] | None = None  # NEW — verifier introspects this
    available: bool = True
    deferred_category: str | None = None

    model_config = {"arbitrary_types_allowed": True}


def register_library_helper(
    name: str,
    fn: Callable,
    schema: HelperSchema,
    return_type: type[BaseModel] | None = None,
    deferred_category: str | None = None,
) -> None:
    ...
```

### 3.4 Projection rules

The dispatcher exposes helpers to the LLM via four projection functions, each serializing exactly one tier of sub-models:

```python
class ToolDispatcher:
    def project_l1(self) -> dict:
        """Always loaded. Group L1.5 entries by category."""
        return {
            "categories": {
                cat.value: {
                    "summary": CATEGORY_SUMMARIES[cat],
                    "helpers": [h.directory.name for h in self.helpers if h.directory.category == cat],
                }
                for cat in Category
            }
        }

    def project_l1_5(self) -> list[dict]:
        """Always loaded. Helper directory."""
        return [h.directory.model_dump() for h in self.helpers]

    def project_l2(self, helper_names: list[str]) -> list[dict]:
        """Loaded after planner picks helpers."""
        return [
            {"directory": h.directory.model_dump(),
             "selection": h.selection.model_dump(),
             "contract": h.contract.model_dump()}
            for h in self.helpers if h.directory.name in helper_names
        ]

    def project_l3(self, helper_name: str) -> str:
        """Loaded on demand. Reads skills.md file."""
        helper = self.get(helper_name)
        if helper.skill_doc is None:
            raise ValueError(f"no skill doc for {helper_name}")
        return Path(helper.skill_doc.path).read_text()
```

Tier boundaries are enforced by the type system, not comments. Adding a `when_to_use` field to `DirectoryEntry` is a structural mistake the LLM never silently pays for.

---

## 4. Boot-time validation

`register_library_helper` runs these checks at call time, raising on first failure:

1. **Category in closed set:** `schema.directory.category` is a valid `Category` enum value.
2. **Artifact references resolve:** every entry in `produces_artifacts` and `consumes_artifacts` exists in `artifact_types.yaml`.
3. **Return type matches one produced artifact:** if `return_type` is set, the Pydantic model class must equal the `shape_module` of one of the helper's `produces_artifacts`.
4. **Skill doc exists if referenced:** if `skill_doc` is set, the file at `skill_doc.path` exists at registry boot.

A final pass after all helpers are registered:

5. **Producer coverage:** every artifact type listed in any `consumes_artifacts` has at least one producer somewhere in the registry. Surfaces orphan dependencies before any run starts.
6. **No cycles:** the producer-consumer graph is a DAG. Cycles indicate a design error; boot fails.

---

## 5. Output validation flow (verifier coherence)

The verifier's `block_shape` issue type validates artifact shapes by introspecting **the runtime Pydantic return model**, not the schema metadata:

```python
def validate_artifact(helper_name: str, artifact: Any) -> list[VerifierIssue]:
    helper = registry.get(helper_name)
    if helper.return_type is None:
        return []  # no machine-checkable contract; documentation-only
    try:
        helper.return_type.model_validate(artifact)
        return []
    except ValidationError as e:
        return [VerifierIssue(type="block_shape", helper=helper_name, detail=str(e))]
```

This closes the coherence gap from the previous draft: there is exactly one source of truth for output shape (the Pydantic model), and `HelperOutput.description` exists only to brief the drafter on what to expect.

---

## 6. skills.md list (~18 helpers)

Selection criterion: **multi-step OR has dangerous defaults OR easily confused with a neighbor.** Atomic fetch/ratio helpers do not qualify — their structured `SelectionGuidance` card suffices.

| # | Helper | Category | Why it needs a skill doc |
|---|---|---|---|
| 1 | `dcf_engine` | dcf | 30+ inputs; mid-year convention; terminal-value method choice; sensitivity grid logic |
| 2 | `cost_of_capital_builder` | dcf | CAPM vs Hamada vs build-up; country risk premium; size premium gotchas |
| 3 | `comparables.run` | comparables | Peer-set construction; combined-range methodology; NM handling |
| 4 | `ddm_family` | alternative_valuation | Gordon vs multi-stage vs H-model; when each applies; dividend sustainability |
| 5 | `justified_multiples` | alternative_valuation | Derivation from fundamentals (g, ROE, payout); pairs with comparables |
| 6 | `sotp_builder` | alternative_valuation | Segment-level valuation; net debt allocation; conglomerate discount handling |
| 7 | `price_target_blender` | decision | Weighting across DCF / comps / DDM; ETR; risk/reward asymmetry |
| 8 | `rating_band_assigner` | decision | Upside/downside thresholds vs. risk; judgmental, not mechanical |
| 9 | `rnpv_pipeline` | sector_pharma | Stage-specific PoS; peak sales; royalty stacks; risk-adjusted NPV |
| 10 | `banks_sector_panel` | sector_banks | NIM / CET1 / ROTCE / efficiency / NCO interlocks; regulatory regime |
| 11 | `reit_valuation_panel` | sector_reits | FFO/AFFO normalization; NAV vs implied cap rate; same-store NOI |
| 12 | `ep_sector_panel` | sector_energy | EBITDAX, DACF, netback, reserves replacement; AISC variant |
| 13 | `insurance_valuation_panel` | sector_insurance | Combined ratio, embedded value, P&C vs Life differences |
| 14 | `forensic_panel` | forensic | Beneish M, Altman Z variants, Sloan accruals — interpretation rules |
| 15 | `statement_integrity_bundle` | statement_integrity | Piotroski F-score, Dechow-Dichev, earnings persistence |
| 16 | `insider_signal_panel` | signals | Form 4 code filtering, 10b5-1 handling, cluster detection, role weighting |
| 17 | `historical_multiple_trends` | signals | Re-rating slope, NM handling, sector overlay; pairs with comparables |
| 18 | `workbook_builder` | (output) | Multi-sheet structure, cross-sheet formulas, formatting conventions |

**Explicit exclusions:**
- All single-ratio helpers — structured card is sufficient
- All EODHD adapter wrappers — vendor docs are the skill doc
- All FinanceToolkit / statsmodels wrappers — library docs serve as the skill doc
- Simple panel helpers (`peer_multiples_panel`, `moving_average_panel`) — good `when_not_to_use` is enough

---

## 7. skills.md template

```markdown
---
name: dcf_engine
category: dcf
version: 1.0
produces_artifacts:
  - dcf_base_valuation
  - sensitivity_grid
consumes_artifacts:
  - financial_statement_pack
  - cost_of_capital_inputs
---

# DCF Engine

## Purpose
[1 paragraph — what it computes and the methodological frame]

## When to use
- Initiation report, valuation section
- User requests "fair value" or "DCF" explicitly
- Triangulation against comparables for relative-vs-absolute spread

## When NOT to use
- High-uncertainty businesses where comparables dominate → use `comparables.run` as primary
- Pre-revenue biotech → use `rnpv_pipeline` instead
- REITs → use `reit_valuation_panel` (FFO-based, not FCF)

## Inputs
[Annotated table of all params with derivations and defaults]

## Methodology
[Step-by-step computation; mid-year convention; TV approach choices]

## Common pitfalls
- WACC pulled from FinanceToolkit but country risk premium not added
- Terminal growth > risk-free rate — Stage 8 verifier rejects
- ...

## Outputs
[Structured shape with field meanings; mirrors the Pydantic return model]

## Example
[One concrete call + result trace]
```

---

## 8. Implementation order

1. **Update `library_helpers/__init__.py`** with the new sub-model schema (back-compat: existing 6 helpers get a one-shot wrapper that fills `directory.one_liner` from old `description` and synthesizes empty `selection`/`contract` blocks until rewritten).
2. **Create `artifact_types.yaml`** with the initial artifact registry. Seeded from PR #151 + Wave 0 / Wave 1 helpers as those tasks build.
3. **Add boot-time DAG validation** in `register_library_helper` and a final registry-wide `validate_registry()` call.
4. **Write `ToolDispatcher` projection methods** (`project_l1`, `project_l1_5`, `project_l2`, `project_l3`). Wire to Stage 3 / Stage 5 planners and Stage 7 drafter.
5. **Author skills.md files lazily** — one per task. Each task that builds a complex helper also produces its `skills/<name>.md` in the same PR.

This is foundation work for the v2.2 engine. Should land before any Wave 0 task starts implementation, so all subsequent helpers register against the corrected schema.

---

## 9. Open questions parked for later

- **Helper versioning** (`HelperSchema.version`) — bumped on contract changes; no migration story defined yet. Defer until first real version bump.
- **L1.5 caching strategy** — exact cache key (sessionId vs. global) depends on multi-user company-mode behavior. Defer to deployment task.
- **Artifact-type evolution** — adding a new ArtifactType requires registry rebuild; no live-reload yet. Acceptable for v2.2.
