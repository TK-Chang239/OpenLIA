"""Alembic round-trip for the Morning Briefing v2 schema migration."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

_MB_TABLES = {
    "report_mb",
    "report_mb_sections",
    "report_mb_charts",
    "report_mb_citations",
    "report_mb_tool_call_log",
    "report_mb_templates",
    "report_mb_instructions",
}

# Revision immediately before the MB v2 migration. Downgrading here reverts
# the whole MB v2 stack and restores ``mb_user_configs``.
_PRE_MB_REVISION = "eu_batch_state_0602"


def _alembic_config(db_path: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        "packages/server/src/openlia_server/db/migrations",
    )
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_migration_upgrade_creates_mb_tables_and_seeds_default(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    names = set(insp.get_table_names())

    # All seven report_mb* tables exist.
    assert _MB_TABLES <= names

    # mb_schedules gained the config-binding columns.
    mb_sched_cols = {c["name"] for c in insp.get_columns("mb_schedules")}
    assert "template_id" in mb_sched_cols
    assert {
        "instructions_id",
        "enabled_connectors",
        "provider_kind",
        "model",
        "language",
        "length",
        "reasoning_effort",
        "web_search",
    } <= mb_sched_cols

    # repo_items gained the MB pointer.
    repo_cols = {c["name"] for c in insp.get_columns("repo_items")}
    assert "mb_v2_report_id" in repo_cols

    # The old per-user config table is gone.
    assert "mb_user_configs" not in names

    # report_mb has no ticker / fiscal_date columns.
    report_mb_cols = {c["name"] for c in insp.get_columns("report_mb")}
    assert "ticker" not in report_mb_cols
    assert "fiscal_date" not in report_mb_cols
    assert {"trigger_kind", "schedule_id", "instructions_id"} <= report_mb_cols

    # Builtin mb_default template seeded.
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, name, is_builtin FROM report_mb_templates WHERE id = 'mb_default'")
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "mb_default"
    assert bool(rows[0][2]) is True


def test_migration_downgrade_reverses(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _PRE_MB_REVISION)

    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    names = set(insp.get_table_names())

    # MB v2 tables dropped, original config table restored.
    assert not (_MB_TABLES & names)
    assert "mb_user_configs" in names

    # repo_items MB pointer removed.
    repo_cols = {c["name"] for c in insp.get_columns("repo_items")}
    assert "mb_v2_report_id" not in repo_cols

    # mb_schedules config-binding columns removed.
    mb_sched_cols = {c["name"] for c in insp.get_columns("mb_schedules")}
    assert "template_id" not in mb_sched_cols
    assert "enabled_connectors" not in mb_sched_cols
