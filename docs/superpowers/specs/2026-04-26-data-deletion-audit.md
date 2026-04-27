# Connector redesign — pre-deletion audit

Generated: 2026-04-26.
Scope: every consumer of `openlia.data` / `data_providers` / legacy provider routes that the connector redesign cutover (Phase H + deferred E2) must address.

Method: ran the four greps in the task brief, then chased each match to its owner. Numbers in parens after each bucket header indicate file count.

## Bucket A — `openlia.data` package itself (deleted in H3) — 30 files

- packages/core/src/openlia/data/__init__.py
- packages/core/src/openlia/data/_http.py
- packages/core/src/openlia/data/base.py
- packages/core/src/openlia/data/errors.py
- packages/core/src/openlia/data/resolver.py
- packages/core/src/openlia/data/types.py
- packages/core/src/openlia/data/adapters/__init__.py
- packages/core/src/openlia/data/adapters/_stub.py
- packages/core/src/openlia/data/adapters/brave.py
- packages/core/src/openlia/data/adapters/eodhd.py
- packages/core/src/openlia/data/adapters/finnhub.py
- packages/core/src/openlia/data/adapters/firecrawl.py
- packages/core/src/openlia/data/adapters/fmp.py
- packages/core/src/openlia/data/adapters/mediastack.py
- packages/core/src/openlia/data/adapters/newsapi_ai.py
- packages/core/src/openlia/data/adapters/newsapi_org.py
- packages/core/src/openlia/data/adapters/reddit.py
- packages/core/src/openlia/data/adapters/serper.py
- packages/core/src/openlia/data/adapters/tavily.py
- packages/core/src/openlia/data/adapters/x.py
- packages/core/src/openlia/data/adapters/yfinance.py
- packages/core/src/openlia/data/catalog/__init__.py
- packages/core/src/openlia/data/dispatch/__init__.py
- packages/core/src/openlia/data/manifest/__init__.py
- packages/core/src/openlia/data/manifest/checker.py
- packages/core/src/openlia/data/manifest/loader.py
- packages/core/src/openlia/data/manifest/requirements.yaml
- packages/core/src/openlia/data/manifest/types.py
- packages/core/src/openlia/data/python_providers/__init__.py
- packages/core/src/openlia/data/review/__init__.py
- packages/core/src/openlia/data/sentiment/__init__.py

## Bucket B — server services to delete (H2) — 4 files

- packages/server/src/openlia_server/services/data_providers.py — 353 lines. Imports `openlia.data.adapters.ADAPTERS`, `openlia.data.manifest.types.RequirementsManifest`, `openlia.data.types.{ProviderCategory, ProviderEntry, ProviderMode}`. Used by: `routes/settings.py` (build_data_providers_router), `routes/setup.py` (`get_providers` handler), `services/runtime.py` (`list_providers_by_category` for web search resolver), `services/wizard_review.py`.
- packages/server/src/openlia_server/services/wizard_providers.py — 333 lines. Imports `openlia.data.adapters.ADAPTERS`, `openlia.data.adapters._stub._StubAdapter`, `openlia.data.types.{ProviderCategory, ProviderMode, ProviderEntry}`, `openlia.data.errors.DataNotAvailable`. Used by: `routes/setup.py` (post/patch/delete/test/confirm endpoints) and tests `test_e2e_smoke_matrix.py`, `test_setup_routes.py`.
- packages/server/src/openlia_server/services/wizard_review.py — 435 lines. Imports `openlia.data.catalog.{ProviderCatalog, build_catalog}`. Used by: `routes/setup.py` (`/review/run` endpoint).
- packages/server/src/openlia_server/services/runtime.py — DOES use `openlia.data.adapters.ADAPTERS` and `openlia.data.types.ProviderCategory`. Lines 14-15, 26, 58, 65. Builds the search-provider list for chat/batch/report runners. NOT a full delete — needs migration to read from connectors/secrets store. See Bucket E.

## Bucket C — server routes to remove (H2) — 2 files

