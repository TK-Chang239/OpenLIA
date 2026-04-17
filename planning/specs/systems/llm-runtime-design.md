# LLM Runtime / Execution System Design

## Purpose

Defines the layer between the `LLMProvider` returned by the resolver in `llm-provider-design.md` and the frontend. Covers prompt assembly, framework / style-guide injection, tool-schema construction from the data-provider surface, the backend→frontend SSE streaming protocol, web search as a department capability, and cancellation.

This is **part 2 of 2** in the LLM system series. Part 1 (`llm-provider-design.md`) specifies provider adapters, capability gating, configuration storage, and failure classification. This spec consumes that contract.

> **Cross-reference note (2026-04-15):** Updated to reflect `database-design.md` decisions: `TierNotConfiguredError` handling in all runners (replaces `LLMConfigError`), dedicated SSE error events for unconfigured tiers.

## Scope

In scope:

- Execution-time layer under `packages/core/src/openlia/llm/runtime/`.
- Three runner modules — `ChatRunner`, `ReportRunner`, `BatchRunner` — one per execution flavor.
- Prompt authoring: one YAML file per department, Jinja2-templated, loaded into system / user messages.
- Framework JSON + style-guide markdown injection into report-generation prompts.
- Tool-schema construction from the data-provider mapping files, plus the `find_more_data` meta-tool and the `web_search` tool.
- SSE event taxonomy for chat and report streaming (`chat.*` and `report.*` flat typed events).
- Web search sourcing — native-provider-first, user-configured search-provider fallback.
- Cancellation semantics driven by client disconnect.
- Error-class mapping into SSE error events (non-transient classes from Part 1).

Out of scope:

- Everything in Part 1: provider adapters, resolver, configuration storage, wizard / settings UI for models.
- Chat-session persistence (prior message storage, transcript DB schema) — owned by the server layer.
- Report schema definition and renderer — specified by `report-rendering-pipeline-design.md`.
- Data-provider catalog structure, AI-review mapping, and runtime-expansion catalog search — specified by `data-provider-design.md`. This spec consumes the mapping files it produces.
- Vision / image inputs. `ChatRunner.attachments` is reserved but empty in v1.
- User-authored custom tools. See dev note.

---

## Architecture

The runtime takes a department's intent and executes it as LLM calls with the right prompts, tools, and output format, streaming or returning results. Three runners, one per execution flavor:

| Runner | Used by | Flavor |
|---|---|---|
| `ChatRunner` | Secretary, Equity Research follow-ups | Multi-turn chat, tool calls, token streaming |
| `ReportRunner` | Equity Research report modes, Earnings Update, Morning Briefing | Single-pass template fill, tool calls, structured output |
| `BatchRunner` | Retail Sentiment classification, Macro Research T4 / T5 assessments | Many small structured calls, no streaming |

Panic Thermometer does not use the LLM at all.

Each runner:

1. Calls `resolve()` from Part 1 with `(department_id, user_id, tier_override?)` to obtain an `LLMProvider`. If the resolved tier has no enabled models, `resolve()` raises `TierNotConfiguredError` — the runner terminates with a `*.error` event.
2. Loads the department's prompt YAML, the style guide (report only), and the framework JSON (report only).
3. Builds the tool list (tool-calling departments only).
4. Runs the provider call, dispatching tool calls as they arrive.
5. Emits SSE events (chat and report) or returns a structured result (batch).

The runners share: the `LLMProvider` contract, Part 1's retry / error classes, and a `ToolDispatcher` that routes tool calls to the data-provider layer.

**Scope boundary.** The runtime consumes the `LLMProvider` contract. Configuration, credentials, capability gating, and failure classification belong to Part 1. The runtime is pure execution.

---

## File Layout

