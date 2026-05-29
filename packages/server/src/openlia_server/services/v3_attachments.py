"""Prepare user-uploaded source documents for a v3 run.

The v3 engine takes attachments as core ``Attachment`` objects on the
``RunRequest``; the runner materializes them into multimodal content
blocks (native PDF/image where the model supports it, extracted text
otherwise). Unlike the chat path, v3 does NOT persist ``chat_attachments``
rows — it keeps the v3 engine independent of the chat tables. We still
reuse the shared storage backend (so bytes land on disk for the
background runner to read) and the shared text extractor.

Caller must run ``attachments.validate_uploads`` first; this does not
re-validate.
"""

from __future__ import annotations

import uuid

from openlia.llm.runtime.messages import Attachment

from openlia_server.services import attachment_storage
from openlia_server.services.attachments import FileUpload, extract_text


def prepare_v3_attachments(uploads: list[FileUpload]) -> list[Attachment]:
    """Persist bytes + extract text, returning core ``Attachment`` objects
    in upload order for ``RunRequest.attachments``."""
    out: list[Attachment] = []
    for u in uploads:
        storage_path = attachment_storage.save(u.content, original_filename=u.filename)
        out.append(
            Attachment(
                id=str(uuid.uuid4()),
                filename=u.filename,
                mime_type=u.mime_type,
                storage_path=storage_path,
                size_bytes=len(u.content),
                extracted_text=extract_text(u),
            )
        )
    return out


__all__ = ["prepare_v3_attachments"]
