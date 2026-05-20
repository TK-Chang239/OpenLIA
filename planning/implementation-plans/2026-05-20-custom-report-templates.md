# Custom Report Templates — Implementation Plan

**Date:** 2026-05-20
**Branch:** `feat/custom-report-templates` (off `main@acb60c62`)
**Driver:** Product goal — users upload their own report template (text / markdown / docx), and the Equity Research department generates a report against it. The system should behave like Claude.ai project knowledge + tool use: simple, straightforward, seamless. Template authoring is the user's responsibility; the machine guarantees a fixed contract of structural and data-hygiene mechanics regardless of which template is active.
**Scope:** `packages/core/src/openlia/llm/runtime/report_v2/` (runner + dispatcher + validators + scanners), `packages/core/src/openlia/reports/frameworks/`, `packages/server/src/openlia_server/` (new template upload + storage routes), `frontend/src/` (template upload UI), `packages/core/tests/`.

---

## 1. The framing, in one paragraph

Today the runtime is one large equity-research-initiation report generator with universal mechanics tangled inside it. Hardcoded English section IDs, an embedded house-style guide as a Python string default, freshness budgets keyed to equity facts, identity-equation checks hardcoded to `market_cap`/`current_price`/`shares_outstanding`, industry overlays bolted to one specific framework. To support user-uploaded templates, none of that needs to be deleted — but **all of it needs to be on the template side of the contract, not the runner side**. The work is a series of careful lifts that change *who owns* each rule, with the default template absorbing every equity-research-flavored rule the runner currently ships with. Then the upload pipeline + LLM-assisted extraction turn an uploaded `.docx` or `.md` into a runnable template config.

The product position: **soft floor universal contract**. The machine guarantees data hygiene, structural validity, retry mechanics, presentation primitives. The template owns analysis substance, voice, fact-citation discipline, conditional flow, and whether to author verdicts. A user who uploads a sloppy template gets a sloppy report; a user who uploads a rigorous template (like the current default) gets a rigorous report.

The execution model: **prose is the section brief**. The runtime mechanically parses the uploaded markdown into section boundaries; the original prose under each heading is passed verbatim to the section-writing LLM as that section's instruction. No LLM-driven extraction step converts prose into typed fields, no summarization step loses the nuance of the user's own writing. The only structured data the runtime *needs* from an uploaded template is the section boundary list. Everything else — voice rules, identity-check requests, fact-citation requirements — lives in the prose and is consumed by the section-writing LLM at runtime. Power users may opt into declarative override via an optional markdown frontmatter convention (§6). The default equity-research template stays authored as a Python loader and keeps every typed field it has today; uploaded templates get the soft floor by default and can climb toward the default template's rigor by opting into frontmatter declarations.

---

## 2. The universal contract (what the machine guarantees, every report)

These are the mechanical guarantees the runner provides regardless of which template is active. This list is the spec — every section in §5 either preserves an existing guarantee, lifts a guarantee from hardcoded to config, or adds a new one.

| # | Guarantee | Current location | Target location |
|---|-----------|------------------|-----------------|
| C1 | Every Fact carries `data_as_of` and `source_tier` | `types.py`, all extractors | Stays — already universal |
| C2 | Stale data refuses to render | `freshness.py` `FRESHNESS_BUDGETS` (hardcoded) | Per-template config (budgets ship inside template JSON) |
| C3 | Numbers in prose without provenance get soft-warned | `validators/numeric_consistency.py` `_check_numeric_not_in_facts` | Stays — already universal |
| C4 | Cross-section arithmetic identity equations checked | `validators/numeric_consistency.py` `_check_identity_equations` (hardcoded equations) | Per-template config (equations declared in template JSON) |
| C5 | Block shape gates reject broken charts/tables before render | `packer/block_shape.py` + each block's `validate_shape` | Stays — already universal |
| C6 | Block dedup by `purpose_tag` | `packer/block_shape.py` `dedupe_by_purpose_tag` | Stays — already universal |
| C7 | Auto-repair of common parse errors before validation | `packer/auto_repair.py` | Stays — already universal |
| C8 | Section retry loop with structured feedback on failure | `sections/dispatcher.py` | Stays — already universal |
| C9 | Tombstone phrase rejection | `sections/prompts.py` `TOMBSTONE_PHRASES` | Stays universal; templates may extend the list |
| C10 | Year-label slip detection | `validators/numeric_consistency.py` `_check_year_labels` | Stays — already universal |
| C11 | Citation reference system + manifest | `manifest/`, `packer/parser.py` | Stays — already universal |
| C12 | Helpers exposed as tool-callable functions to every section | currently bound to specific facts in framework JSON | Universal helper catalog injected into every section prompt; template may also wire helpers into named Facts |
| C13 | Material events + catalyst news scanners run before dispatch | `scanners/material_events.py`, `scanners/catalyst_pack.py` (equity event classes hardcoded) | Per-template config (event class regexes declared in template) |
| C14 | First-person voice check fires only on sections that opt in | `validators/numeric_consistency.py` `_check_first_person` (hardcoded `{"analyst_view", "investment_recommendation"}`) | Per-section flag in template JSON |
| C15 | Industry-mode overlay system | `mode_selector.py` + `report_mode_overrides/` (hardcoded coupling to `stock_initiation.json`) | Per-template — overlay set declared in template; selector rules generic |

Items marked "Stays" are already universal — those touch only at the audit level (verify they have no hidden template-specific assumption).

---

## 3. Current coupling points to lift (audit of the wall)

Grounded in actual code locations as of `main@acb60c62`. Each row is a coupling point that prevents non-equity templates from working. The plan in §5 dismantles them one PR at a time.

