# Rescope Connector Need-Resolution to Portfolio-Only

Trim the connector "need-resolution" mechanism down to exactly what the **Portfolio page** requires, and retire the now-dead Macro-Research / Retail-Sentiment / department-runner machinery layered on top of it.

## 1. Why this exists (corrected understanding)

An earlier exploration wrongly concluded the "runner-need-resolution" layer was consumer-less. It is **not**: the Portfolio price/history/search feature resolves all its data through it.

`ConnectorFinancialAdapter` (wired at `app.py` as `app.state.financial_adapter`) is Portfolio's data provider. Every fetch flows:

```
portfolio route / scheduler
  → ConnectorFinancialAdapter.fetch(need_id, params)
  → dept = _NEED_DEPARTMENT_MAP[need_id]
  → build_dispatcher(session)                     # loads RunnerCallableSpec rows → callable_specs
  → dispatcher.in_department(dept)
  → dispatcher.fetch_need(need_id, **params)      # resolves via callable_specs[(dept, need_id)]
```

The `RunnerCallableSpec` rows are written by `connectors_service._upsert_runner_specs_from_template` on connector validation, from the builtin connector templates' `runner_specs`. This whole chain is **live and load-bearing** for Portfolio.

What IS dead (MR and RS migrated to LLM-dashboard engines; no department is `requires_runner=True`):
- the department-`requires_runner` health/runtime gating,
- the interactive wizard need-resolution flow (propose/approve UI + routes + services),
- `deterministic.py`'s MR/RS T1 helpers,
- the MR macro-indicator + RS `social_posts` need declarations and builtin `runner_specs`.

**Goal:** keep the Portfolio resolution chain, trimmed to Portfolio's needs and re-homed in a clean `portfolio` namespace; delete the dead remainder.

Portfolio's needs (the only ones to keep): `stock_quote` (refresh prices, scheduled), `eod_history` (backfill on add-holding), `company_profile` (ticker search — currently a pre-existing bug: absent from `_NEED_DEPARTMENT_MAP`).

## 2. Decision log

| ID | Decision | Rationale |
|----|----------|-----------|
| P1 | Keep the resolution chain (`fetch_need`, `callable_specs`, `RunnerCallableSpec`, `_upsert_runner_specs_from_template`, `build_dispatcher` spec-load, `_NEED_DEPARTMENT_MAP`, `sync_template_specs`, `covered_need_ids`); it is Portfolio's backbone. | Removing it breaks Portfolio (proven). |
| P2 | Builtin-only resolution. Drop the interactive wizard need-resolution flow entirely. | User decision. Portfolio resolves via builtin EODHD/FMP `runner_specs` auto-upserted on validation; custom-connector price resolution is dropped (accepted regression vs main). |
| P3 | Re-home Portfolio needs in a single `portfolio` namespace. | Today `stock_quote` borrows the `macro_research` dept context, which we're deleting. All three needs become `(department_id="portfolio", need_id)`. |
| P4 | Drop the `needs.yaml` mechanism (`load_needs`, the `Need` type, both `*.needs.yaml`). Make the builtin `runner_specs` self-contained for the 3 portfolio needs; replace the needs.yaml drift test with an internal-consistency test. | `fetch_need`/`_upsert` never read `needs.yaml` at runtime; it was only a department-runner contract + a drift test. The builtin template `runner_specs` are the real source of truth. |
| P5 | Remove the `requires_runner` field, the deterministic runtime mode, `DepartmentHealth.unresolved_needs`, and `deterministic.py`. | All dead (no runner dept; MR/RS migrated). |
| P6 | Fix the pre-existing `company_profile` ticker-search bug as part of giving Portfolio a clean, complete need-set. | It's one of Portfolio's three needs; leaving it broken while fixing the other two is inconsistent. Best-effort on the EODHD endpoint mapping (flag if EODHD lacks a suitable callable). |
| P7 | Guardrail: the resolution chain must stay green. The gate is the **resolution-chain tests** — `test_dispatcher.py` (`fetch_need`), `test_dispatcher_factory_substitutions.py` (`_hydrate_spec`/`callable_specs`), and `test_connectors_service` (`_upsert`). These pass on main and exercise the real chain. NOTE: `test_value_series_returns_points` is a **pre-existing baseline red** (quote-seeded route test, unrelated to `fetch_need`) — it is NOT a guardrail; leave it red. | Verify the chain explicitly at every step; don't be misled by the unrelated pre-existing portfolio red. |

## 3. Goals / Non-goals

**Goals**
- Portfolio price refresh, history backfill, and ticker search resolve correctly via builtin connectors, after the trim.
- A clean `portfolio` need namespace with exactly `stock_quote`, `eod_history`, `company_profile`.
- All MR/RS/department-runner/wizard machinery removed.

**Non-goals**
- No change to chat / dashboard engines (`candidate_tools` path), connector install/validation/MCP discovery, or connector CRUD beyond trimming spec content.
- No custom-connector (python_lib/MCP) Portfolio price resolution (dropped per P2).
- No new Portfolio features.

## 4. KEEP + trim

