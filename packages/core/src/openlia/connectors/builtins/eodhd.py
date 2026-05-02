"""EODHD built-in connector template.

Sources:
- https://github.com/EodHistoricalData/EODHD-APIs-Python-Financial-Library
- https://eodhd.com/financial-apis/macroeconomics-data-and-macro-indicators-api
- https://eodhistoricaldata.com/financial-apis/economic-events-data-api/

Covers most of Macro Research's macro indicators plus stock_quote and
the retail_sentiment social_posts need. The macro-indicators catalog
exposes debt_percent_gdp, gdp_growth_annual, and inflation_consumer_prices_annual.
The economic-events feed (via our ExtendedAPIClient wrapper) covers
core inflation rate and ISM Manufacturing PMI. The remaining
interest_revenue need is covered by Firecrawl scraping (see firecrawl.py).
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
# We instantiate openlia.data.eodhd_extended.ExtendedAPIClient (a subclass
# of eodhd.APIClient) so callers get every official APIClient method plus
# our derived series (core_inflation_rate, ism_manufacturing_pmi).
_API_CLIENT = InstanceFactory(cls="ExtendedAPIClient", args={"api_key": _API_KEY_PLACEHOLDER})


def _reducer_spec(*, need_id: str, method_name: str) -> CallableSpec:
    """Macro-indicator spec that targets one of ExtendedAPIClient's
    reducer methods (debt_to_gdp / gdp_growth_yoy / cpi_yoy / …).

    The reducer translates iso-2 → iso-3 internally, calls EODHD's
    macro-indicators endpoint, and returns the latest non-null Value
    as a float. Country code stays iso-2 on the wire (matches needs.yaml).
    """
    return CallableSpec(
        need_id=need_id,
        access_mode="python_lib",
        module="openlia.data.eodhd_extended",
        method=f"ExtendedAPIClient.{method_name}",
        instance_factory=_API_CLIENT,
        param_bindings={"country": ParamBinding(to_arg="country")},
        constants={},
        result_path=(),
        shape="float",
    )


# Macro-indicator-catalog series, reduced to floats by ExtendedAPIClient.
_DEBT_GDP = _reducer_spec(need_id="debt_gdp", method_name="debt_to_gdp")
_GDP_YOY = _reducer_spec(need_id="gdp_yoy", method_name="gdp_growth_yoy")
_CPI_YOY = _reducer_spec(need_id="cpi_yoy", method_name="cpi_yoy")

# Derived series. Core CPI and ISM PMI aren't in EODHD's macro-indicators
# catalog, but both surface in its economic-events feed. ExtendedAPIClient
# filters and reduces each to a latest-non-null float. Country code here
# follows the events-feed convention (alpha-2), no transform applied.
_CPI_CORE_YOY = CallableSpec(
    need_id="cpi_core_yoy",
    access_mode="python_lib",
    module="openlia.data.eodhd_extended",
    method="ExtendedAPIClient.core_inflation_rate",
    instance_factory=_API_CLIENT,
    param_bindings={"country": ParamBinding(to_arg="country")},
    constants={},
    result_path=(),
    shape="float",
)

_PMI = CallableSpec(
    need_id="pmi",
    access_mode="python_lib",
    module="openlia.data.eodhd_extended",
    method="ExtendedAPIClient.ism_manufacturing_pmi",
    instance_factory=_API_CLIENT,
    param_bindings={"country": ParamBinding(to_arg="country")},
    constants={},
    result_path=(),
    shape="float",
)

# APIClient.get_live_stock_prices(ticker, s=None). The first positional arg
# is named "ticker" on the SDK, matching the runtime parameter from
# macro_research.needs.yaml#stock_quote.
_STOCK_QUOTE = CallableSpec(
    need_id="stock_quote",
    access_mode="python_lib",
    module="eodhd",
    method="ExtendedAPIClient.get_live_stock_prices",
    instance_factory=_API_CLIENT,
    param_bindings={"ticker": ParamBinding(to_arg="ticker")},
    constants={},
    result_path=(),
    shape="dict",
)

# APIClient.get_sentiment(s, from_date=None, to_date=None). Comma-separated
# tickers (we pass one). The runtime param "ticker" maps to the SDK's "s".
_SOCIAL_POSTS = CallableSpec(
    need_id="social_posts",
    access_mode="python_lib",
    module="eodhd",
    method="ExtendedAPIClient.get_sentiment",
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
        PythonLibRecipe(
            kind="python_lib",
            pip_name="eodhd",
            pip_version=">=1.0.0,<2.0.0",
            import_module="openlia.data.eodhd_extended",
            instance_factory_cls="ExtendedAPIClient",
            instance_factory_args=(("api_key", _API_KEY_PLACEHOLDER),),
        ),
        CliMcpRecipe(
            kind="cli_mcp",
            argv=("uvx", "eodhd-mcp"),
            env_keys=("EODHD_API_KEY",),
        ),
    ),
    canary_tool="get_live_stock_prices",
    runner_specs=(
        _DEBT_GDP,
        _GDP_YOY,
        _CPI_YOY,
        _CPI_CORE_YOY,
        _PMI,
        _STOCK_QUOTE,
        _SOCIAL_POSTS,
    ),
)
