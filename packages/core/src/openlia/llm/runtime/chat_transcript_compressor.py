"""Deterministic compression of a chat-message transcript for inclusion
in a revision editor request.

User and assistant text content is kept verbatim. Tool calls become
one-line summaries showing the tool name + arg keys. Tool results become
size-suffix summaries (no payload bodies). Oldest content is trimmed
first when the cap is exceeded; a marker is inserted.
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_CAP_CHARS = 30_000


def _format_tool_call(call: dict[str, Any]) -> str:
    name = (call.get("function") or {}).get("name", "?")
    raw_args = (call.get("function") or {}).get("arguments", "{}")
    try:
        parsed = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
    except json.JSONDecodeError:
        parsed = {}
    args_summary = ", ".join(f"{k}={parsed[k]!r}" for k in list(parsed.keys())[:4])
    return f"[tool_call] {name}({args_summary})"


def _format_tool_result(content: str) -> str:
    chars = len(content or "")
    head = (content or "").strip().split("\n", 1)[0][:80]
    return f"[tool_result] {chars} chars: {head}"


def _format_message(msg: dict[str, Any]) -> str:
    role = msg.get("role", "?")
    content = msg.get("content", "") or ""
    tool_calls = msg.get("tool_calls") or []
    if role == "tool":
        return _format_tool_result(content)
    if role == "assistant" and tool_calls:
        lines = [_format_tool_call(tc) for tc in tool_calls]
        if content.strip():
            lines.append(f"assistant: {content}")
        return "\n".join(lines)
    return f"{role}: {content}"


def compress_chat_transcript(
    messages: list[dict[str, Any]],
    *,
    cap_chars: int = DEFAULT_CAP_CHARS,
) -> str:
    """Compress messages into a string under ``cap_chars``. Oldest
    content is trimmed first; a marker is inserted when trimming occurs."""
    if not messages:
        return ""
    formatted = [_format_message(m) for m in messages]
    joined = "\n\n".join(formatted)
    if len(joined) <= cap_chars:
        return joined
    # Trim from the front, leaving a marker.
    marker = "[... earlier discussion trimmed ...]\n\n"
    available = cap_chars - len(marker)
    # Build from the END so most-recent content is kept.
    out_parts: list[str] = []
    running = 0
    for chunk in reversed(formatted):
        size = len(chunk) + 2  # +2 for "\n\n" separator
        if running + size > available:
            break
        out_parts.append(chunk)
        running += size
    out_parts.reverse()
    return marker + "\n\n".join(out_parts)
