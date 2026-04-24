from __future__ import annotations

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import MbUserConfig
from openlia_server.services import mb_config as svc
from sqlalchemy.orm import Session


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(
        id=user_id,
        email=f"{user_id}@x",
        display_name=user_id,
        password_hash="x",
        is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


def test_get_returns_defaults_when_no_row(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert cfg.report_length == "normal"
    assert len(cfg.enabled_section_ids) == 7
    assert cfg.section_topics == {}
    assert cfg.custom_sections == []
    assert cfg.reference_portfolio is False
    assert db_session.query(MbUserConfig).count() == 0


def test_defaults_match_framework_section_ids(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert set(cfg.enabled_section_ids) == {
        "executive_summary",
        "global_macro",
        "country_news",
        "market_news",
        "sector_news",
        "stock_news",
        "upcoming_preview",
    }


def test_update_persists(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(
        db_session,
        user_id="u_1",
        report_length="concise",
        enabled_section_ids=["executive_summary", "global_macro"],
        section_topics={"global_macro": [{"topic": "War", "notes": "Russia"}]},
        custom_sections=[
            {"id": "abc", "title": "My Macro Focus", "description": "FX crosses"}
        ],
        reference_portfolio=True,
    )
    row = db_session.query(MbUserConfig).filter_by(user_id="u_1").one()
    assert row.report_length == "concise"
    assert row.enabled_section_ids == ["executive_summary", "global_macro"]
    assert row.section_topics["global_macro"][0]["topic"] == "War"
    assert row.custom_sections[0]["title"] == "My Macro Focus"
    assert row.reference_portfolio is True


def test_update_is_upsert(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(
        db_session,
        user_id="u_1",
        report_length="concise",
        enabled_section_ids=["executive_summary"],
        section_topics={},
        custom_sections=[],
        reference_portfolio=False,
    )
    svc.update_config(
        db_session,
        user_id="u_1",
        report_length="elaborative",
        enabled_section_ids=["global_macro"],
        section_topics={},
        custom_sections=[],
        reference_portfolio=True,
    )
    rows = db_session.query(MbUserConfig).filter_by(user_id="u_1").all()
    assert len(rows) == 1
    assert rows[0].report_length == "elaborative"
    assert rows[0].reference_portfolio is True


def test_update_rejects_invalid_length(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="report_length"):
        svc.update_config(
            db_session,
            user_id="u_1",
            report_length="tiny",
            enabled_section_ids=[],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )


def test_update_rejects_unknown_section_id(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="unknown section"):
        svc.update_config(
            db_session,
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=["not_a_section"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )


def test_update_rejects_custom_section_without_title(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="title"):
        svc.update_config(
            db_session,
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=[],
            section_topics={},
            custom_sections=[{"id": "x", "title": "", "description": "d"}],
            reference_portfolio=False,
        )


def test_update_rejects_topic_without_name(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="topic"):
        svc.update_config(
            db_session,
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=["global_macro"],
            section_topics={"global_macro": [{"topic": "", "notes": "x"}]},
            custom_sections=[],
            reference_portfolio=False,
        )
