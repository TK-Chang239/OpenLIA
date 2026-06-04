"""Firecrawl built-in connector template.

Sources:
- https://github.com/firecrawl/firecrawl-mcp-server (npm: firecrawl-mcp)
- https://docs.firecrawl.dev/sdks/python (PyPI: firecrawl-py)

MCP recipes expose firecrawl_search / firecrawl_scrape to chat departments.
No deterministic runner specs — all previous MR needs were removed.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    PythonLibRecipe,
    RemoteMcpRecipe,
)
from openlia.connectors.types import Category

FIRECRAWL_TEMPLATE = BuiltInTemplate(
    template_id="firecrawl",
    display_name="Firecrawl",
    category=Category.WEB_SEARCH,
    api_key_env_var="FIRECRAWL_API_KEY",
    available_modes=(
        PythonLibRecipe(
            kind="python_lib",
            pip_name="firecrawl-py",
            pip_version=">=4.0.0,<5.0.0",
            import_module="firecrawl",
            instance_factory_cls="Firecrawl",
            instance_factory_args=(("api_key", "$FIRECRAWL_API_KEY"),),
        ),
        RemoteMcpRecipe(
            kind="remote_mcp",
            url="https://mcp.firecrawl.dev/{FIRECRAWL_API_KEY}/v2/mcp",
            headers=(),
        ),
        CliMcpRecipe(
            kind="cli_mcp",
            argv=("npx", "-y", "firecrawl-mcp"),
            env_keys=("FIRECRAWL_API_KEY",),
        ),
    ),
    canary_tool="scrape",
)
