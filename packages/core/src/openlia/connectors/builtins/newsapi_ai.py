"""NewsAPI.ai built-in template — placeholder allowlist filled in Task C4."""

from __future__ import annotations

from openlia.connectors.builtins import register
from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.types import Category

register(
    BuiltInTemplate(
        template_id="newsapi_ai",
        display_name="NewsAPI.ai",
        category=Category.NEWS,
        api_key_env_var="NEWSAPI_AI_KEY",
        cli_argv=("uvx", "newsapi-ai-mcp"),
        canary_tool="get_api_usage",
        shipped_allowlist=(
            ShippedAssignment(department_id="equity_research", tool_name="search_articles"),
        ),
    )
)
