from __future__ import annotations

import os

import pytest
from openlia_server.cli import app


class TestGlobalFlags:
    def test_version_prints_and_exits_zero(self, cli_runner) -> None:
        result = cli_runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "0.1.0"

    def test_help_lists_every_subcommand(self, cli_runner) -> None:
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("serve", "admin", "wizard", "secrets", "maintenance"):
            assert cmd in result.stdout


class TestServeFlags:
    def test_no_scheduler_sets_env_before_uvicorn(
        self, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: dict[str, object] = {}

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            called["target"] = target
            called["kwargs"] = kwargs
            called["scheduler_env"] = os.environ.get("OPENLIA_SCHEDULER_ENABLED")

        def fake_bootstrap() -> None:
            called["bootstrap"] = True

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", fake_bootstrap)
        monkeypatch.delenv("OPENLIA_SCHEDULER_ENABLED", raising=False)

        result = cli_runner.invoke(app, ["serve", "--no-scheduler", "--port", "1234"])
        assert result.exit_code == 0, result.output
        assert called["bootstrap"] is True
        assert called["target"] == "openlia_server.app:create_app"
        assert called["kwargs"]["factory"] is True
        assert called["kwargs"]["port"] == 1234
        assert called["scheduler_env"] == "false"

    def test_serve_without_no_scheduler_does_not_override_env(
        self, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            captured["scheduler_env"] = os.environ.get("OPENLIA_SCHEDULER_ENABLED")

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.setenv("OPENLIA_SCHEDULER_ENABLED", "true")

        result = cli_runner.invoke(app, ["serve"])
        assert result.exit_code == 0
        assert captured["scheduler_env"] == "true"
