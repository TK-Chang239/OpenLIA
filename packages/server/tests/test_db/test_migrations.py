"""Alembic scaffold test — env.py loads without error."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_alembic_env_loads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/empty.db")

    repo_root = Path(__file__).resolve().parents[2]  # packages/server
    result = subprocess.run(
        ["uv", "run", "alembic", "current"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
