"""bootstrap() must leave the DB at the latest Alembic head."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from openlia_server.db import bootstrap as bootstrap_module
from openlia_server.db import session as session_mod
from sqlalchemy import text

_QUOTED = re.compile(r'"([^"]+)"')


def _latest_revision() -> str:
    versions_dir = Path(bootstrap_module.__file__).parent / "migrations" / "versions"
    # rev_id -> set of parent rev_ids (a merge migration has multiple parents)
    revisions: dict[str, set[str]] = {}
    for path in versions_dir.glob("*.py"):
        text_body = path.read_text()
        # `revision: str = "<id>"` — first occurrence wins.
        rev_match = re.search(r"^\s*revision\s*:?[^=]*=\s*\"([^\"]+)\"", text_body, re.MULTILINE)
        if not rev_match:
            continue
        rev_id = rev_match.group(1)
        # `down_revision: ... = "<id>"`  OR  `... = ("<id>", "<id>", ...)`
        # The tuple form spans multiple lines, so match through the closing paren.
        down_match = re.search(
            r"^\s*down_revision\s*:?[^=]*=\s*(.+?)(?:\n\s*(?:branch_labels|depends_on)\s*:?)",
            text_body,
            re.MULTILINE | re.DOTALL,
        )
        parents: set[str] = set()
        if down_match:
            parents = set(_QUOTED.findall(down_match.group(1)))
        revisions[rev_id] = parents
    if not revisions:
        raise AssertionError("no migration revisions discovered")
    all_parents: set[str] = set()
    for ps in revisions.values():
        all_parents |= ps
    heads = [rev for rev in revisions if rev not in all_parents]
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
