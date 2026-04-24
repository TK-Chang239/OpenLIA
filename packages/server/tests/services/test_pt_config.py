import uuid

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import PtUserConfig
from openlia_server.services.pt_config import PtConfigService


@pytest.fixture()
def user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email="pt@example.com",
        display_name="PT",
        password_hash="x",
        is_admin=False,
        must_change_password=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_get_or_create_seeds_defaults_on_first_call(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    cfg = svc.get_or_create_for_user(user.id)
    assert cfg.user_id == user.id
    panels = {p["panel_id"]: p for p in cfg.panel_config}
    assert set(panels.keys()) == {
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    }
    assert panels["oil"]["rules"][0]["status"] == "dark_red"
    assert cfg.composite_settings["mode"] == "count"
    assert cfg.composite_settings["red_threshold"] == 2


def test_get_or_create_idempotent(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    first = svc.get_or_create_for_user(user.id)
    second = svc.get_or_create_for_user(user.id)
    assert first.id == second.id
    assert db_session.query(PtUserConfig).filter_by(user_id=user.id).count() == 1


def test_update_config_replaces_panel_config(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    new_cfg = [
        {
            "panel_id": "oil",
            "rules": [{"status": "green", "formula": "true", "label": "Always green"}],
            "params": {"price_threshold": 999},
            "streak_condition": None,
            "manual_override": None,
            "milestone_date": None,
        }
    ]
    updated = svc.update_config(
        user.id,
        panel_config=new_cfg,
        composite_settings={"mode": "count", "red_threshold": 3},
    )
    assert updated.panel_config == new_cfg
    assert updated.composite_settings["red_threshold"] == 3
