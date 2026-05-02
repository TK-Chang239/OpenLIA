# Resolver Redesign — Implementation Plan

Status: Plan — drafted 2026-05-02, awaiting execution approval

Companion to `docs/superpowers/specsv2/2026-05-02-resolver-redesign-manual-pick.md`. Read the design doc first; this plan assumes its decisions.

## Plan shape

Twelve phases. Each phase is structured for TDD subagent execution: a tight goal, the files that change, the tests to write first, the implementation steps, and a clear "done" condition. Phases are ordered by dependency. Phases that can fan out in parallel are marked.

The plan does not introduce backwards-compatibility shims. The shipped resolver is on `feat/builtin-connectors`, not on `main`; that branch will be retired or rebased once this redesign lands. No production users to migrate.

## Phase 1 — Schema migration

**Goal.** Persist the new fields on `RunnerCallableSpec` and create the two audit tables.

**Files.**
- `packages/server/src/openlia_server/db/models/connectors.py`
- New Alembic revision under `packages/server/src/openlia_server/db/migrations/versions/`

**Tests first.**
- `test_runner_callable_spec_new_columns_persist_and_load` — round-trip a row with each new column populated.
- `test_resolver_call_log_round_trip` and `test_smoke_call_log_round_trip` — basic insert + query.
- `test_resolution_mode_enum_rejects_unknown_value` — DB-level constraint check.

**Implementation.**
- Add columns to `runner_callable_specs`: `resolution_mode` (enum-as-text with CHECK), `connector_id` (FK to `connectors.id`, nullable for transitional rows), `user_inputs` (JSON), `llm_warning` (TEXT), `manually_overridden` (BOOLEAN, default FALSE), `last_smoke_at` (TIMESTAMP).
- Create `resolver_call_log` and `smoke_call_log` per the design doc §10.2.
- Index `(spec_id, created_at DESC)` on both audit tables for the admin panel's history view.

**Done when.** Migration runs cleanly forward and back on an empty DB and on a DB containing existing rows from `feat/builtin-connectors`. All three tests pass.

## Phase 2 — Per-need YAML: `canonical_keys`

**Goal.** Annotate every `list[dict]`-shaped need with the canonical key set its dept-side adapter expects.

**Files.**
- `packages/core/src/openlia/departments/macro_research.needs.yaml`
- `packages/core/src/openlia/departments/retail_sentiment.needs.yaml`
- `packages/core/src/openlia/connectors/types.py` (extend `RunnerNeed` and `NeedParameter` adjacent types)
- `packages/core/src/openlia/departments/loader.py` (parse the new field)

**Tests first.**
- `test_loader_parses_canonical_keys_for_list_dict_shapes` — load both YAMLs, assert `canonical_keys` populated for `geopolitical_news` and `social_posts` and absent for scalar needs.
- `test_loader_rejects_canonical_keys_on_scalar_shape` — schema invariant: scalar needs cannot declare `canonical_keys`.
- `test_loader_rejects_list_dict_shape_without_canonical_keys` — once the new field exists, list-shape needs without it should fail loud at startup.

**Implementation.**
- Add `canonical_keys: dict[str, str] | None` to `RunnerNeed`.
- For each `list[dict]` need, write the canonical key set by inspecting how the dept currently consumes it. `geopolitical_news` and `social_posts` are the two known cases.
- Loader validation per the test invariants above.

**Done when.** Both YAMLs parse, scalar needs have `canonical_keys = None`, list-shape needs have populated maps, validation rejects mismatches.

## Phase 3 — Executor: apply `field_map`

**Goal.** Make the runtime dispatcher honor `CallableSpec.field_map` when present.

**Files.**
- `packages/core/src/openlia/connectors/dispatch.py`
- `packages/core/src/openlia/connectors/types.py` (add `field_map` to the dataclass)
- `packages/core/src/openlia/connectors/spec_executor.py` if such a layer exists; otherwise the field-map walk lives next to the existing `result_path` walk.