| # | Coupling point | File:Line | Lift strategy |
|---|----------------|-----------|---------------|
| W1 | `if report_type != "stock_initiation": raise` | `runner.py:326` | Replace with template-registry lookup |
| W2 | `BODY_SECTIONS_STOCK_INITIATION` tuple | `runner.py:112` | Read from active template config |
| W3 | `SYNTHESIS_SECTIONS_STOCK_INITIATION` tuple | `runner.py:124` | Read from active template config |
| W4 | `DEFAULT_WORD_TARGETS` dict | `runner.py:131` | Read from active template config |
| W5 | `_SECTION_BRIEFS` dict (per-section instructions hardcoded in Python) | `runner.py:140-269` | Move to default template's JSON; runner reads briefs from config |
| W6 | `DEFAULT_BRIEFS` derived dict | `runner.py:272` | Folded into the above |
| W7 | `style_guide` default — multi-line string literal embedding equity house style | `runner.py:296-307` | Default to empty string in runner; default template ships its own style guide markdown |
| W8 | `system_role` default `"You are an equity research section writer."` | `runner.py:294` | Default template provides; runner default becomes generic ("You are a research section writer.") |
| W9 | `FRESHNESS_BUDGETS` dict | `freshness.py:23` | Move budgets into template JSON; runtime loads them at template-load time |
| W10 | Identity-equation hardcoded fact lookups | `validators/numeric_consistency.py:_check_identity_equations` | Equations declared in template JSON as a list; evaluator is generic |
| W11 | First-person section allowlist `{"analyst_view","investment_recommendation"}` | `validators/numeric_consistency.py:748` | Replaced by per-section flag `voice: "third_person_only"` |
| W12 | Material-events regex classes (Ch.11, M&A, etc.) | `scanners/material_events.py` | Event-class regex set declared in template; scanner is generic |
| W13 | Catalyst event classes (GTC, hyperscaler capex, etc.) | `scanners/catalyst_pack.py` | Same pattern as W12 |
| W14 | Industry overlay set hardcoded to `{"generic","saas","semis","distressed"}` | `mode_selector.py:31` | Mode set + selector rules read from template |
| W15 | `report_mode_overrides/` files keyed to `stock_initiation.*.json` | `reports/frameworks/report_mode_overrides/` | Overlays scoped to template ID, not global |
| W16 | `freshness_override`, `material_events_override`, `numeric_validation_override`, `peer_set_override`, `report_mode_override`, `catalyst_pack_enabled` constructor flags | `runner.py:319-325` | Stay — these are universal escape hatches |
| W17 | Helpers exposed to LLM only via JSON-declared Fact bindings | `frameworks/stock_initiation.facts.json` | Add: helper catalog auto-exposed as tools in every section prompt; template may still declare named-Fact bindings |
| W18 | Cover assembler hardcoded to `analyst_consensus_rating` / `analyst_target_mean` / `consensus_upside_pct` fact names | `packer/assembler.py:_build_cover` | Cover field-to-Fact bindings declared in template config |

---

## 4. Bucket discipline (what work belongs where)

**Bucket A — leave alone, only audit.** Universal mechanics that already work template-agnostically. Verify no hidden coupling, write at most a regression test:
C1, C3, C5, C6, C7, C8, C9, C10, C11. Roughly half of the existing quality stack.

**Bucket B — lift hardcoded specifics into per-template config.** Mechanism stays in the runtime; configuration moves to the template JSON:
C2 (freshness), C4 (identity equations), C13 (event scanner classes), C14 (voice allowlist), C15 (industry overlays), C12 helper catalog exposure. Six items.

**Bucket C — delete from the runner, move into the default template.** Equity-research-flavored content that currently lives in `runner.py` because it's been written as Python defaults:
W2-W8, W18. Section list, briefs, style guide, system role, cover bindings.

**Bucket D — new code.** Upload pipeline, ingest, LLM-assisted extraction, storage, UI. Builds on top of the cleanly-separated Buckets A+B+C.

---

## 5. PR sequencing

Eight PRs for v1. Each PR is shippable on its own — the chain doesn't depend on the final outcome to deliver intermediate value. After PR 1-7 the runner is template-agnostic with the default equity template producing identical output to today. After PR 8 users can upload custom templates.

Order is dictated by *what each PR unblocks*: the runner refactor must come before the upload pipeline (Bucket B + C before D), and within Bucket B the items that are simplest and most-independent come first.

### PR 1 — Introduce `TemplateSpec` schema and default-template loading

**Scope:** Pure refactor with zero behavior change. Establishes the abstraction every later PR plugs into.

**Files:**
- New: `packages/core/src/openlia/reports/frameworks/template_spec.py` — Pydantic `TemplateSpec` dataclass. Minimum required fields: `name: str`, `global_preface: str` (preamble injected into every section prompt), `body_sections: list[SectionSpec]`, `synthesis_sections: list[SectionSpec]`. Optional declarative fields (populated by the default Python loader; left empty/default for prose-only uploads): `default_word_targets`, `style_guide`, `system_role`, `web_search_budget_default`, `freshness_budgets`, `identity_equations`, `material_event_classes`, `catalyst_classes`, `industry_modes`, `cover_bindings`. `SectionSpec` carries `id: str`, `title: str`, `brief: str` (verbatim prose from the source markdown), plus optional `voice`, `word_target`, `preload_helpers`, `required_facts` — all defaulting to empty/none.
- New: `packages/core/src/openlia/reports/frameworks/registry.py` — `TemplateRegistry` with `register(template_id, loader)` and `get(template_id) -> TemplateSpec`. Ships with `"stock_initiation"` pre-registered.
- New: `packages/core/src/openlia/reports/frameworks/loaders/stock_initiation.py` — loader function returning a fully-populated `TemplateSpec` whose body sections / briefs / style guide come from *re-export* of the current Python constants in `runner.py`. No content moves yet; the default template carries every optional field declaratively because it is authored as code, not uploaded as prose.
- Modified: `packages/core/src/openlia/llm/runtime/report_v2/runner.py` — runner accepts an optional `template: TemplateSpec | None` parameter. When None, looks up by `report_type` in the registry. All other behavior unchanged.

**Validation:** Run the full `report_v2` test suite. Every existing test must pass without modification.

**Risk:** Pure plumbing. The registry and TemplateSpec exist but the runner still uses the hardcoded Python constants for everything except dispatch.

### PR 2 — Move section list, briefs, and style guide from `runner.py` into the default template's loader

