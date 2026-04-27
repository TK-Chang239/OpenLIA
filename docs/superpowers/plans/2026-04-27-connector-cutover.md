# Connector Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate every department runner onto `connectors.dispatch.Dispatcher`, then delete `openlia.data`, the `data_providers` tables, the legacy provider services/routes/UI, and the legacy LLM-runtime tool dispatcher.

**Architecture:** Unify on `connectors.dispatch.Dispatcher` as the single tool-routing seam. Encrypted credentials live on the `connectors` row (column `api_key_encrypted`), rotated via the existing CLI flow. Macro Research and Retail Sentiment runners drop their typed `_DataProvider` Protocols; the RS classifier keeps its typed input via a small JSON-parsing adapter. Web search becomes a normal connector category dispatched through the same seam.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x + Alembic, MCP Python SDK, anthropic SDK, pytest, React + TypeScript + Vitest, uv, ruff.

**Spec:** `docs/superpowers/specs/2026-04-27-connector-cutover-design.md` (commit `8c78f8d`).
**Companion audit:** `docs/superpowers/specs/2026-04-26-data-deletion-audit.md` (commit `2a1423e` on the PR #79 branch).
**Predecessor PR:** #79 (additive connector subsystem, branch `refactor/connector-redesign`).

**Working notes:**
- Branch off main once PR #79 is merged: `git checkout -b refactor/connector-cutover`.
- All Python tests run with `uv run pytest`. Lint with `uv run ruff check .` and format with `uv run ruff format .` after every task before commit.
- Frontend tests run with `cd frontend && npm test -- --run`. Lint with `npm run lint`.
- Each task is its own commit. Conventional Commit prefixes.
- Phase H is destructive. Run the full test suite (`uv run pytest && cd frontend && npm test -- --run`) at the end of every step. The legacy and new code paths cannot coexist mid-step except where explicitly noted.
- Pre-existing dev databases (`.openlia.dev.db`) get wiped during this PR; the project is pre-1.0 and there is no compatibility shim for legacy `data_providers` rows.

**Reading order for the implementer:**
1. The cutover design doc above.
2. The audit at `docs/superpowers/specs/2026-04-26-data-deletion-audit.md` (lists every consumer file by bucket).
3. `CLAUDE.md` for boundary rules (core never imports FastAPI, etc.) and lint/format requirements.
4. The existing PR #79 code: `packages/core/src/openlia/connectors/`, `packages/server/src/openlia_server/services/connectors_service.py`, the new routes.

---

## Step H2 — Add `api_key_encrypted` column to `connectors`

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-27-XXXX_connector_secrets.py`
- Modify: `packages/server/src/openlia_server/db/models/connectors.py`
- Test: `packages/server/tests/test_db_models_connectors.py` (extend existing file)

### Task H2.1 — Migration

- [ ] **Step 1: Locate previous head**
  ```bash
  uv run alembic -c packages/server/alembic.ini current
  ```
  Use that as `down_revision`.

- [ ] **Step 2: Write migration**

  ```python
  """Add api_key_encrypted to connectors.

  See docs/superpowers/specs/2026-04-27-connector-cutover-design.md §5.1.
  Mirrors LLMProvider/WebSearchProvider; AES-256-GCM with row id as AAD,
  applied at the ORM layer (encrypt_credential / decrypt_credential).
  """

  from __future__ import annotations
  from collections.abc import Sequence

  import sqlalchemy as sa
  from alembic import op

  revision: str = "20260427_XXXX_connector_secrets"
  down_revision: str | Sequence[str] | None = "<HEAD>"
  branch_labels: str | Sequence[str] | None = None
  depends_on: str | Sequence[str] | None = None


  def upgrade() -> None:
      with op.batch_alter_table("connectors", schema=None) as batch_op:
          batch_op.add_column(sa.Column("api_key_encrypted", sa.Text(), nullable=True))


  def downgrade() -> None:
      with op.batch_alter_table("connectors", schema=None) as batch_op:
          batch_op.drop_column("api_key_encrypted")
  ```

- [ ] **Step 3: Verify upgrade and downgrade**

  ```bash
  rm -f .openlia.dev.db
  uv run alembic -c packages/server/alembic.ini upgrade head
  uv run python -c "import sqlite3; c=sqlite3.connect('.openlia.dev.db'); cols=[r[1] for r in c.execute('PRAGMA table_info(connectors)')]; assert 'api_key_encrypted' in cols, cols; print('OK')"
  uv run alembic -c packages/server/alembic.ini downgrade -1
  uv run alembic -c packages/server/alembic.ini upgrade head
  ```

- [ ] **Step 4: Update `EXPECTED_TABLES`** — N/A (no new tables, existing test still passes).

- [ ] **Step 5: Lint, commit**

  ```bash
  uv run ruff format packages/server/src/openlia_server/db/migrations/versions/2026-04-27-XXXX_connector_secrets.py
  uv run ruff check packages/server/src/openlia_server/db/migrations/versions/2026-04-27-XXXX_connector_secrets.py
  git add packages/server/src/openlia_server/db/migrations/versions/2026-04-27-XXXX_connector_secrets.py
  git commit -m "feat(db): add api_key_encrypted to connectors"
  ```

### Task H2.2 — ORM column + encrypt/decrypt helpers

- [ ] **Step 1: Read the pattern**
  ```bash
  grep -n "api_key_encrypted\|encrypt_credential\|decrypt_credential" packages/server/src/openlia_server/db/models/config.py
  ```
  The `LLMProvider` and `WebSearchProvider` classes show the existing pattern. Mirror it on `Connector`.

- [ ] **Step 2: Write the failing test (extend `test_db_models_connectors.py`)**

  ```python
  def test_connector_credential_round_trip(engine):
      from openlia_server.db.models.connectors import Connector

      cid = "test-cred-id"
      with Session(engine) as s:
          row = Connector(
              id=cid,
              provider_id="eodhd",
              source="built_in",
              category="financial",
              launch={"kind": "built_in", "template_id": "eodhd"},
              status="validated",
          )
          row.set_credential("super-secret-key")
          s.add(row)
          s.commit()
          loaded = s.query(Connector).filter_by(id=cid).one()
          assert loaded.api_key_encrypted is not None
          assert loaded.api_key_encrypted != "super-secret-key"  # encrypted
          assert loaded.get_credential() == "super-secret-key"


  def test_connector_credential_aad_binds_to_row(engine):
      """Ciphertext from one row cannot be decrypted as another row."""

      from openlia_server.db.models.connectors import Connector

      with Session(engine) as s:
          row_a = Connector(
              id="a", provider_id="eodhd", source="built_in", category="financial",
              launch={"kind": "built_in", "template_id": "eodhd"}, status="validated",
          )
          row_a.set_credential("secret-a")
          s.add(row_a)
          s.commit()

          # Copy ciphertext into row b
          row_b = Connector(
              id="b", provider_id="fmp", source="built_in", category="financial",
              launch={"kind": "built_in", "template_id": "fmp"}, status="validated",
              api_key_encrypted=row_a.api_key_encrypted,
          )
          s.add(row_b)
          s.commit()

          with pytest.raises(Exception):  # InvalidTag or wrapped
              row_b.get_credential()
  ```

- [ ] **Step 3: Run, observe failure (no `set_credential` method).**

- [ ] **Step 4: Add column + methods to `Connector`**

  Read the existing helpers in `LLMProvider` to find the exact import path for `encrypt_credential` / `decrypt_credential` (likely `openlia_server.db.crypto`). Then on `Connector`:

  ```python
  api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

  def set_credential(self, plaintext: str | None) -> None:
      if plaintext is None:
          self.api_key_encrypted = None
          return
      self.api_key_encrypted = encrypt_credential(plaintext, aad=self.id.encode())

  def get_credential(self) -> str | None:
      if self.api_key_encrypted is None:
          return None
      return decrypt_credential(self.api_key_encrypted, aad=self.id.encode())
  ```

- [ ] **Step 5: Run tests, expect green; lint; commit**

  ```bash
  uv run pytest packages/server/tests/test_db_models_connectors.py -v
  uv run ruff format packages/server/src/openlia_server/db/models/connectors.py packages/server/tests/test_db_models_connectors.py
  uv run ruff check packages/server/src/openlia_server/db/models/connectors.py packages/server/tests/test_db_models_connectors.py
  git add packages/server/src/openlia_server/db/models/connectors.py packages/server/tests/test_db_models_connectors.py
  git commit -m "feat(connectors): encrypted credentials on Connector row"
  ```

### Task H2.3 — Wire encryption through the create-connector route

- [ ] **Step 1: Update `connectors_service.create_connector`** to call `row.set_credential(...)` when the request body contains a credential. Drop the unused `credentials_ref` field from the DTO.

- [ ] **Step 2: Update `ConnectorCreate` DTO** to take an `api_key: str | None` field instead of `credentials_ref`.

- [ ] **Step 3: Extend the route test** to verify encryption round-trips end-to-end.

- [ ] **Step 4: Run tests, lint, commit**

  ```bash
  uv run pytest packages/server/tests/test_routes_connectors.py -v
  git add packages/server/src/openlia_server/services/connectors_service.py packages/server/src/openlia_server/routes/connectors.py packages/server/tests/test_routes_connectors.py
  git commit -m "feat(server): wire api_key encryption through POST /api/connectors"
  ```

---

## Step H3 — Unify on `connectors.dispatch.Dispatcher`

This is the largest behavioral step. Existing department runners go through `openlia.llm.runtime.tools.ToolDispatcher`. After H3, they go through `openlia.connectors.dispatch.Dispatcher`. `ToolDispatcher` and its `DataProviderDispatcher` Protocol are deleted.

### Task H3.1 — Inventory ToolDispatcher consumers

**Files:** investigative only.

- [ ] **Step 1: Find every caller**

  ```bash
  grep -rn "ToolDispatcher\|DataProviderDispatcher" packages | tee /tmp/td_consumers.txt
  ```

- [ ] **Step 2: For each caller, note:**
  - File + function.
  - What the caller does with the produced `tools=[...]` list and the `tool_use` callback path.
  - Whether the caller will gain a `Dispatcher` reference in its constructor or via factory injection.

- [ ] **Step 3: Save the inventory** as a comment block at the top of `services/runtime.py` (the central wiring file). This becomes the migration map for H3.2.

### Task H3.2 — Build a `Dispatcher` hydration helper

The runtime needs to construct a `Dispatcher` from VALIDATED `Connector` rows + `ToolAllowlist` rows + cached tool lists + a transport per connector.

**Files:**
- Create: `packages/server/src/openlia_server/services/dispatcher_factory.py`
- Test: `packages/server/tests/test_dispatcher_factory.py`

- [ ] **Step 1: Failing test**

  ```python
  def test_build_dispatcher_loads_validated_connectors(db_session):
      """Builds a Dispatcher from VALIDATED connectors with cached tools and allowlists."""

      # Seed: one VALIDATED connector with cached tools, one allowlist row.
      ...
      dispatcher = build_dispatcher_for_session(db_session)

      out = dispatcher.tools_for_department("equity_research")
      assert any(t["name"].startswith("eodhd__") for t in out)


  def test_build_dispatcher_skips_failed_connectors(db_session):
      ...


  def test_build_dispatcher_uses_default_session_factory(db_session, monkeypatch):
      """The factory wires connectors with the real default_session_factory."""

      ...
  ```

- [ ] **Step 2: Implement**

  ```python
  """Build a runtime Dispatcher from DB state.

  Reads VALIDATED connectors, their cached tool lists, and the allowlist
  rows; constructs a transport per connector via default_session_factory;
  returns a hydrated Dispatcher ready for runtime use.
  """

  from __future__ import annotations

  from sqlalchemy.orm import Session

  from openlia.connectors.dispatch import Dispatcher, PreparedConnector
  from openlia.connectors.mcp_transport import MCPTransport, default_session_factory
  from openlia.connectors.types import ConnectorStatus, MCPLaunchSpec, ToolDefinition
  from openlia_server.db.models.connectors import Connector, ToolAllowlist


  def build_dispatcher_for_session(session: Session) -> Dispatcher:
      conns = (
          session.query(Connector)
          .filter(Connector.status == ConnectorStatus.VALIDATED.value)
          .all()
      )
      prepared: dict[str, PreparedConnector] = {}
      for c in conns:
          tools = {
              t["name"]: ToolDefinition(
                  name=t["name"], description=t.get("description", ""), input_schema=t.get("input_schema", {})
              )
              for t in (c.cached_tools or [])
          }
          # Resolve BUILT_IN to its CLI form before constructing the transport.
          spec = MCPLaunchSpec.from_json(c.launch)
          # ... (delegate to a helper that handles BUILT_IN → CLI resolution; reuse from
          # services.connectors_service._resolve_launch_for_validation)
          transport = MCPTransport(spec=resolved_spec, session_factory=default_session_factory)
          prepared[c.id] = PreparedConnector(
              connector_id=c.id, provider_id=c.provider_id, transport=transport, tools=tools,
          )
      allowlist: dict[str, list[tuple[str, str]]] = {}
      for row in session.query(ToolAllowlist).all():
          allowlist.setdefault(row.department_id, []).append((row.connector_id, row.tool_name))
      return Dispatcher(connectors=prepared, allowlist=allowlist)
  ```

- [ ] **Step 3: Tests pass; lint; commit**

### Task H3.3 — Migrate runtime tool assembly off ToolDispatcher (per-runner)

For each ToolDispatcher consumer identified in H3.1, perform the migration in its own commit:

- Replace the `ToolDispatcher` parameter with a `Dispatcher` parameter (or pull from `app.state` / a factory).
- Replace `tool_dispatcher.build(department_id=..., has_web_search=...)` with `dispatcher.tools_for_department(department_id)` (web search becomes a separate inclusion via the dispatcher's allowlist for `web_search`-category connectors).
- Replace the `tool_use` routing through `tool_dispatcher.route(...)` with `await dispatcher.dispatch_tool_use(name, args)`.
- Update the runner's tests to construct a fake `Dispatcher` instead of a fake `ToolDispatcher`.

Each commit message: `refactor(runtime): <runner> consumes Dispatcher`.

### Task H3.4 — Delete ToolDispatcher

- [ ] **Step 1: Confirm no consumers remain**

  ```bash
  grep -rn "ToolDispatcher\|DataProviderDispatcher" packages
  # Expected: zero matches in non-test code.
  ```

- [ ] **Step 2: Delete**

  ```bash
  git rm packages/core/src/openlia/llm/runtime/tools.py
  ```

  Update `packages/core/src/openlia/llm/runtime/__init__.py` to drop `ToolDispatcher` and `DataProviderDispatcher` from re-exports.

  Delete the matching test file (`packages/core/tests/test_llm/test_runtime/test_tool_dispatcher.py` or equivalent) and the test fakes (`packages/core/tests/test_llm/test_runtime/_fakes.py::FakeRequirementDispatcher`).

- [ ] **Step 3: Run full suite; commit**

  ```bash
  uv run pytest
  git add -A packages/core
  git commit -m "refactor(runtime): delete ToolDispatcher; Dispatcher is the single seam"
  ```

### Task H3.5 — Refactor runner factories (α4 — web search)

`services/runtime.py::build_chat_runner / build_batch_runner / build_report_runner` currently take a search-callable. Replace with a `Dispatcher` reference. When a runner needs web search, it asks the Dispatcher for the same department's tools — the `web_search`-category connectors are already in the allowlist if the user added one.

- [ ] **Step 1: Failing test** — verify `build_chat_runner(dispatcher=...)` produces a runner whose tool list includes `web_search` connector tools when present.

- [ ] **Step 2: Refactor** the three factories. Drop the search-callable parameter. Tests update.

- [ ] **Step 3: Update `app.py`** to pass a Dispatcher (constructed lazily per request via `build_dispatcher_for_session`) instead of constructing a search-callable.

- [ ] **Step 4: Commit**: `refactor(runtime): factories take Dispatcher; drop search-callable abstraction`.

---

## Step H4 — Refactor MR and RS off `_DataProvider` Protocol

### Task H4.1 — MacroResearchRunner + DashboardAssembler

**Files:**
- Modify: `packages/server/src/openlia_server/services/mr_runner.py`
- Modify: `packages/server/src/openlia_server/services/mr_assessment.py`
- Modify: `packages/core/src/openlia/macro_research/assembler.py`
- Modify: `packages/server/src/openlia_server/app.py` (drop `app.state.mr_data_provider`)

- [ ] **Step 1: Read the existing `_DataProvider` Protocol**
  ```bash
  grep -n "_DataProvider\|class.*Protocol" packages/core/src/openlia/macro_research/assembler.py packages/server/src/openlia_server/services/mr_runner.py packages/server/src/openlia_server/services/mr_assessment.py
  ```
  Note every method on the Protocol — these are the calls that need to map to MCP tool calls.

- [ ] **Step 2: Failing test** — write a unit test that constructs `MacroResearchRunner(dispatcher=fake_dispatcher)`, runs a small query, asserts `fake_dispatcher.dispatch_tool_use` was called with the expected `eodhd__<tool_name>`.

- [ ] **Step 3: Refactor**

  - `MacroResearchRunner.__init__` drops `data_provider`; takes `dispatcher: Dispatcher`.
  - Each former `data_provider.<method>(...)` call becomes `await dispatcher.dispatch_tool_use("eodhd__<tool_name>", {...})`. JSON parsing happens inline; no typed shape.
  - `DashboardAssembler` follows the same shape change.
  - `MRAssessmentBuilderImpl(data_provider=…)` becomes `MRAssessmentBuilderImpl(dispatcher=…)`.

- [ ] **Step 4: Delete the local `_DataProvider` Protocol** in each file.

- [ ] **Step 5: Update `app.py`** — drop the `app.state.mr_data_provider` assignment + any factory wiring that produced it. Replace with `app.state.dispatcher_factory = build_dispatcher_for_session` (or pass through whatever request-scope helper is already established).

- [ ] **Step 6: Run all MR tests, lint, commit**

  ```bash
  uv run pytest packages/server/tests/test_macro_research/ packages/core/tests/test_macro_research/ -v
  git commit -m "refactor(mr): MacroResearchRunner + DashboardAssembler consume Dispatcher"
  ```

### Task H4.2 — RetailSentimentRunner + RSDispatcherAdapter

**Files:**
- Modify: `packages/server/src/openlia_server/services/rs_runner.py`
- Create: `packages/server/src/openlia_server/services/rs_dispatcher_adapter.py`
- Modify: `packages/server/src/openlia_server/app.py` (drop `app.state.rs_data_provider`)

The classifier (per H4.tight) keeps its typed input. The new `RSDispatcherAdapter` calls the Dispatcher and parses raw JSON into the shape the classifier expects.

- [ ] **Step 1: Pin down the classifier's input shape** — read the classifier's input dataclass / TypedDict definition. Capture every required field.

- [ ] **Step 2: Failing test for `RSDispatcherAdapter`** — given a fake Dispatcher returning a known JSON payload, the adapter should produce a `RetailSentimentSnapshot` (or whatever the actual shape is named) populated correctly.

- [ ] **Step 3: Implement `RSDispatcherAdapter`**

  ```python
  """Parses Dispatcher JSON output into the classifier's typed input.

  Lives at the boundary between untrusted MCP JSON and trusted internal
  shapes. Every field the classifier requires has a corresponding parse
  step here. If the JSON is malformed, raise — do not return partial.
  """

  from __future__ import annotations
  from typing import Any
  from openlia.connectors.dispatch import Dispatcher
  # ... import the typed shape


  class RSDispatcherAdapter:
      def __init__(self, dispatcher: Dispatcher) -> None:
          self._dispatcher = dispatcher

      async def fetch_snapshot(self, ticker: str) -> "RetailSentimentSnapshot":
          raw = await self._dispatcher.dispatch_tool_use(
              "<provider>__<sentiment_tool>", {"ticker": ticker}
          )
          return self._parse(raw)

      def _parse(self, raw: dict[str, Any]) -> "RetailSentimentSnapshot":
          # Validate every required field; raise ValueError with context on missing.
          ...
  ```

- [ ] **Step 4: Refactor `RetailSentimentRunner`** to take `RSDispatcherAdapter` instead of the typed `_DataProvider`. The classifier itself is unchanged.

- [ ] **Step 5: Delete the local `_DataProvider` Protocol** in `rs_runner.py`.

- [ ] **Step 6: Update `app.py`** — drop `app.state.rs_data_provider`.

- [ ] **Step 7: Run RS tests, lint, commit**

  ```bash
  uv run pytest packages/server/tests/test_services/test_rs_runner.py packages/server/tests/test_services/test_rs_classification_log.py -v
  git commit -m "refactor(rs): RetailSentimentRunner consumes Dispatcher via RSDispatcherAdapter"
  ```

### Task H4.3 — Drop `app.state.{mr,rs}_data_provider`

After H4.1 and H4.2 land, both wirings are gone. Verify by greppping:

```bash
grep -rn "mr_data_provider\|rs_data_provider" packages
# Expected: zero matches.
```

If non-zero, those are stragglers — delete them. Then a small commit: `chore: remove dead app.state.{mr,rs}_data_provider wiring` (often empty if H4.1/H4.2 caught everything).

---

## Step H5 — Curate day-1 built-in allowlists

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/eodhd.py`
- Modify: `packages/core/src/openlia/connectors/builtins/fmp.py`
- Modify: `packages/core/src/openlia/connectors/builtins/newsapi_ai.py`
- Test: `packages/core/tests/test_connectors/test_builtins_eodhd.py` (extend with shape assertions)
- Test: `packages/core/tests/test_connectors/test_builtins_fmp.py`
- Test: `packages/core/tests/test_connectors/test_builtins_newsapi_ai.py`

Each is a curation task. The implementer reads (a) the provider's tool list (via vendor docs or the MCP server's `list_tools()`), (b) each department's prose requirements YAML, then writes the `(tool_name, [department_ids])` mappings.