**Tests first.**
- `test_field_map_renames_keys_per_item_for_list_dict_shape` — given `result_path` to a list and a `field_map`, output items have only the canonical keys.
- `test_field_map_dotted_value_extracts_nested` — `{"author": "user.handle"}` correctly walks per-item nested paths.
- `test_field_map_missing_canonical_key_raises` — if `field_map` is missing a required canonical key at runtime, raise a typed exception with the offending key.
- `test_field_map_ignored_for_scalar_shape` — scalar specs ignore the field, no error.
- `test_no_field_map_returns_items_as_is` — null `field_map` is the legacy behavior (catalog rows that match canonical keys without renaming).

**Implementation.**
- After the existing `result_path` walk, if shape is `list[dict]` and `field_map` is present and non-empty, build the renamed list. Use a small dotted-path helper (existing or new). If `field_map` is `None` or `{}`, return the list unchanged.
- The runtime exception type should be classifiable by the smoke pipeline (Phase 7). Pick a name like `FieldMapError`.

**Done when.** All five tests pass. Dispatcher returns canonical-keyed items for list-shape specs that declare `field_map`, raw items otherwise.

## Phase 4 — Catalog `runner_specs` regeneration

**Goal.** Update every Day-1 built-in template's pre-baked `runner_specs` to include `field_map` for `list[dict]` needs.

**Files.**
- `packages/core/src/openlia/connectors/builtins/eodhd.py`
- `packages/core/src/openlia/connectors/builtins/fmp.py`
- `packages/core/src/openlia/connectors/builtins/firecrawl.py`
- `packages/core/src/openlia/connectors/builtins/news_api_ai.py`
- `packages/core/src/openlia/connectors/builtins/mediastack.py`
- `packages/core/src/openlia/connectors/builtins/x.py`

**Tests first.**
- `test_every_list_dict_runner_spec_has_field_map` — iterate all built-in templates, assert that any `runner_spec` whose need has shape `list[dict]` declares a `field_map`.
- `test_field_maps_cover_canonical_keys` — for each such spec, assert that `field_map` keys ⊇ the need's `canonical_keys`.

**Implementation.**
- Walk each template. For each `list[dict]`-shape spec, write the `field_map`. Many will be `{}` (their endpoint already returns canonical keys). Where the endpoint returns differently named fields, populate the map. The May 1 review noted which templates rely on speculative method names — those are the highest-priority ones to inspect against the actual provider docs.

**Done when.** Both invariants pass for all six templates. The two failing existing tests from Phase 2 now stop failing because catalog specs satisfy them.

## Phase 5 — Resolver LLM: rewrite the prompt

**Goal.** Make the per-need LLM call accept a user-picked endpoint (or URL) and emit a `CallableSpec` including `field_map` for list shapes.

**Files.**
- `packages/core/src/openlia/connectors/adapter/callable_spec_resolver.py`
- The prompt template file referenced from the resolver (likely a sibling `.md` or an inline string; locate it).

**Tests first.**
- `test_resolver_accepts_user_endpoint_pick_and_emits_param_bindings` — given a fixture connector + user pick + LLM stub returning a known JSON, the resolver returns the parsed spec.
- `test_resolver_emits_field_map_for_list_dict_shape` — for a `list[dict]` need, the prompt asks for `field_map`; the LLM stub provides one; the parsed spec carries it.
- `test_resolver_websearch_mode_pins_connector_to_web_search_category` — given a URL input, the prompt is composed with the user's `web_search` connector and the scrape callable pre-bound.
- `test_resolver_warning_field_propagates` — LLM stub returns a `{spec: {...}, warning: "..."}` envelope; the resolver returns both.

**Implementation.**
- Restructure the prompt: replace "the LLM picks a callable" framing with "the user picked this callable; produce the binding."
- Add `canonical_keys` and `shape` to the prompt for list shapes; instruct the LLM to author `field_map`.
- Add the user's freeform hint as a verbatim block in the prompt.
- Output schema becomes `{spec: CallableSpec, warning: string | null}`.
- For websearch mode, the prompt describes the constrained sub-mode (Firecrawl-style scrape spec with JSON-extraction schema) and pre-binds the connector + endpoint.

