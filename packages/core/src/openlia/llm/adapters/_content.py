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
    return out


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
    return out


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
