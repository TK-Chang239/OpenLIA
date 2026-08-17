"""Tests for the template-ingest service (PR 10)."""

from __future__ import annotations

import os
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
    # Point OPENLIA_TEST_DOCX at any .docx to exercise the mammoth conversion
    # path; skipped when unset so the suite stays hermetic and free of any
    # machine-specific path.
    docx_env = os.environ.get("OPENLIA_TEST_DOCX")
    if not docx_env:
        pytest.skip("set OPENLIA_TEST_DOCX to a .docx path to run this test")
    docx_path = Path(docx_env)
    if not docx_path.exists():
        pytest.skip("OPENLIA_TEST_DOCX points at a missing file")
    blob = docx_path.read_bytes()

    out = ingest_document(
        blob,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert isinstance(out, str)
    assert len(out) > 0


def test_unsupported_mime_raises() -> None:
    with pytest.raises(UnsupportedDocumentError, match="unsupported mime type"):
        ingest_document(b"x", mime="application/pdf")
