"""File-resolution service for report and attachment downloads.

Routes in ``openlia_server.routes.files`` are kept thin (request parsing +
``Response`` wrapping). All path resolution, ownership checks, filename
sanitization, and format selection live here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from openlia_server.db.models.content import (
    ChatAttachment,
    ChatMessage,
    ChatSession,
)


class AttachmentNotFound(Exception):
    """Raised when no ChatAttachment row matches the requested ID."""


class MessageNotFound(Exception):
    """Raised when an attachment's ``message_id`` no longer resolves."""


class FileGone(Exception):
    """Raised when an attachment's storage file is missing on disk."""


class Forbidden(Exception):
    """Raised when the row exists but does not belong to this user."""


def _safe_filename(name: str) -> str:
    """Strip CR/LF/quotes from filenames so Content-Disposition is safe."""
    return name.replace('"', "").replace("\r", "").replace("\n", "")


@dataclass(frozen=True)
class InMemoryFile:
    content: bytes
    media_type: str
    filename: str


@dataclass(frozen=True)
class StoredFile:
    path: Path
    media_type: str
    filename: str


def resolve_attachment_download(
    db: Session,
    *,
    user_id: str,
    attachment_id: str,
) -> StoredFile:
    """Resolve an attachment download to a path on local storage."""
    row = db.get(ChatAttachment, attachment_id)
    if row is None:
        raise AttachmentNotFound(attachment_id)
    msg = db.get(ChatMessage, row.message_id)
    if msg is None:
        raise MessageNotFound(row.message_id)
    sess = db.get(ChatSession, msg.session_id)
    if sess is None or sess.user_id != user_id:
        raise Forbidden(attachment_id)
    path = Path(row.storage_path)
    if not path.is_file():
        raise FileGone(str(path))
    return StoredFile(
        path=path,
        media_type=row.mime_type or "application/octet-stream",
        filename=_safe_filename(row.filename),
    )
