# EU v2 — Per-Connector Data Sources Routing (PR 2) — Design

**Date:** 2026-05-30
**Branch:** `feat/eu-v2-per-connector-routing` (stacks on `feat/eu-v2-template-split`, PR #217)
**Status:** Design for review.

## Goal

The EU v2 "Data Sources" section should list **every validated connector** the user has configured and let them toggle each one; an enabled connector's tools actually reach the Earnings Update LLM. The list changes live as connectors are added / removed / (re)validated.

**Locked decision (user):** **Hybrid routing.** EODHD keeps its 4 curated, hand-tuned tools + the dedicated earnings-calendar tool (the weekly scheduler also depends on it). Every *other* validated connector (newsapi_ai, firecrawl, x, FMP/Finnhub if installed, future MCP/CLI connectors) routes through the existing connector **dispatcher**. Model-native web search stays a separate toggle.

## Key facts from investigation

- **Dispatcher** (`openlia.connectors.dispatch.Dispatcher`) is built server-side by `dispatcher_factory.build_dispatcher(db, disabled_connector_ids=...)` from `connectors` + `runner_callable_specs` rows. It uses a **blocklist** (`disabled_connector_ids`) — so per-connector enablement = block everything the user hasn't enabled.
- `dispatcher.candidate_tools()` → `[{name: "<provider_id>__<tool>", description, input_schema, category}]` across all validated, non-blocked connectors.
- `dispatcher.dispatch_tool_use(prefixed_name, args)` is **async**; routes by provider_id + tool name to the connector's transport.
- A connector's tool set comes from its **cached validated inventory** (`connectors.cached_tools`). EODHD's is its **full SDK surface** (dozens of methods) — which is exactly why we keep EODHD curated and only dispatcher-route the others.
- **Async gap:** `report_eu/runner.py` `_dispatch_one` is sync (`tool.execute(args)`) but called from `async def run`. Dispatcher tools are async → the runner's dispatch path must become async-aware.
- The user's dev DB has 4 validated built-in connectors: `eodhd` (financial), `newsapi_ai` (news), `firecrawl` (web_search), `x` (social).

## Design

### 1. Settings model — provider-id enablement set

Replace the three booleans (`financial_enabled` / `calendar_enabled` / `web_search_enabled`) with:

- `enabled_provider_ids: list[str]` — provider ids the user has enabled (e.g. `["eodhd", "newsapi_ai"]`). Provider id (not the row UUID) is the stable, routing-natural key (`candidate_tools` names are `provider_id__tool`; survives connector re-install; works for env-only EODHD where no row exists).
- `web_search_enabled: bool` — model-native web search (kept; it is **not** a registry connector).

**Migration** (`eu_v2_settings`): add `enabled_provider_ids` (JSON/text) column; data-migrate each row — `"eodhd"` added when `financial_enabled` **or** `calendar_enabled` was true; `web_search_enabled` carries over; then drop `financial_enabled` / `calendar_enabled`. (`report_eu` is independent and pre-GA, so a clean replace is fine.)

EODHD note: `"eodhd"` in the set ⇒ **curated** EODHD tools (financial + calendar), resolved via the existing env-or-connector-secret bridge (`resolve_eodhd_api_key`). It does **not** go through the dispatcher.

### 2. Data-sources endpoint — dynamic, registry-driven

Rework `compute_data_sources` (`eu_v2_data_sources.py`) + `GET .../v2/data-sources` to return:

```python
class DataSource(BaseModel):
    key: str                 # provider_id, or "model_web_search"
    display_name: str        # "EODHD", "NewsAPI.ai", "Firecrawl", "X", "Web search"
    category: str            # financial | news | social | web_search
    routing: str             # "curated" (EODHD) | "dispatcher" | "model_native"
    available: bool          # validated connector present / model supports web search
    enabled: bool            # in the user's enabled set
    unavailable_reason: str | None   # reason code (i18n'd client-side)

class DataSourcesOut(BaseModel):
    sources: list[DataSource]
```

Composition:
- **EODHD** slot (`routing="curated"`, `category="financial"`): `available = resolve_eodhd_api_key(db) is not None` (env or installed connector). One slot covering financial + calendar.
- **Every other validated connector** from the registry → one `DataSource` (`routing="dispatcher"`, its category, `available=True`, `display_name`/category from the connector row). This replaces today's muted "also configured" footnote with real, toggleable entries.
- **Model web search** (`key="model_web_search"`, `routing="model_native"`): `available = capabilities_for(provider_kind, model).web_search_native`.

The list is computed from the live registry, so it changes as the user installs/removes/validates connectors.

### 3. Engine wiring — hybrid catalog

`report_eu/tools/registry.py` `build_catalog(...)` gains:
- `dispatcher: Dispatcher | None`
- `enabled_provider_ids: set[str]`

Catalog assembly:
- Output tools — always (unchanged).
- **EODHD curated** — when `"eodhd" in enabled_provider_ids`: build `build_data_tools(...)` + `build_earnings_calendar_tool(...)` as today (from `EuDataTransports`). Unchanged path.
- **Dispatcher connectors** — for every `candidate_tools()` entry whose `provider_id` is in `enabled_provider_ids` and `!= "eodhd"`: build an **async** ledger-aware `ResearchTool` (see §4).
- **Model web search** — `native_tools=("web_search",)` when `web_search_enabled`.

Server wiring (`eu_v2_run_service`): build the dispatcher via `dispatcher_factory.build_dispatcher(db, disabled_connector_ids=<all validated connector ids whose provider_id ∉ enabled_provider_ids>)`, pass it + `enabled_provider_ids` to the runner/catalog. EODHD transports continue to be resolved as today.

### 4. Async dispatch + the connector-tool wrapper

**Async refactor (localized):**
- `report_eu/runner.py`: make `_dispatch_one` `async`; in the loop, `await _dispatch_one(...)`. Inside it: `result = tool.execute(args)`; `if inspect.isawaitable(result): result = await result`. Curated/output tools stay sync (return `ToolResult`); dispatcher tools return a coroutine. Wrap the whole tool loop in `async with dispatcher.in_department("earnings_update"):` when a dispatcher is present.
- `ResearchTool.execute` is typed sync; the dispatcher wrapper returns an awaitable. We loosen the EU dispatch path to accept either (documented), rather than changing the shared v2.3 `ResearchTool` type.

**Wrapper** (`report_eu/tools/dispatcher_tools.py`, new): for each enabled connector tool,
- descriptor: `name = "<provider>__<tool>"`, `description`, `parameters = input_schema` (from `candidate_tools`).
- async execute: `raw = await dispatcher.dispatch_tool_use(name, args)` → `to_jsonable(raw)` (reuse the chat runner's coercion) → `prune_empty(payload)` → `ledger.append(tool_name=name, arguments=args, result_summary=..., provenance=DataProviderSource(provider=provider_id.upper(), endpoint=tool, retrieved_at=now))` → return `ToolResult(payload={source_id, summary, data}, provenance, summary)`. Mirrors the curated `_wrap` so citations/fidelity/ledger all work identically.
- transport failures → `ToolExecutionError` (structured, the loop surfaces it to the model).

### 5. Prompt — generic per-connector block

`report_eu/prompts.py` `_render_connectors_block`: replace the hardcoded financial/calendar/web text with:
- the curated EODHD block (when `"eodhd"` enabled) — same wording as today;
- a generic block per enabled dispatcher connector: its display name + category + the names/one-line descriptions of its tools (from `candidate_tools`), so the model knows what it can call;
- the web-search block (when model-native enabled);
- the existing "no data tools" fallback when nothing is enabled.

### 6. Frontend — dynamic per-connector toggles

`ReportSettingsModal.tsx` Data Sources section: render the `sources` list from the reworked endpoint as a list of per-connector toggles (provider label + category), plus the model-web-search toggle. Disabled+reason for unavailable sources; the muted "also configured" footnote is **removed** (those are now real toggles). Save persists `enabled_provider_ids` + `web_search_enabled`. `useEuDataSources` already refetches on model change (drives web-search availability). i18n for category labels + reason codes (en + zh-TW).

### 7. Run-time enforcement & scheduler

- `build_run_request`: enabled providers ∩ validated connectors (AND-gate) — a stale-enabled but now-removed connector silently drops.
- The weekly `EU_V2_SYNC` calendar build and `EU_V2_DISPATCH` are **unchanged** — they use the curated EODHD calendar path, independent of the per-connector report toggles.

## Risks / open points

- **Tool-schema cleanliness:** dispatcher `input_schema`s come from connector introspection; some may not be Anthropic-validator-clean (the EODHD builtin documents such quirks). Non-EODHD built-ins validated at install should be fine; flag if a connector's schema 400s — surface as a tool-load skip, not a run failure.
- **Relevance:** social (x) / web (firecrawl) tools on an earnings report are the user's call (they toggle). The prompt should tell the model these are optional context, not required.
- **Result size:** raw dispatcher payloads are pruned (`prune_empty`) but otherwise uncurated; watch token cost (the caching + prune work already helps).
- **Citations:** dispatcher results cite via the same ledger `source_id`; provenance is a generic `DataProviderSource` — confirm the renderer/bibliography handles it (it already renders `DataProviderSource`).

## Testing

- `compute_data_sources`: registry with N validated connectors → N+EODHD+web entries; reflects enable/remove; EODHD availability via env vs connector secret.
- Catalog: enabled set → curated EODHD tools present when "eodhd" on; dispatcher wrappers present per enabled non-eodhd provider; none when disabled.
- Async dispatch: a fake dispatcher tool (async) resolves through `_dispatch_one`; ledger entry + source_id + pruned payload; failure → `ToolExecutionError`.
- Migration: old (financial/calendar/web bools) → `enabled_provider_ids` seeded with "eodhd" + web carry-over.
- Run-time AND-gate; scheduler calendar path unaffected.
- Frontend: dynamic toggle list from endpoint; save persists provider set; unavailable disabled+reason.

## Non-goals

- Routing EODHD through the dispatcher (kept curated by decision).
- Per-run connector overrides (settings stay per-user).
- `runner_callable_specs`-based deterministic need fetching (the EU engine is LLM-driven tool use, not fixed needs).
- Changing the connector install / validation flow.
