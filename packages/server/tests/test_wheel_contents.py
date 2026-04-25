"""Lock the installable surface of the `openlia` wheel.

Builds the wheel via ``uv build --package openlia`` and asserts that:

- The ``openlia_server/`` package directory ships in the wheel.
- Repository-only paths (``planning/``, ``tests/``, ``.venv/``) do NOT
  ship in the wheel.
- The ``openlia = openlia_server.cli:main`` console script entry point
  is registered in ``entry_points.txt``.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_wheel(out_dir: Path) -> Path:
    if shutil.which("uv") is None:
        pytest.skip("uv binary not available on PATH")
    subprocess.run(
        [
            "uv",
            "build",
            "--package",
            "openlia",
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    candidates = sorted(out_dir.glob("openlia-*.whl"))
    assert candidates, "expected uv build to emit an openlia wheel"
    return candidates[-1]


def test_wheel_ships_server_package_and_no_repo_artifacts(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()

    assert any(name.startswith("openlia_server/") for name in names), (
        "openlia_server/ package missing from wheel"
    )
    assert not any("planning/" in name for name in names), "planning/ leaked into wheel"
    assert not any("/tests/" in name for name in names), "tests/ leaked into wheel"
    assert not any(".venv/" in name for name in names), ".venv/ leaked into wheel"


def test_wheel_registers_console_script(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        entry_points = next((n for n in zf.namelist() if n.endswith("entry_points.txt")), None)
        assert entry_points, "entry_points.txt missing from wheel"
        body = zf.read(entry_points).decode()

    assert "openlia = openlia_server.cli:main" in body, body
