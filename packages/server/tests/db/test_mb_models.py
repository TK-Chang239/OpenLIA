from __future__ import annotations

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import MbUserConfig
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _mk_user(db: Session, user_id: str = "u_mb_1") -> User:
    u = User(
        id=user_id,
        email=f"{user_id}@x",
        display_name="MB",
        password_hash="x",
        is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


def test_mb_config_columns(create_tables) -> None:
    cols = {c.name for c in inspect(MbUserConfig).columns}
    for expected in {
        "id",
        "user_id",
        "report_length",
        "enabled_section_ids",
        "section_topics",
        "custom_sections",
        "reference_portfolio",
        "created_at",
        "updated_at",
    }:
        assert expected in cols


def test_mb_config_one_per_user(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_mb_1",
            report_length="normal",
            enabled_section_ids=["executive_summary"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    )
    db_session.commit()
    db_session.add(
        MbUserConfig(
            id="c2",
            user_id="u_mb_1",
            report_length="normal",
            enabled_section_ids=[],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_mb_config_length_check_constraint(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c3",
            user_id="u_mb_1",
            report_length="tiny",
            enabled_section_ids=[],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_mb_config_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c4",
            user_id="u_mb_1",
            report_length="normal",
            enabled_section_ids=[],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    )
    db_session.commit()
    db_session.query(User).filter_by(id="u_mb_1").delete()
    db_session.commit()
    assert db_session.query(MbUserConfig).count() == 0
