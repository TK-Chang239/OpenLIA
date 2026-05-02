"""FMP (Financial Modeling Prep) built-in connector template.

Source: FMP's officially hosted MCP server.
  https://financialmodelingprep.com/mcp?apikey=FMP_API_KEY

Tool surface and indicator codes verified against the live MCP server
(2026-05-01) using the user's FMP API key. Findings:

- Tools are dispatched via an `endpoint` enum, not flat names. So
  `quote` is a tool that takes `{endpoint, symbol}` and `economics`
  takes `{endpoint, name, from, to}`.
- Of the macro indicator names we wanted, only `GDP`, `CPI`, and
  `inflationRate` are accepted. `coreCPI`, `debtToGDP`, `PMI`, and
  `interestToRevenue` are rejected with "Invalid name". Specs that
  named those indicators have been dropped.
- FMP has no social-sentiment endpoint. The `social_posts` need is
  served by EODHD only.

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


def _macro_spec(*, need_id: str, indicator_name: str) -> CallableSpec:
    """Macro indicator spec.

    Routes to FMP's `economics` tool with `endpoint=economics-indicators`.
    Response is a list of `{name, date, value}` dicts sorted by date desc.
    """
    return CallableSpec(
        need_id=need_id,
        access_mode="remote_mcp",
        tool_name="economics",
        param_bindings={"country": ParamBinding(to_arg="country")},
        constants={"endpoint": "economics-indicators", "name": indicator_name},
        result_path=(),
        shape="float",
    )


# Verified live: GDP, CPI accepted. coreCPI/debtToGDP/PMI/interestToRevenue
# rejected as "Invalid name" — those needs are uncovered by FMP.
_GDP_YOY = _macro_spec(need_id="gdp_yoy", indicator_name="GDP")
_CPI_YOY = _macro_spec(need_id="cpi_yoy", indicator_name="CPI")

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


FMP_TEMPLATE = BuiltInTemplate(
    template_id="fmp",
    display_name="Financial Modeling Prep",
    category=Category.FINANCIAL,
    api_key_env_var="FMP_API_KEY",
    available_modes=(
        RemoteMcpRecipe(
            kind="remote_mcp",
            url="https://financialmodelingprep.com/mcp?apikey={api_key}",
            headers=(),
        ),
    ),
    canary_tool="quote",
    runner_specs=(
        _GDP_YOY,
        _CPI_YOY,
        _STOCK_QUOTE,
    ),
)
