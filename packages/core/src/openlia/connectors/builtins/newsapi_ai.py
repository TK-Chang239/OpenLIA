"""NewsAPI.ai (Event Registry) built-in connector template.

Source: https://github.com/EventRegistry/event-registry-python (pip: `eventregistry`)

Covers the macro_research `geopolitical_news` runner need via a Python-lib
mode. Event Registry's QueryArticlesIter takes keywords and date range and
returns a list of article dicts.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    PythonLibRecipe,
)
from openlia.connectors.types import (
    CallableSpec,
    Category,
    InstanceFactory,
    ParamBinding,
)

_API_KEY_PLACEHOLDER = "$NEWSAPI_AI_API_KEY"
_ER_CLIENT = InstanceFactory(cls="EventRegistry", args={"apiKey": _API_KEY_PLACEHOLDER})

_GEOPOLITICAL_NEWS = CallableSpec(
    need_id="geopolitical_news",
    access_mode="python_lib",
    module="eventregistry",
    method="EventRegistry.execQuery",
    instance_factory=_ER_CLIENT,
    param_bindings={
        "keywords": ParamBinding(to_arg="keywords"),
        "since_iso": ParamBinding(to_arg="dateStart"),
    },
    constants={"lang": "eng"},
    result_path=(),
    shape="list[dict]",
)


NEWSAPI_AI_TEMPLATE = BuiltInTemplate(
    template_id="newsapi_ai",
    display_name="NewsAPI.ai (Event Registry)",
    category=Category.NEWS,
    api_key_env_var="NEWSAPI_AI_API_KEY",
    available_modes=(
        PythonLibRecipe(
            kind="python_lib",
            pip_name="eventregistry",
            pip_version=">=9.0,<10.0",
            import_module="eventregistry",
            instance_factory_cls="EventRegistry",
            instance_factory_args=(("apiKey", _API_KEY_PLACEHOLDER),),
        ),
    ),
    canary_tool="execQuery",
    runner_specs=(_GEOPOLITICAL_NEWS,),
)
