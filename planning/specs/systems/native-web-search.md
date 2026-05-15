# Native Web Search & Two-Source Discipline

## Purpose

Wire native, provider-side web search across the four LLM providers OpenLIA targets (Anthropic, Gemini, OpenAI, xAI/Grok-deferred) and shift the system from "knowledge-first with optional search" to "tool-first, source-cited research." Companion to `llm-provider-design.md` (provider abstraction) and `llm-runtime-design.md` (runtime/execution).

This spec exists because:

1. **Stale data symptom.** Equity research reports were dated ~May 2025 in May 2026 because no department prompt anchored the model to today's date and the model fell back to its training cutoff. Date anchoring was fixed in commit `59a730d`; this spec extends that fix into a complete two-source discipline.
2. **Native search is wired in name only.** `Capabilities.web_search_native=True` is set on Anthropic/Gemini/OpenAI models and `resolve_web_search()` returns `variant="native"`, but **no adapter ever swaps the generic `web_search` ToolSchema for the provider-native tool**. When the runtime advertises `web_search` to a native-capable model, dispatch fails with `"web_search unavailable"` because the dispatcher only handles the `"configured"` variant.
3. **Quant/qual blur.** Without explicit discipline, models pull numbers from web snippets when EODHD/FMP would answer authoritatively. Reverse also happens: models lean on training knowledge for time-sensitive qualitative claims (CEO, strategy, recent news) that have changed.

## Scope

**In scope:**

- Provider-native web search for Anthropic, Gemini, and OpenAI.
- A canonical adapter contract (`LLMRequest.native_tools`, `LLMResponse.citations`, `LLMResponse.server_tool_calls`, `LLMResponse.server_tool_failures`) so the runtime is provider-agnostic.
- Per-turn provider routing for OpenAI via an `OpenAIRouter` multiplexer over `OpenAIChatAdapter` (Chat Completions) and `OpenAIResponsesAdapter` (Responses API).
- A reusable `shared/two_source_discipline.yaml.j2` prompt partial included by every report-producing department.
- Per-mode `web_search_budget_default` in framework JSON.
- Per-department user override of search budgets, surfaced in each department's Report Settings panel.
- First-class `ReportSchema.citations` (Phase A: populate + side-panel render + warn-mode validator; Phase B: inline `[N]` + strict validator).
- Streaming `WebSearchInvoked` / `WebSearchCompleted` SSE events so the UI never appears frozen during a 5–15s server-side search.
- Tool-call-rewrite fallback path: when a native search fails mid-turn and a configured search adapter is available, runtime rewrites the failure into a configured-adapter tool call dispatched on the next turn.

**Out of scope (deferred):**

- xAI / Grok wiring (`OpenAIResponsesAdapter` is left `base_url`-parameterized so xAI is a 5-line follow-up).
- `request_replan` tool for "model realizes it needs more data mid-write" (prompt handles via `"Data not available"` until telemetry justifies more).
- Per-user (vs per-department) budget toggles.
- Org-wide kill switch UI (deferred until we see a real abuse case; a single `OPENLIA_DISABLE_NATIVE_WEB_SEARCH` env flag covers the operator-side emergency stop).

**Out of scope entirely:**

- Connector-quirk content in the shared discipline partial. EODHD-specific ticker substitutions (`BZ.COMM` → `BNO.US`, `T5YIE.INDX` → composite) live in a separate `shared/connector_quirks/eodhd.yaml.j2` partial that loads only when EODHD is active.
- Server-side search-result caching. Each call hits the provider's native search live.

---

## Key decisions (locked)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| A1 | Per-mode budget defaults | Initiation 10, Update 5, Sector 15, Earnings 6, Morning Briefing 6, Macro 10 | Reflects qualitative-claim volume per mode; quant claims do not consume budget |
| A2 | Department gating | All report-producing departments enabled | Cost delta ~$0.10/report makes selective gating premature |
| A3 | User override | Per-department in Report Settings panel; falls through to framework default | Enables power-user tuning without per-user complexity |
| B1 | OpenAI adapter shape | Separate `OpenAIChatAdapter` + `OpenAIResponsesAdapter` classes | Two APIs are different enough that branching inside one class creates split personality |
| B2 | OpenAI routing | Per-turn via `OpenAIRouter` multiplexer; Responses only when `web_search` in `native_tools` | Latency/cost win on non-search turns; surface is internal to adapter package |
| C | Citations | First-class `ReportSchema.citations`, staged. Phase A: populate + side-panel + warn validator. Phase B: inline `[N]` + strict | Side-panel-only leaves model with no incentive for tight citations |
| D | Writing-phase tools | Strip `web_search` from writing-phase tool list | Search mid-write triggers cost spike + turn blowout + validation-bypass |
| E | xAI / Grok | Deferred. Keep `OpenAIResponsesAdapter` `base_url`-parameterized for future | No concrete user need vs maintenance burden |
| F | Streaming events | `WebSearchInvoked` / `WebSearchCompleted` folded into Phase 0–5, not Phase 6 | A 5–15s frozen UI tanks perceived quality |
| G | Configured search adapters (Brave/Tavily/Serper/You.com) | Kept as fallback layer | Already-built; covers Ollama + native-failure cases; cost ≈ 0 to keep |
| H | Prompt aggressiveness | Two-source discipline (quant→tools, qual→web_search) | Resolved by `two_source_discipline.yaml.j2` partial |
| I | Native search failure | Tool-call-rewrite fallback to configured adapter; single attempt; one budget unit | Lower complexity than message-splicing, leverages existing dispatch loop |

