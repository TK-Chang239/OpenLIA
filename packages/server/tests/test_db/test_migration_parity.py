"""Frozen-schema parity + single-head tests for the Alembic chain.

Covers audit items NEW-1b-08 (metadata vs. Alembic head) and NEW-1b-09
(step-by-step catch-up migration round-trip), plus a single-head guard.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import MetaData, create_engine, inspect, text

REPO_ROOT_SERVER = Path(__file__).resolve().parents[2]  # packages/server


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    merged["OPENLIA_DB_URL"] = db_url
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT_SERVER,
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def test_single_alembic_head() -> None:
    """Guard against accidental branched migration graph."""
    proc = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=REPO_ROOT_SERVER,
        capture_output=True,
        text=True,
        check=True,
    )
    heads = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(heads) == 1, f"expected exactly one head, got {heads!r}"


def test_metadata_matches_alembic_head(tmp_path: Path) -> None:
    """ORM `Base.metadata` and the live-migrated DB must agree on column sets."""
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.db.base import Base

    db_file = tmp_path / "parity.db"
    db_url = f"sqlite:///{db_file}"

    proc = _run_alembic(["upgrade", "head"], db_url)
    assert proc.returncode == 0, f"alembic upgrade failed: {proc.stderr}"

    engine = create_engine(db_url)
    reflected = MetaData()
    reflected.reflect(bind=engine)

    orm_tables = set(Base.metadata.tables.keys())
    db_tables = set(reflected.tables.keys())
    db_tables.discard("alembic_version")
    # The SQLite FTS5 shadow of graph_artifact_summaries (slice 10
    # hybrid retrieval) creates one virtual table plus four internal
    # auxiliary tables that aren't modeled in the ORM by design — they
    # are managed by SQLite itself.
    _FTS_SHADOW = {
        "graph_artifact_summaries_fts",
        "graph_artifact_summaries_fts_config",
        "graph_artifact_summaries_fts_data",
        "graph_artifact_summaries_fts_docsize",
        "graph_artifact_summaries_fts_idx",
    }
    db_tables -= _FTS_SHADOW
    # Tables of the removed equity-research engines (v1/v2/v2.2/v2.3). The
    # ORM models were deleted with the engines but the tables are retained
    # on disk for rollback / data preservation (see env._LEGACY_ORPHANED_TABLES).
    _LEGACY_ORPHANED = {
        "er_v2_model_assignments",
        "er_v2_3_model_assignments",
        "er_v2_3_run_state",
        "er_user_configs",
        "er_templates",
    }
    db_tables -= _LEGACY_ORPHANED

    assert orm_tables == db_tables, (
        f"Missing from DB: {orm_tables - db_tables}; Extra in DB: {db_tables - orm_tables}"
    )

    for table_name in sorted(orm_tables):
        orm_cols = {c.name for c in Base.metadata.tables[table_name].columns}
        db_cols = {c.name for c in reflected.tables[table_name].columns}
        assert orm_cols == db_cols, (
            f"Column mismatch on {table_name}: "
            f"missing {orm_cols - db_cols}, extra {db_cols - orm_cols}"
        )
    engine.dispose()


def test_mr_dashboard_state_schedule_cols_step(tmp_path: Path) -> None:
    """Catch-up migration adds the two schedule columns and cleanly reverses."""
    db_file = tmp_path / "step_mr.db"
    db_url = f"sqlite:///{db_file}"

    proc = _run_alembic(["upgrade", "20260423_2100_mb"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mr_dashboard_state")}
    assert "assessment_schedule" not in cols
    assert "last_assessment_at" not in cols
    engine.dispose()

    proc = _run_alembic(["upgrade", "20260424_0001_mr"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mr_dashboard_state")}
    assert "assessment_schedule" in cols
    assert "last_assessment_at" in cols
    engine.dispose()

    proc = _run_alembic(["downgrade", "20260423_2100_mb"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("mr_dashboard_state")}
    assert "assessment_schedule" not in cols
    assert "last_assessment_at" not in cols
    engine.dispose()


@pytest.mark.parametrize(
    ("table", "column", "expected"),
    [
        ("pt_presets", "is_shipped", 0),
        ("mb_schedules", "is_enabled", 1),
        ("eu_schedules", "is_enabled", 1),
    ],
)
def test_boolean_server_defaults(tmp_path: Path, table: str, column: str, expected: int) -> None:
    """NEW-1b-02, NEW-1b-03: omitting the column in a raw SQL insert yields
    the spec default."""
    db_file = tmp_path / f"bool_{table}.db"
    db_url = f"sqlite:///{db_file}"

    proc = _run_alembic(["upgrade", "head"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        if table == "pt_presets":
            conn.execute(
                text(
                    "INSERT INTO pt_presets (id, name, panel_config, composite_settings, "
                    "created_at, updated_at) "
                    "VALUES ('p1', 'np', '[]', '{}', datetime('now'), datetime('now'))"
                )
            )
        elif table in {"mb_schedules", "eu_schedules"}:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, display_name, is_admin, is_disabled, "
                    "must_change_password, failed_login_attempts, created_at, updated_at) "
                    "VALUES ('u1', 'u@x', 'U', 0, 0, 0, 0, datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    f"INSERT INTO {table} (id, user_id, time, timezone, days_of_week) "
                    "VALUES ('s1', 'u1', '07:00', 'UTC', '[\"mon\"]')"
                )
            )
        actual = conn.execute(text(f"SELECT {column} FROM {table}")).scalar_one()
    engine.dispose()
    assert int(actual) == expected


@pytest.mark.parametrize(
    ("table", "column", "expected"),
    [
        ("pt_user_configs", "panel_config", "[]"),
        ("pt_user_configs", "composite_settings", "{}"),
        ("rs_user_config", "metric_settings", "{}"),
        ("rs_user_config", "filter_presets", "[]"),
    ],
)
def test_json_server_defaults(tmp_path: Path, table: str, column: str, expected: str) -> None:
    """NEW-1b-04: omitting JSON columns in raw SQL insert yields '{}' or '[]'."""
    db_file = tmp_path / f"json_{table}_{column}.db"
    db_url = f"sqlite:///{db_file}"

    proc = _run_alembic(["upgrade", "head"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.execute(
            text(
                "INSERT INTO users (id, email, display_name, is_admin, is_disabled, "
                "must_change_password, failed_login_attempts, created_at, updated_at) "
                "VALUES ('u1', 'u@x', 'U', 0, 0, 0, 0, datetime('now'), datetime('now'))"
            )
        )
        if table == "pt_user_configs":
            conn.execute(
                text(
                    "INSERT INTO pt_user_configs (id, user_id, created_at, updated_at) "
                    "VALUES ('c1', 'u1', datetime('now'), datetime('now'))"
                )
            )
        elif table == "mr_dashboard_state":
            conn.execute(
                text(
                    "INSERT INTO mr_dashboard_state (id, user_id, dashboard, updated_at) "
                    "VALUES ('m1', 'u1', 'debt_cycle', datetime('now'))"
                )
            )
        elif table == "rs_user_config":
            conn.execute(
                text(
                    "INSERT INTO rs_user_config (id, user_id, active_tab, "
                    "refresh_interval_minutes, updated_at) "
                    "VALUES ('r1', 'u1', 'overview', 60, datetime('now'))"
                )
            )
        actual = conn.execute(text(f"SELECT {column} FROM {table}")).scalar_one()
    engine.dispose()
    # SQLite returns the stored text as-is.
    assert actual == expected
