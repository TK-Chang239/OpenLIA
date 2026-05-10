"""Phase 7 — provider adapters render neutral content blocks.

Each provider has its own message-content shape: Anthropic uses typed blocks,
OpenAI/OpenRouter use ``image_url``, Gemini uses ``inline_data``, Ollama and
OpenAI-compat default profiles handle text-only.

These tests exercise the pure renderers directly (no HTTP) since the goal is
to verify the *shape* produced for each provider given a set of neutral
blocks. Each renderer must:
  - Wrap the original ``content`` text as a text block / first part.
  - Translate each ``ContentBlock`` to the provider's native shape.
  - Be safe to call when ``content_blocks`` is empty (must reduce to today's
    ``[{"role": ..., "content": "..."}]`` shape so existing requests don't
    change).
"""

from __future__ import annotations

import base64

from openlia.llm.adapters._content import (
    render_anthropic_messages,
    render_gemini_contents,
    render_ollama_messages,
    render_openai_messages,
)
from openlia.llm.runtime.messages import DocumentBlock, ImageBlock, TextBlock
from openlia.llm.types import Message


def _user(text: str, blocks: tuple = ()) -> Message:
    return Message(role="user", content=text, content_blocks=blocks)


# ─── Backward compatibility: empty blocks ────────────────────────────────────


def test_anthropic_renderer_no_blocks_matches_legacy_shape() -> None:
    msgs = [_user("hello")]
    out = render_anthropic_messages(msgs)
    assert out == [{"role": "user", "content": "hello"}]


def test_openai_renderer_no_blocks_matches_legacy_shape() -> None:
    msgs = [_user("hello")]
    out = render_openai_messages(msgs)
    assert out == [{"role": "user", "content": "hello"}]


def test_gemini_renderer_no_blocks_matches_legacy_shape() -> None:
    msgs = [_user("hello")]
    out = render_gemini_contents(msgs)
    assert out == [{"role": "user", "parts": [{"text": "hello"}]}]


def test_ollama_renderer_no_blocks_matches_legacy_shape() -> None:
    msgs = [_user("hello")]
    out = render_ollama_messages(msgs)
    assert out == [{"role": "user", "content": "hello"}]


# ─── Anthropic: text, image, document ────────────────────────────────────────


def test_anthropic_renders_text_block_appended_to_user_text() -> None:
    msgs = [
        _user(
            "see attached",
            blocks=(TextBlock(text="extracted notes", source_filename="notes.txt"),),
        )
    ]
    out = render_anthropic_messages(msgs)
    assert len(out) == 1
    content = out[0]["content"]
    assert isinstance(content, list)
    types = [b["type"] for b in content]
    assert types == ["text", "text"]
    assert content[0]["text"] == "see attached"
    assert "extracted notes" in content[1]["text"]
    assert "notes.txt" in content[1]["text"]


def test_anthropic_renders_image_block_as_base64_image() -> None:
    img = b"\x89PNG fake"
    msgs = [
        _user(
            "look", blocks=(ImageBlock(data=img, mime_type="image/png", source_filename="x.png"),)
        )
    ]
    out = render_anthropic_messages(msgs)
    content = out[0]["content"]
    image_parts = [b for b in content if b["type"] == "image"]
    assert len(image_parts) == 1
    src = image_parts[0]["source"]
    assert src["type"] == "base64"
    assert src["media_type"] == "image/png"
    assert src["data"] == base64.standard_b64encode(img).decode()


def test_anthropic_renders_document_block_as_base64_document() -> None:
    pdf = b"%PDF-1.4 ..."
    msgs = [
        _user(
            "summarize",
            blocks=(DocumentBlock(data=pdf, mime_type="application/pdf", source_filename="r.pdf"),),
        )
    ]
    out = render_anthropic_messages(msgs)
    content = out[0]["content"]
    doc_parts = [b for b in content if b["type"] == "document"]
    assert len(doc_parts) == 1
    src = doc_parts[0]["source"]
    assert src["type"] == "base64"
    assert src["media_type"] == "application/pdf"
    assert src["data"] == base64.standard_b64encode(pdf).decode()


# ─── OpenAI / OpenRouter (OpenAI-style chat completions) ─────────────────────


def test_openai_renders_text_block_appended_as_extra_text_part() -> None:
    msgs = [
        _user(
            "context follows",
            blocks=(TextBlock(text="line A\nline B", source_filename="a.txt"),),
        )
    ]
    out = render_openai_messages(msgs)
    parts = out[0]["content"]
    assert isinstance(parts, list)
    assert parts[0] == {"type": "text", "text": "context follows"}
    assert parts[1]["type"] == "text"
    assert "line A" in parts[1]["text"]
    assert "a.txt" in parts[1]["text"]


def test_openai_renders_image_block_as_image_url_data_uri() -> None:
    img = b"\x89PNG fake"
    msgs = [
        _user("?", blocks=(ImageBlock(data=img, mime_type="image/png", source_filename="x.png"),))
    ]
    out = render_openai_messages(msgs)
    parts = out[0]["content"]
    image_parts = [p for p in parts if p["type"] == "image_url"]
    assert len(image_parts) == 1
    url = image_parts[0]["image_url"]["url"]
    expected_b64 = base64.standard_b64encode(img).decode()
    assert url == f"data:image/png;base64,{expected_b64}"