**Scope:** Bucket C — `runner.py` shrinks dramatically. `_SECTION_BRIEFS`, `BODY_SECTIONS_STOCK_INITIATION`, `SYNTHESIS_SECTIONS_STOCK_INITIATION`, `DEFAULT_WORD_TARGETS`, the `style_guide` default literal, and `system_role` default literal all move into `loaders/stock_initiation.py`. The runner reads them from the resolved `TemplateSpec`. The `report_type != "stock_initiation"` guard is replaced by `template = self.template or registry.get(report_type)` — unknown report types raise via the registry rather than via the explicit check.

**Files:**
- Modified: `runner.py` — delete ~160 lines of constants. Read from `template.body_sections`, `template.synthesis_sections`, `template.default_word_targets`, `template.style_guide`, `template.system_role`. Constructor signature stays the same for backward compat; `report_type` arg now resolves via registry.
- Modified: `loaders/stock_initiation.py` — accepts the moved constants. The default-equity style guide string literal (the long block at runner.py:296-307) is now defined here.
- New: `packages/core/src/openlia/reports/frameworks/stock_initiation_brief.md` — the per-section briefs in markdown form, parsed at loader time into `SectionSpec.brief`. Optional — could also live as a Python dict in the loader; markdown is cleaner for diff review when briefs change.

**Validation:** Same test suite must pass. Re-run a smoke `stock_initiation` report against AAPL via the CLI; output must be byte-identical to a pre-refactor run (modulo timestamps).

**Risk:** Highest-touch PR of the refactor. Everything that imports `BODY_SECTIONS_STOCK_INITIATION` from `runner.py` (tests, dispatcher, telemetry hooks) needs to import from the loader or the resolved template. Grep before merging.

### PR 3 — Lift freshness budgets to per-template config

**Scope:** Bucket B item. `freshness.py` keeps its checker logic but `FRESHNESS_BUDGETS` becomes a parameter (`check_freshness(facts, as_of, budgets)`). The runner reads `template.freshness_budgets` and passes it in. Default template ships the equity-flavored budgets (current_price=7, consensus_=14, revenue_q=100, eps_annual=380, etc.).

**Files:**
- Modified: `freshness.py` — `FRESHNESS_BUDGETS` constant removed; `check_freshness` takes budgets as a param.
- Modified: `TemplateSpec` — add `freshness_budgets: dict[str, int]` field.
- Modified: `loaders/stock_initiation.py` — populate budgets from the current hardcoded values.
- Modified: `runner.py` — pass `template.freshness_budgets` into `check_freshness`.

**Validation:** Tests in `test_freshness.py` updated to inject budgets explicitly. Existing default-template runs unchanged.

**Risk:** Low. Mechanical lift.

### PR 4 — Lift identity equations to per-template config

**Scope:** Bucket B item. The hardcoded equation list in `_check_identity_equations` (price × shares = market_cap, margin × revenue = income, target_mean → upside_pct) becomes data. Each template declares its identity equations as a list of expressions referencing Fact names. The evaluator is generic.

**Files:**
- New: `validators/identity_equations.py` — `IdentityEquation` dataclass with `name`, `lhs_facts: list[str]`, `rhs_facts: list[str]`, `tolerance_pct: float`, plus an `evaluate(facts, sections_text) -> list[Failure]` function. Built-in operators: `mul`, `div`, `sum`, `pct_change`.
- Modified: `validators/numeric_consistency.py` — `_check_identity_equations` becomes a thin wrapper that loads equations from the active `TemplateSpec` and delegates to the generic evaluator.
- Modified: `TemplateSpec` — add `identity_equations: list[IdentityEquationSpec]` field.
- Modified: `loaders/stock_initiation.py` — equations re-expressed in the new declarative form. Three equations: market_cap ≡ current_price × shares_outstanding (±1%); operating_income_ttm ≡ operating_margin_ttm × revenue_ttm (±0.5pp); consensus_upside_pct ≡ (analyst_target_mean − current_price) / current_price × 100 (±0.5pp).

**Validation:** `test_numeric_consistency.py` updated so the existing equity equations are loaded from the default template's spec. New unit test: an identity equation declared in a synthetic template fires correctly.

**Risk:** Low. The evaluator is small (~80 lines). Operators are intentionally limited — anything more elaborate stays Python until a real second template asks for it.

### PR 5 — First-person voice as a per-section flag

**Scope:** Bucket B item. `_check_first_person` reads the per-section `voice` field from the active template's `SectionSpec` instead of the hardcoded `{"analyst_view", "investment_recommendation"}` set.

**Files:**
- Modified: `validators/numeric_consistency.py` — `_check_first_person(section_id, prose, template_spec)` looks up `template.section_by_id(section_id).voice`.
- Modified: `SectionSpec` — `voice` field already added in PR 1; the default equity template sets `voice="third_person_only"` on `analyst_view` and `investment_recommendation` to preserve current behavior.

**Validation:** Existing first-person tests pass with default template loaded. New test: a section with `voice="any"` does not trigger the check; a section with `voice="third_person_only"` does.

**Risk:** Low.

### PR 6 — Generalize material-events + catalyst scanners to read event classes from template

**Scope:** Bucket B item. Both scanners currently hardcode the regex patterns for their event classes. Templates declare which event classes their reports care about and the runtime composes them.

**Files:**
- Modified: `scanners/material_events.py` — `MATERIAL_EVENT_CLASSES` becomes a parameter; default exported set stays equity-flavored.
- Modified: `scanners/catalyst_pack.py` — same pattern; `CATALYST_CLASSES` parameterized.
- Modified: `TemplateSpec` — add `material_event_classes: list[EventClassSpec]` and `catalyst_classes: list[EventClassSpec]`.
- Modified: `loaders/stock_initiation.py` — re-declares the existing 7 material-event classes and 7 catalyst classes as `EventClassSpec` records.
- Modified: `runner.py` — pass the spec lists into the scanners.

**Validation:** Existing scanner tests pass against the default template's classes. New test: a template with zero material-event classes runs without invoking the scanner.

**Risk:** Medium. The regex patterns are date-tested against real news strings; care with regex compilation and feature-parity.

### PR 7 — Generalize industry-mode overlays to per-template; default template keeps current behavior

**Scope:** Bucket B item. The mode selector + overlay set become template-scoped. The default equity template ships its four overlays (generic / saas / semis / distressed) inside its own directory. Custom templates without overlays just skip the mode-selection step.

