# Built-in Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a curated day-1 catalog of six built-in connector templates (EODHD, FMP, NewsAPI.ai, Mediastack, Firecrawl, X) so a user can enable a provider by pasting only an API key, with all runner-need-to-callable mappings pre-baked.

**Architecture:** Two additive schema changes (`runner_specs` on `BuiltInTemplate`, `result_path` on `CallableSpec`); one curated registry module per provider; one new install path that bypasses the wizard-time adapter LLM and writes pre-baked `CallableSpec` rows directly; a catalog UI in both the setup wizard and admin panel.

**Tech Stack:** Python 3.13 + uv + pytest + ruff (core/server). React 18 + TypeScript + Vite + Vitest (frontend). FastAPI (server). SQLAlchemy + Alembic (DB).

**Reference spec:** `docs/superpowers/specs/2026-05-01-builtin-connectors-design.md`

**Branch:** `feat/builtin-connectors` (worktree at `.worktrees/builtin-connectors`, branched from `feat/batched-resolver`).

**All paths in this plan are relative to the worktree root** (`.worktrees/builtin-connectors/`).

---

## Phase 1 — Schema extensions

Two additive changes plus dispatcher support. Land before any template work because every template depends on these.

### Task 1: Add `result_path` to `CallableSpec`

**Files:**
- Modify: `packages/core/src/openlia/connectors/types.py` (the `CallableSpec` dataclass)
- Test: `packages/core/tests/connectors/test_types.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/core/tests/connectors/test_types.py`:

```python
def test_callable_spec_result_path_default_is_empty_tuple() -> None:
    spec = CallableSpec(need_id="x", access_mode="cli_mcp", tool_name="t")
    assert spec.result_path == ()


def test_callable_spec_result_path_accepts_tuple() -> None:
    spec = CallableSpec(
        need_id="x",
        access_mode="remote_mcp",
        tool_name="firecrawl_extract",
        result_path=("data", "usd_share_pct"),
    )
    assert spec.result_path == ("data", "usd_share_pct")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest packages/core/tests/connectors/test_types.py::test_callable_spec_result_path_default_is_empty_tuple packages/core/tests/connectors/test_types.py::test_callable_spec_result_path_accepts_tuple -v
```

Expected: FAIL with "got an unexpected keyword argument 'result_path'" or similar.

- [ ] **Step 3: Add the field**

In `packages/core/src/openlia/connectors/types.py`, locate the `CallableSpec` dataclass and add the new field after `shape`:

```python
@dataclass(frozen=True)
class CallableSpec:
    """Persisted resolution from a RunnerNeed to a concrete connector callable."""

    need_id: str
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"]
    # MCP fields:
    tool_name: str | None = None
    # python_lib fields:
    module: str | None = None
    instance_factory: InstanceFactory | None = None
    method: str | None = None
    # shared fields:
    param_bindings: dict[str, ParamBinding] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)
    shape: str = "any"
    result_path: tuple[str, ...] = ()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest packages/core/tests/connectors/test_types.py -v
```

Expected: all green (the two new tests + existing tests still pass; `result_path` defaults to `()` so existing constructions are untouched).

- [ ] **Step 5: Verify no other tests broke**

```bash
uv run pytest packages/core/tests/connectors -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/connectors/types.py packages/core/tests/connectors/test_types.py
git commit -m "feat(connectors): add result_path to CallableSpec"
```

---

### Task 2: Dispatcher honors `result_path`

