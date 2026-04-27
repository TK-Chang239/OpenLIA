"""EODHD built-in template — placeholder allowlist filled in Task C2."""

from __future__ import annotations

from openlia.connectors.builtins import register
from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.types import Category

register(
    BuiltInTemplate(
        template_id="eodhd",
        display_name="EODHD",
        category=Category.FINANCIAL,
        api_key_env_var="EODHD_API_KEY",
        cli_argv=("uvx", "eodhd-mcp-server"),
        canary_tool="get_user_details",
        shipped_allowlist=(
            ShippedAssignment(department_id="equity_research", tool_name="get_quote"),
        ),
    )
)
