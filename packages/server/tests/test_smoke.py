"""Smoke tests for the openlia server package."""

import openlia
from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.cli import app as cli_app
from typer.testing import CliRunner


def test_core_is_importable_from_server():
    """Server depends on core via workspace reference."""
    assert openlia.__version__


def test_app_factory_returns_fastapi_instance():
    app = create_app()
    assert app.title == "OpenLIA"


def test_health_endpoint_returns_200():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cli_help_runs():
    runner = CliRunner()
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.stdout


def test_cli_serve_help_runs():
    import re

    runner = CliRunner()
    result = runner.invoke(cli_app, ["serve", "--help"])
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    assert "--host" in plain
    assert "--port" in plain