**Files:**
- Modify: `packages/core/src/openlia/connectors/dispatch.py` (the `_invoke_spec` method, around line 178-220)
- Test: `packages/core/tests/connectors/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/core/tests/connectors/test_dispatcher.py`. (Use an existing helper to construct a `Dispatcher` with a fake transport. Look at the existing `test_dispatcher.py` file for the prevailing pattern — there's a fixture or builder around line 140 you can reuse.)

```python
@pytest.mark.asyncio
async def test_invoke_spec_walks_result_path() -> None:
    """When result_path is set, dispatcher reduces tool result to the nested value."""

    class _FakeTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return {"data": {"usd_share_pct": 58.4, "as_of": "2026-Q1"}}

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),  # type: ignore[arg-type]
        tools={"firecrawl_extract": ToolDefinition(name="firecrawl_extract", description="", input_schema={})},
    )
    spec = CallableSpec(
        need_id="usd_fx_reserve_share",
        access_mode="remote_mcp",
        tool_name="firecrawl_extract",
        constants={"urls": ["https://example"]},
        result_path=("data", "usd_share_pct"),
        shape="float",
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    result = await dispatcher._invoke_spec(conn, spec, runtime_args={})
    assert result == 58.4


@pytest.mark.asyncio
async def test_invoke_spec_empty_result_path_returns_raw() -> None:
    """When result_path is empty, dispatcher returns the tool result unchanged."""

    class _FakeTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return {"value": 42}

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="p",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),  # type: ignore[arg-type]
        tools={"t": ToolDefinition(name="t", description="", input_schema={})},
    )
    spec = CallableSpec(need_id="n", access_mode="remote_mcp", tool_name="t")
    dispatcher = Dispatcher(connectors={"c1": conn})
    result = await dispatcher._invoke_spec(conn, spec, runtime_args={})
    assert result == {"value": 42}


@pytest.mark.asyncio
async def test_invoke_spec_result_path_missing_key_raises() -> None:
    """If a key in result_path is absent from the tool result, dispatcher raises DispatchError."""

    class _FakeTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return {"data": {}}  # missing usd_share_pct

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),  # type: ignore[arg-type]
        tools={"firecrawl_extract": ToolDefinition(name="firecrawl_extract", description="", input_schema={})},
    )
    spec = CallableSpec(
        need_id="usd_fx_reserve_share",
        access_mode="remote_mcp",
        tool_name="firecrawl_extract",
        result_path=("data", "usd_share_pct"),
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    with pytest.raises(DispatchError, match="result_path"):
        await dispatcher._invoke_spec(conn, spec, runtime_args={})
```

Make sure the imports at the top of the test file include `DispatchError`, `Dispatcher`, `PreparedConnector`, `Category`, `ConnectorStatus`, `ToolDefinition`, `CallableDefinition`. They likely already exist; add what's missing.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest packages/core/tests/connectors/test_dispatcher.py::test_invoke_spec_walks_result_path packages/core/tests/connectors/test_dispatcher.py::test_invoke_spec_empty_result_path_returns_raw packages/core/tests/connectors/test_dispatcher.py::test_invoke_spec_result_path_missing_key_raises -v
```

Expected: the first test FAILs (the dispatcher returns the whole dict, not 58.4). The empty-path test PASSes by accident (existing behavior). The missing-key test FAILs.

- [ ] **Step 3: Implement result_path walking**

In `packages/core/src/openlia/connectors/dispatch.py`, locate `_invoke_spec` (around line 178-220) and at the end, before the final `return` statements, route the result through a small helper. Replace the two `return await conn.transport.call_tool(...)` lines with assignments + a single result reduction:

Current code (last ~12 lines of `_invoke_spec`):

```python
        # Dispatch.
        if spec.access_mode in ("cli_mcp", "remote_mcp"):
            tool_name = spec.tool_name
            if tool_name is None:
                raise DispatchError(f"spec for need {spec.need_id!r} missing tool_name")
            return await conn.transport.call_tool(tool_name, bound)

        if spec.access_mode == "python_lib":
            method = spec.method
            if method is None:
                raise DispatchError(f"spec for need {spec.need_id!r} missing method")
            return await conn.transport.call_tool(method, bound)

        raise DispatchError(f"unknown access_mode {spec.access_mode!r}")
```

Replace with:

```python
        # Dispatch.
        if spec.access_mode in ("cli_mcp", "remote_mcp"):
            tool_name = spec.tool_name
            if tool_name is None:
                raise DispatchError(f"spec for need {spec.need_id!r} missing tool_name")
            raw = await conn.transport.call_tool(tool_name, bound)
        elif spec.access_mode == "python_lib":
            method = spec.method
            if method is None:
                raise DispatchError(f"spec for need {spec.need_id!r} missing method")
            raw = await conn.transport.call_tool(method, bound)
        else:
            raise DispatchError(f"unknown access_mode {spec.access_mode!r}")

        return _walk_result_path(raw, spec.result_path, need_id=spec.need_id)
```

Then add the helper at module scope (above the `Dispatcher` class is fine):

```python
def _walk_result_path(value: Any, path: tuple[str, ...], *, need_id: str) -> Any:
    """Reduce a tool result to a nested field per `path`. Empty path returns value unchanged."""
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise DispatchError(
                f"result_path {path!r} missing key {key!r} for need {need_id!r}"
            )
        value = value[key]
    return value
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest packages/core/tests/connectors/test_dispatcher.py -v
```

Expected: all green, including the three new tests.

- [ ] **Step 5: Lint**

```bash
uv run ruff check packages/core/src/openlia/connectors/dispatch.py packages/core/tests/connectors/test_dispatcher.py
```

Expected: clean. Fix any issues with `uv run ruff format` and re-run.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/connectors/dispatch.py packages/core/tests/connectors/test_dispatcher.py
git commit -m "feat(connectors): dispatcher honors CallableSpec.result_path"
```

---

### Task 3: Add `runner_specs` to `BuiltInTemplate`

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/types.py`
- Modify: `packages/core/tests/connectors/builtins/test_registry.py` (the existing `test_builtin_template_is_frozen` test constructs `BuiltInTemplate` without `runner_specs`)

- [ ] **Step 1: Write the failing test**

Append to `packages/core/tests/connectors/builtins/test_registry.py`:

```python
def test_builtin_template_runner_specs_default_is_empty_tuple() -> None:
    tpl = BuiltInTemplate(
        template_id="x",
        display_name="X",
        category=Category.SOCIAL,
        api_key_env_var="X_API_KEY",
        available_modes=(),
        canary_tool=None,
    )
    assert tpl.runner_specs == ()


def test_builtin_template_runner_specs_accepts_tuple() -> None:
    from openlia.connectors.types import CallableSpec

    spec = CallableSpec(need_id="n", access_mode="remote_mcp", tool_name="t")
    tpl = BuiltInTemplate(
        template_id="x",
        display_name="X",
        category=Category.NEWS,
        api_key_env_var="X_API_KEY",
        available_modes=(),
        canary_tool=None,
        runner_specs=(spec,),
    )
    assert tpl.runner_specs == (spec,)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_registry.py -v
```

Expected: the two new tests FAIL with "got an unexpected keyword argument 'runner_specs'".

- [ ] **Step 3: Add the field**

In `packages/core/src/openlia/connectors/builtins/types.py`, modify the `BuiltInTemplate` dataclass:

```python
from openlia.connectors.types import CallableSpec, Category

# ... existing CliMcpRecipe / RemoteMcpRecipe / PythonLibRecipe / ModeRecipe unchanged ...

@dataclass(frozen=True)
class BuiltInTemplate:
    template_id: str
    display_name: str
    category: Category
    api_key_env_var: str
    available_modes: tuple[ModeRecipe, ...]
    canary_tool: str | None
    runner_specs: tuple[CallableSpec, ...] = ()
```

(`CallableSpec` import already needs adding — `Category` is already imported per the existing module.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_registry.py -v
```

Expected: all green.

- [ ] **Step 5: Verify no broken downstream**

```bash
uv run pytest packages/core/tests/connectors -v
uv run ruff check packages/core/src/openlia/connectors/builtins
```

Expected: all green, no lint errors.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/connectors/builtins/types.py packages/core/tests/connectors/builtins/test_registry.py
git commit -m "feat(connectors): add runner_specs to BuiltInTemplate"
```

---

## Phase 2 — Per-provider templates

Each template lives in its own module under `packages/core/src/openlia/connectors/builtins/`. The order is: Firecrawl first (most novel — exercises `result_path` and `firecrawl_extract`), EODHD second (most runner needs), then FMP, NewsAPI.ai, Mediastack, X.

Each provider task has the same shape:

1. **Research step** — concrete commands the engineer runs to discover the upstream MCP package name, version, tool surface, or Python lib API.
2. **Code step** — fill the template module with the discovered values.
3. **Test step** — assert template is well-formed (modes well-typed, canary_tool exists in tools-or-callables surface, runner_specs reference declared need_ids).

The plan tells you exactly what to look up. If a research step finds the upstream package doesn't exist or has changed shape, stop and discuss before proceeding.

### Task 4: Firecrawl template

**Files:**
- Create: `packages/core/src/openlia/connectors/builtins/firecrawl.py`
- Test: `packages/core/tests/connectors/builtins/test_firecrawl.py`

**Need coverage:** `usd_fx_reserve_share`, `cb_gold_purchases`, `foreign_treasury_holdings` (all `Macro Research`).

- [ ] **Step 1: Research the Firecrawl recipe**

Look up the canonical launch recipe. Required fields:

- The MCP launch command (Firecrawl publishes both a remote MCP and a CLI MCP via `npx -y firecrawl-mcp`).
- The env var name for the API key (Firecrawl uses `FIRECRAWL_API_KEY`).
- The tool name for extraction (`firecrawl_extract`).
- The exact request schema for `firecrawl_extract` (urls, prompt, schema, possibly `enableWebSearch`).

Run:

```bash
WebFetch https://docs.firecrawl.dev/mcp-server
WebFetch https://github.com/mendableai/firecrawl-mcp-server
```

Document findings as a one-line comment at the top of `firecrawl.py` you'll create in step 2 (e.g., `# Source: https://github.com/mendableai/firecrawl-mcp-server @ vX.Y.Z`).

For the three URLs, the canonical official-statistics pages are:

- `usd_fx_reserve_share` → `https://data.imf.org/regular.aspx?key=41175` (IMF COFER quarterly).
- `cb_gold_purchases` → `https://www.gold.org/goldhub/research/gold-demand-trends` (World Gold Council).
- `foreign_treasury_holdings` → `https://home.treasury.gov/data/treasury-international-capital-tic-system/tic-forms-instructions/major-foreign-holders-treasury-securities` (US Treasury TIC).

Verify each URL is still live with `WebFetch <url>` and that the page contains the relevant data point. If a URL has moved, find the new canonical URL and use that.

- [ ] **Step 2: Write the failing test**

Create `packages/core/tests/connectors/builtins/test_firecrawl.py`:

```python
"""Built-in Firecrawl template tests."""

from __future__ import annotations

from openlia.connectors.builtins.firecrawl import FIRECRAWL_TEMPLATE
from openlia.connectors.builtins.types import RemoteMcpRecipe
from openlia.connectors.types import Category


def test_firecrawl_template_id_and_category() -> None:
    assert FIRECRAWL_TEMPLATE.template_id == "firecrawl"
    assert FIRECRAWL_TEMPLATE.category == Category.WEB_SEARCH
    assert FIRECRAWL_TEMPLATE.api_key_env_var == "FIRECRAWL_API_KEY"


def test_firecrawl_template_has_remote_mcp_mode() -> None:
    modes = FIRECRAWL_TEMPLATE.available_modes
    assert len(modes) >= 1
    assert any(isinstance(m, RemoteMcpRecipe) for m in modes)


def test_firecrawl_runner_specs_cover_world_order_needs() -> None:
    need_ids = {spec.need_id for spec in FIRECRAWL_TEMPLATE.runner_specs}
    assert need_ids == {
        "usd_fx_reserve_share",
        "cb_gold_purchases",
        "foreign_treasury_holdings",
    }


def test_firecrawl_runner_specs_use_firecrawl_extract() -> None:
    for spec in FIRECRAWL_TEMPLATE.runner_specs:
        assert spec.access_mode == "remote_mcp"
        assert spec.tool_name == "firecrawl_extract"
        # Each spec must reduce the dict result to a single value via result_path.
        assert len(spec.result_path) >= 1
        # Each spec must prebind the URL.
        assert "urls" in spec.constants
        assert isinstance(spec.constants["urls"], list)
        assert all(u.startswith("https://") for u in spec.constants["urls"])


def test_firecrawl_canary_tool_is_extract() -> None:
    assert FIRECRAWL_TEMPLATE.canary_tool == "firecrawl_extract"
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_firecrawl.py -v
```

Expected: FAIL with "ModuleNotFoundError: openlia.connectors.builtins.firecrawl".

- [ ] **Step 4: Create the template module**

Create `packages/core/src/openlia/connectors/builtins/firecrawl.py`:

```python
"""Firecrawl built-in connector template.

Source: <fill in upstream URL + version pin from Step 1 research>

Covers the three Macro Research World Order needs that require scraping
official-statistics websites (IMF COFER, World Gold Council, US Treasury TIC).
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    RemoteMcpRecipe,
)
from openlia.connectors.types import CallableSpec, Category

_FIRECRAWL_REMOTE_URL = "https://mcp.firecrawl.dev/{api_key}/mcp"  # update if upstream differs

_USD_FX_RESERVE_SHARE = CallableSpec(
    need_id="usd_fx_reserve_share",
    access_mode="remote_mcp",
    tool_name="firecrawl_extract",
    constants={
        "urls": ["https://data.imf.org/regular.aspx?key=41175"],
        "prompt": (
            "Extract the most recent USD share of total allocated foreign exchange "
            "reserves, expressed as a percentage (e.g. 58.4)."
        ),
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

_CB_GOLD_PURCHASES = CallableSpec(
    need_id="cb_gold_purchases",
    access_mode="remote_mcp",
    tool_name="firecrawl_extract",
    constants={
        "urls": ["https://www.gold.org/goldhub/research/gold-demand-trends"],
        "prompt": (
            "Extract net central-bank gold purchases over the trailing year, in tonnes."
        ),
        "schema": {
            "type": "object",
            "properties": {"net_purchases_tonnes": {"type": "number"}},
            "required": ["net_purchases_tonnes"],
        },
    },
    param_bindings={},  # window_days param has a static default of 365 baked into the prompt
    result_path=("data", "net_purchases_tonnes"),
    shape="float",
)

_FOREIGN_TREASURY_HOLDINGS = CallableSpec(
    need_id="foreign_treasury_holdings",
    access_mode="remote_mcp",
    tool_name="firecrawl_extract",
    constants={
        "urls": [
            "https://home.treasury.gov/data/treasury-international-capital-tic-system/"
            "tic-forms-instructions/major-foreign-holders-treasury-securities"
        ],
        "prompt": (
            "Extract the trailing 90-day change in total foreign holdings of US "
            "Treasury securities, in USD billions (positive = accumulation, negative = sales)."
        ),
        "schema": {
            "type": "object",
            "properties": {"change_usd_billions": {"type": "number"}},
            "required": ["change_usd_billions"],
        },
    },
    param_bindings={},
    result_path=("data", "change_usd_billions"),
    shape="float",
)


FIRECRAWL_TEMPLATE = BuiltInTemplate(
    template_id="firecrawl",
    display_name="Firecrawl",
    category=Category.WEB_SEARCH,
    api_key_env_var="FIRECRAWL_API_KEY",
    available_modes=(
        RemoteMcpRecipe(
            kind="remote_mcp",
            url=_FIRECRAWL_REMOTE_URL,
            headers=(),  # API key is in the URL path; no headers needed
        ),
        CliMcpRecipe(
            kind="cli_mcp",
            argv=("npx", "-y", "firecrawl-mcp"),
            env_keys=("FIRECRAWL_API_KEY",),
        ),
    ),
    canary_tool="firecrawl_extract",
    runner_specs=(
        _USD_FX_RESERVE_SHARE,
        _CB_GOLD_PURCHASES,
        _FOREIGN_TREASURY_HOLDINGS,
    ),
)
```

If your research from Step 1 found the actual MCP url shape differs (e.g., it requires the API key in a header rather than the path), correct `_FIRECRAWL_REMOTE_URL` and the `headers` tuple accordingly.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_firecrawl.py -v
```

Expected: all five tests green.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/core/src/openlia/connectors/builtins/firecrawl.py packages/core/tests/connectors/builtins/test_firecrawl.py
uv run ruff format packages/core/src/openlia/connectors/builtins/firecrawl.py packages/core/tests/connectors/builtins/test_firecrawl.py
git add packages/core/src/openlia/connectors/builtins/firecrawl.py packages/core/tests/connectors/builtins/test_firecrawl.py
git commit -m "feat(connectors): firecrawl built-in template"
```

---

### Task 5: EODHD template

**Files:**
- Create: `packages/core/src/openlia/connectors/builtins/eodhd.py`
- Test: `packages/core/tests/connectors/builtins/test_eodhd.py`

**Need coverage:** `debt_gdp`, `interest_revenue`, `gdp_yoy`, `cpi_yoy`, `cpi_core_yoy`, `pmi`, `stock_quote`, `social_posts`.

- [ ] **Step 1: Research the EODHD recipe**

EODHD has both an MCP server and a Python SDK. Look up:

```bash
WebFetch https://eodhd.com/financial-apis/
WebFetch https://github.com/eodhd/mcp-server-eodhd
WebFetch https://pypi.org/project/eodhd/
```

Identify:

1. The CLI MCP launch command (typical pattern: `uvx eodhd-mcp` with `EODHD_API_KEY` env). Confirm the actual package name.
2. The Python lib pip name (`eodhd`), version pin (latest stable, e.g., `>=1.0,<2.0` — confirm).
3. The Python lib instance class (`APIClient`) and constructor arg (`api_key`).
4. The method names for each macro indicator. EODHD's macro endpoint is reachable via `APIClient.get_economic_calendar(...)` or `APIClient.get_macro_indicators_data(country, indicator)` — confirm the actual method name and the indicator-code vocabulary (e.g., `"debt_to_gdp"`, `"gdp_growth_annual"`, `"cpi"`).
5. The method for `stock_quote` (e.g., `APIClient.real_time_quote(symbol)`).
6. The method for `social_posts` (e.g., `APIClient.sentiment_data(s=ticker)`).

For each indicator, document the exact `(method, indicator_code)` pair you'll bake in. If a method does not exist for a given indicator, mark that need as "EODHD-uncovered" and remove it from EODHD's `runner_specs` (FMP picks it up in Task 6).

- [ ] **Step 2: Write the failing test**

Create `packages/core/tests/connectors/builtins/test_eodhd.py`:

```python
"""Built-in EODHD template tests."""

from __future__ import annotations

from openlia.connectors.builtins.eodhd import EODHD_TEMPLATE
from openlia.connectors.builtins.types import CliMcpRecipe, PythonLibRecipe
from openlia.connectors.types import Category


def test_eodhd_template_id_and_category() -> None:
    assert EODHD_TEMPLATE.template_id == "eodhd"
    assert EODHD_TEMPLATE.category == Category.FINANCIAL
    assert EODHD_TEMPLATE.api_key_env_var == "EODHD_API_KEY"


def test_eodhd_has_both_cli_mcp_and_python_lib_modes() -> None:
    modes = EODHD_TEMPLATE.available_modes
    assert any(isinstance(m, CliMcpRecipe) for m in modes), "expected CLI MCP mode"
    assert any(isinstance(m, PythonLibRecipe) for m in modes), "expected python_lib mode"


def test_eodhd_python_lib_recipe_uses_api_key_env_placeholder() -> None:
    py = next(m for m in EODHD_TEMPLATE.available_modes if isinstance(m, PythonLibRecipe))
    assert py.pip_name == "eodhd"
    assert py.import_module == "eodhd"
    args = dict(py.instance_factory_args)
    assert args.get("api_key") == "$EODHD_API_KEY"


def test_eodhd_runner_specs_cover_expected_needs() -> None:
    need_ids = {spec.need_id for spec in EODHD_TEMPLATE.runner_specs}
    expected = {
        "debt_gdp",
        "interest_revenue",
        "gdp_yoy",
        "cpi_yoy",
        "cpi_core_yoy",
        "pmi",
        "stock_quote",
        "social_posts",
    }
    # Allow EODHD to drop a need that turns out to be unsupported upstream;
    # the dropped need(s) are picked up by FMP in Task 6. But the bulk must be present.
    assert expected - need_ids == set() or len(expected & need_ids) >= 6, (
        f"EODHD must cover most expected needs; missing: {expected - need_ids}"
    )


def test_eodhd_runner_specs_have_python_lib_or_mcp_access_mode() -> None:
    for spec in EODHD_TEMPLATE.runner_specs:
        assert spec.access_mode in ("python_lib", "cli_mcp", "remote_mcp")
        if spec.access_mode == "python_lib":
            assert spec.module == "eodhd"
            assert spec.method is not None
            assert spec.instance_factory is not None
            assert spec.instance_factory.cls == "APIClient"
            assert spec.instance_factory.args.get("api_key") == "$EODHD_API_KEY"


def test_eodhd_canary_tool_is_set() -> None:
    assert EODHD_TEMPLATE.canary_tool is not None
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_eodhd.py -v
```

Expected: FAIL with "ModuleNotFoundError".

- [ ] **Step 4: Create the template module**

Create `packages/core/src/openlia/connectors/builtins/eodhd.py`. Use the per-need-CallableSpec pattern from Firecrawl. Each macro need is a `python_lib` CallableSpec with `module="eodhd"`, `method="APIClient.<from-research>"`, `instance_factory=InstanceFactory(cls="APIClient", args={"api_key": "$EODHD_API_KEY"})`, `param_bindings={"country": ParamBinding(to_arg="country", transform="iso_to_eodhd")}`, `constants={"indicator": "<from-research>"}`, `result_path=()`, `shape="float"`.

If the method returns a dict and the value is at a known key, set `result_path` accordingly.

`stock_quote` and `social_posts` follow similar shapes — bind `ticker` to the method's symbol arg, no transform.

Use `_eodhd_macro_spec(...)` and `_eodhd_quote_spec(...)` helper functions inside the module if it reduces repetition for the macro indicators.

```python
"""EODHD built-in connector template.

Source: <fill in from Step 1 research, e.g. https://github.com/eodhd/mcp-server-eodhd @ v0.4.0>
Python SDK: eodhd>=1.0,<2.0  (confirm exact version pin from PyPI)
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    PythonLibRecipe,
)
from openlia.connectors.types import (
    CallableSpec,
    Category,
    InstanceFactory,
    ParamBinding,
)

_API_KEY_PLACEHOLDER = "$EODHD_API_KEY"
_API_CLIENT = InstanceFactory(cls="APIClient", args={"api_key": _API_KEY_PLACEHOLDER})


def _macro_spec(
    *,
    need_id: str,
    method: str,
    indicator_code: str,
    result_path: tuple[str, ...] = (),
) -> CallableSpec:
    return CallableSpec(
        need_id=need_id,
        access_mode="python_lib",
        module="eodhd",
        method=method,
        instance_factory=_API_CLIENT,
        param_bindings={"country": ParamBinding(to_arg="country", transform="iso_to_eodhd")},
        constants={"indicator": indicator_code},
        result_path=result_path,
        shape="float",
    )


# Indicator codes confirmed from upstream EODHD docs in Step 1.
_DEBT_GDP = _macro_spec(need_id="debt_gdp", method="APIClient.get_macro_indicators_data", indicator_code="debt_to_gdp")
_INTEREST_REVENUE = _macro_spec(need_id="interest_revenue", method="APIClient.get_macro_indicators_data", indicator_code="interest_to_revenue")
_GDP_YOY = _macro_spec(need_id="gdp_yoy", method="APIClient.get_macro_indicators_data", indicator_code="gdp_growth_annual")
_CPI_YOY = _macro_spec(need_id="cpi_yoy", method="APIClient.get_macro_indicators_data", indicator_code="inflation_consumer_prices_annual")
_CPI_CORE_YOY = _macro_spec(need_id="cpi_core_yoy", method="APIClient.get_macro_indicators_data", indicator_code="inflation_core_annual")
_PMI = _macro_spec(need_id="pmi", method="APIClient.get_macro_indicators_data", indicator_code="pmi_manufacturing")

_STOCK_QUOTE = CallableSpec(
    need_id="stock_quote",
    access_mode="python_lib",
    module="eodhd",
    method="APIClient.real_time_quote",
    instance_factory=_API_CLIENT,
    param_bindings={"ticker": ParamBinding(to_arg="symbol")},
    constants={},
    result_path=(),
    shape="dict",
)

_SOCIAL_POSTS = CallableSpec(
    need_id="social_posts",
    access_mode="python_lib",
    module="eodhd",
    method="APIClient.sentiment_data",
    instance_factory=_API_CLIENT,
    param_bindings={"ticker": ParamBinding(to_arg="s")},
    constants={},
    result_path=(),
    shape="list[dict]",
)


EODHD_TEMPLATE = BuiltInTemplate(
    template_id="eodhd",
    display_name="EODHD",
    category=Category.FINANCIAL,
    api_key_env_var="EODHD_API_KEY",
    available_modes=(
        CliMcpRecipe(
            kind="cli_mcp",
            argv=("uvx", "eodhd-mcp"),  # confirm with research
            env_keys=("EODHD_API_KEY",),
        ),
        PythonLibRecipe(
            kind="python_lib",
            pip_name="eodhd",
            pip_version=">=1.0,<2.0",  # confirm with research
            import_module="eodhd",
            instance_factory_cls="APIClient",
            instance_factory_args=(("api_key", _API_KEY_PLACEHOLDER),),
        ),
    ),
    canary_tool="real_time_quote",  # or whichever cheap method confirms the API key
    runner_specs=(
        _DEBT_GDP,
        _INTEREST_REVENUE,
        _GDP_YOY,
        _CPI_YOY,
        _CPI_CORE_YOY,
        _PMI,
        _STOCK_QUOTE,
        _SOCIAL_POSTS,
    ),
)
```

If research reveals different method names or indicator codes, replace the strings above. If a method takes different param names than `country` / `symbol` / `s`, update the `to_arg` accordingly.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_eodhd.py -v
```

Expected: green.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/connectors/builtins/test_eodhd.py
uv run ruff format packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/connectors/builtins/test_eodhd.py
git add packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/connectors/builtins/test_eodhd.py
git commit -m "feat(connectors): eodhd built-in template"
```

---

### Task 6: FMP template

**Files:**
- Create: `packages/core/src/openlia/connectors/builtins/fmp.py`
- Test: `packages/core/tests/connectors/builtins/test_fmp.py`

**Need coverage:** Same financial set as EODHD (the alternate primary). Plus any need EODHD couldn't cover (carried over from Task 5).

- [ ] **Step 1: Research the FMP recipe**

```bash
WebFetch https://site.financialmodelingprep.com/developer/docs
WebFetch https://github.com/financialmodelingprep/fmp-mcp-server
WebFetch https://pypi.org/project/fmpsdk/
```

Identify pip name, version, MCP package name, instance constructor, and method names per indicator (FMP uses `economic_indicator(name=...)` style, with names like `"GDP"`, `"CPI"`, `"federalFunds"`).

- [ ] **Step 2: Write the failing test**

Create `packages/core/tests/connectors/builtins/test_fmp.py`. Mirror `test_eodhd.py` but with `FMP_TEMPLATE`, `template_id="fmp"`, `api_key_env_var="FMP_API_KEY"`. Same coverage assertions on need_ids.

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_fmp.py -v
```

Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 4: Create the template module**

Create `packages/core/src/openlia/connectors/builtins/fmp.py`, mirroring the EODHD module structure. Use `instance_factory_cls` for the FMP SDK's main client class (commonly `FinancialModelingPrep` or `FMPClient` — confirm via research). Reuse the `_macro_spec` pattern.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_fmp.py -v
```

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/core/src/openlia/connectors/builtins/fmp.py packages/core/tests/connectors/builtins/test_fmp.py
uv run ruff format packages/core/src/openlia/connectors/builtins/fmp.py packages/core/tests/connectors/builtins/test_fmp.py
git add packages/core/src/openlia/connectors/builtins/fmp.py packages/core/tests/connectors/builtins/test_fmp.py
git commit -m "feat(connectors): fmp built-in template"
```

---

### Task 7: NewsAPI.ai template

**Files:**
- Create: `packages/core/src/openlia/connectors/builtins/newsapi_ai.py`
- Test: `packages/core/tests/connectors/builtins/test_newsapi_ai.py`

**Need coverage:** `geopolitical_news`.

- [ ] **Step 1: Research the NewsAPI.ai recipe**

```bash
WebFetch https://eventregistry.org/documentation
WebFetch https://github.com/EventRegistry/event-registry-python
WebFetch https://pypi.org/project/eventregistry/
```

Identify pip name (`eventregistry`), version, instance class (`EventRegistry`), constructor arg (commonly `apiKey`), and method for keyword-search (commonly `QueryArticlesIter` or `getEvents`).

If a remote MCP exists, prefer it; otherwise ship Python-lib only.

- [ ] **Step 2: Write the failing test**

```python
"""Built-in NewsAPI.ai template tests."""

from __future__ import annotations

from openlia.connectors.builtins.newsapi_ai import NEWSAPI_AI_TEMPLATE
from openlia.connectors.types import Category


def test_newsapi_ai_template_id_and_category() -> None:
    assert NEWSAPI_AI_TEMPLATE.template_id == "newsapi_ai"
    assert NEWSAPI_AI_TEMPLATE.category == Category.NEWS
    assert NEWSAPI_AI_TEMPLATE.api_key_env_var == "NEWSAPI_AI_API_KEY"


def test_newsapi_ai_has_at_least_one_mode() -> None:
    assert len(NEWSAPI_AI_TEMPLATE.available_modes) >= 1


def test_newsapi_ai_runner_specs_cover_geopolitical_news() -> None:
    need_ids = {spec.need_id for spec in NEWSAPI_AI_TEMPLATE.runner_specs}
    assert "geopolitical_news" in need_ids


def test_newsapi_ai_canary_tool_set() -> None:
    assert NEWSAPI_AI_TEMPLATE.canary_tool is not None
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_newsapi_ai.py -v
```

- [ ] **Step 4: Create the template module**

Create `packages/core/src/openlia/connectors/builtins/newsapi_ai.py` with one Python-lib mode (and an optional remote MCP if one exists upstream). The single runner spec for `geopolitical_news` binds query keyword(s) and date range to the search method.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_newsapi_ai.py -v
```

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/core/src/openlia/connectors/builtins/newsapi_ai.py packages/core/tests/connectors/builtins/test_newsapi_ai.py
uv run ruff format packages/core/src/openlia/connectors/builtins/newsapi_ai.py packages/core/tests/connectors/builtins/test_newsapi_ai.py
git add packages/core/src/openlia/connectors/builtins/newsapi_ai.py packages/core/tests/connectors/builtins/test_newsapi_ai.py
git commit -m "feat(connectors): newsapi_ai built-in template"
```

---

### Task 8: Mediastack template

**Files:**
- Create: `packages/core/src/openlia/connectors/builtins/mediastack.py`
- Test: `packages/core/tests/connectors/builtins/test_mediastack.py`

**Need coverage:** `geopolitical_news` (alternate to NewsAPI.ai).

- [ ] **Step 1: Research the Mediastack recipe**

Mediastack does not publish an official MCP. It exposes a REST API at `api.mediastack.com`.

```bash
WebFetch https://mediastack.com/documentation
WebFetch https://pypi.org/search/?q=mediastack
```

Decide between two options:

- (a) Ship as Python-lib only using a community PyPI wrapper (verify the wrapper exists and is maintained).
- (b) Ship a thin in-repo Python lib (a tiny module under `openlia.data.mediastack` exposing a class with one search method that calls the REST endpoint via `requests`/`httpx`). Only do this if (a) is unavailable.

Pick (a) if a maintained wrapper exists; otherwise pick (b) and create the in-repo module as part of this task. Document the choice in the module's docstring.

- [ ] **Step 2: Write the failing test**

```python
"""Built-in Mediastack template tests."""

from __future__ import annotations

from openlia.connectors.builtins.mediastack import MEDIASTACK_TEMPLATE
from openlia.connectors.builtins.types import PythonLibRecipe
from openlia.connectors.types import Category


def test_mediastack_template_id_and_category() -> None:
    assert MEDIASTACK_TEMPLATE.template_id == "mediastack"
    assert MEDIASTACK_TEMPLATE.category == Category.NEWS
    assert MEDIASTACK_TEMPLATE.api_key_env_var == "MEDIASTACK_API_KEY"


def test_mediastack_has_python_lib_only() -> None:
    assert len(MEDIASTACK_TEMPLATE.available_modes) == 1
    assert isinstance(MEDIASTACK_TEMPLATE.available_modes[0], PythonLibRecipe)


def test_mediastack_covers_geopolitical_news() -> None:
    need_ids = {spec.need_id for spec in MEDIASTACK_TEMPLATE.runner_specs}
    assert "geopolitical_news" in need_ids
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_mediastack.py -v
```

- [ ] **Step 4: Create the template module (and in-repo wrapper if needed)**

Create `packages/core/src/openlia/connectors/builtins/mediastack.py`. If using option (b), also create `packages/core/src/openlia/data/mediastack/__init__.py` exposing a `MediastackClient` class with constructor arg `api_key` and method `search(query, since=None, limit=100)`.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_mediastack.py -v
```

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/core/src/openlia/connectors/builtins/mediastack.py packages/core/tests/connectors/builtins/test_mediastack.py
uv run ruff format packages/core/src/openlia/connectors/builtins/mediastack.py packages/core/tests/connectors/builtins/test_mediastack.py
git add packages/core/src/openlia/connectors/builtins/mediastack.py packages/core/tests/connectors/builtins/test_mediastack.py
# include the in-repo wrapper if you created one
git commit -m "feat(connectors): mediastack built-in template"
```

---

### Task 9: X template

**Files:**
- Create: `packages/core/src/openlia/connectors/builtins/x.py`
- Test: `packages/core/tests/connectors/builtins/test_x.py`

**Need coverage:** None (chat-dept tools only).

- [ ] **Step 1: Research the X / Twitter MCP recipe**

```bash
WebFetch https://github.com/xai-org
WebFetch https://docs.x.ai/api
```

Identify the X MCP launch recipe (likely a remote MCP at xAI; confirm).

- [ ] **Step 2: Write the failing test**

```python
"""Built-in X template tests."""

from __future__ import annotations

from openlia.connectors.builtins.x import X_TEMPLATE
from openlia.connectors.types import Category


def test_x_template_id_and_category() -> None:
    assert X_TEMPLATE.template_id == "x"
    assert X_TEMPLATE.category == Category.SOCIAL


def test_x_has_no_runner_specs() -> None:
    """X is chat-only on day 1; no runner-need mappings."""
    assert X_TEMPLATE.runner_specs == ()


def test_x_has_at_least_one_mode() -> None:
    assert len(X_TEMPLATE.available_modes) >= 1


def test_x_canary_tool_set() -> None:
    assert X_TEMPLATE.canary_tool is not None
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_x.py -v
```

- [ ] **Step 4: Create the template module**

Create `packages/core/src/openlia/connectors/builtins/x.py` with a `RemoteMcpRecipe` (or `CliMcpRecipe` if that's what upstream ships) and `runner_specs=()`.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_x.py -v
```

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/core/src/openlia/connectors/builtins/x.py packages/core/tests/connectors/builtins/test_x.py
uv run ruff format packages/core/src/openlia/connectors/builtins/x.py packages/core/tests/connectors/builtins/test_x.py
git add packages/core/src/openlia/connectors/builtins/x.py packages/core/tests/connectors/builtins/test_x.py
git commit -m "feat(connectors): x built-in template"
```

---

### Task 10: Wire templates into `BUILTIN_TEMPLATES`

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/_registry.py`
- Modify: `packages/core/tests/connectors/builtins/test_registry.py` (existing tests assert empty tuple — need updating)

- [ ] **Step 1: Write the failing test**

Replace the existing `test_builtin_templates_is_empty_tuple` and `test_list_templates_returns_empty_tuple` tests with the new shape, and add a coverage matrix test:

```python
def test_builtin_templates_has_six_entries() -> None:
    template_ids = {t.template_id for t in BUILTIN_TEMPLATES}
    assert template_ids == {"eodhd", "fmp", "newsapi_ai", "mediastack", "firecrawl", "x"}


def test_list_templates_returns_six_entries() -> None:
    assert len(list_templates()) == 6


def test_get_template_finds_each_builtin() -> None:
    for tid in ("eodhd", "fmp", "newsapi_ai", "mediastack", "firecrawl", "x"):
        tpl = get_template(tid)
        assert tpl is not None, f"missing template: {tid}"
        assert tpl.template_id == tid


def test_runner_specs_reference_only_declared_need_ids() -> None:
    """Every runner_spec's need_id must appear in the corresponding department's needs.yaml."""
    import yaml
    from pathlib import Path

    needs_dir = Path(__file__).resolve().parents[4] / "src" / "openlia" / "departments"
    declared: set[str] = set()
    for yaml_path in needs_dir.glob("*.needs.yaml"):
        data = yaml.safe_load(yaml_path.read_text())
        for need in data.get("needs", []):
            declared.add(need["id"])

    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            assert spec.need_id in declared, (
                f"template {tpl.template_id!r} references unknown need {spec.need_id!r}"
            )


def test_every_runner_need_is_covered_by_at_least_one_template() -> None:
    """Every declared need (across both runner depts) is covered by at least one builtin."""
    import yaml
    from pathlib import Path

    needs_dir = Path(__file__).resolve().parents[4] / "src" / "openlia" / "departments"
    declared: set[str] = set()
    for yaml_path in needs_dir.glob("*.needs.yaml"):
        data = yaml.safe_load(yaml_path.read_text())
        for need in data.get("needs", []):
            declared.add(need["id"])

    covered: set[str] = set()
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            covered.add(spec.need_id)

    missing = declared - covered
    assert not missing, f"runner needs uncovered by day-1 catalog: {missing}"
```

Keep the four existing shape/freezing tests (they still pass).

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest packages/core/tests/connectors/builtins/test_registry.py -v
```

Expected: the new tests FAIL with assertion errors (`BUILTIN_TEMPLATES` is still empty). The old empty-tuple tests will also fail because we just removed them; if any remain, delete them.

- [ ] **Step 3: Wire up the registry**

Edit `packages/core/src/openlia/connectors/builtins/_registry.py`:

```python
"""Built-in template registry.

Day-1 catalog per docs/superpowers/specs/2026-05-01-builtin-connectors-design.md §2.
"""

from __future__ import annotations

from openlia.connectors.builtins.eodhd import EODHD_TEMPLATE
from openlia.connectors.builtins.firecrawl import FIRECRAWL_TEMPLATE
from openlia.connectors.builtins.fmp import FMP_TEMPLATE
from openlia.connectors.builtins.mediastack import MEDIASTACK_TEMPLATE
from openlia.connectors.builtins.newsapi_ai import NEWSAPI_AI_TEMPLATE
from openlia.connectors.builtins.types import BuiltInTemplate
from openlia.connectors.builtins.x import X_TEMPLATE

BUILTIN_TEMPLATES: tuple[BuiltInTemplate, ...] = (
    EODHD_TEMPLATE,
    FMP_TEMPLATE,
    NEWSAPI_AI_TEMPLATE,
    MEDIASTACK_TEMPLATE,
    FIRECRAWL_TEMPLATE,
    X_TEMPLATE,
)


def get_template(template_id: str) -> BuiltInTemplate | None:
    return next((t for t in BUILTIN_TEMPLATES if t.template_id == template_id), None)


def list_templates() -> tuple[BuiltInTemplate, ...]:
    return BUILTIN_TEMPLATES
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest packages/core/tests/connectors/builtins -v
```

Expected: green. If `test_every_runner_need_is_covered_by_at_least_one_template` fails, that's a real coverage gap — go back to Task 5/6 and add the missing need to either EODHD or FMP, or to Firecrawl as a scrape if it's a specialized macro need.

- [ ] **Step 5: Run the full core test suite to catch regressions**

```bash
uv run pytest packages/core/tests -v
```

Expected: green.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check packages/core/src/openlia/connectors/builtins/_registry.py packages/core/tests/connectors/builtins/test_registry.py
git add packages/core/src/openlia/connectors/builtins/_registry.py packages/core/tests/connectors/builtins/test_registry.py
git commit -m "feat(connectors): wire 6-template day-1 catalog"
```

---

## Phase 3 — Server install path

### Task 11: Add `install_builtin` service function

**Files:**
- Modify: `packages/server/src/openlia_server/services/connectors_service.py`
- Test: `packages/server/tests/services/test_connectors_service.py` (create if absent)

- [ ] **Step 1: Write the failing test**

Create or extend `packages/server/tests/services/test_connectors_service.py`:

```python
"""Tests for connectors_service.install_builtin."""

from __future__ import annotations

import pytest
from openlia.connectors.types import ConnectorSource, ConnectorStatus
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.connectors import Connector, RunnerCallableSpec
from openlia_server.services import connectors_service


@pytest.mark.asyncio
async def test_install_builtin_unknown_template_raises(db_session: DBSession) -> None:
    with pytest.raises(KeyError):
        await connectors_service.install_builtin(
            db_session, template_id="does-not-exist", api_key="k"
        )


@pytest.mark.asyncio
async def test_install_builtin_creates_connector_with_modes_from_template(
    db_session: DBSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Builtin install persists a Connector row with the template's modes and the user's API key."""
    # Avoid hitting the network during canary validation.
    async def _fake_validate(launch, secrets):  # type: ignore[no-redef]
        from openlia_server.services.connectors_service import ValidationOk
        return ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _fake_validate)

    conn = await connectors_service.install_builtin(
        db_session, template_id="firecrawl", api_key="user-supplied-key"
    )
    assert conn.provider_id == "firecrawl"
    assert conn.source == ConnectorSource.BUILT_IN.value
    assert conn.category == "web_search"
    assert conn.status == ConnectorStatus.VALIDATED.value
    assert conn.secrets == {"FIRECRAWL_API_KEY": "user-supplied-key"}
    # launch.modes mirrors the template's available_modes:
    assert "modes" in conn.launch
    assert len(conn.launch["modes"]) >= 1


@pytest.mark.asyncio
async def test_install_builtin_inserts_runner_callable_specs_for_runner_needs(
    db_session: DBSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake_validate(launch, secrets):  # type: ignore[no-redef]
        from openlia_server.services.connectors_service import ValidationOk
        return ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _fake_validate)

    await connectors_service.install_builtin(
        db_session, template_id="firecrawl", api_key="k"
    )
    rows = db_session.query(RunnerCallableSpec).all()
    need_ids = {r.need_id for r in rows}
    assert {"usd_fx_reserve_share", "cb_gold_purchases", "foreign_treasury_holdings"}.issubset(need_ids)
    for r in rows:
        # All Firecrawl needs serve macro_research per the spec.
        assert r.department_id == "macro_research"


@pytest.mark.asyncio
async def test_install_builtin_template_with_no_runner_specs_inserts_no_specs(
    db_session: DBSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake_validate(launch, secrets):  # type: ignore[no-redef]
        from openlia_server.services.connectors_service import ValidationOk
        return ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _fake_validate)

    await connectors_service.install_builtin(db_session, template_id="x", api_key="k")
    rows = db_session.query(RunnerCallableSpec).all()
    assert rows == []
```

If `db_session` fixture and the test directory don't yet exist, look at the prevailing test pattern in `packages/server/tests/` to match. There should be a `conftest.py` providing `db_session`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest packages/server/tests/services/test_connectors_service.py -v
```

Expected: FAIL with "module 'connectors_service' has no attribute 'install_builtin'".

- [ ] **Step 3: Implement `install_builtin`**

Append to `packages/server/src/openlia_server/services/connectors_service.py`:

```python
import dataclasses
import json

from openlia.connectors.builtins import (
    BuiltInTemplate,
    CliMcpRecipe,
    PythonLibRecipe,
    RemoteMcpRecipe,
    get_template,
)
from openlia.connectors.types import (
    CallableSpec,
    Category,
    CliMcpMode,
    ConnectorSource,
    InstanceFactory,
    LaunchSpec,
    PythonLibMode,
    RemoteMcpMode,
)
from openlia_server.db.models.connectors import RunnerCallableSpec


# Maps each runner-need's id back to the department that owns it.
# Source of truth: packages/core/src/openlia/departments/*.needs.yaml
_NEED_DEPARTMENT_MAP: dict[str, str] = {
    # macro_research
    "debt_gdp": "macro_research",
    "interest_revenue": "macro_research",
    "pmi": "macro_research",
    "gdp_yoy": "macro_research",
    "cpi_yoy": "macro_research",
    "cpi_core_yoy": "macro_research",
    "usd_fx_reserve_share": "macro_research",
    "cb_gold_purchases": "macro_research",
    "foreign_treasury_holdings": "macro_research",
    "stock_quote": "macro_research",
    "geopolitical_news": "macro_research",
    # retail_sentiment
    "social_posts": "retail_sentiment",
}


def _recipe_to_mode(recipe):  # type: ignore[no-untyped-def]
    """Convert a builtin ModeRecipe to a runtime LaunchMode (LaunchSpec dict shape)."""
    if isinstance(recipe, CliMcpRecipe):
        return CliMcpMode(kind="cli_mcp", argv=list(recipe.argv), env_keys=list(recipe.env_keys))
    if isinstance(recipe, RemoteMcpRecipe):
        return RemoteMcpMode(kind="remote_mcp", url=recipe.url, headers=dict(recipe.headers))
    if isinstance(recipe, PythonLibRecipe):
        factory = InstanceFactory(
            cls=recipe.instance_factory_cls,
            args=dict(recipe.instance_factory_args),
        )
        return PythonLibMode(
            kind="python_lib",
            pip_name=recipe.pip_name,
            pip_version=recipe.pip_version,
            import_module=recipe.import_module,
            instance_factory=factory,
        )
    raise ValueError(f"unknown recipe kind: {type(recipe).__name__}")


def _spec_to_json(spec: CallableSpec) -> dict[str, Any]:
    """Persist CallableSpec to the JSON column shape expected by RunnerCallableSpec.spec."""
    payload = dataclasses.asdict(spec)
    # ParamBinding objects already become dicts via asdict.
    # InstanceFactory objects too.
    return payload


async def install_builtin(
    session: DBSession,
    *,
    template_id: str,
    api_key: str,
) -> Connector:
    """Install a built-in template by id, persisting the connector + runner specs.

    Bypasses the wizard-time adapter LLM. The template's curated runner_specs are
    written directly to runner_callable_specs.
    """
    template = get_template(template_id)
    if template is None:
        raise KeyError(f"unknown template_id: {template_id!r}")

    launch = LaunchSpec(modes=[_recipe_to_mode(r) for r in template.available_modes])
    secrets = {template.api_key_env_var: api_key}

    connector = await create_connector(
        session,
        provider_id=template.template_id,
        display_name=template.display_name,
        source=ConnectorSource.BUILT_IN,
        category=template.category,
        launch=launch,
        secrets=secrets,
    )

    if connector.status != ConnectorStatus.VALIDATED.value:
        # create_connector already persisted the failure reason in last_error;
        # leave the connector visible with status=failed and skip writing
        # runner_specs. The caller can re-validate after fixing the API key.
        return connector

    for spec in template.runner_specs:
        dept = _NEED_DEPARTMENT_MAP.get(spec.need_id)
        if dept is None:
            raise ValueError(
                f"template {template.template_id!r} references need {spec.need_id!r} "
                f"with no known department mapping"
            )
        row = RunnerCallableSpec(
            id=str(uuid.uuid4()),
            department_id=dept,
            need_id=spec.need_id,
            connector_id=connector.id,
            access_mode=spec.access_mode,
            spec=_spec_to_json(spec),
        )
        session.add(row)

    session.commit()
    session.refresh(connector)
    _invalidate(session)
    return connector
```

(Make sure the imports near the top of the file — including `uuid` — are already present; if not, add them.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest packages/server/tests/services/test_connectors_service.py -v
```

Expected: green.

- [ ] **Step 5: Lint**

```bash
uv run ruff check packages/server/src/openlia_server/services/connectors_service.py packages/server/tests/services/test_connectors_service.py
```

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services/connectors_service.py packages/server/tests/services/test_connectors_service.py
git commit -m "feat(connectors): install_builtin service bypasses wizard adapter"
```

---

### Task 12: `POST /api/connectors/install-builtin` route

**Files:**
- Modify: `packages/server/src/openlia_server/routes/connectors.py`
- Test: `packages/server/tests/routes/test_routes_connectors.py` (extend existing, or create if absent)

- [ ] **Step 1: Write the failing test**

```python
"""Route tests for POST /api/connectors/install-builtin."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_install_builtin_unknown_template_returns_404(client: TestClient) -> None:
    res = client.post(
        "/api/connectors/install-builtin",
        json={"template_id": "does-not-exist", "api_key": "k"},
    )
    assert res.status_code == 404


def test_install_builtin_missing_api_key_returns_422(client: TestClient) -> None:
    res = client.post("/api/connectors/install-builtin", json={"template_id": "firecrawl"})
    assert res.status_code == 422


def test_install_builtin_returns_201_and_connector_row(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: install Firecrawl with a stubbed canary."""
    from openlia_server.services import connectors_service

    async def _fake_validate(launch, secrets):  # type: ignore[no-redef]
        return connectors_service.ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _fake_validate)

    res = client.post(
        "/api/connectors/install-builtin",
        json={"template_id": "firecrawl", "api_key": "user-key"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["provider_id"] == "firecrawl"
    assert body["source"] == "built_in"
    assert body["status"] == "validated"
```

(`client` fixture matches the prevailing pattern in `packages/server/tests/routes/conftest.py`.)

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest packages/server/tests/routes/test_routes_connectors.py::test_install_builtin_unknown_template_returns_404 -v
```

Expected: 405/404 from FastAPI (route doesn't exist).

- [ ] **Step 3: Implement the route**

In `packages/server/src/openlia_server/routes/connectors.py`, add a new request body model and route handler. Place near the existing `ConnectorCreate` models:

```python
class InstallBuiltinIn(BaseModel):
    template_id: str = Field(min_length=1, max_length=64)
    api_key: str = Field(min_length=1, max_length=512)
```

In the `build_router(...)` (or equivalent) block, add the route handler between existing routes:

```python
@router.post("/install-builtin", status_code=status.HTTP_201_CREATED, response_model=ConnectorOut)
async def install_builtin_route(
    body: InstallBuiltinIn,
    session: DBSession = Depends(make_session_dependency()),
    _: Any = Depends(build_require_active_admin()),
) -> ConnectorOut:
    try:
        connector = await connectors_service.install_builtin(
            session, template_id=body.template_id, api_key=body.api_key
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _connector_to_out(connector)
```

(`_connector_to_out` is the existing serializer used by other routes — match its name as it appears in the file.)

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest packages/server/tests/routes/test_routes_connectors.py -v
```

Expected: green.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check packages/server/src/openlia_server/routes/connectors.py packages/server/tests/routes/test_routes_connectors.py
git add packages/server/src/openlia_server/routes/connectors.py packages/server/tests/routes/test_routes_connectors.py
git commit -m "feat(connectors): POST /api/connectors/install-builtin"
```

---

### Task 13: `GET /api/connectors/builtins` route

**Files:**
- Modify: `packages/server/src/openlia_server/routes/connectors.py`
- Test: `packages/server/tests/routes/test_routes_connectors.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_builtin_templates_returns_six_entries(client: TestClient) -> None:
    res = client.get("/api/connectors/builtins")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    template_ids = {t["template_id"] for t in body}
    assert template_ids == {"eodhd", "fmp", "newsapi_ai", "mediastack", "firecrawl", "x"}


def test_get_builtin_templates_card_shape(client: TestClient) -> None:
    res = client.get("/api/connectors/builtins")
    body = res.json()
    for t in body:
        assert {"template_id", "display_name", "category", "api_key_env_var", "covered_need_ids"}.issubset(t.keys())
        # Internal recipe details are NOT exposed (no argv, no urls, no schemas):
        assert "available_modes" not in t
        assert "runner_specs" not in t
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest packages/server/tests/routes/test_routes_connectors.py::test_get_builtin_templates_returns_six_entries -v
```

- [ ] **Step 3: Implement the route**

Add to `packages/server/src/openlia_server/routes/connectors.py`:

```python
class BuiltinTemplateOut(BaseModel):
    template_id: str
    display_name: str
    category: str
    api_key_env_var: str
    covered_need_ids: list[str]


@router.get("/builtins", response_model=list[BuiltinTemplateOut])
def get_builtin_templates() -> list[BuiltinTemplateOut]:
    from openlia.connectors.builtins import list_templates

    return [
        BuiltinTemplateOut(
            template_id=t.template_id,
            display_name=t.display_name,
            category=t.category.value,
            api_key_env_var=t.api_key_env_var,
            covered_need_ids=[s.need_id for s in t.runner_specs],
        )
        for t in list_templates()
    ]
```

The route is read-only and does not require admin auth (the catalog is not sensitive); if the project convention requires auth for all `/api/connectors` routes, follow that — check the existing `GET /api/connectors` for the pattern.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest packages/server/tests/routes/test_routes_connectors.py -v
```

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check packages/server/src/openlia_server/routes/connectors.py packages/server/tests/routes/test_routes_connectors.py
git add packages/server/src/openlia_server/routes/connectors.py packages/server/tests/routes/test_routes_connectors.py
git commit -m "feat(connectors): GET /api/connectors/builtins"
```

---

## Phase 4 — Frontend catalog UI

### Task 14: Frontend API client extensions

**Files:**
- Modify: `frontend/src/api/connectors.ts`
- Test: `frontend/src/api/connectors.test.ts`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/api/connectors.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { listBuiltinTemplates, installBuiltin } from "./connectors";
import * as client from "./client";

describe("listBuiltinTemplates", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("GETs /api/connectors/builtins and returns the list", async () => {
    const stub = vi.spyOn(client, "fetchJson").mockResolvedValue([
      { template_id: "firecrawl", display_name: "Firecrawl", category: "web_search", api_key_env_var: "FIRECRAWL_API_KEY", covered_need_ids: ["usd_fx_reserve_share"] },
    ]);
    const result = await listBuiltinTemplates();
    expect(stub).toHaveBeenCalledWith("/api/connectors/builtins");
    expect(result).toHaveLength(1);
    expect(result[0].template_id).toBe("firecrawl");
  });
});

describe("installBuiltin", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("POSTs to /api/connectors/install-builtin with the body", async () => {
    const stub = vi.spyOn(client, "fetchJson").mockResolvedValue({
      id: "abc", provider_id: "firecrawl", display_name: "Firecrawl",
      source: "built_in", category: "web_search", status: "validated",
      last_error: null, cached_tools_count: 0,
    });
    const result = await installBuiltin({ template_id: "firecrawl", api_key: "k" });
    expect(stub).toHaveBeenCalledWith(
      "/api/connectors/install-builtin",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ template_id: "firecrawl", api_key: "k" }) }),
    );
    expect(result.provider_id).toBe("firecrawl");
  });
});
```

(Match the actual `fetchJson` signature: it may take `(path, init)` or `(path, opts)`. Inspect existing tests in the file to mirror the pattern.)

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/api/connectors.test.ts
```

