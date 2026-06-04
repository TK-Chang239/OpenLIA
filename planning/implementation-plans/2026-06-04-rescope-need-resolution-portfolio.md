# Rescope Connector Need-Resolution to Portfolio-Only — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Trim the connector need-resolution chain to Portfolio's needs (`stock_quote`/`eod_history`/`company_profile` in a clean `portfolio` namespace) and delete the dead MR/RS/department-runner + interactive-wizard machinery.

**Architecture:** Start from working `main` (the resolution chain works for `stock_quote`). Trim, then delete dead code. The chain `connector-validate → _upsert_runner_specs_from_template → build_dispatcher (callable_specs) → fetch_need` is **load-bearing for Portfolio** and stays; only its *content* (which needs) is trimmed.

**Tech stack:** Python 3.12 + SQLAlchemy/Alembic, React/TS/Vite + Vitest, `uv`/`ruff`/`pytest`.

**Spec:** `planning/specs/systems/rescope-need-resolution-to-portfolio-design.md` (read first). **Branch:** `refactor/rescope-need-resolution-portfolio` (created; spec committed).

**THE GUARDRAIL (green at every step):** `packages/core/tests/connectors/test_dispatcher.py` + `test_dispatcher_field_map.py` (`fetch_need`), `packages/server/tests/test_services/test_dispatcher_factory_substitutions.py` (`_hydrate_spec`), `packages/server/tests/services/test_connectors_service.py` (`_upsert`). These pass on main and exercise the real resolution chain. **`test_value_series_returns_points` already FAILS on main (pre-existing baseline red, quote-seeded, unrelated) — not a regression signal.**

**Conventions:** `uv run ruff check --fix . && uv run ruff format .` (repo root) / `cd frontend && npx tsc --noEmit` before commit. No emojis. uv-cache sandbox error = sandbox restriction, not a code failure (controller re-runs unsandboxed). Commit per task with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

**Key grounded facts (from exploration):**
- `CallableSpec` has NO `department_id`; the dept is assigned at upsert via `_NEED_DEPARTMENT_MAP[need_id]` (`connectors_service.py:541`). So re-keying `stock_quote`→`portfolio` is a `_NEED_DEPARTMENT_MAP` edit ONLY.
- EODHD `runner_specs` = `(_DEBT_GDP, _GDP_YOY, _CPI_YOY, _CPI_CORE_YOY, _PMI, _STOCK_QUOTE, _SOCIAL_POSTS)`. FMP = `(_STOCK_QUOTE, _CPI_YOY, _GDP_YOY)`. Only `_STOCK_QUOTE` is a Portfolio need. `eod_history`/`company_profile` have NO spec anywhere (pre-existing gap).
- `fetch_need`/`_upsert` never read `needs.yaml` (only the dead health branch + drift tests do).

---

## Phase 1 — Trim the need-set to Portfolio (the careful one)

