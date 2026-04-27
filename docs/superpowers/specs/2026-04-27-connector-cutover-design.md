# Connector Cutover — Design Spec

**Date:** 2026-04-27
**Status:** Approved for implementation planning
**Companion:** `docs/superpowers/specs/2026-04-26-connector-redesign-design.md` (the additive-system spec; this doc covers the cutover that follows it)
**Audit:** `docs/superpowers/specs/2026-04-26-data-deletion-audit.md`
**Branch context:** PR #79 landed Phases A-G + H1 of the original plan. This doc plans Phases H2-H11, executed as a single follow-up PR.

## 1. Why

PR #79 added a complete connector subsystem alongside the legacy `openlia.data` layer. Both work; nothing is wired together at runtime yet. This cutover removes the legacy layer, wires every department through the new `Dispatcher`, and finishes the architectural goal of one tool-routing seam.

## 2. Goals

- One tool-routing seam: `connectors.dispatch.Dispatcher`. Every department, every tool call, every web search.
- No `openlia.data` package, no `data_providers` tables, no `ToolDispatcher` legacy runtime, no `_DataProvider` Protocols.
- Encrypted credentials live on the Connector row, rotatable through the existing CLI flow.
- Day-1 built-in catalog (EODHD, FMP, NewsAPI.ai) ships with curated tool→department allowlists.
- Single PR. Scope is large but coherent: the cutover is one unit of work, not a sequence of half-states.

## 3. Non-goals

- LLM-runtime modernization beyond what the Dispatcher unification requires.
- Adding new department capabilities or new connector providers beyond the day-1 catalog.
- A rich `connector_secrets` schema. The encrypted blob lives on the Connector row.
- Re-architecting the Retail Sentiment classifier. It keeps its typed input contract; a thin parsing layer feeds it.

## 4. Decision log

| Decision | Choice | Rationale |
|---|---|---|
| α1 — Where do credentials live? | **A: column on Connector row.** `api_key_encrypted: Text \| None`. AES-256-GCM with row id as AAD, mirroring `LLMProvider`/`WebSearchProvider`. | Existing rotation code already walks tables of this shape. Inventing a separate secret store solves no problem we have. |
| α2 — Two dispatchers (ToolDispatcher vs Dispatcher) | **B: unify on `Dispatcher`.** Delete `openlia.llm.runtime.tools.ToolDispatcher` and its `DataProviderDispatcher` Protocol. | Project is pre-1.0; one tool-routing seam end-to-end is the redesign's goal. Adapter shim would freeze the asymmetry. |
| α3 — MR/RS typed `_DataProvider` Protocol | **B: refactor runners onto Dispatcher.** Drop `app.state.{mr,rs}_data_provider`. Runners consume the Dispatcher directly. | Same homogenization argument as α2. Acceptable cost given pre-1.0 state. |
| α4 — Web search Python callable | **A: factories take Dispatcher.** Drop the search-callable abstraction. | Same seam, no shim. |
| H4 — Classifier input shape (RS) | **tight.** Classifier keeps its typed input. A thin JSON-to-typed parser sits between Dispatcher output and the classifier. | RS classifier is recently-rewritten and stable; full refactor is unnecessary work. The parser is small and lives at a real boundary (untrusted JSON → trusted internal shape). |
| PR shape | **single PR.** | The cutover is incoherent in pieces — half-migrated runtime is worse than no migration. |

## 5. Domain changes

### 5.1 Connector model gains an encrypted credential column