```
packages/core/src/openlia/llm/runtime/
├── __init__.py              # Public exports: ChatRunner, ReportRunner, BatchRunner
├── chat.py                  # ChatRunner
├── report.py                # ReportRunner
├── batch.py                 # BatchRunner
├── prompts.py               # YAML prompt loader + Jinja2 rendering
├── tools.py                 # ToolDispatcher: build tool list, dispatch calls
├── web_search.py            # Native-or-configured web search resolution + adapter
├── events.py                # SseEvent dataclasses (chat.*, report.*)
├── messages.py              # ChatMessage, ReportRequest, BatchItem dataclasses
└── cancellation.py          # CancellationToken + grace-period helpers

packages/core/src/openlia/prompts/
├── secretary.yaml
├── equity_research.yaml
├── earnings_update.yaml
├── morning_briefing.yaml
├── macro_research.yaml          # for T4 / T5 batch assessments only
├── retail_sentiment.yaml        # for batch classification only
└── shared/
    ├── voice.yaml.j2            # shared voice snippets (Jinja2 includes)
    └── output_discipline.yaml.j2

packages/core/src/openlia/reports/frameworks/
├── stock_initiation.json            # framework, moved from planning/frameworks/
├── stock_initiation_style_guide.md
├── stock_update.json
├── stock_update_style_guide.md
├── sector_research.json
├── sector_research_style_guide.md
├── earnings_update.json
├── earnings_update_style_guide.md
├── morning_briefing.json
└── morning_briefing_style_guide.md
```

Frameworks and style guides move from `planning/frameworks/` (dev-only, excluded from the package) into the core package, as already planned by `report-rendering-pipeline-design.md`.

---

## Runner Interfaces

### ChatRunner

```python
class ChatRunner:
    async def run(
        self,
        department_id: str,
        user_id: str | None,
        messages: list[ChatMessage],                # full history, new user turn last
        attachments: list[Attachment] = [],         # reserved for vision; v1 empty
        cancel_token: CancellationToken | None = None,
    ) -> AsyncIterator[SseEvent]:
        ...
```

Server contract: the route loads prior messages from the chat-session DB, appends the new user turn, calls `ChatRunner.run()`, forwards events to the frontend, and on `chat.done` persists the assistant message plus any `stopped_at` marker. The runtime never touches the DB — it is stateless per call.

### ReportRunner

```python
class ReportRunner:
    async def run(
        self,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,                     # mode, user input, customizations
        cancel_token: CancellationToken | None = None,
    ) -> AsyncIterator[SseEvent]:
        ...
```

`ReportRequest` carries: `mode` (e.g. `stock_initiation`), the user's free-text prompt, enabled sections, custom sections, and length preference. The terminal `report.complete` event's payload is the full `ReportSchema` from the report-rendering spec.

### BatchRunner

```python
class BatchRunner:
    async def run(
        self,
        department_id: str,
        task: str,                                  # e.g. "rs_sentiment_classify", "mr_t4_assessment"
        items: list[BatchItem],
        schema: type[BaseModel],                    # pydantic schema each result must match
        concurrency: int = 8,
    ) -> list[BatchResult]:
        ...
```

Non-streaming. Each item's result is returned as `BatchResult(ok=True, data=...)` or `BatchResult(ok=False, error=...)` — per-item failures do not sink the batch.

---

## Prompt Authoring

One YAML file per department. Jinja2-templated. Loaded by `prompts.py` with a single render entry point.

### Structure

```yaml
# equity_research.yaml
chat:
  system: |
    You are the Equity Research analyst for OpenLIA...
    {% include "shared/voice.yaml.j2" %}

report:
  system: |
    You are the Equity Research analyst drafting a professional report.
    Follow the style guide below exactly.

    --- STYLE GUIDE ---
    {{ style_guide }}
    --- END STYLE GUIDE ---

    {% include "shared/output_discipline.yaml.j2" %}

  stock_initiation:
    user: |
      Generate a Stock Initiation Report for {{ user_input }}.

      Apply these customizations:
      - Enabled sections: {{ enabled_sections | join(', ') }}
      - Custom sections: {{ custom_sections | tojson }}
      - Length preference: {{ length }}

      Fill the framework below. Leave `instructions` fields empty in the
      response — the renderer strips them anyway.

      --- FRAMEWORK ---
      {{ framework | tojson(indent=2) }}
      --- END FRAMEWORK ---

  stock_update:
    user: |
      ...
  sector_research:
    user: |
      ...

batch:
  # Only for departments that use BatchRunner.
  classify_sentiment:
    system: |
      ...
    user: |
      ...
```

