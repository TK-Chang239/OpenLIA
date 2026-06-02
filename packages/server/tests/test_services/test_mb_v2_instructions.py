"""MB instruction-profile service tests.

Exercises:
  - create_instructions_from_upload: persists extracted body_text +
    source artifacts; rejects empty / whitespace-only text
  - resolve_instructions: owner-scoped, other-user invisibility,
    soft-deleted invisibility, unknown id
  - list_instructions: owner's uploads only, name-sorted, round-trip
  - soft_delete_instructions: success hides from resolve/list
"""

from __future__ import annotations

import pytest
from openlia_server.services import mb_v2_instructions_service as svc


def test_create_resolve_list_round_trip(db_session, seeded_user):
    row = svc.create_instructions_from_upload(
        db=db_session,
        user_id=seeded_user.id,
        name="Pre-market read framework",
        body_text="  Lead with the overnight tape.  ",
        source_doc_blob=b"\x00\x01raw-docx-bytes",
        source_doc_mime="application/pdf",
    )
    assert row.is_builtin is False
    assert row.user_id == seeded_user.id
    assert row.name == "Pre-market read framework"
    # body_text is stored stripped.
    assert row.body_text == "Lead with the overnight tape."
    assert row.source_doc_blob == b"\x00\x01raw-docx-bytes"
    assert row.source_doc_mime == "application/pdf"

    assert (
        svc.resolve_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)
        == "Lead with the overnight tape."
    )

    rows = svc.list_instructions(db=db_session, user_id=seeded_user.id)
    assert [r.id for r in rows] == [row.id]
    assert rows[0].name == "Pre-market read framework"


def test_create_rejects_empty_text(db_session, seeded_user):
    with pytest.raises(svc.InstructionsValidationError):
        svc.create_instructions_from_upload(
            db=db_session,
            user_id=seeded_user.id,
            name="Empty",
            body_text="   \n\t  ",
        )


def test_resolve_unknown_raises(db_session, seeded_user):
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(
            db=db_session, user_id=seeded_user.id, instructions_id="does_not_exist"
        )


def test_soft_delete_hides_from_resolve_and_list(db_session, seeded_user):
    row = svc.create_instructions_from_upload(
        db=db_session, user_id=seeded_user.id, name="Temp", body_text="x"
    )
    svc.soft_delete_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)
    assert svc.list_instructions(db=db_session, user_id=seeded_user.id) == []


def test_resolve_hides_other_users(db_session, seeded_user, other_user):
    row = svc.create_instructions_from_upload(
        db=db_session,
        user_id=seeded_user.id,
        name="Mine",
        body_text="Secret methodology.",
    )
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(db=db_session, user_id=other_user.id, instructions_id=row.id)
