"""Tests for WizardService.get_status and env-override resolution."""
from __future__ import annotations

from openlia_server.services import wizard as svc
from sqlalchemy.orm import Session


def test_get_status_fresh_install_returns_personal_step_mode(
    create_tables, db_session: Session
) -> None:
    status = svc.get_status(db_session, env={})
    assert status.mode == "personal"
    assert status.wizard_completed is False
    assert status.current_step == "mode"
    assert status.completed_steps == []
    assert status.env_overrides == {}


def test_get_status_reflects_env_mode_override(create_tables, db_session: Session) -> None:
    status = svc.get_status(db_session, env={"OPENLIA_MODE": "company"})
    assert status.mode == "company"
    assert "mode" in status.env_overrides


def test_get_status_reflects_wizard_completed_flag(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.add(ConfigStore(key="wizard.mode", value="company"))
    db_session.commit()

    status = svc.get_status(db_session, env={})
    assert status.wizard_completed is True
    assert status.mode == "company"


def test_get_status_env_mode_shadows_db_mode(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.mode", value="personal"))
    db_session.commit()

    status = svc.get_status(db_session, env={"OPENLIA_MODE": "company"})
    assert status.mode == "company"
    assert "mode" in status.env_overrides
