"""X (Twitter) built-in connector template.

Source: https://github.com/xai-org (xAI). Day-1 catalog ships this template
with no runner-need mappings; chat departments consume X tools through MCP
tool-use.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    RemoteMcpRecipe,
)
from openlia.connectors.types import Category

X_TEMPLATE = BuiltInTemplate(
    template_id="x",
    display_name="X",
    category=Category.SOCIAL,
    api_key_env_var="X_API_KEY",
    available_modes=(
        RemoteMcpRecipe(
            kind="remote_mcp",
            url="https://mcp.x.ai/mcp",
            headers=(("Authorization", "Bearer $X_API_KEY"),),
        ),
    ),
    canary_tool="search_tweets",
    runner_specs=(),
)
