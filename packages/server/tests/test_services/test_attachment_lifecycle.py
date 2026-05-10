"""Phase 12 — attachment lifecycle: after_commit unlink + janitor.

Verifies that a ``ChatAttachment`` row deletion that commits removes the
file from disk, and that the janitor sweep removes orphan files older than
the grace period.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from openlia_server.db.models.content import ChatMessage, ChatSession
from openlia_server.services import attachment_storage
from openlia_server.services.attachment_lifecycle import gc_orphaned_attachments
from openlia_server.services.attachments import FileUpload, persist_attachments
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path / "attachments"))
    return tmp_path


@pytest.fixture
def db(db_session: Session) -> Session:
    sess = ChatSession(id="s1", user_id="u-1", department="secretary", title="t")
    msg = ChatMessage(
        id="m1",
        session_id="s1",
        role="user",
        content="hi",
        created_at=datetime.now(UTC),
    )
    db_session.add_all([sess, msg])
    db_session.commit()
    return db_session


def test_committing_attachment_delete_unlinks_file(db: Session) -> None:
    [row] = persist_attachments(
        db,
        message_id="m1",
        uploads=[FileUpload(filename="x.txt", mime_type="text/plain", content=b"x")],
    )
    path = Path(row.storage_path)
    assert path.is_file()

    db.delete(row)
    db.commit()

    assert not path.exists(), "after_commit hook must unlink the storage file"


def test_uncommitted_delete_keeps_file_on_disk(db: Session) -> None:
    """If the transaction never commits (rollback), the file must stay so
    nothing is silently lost."""
    [row] = persist_attachments(
        db,
        message_id="m1",
        uploads=[FileUpload(filename="x.txt", mime_type="text/plain", content=b"x")],
    )
    path = Path(row.storage_path)

    db.delete(row)
    db.rollback()

    assert path.is_file()


def test_cascading_message_delete_unlinks_attachment_files(db: Session) -> None:
    """Deleting the parent message cascades to attachments via the FK; the
    cascaded row's deletion must still trigger the unlink."""
    [row] = persist_attachments(
        db,
        message_id="m1",
        uploads=[FileUpload(filename="x.txt", mime_type="text/plain", content=b"x")],
    )
    path = Path(row.storage_path)
    msg = db.get(ChatMessage, "m1")

    db.delete(msg)
    db.commit()

    assert not path.exists()


# ─── Janitor ────────────────────────────────────────────────────────────────


def test_janitor_removes_orphan_files_older_than_grace(db: Session, tmp_path: Path) -> None:
    """A file on disk that no DB row references and is older than the grace
    period must be removed."""
    root = attachment_storage.configured_root()
    orphan = root / "or" / "orphan.txt"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"stale")
    # Backdate the mtime so the grace window has expired.
    old = time.time() - 7200  # 2h ago
    import os

    os.utime(orphan, (old, old))

    removed = gc_orphaned_attachments(db, grace_seconds=3600)
    assert removed >= 1
    assert not orphan.exists()


def test_janitor_keeps_files_within_grace_window(db: Session, tmp_path: Path) -> None:
    """Recent files (within the grace period) must be left alone — they may
    belong to an in-flight upload."""
    root = attachment_storage.configured_root()
    fresh = root / "fr" / "fresh.txt"
    fresh.parent.mkdir(parents=True, exist_ok=True)
    fresh.write_bytes(b"new")

    removed = gc_orphaned_attachments(db, grace_seconds=3600)
    assert removed == 0
    assert fresh.is_file()


def test_janitor_keeps_referenced_files(db: Session) -> None:
    """A file that a ChatAttachment row points to must NOT be swept, even
    if it's older than the grace window."""
    [row] = persist_attachments(
        db,
        message_id="m1",
        uploads=[FileUpload(filename="keep.txt", mime_type="text/plain", content=b"k")],
    )
    path = Path(row.storage_path)
    import os

    old = time.time() - 7200
    os.utime(path, (old, old))

    removed = gc_orphaned_attachments(db, grace_seconds=3600)
    assert removed == 0
    assert path.is_file()