---

## Architecture

### Provider matrix

| Provider | Endpoint | Native tool wire format | Result mechanism | Status |
|---|---|---|---|---|
| Anthropic | `/v1/messages` (existing) | `{"type":"web_search_20250305","name":"web_search","max_uses":N}` in `tools` | Server-side; `server_tool_use` + `web_search_tool_result` blocks inline in assistant content | **Phase 1** |
| Gemini | `/v1beta/models/{m}:generateContent` (existing) | `{"google_search":{}}` in `tools` | Server-side; `candidates[0].groundingMetadata` with `groundingChunks` + `groundingSupports` | **Phase 2** |
| OpenAI | `/v1/responses` (new code path) | `{"type":"web_search"}` in `tools` | Server-side; `web_search_call` output items + `url_citation` annotations | **Phase 3** |
| xAI / Grok | `/v1/responses` (xAI base URL) | `{"type":"web_search"}` in `tools` | Server-side; OpenAI-compatible response shape | Deferred |

### Canonical contract additions

```python
# packages/core/src/openlia/llm/types.py

@dataclass(frozen=True)
class Citation:
    """Provider-agnostic source reference. Lives on LLMResponse.citations
    and on ReportSchema.citations. Each tool / web_search result that the
    runtime sees produces one Citation."""
    id: str                      # e.g., "c1", "c2" — stable within a run
    kind: Literal["tool", "web", "memory"]
    tool_name: str | None        # for kind="tool"
    tool_args: dict | None
    url: str | None              # for kind="web"
    title: str | None
    source: str | None           # publisher: "Reuters", "Nvidia IR", "Brave"
    date: str | None             # ISO date, if known
    snippet: str | None          # short excerpt for hover preview
    segment_start: int | None    # char offset in the assistant text the citation backs
    segment_end: int | None


@dataclass(frozen=True)
class ServerToolCall:
    """Telemetry record of a provider-side tool invocation we didn't
    dispatch ourselves (native web_search). Never enters
    ToolDispatcher.dispatch()."""
    name: str                    # always "web_search" in v1
    arguments: dict
    turn_idx: int


@dataclass(frozen=True)
class FailedSearch:
    """Adapter-detected native search failure. Runtime uses this to
    rewrite into a configured-adapter tool call (I-a fallback)."""
    query: str
    error_kind: Literal[
        "rate_limit", "server_error", "region_block",
        "content_filter", "timeout", "unknown"
    ]
    error_message: str
    turn_idx: int


@dataclass(frozen=True)
class LLMRequest:
    # ...existing fields...
    native_tools: tuple[str, ...] = ()       # e.g., ("web_search",)
    web_search_max_uses: int | None = None   # mapped to provider-specific cap


@dataclass(frozen=True)
class LLMResponse:
    # ...existing fields...
    citations: tuple[Citation, ...] = ()
    server_tool_calls: tuple[ServerToolCall, ...] = ()
    server_tool_failures: tuple[FailedSearch, ...] = ()
```

### Provider router (OpenAI only)

```python
# packages/core/src/openlia/llm/adapters/openai_router.py (new file)

class OpenAIRouter(LLMProvider):
    """Per-turn multiplexer. Routes to Responses API when the request
    asks for native web_search; otherwise to Chat Completions.

    Both inner adapters share the same conversation representation
    (canonical Message list). Translation to each provider's wire
    format happens inside each adapter, so a run can hop between them
    turn-by-turn without corrupting conversation continuity."""

    def __init__(
        self,
        *,
        chat: OpenAIChatAdapter,
        responses: OpenAIResponsesAdapter,
    ) -> None:
        self._chat = chat
        self._responses = responses

    async def generate(self, req: LLMRequest) -> LLMResponse:
        return await self._select(req).generate(req)

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMChunk]:
        async for chunk in self._select(req).stream(req):
            yield chunk

    def _select(self, req: LLMRequest) -> LLMProvider:
        if "web_search" in req.native_tools:
            return self._responses
        return self._chat
```