**Done when.** All four tests pass. The resolver no longer chooses callables; user input is required.

## Phase 6 — Validation gate extensions

**Goal.** Strengthen the post-LLM validation to cover `field_map`, the extended transform allowlist, and the warning envelope.

**Files.**
- `packages/core/src/openlia/connectors/adapter/callable_spec_resolver.py` (gate is colocated with the resolver today)
- Possibly a new `validation.py` module if the gate grows large.

**Tests first.**
- `test_validation_rejects_unknown_transform` — running the gate with `transform: "to_uppercase"` (not in the allowlist) raises.
- `test_validation_accepts_extended_allowlist` — each of `to_float`, `to_int`, `strip`, `list_first`, `iso_date` passes.
- `test_validation_rejects_field_map_missing_canonical_key` — gate fails if `field_map` doesn't cover all `canonical_keys` for a `list[dict]` need.
- `test_validation_rejects_field_map_for_scalar_shape` — non-list specs cannot declare `field_map`.
- `test_validation_passes_with_null_field_map_when_keys_already_match` — explicit empty map is valid for catalog-style "no rename needed" cases (use `{}` not `None` to express intent).

**Implementation.**
- Extend `ALLOWED_TRANSFORMS`. Implement the new transforms: `to_float`, `to_int`, `strip`, `list_first`, `iso_date`.
- Add `field_map` validation rules.
- Wire the warning field through to the caller.

**Done when.** All five tests pass. Existing resolver tests still pass.

## Phase 7 — Smoke pipeline

**Goal.** Build the per-save smoke-call pipeline with canonical test args, classifier, and the `from_dict` constructibility check.

**Files.**
- New `packages/server/src/openlia_server/services/smoke_service.py`
- `packages/server/src/openlia_server/routes/runner_specs.py` (or wherever the resolve endpoint lives) — wire smoke into the save flow.

**Tests first.**
- `test_smoke_uses_canonical_args` — fixture spec for `stock_quote(ticker)`; smoke call inspects the dispatched args and asserts `ticker = "AAPL"`.
- `test_smoke_classifies_auth_failure` — stub transport raises 401; result has `status = "auth"`.
- `test_smoke_classifies_schema_miss` — stub returns valid JSON, but `result_path` doesn't resolve; status is `schema_miss`.
- `test_smoke_classifies_empty_result` — response is `[]`; status is `empty`.
- `test_smoke_classifies_bad_params` — 400 response; status is `bad_params`.
- `test_smoke_classifies_transient_and_retries` — stub raises timeout twice, succeeds third; total attempt count is 3, status is `success`.
- `test_smoke_pipes_first_item_through_from_dict_for_list_dict_shape` — the dept's `from_dict` raises `KeyError`; smoke returns `schema_miss` with the offending key in the message.
- `test_smoke_blocks_save_on_failure` — calling save with a spec that smoke-fails returns the typed failure and does not persist a `RunnerCallableSpec` row.
- `test_smoke_persists_log_row` — every smoke attempt writes to `smoke_call_log`.

**Implementation.**
- Canonical args dictionary as a constant in `smoke_service.py`.
- Classifier function operating on the dispatched response or raised exception.
- Dept-side `from_dict` invocation: locate the dept's adapter for each list-shape need; use a registry mapping `(department, need_id) → from_dict_callable`.
- Save flow becomes: persist spec as `draft` → run LLM → run smoke → on success commit live; on failure rollback draft and return typed failure.

**Done when.** All nine tests pass. Save-time smoke is the only path that creates a non-draft `RunnerCallableSpec`.

## Phase 8 — Resolve UI: per-row form

**Goal.** Build the in-wizard resolve screen with mode toggle, type-to-search endpoint picker, hint field, override flow, and typed failure panel.