### Loader Contract

```python
def render(
    department_id: str,
    slot: str,                 # e.g. "chat.system", "report.stock_initiation.user"
    **context,                 # user_input, framework, style_guide, enabled_sections, ...
) -> str:
    """Render a prompt slot. Raises PromptSlotNotFound if the slot doesn't exist."""
```

Unknown slots raise at load time during app startup (every department's declared slots are validated), not at runtime — prompt typos fail loudly at test time, not during a user-facing call.

### System / User Split

System message = persona + style guide (stable across calls).
User message = framework JSON + user inputs + customizations (variable per call).

This split is explicit so prompt caching works naturally: the system string repeats across all stock-initiation reports, which providers' caches pick up automatically. OpenAI and Gemini cache above their built-in thresholds; the Anthropic adapter attaches `cache_control` markers to the system message by default.

---

## Framework & Style-Guide Injection (ReportRunner)

1. Server builds `ReportRequest` from department settings plus the user's prompt.
2. `ReportRunner` loads `reports/frameworks/{mode}.json`, applies user customizations (strips disabled sections, inserts custom sections, tags length preference), producing a call-ready framework dict.
3. `ReportRunner` loads `reports/frameworks/{mode}_style_guide.md` as plain text.
4. `ReportRunner` calls `prompts.render("equity_research", "report.{mode}.user", user_input=..., framework=call_ready_framework, length=..., enabled_sections=..., custom_sections=...)` for the user message.
5. Same for `report.system` with `style_guide=...`.
6. Both are passed to the provider via `LLMRequest`; `response_format` is set to the report schema JSON.
7. Data tool calls loop until the LLM stops requesting tools.
8. Final structured response is parsed as `ReportSchema`, yielded in `report.complete`.

---

## Structured Report Output

Report runners use native structured output (`response_format` with a JSON schema) to return the filled report schema. Part 1's per-department requirements manifest gates report-producing departments on `Capability.structured_output`, so every model that can be resolved for these departments supports this path. If a user somehow configures a non-supporting model into a report department, the adapter raises `CapabilityError` (Part 1) and the runtime terminates the call with a `report.error` event.

Tool calling is used for data fetching only — never for submitting the final report. Keeping these channels separate means tool-call events stay meaningful UI narration ("Fetched earnings for AAPL…") rather than being polluted by the final-submit call.

No incremental streaming of the structured output. The user sees the skeleton and `report.phase` / `report.tool_call` ticks until the full schema arrives in `report.complete`. Partial structured JSON is not safely parseable mid-stream, and section-by-section calls were explicitly rejected by the report-rendering spec.

---

## Tool Schema Construction

Tool-calling departments (Secretary, Equity Research, Earnings Update, Morning Briefing, Macro Research report path) see a tool list assembled from three sources.

### 1. Requirement-named data tools

The `ToolDispatcher` loads `~/.openlia/mappings/{department}.yaml` (produced by the data-provider AI review) and builds one tool per mapped requirement. Tool names = requirement types. The runtime routes each call to the winning provider per user priority.

```json
{
  "name": "stock_quote",
  "description": "Real-time or delayed stock quote (price, volume, market cap, ...) for a ticker.",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL"}
    },
    "required": ["symbol"]
  }
}
```

Tool schemas are generated from the `params` and `returns` fields of the mapped endpoint in the active provider catalog. `description` is lifted from the endpoint's `summary` and `description`. The LLM sees a clean, provider-agnostic surface — it never knows or cares which provider answered.

### 2. `find_more_data` meta-tool

Always present when any data tools are exposed.

```json
{
  "name": "find_more_data",
  "description": "Search all configured data providers for an endpoint matching a description. If found, the endpoint becomes available as a new tool you can call in a follow-up turn.",
  "parameters": {
    "type": "object",
    "properties": {
      "description": {"type": "string", "description": "Plain-language description of the data you need."}
    },
    "required": ["description"]
  }
}
```

Dispatching `find_more_data` invokes the Quick-tier LLM against active catalogs (per `data-provider-design.md`). On a hit, the new tool is added to the runner's in-memory tool list for subsequent turns in the same call. Bounded by `max_expansions_per_report`; Secretary is unlimited per the data-provider spec.

### 3. `web_search` tool

Present only when web search is available for this call — see the Web Search section.

```json
{
  "name": "web_search",
  "description": "Search the web for recent information not covered by configured data providers.",
  "parameters": {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"]
  }
}
```

### Dispatcher Contract

```python
class ToolDispatcher:
    async def build(
        self,
        department_id: str,
        has_web_search: bool,
    ) -> list[ToolSchema]:
        """Returns the full tool list: mapped requirements + find_more_data + (optional) web_search."""

    async def dispatch(self, call: ToolCall) -> ToolResult:
        """Routes by tool name:
           - mapped requirement → data-provider adapter for the winning provider
           - find_more_data    → Quick-tier catalog search
           - web_search        → web-search adapter (native or configured)
        """
```

### Parallel Tool Calls

Providers that return multiple tool calls in a single turn (OpenAI, Anthropic) hand them over together; the dispatcher runs them concurrently with `asyncio.gather` and merges results back into the conversation before the next LLM turn. Providers that return one call at a time work unchanged.

### Response Normalization

Every tool result is trimmed to a compact JSON shape before going back to the LLM: drop nulls, cap array length with a `"truncated": true` marker when exceeded. Keeps token usage predictable on data endpoints with verbose payloads.

### ReportRunner Tool Flow

Data tool calls happen in a `fetching_data` loop before the final structured-output turn. `report.phase` transitions `fetching_data → writing` when the LLM stops requesting data tools and emits its final response. `find_more_data` counts against the expansion budget.

---

## SSE Protocol

### Wire Format

Every event is a JSON object with a `type` field (flat discriminated union). One SSE stream per request: one chat turn = one request = one stream; one report generation = one request = one stream.

```
data: {"type": "chat.token", "message_id": "m_abc", "text": "Apple"}\n\n
```

Frontend parses with a TypeScript discriminated-union type over the `type` field.

### Event Taxonomy

| Event | Payload | Emitted by |
|---|---|---|
| `chat.start` | `{message_id}` | ChatRunner at turn start |
| `chat.tool_call.start` | `{message_id, call_id, tool_name, args_preview}` | Before dispatching a tool; `args_preview` is a short truncated string rendering of the arguments for UI narration only |
| `chat.tool_call.result` | `{message_id, call_id, ok, summary}` | After tool completes; `summary` is one-line UI text |
| `chat.token` | `{message_id, text}` | Provider token delta |
| `chat.report_thumbnail` | `{message_id, report_id, mode}` | When a chat turn produced a report inline |
| `chat.done` | `{message_id, stop_reason}` | Terminal on success; `stop_reason = "complete"` |
| `chat.error` | `{message_id, error_class, message}` | Terminal on error; `chat.done` is not sent after `chat.error` |
| `report.start` | `{report_id, department, mode, section_titles}` | ReportRunner at begin |
| `report.phase` | `{report_id, phase}` | `fetching_data \| writing \| finalizing` |
| `report.tool_call` | `{report_id, tool_name, summary}` | During `fetching_data` phase |
| `report.complete` | `{report_id, schema}` | Terminal on success; carries full `ReportSchema` |
| `report.error` | `{report_id, error_class, message}` | Terminal on error |

### Summary Formatting

Tool-call `summary` strings are pre-formatted for UI display — built by small formatter functions per tool (e.g. `stock_quote` summary: `"Fetched quote for {symbol}"`). Raw tool payloads never cross the wire; only the summary. This keeps the event stream cheap and prevents accidentally leaking API internals to the frontend.

### No Streaming of Structured Output

Report runners do not emit incremental token events. Skeleton until `report.complete`. Rationale in the Structured Report Output section.

---

## Cancellation

Client disconnect is the signal.

1. Frontend abandons the `EventSource` / fetch-stream (user hits Stop, navigates away, closes tab).
2. Server route polls `request.is_disconnected()` between yields and flips the runner's `CancellationToken`.
3. Runner aborts the provider stream using each adapter's native cancel path (`httpx` stream close for most, SDK-level cancel where provided).
4. In-flight tool calls get a 2-second grace period, then are abandoned (fire-and-forget).
5. No terminal SSE event is sent — the connection is already gone.
6. Server persistence layer (outside runtime scope) writes partial chat text with a `stopped_at` marker. For reports nothing is persisted; there is no partial-report state.

Runners raise no exception on cancellation — the async iterator simply stops yielding.

---

## Web Search

Resolution order per call:

```
1. If the resolved LLM supports native web search
     (capability flag: capabilities.web_search_native)
   → expose the provider's native web-search tool directly.
     Provider bills the user; no separate key.

2. Else if a search provider is configured in the data-provider system
     (new "search" category — Brave / Tavily / Serper / You.com)
   → expose a `web_search` tool that proxies to that provider.

3. Else → web_search is unavailable for this call.
```

The runtime resolves this once per call and passes `has_web_search: bool` plus the chosen variant into `ToolDispatcher.build()`. From the LLM's perspective both variants look identical — one tool called `web_search` taking a `query` string. Native tool return shapes (snippets + citations) are normalized to the configured-search adapter's shape so the prompt surface is stable.

### Additions to Part 1

1. `Capabilities.web_search_native: bool` added to `core/llm/capabilities.py`. Shipped map flips it on for: Anthropic families supporting `web_search_20250305`, OpenAI `gpt-5.4+` with `web_search_preview`, Gemini with Google Search grounding. Off elsewhere.
2. `Capability.web_search` added as a new enum value usable in `DepartmentRequirements.preferred` only, never in `required`. A department must function without web search.

### New Data-Provider Category: `search`

Sibling to `financial`, `news`, `social_media`. Same `ProviderEntry` shape; `api_key` mode only (MCP mode not applicable).

| Provider | Mode | Credentials |
|---|---|---|
| Brave Search API | api_key | API key |
| Tavily | api_key | API key |
| Serper | api_key | API key |
| You.com Search API | api_key | API key |

Setup Wizard Step 4 gains an optional "Web Search" card. Startup validation does not require a search provider — web search is optional everywhere.

### Per-Department Declarations

| Department | `web_search` in `preferred`? |
|---|---|
| Secretary | Yes — chat often benefits from fresh web context |
| Equity Research | Yes — recent news context during report generation |
| Earnings Update | Yes |
| Morning Briefing | Yes — fresh news is the whole point |
| Macro Research | Yes |
| Retail Sentiment | No — uses social feeds, not web |
| Panic Thermometer | Not applicable (no LLM) |

---

## BatchRunner

Used by Retail Sentiment (sentiment classification, per `retail-sentiment-dashboard-design.md`) and Macro Research (T4 / T5 LLM assessments, per `macro-research-dalio-dashboards-design.md`). Non-streaming, non-interactive.

```python
async def run(self, department_id, task, items, schema, concurrency=8) -> list[BatchResult]:
    # For each item: render prompt, call LLM with response_format=schema,
    # parse, return. asyncio.Semaphore(concurrency) bounds in-flight calls.
    # Per-item failures are surfaced as BatchResult(ok=False, error=...)
    # so one bad item doesn't sink the batch.
```

Batches always use `response_format`. The Quick-tier model resolved for the caller is gated on `structured_output` per requirements — no capability gap to bridge.

No tool calling in batch. `BatchRunner` never builds a tool list. The per-item prompt is the only input the LLM sees per call.

Examples:

- **RS sentiment classification.** Item = a social post's text. Prompt instructs the LLM to classify into a fixed enum (bullish / bearish / neutral) with confidence. Schema: `{sentiment: Literal[...], confidence: float}`.
- **MR T4 / T5 assessment.** Item = one framework question plus the live data bundle MR's dashboard code gathered. Prompt instructs the LLM to score + justify. Schema: `{score: int, justification: str, citations: list[str]}`.

---

## Error Handling

Inherits Part 1 unchanged. Every runner sits on top of `LLMProvider`, so the retry / error-class machinery is already there. Runner-specific mapping into SSE events:

| Part 1 error class | Runner behavior |
|---|---|
| `TransportError` / `RateLimitError` / `ProviderOutageError` | Retried inside the adapter. If retries exhaust, the exception reaches the runner and becomes a terminal `*.error` event with the corresponding `error_class`. |
| `AuthError` / `ModelNotFoundError` / `ContextLengthError` / `CapabilityError` | No retry. Terminal `*.error` event with the Part 1 chat-facing message. |
| `TierNotConfiguredError` | No retry. Terminal `*.error` event. Chat message: "The `<tier>` tier has no models configured. Ask your admin to add one in Settings → Admin → Models." Frontend renders a deep-link to the admin panel. |

### Tool-Dispatch Failures

Tool-dispatch failures (data-provider HTTP errors, web-search failures, `find_more_data` misses) do **not** terminate the runner. The error is returned to the LLM as a tool result with `ok=false` and a terse error string — the LLM decides whether to retry, pick a different tool, or ignore. A `chat.tool_call.result` with `ok=false` and a human summary ("Failed to fetch quote for AAPL") is emitted; the turn continues.

### Unexpected Exceptions

A runner that dies from a bug (not a Part 1 error class) bubbles up as an unexpected exception. The server turns it into a generic `*.error` event with `error_class="RuntimeError"` and message "An internal error occurred."

---

## Testing Strategy

- **Prompt rendering tests.** Each department's YAML renders cleanly for every slot it declares; golden-file snapshots for common contexts catch prompt regressions.
- **ChatRunner tests.** Fake `LLMProvider` yielding a canned stream (with and without tool calls); assert the SSE event sequence matches expectations. Cancellation test: flip the token mid-stream, assert the runner stops emitting within 2 seconds.
- **ReportRunner tests.** End-to-end with a fake provider returning a canned report schema; assert `report.start → phase(fetching_data) → tool_calls → phase(writing) → complete` sequence.
- **BatchRunner tests.** Concurrency respected, per-item failures surfaced without sinking the batch.
- **ToolDispatcher tests.** Mapping-file loading, requirement → provider routing with multiple providers and priority ordering, `find_more_data` hit and miss paths, web_search native vs. configured routing.
- **Integration test per department.** Canned LLM output + mocked data-provider HTTP returns; assert the final SSE event sequence (chat) or final report schema (report) matches expectation.

---

## Non-Goals (v1)

- Streaming partial report schema — skeleton-until-complete stays.
- Section-by-section report generation — single-pass stays, per the report-rendering pipeline decision.
- Vision inputs — `ChatRunner.attachments` is reserved but empty.
- Multi-modal output — no image / audio generation.
- Persistent tool-call cache — every chat turn rebuilds the tool list.
- Cross-session conversation memory — runtime is stateless per call; the session DB is the only persistence mechanism.
- Provider-native "computer use" or agent modes — tool calling is limited to the three sources defined above.
- Automatic prompt A/B testing framework — prompts are author-curated, not tuned from telemetry.
- Runtime prompt-injection defense layer — input sanitization is the department author's responsibility at the prompt-template level.
- Fine-grained per-tool rate limiting — rate limits are the data-provider adapter's concern, not the runtime's.
- User-authored custom tools. See dev note.

---

## Cross-References: Required Edits to Other Specs

1. **`llm-provider-design.md` § Capabilities.**
   - Add `web_search_native: bool` to the `Capabilities` dataclass.
   - Extend the shipped capability map to flag `web_search_native` on supporting OpenAI, Anthropic, Gemini, and OpenRouter model families.
   - Add `web_search` as a `Capability` enum value valid in `DepartmentRequirements.preferred` only.

2. **`data-provider-design.md` § Provider Categories.**
   - Add fourth category `search` (Brave / Tavily / Serper / You.com). Same `ProviderEntry` shape, `api_key` mode only, optional at startup.
   - Note that search providers do not participate in the requirements-manifest AI-review flow — they are consumed by the runtime layer directly, not by the data-tool mapping.

3. **`SetupWizardSpec.md` § Step 4 — Data Providers.**
   - Add optional "Web Search" card below the Social Media card. Cleared fields = web search unavailable for departments that declare it as preferred (shows as amber in Step 6 review, never blocking).

4. **`report-rendering-pipeline-design.md` § Streaming During Generation.**
   - Expand the four `report:*` SSE events to match the taxonomy in this spec (namespace normalized to `report.*` with a dot, adds `report.tool_call`, and `report.complete` payload is explicitly the full `ReportSchema`).

5. **`ChatInterfaceSpec.md` § (new) Event Handling.**
   - Add a short section specifying how the frontend consumes the `chat.*` event stream: which events drive which UI state (`chat.start` → show badge + thinking dots; `chat.tool_call.start` → show narration chip; `chat.tool_call.result` with `ok=false` → show inline chip with muted color; `chat.token` → append text; `chat.report_thumbnail` → render thumbnail card; `chat.done` → stop cursor on success; `chat.error` → stop cursor + show inline error; connection closed without a terminal event → stop cursor and render the "Response stopped." label from `ChatInterfaceSpec.md`).

6. **`planning/projectStructure.md` § `core/openlia/llm/`.**
   - Add the `runtime/` subdirectory and its file list.
   - Add `core/openlia/prompts/` as a sibling with the YAML file list per department.
   - Note that `reports/frameworks/` holds the framework JSON and style-guide markdown moved from `planning/frameworks/`.

---

## Dev Notes

> **Dev note — prompt caching effectiveness.** The system / user split is designed so providers' automatic prompt caching catches the stable parts (persona + style guide). Anthropic requires explicit `cache_control` markers; adapters attach them to the system message by default. OpenAI and Gemini cache automatically above their thresholds. Validate cache-hit rates in the first few weeks of production telemetry; if hit rates are poor, review the YAML structure for incidental per-call variation leaking into the system prompt.

> **Dev note — `find_more_data` latency.** The expansion meta-tool invokes the Quick-tier LLM to search catalogs, adding a ~1-2 second round trip per call. For chat (Secretary) this is acceptable. For reports, bursty expansion calls could inflate total generation time. Consider caching expansion results per `(department, description)` for the lifetime of a report-generation call.

> **Dev note — parallel tool calls and ordering.** When providers return multiple tool calls in one turn, the dispatcher runs them concurrently and returns results in the order the LLM requested. If provider-side enforcement of order matters for any future tool, add a serialize-per-turn flag on the `ToolDispatcher`. v1 runs everything in parallel.

> **Dev note — batch-runner concurrency defaults.** Default `concurrency=8` is a guess. RS classifies hundreds of social posts per dashboard refresh; this could saturate a rate-limited tier. Instrument batch duration and 429 counts; tune per department if needed.

> **Dev note — native web-search cost accounting.** Anthropic and OpenAI bill web-search use on top of completion tokens. Users on paid tiers may see unexpected bills on Secretary chats. Surface this in Settings → Models with a one-liner when native web search is active.

> **Dev note — v2: user-configurable custom tools.** v1 restricts the tool surface to three sources: requirement-mapped data tools (from the data-provider system), `find_more_data`, and `web_search`. A later version could allow users to register arbitrary tools — user-supplied OpenAPI specs, MCP tool servers beyond the data-provider category, or hand-written Python callables — and attach them per department. Design considerations for that iteration: where user-added tools live in the capability-gating story (users would need to self-declare `tool_calling` suitability), how they interact with per-department mappings, whether they count against the `find_more_data` budget, and how naming collisions with requirement tools are resolved. Worth revisiting once the core three-source model has been running in production and real user asks are visible.

---

## Next in This Series

The LLM system series ends with this spec. The runtime layer consumes Part 1's `LLMProvider` and the data-provider spec's mapping files; together they define how every department reaches the LLM.
