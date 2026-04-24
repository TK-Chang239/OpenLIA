import uuid

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import PtPreset
from openlia_server.services.pt_config import PtConfigService


@pytest.fixture()
def user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email="p@x",
        display_name="U",
        password_hash="x",
        is_admin=False,
        must_change_password=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_seed_inserts_fifteen_shipped_rows(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.seed_shipped_presets()
    rows = db_session.query(PtPreset).filter_by(is_shipped=True, user_id=None).all()
    assert len(rows) == 15
    names = {r.name for r in rows}
    assert {
        "oil::report_defaults",
        "fed_language::volatility_adjusted",
        "diplomacy::ma_relative",
    } <= names


def test_seed_is_idempotent(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.seed_shipped_presets()
    svc.seed_shipped_presets()
    assert db_session.query(PtPreset).filter_by(is_shipped=True, user_id=None).count() == 15


def test_create_and_list_user_preset(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.seed_shipped_presets()
    svc.get_or_create_for_user(user.id)
    p = svc.create_preset(user.id, name="my-setup", description="custom")
    assert p.user_id == user.id
    assert p.is_shipped is False
    listed = svc.list_presets(user.id)
    shipped = [r for r in listed if r.is_shipped]
    user_rows = [r for r in listed if not r.is_shipped]
    assert len(user_rows) == 1 and user_rows[0].name == "my-setup"
    assert len(shipped) >= 15


def test_delete_user_preset(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    p = svc.create_preset(user.id, name="tmp", description=None)
    svc.delete_preset(user.id, p.id)
    assert db_session.query(PtPreset).filter_by(id=p.id).one_or_none() is None


def test_apply_shipped_preset_overwrites_panel_only(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.seed_shipped_presets()
    svc.get_or_create_for_user(user.id)
    oil_preset = (
        db_session.query(PtPreset).filter_by(name="oil::ma_relative", is_shipped=True).one()
    )
    updated = svc.apply_preset(user.id, oil_preset.id)
    oil = next(p for p in updated.panel_config if p["panel_id"] == "oil")
    assert oil["streak_condition"] == "price > ma200 * ma_multiplier"
    wage = next(p for p in updated.panel_config if p["panel_id"] == "wage_growth")
    assert wage["params"]["wage_threshold_red"] == 0.5
