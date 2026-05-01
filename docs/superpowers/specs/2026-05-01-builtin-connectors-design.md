# Built-in Supported Connectors — Design

**Date:** 2026-05-01
**Branch:** `feat/batched-resolver`
**Supersedes:** spec §13.5 lock on empty day-1 catalog
**Companion:** `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md`

---

## 1. Goal

Ship a curated day-1 catalog of built-in connector templates so a user can enable a provider by pasting **only an API key**. OpenLIA owns every other detail — launch recipe, mode selection, and the runner-need-to-callable mapping.

User flow target: pick provider from catalog → paste API key → connector validated and immediately serving both chat-dept tools (where the provider has an MCP) and runner needs (per pre-baked mappings).

## 2. Day-1 catalog

Six providers, locked:

| `template_id` | Provider | Category | Modes installed under one key | Runner needs pre-mapped |
|---|---|---|---|---|
| `eodhd` | EODHD | financial | CLI MCP + Python lib (`eodhd`) | `debt_gdp`, `interest_revenue`, `gdp_yoy`, `cpi_yoy`, `cpi_core_yoy`, `pmi`, `stock_quote`, `social_posts` |
| `fmp` | Financial Modeling Prep | financial | CLI MCP + Python lib | same financial set as EODHD (alternate primary) |
| `newsapi_ai` | NewsAPI.ai (Event Registry) | news | Remote MCP or CLI MCP | `geopolitical_news` |
| `mediastack` | Mediastack | news | Python lib only (no upstream MCP) | `geopolitical_news` (alt) |
| `firecrawl` | Firecrawl | web_search | Remote MCP | `usd_fx_reserve_share`, `cb_gold_purchases`, `foreign_treasury_holdings` |
| `x` | X (Twitter) | social | Remote MCP | (chat-dept tools only) |

Notes:

- When a provider has both an MCP server and a Python SDK, the template installs both modes under one credential per spec §1.2. Chat-dept tools come from the MCP; runner needs use whichever mode the pre-baked `CallableSpec` points to.
- EODHD and FMP both satisfy the same financial needs. Either alone gives the user a working financial layer; the resolver already handles "multiple connectors satisfy this need" via existing routing.
- X has no runner-need mappings on day 1. It exists as a chat-dept tools provider.
- The three specialized macro needs (`usd_fx_reserve_share`, `cb_gold_purchases`, `foreign_treasury_holdings`) are served by Firecrawl scraping official-statistics websites (IMF COFER, World Gold Council, US Treasury TIC).

## 3. Schema extensions

Two additive changes to `packages/core/src/openlia/connectors`.

### 3.1 `BuiltInTemplate` gains `runner_specs`

`packages/core/src/openlia/connectors/builtins/types.py`:

```python
@dataclass(frozen=True)
class BuiltInTemplate:
    template_id: str
    display_name: str
    category: Category
    api_key_env_var: str
    available_modes: tuple[ModeRecipe, ...]
    canary_tool: str | None
    runner_specs: tuple[CallableSpec, ...]   # NEW
```

`runner_specs` is the curated table of `need_id` → concrete callable, baked into the template. Empty tuple = template serves chat tools only (e.g. `x`).

### 3.2 `CallableSpec` gains `result_path`

`packages/core/src/openlia/connectors/types.py`:

```python
@dataclass(frozen=True)
class CallableSpec:
    ...
    result_path: tuple[str, ...] = ()   # NEW
```