Provider factory in `services/runtime.py` constructs both inner adapters with the same credentials/model, wraps in `OpenAIRouter`, returns the router. Calling sites (ReportRunner, ChatRunner) see one `LLMProvider`.

### Conversation continuity across APIs

The router can route turn N to Responses and turn N+1 to Chat Completions within a single run. The canonical `Message` list is the source of truth. Each adapter renders it into its own wire format on every send:

- **Chat Completions** keeps the existing `_to_openai_messages(messages)` path.
- **Responses API** uses a new `_to_responses_input(messages)` helper:
  - `Message(role="user")` → `{"role":"user","content":[{"type":"input_text","text":...}]}`
  - `Message(role="assistant", content=...)` → `{"role":"assistant","content":[{"type":"output_text","text":...}]}` + per-call `{"type":"function_call","call_id":id,"name":n,"arguments":json}` items
  - `Message(role="tool", tool_call_id=..., content=...)` → `{"type":"function_call_output","call_id":id,"output":...}`
  - Server-side `web_search_call` items from prior Responses turns are **dropped on translation** (the model has already integrated them into `output_text`; citations are surfaced separately via `LLMResponse.citations`).

Stateless replay each turn — no `response_id` chaining. Costs ~5–10% more input tokens per Responses turn vs chained mode but preserves cross-API portability. Acceptable tradeoff.

### Tool dispatcher changes

```python
# packages/core/src/openlia/llm/runtime/tools.py

class ToolDispatcher:
    # ...existing fields...
    _web_search_calls_per_run: int = 0   # soft-cap counter for non-Anthropic providers

    async def build(
        self,
        department_id: str,
        *,
        has_web_search: bool,
        extra_tools: tuple[dict[str, Any], ...] = (),
    ) -> list[ToolSchema]:
        # ...existing logic...

        # When native is in effect, suppress the generic web_search ToolSchema
        # entirely; the adapter ships the native form. This prevents the model
        # from seeing two tools with the same name.
        if has_web_search and self._web_search.available:
            if self._web_search.variant == "native":
                pass  # do not append generic _WEB_SEARCH_SCHEMA
            else:
                header.append(_WEB_SEARCH_SCHEMA)
```

### Runtime — soft budget enforcement

`LLMRequest.web_search_max_uses` maps to Anthropic's `max_uses` natively. For Gemini and OpenAI Responses (no native cap parameter), the dispatcher's counter enforces the budget:

```python
# Inside ToolDispatcher._dispatch_web_search (configured) AND
# after parsing ServerToolCall from LLMResponse (native, non-Anthropic):

if self._web_search_calls_per_run >= self._web_search_budget:
    return ToolCallResult(
        ok=False,
        summary="Search budget exhausted",
        payload={"error": "...", "budget": self._web_search_budget},
    )
self._web_search_calls_per_run += 1
```

For Anthropic, server enforces; we just record the increment for telemetry parity.

### Native-failure rewrite (I-a)

```python
# Inside ReportRunner, after each LLM turn:

for failure in response.server_tool_failures:
    if self._web_search_resolution.variant == "configured" or \
       self._configured_search_fallback is not None:
        synthetic_call = ToolCall(
            id=f"rescue_{failure.turn_idx}_{i}",
            name="web_search",
            arguments={"query": failure.query},
        )
        # Inject into the assistant message so the standard dispatch
        # loop fires it on the next turn:
        response.tool_calls = (*response.tool_calls, synthetic_call)
        # Telemetry:
        self._trace(
            "web_search.rescue",
            f"native failed ({failure.error_kind}); routing to configured",
            {"query": failure.query, "error_kind": failure.error_kind},
        )
    else:
        # No fallback available. Leave failure inline; prompt handles
        # via "Data not available as of {current_date}".
        self._trace(
            "web_search.failed",
            f"native failed ({failure.error_kind}); no fallback configured",
            {"query": failure.query, "error_kind": failure.error_kind},
        )
```

### Streaming events

```python
# packages/core/src/openlia/llm/runtime/events.py

@dataclass
class WebSearchInvoked:
    query: str
    turn_idx: int
    provider: str         # "anthropic" / "gemini" / "openai_responses"

@dataclass
class WebSearchCompleted:
    n_results: int
    urls: tuple[str, ...]
    turn_idx: int
    provider: str
```

