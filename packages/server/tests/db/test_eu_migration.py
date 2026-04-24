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


def test_migration_creates_eu_watchlist(tmp_path, monkeypatch) -> None:
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "eu_watchlist" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("eu_watchlist")}
    assert {
        "id",
        "user_id",
        "ticker",
        "company_name",
        "next_earnings_date",
        "release_timing",
    } <= cols


def test_migration_creates_eu_user_configs(tmp_path, monkeypatch) -> None:
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "eu_user_configs" in insp.get_table_names()


def test_migration_has_unique_on_user_ticker(tmp_path, monkeypatch) -> None:
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    uqs = insp.get_unique_constraints("eu_watchlist")
    names = {uq["name"] for uq in uqs}
    assert "uq_eu_watchlist_user_ticker" in names


def test_migration_downgrade_drops_tables(tmp_path, monkeypatch) -> None:
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "eu_watchlist" not in insp.get_table_names()
    assert "eu_user_configs" not in insp.get_table_names()
