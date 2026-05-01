"""Per-connector grounding clone orchestration.

`grounding_service.ensure_clone(session, connector_id)` shallow-clones the
connector's `source_repo_url` to `<openlia_home>/connector_repos/<id>/` and
updates `grounding_status` + `cached_repo_commit_sha` + `grounding_fetched_at`
on the row. Re-running is a no-op when the clone is already present and the
connector's URL/revision haven't changed.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from openlia.connectors.types import ConnectorStatus
from openlia_server.db.models.connectors import Connector
from openlia_server.services import grounding_service
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DBSession


def _init_local_repo(repo_path: Path, branch: str = "main") -> str:
    repo_path.mkdir(parents=True, exist_ok=True)
    env_args = [
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=Test",
        "-c",
        "init.defaultBranch=" + branch,
    ]
    subprocess.run(
        ["git", *env_args, "init", "-b", branch, str(repo_path)],
        check=True,
        capture_output=True,
    )
    (repo_path / "README.md").write_text("hello\n")
    subprocess.run(
        ["git", "-C", str(repo_path), *env_args, "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), *env_args, "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    out = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _seed_connector(
    session: DBSession,
    *,
    cid: str | None = None,
    source_repo_url: str | None = None,
    source_repo_revision: str | None = None,
) -> Connector:
    row = Connector(
        id=cid or str(uuid.uuid4()),
        provider_id="x",
        display_name="X",
        source="cli_mcp",
        category="financial",
        launch={"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
        secrets={},
        status=ConnectorStatus.VALIDATED.value,
        source_repo_url=source_repo_url,
        source_repo_revision=source_repo_revision,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_ensure_clone_returns_path_and_marks_ready(
    engine: Engine, db_session: DBSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src"
    expected_sha = _init_local_repo(src)
    monkeypatch.setattr(grounding_service, "_clones_root", lambda: tmp_path / "clones")

    conn = _seed_connector(
        db_session,
        source_repo_url=f"file://{src}",
        source_repo_revision="main",
    )

    target = grounding_service.ensure_clone(db_session, connector_id=conn.id)

    assert target is not None
    assert (target / "README.md").read_text() == "hello\n"
    db_session.refresh(conn)
    assert conn.grounding_status == "ready"
    assert conn.cached_repo_commit_sha == expected_sha
    assert conn.grounding_fetched_at is not None


def test_ensure_clone_returns_none_when_no_url(
    engine: Engine, db_session: DBSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(grounding_service, "_clones_root", lambda: tmp_path / "clones")
    conn = _seed_connector(db_session)

    assert grounding_service.ensure_clone(db_session, connector_id=conn.id) is None
    db_session.refresh(conn)
    assert conn.grounding_status == "none"


def test_ensure_clone_marks_failed_on_git_error(
    engine: Engine, db_session: DBSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(grounding_service, "_clones_root", lambda: tmp_path / "clones")
    conn = _seed_connector(
        db_session,
        source_repo_url=f"file://{tmp_path}/no-such-repo",
        source_repo_revision="main",
    )

    target = grounding_service.ensure_clone(db_session, connector_id=conn.id)

    assert target is None
    db_session.refresh(conn)
    assert conn.grounding_status == "failed"


def test_ensure_clone_is_idempotent_for_unchanged_url(
    engine: Engine, db_session: DBSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src"
    _init_local_repo(src)
    monkeypatch.setattr(grounding_service, "_clones_root", lambda: tmp_path / "clones")
    conn = _seed_connector(
        db_session,
        source_repo_url=f"file://{src}",
        source_repo_revision="main",
    )

    first = grounding_service.ensure_clone(db_session, connector_id=conn.id)
    assert first is not None
    first_mtime = first.stat().st_mtime

    # Second call must not re-clone (target already exists).
    second = grounding_service.ensure_clone(db_session, connector_id=conn.id)
    assert second == first
    assert second.stat().st_mtime == first_mtime


def test_resync_clone_recreates_when_url_changes(
    engine: Engine, db_session: DBSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src_a = tmp_path / "src_a"
    src_b = tmp_path / "src_b"
    _init_local_repo(src_a)
    sha_b = _init_local_repo(src_b)
    monkeypatch.setattr(grounding_service, "_clones_root", lambda: tmp_path / "clones")
    conn = _seed_connector(
        db_session,
        source_repo_url=f"file://{src_a}",
        source_repo_revision="main",
    )
    grounding_service.ensure_clone(db_session, connector_id=conn.id)

    # User points the connector at a different repo.
    conn.source_repo_url = f"file://{src_b}"
    db_session.commit()
    target = grounding_service.resync_clone(db_session, connector_id=conn.id)

    assert target is not None
    db_session.refresh(conn)
    assert conn.cached_repo_commit_sha == sha_b
