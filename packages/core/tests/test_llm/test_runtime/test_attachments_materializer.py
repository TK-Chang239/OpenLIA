"""Phase 4 — runtime materializer.

Turns a list of ``Attachment``s into provider-neutral content blocks based on
mime type and the active model's capabilities. Strict-reject only when no
materialization path exists for the (mime x capabilities) pair (e.g. image
attached to a non-vision model). For text-extractable formats (PDF on
non-native providers, all Office docs), the runtime relies on extracted text
provided by the caller via ``extracted_text_cache``.

These tests stub the filesystem with ``tmp_path`` and call
``materialize_for_model`` through its public surface only — internals
(extension sniffing, MIME table) are not asserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia.llm.runtime.attachments import (
    AttachmentNotSupportedError,
    materialize_for_model,
)
from openlia.llm.runtime.messages import (
    Attachment,
    DocumentBlock,
    ImageBlock,
    TextBlock,
)
from openlia.llm.types import Capabilities

_VISION_NO_PDF = Capabilities(vision=True, pdf_native=False, max_context_tokens=200_000)
_NO_VISION_NO_PDF = Capabilities(vision=False, pdf_native=False, max_context_tokens=200_000)
_VISION_AND_PDF = Capabilities(vision=True, pdf_native=True, max_context_tokens=200_000)


def _store(tmp_path: Path, name: str, payload: bytes) -> Attachment:
    """Write ``payload`` to a file under ``tmp_path`` and wrap as an Attachment."""
    path = tmp_path / name
    path.write_bytes(payload)
    return Attachment(
        id=f"att-{name}",
        filename=name,
        mime_type=_mime_for(name),
        storage_path=str(path),
        size_bytes=len(payload),
    )


def _mime_for(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".zip": "application/zip",
    }[suffix]


# ─── Tracer bullet ────────────────────────────────────────────────────────────


def test_plain_text_file_becomes_a_text_block(tmp_path: Path) -> None:
    att = _store(tmp_path, "notes.txt", b"hello world")
    result = materialize_for_model([att], capabilities=_VISION_AND_PDF)

    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert isinstance(block, TextBlock)
    assert block.text == "hello world"
    assert block.source_filename == "notes.txt"
    assert result.warnings == []


# ─── Text-family formats ─────────────────────────────────────────────────────


def test_markdown_csv_json_all_decode_as_text(tmp_path: Path) -> None:
    md = _store(tmp_path, "doc.md", b"# title\n\nbody")
    csv = _store(tmp_path, "data.csv", b"a,b\n1,2\n")
    js = _store(tmp_path, "x.json", b'{"k": 1}')

    result = materialize_for_model([md, csv, js], capabilities=_VISION_AND_PDF)

    assert [b.text for b in result.blocks] == ["# title\n\nbody", "a,b\n1,2\n", '{"k": 1}']
    assert all(isinstance(b, TextBlock) for b in result.blocks)


# ─── Images ──────────────────────────────────────────────────────────────────


def test_image_with_vision_model_becomes_image_block(tmp_path: Path) -> None:
    att = _store(tmp_path, "chart.png", b"\x89PNG\r\n\x1a\n...")
    result = materialize_for_model([att], capabilities=_VISION_NO_PDF)

    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert isinstance(block, ImageBlock)
    assert block.data == b"\x89PNG\r\n\x1a\n..."
    assert block.mime_type == "image/png"
    assert block.source_filename == "chart.png"


def test_image_without_vision_model_raises(tmp_path: Path) -> None:
    att = _store(tmp_path, "chart.png", b"\x89PNG\r\n\x1a\n...")
    with pytest.raises(AttachmentNotSupportedError) as excinfo:
        materialize_for_model([att], capabilities=_NO_VISION_NO_PDF)

    msg = str(excinfo.value)
    assert "chart.png" in msg
    assert "vision" in msg.lower()


# ─── PDFs ────────────────────────────────────────────────────────────────────


def test_pdf_with_pdf_native_model_becomes_document_block(tmp_path: Path) -> None:
    att = _store(tmp_path, "filing.pdf", b"%PDF-1.4 ...payload...")
    result = materialize_for_model([att], capabilities=_VISION_AND_PDF)

    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert isinstance(block, DocumentBlock)
    assert block.data == b"%PDF-1.4 ...payload..."
    assert block.mime_type == "application/pdf"
    assert block.source_filename == "filing.pdf"


def test_pdf_without_pdf_native_uses_extracted_text(tmp_path: Path) -> None:
    """When the model can't take native PDFs, the runtime relies on
    pre-extracted text supplied via the cache."""
    att = _store(tmp_path, "filing.pdf", b"%PDF-1.4 ...irrelevant for non-native...")
    cache = {att.id: "Page 1 — extracted text body"}

    result = materialize_for_model([att], capabilities=_VISION_NO_PDF, extracted_text_cache=cache)

    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert isinstance(block, TextBlock)
    assert block.text == "Page 1 — extracted text body"
    assert block.source_filename == "filing.pdf"


def test_pdf_without_pdf_native_and_no_cache_warns_and_drops(tmp_path: Path) -> None:
    """If the runtime needs extracted text but it wasn't supplied, surface a
    warning and skip the attachment rather than send raw bytes the model
    cannot decode."""
    att = _store(tmp_path, "filing.pdf", b"%PDF-1.4 ...")
    result = materialize_for_model([att], capabilities=_VISION_NO_PDF)

    assert result.blocks == []
    assert any("filing.pdf" in w and "extracted" in w.lower() for w in result.warnings)


# ─── Office docs (always extract regardless of provider) ─────────────────────


def test_docx_uses_extracted_text(tmp_path: Path) -> None:
    att = _store(tmp_path, "memo.docx", b"PK\x03\x04...zip-format docx bytes...")
    cache = {att.id: "Memo body — bullet 1, bullet 2"}

    result = materialize_for_model([att], capabilities=_VISION_AND_PDF, extracted_text_cache=cache)

    assert len(result.blocks) == 1
    block = result.blocks[0]
    assert isinstance(block, TextBlock)
    assert block.text == "Memo body — bullet 1, bullet 2"
    assert block.source_filename == "memo.docx"


def test_xlsx_uses_extracted_text(tmp_path: Path) -> None:
    att = _store(tmp_path, "model.xlsx", b"PK\x03\x04...")
    cache = {att.id: "Sheet1: A1=foo, B1=bar"}

    result = materialize_for_model([att], capabilities=_VISION_AND_PDF, extracted_text_cache=cache)

    assert isinstance(result.blocks[0], TextBlock)
    assert result.blocks[0].text == "Sheet1: A1=foo, B1=bar"


def test_pptx_uses_extracted_text(tmp_path: Path) -> None:
    att = _store(tmp_path, "deck.pptx", b"PK\x03\x04...")
    cache = {att.id: "Slide 1: Title\nSlide 2: Body"}

    result = materialize_for_model([att], capabilities=_VISION_AND_PDF, extracted_text_cache=cache)

    assert isinstance(result.blocks[0], TextBlock)
    assert result.blocks[0].text.startswith("Slide 1:")


# ─── Disallowed types ────────────────────────────────────────────────────────


def test_unsupported_mime_raises(tmp_path: Path) -> None:
    att = _store(tmp_path, "secret.zip", b"PK\x03\x04...")
    with pytest.raises(AttachmentNotSupportedError):
        materialize_for_model([att], capabilities=_VISION_AND_PDF)


# ─── Multi-attachment ordering ───────────────────────────────────────────────


def test_multiple_attachments_emit_blocks_in_input_order(tmp_path: Path) -> None:
    txt = _store(tmp_path, "a.txt", b"A")
    img = _store(tmp_path, "b.png", b"\x89PNG B")
    pdf = _store(tmp_path, "c.pdf", b"%PDF C")

    result = materialize_for_model([txt, img, pdf], capabilities=_VISION_AND_PDF)

    assert [type(b).__name__ for b in result.blocks] == [
        "TextBlock",
        "ImageBlock",
        "DocumentBlock",
    ]
    assert [getattr(b, "source_filename", None) for b in result.blocks] == [
        "a.txt",
        "b.png",
        "c.pdf",
    ]


def test_empty_attachment_list_yields_empty_result() -> None:
    result = materialize_for_model([], capabilities=_VISION_AND_PDF)
    assert result.blocks == []
    assert result.warnings == []
