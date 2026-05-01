"""Tests for /api/connectors CRUD + V2 validate."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.connectors.types import ToolDefinition
from openlia_server.services import connectors_service
from sqlalchemy import event
from sqlalchemy.engine import Engine


@pytest.fixture
def client(engine: Engine, db_session_factory) -> Iterator[TestClient]:
    from openlia_server.db.models.auth import User
    from openlia_server.middleware.auth import LOCAL_USER_ID
    from openlia_server.routes.connectors import build_connectors_router

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Personal-mode auth resolves to the synthetic `local` user; the admin
    # gate then checks `is_admin`, so seed an admin row before the client
    # exercises any /api/connectors/* route.
    with db_session_factory() as s:
        s.merge(
            User(
                id=LOCAL_USER_ID,
                email="local@openlia.local",
                display_name="Local",
                password_hash=None,
                is_admin=True,
                is_disabled=False,
                must_change_password=False,
            )
        )
        s.commit()

    app = FastAPI()
    app.include_router(
        build_connectors_router(
            db_session_factory=db_session_factory, mode="personal"
        ),
        prefix="/api",
    )
    yield TestClient(app)


def _patch_validation_ok(monkeypatch, tools=None, callables=None):
    async def fake(launch, secrets):
        return connectors_service.ValidationOk(
            tools=tools
            or [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in [ToolDefinition(name="get_quote", description="d", input_schema={})]
            ],
            python_callables=callables or [],
        )

    monkeypatch.setattr("openlia_server.services.connectors_service._validate_launch", fake)


def _patch_validation_failure(monkeypatch, message="bad key"):
    async def fake(launch, secrets):
        return connectors_service.ValidationFailure(error=message)

    monkeypatch.setattr("openlia_server.services.connectors_service._validate_launch", fake)


def test_company_mode_rejects_unauthenticated_caller(
    engine: Engine, db_session_factory
) -> None:
    """In company mode, /api/connectors/* requires a valid admin session."""
    from openlia_server.routes.connectors import build_connectors_router

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    app = FastAPI()
    app.include_router(
        build_connectors_router(
            db_session_factory=db_session_factory, mode="company"
        ),
        prefix="/api",
    )
    client = TestClient(app)
    # No session cookie -> 401
    assert client.get("/api/connectors").status_code == 401
    assert client.post("/api/connectors", json={}).status_code == 401
    assert (
        client.post(
            "/api/connectors/introspect-python-lib",
            json={"import_module": "x", "cls": "y"},
        ).status_code
        == 401
    )


def test_create_connector_validated(client, monkeypatch):
    _patch_validation_ok(monkeypatch)
    resp = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": []}]
            },
            "secrets": {"EODHD_API_KEY": "k"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "validated"
    assert body["cached_tools_count"] == 1


def test_create_connector_failed(client, monkeypatch):
    _patch_validation_failure(monkeypatch, "bad key")
    resp = client.post(
        "/api/connectors",
        json={
            "source": "remote_mcp",
            "category": "news",
            "provider_id": "user_mcp_news1",
            "display_name": "Custom News MCP",
            "launch": {"modes": [{"kind": "remote_mcp", "url": "https://x", "headers": {}}]},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert "bad key" in body["last_error"]


def test_list_connectors(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": []}]
            },
        },
    )
    resp = client.get("/api/connectors")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["provider_id"] == "eodhd"


def test_revalidate_404_for_unknown(client):
    resp = client.post("/api/connectors/no-such-id/validate")
    assert resp.status_code == 404


def test_get_connector_detail_returns_launch_and_secret_keys(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    create = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [
                    {"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": ["EODHD_API_KEY"]}
                ]
            },
            "secrets": {"EODHD_API_KEY": "secret-value"},
        },
    )
    cid = create.json()["id"]

    resp = client.get(f"/api/connectors/{cid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == cid
    assert body["provider_id"] == "eodhd"
    assert body["launch"]["modes"][0]["argv"] == ["uvx", "eodhd-mcp"]
    assert body["secret_keys"] == ["EODHD_API_KEY"]
    assert "secrets" not in body  # values must never leak


def test_get_connector_detail_404_for_unknown(client):
    resp = client.get("/api/connectors/no-such-id")
    assert resp.status_code == 404


def test_update_connector_revalidates_and_replaces_launch(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    create = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["old"], "env_keys": []}]
            },
            "secrets": {"EODHD_API_KEY": "old-value"},
        },
    )
    cid = create.json()["id"]

    resp = client.put(
        f"/api/connectors/{cid}",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD (renamed)",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["new", "argv"], "env_keys": []}]
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["display_name"] == "EODHD (renamed)"
    assert body["status"] == "validated"

    detail = client.get(f"/api/connectors/{cid}").json()
    assert detail["launch"]["modes"][0]["argv"] == ["new", "argv"]
    # secrets omitted in PUT body -> existing secrets preserved
    assert detail["secret_keys"] == ["EODHD_API_KEY"]


def test_update_connector_replaces_secrets_when_provided(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    create = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
            "secrets": {"OLD_KEY": "v"},
        },
    )
    cid = create.json()["id"]

    client.put(
        f"/api/connectors/{cid}",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
            "secrets": {"NEW_KEY": "v2"},
        },
    )
    detail = client.get(f"/api/connectors/{cid}").json()
    assert detail["secret_keys"] == ["NEW_KEY"]


def test_introspect_python_lib_returns_init_param_names(client):
    """Real-import path: `eodhd.APIClient.__init__(self, api_key: str)`."""
    resp = client.post(
        "/api/connectors/introspect-python-lib",
        json={"import_module": "eodhd", "cls": "APIClient"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    names = [p["name"] for p in body["params"]]
    assert "api_key" in names
    api_key = next(p for p in body["params"] if p["name"] == "api_key")
    assert api_key["required"] is True
    # type annotation captured as string
    assert "str" in (api_key.get("type") or "")


def test_introspect_python_lib_module_not_installed(client):
    resp = client.post(
        "/api/connectors/introspect-python-lib",
        json={
            "import_module": "definitely_not_a_real_module_xyz",
            "cls": "Whatever",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "definitely_not_a_real_module_xyz" in body["detail"]
    assert "pip install" in body["detail"].lower()


def test_install_python_package_success(client, monkeypatch):
    captured: dict[str, list[str]] = {}

    class FakeProc:
        returncode = 0
        stdout = "Successfully installed eodhd-1.2.3\n"
        stderr = ""

    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        return FakeProc()

    monkeypatch.setattr(
        "openlia_server.routes.connectors.subprocess.run", fake_run
    )

    resp = client.post(
        "/api/connectors/install-python-package",
        json={"pip_name": "eodhd", "pip_version": "==1.2.3"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "Successfully installed" in body["stdout"]
    # Pip command targets the server's own Python interpreter and the right spec
    assert "pip" in captured["args"]
    assert "install" in captured["args"]
    assert "eodhd==1.2.3" in captured["args"]


def test_install_python_package_rejects_shell_meta(client):
    resp = client.post(
        "/api/connectors/install-python-package",
        json={"pip_name": "eodhd; rm -rf /", "pip_version": ""},
    )
    assert resp.status_code in (400, 422)


def test_install_python_package_rejects_flag_smuggling(client):
    """Refuse pip_name that begins with '-' (would be parsed as a pip flag)."""
    resp = client.post(
        "/api/connectors/install-python-package",
        json={"pip_name": "--editable", "pip_version": ""},
    )
    assert resp.status_code in (400, 422)


def test_install_python_package_rejects_url_install(client):
    resp = client.post(
        "/api/connectors/install-python-package",
        json={"pip_name": "https://evil.example.com/pkg.tar.gz", "pip_version": ""},
    )
    assert resp.status_code in (400, 422)


def test_install_python_package_rejects_invalid_version(client):
    resp = client.post(
        "/api/connectors/install-python-package",
        json={"pip_name": "eodhd", "pip_version": "==1; rm"},
    )
    assert resp.status_code in (400, 422)


def test_install_python_package_pip_failure_returns_stderr(client, monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "ERROR: Could not find a version that satisfies eodhd==999"

    monkeypatch.setattr(
        "openlia_server.routes.connectors.subprocess.run",
        lambda *a, **kw: FakeProc(),
    )

    resp = client.post(
        "/api/connectors/install-python-package",
        json={"pip_name": "eodhd", "pip_version": "==999"},
    )
    assert resp.status_code == 400
    assert "Could not find a version" in resp.json()["detail"]


def test_install_python_package_invalidates_import_caches(client, monkeypatch):
    """After install succeeds we invalidate the importer cache so a subsequent
    introspect can find the just-installed module without restarting."""
    class FakeProc:
        returncode = 0
        stdout = "Successfully installed eodhd-1\n"
        stderr = ""

    monkeypatch.setattr(
        "openlia_server.routes.connectors.subprocess.run",
        lambda *a, **kw: FakeProc(),
    )
    invalidated = {"called": False}
    monkeypatch.setattr(
        "openlia_server.routes.connectors.importlib.invalidate_caches",
        lambda: invalidated.update(called=True),
    )
    resp = client.post(
        "/api/connectors/install-python-package",
        json={"pip_name": "eodhd", "pip_version": ""},
    )
    assert resp.status_code == 200
    assert invalidated["called"] is True


def test_introspect_python_lib_class_not_found(client):
    resp = client.post(
        "/api/connectors/introspect-python-lib",
        json={"import_module": "eodhd", "cls": "NoSuchClass"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "NoSuchClass" in body["detail"]


def test_create_connector_persists_grounding_fields(client, monkeypatch):
    _patch_validation_ok(monkeypatch)
    resp = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": []}]
            },
            "secrets": {"EODHD_API_KEY": "k"},
            "source_repo_url": "https://github.com/eodhistoricaldata/eodhd-mcp-server",
            "source_repo_revision": "main",
            "openapi_url": "https://eodhd.com/openapi.json",
        },
    )
    assert resp.status_code == 201, resp.text
    cid = resp.json()["id"]

    detail = client.get(f"/api/connectors/{cid}").json()
    assert detail["source_repo_url"] == "https://github.com/eodhistoricaldata/eodhd-mcp-server"
    assert detail["source_repo_revision"] == "main"
    assert detail["openapi_url"] == "https://eodhd.com/openapi.json"
    assert detail["grounding_status"] == "none"


def test_update_connector_404_for_unknown(client):
    resp = client.put(
        "/api/connectors/no-such-id",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "x",
            "display_name": "x",
            "launch": {"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
        },
    )
    assert resp.status_code == 404
