"""X (Twitter) built-in connector template.

Sources:
- https://docs.x.com/xdks/python/overview (official Python SDK)
- PyPI: `xdk`

The previous template pointed at `https://mcp.x.ai/mcp` — that's xAI
(the Grok company), not X the social network. They are unrelated.

X exposes its API through a REST surface; the official SDK is `xdk`,
authenticated by a bearer token. We use the python_lib transport
through `openlia.data.x_wrapper.XClient`, a subclass of `xdk.Client`
that flattens the SDK's nested-resource methods (e.g.
`client.posts.search_recent`) into top-level methods discoverable by
`PythonLibTransport.list_tools`.

X is a chat-toolbox connector — `runner_specs=()` because it isn't
bound to any deterministic-runner need. Chat departments pick from
its tool surface at request time. Live-verified against api.x.com on
2026-05-01 with the user's bearer token.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    PythonLibRecipe,
)
from openlia.connectors.types import Category

_API_KEY_PLACEHOLDER = "$X_API_BEARER_TOKEN"

X_TEMPLATE = BuiltInTemplate(
    template_id="x",
    display_name="X",
    category=Category.SOCIAL,
    api_key_env_var="X_API_BEARER_TOKEN",
    available_modes=(
        PythonLibRecipe(
            kind="python_lib",
            pip_name="xdk",
            pip_version=">=0.9.0,<1.0.0",
            import_module="openlia.data.x_wrapper",
            instance_factory_cls="XClient",
            instance_factory_args=(("bearer_token", _API_KEY_PLACEHOLDER),),
        ),
    ),
    canary_tool="search_recent_posts",
    runner_specs=(),
)
