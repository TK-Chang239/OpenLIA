"""Tool-handler protocol, registry, and helper adapter (PR 8a).

`ToolHandler` is the backend-agnostic shape every callable tool implements —
local helpers in v1, uploaded-template helpers and in-section connectors in
later PRs. `ToolResult` carries citation metadata at result time so the
report's citation pool can absorb tool outputs uniformly whether they came
from a pre-computed Fact, a fresh web_search, or an uploaded helper.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.manifest import render_manifest
from openlia.llm.runtime.report_v2.tools.protocol import (
    ToolHandler,
    ToolResult,
)
from openlia.llm.runtime.report_v2.tools.registry import ToolRegistry, default_tool_registry

__all__ = [
    "ToolHandler",
    "ToolRegistry",
    "ToolResult",
    "default_tool_registry",
    "render_manifest",
]