- packages/server/src/openlia_server/routes/settings.py — `build_data_providers_router` (lines 81+, mounted at app.py:425 with prefix `/api/settings/data-providers`). Imports `openlia.data.types.{ProviderCategory, ProviderMode}` (line 12) and `db.models.config.DataProviderRequirementMapping` (line 18). All Pydantic models prefixed `_DataProvider*` and `_CreateDataProviderIn`/`_UpdateDataProviderIn` are scoped to this router and disappear with it.
- packages/server/src/openlia_server/routes/setup.py — these specific endpoints/sections under `/api/setup`:
  - `GET /providers` (lines 369-398) — calls `data_providers.list_providers`.
  - `POST /providers` (lines 401-422) — calls `wizard_providers.add_provider`.
  - `PATCH /providers/{provider_id}` (lines 425-437) — calls `wizard_providers.patch_provider`.
  - `DELETE /providers/{provider_id}` (lines 440-451) — calls `wizard_providers.delete_provider`.
  - `POST /providers/{provider_id}/test` (lines 454-464) — calls `wizard_providers.retest_provider`.
  - `POST /providers/confirm` (lines 467-487) — calls `wizard_providers.providers_complete`.
  - `POST /review/run` (lines 283-301) — calls `wizard_review.schedule_review`.
  - `GET /review/{review_id}` (lines 303-...) — uses `review_store_mod.DEFAULT_STORE`.
  - The `_StepProviderEntryIn` body model and `WIZARD_STEP_PROVIDER_*` constants used only by these endpoints.

## Bucket D — frontend client to delete (H2) — 4 files

- frontend/src/api/data_providers.ts — imported only by `components/settings/admin/DataProvidersAdminPanel.tsx` and its test.
- frontend/src/components/settings/admin/DataProvidersAdminPanel.tsx — admin panel for the legacy `/api/settings/data-providers/*` routes. Mounted at SettingsPage route `data-providers`.
- frontend/src/components/settings/admin/__tests__/DataProvidersAdminPanel.test.tsx — companion test.
- frontend/src/api/setup.ts — `listProviders`, `addProvider`, `patchProvider`, `deleteProvider`, `retestProvider`, `runReview`, `pollReview`, `confirmProviders` (lines 94-124). Confirmed: NO callers in frontend src; ProvidersStep already imports from `api/connectors`. Safe to delete these exports (not the whole file — `getStatus`, `setMode`, `setIdentity`, `setAdmin`, `saveModels`, `testModel`, `setAccessControl`, `finish`, `takeover` are still in use).
- frontend/src/pages/SettingsPage.tsx — line 11 import + line 40 `<Route path="data-providers" .../>` need removal.
- frontend/src/pages/SettingsPage.test.tsx and frontend/src/pages/__tests__/SettingsPage.test.tsx — both `vi.mock` the panel; mocks need cleanup.

## Bucket E — runtime business code calling openlia.data (E2 work in H2) — 3 files

For each: path | symbol | what it imports | replacement strategy

- packages/server/src/openlia_server/services/runtime.py | `_resolve_search_provider` (web-search resolver builder used by `build_chat_runner`, `build_batch_runner`, `build_report_runner`) | `openlia.data.adapters.ADAPTERS`, `openlia.data.types.ProviderCategory`, `services.data_providers.list_providers_by_category` | replace with `Dispatcher.tools_for_department` lookup of search-category connectors (Plan-3 / E2). This is the production wiring path that must be migrated before runtime tools can be served.
- packages/server/src/openlia_server/app.py | factory wiring (lines 78, 425) | `routes.settings.build_data_providers_router` | drop the import + `app.include_router(...)` call once Bucket C is gone.
- packages/core/src/openlia/macro_research/assembler.py | `DashboardAssembler` ctor takes `data_provider: _DataProvider` | NO import of `openlia.data` — `_DataProvider` is a local `Protocol` defined in this file. Real instances are wired in app.py via `app.state.mr_data_provider` (legacy adapter today). Migration: provide an MR-flavoured implementation backed by the connector dispatcher; the Protocol stays.
- packages/server/src/openlia_server/services/mr_assessment.py | `MRAssessmentBuilderImpl(data_provider=…)` | local `_DataProvider` Protocol, no `openlia.data` import. Same deal — replace whatever app.state injects with a dispatcher-backed adapter.
- packages/server/src/openlia_server/services/mr_runner.py | `MacroResearchRunner.__init__(data_provider=…)` | local `_DataProvider` Protocol, no `openlia.data` import. Same.
- packages/server/src/openlia_server/services/rs_runner.py | `RetailSentimentRunner.__init__(data_provider=…)` | local `_DataProvider` Protocol, no `openlia.data` import. Live wiring uses `app.state.rs_data_provider`. Same migration shape.

