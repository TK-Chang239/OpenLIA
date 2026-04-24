# Phase 3 — Data Provider Adapter System fix plan (→ 100%)

**Current shipped:** ~95% vs. plan / ~55% vs. spec.
**Plan:** [planning/implementation-plans/2026-04-16-phase-3-data-provider-adapter-system.md](../../implementation-plans/2026-04-16-phase-3-data-provider-adapter-system.md)
**Spec:** [planning/specs/systems/data-provider-design.md](../../specs/systems/data-provider-design.md)
**Dominant root cause(s):** SPEC_DRIFT (catalog / AI-review / dispatch / python_providers / sentiment layers all deferred by the plan) + IMPLEMENTER (category column never persisted; `auto_map` iterates every capable provider instead of the highest-priority one; MCP mode accepted at request level but dropped on the way to the DB; adapter registry shipped EODHD only and never carried the four-capability promise).

**Gap summary:** Plan-scoped work is largely complete (ABC, errors, types, manifest loader + checker, EODHD adapter, resolver, `/settings/data-providers/*` CRUD including `auto-map`, `test-connection` and per-requirement mappings, Task-15 end-to-end test). Against the plan the only straggler is the advertised `company_fundamentals` capability on the EODHD adapter (declared in manifest as advanced, missing from `EODHDAdapter.capabilities`, and the integration test explicitly asserts it remains unmet). Against the spec, the catalog / review / dispatch / python_providers / sentiment subsystems are entirely absent, FMP/Finnhub/yfinance/news adapters are not shipped, the `search` provider category is missing from `ProviderCategory`, and several plan-level correctness defects escaped review: `DataProvider` has no `category` column yet the service layer accepts one and silently discards it; `mcp_url` is accepted in the create body but never persisted; `auto_map` maps every capable provider (not just the highest priority) and skips the department-level de-dup the spec mandates; `_row_to_entry` falls back to `FINANCIAL` on unknown kinds. Tests are structurally present but leave the category-drop, mcp_url-drop, and priority-tie regressions uncovered.

## P0 — Live failures

1. **P0-3-01 — `DataProvider.category` is accepted by the API but never persisted (breaks multi-category resolution).**
   - Bug: `routes/settings.py::_CreateDataProviderIn.category` is required (`Literal["financial","news","social_media"]`), but `services/data_providers.create_provider` executes `del category` after validation and the `DataProvider` SQLAlchemy model at `db/models/config.py:89-107` has no `category` column. On read, `_row_to_entry` falls back to `adapter_cls.category if adapter_cls is not None else ProviderCategory.FINANCIAL`, so any provider whose `kind` is not in `ADAPTERS` silently claims to be financial. Startup validation ("at least one financial, at least one news") cannot be expressed.
   - Files: `packages/server/src/openlia_server/db/models/config.py:89-107` (add `category` column + Alembic migration), `packages/server/src/openlia_server/services/data_providers.py:64-167` (stop discarding `category` and `mode`; persist both; source the value in `_row_to_entry` from the row, not from the adapter class).
   - Plan ref: Task 10, Task 12.
   - Spec ref: `data-provider-design.md` §"Provider Entry" (category is a first-class field of every `ProviderEntry`).
   - Acceptance: new `test_create_provider_persists_category` and `test_row_to_entry_uses_db_category_for_unknown_kinds` (see "Missing tests"); Alembic migration round-trips on SQLite + Postgres; `services/data_providers.list_providers_by_category(...)` added and used by the startup validator.