**Files:**
- Modified: `mode_selector.py` — `select_report_mode` accepts an `available_modes: list[ModeSpec]` parameter with selector rules declared per mode (industry regex, distress triggers, etc.). When `available_modes` is empty, returns `None` and no overlay applies.
- Modified: `framework_overlay.py` — overlay-loading helper takes a template-scoped overlay directory rather than a hardcoded one.
- Modified: `loaders/stock_initiation.py` — declares the four modes and points the loader at `reports/frameworks/stock_initiation/overlays/*.json`.
- File move: `reports/frameworks/report_mode_overrides/stock_initiation.*.json` → `reports/frameworks/stock_initiation/overlays/*.json`. Co-locates each template with its overlays.
- Modified: `TemplateSpec` — add `industry_modes: list[ModeSpec]`.

**Validation:** `test_mode_selector.py` and `test_framework_overlay.py` pass with re-declared modes. Equity reports must produce identical mode selection.

**Risk:** Medium. The deep-merge semantics need to be preserved exactly; existing tests cover them.

### PR 8 — Helpers as tool-callable handlers (split across 8.0 / 8a / 8b / 8c)

The original PR 8 ("append helper catalog as prose") was too thin. The right design separates *discovery* from *loading*: the model sees a lightweight manifest of available helpers in every section prompt and can fetch full docs (signature, conventions, worked example) on demand for the helpers it actually intends to call. This decouples the cost of *knowing a helper exists* from the cost of *knowing how to call it correctly*, and pushes the routing decision into the model at the moment it has the most context.

**Three load-bearing rules** govern this design — assert them as code, not docs:

1. **Helper complexity is structural, not promotional.** Each helper declares itself `simple` or `complex` at registration. Simple helpers render their full signature inline in the manifest (no inspect path needed). Complex helpers render only a one-liner; their full doc lives behind `get_helper_docs(name)`. The "inspect when in doubt" instruction operates only over the complex subset.
2. **`use_when` hints are written in contrast sets, not in isolation.** Sibling helpers (everything in `facts/helpers/valuation`, for instance) are authored together; each hint says what distinguishes it from its neighbors. The discriminative failure is sibling overlap, not isolated description quality.
3. **Per (section, helper) partition invariant.** Every helper is in exactly one of three buckets per section: `eager-fact` (pre-computed into the facts pack, suppressed from the manifest), `lazy-tool` (callable via tool-use, appears in the manifest), or `absent`. Asserted at build time: `eager_set(section) ∩ manifest_set(section) == ∅`. No helper is ever live in two modes for one section — that's how the double-compute trap is eliminated.

#### PR 8.0 — Manifest dogfood evaluation (notebook only, no code merged)

Before any execution infrastructure ships, evaluate the manifest's routing accuracy in isolation. Output is tuned `summary` + `use_when` hints, ready to wire into PR 8a.

Procedure: build the manifest strings, take ~20 real section briefs spanning the current equity template plus the Chinese 28-section sample, feed each brief + the manifest to Claude with the prompt *"Given this section brief, which helpers (if any) would you call? List by name with a one-sentence justification."*, compare against my own judgment. Iterate hints — focusing on the contrast-set rule — until disagreement on ambiguous cases drops to acceptable.

Deliverables: (a) the final hint set as a fixture, (b) a list of section briefs the manifest cannot disambiguate (informs either hint refinement or a helper-design gap), (c) classification of each existing helper as `simple` or `complex`.

#### PR 8a — `ToolHandler` protocol, registry, manifest, single-round tool use

**Scope:** The backend-agnostic execution layer. Helpers become the first concrete implementation of a generic tool-handler protocol that future PRs will reuse for uploaded-template helpers and in-section connectors.

**Files:**
- New: `packages/core/src/openlia/llm/runtime/report_v2/tools/protocol.py` — `ToolHandler` protocol and `ToolResult` envelope:
  ```python
  class ToolHandler(Protocol):
      name: str
      summary: str          # one-line description, used in manifest + tool description
      use_when: str         # contrast-set discriminator
      complexity: Literal["simple", "complex"]
      input_schema: dict    # JSON schema for arguments
      doc_path: str | None  # populated only for complex helpers

      async def execute(self, args: dict) -> ToolResult: ...

  @dataclass
  class ToolResult:
      value: Any
      citations: list[Citation]   # propagates into ReportSchema citation pool
      source_facts: list[str]     # which Facts the result depended on (telemetry)
      metadata: dict
  ```
  The `citations` field is non-optional and append-only-mutable into the manifest at tool-result time. Future web_search-as-tool work plugs in here without re-architecting citations.
- New: `tools/registry.py` — `ToolRegistry` with `register(handler)`, `get(name)`, `all()`, `available_for(section_id, template)` filtered view. Phase-scoped tool availability is a registry filter, not a dispatcher branch.
- New: `tools/helpers_adapter.py` — adapts every helper in `facts/helpers/` to the `ToolHandler` protocol. Each helper's existing function signature drives the JSON `input_schema` (Pydantic / type hints). Registration decorator enforces `summary`, `use_when`, `complexity`, and (for `complex`) `doc_path`.
- New: `docs/helpers/*.md` — one markdown file per complex helper with worked example, parameter conventions, edge cases. Simple helpers have no doc file — their full signature is in the manifest.
- Modified: `sections/prompts.py` — `assemble_body_section_prompt` appends a `## Helpers Available` manifest block built from `registry.available_for(section_id, template)`. Simple helpers render with inline signature; complex helpers render with one-liner only.
- Modified: `sections/dispatcher.py` — handles single-round tool use. Model emits tool_use → dispatcher runs handler → tool_result returned → model writes prose. No `get_helper_docs` yet; complex helpers' doc paths exist but aren't fetched.
- Modified: `TemplateSpec` and `SectionSpec` — `SectionSpec.eager_helpers: list[str]` (helpers pre-computed into facts), `SectionSpec.lazy_helpers: list[str]` (helpers exposed in the manifest). Build-time check enforces the partition invariant.
- Modified: `packer/assembler.py` — `_build_cover` reads `template.cover_bindings`.
- Modified: `ReportSchema` citation pool — append-only-mutable at tool-result time.