The four other runners (`equity_research_runner.py`, `eu_runner.py`, `mb_runner.py`, `pt_runner.py`, `secretary_chat_runner.py`) do NOT import `openlia.data` directly nor declare a `_DataProvider` Protocol — they expect tool dispatch through the LLM runtime layer (Bucket F).

## Bucket F — LLM runtime tool assembly (E2 plug point) — 1 file

- packages/core/src/openlia/llm/runtime/tools.py | `class ToolDispatcher` and `Protocol DataProviderDispatcher` (lines 62-83, 139+). `ToolDispatcher.__init__(*, data_dispatcher: DataProviderDispatcher, web_search: WebSearchResolution)`. `ToolDispatcher.build(department_id, *, has_web_search, extra_tools=())` is the call-time tool assembly that emits the `tools=[...]` list for `messages.create()`. The new `openlia.connectors.dispatch.Dispatcher` must implement this Protocol (or be wrapped in an adapter). This is the single plug-point for the E2 cutover.
- packages/core/src/openlia/llm/runtime/__init__.py | re-exports `DataProviderDispatcher` and `ToolDispatcher` (lines 38, 64). No code change needed; just keep the public surface stable.
- packages/core/tests/test_llm/test_runtime/_fakes.py (line 119) | `class FakeRequirementDispatcher` implements the Protocol — used by all runtime tests. Stays as the test double.

## Bucket G — tests to update or delete (H2) — 25+ files

Core (delete entirely with the package):
- packages/core/tests/test_data/__init__.py
- packages/core/tests/test_data/test_base.py
- packages/core/tests/test_data/test_catalog.py
- packages/core/tests/test_data/test_errors.py
- packages/core/tests/test_data/test_manifest_checker.py
- packages/core/tests/test_data/test_manifest_loader.py
- packages/core/tests/test_data/test_public_surface.py
- packages/core/tests/test_data/test_resolver.py
- packages/core/tests/test_data/test_types.py
- packages/core/tests/test_data/test_adapters/__init__.py
- packages/core/tests/test_data/test_adapters/test_brave.py
- packages/core/tests/test_data/test_adapters/test_eodhd.py
- packages/core/tests/test_data/test_adapters/test_finnhub.py
- packages/core/tests/test_data/test_adapters/test_firecrawl.py
- packages/core/tests/test_data/test_adapters/test_fmp.py
- packages/core/tests/test_data/test_adapters/test_mediastack.py
- packages/core/tests/test_data/test_adapters/test_newsapi_ai.py
- packages/core/tests/test_data/test_adapters/test_newsapi_org.py
- packages/core/tests/test_data/test_adapters/test_reddit.py
- packages/core/tests/test_data/test_adapters/test_serper.py
- packages/core/tests/test_data/test_adapters/test_tavily.py
- packages/core/tests/test_data/test_adapters/test_x.py
- packages/core/tests/test_data/test_adapters/test_yfinance.py

Server (delete with their target services/routes):
- packages/server/tests/test_services/test_data_providers.py
- packages/server/tests/test_services/test_ai_review.py
- packages/server/tests/test_routes/test_data_providers_routes.py
- packages/server/tests/test_routes/test_data_providers_integration.py

Server (touch-up — only the legacy provider/review test cases need updating, file stays):
- packages/server/tests/test_routes/test_setup_routes.py — drop the `provider`/`review` test cases (lines 547+, 604+).
- packages/server/tests/test_routes/test_must_change_password_gate.py — drop `test_settings_data_providers_list_blocked` (line 101).
- packages/server/tests/test_e2e_smoke_matrix.py — drop `wizard_providers._run_health_check` patches (line 115+).
- packages/server/tests/test_cli/test_cli_wizard.py — `completed_steps` lists still mention `"data_providers"` (lines 15/45/63); update to the new step name (`"providers"` per `services/wizard.STEP_ORDER_*`) or drop entirely.
- packages/server/tests/test_cli/test_cli_secrets.py and test_cli_crypto_rotation.py — touch `DataProvider` rows; update once `DataProvider` model is dropped (Bucket H).
- packages/server/tests/test_db/test_migrations.py — asserts `"data_providers"` and `"data_provider_requirement_mapping"` exist in baseline (line 25-26) and notes the connector replacement (line 69). Update to assert NOT-EXISTS in the new head revision.
- packages/server/tests/test_db/test_models_config.py — `test_data_provider_requirement_mapping_composite_pk` (line 77) needs deletion.