Expected: FAIL with "listBuiltinTemplates is not a function" or similar.

- [ ] **Step 3: Implement the API helpers**

Append to `frontend/src/api/connectors.ts`:

```ts
export interface BuiltinTemplate {
  template_id: string;
  display_name: string;
  category: Category;
  api_key_env_var: string;
  covered_need_ids: string[];
}

export interface InstallBuiltinInput {
  template_id: string;
  api_key: string;
}

export async function listBuiltinTemplates(): Promise<BuiltinTemplate[]> {
  return fetchJson("/api/connectors/builtins");
}

export async function installBuiltin(input: InstallBuiltinInput): Promise<ConnectorRow> {
  return fetchJson("/api/connectors/install-builtin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npx vitest run src/api/connectors.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/connectors.ts frontend/src/api/connectors.test.ts
git commit -m "feat(connectors-frontend): API client for builtins catalog"
```

---

### Task 15: `CatalogGrid` and `CatalogCard` components

**Files:**
- Create: `frontend/src/components/connectors/CatalogCard.tsx`
- Create: `frontend/src/components/connectors/CatalogGrid.tsx`
- Test: `frontend/src/components/connectors/__tests__/CatalogGrid.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CatalogGrid } from "../CatalogGrid";
import type { BuiltinTemplate } from "../../../api/connectors";

const TEMPLATES: BuiltinTemplate[] = [
  {
    template_id: "firecrawl",
    display_name: "Firecrawl",
    category: "web_search",
    api_key_env_var: "FIRECRAWL_API_KEY",
    covered_need_ids: ["usd_fx_reserve_share", "cb_gold_purchases", "foreign_treasury_holdings"],
  },
  {
    template_id: "x",
    display_name: "X",
    category: "social",
    api_key_env_var: "X_API_KEY",
    covered_need_ids: [],
  },
];

describe("CatalogGrid", () => {
  it("renders a card per template", () => {
    render(<CatalogGrid templates={TEMPLATES} onSelect={() => {}} />);
    expect(screen.getByText("Firecrawl")).toBeInTheDocument();
    expect(screen.getByText("X")).toBeInTheDocument();
  });

  it("calls onSelect with the template when a card is clicked", () => {
    const onSelect = vi.fn();
    render(<CatalogGrid templates={TEMPLATES} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Firecrawl"));
    expect(onSelect).toHaveBeenCalledWith(TEMPLATES[0]);
  });

  it("renders the category badge per card", () => {
    render(<CatalogGrid templates={TEMPLATES} onSelect={() => {}} />);
    expect(screen.getByText(/web_search/i)).toBeInTheDocument();
    expect(screen.getByText(/social/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/components/connectors/__tests__/CatalogGrid.test.tsx
```