### Task 1: Trim builtins + `_NEED_DEPARTMENT_MAP`; drop `needs.yaml`; rewrite the drift test

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/eodhd.py`, `fmp.py` (+ check `firecrawl.py`, `mediastack.py`, `newsapi_ai.py` for MR/RS-only `runner_specs`).
- Modify: `packages/server/src/openlia_server/services/connectors_service.py` (`_NEED_DEPARTMENT_MAP`).
- Delete: `packages/core/src/openlia/departments/macro_research.needs.yaml`, `retail_sentiment.needs.yaml`.
- Modify/rewrite tests: `packages/core/tests/connectors/builtins/test_registry.py`, `packages/core/tests/connectors/test_dispatcher.py` / `test_dispatcher_field_map.py` (only if they reference removed MR/RS needs), `packages/server/tests/services/test_connectors_service.py`.

- [ ] **Step 1: Baseline the guardrail.** Run the guardrail set; record it green: `cd packages/core && uv run pytest tests/connectors/test_dispatcher.py tests/connectors/test_dispatcher_field_map.py -q` + `cd packages/server && uv run pytest tests/test_services/test_dispatcher_factory_substitutions.py tests/services/test_connectors_service.py -q`.

- [ ] **Step 2: `_NEED_DEPARTMENT_MAP` → portfolio-only.** In `connectors_service.py` replace the map with:
```python
_NEED_DEPARTMENT_MAP: dict[str, str] = {
    "stock_quote": "portfolio",
    "eod_history": "portfolio",
    "company_profile": "portfolio",
}
```
(Removes all MR/RS entries; re-keys `stock_quote` from `macro_research`; adds `company_profile`.)

- [ ] **Step 3: Trim builtin `runner_specs`.** EODHD: `runner_specs=(_STOCK_QUOTE,)` (remove `_DEBT_GDP`/`_GDP_YOY`/`_CPI_YOY`/`_CPI_CORE_YOY`/`_PMI`/`_SOCIAL_POSTS` + their now-unused `CallableSpec` defs + the `_reducer_spec` helper if unused). FMP: `runner_specs=(_STOCK_QUOTE,)` (remove `_CPI_YOY`/`_GDP_YOY`). For firecrawl/mediastack/newsapi_ai: if their `runner_specs` only served MR/RS news needs, set `runner_specs=()` (or remove the field). **Best-effort (P6):** if EODHD has a clean profile/EOD-history callable, add `_COMPANY_PROFILE`/`_EOD_HISTORY` `CallableSpec`s and include them; if not, leave those two needs as declared-in-map-only (pre-existing gap — do NOT block).

- [ ] **Step 4: Delete both `.needs.yaml` files** (`git rm`).

- [ ] **Step 5: Rewrite the drift test.** In `test_registry.py`, the cases that assert `runner_specs` reference need ids declared in `needs.yaml` now have no `needs.yaml`. Replace them with an **internal-consistency** check over the (portfolio-only) builtin `runner_specs`: every `list[dict]`-shaped spec's `field_map` covers its declared canonical keys; required `param_bindings` present; `need_id` non-empty. Keep template-shape tests that don't touch needs.yaml. Do NOT call `load_needs` here anymore.

- [ ] **Step 6: Fix references in chain tests.** If `test_dispatcher.py`/`test_dispatcher_field_map.py` build fixtures around a removed MR need id (e.g. `"debt_gdp"`), re-point them to `"stock_quote"` (they fabricate their own `CallableSpec`, so this is cosmetic). In `test_connectors_service.py`, update the `_upsert` test to assert a `RunnerCallableSpec(department_id="portfolio", need_id="stock_quote")` row is written on EODHD validation (was `macro_research`).

- [ ] **Step 7: GUARDRAIL.** Re-run the Step-1 guardrail set — all green (the chain resolves `stock_quote` under the `portfolio` namespace). Then `cd packages/core && uv run pytest tests/connectors/ -q`.

- [ ] **Step 8: Commit** — `refactor(connectors): trim runner_specs + need map to portfolio-only; drop needs.yaml`

---

## Phase 2 — Remove the dead department-runner + deterministic machinery

### Task 2: `requires_runner`, deterministic runtime mode, `deterministic.py`, health branch (core+server atomic)

**Files:**
- Core: `departments/health.py`, `departments/loader.py`, `departments/base.py`, the 7 dept files, `llm/runtime/deterministic.py` (delete).
- Server: `services/dept_health.py`, `services/runtime.py`.
- Tests: `packages/core/tests/departments/test_health.py`, `tests/departments/test_department_artifacts.py`, `tests/test_llm/test_runtime/test_deterministic.py` (delete), `packages/server/tests/test_services/test_runtime_entry.py`.

- [ ] **Step 1: Core `health.py`** — remove the `if dept.requires_runner:` branch, `_RunnerSpecLike`, the `runner_specs` param of `check_dept_health`, and `DepartmentHealth.unresolved_needs`. Keep category gating + `satisfied_categories`.
- [ ] **Step 2: Server `dept_health.py`** — remove the `select(RunnerCallableSpec)` query, the `runner_specs=` arg, and the `"unresolved_needs"` key in `serialize()`. Drop the `RunnerCallableSpec` import. (This is the atomic core+server signature change for health.)
- [ ] **Step 3: Server `runtime.py`** — remove `run_department`'s deterministic branch, the `requires_runner` logic in `select_runtime_mode`, and `"deterministic"` from the `RuntimeMode` literal (chat/scheduled_chat only; keep `UnknownDepartmentError`/`RuntimeModeMismatchError`).
- [ ] **Step 4: Delete `deterministic.py`** (`git rm`) + `tests/test_llm/test_runtime/test_deterministic.py`. Confirm no other importer: `grep -rn "runtime.deterministic\|fetch_mr_t1_data\|fetch_rs_social_posts\|parse_mr_requirement" packages --include=*.py | grep -v __pycache__`.
- [ ] **Step 5: `base.py`** — remove the `requires_runner` field from the `Department` protocol. **Dept files** — remove the `requires_runner` ClassVar from all 7 (`secretary`, `equity_research`, `earnings_update`, `morning_briefing`, `panic_thermometer`, `macro_research`, `retail_sentiment`).
- [ ] **Step 6: `loader.py`** — remove `load_needs` + the `Need` type (now unused: the health branch is gone, the drift test was rewritten in Task 1). Keep `load_routing_context`. Confirm: `grep -rn "load_needs\|import Need\b" packages --include=*.py | grep -v __pycache__` → empty.
- [ ] **Step 7: Tests** — `test_health.py`: drop the `unresolved_needs`/runner-gating cases (keep category + `satisfied_categories`). `test_department_artifacts.py`: drop `test_needs_yaml_present_when_runner_required`, `test_runner_referenced_ids_are_declared`, `test_declared_ids_are_referenced_by_runner` (keep `test_routing_context_*`). `test_runtime_entry.py`: drop the deterministic / synthetic-runner cases; keep chat/scheduled_chat/unknown-dept.
- [ ] **Step 8: GUARDRAIL + verify** — `cd packages/core && uv run pytest -q` (full core); `cd packages/server && uv run pytest tests/test_services/test_runtime_entry.py tests/test_routes/ -q`. Guardrail set still green.
- [ ] **Step 9: Commit** — `refactor(departments): remove requires_runner, deterministic runtime mode, deterministic.py`

---

## Phase 3 — Remove the interactive wizard resolution flow (server)

### Task 3: Delete wizard routes/services; keep `_upsert`/`build_dispatcher`/`sync_template_specs`

**Files:**
- Delete: `routes/runner_specs.py`, `services/runner_specs_service.py`, `services/resolver_save_flow.py`.
- Conditional: `services/template_upgrade.py` — **first check** whether the live `sync-template-specs` route or `_upsert` uses anything from it (`grep -rn "template_upgrade\|revert_to_default" packages/server/src --include=*.py | grep -v __pycache__`). If only the wizard used it, delete it; if `sync_template_specs`/the route uses `revert_to_default`, keep that function.
- Modify: `app.py` (router mounts + `hydrate_dept_registries()` call + `runner_specs_service.set_dept_health_hook` wiring — keep the `connectors_service` hook).
- Delete tests: `tests/test_routes_runner_specs.py`, `tests/test_routes_runner_specs_dept.py`, `tests/test_runner_specs_dept_service.py`, `tests/test_resolver_save_flow.py`, `tests/test_resolver_redesign_e2e.py`, `tests/e2e/test_python_lib_runner_activation.py`, `tests/e2e/test_atomic_disable_on_delete.py`, `tests/test_override_wins_upgrade.py` (if `template_upgrade` deleted).

- [ ] **Step 1: Inventory** — `grep -rn "runner_specs_service\|resolver_save_flow\|template_upgrade\|hydrate_dept_registries\|build_runner_specs_router\|build_dept_proposed_specs_router\|build_runner_specs_list_router\|propose_specs\|approve_spec\|save_user_picked_spec" packages/server/src --include=*.py | grep -v __pycache__`.
- [ ] **Step 2: Strip `app.py`** — remove the runner-specs router includes + imports, the `hydrate_dept_registries()` call, the `runner_specs_service.set_dept_health_hook(...)` line. KEEP everything connector/dispatcher/financial-adapter.
- [ ] **Step 3: Delete** the wizard route/service files + the listed tests. **Do NOT touch** `connectors_service._upsert_runner_specs_from_template` / `sync_template_specs`, `dispatcher_factory.build_dispatcher`/`_hydrate_spec`, `dispatch.fetch_need` — those are Portfolio's chain.
- [ ] **Step 4: GUARDRAIL + verify** — `cd packages/server && uv run pytest tests/test_routes/ tests/test_services/ tests/test_scheduler/ tests/e2e/ -q` (run from repo root for cwd-dependent migration tests). No import errors; guardrail green; only baseline reds (MB-lifespan, `mr_dashboard_cache` alembic drift, the pre-existing `test_value_series_returns_points`). Re-grep: remaining `runner_specs`/`RunnerCallableSpec` hits only in `connectors_service`/`dispatcher_factory`/`dept_health`(removed)/`db/models` — the KEEP set.
- [ ] **Step 5: Commit** — `refactor(connectors): delete interactive wizard need-resolution flow`

---

## Phase 4 — Frontend

### Task 4: Remove wizard resolve UI + proposed-spec api; keep `syncTemplateSpecs`/`covered_need_ids`

**Files:**
- Delete: `setup/steps/{ResolveStep,ResolveRow,SmokeFailurePanel,PerNeedReviewCard,DeptResolvePanel}.tsx` + their `__tests__`; `components/settings/admin/{RunnerCallableSpecsAdminPanel,ResolutionsAdminPanel}.tsx` + tests; `api/runner_specs.ts` (if present).
- Modify: the SetupWizard step sequence (drop the resolve step; `ReviewStep`/`FirstRunSummary` drop resolve/runner refs); `components/settings/sections/AdminSection.tsx` (drop the `runner-specs` tab) + its test; `pages/SettingsPage.tsx` (drop the route mount); `api/connectors.ts` (remove the proposed-spec block: `ProposedSpec`, `ResolveEvent`, `ApprovalOut`, `listProposedSpecs`, `reResolveSpecs`/`resolveProposedSpecs`, `approveSpec`, `listDeptProposedSpecs`, `resolveDeptProposedSpecs`, `listDeptResolveEvents`, `resolveDeptNeed`, `approveDeptSpec`) + its tests; `api/connectors.test.ts`, `setup/steps/__tests__/ConnectorsStep.test.tsx`; `api/departments.ts` (`RUNNER_BEARING_DEPARTMENTS`); `api/dept-health.ts` (`unresolved_needs`) + `components/sidebar/DeptDisabledBanner.tsx` + its test.
- **KEEP:** `api/connectors.ts` `syncTemplateSpecs` + `BuiltinTemplate.covered_need_ids`; `components/connectors/CatalogCard.tsx` need-count badge; `ConnectorsStep`/`ConnectorsSection` sync calls (the server route + `covered_need_ids` are retained by Phase 1/3).

- [ ] **Step 1: Inventory** — `grep -rn "ResolveStep\|ResolveRow\|SmokeFailurePanel\|PerNeedReviewCard\|DeptResolvePanel\|RunnerCallableSpecsAdminPanel\|ResolutionsAdminPanel\|ProposedSpec\|ResolveEvent\|listProposedSpecs\|approveSpec\|resolveDeptNeed\|approveDeptSpec\|RUNNER_BEARING\|unresolved_needs\|runner_specs" frontend/src`. Read the SetupWizard step wiring + `DeptDisabledBanner` + `AdminSection`.
- [ ] **Step 2: Re-wire the wizard** to advance without the resolve step (→ ReviewStep → FirstRunSummary); strip resolve/runner refs from ReviewStep/FirstRunSummary.
- [ ] **Step 3: Drop `unresolved_needs`** from `dept-health.ts` + `DeptDisabledBanner` (disabled reason from missing categories only) + fixtures.
- [ ] **Step 4: Remove the proposed-spec block** from `api/connectors.ts` (the list in Files above) + the matching `connectors.test.ts` cases + the dead mock entries in `ConnectorsStep.test.tsx`. KEEP `syncTemplateSpecs`/`covered_need_ids`.
- [ ] **Step 5: Delete** the UI files + tests; drop `RUNNER_BEARING_DEPARTMENTS`; drop the `runner-specs` admin tab in `AdminSection` + update `AdminSection.test.tsx`; drop the route mount in `SettingsPage`.
- [ ] **Step 6: Verify** — `cd frontend && npx tsc --noEmit` (clean) + `npm run test` (no NEW failures beyond the pre-existing SettingsShellBlocker global). Orphan grep (Step 1 terms minus the kept `syncTemplateSpecs`/`covered_need_ids`) → no live refs.
- [ ] **Step 7: Commit** — `refactor(connectors): remove wizard resolve UI + proposed-spec api (keep sync/covered_need_ids)`

---

## Phase 5 — DB

### Task 5: Drop `resolver_call_log` + `smoke_call_log`; keep `runner_callable_specs`

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-06-04-1300_drop_resolver_audit_tables.py`.
- Modify: `packages/server/src/openlia_server/db/models/connectors.py` (remove `ResolverCallLog`, `SmokeCallLog`; KEEP `Connector`, `RunnerCallableSpec`).
- Tests: `tests/test_db/test_resolver_redesign_schema.py` (delete or trim), `tests/test_db/test_migrations.py` (drop the 2 tables from `EXPECTED_TABLES`; keep `runner_callable_specs`).

