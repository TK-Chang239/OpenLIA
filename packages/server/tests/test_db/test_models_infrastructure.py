from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.infrastructure  # noqa: F401
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_wizard_state_singleton(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import WizardState

    db_session.add(WizardState(id=1))
    db_session.commit()

    db_session.add(WizardState(id=2))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_wizard_state_defaults(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import WizardState

    w = WizardState(id=1)
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)

    assert w.status == "not_started"
    assert w.current_step == "mode"
    assert w.completed_steps == []
    assert w.step_data == {}
    assert w.active_session_token is None


def test_wizard_state_accepts_named_step_and_session_token(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.infrastructure import WizardState

    w = WizardState(
        id=1,
        current_step="providers",
        completed_steps=["mode", "account", "models"],
        active_session_token="abc123",
    )
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)

    assert w.current_step == "providers"
    assert w.completed_steps == ["mode", "account", "models"]
    assert w.active_session_token == "abc123"


def test_config_store_roundtrip(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    row = ConfigStore(key="wizard.completed", value=False)
    db_session.add(row)
    db_session.commit()

    db_session.refresh(row)
    assert row.value is False
    assert row.key == "wizard.completed"


def test_config_store_key_primary(create_tables) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    pk_cols = {c.name for c in ConfigStore.__table__.primary_key}
    assert pk_cols == {"key"}