Expected: FAIL with "Cannot find module '../CatalogGrid'".

- [ ] **Step 3: Implement `CatalogCard`**

Create `frontend/src/components/connectors/CatalogCard.tsx`:

```tsx
import type { BuiltinTemplate } from "../../api/connectors";

interface Props {
  template: BuiltinTemplate;
  onClick: () => void;
}

export function CatalogCard({ template, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border p-4 text-left hover:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold">{template.display_name}</span>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs uppercase">
          {template.category}
        </span>
      </div>
      <p className="mt-2 text-sm text-gray-600">
        {template.covered_need_ids.length > 0
          ? `Covers ${template.covered_need_ids.length} runner need${template.covered_need_ids.length === 1 ? "" : "s"}.`
          : "Chat tools only."}
      </p>
    </button>
  );
}
```

- [ ] **Step 4: Implement `CatalogGrid`**

Create `frontend/src/components/connectors/CatalogGrid.tsx`:

```tsx
import { CatalogCard } from "./CatalogCard";
import type { BuiltinTemplate } from "../../api/connectors";

interface Props {
  templates: BuiltinTemplate[];
  onSelect: (template: BuiltinTemplate) => void;
}

export function CatalogGrid({ templates, onSelect }: Props) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
      {templates.map((t) => (
        <CatalogCard key={t.template_id} template={t} onClick={() => onSelect(t)} />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd frontend && npx vitest run src/components/connectors/__tests__/CatalogGrid.test.tsx
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/connectors/CatalogCard.tsx frontend/src/components/connectors/CatalogGrid.tsx frontend/src/components/connectors/__tests__/CatalogGrid.test.tsx
git commit -m "feat(connectors-frontend): catalog grid components"
```

