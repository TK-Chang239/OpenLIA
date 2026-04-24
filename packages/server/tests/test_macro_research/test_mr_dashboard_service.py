from __future__ import annotations

import pytest
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.services.mr_dashboard import MRDashboardService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def factory():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, expire_on_commit=False)
    with S() as s:
        s.add(User(id="u-1", email="a@b", password_hash="x", display_name="A"))
        s.commit()
    return S


def test_get_or_create_creates_row(factory) -> None:
    svc = MRDashboardService(session_factory=factory)
    row = svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    assert row.id
    assert row.view_config == {}


def test_update_config_persists(factory) -> None:
    svc = MRDashboardService(session_factory=factory)
    svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    svc.update_config(
        user_id="u-1",
        dashboard="debt_cycle",
        view_config={"auto_refresh": "5m"},
        threshold_overrides={"debt_gdp_warn": 95.0},
    )
    row = svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    assert row.view_config == {"auto_refresh": "5m"}
    assert row.threshold_overrides == {"debt_gdp_warn": 95.0}


def test_list_for_user(factory) -> None:
    svc = MRDashboardService(session_factory=factory)
    svc.get_or_create(user_id="u-1", dashboard="debt_cycle")
    svc.get_or_create(user_id="u-1", dashboard="four_seasons")
    rows = svc.list_for_user(user_id="u-1")
    assert {r.dashboard for r in rows} == {"debt_cycle", "four_seasons"}
