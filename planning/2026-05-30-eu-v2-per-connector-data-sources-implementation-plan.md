# EU v2 — Per-Connector Data Sources Routing (PR 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Data Sources lists every validated connector as a toggle; enabled non-EODHD connectors route to the EU LLM via the dispatcher (hybrid — EODHD stays curated). Dynamic with the registry.

**Architecture:** See `planning/2026-05-30-eu-v2-per-connector-data-sources-design.md`. Hybrid: EODHD curated (unchanged), other connectors dispatcher-routed (async). Settings move from 3 booleans to `enabled_provider_ids` + `web_search_enabled`. Branch `feat/eu-v2-per-connector-routing` (stacks on #217).

**Tech Stack:** core `report_eu` engine + `openlia.connectors.dispatch`, FastAPI/SQLAlchemy/Alembic, React/TS, pytest, ruff, i18next.

**Build order:** core schema → engine (async dispatch, wrapper, catalog, prompt) → server (settings+migration, data-sources, run-service+routes) → frontend.

---

## Task 1: `EnabledConnectors` schema → provider set (core)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/schemas.py`
- Test: `packages/core/tests/runtime/report_eu/test_schemas.py`

Today `EnabledConnectors` = `{financial, earnings_calendar, web_search}` booleans. Change to:

```python
class EnabledConnectors(BaseModel):
    """Which data sources the LLM may use this run.

    ``provider_ids`` are the registry provider ids enabled for routing
    (``"eodhd"`` ⇒ curated EODHD tools; any other ⇒ dispatcher-routed).
    ``web_search`` is model-native web search (not a registry connector).
    """
    provider_ids: frozenset[str] = frozenset()
    web_search: bool = False

    @property
    def eodhd(self) -> bool:        # curated EODHD financial + calendar
        return "eodhd" in self.provider_ids
```

- [ ] Test: `EnabledConnectors(provider_ids={"eodhd","newsapi_ai"}, web_search=True)` → `.eodhd is True`, `"newsapi_ai" in .provider_ids`; default → empty set, `web_search False`, `.eodhd False`.
- [ ] Run → fail → implement → pass. Update any direct `EnabledConnectors(financial=...)` constructions in core tests/fixtures to the new shape (grep `EnabledConnectors(` under packages/core).
- [ ] ruff; commit: `feat(eu-v2): EnabledConnectors as provider set + web_search`.

---

## Task 2: async tool dispatch in the runner (core)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/runner.py`
- Test: `packages/core/tests/runtime/report_eu/test_runner.py` (add a case; reuse `_fakes.py`)

Make the dispatch path async so dispatcher tools (coroutine `execute`) work; curated/output tools (sync `execute`) keep working.

- [ ] **Step 1: failing test** — a fake `ResearchTool` whose `execute` is an async function returns a `ToolResult`; drive one turn that calls it; assert the tool result message contains the payload. (Today this would fail because `_dispatch_one` doesn't await.)

- [ ] **Step 2: implement**
  - `_dispatch_one` → `async def _dispatch_one(call, tools_by_name) -> Message`. Inside:
    ```python
    result = tool.execute(call.arguments)
    if inspect.isawaitable(result):
        result = await result
    ```
  - In `run`'s loop: `result_message = await _dispatch_one(call, tools_by_name)`.
  - Add `dispatcher` param to the `Runner` (constructor or `run`) — default `None`. When not `None`, wrap the **turn loop** in `async with dispatcher.in_department("earnings_update"):`. (Import the dispatcher type lazily / under TYPE_CHECKING to avoid a hard import; the param is duck-typed.)
  - `import inspect`.

- [ ] **Step 3: pass.** Confirm the existing sync-tool runner tests still pass (curated path unchanged).
- [ ] ruff; commit: `feat(eu-v2): async-capable tool dispatch + in_department context`.

---

## Task 3: dispatcher-tool wrapper (core)

**Files:**
- Create: `packages/core/src/openlia/llm/runtime/report_eu/tools/dispatcher_tools.py`
- Test: `packages/core/tests/runtime/report_eu/test_dispatcher_tools.py`

Mirror the curated `data_tools._wrap`, but async and dispatcher-backed.

- [ ] **Step 1: failing test** — a fake dispatcher exposing `candidate_tools()` (one entry `{"name":"newsapi_ai__search","description":"d","input_schema":{...},"category":"news"}`) and async `dispatch_tool_use(name,args)` returning a dict with a null field. `build_dispatcher_tools(ledger=..., dispatcher=fake, enabled_provider_ids={"newsapi_ai"})` returns one `ResearchTool` named `newsapi_ai__search`; `await tool.execute({...})` → `ToolResult` whose `payload["source_id"]` is ledgered, `payload["data"]` is `prune_empty`'d, provenance is a `DataProviderSource(provider="NEWSAPI_AI", ...)`. A second test: `enabled_provider_ids` excluding the provider → no tools; `"eodhd"` is always excluded (curated elsewhere).

- [ ] **Step 2: implement**
  ```python
  from datetime import UTC, datetime
  import inspect
  from openlia.connectors.serialization import to_jsonable
  from ...report_v2_3.research import ResearchTool, ToolDescriptor, ToolExecutionError, ToolResult, prune_empty
  from ...report_v2_3.schemas import DataProviderSource
  from ..ledger import CitationLedger

  def build_dispatcher_tools(*, ledger: CitationLedger, dispatcher, enabled_provider_ids: frozenset[str]) -> list[ResearchTool]:
      tools = []
      for td in dispatcher.candidate_tools():
          name = td["name"]
          provider_id = name.split("__", 1)[0]
          if provider_id == "eodhd" or provider_id not in enabled_provider_ids:
              continue
          tools.append(_wrap_dispatcher_tool(ledger, dispatcher, td, provider_id))
      return tools

  def _wrap_dispatcher_tool(ledger, dispatcher, td, provider_id) -> ResearchTool:
      name = td["name"]
      async def _execute(args: dict):
          try:
              raw = await dispatcher.dispatch_tool_use(name, args)
          except Exception as exc:
              raise ToolExecutionError(f"{name} failed: {exc!s}") from exc
          data = prune_empty(to_jsonable(raw))
          provenance = DataProviderSource(provider=provider_id.upper(), endpoint=name.split("__",1)[1], retrieved_at=datetime.now(UTC))
          summary = f"{provider_id} {name.split('__',1)[1]} result"
          entry = ledger.append(tool_name=name, arguments=dict(args), result_summary=summary, provenance=_prov_dict(provenance))
          return ToolResult(payload={"source_id": entry.source_id, "summary": summary, "data": data}, provenance=provenance, summary=summary)
      return ResearchTool(descriptor=ToolDescriptor(name=name, description=td.get("description",""), parameters=td.get("input_schema") or {"type":"object","properties":{}}), execute=_execute)
  ```
  `_prov_dict` = `provenance.model_dump(mode="json")` with a str() fallback (copy from `data_tools._provenance_to_dict`). Note `DataProviderSource` field names — verify against `report_v2_3/schemas.py` (provider/endpoint/period/retrieved_at) and adjust (period optional).

- [ ] **Step 3: pass.** ruff; commit: `feat(eu-v2): dispatcher-backed connector tool wrapper`.

---

## Task 4: hybrid catalog (core)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/tools/registry.py`
- Test: `packages/core/tests/runtime/report_eu/test_registry.py` (or existing catalog test)

- [ ] **Step 1: failing test** — `build_catalog(ledger, workspace, transports=fake_eodhd, enabled_connectors=EnabledConnectors(provider_ids={"eodhd","newsapi_ai"}, web_search=True), dispatcher=fake_dispatcher)` → catalog `by_name()` contains the curated EODHD tools AND `newsapi_ai__search`; `native_tools == ("web_search",)`. With `provider_ids={"newsapi_ai"}` (no eodhd) → no curated EODHD tools, dispatcher tool present. With `dispatcher=None` → curated-only (back-compat).

- [ ] **Step 2: implement** — `build_catalog(..., dispatcher=None)` gains the dispatcher param. Assembly:
  - output tools always.
  - `if enabled_connectors.eodhd:` → `build_data_tools(...)` + `build_earnings_calendar_tool(...)` (unchanged).
  - `if dispatcher is not None:` → `core.extend(build_dispatcher_tools(ledger=ledger, dispatcher=dispatcher, enabled_provider_ids=enabled_connectors.provider_ids))`.
  - `native = ("web_search",) if enabled_connectors.web_search else ()`.
  - Update the call site in `runner.run` to pass `dispatcher=self._dispatcher` (from Task 2).

- [ ] **Step 3: pass.** ruff; commit: `feat(eu-v2): hybrid tool catalog (curated EODHD + dispatcher connectors)`.

---

## Task 5: generic per-connector prompt block (core)

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_eu/prompts.py`
- Test: `packages/core/tests/runtime/report_eu/test_prompts.py`

`_render_connectors_block` currently keys off the 3 booleans. It now needs the enabled providers + the dispatcher's tool descriptions. Simplest: pass a small list of `(provider_label, [tool names])` for enabled dispatcher connectors into `build_system_prompt`.

- [ ] **Step 1: failing test** — prompt for a run with `provider_ids={"eodhd","newsapi_ai"}` contains the curated EODHD block AND a "NewsAPI" connector block naming its tool(s); with only `{"eodhd"}` → no extra connector block; empty providers + no web search → the "No data tools" fallback.

- [ ] **Step 2: implement** — extend `build_system_prompt(request, *, connector_tools: list[ConnectorPromptInfo] = ())` where `ConnectorPromptInfo = (provider_label, category, [(' tool_name', 'desc')])`. `_render_connectors_block` renders: curated EODHD block when `request.enabled_connectors.eodhd`; one block per `connector_tools` entry (label, category, bulleted tool names + one-line descs, noting they're optional context); the web-search block when `request.enabled_connectors.web_search`; the no-tools fallback when nothing. The runner builds `connector_tools` from the catalog's dispatcher tools (names + descriptions) and passes it in.

- [ ] **Step 3: pass.** ruff; commit: `feat(eu-v2): generic per-connector prompt block`.

---

## Task 6: settings model + migration (server)

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/report_eu.py` (`EuV2Settings`)
- Create: migration `packages/server/.../versions/2026-05-31_1200_eu_v2_enabled_providers.py`
- Modify: `packages/server/src/openlia_server/services/eu_v2_settings.py`
- Test: `packages/server/tests/db/test_report_eu_migration.py`, `packages/server/tests/test_services/test_eu_v2_settings.py`

- [ ] **Step 1: model + migration**
  - `EuV2Settings`: add `enabled_provider_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)`; keep `web_search_enabled`; drop `financial_enabled`/`calendar_enabled` (or keep nullable for one release — plan: drop). Add `report_eu_instructions`-style migration: add JSON column, data-migrate (`["eodhd"]` when financial or calendar was true), drop the two bool columns. down_revision = current head (`uv run --directory packages/server alembic heads`).
  - Migration test: after upgrade, a row that had financial=1 → `enabled_provider_ids == ["eodhd"]`; `_EU_V2_TABLES` unchanged; single head.

- [ ] **Step 2: settings service** — `EuSettingsDTO`: replace `financial_enabled`/`calendar_enabled` with `enabled_provider_ids: frozenset[str]`; keep `web_search_enabled`. `_row_to_dto`, `get_settings` defaults (`enabled_provider_ids=frozenset({"eodhd"})` default-on?? — decide: default = `{"eodhd"}` to match today's financial/calendar-on default), `update_settings(enabled_provider_ids, web_search_enabled, ...)`. Tests: round-trip the set.

- [ ] Run targeted + migration tests (sandbox disabled). ruff; commit: `feat(eu-v2): settings enabled_provider_ids + migration`.

---

## Task 7: dynamic data-sources service (server)

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_data_sources.py`
- Test: `packages/server/tests/test_services/test_eu_v2_data_sources.py`

- [ ] **Step 1: failing tests** — with a registry of `eodhd, newsapi_ai, firecrawl, x` (validated) + EODHD key present + a web-search-capable model: `compute_data_sources(...)` returns a `sources` list with: an EODHD entry (`routing="curated"`, `available=True`, `enabled` per settings), one entry per non-eodhd validated connector (`routing="dispatcher"`, `available=True`, category/label from the row), and a `model_web_search` entry (`routing="model_native"`, available per `capabilities_for`). Removing a connector from the registry drops its entry. EODHD `available=False` (no key) → reason `eodhd_unconfigured`.

- [ ] **Step 2: implement** — new frozen dataclasses `DataSource(key, display_name, category, routing, available, enabled, unavailable_reason)` + `EuDataSources(sources)`. Build from `connectors_service.list_connectors(db)` filtered to `status == ConnectorStatus.VALIDATED.value`: EODHD → curated slot (availability via `resolve_eodhd_api_key`); others → dispatcher slots; append the `model_web_search` slot (`capabilities_for(...).web_search_native`). `enabled` from `eu_v2_settings.get_settings(...).enabled_provider_ids` (+ `web_search_enabled` for the model slot). Keep the `provider_kind`/`model` override params.

- [ ] Run; pass. ruff; commit: `feat(eu-v2): dynamic registry-driven data-sources service`.

---

## Task 8: run-service dispatcher wiring + routes (server)

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_run_service.py`
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
- Test: `packages/server/tests/test_services/test_eu_v2_run_service.py`, route tests

- [ ] **Step 1: run service** — in `build_run_request`/`start_run_async` path:
  - settings → `EnabledConnectors(provider_ids=settings.enabled_provider_ids, web_search=settings.web_search_enabled and caps.web_search_native)` (AND-gate web search by capability as today; AND-gate provider_ids by validated registry — drop ids not in the validated set).
  - Build the dispatcher: `disabled = {c.id for c in connectors_service.list_connectors(db) if c.provider_id not in settings.enabled_provider_ids}`; `dispatcher = dispatcher_factory.build_dispatcher(db, disabled_connector_ids=frozenset(disabled))`. Pass the dispatcher into the runner construction (alongside the existing EODHD transports). EODHD transports resolved as today (`build_eu_v2_transports(api_key=resolve_eodhd_api_key(db))`).
  - Test: a settings set incl. a non-eodhd provider → the constructed `RunRequest.enabled_connectors.provider_ids` matches; a removed/unvalidated provider is dropped.

- [ ] **Step 2: routes** — rework the data-sources DTOs to the new shape:
  ```python
  class DataSourceOut(BaseModel):
      key: str; display_name: str; category: str; routing: str
      available: bool; enabled: bool; unavailable_reason: str | None
  class DataSourcesOut(BaseModel):
      sources: list[DataSourceOut]
  ```
  Update `GET /data-sources` to map the new service output. Update `SettingsOut`/`SettingsUpdateIn`: replace `financial_enabled`/`calendar_enabled` with `enabled_provider_ids: list[str]`; keep `web_search_enabled` + `instructions_id` + `template_id`. Wire the settings GET/PUT to the new service signature.
  - Route tests: `GET /data-sources` returns the dynamic list; `PUT /settings` round-trips `enabled_provider_ids`.

- [ ] Run the full EU server suite (`-k "eu_v2 or earnings_update_v2"`); fix fallout from the settings-shape change. ruff; commit: `feat(eu-v2): wire dispatcher into runs + per-connector data-sources API`.

---

## Task 9: frontend dynamic toggles (frontend)

**Files:**
- Modify: `frontend/src/api/earnings-update.ts`, `frontend/src/hooks/useEuDataSources.ts`
- Modify: `frontend/src/components/earnings-update/ReportSettingsModal.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `zh-TW.json`
- Test: `ReportSettingsModal.test.tsx`

- [ ] **Step 1** — API client: `DataSource { key; display_name; category; routing; available; enabled; unavailable_reason }` + `DataSourcesInfo { sources: DataSource[] }`; `EuSettings`: replace `financial_enabled`/`calendar_enabled` with `enabled_provider_ids: string[]`. `useEuDataSources` returns the `sources` list (keep model-change refetch).

- [ ] **Step 2** — Data Sources section in the modal: render one toggle per `source` (label + category chip; disabled + reason when `!available`). Toggling a registry source adds/removes its `key` in `draft.enabled_provider_ids`; the `model_web_search` source toggles `draft.web_search_enabled`. Remove the old 3 fixed slots + "also configured" footnote. Save persists `enabled_provider_ids` + `web_search_enabled`.

- [ ] **Step 3** — i18n: category labels (financial/news/social/web_search), reason codes, in en + zh-TW (parity).

- [ ] **Step 4** — tests: toggling a connector updates the persisted set; unavailable source is disabled with reason. `tsc --noEmit` clean; `npm run build` ok.

- [ ] ruff/format n/a (frontend); commit: `feat(eu-v2-fe): dynamic per-connector data-sources toggles`.

---

## Final verification

- [ ] Backend: `uv run pytest packages/core/tests/runtime/report_eu packages/server/tests -k "eu_v2 or report_eu or earnings_update_v2" -q` green; ruff clean.
- [ ] Frontend: `tsc --noEmit` + `npm run build` clean; EU FE tests pass.
- [ ] **Live smoke (verify skill):** host on the user's migrated DB (4 connectors), enable EODHD + NewsAPI, run an on-demand SNOW report; confirm via SSE/tool-call log that a `newsapi_ai__*` tool fired and its result was cited; confirm EODHD curated tools + calendar still work; toggle a connector off and confirm its tools disappear.

## Non-goals
- Routing EODHD via dispatcher (curated by decision); per-run overrides; deterministic `fetch_need`; connector install/validation changes.