---

### Task 16: `InstallBuiltinForm` component

**Files:**
- Create: `frontend/src/components/connectors/InstallBuiltinForm.tsx`
- Test: `frontend/src/components/connectors/__tests__/InstallBuiltinForm.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InstallBuiltinForm } from "../InstallBuiltinForm";
import type { BuiltinTemplate } from "../../../api/connectors";
import * as connectorsApi from "../../../api/connectors";

const TEMPLATE: BuiltinTemplate = {
  template_id: "firecrawl",
  display_name: "Firecrawl",
  category: "web_search",
  api_key_env_var: "FIRECRAWL_API_KEY",
  covered_need_ids: [],
};

describe("InstallBuiltinForm", () => {
  it("renders the env-var label and an api_key input", () => {
    render(<InstallBuiltinForm template={TEMPLATE} onCancel={() => {}} onInstalled={() => {}} />);
    expect(screen.getByText("FIRECRAWL_API_KEY")).toBeInTheDocument();
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
  });

  it("calls installBuiltin and onInstalled on submit", async () => {
    const installStub = vi.spyOn(connectorsApi, "installBuiltin").mockResolvedValue({
      id: "1", provider_id: "firecrawl", display_name: "Firecrawl",
      source: "built_in", category: "web_search", status: "validated",
      last_error: null, cached_tools_count: 0,
    });
    const onInstalled = vi.fn();

    render(<InstallBuiltinForm template={TEMPLATE} onCancel={() => {}} onInstalled={onInstalled} />);
    fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "user-key" } });
    fireEvent.click(screen.getByRole("button", { name: /install/i }));

    await waitFor(() => expect(installStub).toHaveBeenCalledWith({ template_id: "firecrawl", api_key: "user-key" }));
    await waitFor(() => expect(onInstalled).toHaveBeenCalled());
  });

  it("shows an error message if install fails", async () => {
    vi.spyOn(connectorsApi, "installBuiltin").mockRejectedValue(new Error("nope"));
    render(<InstallBuiltinForm template={TEMPLATE} onCancel={() => {}} onInstalled={() => {}} />);
    fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: /install/i }));
    expect(await screen.findByText(/nope/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/components/connectors/__tests__/InstallBuiltinForm.test.tsx
```

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/connectors/InstallBuiltinForm.tsx`:

```tsx
import { useState } from "react";
import { installBuiltin, type BuiltinTemplate, type ConnectorRow } from "../../api/connectors";

