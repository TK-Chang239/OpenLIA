"""NewsAPI.ai (Event Registry) built-in connector template.

Sources:
- https://github.com/EventRegistry/event-registry-python (pip: `eventregistry`)
- https://newsapi.ai/

Covers macro_research's `geopolitical_news` need.

Event Registry's `EventRegistry.execQuery(query: QueryParamsBase)`
takes a constructed Query object (not kwargs), so the python_lib
transport can't call it directly. We import
`openlia.data.eventregistry_wrapper.EventRegistryWrapper` (subclass of
EventRegistry) which exposes a kwargs-only `geopolitical_news(window_days,
limit)` method. Live-verified against newsapi.ai with the user's API
key on 2026-05-01.
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
_ER_CLIENT = InstanceFactory(
    cls="EventRegistryWrapper",
    args={"apiKey": _API_KEY_PLACEHOLDER},
)

# EventRegistry article fields per their docs: title, url, source.title,
# dateTime (ISO-8601), body. The wrapper passes articles through verbatim,
# so field_map maps canonical keys to those source paths. Nested
# `source.title` is expressed via tuple form (executor walks dotted paths).
_GEOPOLITICAL_NEWS = CallableSpec(
    need_id="geopolitical_news",
    access_mode="python_lib",
    module="openlia.data.eventregistry_wrapper",
    method="EventRegistryWrapper.geopolitical_news",
    instance_factory=_ER_CLIENT,
    param_bindings={
        "window_days": ParamBinding(to_arg="window_days"),
        "limit": ParamBinding(to_arg="limit"),
    },
    constants={},
    result_path=(),
    shape="list[dict]",
    field_map={
        "title": "title",
        "url": "url",
        "source": ("source", "title"),
        "published_at": "dateTime",
        "summary": "body",
    },
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
            import_module="openlia.data.eventregistry_wrapper",
            instance_factory_cls="EventRegistryWrapper",
            instance_factory_args=(("apiKey", _API_KEY_PLACEHOLDER),),
        ),
    ),
    canary_tool="geopolitical_news",
    runner_specs=(_GEOPOLITICAL_NEWS,),
)
