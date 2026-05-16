"""services/files.py — attachment download only (report MD path removed)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from openlia_server.db.models.content import ChatAttachment, ChatMessage, ChatSession
from openlia_server.services import files as svc


def test_resolve_attachment_round_trip(db_session, seeded_user, tmp_path):
    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id=seeded_user.id,
        department="secretary",
        title="x",
        is_pinned=False,
        is_archived=False,
    )
    db_session.add(sess)
    db_session.commit()
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        role="user",
        content="hi",
    )
    db_session.add(msg)
    db_session.commit()
    fp: Path = tmp_path / "a.txt"
    fp.write_text("hello")
    att = ChatAttachment(
        id=str(uuid.uuid4()),
        message_id=msg.id,
        filename="a.txt",
        mime_type="text/plain",
        size_bytes=5,
        storage_path=str(fp),
    )
    db_session.add(att)
    db_session.commit()
    stored = svc.resolve_attachment_download(
        db_session, user_id=seeded_user.id, attachment_id=att.id
    )
    assert stored.path == fp
    assert stored.filename == "a.txt"
    assert stored.media_type == "text/plain"


def test_resolve_attachment_file_gone(db_session, seeded_user, tmp_path):
    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id=seeded_user.id,
        department="secretary",
        title="x",
        is_pinned=False,
        is_archived=False,
    )
    db_session.add(sess)
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        role="user",
        content="hi",
    )
    db_session.add(msg)
    db_session.commit()
    att = ChatAttachment(
        id=str(uuid.uuid4()),
        message_id=msg.id,
        filename="missing.txt",
        mime_type="text/plain",
        size_bytes=0,
        storage_path=str(tmp_path / "missing.txt"),
    )
    db_session.add(att)
    db_session.commit()
    with pytest.raises(svc.FileGone):
        svc.resolve_attachment_download(db_session, user_id=seeded_user.id, attachment_id=att.id)