2. **P0-3-02 — MCP mode is un-wired end-to-end.**
   - Bug: `_CreateDataProviderIn.mcp_url` is accepted by the route body, but `create_provider` does not forward it, the `DataProvider` model has no `mcp_url` / `mcp_auth_header` columns, and `_row_to_entry` hard-codes `mcp_url=None` and always returns `ProviderMode.API_KEY if row.base_url else ProviderMode.MCP` (so an MCP provider created without `base_url` deserializes with `mcp_url=None`, immediately failing `ProviderEntry._transport_requirements`).
   - Files: `packages/server/src/openlia_server/db/models/config.py:89-107` (add `mcp_url`, `mcp_auth_header`), `packages/server/src/openlia_server/services/data_providers.py:51-167` (persist + load both), `packages/server/src/openlia_server/routes/settings.py:22-65` (reflect in `_UpdateDataProviderIn` + `_DataProviderOut`).
   - Plan ref: Task 10 Step 6 "mode persistence".
   - Spec ref: `data-provider-design.md` §"Dual Transport".
   - Acceptance: new `test_create_mcp_provider_roundtrips` — POST with `mode=mcp, mcp_url=…`, GET returns `mode=mcp` and `mcp_url`; `load_provider_entry` yields a `ProviderEntry` whose `mode is ProviderMode.MCP` and `mcp_url` is populated.

3. **P0-3-03 — `auto_map` maps every capable provider per requirement instead of the highest-priority one.**
   - Bug: `services/data_providers.py:278-308` iterates `capable` providers and calls `set_requirement_mapping` for every one of them, not just the priority winner. The spec explicitly says "the first provider that can satisfy a requirement wins — assign that endpoint" and `resolve_provider_for_capability` at `data/resolver.py:39-59` assumes a single winner. Result: after two FINANCIAL providers are configured, `mappings` contains both rows per requirement and `list_entries_for_capability` returns both, silently changing priority-ordering semantics when Plan 5's dispatch lands.
   - Files: `packages/server/src/openlia_server/services/data_providers.py:254-310` (stop at first capable provider per requirement; also dedup `seen_req_types` across departments so only one unmet entry is produced).
   - Plan ref: Task 11 Step 3 "first-match-wins semantic".
   - Spec ref: `data-provider-design.md` §"AI Review" flow 3(a)(iii).
   - Acceptance: new `test_auto_map_first_match_wins` with two EODHD-clone providers at priorities 10 and 50 — only the priority-10 mapping rows should land; update `test_auto_map_returns_summary` to assert `len({(m.requirement_type, m.provider_id) for m in body["mapped"]}) == len(body["mapped"])`.

4. **P0-3-04 — EODHD `company_fundamentals` capability deferred but manifest declares it.**
   - Bug: `requirements.yaml:28-30` declares `company_fundamentals` as an `advanced` requirement for `equity_research`; `EODHDAdapter.capabilities` at `adapters/eodhd.py:34-41` omits it; the `fetch` router has no branch for it. `auto_map` therefore reports it as permanently unmet even though the adapter already hits `/fundamentals/{ticker}.US` for `company_profile` and could return the statements block from the same response.
   - Files: `packages/core/src/openlia/data/adapters/eodhd.py:34-97` (add capability + route to `/fundamentals/{ticker}.US` selecting `Financials` block), `packages/core/tests/test_data/test_adapters/test_eodhd.py` (new respx test), `packages/server/tests/test_routes/test_data_providers_routes.py:217-219` (drop `company_fundamentals` from the expected-unmet set), `packages/server/tests/test_services/test_data_providers.py:206` (same).
   - Plan ref: Task 8 "EODHD adapter (4 capabilities)" — originally deferred to a follow-up.
   - Spec ref: `data-provider-design.md` §"Mapping Output" (lists `company_fundamentals` as a stock-Equity-Research requirement).
   - Acceptance: `test_fetch_company_fundamentals_extracts_financials_block` green against a respx fixture; `test_auto_map_returns_summary` no longer lists it as unmet when an EODHD provider is configured.

## P1 — Silent correctness gaps

