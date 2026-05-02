"""FMP (Financial Modeling Prep) built-in connector template.

Source: FMP's officially hosted MCP server.
  https://financialmodelingprep.com/mcp?apikey=FMP_API_KEY

Tool surface verified against the live MCP server (2026-05-01).

The day-1 spec set is intentionally small — just `stock_quote` via the
`quote` tool. FMP's `economics` tool returns list[dict] of dated
records, not a float, so binding it to needs declared with `shape='float'`
is a runtime shape mismatch. Macro indicators (gdp_yoy, cpi_yoy,
debt_gdp, cpi_core_yoy, pmi) are covered by EODHD's reducer methods on
ExtendedAPIClient instead. FMP also has no social-sentiment endpoint,
so social_posts is EODHD-only.

The chat-toolbox surface (FMP's other tools — calendar, statements,
analyst, etc.) is still available to chat departments through the MCP
client; only deterministic-runner specs are scoped here.

The Python SDK `daxm/fmpsdk` is stale (last commit 2021-02-20) and
can't reach modern endpoints. Avoid.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    RemoteMcpRecipe,
)
from openlia.connectors.types import (
    CallableSpec,
    Category,
    ParamBinding,
)

# Verified live: quote tool with endpoint='quote', symbol=<ticker>.
# Returns a list with one quote dict.
_STOCK_QUOTE = CallableSpec(
    need_id="stock_quote",
    access_mode="remote_mcp",
    tool_name="quote",
    param_bindings={"ticker": ParamBinding(to_arg="symbol")},
    constants={"endpoint": "quote"},
    result_path=(),
    shape="dict",
)

# Macro indicators verified live (2026-05-02). FMP's economics-indicators
# returns list[{name, date, value}]; we apply a result_reducer per spec
# to collapse the time-series into a single float.
_CPI_YOY = CallableSpec(
    need_id="cpi_yoy",
    access_mode="remote_mcp",
    tool_name="economics",
    constants={"endpoint": "economics-indicators", "name": "inflationRate"},
    result_reducer="latest_value_by_date",
    shape="float",
)

# realGDP returns quarterly *levels* — yoy_pct_quarterly reducer turns
# them into year-over-year %. The reducer needs ≥5 quarterly records
# (latest + 4 quarters back); FMP's default window is too narrow, so we
# pin a wide `from` date to ensure enough history.
_GDP_YOY = CallableSpec(
    need_id="gdp_yoy",
    access_mode="remote_mcp",
    tool_name="economics",
    constants={
        "endpoint": "economics-indicators",
        "name": "realGDP",
        "from": "2020-01-01",
    },
    result_reducer="yoy_pct_quarterly",
    shape="float",
)


FMP_TEMPLATE = BuiltInTemplate(
    template_id="fmp",
    display_name="Financial Modeling Prep",
    category=Category.FINANCIAL,
    api_key_env_var="FMP_API_KEY",
    available_modes=(
        RemoteMcpRecipe(
            kind="remote_mcp",
            url="https://financialmodelingprep.com/mcp?apikey={FMP_API_KEY}",
            headers=(),
        ),
    ),
    canary_tool="quote",
    # Authenticated round-trip: list_tools alone passes without auth on
    # FMP's hosted MCP, so we exercise the cheapest authenticated tool
    # (a single AAPL quote) at install time.
    canary_args=(("endpoint", "quote"), ("symbol", "AAPL")),
    # FMP and EODHD are alternatives — the user installs one or the other.
    # install_builtin's replace-on-conflict logic transfers ownership of
    # any overlapping (dept, need) to the most-recently-installed template.
    runner_specs=(_STOCK_QUOTE, _CPI_YOY, _GDP_YOY),
)
