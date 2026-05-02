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


# Source URLs were live-verified against Firecrawl's scrape API on
# 2026-05-01. Sources picked so the target field falls out of plain text
# (not JS-rendered tables / interactive charts), since Firecrawl's JSON
# mode reads the rendered markdown.

_USD_FX_RESERVE_SHARE = _scrape_spec(
    need_id="usd_fx_reserve_share",
    url="https://en.wikipedia.org/wiki/Reserve_currency",
    field_name="usd_share_pct",
    field_description=(
        "Most recent USD share of total allocated foreign exchange reserves "
        "(IMF COFER), as a percentage (e.g. 58.4)."
    ),
)

_CB_GOLD_PURCHASES = _scrape_spec(
    need_id="cb_gold_purchases",
    url="https://www.gold.org/goldhub/research/gold-demand-trends",
    field_name="net_purchases_tonnes",
    field_description="Net central-bank gold purchases over trailing year, in tonnes.",
)

# Treasury's Major Foreign Holders text file lists totals month-by-month.
# We scrape the most recent total holdings figure (USD billions). The need
# was originally framed as a 90-day Δ but no public page publishes the
# delta directly, so the day-1 catalog ships the absolute total. Computing
# Δ from two snapshots is a future scope item for the runner-side wrapper.
_FOREIGN_TREASURY_HOLDINGS = _scrape_spec(
    need_id="foreign_treasury_holdings",
    url="https://ticdata.treasury.gov/Publish/mfh.txt",
    field_name="total_usd_billions",
    field_description=(
        "Most recent total foreign holdings of US Treasury securities, "
        "in USD billions (e.g. 7402.5)."
    ),
)

# US federal interest expense as a percentage of federal revenue. EODHD's
# macro-indicators catalog and FMP's economics endpoint both lack this
# series. Wikipedia's National-debt-of-the-United-States page summarizes
# the ratio in plain text; live-probed value matched recent fiscal-year
# figures.
_INTEREST_REVENUE = _scrape_spec(
    need_id="interest_revenue",
    url="https://en.wikipedia.org/wiki/National_debt_of_the_United_States",
    field_name="interest_to_revenue_pct",
    field_description=(
        "Net interest outlays divided by total federal revenue (or "
        "receipts) for the latest available fiscal year, expressed as "
        "a percentage. Example: if interest is $1T and revenue is $5T, "
        "this value is 20.0."
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
            url="https://mcp.firecrawl.dev/{FIRECRAWL_API_KEY}/v2/mcp",
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