5. **P1-3-05 — `ProviderCategory` missing `SEARCH` and adapter registry missing news/social adapters.**
   - Bug: `data/types.py:15-18` enumerates only `FINANCIAL / NEWS / SOCIAL_MEDIA`; spec lists a fourth category `search`. `adapters/__init__.py:11-13` ships only `EODHDAdapter`, so **every** news/social-media/search provider fails `_require_known_kind` in `create_provider`. The startup-validation rule "at least one news provider" cannot ever be satisfied.
   - Files: `packages/core/src/openlia/data/types.py:15-18` (add `SEARCH`), `packages/core/src/openlia/data/adapters/__init__.py` (stub adapters for `fmp`, `finnhub`, `newsapi_ai`, `newsapi_org`, `mediastack` raising `DataNotAvailable` from `fetch` until implemented, so `_require_known_kind` passes and `auto-map` still produces unmet entries), `packages/server/src/openlia_server/routes/settings.py:26` (extend `Literal` to include `search`).
   - Plan ref: Task 3 + Task 8 (scope called out FMP/Finnhub/yfinance as deferred but the registry keys must still register or CRUD for them is impossible).
   - Spec ref: `data-provider-design.md` §"Provider Categories", §"Search category specifics".
   - Acceptance: `test_create_provider_accepts_fmp_newsapi_search_kinds`; `test_provider_category_enum_includes_search`.

6. **P1-3-06 — Error mapping for 401/403 / timeouts / malformed responses is under-specified.**
   - Bug: `EODHDAdapter._get_json` maps 404 → `DataNotAvailable`, 429 → `RateLimitError`, any other non-200 → `DataSourceError(status_code=…)`. It does NOT distinguish 401/403 (auth) from 5xx (transient) — both degrade to `DataSourceError` with no `auth_failed` flag. Connection-level errors (`httpx.ConnectTimeout`, `httpx.ReadTimeout`) are wrapped in generic `DataSourceError` losing classification needed by Plan 5's retry/backoff. No `Retry-After` `http-date` handling (`_parse_retry_after` only accepts integer seconds).
   - Files: `packages/core/src/openlia/data/errors.py` (add `AuthenticationError(DataProviderError)`; extend `RateLimitError` / `DataSourceError` with `is_transient: bool`), `packages/core/src/openlia/data/adapters/eodhd.py:111-153` (classify 401/403 → `AuthenticationError`, 5xx → `DataSourceError(is_transient=True)`, `httpx.TimeoutException` → `DataSourceError(is_transient=True)`; upgrade `_parse_retry_after` to accept RFC-1123 dates via `email.utils.parsedate_to_datetime`).
   - Plan ref: Task 2 "typed errors".
   - Spec ref: `data-provider-design.md` §"Error Handling" table (three error classes; spec includes auth failures in `DataSourceError` but separates on handling intent).
   - Acceptance: `test_eodhd_401_raises_authentication_error`, `test_eodhd_5xx_marks_transient`, `test_eodhd_http_date_retry_after`.

7. **P1-3-07 — No retry/backoff wrapper around adapter HTTP calls.**
   - Bug: Spec says `RateLimitError` should be retried with exponential backoff and converted to `DataNotAvailable` when exhausted. No retry wrapper exists; the EODHD adapter raises the error straight up to the caller. Plan 3 explicitly defers dispatch, but the adapter itself is the only layer that has the `Retry-After` header in scope, so retry has to live here (or in a shared `_http_client` helper).
   - Files: new `packages/core/src/openlia/data/_http.py` with `async_request_with_retry(client, request, *, max_attempts=3, base_backoff=0.5)` that respects `Retry-After` when set and applies capped exponential jitter otherwise; refactor `EODHDAdapter._get_json` to use it.
   - Plan ref: Not in plan — plan defers dispatch. Spec adds this requirement.
   - Spec ref: `data-provider-design.md` §"Error Handling" handling column for `RateLimitError`.
   - Acceptance: `test_rate_limit_retries_and_succeeds_on_third_attempt`; `test_rate_limit_exhausted_raises_rate_limit_error`.

