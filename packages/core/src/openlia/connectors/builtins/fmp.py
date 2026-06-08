"""FMP (Financial Modeling Prep) built-in connector template.

Source: FMP's officially hosted MCP server.
  https://financialmodelingprep.com/mcp?apikey=FMP_API_KEY

Tool surface verified against the live MCP server (2026-05-01).

Covers Portfolio's stock_quote need via the `quote` tool. The full
chat-toolbox surface (calendar, statements, analyst, etc.) is available
to chat departments through the MCP client.

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
    runner_specs=(_STOCK_QUOTE,),
)
