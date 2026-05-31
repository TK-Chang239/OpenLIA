"""Tests for v3 source-document attachment preparation.

``prepare_v3_attachments`` persists upload bytes to the shared storage
backend, extracts text where applicable, and returns core ``Attachment``
objects for ``RunRequest.attachments`` — without touching the
chat_attachments table (v3 stays independent of the chat schema).
"""

from __future__ import annotations

from pathlib import Path

from openlia.llm.runtime.messages import Attachment
from openlia_server.services.attachments import FileUpload
from openlia_server.services.v3_attachments import prepare_v3_attachments


def test_prepare_v3_attachments_persists_and_extracts_text(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path / "att"))
    uploads = [
        FileUpload(
            filename="notes.txt",
            mime_type="text/plain",
            content=b"SECRET MARKER 42",
        )
    ]
    out = prepare_v3_attachments(uploads)
    assert len(out) == 1
    att = out[0]
    assert isinstance(att, Attachment)
    assert att.filename == "notes.txt"
    assert att.mime_type == "text/plain"
    assert att.size_bytes == len(b"SECRET MARKER 42")
    # Text was extracted server-side.
    assert att.extracted_text == "SECRET MARKER 42"
    # Bytes landed on disk at the returned storage_path.
    assert Path(att.storage_path).read_bytes() == b"SECRET MARKER 42"


def test_prepare_v3_attachments_preserves_order_and_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path / "att"))
    uploads = [
        FileUpload(filename="a.txt", mime_type="text/plain", content=b"alpha"),
        FileUpload(filename="b.txt", mime_type="text/plain", content=b"beta"),
    ]
    out = prepare_v3_attachments(uploads)
    assert [a.filename for a in out] == ["a.txt", "b.txt"]
    # Distinct ids per attachment.
    assert out[0].id != out[1].id


def test_prepare_v3_attachments_leaves_image_text_none(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path / "att"))
    uploads = [FileUpload(filename="chart.png", mime_type="image/png", content=b"\x89PNG\r\n")]
    out = prepare_v3_attachments(uploads)
    # Images are not text-extracted; the runtime reads raw bytes instead.
    assert out[0].extracted_text is None
    assert Path(out[0].storage_path).read_bytes() == b"\x89PNG\r\n"