8. **P1-3-08 — Connection-test endpoint returns `{"ok": False}` for unknown `kind` instead of 400.**
   - Bug: `routes/settings.py:258-264`: when the loaded `ProviderEntry.kind` has no entry in `ADAPTERS`, the route returns `200 {"ok": False}`. This masks "we don't even ship this adapter" as a transient connection failure. Unknown-kind should be 400 / 501 so the admin UI can distinguish "key is bad" from "openlia can't talk to this at all".
   - Files: `packages/server/src/openlia_server/routes/settings.py:248-264`.
   - Plan ref: Task 14 Step 5.
   - Spec ref: `data-provider-design.md` §"Dual Transport".
   - Acceptance: `test_test_connection_returns_501_for_unknown_kind`.

9. **P1-3-09 — `create_provider` does not require `mcp_url` when `mode=mcp`.**
   - Bug: `services/data_providers.py:65-68` only validates `api_key` mode. POSTing `mode=mcp` without `mcp_url` sinks into `DataProvider` with `base_url=None, mcp_url=None` (and once P0-3-02 is fixed, re-reading the row into `ProviderEntry` fails validation only at read time, not create time).
   - Files: `packages/server/src/openlia_server/services/data_providers.py:51-88`.
   - Plan ref: Task 10 Step 6 "mode persistence".
   - Spec ref: `data-provider-design.md` §"Dual Transport".
   - Acceptance: `test_create_mcp_provider_without_mcp_url_returns_400`.

10. **P1-3-10 — `load_entries_for_capability` respects `DataProviderRequirementMapping.priority` but not `DataProvider.is_enabled`.**
    - Bug: `services/data_providers.py:190-205` joins + orders by priority but does not `WHERE DataProvider.is_enabled = True`. A disabled provider with a priority-10 row wins over an enabled priority-20 sibling. `resolve_provider_for_capability` filters on `is_enabled` downstream, so the behavior is "correct by accident" only because Plan 5 hasn't landed yet.
    - Files: `packages/server/src/openlia_server/services/data_providers.py:190-205`.
    - Plan ref: Task 11.
    - Spec ref: `data-provider-design.md` §"Configuration" (provider lists ordered by priority — disabled providers should drop out).
    - Acceptance: `test_load_entries_for_capability_skips_disabled_provider`.

11. **P1-3-11 — `auto_map` `_DEFAULT_PRIORITY_KEY` shortcut is tied to `extra_config` and is never exposed in the API.**
    - Bug: `services/data_providers.py:208-221` stores default priority under `extra_config["default_priority"]`, but no route sets it and no part of the service reads it when creating a provider. In practice every provider is ordered at priority 100 and auto-map first-write-wins resolves purely by insertion order. The spec expects a first-class admin-set priority per `data_provider_requirement_mapping` row (which already exists) or per provider.
    - Files: `packages/server/src/openlia_server/routes/settings.py` (add `PATCH /{provider_id}/priority`), `packages/server/src/openlia_server/services/data_providers.py:208-221` (rename helper to `set_provider_default_priority` already exists but no route; add validation for negative / non-int).
    - Plan ref: Task 11 Step 4.
    - Spec ref: `data-provider-design.md` §"Configuration" (admin-set priority).
    - Acceptance: `test_patch_provider_priority_reorders_auto_map`.

12. **P1-3-12 — `openlia.data.__init__` does not re-export the adapter registry or manifest helpers.**
    - Bug: Consumers (Plan 5 dispatch, Plan 10 wizard, Plan 13+ departments) currently have to `from openlia.data.adapters import ADAPTERS` and `from openlia.data.manifest import load_manifest`. The public-surface docstring at `data/__init__.py:1-5` promises a minimal surface but omits `ADAPTERS`, `load_manifest`, `RequirementsManifest`, `Requirement`, and the typed errors already added.
    - Files: `packages/core/src/openlia/data/__init__.py`.
    - Plan ref: Task 16 acceptance item 1 ("public surface kept minimal").
    - Spec ref: —
    - Acceptance: `test_public_surface_exports_all` runs `import openlia.data` and asserts every name in `__all__` is accessible; new names include `ADAPTERS`, `load_manifest`, `RequirementsManifest`, `Requirement`, `RequirementTier`, `UnmetRequirement`.

## P2 — Drift / hygiene

