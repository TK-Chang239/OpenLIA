"""Report store service — validation + persistence + owner-scoped read."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report


def _valid_schema() -> dict:
    return {
        "title": "AAPL Q3 Update",
        "sections": [
            {"heading": "Summary", "content": "Revenue up 10%."},
            {"heading": "Risks", "content": "FX exposure."},
        ],
    }


def _seed_user(db_session: Session, uid: str = "u1") -> User:
    u = User(id=uid, email=f"{uid}@example.com", display_name=uid)
    db_session.add(u)
    db_session.commit()
    return u


def test_validate_report_schema_accepts_canonical_shape(create_tables) -> None:
    from openlia_server.services import reports as svc

    svc.validate_report_schema(_valid_schema())


@pytest.mark.parametrize(
    "schema",
    [
        {},
        {"sections": []},
        {"title": "t"},
        {"title": 5, "sections": []},
        {"title": "t", "sections": "not-a-list"},
        {"title": "t", "sections": [{"heading": "h"}]},
        {"title": "t", "sections": [{"content": "c"}]},
        {"title": "t", "sections": [{"heading": 3, "content": "c"}]},
        {"title": "t", "sections": [{"heading": "h", "content": None}]},
    ],
)
def test_validate_report_schema_rejects_malformed(create_tables, schema) -> None:
    from openlia_server.services import reports as svc

    with pytest.raises(svc.InvalidReportSchemaError):
        svc.validate_report_schema(schema)


def test_save_report_persists_and_round_trips_structured_content(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session)
    schema = _valid_schema()

    report = svc.save_report(
        db_session,
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title=schema["title"],
        subject=None,
        content_markdown="# AAPL",
        content_structured=schema,
        model_ref="gpt-4o",
    )
    db_session.commit()

    stored = db_session.execute(select(Report).where(Report.id == report.id)).scalar_one()
    assert stored.content_structured == schema
    assert stored.department == "secretary"
    assert stored.user_id == "u1"


def test_save_report_rejects_invalid_schema_without_writing(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session)
    with pytest.raises(svc.InvalidReportSchemaError):
        svc.save_report(
            db_session,
            user_id="u1",
            department="secretary",
            report_type="chat_summary",
            title="t",
            subject=None,
            content_markdown="x",
            content_structured={"title": "t"},  # missing sections
            model_ref="gpt-4o",
        )
    db_session.rollback()
    assert db_session.execute(select(Report)).scalar_one_or_none() is None


def test_get_report_for_user_returns_owner_row(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session, uid="u1")
    report = svc.save_report(
        db_session,
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title="t",
        subject=None,
        content_markdown="x",
        content_structured=_valid_schema(),
        model_ref="gpt-4o",
    )
    db_session.commit()

    got = svc.get_report_for_user(db_session, user_id="u1", report_id=report.id)
    assert got is not None
    assert got.id == report.id


def test_get_report_for_user_returns_none_for_non_owner(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session, uid="u1")
    _seed_user(db_session, uid="u2")
    report = svc.save_report(
        db_session,
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title="t",
        subject=None,
        content_markdown="x",
        content_structured=_valid_schema(),
        model_ref="gpt-4o",
    )
    db_session.commit()

    assert svc.get_report_for_user(db_session, user_id="u2", report_id=report.id) is None


def test_get_report_for_user_returns_none_for_missing_id(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import reports as svc

    _seed_user(db_session, uid="u1")
    assert svc.get_report_for_user(db_session, user_id="u1", report_id="missing") is None
