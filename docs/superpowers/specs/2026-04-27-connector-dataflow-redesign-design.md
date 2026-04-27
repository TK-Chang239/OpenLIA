# Connector Data Flow Redesign — Design Spec

- **Date:** 2026-04-27
- **Status:** Draft (awaiting user review)
- **Supersedes:**
  - `docs/superpowers/specs/2026-04-26-connector-redesign-design.md` (the original additive redesign)
  - `docs/superpowers/specs/2026-04-27-connector-cutover-design.md` (the Phase H follow-up that defined H4/H5)
  - `docs/superpowers/plans/2026-04-27-connector-cutover.md` (the implementation plan whose H4/H5 sections are now obsolete)
- **Implementation plan:** to be authored at `docs/superpowers/plans/2026-04-27-connector-dataflow-redesign.md`

This spec replaces the previous "all connectors are MCP, scoped statically by a wizard adapter LLM" architecture with a three-layer customization model: MCP tools for the LLM, optional skills/plug-ins for the LLM, and Python libraries for deterministic runners. It moves chat-department tool scoping from setup time to runtime (a per-conversation router with an escalation tool), introduces structured callable specs for runner needs, and defines a graceful-disable contract for departments whose required tools are not configured.

---

## 1. Context and motivation

### 1.1 Where we are

PR #80 ("Connector cutover") landed against a stale base branch (`refactor/connector-redesign`, which had already been merged to main as PR #79). As a result, the cutover work — deleting `openlia.data`, migrating to `connectors.Dispatcher`, deleting legacy admin routes — never reached `main`. The work sits on `refactor/connector-cutover` with the H4 (MR/RS runtime wiring) and H5 (curated allowlists) tasks deferred.

### 1.2 Why we are not just rebasing and shipping the deferred tasks

While planning the deferred work, several structural problems with the previous architecture surfaced:

1. **Deterministic runners cannot use the dispatcher cleanly.** MR's T1 stage and RS data fetch are not LLM-driven. They have no prompt for an LLM to interpret. Yet the existing dispatcher exposes tools as if everything is LLM-driven. The H4 plan tried to bridge this by hardcoding `eodhd__<tool_name>` strings in runner code, which couples runners to a specific provider.
2. **Many providers ship Python SDKs alongside MCP servers.** EODHD, FMP, and others. Forcing every data path through MCP imposes a protocol layer that adds latency and serialization overhead the runners do not need.
3. **Wizard-time tool scoping is approximate.** The existing wizard adapter LLM picks tools based on a department's prose YAML and a tool list. It never sees the actual user prompt. A runtime router has strictly more context and produces better picks.
4. **The day-1 social provider gap.** The previous architecture required a `social` connector for Retail Sentiment. No day-1 connector existed. RS shipped non-functional. (Resolved here: RS can use sentiment endpoints from financial providers.)

This spec addresses all four.

### 1.3 What survives from the existing cutover branch

The existing `refactor/connector-cutover` branch's H1-H3 and H6-H11 tasks remain mostly valid:

- H1 (audit), H2.1-H2.3 (api_key_encrypted column + wiring), H3.1 (consumer migration map), H3.4 (delete `ToolDispatcher`), H3.5 (drop search-callable, web search via Dispatcher) — keep as-is.
- H3.2 (`dispatcher_factory`), H3.3a (runtime_dispatch helper), H3.3b (ChatRunner refactor), H3.3c (ReportRunner refactor) — substantively rewritten in this redesign because the Dispatcher's API changes.
- H6-H9 (delete legacy provider services, routes, frontend admin panel, `openlia.data` package) — keep as-is.
- H10 (drop legacy DB tables) — extended to also drop `tool_allowlists` and add a new persistence shape for callable specs.
- H11 (retire data-provider-design.md) — extended to also supersede the previous connector design specs.

Net new work introduced by this redesign is enumerated in §11.

---

## 2. Three layers of customization

The user can customize OpenLIA on three independent layers. All three are optional. The system must function with zero configuration on any layer; departments whose required dependencies are missing become disabled with a user-facing warning (§10).

### 2.1 Layer 1 — API tools for the LLM

MCP-only. Two configuration shapes:

- **Remote MCP** — a hosted URL plus optional headers.
- **CLI MCP** — a local subprocess speaking MCP over stdio, launched via `argv` (e.g., `["uvx", "eodhd-mcp-server"]`) plus environment variables (typically the API key).

Optional. A user with no Layer 1 connectors loses LLM tool-use capability across chat departments.

### 2.2 Layer 2 — Skills and plug-ins for the LLM

Optional. Day-1 design: this layer is acknowledged as a slot but its format and consumption are deferred to a follow-up brainstorm. The connector data model anticipates skills as a third `ConnectorSource` value (`skill`) but does not yet define how they are loaded, attached to departments, or consumed by the LLM.

### 2.3 Layer 3 — Python libraries for deterministic runners

Arbitrary user-supplied pip packages. The user provides the package name (and optionally a pinned version). The wizard-time adapter LLM introspects the lib's surface, reads the relevant department's declared `needs.yaml`, and produces a structured callable spec per need. This callable spec is the runtime contract for runners.