`result_path` is a JSON path tuple read at dispatch time. Empty tuple means "use whole result" (today's behavior — fully back-compatible with existing wizard-resolver output on `feat/batched-resolver`).

The wizard-time LLM resolver in `connectors/adapter/callable_spec_resolver.py` does **not** populate `result_path` for ad-hoc connectors; it stays `()` because the LLM picks methods that already return the right shape. `result_path` exists specifically for built-in templates that want to invoke a generic tool (e.g. `firecrawl_extract`) and reduce its dict result to the need's declared shape.

Dispatcher behavior: after invoking the tool/method, walk `result_path` into the result; if `result_path` is empty, return the result as-is.

## 4. Install-time flow

When the user installs a built-in template, the install path is:

1. Validate the API key by running the canary check on `template.canary_tool`.
2. Persist a `Connector` row with `launch=LaunchSpec(modes=template.available_modes)` and the user-supplied API key in the env-store under `template.api_key_env_var`.
3. **Skip the wizard-time adapter LLM.** Insert each entry of `template.runner_specs` directly as a `CallableSpec` row, swapping in the new connector's id.

Custom (non-built-in) connectors still go through the LLM resolver as today. The bypass is the only place the adapter LLM is skipped.

New backend route: `POST /api/connectors/install-builtin` with body `{template_id: str, api_key: str}`. Returns the created `Connector` row plus the validation outcome.

Existing `POST /api/connectors` (custom) stays unchanged.

## 5. Frontend

`frontend/src/setup/steps/ConnectorsStep.tsx` and `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx` already exist. Add:

- A **"Add from catalog"** path as the prominent default. Renders a grid of cards (one per built-in template) showing display name, category badge, one-line description, and the runner needs it satisfies. Clicking a card opens a single-field form (API key only). Submit → calls `POST /api/connectors/install-builtin`.
- The existing **"Add custom"** flow stays available as a less prominent secondary button.

The catalog list comes from a new endpoint `GET /api/connectors/builtins` that returns `list_templates()` projected to a UI-friendly shape (no recipe internals — only what the cards render).

## 6. Per-provider recipe shape

Each template's exact recipe values (MCP package names, version pins, Firecrawl extraction schemas, EODHD method names per indicator, NewsAPI.ai query parameters) are curated at implementation time. Design only fixes the *shape* of the curation work.

Recipe shape per template:

```python
BuiltInTemplate(
    template_id="<slug>",
    display_name="<human name>",
    category=Category.<X>,
    api_key_env_var="<UPPERCASE_KEY>",
    available_modes=(
        # zero-or-more of: CliMcpRecipe, RemoteMcpRecipe, PythonLibRecipe
    ),
    canary_tool="<tool/method name to ping with the API key>",
    runner_specs=(
        # zero-or-more CallableSpec, one per pre-mapped need
    ),
)
```

### 6.1 Worked example — Firecrawl, `usd_fx_reserve_share`

The need declares `shape: float` and has no parameters. Firecrawl's `firecrawl_extract` tool takes URLs + a JSON schema and returns structured data. The mapping prebinds URL and schema as constants and uses `result_path` to reduce the dict to a float.

```python
CallableSpec(
    need_id="usd_fx_reserve_share",
    access_mode="remote_mcp",
    tool_name="firecrawl_extract",
    constants={
        "urls": ["https://data.imf.org/regular.aspx?key=41175"],
        "prompt": "Extract the most recent USD share of allocated reserves, in percent.",
        "schema": {
            "type": "object",
            "properties": {"usd_share_pct": {"type": "number"}},
            "required": ["usd_share_pct"],
        },
    },
    param_bindings={},
    result_path=("data", "usd_share_pct"),
    shape="float",
)
```

`cb_gold_purchases` and `foreign_treasury_holdings` follow the same pattern with their own URLs, schemas, and result paths.

### 6.2 Worked example — EODHD, `debt_gdp` (Python lib mode)

```python
CallableSpec(
    need_id="debt_gdp",
    access_mode="python_lib",
    module="eodhd",
    method="APIClient.<macro-method-name-tbd>",
    instance_factory=InstanceFactory(cls="APIClient", args={"api_key": "$EODHD_API_KEY"}),
    param_bindings={"country": ParamBinding(to_arg="country", transform="iso_to_eodhd")},
    constants={"indicator": "<eodhd-indicator-code-tbd>"},
    result_path=(),
    shape="float",
)
```

The `iso_to_eodhd` transform already exists in `TRANSFORMS`. Method name and indicator code are filled in at implementation time after checking the `eodhd` SDK.

## 7. Spec §13.5 amendment

`docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md` §13.5 currently locks the day-1 catalog to empty. This design deliberately revisits that decision. The amendment edits §13.5 to: "Day-1 catalog ships six templates: EODHD, FMP, NewsAPI.ai, Mediastack, Firecrawl, X. The mode recipes and runner-need mappings are curated under the design at `docs/superpowers/specs/2026-05-01-builtin-connectors-design.md`."

The amendment is part of the implementation plan, not a separate change.

## 8. Risks and mitigations

- **Upstream MCP package drift** — pin versions in every `CliMcpRecipe.argv` and `PythonLibRecipe.pip_version`. Run canary on every install. Failures surface a clear "this template is broken because upstream X changed" message rather than a silent miss.
- **Firecrawl extract latency and cost on macro refresh** — World Order's three needs refresh quarterly/monthly. The Macro Research T1 cache (already in the runner pipeline) absorbs the cost.
- **Mediastack has no official MCP** — template ships Python-lib only. Chat depts don't see Mediastack tools; the runner need `geopolitical_news` still works.
- **EODHD/FMP coverage overlap** — intentional. Either alone gives the user a working financial layer. The existing runner-spec resolver picks whichever validated connector covers the need.
- **Specialized-macro scraping fragility** — IMF / WGC / Treasury sites change layout occasionally. Firecrawl's `firecrawl_extract` is layout-tolerant (LLM-driven), but a true page-structure change still breaks it. Macro Research's graceful-disable per spec §10 covers the failure mode: the dashboard reports "data unavailable" rather than emitting a wrong number.

## 9. Out of scope

- Layer 2 skills/plug-ins. The data model reserves a slot for skills; this design adds nothing to it.
- Localization of catalog card copy. English-only per existing project policy.
- A "browse marketplace" UX for community-contributed templates. The day-1 catalog is OpenLIA-curated and code-resident.
- Dynamic refresh of templates (e.g. updating the EODHD MCP version without a code release). Templates are versioned with the codebase.