- **`packages/core/src/openlia/connectors/dispatch.py`** — `Dispatcher`, `fetch_need`, `callable_specs`, `CallableSpec`, `in_department`, `NeedNotResolved`, `candidate_tools`, `dispatch_tool_use`. Unchanged.
- **`packages/server/src/openlia_server/services/connector_financial_adapter.py`** — unchanged.
- **`services/connectors_service.py`** — keep `_upsert_runner_specs_from_template`, `sync_template_specs`, connector CRUD. **Trim `_NEED_DEPARTMENT_MAP`** to `{stock_quote: portfolio, eod_history: portfolio, company_profile: portfolio}` (add `company_profile`; re-key `stock_quote` from `macro_research`; remove all MR/RS entries).
- **`services/dispatcher_factory.py`** — keep `build_dispatcher` + `_hydrate_spec` (the `RunnerCallableSpec` → `callable_specs` load). Unchanged.
- **`routes/connectors.py`** — keep the `sync-template-specs` route + `covered_need_ids` on `BuiltinTemplateOut` (now reflecting only portfolio needs).
- **`db/models/connectors.py`** — keep `RunnerCallableSpec`. (Drop `ResolverCallLog`/`SmokeCallLog` — wizard-only; see §5.)
- **Builtin templates** (`connectors/builtins/{eodhd,fmp}.py`) — **trim `runner_specs`** to the portfolio needs only, keyed to `department_id="portfolio"`: keep/relabel `stock_quote` + `eod_history`; **add `company_profile`** (map to EODHD's fundamentals/search endpoint — best-effort per P6); remove the MR macro-indicator specs (`debt_gdp`, `pmi`, `cpi_yoy`, `usd_fx_reserve_share`, … ) and the RS `social_posts` spec. Firecrawl/mediastack/newsapi_ai: remove their `runner_specs` if they only served MR/RS news needs.
- **Frontend** — keep `syncTemplateSpecs` + `covered_need_ids` + `CatalogCard` need-count badge (they reflect portfolio coverage now).
- **`dept_health.py` / `health.py`** — keep all category gating + `gate_dept_or_409` + `satisfied_categories`.

## 5. REMOVE (dead)

- **Core**: `llm/runtime/deterministic.py` (whole file); `departments/loader.py` `load_needs` + the `Need` type (keep `load_routing_context`); `departments/base.py` `requires_runner` field; the `requires_runner` ClassVar in all 7 dept files; `departments/macro_research.needs.yaml` + `retail_sentiment.needs.yaml`; the MR/RS `runner_specs` entries in the builtin templates (per §4 trim).
- **Core health**: `health.py` `if dept.requires_runner:` branch + `_RunnerSpecLike` + the `runner_specs` param of `check_dept_health` + `DepartmentHealth.unresolved_needs`.
- **Server**: `routes/runner_specs.py` (all routers) + their `app.py` mounts + the `hydrate_dept_registries()` startup call; `services/runner_specs_service.py`; `services/resolver_save_flow.py`; `services/template_upgrade.py` (wizard spec management — confirm not used by `_upsert`/`sync_template_specs`; if `revert_to_default` is used by the live `sync` UX, keep that piece). `services/runtime.py`: `run_department` deterministic branch + `select_runtime_mode` `requires_runner` logic + the `"deterministic"` `RuntimeMode`. `dept_health.py`: the `RunnerCallableSpec` query + `runner_specs` arg + `unresolved_needs` emit.
- **DB**: drop `resolver_call_log` + `smoke_call_log` tables (wizard audit; no live writer/reader) via migration + remove the 2 models. **KEEP `runner_callable_specs`.**
- **Frontend**: `setup/steps/ResolveStep.tsx`, `ResolveRow.tsx`, `SmokeFailurePanel.tsx`, `PerNeedReviewCard.tsx`, `DeptResolvePanel.tsx`; `components/settings/admin/{RunnerCallableSpecsAdminPanel,ResolutionsAdminPanel}.tsx`; the wizard ResolveStep wiring; the proposed-spec/approve functions in `api/connectors.ts` (`listProposedSpecs`, `resolveProposedSpecs`/`reResolveSpecs`, `approveSpec`, `listDeptProposedSpecs`, `resolveDeptProposedSpecs`, `listDeptResolveEvents`, `resolveDeptNeed`, `approveDeptSpec`, `ProposedSpec`, `ResolveEvent`); `RUNNER_BEARING_DEPARTMENTS`; `unresolved_needs` from `dept-health.ts` + `DeptDisabledBanner`. **KEEP `syncTemplateSpecs` + `covered_need_ids` + `CatalogCard`.**
- **Tests**: the wizard/runner-path tests (`test_routes_runner_specs*`, `test_runner_specs_dept_service`, `test_resolver_save_flow`, `test_resolver_redesign_e2e`, e2e `test_python_lib_runner_activation`/`test_atomic_disable_on_delete`, `test_override_wins_upgrade` if `template_upgrade` goes); `test_needs_canonical_keys`; the needs.yaml-present cases in `test_department_artifacts`; the deterministic.py tests; simplify `test_runtime_entry` (drop deterministic) + the `unresolved_needs`/runner cases in health tests. **Trim, don't delete, `test_registry.py`** — replace the needs.yaml-drift cases with an internal-consistency check on the (now portfolio-only) builtin `runner_specs` (field_map covers each spec's own canonical_keys/result shape).

