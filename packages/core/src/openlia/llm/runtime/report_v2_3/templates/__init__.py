"""Template module — TemplateSpec schema + built-in instances."""

from .builtins import BUILTIN_TEMPLATES, get_builtin
from .spec import SectionSpec, TemplateSpec

__all__ = [
    "BUILTIN_TEMPLATES",
    "SectionSpec",
    "TemplateSpec",
    "get_builtin",
]