Frontend:
- frontend/src/components/settings/admin/__tests__/DataProvidersAdminPanel.test.tsx — delete with the panel.
- frontend/src/api/setup.test.ts — strip the legacy provider/review function tests.
- frontend/src/pages/SettingsPage.test.tsx and frontend/src/pages/__tests__/SettingsPage.test.tsx — drop the panel mock/route case.

## Bucket H — DB migration (H4)

New revision must:
- Drop FK + table `data_provider_requirement_mapping`.
- Drop table `data_providers` (3 indexes + 2 check constraints `ck_data_providers_category` / `ck_data_providers_mode` go with it).
- Drop the corresponding ORM classes from `packages/server/src/openlia_server/db/models/config.py`: `DataProvider` (line 107) and `DataProviderRequirementMapping` (line 145), plus the docstring at line 2.
- Existing migrations to inspect (do NOT modify; they remain history): `2026-04-18-1609_baseline.py`, `2026-04-21-0001_reshape_wizard_state.py`, `2026-04-24-0300_spec_check_constraints.py`, `2026-04-24-0400_data_providers_category_mode_mcp.py`. The `2026-04-26-1700_connectors.py` migration explicitly notes the cutover happens later (line 6 comment).
- CLI references in `packages/server/src/openlia_server/cli.py`: lines 763-786 (wizard reset --purge), 805-808 (secrets app imports), 894-898 (crypto rotation loop) all reference `DataProvider`/`DataProviderRequirementMapping`. Each must be removed or rewritten to operate on `Connector` rows.

## Bucket I — docs to retire (H5)

- planning/specs/systems/data-provider-design.md — primary retirement target.
- planning/specs/ — sweep for stale references to `data_providers`, the old wizard step name, and the AI-review step (any per-page spec that mentions provider auto-mapping).
- README/CLAUDE.md — quick scan for surfaces mentioning the legacy package.

## Open questions / surprises

1. **`services/runtime.py` is the highest-risk file in Bucket B**. The brief implies all three legacy services delete cleanly, but `runtime.py` is the wiring used by every department (chat / batch / report runners) and is NOT in the delete list — it has to be MIGRATED from `data_providers.list_providers_by_category` + `ADAPTERS` to a connector-backed search resolver before H2 can land. This blocks H2 unless the dispatcher exposes equivalent "list search-category connectors with resolved API keys" semantics. Verify `openlia.connectors.dispatch.Dispatcher` (or `services/connectors_service.py`) has a method that returns the same shape `runtime._resolve_search_provider` consumes today.

2. **CLI entanglement**. `packages/server/src/openlia_server/cli.py` references `DataProvider` in three different sub-apps (`wizard reset --purge`, `secrets`, `secrets rotate-key`). The crypto-rotation loop iterates `(LLMProvider, DataProvider, WebSearchProvider)` — dropping `DataProvider` mid-flight would orphan any encrypted keys still stored against the old table. Order-of-operations: Bucket H migration must run AFTER any production install has been migrated off legacy adapters, and the CLI commands need parallel updates to swap `DataProvider` for `Connector` (or whatever encrypted-secret table the new design uses).

3. **`openlia.data.review` and `openlia.data.sentiment` are marker-only packages today** (empty `__init__.py`). The wizard_review service comment at `data_providers.py:300` confirms `data.review` is just a placeholder. Nothing depends on them functionally — pure deletion.

4. **`openlia.data.dispatch` is a marker-only package**. Confirmed empty `__init__.py`. The actual dispatcher logic landed in `openlia.connectors.dispatch`. Safe to delete with the rest.

5. **Macro Research and Retail Sentiment runners use a LOCAL `_DataProvider` Protocol**, not the legacy `openlia.data` adapter classes. The "deferred E2 work" for these two departments is NOT a port of imports — it's swapping the concrete implementation passed via `app.state.mr_data_provider` / `app.state.rs_data_provider`. Cosmetic for the audit, important for the cleanup PR description.

