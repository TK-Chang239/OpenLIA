"""ToolRegistry — backend-agnostic registry of callable tools.

Phase-scoped tool availability is a registry view, not a dispatcher branch.
`available_for(section_id, template)` returns the subset of tools the active
template exposes to the named section.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openlia.llm.runtime.report_v2.tools.protocol import ToolHandler

if TYPE_CHECKING:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, handler: ToolHandler) -> None:
        if handler.name in self._handlers:
            raise ValueError(f"tool {handler.name!r} is already registered")
        self._handlers[handler.name] = handler

    def get(self, name: str) -> ToolHandler:
        if name not in self._handlers:
            raise KeyError(name)
        return self._handlers[name]

    def all(self) -> tuple[ToolHandler, ...]:
        return tuple(self._handlers.values())

    def available_for(
        self,
        section_id: str,
        template: TemplateSpec | None,
    ) -> tuple[ToolHandler, ...]:
        """Return the tools the named section may call.

        Filtering: when the section declares non-empty `lazy_helpers`, only
        those are exposed. Otherwise every registered tool is exposed.
        Helpers declared in `eager_helpers` are always suppressed — they're
        pre-computed into the facts pack (partition invariant).
        """
        if template is None:
            return self.all()
        section: SectionSpec | None = template.section_by_id(section_id)
        if section is None:
            return self.all()
        eager = set(section.eager_helpers)
        if section.lazy_helpers:
            allowed = set(section.lazy_helpers) - eager
            return tuple(h for h in self._handlers.values() if h.name in allowed)
        return tuple(h for h in self._handlers.values() if h.name not in eager)


default_tool_registry = ToolRegistry()
