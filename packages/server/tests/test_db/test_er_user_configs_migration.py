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


def test_er_user_configs_created_at_head(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "er_user_configs" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("er_user_configs")}
    assert cols >= {
        "id",
        "user_id",
        "report_mode",
        "report_length",
        "sections_by_mode",
        "custom_sections_by_mode",
        "created_at",
        "updated_at",
    }


def test_er_user_configs_downgrade_drops_table(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db}")
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "er_user_configs" not in insp.get_table_names()