6. **`api/setup.ts` retains 9 working functions** (status/mode/identity/admin/models/test-model/access-control/finish/takeover). The file is NOT deletable — only the 7 provider/review exports inside it are. The brief said "delete `frontend/src/api/data_providers.ts`" which is correct, but `api/setup.ts` needs surgical edits, not deletion.

7. **`completed_steps` step name drift**. Test fixtures at `test_cli_wizard.py` use `"data_providers"` as a step name; the live `services/wizard.py` `STEP_ORDER_*` use `"providers"`. Pre-existing inconsistency — flagged so cleanup PRs don't accidentally ship a regression.

8. **No new-style `openlia.connectors` consumers in runners yet**. Only `packages/core/src/openlia/departments/{__init__.py, requirements_loader.py}` and the connector tests/services use it. Department runners still go through the legacy path. The H2 migration is therefore non-trivial; it's the first time business code crosses the new dispatcher.

## Bucket F.1 — ToolDispatcher consumer migration map (H3.1)

Generated: 2026-04-27.
Scope: every consumer of `ToolDispatcher` and `DataProviderDispatcher` from
`packages/core/src/openlia/llm/runtime/tools.py`.

Method: `grep -rln "ToolDispatcher\|DataProviderDispatcher" packages` then
walked every match. ToolDispatcher itself is defined at
`packages/core/src/openlia/llm/runtime/tools.py:139`; the
`DataProviderDispatcher` Protocol is at the same file, line 62. The new
target API lives at `packages/core/src/openlia/connectors/dispatch.py`
(`Dispatcher.tools_for_department(department_id)` synchronous,
`Dispatcher.dispatch_tool_use(prefixed_name, arguments)` async).

### Production consumers (migrate in H3.3)

For each: file | function/class | injection style | call shape | migration notes

