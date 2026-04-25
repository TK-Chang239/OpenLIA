"""Tests for `bootstrap.resolve_db_url` (Plan 1a P1-1a-06 / P1-1a-09)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia_server.db import bootstrap  # submodule


def test_resolve_db_url_absolute_path_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    explicit = tmp_path / "explicit.db"
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{explicit}")
    monkeypatch.delenv("OPENLIA_HOME", raising=False)

    assert bootstrap.resolve_db_url() == f"sqlite:///{explicit}"


def test_resolve_db_url_expands_tilde_in_sqlite_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", "sqlite:///~/my.db")

    expected = str(tmp_path / "my.db")
    assert bootstrap.resolve_db_url() == f"sqlite:///{expected}"


def test_resolve_db_url_non_sqlite_passes_through_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENLIA_DB_URL", "postgresql+psycopg://user:pw@host/db")

    assert bootstrap.resolve_db_url() == "postgresql+psycopg://user:pw@host/db"


def test_resolve_db_url_uses_openlia_home_when_db_url_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENLIA_DB_URL", raising=False)
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))

    url = bootstrap.resolve_db_url()
    assert url == f"sqlite:///{tmp_path / 'openlia.db'}"


def test_openlia_home_env_var_overrides_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))

    assert bootstrap.openlia_home() == tmp_path
