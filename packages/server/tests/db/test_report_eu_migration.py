from __future__ import annotations

import json

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
    "report_eu_instructions",
    "eu_v2_watchlist",
    "eu_v2_earnings_schedule",
    "eu_v2_settings",
}

# Last revision before the EU v2 stack. Downgrading here reverts every EU
# migration (tables + later additions like instructions), so the drop test
# stays correct as EU migrations accrue — a fixed ``-1`` only reverts the
# newest one.
_PRE_EU_REVISION = "c1e3a7d9f2b4"


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


def test_migration_data_migrates_enabled_provider_ids(tmp_path, monkeypatch):
    """A row with the old financial bool on maps to ``["eodhd"]``."""
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    # Upgrade only to the revision that still has the bool columns, seed a
    # row, then run the enabled_provider_ids migration over it.
    command.upgrade(cfg, "7f2a9c4be103")

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO eu_v2_settings "
                "(user_id, provider_kind, model, template_id, language, length, "
                " financial_enabled, calendar_enabled, web_search_enabled, "
                " created_at, updated_at) "
                "VALUES ('u-on', 'anthropic', 'm', 'eu_default', 'en', 'normal', "
                " 1, 0, 0, '2026-01-01', '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO eu_v2_settings "
                "(user_id, provider_kind, model, template_id, language, length, "
                " financial_enabled, calendar_enabled, web_search_enabled, "
                " created_at, updated_at) "
                "VALUES ('u-off', 'anthropic', 'm', 'eu_default', 'en', 'normal', "
                " 0, 0, 0, '2026-01-01', '2026-01-01')"
            )
        )

    command.upgrade(cfg, "898ac749e884")

    with engine.connect() as conn:
        on = conn.execute(
            text("SELECT enabled_provider_ids FROM eu_v2_settings WHERE user_id = 'u-on'")
        ).scalar_one()
        off = conn.execute(
            text("SELECT enabled_provider_ids FROM eu_v2_settings WHERE user_id = 'u-off'")
        ).scalar_one()
    assert json.loads(on) == ["eodhd"]
    assert json.loads(off) == []


def test_migration_downgrade_drops_tables(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _PRE_EU_REVISION)

    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    assert not (_EU_V2_TABLES & names)
