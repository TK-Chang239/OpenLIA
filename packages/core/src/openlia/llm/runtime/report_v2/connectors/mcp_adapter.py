from __future__ import annotations

from openlia.llm.runtime.report_v2.connectors.base import ToolMeta, ToolResult


class MCPAdapter:
    def __init__(
        self,
        name: str,
        mcp_client: object,
        cacheable_tools: set[str] | None = None,
    ) -> None:
        self.name = name
        self.tool_kind = "mcp"
        self.cacheable = False  # per-call decided via tool meta
        self._client = mcp_client
        self._cacheable_tools = cacheable_tools or set()

    def list_tools(self) -> list[ToolMeta]:
        return [
            ToolMeta(
                name=t.name,
                description=t.description,
                cacheable=(t.name in self._cacheable_tools),
            )
            for t in self._client.list_tools()  # type: ignore[attr-defined]
        ]

    def call(self, tool: str, params: dict) -> ToolResult:
        result = self._client.invoke(tool, params)  # type: ignore[attr-defined]
        return ToolResult(
            content=result.payload,
            metadata=result.metadata,
            served_from_cache=False,
        )
