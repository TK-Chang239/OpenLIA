"""Firecrawl built-in connector template.

Sources:
- https://github.com/firecrawl/firecrawl-mcp-server (npm: firecrawl-mcp)
- https://docs.firecrawl.dev/sdks/python (PyPI: firecrawl-py)

Covers three Macro Research World Order needs that require scraping
official-statistics websites (IMF COFER, World Gold Council, US Treasury TIC).

Runner specs use the Python SDK's `scrape` method with v2 JSON mode
(`formats=[{"type": "json", "schema": {...}}]`). The deprecated `/extract`
endpoint is avoided. MCP recipes remain available for chat-toolbox use
(firecrawl_search / firecrawl_scrape exposed to chat departments).
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    PythonLibRecipe,
    RemoteMcpRecipe,
)
from openlia.connectors.types import CallableSpec, Category


def _scrape_spec(
    *,
    need_id: str,
    url: str,
    field_name: str,
    field_description: str,
) -> CallableSpec:
    """Build a python_lib scrape spec extracting a single numeric field."""
    return CallableSpec(
        need_id=need_id,
        access_mode="python_lib",
        method="Firecrawl.scrape",
        constants={
            "url": url,
            "formats": [
                {
                    "type": "json",
                    "schema": {
                        "type": "object",
                        "properties": {
                            field_name: {
                                "type": "number",
                                "description": field_description,
                            }
                        },
                        "required": [field_name],
                    },
                }
            ],
        },
        result_path=("json", field_name),
        shape="float",
    )


_USD_FX_RESERVE_SHARE = _scrape_spec(
    need_id="usd_fx_reserve_share",
    url="https://data.imf.org/regular.aspx?key=41175",
    field_name="usd_share_pct",
    field_description=(
        "Most recent USD share of total allocated foreign exchange reserves, "
        "as a percentage (e.g. 58.4)."
    ),
)

_CB_GOLD_PURCHASES = _scrape_spec(
    need_id="cb_gold_purchases",
    url="https://www.gold.org/goldhub/research/gold-demand-trends",
    field_name="net_purchases_tonnes",
    field_description="Net central-bank gold purchases over trailing year, in tonnes.",
)

_FOREIGN_TREASURY_HOLDINGS = _scrape_spec(
    need_id="foreign_treasury_holdings",
    url=(
        "https://home.treasury.gov/data/treasury-international-capital-tic-system/"
        "tic-forms-instructions/major-foreign-holders-treasury-securities"
    ),
    field_name="change_usd_billions",
    field_description=(
        "Trailing 90-day change in total foreign holdings of US Treasury "
        "securities, in USD billions (positive = accumulation)."
    ),
)

# US federal interest expense as a percentage of federal revenue. EODHD's
# macro-indicators catalog and FMP's economics endpoint both lack this
# series, so we scrape Treasury's Fiscal Data summary page where the
# ratio is published in plain text.
_INTEREST_REVENUE = _scrape_spec(
    need_id="interest_revenue",
    url="https://fiscaldata.treasury.gov/americas-finance-guide/national-debt/",
    field_name="interest_to_revenue_pct",
    field_description=(
        "Federal interest expense as a percentage of federal revenue, "
        "expressed as a percentage (e.g. 16.5)."
    ),
)


FIRECRAWL_TEMPLATE = BuiltInTemplate(
    template_id="firecrawl",
    display_name="Firecrawl",
    category=Category.WEB_SEARCH,
    api_key_env_var="FIRECRAWL_API_KEY",
    available_modes=(
        PythonLibRecipe(
            kind="python_lib",
            pip_name="firecrawl-py",
            pip_version=">=4.0.0,<5.0.0",
            import_module="firecrawl",
            instance_factory_cls="Firecrawl",
            instance_factory_args=(("api_key", "$FIRECRAWL_API_KEY"),),
        ),
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
    canary_tool="scrape",
    runner_specs=(
        _USD_FX_RESERVE_SHARE,
        _CB_GOLD_PURCHASES,
        _FOREIGN_TREASURY_HOLDINGS,
        _INTEREST_REVENUE,
    ),
)
