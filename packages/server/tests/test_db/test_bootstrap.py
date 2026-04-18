from __future__ import annotations

from pathlib import Path

import pytest


def test_resolve_db_url_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("OPENLIA_DB_URL", "sqlite:///tmp/explicit.db")
    assert bootstrap.resolve_db_url() == "sqlite:///tmp/explicit.db"


def test_resolve_db_url_defaults_to_home_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.delenv("OPENLIA_DB_URL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    expected = f"sqlite:///{tmp_path / '.openlia' / 'openlia.db'}"
    assert bootstrap.resolve_db_url() == expected


def test_ensure_openlia_dir_creates_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("HOME", str(tmp_path))
    path = bootstrap.ensure_openlia_dir()

    assert path == tmp_path / ".openlia"
    assert path.is_dir()


def test_ensure_openlia_dir_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("HOME", str(tmp_path))
    bootstrap.ensure_openlia_dir()
    bootstrap.ensure_openlia_dir()  # must not raise

    assert (tmp_path / ".openlia").is_dir()


def test_resolve_db_url_expands_tilde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", "sqlite:///~/custom.db")

    assert bootstrap.resolve_db_url() == f"sqlite:///{tmp_path / 'custom.db'}"


def test_bootstrap_creates_local_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openlia_server.db import bootstrap
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/bootstrap.db")

    bootstrap.bootstrap()

    with session_mod.SessionLocal() as s:
        local = s.get(User, "local")
        assert local is not None
        assert local.email == "local@openlia.local"
        assert local.is_admin is True
        assert local.password_hash is None
        assert local.display_name == "Local"

    session_mod.dispose_engine()


def test_bootstrap_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openlia_server.db import bootstrap
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.infrastructure import ConfigStore

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/idempotent.db")

    bootstrap.bootstrap()
    with session_mod.SessionLocal() as s:
        first_instance_id = s.get(ConfigStore, "system.instance_id").value
    session_mod.dispose_engine()

    bootstrap.bootstrap()
    with session_mod.SessionLocal() as s:
        count = s.query(User).filter_by(id="local").count()
        assert count == 1
        second_instance_id = s.get(ConfigStore, "system.instance_id").value
    session_mod.dispose_engine()

    assert first_instance_id == second_instance_id


def test_bootstrap_seeds_config_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openlia_server.db import bootstrap
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.infrastructure import ConfigStore

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/configstore.db")

    bootstrap.bootstrap()

    with session_mod.SessionLocal() as s:
        wc = s.get(ConfigStore, "wizard.completed")
        assert wc is not None
        assert wc.value is False

        iid = s.get(ConfigStore, "system.instance_id")
        assert iid is not None
        assert isinstance(iid.value, str)
        assert len(iid.value) == 36

    session_mod.dispose_engine()


def test_bootstrap_runs_migrations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from openlia_server.db import bootstrap
    from sqlalchemy import create_engine, inspect

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/fresh.db")

    bootstrap.bootstrap()

    eng = create_engine(f"sqlite:///{tmp_path}/fresh.db")
    table_names = set(inspect(eng).get_table_names())
    assert "users" in table_names
    assert "alembic_version" in table_names
