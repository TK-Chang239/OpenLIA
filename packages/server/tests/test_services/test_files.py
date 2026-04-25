"""Phase 12 NEW-12-12 — services/files.py extraction tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from openlia_server.db.models.content import (
    ChatAttachment,
    ChatMessage,
    ChatSession,
    Report,
)
from openlia_server.services import files as svc


def _make_report(db_session, *, user_id: str, title: str = "Report") -> Report:
    row = Report(
        id=str(uuid.uuid4()),
        user_id=user_id,
        department="secretary",
        report_type="ad_hoc",
        title=title,
        content_markdown="# hi",
        content_structured={},
        model_ref="test:model",
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_resolve_report_default_serves_md(db_session, seeded_user):
    report = _make_report(db_session, user_id=seeded_user.id)
    blob = svc.resolve_report_download(db_session, user_id=seeded_user.id, report_id=report.id)
    assert blob.filename.endswith(".md")
    assert blob.media_type == "text/markdown"
    assert blob.content == b"# hi"


def test_resolve_report_explicit_md_supported(db_session, seeded_user):
    report = _make_report(db_session, user_id=seeded_user.id)
    blob = svc.resolve_report_download(
        db_session, user_id=seeded_user.id, report_id=report.id, format="md"
    )
    assert blob.media_type == "text/markdown"


def test_resolve_report_pdf_format_unsupported(db_session, seeded_user):
    report = _make_report(db_session, user_id=seeded_user.id)
    with pytest.raises(svc.UnsupportedFormat):
        svc.resolve_report_download(
            db_session, user_id=seeded_user.id, report_id=report.id, format="pdf"
        )


def test_resolve_report_unknown_format_raises(db_session, seeded_user):
    report = _make_report(db_session, user_id=seeded_user.id)
    with pytest.raises(svc.UnsupportedFormat):
        svc.resolve_report_download(
            db_session,
            user_id=seeded_user.id,
            report_id=report.id,
            format="exe",
        )


def test_resolve_report_other_user_forbidden(db_session, seeded_user, other_user):
    report = _make_report(db_session, user_id=seeded_user.id)
    with pytest.raises(svc.Forbidden):
        svc.resolve_report_download(db_session, user_id=other_user.id, report_id=report.id)


def test_resolve_report_not_found(db_session, seeded_user):
    with pytest.raises(svc.ReportNotFound):
        svc.resolve_report_download(db_session, user_id=seeded_user.id, report_id="nope")


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
