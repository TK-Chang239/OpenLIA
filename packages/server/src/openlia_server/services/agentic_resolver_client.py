"""Multi-turn tool-use resolver client.

Wraps an `LLMProvider` and runs a bounded tool-use loop. When the user
supplies a connector grounding repo, the LLM gets filesystem tools
(`list_directory`, `read_file`, `search_files`) over a sandboxed clone
and uses them to discover provider-specific enum slugs that the
plain `tools/list` payload doesn't expose. Without a clone, the loop
degenerates to single-shot JSON generation.

Implements the `LlmClient` Protocol used by the resolver
(`generate_json(*, prompt) -> dict`) so it's a drop-in replacement
for `AdapterLlmJsonClient` at the call site.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message, ResponseFormat, ToolCall, ToolSchema

from openlia_server.services.resolver_tools import (
    ResolverToolError,
    list_directory,
    read_file,
    search_files,
)


class AgenticResolverError(Exception):
    """Raised when the agentic loop cannot produce a valid JSON answer."""


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _strip_fence(text: str) -> str:
    match = _FENCE_RE.match(text.strip())
    return match.group(1).strip() if match else text.strip()


class AgenticResolverClient:
    """Tool-use loop with bounded turns; final answer is parsed JSON."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        connector_root: Path | None,
        max_turns: int = 10,
    ) -> None:
        self._provider = provider
        self._connector_root = connector_root
        self._max_turns = max_turns

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        conversation: list[Message] = [Message(role="user", content=prompt)]
        tools = self._tool_schemas() if self._connector_root is not None else None

        for _ in range(self._max_turns):
            response = await self._provider.generate(
                LLMRequest(
                    messages=conversation,
                    system="Return ONLY a JSON object. No prose, no fences.",
                    tools=tools,
                    response_format=ResponseFormat(kind="json_object"),
                    max_tokens=2048,
                    temperature=0.0,
                )
            )
            if not response.tool_calls:
                return self._parse_final(response.text)

            for call in response.tool_calls:
                payload = self._dispatch(call)
                conversation.append(
                    Message(
                        role="tool",
                        content=json.dumps({"call_id": call.id, "result": payload}),
                    )
                )

        raise AgenticResolverError(
            f"agentic loop exceeded {self._max_turns} turns without final JSON"
        )

    def _parse_final(self, text: str) -> dict[str, Any]:
        cleaned = _strip_fence(text or "")
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AgenticResolverError(f"adapter LLM returned non-JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise AgenticResolverError("adapter LLM returned a non-object JSON value")
        return parsed

    def _tool_schemas(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="list_directory",
                description=(
                    "List entries in a directory under the connector's "
                    "grounding repo. Returns [{name, type}]. type is "
                    "'file' or 'dir'."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to repo root.",
                        },
                    },
                    "required": ["path"],
                },
            ),
            ToolSchema(
                name="read_file",
                description=(
                    "Read a file from the connector's grounding repo. "
                    "Returns the contents (truncated at 200KB)."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path relative to repo root.",
                        },
                    },
                    "required": ["path"],
                },
            ),
            ToolSchema(
                name="search_files",
                description=(
                    "Regex-search files in the connector's grounding repo. "
                    "Returns [{path, line_number, line}]."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Python regex pattern.",
                        },
                        "glob": {
                            "type": "string",
                            "description": "File glob (default '**/*').",
                        },
                    },
                    "required": ["pattern"],
                },
            ),
        ]

    def _dispatch(self, call: ToolCall) -> Any:
        if self._connector_root is None:
            return {"error": "no grounding repo configured for this connector"}
        try:
            if call.name == "list_directory":
                return list_directory(self._connector_root, call.arguments["path"])
            if call.name == "read_file":
                return read_file(self._connector_root, call.arguments["path"])
            if call.name == "search_files":
                return search_files(
                    self._connector_root,
                    pattern=call.arguments["pattern"],
                    glob=call.arguments.get("glob", "**/*"),
                )
            return {"error": f"unknown tool: {call.name!r}"}
        except ResolverToolError as exc:
            return {"error": str(exc)}
        except KeyError as exc:
            return {"error": f"missing argument: {exc}"}