For each provider:

- [ ] **Step 1: Replace the placeholder `shipped_allowlist` tuple** with the curated mapping. Include a comment block above the tuple that documents the reasoning ("EODHD `get_fundamentals_data` → equity_research, earnings_update because ..."). Future maintainers should be able to challenge the mapping from the comment alone.

- [ ] **Step 2: Extend the test** to assert the curated mapping is non-trivial:
  - Every department whose requirements declare the connector's category should appear at least once in the allowlist.
  - Tools that are obviously off-topic (e.g., EODHD `get_us_options_eod` → likely no department) should NOT appear in the allowlist.

- [ ] **Step 3: Run tests, lint, commit per provider** (three separate commits is fine).

After all three:

- [ ] **Step 4: Adapter LLM regression baseline (optional but recommended)**

  Run `scope_connector` against each built-in's tool list with the user's quick-tier model. Compare its output to the shipped map. Capture diff in a one-off script (don't ship the script). Large divergences signal either the prompt needs work or the curated mapping is opinionated in ways the LLM won't follow — adjust accordingly.

---

## Step H6 — Delete legacy provider services

**Files:**
- Delete: `packages/server/src/openlia_server/services/data_providers.py`
- Delete: `packages/server/src/openlia_server/services/wizard_providers.py`
- Delete: `packages/server/src/openlia_server/services/wizard_review.py`
- Delete: `packages/server/tests/test_services/test_data_providers.py`
- Delete: `packages/server/tests/test_services/test_ai_review.py`

- [ ] **Step 1: Verify no imports remain outside the to-delete set**

  ```bash
  grep -rn "from openlia_server.services.data_providers\|import openlia_server.services.data_providers" packages | grep -v "openlia_server/services/data_providers.py\|tests/test_services/test_data_providers.py"
  grep -rn "wizard_providers\|wizard_review" packages | grep -v "wizard_providers.py\|wizard_review.py"
  ```

  If any non-empty output remains, those are stragglers — fix before deletion.

- [ ] **Step 2: Delete the files**

  ```bash
  git rm packages/server/src/openlia_server/services/{data_providers,wizard_providers,wizard_review}.py
  git rm packages/server/tests/test_services/{test_data_providers,test_ai_review}.py
  ```

- [ ] **Step 3: Run full suite; commit**

  ```bash
  uv run pytest
  git commit -m "refactor(server): delete legacy provider services"
  ```

---

## Step H7 — Delete legacy provider routes

**Files:**
- Modify: `packages/server/src/openlia_server/routes/settings.py` (remove `build_data_providers_router`)
- Modify: `packages/server/src/openlia_server/routes/setup.py` (remove provider/review endpoints)
- Modify: `packages/server/src/openlia_server/app.py` (remove the mount)
- Delete: `packages/server/tests/test_routes/test_data_providers_routes.py`
- Delete: `packages/server/tests/test_routes/test_data_providers_integration.py`
- Modify: `packages/server/tests/test_routes/test_setup_routes.py` (drop provider/review test cases per audit)
- Modify: `packages/server/tests/test_routes/test_must_change_password_gate.py` (drop `test_settings_data_providers_list_blocked`)
- Modify: `packages/server/tests/test_e2e_smoke_matrix.py` (drop `wizard_providers._run_health_check` patches)

- [ ] **Step 1: Remove the router definition** from `settings.py`. Remove the import + mount in `app.py`.

- [ ] **Step 2: Remove the eight wizard endpoints** in `setup.py` per audit §C lines 52-61.

- [ ] **Step 3: Update the affected tests** per audit §G server "touch-up" list. Each test that referenced the legacy endpoints either drops the test case or updates assertions to expect a 404.

- [ ] **Step 4: Run full suite; commit**

  ```bash
  uv run pytest
  git commit -m "refactor(server): delete legacy /api/settings/data-providers + /api/setup/providers routes"
  ```

---

## Step H8 — Delete legacy frontend provider UI

**Files:**
- Delete: `frontend/src/api/data_providers.ts`
- Delete: `frontend/src/components/settings/admin/DataProvidersAdminPanel.tsx`
- Delete: `frontend/src/components/settings/admin/__tests__/DataProvidersAdminPanel.test.tsx`
- Modify: `frontend/src/api/setup.ts` (remove dead exports — see audit §D)
- Modify: `frontend/src/api/setup.test.ts` (drop tests for those exports)
- Modify: `frontend/src/pages/SettingsPage.tsx` (remove import + route)
- Modify: `frontend/src/pages/SettingsPage.test.tsx` and `frontend/src/pages/__tests__/SettingsPage.test.tsx` (drop the panel mock and the route case)

- [ ] **Step 1: Verify no remaining imports** of `data_providers.ts` or the panel component.

- [ ] **Step 2: Delete files; remove dead exports from `setup.ts` and the page route.**

- [ ] **Step 3: Run frontend tests, lint, type-check, commit**

  ```bash
  cd frontend && npm test -- --run && npm run lint && npx tsc --noEmit
  git commit -m "refactor(frontend): delete DataProvidersAdminPanel + legacy /api/setup provider exports"
  ```

---

## Step H9 — Delete `openlia.data` package

**Files:** entire `packages/core/src/openlia/data/` tree + the matching `packages/core/tests/test_data/` tree.

- [ ] **Step 1: Confirm no imports remain**

  ```bash
  grep -rn "from openlia.data\|import openlia.data" packages
  # Expected: zero matches.
  ```

  If any: those are stragglers from H3-H8 that slipped through. Fix before proceeding.

- [ ] **Step 2: Delete**

  ```bash
  git rm -r packages/core/src/openlia/data
  git rm -r packages/core/tests/test_data
  ```

- [ ] **Step 3: Full suite green; commit**

  ```bash
  uv run pytest
  git commit -m "refactor: delete openlia.data (replaced by openlia.connectors)"
  ```

---

## Step H10 — Drop `data_providers` tables + ORM cleanup + CLI fixes

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-27-YYYY_drop_data_providers.py`
- Modify: `packages/server/src/openlia_server/db/models/config.py` (remove `DataProvider` and `DataProviderRequirementMapping` classes)
- Modify: `packages/server/src/openlia_server/db/models/__init__.py` (remove from `__all__` if present)
- Modify: `packages/server/src/openlia_server/cli.py` (per audit §H lines 145):
  - `wizard reset --purge` (lines ~763-786): swap `DataProvider` references for `Connector`.
  - `secrets` and `secrets rotate-key` (lines ~805-808, 894-898): rotation loop iterates `(LLMProvider, Connector, WebSearchProvider)`.
- Modify: `packages/server/tests/test_db/test_migrations.py` (remove `data_providers` and `data_provider_requirement_mapping` from `EXPECTED_TABLES`).
- Modify: `packages/server/tests/test_db/test_models_config.py` (delete `test_data_provider_requirement_mapping_composite_pk`).
- Modify: `packages/server/tests/test_cli/test_cli_wizard.py`, `test_cli_secrets.py`, `test_cli_crypto_rotation.py` per audit §G.

- [ ] **Step 1: Migration**

  ```python
  """Drop data_providers and data_provider_requirement_mapping.

  Revision ID: 20260427_YYYY_drop_dp
  Revises: 20260427_XXXX_connector_secrets
  """

  from __future__ import annotations
  from collections.abc import Sequence

  from alembic import op


  revision: str = "20260427_YYYY_drop_dp"
  down_revision: str | Sequence[str] | None = "20260427_XXXX_connector_secrets"
  branch_labels: str | Sequence[str] | None = None
  depends_on: str | Sequence[str] | None = None


  def upgrade() -> None:
      op.drop_table("data_provider_requirement_mapping")
      op.drop_table("data_providers")


  def downgrade() -> None:
      raise RuntimeError("data_providers drop is one-way; pre-1.0 migration")
  ```

- [ ] **Step 2: Remove ORM classes** from `db/models/config.py`. Drop the docstring lines that reference them.

- [ ] **Step 3: CLI updates** — apply the changes from audit §H. Each CLI command's tests get updated alongside.

- [ ] **Step 4: Update test fixtures**

  ```bash
  uv run pytest packages/server/tests/test_db/test_migrations.py packages/server/tests/test_db/test_models_config.py packages/server/tests/test_cli/ -v
  ```

- [ ] **Step 5: Migrate fresh DB end-to-end**

  ```bash
  rm -f .openlia.dev.db
  uv run alembic -c packages/server/alembic.ini upgrade head
  uv run python -c "import sqlite3; c=sqlite3.connect('.openlia.dev.db'); names=set(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")); assert 'data_providers' not in names and 'data_provider_requirement_mapping' not in names, names; print('OK')"
  ```

- [ ] **Step 6: Full suite green; commit**

  ```bash
  uv run pytest
  git commit -m "feat(db): drop data_providers tables; migrate CLI to Connector"
  ```

---

## Step H11 — Retire docs

**Files:**
- Delete: `planning/specs/systems/data-provider-design.md`
- Sweep: `planning/specs/`, `README.md`, `CLAUDE.md` for stale references.

- [ ] **Step 1: Delete the primary doc**

  ```bash
  git rm planning/specs/systems/data-provider-design.md
  ```

- [ ] **Step 2: Grep for stale references**

  ```bash
  grep -rln "data_providers\|openlia.data\|ProviderCategory\|DataProviderRequirementMapping" planning README.md CLAUDE.md
  ```

  For each match, either remove the reference or update it to point at `connectors`. Per-spec edits land in this same commit.

- [ ] **Step 3: Commit**

  ```bash
  git add -A planning README.md CLAUDE.md
  git commit -m "docs: retire data-provider-design.md; sweep stale references"
  ```

---

## End-of-PR verification

- [ ] **Full Python test suite green**: `uv run pytest`
- [ ] **Full frontend test suite green**: `cd frontend && npm test -- --run`
- [ ] **Lint clean**: `uv run ruff check . && cd frontend && npm run lint`
- [ ] **Type-check clean**: `cd frontend && npx tsc --noEmit`
- [ ] **Migration end-to-end**: `rm .openlia.dev.db && uv run alembic -c packages/server/alembic.ini upgrade head`
- [ ] **No remaining legacy imports**:
  ```bash
  grep -rn "from openlia.data\|import openlia.data\|DataProvider\|DataProviderRequirementMapping\|wizard_providers\|wizard_review\|ToolDispatcher\|DataProviderDispatcher\|_DataProvider" packages frontend
  ```
  Should return zero matches outside test fakes that test for absence.
- [ ] **Manual smoke** (post-merge or pre-merge in a safe env): walk the wizard with real keys for EODHD, FMP, NewsAPI.ai. Confirm Equity Research becomes Ready. Run a department report; verify it actually invokes MCP tools end-to-end.

## Self-review

**Spec coverage**

| Spec section | Implemented in |
|---|---|
| §5.1 Encrypted credential column | H2 |
| §5.2 Dispatcher unification | H3 |
| §5.3 MR/RS refactor | H4 |
| §5.4 CLI updates | H10 |
| §6 Step sequence | H2-H11 |
| §7 Test strategy | distributed across H2-H4 + end-of-PR sweep |

**Placeholder check**: H2.1 has a `<HEAD>` placeholder for the previous revision id; the implementer fills in via `alembic current`. H2.1 also has `XXXX` and H10 has `YYYY` in the migration filename — replaced with timestamp during creation. These are intentional fill-ins, not gaps.

**Type consistency**: `Dispatcher`, `PreparedConnector`, `Connector`, `ToolAllowlist`, `RSDispatcherAdapter`, `MCPLaunchSpec`, `default_session_factory`, `ConnectorStatus`, `ToolDefinition` — all defined once in PR #79 or H4.2 and reused with stable names.

**Sequencing dependencies**: H2 unblocks every later step that touches `Connector`. H3 must complete before H6 (deleting legacy services that ToolDispatcher consumers indirectly relied on). H4 must complete before H6 (deleting `data_providers` service that MR/RS code may have referenced through `app.state`). H5 is independent; can land anywhere after H2. H6-H11 are mechanical and order-independent except H10 (drop tables) which must come after H6/H7 (remove every consumer).

---

## Execution

Plan saved to `docs/superpowers/plans/2026-04-27-connector-cutover.md`. Two execution options:

1. **Subagent-Driven** — fresh subagent per task; main agent reviews between tasks. Best fit for this ~25-task plan.
2. **Inline Execution** — execute tasks in this session via the executing-plans skill.

Recommend (1) for the same reasons as PR #79 — phase-by-phase reviews catch scope creep at boundaries.