- [ ] **Step 1: Confirm no live refs** — `grep -rn "ResolverCallLog\|SmokeCallLog\|resolver_call_log\|smoke_call_log" packages/server/src --include=*.py | grep -v __pycache__ | grep -v "db/models/connectors.py" | grep -v "migrations/"` → empty (wizard removed in Phase 3).
- [ ] **Step 2: Migration** — head via `uv run alembic heads`; `revision="drop_resolver_audit_tables"`. `upgrade()`: drop indexes + `drop_table("smoke_call_log")`, `drop_table("resolver_call_log")`. `downgrade()`: recreate both (copy column defs from `2026-05-02-0100_resolver_redesign_phase1.py` / `2026-05-02-0200_audit_log_orphan_friendly.py`). Do NOT touch `runner_callable_specs`.
- [ ] **Step 3: Remove the 2 models** from `connectors.py` (keep `RunnerCallableSpec`).
- [ ] **Step 4: Tests** — delete/trim `test_resolver_redesign_schema.py`; update `test_migrations.py` `EXPECTED_TABLES`.
- [ ] **Step 5: Verify** — `cd packages/server && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`; `uv run pytest tests/test_db/ -q`; autogenerate check shows no new drift for the dropped tables (only pre-existing `mr_dashboard_cache`).
- [ ] **Step 6: Commit** — `refactor(db): drop resolver_call_log + smoke_call_log (keep runner_callable_specs)`

