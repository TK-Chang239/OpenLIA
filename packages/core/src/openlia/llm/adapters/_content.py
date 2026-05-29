"""Provider-specific content-block renderers.

Each renderer takes a runtime ``Message`` list and produces the provider's
chat-completions ``messages`` (or ``contents``) array. When a user message
carries no ``content_blocks``, the renderer collapses to the legacy
``{"role": ..., "content": <str>}`` shape so existing requests are unchanged.

The runtime guarantees that any ``content_blocks`` it emits are already valid
for the active model's capabilities — adapters do not re-validate. See
``planning/specs/systems/composer-attachments-design.md``.
"""

from __future__ import annotations

import base64
from typing import Any

from openlia.llm.runtime.messages import DocumentBlock, ImageBlock, TextBlock
from openlia.llm.types import Message

# Prompt-cache breakpoint marker. Embedded in the rendered system prompt by
# shared/cache_breakpoint.yaml.j2 between the static prefix (cacheable across
# turns) and the per-turn dynamic suffix (memory_block, exemplars_block,
# anything else that varies). Adapters that support prompt caching split on
# this marker; adapters that don't strip it so the model never sees it.
CACHE_BREAKPOINT_MARKER = "<!-- OPENLIA_CACHE_BREAKPOINT -->"


def split_at_cache_breakpoint(system: str | None) -> tuple[str, str | None]:
    """Split a system prompt at the cache breakpoint marker.

    Returns (static_prefix, dynamic_suffix). dynamic_suffix is None when the
    marker is absent so the adapter can skip the multi-block code path.
    """
    if not system:
        return "", None
    if CACHE_BREAKPOINT_MARKER not in system:
        return system, None
    static, dynamic = system.split(CACHE_BREAKPOINT_MARKER, 1)
    return static.strip(), dynamic.strip()


def strip_cache_breakpoint(system: str | None) -> str | None:
    """Remove the cache breakpoint marker entirely.

    Used by adapters that don't support prompt caching. The marker is a
    line-comment so leaking it would be cosmetically ugly but not breaking;
    we still strip for cleanliness and to avoid the model ever pattern-
    matching on the sentinel.
    """
    if system is None:
        return None
    if CACHE_BREAKPOINT_MARKER not in system:
        return system
    return system.replace(CACHE_BREAKPOINT_MARKER, "").strip()


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode()


_INLINE_DIRECTIVE = (
    "The contents of this file are included inline below. "
    "Read them directly; do not call any tools to parse, fetch, or download "
    "this file."
)


def _wrap_inline_text(filename: str | None, body: str) -> str:
    """Wrap an extracted-text attachment in an unambiguous inline banner.

    Models were treating ``[Attached file: x.pdf]`` as a *path* and calling
    document-parser tools on it (issue #99). The explicit BEGIN/END markers
    plus the directive line make it clear the content is right there.
    """
    label = filename or "untitled"
    return (
        f"<<<BEGIN ATTACHED FILE: {label}>>>\n"
        f"{_INLINE_DIRECTIVE}\n"
        f"{body}\n"
        f"<<<END ATTACHED FILE: {label}>>>"
    )


# ─── Anthropic ──────────────────────────────────────────────────────────────


def render_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # Anthropic packs all tool_result blocks from one assistant turn into
    # a single follow-up user message — we coalesce consecutive
    # role="tool" messages here.
    pending_tool_results: list[dict[str, Any]] = []

    def flush_tool_results() -> None:
        if pending_tool_results:
            out.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for m in messages:
        if m.role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content,
                }
            )
            continue

        flush_tool_results()

        if m.role == "assistant" and m.tool_calls:
            content_blocks: list[dict[str, Any]] = []
            if m.content:
                content_blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments or {},
                    }
                )
            out.append({"role": "assistant", "content": content_blocks})
            continue

        blocks = tuple(getattr(m, "content_blocks", ()) or ())
        if m.role != "user" or not blocks:
            out.append({"role": m.role, "content": m.content})
            continue
        parts: list[dict[str, Any]] = [{"type": "text", "text": m.content}]
        for b in blocks:
            if isinstance(b, TextBlock):
                parts.append(
                    {
                        "type": "text",
                        "text": _wrap_inline_text(b.source_filename, b.text),
                    }
                )
            elif isinstance(b, ImageBlock):
                parts.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": b.mime_type,
                            "data": _b64(b.data),
                        },
                    }
                )
            elif isinstance(b, DocumentBlock):
                parts.append(
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": b.mime_type,
                            "data": _b64(b.data),
                        },
                    }
                )
        out.append({"role": m.role, "content": parts})

    flush_tool_results()
    return _coalesce_anthropic_user_turns(out)


