from __future__ import annotations

import openlia_server.db.models.register_all  # noqa: F401  (register all tables)
from alembic import command
from alembic.config import Config
from openlia_server.db.base import Base
from sqlalchemy import create_engine, inspect, text

_EU_V2_TABLES = {
    "report_eu",
    "report_eu_sections",
    "report_eu_charts",
    "report_eu_citations",
    "report_eu_tool_call_log",
    "report_eu_templates",
    "eu_v2_watchlist",
    "eu_v2_earnings_schedule",
    "eu_v2_settings",
}


def _alembic_config(db_path: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        "packages/server/src/openlia_server/db/migrations",
    )
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_create_all_builds_eu_v2_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    Base.metadata.create_all(engine)
    names = set(inspect(engine).get_table_names())
    assert _EU_V2_TABLES <= names


def test_migration_upgrade_creates_tables_and_seeds_default(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    assert _EU_V2_TABLES <= names

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, name, is_builtin FROM report_eu_templates WHERE id = 'eu_default'")
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "eu_default"
    assert bool(rows[0][2]) is True


def test_migration_downgrade_drops_tables(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")

    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    assert not (_EU_V2_TABLES & names)