**Validation:** All existing equity tests pass with helpers exposed as `lazy-tool` only for sections that currently *don't* eager-compute them. The default template's existing eager bindings (e.g. `peer_multiple_implied_range` pre-computed into the `valuation_analysis` facts slice) remain `eager-fact` and are suppressed from those sections' manifests. New test: partition invariant assertion fires when a template declares the same helper in both `eager_helpers` and `lazy_helpers` for a section.

**Risk:** Medium. Largest single PR in the series; touches dispatcher, prompt assembly, registry, and schema. Mitigation: the dispatcher tool-use loop is single-round in this PR; multi-round (and `get_helper_docs`) wait for 8b. Validates the routing layer in isolation before adding the inspect layer.

#### PR 8b — `get_helper_docs` meta-tool, multi-round tool use, typed round telemetry

**Scope:** Adds the inspect layer for complex helpers, the round budget mechanic, and the typed-round telemetry that makes degradations diagnostic.

**Files:**
- New: `tools/meta.py` — `get_helper_docs(name: str) -> str` meta-tool. Reads `doc_path` from the registry, returns the markdown. Cached per-run.
- Modified: `sections/dispatcher.py` — multi-round tool-use loop. Per attempt: max-rounds cap (default 8), parallel tool_use blocks supported, rounds typed at telemetry time.
- Modified: `telemetry.py` — `ToolRoundEvent` with `round_type: Literal["inspect","call","error"]`, `tool_name`, `args_validated`, `result_null`, `elapsed_ms`. Per-section terminal-state metadata aggregates round counts by type.
- Modified: `types.py` — new `SectionTerminalState.DEGRADED_CAP_HIT` for cap-out cases. On cap hit: dispatcher emits prose with the helper results gathered so far and flags the section in metadata. Renderer surfaces a banner ("This section was generated with incomplete tool-call data; specifically: <attempted-but-uncalled helpers>"). One degraded section does not sink the report.
- Optional structural prompt cue (added only if PR 8a measurement shows the model serializes inspects unnecessarily): a single explicit "identify all helpers this section needs" step before any inspection, encouraging the model to group inspect calls into one parallel turn. Decision: ship the neutral prompt in 8a; measure; add the cue here in 8b only if rate is bad.

**Validation:** Multi-round dispatch on a synthetic section that requires inspecting two complex helpers; degraded-cap-hit path triggered by capping at 2 rounds on a 3-helper section. Telemetry surfaces the round-type distribution and the renderer surfaces the degradation banner.

**Risk:** Medium. The cap mechanic plus graceful degrade plus telemetry tagging is independently testable; the prompt-cue addition is conditional on measurement.

#### PR 8c — Template-declared `preload_helpers` (matrix-driven preflight)

**Scope:** Closes the partition matrix loop. Templates declare per-section preload bindings; the facts-pack builder reads them; eager-bound helpers are pre-computed and suppressed from the manifest for that section.

For the default equity template, existing eager bindings stay where they are (no behavior change). For uploaded templates, `preload_helpers` is populated either by the markdown frontmatter (power-user opt-in) or left empty (lazy-tool only — works fine via manifest discovery, just costs round trips).

**Files:**
- Modified: `facts/pack.py` — facts-pack builder iterates `template.section_by_id(sid).eager_helpers` and pre-computes each, storing results as Facts in the slice.
- Modified: `sections/prompts.py` — manifest excludes any helper in the section's `eager_helpers`.
- Modified: `loaders/stock_initiation.py` — declares the current eager bindings explicitly (was implicit via fact-extractor JSON).
- New: build-time invariant check in `template_spec.py` constructor — raises if any section's `eager_helpers ∩ lazy_helpers != ∅`.

