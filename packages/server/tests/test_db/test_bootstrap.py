from __future__ import annotations

import os
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


def test_ensure_openlia_dir_creates_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("HOME", str(tmp_path))
    path = bootstrap.ensure_openlia_dir()

    assert path == tmp_path / ".openlia"
    assert path.is_dir()


def test_ensure_openlia_dir_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
