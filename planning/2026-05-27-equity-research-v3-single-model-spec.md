# Equity Research v3 — Single-Model Engine Spec

**Date opened:** 2026-05-27
**Status:** Draft — design only, no code yet.
**Supersedes:** the 8-stage pipeline in `packages/core/src/openlia/llm/runtime/report_v2_3/`.
**Branch (planned):** `feat/equity-research-v3`.

---

## The premise

v2.3 is 6,750 lines, 8 stages, 21 Pydantic models, 25–35 LLM turns per report. It fails on truncation and schema mismatches. Claude.ai produces comparable reports with one model, one web search tool, and free-form prose. v3 takes the claude.ai shape and adds the three things the user actually requires:

1. **Citations** — every numeric/factual claim resolves to a real source.
2. **Charts** — embedded graphs in the rendered report.
3. **Financial tools** — DCF, Comps, sensitivity run as deterministic Python.

Everything else from v2.3 — multi-stage validation, fact bundles, derived_from graphs, marker grammars, coverage gates — goes away.

---

## Non-goals

- **No Ollama support.** Web search and code execution are non-negotiable for v3; local models without them are out of scope. The engine will refuse to start on a local-model provider with a clear error.
- **No backwards compatibility with v2.3 state.** v3 runs in parallel; v2.3 stays as rollback until v3 is proven. v2.3 will be deleted in a follow-up once v3 is the default and stable.
- **No multi-stage checkpointing.** A failed run re-runs from scratch. The engine is fast enough end-to-end (one LLM context, no inter-stage waste) that resume is unnecessary complexity.
- **No per-section model routing.** One model runs the whole report.

---

## Architecture

**One LLM. One tool-use loop. One final structured emit.**

```
┌─────────────────────────────────────────────────────────────────┐
│ Server: load template, build tool catalog, open LLM session    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ One LLM session:                                                │
│   System prompt: template + intent + language + tool catalog    │
│   User turn: "Produce the report for {ticker} / {topic}"        │
│                                                                  │
│   Loop until model calls finalize():                             │
│     - model thinks                                               │
│     - model calls tools (web_search, get_fundamentals, run_dcf, │
│       emit_chart, write_section)                                 │
│     - server executes tool, returns result                       │
│     - server logs every tool call with provenance               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Server: resolve citations from tool log, render charts,         │
│ assemble final report, persist                                  │
└─────────────────────────────────────────────────────────────────┘
```

Loop terminates when the model calls `finalize()` AND every required section in the template has been written via `write_section()`. If a required section is missing, `finalize()` returns an error to the model with the list of missing sections, and the loop continues.

---

## Provider support matrix

| Provider | Web search | Code exec | DCF/Comps as fn tools | Supported in v3? |
|---|---|---|---|---|
| OpenAI (Responses API) | `web_search_preview` native | `code_interpreter` native | Yes | **Yes** |
| Anthropic (Messages API) | `web_search` native | `code_execution` native | Yes | **Yes** |
| Gemini | `google_search` grounding | `code_execution` native | Yes | **Yes** |
| OpenRouter | Model-dependent | Model-dependent | Yes | **Yes, with capability gate** |
| Ollama (local) | None | None | Yes | **No — engine refuses** |

The "DCF/Comps as fn tools" column is the deterministic fallback: even when the provider has code execution, the DCF math runs as a registered Python tool the model calls, not as model-generated code. This guarantees:
- Same DCF formula across providers
- No risk of the model writing buggy DCF code in a sandbox
- Cheap and fast (no sandbox spin-up per call)
- Auditable (we control the formula)

Code execution is available to the model for **ad-hoc** math the registered tools don't cover (e.g., "compute the average revenue growth from these 5 quarters") but is optional.

---

## Tool catalog

The model sees these tools in its system prompt. All tools return JSON the model can read inline.

### Provider-native tools (wired through, not wrapped)

1. **`web_search(query, max_results=5)`**
   Native web search via the provider's built-in tool. Server intercepts the tool call to log the result URLs + snippets to the **citation ledger** before passing the result back to the model. Each result gets a stable `source_id` like `web_1`, `web_2`, etc.

2. **`code_execution(code)`** *(optional)*
   Provider-native sandbox. Available but the model should prefer registered tools for known math. Results are not citable (the model must cite the inputs, not the computation).

### Data tools (function tools, server-executed)

Reuse the existing v2.3 EODHD transports from `report_v2_3/research/registry.py`. Same signatures, same provenance attachment, exposed to the v3 model as function tools.