Each adapter parses provider-specific streaming markers and surfaces them through `LLMChunk.server_tool_event: ServerToolEvent | None`. Runtime translates `ServerToolEvent` → `WebSearchInvoked` / `WebSearchCompleted` SSE frames consumed by the frontend status row.

---

## Guardrails (baked in to v1)

These are the cost-and-stability protections each phase must implement. They are not optional.

### G-1. No retry loop on failure rewrite

A native search failure that gets rewritten into a configured-adapter call is attempted **exactly once**. If the configured adapter also fails, the failure surfaces inline; the model handles it via the two-source-discipline prompt ("Data not available as of {date}"). Implementation: `_web_search_rescue_seen: set[str]` keyed by `(turn_idx, query)` prevents a second rewrite.

### G-2. Budget accounting is by successful result, not attempt

`_web_search_calls_per_run` increments only when a result (native success OR rescue success) returns. Failed-then-rescued counts as 1, not 2. Rescue rate is tracked separately in DevPanel telemetry so operators can spot when native is degrading.

### G-3. Double-cost flag

Anthropic bills for partial native searches in some failure modes; rescued queries hit a second provider's quota. The runtime emits a `web_search.double_billed` trace event whenever a rescue fires (regardless of rescue success/failure). DevPanel renders the rescue rate × estimated double-bill cost.

### G-4. Citation source consistency

Every Citation has a `source` field that names the backend:
- `kind="tool"`: `source` is the connector category (`"financial"`, `"news"`, `"economic_calendar"`).
- `kind="web"` from native: `source` is the provider (`"Anthropic Web Search"`, `"Google Search"`, `"OpenAI Web Search"`).
- `kind="web"` from configured rescue: `source` is the configured adapter name (`"Brave"`, `"Tavily"`, `"Serper"`).
- `kind="memory"`: `source` is `"model_knowledge"`, with `date=current_date` indicating staleness boundary.

Validators and DevPanel rely on this distinction to debug "where did this fact come from" cleanly.

### G-5. Writing-phase tool whitelist

The writing phase calls `ToolDispatcher.build(..., has_web_search=False)`. Test asserts the resulting tool list never contains `web_search` for writing turns. Regression guard: a single `test_writing_phase_tools_exclude_web_search` test pins this.

### G-6. Native + generic mutual exclusion

When native is active, `ToolDispatcher.build` does not append `_WEB_SEARCH_SCHEMA`. Test asserts: given a `WebSearchResolution(variant="native")`, the returned tool list contains no entry named `web_search` (the adapter injects the native form into the wire payload after the runtime returns). Prevents the dual-tool collision that causes provider-side validation errors.

### G-7. Budget surfaces in prompt context

The rendered system prompt for every report turn includes `{{ search_budget }}` resolved from the per-mode/per-department setting. If the user has not overridden, framework default is used. If the framework JSON is missing the field, a global default of 8 applies. Test asserts the resolved budget appears in the rendered prompt.

### G-8. Per-turn provider trace

Every LLM turn emits `llm.provider.selected` trace with `{provider_kind, sub_path, native_tools, turn_idx}` — for OpenAI, `sub_path` is `"chat_completions"` or `"responses"`. Lets us audit per-turn routing in real runs.

### G-9. Cost telemetry per report

`ReportComplete` event gains `web_search_count: int`, `web_search_provider_breakdown: dict[str, int]`, and `web_search_rescues: int`. DevPanel renders these in the run summary. Operator can spot a runaway search loop instantly.

### G-10. Strict-undefined safety

The two-source-discipline partial references `{{ search_budget }}` and `{{ current_date }}`. Every call to `build_report_system_prompt` must pass both. Tests cover the assertion (existing pattern from the temporal_anchor partial work in commit `59a730d`).

---

## Phase plan

Phase numbers are non-contiguous because Phase 4 (xAI) is reserved-and-deferred.

### Phase 0 — Foundation contract

**Scope:** All shared types and dispatch logic, no provider work.

**Files touched:**

- `packages/core/src/openlia/llm/types.py` — add `Citation`, `ServerToolCall`, `FailedSearch` dataclasses; extend `LLMRequest` (`native_tools`, `web_search_max_uses`) and `LLMResponse` (`citations`, `server_tool_calls`, `server_tool_failures`).
- `packages/core/src/openlia/llm/runtime/events.py` — add `WebSearchInvoked` / `WebSearchCompleted` SSE event dataclasses.
- `packages/core/src/openlia/llm/runtime/web_search.py` — no changes; existing resolver already returns `variant="native"` correctly.
- `packages/core/src/openlia/llm/runtime/tools.py`:
  - Suppress `_WEB_SEARCH_SCHEMA` from header when `variant=="native"` (guardrail G-6).
  - Add `_web_search_calls_per_run` counter and `_web_search_budget` field.
  - Enforce budget on `_dispatch_web_search` (configured) and on native-result accounting hook.
