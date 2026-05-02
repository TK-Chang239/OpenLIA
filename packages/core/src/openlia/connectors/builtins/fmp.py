"""FMP (Financial Modeling Prep) built-in connector template.

Source: FMP's officially hosted MCP server.
  https://financialmodelingprep.com/mcp?apikey=FMP_API_KEY

The Python SDK `fmpsdk` (github.com/daxm/fmpsdk) is stale — last touched
2021-02-20 — and its hardcoded indicator allowlist lacks debtToGDP,
coreCPI, PMI, and interestToRevenue. We avoid it. The hosted MCP server
is the only mode we ship.

Per FMP's MCP example, `quote(symbol)` is exposed and returns
`structured_content={"data": [{...}]}` (a list with one quote record).
The `economic_indicator` and `historical_social_sentiment` tools listed
below mirror FMP's REST endpoints and are canary-verified at install
time — wrong tool names will surface as `status=failed` instead of
silent miswiring.
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

    FMP's REST `/economic` endpoint accepts a `name` query param. The
    canonical valid names per FMP's docs include GDP, CPI, coreCPI,
    PMI, debtToGDP, interestToRevenue. Hosted MCP exposes this as the
    `economic_indicator` tool.
    """
    return CallableSpec(
        need_id=need_id,
        access_mode="remote_mcp",
        tool_name="economic_indicator",
        param_bindings={"country": ParamBinding(to_arg="country")},
        constants={"name": indicator_name},
        result_path=(),
        shape="float",
    )


_DEBT_GDP = _macro_spec(need_id="debt_gdp", indicator_name="debtToGDP")
_INTEREST_REVENUE = _macro_spec(need_id="interest_revenue", indicator_name="interestToRevenue")
_GDP_YOY = _macro_spec(need_id="gdp_yoy", indicator_name="GDP")
_CPI_YOY = _macro_spec(need_id="cpi_yoy", indicator_name="CPI")
_CPI_CORE_YOY = _macro_spec(need_id="cpi_core_yoy", indicator_name="coreCPI")
_PMI = _macro_spec(need_id="pmi", indicator_name="PMI")

# `quote(symbol)` — verified from FMP's official MCP usage example.
_STOCK_QUOTE = CallableSpec(
    need_id="stock_quote",
    access_mode="remote_mcp",
    tool_name="quote",
    param_bindings={"ticker": ParamBinding(to_arg="symbol")},
    constants={},
    result_path=(),
    shape="dict",
)

# `historical_social_sentiment(symbol)` mirrors FMP's REST endpoint
# /api/v4/historical/social-sentiment. Canary will catch a name mismatch.
_SOCIAL_POSTS = CallableSpec(
    need_id="social_posts",
    access_mode="remote_mcp",
    tool_name="historical_social_sentiment",
    param_bindings={"ticker": ParamBinding(to_arg="symbol")},
    constants={},
    result_path=(),
    shape="list[dict]",
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