3. **`get_fundamentals(ticker)`** — latest snapshot. Returns trimmed payload. Server logs as `eodhd_1`, `eodhd_2`, etc.
4. **`get_historical_prices(ticker, from_date, to_date)`**
5. **`get_company_news(ticker, limit=5)`**

(The existing `_trim_eodhd_fundamentals` payload trimming carries over verbatim — pure win.)

### Financial computation tools (deterministic Python)

Reuse the existing v2.3 valuation engines from `report_v2_3/valuation/` as function tools.

6. **`run_dcf(inputs)`**
   Wraps `valuation/dcf.py::dcf`. Inputs: `revenue_base`, `revenue_growth_path`, `margin_path`, `wacc`, `terminal_growth`, `tax_rate`, optional `net_debt`, `shares_outstanding`. Returns: `enterprise_value`, `equity_value`, `fair_value_per_share`.

   **Key change from v2.3:** the model passes the input values directly (not `*_fact_id` references into a bundle). The model is responsible for citing the inputs in the surrounding prose. The DCF result is logged with the inputs as `dcf_1`, `dcf_2`, etc., and the model can cite the result.

7. **`run_comps(inputs)`** — wraps `valuation/comps.py`.
8. **`run_sensitivity(base_case, sensitivities)`** — wraps `valuation/sensitivity.py`.

### Output tools (the model's only way to produce report content)

9. **`emit_chart(chart_id, chart_type, title, data, axes)`**
   The model emits chart specs as JSON. Server stores them in a chart registry keyed by `chart_id`. The model later references the chart inline in section markdown as `{{chart:chart_id}}`.

   **Allowed chart types** (matching what the renderer supports today): `line`, `bar`, `column`, `area`, `pie`, `scatter`, `table`. The `data` field is a list of `{label, value}` objects or `{x, y}` for scatter; the renderer normalizes.

   The chart spec is **freeform within the schema** — the model is not required to use facts from a registered bundle. Citation for the data shown in a chart is via a separate `source_ids` list on the chart spec, resolved against the tool log.

10. **`write_section(section_id, markdown)`**
    Append section content. `section_id` must match one of the template's section ids. Markdown body uses inline citations as `[^source_id]` (e.g., `[^web_1]`, `[^eodhd_2]`, `[^dcf_1]`). Server validates each citation marker resolves to a logged tool call; unresolved markers return an error to the model, which then re-emits.

    Sections can be written in any order; can be re-emitted (last write wins). This is the model's iteration mechanism: write a draft, do more research, re-write.

11. **`finalize()`**
    Signal that the report is done. Server checks every required section is written; if not, returns `{"missing_sections": [...]}` and the loop continues.

### Tool count: 11 (4 native/data + 3 compute + 3 output + 1 native-optional)

---

## Citation mechanism

**Every tool call appends to a server-side citation ledger.** Schema:

```python
class CitationLogEntry:
    source_id: str            # "web_1", "eodhd_3", "dcf_1"
    tool_name: str            # "web_search", "get_fundamentals", "run_dcf"
    arguments: dict           # the call args (truncated for storage)
    result_summary: str       # one-line human-readable summary
    provenance: Provenance    # WebSource | DataProviderSource | ComputedSource
    timestamp: datetime
```

Two log views derived from this:

- **Model-facing**: when a tool returns, the result payload is prefixed with the source_id (`"This is web_3"`) so the model knows what id to cite.
- **Reader-facing**: at render time, the model's `[^web_3]` markers get rewritten to numbered footnotes (`[^1]`) and the bibliography is generated from the ledger.

**Citation validation runs deterministically** at every `write_section` call: regex extracts every `[^xxx_N]` marker, verifies each exists in the ledger, returns errors for unresolved ones. No LLM-based verification needed.

**No estimates / derivations as marker grammar.** If the model wants to state a derived number, it either:
- Calls a tool (e.g., `run_dcf`) that returns the number with provenance, OR
- Writes "we estimate X based on Y and Z" in prose, with `[^...]` citations on Y and Z. The "estimate" framing is naturally surfaced by the prose, not a structured marker.

This is the v2.3 `{{DERIVE:...}}` / `{{ESTIMATE:...}}` grammar gone. The reason it existed was to enable post-hoc auditing of derived numbers; v3 trades that audit capability for simplicity. If we miss it later, we can add a `log_estimate(label, value, basis)` tool that appends to the ledger — but we start without it.

---

## Chart rendering