13. **NEW-3-01 — Ship `catalog/`, `review/`, `dispatch/`, `python_providers/`, `sentiment/` module stubs per spec file layout.** Why new: tracker treats spec drift as out-of-scope; this closes the spec-vs-impl gap explicitly without committing to the full subsystems.
    - Files: create `packages/core/src/openlia/data/catalog/__init__.py`, `…/review/__init__.py`, `…/dispatch/__init__.py`, `…/python_providers/__init__.py`, `…/sentiment/__init__.py`, each containing a `__deferred__ = True` marker + docstring linking the follow-up phase that will fill them in, and raising `NotImplementedError` from any top-level callable.
    - Spec ref: `data-provider-design.md` §"Complete File Layout".
    - Acceptance: `from openlia.data import catalog, review, dispatch, python_providers, sentiment` succeeds; `catalog.__deferred__ is True`.

14. **NEW-3-02 — Prepend an "Implementation Status" section to `data-provider-design.md` enumerating which spec sections are NOT in phase-3 scope.** Why new: Phase 17 shipped the same kind of drift; the spec should self-document the deferral so future phases can close it explicitly.
    - Files: `planning/specs/systems/data-provider-design.md` (prepend).
    - Acceptance: coordinator-review checklist on the new section (catalog, AI review, dispatch router, runtime expansion, MCP client, python_providers, retail-sentiment availability checker) lists the future phase owning each item.

15. **NEW-3-03 — Audit and re-docstring `auto_map` so its current "deterministic first-match" semantic is not confused with the spec's "AI review".**
    - Files: `packages/server/src/openlia_server/services/data_providers.py:254-310` (docstring), `packages/server/src/openlia_server/routes/settings.py:124-138` (route docstring + 200-body `"mode": "heuristic"`).
    - Plan ref: Tasks 11, 14.
    - Spec ref: `data-provider-design.md` §"AI Review".
    - Acceptance: both docstrings mention "heuristic mapping, not LLM review — see deferred spec"; no code imports from `openlia.data.review`.

16. **NEW-3-04 — Setup Wizard Step 2 never POSTs to `/settings/data-providers`.** `routes/setup.py:223-236` reads `list_providers` inside the review run, but no Step 2 route stub exists (Step 2 of the wizard is Data Providers per the spec). Either the wizard collects nothing in Step 2 (then mark NEW-3-04 closed when Step 2 UX is finalized in Plan 10 follow-ups) or a `POST /setup/data-providers` thin wrapper is needed. Track the decision here so Plan 10 owners do not forget.
    - Files: `packages/server/src/openlia_server/routes/setup.py`, `frontend/src/api/setup.ts`.
    - Acceptance: explicit decision logged in the tracker; Step 2 wizard e2e passes.

17. **NEW-3-05 — `DataProvider.mcp_auth_header`, `.category`, `.mcp_url` need an Alembic migration.** Paired with P0-3-01 and P0-3-02. Split out because the schema change requires baseline-migration coordination.
    - Files: `packages/server/alembic/versions/XXXX_add_category_and_mcp_to_data_providers.py`.
    - Acceptance: `alembic upgrade head` + `alembic downgrade -1` round-trips clean on SQLite and Postgres; existing rows default `category='financial'` for rows whose `kind in {'eodhd','fmp','finnhub','yfinance'}`.

18. **NEW-3-06 — `ProviderEntry.extra_config` type is `dict[str, Any]` but is frozen by `model_config = ConfigDict(frozen=True)`.** Pydantic v2 does not deeply freeze nested dicts; Plan 5 expects this to be immutable for hashing. Add `MappingProxyType` wrap at validation time.
    - Files: `packages/core/src/openlia/data/types.py:26-52`.
    - Acceptance: `test_provider_entry_extra_config_rejects_mutation` passes.

19. **NEW-3-07 — `_format_ticker` in EODHD hard-codes `.US`.** Multi-exchange support is deferred per Task 8 header but no issue is filed. Convert to `extra_config["exchange_suffix"]` with default `US`.
    - Files: `packages/core/src/openlia/data/adapters/eodhd.py:106-109`.
    - Acceptance: `test_format_ticker_honors_extra_config_suffix`.

