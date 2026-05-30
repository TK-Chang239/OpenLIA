"""Research-phase utilities for the v2.3 pipeline.

Owns the tool registry and supporting abstractions that the
LLM-backed researcher uses to gather facts with provenance attached
at fetch time. Stays free of provider SDK imports — concrete EODHD /
web adapters live in submodules so the runtime layer can depend on
them without dragging FastAPI or the openai SDK into the core.
"""

from .prune import prune_empty
from .registry import (
    NullToolExecutor,
    ToolExecutionError,
    build_eodhd_tools,
    build_research_tools,
    build_web_search_tool,
)
from .tools import ResearchTool, ToolDescriptor, ToolResult

__all__ = [
    "NullToolExecutor",
    "ResearchTool",
    "ToolDescriptor",
    "ToolExecutionError",
    "ToolResult",
    "build_eodhd_tools",
    "build_research_tools",
    "build_web_search_tool",
    "prune_empty",
]