interface Props {
  template: BuiltinTemplate;
  onCancel: () => void;
  onInstalled: (row: ConnectorRow) => void;
}

export function InstallBuiltinForm({ template, onCancel, onInstalled }: Props) {
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const row = await installBuiltin({ template_id: template.template_id, api_key: apiKey });
      onInstalled(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Install failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <h3 className="text-lg font-semibold">{template.display_name}</h3>
      <label className="block">
        <span className="text-sm font-medium">API key</span>
        <span className="ml-2 text-xs text-gray-500">{template.api_key_env_var}</span>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          required
          className="mt-1 block w-full rounded border px-3 py-2"
        />
      </label>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={submitting || !apiKey} className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50">
          {submitting ? "Installing..." : "Install"}
        </button>
        <button type="button" onClick={onCancel} className="rounded border px-4 py-2">
          Cancel
        </button>
      </div>
    </form>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd frontend && npx vitest run src/components/connectors/__tests__/InstallBuiltinForm.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/connectors/InstallBuiltinForm.tsx frontend/src/components/connectors/__tests__/InstallBuiltinForm.test.tsx
git commit -m "feat(connectors-frontend): single-field install form"
```

---

### Task 17: Wire catalog into `ConnectorsAdminPanel` and `ConnectorsStep`

**Files:**
- Modify: `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx`
- Modify: `frontend/src/setup/steps/ConnectorsStep.tsx`
- Test: extend `frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx`
- Test: extend `frontend/src/setup/steps/__tests__/ConnectorsStep.test.tsx`

The wiring is the same pattern in both files: render a "Add from catalog" primary button that opens `CatalogGrid`; when a card is clicked, swap to `InstallBuiltinForm`; the existing "Add custom" flow stays as a less-prominent secondary button.

- [ ] **Step 1: Write the failing test (admin panel)**

Append to `frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx`:

```tsx
import * as connectorsApi from "../../../../api/connectors";

it("renders the catalog grid when 'Add from catalog' is clicked", async () => {
  vi.spyOn(connectorsApi, "listBuiltinTemplates").mockResolvedValue([
    { template_id: "firecrawl", display_name: "Firecrawl", category: "web_search", api_key_env_var: "FIRECRAWL_API_KEY", covered_need_ids: [] },
  ]);
  render(<ConnectorsAdminPanel />);
  fireEvent.click(await screen.findByRole("button", { name: /add from catalog/i }));
  expect(await screen.findByText("Firecrawl")).toBeInTheDocument();
});

it("opens the install form when a catalog card is clicked", async () => {
  vi.spyOn(connectorsApi, "listBuiltinTemplates").mockResolvedValue([
    { template_id: "firecrawl", display_name: "Firecrawl", category: "web_search", api_key_env_var: "FIRECRAWL_API_KEY", covered_need_ids: [] },
  ]);
  render(<ConnectorsAdminPanel />);
  fireEvent.click(await screen.findByRole("button", { name: /add from catalog/i }));
  fireEvent.click(await screen.findByText("Firecrawl"));
  expect(await screen.findByLabelText(/api key/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend && npx vitest run src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx
```

- [ ] **Step 3: Wire the catalog into `ConnectorsAdminPanel.tsx`**

In the existing component, add three local-state slots:

```tsx
const [catalog, setCatalog] = useState<BuiltinTemplate[] | null>(null);
const [picking, setPicking] = useState(false);
const [chosenTemplate, setChosenTemplate] = useState<BuiltinTemplate | null>(null);
```

Replace the existing single "Add" button with:

```tsx
<div className="flex gap-2">
  <button
    type="button"
    onClick={async () => {
      if (catalog === null) setCatalog(await listBuiltinTemplates());
      setPicking(true);
    }}
    className="rounded bg-blue-600 px-4 py-2 text-white"
  >
    Add from catalog
  </button>
  <button type="button" onClick={() => setAdding(true)} className="rounded border px-4 py-2">
    Add custom
  </button>
</div>
```

When `picking` is true, render the `<CatalogGrid templates={catalog ?? []} onSelect={(t) => { setChosenTemplate(t); setPicking(false); }} />`.

When `chosenTemplate` is non-null, render `<InstallBuiltinForm template={chosenTemplate} onCancel={() => setChosenTemplate(null)} onInstalled={(row) => { setChosenTemplate(null); refresh(); }} />`.

Add the imports:

```tsx
import { CatalogGrid } from "../../connectors/CatalogGrid";
import { InstallBuiltinForm } from "../../connectors/InstallBuiltinForm";
import { listBuiltinTemplates, type BuiltinTemplate } from "../../../api/connectors";
```

- [ ] **Step 4: Repeat for `ConnectorsStep.tsx`**

Apply the same wiring pattern in `frontend/src/setup/steps/ConnectorsStep.tsx`. Keep the existing "Add custom" path (`AddConnectorForm`) intact.

- [ ] **Step 5: Run the tests**

```bash
cd frontend && npx vitest run src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx src/setup/steps/__tests__/ConnectorsStep.test.tsx
```

If the existing `ConnectorsStep.test.tsx` doesn't have catalog tests, add one analogous to the admin-panel test in Step 1.

- [ ] **Step 6: Browser smoke**

```bash
cd frontend && npm run dev &  # serves on http://localhost:5173 with proxy to FastAPI
# in another shell:
uv run openlia serve
```

Open `http://localhost:5173/setup` (or `/settings/admin/connectors`), click "Add from catalog", verify all six cards render, click Firecrawl, paste a real API key (or any non-empty string if you stub the canary), confirm the Connector row appears in the list with `status=validated` (or `failed` with a clear last_error if the key is bogus).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx frontend/src/setup/steps/ConnectorsStep.tsx frontend/src/components/settings/admin/__tests__/ConnectorsAdminPanel.test.tsx frontend/src/setup/steps/__tests__/ConnectorsStep.test.tsx
git commit -m "feat(connectors-frontend): catalog entry in wizard + admin panel"
```

---

## Phase 5 — Spec amendment + integration

### Task 18: Amend §13.5 of the connector dataflow spec

**Files:**
- Modify: `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md` (§13.5)

- [ ] **Step 1: Locate §13.5**

```bash
grep -n "13\.5" docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md
```

- [ ] **Step 2: Replace the locked-empty wording**

Open the file. Find the §13.5 paragraph that reads (paraphrased): "the day-1 catalog of built-in templates is locked empty …". Replace with:

```markdown
### 13.5 Day-1 catalog (revised 2026-05-01)

The day-1 built-in catalog ships six templates: EODHD, FMP, NewsAPI.ai,
Mediastack, Firecrawl, X. Each is curated under
`docs/superpowers/specs/2026-05-01-builtin-connectors-design.md`, which
documents the per-provider mode recipes, runner-need mappings, and the
two additive type-system extensions (`BuiltInTemplate.runner_specs` and
`CallableSpec.result_path`). The earlier "locked empty" decision is
superseded.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md
git commit -m "docs(specs): amend §13.5 — day-1 catalog ships six templates"
```

---

### Task 19: End-to-end smoke + final lint pass

**Files:**
- Test: full suite

- [ ] **Step 1: Run the full backend test suite**

```bash
uv run pytest -v
```

Expected: all green. Investigate any red.

- [ ] **Step 2: Run the full frontend test suite**

```bash
cd frontend && npx vitest run
```

Expected: all green.

- [ ] **Step 3: Lint the entire repo**

```bash
uv run ruff check .
uv run ruff format --check .
cd frontend && npx eslint src
```

Expected: clean across all three. Fix any issues with `uv run ruff format .` and re-run.

- [ ] **Step 4: Smoke-test one real install end-to-end**

Pick the lowest-cost provider with the easiest free API key (Firecrawl has a free tier with 500 requests/month; if you have a key, use it).

```bash
uv run openlia serve &
# Get an admin token via the existing auth flow.
curl -X POST http://localhost:8000/api/connectors/install-builtin \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"template_id": "firecrawl", "api_key": "<your-firecrawl-key>"}'
```

Expected: HTTP 201, body has `status: "validated"`. Then:

```bash
curl http://localhost:8000/api/connectors -H "Authorization: Bearer <admin-token>"
```

Expected: list includes the new Firecrawl row.

If you don't have a real key, run the route test from Task 12 — the stubbed canary path covers the same flow.

- [ ] **Step 5: Push the branch and open the PR**

```bash
git push -u origin feat/builtin-connectors
gh pr create --title "feat: built-in connector catalog (day-1: 6 templates)" --body "$(cat <<'EOF'
## Summary
- Curated day-1 built-in connector catalog of 6 templates (EODHD, FMP, NewsAPI.ai, Mediastack, Firecrawl, X)
- Adds `runner_specs` to `BuiltInTemplate` and `result_path` to `CallableSpec` (both additive, fully back-compat)
- New install path `POST /api/connectors/install-builtin` that bypasses the wizard-time adapter LLM
- Catalog UI in setup wizard and admin panel — user provides only an API key
- Supersedes spec §13.5 lock on empty day-1 catalog

## Test plan
- [ ] `uv run pytest -v` (backend, all green)
- [ ] `npx vitest run` (frontend, all green)
- [ ] `uv run ruff check .` + `npx eslint src`
- [ ] Manual: install Firecrawl from catalog UI in browser, verify Connector row appears with `status=validated`
- [ ] Manual: trigger Macro Research's World Order dashboard, verify the three Firecrawl-served needs return numeric values

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

(`gh pr create` opens the PR against `main` by default. If `feat/batched-resolver`'s PR #82 has not yet merged, target this PR at `feat/batched-resolver` instead with `--base feat/batched-resolver` so it stacks cleanly.)

- [ ] **Step 6: Done**

Plan complete. Mark all tasks done.

---

## Self-review notes

- **Spec coverage:** §1 goal → Tasks 11-13 (install path) + 14-17 (catalog UX). §2 catalog table → Tasks 4-10. §3 schema → Tasks 1-3. §4 install flow → Task 11. §5 frontend → Tasks 14-17. §6 recipe shape → covered in each per-provider task. §7 §13.5 amendment → Task 18. §8 risks → addressed throughout (canary in Task 11, version pins in Tasks 4-9).
- **Type consistency:** `BuiltInTemplate.runner_specs` is `tuple[CallableSpec, ...]` everywhere; `CallableSpec.result_path` is `tuple[str, ...]` everywhere. `_NEED_DEPARTMENT_MAP` keys match the need ids in `*.needs.yaml`.
- **No placeholders:** the per-provider tasks contain explicit research commands (WebFetch URLs, grep targets) and the engineer fills in concrete values from research. The plan is candid that exact MCP package names / version pins / EODHD method names get filled at impl time — that's research work, not undefined plan content. Each task's *test* is concrete and asserts the structural invariants the recipe must satisfy regardless of upstream specifics.
