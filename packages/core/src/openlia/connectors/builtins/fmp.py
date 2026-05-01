"""FMP (Financial Modeling Prep) built-in connector template.

Source: https://github.com/daxm/fmpsdk (pip: `fmpsdk`)

Alternate financial provider; covers the same Macro Research macro indicators
as EODHD plus stock_quote and the retail_sentiment social_posts need. FMP's
`fmpsdk` package exposes module-level functions (not a class), so each
runner spec calls a function directly with `apikey` constant.
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

_API_KEY_PLACEHOLDER = "$FMP_API_KEY"
# fmpsdk exposes module-level functions; we reuse the InstanceFactory shape
# so the same dispatcher path works. The `cls` is the module, args carry
# the apikey to inject as a constant on every call.
_API_CLIENT = InstanceFactory(cls="fmpsdk", args={"apikey": _API_KEY_PLACEHOLDER})


def _macro_spec(*, need_id: str, indicator_name: str) -> CallableSpec:
    return CallableSpec(
        need_id=need_id,
        access_mode="python_lib",
        module="fmpsdk",
        method="economic_indicator",
        instance_factory=_API_CLIENT,
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

_STOCK_QUOTE = CallableSpec(
    need_id="stock_quote",
    access_mode="python_lib",
    module="fmpsdk",
    method="quote",  # TODO(verify): confirm method name in fmpsdk
    instance_factory=_API_CLIENT,
    param_bindings={"ticker": ParamBinding(to_arg="symbol")},
    constants={},
    result_path=(),
    shape="dict",
)

_SOCIAL_POSTS = CallableSpec(
    need_id="social_posts",
    access_mode="python_lib",
    module="fmpsdk",
    method="historical_social_sentiment",  # TODO(verify): confirm method name in fmpsdk
    instance_factory=_API_CLIENT,
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
        CliMcpRecipe(
            kind="cli_mcp",
            argv=("uvx", "fmp-mcp"),
            env_keys=("FMP_API_KEY",),
        ),
        PythonLibRecipe(
            kind="python_lib",
            pip_name="fmpsdk",
            pip_version=">=20240101",
            import_module="fmpsdk",
            instance_factory_cls="fmpsdk",
            instance_factory_args=(("apikey", _API_KEY_PLACEHOLDER),),
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
