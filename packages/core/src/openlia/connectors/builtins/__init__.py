"""Day-1 built-in catalog: EODHD, FMP, NewsAPI_ai.

See spec §12 for rationale and scope.
"""

from __future__ import annotations

from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.types import Category

# Tasks C2/C3/C4 fill these in with curated allowlists.
_REGISTRY: dict[str, BuiltInTemplate] = {}


def register(template: BuiltInTemplate) -> None:
    if template.template_id in _REGISTRY:
        raise ValueError(f"duplicate built-in: {template.template_id}")
    _REGISTRY[template.template_id] = template


def get_builtin(template_id: str) -> BuiltInTemplate:
    return _REGISTRY[template_id]


def list_builtins_for_category(category: Category) -> list[BuiltInTemplate]:
    return [t for t in _REGISTRY.values() if t.category is category]


def all_builtins() -> list[BuiltInTemplate]:
    return list(_REGISTRY.values())


# Side-effect imports that populate _REGISTRY.
from openlia.connectors.builtins import eodhd, fmp, newsapi_ai  # noqa: E402, F401

__all__ = [
    "BuiltInTemplate",
    "ShippedAssignment",
    "all_builtins",
    "get_builtin",
    "list_builtins_for_category",
    "register",
]
