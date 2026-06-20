"""Tests for WizardService.get_status and env-override resolution."""

from __future__ import annotations

import pytest
from openlia_server.services import wizard as svc
from sqlalchemy.orm import Session


def test_create_first_admin_ignores_synthetic_local_user(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.auth import User

    # A fresh personal-mode DB carries the synthetic `local` admin. The wizard
    # must still be able to create the first real admin over it.
    db_session.add(
        User(
            id="local",
            email="local@openlia.local",
            display_name="Local",
            password_hash=None,
            is_admin=True,
            is_disabled=False,
        )
    )
    db_session.commit()

    admin = svc.create_first_admin(db_session, "admin@corp.com", "S3curePass12!", "Admin")
    db_session.commit()

    assert admin.is_admin is True
    assert admin.id != "local"


def test_create_first_admin_rejects_when_real_admin_exists(
    create_tables, db_session: Session
) -> None:
    svc.create_first_admin(db_session, "a@corp.com", "S3curePass12!", "A")
    db_session.commit()

    with pytest.raises(svc.AdminExistsError):
        svc.create_first_admin(db_session, "b@corp.com", "S3curePass12!", "B")


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


def test_set_mode_persists_both_columns(create_tables, db_session: Session) -> None:
    """Cross-plan contract: set_mode writes both ConfigStore + WizardState.mode."""
    from openlia_server.db.models.infrastructure import ConfigStore, WizardState

    svc.set_mode(db_session, "company")
    db_session.commit()

    cs_row = db_session.get(ConfigStore, "wizard.mode")
    state = db_session.get(WizardState, 1)
    assert cs_row is not None and cs_row.value == "company"
    assert state is not None and state.mode == "company"
