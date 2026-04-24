from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_config(db_path: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        "packages/server/src/openlia_server/db/migrations",
    )
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_migration_creates_mb_user_configs(tmp_path, monkeypatch) -> None:
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "mb_user_configs" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("mb_user_configs")}
    assert {
        "id",
        "user_id",
        "report_length",
        "enabled_section_ids",
        "section_topics",
        "custom_sections",
        "reference_portfolio",
        "created_at",
        "updated_at",
    } <= cols


def test_migration_has_unique_on_user(tmp_path, monkeypatch) -> None:
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    uqs = insp.get_unique_constraints("mb_user_configs")
    has_uq = any("user_id" in uq.get("column_names", []) for uq in uqs)
    idxs = insp.get_indexes("mb_user_configs")
    has_unique_idx = any(i.get("unique") and i.get("column_names") == ["user_id"] for i in idxs)
    assert has_uq or has_unique_idx


def test_migration_downgrade_drops_table(tmp_path, monkeypatch) -> None:
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "mb_user_configs" not in insp.get_table_names()
