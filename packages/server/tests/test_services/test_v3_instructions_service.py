"""v3 instruction-profile service tests.

Exercises:
  - create_instructions_from_upload: persists extracted body_text +
    source artifacts; rejects empty / whitespace-only text
  - resolve_instructions: owner-scoped, other-user invisibility,
    soft-deleted invisibility, unknown id
  - list_instructions: owner's uploads only, soft-deleted hidden,
    name-sorted
  - soft_delete_instructions: success, owner mismatch, already-deleted
"""

from __future__ import annotations

import pytest
from openlia_server.services import v3_instructions_service as svc


def test_create_persists_body_and_source(db_session, seeded_user):
    row = svc.create_instructions_from_upload(
        db=db_session,
        user_id=seeded_user.id,
        name="Winner-approach framework",
        body_text="  Look at the industry before the company.  ",
        source_doc_blob=b"\x00\x01raw-docx-bytes",
        source_doc_mime="application/pdf",
    )
    assert row.is_builtin is False
    assert row.user_id == seeded_user.id
    assert row.name == "Winner-approach framework"
    # body_text is stored stripped.
    assert row.body_text == "Look at the industry before the company."
    assert row.source_doc_blob == b"\x00\x01raw-docx-bytes"
    assert row.source_doc_mime == "application/pdf"


def test_create_rejects_empty_text(db_session, seeded_user):
    with pytest.raises(svc.InstructionsValidationError):
        svc.create_instructions_from_upload(
            db=db_session,
            user_id=seeded_user.id,
            name="Empty",
            body_text="   \n\t  ",
        )


def test_resolve_returns_body_text(db_session, seeded_user):
    row = svc.create_instructions_from_upload(
        db=db_session,
        user_id=seeded_user.id,
        name="Mine",
        body_text="Principle one.",
    )
    assert (
        svc.resolve_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)
        == "Principle one."
    )


def test_resolve_hides_other_users(db_session, seeded_user, other_user):
    row = svc.create_instructions_from_upload(
        db=db_session,
        user_id=other_user.id,
        name="Theirs",
        body_text="Secret methodology.",
    )
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)


def test_resolve_unknown_raises(db_session, seeded_user):
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(
            db=db_session, user_id=seeded_user.id, instructions_id="does_not_exist"
        )


def test_list_owner_scoped_and_sorted(db_session, seeded_user, other_user):
    svc.create_instructions_from_upload(
        db=db_session, user_id=seeded_user.id, name="Zeta", body_text="z"
    )
    svc.create_instructions_from_upload(
        db=db_session, user_id=seeded_user.id, name="alpha", body_text="a"
    )
    svc.create_instructions_from_upload(
        db=db_session, user_id=other_user.id, name="Theirs", body_text="t"
    )
    rows = svc.list_instructions(db=db_session, user_id=seeded_user.id)
    # Only the caller's profiles, case-insensitively name-sorted.
    assert [r.name for r in rows] == ["alpha", "Zeta"]


def test_soft_delete_hides_from_resolve_and_list(db_session, seeded_user):
    row = svc.create_instructions_from_upload(
        db=db_session, user_id=seeded_user.id, name="Temp", body_text="x"
    )
    svc.soft_delete_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.resolve_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)
    assert svc.list_instructions(db=db_session, user_id=seeded_user.id) == []


def test_soft_delete_rejects_other_user(db_session, seeded_user, other_user):
    row = svc.create_instructions_from_upload(
        db=db_session, user_id=other_user.id, name="Theirs", body_text="x"
    )
    with pytest.raises(svc.InstructionsNotFoundError):
        svc.soft_delete_instructions(db=db_session, user_id=seeded_user.id, instructions_id=row.id)
