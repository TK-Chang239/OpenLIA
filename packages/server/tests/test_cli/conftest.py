"""CLI test fixtures + sys.path helper so sibling test modules can share
local imports under --import-mode=importlib (no tests.* package)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point OPENLIA_HOME at a fresh tmp dir so secret.key auto-creation
    and DB resolution don't touch the real ~/.openlia."""
    home = tmp_path / "openlia_home"
    home.mkdir()
    monkeypatch.setenv("OPENLIA_HOME", str(home))
    return home


@pytest.fixture
def cli_secret_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    raw = b"\x11" * 32
    monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
    from openlia_server.db import crypto

    crypto._reset_cached_key()
    yield raw
    crypto._reset_cached_key()


@pytest.fixture
def cli_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path}/cli.db"
    monkeypatch.setenv("OPENLIA_DB_URL", url)
    return url


@pytest.fixture
def cli_engine(cli_db_url: str):
    """Configure the engine once per test + create every table. Yields the
    engine and disposes at teardown so state doesn't leak across tests."""
    from openlia_server.db import session as session_mod
    from openlia_server.db.base import Base

    session_mod.dispose_engine()
    engine = session_mod.configure_engine(cli_db_url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        session_mod.dispose_engine()


@pytest.fixture
def cli_session(cli_engine):
    from openlia_server.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def cli_runner():
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def company_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENLIA_MODE", "company")


@pytest.fixture
def personal_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
