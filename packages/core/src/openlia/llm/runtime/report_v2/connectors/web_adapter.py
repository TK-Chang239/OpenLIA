from __future__ import annotations

import httpx

from openlia.llm.runtime.report_v2.connectors.base import ToolMeta, ToolResult


class WebAdapter:
    def __init__(self, name: str = "web") -> None:
        self.name = name
        self.tool_kind = "web"
        self.cacheable = False

    def list_tools(self) -> list[ToolMeta]:
        return [
            ToolMeta(
                name="fetch",
                description="HTTP GET a URL and return text body",
                cacheable=False,
            )
        ]

    def call(self, tool: str, params: dict) -> ToolResult:
        if tool != "fetch":
            raise KeyError(f"web adapter has no tool {tool!r}")
        url = params["url"]
        r = httpx.get(url, timeout=params.get("timeout", 15.0))
        r.raise_for_status()
        return ToolResult(
            content=r.text,
            metadata={"status": r.status_code, "url": url},
            served_from_cache=False,
        )
