"""Web-search descriptor shim — re-exports from report_dash_mr.tools."""

from __future__ import annotations

from ...report_dash_mr.tools.web_search import (
    WEB_SEARCH_TOOL_NAME,
    build_web_search_descriptor,
)

__all__ = ["WEB_SEARCH_TOOL_NAME", "build_web_search_descriptor"]
