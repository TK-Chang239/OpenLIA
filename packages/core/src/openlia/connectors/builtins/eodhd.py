"""EODHD built-in connector template.

Source: https://github.com/eodhd/python-package (pip: `eodhd`)

Covers Macro Research macro indicators (debt_gdp, interest_revenue, gdp_yoy,
cpi_yoy, cpi_core_yoy, pmi), the stock_quote runner need, and the
retail_sentiment social_posts need.
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


def _macro_spec(*, need_id: str, indicator_code: str) -> CallableSpec:
    return CallableSpec(
        need_id=need_id,
        access_mode="python_lib",
        module="eodhd",
        method="APIClient.get_macro_indicators_data",
        instance_factory=_API_CLIENT,
        param_bindings={"country": ParamBinding(to_arg="country", transform="iso_to_eodhd")},
        constants={"indicator": indicator_code},
        result_path=(),
        shape="float",
    )


_DEBT_GDP = _macro_spec(need_id="debt_gdp", indicator_code="debt_to_gdp")
_INTEREST_REVENUE = _macro_spec(need_id="interest_revenue", indicator_code="interest_to_revenue")
_GDP_YOY = _macro_spec(need_id="gdp_yoy", indicator_code="gdp_growth_annual")
_CPI_YOY = _macro_spec(need_id="cpi_yoy", indicator_code="inflation_consumer_prices_annual")
_CPI_CORE_YOY = _macro_spec(need_id="cpi_core_yoy", indicator_code="inflation_core_annual")
_PMI = _macro_spec(need_id="pmi", indicator_code="pmi_manufacturing")

_STOCK_QUOTE = CallableSpec(
    need_id="stock_quote",
    access_mode="python_lib",
    module="eodhd",
    method="APIClient.real_time_quote",  # TODO(verify): confirm method name in eodhd SDK
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
    method="APIClient.sentiment_data",  # TODO(verify): confirm method name in eodhd SDK
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
            argv=("uvx", "eodhd-mcp"),
            env_keys=("EODHD_API_KEY",),
        ),
        PythonLibRecipe(
            kind="python_lib",
            pip_name="eodhd",
            pip_version=">=1.0.0,<2.0.0",
            import_module="eodhd",
            instance_factory_cls="APIClient",
            instance_factory_args=(("api_key", _API_KEY_PLACEHOLDER),),
        ),
    ),
    canary_tool="real_time_quote",
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
