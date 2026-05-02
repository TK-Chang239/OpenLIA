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
from collections.abc import Callable
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
        tool_call_listener: Callable[[ToolCall], None] | None = None,
        grounding_paths: list[str] | None = None,
    ) -> None:
        self._provider = provider
        self._connector_root = connector_root
        self._max_turns = max_turns
        self._tool_call_listener = tool_call_listener
        self._grounding_paths = grounding_paths or None

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        conversation: list[Message] = [Message(role="user", content=prompt)]
        tools = self._tool_schemas() if self._connector_root is not None else None
        # `response_format=json_object` is incompatible with tool_use on most
        # providers (OpenAI/OpenRouter reject the second turn). Only bind it
        # when we're running single-shot.
        response_format = ResponseFormat(kind="json_object") if tools is None else None

        for _ in range(self._max_turns):
            response = await self._provider.generate(
                LLMRequest(
                    messages=conversation,
                    system=(
                        "Return ONLY a JSON object as your final answer. "
                        "When the inventory doesn't expose enum slugs "
                        "directly, use the filesystem tools to read the "
                        "provider's source before choosing constants.\n\n"
                        "STRICT RULE 1 (verbatim): every string constant "
                        "must be copied VERBATIM from a literal you saw in "
                        "the source code (e.g. an item in a set/list/dict "
                        "the server uses to validate input). Do not "
                        "paraphrase, rename, qualify, or merge terms from "
                        "documentation. If a slug appears only in prose, "
                        "comments, or a docstring -- not in a validator "
                        "collection -- it is NOT acceptable.\n\n"
                        "STRICT RULE 2 (semantic match): the slug must "
                        "mean the SAME METRIC as the need, not just be "
                        "thematically related. 'Same theme' is NOT a "
                        "match. Examples that are NOT matches:\n"
                        "  - need 'PMI' vs slug 'gdp_current_usd' (both "
                        "macro indicators, but PMI != GDP)\n"
                        "  - need 'core CPI' vs slug 'consumer_price_"
                        "index' (CPI is not core CPI)\n"
                        "  - need 'central bank gold purchases' vs slug "
                        "'gdp_current_usd' (different metric entirely)\n"
                        "Before choosing a slug, state in your reasoning: "
                        "(a) the metric the need is asking for in plain "
                        "language, (b) the candidate slug, (c) why they "
                        "denote the same metric (not just the same "
                        "topic). If you cannot make that case honestly, "
                        "the need is unsatisfiable.\n\n"
                        "STRICT RULE 3 (default to unsatisfiable): when "
                        "the validator collection contains nothing whose "
                        "meaning is the requested metric, return "
                        '{"unsatisfiable": true, "reason": "<short '
                        'explanation naming the missing metric>"} '
                        "instead of picking the closest-themed slug. A "
                        "real provider gap is normal and expected; "
                        "guessing is worse than admitting it."
                    ),
                    tools=tools,
                    response_format=response_format,
                    max_tokens=2048,
                    temperature=0.0,
                )
            )
            if not response.tool_calls:
                return self._parse_final(response.text)

            # Replay the assistant turn that emitted the tool calls so the
            # next request preserves the protocol-required pairing.
            conversation.append(
                Message(
                    role="assistant",
                    content=response.text or "",
                    tool_calls=tuple(response.tool_calls),
                )
            )
            for call in response.tool_calls:
                if self._tool_call_listener is not None:
                    try:
                        self._tool_call_listener(call)
                    except Exception:
                        # Listeners are observability — never break the loop.
                        pass
                payload = self._dispatch(call)
                conversation.append(
                    Message(
                        role="tool",
                        content=json.dumps(payload),
                        tool_call_id=call.id,
                    )
                )

        raise AgenticResolverError(
            f"agentic loop exceeded {self._max_turns} turns without final JSON"
        )

    def _parse_final(self, text: str) -> dict[str, Any]:
        cleaned = _strip_fence(text or "").strip()
        if not cleaned:
            raise AgenticResolverError("adapter LLM returned empty output")
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Tolerate trailing prose / multiple JSON values: take the first
            # JSON object via raw_decode.
            try:
                parsed, _ = json.JSONDecoder().raw_decode(cleaned)
            except json.JSONDecodeError as exc2:
                raise AgenticResolverError(f"adapter LLM returned non-JSON: {exc2}") from exc2
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
                return list_directory(
                    self._connector_root,
                    call.arguments["path"],
                    grounding_paths=self._grounding_paths,
                )
            if call.name == "read_file":
                return read_file(
                    self._connector_root,
                    call.arguments["path"],
                    grounding_paths=self._grounding_paths,
                )
            if call.name == "search_files":
                return search_files(
                    self._connector_root,
                    pattern=call.arguments["pattern"],
                    glob=call.arguments.get("glob", "**/*"),
                    grounding_paths=self._grounding_paths,
                )
            return {"error": f"unknown tool: {call.name!r}"}
        except ResolverToolError as exc:
            return {"error": str(exc)}
        except KeyError as exc:
            return {"error": f"missing argument: {exc}"}
