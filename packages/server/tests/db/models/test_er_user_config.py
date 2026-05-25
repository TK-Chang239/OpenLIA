import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import ErUserConfig
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_er_user_config_columns(create_tables):
    insp = inspect(ErUserConfig)
    cols = {c.name: c for c in insp.columns}
    assert set(cols) >= {
        "id",
        "user_id",
        "report_mode",
        "report_length",
        "sections_by_mode",
        "custom_sections_by_mode",
        "created_at",
        "updated_at",
    }
    assert cols["user_id"].unique is True


def test_er_user_config_one_per_user(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()

    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_initiation",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c2",
            user_id="u1",
            report_mode="stock_update",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_er_user_config_cascade_on_user_delete(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_update",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    db_session.commit()

    db_session.query(User).filter(User.id == "u1").delete()
    db_session.commit()

    assert db_session.query(ErUserConfig).count() == 0


def test_er_user_config_report_mode_check_constraint(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="bogus_mode",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_er_user_config_report_length_check_constraint(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_update",
            report_length="verbose",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_er_user_config_reasoning_effort_column_nullable(create_tables, db_session):
    """Column accepts NULL (the default for rows written before the
    migration) and the three pill values."""
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_initiation",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
            report_reasoning_effort=None,
        )
    )
    db_session.commit()
    row = db_session.query(ErUserConfig).filter(ErUserConfig.user_id == "u1").one()
    assert row.report_reasoning_effort is None


def test_er_user_config_reasoning_effort_check_constraint(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_initiation",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
            report_reasoning_effort="extreme",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
