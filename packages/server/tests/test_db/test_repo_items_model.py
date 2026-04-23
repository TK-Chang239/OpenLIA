"""RepoItem model registration, FK cascades, and unique constraint."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models  # noqa: F401 — register all models
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_repo_item_registered_on_metadata() -> None:
    import openlia_server.db.models  # noqa: F401
    from openlia_server.db.base import Base

    assert "repo_items" in Base.metadata.tables


def test_repo_item_unique_user_report(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import RepoItem, Report

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1",
        user_id="u1",
        department="secretary",
        report_type="chat_summary",
        title="t",
        content_markdown="x",
        content_structured={},
        model_ref="gpt-4o",
    )
    db_session.add_all([u, r])
    db_session.flush()

    db_session.add(RepoItem(id="ri1", user_id="u1", report_id="r1"))
    db_session.commit()

    db_session.add(RepoItem(id="ri2", user_id="u1", report_id="r1"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_repo_item_cascade_on_report_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import RepoItem, Report

    u = User(id="u2", email="u2@example.com", display_name="U2")
    r = Report(
        id="r2",
        user_id="u2",
        department="secretary",
        report_type="chat_summary",
        title="t",
        content_markdown="x",
        content_structured={},
        model_ref="gpt-4o",
    )
    db_session.add_all([u, r])
    db_session.flush()
    db_session.add(RepoItem(id="ri3", user_id="u2", report_id="r2"))
    db_session.commit()

    db_session.delete(r)
    db_session.commit()
    assert db_session.execute(select(RepoItem)).scalar_one_or_none() is None


def test_report_no_longer_has_is_starred_or_tags() -> None:
    from openlia_server.db.models.content import Report

    cols = {c.name for c in Report.__table__.columns}
    assert "is_starred" not in cols
    assert "tags" not in cols
