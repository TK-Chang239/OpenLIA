"""Tests for the template-ingest service (PR 10)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia_server.services.template_ingest import (
    UnsupportedDocumentError,
    ingest_document,
)


def test_markdown_passes_through_unchanged() -> None:
    blob = b"# Heading\n\nBody text."

    out = ingest_document(blob, mime="text/markdown")

    assert out == "# Heading\n\nBody text."


def test_plain_text_passes_through_unchanged() -> None:
    blob = b"Just some text."

    out = ingest_document(blob, mime="text/plain")

    assert out == "Just some text."


def test_docx_converts_to_markdown_via_mammoth() -> None:
    # Use the Chinese 28-section sample that already exists on disk.
    docx_path = Path(
        "/Users/tkchang/Downloads/公司研究框架_v2_3_1_ProjectInstructions_Markdown版本.docx"
    )
    if not docx_path.exists():
        pytest.skip("sample docx not available in this environment")
    blob = docx_path.read_bytes()

    out = ingest_document(
        blob,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert isinstance(out, str)
    assert len(out) > 100
    # The framework's distinctive five-principles heading should survive
    assert "五大原則" in out or "公司深度研究框架" in out


def test_unsupported_mime_raises() -> None:
    with pytest.raises(UnsupportedDocumentError, match="unsupported mime type"):
        ingest_document(b"x", mime="application/pdf")
