"""Tests for /setup/* routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Task 4: GET /setup/status
# ---------------------------------------------------------------------------


def test_status_fresh_install(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.get("/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "personal"
    assert body["wizard_completed"] is False
    assert body["current_step"] == "mode"
    assert body["completed_steps"] == []
    assert body["env_overrides"] == {}


def test_status_after_completion_still_returns_200(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.add(ConfigStore(key="wizard.mode", value="personal"))
    db_session.commit()

    resp = wizard_personal_client.get("/setup/status")
    assert resp.status_code == 200
    assert resp.json()["wizard_completed"] is True


# ---------------------------------------------------------------------------
# Task 5: POST /setup/mode
# ---------------------------------------------------------------------------


def test_post_mode_persists_and_issues_cookie(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.post("/setup/mode", json={"mode": "company"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "company"
    assert "openlia_wizard_session" in resp.cookies

    status = wizard_personal_client.get("/setup/status").json()
    assert status["mode"] == "company"
    assert "mode" in status["completed_steps"]


def test_post_mode_rejected_when_env_override_set(
    wizard_personal_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    resp = wizard_personal_client.post("/setup/mode", json={"mode": "company"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "env_locked"


def test_post_mode_rejects_invalid_value(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.post("/setup/mode", json={"mode": "banana"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Task 6: Session cookie + takeover
# ---------------------------------------------------------------------------


def test_second_browser_without_takeover_rejected(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    cookie = wizard_personal_client.cookies.get("openlia_wizard_session")
    assert cookie

    wizard_personal_client.cookies.clear()
    resp = wizard_personal_client.post("/setup/identity", json={"display_name": "Hacker"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "wizard_session_active"


def test_takeover_rotates_token(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    first = wizard_personal_client.cookies.get("openlia_wizard_session")

    wizard_personal_client.cookies.clear()
    resp = wizard_personal_client.post("/setup/takeover")
    assert resp.status_code == 200
    second = wizard_personal_client.cookies.get("openlia_wizard_session")
    assert second and second != first


# ---------------------------------------------------------------------------
# Task 7: POST /setup/identity (personal)
# ---------------------------------------------------------------------------


def test_post_identity_creates_local_user(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.auth import User

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/identity", json={"display_name": "TK"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "TK"

    user = db_session.query(User).filter_by(email="local@openlia.local").one()
    assert user.display_name == "TK"
    assert user.is_admin is False


def test_post_identity_is_idempotent_on_display_name(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.auth import User

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    wizard_personal_client.post("/setup/identity", json={"display_name": "A"})
    wizard_personal_client.post("/setup/identity", json={"display_name": "B"})

    rows = db_session.query(User).filter_by(email="local@openlia.local").all()
    assert len(rows) == 1
    assert rows[0].display_name == "B"


# ---------------------------------------------------------------------------
# Task 8: POST /setup/admin (company)
# ---------------------------------------------------------------------------


def test_post_admin_creates_first_admin(wizard_company_client: TestClient, db_session) -> None:
    from openlia_server.db.models.auth import User

    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post(
        "/setup/admin",
        json={
            "email": "boss@example.com",
            "password": "CorrectHorseBattery9!",
            "display_name": "Boss",
        },
    )
    assert resp.status_code == 200

    user = db_session.query(User).filter_by(email="boss@example.com").one()
    assert user.is_admin is True
    assert user.password_hash.startswith("$argon2")


def test_post_admin_rejects_second_admin(wizard_company_client: TestClient) -> None:
    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    wizard_company_client.post(
        "/setup/admin",
        json={
            "email": "first@example.com",
            "password": "CorrectHorseBattery9!",
            "display_name": "A",
        },
    )
    resp = wizard_company_client.post(
        "/setup/admin",
        json={
            "email": "second@example.com",
            "password": "CorrectHorseBattery9!",
            "display_name": "B",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "admin_exists"


def test_post_admin_rejects_short_password(wizard_company_client: TestClient) -> None:
    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post(
        "/setup/admin",
        json={"email": "weak@example.com", "password": "short", "display_name": "W"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Task 11: POST /setup/access_control (company only)
# ---------------------------------------------------------------------------


def test_access_control_writes_policy_and_bind_config(
    wizard_company_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.auth import SignupPolicy
    from openlia_server.db.models.infrastructure import ConfigStore

    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post(
        "/setup/access_control",
        json={
            "signup_policy": "invite_only",
            "allowed_domains": "example.com,acme.com",
            "bind_host": "0.0.0.0",
            "bind_port": 8000,
        },
    )
    assert resp.status_code == 200

    policy = db_session.get(SignupPolicy, 1)
    assert policy is not None
    assert policy.mode == "invite_only"
    assert "example.com" in policy.allowed_email_domains

    host = db_session.get(ConfigStore, "server.bind_host")
    port = db_session.get(ConfigStore, "server.bind_port")
    assert host.value == "0.0.0.0"
    assert port.value == "8000"


def test_access_control_rejects_personal_mode(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post(
        "/setup/access_control",
        json={"signup_policy": "invite_only", "bind_host": "127.0.0.1", "bind_port": 8000},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "wrong_mode"


# ---------------------------------------------------------------------------
# Task 15: POST /setup/finish
# ---------------------------------------------------------------------------


def test_finish_writes_completed_and_returns_redirect(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore, WizardState

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/finish")
    assert resp.status_code == 200
    assert resp.json()["redirect"] == "/"

    completed = db_session.get(ConfigStore, "wizard.completed")
    assert completed is not None
    assert completed.value == "true"
    state = db_session.get(WizardState, 1)
    assert state.active_session_token is None


def test_finish_returns_410_once_done(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    wizard_personal_client.post("/setup/finish")
    resp = wizard_personal_client.post("/setup/finish")
    assert resp.status_code == 410


def test_finish_company_mode_redirects_to_login(wizard_company_client: TestClient) -> None:
    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post("/setup/finish")
    assert resp.json()["redirect"] == "/login"


# ---------------------------------------------------------------------------
# Task 9 (Phase 10): POST /setup/models
# ---------------------------------------------------------------------------


def _ollama_payload() -> dict:
    """Three Ollama models, with department + system-role defaults wired."""
    from openlia.departments import get_registered_department_ids
    from openlia.llm.system_roles import SYSTEM_ROLE_IDS

    models = [
        {
            "provider_kind": "ollama",
            "base_url": "http://localhost:11434",
            "model_ref": "llama3.1:70b",
            "display_name": "Llama 3.1 70B",
        },
        {
            "provider_kind": "ollama",
            "base_url": "http://localhost:11434",
            "model_ref": "llama3.1:8b",
            "display_name": "Llama 3.1 8B",
        },
        {
            "provider_kind": "ollama",
            "base_url": "http://localhost:11434",
            "model_ref": "qwen2.5:7b",
            "display_name": "Qwen 2.5 7B",
        },
    ]
    dept_defaults = {dept_id: "llama3.1:70b" for dept_id in get_registered_department_ids()}
    role_defaults = {role_id: "llama3.1:8b" for role_id in SYSTEM_ROLE_IDS}
    return {
        "models": models,
        "department_defaults": dept_defaults,
        "system_role_defaults": role_defaults,
    }


def test_post_models_roundtrip(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.config import LLMModel, LLMProvider

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/models", json=_ollama_payload())
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    # All three Ollama models share the same (kind, api_key, base_url, env) tuple,
    # so they collapse to a single LLMProvider row.
    assert db_session.query(LLMProvider).count() == 1
    assert db_session.query(LLMModel).count() == 3


def test_post_models_idempotent_on_second_post(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.config import LLMModel, LLMProvider

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    wizard_personal_client.post("/setup/models", json=_ollama_payload())
    # Second POST upserts the same providers/models — counts stay constant.
    resp = wizard_personal_client.post("/setup/models", json=_ollama_payload())
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    assert db_session.query(LLMProvider).count() == 1
    assert db_session.query(LLMModel).count() == 3


def test_post_models_410_after_completion(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.commit()
    resp = wizard_personal_client.post("/setup/models", json=_ollama_payload())
    assert resp.status_code == 410


def test_post_models_409_without_session_token(wizard_personal_client: TestClient) -> None:
    # No /setup/mode call -> no cookie issued.
    resp = wizard_personal_client.post("/setup/models", json=_ollama_payload())
    assert resp.status_code == 409


def _seed_connector(db_session, *, status: str) -> None:
    import uuid

    from openlia_server.db.models.connectors import Connector

    db_session.add(
        Connector(
            id=str(uuid.uuid4()),
            provider_id="eodhd",
            display_name="EODHD",
            source="cli_mcp",
            category="financial",
            launch={"modes": [{"kind": "cli_mcp", "argv": ["echo", "hi"], "env_keys": []}]},
            secrets={},
            status=status,
        )
    )
    db_session.commit()


def test_post_providers_advances_when_a_connector_is_validated(
    wizard_personal_client: TestClient, db_session
) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    _seed_connector(db_session, status="validated")
    resp = wizard_personal_client.post("/setup/providers")
    assert resp.status_code == 200, resp.text
    status_body = wizard_personal_client.get("/setup/status").json()
    assert "providers" in status_body["completed_steps"]
    assert status_body["current_step"] == "review"


def test_post_providers_422_when_no_validated_connector(
    wizard_personal_client: TestClient, db_session
) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    _seed_connector(db_session, status="pending")
    resp = wizard_personal_client.post("/setup/providers")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "no_validated_connector"


def test_post_providers_409_without_session_token(
    wizard_personal_client: TestClient,
) -> None:
    resp = wizard_personal_client.post("/setup/providers")
    assert resp.status_code == 409


def test_post_models_test_success(wizard_personal_client: TestClient, monkeypatch) -> None:
    from openlia_server.routes import settings as settings_routes

    class _FakeResult:
        ok = True
        latency_ms = 12
        error_class = None
        error_msg = None

        def model_dump(self) -> dict:
            return {
                "ok": True,
                "latency_ms": 12,
                "error_class": None,
                "error_msg": None,
            }

    async def _fake(*args, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(settings_routes, "_run_connection_test", _fake)

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post(
        "/setup/models/test",
        json={"provider": "ollama", "model": "x", "base_url": "http://localhost"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["latency_ms"] == 12


def test_post_models_test_failure(wizard_personal_client: TestClient, monkeypatch) -> None:
    from openlia_server.routes import settings as settings_routes

    class _FakeResult:
        def model_dump(self) -> dict:
            return {
                "ok": False,
                "latency_ms": 0,
                "error_class": "ConnectionError",
                "error_msg": "could not reach host",
            }

    async def _fake(*args, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(settings_routes, "_run_connection_test", _fake)
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post(
        "/setup/models/test",
        json={"provider": "ollama", "model": "x", "base_url": "http://localhost"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "could not reach host"


def test_post_models_rejects_unknown_department_default(
    wizard_personal_client: TestClient,
) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    payload = {
        "models": [
            {
                "provider_kind": "ollama",
                "base_url": "http://localhost:11434",
                "model_ref": "llama3.1:8b",
                "display_name": "Llama 3.1 8B",
            }
        ],
        "department_defaults": {"not_a_real_department": "llama3.1:8b"},
        "system_role_defaults": {},
    }
    resp = wizard_personal_client.post("/setup/models", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_slot"


def test_post_models_rejects_unknown_model_ref(wizard_personal_client: TestClient) -> None:
    from openlia.departments import get_registered_department_ids

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    dept_id = get_registered_department_ids()[0]
    payload = {
        "models": [
            {
                "provider_kind": "ollama",
                "base_url": "http://localhost:11434",
                "model_ref": "llama3.1:8b",
                "display_name": "Llama 3.1 8B",
            }
        ],
        "department_defaults": {dept_id: "does-not-exist"},
        "system_role_defaults": {},
    }
    resp = wizard_personal_client.post("/setup/models", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "unknown_model_ref"


def test_post_models_loopback_required(db_session) -> None:
    from fastapi.testclient import TestClient
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: False,
    )
    client = TestClient(app)
    resp = client.post("/setup/mode", json={"mode": "personal"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "loopback_required"


# ---------------------------------------------------------------------------
# GET /setup/state
# ---------------------------------------------------------------------------


def test_state_returns_department_and_role_ids(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.get("/setup/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "secretary" in body["enabled_department_ids"]
    assert isinstance(body["system_role_ids"], list)
    assert len(body["system_role_ids"]) > 0
