from __future__ import annotations

import os
import re

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

    def test_version_flag_runs_before_subcommand(
        self, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Eager --version must short-circuit before the admin callback hits
        # require_company(); mode left as personal would otherwise abort.
        monkeypatch.setenv("OPENLIA_MODE", "personal")
        called: dict[str, bool] = {}

        def spy_require_company() -> None:
            called["hit"] = True

        monkeypatch.setattr("openlia_server.cli.require_company", spy_require_company)
        # Root-level eager --version must short-circuit before any subcommand
        # parsing or callback runs. We invoke with --version positioned before
        # the subcommand so Click's root-level option lookup fires first.
        result = cli_runner.invoke(app, ["--version", "admin"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout
        assert "hit" not in called

    def test_no_color_help_has_no_ansi_escapes(self, cli_runner) -> None:
        result = cli_runner.invoke(app, ["--no-color", "--help"])
        assert result.exit_code == 0
        assert re.search(r"\x1b\[", result.stdout) is None


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


class TestServeBanner:
    def test_serve_prints_banner(
        self, cli_runner, cli_engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        order: list[str] = []

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            order.append("uvicorn")

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.setenv("OPENLIA_MODE", "personal")
        monkeypatch.delenv("OPENLIA_SCHEDULER_ENABLED", raising=False)

        result = cli_runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "8000"])
        assert result.exit_code == 0, result.output
        out_lines = result.output.splitlines()
        # Locate the canonical four lines (plus Scheduler line) in order.
        banner_idx = next(i for i, ln in enumerate(out_lines) if ln.startswith("OpenLIA v"))
        assert out_lines[banner_idx] == "OpenLIA v0.1.0"
        assert out_lines[banner_idx + 1].startswith("Mode:      personal")
        assert out_lines[banner_idx + 2].startswith("Database:  ")
        assert out_lines[banner_idx + 3] == "Listening: http://127.0.0.1:8000"
        assert out_lines[banner_idx + 4].startswith("Scheduler: ")
        # Banner must be emitted BEFORE uvicorn.run.
        assert order == ["uvicorn"]

    def test_serve_prints_wizard_pending_line(
        self, cli_runner, cli_engine, cli_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openlia_server.db.models.infrastructure import ConfigStore

        cli_session.add(ConfigStore(key="wizard.completed", value=False))
        cli_session.commit()

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", lambda *a, **k: None)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.setenv("OPENLIA_MODE", "personal")

        result = cli_runner.invoke(app, ["serve", "--port", "8000"])
        assert result.exit_code == 0, result.output
        assert "Setup wizard: pending" in result.output

    def test_serve_no_wizard_line_when_completed(
        self, cli_runner, cli_engine, cli_session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openlia_server.db.models.infrastructure import ConfigStore

        cli_session.add(ConfigStore(key="wizard.completed", value=True))
        cli_session.commit()

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", lambda *a, **k: None)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.setenv("OPENLIA_MODE", "personal")

        result = cli_runner.invoke(app, ["serve", "--port", "8000"])
        assert result.exit_code == 0, result.output
        assert "Setup wizard" not in result.output