---

## Phase 6 — Final sweep + verification + review

### Task 6: Orphan sweep + whole-branch verification + review

- [ ] **Step 1: Orphan sweep** — `grep -rn "requires_runner\|unresolved_needs\|load_needs\|\.needs\.yaml\|deterministic\|runner_specs_service\|resolver_save_flow\|ResolveStep\|RUNNER_BEARING\|propose_specs\|approve_spec\|ResolverCallLog\|SmokeCallLog" packages frontend/src --include=*.py --include=*.ts --include=*.tsx | grep -v __pycache__ | grep -v node_modules | grep -v migrations` → only unrelated "deterministic" comments. CONFIRM the KEEP set survives: `grep -rn "fetch_need\|RunnerCallableSpec\|_NEED_DEPARTMENT_MAP\|callable_specs\|_upsert_runner_specs\|sync_template_specs\|covered_need_ids" packages` returns the portfolio chain.
- [ ] **Step 2: Guardrail** — the resolution-chain tests green: `test_dispatcher.py`, `test_dispatcher_field_map.py`, `test_dispatcher_factory_substitutions.py`, `test_connectors_service.py`.
- [ ] **Step 3: Full** — `cd packages/core && uv run pytest -q`; `cd packages/server && uv run pytest tests/test_routes/ tests/test_services/ tests/test_scheduler/ tests/test_db/ tests/e2e/ -q` (repo root); `cd frontend && npx tsc --noEmit && npm run test`; `uv run ruff check .`.
- [ ] **Step 4: Red-count** — only the documented baseline reds remain (SettingsShellBlocker; MB-lifespan; `mr_dashboard_cache` alembic drift; the pre-existing `test_value_series_returns_points`). No NEW failures; the dead-path tests are gone.
- [ ] **Step 5: Review** — `feature-dev:code-reviewer` over `git diff main...HEAD`. Focus: Portfolio's resolution chain intact (validate→upsert→fetch_need for `stock_quote` under `portfolio`); no live code path lost; migration downgrade faithful; wizard removed without breaking connector setup (sync/covered_need_ids kept).