- packages/core/src/openlia/llm/runtime/chat.py | `ChatRunner.__init__` (line 60) + `ChatRunner.run` (line 77) | `__init__` parameter `tools: ToolDispatcher` (line 64); stored as `self._tools` (line 71) | `await self._tools.build(department_id, has_web_search=True, extra_tools=extra_tool_specs)` (lines 112-114, repeated at 183-185) and `await self._tools.dispatch_many(department_id=..., calls=response.tool_calls, extra_tool_names=extra_tool_names, max_expansions=None)` (lines 162-169) | Replace `tools: ToolDispatcher` with `dispatcher: Dispatcher`; replace `.build(...)` with synchronous `dispatcher.tools_for_department(department_id)` plus an explicit web_search inclusion step (H3.5); replace each per-call branch in `dispatch_many` with `await dispatcher.dispatch_tool_use(call.name, call.arguments)` and adapt `ToolCallResult` shaping locally. `extra_tools` (Secretary's `suggest_redirect`) needs an equivalent path: today it's an echo handled inside `ToolDispatcher._dispatch_structured_echo`; either keep the echo logic in `ChatRunner` or have the Dispatcher accept ad-hoc per-department tool definitions. `find_more_data` semantics disappear with the dispatcher swap — confirm whether Secretary still needs unbounded expansion or whether the new connector model removes the concept.
- packages/core/src/openlia/llm/runtime/report.py | `ReportRunner.__init__` (line 103) + `ReportRunner.run` (line 124) | `__init__` parameter `tools: ToolDispatcher` (line 107); stored as `self._tools` (line 115) | `tools = await self._tools.build(department_id, has_web_search=True)` (line 176, repeated at 238); `await self._tools.dispatch_many(department_id=department_id, calls=response.tool_calls, max_expansions=max_expansions)` (lines 219-223) | Same swap as ChatRunner: `Dispatcher.tools_for_department` (sync) + per-call `dispatch_tool_use`. `max_expansions` budget is currently passed all the way down to `_dispatch_find_more_data`; the new dispatcher has no equivalent. Decision needed: drop the budget concept or move it up to `ReportRunner` itself if reports still expand tool sets across turns. `has_web_search=True` is hard-coded — same H3.5 work as ChatRunner.
- packages/server/src/openlia_server/services/runtime.py | `_build_chat_runner_with_registry` (line 79) | constructs `ToolDispatcher(data_dispatcher=_EmptyDataDispatcher(), web_search=web_search)` (lines 85-88) and passes it to `ChatRunner(... tools=tools, ...)` (line 100) | constructor wiring | Replace with constructing a `Dispatcher` from the connector registry (see H3.3 prerequisites). `_EmptyDataDispatcher` (lines 30-44) — a placeholder `DataProviderDispatcher` impl — is deleted with H3.4; the new dispatcher is hydrated from the connector registry instead.
- packages/server/src/openlia_server/services/runtime.py | `_build_report_runner_with_registry` (line 152) | constructs `ToolDispatcher(data_dispatcher=_EmptyDataDispatcher(), web_search=web_search)` (lines 158-161) and passes it to `ReportRunner(... tools=tools, ...)` (line 173) | constructor wiring | Same as the chat case. Both Refreshing*Runner classes (`RefreshingChatRunner` line 107, `RefreshingReportRunner` line 180) call these builders per `.run()`, so the swap propagates with no signature changes upstream.

### Production providers (wiring sites that die in H3.4)

- packages/server/src/openlia_server/services/runtime.py:30-44 — `_EmptyDataDispatcher` placeholder class (the only production `DataProviderDispatcher` implementation). Deletes with the protocol.
- packages/server/src/openlia_server/services/runtime.py:85-88 — `ToolDispatcher(...)` construction inside `_build_chat_runner_with_registry`. Replaced by Dispatcher hydration.
- packages/server/src/openlia_server/services/runtime.py:158-161 — `ToolDispatcher(...)` construction inside `_build_report_runner_with_registry`. Replaced by Dispatcher hydration.
- packages/server/src/openlia_server/app.py:559-566 — `build_chat_runner` / `build_report_runner` factory wiring. No code change needed here in H3.3 because the builder signatures stay the same; the implementations behind them change. Listed here for awareness only.
- packages/core/src/openlia/llm/runtime/__init__.py:37-41 + lines 64, 75-76 — public re-exports of `DataProviderDispatcher`, `ToolCallResult`, `ToolDispatcher`. Re-exports vanish with H3.4. `ToolCallResult` (line 86 in tools.py) currently double-duties as the dispatch_many output shape; whoever picks H3.3 needs to either keep it as a tiny local dataclass in `chat.py` / `report.py` or replace it with whatever the new dispatcher returns.
- packages/core/src/openlia/llm/runtime/web_search.py:8 — docstring reference to `ToolDispatcher.dispatch()`. Cosmetic; updates with H3.5 web-search rework.

### Tests + fakes (delete with H3.4)

- packages/core/tests/test_llm/test_runtime/_fakes.py:117-138 — `FakeDataDispatcher` (the `DataProviderDispatcher` Protocol fake). The task brief calls it `FakeRequirementDispatcher`; it's actually named `FakeDataDispatcher` in the file. Deletes with the Protocol.
- packages/core/tests/test_llm/test_runtime/test_tools.py — entire file (340 lines). Constructs `ToolDispatcher` directly across 14 tests (lines 7, 40, 54, 66, 79, 95, 121, 139, 156, 176, 212, 233, 271, 311, 329). No survivors in this file once `ToolDispatcher` is gone.
- packages/core/tests/test_llm/test_runtime/test_chat.py — 9 sites (line 22 import; constructions at 107, 161, 188, 222, 252, 309, 357, 410, 464). The whole file is structured around `ChatRunner(tools=ToolDispatcher(...), ...)`; tests have to be rewritten against the new `ChatRunner(dispatcher=Dispatcher(...), ...)` signature. Not a delete — a rewrite belonging to H3.3 along with the runner change.
- packages/core/tests/test_llm/test_runtime/test_report.py — 13 sites (line 24 import; constructions at 132, 166, 224, 280, 340, 367, 399, 452, 501, 548, 598, 636, 720). Same story as test_chat.py: rewrite, not delete.
- packages/core/tests/test_llm/test_runtime/test_cancel_streaming_grace.py — line 28 import; lines 117 and 245 build `ChatRunner(tools=ToolDispatcher(...))`; line 145 defines `_SlowToolDispatcher(ToolDispatcher)` subclass to inject a tool-dispatch slowdown for grace-period tests; line 192 instantiates the subclass. Rewrite required: the slow-dispatch hook needs to live on the new Dispatcher (or on a fake transport injected into one of its connectors).

### Shape mismatches and migration notes

- **`has_web_search` flag**: today, both ChatRunner (line 113-114, 184-185) and ReportRunner (line 176, 238) pass `has_web_search=True` unconditionally. The new `Dispatcher.tools_for_department` does not append a `web_search` schema; it only emits connector-allowlisted tools. H3.5 work: pull web-search tool injection out of the dispatcher entirely (so the `WebSearchResolution` resolver decides whether to append `_WEB_SEARCH_SCHEMA` to the tool list returned by `tools_for_department`). Every caller currently writing `has_web_search=True` needs that surrounding code path.
- **`extra_tools` parameter**: only ChatRunner uses it (lines 113, 184), pulling `dept.extra_tools` from `get_department(department_id)`. The matching dispatch path is `_dispatch_structured_echo` (tools.py:228-240). The new `Dispatcher` has no concept of department-provided structured tools; the echo behavior has to move into ChatRunner itself (or ChatRunner has to keep a small static list of "echo these names back as `structured`" alongside the dispatcher list). ReportRunner does NOT use `extra_tools` — only ChatRunner.
- **`find_more_data` and `max_expansions`**: ToolDispatcher tracks per-department expansion budget (`_expansion_count` in tools.py:148-152) and routes `find_more_data` calls through `DataProviderDispatcher.find_more_data` (tools.py:261-309). ReportRunner threads `max_expansions` through (line 222); ChatRunner pins it to `None` (line 167) for unlimited Secretary expansions. The new Dispatcher has no `find_more_data` concept at all — the connector model is "all available tools are listed up front." Decision needed before H3.3: either (a) drop `find_more_data` entirely (acceptable if connectors fully replace the legacy mapping system), or (b) keep `find_more_data` as a department-level tool with its own implementation outside the Dispatcher.
- **tool_use callback path**: today the runner calls `await self._tools.dispatch_many(department_id=..., calls=[...], extra_tool_names=..., max_expansions=...)` and gets back `list[ToolCallResult]` with `call_id`/`ok`/`summary`/`payload`/`structured`. With the new API, each call site loops over `response.tool_calls` and invokes `await dispatcher.dispatch_tool_use(call.name, call.arguments)` per call. The new return is raw connector output — there is no `summary`, no `ok` flag, no `structured` echo. The runner itself has to (i) catch `DispatchError` for the `ok=False` path, (ii) build a one-line `summary` for SSE (`ChatToolCallResult` and `ReportToolCall` both consume `summary`), and (iii) decide whether to keep the `_normalize_payload` JSON shaping (tools.py:103-119) — currently the LLM sees the truncated payload, not the raw connector response. If we drop normalization the LLM context can balloon; recommend keeping a normalization helper local to chat.py / report.py. Parallelism: today's `asyncio.gather` is implicit in `dispatch_many` (tools.py:209-226); the runner has to wrap its own `gather` after the swap.

### Open questions

1. **`find_more_data` future**. Connectors enumerate all available tools at allowlist time. Confirm with product whether the "search the catalog mid-turn for an unmapped endpoint" UX still exists post-cutover; if not, both runners and Secretary's prompt change.
2. **`extra_tools` / `suggest_redirect`**. Does the connector model express department-level meta tools (Secretary's redirect card) at all, or do those remain a runner-local concept that ChatRunner appends to the dispatcher's list and handles via a local echo? H3.3 needs the answer to know whether Dispatcher needs an `extra_tools` injection point.
3. **`ToolCallResult` lifetime**. The dataclass is currently the runtime's contract for SSE event payloads. When `ToolDispatcher` deletes, the dataclass either moves into the runtime (chat.py / report.py) or gets replaced by a new shape sourced from the dispatcher. H3.3 needs to pick one.
4. **Web-search tool inclusion (H3.5 preview)**. Today `web_search` is appended inside `ToolDispatcher.build`. After the swap, the `WebSearchResolution` adapter has to be invoked separately and its `_WEB_SEARCH_SCHEMA` appended manually to the dispatcher's tool list. Confirm where this lives — runner-local helper, or a new dispatcher mixin?
