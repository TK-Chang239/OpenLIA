"""Mediastack built-in connector template.

Source: in-repo `openlia.data.mediastack.MediastackClient` wrapping the
public Mediastack REST API at `api.mediastack.com`. Mediastack ships no
official MCP server and no official Python SDK, so OpenLIA carries a tiny
HTTP wrapper alongside the template.

Covers the macro_research `geopolitical_news` runner need.
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

_API_KEY_PLACEHOLDER = "$MEDIASTACK_API_KEY"
_CLIENT = InstanceFactory(cls="MediastackClient", args={"api_key": _API_KEY_PLACEHOLDER})


# Mediastack article fields per their docs: title, url, source, published_at
# (ISO-8601), description. The wrapper returns the `data` array verbatim, so
# canonical keys map directly to those source paths.
_GEOPOLITICAL_NEWS = CallableSpec(
    need_id="geopolitical_news",
    access_mode="python_lib",
    module="openlia.data.mediastack",
    method="MediastackClient.search",
    instance_factory=_CLIENT,
    param_bindings={
        "keywords": ParamBinding(to_arg="keywords"),
        "since_iso": ParamBinding(to_arg="since"),
    },
    constants={},
    result_path=(),
    shape="list[dict]",
    field_map={
        "title": "title",
        "url": "url",
        "source": "source",
        "published_at": "published_at",
        "summary": "description",
    },
)


MEDIASTACK_TEMPLATE = BuiltInTemplate(
    template_id="mediastack",
    display_name="Mediastack",
    category=Category.NEWS,
    api_key_env_var="MEDIASTACK_API_KEY",
    available_modes=(
        PythonLibRecipe(
            kind="python_lib",
            pip_name="openlia-core",
            pip_version="*",
            import_module="openlia.data.mediastack",
            instance_factory_cls="MediastackClient",
            instance_factory_args=(("api_key", _API_KEY_PLACEHOLDER),),
        ),
    ),
    canary_tool="search",
    runner_specs=(_GEOPOLITICAL_NEWS,),
)