---

## Self-Review (plan author)

- **Spec coverage:** §4 KEEP+trim → Task 1 (+ chain untouched in 2/3); §5 REMOVE: deterministic/requires_runner/health → Task 2, wizard server → Task 3, frontend → Task 4, DB tables → Task 5; §6 namespace+needs.yaml-drop → Task 1; §9 verify → Task 6 + per-task guardrails.
- **Guardrail discipline:** every phase re-runs the resolution-chain tests; `test_value_series_returns_points` explicitly excluded as pre-existing red.
- **Importers-before-definitions:** drift test rewritten (Task 1) before `load_needs` removed (Task 2); wizard server deleted (Task 3) before its DB tables (Task 5); `health.py`+`dept_health.py` signature change atomic in Task 2; frontend stops calling removed routes (Task 4) — `syncTemplateSpecs`/`covered_need_ids` routes are KEPT so no frontend↔server drift.
- **KEEP set protected:** `_upsert`, `build_dispatcher`/`_hydrate_spec`, `fetch_need`/`callable_specs`/`CallableSpec`, `RunnerCallableSpec` table, `_NEED_DEPARTMENT_MAP`, `sync_template_specs`, `covered_need_ids` — none removed; only trimmed/re-keyed.
- **Destructive step:** Task 5 drops 2 audit tables (recreating downgrade); no live reader/writer.

## Execution Handoff

**Subagent-Driven (recommended)** — fresh subagent per task, controller verifies via diff + the guardrail set, final whole-branch review. Or **Inline.** Which approach?