Necessary if the user wants runner-driven dashboards (MR's T1 stage, RS data fetch) to produce real data. Without Layer 3 configured for the relevant providers, the affected departments are disabled (§10).

### 2.4 Unified connector model across layers

A single logical `Connector` record per provider. The `launch` field becomes a list of typed launch shapes — one entry per access mode the user has enabled for that provider. EODHD configured with both MCP-CLI and Python-lib is one row, one API key, two `launch` entries.

The user enables modes explicitly per connector at setup time. There is no runtime probing ("does this connector also have python_lib?"). There is no MCP-fallback for runners: if a runner's needs are scoped against the python-lib mode and that mode is missing, the dept is disabled — the runner does not silently fall back to MCP.

---

## 3. Connector data model

### 3.1 Enums

```python
class Category(StrEnum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL = "social"
    WEB_SEARCH = "web_search"


class ConnectorSource(StrEnum):
    BUILT_IN = "built_in"
    REMOTE_MCP = "remote_mcp"
    CLI_MCP = "cli_mcp"
    PYTHON_LIB = "python_lib"  # NEW
    # SKILL = "skill"  # reserved for Layer 2 follow-up


class ConnectorStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"
```

### 3.2 Launch spec — one entry per enabled access mode

`Connector.launch` JSON becomes a list of typed launch shapes. Each shape carries its own `kind` and per-kind configuration:

```json
{
  "modes": [
    {
      "kind": "cli_mcp",
      "argv": ["uvx", "eodhd-mcp-server"],
      "env_keys": ["EODHD_API_KEY"]
    },
    {
      "kind": "python_lib",
      "pip_name": "eodhd",
      "pip_version": ">=1.2.0",
      "import_module": "eodhd",
      "instance_factory": {
        "class": "APIClient",
        "args": {"api_key": "$EODHD_API_KEY"}
      }
    }
  ]
}
```

`built_in` continues to act as a recipe pointer: a `built_in` mode resolves to a concrete `cli_mcp` (or, eventually, `python_lib`) via the built-in template registry at validation time.

### 3.3 Connector ORM (incremental)

Existing columns kept: `id`, `provider_id`, `category`, `status`, `api_key_encrypted`, `cached_tools`.

New column:
- `cached_python_callables: JSON` — a serialized snapshot of the lib's introspected public surface, captured at validation time. Used by the wizard-time adapter LLM as input. Shape: `[{"qualname": "APIClient.real_time_quote", "signature": "(symbol: str) -> dict", "doc": "..."}]`.

Existing column changed:
- `launch: JSON` — was a single launch spec; becomes a `{"modes": [...]}` list.

### 3.4 Persistence for callable specs

A new table `runner_callable_specs` stores one row per (department, need_id, connector) tuple with a resolved callable spec. Schema:

| Column | Type | Notes |
|---|---|---|
| `id` | string PK | UUID |
| `department_id` | string FK | e.g., `macro_research` |
| `need_id` | string | e.g., `debt_gdp` |
| `connector_id` | string FK | resolved against this connector |
| `access_mode` | string | one of `cli_mcp`, `remote_mcp`, `python_lib` |
| `spec` | JSON | structured callable spec (see §5.4) |
| `canary_value` | JSON | a sample response captured at validation time |
| `canary_at` | timestamp | when the canary was last refreshed |

Constraint: `(department_id, need_id)` is unique — one spec per need (day-1 decision). Multi-connector dynamic selection is a future evolution (§13).

### 3.5 Tables removed by this redesign

- `tool_allowlists` (introduced by the connector-redesign branch) — removed. Chat departments no longer have per-(dept, connector, tool) allowlist rows. The runtime router operates against the full validated tool inventory; deterministic runners operate against `runner_callable_specs`.
- `data_providers`, `data_provider_requirement_mapping` (legacy) — already in scope for deletion via H10 of the cutover plan.

---

## 4. Per-department artifacts

Each department directory holds these files:

| File | Purpose | Consumer | New / existing |
|---|---|---|---|
| `<dept>.py` | Code-level metadata: id, modes, required/optional categories, `requires_runner` flag | Server bootstrapping, health check | Existing — extended with new fields |
| `<dept>.routing_context.md` | Curated routing context (what the dept does, data needs, out-of-scope topics, example prompts) | Runtime router LLM | **New** |
| `<dept>.needs.yaml` | Declarative parameterized needs (id, description, parameters, shape) | Wizard-time runner adapter LLM | **New**; only present for depts with `requires_runner=True` |
| `<dept>.requirements.yaml` | Existing prose requirements (per-category required/optional + descriptions) | (was: wizard chat-scoping LLM, runner adapter) | **Deprecated** — content split between routing_context.md and needs.yaml; file removed at end of migration |

### 4.1 Department dataclass — new fields

```python
@dataclass(frozen=True)
class EarningsUpdateDepartment:
    name: str = "earnings_update"
    display_name: str = "Earnings Update"
    # ...existing fields...
    required_categories: tuple[Category, ...] = (Category.FINANCIAL,)
    optional_categories: tuple[Category, ...] = (Category.NEWS,)
    requires_runner: bool = False
```

The full dependency table (§10.1) records these per dept.

### 4.2 routing_context.md — recommended structure

Markdown, 300-800 tokens per dept. No frontmatter required. Loaded as a single string at startup and injected into the runtime router prompt.

```markdown
# Equity Research — Routing Context

## What this department does
[1-2 sentences: dept role and primary outputs.]

## Data this department needs access to
[Curated data needs by use case. Drawn from frameworks
(`packages/core/src/openlia/reports/frameworks/*.json`), specs
in `planning/specs/`, and the dept's code. Examples of the
kinds of API endpoints / tools the router should bias toward
when prompts touch each topic.]

## Out-of-scope topics
[What this dept does NOT handle. Helps the router not over-reach
into other depts' territory.]

## Example prompts and the data they imply
[3-6 representative prompts paired with the kind of tools the
router should pick. Few-shot ground truth that calibrates the
router.]
```

The "Example prompts" section is the highest-leverage piece. Worth the curation effort.

**Day-1 ship:** skeleton placeholders only. Content authoring is a separate session (and likely a separate PR) where the user reads the relevant frameworks, specs, and dept code to author each routing_context. The redesign PR ships the contract (file format, location, loader, tests); the content session fills in the prose.

### 4.3 needs.yaml — declarative parameterized needs

Only for departments with `requires_runner=True`. Replaces the implicit `T1_REQUIREMENTS` tuples currently buried in dashboard classes.

```yaml
department: macro_research
needs:
  - id: debt_gdp
    description: |
      Government gross debt as a percentage of GDP, in percentage
      points (e.g., 110.0 means 110%). Sourced from official
      government statistics or central bank releases.
    parameters:
      - name: country
        description: "ISO 3166-1 alpha-2 code; defaults to 'US'"
        type: string
        required: false
        default: "US"
    shape: float

  - id: stock_quote
    description: |
      Latest closing price for an equity, given its NYSE/NASDAQ/etc.
      ticker symbol.
    parameters:
      - name: ticker
        description: "Ticker symbol, e.g. 'TIP', 'HYG'"
        type: string
        required: true
    shape: float
```

Runner code references needs by `id`:

```python
class DebtCycleDashboard:
    T1_NEEDS: ClassVar[tuple[str, ...]] = (
        "debt_gdp",
        "interest_revenue",
        "tips_quote",
        "dxy_proxy",
    )

# elsewhere, in the runner:
debt_value = await dispatcher.fetch_need("debt_gdp", country="US")
```

Formulas reference by id too: `T2_FORMULAS = {"debt_gdp": "debt_gdp"}`.

### 4.4 Loader and drift safety

`packages/core/src/openlia/departments/loader.py` exposes:

```python
def load_routing_context(department_id: str) -> str: ...
def load_needs(department_id: str) -> list[RunnerNeed]: ...
```

A test (`test_department_artifacts.py`) asserts:

1. Every department has a `<dept>.routing_context.md` of at least N tokens with all expected H2 sections present.
2. Every department with `requires_runner=True` has a non-empty `<dept>.needs.yaml`.
3. Every `id` referenced from runner code (e.g., `T1_NEEDS`) exists in the dept's `needs.yaml`. Reverse check: every id in `needs.yaml` is referenced from at least one runner.

Each `<dept>.py` carries a docstring: "If you change this department's behavior or its associated framework, update `<dept>.routing_context.md` and (if applicable) `<dept>.needs.yaml`." Soft enforcement via PR review.

---

## 5. Parameterized runner needs

### 5.1 Need declaration

A need is the atomic unit of "data this runner consumes." Declared in `<dept>.needs.yaml`:

| Field | Type | Purpose |
|---|---|---|
| `id` | string | Stable, code-facing identifier. Referenced from runner code, formulas, response payloads. Never changes once shipped (treat as a public API). |
| `description` | prose | Adapter LLM input. Rich enough to disambiguate the need's intent including units and conventions. |
| `parameters` | list of declared parameters (name, description, type, required, optional default) | Runtime arguments. The runner supplies values per call; the dispatcher binds them per the callable spec. |
| `shape` | type hint string | Return value shape (`float`, `list[object]`, etc.). Used to validate canary responses during scoping. |

### 5.2 Three categories of arguments at the underlying API

The callable spec produced by the adapter must distinguish:

- **Auth** — handled by the connector layer. Decrypted from `api_key_encrypted` at instance construction time. Never appears in the callable spec.
- **Constants** — baked into the callable spec at scoping time (e.g., `fmt: json`, `indicator: DEBT_GDP_PCT`).
- **Runtime args** — supplied by the runner per call, passed through `parameter` declarations.

### 5.3 Runner usage

Runners declare their needs via id tuples and call by id:

```python
debt_value = await dispatcher.fetch_need("debt_gdp", country="US")
tip_price = await dispatcher.fetch_need("stock_quote", ticker="TIP")
```

The dispatcher walks the persisted callable spec, binds the runner-supplied parameters per the binding rules (renaming, transforms, defaults), invokes the underlying lib (or MCP), and returns the result.

### 5.4 Callable spec — persisted JSON shape

```json
{
  "need_id": "debt_gdp",
  "access_mode": "python_lib",
  "module": "eodhd",
  "instance_factory": {
    "class": "APIClient",
    "args": {"api_key": "$EODHD_API_KEY"}
  },
  "method": "economic_data",
  "param_bindings": {
    "country": {"to_arg": "country_code", "transform": null}
  },
  "constants": {
    "indicator": "DEBT_GDP_PCT"
  },
  "shape": "float",
  "canary_at": "2026-04-27T10:30:00Z",
  "canary_value": 122.4
}
```

For an MCP access mode the shape is similar but with `tool_name` instead of `module`/`method`:

```json
{
  "need_id": "debt_gdp",
  "access_mode": "cli_mcp",
  "tool_name": "get_economic_indicator",
  "param_bindings": {
    "country": {"to_arg": "country", "transform": "upper"}
  },
  "constants": {"indicator": "DEBT_GDP_PCT"},
  "shape": "float",
  "canary_value": 122.4
}
```

The dispatcher's `fetch_need` walks this structured data; no LLM is in the runtime path; no `eval` of code strings.

### 5.5 One spec per need (day-1)

If two configured connectors can both satisfy `debt_gdp`, the user picks one at scoping time and that connector's spec is persisted. Multi-connector overlap with runtime selection is a future evolution (§13).

---

## 6. Wizard-time runner adapter

Distinct from the previous wizard chat-scoping adapter (which is removed by this redesign). The new wizard-time adapter has one job: produce structured callable specs for runner needs.

### 6.1 Inputs

Per (validated connector, runner-bearing department):

- The connector's `cached_python_callables` (for python_lib mode) and/or `cached_tools` (for MCP modes).
- The department's `<dept>.needs.yaml` (the declarative needs list).
- For each need, the lib's relevant function signatures, docstrings, and any provided sample data.

### 6.2 Output

For each need, a proposed callable spec (§5.4) plus a canary call result.

### 6.3 Validation per access mode

**python_lib mode:**

1. Verify the pip package is importable. Capture the resolved version.
2. Walk the public surface via `inspect.signature`, `inspect.getdoc`, etc. Persist as `cached_python_callables`.
3. For each need, the adapter LLM produces a callable spec proposal.
4. Execute the canary: instantiate the factory, bind the proposed parameters to a sample value (e.g., `country="US"`), invoke the method, capture the response.
5. Verify the response matches the declared `shape` (basic type check).
6. Persist the spec + canary on user approval.

**MCP modes (`cli_mcp`, `remote_mcp`, `built_in`):**

1. Existing validation: spawn the server, call `list_tools()`, optionally invoke a `canary_tool`. Persist as `cached_tools`.
2. For each need, the adapter LLM proposes a callable spec selecting one of the discovered tools and binding parameters.
3. Execute the canary: invoke the tool with sample arguments. Capture the response.
4. Verify shape; persist on user approval.

**Skill mode (Layer 2):** deferred (§13).

### 6.4 User review surface

For each runner-bearing department, the wizard shows a per-need card:

```
Macro Research — debt_gdp
"Government gross debt as a percentage of GDP..."

Resolved against: EODHD (python_lib)
   eodhd.APIClient.economic_data(country=country_code, indicator='DEBT_GDP_PCT')

Sample for country='US': 122.4

[Approve]  [Re-resolve]  [Try a different connector]
```

If the user approves, the spec persists. If they choose "Re-resolve," the adapter runs again with a different prompt (perhaps biased toward a different function in the same lib). If they choose "Try a different connector," the wizard re-routes the resolution against another configured connector for the same category.

### 6.5 The chat-scoping role is gone

The previous wizard adapter also produced (department, connector, tool) allowlist rows for chat departments. **That output is removed.** Chat-department tool scoping happens at runtime (§7), not at wizard time. The wizard adapter exists solely for runner callable spec resolution.

---

## 7. Runtime architecture for chat departments

### 7.1 Candidate pool

Each chat department's candidate pool is the **full validated tool inventory** across all configured connectors. There are no per-(dept, connector, tool) allowlist rows. There is no day-1 deny-list.

### 7.2 Conversation-scoped routing

A new module `runtime_router.py` exposes:

```python
async def route_for_conversation(
    *,
    department_id: str,
    user_prompt: str,
    candidate_tools: list[ToolDefinition],
    routing_context: str,
    router_llm: LLMClient,
) -> list[ToolDefinition]: ...
```

The router runs **once** at conversation start. Its prompt template:

```
You are routing tools for the {department_id} department.

{routing_context}

User prompt:
{user_prompt}

Available tools (the dept's full validated tool inventory):
{candidate_tools}

Pick the smallest subset of tools that lets the main LLM answer
this prompt well. Be liberal: if a tool might plausibly be useful
during the conversation, include it. Be conservative: do not
include tools that are clearly off-topic for the dept.

Return the chosen tools as a JSON array of tool names.
```

Output: a subset of `candidate_tools`. Always includes the **escalation tool** (§7.3) regardless of the router's pick.

### 7.3 Escalation tool

Every routed conversation includes an additional system-provided tool:

```python
{
    "name": "request_additional_tools",
    "description": (
        "Call this if you realize you need a capability that's not in "
        "your current toolset. Provide a one-sentence reason describing "
        "what you want to do; new tools will be added to your toolset "
        "for the rest of the conversation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string"}
        },
        "required": ["reason"]
    }
}
```

When the main LLM emits a `tool_use` for `request_additional_tools`, the orchestrator:

1. Pauses the main LLM turn.
2. Calls the runtime router again with: recent conversation turns + current tool set + the LLM's reason + dept's full candidate pool.
3. Router returns N additional tools (might be 0 if nothing else applies).
4. Orchestrator merges the additional tools into the conversation's tool set. The set only grows; never shrinks.
5. Main LLM continues with the expanded set. It receives the escalation's `tool_result` containing a brief summary of what was added: `"Added tools: get_company_news, get_analyst_estimates."`

### 7.4 Cache behavior

Tool definitions live in the cached prompt prefix. With static tools across a conversation, the prefix is stable and Anthropic's prompt cache yields high hit rates after the first turn.

On escalation, the tool set changes — the cache invalidates from the tools-portion forward. Subsequent turns re-stabilize on the expanded set.

To preserve as much caching as possible, the prompt is structured:

```
[stable: system instructions]
[stable: dept role prefix]
[volatile: routed tool definitions]
[append-only: conversation history]
```

The cache breakpoint is set before the routed tools so that everything above stays cached.

### 7.5 Routing default-on with per-dept override

Routing is on by default for every chat department. Each `Department` dataclass carries an optional `disable_runtime_routing: bool = False`. When `True`, the dept skips the router and the main LLM gets the full candidate pool. Reserved for departments with strict reliability/predictability requirements (e.g., Panic Thermometer if it ships with a determinism need).

### 7.6 Defense in depth

The runtime router is bounded by the dept's validated tool inventory: it can only return tools from connectors with `status=VALIDATED`. A bug in the router cannot escape this bound.

---

## 8. Runtime architecture for deterministic runners

### 8.1 No LLM in the runtime path

Deterministic runners (MR's T1 stage, RS data fetch, future scheduled jobs) walk persisted callable specs. There is no LLM call at runtime; no prompt; no routing.

### 8.2 Dispatcher API additions

```python
class Dispatcher:
    # existing:
    async def dispatch_tool_use(self, prefixed_name: str, arguments: dict) -> Any: ...

    # new:
    async def fetch_need(
        self,
        need_id: str,
        **runtime_args: Any,
    ) -> Any:
        """Resolve and invoke the callable spec for the given need.

        Looks up `runner_callable_specs` row keyed by (current_dept, need_id),
        binds runtime_args per the spec, invokes via the appropriate access
        mode, and returns the raw response. Raises if no spec is configured
        (caller should treat this as the dept being mis-configured).
        """
```

The current_dept is determined from the calling context (e.g., MR runner sets `dispatcher.set_department("macro_research")` before invoking).

### 8.3 MR T1 stage migration

Before (cutover branch state):

```python
t1_data: dict[str, Any] = dict.fromkeys(dashboard.T1_REQUIREMENTS)  # all None
```

After:

```python
t1_data = {}
for need_id in dashboard.T1_NEEDS:
    needs_spec = NEEDS_BY_ID[need_id]
    if not needs_spec.parameters:
        t1_data[need_id] = await dispatcher.fetch_need(need_id)
    else:
        # Dashboard supplies the runtime args specific to its scope.
        # E.g., for stock_quote, the dashboard knows which tickers it cares about.
        t1_data[need_id] = await dispatcher.fetch_need(
            need_id, **dashboard.runtime_args_for(need_id)
        )
```

If `fetch_need` raises because no spec is configured, the dashboard's containing department is in a disabled state (caught by the health check, §10) and this code path is not reached. Inside this code path, `fetch_need` failures are bubbled up to the caller.

### 8.4 RS data fetch migration

`RsRunner._fetch_posts(ticker)` becomes:

```python
async def _fetch_posts(self, ticker: str) -> list[RawSocialPost]:
    raw = await self._dispatcher.fetch_need("social_posts", ticker=ticker)
    return [RawSocialPost.from_dict(item) for item in raw]
```

`<retail_sentiment>.needs.yaml` declares:

```yaml
department: retail_sentiment
needs:
  - id: social_posts
    description: |
      Recent social media posts mentioning the given ticker, sorted
      by recency. Sourced from the financial connector's sentiment
      endpoint (e.g., EODHD's sentiment_data, FMP's social_sentiment).
      Returns a list of objects with at minimum: id, body, author,
      timestamp, source.
    parameters:
      - name: ticker
        description: "NYSE/NASDAQ ticker"
        type: string
        required: true
    shape: list[object]
```

Sourcing: per the user's clarification, RS pulls from sentiment endpoints exposed by financial connectors (EODHD, FMP). Day-1 RS is functional with just an EODHD or FMP python_lib mode configured. No separate `social`-category connector is required for RS to function.

### 8.5 No fallback

If a runner's needed callable spec is missing (no connector configured for that need's resolution), the runner's department is disabled (§10). The runner is never invoked in a disabled state. There is no MCP-fallback when python_lib is missing or vice versa.

---

## 9. Wizard / setup UX

### 9.1 Add-connector flow

The wizard asks the user to select one of:

- A built-in template (from the curated catalog).
- A remote MCP URL (with optional headers).
- A local CLI MCP launch (argv + env keys).

Then the user enables which access modes apply for this connector. If the user selects a built-in template that ships with both MCP and python_lib recipes (e.g., EODHD), the wizard surfaces a checkbox for each: "Enable MCP server (recommended for chat)?" and "Enable Python library (required for runner-driven dashboards)?"

For an arbitrary user-supplied python_lib, the user provides:

- pip package name and optional version pin.
- The import path (often the same as the pip name).
- An instance factory, if the lib uses a client class. The wizard surfaces the introspected classes after pip install and lets the user pick.

The user then provides the API key. The server encrypts and stores. Validation runs per access mode (§6.3). Upon success, the connector enters `VALIDATED` state and its modes' tools/callables are cached.

### 9.2 Per-need callable spec review

For each runner-bearing department, the wizard shows a card per need (§6.4). The user reviews the proposed spec + canary value and approves, re-resolves, or routes to a different connector.

### 9.3 No per-tool review for chat departments

Chat depts no longer have a per-tool review step. The wizard's chat-dept summary shows: "X tools available across N connectors. Routed dynamically per conversation."

### 9.4 First-run summary

After the user finishes the wizard, OpenLIA shows a department status summary:

```
Departments: 4 of 7 active.
- ✓ Active: Equity Research, Earnings Update, Morning Briefing, Secretary
- ⚠ Disabled: Macro Research (configure Python library for EODHD), Retail Sentiment, Panic Thermometer

You can configure additional connectors anytime from Settings.
```

### 9.5 CLI for setup

`openlia connectors add ...` and related commands are acknowledged as desirable but deferred to a follow-up spec. Day-1 ships wizard-only configuration.

---

## 10. Department health and graceful disable

All three customization layers are optional. The system must function with zero configuration; departments whose required dependencies are not met are cleanly disabled with a user-facing warning rather than producing errors at request time.

### 10.1 Dependency declarations per department

Department dataclass fields:

```python
@dataclass(frozen=True)
class Department:
    name: str
    display_name: str
    required_categories: tuple[Category, ...]
    optional_categories: tuple[Category, ...]
    requires_runner: bool
    disable_runtime_routing: bool = False
```

Day-1 declared values:

| Department | Required | Optional | requires_runner |
|---|---|---|---|
| Secretary | () | (web_search,) | False |
| Equity Research | (financial,) | (news, social, web_search) | False |
| Earnings Update | (financial,) | (news,) | False |
| Morning Briefing | (financial, news) | (web_search,) | False |
| Macro Research | (financial,) | (news,) | True |
| Retail Sentiment | (financial,) | (news, social) | True |
| Panic Thermometer | (financial,) | (news,) | False |

Note: Retail Sentiment requires `financial` (not `social`) because RS pulls sentiment data from EODHD/FMP sentiment endpoints rather than from a separate social provider. A standalone social-category connector is not required for RS to function day-1.

### 10.2 Health check

`packages/server/src/openlia_server/services/dept_health.py`:

```python
@dataclass(frozen=True)
class DeptHealth:
    department_id: str
    status: Literal["active", "disabled"]
    reason: str | None  # human-readable; populated when disabled


def check_dept_health(dept: Department, db: Session) -> DeptHealth:
    missing_categories = [
        c for c in dept.required_categories
        if not has_validated_connector_in_category(db, c)
    ]
    if missing_categories:
        return DeptHealth(
            department_id=dept.name,
            status="disabled",
            reason=(
                f"No connector configured for required categories: "
                f"{', '.join(c.value for c in missing_categories)}"
            ),
        )
    if dept.requires_runner:
        unresolved_needs = needs_without_callable_spec(db, dept.name)
        if unresolved_needs:
            return DeptHealth(
                department_id=dept.name,
                status="disabled",
                reason=(
                    f"No callable spec resolved for runner needs: "
                    f"{', '.join(unresolved_needs)}. Configure a Python "
                    f"library mode for the relevant financial connector."
                ),
            )
    return DeptHealth(department_id=dept.name, status="active", reason=None)
```

The health check runs:
- At app startup (populating `app.state.dept_health`).
- Whenever a connector transitions to/from `VALIDATED`.
- Whenever a callable spec is added or removed.

Health changes invalidate the dept-tools cache and update the `app.state.dept_health` snapshot atomically.

### 10.3 User-facing surfaces

**Settings → Departments tab.** Lists every department with a health badge and reason:

```
Active (4)
- Equity Research                              [✓ Active]
- Earnings Update                              [✓ Active]
- Morning Briefing                             [✓ Active]
- Secretary                                    [✓ Active]

Disabled (3)
- Macro Research        [⚠ Disabled]
    No callable spec resolved for runner needs:
    debt_gdp, interest_revenue, tips_quote, dxy_proxy.
    [Configure a Python library connector →]
- Retail Sentiment      [⚠ Disabled]
    No callable spec resolved for runner needs: social_posts.
- Panic Thermometer     [⚠ Disabled]
    No connector configured for required categories: financial.
```

**Sidebar.** Disabled departments appear greyed out with a tooltip on hover ("Disabled — see Settings to configure"). Clicking still navigates to the dept page.

**Department page (when disabled).** A banner at the top of the dept's main view:

```
This department is disabled.
[reason from DeptHealth]
[Configure connectors →]
```

Below the banner, the dept's UI renders in a read-only state showing whatever cached data exists from previous runs (if any).

**API endpoints for disabled departments.** Any mutating endpoint (start a chat, run a report, refresh a dashboard) returns `409 Conflict` with the `DeptHealth.reason` in the response body. Read endpoints (fetch cached state) continue to work.

**Scheduler.** Cron jobs targeting a disabled department log `skipped: disabled (reason)` and do not invoke the runner.

### 10.4 Re-enablement

Health is dynamic. When the user adds a connector that satisfies a previously-disabled dept's requirements, the dept becomes active immediately on the next health-check tick (no restart). The frontend polls or subscribes to dept-health changes and updates the sidebar/Settings view accordingly.

---

## 11. Migration and execution sequencing

### 11.1 Branch strategy

A new branch (`refactor/connector-dataflow-redesign`) is created from `main`. The valid portions of `refactor/connector-cutover` are cherry-picked or rebased onto it. The redesign-specific work is then layered on top. A single PR opens against `main`.

### 11.2 Step inventory

#### Steps from the existing cutover plan that survive as-is

| Step | Original commit | Notes |
|---|---|---|
| H2.1 | `8b876af` | DB migration: api_key_encrypted column |
| H2.2 | `1c02393` | Connector ORM column |
| H2.3 | `df702c1` | Wire encryption through POST /api/connectors |
| H3.1 | `a4b12b6` | Doc: ToolDispatcher consumer migration map |
| H3.4 | `da030ea` | Delete ToolDispatcher |
| H3.5 | `1805f1d` | Drop search-callable; web search via Dispatcher |
| H6 | (part of `03c3a57`) | Delete legacy provider services |
| H7 | (part of `03c3a57`) | Delete legacy provider routes |
| H8 | `e09104a` | Delete frontend admin panel |
| H9 | `8d610e0` | Delete openlia.data package |

#### Steps that need rewriting

| Step | Was | Now |
|---|---|---|
| H3.2 | `dispatcher_factory hydrates Dispatcher; category filter on tools_for_department` | `dispatcher_factory hydrates Dispatcher with `candidate_tools_for_router(dept_id)` and `fetch_need(need_id, **)`. No `tools_for_department` (allowlist gone). |
| H3.3a | `runtime_dispatch helper — envelope shaping + parallelism` | Two helpers: `chat_dispatch_helper` (post-routing tool_use round-tripping) and `runner_fetch_helper` (callable_spec walking). |
| H3.3b | ChatRunner consumes Dispatcher | ChatRunner: routes at conversation start, exposes escalation tool, handles re-routing, merges new tools. Substantial rewrite. |
| H3.3c | ReportRunner consumes Dispatcher | Same rewrite as ChatRunner. |
| H10 | Drop legacy data_provider tables; CLI rotation iterates Connector | Same plus drop `tool_allowlists` table; add `runner_callable_specs` table. |
| H11 | Retire data-provider-design.md | Same plus mark previous connector design specs as superseded. |

#### Net new steps the redesign introduces

| Step | What |
|---|---|
| N1 | Add `python_lib` to `ConnectorSource` enum; per-mode launch shape |
| N2 | `Connector.launch` JSON becomes a list of typed launch shapes |
| N3 | New `cached_python_callables` column on Connector |
| N4 | New `runner_callable_specs` table |
| N5 | Wizard adapter LLM rewrite — sole job is callable_spec resolution |
| N6 | Runtime router LLM module — conversation-scoped routing |
| N7 | Escalation tool (`request_additional_tools`) integration into ChatRunner |
| N8 | Per-dept `routing_context.md` skeletons (content authored later) |
| N9 | Per-dept `<dept>.needs.yaml` files for runner-bearing depts |
| N10 | Loader for routing_context.md and needs.yaml + drift-safety tests |
| N11 | Migration: deprecate and remove `*.requirements.yaml` |
| N12 | MR T1 stage refactor: `dispatcher.fetch_need(...)` |
| N13 | RS `_fetch_posts` and `_fetch_optional` refactor through fetch_need |
| N14 | Frontend wizard updates: per-mode access selection, per-need callable_spec review with canary samples, no chat-tool review |
| N15 | Department health check service + frontend surfaces (sidebar, Settings, dept page banner, scheduler skip, 409 from API) |

### 11.3 Sequencing dependencies

- N1, N2, N3 (connector data model) precede everything else that touches `Connector`.
- H2.1-H2.3 precede N5 (adapter writes specs that reference encrypted keys).
- N4 (callable_specs table) precedes N5 (adapter writes to it).
- N5 precedes N12, N13 (runners need specs to fetch).
- N6, N7 precede H3.3b, H3.3c (chat/report runners consume the router).
- N8, N9, N10 precede N5 (adapter reads needs.yaml; router reads routing_context.md).
- H11 (deprecate `*.requirements.yaml`) is last — depends on N9, N10 completing.
- H3.4, H3.5 are runtime-dispatcher cleanups; they land after H3.2's redesign.
- H6, H7, H8, H9, H10 are deletions; land after every consumer of the legacy paths is removed.
- N15 (dept health) lands once the dept dataclass changes, the health service exists, and at least one dept has runner needs that can be resolved.

### 11.4 What ships in the PR vs. follow-ups

**Ships in this PR:**

- All redesign work (N1-N15).
- All surviving cutover steps (H1-H10 in their final form).
- Per-dept routing_context.md **skeletons** (each with section headers and a one-line TODO).
- Per-dept needs.yaml **filled** (these are needed for the runner adapter to function; runners use ids that must exist).

**Deferred to follow-up PRs:**

- Authoring the per-dept routing_context.md content (separate session per dept).
- Layer 2 (skills) format and consumption.
- Layer 3 install/trust details (pip install via wizard vs. user-managed venv; sandboxing posture).
- CLI for connector setup (`openlia connectors add ...`).
- Multi-connector dynamic selection for runner needs.
- Day-1 catalog of built-in templates with python_lib modes pre-wired.

---

## 12. Test strategy

### 12.1 Connector data model

- `tests/test_db/test_models_connectors.py`: `Connector.launch` JSON parses round-trip with multiple modes; `cached_python_callables` accepts None and lists; `runner_callable_specs` row creation and unique-constraint enforcement on (department_id, need_id).

### 12.2 Per-dept artifacts

- `tests/test_departments/test_artifacts.py`: every dept has a `.routing_context.md` of at least N tokens with all required H2 sections; every `requires_runner=True` dept has a non-empty `.needs.yaml`; every `id` referenced from runner code is declared in YAML; every YAML id is referenced from at least one runner.

### 12.3 Wizard-time runner adapter

- `tests/test_services/test_callable_spec_resolver.py`: given a fake introspected lib surface and a known need, the adapter returns a structured callable spec; the canary execution invokes the bound method and stores its response; shape mismatch surfaces as a validation error.

### 12.4 Dispatcher

- `tests/test_connectors/test_dispatcher.py`: `fetch_need` walks a python_lib spec end-to-end against a mock lib; `fetch_need` walks an MCP spec against a mock transport; `candidate_tools_for_router` returns the union of validated tools (no allowlist filtering).

### 12.5 Runtime router

- `tests/test_services/test_runtime_router.py`: given fake routing_context + tool list + prompt, the router returns a non-empty subset; the escalation tool is always included; on escalation, the new tool list is the union of the old and the router's new picks.

### 12.6 Chat runner

- `tests/test_services/test_chat_runner_routing.py`: opening a conversation triggers exactly one routing call; mid-turn `request_additional_tools` triggers exactly one re-route; the merged tool set is monotonically increasing.

### 12.7 Department health

- `tests/test_services/test_dept_health.py`: a dept with `required_categories=(financial,)` is `active` when any validated FINANCIAL connector exists, `disabled` otherwise; a `requires_runner` dept is `disabled` when any need lacks a callable spec, `active` when all needs have specs; health re-checks fire on connector status change and on callable_spec changes.

### 12.8 API behavior on disabled depts

- `tests/test_routes/test_disabled_depts.py`: mutating endpoints on a disabled dept return 409 with the reason body; read endpoints continue to work.

### 12.9 MR / RS migration

- `tests/test_macro_research/test_runner.py`: with a mocked dispatcher, MR's T1 stage produces real values (not Nones); each `fetch_need` call hits the dispatcher with the dashboard-supplied parameters.
- `tests/test_services/test_rs_runner.py`: with a mocked dispatcher returning sample posts, RS produces a non-empty `MetricSnapshot` with classified posts.

---

## 13. Open items deferred

Each item below is acknowledged but not designed in this spec. Capturing them here ensures they are not forgotten.

### 13.1 Layer 2 — Skills and plug-ins

The connector data model reserves a `SKILL` value in `ConnectorSource` but does not define how skills are stored, attached to departments, or consumed by the LLM. Open questions: file format (Claude Code skill format vs. custom), attachment model (per-dept system-prompt extension vs. tool definition), discovery (filesystem vs. registry), trust posture. Needs its own brainstorm.

### 13.2 Layer 3 — install and trust posture

How does the user "install" a Python library for a connector? Three options: (a) the wizard runs `pip install <pkg>` against the OpenLIA process's venv; (b) the user runs pip themselves and OpenLIA imports; (c) OpenLIA spawns a sandboxed subprocess with a per-connector venv.

(a) is the most user-friendly but means OpenLIA is mutating its own environment based on user input — operationally fragile. (b) is the simplest to ship but burdens the user. (c) is the cleanest isolation model but adds significant complexity (per-connector venvs, IPC for invocation).

Day-1 default in this redesign: option (b) — the user pip-installs in their venv before configuring the connector. The wizard validates by attempting to import. Future evolution may add (a) or (c).

Needs its own decision in a follow-up brainstorm.

### 13.3 Per-mode validation detail

The high-level validation contract per access mode is defined in §6.3. The implementation detail (exact error messages, retry behavior, version-pinning behavior, handling of optional vs. required parameters during canary) is left to the implementation plan.

### 13.4 CLI setup

`openlia connectors add ...`, `openlia connectors validate <id>`, `openlia connectors rotate-key <id>`, etc. Day-1 wizard-only. CLI add-flow gets its own follow-up spec.

### 13.5 Day-1 catalog of built-ins

Whether day-1 ships any built-in templates with both MCP and python_lib modes pre-wired (e.g., EODHD with both shipped), or whether users always start from an empty catalog and configure their own. This is a content question more than an architectural one.

### 13.6 Multi-connector dynamic selection for runner needs

If two configured connectors can both satisfy `debt_gdp`, day-1 the user picks one at scoping time and a single callable spec is persisted (§5.5). Future evolution: store one spec per (need, connector) and let a runtime selector pick the best at fetch time (e.g., based on country coverage, latency, freshness). Adds complexity; not day-1.

### 13.7 routing_context.md content authoring

Day-1 ships skeleton placeholders. The deep-dive content session — where each dept's routing_context.md is authored by reading the full set of sources (frameworks, specs, dept code) — is a separate effort and likely a separate PR. The redesign PR ships the contract; the content session fills the prose.

---

## Appendix A — Glossary

- **Connector** — a single configured provider (e.g., the user's EODHD setup). One row in the `connectors` table. May expose multiple **access modes** (cli_mcp, remote_mcp, python_lib).
- **Access mode** — one way of invoking a provider (MCP server vs. Python library). Modes are configured per connector at setup time.
- **Need** — a declarative unit of "data this runner consumes," identified by stable id, described in prose, parameterized by named args, and shaped by a return type. Lives in `<dept>.needs.yaml`.
- **Callable spec** — a structured JSON description of how to satisfy a specific need against a specific connector. Persisted in `runner_callable_specs`. Walked by the dispatcher at runtime to invoke the underlying lib or MCP tool.
- **Setup adapter / Wizard adapter** — the LLM (typically the user's quick-tier model) that produces callable specs for runner needs at wizard time. Distinct from the runtime router.
- **Runtime router** — the LLM (typically the user's quick-tier model, e.g., Haiku) that picks the chat-conversation-relevant tool subset at conversation start.
- **Escalation tool** — the system-provided `request_additional_tools` tool that lets the main LLM ask the runtime router for additional tools mid-conversation.
- **Routing context** — the curated per-dept document at `<dept>.routing_context.md`. Read by the runtime router. Includes role, data needs, out-of-scope topics, and example prompts.
- **Department health** — runtime status (`active` | `disabled`) for each department, computed from the dept's declared required categories and (for runner-bearing depts) the resolution status of every declared need.

---

## Appendix B — Files touched

**New files:**
- `packages/core/src/openlia/connectors/python_lib.py` — pure-value types and adapter for python_lib mode
- `packages/core/src/openlia/connectors/runner_needs.py` — RunnerNeed, CallableSpec, parameter-binding logic
- `packages/server/src/openlia_server/services/runtime_router.py` — runtime tool routing
- `packages/server/src/openlia_server/services/callable_spec_resolver.py` — wizard-time adapter for callable specs
- `packages/server/src/openlia_server/services/dept_health.py` — health check service
- `packages/server/src/openlia_server/db/models/runner_callable_specs.py` — ORM
- `packages/server/alembic/versions/<rev>_runner_callable_specs.py` — migration
- `packages/core/src/openlia/departments/<dept>.routing_context.md` — one per dept (skeleton initially)
- `packages/core/src/openlia/departments/<dept>.needs.yaml` — for runner-bearing depts only
- `frontend/src/components/SetupWizard/PythonLibStep.tsx` — wizard step for python_lib mode
- `frontend/src/components/SetupWizard/CallableSpecReview.tsx` — per-need review with canary
- `frontend/src/components/Settings/DepartmentStatus.tsx` — dept health surface

**Modified files:**
- `packages/core/src/openlia/connectors/types.py` — add PYTHON_LIB to ConnectorSource; multi-mode launch
- `packages/core/src/openlia/connectors/dispatch.py` — add fetch_need; add candidate_tools_for_router
- `packages/server/src/openlia_server/db/models/connectors.py` — cached_python_callables column; multi-mode launch
- `packages/server/src/openlia_server/services/connectors_service.py` — multi-mode validation orchestration
- `packages/server/src/openlia_server/services/chat_runner.py` (and report_runner) — runtime router integration; escalation tool
- `packages/core/src/openlia/macro_research/assembler.py` — fetch_need for T1 inputs
- `packages/server/src/openlia_server/services/rs_runner.py` — fetch_need for posts/optional
- `packages/core/src/openlia/departments/*.py` — required_categories, optional_categories, requires_runner
- `frontend/src/pages/<Dept>.tsx` — disabled banner

**Deleted files:**
- `packages/core/src/openlia/departments/*.requirements.yaml` (after migration to needs.yaml + routing_context.md)
- everything already in scope for deletion via H6-H9 of the existing cutover plan

---

## Appendix C — Decision log

This redesign reflects the brainstorming session of 2026-04-27. Key decisions and their rationale:

1. **Unified `Connector` record with multi-mode launch (Option A in brainstorm Q1).** One API key per provider; allowlist coherence across modes; graceful degradation when modes are missing.
2. **Layer 1 is MCP-only.** Remote URL or CLI-installed MCP server. No arbitrary REST.
3. **Arbitrary user-supplied pip packages for Layer 3 (Option B in brainstorm Q2).** Adapter LLM does the resolution; built-in templates retain hand-curated mappings as a parallel path.
4. **Needs declared with stable id + prose description + parameters + shape.** Stable id for code references; prose for adapter targeting; parameters for runtime arguments; shape for canary validation.
5. **Parameterized needs (Option B in brainstorm Q4).** No cross-product blowup; matches real API shapes; runtime stays static.
6. **Runtime tool routing with conversation-scoped initial route + escalation tool.** Caching mostly preserved; reliability prioritized over cost; defense-in-depth via static validated tool inventory.
7. **Drop wizard chat-scoping LLM.** Runtime router has strictly more context; wizard adapter survives only for callable_spec resolution.
8. **Routing default-on with per-dept override (Option C in brainstorm).** Reliability priority; consistent UX; opt-out for depts that need determinism.
9. **Curated `routing_context.md` per dept.** Authored hand-curated in a separate session; replaces auto-extracted role descriptions; section structure includes example prompts as the highest-leverage routing signal.
10. **Department health and graceful disable.** All layers optional; dependencies declared per dept; user-facing surfaces in Settings, sidebar, dept page, scheduler, API.
11. **One callable spec per (department, need_id), day-1.** Multi-connector dynamic selection deferred.
12. **Retail Sentiment requires `financial` (not `social`).** Sentiment endpoints live inside financial connectors (EODHD, FMP). Resolves the day-1 social-gap concern.