20. **NEW-3-08 — `ProviderEntry._transport_requirements` rejects MCP entries that were loaded with a legacy row missing both `base_url` and `mcp_url`.** Paired with P0-3-02 migration — surface the ambiguity instead of silently validating.
    - Files: `packages/core/src/openlia/data/types.py:54-60`.
    - Acceptance: error message includes `row_id` context via `ValidationError`.

## Missing tests

- `test_eodhd_company_fundamentals` — respx fixture targeting `/fundamentals/AAPL.US`, asserting the adapter returns the `Financials` subtree under `ToolResult.payload`.
- `test_eodhd_401_raises_authentication_error`, `test_eodhd_5xx_marks_transient`, `test_eodhd_timeout_marks_transient`, `test_eodhd_http_date_retry_after`.
- `test_rate_limit_retries_and_succeeds_on_third_attempt`, `test_rate_limit_exhausted_raises_rate_limit_error`.
- `test_create_provider_persists_category`, `test_row_to_entry_uses_db_category_for_unknown_kinds`.
- `test_create_mcp_provider_roundtrips`, `test_create_mcp_provider_without_mcp_url_returns_400`.
- `test_auto_map_first_match_wins` — two EODHD-clone providers, assert only one mapping row per requirement_type.
- `test_auto_map_is_idempotent` — run `auto_map` twice; mapping set identical; referenced by Task-16 acceptance item 12 but not shipped.
- `test_load_entries_for_capability_skips_disabled_provider`.
- `test_patch_provider_priority_reorders_auto_map`.
- `test_test_connection_returns_501_for_unknown_kind`, `test_test_connection_uses_auth_error_to_distinguish_401`.
- `test_public_surface_exports_all` — asserts `openlia.data.__all__` round-trips.
- `test_setup_step2_data_providers_route` (once NEW-3-04 decision lands).
- `test_provider_entry_extra_config_rejects_mutation`.
- `test_format_ticker_honors_extra_config_suffix`.
- `test_unknown_kinds_accepted_once_registry_has_stub_adapter` — covers P1-3-05.
- `test_search_category_enum` — asserts `ProviderCategory.SEARCH` exists and the pydantic model accepts it.
- `test_category_column_migration_roundtrip` — Alembic upgrade/downgrade in `test_db_migrations.py`.

## Verification checklist

- `uv run pytest packages/core/tests/test_data/ packages/server/tests/test_routes/test_data_providers_routes.py packages/server/tests/test_routes/test_data_providers_integration.py packages/server/tests/test_services/test_data_providers.py -v` green after every task.
- `uv run alembic -c packages/server/alembic.ini upgrade head && uv run alembic -c packages/server/alembic.ini downgrade -1` clean.
- `python -c "import openlia.data.catalog, openlia.data.review, openlia.data.dispatch, openlia.data.python_providers, openlia.data.sentiment"` exits 0.
- `python -c "from openlia.data import ADAPTERS; print(sorted(ADAPTERS))"` lists at least `['eodhd', 'finnhub', 'fmp', 'mediastack', 'newsapi_ai', 'newsapi_org']` (stubs acceptable).
- Manual: POST a `mode=mcp` provider → GET → PATCH → DELETE round-trip works and `mcp_url` round-trips.
- Manual: POST two EODHD providers with `extra_config.default_priority` 10 and 50 → POST `/auto-map` → GET `/mappings` shows exactly one row per requirement_type pointing at the priority-10 provider.
- Manual: `POST /settings/data-providers/{id}/test-connection` against a provider whose `kind` is a stub adapter returns `501` (or `400`) — not `200 {"ok": false}`.
- Coordinator signs off on the new "Implementation Status" header in `data-provider-design.md`.
- Tracker rows for NEW-3-01 … NEW-3-08 flipped to `[x]` only after each acceptance criterion is independently verified.