**Files.**
- `frontend/src/setup/steps/ResolveStep.tsx` (new — replaces the current `DeptResolvePanel` driven flow)
- `frontend/src/setup/steps/ResolveRow.tsx` (per-need row)
- `frontend/src/setup/steps/EndpointPicker.tsx` (type-to-search over cached endpoints)
- `frontend/src/setup/steps/SmokeFailurePanel.tsx` (typed failure rendering)
- `frontend/src/api/runner_specs.ts` (new endpoints; extend existing if any)

**Tests first.** Vitest + React Testing Library:
- `test_resolve_step_shows_all_twelve_needs_with_status_badges`
- `test_catalog_row_renders_read_only_with_edit_button`
- `test_unresolved_row_renders_form_expanded`
- `test_endpoint_picker_filters_by_typed_query`
- `test_websearch_mode_disabled_when_no_web_search_connector`
- `test_save_calls_resolve_endpoint_and_renders_smoke_failure_panel_on_failure`
- `test_warning_modal_offers_proceed_or_cancel`
- `test_proceed_with_warning_sets_manually_overridden_flag`
- `test_auth_failure_panel_links_to_connector_settings_and_preserves_spec`
- `test_finish_wizard_blocked_until_all_rows_resolved`

**Implementation.**
- Mode toggle on each row: "Connector + endpoint" or "Websearch."
- Endpoint picker is a combobox; query the connector's cached endpoints client-side.
- Save handler hits a single backend endpoint that runs LLM + smoke + commit.
- Failure panel is keyed by the typed status from smoke.
- Warning modal renders the LLM's warning string; confirming sets `manually_overridden = true` in the request body.

**Done when.** All ten tests pass. Manual exercise in `npm run dev` against a backend with one custom connector installed walks through the full happy path and at least two failure paths.

## Phase 9 — `ResolutionsAdminPanel`

**Goal.** Mount the resolve UI as a post-wizard admin panel under Settings.

**Files.**
- `frontend/src/components/settings/admin/ResolutionsAdminPanel.tsx`
- `frontend/src/components/settings/admin/__tests__/ResolutionsAdminPanel.test.tsx`
- `frontend/src/components/settings/sections/AdminSection.tsx` (add the panel)
- `frontend/src/router/routes.tsx` if a dedicated route is needed.

**Tests first.**
- `test_admin_panel_renders_all_resolved_specs_with_history_button`
- `test_edit_drops_spec_to_draft_until_smoke_passes`
- `test_failed_edit_preserves_old_spec`
- `test_history_button_shows_recent_resolver_and_smoke_logs`

**Implementation.**
- Reuse `ResolveRow` from Phase 8. The panel is a thin wrapper: list rows, no wizard step pointer.
- Edit flow mirrors wizard edit: drops spec to draft, runs LLM + smoke, commits or surfaces failure.
- History view fetches from `resolver_call_log` and `smoke_call_log` (Phase 10).

**Done when.** All four tests pass. Admin panel is reachable from Settings and exercises the same backend endpoints as the wizard.

## Phase 10 — Audit log persistence and history endpoint

**Goal.** Persist `resolver_call_log` and `smoke_call_log` rows on every LLM call and smoke attempt, and expose a read endpoint for the admin panel.

**Files.**
- `packages/server/src/openlia_server/services/smoke_service.py` (already touched in Phase 7; add the persistence call)
- `packages/server/src/openlia_server/services/resolver_service.py` (or wherever the resolver is invoked from the server)
- `packages/server/src/openlia_server/routes/runner_specs.py` (new GET endpoint for history)

**Tests first.**
- `test_resolver_call_log_row_written_per_llm_attempt` — three attempts → three rows.
- `test_smoke_call_log_row_written_per_smoke_attempt`
- `test_history_endpoint_returns_recent_logs_for_spec`