- `packages/core/src/openlia/llm/runtime/report.py` — populate `LLMRequest.native_tools` and `LLMRequest.web_search_max_uses` from runtime context; consume `LLMResponse.server_tool_failures` for I-a rewrite; emit streaming events.

**Tests:**

- `test_llmrequest_native_tools_set_when_variant_native`
- `test_tool_dispatcher_suppresses_generic_schema_under_native`
- `test_tool_dispatcher_budget_counter_increments`
- `test_tool_dispatcher_budget_exhausted_returns_error`
- `test_runtime_rewrites_failure_into_configured_call`
- `test_runtime_no_rewrite_when_configured_unavailable`

**Estimated:** ~250 LOC src + ~150 LOC tests.

### Phase 1 — Anthropic native

**Scope:** Adapter swap + citations + failure detection + streaming.

**Files touched:**

- `packages/core/src/openlia/llm/adapters/anthropic.py`:
  - In `generate()` and `stream()`: when `"web_search" in request.native_tools`, strip any tool named `web_search` from the function-tool list and append `{"type": "web_search_20250305", "name": "web_search", "max_uses": request.web_search_max_uses or 5}`.
  - Parse response blocks: skip `server_tool_use` + `web_search_tool_result` from `tool_calls`; collect citations from content blocks' `citations` field; detect `is_error: true` results and surface as `FailedSearch`.
  - Streaming: parse `content_block_start type=server_tool_use name=web_search` → emit `WebSearchInvoked(input.query)`; `content_block_stop` after the matching result block → `WebSearchCompleted`.

**Tests:**

- `test_anthropic_appends_native_web_search_tool_block`
- `test_anthropic_omits_generic_envelope_when_native`
- `test_anthropic_parses_citations_from_content_blocks`
- `test_anthropic_detects_failed_search_block`
- `test_anthropic_stream_emits_web_search_invoked_completed`
- `test_anthropic_stream_skips_server_tool_use_in_tool_calls`

**Estimated:** ~180 LOC src + ~120 LOC tests.

### Phase 2 — Gemini native

**Scope:** Same as Phase 1, Gemini wire format.

**Files touched:**

