# Waved Report Runner — Design

**Date:** 2026-05-17
**Status:** Draft — pending implementation plan
**Branch (planned):** `feat/waved-report-runner`
**Predecessor PRs:** [#122](https://github.com/TK-Chang239/OpenLIA/pull/122), [#123](https://github.com/TK-Chang239/OpenLIA/pull/123), [#126](https://github.com/TK-Chang239/OpenLIA/pull/126) (F1–F23 fix series)
**Reference:** [`docs/equity-research-stock-initiation-prompts.md`](../../equity-research-stock-initiation-prompts.md) (current 11-layer prompt architecture)

---

## Problem

The current `ReportRunner` (and the partially-built `SubagentReportRunner`) ask one model call to do two fundamentally different jobs in a single pass: analytical writing and strict-schema serialization. The 23-fix F1–F23 series across four PRs has been remediation work against symptoms of that single architectural choice. The six recurring failure themes are:

1. **Schema-drift** — model emits citations at wrong nesting (`rail.citations` vs root), uses `c1/c2` shorthand instead of `[N]` markers, misses required fields under cognitive load mid-narrative.
2. **Citation invention** — model fabricates inline citation tuples, formats them inconsistently, places them in the wrong location.
3. **"Fetched but unused"** — `cover.key_metrics` populates with "No Data Available" despite the model having fetched the underlying fundamentals payload. Mid-narrative, the model forgets to pull values from payloads three turns back.
4. **Narrative thinness** — sections punt with "data not available" when search comes back empty, instead of using the search budget aggressively.
5. **Whole-report repair cost** — a single drift in section 9 forces re-emission of sections 1–8 that were already perfect. Repair budget exhausts on systemic drift, not surgical fixes.
6. **Cross-section numeric inconsistency** — revenue CAGR appears in 4 sections with slightly different values because each section re-derives it from the same raw data.

The common cause: a single writer model is asked to handle retrieval, computation, narrative writing, schema serialization, and citation formatting simultaneously. Every layer of the F-fix stack is doing remediation work against that conflation.

## Goal

Replace both existing runners with one architecturally clean runner that codifies a single load-bearing principle:

> Gather all data first, then write. Writing and retrieval are different cognitive tasks; the second one ruins the first.

Everything in this design is structural codification of that principle.

## Non-goals

- Re-design the rendering layer (charts, tables, PDF export) — those keep their current strict-schema contract; the new runner produces the same `ReportSchema` payload.
- Change the report viewer UI or SSE event contract.
- Replace runners in other departments — `Earnings Update`, `Macro Research`, `Retail Sentiment`, etc. stay on their current paths.
- Build a revision-pass infrastructure for the `[SEARCH:]` discovery gap — telemetry first, build only if signal warrants.
- Introduce a model-tier fallback (e.g., cheap-then-Opus) — silent fallback hides which sections are failing on which tier.

## Cutover strategy

Single new runner replaces both existing runners. Classic `ReportRunner` (`report.py`, 1646 lines) and `SubagentReportRunner` (`subagent_runner.py`, 637 lines + ~5 helper modules) are deleted on cutover. Feature flag during dev for side-by-side diff comparison; flag removed when new runner is confirmed faithful.

## Working name

`WavedReportRunner`. Open to `StagedReportRunner` or `ManifestReportRunner` if those read better at the call site.

---

## Architecture overview

Six waves, executed in order. Each wave's output becomes a stable, citable artifact for the wave below it. The writer model only fires in W4 and W5, and only ever emits Markdown — never structured JSON against a strict schema.

| Wave | What runs | Output |
|---|---|---|
| **W1. Baseline fetch** | Hard-coded always-required data fetches for the report type (deterministic, parallel) | Manifest entries `[1]..[K]` |
| **W2. Per-section pre-flight** | One cheap (Haiku-tier) structured-output call per section declares the additional searches and fetches that section needs. Aggregated across sections, deduped, executed centrally | Manifest entries `[K+1]..` |
| **W3. Facts compile** | Framework-declared facts extracted via the named registry using three extractor tiers (deterministic, compute, LLM). DAG dependency ordering | Single `facts_pack` artifact, citation-tagged |
| **W4. Body write** | 11 body sections dispatched in parallel. Each receives stable cached prefix + per-section facts slice + framework section brief. Emits Markdown + typed fenced YAML blocks + `synthesis_hooks` frontmatter. **No tool calls during write.** Per-section repair within the wave | 11 section Markdown documents |
| **W5. Synthesis write** | 4 synthesis sections dispatched in parallel after W4 fully settles (all body sections in terminal state — success, degraded, or exhausted). Synthesis writers see the compact `synthesis_hooks` bullet list (~700 tokens), not full body prose | 4 section Markdown documents |
| **W6. Pack** | Deterministic packer parses each section file, runs semantic validation, per-section auto-repair, per-section retry with structured error on hard fail. Fills rigid schema slots (`cover.key_metrics`, `rail.*`) directly from facts pack | Strict `ReportSchema` payload |

### Why this kills the six failure themes

| Failure theme | How it dies |
|---|---|
| 1. Schema-drift | Model never sees the strict schema. Packer owns all field-name/enum/nesting decisions in Python. |
| 2. Citation invention | Citations exist before the writer dispatches. Writer emits `[N]` markers against a numbered manifest it was handed. |
| 3. "Fetched but unused" | `cover.key_metrics` and other rigid envelope fields are populated by the packer from facts pack. Writer literally cannot fail to populate them because writer doesn't write them. |
| 4. Narrative thinness | Pre-flight wave declared section's data needs upfront; data is in the facts pack and manifest before write dispatches. Writer cannot punt because the data is in its prompt. |
| 5. Whole-report repair cost | Repair scope = one section, not one report. One section failing 14× of nothing instead of 14× of everything. |
| 6. Cross-section numeric inconsistency | Named-fact registry guarantees `revenue_cagr_3y` is one computed value across the whole run. Cross-section semantic validation (W6) flags any prose that re-quotes a different number. |

---

## W1 — Baseline fetch

Hard-coded per report type. For `stock_initiation`:

- Live price
- Fundamentals (EODHD `get_fundamentals_data`)
- Historical market cap
- 60-day price history (sparkline)
- 5-year price history (trends)
- 5-year income statement
- 5-year balance sheet
- 5-year cash flow statement
- Earnings trends
- Recent news (last 30 days)
- Top holders
- Insider transactions

~12 calls, all parallelizable. Each becomes a manifest entry with a stable `[N]` index. Failure to fetch a baseline source does NOT block the wave — the manifest records the failure and downstream waves see a missing entry; sections that depend on it surface the gap via the packer's `fetched-but-unused` inverse check.

## W2 — Per-section pre-flight

One Haiku-tier structured-output call per section. Each call sees:

- Section's framework brief (instructions + required outputs)
- The W1 manifest already built (`[1]..[K]`)
- The registry catalog (so the model knows what fact names already exist)

The call emits:

```yaml
searches: [{query: str, intent: str}, ...]
fetches: [{provider: str, tool: str, args: {}}, ...]
proposed_facts: [str, ...]   # NEW fact names this section thinks should exist but don't
```

**`proposed_facts` is telemetry-only.** It never adds new facts at runtime. It logs which sections are signaling for new framework-declared facts, so the developer can review and add registry entries deliberately.

Aggregator dedupes searches and fetches across all 14 sections, executes them centrally in parallel, appends results to the manifest as `[K+1]..`.

**No section ever performs a tool call during W4/W5 writing.** This is deliberate. Inline search escape hatches are how writers learn to lean on retrieval mid-prose, which re-creates the cognitive overload the architecture is built to avoid.

## W3 — Facts compile

A single named-fact registry with three extractor tiers, all registered by name.

### Extractor tiers

- **Deterministic** — JSONPath / Pydantic against fixed-shape provider payloads. Examples: `current_price`, `market_cap`, `sector`, `officers`, raw income statement rows.
- **Compute** — Pure Python math on already-extracted facts. Examples: `revenue_cagr_3y`, `gross_margin_ttm`, `fcf_yield`, `peer_avg_pe`.
- **LLM** — Tiny Haiku structured-output calls for fuzzy judgment. Examples: `peer_set` (which companies belong in the comp set), `business_model_one_liner`, `valuation_methods` (which DCF/comp/sum-of-parts methods are appropriate for this company).

### Registry shape

**Python decorators with optional YAML overrides.**

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/deterministic.py

@register_fact("current_price", tier="deterministic", depends_on=["live_price_payload"])
def current_price(payloads: PayloadView) -> Fact:
    return Fact(
        name="current_price",
        value=payloads["live_price"]["price"],
        source_ids=[payloads.manifest_id_for("live_price")],
    )
```

```python
# packages/core/src/openlia/llm/runtime/report_v2/facts/extractors/compute.py

@register_fact("revenue_cagr_3y", tier="compute", depends_on=["revenue_annual"])
def revenue_cagr_3y(facts: FactView) -> Fact:
    revenues = facts["revenue_annual"].value
    cagr = ((revenues[-1] / revenues[-4]) ** (1/3)) - 1
    return Fact(
        name="revenue_cagr_3y",
        value=cagr,
        source_ids=facts["revenue_annual"].source_ids,  # inherit via union
    )
```

YAML lives only for the per-report-type fact requirements list (`stock_initiation.facts.json`) that maps section name → list of registered fact names. Extractor logic stays in Python — debugging YAML-as-config-language is exactly what the registry exists to avoid.

### Fact contract

```python
@dataclass
class Fact:
    name: str
    value: Any
    source_ids: list[int]    # manifest [N] entries; union of inputs for compute/LLM tiers
    extractor: Literal["deterministic", "compute", "llm"]
    depends_on: list[str]    # other fact names
```

### Citation provenance composition

- **Deterministic facts** inherit `source_ids` from the manifest entry of the payload they read.
- **Compute facts** inherit the union of `source_ids` from all input facts.
- **LLM facts** inherit the union of `source_ids` from all payloads passed in the prompt.

Union is the default for all three. Explicit in the Fact dataclass to ensure no extractor silently drops provenance.

### Compile phase

1. Read `stock_initiation.facts.json` → flatten unique fact names across all sections.
2. Topologically sort by `depends_on`.
3. Run extractors in DAG order. Deterministic + compute extractors are pure functions; LLM extractors run in parallel where the DAG allows.
4. Produce `facts_pack`: `dict[fact_name, Fact]`.

### Slicing per section

At W4/W5 dispatch, each section gets a slice: only the facts named in its framework declaration, rendered as a labeled, citation-tagged block:

```
FACTS FOR THIS SECTION:
  current_price: 89.43 USD (sources: [3])
  market_cap: 30.2B USD (sources: [3])
  pe_ratio_ttm: 142.1 (sources: [3])
  revenue_cagr_3y: 23.4% (sources: [7, 8, 9])
```

The writer cannot punt because the data is right there, formatted, and citable.

---

## W4 — Body write

**11 body sections, dispatched in parallel:**

1. `company_overview`
2. `industry_overview`
3. `products_and_services`
4. `business_model`
5. `management_team`
6. `historical_financials`
7. `financial_analysis`
8. `financial_projections`
9. `valuation_analysis`
10. `competitive_analysis`
11. `recent_developments`

### Section dispatch contract

Prompt assembly order (for cache efficiency):

```
[CACHED ACROSS RUNS OF SAME REPORT TYPE]
System role (section subagent)
Style guide
Framework section brief

[CACHED WITHIN RUN — varies per company]
Manifest (numbered [1]..[K+N])

[PER-SECTION DYNAMIC]
Facts slice for this section
Word target
Output format reminder (Markdown + typed fenced YAML blocks + synthesis_hooks frontmatter)
```

Framework portion is placed **before** the facts pack slice deliberately. Facts vary per company; framework is stable per report type. This ordering maximizes cross-run cache hit on the framework prefix.

### Section output format (Option E)

Each section emits a single Markdown document:

```markdown
---
section_id: industry_overview
title: Industry Overview
sources_used: [1, 3, 7, 12]
web_searches_used: 4
synthesis_hooks:
  thesis_contribution: "Cloudflare's edge platform sits in a TAM growing 22% annually..."
  bull_case_inputs:
    - "Edge compute market expanding 28% CAGR through 2028 [12]"
    - "Cloudflare gaining share vs Akamai in enterprise tier [7]"
  bear_case_inputs:
    - "Hyperscalers (AWS, GCP) compressing margins on basic CDN [3]"
---

## Industry Overview

The content delivery and edge platform market reached $24.6B in 2025 [12]...

```chart:combo
type: line+bar
title: Edge Platform Market TAM 2020–2028E
x_axis: year
series:
  - name: Market size ($B)
    values: [...]
sources: [12]
```

Cloudflare's position within this market...
```

### Fenced block types

Catalog deferred to implementation plan (largest single chunk of packer work). Initial types expected:

- `table` — tabular data with column metadata
- `chart:combo`, `chart:line`, `chart:bar`, `chart:pie` — typed chart specifications
- `metric_cards` — key metric grids
- `key_finding` — highlighted analytical conclusions
- `quote` — verbatim quotations with attribution
- `peer_comp` — peer comparison tables

Each type has its own YAML schema, validator rules, and packer parser. Schema design lives in the implementation plan.

### synthesis_hooks contract (framework-declared)

```yaml
synthesis_hooks:
  thesis_contribution: str             # ≤30 words, this section's contribution to the investment thesis
  bull_case_inputs: list[str]          # 1–3 items, each ≤25 words, each with at least one [N] marker
  bear_case_inputs: list[str]          # 1–3 items, each ≤25 words, each with at least one [N] marker
```

Body writers cannot improvise this shape; the framework JSON declares it per body section, and the packer's auto-repair pass enforces it (with retry on hard fail). Synthesis writers receive these hooks across all body sections as their primary cross-section context.

---

## W5 — Synthesis write

**4 synthesis sections, dispatched in parallel after W4 fully settles:**

1. `competitive_advantages_and_weaknesses` — promoted from the original framework body to W5 because it's structurally synthesis (pulls from `competitive_analysis`, `financial_analysis`, `business_model`).
2. `risk_analysis` — also synthesis; the most consequential risks emerge from body analysis, not from pre-fetchable risk-factor data.
3. `investment_recommendation` — explicit synthesis section (buy/hold/sell + target price + thesis).
4. `cover` — TL;DR + tagline + cover blurb prose. Note that `cover.key_metrics` is packer-filled, not writer-emitted; only the prose pieces of cover are written here.

Count check: 11 body + 4 synthesis = 15. Original framework has 14 sections + cover = 15. Match confirmed.

### W4 → W5 gate

The dispatcher must wait for all 11 body sections to reach a **terminal state** before dispatching synthesis:

- `success` — packer accepted on first attempt
- `degraded` — packer accepted after auto-repair
- `exhausted` — retry budget exhausted; placeholder used

**Not** "all body sections returned at least once." Otherwise a body section in repair would have its first-attempt output used as the `synthesis_hooks` input, defeating the gate's purpose.

### Synthesis dispatch contract

Prompt assembly order:

```
[CACHED ACROSS RUNS OF SAME REPORT TYPE]
System role (synthesis subagent)
Style guide
Framework synthesis section brief

[CACHED WITHIN RUN]
Manifest (full)

[PER-SECTION DYNAMIC]
synthesis_hooks bullet list (across all body sections, ~700 tokens total)
Facts slice for this synthesis section
Word target
Output format reminder
```

Same framework-before-dynamic ordering as W4, for the same cache reason.

---

## W6 — Pack

The packer is a deterministic Python pipeline. It is the only validator. There is no parallel LLM judge.

### Pipeline stages (per section file)

1. **Parse.** Markdown frontmatter → YAML. Body → Markdown AST. Fenced blocks → typed YAML payloads via the block catalog.
2. **Structural validation.** Required blocks present? Required frontmatter fields set? Block types recognized? YAML valid in each fence?
3. **Semantic validation (5A).** Five checks:
   - **Word count minimum.** Each section's framework brief declares a word target; flag if body falls below threshold (e.g., 70% of target).
   - **Tombstone regex.** Match `\b(no data available|N/A|TBD|data not provided|unable to determine)\b` (case-insensitive) in prose. Flag any hit.
   - **Quantitative-claim-near-citation.** Find numeric values in prose (regex for `\d+(\.\d+)?\s*(%|B|M|K|x|USD|...)`); within ±N tokens of each, expect a `[N]` marker. Flag uncited numbers.
   - **Fetched-but-unused.** For each fact named in the section's facts slice, expect at least one mention in prose or a fenced block. Flag facts that were given to the writer but never referenced.
   - **Cross-section numeric consistency.** Extract numeric claims from each section's prose, group by semantic identity (e.g., "revenue CAGR 3y"), flag mismatches across sections. This is the safety net for writers re-computing values that should match the facts pack.
4. **Auto-repair.** Soft fixes the packer applies silently:
   - Typo'd block type names → fuzzy match to catalog (`chart:combo` for `combo_chart`).
   - Missing optional fields with sensible defaults.
   - `[N]` marker resolution against the manifest.
   - Inline citation tuples in prose → `[N]` markers (legacy migration helper).
5. **Assembly.** Walk the parsed section file, fill schema slots:
   - Prose → `TextBlock` instances.
   - Fenced blocks → their typed schema shapes.
   - Rigid envelope fields (`cover.key_metrics`, `rail.quick_stats`, `rail.sparkline`, etc.) → populated directly from facts pack, never from the writer's output.

### Retry on hard fail

If any stage (2 or 3) hard-fails after auto-repair, the section is retried once. Retry context:

```
[Original section prompt]

YOUR PREVIOUS ATTEMPT FAILED VALIDATION:
- [structured error 1]: [details]
- [structured error 2]: [details]

Re-emit the section. Address each error explicitly.
```

### Failure handling

- Per-section retry budget: **1 retry (2 total attempts)** on the default model.
- Section exhausts retries → `degraded` marker + placeholder + failed content captured for review.
- **No model-tier fallback.** Preserves failure-pattern signal for diagnosis.
- Report always delivers with whatever succeeded. UI surfaces degraded sections.

---

## Cache shape

| Cache region | Stability | Reused across |
|---|---|---|
| System role + style guide + framework briefs | Stable per report type | All runs of `stock_initiation` |
| Manifest (W1+W2) | Stable per run | All 11 body dispatches in W4, all 4 synthesis dispatches in W5 |
| Facts pack | Stable per run | All 14 dispatches |
| `synthesis_hooks` bundle | Per run | All 4 synthesis dispatches |

Body wave shares one cached prefix across 11 dispatches. Synthesis wave shares a slightly larger cached prefix across 4 dispatches. Both prefixes survive cross-run for the framework portion (the dominant token count by far in equity research reports).

---

## Telemetry (day-one)

Wire from initial implementation, even before acting on it:

- Per-section retry count, exhaustion count, degradation rate
- Packer semantic validation hit counts (which checks fire, on which sections)
- `[SEARCH: query]` sentinel emissions per section per run
- `proposed_facts: []` channel — pre-flight requests for unregistered fact names
- Packer auto-repair counts (which soft fixes fire how often)
- Wave latency breakdown (W1 fetch, W2 pre-flight, W3 compile, W4 body, W5 synthesis, W6 pack)
- End-to-end report cost per run, broken down by wave

### Telemetry-driven evolution rules

- **`[SEARCH:]` sentinel rule** — if sentinels fire on the same section in >5% of runs for >7 days, that section's pre-flight is under-declaring searches. Action: retune the pre-flight prompt OR add a revision-pass step for that section. Do NOT build revision-pass infrastructure speculatively.
- **`proposed_facts` rule** — review weekly. If the same fact name is proposed across multiple runs/sections, evaluate for inclusion in the registry.

---

## Module surface

```
packages/core/src/openlia/llm/runtime/report_v2/
├── runner.py              # WavedReportRunner — wave orchestration, W4→W5 gate
├── manifest/
│   ├── baseline.py        # W1: hard-coded per-report-type baseline fetches
│   ├── preflight.py       # W2: per-section pre-flight + aggregator + central executor
│   └── manifest.py        # numbered source list, dedup, [N] resolution
├── facts/
│   ├── registry.py        # @register_fact decorator + DAG resolver
│   ├── extractors/
│   │   ├── deterministic.py  # JSONPath/Pydantic
│   │   ├── compute.py        # pure math
│   │   └── llm.py            # Haiku structured-output
│   └── pack.py            # facts_pack compile + per-section slicing
├── sections/
│   ├── dispatcher.py      # parallel dispatch, wave gating, terminal-state tracking
│   ├── prompts.py         # section writer prompt assembly (cache-ordered)
│   └── synthesis_hooks.py # contract enforcement (framework-declared schema)
├── packer/
│   ├── parser.py          # YAML frontmatter + Markdown + fenced block parsing
│   ├── blocks/            # one module per fenced block type (catalog TBD in plan)
│   ├── validator.py       # 5A semantic checks (5 enumerated)
│   ├── auto_repair.py     # soft fixes (enum renames, citation tuple migration, etc.)
│   └── assembler.py       # ReportSchema slot filling, rigid-slot population from facts
└── telemetry.py           # failure rates, sentinels, proposed_facts, latency, cost
```

Existing files to delete on cutover (do not modify):

- `packages/core/src/openlia/llm/runtime/report.py` (1646 lines)
- `packages/core/src/openlia/llm/runtime/subagent_runner.py` (637 lines)
- `packages/core/src/openlia/llm/runtime/subagent_client.py`
- `packages/core/src/openlia/llm/runtime/editor_client.py`
- `packages/core/src/openlia/llm/runtime/section_draft.py`
- `packages/core/src/openlia/llm/runtime/prior_section_summarizer.py`
- `packages/core/src/openlia/llm/runtime/plan_schema.py`
- `packages/core/src/openlia/prompts/shared/editor_role.yaml.j2`
- `packages/core/src/openlia/prompts/shared/section_subagent_role.yaml.j2`

---

## Migration / cutover plan

1. Build `report_v2/` alongside existing runners. Feature flag selects which runner the equity research department uses.
2. Flag-gated side-by-side runs: produce both classic and waved outputs for the same `ReportRequest`. Persist both.
3. **Structured diff between outputs** — not a text diff. Compare:
   - Citation count per section
   - Fact values (resolve names in both reports, compare)
   - Section word counts within tolerance (±20%)
   - Same key claims appearing (extract numeric+citation pairs, set comparison)
   - Cost per run
   - Wall-clock latency
4. When the diff stabilizes (most claims match, no critical regressions, cost ceiling met), default the flag to `report_v2`.
5. After a stabilization window with `report_v2` as default and no rollbacks, delete the listed legacy files.

---

## Open items resolved during brainstorming

| Item | Resolution |
|---|---|
| Fact source-of-truth | Framework JSON declares per-section facts; pre-flight declares only searches/fetches; `proposed_facts` is telemetry-only |
| Registry shape | Python decorators with typed extractors; YAML for per-report-type fact lists only |
| Citation provenance | Union default for all three tiers; explicit in Fact contract |
| Wave 1 baseline catalog | ~12 fetches enumerated above for `stock_initiation` |
| Migration diff strategy | Structured contract diff, not text diff |
| `[SEARCH:]` revision pass | Deferred behind telemetry threshold (>5% of runs / >7 days) |
| Retry budget | 1 retry / 2 total attempts |
| Model-tier fallback | None — preserve failure signal |
| `competitive_advantages_and_weaknesses` placement | Promoted to W5 synthesis wave |
| `risk_analysis` placement | W5 synthesis wave |
| W4→W5 gate semantics | "all body sections in terminal state," not "first attempt returned" |
| Prompt assembly order | Framework prefix before facts pack slice (cross-run cache) |

## Open items deferred to implementation plan

| Item | Note |
|---|---|
| **Fenced block type catalog** | Largest single chunk of implementation. Block type DSL design, YAML schemas per type, validator rules per type, packer parsers per type. Budget real time. |
| W6 auto-repair soft-fix catalog | What soft fixes the packer applies before declaring hard fail (typo'd block type → fuzzy match, missing optional defaults, etc.) |
| Pre-flight call's structured-output schema | Exact JSON shape of the `searches/fetches/proposed_facts` output |
| Framework JSON evolution | New fields needed: `facts: [str]` per section, `synthesis_hooks` schema per body section, `word_target` per section, `required` flag per section |
| LLM extractor model choice | Haiku-tier presumed for cost; confirm against latency budget |
| Wave 1 baseline failure tolerance | Per-fetch policy (block-on-failure for live_price, soft-fail for insiders, etc.) |

---

## Success criteria

- All six failure themes architecturally eliminated (verified by structured diff against classic runner output and by failure-mode regression tests).
- End-to-end cost per equity research report ≤ classic runner's current cost at ≥ same quality. Stretch goal: ≤$0.50 per report.
- End-to-end latency comparable to classic (max(W4) + max(W5) + W6 pack ≈ 1 minute target).
- Cross-run cache hit on framework prefix verified by per-run cost telemetry.
- Zero "No Data Available" appearances in `cover.key_metrics` across smoke test suite (packer-filled, structurally impossible).
- Zero citation-nesting drift incidents across smoke test suite (packer owns nesting).
- Per-section failure rate visible per section name in telemetry within first week post-cutover.
