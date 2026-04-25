"""Lock the installable surface of the `openlia-core` wheel.

Builds the wheel via ``uv build --package openlia-core`` and asserts:

- The ``openlia/`` package directory ships in the wheel.
- ``openlia/prompts/`` YAML resources ship in the wheel.
- ``openlia/reports/frameworks/`` resources ship in the wheel.
- Repository-only paths (``planning/``, ``tests/``) do NOT ship.
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
            "openlia-core",
            "--out-dir",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    candidates = sorted(out_dir.glob("openlia_core-*.whl"))
    assert candidates, "expected uv build to emit an openlia-core wheel"
    return candidates[-1]


def test_core_wheel_ships_resources_and_no_repo_artifacts(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()

    assert any(name.startswith("openlia/") for name in names), "openlia/ package missing from wheel"
    assert any(name.startswith("openlia/prompts/") and name.endswith(".yaml") for name in names), (
        "openlia/prompts/*.yaml resources missing from wheel"
    )
    assert any(name.startswith("openlia/reports/frameworks/") for name in names), (
        "openlia/reports/frameworks/* resources missing from wheel"
    )
    assert not any("planning/" in name for name in names), "planning/ leaked into wheel"
    assert not any("/tests/" in name for name in names), "tests/ leaked into wheel"
