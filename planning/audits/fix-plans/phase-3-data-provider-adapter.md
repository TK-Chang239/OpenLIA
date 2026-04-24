# Phase 3 — Data Provider Adapter fix plan (→ 100%)


**Current:** ~95% vs. plan; ~55% vs. spec. **Root cause:** SPEC_DRIFT — plan deliberately shrank the spec's surface (catalog system, AI review, dispatch router, MCP client, Python-provider shim, Retail-Sentiment availability checker were all pushed off).

**Gap summary:** Plan-scoped work is nearly complete (manifest, EODHD adapter, resolver, `/settings/data-providers/*` CRUD, `auto_map`, `test-connection`). Against the spec, whole subsystems are absent: `catalog/`, `review/`, `dispatch/`, `python_providers/`, `sentiment/`. The `company_fundamentals` deferral and an un-shipped LLM-based auto-map review are the two plan-side stragglers.

**Tasks (in execution order):**

1. **Deferred-company-fundamentals — Ship EODHD `company_fundamentals` capability.**
   - Files: `packages/core/src/openlia/data/adapters/eodhd.py:80-110` (extend), `packages/core/src/openlia/data/manifest/requirements.yaml:28` (already lists the type — align adapter `declared_capabilities`).
   - Plan ref: Task 8 "EODHD adapter (4 capabilities)" — originally deferred.
   - Spec ref: `data-provider-design.md` §"Department Data Access Patterns".
   - Acceptance: `test_eodhd_adapter.py::test_company_fundamentals_capability` green against a respx fixture.

2. **NEW-3-01 — Ship `catalog` + `review` + `dispatch` + `python_providers` + `sentiment` stubs per spec file layout.** Why new: tracker treats spec drift as out-of-scope; this closes the spec-vs-impl gap explicitly.
   - Files: create `packages/core/src/openlia/data/catalog/__init__.py`, `…/review/__init__.py`, `…/dispatch/__init__.py`, `…/python_providers/__init__.py`, `…/sentiment/__init__.py`, each exporting `NotImplementedError`-raising stubs.
   - Spec ref: `data-provider-design.md` "Complete File Layout", "Placeholder Files Summary".
   - Acceptance: `from openlia.data import catalog, review, dispatch, python_providers, sentiment` succeeds.

3. **NEW-3-02 — Document the spec-vs-plan split in an amendment header.** Why new: Phase 17 made the same mistake; add a "Deferred from v1 — see Phase N+" box at the top of `data-provider-design.md` enumerating which spec sections are NOT in phase-3 scope.
   - Files: `planning/specs/systems/data-provider-design.md` (prepend an "Implementation Status" section).
   - Acceptance: coordinator review signs off on the deferred list.

4. **NEW-3-03 — Audit `auto_map` to confirm it matches the plan's heuristic mode (not the spec's LLM-driven review mode).**
   - Files: `packages/server/src/openlia_server/services/data_providers.py` (audit), `routes/settings.py:125-130` (audit docstring).
   - Plan ref: Tasks 11, 14.
   - Spec ref: `data-provider-design.md` §"AI Review".
   - Acceptance: docstrings say "heuristic mapping, not LLM review — see deferred spec"; no code imports from `openlia.data.review`.

**Verification:** `uv run pytest packages/core/tests/test_data/ packages/server/tests/test_routes/test_settings_data_providers*.py -v` green; manual `python -c "import openlia.data.catalog, openlia.data.review, openlia.data.dispatch"` succeeds.
