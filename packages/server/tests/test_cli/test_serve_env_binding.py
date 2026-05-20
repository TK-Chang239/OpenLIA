"""OPENLIA_HOST / OPENLIA_PORT fallback chain for `openlia serve`.

Contract:

- Explicit ``--host`` / ``--port`` flags win.
- If the flag is absent, the corresponding env var (`OPENLIA_HOST`,
  `OPENLIA_PORT`) is honoured.
- Otherwise fall back to the mode-aware default
  (``127.0.0.1`` personal / ``0.0.0.0`` company; port 8080).
"""

from __future__ import annotations

import pytest
from openlia_server.cli import app


class TestServeEnvBinding:
    def test_help_documents_host_and_port_flags(self, cli_runner) -> None:
        result = cli_runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output

    def test_env_host_and_port_flow_to_uvicorn(
        self, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            captured["target"] = target
            captured["kwargs"] = kwargs

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.setenv("OPENLIA_HOST", "0.0.0.0")
        monkeypatch.setenv("OPENLIA_PORT", "9000")

        result = cli_runner.invoke(app, ["serve"])
        assert result.exit_code == 0, result.output
        assert captured["kwargs"]["host"] == "0.0.0.0"
        assert captured["kwargs"]["port"] == 9000

    def test_explicit_flags_override_env(self, cli_runner, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            captured["kwargs"] = kwargs

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.setenv("OPENLIA_HOST", "0.0.0.0")
        monkeypatch.setenv("OPENLIA_PORT", "9000")

        result = cli_runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "1234"])
        assert result.exit_code == 0, result.output
        assert captured["kwargs"]["host"] == "127.0.0.1"
        assert captured["kwargs"]["port"] == 1234

    def test_personal_mode_default_host_loopback(
        self, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            captured["kwargs"] = kwargs

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.delenv("OPENLIA_HOST", raising=False)
        monkeypatch.delenv("OPENLIA_PORT", raising=False)
        monkeypatch.setenv("OPENLIA_MODE", "personal")

        result = cli_runner.invoke(app, ["serve"])
        assert result.exit_code == 0, result.output
        assert captured["kwargs"]["host"] == "127.0.0.1"
        assert captured["kwargs"]["port"] == 8080
