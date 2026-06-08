"""Mediastack built-in connector template.

Source: in-repo `openlia.data.mediastack.MediastackClient` wrapping the
public Mediastack REST API at `api.mediastack.com`. Mediastack ships no
official MCP server and no official Python SDK, so OpenLIA carries a tiny
HTTP wrapper alongside the template.

No deterministic runner specs — the previous MR geopolitical_news need
was removed.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    PythonLibRecipe,
)
from openlia.connectors.types import Category

_API_KEY_PLACEHOLDER = "$MEDIASTACK_API_KEY"


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
)
