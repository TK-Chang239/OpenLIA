"""Built-in connector template registry (v2 redesign).

Day-1 catalog is locked to empty per spec §13.5; this module ships the
shape (types + lookups) so downstream code can compile against it.
"""

from __future__ import annotations

from openlia.connectors.builtins._registry import (
    BUILTIN_TEMPLATES,
    get_template,
    list_templates,
)
from openlia.connectors.builtins.types import (
    BuiltInTemplate,
    CliMcpRecipe,
    ModeRecipe,
    PythonLibRecipe,
    RemoteMcpRecipe,
)

__all__ = [
    "BUILTIN_TEMPLATES",
    "BuiltInTemplate",
    "CliMcpRecipe",
    "ModeRecipe",
    "PythonLibRecipe",
    "RemoteMcpRecipe",
    "get_template",
    "list_templates",
]
