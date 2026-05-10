"""Lifecycle hooks + janitor for chat attachment files.

Two mechanisms keep ``$OPENLIA_ATTACHMENTS_DIR`` consistent with the
``chat_attachments`` table:

1. **Synchronous after-commit unlink.** When a ``ChatAttachment`` row is
   deleted (directly or via CASCADE from message/session/user), an
   ``after_commit`` event reads the captured ``storage_path`` and removes
   the file. Rollbacks leave files intact.

2. **Hourly janitor sweep.** A periodic task (and a ``openlia attachments
   gc`` CLI escape hatch) walks the storage root and removes files that
   no row references and that are older than the grace period.

See ``planning/specs/systems/composer-attachments-design.md`` (Q8).
"""

from __future__ import annotations

import time

from sqlalchemy import event
from sqlalchemy.orm import Session

from openlia_server.db.models.content import ChatAttachment
from openlia_server.services import attachment_storage

_PENDING_KEY = "_openlia_pending_attachment_unlinks"


@event.listens_for(ChatAttachment, "before_delete")
def _stage_attachment_unlink(_mapper, _connection, target: ChatAttachment) -> None:
    sess = Session.object_session(target)
    if sess is None:
        return
    pending: list[str] = sess.info.setdefault(_PENDING_KEY, [])
    if target.storage_path:
        pending.append(target.storage_path)


@event.listens_for(Session, "before_flush")
def _stage_cascade_attachment_unlinks(sess: Session, _flush_context, _instances) -> None:
    """When a ``ChatMessage`` (or further-up ancestor) is deleted, the DB-level
    ``ON DELETE CASCADE`` removes the ``chat_attachments`` rows directly,
    bypassing the per-instance ``before_delete`` event. Pre-fetch the
    cascaded ``storage_path`` values so ``after_commit`` can still unlink.
    """
    from openlia_server.db.models.content import ChatMessage, ChatSession

    pending: list[str] = sess.info.setdefault(_PENDING_KEY, [])
    if not sess.deleted:
        return
    message_ids: list[str] = []
    session_ids: list[str] = []
    for obj in sess.deleted:
        if isinstance(obj, ChatMessage):
            message_ids.append(obj.id)
        elif isinstance(obj, ChatSession):
            session_ids.append(obj.id)
    if message_ids:
        rows = (
            sess.query(ChatAttachment.storage_path)
            .filter(ChatAttachment.message_id.in_(message_ids))
            .all()
        )
        pending.extend(r[0] for r in rows if r[0])
    if session_ids:
        rows = (
            sess.query(ChatAttachment.storage_path)
            .join(ChatMessage, ChatMessage.id == ChatAttachment.message_id)
            .filter(ChatMessage.session_id.in_(session_ids))
            .all()
        )
        pending.extend(r[0] for r in rows if r[0])


@event.listens_for(Session, "after_commit")
def _unlink_attachment_files_after_commit(sess: Session) -> None:
    paths = sess.info.pop(_PENDING_KEY, None)
    if not paths:
        return
    for p in paths:
        attachment_storage.unlink(p)


@event.listens_for(Session, "after_rollback")
def _drop_pending_unlinks_after_rollback(sess: Session) -> None:
    sess.info.pop(_PENDING_KEY, None)


def gc_orphaned_attachments(db: Session, *, grace_seconds: int = 3600) -> int:
    """Remove files in the storage root that no ``chat_attachments`` row
    references and that haven't been touched in the last ``grace_seconds``.

    Returns the number of files removed."""
    referenced = {row[0] for row in db.query(ChatAttachment.storage_path).all()}
    root = attachment_storage.configured_root()
    cutoff = time.time() - grace_seconds
    removed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if str(path) in referenced:
            continue
        try:
            if path.stat().st_mtime >= cutoff:
                continue
        except FileNotFoundError:
            continue
        try:
            path.unlink()
            removed += 1
        except FileNotFoundError:
            pass
    return removed
