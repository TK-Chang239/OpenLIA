"""bootstrap() must leave the DB at the latest Alembic head."""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia_server.db import bootstrap as bootstrap_module
from openlia_server.db import session as session_mod
from sqlalchemy import text


def _latest_revision() -> str:
    versions_dir = Path(bootstrap_module.__file__).parent / "migrations" / "versions"
    revisions: dict[str, str | None] = {}  # rev_id -> down_revision
    for path in versions_dir.glob("*.py"):
        text_body = path.read_text()
        rev_id: str | None = None
        down_rev: str | None = None
        for line in text_body.splitlines():
            stripped = line.strip()
            if stripped.startswith("revision:") and rev_id is None:
                # Match: `revision: str = "..."`
                rev_id = stripped.split('"')[1] if '"' in stripped else None
            elif stripped.startswith("down_revision:"):
                if '"' in stripped:
                    down_rev = stripped.split('"')[1]
                else:
                    down_rev = None
        if rev_id:
            revisions[rev_id] = down_rev
    if not revisions:
        raise AssertionError("no migration revisions discovered")
    parents = {down for down in revisions.values() if down}
    heads = [rev for rev in revisions if rev not in parents]
    assert len(heads) == 1, f"expected one head, found {heads}"
    return heads[0]


def test_bootstrap_runs_alembic_upgrade_to_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "openlia_home"
    home.mkdir()
    db_file = tmp_path / "fresh.db"
    monkeypatch.setenv("OPENLIA_HOME", str(home))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("OPENLIA_MODE", "personal")

    session_mod.dispose_engine()
    try:
        bootstrap_module.bootstrap()
        engine = session_mod.get_engine()
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
        assert row is not None
        assert row[0] == _latest_revision()
    finally:
        session_mod.dispose_engine()
