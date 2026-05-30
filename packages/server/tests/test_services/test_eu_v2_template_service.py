# packages/server/tests/test_services/test_eu_v2_template_service.py
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_eu.default_template import build_default_template
from openlia_server.db.models.report_eu import ReportEuTemplate
from openlia_server.services.eu_v2_template_service import (
    TemplateNotFoundError,
    list_templates,
    resolve_template,
)


def _seed_eu_default(db) -> None:
    """Insert the eu_default builtin row, mirroring what the migration does."""
    spec = build_default_template()
    now = datetime.now(UTC)
    row = ReportEuTemplate(
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
    db.add(row)
    db.flush()


@pytest.fixture
def db_session_with_seed(db_session):
    _seed_eu_default(db_session)
    return db_session


def test_resolve_builtin_default(db_session_with_seed):
    spec = resolve_template(db_session_with_seed, user_id="u-1", template_id="eu_default")
    assert spec.template_id == "eu_default"
    assert len(spec.sections) == 8


def test_list_includes_builtin(db_session_with_seed):
    rows = list_templates(db_session_with_seed, user_id="u-1")
    assert any(t.id == "eu_default" and t.is_builtin for t in rows)


def test_resolve_unknown_raises(db_session_with_seed):
    with pytest.raises(TemplateNotFoundError):
        resolve_template(db_session_with_seed, user_id="u-1", template_id="ghost")
