"""Tests for the MB v2 render service (html + docx over a persisted run)
plus the shared download-filename convention.

The PDF path needs a Playwright ``BrowserLauncher`` and is covered by the
endpoint test; here html + docx suffice. The ``db_session_with_seed``
fixture seeds a ``users`` row (the report_mb FK requires it) and the
builtin ``mb_default`` template the migration installs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_mb.default_template import build_default_template
from openlia_server.db.models.report_mb import (
    ReportMb,
    ReportMbSection,
    ReportMbTemplate,
)
from openlia_server.services import mb_v2_filename as filename_svc
from openlia_server.services import mb_v2_render_service as render_svc


def _seed_user(db, user_id: str = "u-1") -> None:
    from openlia_server.db.models.auth import User

    if db.get(User, user_id) is not None:
        return
    now = datetime.now(UTC)
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@openlia.local",
            display_name=user_id,
            password_hash=None,
            is_admin=True,
            is_disabled=False,
            created_at=now,
            updated_at=now,
        )
    )
    db.flush()


def _seed_mb_default(db) -> None:
    spec = build_default_template()
    now = datetime.now(UTC)
    db.add(
        ReportMbTemplate(
            id=spec.template_id,
            user_id=None,
            name=spec.name,
            is_builtin=True,
            template_spec_json=json.loads(spec.model_dump_json()),
            source_markdown=None,
            source_doc_blob=None,
            source_doc_mime=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
    )
    db.flush()


@pytest.fixture
def db_session_with_seed(db_session, monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "test-eodhd-key")
    _seed_user(db_session)
    _seed_mb_default(db_session)
    return db_session


def _seed_completed(db, *, subject: str = "Morning Briefing - 2026-06-02") -> str:
    rid = "rr-1"
    db.add(
        ReportMb(
            id=rid,
            user_id="u-1",
            subject=subject,
            trigger_kind="on_demand",
            schedule_id=None,
            template_id="mb_default",
            instructions_id=None,
            language="en",
            length="normal",
            provider_kind="anthropic",
            model="m",
            status="completed",
            error_message=None,
            created_at=datetime.now(UTC),
            completed_at=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
            cover_json=None,
            reasoning_effort=None,
        )
    )
    db.add(
        ReportMbSection(
            report_id=rid,
            section_id="market_wrap",
            section_index=0,
            title="Market Wrap",
            markdown="Indices opened higher.",
            version=1,
        )
    )
    db.add(
        ReportMbSection(
            report_id=rid,
            section_id="outlook",
            section_index=1,
            title="Outlook",
            markdown="Watch the CPI print.",
            version=1,
        )
    )
    db.flush()
    return rid


def test_render_html_contains_subject_and_section_titles(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    out = render_svc.render_html(db=db_session_with_seed, user_id="u-1", report_id=rid)
    assert "Morning Briefing - 2026-06-02" in out.html
    assert "Market Wrap" in out.html
    assert "Outlook" in out.html


def test_render_docx_returns_bytes(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    out = render_svc.render_docx(db=db_session_with_seed, user_id="u-1", report_id=rid)
    assert isinstance(out, (bytes, bytearray)) and out[:2] == b"PK"


def test_build_download_filename_subject_template_date(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    row = db_session_with_seed.get(ReportMb, rid)
    name = filename_svc.build_download_filename(row=row, ext="pdf")
    assert name == "Morning_Briefing_2026-06-02_Morning-Briefing_2026-06-02.pdf"


def test_build_download_filename_extension_swaps(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    row = db_session_with_seed.get(ReportMb, rid)
    assert filename_svc.build_download_filename(row=row, ext="docx").endswith(".docx")
    assert filename_svc.build_download_filename(row=row, ext="html").endswith(".html")
