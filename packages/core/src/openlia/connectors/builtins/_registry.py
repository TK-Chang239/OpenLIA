"""Built-in template registry.

Day-1 catalog locked to empty per spec §13.5. Templates ship in a later
phase, when each upstream MCP server's launch recipe is curated.
"""

from __future__ import annotations

from openlia.connectors.builtins.types import BuiltInTemplate

BUILTIN_TEMPLATES: tuple[BuiltInTemplate, ...] = ()


def get_template(template_id: str) -> BuiltInTemplate | None:
    return next((t for t in BUILTIN_TEMPLATES if t.template_id == template_id), None)


def list_templates() -> tuple[BuiltInTemplate, ...]:
    return BUILTIN_TEMPLATES