**Validation:** Identical-output smoke run against the default equity template (the eager bindings already existed implicitly; making them explicit shouldn't change output). Custom-template smoke: a template with frontmatter `preload_helpers: [peer_multiple_implied_range]` on a section pre-computes that helper and excludes it from the manifest.

**Risk:** Low. The mechanic is already implicit in the current pipeline; this PR makes it declarative and adds the invariant assertion.

#### PR 8d — Helper bundle: three-scenario forecast, DuPont, catalyst horizon, consensus-vs-three-scenarios

**Scope:** Four small helper additions surfaced by gap analysis against a representative custom template (Chinese 28-section framework). Each ships as a registered handler with `summary`, `use_when`, complexity classification, doc_path (for complex helpers), and unit tests. Ships after the 8a/b/c registry/manifest infrastructure so each helper plugs in via the same `ToolHandler` protocol.

**Files:**
- New helper in `facts/helpers/forecast.py`: `three_scenario_forecast(base_facts, conservative_deltas, optimistic_deltas) -> dict[Literal["conservative","neutral","optimistic"], list[float]]`. Neutral path = base; conservative/optimistic apply per-line deltas to revenue growth, gross margin, opex/rev across a 3-year horizon. Complex helper (parameter conventions and a worked example matter — bounded deltas, what "delta" means per line). `docs/helpers/three_scenario_forecast.md` carries the worked example.
- New helper in `facts/helpers/returns.py`: `dupont_decomposition(net_income, revenue, total_assets, equity) -> {net_margin, asset_turnover, equity_multiplier, roe_check}`. Returns the three components plus a reconciliation check that the product equals ROE within tolerance. Simple helper (signature inline in manifest).
- New helper in `facts/helpers/forecast.py`: `consensus_vs_three_scenarios_table(scenarios, consensus_facts)`. Takes the output of `three_scenario_forecast` plus consensus revenue/EPS facts and emits a comparison row per scenario (delta vs consensus mean, % above/below). Simple helper.
- Modified `scanners/catalyst_pack.py`: extend `CatalystEvent` with `time_horizon: Literal["3m","3-12m","1-3y"] | None` computed from the event date relative to report-as-of date. New helper `catalysts_by_horizon(catalysts_recent) -> dict[horizon, list[CatalystEvent]]` buckets the existing flat list. Simple helper.

**Validation:** Per-helper unit tests covering happy path + edge cases (e.g. `three_scenario_forecast` with conservative deltas that drive revenue to zero). Smoke: a synthetic section brief that asks for "conservative / neutral / optimistic FY+1/+2/+3 revenue and EPS" invokes `three_scenario_forecast` via the tool registry and renders a three-column table.

**Risk:** Low. Self-contained helpers; no dispatcher / registry / schema changes beyond the new registrations.

---

After PR 8, the refactor is complete. The runner is template-agnostic, the default equity template behaves identically to today's output, and the system is ready for user-uploadable templates. The remaining PRs (9-11) build the upload pipeline.

### PR 9 — Template storage: DB table, server routes, basic CRUD

**Scope:** Backend foundation for storing user-uploaded templates. No LLM extraction yet — this PR accepts a JSON `TemplateSpec` payload via API and stores it. Lets us test the runtime side end-to-end before adding ingest complexity.

**Files:**
- New: `packages/server/src/openlia_server/db/models/report_template.py` — SQLAlchemy `ReportTemplate` model with `id`, `user_id`, `name`, `template_spec` (JSON column), `source_doc_blob` (nullable, for the original upload), `source_doc_mime`, `created_at`, `updated_at`.
- New: Alembic migration for the table.
- New: `packages/server/src/openlia_server/routes/templates.py` — REST endpoints: `GET /api/templates` (list user's templates), `POST /api/templates` (create from JSON spec), `GET /api/templates/{id}`, `PUT /api/templates/{id}`, `DELETE /api/templates/{id}`.
- Modified: `packages/server/src/openlia_server/routes/reports.py` — accept optional `template_id` on the report-create request; resolves to a `TemplateSpec` and passes it into `WavedReportRunner`.

**Validation:** Server tests cover CRUD + auth (only the owning user sees their templates). Integration test: create a template via API, generate a report with `template_id` set, confirm the runner used the custom template.

**Risk:** Low. Standard CRUD + auth. The interesting work is in PR 10-11.

### PR 10 — Document ingest (docx / md / text → markdown)

**Scope:** The mechanical conversion step. User uploads a `.docx`, `.md`, or `.txt`; server returns clean markdown.

**Files:**
- New: `packages/server/src/openlia_server/services/template_ingest.py` — single function `ingest_document(blob: bytes, mime: str) -> str`. Uses `mammoth` for docx (preserves headings + lists, drops styles), passthrough for md, simple wrap for txt.
- Modified: `routes/templates.py` — `POST /api/templates/upload` accepts multipart file, calls `ingest_document`, returns markdown for client preview.
- Frontend new: `frontend/src/pages/Settings/CustomTemplates.tsx` — minimal UI: file picker, preview pane showing extracted markdown, "looks right?" confirm button.

**Validation:** Unit tests against the Chinese 28-section docx sample plus 2-3 simpler markdown / txt samples. Heading hierarchy must round-trip.

**Risk:** Low. `mammoth` is a well-established docx parser. Edge cases: embedded tables, images (ignored for v1), complex numbered lists.

### PR 11 — Mechanical boundary detection + frontmatter parser + review UI

**Scope:** Collapsed from the original "LLM-assisted extraction" design. No LLM call in the parse path. The markdown's own heading structure determines section boundaries; an optional frontmatter convention (§6) supplies declarative overrides for power users. The user's prose is the section brief, passed verbatim to the section-writing LLM at runtime — no extraction, no summarization, no silent-error class.

**Files:**
- New: `packages/server/src/openlia_server/services/template_parser.py` — single pure function `parse_template(markdown: str) -> ParsedTemplate`. Splits on H1/H2 boundaries; first segment before the first heading becomes `global_preface`; each subsequent heading + body becomes one `Section(id=slugify(heading), title=heading, brief=body, frontmatter=…)`. Frontmatter is YAML in a comment-fenced block at the top of each section body (see §6 spec); when present, its keys populate the optional `SectionSpec` fields. Total implementation: ~150 lines including frontmatter parsing.
- Modified: `routes/templates.py` — `POST /api/templates/parse` returns the `ParsedTemplate`. Save is a separate `POST /api/templates` call; the user reviews boundaries between parse and save.
- Modified: `CustomTemplates.tsx` — review step shows the parsed section list ("we identified N sections at these headings") with the ability to merge adjacent sections or split a section by inserting a new boundary. The user can also edit the source markdown directly in a panel and re-parse; the prose itself is what flows through at runtime, so editing the markdown IS editing the template.
- New: `frontend/src/components/templates/TemplateReview.tsx` — boundary review component. Left pane: source markdown with heading anchors. Right pane: section list with merge/split controls and frontmatter preview where present.

**Validation:** Parse the Chinese 28-section `.docx` sample (after PR 10's mammoth conversion) and confirm 28 sections detected at the §N headings, the 五大原則 / 啟動流程 preamble caught as `global_preface`. Unit tests for: frontmatter present / absent / malformed; nested headings (H3 stays inside its H2 parent's brief); empty sections; duplicate slugified IDs (numeric suffix disambiguation).

**Risk:** Low. Mechanical parsing has deterministic, debuggable failure modes. The original PR 11's silent-extraction class is eliminated entirely.

### PR 12 — Post-report meta-section dispatch tier

**Scope:** Adds a third dispatch tier — *meta* — that runs after every body + synthesis section completes, with the full concatenated report markdown injected into the prompt. Enables templates with §28-class sections (self-audit, blind-spot review, summary commentary, pre-mortem). Required for the Chinese template's §28 Mode A self-audit and likely for any template with a serious review-pass section.

**Architectural minimum:** A section opts into `dispatch_tier: "meta"` via SectionSpec; the runner adds a third dispatch loop after synthesis completion; meta-section prompt assembly injects the concatenated body+synthesis markdown alongside the section's brief. Universal validators (block shape, tombstone, year-label, numeric-not-in-facts) apply. The first-person voice check respects the section's `voice` flag (meta sections that want a persona-driven first-person voice — like §28 Mode A's "you are now a Goldman analyst" — set `voice: any`, which is the default).

**Persona instructions stay in the prose.** The Chinese template's §28 Mode A contains five specific reset instructions ("forget what you wrote," "minimum 7 blind spots," "attack the strongest pillar," "Pre-Mortem 3 failure scenarios," "forced final stance"). Under the prose-as-brief model these flow through to the LLM as part of the brief — no per-section `system_role` override is required. If a template wants a different persona, the prose handles it.

**Files:**
- Modified: `template_spec.py` — `SectionSpec.dispatch_tier: Literal["body","synthesis","meta"] = "body"`. `TemplateSpec.meta_sections` computed property filtering by tier.
- Modified: `runner.py` — third dispatch loop after `synthesis_dispatch` completes. Each meta section receives a `MetaSectionDispatch` (extends `SectionDispatch`) with a `report_markdown: str` field carrying the concatenated body + synthesis output.
- New helper in `sections/prompts.py`: `assemble_meta_section_prompt(spec, brief, report_markdown, facts, helpers_manifest)` builds the prompt: section brief → `## Full Report Context` block with the concatenated markdown → helpers manifest → output format reminder.
- Modified: `validators/numeric_consistency.py` — meta sections validated identically to body/synthesis; voice check reads the section's `voice` flag as established in PR 5.
- Modified: `telemetry.py` — `ToolRoundEvent.dispatch_tier: Literal["body","synthesis","meta"]` for diagnostic tagging.

**Validation:** Default equity template has no meta section → identical-output smoke passes unchanged. Synthetic test template with one meta section ("summarize the report's strongest argument in 50 words") successfully receives the concatenated markdown. Chinese template's §28 Mode A with frontmatter `dispatch_tier: "meta"` produces a coherent self-audit that references earlier sections by content (e.g. "the Bull Case in §25 leans heavily on Blackwell adoption [c5]; the most credible attack on it would be…").

**Risk:** Medium. Token-budget audit required — the concatenated markdown can be 9-15K tokens for a 15-section template before the meta section's own brief and tools are added. Meta tier is opt-in; default templates have none; the universal contract is unchanged. Mode B (cleared-context sub-agent) is **not** in this PR — it's documented as a v2 follow-up.

---

## 6. Optional frontmatter convention (power-user opt-in)

The default execution model is prose-only: upload markdown, runtime reads the prose. For users who want declarative control beyond what they can express in prose, sections may carry an optional YAML frontmatter block at the top of the section body. The parser reads it mechanically; missing or malformed frontmatter is ignored without error.

Per-section frontmatter is fenced in an HTML comment so it doesn't render visually if the markdown is ever viewed standalone:

```markdown
## §16 Scorecard

<!-- openlia
voice: third_person_only
word_target: 800
preload_helpers:
  - peer_multiple_implied_range
  - historical_pe_band
required_facts:
  - segment_revenue_latest
  - analyst_consensus_rating
-->

(section prose, the brief, verbatim)
```

Template-level frontmatter sits at the top of the document, before any heading:

```markdown
<!-- openlia
name: 公司深度研究框架 v2.3.1
freshness_budgets:
  current_price: 7
  analyst_: 30
identity_equations:
  - name: upside_reconciliation
    lhs: consensus_upside_pct
    rhs: (analyst_target_mean - current_price) / current_price * 100
    tolerance_pct: 0.5
cover_bindings:
  consensus_rating: analyst_consensus_rating
  consensus_target_mean: analyst_target_mean
-->

# (document body starts here)
```

Supported per-section keys: `voice`, `word_target`, `preload_helpers`, `lazy_helpers`, `required_facts`. Supported document keys: `name`, `freshness_budgets`, `identity_equations`, `cover_bindings`, `material_event_classes`, `catalyst_classes`. Unknown keys are ignored with a warning surfaced in the review UI.

The frontmatter is the bridge between "upload prose, get soft-floor universal contract" and "declarative rigor like the default equity template." Users who want the rigor can climb toward it one declaration at a time; users who don't never see it.

---

## 7. What stays out of scope for v1

These were considered and explicitly deferred:

- **Conditional sections** (§16.3 only when Scorecard < ★★★ in the Chinese template). Requires a runtime gating mechanism where one section's output feeds a downstream decision. Doable as a follow-up; v1 dispatches every section in the catalog unconditionally.
- **Mid-run `AskUserQuestion` workflow steps**. The Chinese template has Steps 1, 5 that ask the user for input partway through. v1 maps these to *pre-run* setup forms (the existing scope picker), not in-flight pauses.
- **Sub-agent review pass (Mode B blind-spot review).** A second LLM pass with a different system prompt on the finished report. Worth building eventually as a generic "review pass" capability that any template can opt into. Out of scope for v1.
- **`.docx` output rendering.** v1 sticks with the existing HTML/PDF renderer.
- **Helper authoring by users.** v1 ships with the existing equity-flavored helper catalog. Users can choose which helpers their template binds but can't define new ones. Adding user-defined helpers is a security and review problem in itself.
- **Multiple report types per template.** A `TemplateSpec` corresponds to one report type. A user's "earnings update" template and their "stock initiation" template are separate `ReportTemplate` rows.
- **Sharing / marketplace.** Templates are user-scoped. Cross-user sharing comes later.
- **Versioning history of a template.** Each save overwrites; v1 has no history. Trivial to add later if demand exists.

---

## 8. v2 follow-ups (identified during template gap analysis)

These items surfaced during a gap analysis of a real user-uploaded template (the Chinese 28-section 公司深度研究框架 v2.3.1) against the v1 engine described in §5. They are catalogued here as forward roadmap items, **not** as v1 commitments.

**Guiding principle:** fix what we've already built first. Stabilize the v1 engine — the universal contract, the prose-as-brief runtime, the tool registry and helpers — and prove it against ≥2 distinct user-uploaded templates before expanding the capability surface. None of the items below are required to ship a useful first version; they are upgrades whose value will be clearer after v1 telemetry comes back.

### Interactivity / orchestration

- **Conditional section dispatch** (e.g. §16.3 triggered when an upstream section produces a Scorecard score < ★★★). v1 dispatches every section unconditionally; the LLM writes graceful-no-op prose when the trigger condition isn't met. Future work: declarative `trigger_when: <expression over prior section outputs>` field on `SectionSpec`; dispatcher evaluates after the dependency section completes and either runs or skips.
- **Mode B sub-agent review pass** (cleared-context separate LLM thread). v1 supports Mode A via the meta-section tier (PR 12); Mode B requires a new orchestration pattern with a fresh conversation thread and no prior system-prompt continuity. Deferred until we see whether Mode A alone is sufficient in practice.
- **AskUserQuestion mid-run** — Step-5 blind-spot mode picker, > 8000-word chunked output with continuation confirm, any other section-boundary user-confirm pause. v1 maps these to pre-run setup-form inputs. Future work: section-boundary pause + resume with stored interim state.
- **`.docx` output rendering**. v1 is HTML/PDF only via the existing renderer.

### Data layer and capability extensions

- **Multi-quarter earnings call transcript time-series analysis** (§13.2-class keyword-frequency tracking across last 4-8 quarters with ↑↑ / ↑ / ↓ / 迴避 annotations). Requires a transcript fetcher (new data adapter — Seeking Alpha / Motley Fool / Quartr or equivalent), per-call structured LLM extraction stored as time-keyed Facts, and a comparison helper that produces the trend table. New pre-section pipeline.
- **Industry-level facts entity** (Part-I-class TAM/SAM/SOM, industry CAGR cross-checked against ≥2 research houses, Porter Five Forces scoring inputs, S-curve positioning). Requires an `IndustryEntity` alongside the current `TickerEntity` in the facts model — new entity type, new pack, new manifest section, possibly new data sources.
- **Deep per-peer KSF-aligned facts** (Scorecard-class per-peer R&D intensity, customer concentration, capex moat depth, talent retention). Extends the peer extractor breadth from "multiples + market cap" to "full KSF dimensions across 5 peers" — multiplies fundamentals + filings extraction per report.
- **Investor Day target archive + achievement tracking** (§13.3-class compare-prior-targets-to-current-actuals). Requires a historical-announcement store with point-in-time target capture and retrospective comparison helpers.

### Already resolved by the v1 architecture (no follow-up needed)

- **Template-authored verdicts** (rating, price target, stop loss, position size, Bear Case Steelman, entry/exit triggers). Previously blocked by the hardcoded English style guide forbidding first-person voice and OpenLIA-authored targets. Resolved by the soft-floor architecture in §5: uploaded templates own voice; verdict-bearing prose flows through. Confirmed working under the v1 plan.

---

## 9. Backward compatibility and migration

After PR 1-8 the default equity template's *behavior* is identical to today, but its *configuration* lives in a different shape. The migration story:

1. Existing report-generation API calls (`POST /api/reports` with `report_type=stock_initiation`) work unchanged — the resolved `TemplateSpec` is loaded from the registry by name.
2. Existing tests reference `BODY_SECTIONS_STOCK_INITIATION` and similar Python constants. After PR 2 these are re-exported from `loaders/stock_initiation.py` to keep the imports working; later migration to read from `TemplateSpec` is a tidy-up, not a blocker.
3. The `style_guide` parameter on `WavedReportRunner.__init__` stays as a runtime-override path. When not provided, the template's bundled style guide applies.
4. SSE event stream payloads unchanged. Telemetry record structure unchanged.

The one user-visible difference between pre- and post-refactor: any framework JSON edits made directly to `stock_initiation.json` need to be re-mapped onto the new loader after PR 2 (the section briefs move out of the JSON into the loader markdown). Worth surfacing in the PR 2 description.

---

## 10. Testing strategy

Each PR ships with the unit tests for its own additions plus a regression check on the existing test suite. The cross-cutting smoke test:

1. **The "identical-output" smoke** — after each refactor PR (1-8), run a `stock_initiation` report against a fixed ticker (e.g. AAPL) and diff against a stored golden output. Allow only timestamp differences. Catches any accidental behavior drift during the lift.
2. **The "minimal custom template" smoke** — once PR 9-11 land, the simplest possible custom template (3 sections, no helpers, no equations, no voice rules) must produce a coherent report. Catches over-eager assumptions in the runtime that depend on equity-flavored config.
3. **The "Chinese 28-section template" smoke** — final acceptance bar. Upload the user's `公司研究框架_v2_3_1` docx, run the extractor, review the result, save, generate a report against NVDA. Output must (a) not crash, (b) have all 28 sections, (c) honor the per-section voice flags, (d) cite Facts where the template asks for citations. Quality of analysis is the template author's responsibility; the machine's job is to make the framework run.

---

## 11. Success criteria

The initiative is done when:

- The runner has zero hardcoded section IDs, briefs, style guide strings, fact-name lookups, or equity-domain assumptions outside of the explicit "default template loader."
- A user can upload a `.docx` / `.md` / `.txt` via the UI, review the extracted `TemplateSpec`, save it, and generate a report against any ticker using that template.
- The default `stock_initiation` template produces identical output to the current production behavior — every test in the existing report_v2 suite passes unchanged in semantics (with possibly different imports).
- The Chinese 28-section template, after upload + review + save, generates a non-crashing report whose section structure matches the uploaded template.
- The universal contract in §2 holds for every template: every Fact has provenance, stale data is gated, block shapes are validated, retries happen, tombstones are rejected, citations resolve.

---

## 12. Open product questions before code starts

These are worth a quick alignment before PR 1.

- **Q1 (resolved).** Helper catalog visibility: manifest + on-demand inspect, per the design in §5 PR 8.0/8a/8b/8c. Partition invariant enforced at build time. Dogfood loop precedes implementation infra.
- **Q2 (resolved).** Template review UI is **minimal**: left pane source markdown with heading anchors, right pane parsed section list with merge/split controls. Editing the markdown is the editing path; the parser is a pure function over whatever the user wrote. Inline form controls for frontmatter fields are deferred until usage shows users struggling with YAML syntax.
- **Q3 (moot).** LLM extractor's silent-error class is eliminated by the no-extractor architecture in §5 PR 11. The parser is mechanical; section boundaries from headers are deterministically verifiable; everything else is the user's own prose.
- **Q4 (resolved).** Missing required fact at render time → **skip the section** with a banner ("Section X omitted: required fact `segment_revenue_latest` unavailable for this subject"). Preserves the rest of the report and gives the user a clear, actionable signal. Hard run-fail is reserved for universal-contract violations (stale data, material events) where override flags already exist.
- **Q5 (moot).** No extractor prompt to locate.
