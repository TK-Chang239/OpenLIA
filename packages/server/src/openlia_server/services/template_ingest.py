"""Document ingest — converts uploaded files to plain markdown (PR 10).

The runtime never sees docx or txt directly. This service is the bridge:
mammoth handles docx → markdown (preserves headings + lists, drops styles),
markdown and text pass through. PR 11 takes the resulting markdown and
runs the mechanical boundary parser to produce a TemplateSpec.
"""

from __future__ import annotations

import io
from typing import Literal

import mammoth

SupportedMime = Literal[
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "text/markdown",
    "text/plain",
]


class UnsupportedDocumentError(ValueError):
    """Raised when the uploaded mime type is not in `SupportedMime`."""


def ingest_document(blob: bytes, mime: str) -> str:
    """Return plain markdown extracted from the uploaded document.

    docx is converted via `mammoth.convert_to_markdown`. Markdown and plain
    text pass through unchanged (text is wrapped so paragraph boundaries
    survive). Unknown mime types raise `UnsupportedDocumentError`.
    """
    if mime in ("text/markdown", "text/x-markdown"):
        return blob.decode("utf-8")
    if mime in ("text/plain",):
        # Plain text: pass through; the boundary parser will treat it as a
        # single section because there are no markdown headings.
        return blob.decode("utf-8")
    if mime == ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        result = mammoth.convert_to_markdown(io.BytesIO(blob))
        return result.value
    raise UnsupportedDocumentError(f"unsupported mime type: {mime}")
