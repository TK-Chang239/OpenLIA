"""Firecrawl built-in connector template.

Source: https://github.com/mendableai/firecrawl-mcp-server (npm: firecrawl-mcp)

Covers three Macro Research World Order needs that require scraping
official-statistics websites (IMF COFER, World Gold Council, US Treasury TIC).
Each runner spec invokes Firecrawl's `firecrawl_extract` tool with a fixed
URL and JSON schema, then uses `result_path` to reduce the structured
response to a float.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    RemoteMcpRecipe,
)
from openlia.connectors.types import CallableSpec, Category

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
        "prompt": ("Extract net central-bank gold purchases over the trailing year, in tonnes."),
        "schema": {
            "type": "object",
            "properties": {"net_purchases_tonnes": {"type": "number"}},
            "required": ["net_purchases_tonnes"],
        },
    },
    param_bindings={},
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
            url="https://mcp.firecrawl.dev/{api_key}/v2/mcp",
            headers=(),
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