1. Model calls `emit_chart(chart_id="rev_growth", chart_type="line", title="Revenue YoY", data=[{x: "FY23", y: 1.2}, ...], axes={x: "Fiscal Year", y: "Revenue ($B)"}, source_ids=["eodhd_1"])`.
2. Server validates the spec against a Pydantic `ChartSpec` model (lean — just what the renderer needs), validates source_ids resolve, stores in the chart registry.
3. Section markdown contains `{{chart:rev_growth}}`. At render time, server substitutes with an `<img>` tag (PNG/SVG) or an inline chart component (HTML/PDF).
4. Renderer is the existing v2.3 chart renderer or a thin replacement — out of scope for this spec but blocked-out as a known integration point.

**Chart-type allowlist enforced server-side**, not in the LLM prompt. The error message returned for invalid chart types is descriptive enough for the model to retry with a valid type.

---

## System prompt structure

```
You are an equity research analyst producing a report for a professional
investor. The report structure is fixed by the user's template (below).
Your job: research the subject, write each section, embed citations and
charts where they add value.

# Report subject
{ticker or topic}

# Report language
{en | zh-TW}

# Report length target
{short | medium | long} (approx word count: {N})

# Template
The report has the following sections. Each section's `intent` describes
what the user wants in it. You MUST produce a `write_section` call for
every section.

{for each section in template:}
  - id: {section.id}
    title: {section.title}
    intent: {section.intent}
    methodology_hints: {section.methodology_hints | "none"}

# Tools

You have these tools available. Use them freely — research thoroughly,
verify numbers before citing them, run DCF/comps when valuation is in
scope.

{tool catalog as compact text — name, one-line description, parameters}

# Citation rules

Every numeric or factual claim must cite a tool result. Cite with
[^source_id], e.g. [^web_3] or [^eodhd_1]. Tool results tell you their
source_id when they return. Unresolved citations will reject your
write_section call.

# When to call finalize()

When every template section has been written and you are satisfied with
the report. If finalize() reports missing sections, write them and try
again.
```

~350 words of system prompt. No "MUST NOT" walls, no schema fragments dumped inline, no marker grammars to memorize.

---

## What we keep from v2.3

- **`TemplateSpec` / `SectionSpec` from `templates/spec.py`** — reuse as-is.
- **Built-in templates from `templates/builtins.py`** — reuse as-is.
- **EODHD transports from `research/registry.py`** — repackage as v3 tools, same signatures.
- **`_trim_eodhd_fundamentals` payload trimming** — pure win, carry over.
- **Valuation engines (`valuation/dcf.py`, `valuation/comps.py`, `valuation/sensitivity.py`)** — wrap as tools, same math.
- **Provenance types (`WebSource`, `DataProviderSource`, `ComputedSource`)** — reuse for the citation ledger.
- **The provider routing layer** that picks between OpenAI/Anthropic/Gemini/OpenRouter SDK — reuse, add a `requires_web_search=True` capability check.
- **The chart renderer** (whatever produces the final SVG/PNG) — reuse.
- **The streaming event spine** that surfaces progress to the frontend — reuse with simplified event types.

## What we drop from v2.3

- 8 stages → 0 stages (one loop)
- `runner.py`, `state.py` simplified to a thin session+ledger holder
- `schemas.py` (845 lines, 21 models) → a lean `~150-line` schema file (Template, ChartSpec, CitationLogEntry, RunRequest, RunResult)
- `clients/llm_researcher.py` (837 lines), `clients/llm_stage_clients.py` (1027 lines), all per-stage clients → one `LLMSession` wrapper around the provider SDK
- `stages/` directory entirely
- `derivations.py`, `_mint.py` (CITE/DERIVE/ESTIMATE machinery)
- `BundleFact` / `ResearchBundle` / `derived_from` chain validation
- `DataNeed` dual-lane routing
- `UNCITED_NUMBER` regex verifier
- `canonical_figures` consistency layer
- Per-stage token budget tuning (one model session has one ceiling)

