from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner


def test_serve_calls_bootstrap_before_uvicorn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/cli.db")

    from openlia_server.cli import app

    runner = CliRunner()

    with (
        patch("openlia_server.cli.bootstrap") as mock_bootstrap,
        patch("openlia_server.cli.uvicorn.run") as mock_uvicorn,
    ):
        mock_bootstrap.return_value = None
        result = runner.invoke(app, ["serve"])

    assert result.exit_code == 0, result.output
    mock_bootstrap.assert_called_once()
    mock_uvicorn.assert_called_once()


def test_serve_fails_loudly_if_bootstrap_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/broken.db")

    from openlia_server.cli import app

    runner = CliRunner()
    with (
        patch("openlia_server.cli.bootstrap", side_effect=RuntimeError("boom")),
        patch("openlia_server.cli.uvicorn.run") as mock_uvicorn,
    ):
        result = runner.invoke(app, ["serve"])

    assert result.exit_code != 0
    assert "boom" in (result.output + str(result.exception))
    mock_uvicorn.assert_not_called()
