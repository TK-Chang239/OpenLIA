"""NewsAPI.ai (Event Registry) built-in connector template.

Sources:
- https://github.com/EventRegistry/event-registry-python (pip: `eventregistry`)
- https://newsapi.ai/

Available for chat departments via the python_lib transport. No
deterministic runner specs — the previous MR geopolitical_news need
was removed.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    PythonLibRecipe,
)
from openlia.connectors.types import Category

_API_KEY_PLACEHOLDER = "$NEWSAPI_AI_API_KEY"


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
)