**Estimated v3 size: 800–1,200 lines** (vs. v2.3's 6,750).

---

## Failure handling

### Tool failures
- **Web search returns nothing**: returned to model as `{"results": []}`. Model decides whether to retry with different query or proceed without.
- **EODHD endpoint errors**: returned as `{"error": "..."}`. Model retries or proceeds.
- **DCF inputs violate constraints** (e.g., `wacc <= terminal_growth`): tool raises with explanatory message, returned to model. Model corrects inputs.

### Citation failures
- **Unresolved `[^xxx_N]` marker in `write_section`**: server returns `{"unresolved_citations": ["web_99"], "valid_ids": [...]}`. Model re-emits the section with corrected citations.

### Chart failures
- **Invalid chart_type**: server returns `{"error": "chart_type must be one of [line, bar, ...]"}`. Model retries.
- **Unresolved source_id in chart**: same as citation failure.

### Finalize failures
- **Missing required sections**: server returns `{"missing_sections": ["valuation", "risks"]}`. Model writes them.

### Hard limits
- **Max turns**: 60 (generous; v2.3 RESEARCH alone can use 12 just on tool-use). Run fails with partial progress preserved.
- **Max context tokens**: tracked per provider, soft warning at 80%, hard fail at 95%. Run aborts cleanly.
- **Max wall time**: 15 minutes default; user-configurable up to 60.

### Retry policy
- **Zero engine-level retries on individual tool calls** — the model retries via the loop.
- **One run-level retry** if the run dies on a transient error (e.g., 429 from provider).

---

## Persistence model

A v3 run produces:
- **`Report`**: id, ticker/topic, template_id, language, status, created_at, completed_at
- **`ReportSection`**: report_id, section_id, section_index, title, markdown (with `[^...]` markers still embedded)
- **`Chart`**: report_id, chart_id, spec (JSON), rendered_url (after render)
- **`Citation`**: report_id, source_id, tool_name, provenance (JSON), display_index (the `[^N]` shown to readers)
- **`ToolCallLog`**: report_id, turn_index, tool_name, arguments, result_summary, provenance, timestamp, source_id

The `ToolCallLog` is the audit trail. The `Citation` table is the deduplicated reader-facing bibliography (one entry per unique source actually cited in the body, with display numbers assigned at render).

The legacy v2.3 tables (`ReportState`, `ResearchBundle` JSON blob) are not used.

---

## Frontend events (streaming)

Simplified event types — one per meaningful state transition:

- `run.started` — `{run_id, template_id, ticker}`
- `tool.called` — `{turn, tool_name, args_summary}`
- `tool.completed` — `{turn, tool_name, source_id, summary}`
- `section.written` — `{section_id, title, char_count}`
- `chart.emitted` — `{chart_id, chart_type, title}`
- `run.completed` — `{run_id, section_count, chart_count, citation_count}`
- `run.failed` — `{run_id, error, partial_sections_written}`

The current v2.3 frontend has rich per-stage progress UI (Plan / Research / Synthesize / Write / Verify chips). For v3, those chips collapse to a live activity feed driven by these events. UI work is a separate spec.

---

## Migration & rollout

1. **Build v3 in a new module** at `packages/core/src/openlia/llm/runtime/report_v3/`. Do not touch v2.3.
2. **Feature flag** at the server: `REPORT_ENGINE_VERSION = "v2.3" | "v3"`, defaults to v2.3.
3. **Smoke test** v3 on the same 14 AI-infra tickers v2.2 was validated on (per `project_report_v2_multi_ticker_validated`). Compare outputs side-by-side.
4. **Default flip** to v3 once smoke pass + manual review of 3 reports across providers (OpenAI, Anthropic, Gemini).
5. **Delete v2.3** in a follow-up PR after one release cycle of v3 being default with no rollbacks.

---

## Resolved design decisions (2026-05-27)

1. **Section ordering**: renderer assembles sections in **template order**, regardless of write order. Model can iterate and re-write freely.

2. **Chart placement**: model decides via inline `{{chart:id}}` markers in section markdown. No separate "primary chart" or auto-placement concept. If a template wants a standalone exhibits section, the model just writes charts into that section like any other.

3. **Length enforcement**: **soft target only** — system prompt mentions the template's `default_length` as guidance; no hard validation, no rejection. Trust the model.

4. **Parallel tool calls**: **allowed when the provider's tool-use protocol supports it** (OpenAI Responses API, Anthropic Messages API). Server executes each tool call independently and returns all results together. Faster runs.

5. **Self-consistency / contradiction handling**: v3 **drops the VERIFY stage entirely**. Trust single-model consistency — one model writing all sections in one context is usually coherent. If a user spots a contradiction, they request a revision. No `review_consistency()` tool, no deterministic contradiction checker. If this turns out to be insufficient in practice, revisit by adding a deterministic-only verifier (citation resolution, chart references, non-empty sections — none of these require an LLM).

6. **Cost telemetry**: tracked **per tool call** in `ToolCallLog` — input tokens, output tokens, wall time. The "stage" dimension is gone. Aggregations (total tokens per run, breakdown by tool type) computed at query time.

7. **`emit_chart` schema strictness**: **lean Pydantic with permissive coercion**. Match the renderer's actual capabilities. Accept numeric strings, coerce common formats. Validation errors are descriptive enough for the model to fix on retry without server hand-holding.

---

## What success looks like

After v3 is the default:

- Reports for typical tickers (RKLB, NVDA, MSFT, etc.) complete in one shot without truncation failures.
- The engine works identically across OpenAI, Anthropic, Gemini.
- New report types (templates) require zero engine changes — just a new `TemplateSpec` in `builtins.py` or a user upload.
- Adding a new financial tool (e.g., `run_ddm`, `run_lbo`) is a single-file addition to the tool catalog.
- Code volume is under 1,500 lines.
- Time-to-first-section is under 30 seconds; full report under 5 minutes.

If any of these break, the spec was wrong; revise before shipping.

---

## Implementation plan (phased PRs)

Listed for completeness; detailed PR-level plans will be written when this spec is approved.

**Phase 0 — Scaffolding**
- New module skeleton at `report_v3/`
- Lean schemas (Template reuse + ChartSpec, CitationLogEntry, RunRequest, RunResult)
- `LLMSession` provider abstraction with capability gate
- Server route `/api/v3/reports` behind feature flag

**Phase 1 — Tools + loop**
- Tool catalog: web_search wiring per provider, EODHD tools, run_dcf/run_comps/run_sensitivity, emit_chart, write_section, finalize
- Citation ledger
- Main loop with citation validation
- Smoke test: one report end-to-end with each provider

**Phase 2 — Persistence + rendering**
- `Report` / `ReportSection` / `Chart` / `Citation` / `ToolCallLog` tables + migrations
- Citation rewriting at render time (`[^web_3]` → `[^1]` + bibliography)
- Chart rendering integration
- PDF/HTML output path

**Phase 3 — Frontend + flip**
- Simplified event stream UI
- Side-by-side comparison page (v2.3 vs v3) for smoke testing
- Multi-ticker validation
- Default flip + v2.3 deprecation notice

**Phase 4 — Cleanup**
- Delete v2.3 module
- Delete legacy tables
- Update planning docs (`README.md`, `phase-progress.md`)
- Close `2026-05-24-v2.3-autonomy-integrity-roadmap.md` with "superseded by v3"

---

## Appendix — a worked example

User request: "Produce an equity research report on RKLB."

Template: built-in `equity_research_long` with sections [business_overview, financials, growth_drivers, competitive_position, valuation, risks, conclusion].

Loop trace (abbreviated):

```
Turn 1 (model):  call get_fundamentals(ticker="RKLB.US")
Turn 1 (server): → returns trimmed payload, logged as eodhd_1
Turn 2 (model):  call get_company_news(ticker="RKLB.US", limit=10)
Turn 2 (server): → eodhd_2
Turn 3 (model):  call web_search(query="Rocket Lab Neutron launch schedule 2026")
Turn 3 (server): → web_1 (5 results, each with stable URL)
Turn 4 (model):  call web_search(query="Rocket Lab Space Systems revenue mix Q4 2025")
Turn 4 (server): → web_2
Turn 5 (model):  call write_section(section_id="business_overview", markdown="...
   Rocket Lab operates two segments: Launch Services and Space Systems
   [^eodhd_1]. In FY24 the Space Systems segment contributed ~$X of
   revenue [^web_2] ...")
Turn 5 (server): → OK (all citations resolve)
Turn 6 (model):  call get_historical_prices(...)
Turn 6 (server): → eodhd_3
Turn 7 (model):  call emit_chart(chart_id="price_5y", chart_type="line",
   title="RKLB 5-year price history", data=[{x: "2021", y: 12.5}, ...],
   source_ids=["eodhd_3"])
Turn 7 (server): → OK
Turn 8 (model):  call write_section(section_id="financials", markdown="...
   {{chart:price_5y}} ...")
...
Turn 18 (model): call run_dcf(revenue_base=380e6, revenue_growth_path=[0.45, 0.40, 0.30, 0.25, 0.20], margin_path=[-0.10, -0.05, 0.05, 0.10, 0.15], wacc=0.12, terminal_growth=0.03, tax_rate=0.21, net_debt=-500e6, shares_outstanding=485e6)
Turn 18 (server): → {enterprise_value: 4.2e9, equity_value: 4.7e9, fair_value_per_share: 9.69}, logged as dcf_1
Turn 19 (model): call write_section(section_id="valuation", markdown="...
   Our DCF yields a fair value of $9.69 per share [^dcf_1], a 12%
   discount to today's price [^eodhd_3] ...")
...
Turn N (model):  call finalize()
Turn N (server): → all sections written, OK. Run complete.
```

Total turns: ~22-30. No multi-stage handoffs. No big JSON object at the end. Each tool call is independently retriable. Citations are mechanical. Charts are mechanical. The model never has to learn a custom marker grammar — `[^source_id]` is the standard Markdown footnote syntax.

---

**End of spec.**
