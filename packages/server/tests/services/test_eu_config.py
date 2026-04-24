import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import EuUserConfig
from openlia_server.services import eu_config as svc


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", display_name=user_id, password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_get_returns_defaults_when_no_row(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert cfg.report_length == "normal"
    assert len(cfg.enabled_section_ids) == 8  # all default sections
    assert cfg.custom_sections == []
    # default row not yet materialized
    assert db_session.query(EuUserConfig).count() == 0


def test_get_creates_no_row_until_put(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.get_config(db_session, user_id="u_1")
    svc.get_config(db_session, user_id="u_1")
    assert db_session.query(EuUserConfig).count() == 0


def test_update_persists(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(
        db_session,
        user_id="u_1",
        report_length="concise",
        enabled_section_ids=["quick_take", "key_financials"],
        custom_sections=[{"id": "custom_abc_123", "title": "My Section", "description": "d"}],
    )
    row = db_session.query(EuUserConfig).filter_by(user_id="u_1").one()
    assert row.report_length == "concise"
    assert row.enabled_section_ids == ["quick_take", "key_financials"]
    assert row.custom_sections[0]["title"] == "My Section"


def test_update_is_upsert(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(db_session, user_id="u_1",
                      report_length="concise",
                      enabled_section_ids=["quick_take"],
                      custom_sections=[])
    svc.update_config(db_session, user_id="u_1",
                      report_length="elaborative",
                      enabled_section_ids=["quick_take", "market_reaction"],
                      custom_sections=[])
    rows = db_session.query(EuUserConfig).filter_by(user_id="u_1").all()
    assert len(rows) == 1
    assert rows[0].report_length == "elaborative"


def test_update_rejects_invalid_length(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="report_length"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="tiny",
                          enabled_section_ids=[],
                          custom_sections=[])


def test_update_rejects_custom_section_without_title(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="title"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="normal",
                          enabled_section_ids=[],
                          custom_sections=[{"id": "custom_x_1", "title": "", "description": "d"}])


def test_defaults_match_framework_section_ids(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert set(cfg.enabled_section_ids) == {
        "quick_take", "market_reaction", "key_financials",
        "operational_highlights", "forward_guidance", "earnings_call",
        "risk_assessment", "thesis_check",
    }
