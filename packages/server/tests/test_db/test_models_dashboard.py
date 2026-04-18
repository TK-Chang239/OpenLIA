"""Verifies the 7 dashboard tables in §7 of database-design.md:
  pt_user_configs, pt_presets, mr_dashboard_state, mr_assessment_cache,
  rs_user_config, rs_snapshots, fe_saved_formulas.

Exercised against a tmp SQLite file via Base.metadata.create_all.
Alembic round-trip is tested in Task 4 of this plan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.auth
    import openlia_server.db.models.dashboard  # noqa: F401 — register models
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _make_user(db_session: Session, user_id: str = "u1") -> None:
    from openlia_server.db.models.auth import User

    db_session.add(User(id=user_id, email=f"{user_id}@example.com", display_name=user_id))
    db_session.commit()


# ---------- pt_user_configs ----------


def test_pt_user_configs_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import PtUserConfig

    cols = {c.name: c for c in PtUserConfig.__table__.columns}
    expected = {
        "id",
        "user_id",
        "active_preset_id",
        "panel_config",
        "composite_settings",
        "created_at",
        "updated_at",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].unique is True
    assert cols["active_preset_id"].nullable is True


def test_pt_user_configs_one_per_user(create_tables, db_session: Session) -> None:
    """UNIQUE(user_id) — one config row per user."""
    from openlia_server.db.models.dashboard import PtUserConfig

    _make_user(db_session)
    db_session.add(PtUserConfig(id="c1", user_id="u1", panel_config=[], composite_settings={}))
    db_session.commit()

    db_session.add(PtUserConfig(id="c2", user_id="u1", panel_config=[], composite_settings={}))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_pt_user_configs_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.dashboard import PtUserConfig

    _make_user(db_session)
    db_session.add(PtUserConfig(id="c1", user_id="u1", panel_config=[], composite_settings={}))
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(PtUserConfig)).scalar_one_or_none() is None


def test_pt_user_configs_active_preset_set_null_on_preset_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.dashboard import PtPreset, PtUserConfig

    _make_user(db_session)
    p = PtPreset(id="p1", user_id="u1", name="My preset", panel_config=[], composite_settings={})
    c = PtUserConfig(
        id="c1",
        user_id="u1",
        active_preset_id="p1",
        panel_config=[],
        composite_settings={},
    )
    db_session.add_all([p, c])
    db_session.commit()

    db_session.delete(p)
    db_session.commit()

    db_session.expire_all()
    fresh = db_session.get(PtUserConfig, "c1")
    assert fresh.active_preset_id is None


# ---------- pt_presets ----------


def test_pt_presets_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import PtPreset

    cols = {c.name: c for c in PtPreset.__table__.columns}
    expected = {
        "id",
        "user_id",
        "name",
        "description",
        "is_shipped",
        "panel_config",
        "composite_settings",
        "created_at",
        "updated_at",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].nullable is True  # shipped presets have NULL user_id
    assert cols["is_shipped"].default.arg is False


def test_pt_presets_user_name_unique(create_tables, db_session: Session) -> None:
    """UNIQUE(user_id, name) — two presets with same name for same user rejected."""
    from openlia_server.db.models.dashboard import PtPreset

    _make_user(db_session)
    db_session.add(
        PtPreset(id="p1", user_id="u1", name="dup", panel_config=[], composite_settings={})
    )
    db_session.commit()

    db_session.add(
        PtPreset(id="p2", user_id="u1", name="dup", panel_config=[], composite_settings={})
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_pt_presets_shipped_partial_unique(create_tables, db_session: Session) -> None:
    """Partial unique: UNIQUE(name) WHERE user_id IS NULL — shipped preset names
    are globally unique among shipped rows; two user presets with the same name
    (across different users or with a user) must not fail the partial index."""
    from openlia_server.db.models.dashboard import PtPreset

    db_session.add(
        PtPreset(
            id="s1",
            user_id=None,
            name="Crisis",
            is_shipped=True,
            panel_config=[],
            composite_settings={},
        )
    )
    db_session.commit()

    db_session.add(
        PtPreset(
            id="s2",
            user_id=None,
            name="Crisis",
            is_shipped=True,
            panel_config=[],
            composite_settings={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_pt_presets_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.dashboard import PtPreset

    _make_user(db_session)
    db_session.add(
        PtPreset(id="p1", user_id="u1", name="mine", panel_config=[], composite_settings={})
    )
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(PtPreset)).scalar_one_or_none() is None


# ---------- mr_dashboard_state ----------


def test_mr_dashboard_state_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import MrDashboardState

    cols = {c.name: c for c in MrDashboardState.__table__.columns}
    expected = {
        "id",
        "user_id",
        "dashboard",
        "view_config",
        "threshold_overrides",
        "updated_at",
    }
    assert set(cols.keys()) == expected


def test_mr_dashboard_state_user_dashboard_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.dashboard import MrDashboardState

    _make_user(db_session)
    db_session.add(
        MrDashboardState(
            id="m1",
            user_id="u1",
            dashboard="debt_cycle",
            view_config={},
            threshold_overrides={},
        )
    )
    db_session.commit()

    db_session.add(
        MrDashboardState(
            id="m2",
            user_id="u1",
            dashboard="debt_cycle",
            view_config={},
            threshold_overrides={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------- mr_assessment_cache ----------


def test_mr_assessment_cache_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import MrAssessmentCache

    cols = {c.name: c for c in MrAssessmentCache.__table__.columns}
    expected = {
        "id",
        "dashboard",
        "assessment_type",
        "input_hash",
        "result",
        "model_ref",
        "token_usage",
        "generated_at",
        "expires_at",
    }
    assert set(cols.keys()) == expected


def test_mr_assessment_cache_key_unique(create_tables, db_session: Session) -> None:
    """UNIQUE(dashboard, assessment_type, input_hash) — cache hit discriminator."""
    from openlia_server.db.models.dashboard import MrAssessmentCache

    now = datetime.now(UTC)
    row = MrAssessmentCache(
        id="a1",
        dashboard="debt_cycle",
        assessment_type="t4",
        input_hash="hash-1",
        result={},
        model_ref="gpt-4",
        generated_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(row)
    db_session.commit()

    dup = MrAssessmentCache(
        id="a2",
        dashboard="debt_cycle",
        assessment_type="t4",
        input_hash="hash-1",
        result={},
        model_ref="gpt-4",
        generated_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------- rs_user_config ----------


def test_rs_user_config_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import RsUserConfig

    cols = {c.name: c for c in RsUserConfig.__table__.columns}
    expected = {
        "id",
        "user_id",
        "active_tab",
        "metric_settings",
        "filter_presets",
        "refresh_interval_minutes",
        "updated_at",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].unique is True
    assert cols["refresh_interval_minutes"].default.arg == 60


def test_rs_user_config_one_per_user(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.dashboard import RsUserConfig

    _make_user(db_session)
    db_session.add(RsUserConfig(id="r1", user_id="u1"))
    db_session.commit()

    db_session.add(RsUserConfig(id="r2", user_id="u1"))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------- rs_snapshots ----------


def test_rs_snapshots_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import RsSnapshot

    cols = {c.name: c for c in RsSnapshot.__table__.columns}
    expected = {
        "id",
        "ticker",
        "snapshot_data",
        "source_breakdown",
        "captured_at",
    }
    assert set(cols.keys()) == expected


def test_rs_snapshots_has_ticker_captured_index(create_tables) -> None:
    """ix_rs_snapshots_ticker_captured must exist on (ticker, captured_at)."""
    from openlia_server.db.models.dashboard import RsSnapshot

    names = {ix.name for ix in RsSnapshot.__table__.indexes}
    assert "ix_rs_snapshots_ticker_captured" in names


# ---------- fe_saved_formulas ----------


def test_fe_saved_formulas_columns(create_tables) -> None:
    from openlia_server.db.models.dashboard import FeSavedFormula

    cols = {c.name: c for c in FeSavedFormula.__table__.columns}
    expected = {
        "id",
        "user_id",
        "name",
        "expression",
        "description",
        "department_scope",
        "created_at",
        "updated_at",
    }
    assert set(cols.keys()) == expected


def test_fe_saved_formulas_user_name_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.dashboard import FeSavedFormula

    _make_user(db_session)
    db_session.add(
        FeSavedFormula(
            id="f1",
            user_id="u1",
            name="dup",
            expression="x + 1",
        )
    )
    db_session.commit()

    db_session.add(
        FeSavedFormula(
            id="f2",
            user_id="u1",
            name="dup",
            expression="x + 2",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_fe_saved_formulas_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.dashboard import FeSavedFormula

    _make_user(db_session)
    db_session.add(
        FeSavedFormula(
            id="f1",
            user_id="u1",
            name="mine",
            expression="x + 1",
        )
    )
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(FeSavedFormula)).scalar_one_or_none() is None


def test_dashboard_and_scheduler_registered_via_models_init() -> None:
    """Importing `openlia_server.db.models` alone must register every
    dashboard + scheduler table on Base.metadata. Alembic's env.py relies
    on this — it imports the package, not each submodule."""
    import importlib
    import openlia_server.db.models as models_pkg

    importlib.reload(models_pkg)

    from openlia_server.db.base import Base

    registered = set(Base.metadata.tables.keys())
    required = {
        # Dashboard
        "pt_user_configs", "pt_presets",
        "mr_dashboard_state", "mr_assessment_cache",
        "rs_user_config", "rs_snapshots",
        "fe_saved_formulas",
        # Scheduler + notifications
        "mb_schedules", "eu_schedules", "job_runs", "user_notifications",
    }
    missing = required - registered
    assert missing == set(), f"Not registered via models/__init__.py: {missing}"