- `packages/core/src/openlia/llm/adapters/gemini.py`:
  - `generate()` / `stream()`: when `"web_search" in request.native_tools`, append `{"google_search": {}}` to `tools` array.
  - Parse `candidates[0].groundingMetadata`: map `groundingChunks` → `Citation(kind="web", source="Google Search", ...)`; use `groundingSupports` to fill `segment_start` / `segment_end`.
  - Streaming: no per-search markers from Gemini; emit synthetic `WebSearchInvoked` on first chunk if `groundingMetadata` will be populated, `WebSearchCompleted` at stream end with the result URLs.
  - Failure detection: `groundingMetadata` absent where expected, or empty `webSearchQueries` despite a search-flavored prompt → `FailedSearch(error_kind="unknown")` for now (Gemini's failure surface is less explicit).

**Tests:**

- `test_gemini_appends_google_search_tool`
- `test_gemini_parses_grounding_metadata_into_citations`
- `test_gemini_synthesizes_stream_events`
- `test_gemini_detects_missing_grounding_as_failure`

**Estimated:** ~140 LOC src + ~100 LOC tests.

### Phase 3 — OpenAI Responses + Router

**Scope:** New adapter class, new router, conversation translation, citations, failure, streaming.

**Files added:**

- `packages/core/src/openlia/llm/adapters/openai_responses.py` — new `OpenAIResponsesAdapter` class. Targets `/v1/responses`. `base_url` parameterized (xAI-ready). Implements `LLMProvider` protocol with `generate()` and `stream()`.
- `packages/core/src/openlia/llm/adapters/openai_router.py` — new `OpenAIRouter` multiplexer.

**Files modified:**

- `packages/core/src/openlia/llm/adapters/openai.py` — rename module-level adapter export to `OpenAIChatAdapter` (alias `OpenAIAdapter` retained for backwards compatibility for one release).
- `packages/server/src/openlia_server/services/runtime.py` — provider factory builds `OpenAIChatAdapter` + `OpenAIResponsesAdapter`, wraps in `OpenAIRouter`, returns the router.

**Implementation notes:**

- Request shape: `input` (not `messages`); each conversation turn renders via `_to_responses_input(messages)`.
- Tools: `[{"type": "web_search"}]` appended when `"web_search" in request.native_tools`; function tools rendered as `{"type": "function", "name": ..., "parameters": ...}`.
- Response shape: `response.output` is a list of items. Item types: `message` (with `content` parts including `output_text` and `url_citation` annotations), `function_call`, `web_search_call`. Adapter walks output items to build `LLMResponse.text`, `tool_calls`, `citations`, `server_tool_calls`.
- Streaming: subscribe to SSE events from the Responses API. `response.web_search_call.in_progress` → `WebSearchInvoked`; `response.web_search_call.completed` → `WebSearchCompleted`. Function-call streaming follows existing patterns.
- Failure: `web_search_call` item with `status: "failed"` or an error annotation → `FailedSearch`.
- `usage` parsing: Responses API returns `input_tokens` / `output_tokens` in a different shape than Chat Completions but normalizes to the same `LLMResponse.input_tokens` / `output_tokens` fields.

**Tests:**

- `test_openai_router_routes_to_responses_when_native_web_search`
- `test_openai_router_routes_to_chat_for_normal_requests`
- `test_openai_responses_renders_messages_to_input_format`
- `test_openai_responses_includes_web_search_tool_block`
- `test_openai_responses_parses_url_citations`
- `test_openai_responses_detects_failed_web_search_call`
- `test_openai_responses_stream_emits_invoked_completed`
- `test_openai_responses_function_tool_call_roundtrip`
- `test_openai_responses_conversation_translation_drops_prior_web_search_items`

**Estimated:** ~400 LOC src + ~250 LOC tests.

### Phase 5 — Prompts, ReportSchema, Settings UI

**Scope:** The product-visible layer. Prompts shift to two-source discipline; schema gains citations; UI exposes per-department budget.

**Files added:**

- `packages/core/src/openlia/prompts/shared/two_source_discipline.yaml.j2` — the full partial documented below.
- `packages/core/src/openlia/prompts/shared/connector_quirks/eodhd.yaml.j2` — EODHD-specific ticker substitutions (BZ.COMM, T5YIE.INDX, etc.), included conditionally when EODHD is active.

**Files modified:**

- All report-producing departments include `two_source_discipline.yaml.j2` in their `report.system` slot:
  - `equity_research.yaml`
  - `earnings_update.yaml`
  - `morning_briefing.yaml`
  - `macro_research.yaml`
  - `retail_sentiment.yaml` (if/when retail sentiment generates reports)
  - `panic_thermometer.yaml`
- Each department's `report.system` slot stops including `shared/temporal_anchor.yaml.j2` (subsumed by the new partial). Chat-only paths keep `temporal_anchor` since they don't need the full discipline.
- `packages/core/src/openlia/reports/frameworks/{mode}.json` — add `"web_search_budget_default": N` per mode.
- `packages/core/src/openlia/reports/schema.py` — add `Citation` model and `ReportSchema.citations: list[Citation]`. Add `source_ids: list[str] = []` to structured value-bearing slots (Metric, Table.row, KeyFinding, Quote).
- `packages/core/src/openlia/reports/validator.py` — warn-mode rule: structured numeric/quote slot with empty `source_ids` emits `ReportValidationWarning("uncited_concrete_claim")`.
- `packages/core/src/openlia/llm/runtime/report.py` — resolve `search_budget` at run start (user pref → framework default → 8), pass to `build_report_system_prompt` and to `LLMRequest.web_search_max_uses`.
- `packages/server/src/openlia_server/db/models/...` — extend per-department settings persistence with `web_search_budgets: dict[str, int]`.
- `packages/server/src/openlia_server/routes/...` — settings endpoint accepts per-mode budget map.
- `frontend/src/...` — `ReportSettingsPanel` component gains a "Web search budget" section with one numeric stepper per mode (placeholder = framework default). Reused across equity research, earnings update, morning briefing, macro research panels.
- `frontend/src/pages/...` — citation side-panel renderer for completed reports. Reads `report.citations` and renders a list with hover-preview snippets.

**Tests:**

- `test_two_source_discipline_renders_with_search_budget_and_date`
- `test_equity_research_report_system_includes_two_source_partial`
- `test_search_budget_resolution_user_override_wins`
- `test_search_budget_resolution_framework_default_fallback`
- `test_search_budget_resolution_global_default_fallback`
- `test_report_schema_accepts_citations`
- `test_validator_warns_on_uncited_metric`
- `test_settings_endpoint_persists_per_mode_budgets`
- Frontend snapshot test of `ReportSettingsPanel` web-search section.

**Estimated:** ~450 LOC backend + ~150 LOC frontend + ~200 LOC tests.

### Phase 6 — Inline citations + cost telemetry

**Scope:** Polish; not blocking MVP.

**Files modified:**

- `packages/core/src/openlia/reports/validator.py` — promote citation warnings to errors (strict mode).
- `frontend/src/...` — inline `[N]` rendering in report blocks; clickable citations open the side-panel item.
- `frontend/src/components/dev/DevPanel.tsx` — cost telemetry panel: searches/report, rescue rate, double-bill estimate.

**Tests:**

- `test_validator_rejects_uncited_metric_strict_mode`
- Frontend visual test of inline citation rendering.

**Estimated:** ~250 LOC.

---

## The `two_source_discipline.yaml.j2` partial

Final text (typos fixed, connector-generic, EODHD-specifics moved out):

```
## Two-source discipline

You produce institutional-quality research. Precision is the product.
A wrong number is worse than no number; a confident tool-cited fact is
worth more than a hedged search summary. Your output flows directly
into reports analysts will act on, so every concrete claim must be
traceable to a source.

You have two information sources. Use them correctly.

### Quantitative claims — financial data tools, not web search

Any structured market or financial metric comes from your financial
data tools. This includes (non-exhaustive): prices, returns, revenue,
EPS, margins, ratios, market cap, financial statements, balance sheet,
cash flow, valuation multiples, beta, dividend history, ownership,
insider trades, short interest, options data and Greeks, implied
volatility, ESG scores, bond yields, Treasury rates, technical
indicators, macro indicators, sentiment scores.

Before searching for any number, scan your available tool list. If a
tool name plausibly covers the metric, call it. With dozens of tools
across your configured financial connectors, your default assumption
should be that a structured endpoint exists.

If you find yourself wanting to search for a number, stop. Did you
actually check the tool catalog? Call the tool.

Narrow exceptions where web_search for a number is allowed:
- Figures that are not market/financial metrics (regulatory counts,
  tariff rates, FDA approval numbers, headcount, patent counts)
- Private company data with no ticker in your connectors
- Breaking deal terms or guidance numbers announced today and not yet
  ingested
- Cross-checking a financial-tool value that looks anomalous

In these cases, search is allowed but cite the source URL explicitly.

### Qualitative claims — web_search is primary, your knowledge is fallback

Company news, management changes, strategy commentary, M&A activity,
regulatory developments, competitive moves, analyst takes, geopolitical
context, sector narratives, product launches, supply chain events,
executive roles, anything time-sensitive.

Your training cutoff is months to years ago. For any qualitative claim
about something that could have changed since then — including "stable"
facts like who runs what company — web_search FIRST. Memory is a
fallback only when search returns nothing relevant.

For ongoing events, prefer sources within the last 7 days unless
historical context is explicitly required. For settled context
(industry structure, long-running competitive dynamics), older sources
are fine.

### Mixed claims

Many sentences blend quant and qual: "Apple grew revenue 8% YoY driven
by services strength." The number comes from a financial data tool;
the attribution comes from search or earnings commentary. Source each
component separately and cite both.

### When sources disagree

If a financial data tool says one number and a search result says
another, default to the financial tool for the figure. If the
discrepancy is material (>5% or affects a key thesis point), note it
in the report: "Tool reports $X; [source] reports $Y; using tool as
primary." Flag for review rather than silently picking one.

### Search budget

You have a budget of {{ search_budget }} web searches for this report.
Spend them on the highest-leverage qualitative claims — the ones that
move the analysis, not background color. If you're approaching the
cap, prioritize: thesis-critical context > recent material events >
supporting narrative > nice-to-have color.

Before each search, state in one line what you expect to find and why
your tools/knowledge are insufficient. This is not bureaucracy; it's
the check that prevents wasted calls.

### Citation format

Every concrete claim must be cited inline.

- Quant citation: `[tool_name(key_params)]`
  Example: "Apple's Q1 2026 revenue was $95.4B [get_fundamentals_data(AAPL.US)]."
- Qual citation: `[source, date, url]`
  Example: "Nvidia announced a new H300 chip [Reuters, 2026-05-12, reuters.com/...]."
- Memory fallback (qual only, when search returns nothing):
  `[from model knowledge, may be outdated as of {{ current_date }}]`
- No source available: "Data not available as of {{ current_date }}."

Do not blend formats. Do not skip citations because a claim feels
obvious. If it's concrete enough to be wrong, it's concrete enough to
cite.

### Anti-patterns

❌ "Apple's revenue last quarter was approximately $95B [searched: Apple Q1 2026 revenue]."
✅ "Apple's Q1 2026 revenue was $95.4B [get_fundamentals_data(AAPL.US)]."
— Numbers come from tools, not search.

❌ "Nvidia's CEO is Jensen Huang." (no citation, from training)
✅ "Nvidia's CEO is Jensen Huang [Nvidia investor relations, 2026-05-10, nvidia.com/...]."
— Even "stable" facts about people in roles can change. Search-verify.

❌ "The stock has been rallying on AI optimism." (vague, uncited)
✅ "NVDA is up 18% over the past month [get_historical_stock_prices(NVDA.US)], driven by reports of accelerating data center capex [FT, 2026-05-11, ft.com/...]."
— Quant + qual sourced separately.

❌ "I'll search for Apple's P/E ratio."
✅ Call `get_fundamentals_data(AAPL.US)`, extract P/E.
— P/E is a structured metric. Use the tool.

The two-source discipline is the single highest-leverage cost lever in
this system. The provider plumbing is a one-time fix; this prompt is
what keeps the system continuously efficient. Follow it strictly.
```

---

## Settings UI specification

Each report-producing department's settings panel gains a "Web search budget" section. For Equity Research, this is the Report Settings Window. For Earnings Update, the Earnings Settings panel. Same component reused.

```
┌─ Web search budget ──────────────────────────────────────────────┐
│                                                                  │
│  Web search supplements your data connectors for qualitative     │
│  context (news, strategy, regulatory updates). It does not       │
│  substitute for financial data tools.                            │
│                                                                  │
│  Budget per report mode:                                         │
│                                                                  │
│    Stock initiation       [ 10 ]  searches  (default)            │
│    Stock update           [  5 ]  searches  (default)            │
│    Sector research        [ 15 ]  searches  (default)            │
│                                                                  │
│  Reset to defaults                                               │
└──────────────────────────────────────────────────────────────────┘
```

Hovering "default" reveals the framework default value and an explainer link.

---

## Cost model

Approximate per-report cost at default budgets (Anthropic native, $10/1000 searches):

| Mode | Default budget | Worst-case cost |
|---|---|---|
| Stock initiation | 10 | $0.10 |
| Stock update | 5 | $0.05 |
| Sector research | 15 | $0.15 |
| Earnings update | 6 | $0.06 |
| Morning briefing | 6 | $0.06 |
| Macro research | 10 | $0.10 |

Gemini Pro (Gemini 3 prompt-grounded) is ~3× this; OpenAI Responses is ~3× this. A power user generating 20 reports/day at default budgets caps at $1–3/day before the soft-cap. DevPanel surfaces actual vs budgeted in run summaries (guardrail G-9).

---

## Migration / rollout

1. **Phase 0–3 land as one PR** (foundation + all three native adapters). Behind feature flag `OPENLIA_NATIVE_WEB_SEARCH=true` initially.
2. **Phase 5 lands separately** — prompt shift + schema + settings UI. Two-source discipline takes effect for all departments simultaneously.
3. **Soak period of one week** with flag enabled in dev/staging. DevPanel telemetry surfaces rescue rate, search count distribution, budget hits.
4. **Phase 6** lands once Phase 5 telemetry shows healthy citation coverage (>90% of structured slots have non-empty `source_ids`).
5. Flag removed once stable.

Rollback: setting `OPENLIA_NATIVE_WEB_SEARCH=false` reverts to today's behavior (generic `web_search` ToolSchema, configured-adapter-only). Schema citations remain populated but the validator skips its warning rule when the flag is off.

---

## Open questions

None blocking. Items deferred to telemetry-driven follow-ups:

- Whether to enable `request_replan` for writing-phase data-realization (deferred per decision D; revisit if telemetry shows >5% of reports hit the "Data not available" path).
- Whether Gemini's failure detection needs strengthening once we have real production traces.
- Whether to introduce a `web_search_quality_score` heuristic on citations to deprioritize low-quality sources in the side-panel ordering.
- Whether Phase 4 (xAI/Grok) should be revisited if Grok-5 or later ships with materially different capabilities for finance research.

---

## References

- `planning/specs/systems/llm-provider-design.md` — adapter abstraction, capability matrix.
- `planning/specs/systems/llm-runtime-design.md` — runtime/execution, prompt assembly, tool schema construction.
- `planning/specs/systems/report-rendering-pipeline-design.md` — report schema, validator, rendering.
- Commit `59a730d` — date anchor + `temporal_anchor.yaml.j2` partial (precedent for the shared-partial + StrictUndefined pattern this spec extends).
- Anthropic Web Search Tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- OpenAI Web Search Tool: https://developers.openai.com/api/docs/guides/tools-web-search
- Gemini Grounding with Google Search: https://ai.google.dev/gemini-api/docs/grounding
- xAI Web Search (deferred): https://docs.x.ai/docs/tools/web-search
