import uuid

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services.pt_config import PtConfigService


@pytest.fixture()
def user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email="pe@x",
        display_name="U",
        password_hash="x",
        is_admin=False,
        must_change_password=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_export_emits_version_1_shape(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    payload = svc.export_config(user.id)
    assert payload["version"] == 1
    assert "panel_config" in payload and len(payload["panel_config"]) == 5
    assert "composite_settings" in payload


def _empty_panel(pid):
    return {
        "panel_id": pid,
        "rules": [],
        "params": {},
        "streak_condition": None,
        "manual_override": None,
        "milestone_date": None,
        "enabled": False,
    }


def test_import_overwrites_config(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    oil = _empty_panel("oil")
    oil["rules"] = [{"status": "green", "formula": "true", "label": "ok"}]
    oil["params"] = {"price_threshold": 1}
    oil["enabled"] = True
    new_payload = {
        "version": 1,
        "panel_config": [
            oil,
            _empty_panel("inflation"),
            _empty_panel("fed_language"),
            _empty_panel("wage_growth"),
            _empty_panel("diplomacy"),
        ],
        "composite_settings": {"mode": "count", "red_threshold": 4},
    }
    updated = svc.import_config(user.id, new_payload)
    assert updated.composite_settings["red_threshold"] == 4
    got_oil = next(p for p in updated.panel_config if p["panel_id"] == "oil")
    assert got_oil["params"]["price_threshold"] == 1


def test_import_rejects_unknown_version(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    with pytest.raises(ValueError, match="unsupported PT config version"):
        svc.import_config(
            user.id,
            {"version": 2, "panel_config": [], "composite_settings": {}},
        )


def test_import_requires_all_five_panels(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    with pytest.raises(ValueError, match="panel_config must contain all 5 panels"):
        svc.import_config(
            user.id,
            {"version": 1, "panel_config": [], "composite_settings": {}},
        )
