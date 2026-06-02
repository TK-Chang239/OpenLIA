# packages/server/tests/test_services/test_mb_v2_templates.py
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_mb.default_template import build_default_template
from openlia_server.db.models.report_mb import ReportMbTemplate
from openlia_server.services.mb_v2_template_service import (
    TemplateNotFoundError,
    create_template_from_markdown,
    list_templates,
    resolve_template,
    soft_delete_template,
)


def _seed_mb_default(db) -> None:
    """Insert the mb_default builtin row, mirroring what the migration does."""
    spec = build_default_template()
    now = datetime.now(UTC)
    row = ReportMbTemplate(
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
    _seed_mb_default(db_session)
    return db_session


def test_resolve_builtin_default(db_session_with_seed):
    spec = resolve_template(db_session_with_seed, user_id="u-1", template_id="mb_default")
    assert spec.template_id == "mb_default"
    assert len(spec.sections) == 5


def test_list_includes_builtin(db_session_with_seed):
    rows = list_templates(db_session_with_seed, user_id="u-1")
    assert any(t.id == "mb_default" and t.is_builtin for t in rows)


def test_resolve_unknown_raises(db_session_with_seed):
    with pytest.raises(TemplateNotFoundError):
        resolve_template(db_session_with_seed, user_id="u-1", template_id="ghost")


def test_create_from_markdown_then_list_and_resolve(db_session_with_seed):
    markdown = "# Section One\n\nIntent one.\n\n# Section Two\n\nIntent two.\n"
    row = create_template_from_markdown(
        db=db_session_with_seed,
        user_id="u-1",
        name="My MB template",
        markdown=markdown,
    )
    assert row.is_builtin is False
    assert row.user_id == "u-1"

    rows = list_templates(db_session_with_seed, user_id="u-1")
    ids = {t.id for t in rows}
    assert "mb_default" in ids
    assert row.id in ids

    spec = resolve_template(db_session_with_seed, user_id="u-1", template_id=row.id)
    assert spec.template_id == row.id
    assert len(spec.sections) == 2


def test_soft_delete_hides_template(db_session_with_seed):
    row = create_template_from_markdown(
        db=db_session_with_seed,
        user_id="u-1",
        name="Temp",
        markdown="# Only\n\nIntent.\n",
    )
    soft_delete_template(db=db_session_with_seed, user_id="u-1", template_id=row.id)
    with pytest.raises(TemplateNotFoundError):
        resolve_template(db_session_with_seed, user_id="u-1", template_id=row.id)
    ids = {t.id for t in list_templates(db_session_with_seed, user_id="u-1")}
    assert row.id not in ids


def test_resolve_hides_other_users(db_session_with_seed):
    row = create_template_from_markdown(
        db=db_session_with_seed,
        user_id="u-1",
        name="Mine",
        markdown="# Only\n\nIntent.\n",
    )
    with pytest.raises(TemplateNotFoundError):
        resolve_template(db_session_with_seed, user_id="u-2", template_id=row.id)