# ─── Gemini ─────────────────────────────────────────────────────────────────


def test_gemini_renders_text_block_as_extra_text_part() -> None:
    msgs = [
        _user(
            "review",
            blocks=(TextBlock(text="extracted body", source_filename="m.docx"),),
        )
    ]
    out = render_gemini_contents(msgs)
    parts = out[0]["parts"]
    assert parts[0] == {"text": "review"}
    assert "extracted body" in parts[1]["text"]
    assert "m.docx" in parts[1]["text"]


def test_gemini_renders_image_block_as_inline_data() -> None:
    img = b"\x89PNG fake"
    msgs = [
        _user("?", blocks=(ImageBlock(data=img, mime_type="image/png", source_filename="x.png"),))
    ]
    out = render_gemini_contents(msgs)
    parts = out[0]["parts"]
    inline = [p for p in parts if "inline_data" in p]
    assert len(inline) == 1
    expected_b64 = base64.standard_b64encode(img).decode()
    assert inline[0]["inline_data"] == {"mime_type": "image/png", "data": expected_b64}


def test_gemini_renders_document_block_as_inline_data_pdf() -> None:
    pdf = b"%PDF-1.4 ..."
    msgs = [
        _user(
            "summarize",
            blocks=(DocumentBlock(data=pdf, mime_type="application/pdf", source_filename="r.pdf"),),
        )
    ]
    out = render_gemini_contents(msgs)
    parts = out[0]["parts"]
    inline = [p for p in parts if "inline_data" in p]
    assert len(inline) == 1
    assert inline[0]["inline_data"]["mime_type"] == "application/pdf"


# ─── Ollama (text-only path) ─────────────────────────────────────────────────


def test_ollama_renders_text_block_appended_to_message() -> None:
    msgs = [
        _user(
            "context",
            blocks=(TextBlock(text="extracted", source_filename="a.txt"),),
        )
    ]
    out = render_ollama_messages(msgs)
    # Single-string content with the extracted text appended (Ollama default
    # path doesn't speak multi-modal).
    assert isinstance(out[0]["content"], str)
    assert "context" in out[0]["content"]
    assert "extracted" in out[0]["content"]
    assert "a.txt" in out[0]["content"]


# ─── Multi-message conversations ─────────────────────────────────────────────


def test_anthropic_renders_assistant_and_tool_messages_unchanged() -> None:
    """Non-user messages keep their string content. Only user messages with
    blocks get the multi-modal treatment."""
    msgs = [
        Message(role="user", content="first turn"),
        Message(role="assistant", content="reply"),
        _user("now look", blocks=(TextBlock(text="more context"),)),
    ]
    out = render_anthropic_messages(msgs)
    assert out[0] == {"role": "user", "content": "first turn"}
    assert out[1] == {"role": "assistant", "content": "reply"}
    assert isinstance(out[2]["content"], list)


# ─── Inline-attachment banner: explicit delimiters + no-tool directive ───────
#
# Issue #99: a model treated `[Attached file: x.pdf]` as a path and called
# firecrawl__parse on it instead of reading inline content. Every text-block
# render must (a) carry an explicit BEGIN/END marker around the content, and
# (b) include a directive telling the model not to call tools to parse it.

_INLINE_DIRECTIVE_PHRASES = ("inline", "do not call")


def _assert_inline_banner(text_part_value: str, *, filename: str) -> None:
    assert "BEGIN ATTACHED FILE" in text_part_value
    assert "END ATTACHED FILE" in text_part_value
    assert filename in text_part_value
    lowered = text_part_value.lower()
    for phrase in _INLINE_DIRECTIVE_PHRASES:
        assert phrase in lowered, (
            f"expected directive phrase {phrase!r} in banner: {text_part_value[:200]!r}"
        )


def test_anthropic_text_block_uses_explicit_inline_banner() -> None:
    msgs = [
        _user(
            "ctx",
            blocks=(TextBlock(text="body", source_filename="r.pdf"),),
        )
    ]
    out = render_anthropic_messages(msgs)
    text_parts = [b for b in out[0]["content"] if b["type"] == "text"]
    # parts[0] is the user message, parts[1+] are attachment text
    _assert_inline_banner(text_parts[1]["text"], filename="r.pdf")


def test_openai_text_block_uses_explicit_inline_banner() -> None:
    msgs = [
        _user(
            "ctx",
            blocks=(TextBlock(text="body", source_filename="r.pdf"),),
        )
    ]
    out = render_openai_messages(msgs)
    parts = out[0]["content"]
    _assert_inline_banner(parts[1]["text"], filename="r.pdf")


def test_gemini_text_block_uses_explicit_inline_banner() -> None:
    msgs = [
        _user(
            "ctx",
            blocks=(TextBlock(text="body", source_filename="r.pdf"),),
        )
    ]
    out = render_gemini_contents(msgs)
    parts = out[0]["parts"]
    _assert_inline_banner(parts[1]["text"], filename="r.pdf")


def test_ollama_text_block_uses_explicit_inline_banner() -> None:
    msgs = [
        _user(
            "ctx",
            blocks=(TextBlock(text="body", source_filename="r.pdf"),),
        )
    ]
    out = render_ollama_messages(msgs)
    _assert_inline_banner(out[0]["content"], filename="r.pdf")
