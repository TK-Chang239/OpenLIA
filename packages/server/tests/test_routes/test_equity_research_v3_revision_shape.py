"""Unit tests for the v3 revision shape resolver.

``_resolve_revision_shape`` rebuilds the (template, instructions_text)
a revision runs with from the parent run row. The key behaviours:
  - a freeform parent resolves to the sections-less spec (so a
    no-template report is revisable at all — previously a 400)
  - the parent's instruction profile is re-resolved and replayed
  - a since-deleted profile degrades to no instructions, not an error
  - a genuinely missing (non-freeform) template still 400s
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_v3 import ReportV3
from openlia_server.routes.departments.equity_research_v3 import (
    FREEFORM_TEMPLATE_ID,
    _resolve_revision_shape,
)
from openlia_server.services import v3_instructions_service as instructions_svc
from openlia_server.services import v3_template_service as templates_svc

_TEMPLATE_MD = "# Overview\n\nbody.\n\n# Financials\n\nbody."


@pytest.fixture
def user(db_session):
    now = datetime.now(UTC)
    row = User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4().hex}@openlia.local",
        display_name="Test",
        is_admin=False,
        is_disabled=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _parent(
    *,
    user_id: str,
    template_id: str,
    instructions_id: str | None,
) -> ReportV3:
    now = datetime.now(UTC)
    return ReportV3(
        id=str(uuid.uuid4()),
        user_id=user_id,
        subject="RKLB.US",
        template_id=template_id,
        instructions_id=instructions_id,
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        status="completed",
        error_message=None,
        created_at=now,
        completed_at=now,
    )


def test_freeform_parent_resolves_to_freeform_spec_and_replays_instructions(db_session, user):
    profile = instructions_svc.create_instructions_from_upload(
        db=db_session,
        user_id=user.id,
        name="Winner framework",
        body_text="Industry before company.",
    )
    db_session.flush()
    parent = _parent(
        user_id=user.id,
        template_id=FREEFORM_TEMPLATE_ID,
        instructions_id=profile.id,
    )

    template, instructions = _resolve_revision_shape(db=db_session, user_id=user.id, parent=parent)
    assert template.template_id == FREEFORM_TEMPLATE_ID
    assert template.sections == []
    assert instructions == "Industry before company."


def test_real_template_parent_resolves_without_instructions(db_session, user):
    row = templates_svc.create_template_from_markdown(
        db=db_session,
        user_id=user.id,
        name="Mine",
        markdown=_TEMPLATE_MD,
    )
    db_session.flush()
    parent = _parent(user_id=user.id, template_id=row.id, instructions_id=None)

    template, instructions = _resolve_revision_shape(db=db_session, user_id=user.id, parent=parent)
    assert template.template_id == row.id
    assert instructions is None


def test_deleted_profile_degrades_to_no_instructions(db_session, user):
    row = templates_svc.create_template_from_markdown(
        db=db_session, user_id=user.id, name="Mine", markdown=_TEMPLATE_MD
    )
    profile = instructions_svc.create_instructions_from_upload(
        db=db_session, user_id=user.id, name="Temp", body_text="x"
    )
    db_session.flush()
    instructions_svc.soft_delete_instructions(
        db=db_session, user_id=user.id, instructions_id=profile.id
    )
    parent = _parent(user_id=user.id, template_id=row.id, instructions_id=profile.id)

    template, instructions = _resolve_revision_shape(db=db_session, user_id=user.id, parent=parent)
    assert template.template_id == row.id
    assert instructions is None


def test_missing_template_raises_400(db_session, user):
    parent = _parent(
        user_id=user.id,
        template_id="ghost_template_xyz",
        instructions_id=None,
    )
    with pytest.raises(HTTPException) as excinfo:
        _resolve_revision_shape(db=db_session, user_id=user.id, parent=parent)
    assert excinfo.value.status_code == 400