**Implementation.**
- Add the inserts. Cap response body at 32KB before persisting (truncate with a marker).
- Endpoint: `GET /api/runner-specs/{id}/history` returns last N of each table.

**Done when.** Three tests pass. Admin panel's history button surfaces real data.

## Phase 11 — Override-wins template-upgrade flow

**Goal.** Detect when a built-in template's pre-baked spec for a need would change on re-install or upgrade, and surface a non-blocking notice without clobbering an override.

**Files.**
- `packages/server/src/openlia_server/services/connectors_service.py` — install/upgrade path.
- `frontend/src/components/settings/admin/ResolutionsAdminPanel.tsx` — render the notice.

**Tests first.**
- `test_install_does_not_overwrite_existing_user_override` — fixture: user override exists for `(macro_research, debt_gdp)`; reinstall catalog FMP; the override row is untouched.
- `test_upgrade_records_pending_default_change_when_override_exists` — fixture as above but the template's pre-baked spec differs from the live override; a "pending default change" record is created.
- `test_revert_to_default_swaps_override_for_template_spec` — explicit revert action consumes the pending record and replaces the spec.
- `test_admin_panel_renders_pending_default_notice_when_present`

**Implementation.**
- A small `pending_template_default_changes` table keyed by `(department, need_id)` — or a column on the spec row. Choose the simpler one based on observed cardinality during implementation.
- Install/upgrade path checks for existing user-mode rows and writes pending records instead of overwriting.

**Done when.** Four tests pass. Catalog reinstall on a user with overrides produces non-blocking notices and zero clobbers.

## Phase 12 — End-to-end and integration coverage

**Goal.** Lock the full happy paths and the most likely failure modes across the redesign.

**Files.**
- `packages/server/tests/integration/test_resolver_redesign_e2e.py`
- `frontend/src/setup/__tests__/setup-wizard-resolver.test.tsx`

**Tests.**
- E2E happy path: install custom connector → reach resolve step → for each need, pick endpoint, save, smoke passes, row turns resolved → finish wizard → confirmed all 12 specs are persistable and dispatch-able.
- E2E websearch path: install Firecrawl + custom financial connector → resolve scalar needs via Firecrawl websearch with URL+hint → smoke passes → finish wizard.
- E2E mixed install: catalog FMP + custom news → resolve screen shows financial as resolved-catalog and news as unresolved → only news rows require manual input.
- E2E override path: catalog row → click Edit → swap to custom connector → smoke passes → spec is now `manual_endpoint` and `manually_overridden = true`.
- Failure path: smoke returns 401 → typed panel surfaces auth bucket → fix key in connector settings → click Retry → spec re-validates without re-pick.
- Failure path: `field_map` mismatch (LLM stub authors a wrong rename) → smoke `from_dict` raises → typed panel surfaces schema-miss with offending key.

**Done when.** Every path passes. CI runs them on every PR touching the resolver.

## Phase order and parallelization

- **Sequential gates:** 1 → 2 → 3 → 4. Schema, YAML, executor, and catalog regeneration are a chain.
- **Parallel after Phase 4:**
  - Track A: Phases 5 → 6 → 7 (resolver, validation, smoke). Backend stack.
  - Track B: Phase 8 (UI). Can start on stubs once Phase 5's API surface is agreed; merges with Track A at Phase 7's save endpoint.
- **Sequential after both tracks complete:** Phase 9 (admin panel reuses Phase 8 components and Phase 7 endpoint), Phase 10 (audit endpoint feeds Phase 9 history), Phase 11 (override-wins logic depends on stable persistence from Phases 1, 7, 10).
- **Final gate:** Phase 12.

Estimated 12 phases × ~half a day median per phase = roughly one week of focused work. Phases 8 and 9 carry the most UI surface and are likely to overrun.

## Out of scope

Per the design doc §13:
- Runtime caching for websearch resolutions.
- Inline "Fix this resolution" link from dept-run failures.
- Multi-source merge or fallback per need.

These are deferred and tracked in this same path under future plans.
