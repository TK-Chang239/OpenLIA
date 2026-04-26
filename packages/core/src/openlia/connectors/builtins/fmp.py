"""FMP built-in template — placeholder allowlist filled in Task C3."""

from __future__ import annotations

from openlia.connectors.builtins import register
from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.types import Category

register(
    BuiltInTemplate(
        template_id="fmp",
        display_name="Financial Modeling Prep",
        category=Category.FINANCIAL,
        api_key_env_var="FMP_API_KEY",
        cli_argv=("uvx", "fmp-mcp-server"),
        canary_tool="search",
        shipped_allowlist=(ShippedAssignment(department_id="equity_research", tool_name="quote"),),
    )
)
