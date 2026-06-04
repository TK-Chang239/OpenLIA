"""Retail Sentiment dashboard tool catalog.

Each module here exposes one or more ``ResearchTool`` factories.
``registry.py`` assembles the per-request catalog the runner dispatches
against. The engine has no tool discovery — the catalog is a fixed,
connector-gated set plus the output tools.
"""

from .registry import ToolCatalog, build_catalog
from .web_search import WEB_SEARCH_TOOL_NAME, build_web_search_descriptor

__all__ = [
    "WEB_SEARCH_TOOL_NAME",
    "ToolCatalog",
    "build_catalog",
    "build_web_search_descriptor",
]
