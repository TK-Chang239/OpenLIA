"""Tests for the EU v2 render service (html + docx over a persisted run).

The PDF path needs a Playwright ``BrowserLauncher`` and is covered by the
endpoint test; here html + docx suffice. The ``db_session_with_seed``
fixture mirrors the one in ``test_eu_v2_run_service.py`` — it seeds the
builtin ``eu_default`` template the migration installs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_eu.default_template import build_default_template
from openlia_server.db.models.report_eu import (
    ReportEu,
    ReportEuSection,
    ReportEuTemplate,
)
from openlia_server.services import eu_v2_render_service as render_svc


def _seed_eu_default(db) -> None:
    """Insert the eu_default builtin row, mirroring what the migration does."""
    spec = build_default_template()
    now = datetime.now(UTC)
    db.add(
        ReportEuTemplate(
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
    _seed_eu_default(db_session)
    return db_session


def _seed_completed(db) -> str:
    rid = "rr-1"
    db.add(
        ReportEu(
            id=rid,
            user_id="u-1",
            subject="AAPL earnings",
            ticker="AAPL",
            trigger_kind="on_demand",
            fiscal_date=None,
            template_id="eu_default",
            language="en",
            length="normal",
            provider_kind="anthropic",
            model="m",
            status="completed",
            error_message=None,
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            cover_json=None,
            reasoning_effort=None,
        )
    )
    db.add(
        ReportEuSection(
            report_id=rid,
            section_id="quick_take",
            section_index=0,
            title="Quick Take",
            markdown="Body text.",
            version=1,
        )
    )
    db.flush()
    return rid


def test_render_html_contains_section(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    out = render_svc.render_html(db=db_session_with_seed, user_id="u-1", report_id=rid)
    assert "Quick Take" in out.html


def test_render_docx_returns_bytes(db_session_with_seed):
    rid = _seed_completed(db_session_with_seed)
    out = render_svc.render_docx(db=db_session_with_seed, user_id="u-1", report_id=rid)
    assert isinstance(out, (bytes, bytearray)) and out[:2] == b"PK"