Migration `2026-04-27-XXXX_connector_secrets.py`:
- Adds `api_key_encrypted: Text NULL` to `connectors`.
- Backfill: existing rows (from PR #79 dev databases) are nullable; not load-bearing in production yet.

ORM gets the column + helpers `encrypt_credential(plaintext)` / `decrypt_credential()` mirroring the pattern in `db/models/config.py::LLMProvider` and `WebSearchProvider`. The `credentials_ref: str` field defined in the redesign spec is dropped — it was a placeholder for an abstraction we walked away from.

### 5.2 Dispatcher becomes the single tool seam

Today: department runners consume a `ToolDispatcher` whose `.build()` produces `tools=[...]` for `messages.create()` and routes `tool_use` callbacks. `ToolDispatcher` consumes a `DataProviderDispatcher` Protocol — itself a pluggable shape.

After: department runners consume `connectors.dispatch.Dispatcher` directly. `Dispatcher.tools_for_department(dep_id)` produces the tool list; `Dispatcher.dispatch_tool_use(name, args)` routes the callback. `ToolDispatcher` and `DataProviderDispatcher` cease to exist.

Web search becomes a normal connector category (`web_search`). When a runner needs search, it pulls tools from the Dispatcher's web_search-category connectors via the same `tools_for_department` plumbing. The `_resolve_search_provider` helper in `services/runtime.py` becomes a thin "include web_search tools in the dispatcher payload for this run" flag.

### 5.3 Macro Research and Retail Sentiment runners

Both currently take a domain-specific `_DataProvider` Protocol via `app.state.{mr,rs}_data_provider`. After the cutover:

- `MacroResearchRunner.__init__(...)` drops the `data_provider` parameter; takes `dispatcher: Dispatcher` instead. Internal calls switch from `data_provider.get_macro_indicator(...)` to `await dispatcher.dispatch_tool_use("eodhd__get_macro_indicator", {...})`. The dashboard assembler (`macro_research/assembler.py`) follows suit.
- `RetailSentimentRunner.__init__(...)` same change. The classifier (per H4.tight) keeps its typed input — a small `RSDispatcherAdapter` parses raw Dispatcher JSON into `RetailSentimentSnapshot` (or equivalent) before handing off to the classifier.
- `mr_assessment.py::MRAssessmentBuilderImpl(...)` same change.
- The `_DataProvider` Protocols in those modules are deleted.
- `app.state.mr_data_provider` and `app.state.rs_data_provider` are deleted from `app.py`'s factory wiring.

### 5.4 CLI updates

`packages/server/src/openlia_server/cli.py`:

- `wizard reset --purge` (lines ~763-786): swap `DataProvider` references for `Connector`. Cascade now drops `ToolAllowlist` rows automatically via the FK.
- `secrets` and `secrets rotate-key` (lines ~805-808, 894-898): the rotation loop iterates `(LLMProvider, Connector, WebSearchProvider)` instead of `(LLMProvider, DataProvider, WebSearchProvider)`.

## 6. Step sequence (single PR, ordered commits)

```
H2  feat(db): add api_key_encrypted to connectors
      Migration + ORM column + encrypt/decrypt helpers + tests.

H3  refactor(runtime): unify on connectors.Dispatcher (α2 + α4)
    H3a  Move ToolDispatcher consumers off DataProviderDispatcher onto Dispatcher.
         Each department runner that uses ToolDispatcher.build() switches.
    H3b  Delete ToolDispatcher and DataProviderDispatcher.
    H3c  Refactor build_chat_runner / build_batch_runner / build_report_runner factories
         in services/runtime.py to take a Dispatcher reference instead of a search callable.

H4  refactor(mr,rs): consume Dispatcher (α3 + H4.tight)
    H4a  MacroResearchRunner + DashboardAssembler take Dispatcher; tool calls go through it.
    H4b  RetailSentimentRunner takes Dispatcher; new RSDispatcherAdapter parses JSON
         into the classifier's typed input.
    H4c  Drop _DataProvider Protocols + app.state.{mr,rs}_data_provider wiring.

H5  feat(connectors): curated day-1 allowlists
    Replace stub ShippedAssignment tuples in builtins/{eodhd,fmp,newsapi_ai}.py
    with hand-curated mappings authored against vendor docs.

H6  refactor(server): delete legacy provider services
    Delete services/data_providers.py, wizard_providers.py, wizard_review.py
    and their tests.

H7  refactor(server): delete legacy provider routes
    Delete build_data_providers_router and the eight /api/setup/providers/*
    + /api/setup/review/* endpoints in setup.py. Update app.py mount list.

H8  refactor(frontend): delete legacy provider UI
    Delete frontend/src/api/data_providers.ts, the DataProvidersAdminPanel,
    its test, and the dead exports in api/setup.ts. SettingsPage route
    cleanup.

H9  refactor: delete openlia.data
    git rm -r packages/core/src/openlia/data and the matching test directory.
    Verify zero remaining importers via grep.

H10 feat(db): drop data_providers tables
    Migration drops data_providers + data_provider_requirement_mapping.
    Remove DataProvider and DataProviderRequirementMapping ORM classes.
    CLI updates from §5.4. Update test_baseline_upgrade_creates_all_tables's
    EXPECTED_TABLES set.

H11 docs: retire data-provider-design.md
    Delete the spec; sweep planning/specs for stale references.
```

H2 is foundation. H3+H4+H5 are the real work. H6 onward is mechanical because nothing imports the deleted code anymore.

## 7. Test strategy

- **Existing tests.** Every test that constructs `_DataProvider` Protocol implementations gets either deleted (along with the production code) or rewritten against the Dispatcher-backed equivalent. Audit §G enumerates the list.
- **New tests for H3/H4.** Each refactored runner gets a unit test that verifies it asks the Dispatcher for tools and routes `tool_use` back through it. Mock Dispatcher; verify call shapes.
- **Integration test.** A single end-to-end test in `packages/server/tests/test_e2e_connector_dispatch.py`: build a fake Dispatcher with one connector, two tools; invoke a department runner; verify the LLM-call payload includes the prefixed tools and that a tool_use response routes to the fake transport. Replaces the legacy ai-review e2e.
- **Migration tests.** H2 migration test: upgrade adds the column. H10 migration test: upgrade drops the tables, downgrade refuses. Both tested via the existing `test_migrations.py` pattern.
- **Smoke.** Full `uv run pytest` and `npm test -- --run` must be green before merge. No skipped tests.

## 8. Rollout and risk

- **Single PR.** Scope is large (~30-40 commits) but the alternative — staged PRs through a half-migrated runtime — is worse. Reviewers can use the commit-by-commit history; the audit doc is the map.
- **Migration ordering.** H2 (add column) must land before any production install upgrades. H10 (drop tables) is irreversible; it's the last DB change in the PR.
- **No backwards compatibility shims.** This is a pre-1.0 codebase; existing dev databases are wiped. Production installs (if any) require a planned cutover, not zero-downtime.
- **Highest-risk steps:** H3a (dispatcher consumer migration — touches every department runner) and H4b (RS classifier adapter — the parser layer needs to faithfully produce the classifier's expected shape from real JSON). Both get extra test coverage.

## 9. What this PR does *not* unlock

- Real production use against live MCP servers. The day-1 built-ins assume MCP servers exist for EODHD, FMP, NewsAPI.ai (`uvx <name>-mcp-server`). Validation that those packages exist and behave is a follow-up.
- The full smoke test from the original plan's I3 — manual wizard walkthrough with real keys — should follow the cutover, not gate it.

## 10. Open items

- Curating the day-1 allowlists (H5) is judgment-heavy authoring work. The implementer reads each provider's tool list, maps each tool to zero or more departments based on the prose requirements YAMLs from PR #79. Review by the user before merge.
- The `RSDispatcherAdapter` in H4b needs the current classifier input shape pinned down before the JSON parser is written. Either inspect the classifier's input dataclass directly or write the test first and grow the parser to satisfy it (TDD).
