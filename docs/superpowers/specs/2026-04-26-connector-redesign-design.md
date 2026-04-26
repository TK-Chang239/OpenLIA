# Connector Redesign — Design Spec

**Date:** 2026-04-26
**Status:** Approved for implementation planning
**Supersedes:** `planning/specs/systems/data-provider-design.md`

## 1. Why

The current `packages/core/src/openlia/data/` stack is ~5,238 lines across 13 HTTP adapters plus a manifest system, catalog, dispatch, review, sentiment, and python_providers subsystems. It is failing in practice and too complex to reason about. The redesign replaces it with a single, MCP-only connector model and an LLM-driven scoping step that maps tools to departments based on prose requirements.

## 2. Goals

- One runtime path for all tool sources (built-in, remote MCP, CLI MCP).
- Department writers express data needs as prose; LLM does the matching.
- "Ready / Not Ready" status per department is explainable per category.
- Zero HTTP adapter code in the repo.
- Add/remove a connector at any time without manual re-scoping of unrelated connectors.

## 3. Non-goals

- Per-mode tool allowlists (modes share their department's allowlist).
- Negative-example requirements ("don't include X"). Prose alone drives matching.
- Auto-detection of stale allowlists. Re-scope is explicit (manual button) or scoped to the connector being added/removed.
- Migration of existing data. Pre-1.0; existing dev DBs are wiped.

## 4. Domain model

### 4.1 Categories
Fixed set: `financial`, `news`, `social`, `web_search`. Each connector belongs to exactly one category.

### 4.2 Connector
An installed source of MCP tools.

```
Connector {
  id:                 uuid
  provider_id:        str          # "eodhd", "fmp", "user_mcp_<slug>"
  source:             BUILT_IN | REMOTE_MCP | CLI_MCP
  category:           Category
  launch:             MCPLaunchSpec
  credentials_ref:    str          # opaque key into secret store; never raw secrets
  cached_tools:       JSON         # last list_tools() result; refreshed on validate
  status:             PENDING | VALIDATED | FAILED
  last_error:         str?         # populated when status = FAILED
  last_validated_at:  datetime?
  created_at:         datetime
}
```

`MCPLaunchSpec` is a tagged union:
- `RemoteMCP { url, headers }`
- `CliMCP { argv: list[str], env: dict[str, str] }`
- `BuiltIn { template_id }` — references a `BuiltInTemplate` registered in `connectors/builtins/`. Template provides `(launch, canary_tool)` and a shipped allowlist.

### 4.3 Department requirements (per-department YAML)
Sibling file next to each department class.

```yaml
# packages/core/src/openlia/departments/equity_research.requirements.yaml
financial:
  required: true
  description: |
    Need company fundamentals (income statement, balance sheet, cash flow),
    historical daily prices, analyst estimates, earnings calendar, dividends.
news:
  required: true
  description: |
    Company-tagged news with publication date and source.
social:
  required: false
  description: |
    Reddit / X mentions for ticker sentiment if available.
```

Schema: top-level keys are `Category` values. Each value has `required: bool` and `description: str` (free-form prose, intended to be one short paragraph). Categories not declared are treated as not-needed by that department.

### 4.4 ToolAllowlist
Output of scoping. One row per (department, connector, tool).

```
ToolAllowlist {
  id:             uuid
  department_id:  str             # e.g. "equity_research"
  connector_id:   uuid (FK)       # cascade delete
  tool_name:      str             # raw, unprefixed; prefix applied at dispatch
  scoped_at:      datetime
  scoped_by:      BUILT_IN_MAP | LLM_ADAPTER
}
```

`(department_id, connector_id, tool_name)` is unique.

## 5. Wizard flow (4 stages)

### Stage 1 — Pick category
User chooses one of `financial | news | social | web_search`. Form fields below adjust to the category's built-in catalog.

### Stage 2 — Pick method + identity
Three branches:
- **Built-in**: pick provider from category-filtered catalog → enter API key. `provider_id` set from template.
- **Remote MCP**: enter URL and optional bearer header.
- **CLI MCP**: enter argv (e.g. `uvx some-mcp-server`) and env vars.

Connector is created with `status = PENDING`.

### Stage 3 — Validate (V2)
Runs immediately when the user submits a connector form.

Algorithm:
1. Open MCP transport (HTTP for remote, stdio subprocess for CLI, stdio for built-ins).
2. Call `list_tools()`. Cache full result on `Connector.cached_tools`.
3. If `source = BUILT_IN`: invoke the canary tool from the template. Built-in templates declare a known-cheap tool such as EODHD `get_user_details`. User-supplied MCP servers do not get a canary call.
4. On success: `status = VALIDATED`, `last_validated_at = now()`.
5. On failure: `status = FAILED`, `last_error = <raw error>`. Surface verbatim in the wizard.

### Stage 4 — Review
User clicks "Review" once they have added all desired connectors.

Two phases:

**Phase 4a — Scope**
For each connector with `status = VALIDATED` and no existing allowlist rows:
- `BUILT_IN` → copy shipped allowlist from `BuiltInTemplate` into `ToolAllowlist`. `scoped_by = BUILT_IN_MAP`.
- `REMOTE_MCP | CLI_MCP` → call adapter LLM once. Inputs: connector's `cached_tools` (name + description + input_schema), all department requirement YAMLs. Output: a list of `(tool_name, [department_ids])`. Persist as `ToolAllowlist` rows with `scoped_by = LLM_ADAPTER`.

Adapter LLM is resolved through the existing LLM resolver using the user-configured **quick** tier. Same 4-level fallback chain as the rest of the system.

Retry policy: one retry on transient errors or schema-invalid output. On hard failure, leave that connector's allowlist empty and surface the error on the review page next to the connector. The user clicks "Re-scope" to retry.

**Phase 4b — Compute readiness**
For each department:
- Group `ToolAllowlist` rows by `connector.category`.
- For each declared category in the department's requirements:
  - `required` and ≥1 row → ✓
  - `required` and 0 rows → ✗
  - `optional` and ≥1 row → "enhanced"
  - `optional` and 0 rows → "basic"
- Department is `ready` iff every required category is ✓.

### Review page output (example)

```
Equity Research          Ready
  financial   (required) ✓ 6 tools — eodhd, fmp
  news        (required) ✓ 4 tools — newsapi, tavily
  social      (optional) basic — no connector

Earnings Update          Not Ready
  financial   (required) ✓ 6 tools — eodhd, fmp
  news        (required) ✗ 0 tools — add a news connector
```

Buttons:
- "Re-scope all" — re-runs scoping for every user-MCP/CLI connector and refreshes built-ins from their shipped maps.
- "Re-scope <connector>" — same, scoped to one connector.

## 6. Lifecycle after wizard

- **Add connector** (settings page) → run Stage 3 then Phase 4a for that one connector. Existing allowlists untouched.
- **Remove connector** → cascade-delete all `ToolAllowlist` rows where `connector_id = X`. No LLM call.
- **Edit connector credentials** → re-run Stage 3 only. `cached_tools` refreshed. Allowlist rows for tool names that disappeared are dropped; tool names that remain are kept.
- **Manual "Re-scope"** button on review page → see Stage 4 phase 4a. Built-ins refresh from shipped map; user MCP/CLI re-run LLM.

The wizard's big-bang scope step is N independent "add connector" runs in a row.

## 7. Runtime dispatch

### 7.1 Server startup
For each `Connector` with `status = VALIDATED`:
- Open the MCP transport (HTTP keep-alive for remote; stdio subprocess for CLI/built-in).
- Cache `list_tools()` once in memory.
- If startup fails, mark connector FAILED with the error; continue with other connectors.

### 7.2 Department invocation
When a department runs (e.g. `EquityResearchDepartment.run()`):
1. Load `ToolAllowlist` rows for `department_id`.
2. For each row, look up the tool object in its connector's cached `list_tools` result. Prefix the name with `<provider_id>__`. Keep `description` and `input_schema` verbatim.
3. Pass the prefixed tool list as `tools=` to `messages.create()`.

### 7.3 Tool call dispatch
When the model emits `tool_use { name: "eodhd__get_quote", input: ... }`:
1. Strip the `<provider_id>__` prefix.
2. Look up the connector by `provider_id`.
3. Call `connector.mcp.call_tool(unprefixed_name, input)`.
4. Return the result to the model as a `tool_result`.

### 7.4 Tool name collisions (N1)
Always prefix at filter time. `eodhd__get_quote`, `fmp__quote`. Predictable, no collision-detection branch.

### 7.5 Runtime failure handling
- `call_tool` raises → return `tool_result` with `is_error: true`. Standard MCP pattern.
- Connector becomes unreachable mid-session → mark connector FAILED, drop its tools from in-memory lists, fail in-flight calls with `is_error`. Other connectors keep working.

## 8. File layout

### New package
```
packages/core/src/openlia/connectors/
  __init__.py            # public API: Connector, ToolAllowlist, scope_connector, dispatch
  models.py              # SQLAlchemy: Connector, ToolAllowlist
  types.py               # MCPLaunchSpec, ConnectorSource, Category, ScopedTool
  validate.py            # V2 logic: list_tools + canary
  scope.py               # adapter LLM caller; loads dept requirement YAMLs
  dispatch.py            # runtime: load allowlist, prefix names, route tool_use back
  mcp_transport.py       # thin wrapper: open/list_tools/call_tool for HTTP + stdio
  builtins/
    __init__.py          # registry of BuiltInTemplate
    eodhd.py             # launch_spec, canary_tool, shipped_allowlist
    fmp.py               # ...
    ...                  # final list deferred (user will re-pick)
```

### Department side
Each department gets a sibling YAML loaded lazily by the base class.
```
packages/core/src/openlia/departments/
  equity_research.py
  equity_research.requirements.yaml
  earnings_update.py
  earnings_update.requirements.yaml
  ...
```

### Server side
```
packages/server/src/openlia_server/routes/connectors.py
  POST   /connectors                 # create + validate (V2)
  GET    /connectors                 # list with status + counts
  DELETE /connectors/:id             # cascade-delete allowlist rows
  POST   /connectors/:id/validate    # re-run V2
  POST   /review/scope               # body: { connector_ids?: [uuid] }; default all user-MCP/CLI
  GET    /review                     # readiness matrix for the review page
```

Boundary: `connectors/` is pure Python; no FastAPI or HTTP imports. Routes are the only place that touches FastAPI, and they call into `connectors/` for all logic.

## 9. Deletions (clean restart)

```
packages/core/src/openlia/data/
  _http.py, base.py, types.py, errors.py, resolver.py
  adapters/                # all 13 HTTP adapters
  manifest/                # types, loader, checker, requirements.yaml
  catalog/, dispatch/, review/, sentiment/, python_providers/

planning/specs/systems/data-provider-design.md   # superseded
```

DB migration: drop existing data-provider tables, add `connectors` and `tool_allowlists` in a single Alembic revision.

## 10. Adapter LLM contract

**Inputs**
- `connector_id`, `provider_id`, `category`
- `tools`: list of `{name, description, input_schema}` from `cached_tools`
- `departments`: list of `{department_id, requirements: {category: {required, description}}}`

**Output (JSON, schema-validated)**
```json
{
  "assignments": [
    { "tool_name": "get_quote", "department_ids": ["equity_research", "earnings_update"] },
    { "tool_name": "get_us_options_eod", "department_ids": [] }
  ]
}
```

A tool may map to zero, one, or many departments. Only departments whose requirements declare the connector's `category` are eligible (the prompt enforces this; the loader also filters on write).

The prompt is fully deterministic in inputs → no temperature override needed beyond the resolver's default. One retry on schema-invalid output; then surface error.

## 11. Decision log (for traceability)

| Q | Decision | Rationale |
|---|----------|-----------|
| Built-in shape | Pre-scoped MCP-launchable templates | One runtime shape; no HTTP code; ship a known allowlist |
| Runtime path | MCP-only | Single dispatcher; matches connector model end-to-end |
| Requirements format | Categories + free-form prose, no negative examples | Tractable to author; rich enough to drive LLM scoping |
| Adapter timing | Run at wizard completion, manual rescope, plus auto on add/remove of one connector | Predictable; low cost; no background magic |
| Readiness rule | Required/optional in YAML + per-category breakdown on review page | Explainable "why not ready" |
| Validation | V2 (list_tools + canary on built-ins) | Catches bad keys cheaply; user MCP can't be canaried generically |
| Tool name collisions | N1 — always prefix with `<provider_id>__` | Mechanical, no branching |
| Modes | M1 — allowlist per-department only | Overscoping is cheap; underscoping is the bug |
| Adapter LLM | User-configured "quick" tier via existing resolver | Reuses the LLM module's fallback chain |

## 12. Day-1 built-in catalog

Three built-ins ship at launch. Kept deliberately small so the new system can be exercised end-to-end before more providers are added.

| `provider_id` | Category | Notes |
|---------------|----------|-------|
| `eodhd`       | financial | Large tool surface (~77 tools); good stress test for the scoping pass and prefix-collision handling. |
| `fmp`         | financial | Two financial built-ins exercises within-category collisions (`get_quote` vs `quote`). |
| `newsapi_ai`  | news     | Single news built-in; covers the second category. |

`social` and `web_search` have no built-ins at launch. Departments that declare those categories as `required` will be Not Ready until the user adds a Remote MCP or CLI MCP connector for them. Departments with these categories as `optional` are unaffected.

Each built-in template ships:
- `launch`: MCPLaunchSpec (typically a `CliMCP` invocation of the provider's official MCP server)
- `canary_tool`: name of a known-cheap tool used by V2 validation
- `shipped_allowlist`: hand-authored mapping of `tool_name → [department_ids]`, frozen with the release

The shipped allowlists also act as a regression baseline for the adapter LLM. During development, the adapter is run against each built-in's tool list (treating it as if it were a user-MCP) and its output diffed against the shipped map. Large drift signals a regression in the prompt, the requirements YAMLs, or the model.

## 13. Open items

- Adapter LLM prompt text — drafted during implementation; spec sets only the input/output contract.