## 6. The `portfolio` namespace + dropping needs.yaml

- All three portfolio needs are keyed `(department_id="portfolio", need_id)` in both the builtin template `runner_specs` and `_NEED_DEPARTMENT_MAP`. `"portfolio"` is a namespace string for `in_department`/`callable_specs` keying — it is **not** a registered chat Department and needs no routing_context (this already holds for `eod_history`).
- `needs.yaml` is removed entirely. The builtin template `runner_specs` are self-contained: each entry carries its `need_id`, `field_map`, and canonical result shape. `_upsert_runner_specs_from_template` and `fetch_need` use those directly; neither reads `needs.yaml`. The drift test becomes an internal-consistency test over the builtin `runner_specs`.

## 7. Sequencing (build order)

1. **Core dead-code**: `deterministic.py`, `requires_runner` field + 7 dept ClassVars, `health.py` branch + `unresolved_needs`, `loader.load_needs`/`Need`. (No portfolio impact — these never touched `fetch_need`/`callable_specs`.)
2. **Server dead-code**: delete `routes/runner_specs.py` + `runner_specs_service` + `resolver_save_flow` + (`template_upgrade` if fully dead); strip `app.py` mounts/hydrate; `runtime.py` deterministic mode; `dept_health.py` de-spec (`runner_specs`/`unresolved_needs`). Delete the wizard/runner-path tests.
3. **Trim the need-set**: builtin `runner_specs` → portfolio-only, keyed `portfolio`; `_NEED_DEPARTMENT_MAP` → 3 portfolio needs; add `company_profile`; delete both `needs.yaml`; rewrite the drift test.
4. **Frontend dead-code**: remove the wizard resolve UI + proposed-spec api block + `RUNNER_BEARING` + `unresolved_needs`; KEEP `syncTemplateSpecs`/`covered_need_ids`/`CatalogCard`.
5. **DB**: drop `resolver_call_log` + `smoke_call_log` (keep `runner_callable_specs`); remove the 2 models.
6. **Verify**: full suites + the Portfolio resolution guardrail.

After each step: the resolution-chain guardrails (`test_dispatcher.py` fetch_need, `test_dispatcher_factory_substitutions.py` _hydrate_spec, `test_connectors_service` _upsert) must stay green. That is the non-negotiable invariant. (`test_value_series_returns_points` is pre-existing red — ignore it.)

## 8. Risks / landmines

1. **Breaking Portfolio (the whole point).** After trimming `runner_specs`/`_NEED_DEPARTMENT_MAP` + re-keying to `portfolio`, the validate→upsert→fetch_need chain must still resolve `stock_quote`/`eod_history`. Guardrail test must pass. The re-key means the EODHD template's `stock_quote` `runner_spec` entry's `department_id` must change `macro_research`→`portfolio` AND `_NEED_DEPARTMENT_MAP` must agree.
2. **`company_profile` endpoint availability.** EODHD may not have a clean profile/search callable. If adding its `runner_spec` is non-trivial, ship the trim + map entry and flag the endpoint mapping as a follow-up rather than block.
3. **`template_upgrade` vs `sync_template_specs`.** Confirm whether the live `sync-template-specs` route uses anything from `template_upgrade` before deleting that file; keep the minimal piece if so.
4. **`covered_need_ids` now portfolio-only.** The catalog badge will show portfolio need coverage only — update the relevant frontend test fixtures accordingly.
5. **Dropping `resolver_call_log`/`smoke_call_log`** is destructive (recreating downgrade); no live reader/writer.
6. **`NeedNotResolved`/`CallableSpec`** stay (portfolio uses them) — do not remove with `deterministic.py`.

## 9. Verification

- Resolution-chain guardrail (must be green at every step): `packages/core/tests/connectors/test_dispatcher.py` + `test_dispatcher_field_map.py` (`fetch_need`), `packages/server/tests/test_services/test_dispatcher_factory_substitutions.py` (`_hydrate_spec`), `packages/server/tests/services/test_connectors_service.py` (`_upsert`). NOTE: `test_value_series_returns_points` already fails on main (pre-existing baseline red) — not a regression signal here.
- `eod_history` / `company_profile` have NO builtin spec today (pre-existing gap; only `stock_quote` resolves) — the rescope does not worsen this. Adding their specs is best-effort (P6), not required.
- Full `core` + targeted server dirs + frontend `tsc`/`vitest` + `alembic` up/down/up.
- Orphan grep: no live `requires_runner`/`unresolved_needs`/`load_needs`/`needs.yaml`/wizard-resolve refs; `fetch_need`/`RunnerCallableSpec`/`_NEED_DEPARTMENT_MAP`/`callable_specs`/`sync_template_specs`/`covered_need_ids` remain (portfolio).
- Baseline pre-existing reds unchanged (SettingsShellBlocker, MB-lifespan, `mr_dashboard_cache` alembic drift).
