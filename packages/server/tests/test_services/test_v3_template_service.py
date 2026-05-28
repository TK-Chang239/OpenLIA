"""v3 template service tests (PR3).

Exercises:
  - create_template_from_markdown: parsing success + validation
    errors (empty sections, non-spec frontmatter ignored)
  - resolve_template: built-in via DB, owner-scoped user upload,
    other-user invisibility, soft-deleted invisibility, unknown
  - list_templates: built-ins + owner's uploads, soft-deleted hidden,
    sort order (builtins first, then user name-sorted)
  - soft_delete_template: success, built-in rejection, owner mismatch
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import BUILTIN_TEMPLATES
from openlia_server.db.models.report_v3 import ReportV3Template
from openlia_server.services import v3_template_service as svc
from sqlalchemy.orm import Session


def _seed_builtins(db: Session) -> None:
    """Mimic the migration: insert the 3 v3 built-ins so tests that
    exercise the resolver against builtins have rows to read."""
    now = datetime.now(UTC)
    for report_type in (
        ReportType.INITIATION,
        ReportType.UPDATE,
        ReportType.SECTOR_RESEARCH,
    ):
        spec = BUILTIN_TEMPLATES[report_type]
        row = ReportV3Template(
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


_GOOD_MD = """\
# Overview

A brief overview of the company and its products.

# Financials

Recent revenue, margin, and cash flow trends.

## Valuation

DCF and comparable-company valuation.
"""

_EMPTY_MD = "This file has no headings, just prose.\n\nAnother paragraph."


def test_create_from_markdown_parses_sections_and_persists(db_session, seeded_user):
    row = svc.create_template_from_markdown(
        db=db_session,
        user_id=seeded_user.id,
        name="My initiation template",
        markdown=_GOOD_MD,
    )
    assert row.is_builtin is False
    assert row.user_id == seeded_user.id
    assert row.name == "My initiation template"
    assert row.source_markdown == _GOOD_MD
    spec = row.template_spec_json
    section_titles = [s["title"] for s in spec["sections"]]
    assert section_titles == ["Overview", "Financials", "Valuation"]
    # Every section gets a stable, snake-case id and a non-empty intent.
    for section in spec["sections"]:
        assert section["id"] and " " not in section["id"]
        assert section["intent"]


def test_create_from_markdown_rejects_empty_sections(db_session, seeded_user):
    with pytest.raises(svc.TemplateValidationError):
        svc.create_template_from_markdown(
            db=db_session,
            user_id=seeded_user.id,
            name="Bad template",
            markdown=_EMPTY_MD,
        )


def test_resolve_template_returns_builtin(db_session, seeded_user):
    _seed_builtins(db_session)
    spec = svc.resolve_template(
        db=db_session, user_id=seeded_user.id, template_id="initiation_default"
    )
    assert spec.template_id == "initiation_default"
    assert spec.sections, "initiation built-in should have at least one section"


def test_resolve_template_returns_user_upload(db_session, seeded_user):
    row = svc.create_template_from_markdown(
        db=db_session,
        user_id=seeded_user.id,
        name="Mine",
        markdown=_GOOD_MD,
    )
    spec = svc.resolve_template(
        db=db_session, user_id=seeded_user.id, template_id=row.id
    )
    assert spec.template_id == row.id


def test_resolve_template_hides_other_users_uploads(
    db_session, seeded_user, other_user
):
    row = svc.create_template_from_markdown(
        db=db_session,
        user_id=other_user.id,
        name="Theirs",
        markdown=_GOOD_MD,
    )
    with pytest.raises(svc.TemplateNotFoundError):
        svc.resolve_template(
            db=db_session, user_id=seeded_user.id, template_id=row.id
        )


def test_resolve_template_hides_soft_deleted(db_session, seeded_user):
    row = svc.create_template_from_markdown(
        db=db_session,
        user_id=seeded_user.id,
        name="Doomed",
        markdown=_GOOD_MD,
    )
    svc.soft_delete_template(
        db=db_session, user_id=seeded_user.id, template_id=row.id
    )
    with pytest.raises(svc.TemplateNotFoundError):
        svc.resolve_template(
            db=db_session, user_id=seeded_user.id, template_id=row.id
        )


def test_resolve_template_raises_for_unknown(db_session, seeded_user):
    with pytest.raises(svc.TemplateNotFoundError):
        svc.resolve_template(
            db=db_session, user_id=seeded_user.id, template_id=str(uuid.uuid4())
        )


def test_list_templates_returns_builtins_plus_owner_uploads(
    db_session, seeded_user, other_user
):
    _seed_builtins(db_session)
    mine = svc.create_template_from_markdown(
        db=db_session, user_id=seeded_user.id, name="alpha", markdown=_GOOD_MD
    )
    theirs = svc.create_template_from_markdown(
        db=db_session, user_id=other_user.id, name="beta", markdown=_GOOD_MD
    )
    rows = svc.list_templates(db=db_session, user_id=seeded_user.id)
    ids = [r.id for r in rows]
    assert mine.id in ids
    assert theirs.id not in ids
    # All three built-ins also appear.
    assert "initiation_default" in ids
    assert "update_default" in ids
    assert "sector_research_default" in ids
    # Builtins sort first.
    is_builtin_seq = [r.is_builtin for r in rows]
    assert is_builtin_seq[:3] == [True, True, True]


def test_list_templates_hides_soft_deleted(db_session, seeded_user):
    row = svc.create_template_from_markdown(
        db=db_session, user_id=seeded_user.id, name="Goner", markdown=_GOOD_MD
    )
    svc.soft_delete_template(
        db=db_session, user_id=seeded_user.id, template_id=row.id
    )
    rows = svc.list_templates(db=db_session, user_id=seeded_user.id)
    assert row.id not in [r.id for r in rows]


def test_soft_delete_rejects_builtin(db_session, seeded_user):
    _seed_builtins(db_session)
    with pytest.raises(svc.TemplateNotFoundError):
        svc.soft_delete_template(
            db=db_session,
            user_id=seeded_user.id,
            template_id="initiation_default",
        )


def test_soft_delete_rejects_other_users_upload(
    db_session, seeded_user, other_user
):
    row = svc.create_template_from_markdown(
        db=db_session, user_id=other_user.id, name="theirs", markdown=_GOOD_MD
    )
    with pytest.raises(svc.TemplateNotFoundError):
        svc.soft_delete_template(
            db=db_session, user_id=seeded_user.id, template_id=row.id
        )
