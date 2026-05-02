"""Built-in template registry.

Day-1 catalog per docs/superpowers/specs/2026-05-01-builtin-connectors-design.md §2.
"""

from __future__ import annotations

from openlia.connectors.builtins.eodhd import EODHD_TEMPLATE
from openlia.connectors.builtins.firecrawl import FIRECRAWL_TEMPLATE
from openlia.connectors.builtins.fmp import FMP_TEMPLATE
from openlia.connectors.builtins.mediastack import MEDIASTACK_TEMPLATE
from openlia.connectors.builtins.newsapi_ai import NEWSAPI_AI_TEMPLATE
from openlia.connectors.builtins.types import BuiltInTemplate
from openlia.connectors.builtins.x import X_TEMPLATE

BUILTIN_TEMPLATES: tuple[BuiltInTemplate, ...] = (
    EODHD_TEMPLATE,
    FMP_TEMPLATE,
    NEWSAPI_AI_TEMPLATE,
    MEDIASTACK_TEMPLATE,
    FIRECRAWL_TEMPLATE,
    X_TEMPLATE,
)


def get_template(template_id: str) -> BuiltInTemplate | None:
    return next((t for t in BUILTIN_TEMPLATES if t.template_id == template_id), None)


def list_templates() -> tuple[BuiltInTemplate, ...]:
    return BUILTIN_TEMPLATES
