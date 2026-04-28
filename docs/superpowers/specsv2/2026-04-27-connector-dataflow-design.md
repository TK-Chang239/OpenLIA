# Connector Data Flow — Design

This document describes how OpenLIA's connector subsystem works. It is the canonical reference for the architecture: how a user configures connectors, how tools and data flow from the user's configuration into runtime, and how each department consumes them.

It is intentionally forward-looking. It documents the system as it should exist once the redesign at `docs/superpowers/specs/2026-04-27-connector-dataflow-redesign-design.md` is fully implemented. For the migration story (what changed, in what order, why), see that document.

---

## Table of contents

1. [Overview](#1-overview)
2. [Three customization layers](#2-three-customization-layers)
3. [Connector data model](#3-connector-data-model)
4. [Configuration: the wizard flow](#4-configuration-the-wizard-flow)
5. [Per-department artifacts](#5-per-department-artifacts)
6. [Parameterized runner needs](#6-parameterized-runner-needs)
7. [Wizard-time runner adapter](#7-wizard-time-runner-adapter)
8. [Runtime architecture: chat departments](#8-runtime-architecture-chat-departments)
9. [Runtime architecture: deterministic runners](#9-runtime-architecture-deterministic-runners)
10. [Department health and graceful disable](#10-department-health-and-graceful-disable)
11. [End-to-end walkthroughs](#11-end-to-end-walkthroughs)
12. [Glossary](#12-glossary)

---

## 1. Overview

### 1.1 What the connector subsystem is

The connector subsystem is the seam between OpenLIA's departments (Equity Research, Macro Research, Earnings Update, etc.) and external data — financial APIs, news APIs, Python libraries, MCP servers, social/sentiment endpoints. It owns three responsibilities:

1. **Configuration.** A clean wizard-driven path for the user to add data sources, provide credentials, and validate that the source works.
2. **Scoping.** Deciding which tools each department can see and call, when, and with what arguments.
3. **Dispatch.** Actually invoking the underlying API or library at runtime, returning the response to the calling department.

The subsystem is shared by every department. A department interacts with it through two interfaces depending on whether the department is LLM-driven or deterministic.

### 1.2 The two consumer kinds

OpenLIA's departments fall into two categories that consume data very differently:

- **LLM-driven (chat) departments.** Equity Research, Earnings Update, Morning Briefing, Secretary, Panic Thermometer. The user prompts the LLM; the LLM decides which tools to call. Tools are exposed to the LLM as JSON-schema'd tool definitions; the LLM emits `tool_use` events that the connector subsystem dispatches.
- **Deterministic-runner departments.** Macro Research's T1 stage, Retail Sentiment's data fetch. There is no LLM in the data-fetch path. The department's code declares a fixed set of typed needs ("debt-to-GDP for the user's selected country"); the connector subsystem resolves each need to a concrete callable and invokes it.

The same connector configured by the user can serve both kinds — an EODHD setup can expose tools to the LLM via MCP and serve runner needs via the Python SDK, all from one configuration with one API key.

### 1.3 Design priorities

In order:

1. **Reliability and accuracy.** Departments must always be able to find the data they need to answer correctly, or fail loudly with a clear "this is disabled because X" message. Silent wrong answers are the worst outcome.
2. **Decoupling.** Departments do not hardcode provider names or endpoint shapes. The dispatcher knows which provider satisfies which need; departments speak in their own vocabulary.
3. **Optional configuration.** All three customization layers are optional. The system functions with zero configuration; departments whose required dependencies are missing are cleanly disabled.
4. **Cost-aware.** Token usage is bounded but not the primary objective. Routing exists primarily to give the main LLM a smaller, more relevant tool set (better picks), not to save money.

---

## 2. Three customization layers

The user customizes OpenLIA across three independent layers. All are optional. Each addresses a different consumer.

### 2.1 Layer 1 — API tools for the LLM

MCP servers exposed to LLM-driven departments as tool definitions. Two configuration shapes:

- **Remote MCP** — a hosted URL with optional headers (e.g., `Authorization: Bearer ...`).
- **CLI MCP** — a local subprocess speaking MCP over stdio, launched via argv (e.g., `["uvx", "eodhd-mcp-server"]`) plus environment variables (typically the API key).

Layer 1 connectors expose tools to chat departments. Without any Layer 1 connectors, chat departments lose LLM tool-use capability and become severely limited or disabled (depending on dept declarations).

### 2.2 Layer 2 — Skills and plug-ins for the LLM

Optional supplementary capabilities that extend the LLM's behavior beyond tool-use. The data model reserves a slot for skills, and the wizard reserves a configuration step. The format and consumption mechanics are deferred to a follow-up design.

### 2.3 Layer 3 — Python libraries for deterministic runners

Arbitrary user-supplied pip packages that the connector subsystem invokes directly (not through MCP). The user provides:

- A pip package name, optionally with a version constraint.
- An import path (often the same as the pip name).
- An instance factory (if the lib uses a client class), with the API key bound to a configured environment variable.

The wizard-time runner adapter then introspects the lib's surface, reads the relevant department's declared `needs.yaml`, and produces structured callable specs that the runtime walks to invoke the lib at fetch time.

Layer 3 is required for any department whose runners need real data (Macro Research's T1, Retail Sentiment's data fetch). Without Layer 3 configured for a relevant provider, those departments are disabled.

### 2.4 Unified connector record across layers

A single `Connector` row per provider. The user adds EODHD once, supplies one API key, and chooses which access modes to enable for that provider — for example, both an MCP server (for LLM tool-use across chat departments) and the Python SDK (for runner needs in Macro Research and Retail Sentiment).

There is no runtime probing across modes. There is no MCP-fallback for runners: if a runner's needs are scoped against the python_lib mode and that mode is missing, the dependent departments are disabled — silent fallback to MCP would mask configuration mistakes that produce wrong data.

---

## 3. Connector data model

### 3.1 Core enums

```python
class Category(StrEnum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL = "social"
    WEB_SEARCH = "web_search"


class ConnectorSource(StrEnum):
    BUILT_IN = "built_in"        # canned recipe + API key
    REMOTE_MCP = "remote_mcp"    # hosted MCP URL
    CLI_MCP = "cli_mcp"          # local MCP subprocess
    PYTHON_LIB = "python_lib"    # pip-installed library
    SKILL = "skill"              # reserved for Layer 2


class ConnectorStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"
```

### 3.2 The Connector row

```python
class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(primary_key=True)
    provider_id: Mapped[str]                # e.g. "eodhd", "fmp", "newsapi_ai"
    display_name: Mapped[str]
    category: Mapped[Category]
    status: Mapped[ConnectorStatus]
    secrets: Mapped[dict]                   # {"EODHD_API_KEY": "..."} — plaintext

    launch: Mapped[dict]                    # see §3.3
    cached_tools: Mapped[list[dict] | None]              # MCP modes
    cached_python_callables: Mapped[list[dict] | None]   # python_lib mode

    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    validated_at: Mapped[datetime | None]
```

One row per provider the user has added. The same `provider_id` can have multiple modes enabled but is a single row with one set of secrets.

API keys live in `secrets` as a plaintext key→value map. OpenLIA's threat model is admin-hosted single-tenant: the admin runs the server on their own machine and is the only party with filesystem access. Database-level encryption added complexity without raising the bar against any plausible attacker — anyone who could read `app.db` could read the secret-key file alongside it. Operational hygiene (`.gitignore`, file permissions, exclude-from-backups) is the right control instead.

### 3.3 Multi-mode launch

`Connector.launch` is a JSON object with one entry per access mode the user has enabled for this connector. Each entry carries its own kind and per-kind configuration.

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

Notation: `$EODHD_API_KEY` is a placeholder that the connector subsystem substitutes at instance-construction time with the value of the corresponding entry in `Connector.secrets`. The user never types the key into the launch spec; it lives in `secrets` and is injected at use time. For `cli_mcp` modes, `env_keys` lists which `secrets` entries to copy into the subprocess environment.

### 3.4 Built-in templates

The connector subsystem ships a curated catalog of built-in templates — known providers with pre-wired launch shapes. A built-in entry declares:

```python
@dataclass(frozen=True)
class BuiltInTemplate:
    template_id: str                          # e.g. "eodhd"
    display_name: str
    category: Category
    api_key_env_var: str                      # e.g. "EODHD_API_KEY"
    available_modes: tuple[ModeRecipe, ...]   # one per access mode this template ships
    canary_tool: str | None                   # for MCP validation
```

A `ModeRecipe` is a typed shape: an MCP-CLI recipe carries argv; a python_lib recipe carries pip_name + import_module + instance_factory. When the user picks a built-in, the wizard offers checkboxes for each available mode and the selected ones become entries in `Connector.launch`.

### 3.5 Persistence for runner callable specs

Resolved callable specs for runner needs live in their own table:

```python
class RunnerCallableSpec(Base):
    __tablename__ = "runner_callable_specs"

    id: Mapped[str] = mapped_column(primary_key=True)
    department_id: Mapped[str]                 # e.g. "macro_research"
    need_id: Mapped[str]                       # e.g. "debt_gdp"
    connector_id: Mapped[str] = mapped_column(ForeignKey("connectors.id"))
    access_mode: Mapped[str]                   # "cli_mcp" | "remote_mcp" | "python_lib"
    spec: Mapped[dict]                         # structured callable spec; see §6.4
    canary_value: Mapped[dict | None]          # captured response sample
    canary_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("department_id", "need_id", name="uq_dept_need"),
    )
```

One spec per (department, need_id) pair. If multiple connectors could satisfy the same need, the user picks one at scoping time and that connector's spec is persisted. (Multi-connector dynamic selection at fetch time is a future evolution; not part of this design.)

### 3.6 What the data model does not contain

- **No `tool_allowlists` table.** Chat departments do not have per-(dept, connector, tool) allowlist rows. The runtime router operates against the full validated tool inventory.
- **No `data_providers` or `data_provider_requirement_mapping`.** The legacy provider system is fully replaced by `connectors` + `runner_callable_specs`.
- **No persisted "tool subset per conversation."** Routing decisions are ephemeral; the dispatcher recomputes them per conversation.

---

## 4. Configuration: the wizard flow

### 4.1 Adding a connector

The wizard's add-connector flow asks the user to pick one of four sources:

1. **A built-in template** (from the curated catalog).
2. **A remote MCP URL** with optional headers.
3. **A local CLI MCP launch** with argv and env keys.
4. **A Python library** with pip package, import path, and instance factory.

For built-ins, the wizard then offers checkboxes for each access mode the template ships ("Enable MCP server (recommended for chat)?" and "Enable Python library (required for runner-driven dashboards)?"). For non-built-ins, the wizard accepts the user's manual configuration.

The user provides the API key. The server stores it in `Connector.secrets` keyed by the env-var name (e.g. `{"EODHD_API_KEY": "..."}`) and persists the connector row with `status=PENDING`. Per §3.2, secrets are stored in plaintext under the admin-hosted threat model; the server takes care never to log secret values.

### 4.2 Validation per mode

Each enabled access mode validates independently. The connector transitions to `VALIDATED` only when all enabled modes succeed.

#### CLI-MCP and Remote-MCP

1. Spawn the MCP server (subprocess for CLI; HTTP session for remote).
2. Call `list_tools()`; persist the result as `cached_tools`.
3. If the template declares a `canary_tool`, invoke it with no arguments (or a known sample), assert a non-error response.
4. Tear down the connection.

#### Python_lib

1. Verify the pip package is importable in the OpenLIA process. Capture the resolved version.
2. Walk the public surface of the import target via `inspect.signature`, `inspect.getdoc`, etc. Persist as `cached_python_callables`. Each entry: `{"qualname": "APIClient.real_time_quote", "signature": "(symbol: str) -> dict", "doc": "..."}`.
3. (Validation here stops at importability + introspection. Per-need callable_spec validation happens during scoping, §7.)

#### Skill

Reserved for Layer 2. Validation deferred to its follow-up design.

### 4.3 Wizard-time scoping for runner needs

Once a connector is `VALIDATED`, the wizard runs the runner adapter (§7) for each runner-bearing department whose required category matches the connector's category. The adapter produces a proposed callable spec per need, and the wizard surfaces a per-need review card with a canary sample (§4.4).

### 4.4 Per-need review

For each runner-bearing department, the user sees a card per need:

```
Macro Research — debt_gdp
"Government gross debt as a percentage of GDP, in percentage points
 (e.g., 110.0 means 110%)."

Resolved against: EODHD (python_lib)
   eodhd.APIClient.economic_data(country=country_code, indicator='DEBT_GDP_PCT')

Sample for country='US': 122.4

[Approve]  [Re-resolve]  [Try a different connector]
```

On approval, the spec is persisted in `runner_callable_specs`. "Re-resolve" runs the adapter again with a biased prompt; "Try a different connector" routes the resolution to another configured connector for the same category.

### 4.5 Chat-department configuration

There is no per-tool configuration step for chat departments. The wizard's chat-dept summary states: "X tools available across N connectors. Routed dynamically per conversation." Once connectors are validated, chat departments see them automatically through the runtime router.

### 4.6 First-run summary

After the wizard completes, OpenLIA shows a department status summary:

```
Departments: 4 of 7 active.
✓ Active: Equity Research, Earnings Update, Morning Briefing, Secretary
⚠ Disabled: Macro Research (configure Python library for EODHD),
            Retail Sentiment, Panic Thermometer

You can configure additional connectors anytime from Settings.
```

Each disabled dept's reason is the human-readable output of the health check (§10).

---

## 5. Per-department artifacts

Each department directory holds a small, focused set of files. Each file has exactly one consumer.

### 5.1 File layout

```
packages/core/src/openlia/departments/
├── earnings_update.py
├── earnings_update.routing_context.md
├── equity_research.py
├── equity_research.routing_context.md
├── macro_research.py
├── macro_research.routing_context.md
├── macro_research.needs.yaml
├── morning_briefing.py
├── morning_briefing.routing_context.md
├── panic_thermometer.py
├── panic_thermometer.routing_context.md
├── retail_sentiment.py
├── retail_sentiment.routing_context.md
├── retail_sentiment.needs.yaml
├── secretary.py
├── secretary.routing_context.md
└── loader.py
```

Every dept has a `.py` and a `.routing_context.md`. Departments with deterministic runners additionally have a `.needs.yaml`.

### 5.2 The `<dept>.py` dataclass

Code-level metadata for the department:

```python
@dataclass(frozen=True)
class MacroResearchDepartment:
    name: str = "macro_research"
    display_name: str = "Macro Research"
    prompt_name: str = "macro_research"
    tier: Tier = "thinking"

    # Connector dependencies
    required_categories: tuple[Category, ...] = (Category.FINANCIAL,)
    optional_categories: tuple[Category, ...] = (Category.NEWS,)

    # Runtime behavior
    requires_runner: bool = True
    disable_runtime_routing: bool = False
```

`required_categories` and `optional_categories` declare which connector categories the dept needs to function. The health check (§10) walks these.

`requires_runner` tells the health check to also verify that every need declared in `<dept>.needs.yaml` has a resolved callable spec.

`disable_runtime_routing`, when `True`, skips the runtime router for this dept's chat conversations and exposes the full validated tool inventory to the main LLM. Default `False`. Used for departments that need maximum determinism.

### 5.3 The `<dept>.routing_context.md` document

Curated routing context for the runtime router. Markdown, sized 300-800 tokens per dept. Loaded once at startup; injected into the runtime router's prompt template.

```markdown
# Equity Research — Routing Context

## What this department does
Bottoms-up analysis of individual companies. Focuses on fundamentals,
earnings drivers, news catalysts, and valuation context. Single-name
outputs; not portfolio-level.

## Data this department needs access to
[Curated, drawn from frameworks, specs, and the dept's code.
 Examples of the kinds of API endpoints / tools the router should
 bias toward when prompts touch each topic.]

## Out-of-scope topics
[What this dept does NOT handle. Helps the router not over-reach
 into other depts' territory.]

## Example prompts and the data they imply
[3-6 representative prompts paired with the kind of tools the router
 should pick. Few-shot ground truth.]
```

The "Example prompts" section is the highest-leverage piece for routing quality and warrants careful curation.

### 5.4 The `<dept>.needs.yaml` declaration

Only present for departments with `requires_runner=True`. Declares the parameterized needs the dept's runners consume.

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
```

### 5.5 The loader and drift safety

`packages/core/src/openlia/departments/loader.py` exposes:

```python
def load_routing_context(department_id: str) -> str: ...
def load_needs(department_id: str) -> list[RunnerNeed]: ...
def all_departments() -> list[Department]: ...
```

A test (`test_department_artifacts.py`) asserts:

1. Every department has a `<dept>.routing_context.md` of at least N tokens with all expected H2 sections.
2. Every dept with `requires_runner=True` has a non-empty `<dept>.needs.yaml`.
3. Every `id` referenced from runner code (e.g., `T1_NEEDS`) exists in the dept's `needs.yaml`.
4. Every `id` declared in `needs.yaml` is referenced from at least one runner.

---

## 6. Parameterized runner needs

The unit of "data this runner consumes" is a **need**: a stable, code-facing identifier paired with a prose description, a typed parameter list, and a return shape.

### 6.1 Need declaration

| Field | Type | Purpose |
|---|---|---|
| `id` | string | Stable code-facing identifier. Referenced from runner code, formulas, response payloads. Treated as a public API; never changes once shipped. |
| `description` | prose | Adapter LLM input. Rich enough to disambiguate intent including units, conventions, and edge cases. |
| `parameters` | list of `{name, description, type, required, default}` | Runtime arguments. The runner supplies values per call; the dispatcher binds them per the callable spec. |
| `shape` | string type hint | Return value shape. Used to validate canary responses during scoping. |

### 6.2 Three categories of arguments

The callable spec produced by the adapter cleanly separates:

- **Auth.** Handled by the connector layer. Resolved from `Connector.secrets` at instance-construction time (see §3.2). Never appears in the callable spec.
- **Constants.** Baked into the callable spec at scoping time (e.g., `fmt: json`, `indicator: DEBT_GDP_PCT`).
- **Runtime arguments.** Supplied by the runner per call; declared in the need's `parameters`.

### 6.3 Runner usage

Runners declare their needs via id tuples and call by id:

```python
debt_value = await dispatcher.fetch_need("debt_gdp", country="US")
tip_price = await dispatcher.fetch_need("stock_quote", ticker="TIP")
```

The dispatcher walks the persisted callable spec, binds the runner-supplied parameters per the binding rules (renaming, transforms, defaults), invokes the underlying lib (or MCP), and returns the result.

### 6.4 Callable spec shape

For a `python_lib` access mode:

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
  "shape": "float"
}
```

For an MCP access mode:

```json
{
  "need_id": "debt_gdp",
  "access_mode": "cli_mcp",
  "tool_name": "get_economic_indicator",
  "param_bindings": {
    "country": {"to_arg": "country", "transform": "upper"}
  },
  "constants": {"indicator": "DEBT_GDP_PCT"},
  "shape": "float"
}
```

The dispatcher's `fetch_need` walks this structured data; no LLM is in the runtime path; no `eval` of code strings.

### 6.5 Parameter binding semantics

`param_bindings` maps a need's parameter name to the underlying lib/tool's argument:

- `to_arg` — the underlying argument name (often differs from the need's parameter name).
- `transform` — an optional, named transformation applied to the value (e.g., `upper` to uppercase, `iso_to_eodhd` to convert `"US"` to `"US.NYSE"`). The set of allowed transforms is enumerated in the implementation; the adapter LLM is constrained to pick from that set.

### 6.6 Optional and defaulted parameters

A need's parameter can be optional (`required: false`) with a default value. If the runner does not supply the parameter at call time, the dispatcher uses the default. This pattern is common for things like `country` where `"US"` is a sensible default for most calls.

---

## 7. Wizard-time runner adapter

The wizard-time adapter is an LLM (typically the user's quick-tier model) that has one job: produce structured callable specs for runner needs.

### 7.1 Inputs

For each (validated connector, runner-bearing department) pair where the connector's category is in the dept's required or optional categories:

- The connector's `cached_python_callables` (for python_lib mode) or `cached_tools` (for MCP modes).
- The dept's `<dept>.needs.yaml` content.
- For each need, the relevant function signatures, docstrings, and (during the canary phase) sample data.

### 7.2 Output

For each need, a proposed callable spec (§6.4) plus a canary execution result.

### 7.3 Algorithm

For each need in `<dept>.needs.yaml`:

1. The adapter LLM receives the need's description + parameter list + shape, plus the connector's available functions/tools. It proposes: (a) which function/tool satisfies the need; (b) parameter bindings; (c) constants to bake in; (d) any transforms.
2. The connector subsystem validates the proposal: the chosen function exists; declared parameters bind to actual function arguments; constants are valid for those arguments.
3. **Canary execution.** With sample values for each declared parameter (default values where defined; otherwise an adapter-provided plausible sample), invoke the bound callable and capture the response.
4. **Shape check.** Verify the response matches the declared `shape`. A `float` shape requires a numeric response; a `list[object]` requires a list; etc.
5. The user approves the spec via the wizard's per-need review card (§4.4). On approval, the spec persists in `runner_callable_specs` along with the canary value and timestamp.

### 7.4 What the adapter does not do

- It does not produce tool allowlists for chat departments. That role is gone; chat scoping happens at runtime (§8).
- It does not invent identifiers. Need ids are authored by humans in `needs.yaml`; the adapter binds them, not invents them.
- It does not make trust decisions about pip packages. The user is responsible for installing the package; the adapter validates that imports succeed and that bound calls produce reasonable responses.

### 7.5 Re-resolution

When the user adds a new connector, removes one, or asks the wizard to re-resolve a specific need:

- The adapter runs against the affected (department, need_id) pairs.
- New callable specs replace existing ones (subject to user approval per need).
- If a need previously had a spec resolved against a now-removed connector, the spec is invalidated; the dept's health drops to disabled until a new connector satisfies the need.

---

## 8. Runtime architecture: chat departments

Chat departments operate on conversations. The user sends a prompt; the LLM responds, possibly using tools across one or more rounds. The connector subsystem provides the LLM's tool set per conversation.

### 8.1 Candidate pool

Each chat department's candidate pool — the set of tools eligible for the runtime router to choose from — is the **full validated tool inventory across all configured connectors**. There is no per-dept allowlist. Categories the dept declares as required or optional are not used to gate the candidate pool; the runtime router decides per-prompt which tools fit.

### 8.2 Conversation-scoped routing

When a user opens a conversation with a chat department:

1. The orchestrator collects: the user's first message, the dept's `<dept>.routing_context.md`, the candidate pool of tools.
2. It calls the **runtime router** — an LLM, typically Haiku-tier — with the prompt template described in §8.4.
3. The router returns a subset of tool names.
4. The orchestrator constructs the main LLM's tool list as: `(routed_subset) + (escalation tool)`. The escalation tool (§8.5) is always present.
5. The main LLM (Sonnet or Opus tier, depending on dept config) responds using this tool set.

The router runs **once** per conversation start. Subsequent turns within the same conversation reuse the same tool set, preserving prompt-caching benefits.

### 8.3 Tool name prefixing

Every tool the dispatcher exposes is prefixed with the connector's `provider_id`:

- `eodhd__get_quote`
- `fmp__get_company_profile`
- `newsapi_ai__search_articles`

The prefix lets the dispatcher route a `tool_use` event back to the correct connector even when multiple connectors expose tools with the same underlying name. The main LLM sees prefixed names; the underlying MCP or library never does.

### 8.4 Router prompt template

```
You are routing tools for the {department_id} department.

{routing_context}

User prompt:
{user_prompt}

Available tools (the dept's full validated tool inventory):
{candidate_tools_json}

Pick the smallest subset of tools that lets the main LLM answer this
prompt well.

Be liberal: if a tool might plausibly be useful during the conversation,
include it.

Be conservative: do not include tools that are clearly off-topic for
the dept.

Return the chosen tools as a JSON array of tool names.
```

The router's output is parsed as a JSON array of strings; tools whose names are not in the candidate pool are silently dropped.

### 8.5 The escalation tool

Every routed conversation includes a system-provided escalation tool:

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
        "properties": {"reason": {"type": "string"}},
        "required": ["reason"]
    }
}
```

When the main LLM emits a `tool_use` for `request_additional_tools`:

1. The orchestrator pauses the main LLM turn.
2. It calls the runtime router again with: the recent conversation turns, the current tool set, the LLM's escalation reason, and the dept's full candidate pool.
3. The router returns N additional tools (N may be 0 if nothing else applies).
4. The orchestrator merges the additional tools into the conversation's tool set. **The set only grows, never shrinks.**
5. The main LLM continues with the expanded set. The escalation's `tool_result` is a brief summary: `"Added tools: get_company_news, get_analyst_estimates."`

Multiple escalations across a long conversation are allowed. Each one grows the tool set monotonically.

### 8.6 Cache behavior

Tool definitions live in the cached prompt prefix. The orchestrator structures the main LLM's prompt so the cache breakpoint is set before the routed tools:

```
[cached: system instructions]
[cached: dept role prefix]
[cached: routed tool definitions] ← cache-eligible for the conversation
[append-only: conversation history]
```

For most conversations, the cache hits on every turn after the first, reducing per-turn cost substantially. On escalation, the tool list changes — the cache invalidates from that point — then re-stabilizes on the expanded set for subsequent turns.

### 8.7 Routing override per department

A department can opt out of routing by setting `disable_runtime_routing=True` on its dataclass. When opted out, the orchestrator skips the router and exposes the full candidate pool directly to the main LLM. The escalation tool is omitted (no point — every tool is already present).

This override is reserved for departments that need maximum tool determinism. It is `False` by default for every dept.

### 8.8 Defense in depth

The runtime router is bounded by the dept's validated tool inventory. It cannot return tools from connectors with `status != VALIDATED`. A bug or hallucination in the router cannot expose unvalidated or unknown tools.

---

## 9. Runtime architecture: deterministic runners

Deterministic runners — Macro Research's T1 stage, Retail Sentiment's data fetch, future scheduled jobs — consume data without an LLM in the path.

### 9.1 The contract

Runners declare their needs via id tuples and call the dispatcher by id:

```python
debt_value = await dispatcher.fetch_need("debt_gdp", country="US")
posts = await dispatcher.fetch_need("social_posts", ticker="AAPL")
```

The dispatcher resolves `(current_department, need_id)` → callable spec, binds the runtime arguments per the spec, invokes the appropriate access mode (`python_lib`, `cli_mcp`, or `remote_mcp`), and returns the raw response.

### 9.2 Department context

The dispatcher knows which department is calling because the runner has set the context:

```python
async with dispatcher.in_department("macro_research"):
    debt = await dispatcher.fetch_need("debt_gdp", country="US")
```

The `in_department` context manager scopes subsequent `fetch_need` calls to that dept's `runner_callable_specs` rows. Without an active department context, `fetch_need` raises.

### 9.3 Failure semantics

If a runner's needed callable spec is missing — no row in `runner_callable_specs` for `(current_department, need_id)` — `fetch_need` raises a clear, structured exception. This case should not normally be reached, because the dept's health check (§10) would have flagged it as disabled before any runner code executes. The runtime exception is a defensive guarantee, not an expected error path.

If the bound call fails (lib raises, MCP returns an error, network timeout), `fetch_need` propagates the failure. There is no automatic fallback to a different connector or access mode. Callers must handle (retry, mark stale, surface to user) explicitly.

### 9.4 Macro Research T1 stage

The T1 stage of MR's dashboards iterates over declared needs and fetches each:

```python
async with dispatcher.in_department("macro_research"):
    t1_data = {}
    for need_id in dashboard.T1_NEEDS:
        runtime_args = dashboard.runtime_args_for(need_id)
        t1_data[need_id] = await dispatcher.fetch_need(need_id, **runtime_args)
```

Where `dashboard.runtime_args_for(need_id)` provides the dashboard-specific parameters — for example, the user's selected country, the relevant ticker for a stock_quote need, etc.

### 9.5 Retail Sentiment data fetch

RS fetches social posts via a sentiment endpoint exposed by financial connectors:

```python
async def _fetch_posts(self, ticker: str) -> list[RawSocialPost]:
    async with self._dispatcher.in_department("retail_sentiment"):
        raw = await self._dispatcher.fetch_need("social_posts", ticker=ticker)
    return [RawSocialPost.from_dict(item) for item in raw]
```

`<retail_sentiment>.needs.yaml` declares `social_posts` with a description that says it pulls from the financial connector's sentiment endpoint. The wizard adapter resolves `social_posts → eodhd.APIClient.sentiment_data(ticker=ticker)` (or the FMP equivalent).

This is why RS's `required_categories` is `(financial,)` rather than `(social,)` — its data source lives inside financial connectors, not in a separate social provider.

### 9.6 Scheduler integration

Scheduled jobs (cron-driven runner invocations) check dept health before invoking the runner:

```python
def run_macro_research_job():
    health = check_dept_health(macro_research_dept, db_session)
    if health.status == "disabled":
        log.info("skipped: %s — %s", health.department_id, health.reason)
        return
    runner.run(...)
```

A disabled dept's scheduled jobs are skipped silently (with logging) rather than failing.

---

## 10. Department health and graceful disable

All three customization layers are optional. The system must function with zero configuration; departments whose required dependencies are missing become disabled with a clear, user-facing reason rather than producing errors at request time.

### 10.1 Department dependency declarations

Every department's dataclass declares its dependencies:

```python
required_categories: tuple[Category, ...]
optional_categories: tuple[Category, ...]
requires_runner: bool
```

Day-1 declared dependencies:

| Department | required_categories | optional_categories | requires_runner |
|---|---|---|---|
| Secretary | () | (web_search,) | False |
| Equity Research | (financial,) | (news, social, web_search) | False |
| Earnings Update | (financial,) | (news,) | False |
| Morning Briefing | (financial, news) | (web_search,) | False |
| Macro Research | (financial,) | (news,) | True |
| Retail Sentiment | (financial,) | (news, social) | True |
| Panic Thermometer | (financial,) | (news,) | False |

Notes on specific entries:

- **Secretary** has no required categories. It is a zero-config conversational dept that can answer general questions without external tools. It never disables.
- **Retail Sentiment** requires `financial`, not `social`, because its sentiment data comes from financial connectors' sentiment endpoints (EODHD, FMP). A standalone social-category connector is not required for RS to function.

### 10.2 Health check

`packages/server/src/openlia_server/services/dept_health.py`:

```python
@dataclass(frozen=True)
class DeptHealth:
    department_id: str
    status: Literal["active", "disabled"]
    reason: str | None  # human-readable; populated when disabled


def check_dept_health(dept: Department, db: Session) -> DeptHealth:
    missing = [
        c for c in dept.required_categories
        if not has_validated_connector_in_category(db, c)
    ]
    if missing:
        return DeptHealth(
            department_id=dept.name,
            status="disabled",
            reason=f"No connector configured for required categories: "
                   f"{', '.join(c.value for c in missing)}",
        )
    if dept.requires_runner:
        unresolved = needs_without_callable_spec(db, dept.name)
        if unresolved:
            return DeptHealth(
                department_id=dept.name,
                status="disabled",
                reason=f"No callable spec resolved for runner needs: "
                       f"{', '.join(unresolved)}. Configure a Python "
                       f"library mode for the relevant financial connector.",
            )
    return DeptHealth(department_id=dept.name, status="active", reason=None)
```

The health check runs:

- At app startup (populating `app.state.dept_health`).
- Whenever a connector transitions to or from `VALIDATED` status.
- Whenever a callable spec is added, removed, or invalidated.

Each health change atomically updates `app.state.dept_health` and invalidates any per-dept caches keyed on health.

### 10.3 User-facing surfaces

**Settings → Departments tab.** Lists every department with a health badge and reason. Disabled depts include a `[Configure connectors →]` link that deep-links to the relevant wizard step.

**Sidebar.** Disabled departments appear greyed out with a tooltip ("Disabled — see Settings to configure"). Clicking still navigates to the dept page, which shows the disabled banner.

**Department page (when disabled).** A banner at the top:

```
This department is disabled.
[reason from DeptHealth]
[Configure connectors →]
```

Below the banner, the dept's UI renders in a read-only state showing whatever cached data exists from prior runs (if any).

**API endpoints.**

- Mutating endpoints (start a chat, run a report, refresh a dashboard): `409 Conflict` with `{"reason": "<DeptHealth.reason>"}`.
- Read endpoints (fetch cached state): continue to work; clients can render historical data even when the dept is disabled.

**Scheduler.** Disabled depts' scheduled jobs log `skipped: <reason>` and do not invoke the runner.

### 10.4 Re-enablement

Health is dynamic. When the user adds a connector that satisfies a previously-disabled dept's requirements, the dept becomes active immediately on the next health-check tick — no app restart required. The frontend polls (or subscribes) to dept-health changes and updates the sidebar/Settings view accordingly.

A re-enabled dept's scheduled jobs resume on the next cron tick.

---

## 11. End-to-end walkthroughs

Concrete scenarios that exercise the full stack.

### 11.1 New user opens the wizard with zero connectors

1. Wizard shows the welcome step. No connectors configured.
2. User skips through without adding anything.
3. Health check runs: every dept with a `required_categories` is disabled. Only Secretary is active (it has no required categories).
4. First-run summary: "1 of 7 departments active. The following are disabled: ... You can configure connectors anytime from Settings."
5. User opens Equity Research from the sidebar (greyed out, but clickable). Sees the disabled banner: "No connector configured for required categories: financial."
6. User clicks "Configure connectors" → returns to Settings → adds an EODHD MCP connector.
7. Validation passes; status becomes `VALIDATED`. Health check re-runs. Equity Research, Earnings Update, Morning Briefing (if news is also configured), and Panic Thermometer become active. Sidebar updates. Banner disappears.

### 11.2 User adds EODHD with both MCP and Python library

1. User picks the built-in EODHD template. Wizard shows checkboxes: ✓ MCP server, ✓ Python library.
2. User checks both, provides API key.
3. Server stores key in `Connector.secrets`, persists `Connector{provider_id="eodhd", secrets={"EODHD_API_KEY": "..."}, launch={"modes": [cli_mcp, python_lib]}}` with `status=PENDING`.
4. CLI-MCP validation: spawn `uvx eodhd-mcp-server`, list_tools (returns ~20 tools), invoke canary tool. Cache tools.
5. Python_lib validation: import `eodhd`, walk `APIClient` surface, cache callables.
6. Both modes pass. Status → `VALIDATED`.
7. Wizard runs the runner adapter for Macro Research and Retail Sentiment (both have `required=financial` and EODHD is in the financial category):
   - For each need in `macro_research.needs.yaml` (debt_gdp, stock_quote, etc.), the adapter proposes a callable spec against the EODHD python_lib mode and runs a canary call.
   - For each need in `retail_sentiment.needs.yaml` (social_posts), same.
8. Wizard shows per-need review cards. User approves all.
9. Specs persist in `runner_callable_specs`. Health check re-runs. Macro Research and Retail Sentiment become active.

### 11.3 User opens an Equity Research chat

1. User types: "How is AAPL trading and what's the sentiment around the Q3 earnings?"
2. Orchestrator builds the candidate pool: union of all validated tools across all connectors (e.g., 15 tools from EODHD + 10 from FMP + 5 from NewsAPI.ai = 30 tools total).
3. Orchestrator calls the runtime router with: user prompt, dept's routing_context, candidate pool.
4. Router returns 6 tools: `eodhd__get_quote`, `eodhd__get_earnings_data`, `eodhd__sentiment_data`, `fmp__get_company_profile`, `fmp__earnings_call_transcript`, `newsapi_ai__search_articles`.
5. Orchestrator adds the escalation tool. Main LLM sees 7 tools.
6. Main LLM responds: emits `tool_use` for `eodhd__get_quote` to fetch AAPL price, then `eodhd__get_earnings_data` for Q3 figures, then `eodhd__sentiment_data` and `newsapi_ai__search_articles` for sentiment context. Composes an answer.
7. Conversation continues. Same tool set (7 tools) for subsequent turns. Cache hits on the tool prefix.

### 11.4 Mid-conversation tool escalation

1. Same conversation as 11.3. User now asks: "What are insiders doing? Any recent buying or selling?"
2. Main LLM looks at its tool set: no insider-transaction tool. Emits `tool_use` for `request_additional_tools` with reason: "I need insider transactions data for AAPL."
3. Orchestrator pauses, calls router again with: recent conversation, current tool set, escalation reason, full candidate pool.
4. Router returns: `[eodhd__get_insider_transactions]`.
5. Orchestrator merges into tool set. Returns escalation `tool_result`: `"Added tools: eodhd__get_insider_transactions."`
6. Main LLM continues, calls the new tool, answers. Conversation tool set is now 8 tools for the rest of the conversation.

### 11.5 Macro Research dashboard refresh

1. Scheduled cron job ticks for the user's "Debt Cycle" dashboard.
2. Job pre-flight: `check_dept_health(macro_research_dept, db)` returns `active`.
3. Job invokes `MRRunner.run(dashboard_slug="debt_cycle", ...)`.
4. Inside the runner: `async with dispatcher.in_department("macro_research"): ...`
5. For each need in `dashboard.T1_NEEDS` (debt_gdp, interest_revenue, tips_quote, dxy_proxy):
   - `dispatcher.fetch_need("debt_gdp", country=user_country)` looks up the `(macro_research, debt_gdp)` row in `runner_callable_specs`, finds the EODHD python_lib spec.
   - Walks the spec: instantiates `eodhd.APIClient(api_key=secrets["EODHD_API_KEY"])`, calls `.economic_data(country_code="US", indicator="DEBT_GDP_PCT")`, returns the float result.
6. T1 data populated. T2 formulas compute. T3 dashboard renders. T4 LLM narrative composes.

### 11.6 User removes the only EODHD connector

1. User deletes the EODHD connector from Settings.
2. Connector row deleted; `runner_callable_specs` rows referencing it are cascaded.
3. Health check re-runs. Macro Research's needs are now unresolved → disabled. Retail Sentiment's `social_posts` need is unresolved → disabled. Equity Research, Earnings Update, etc. lose their `financial` connector → disabled.
4. Sidebar updates: 4 of 7 depts now greyed out.
5. Active dashboards continue rendering historical cached data with a "stale, dept disabled" indicator. New runs are blocked at the API boundary (409).

---

## 12. Glossary

- **Connector** — a single configured provider (e.g., the user's EODHD setup). One row in `connectors`. May expose multiple **access modes** (cli_mcp, remote_mcp, python_lib, eventually skill).
- **Access mode** — one way of invoking a provider (MCP server vs. Python library). Modes are configured per connector at setup time and validated independently.
- **Built-in template** — a curated recipe in OpenLIA's catalog for a known provider (EODHD, FMP, etc.). Encodes the launch shape and available modes; the user provides only the API key.
- **Need** — a declarative unit of "data this runner consumes," identified by a stable id, described in prose, parameterized by named arguments, and shaped by a return type. Lives in `<dept>.needs.yaml`. Treated as a public API; the id never changes once shipped.
- **Callable spec** — a structured JSON description of how to satisfy a specific need against a specific connector. Persisted in `runner_callable_specs`. Walked by the dispatcher at runtime.
- **Dispatcher** — the runtime object that hydrates from the DB and exposes two interfaces: `dispatch_tool_use(name, args)` for chat departments and `fetch_need(need_id, **args)` for runners.
- **Wizard-time runner adapter** — the LLM (typically the user's quick-tier model) that produces callable specs for runner needs at wizard time. Distinct from the runtime router.
- **Runtime router** — the LLM (typically Haiku-tier) that picks the chat-conversation-relevant tool subset at conversation start. Runs once per conversation; re-invoked on escalation.
- **Escalation tool** — the system-provided `request_additional_tools` tool that lets the main LLM ask the runtime router for additional tools mid-conversation. The dept's tool set grows; never shrinks.
- **Routing context** — the curated per-dept document at `<dept>.routing_context.md`. Read by the runtime router. Includes role, data needs, out-of-scope topics, and example prompts.
- **Department health** — runtime status (`active` | `disabled`) for each dept, computed from the dept's declared required categories and (for runner-bearing depts) the resolution status of every declared need.
- **Candidate pool** — for chat departments, the full validated tool inventory across all configured connectors. The runtime router selects from this pool.
