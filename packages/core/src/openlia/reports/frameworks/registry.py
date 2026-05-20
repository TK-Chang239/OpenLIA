"""Template registry — maps template IDs to TemplateSpec loaders.

The registry is intentionally thin: register a loader callable under a template
ID; `get` invokes the loader and returns the resulting `TemplateSpec`. Loaders
are deferred so importing the registry doesn't force loading every template's
resources eagerly.

The default registry instance ships with the equity-research `stock_initiation`
template pre-registered (wired up in `loaders.stock_initiation`).
"""

from __future__ import annotations

from collections.abc import Callable

from openlia.reports.frameworks.template_spec import TemplateSpec

TemplateLoader = Callable[[], TemplateSpec]


class UnknownTemplateError(KeyError):
    """Raised when `TemplateRegistry.get` is called with an unregistered template ID."""


class TemplateRegistry:
    def __init__(self) -> None:
        self._loaders: dict[str, TemplateLoader] = {}

    def register(self, template_id: str, loader: TemplateLoader) -> None:
        if template_id in self._loaders:
            raise ValueError(f"template {template_id!r} is already registered")
        self._loaders[template_id] = loader

    def get(self, template_id: str) -> TemplateSpec:
        loader = self._loaders.get(template_id)
        if loader is None:
            raise UnknownTemplateError(template_id)
        return loader()

    def list_template_ids(self) -> tuple[str, ...]:
        return tuple(self._loaders.keys())


default_registry = TemplateRegistry()