def _coalesce_anthropic_user_turns(
    out: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge adjacent user-role turns into one.

    Anthropic requires user/assistant turns to alternate, so two
    consecutive user messages (e.g. a tool-result turn immediately
    followed by a runtime-injected user note) would 400. Normalize each
    user content to a block list and concatenate."""
    merged: list[dict[str, Any]] = []
    for entry in out:
        if merged and entry["role"] == "user" and merged[-1]["role"] == "user":
            merged[-1] = {
                "role": "user",
                "content": _as_anthropic_blocks(merged[-1]["content"])
                + _as_anthropic_blocks(entry["content"]),
            }
        else:
            merged.append(entry)
    return merged


def _as_anthropic_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return list(content)


# ─── OpenAI / OpenRouter (OpenAI-style chat completions) ────────────────────


def render_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        blocks = tuple(getattr(m, "content_blocks", ()) or ())
        if m.role != "user" or not blocks:
            out.append({"role": m.role, "content": m.content})
            continue
        parts: list[dict[str, Any]] = [{"type": "text", "text": m.content}]
        for b in blocks:
            if isinstance(b, TextBlock):
                parts.append(
                    {
                        "type": "text",
                        "text": _wrap_inline_text(b.source_filename, b.text),
                    }
                )
            elif isinstance(b, ImageBlock):
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{b.mime_type};base64,{_b64(b.data)}",
                        },
                    }
                )
            # OpenAI Chat Completions has no native PDF input; runtime should
            # have extracted to TextBlock already. If a DocumentBlock somehow
            # reaches here, embed it as base64 text so nothing is silently lost.
            elif isinstance(b, DocumentBlock):
                parts.append(
                    {
                        "type": "text",
                        "text": _wrap_inline_text(
                            b.source_filename,
                            f"[Document content not natively supported by this provider; "
                            f"raw bytes omitted. mime={b.mime_type}]",
                        ),
                    }
                )
        out.append({"role": m.role, "content": parts})
    return out


# ─── Gemini ─────────────────────────────────────────────────────────────────


def render_gemini_contents(messages: list[Message]) -> list[dict[str, Any]]:
    """Gemini calls its top-level field ``contents`` (not ``messages``) and
    its parts ``parts``. Gemini's ``contents`` API accepts only ``user``
    and ``model`` — anything else (``system``, ``tool``) must collapse to
    ``user``, since system prompts are passed out-of-band via
    ``systemInstruction`` and tool results are inlined as a follow-up
    user turn. Returning a literal ``role=tool`` would 400 the request."""
    out: list[dict[str, Any]] = []
    for m in messages:
        blocks = tuple(getattr(m, "content_blocks", ()) or ())
        role = "model" if m.role == "assistant" else "user"
        parts: list[dict[str, Any]] = [{"text": m.content}]
        for b in blocks:
            if isinstance(b, TextBlock):
                parts.append({"text": _wrap_inline_text(b.source_filename, b.text)})
            elif isinstance(b, (ImageBlock, DocumentBlock)):
                parts.append({"inline_data": {"mime_type": b.mime_type, "data": _b64(b.data)}})
        out.append({"role": role, "parts": parts})
    return _coalesce_gemini_user_turns(out)


def _coalesce_gemini_user_turns(
    out: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge adjacent user-role turns. Gemini's ``contents`` must
    alternate user/model — tool results already map to ``user``, so a
    following injected user turn would otherwise produce two adjacent
    user entries and 400 the request."""
    merged: list[dict[str, Any]] = []
    for entry in out:
        if merged and entry["role"] == "user" and merged[-1]["role"] == "user":
            merged[-1] = {
                "role": "user",
                "parts": list(merged[-1]["parts"]) + list(entry["parts"]),
            }
        else:
            merged.append(entry)
    return merged


# ─── Ollama (text-only path) ────────────────────────────────────────────────


def render_ollama_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Ollama default path is text-only. The runtime won't emit non-text
    blocks for an Ollama target (vision/pdf_native default to False), but
    if a TextBlock is present we inline it into the user content."""
    out: list[dict[str, Any]] = []
    for m in messages:
        blocks = tuple(getattr(m, "content_blocks", ()) or ())
        if m.role != "user" or not blocks:
            out.append({"role": m.role, "content": m.content})
            continue
        chunks = [m.content]
        for b in blocks:
            if isinstance(b, TextBlock):
                chunks.append("\n\n" + _wrap_inline_text(b.source_filename, b.text))
        out.append({"role": m.role, "content": "".join(chunks)})
    return out
