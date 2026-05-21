from __future__ import annotations

from collections.abc import Callable

from openlia.llm.runtime.report_v2.connectors.base import ToolMeta, ToolResult


class SDKAdapter:
    def __init__(
        self,
        name: str,
        tools: dict[str, Callable],
        cacheable_tools: set[str] | None = None,
    ) -> None:
        self.name = name
        self.tool_kind = "python_sdk"
        self.cacheable = False
        self._tools = tools
        self._cacheable_tools = cacheable_tools or set()

    def list_tools(self) -> list[ToolMeta]:
        return [
            ToolMeta(
                name=k,
                description=(f.__doc__ or "").strip().split("\n", 1)[0],
                cacheable=(k in self._cacheable_tools),
            )
            for k, f in self._tools.items()
        ]

    def call(self, tool: str, params: dict) -> ToolResult:
        if tool not in self._tools:
            raise KeyError(f"{self.name} has no tool {tool!r}")
        result = self._tools[tool](**params)
        return ToolResult(content=result, metadata={}, served_from_cache=False)
