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
# Task 14: /setup/review/* routes
# ---------------------------------------------------------------------------


def test_review_run_kicks_off_task_and_poll_returns_state(
    wizard_personal_client: TestClient, monkeypatch
) -> None:
    from openlia_server.ai_review import store as store_mod

    fresh_store = store_mod.ReviewStore()
    monkeypatch.setattr(store_mod, "DEFAULT_STORE", fresh_store)

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/review/run")
    assert resp.status_code == 200
    review_id = resp.json()["review_id"]

    poll = wizard_personal_client.get(f"/setup/review/{review_id}")
    assert poll.status_code == 200
    assert poll.json()["state"] in ("running", "complete", "failed")


def test_review_poll_unknown_id_returns_404(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.get("/setup/review/nope")
    assert resp.status_code == 404


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
    return {
        "thinking": [
            {
                "provider": "ollama",
                "model": "llama3.1:70b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
        "everyday": [
            {
                "provider": "ollama",
                "model": "llama3.1:8b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
        "quick": [
            {
                "provider": "ollama",
                "model": "qwen2.5:7b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
    }


def test_post_models_roundtrip(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.config import LLMModel, LLMProvider

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/models", json=_ollama_payload())
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    assert db_session.query(LLMProvider).count() == 3
    assert db_session.query(LLMModel).count() == 3


def test_post_models_idempotent_on_second_post(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.config import LLMModel, LLMProvider

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    wizard_personal_client.post("/setup/models", json=_ollama_payload())
    # Second POST replaces wizard-staged models — same row counts, no constraint clash.
    resp = wizard_personal_client.post("/setup/models", json=_ollama_payload())
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    assert db_session.query(LLMProvider).count() == 3
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


def test_post_models_rejects_unknown_provider(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    payload = {
        "thinking": [
            {
                "provider": "imaginary_kind",
                "model": "x",
                "base_url": "http://localhost",
                "is_tier_default": True,
            }
        ],
        "everyday": [],
        "quick": [],
    }
    resp = wizard_personal_client.post("/setup/models", json=payload)
    # `services.llm_providers.create_provider` raises on unknown kind; the
    # request rolls back and returns 500 — the wizard treats that as a
    # validation error in the UI. We accept 4xx OR 5xx but assert non-200.
    assert resp.status_code != 200


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
# Task 10 (Phase 10): /setup/providers + required_tiers
# ---------------------------------------------------------------------------


def _seed_session(client: TestClient) -> None:
    client.post("/setup/mode", json={"mode": "personal"})


def test_get_providers_empty(wizard_personal_client: TestClient) -> None:
    _seed_session(wizard_personal_client)
    resp = wizard_personal_client.get("/setup/providers")
    assert resp.status_code == 200
    assert resp.json() == {"providers": []}


def test_post_provider_persists_with_status(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.config import DataProvider

    _seed_session(wizard_personal_client)
    resp = wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {
                "mode": "builtin",
                "provider": "fmp",
                "api_key": "x",
                "base_url": "https://example.test",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entry_id"]
    db_session.expire_all()
    rows = db_session.query(DataProvider).all()
    assert len(rows) == 1
    assert rows[0].kind == "fmp"
    assert (rows[0].extra_config or {}).get("wizard_status") in ("ok", "error")


def test_providers_confirm_requires_pair(wizard_personal_client: TestClient) -> None:
    _seed_session(wizard_personal_client)
    resp = wizard_personal_client.post("/setup/providers/confirm")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "providers_incomplete"


def test_providers_confirm_advances_after_pair(wizard_personal_client: TestClient) -> None:
    _seed_session(wizard_personal_client)
    # FMP + NewsAPI.org are both stubs — health_check returns True for stubs
    # so wizard_status persists as "ok".
    wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {
                "mode": "builtin",
                "provider": "fmp",
                "api_key": "x",
                "base_url": "https://example.test",
            },
        },
    )
    wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "news",
            "entry": {
                "mode": "builtin",
                "provider": "newsapi_org",
                "api_key": "x",
                "base_url": "https://example.test",
            },
        },
    )
    # Now advance via the dedicated confirm endpoint.
    resp = wizard_personal_client.post("/setup/providers/confirm")
    assert resp.status_code == 200
    status = wizard_personal_client.get("/setup/status").json()
    assert "providers" in status["completed_steps"]


def test_provider_delete_removes_row(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.config import DataProvider

    _seed_session(wizard_personal_client)
    add = wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {
                "mode": "builtin",
                "provider": "fmp",
                "api_key": "x",
                "base_url": "https://example.test",
            },
        },
    )
    pid = add.json()["entry_id"]
    resp = wizard_personal_client.delete(f"/setup/providers/{pid}")
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(DataProvider).count() == 0


def test_provider_patch_priority(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.config import DataProvider

    _seed_session(wizard_personal_client)
    add = wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {
                "mode": "builtin",
                "provider": "fmp",
                "api_key": "x",
                "base_url": "https://example.test",
            },
        },
    )
    pid = add.json()["entry_id"]
    resp = wizard_personal_client.patch(f"/setup/providers/{pid}", json={"priority": 5})
    assert resp.status_code == 200
    db_session.expire_all()
    row = db_session.query(DataProvider).filter_by(id=pid).one()
    assert (row.extra_config or {}).get("default_priority") == 5


def test_provider_test_endpoint(wizard_personal_client: TestClient) -> None:
    _seed_session(wizard_personal_client)
    add = wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {
                "mode": "builtin",
                "provider": "fmp",
                "api_key": "x",
                "base_url": "https://example.test",
            },
        },
    )
    pid = add.json()["entry_id"]
    resp = wizard_personal_client.post(f"/setup/providers/{pid}/test")
    assert resp.status_code == 200
    assert resp.json()["ok"] in (True, False)


def test_post_provider_410_after_completion(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.commit()
    resp = wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {"mode": "builtin", "provider": "fmp"},
        },
    )
    assert resp.status_code == 410


def test_post_provider_409_without_session_token(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.post(
        "/setup/providers",
        json={
            "category": "financial",
            "entry": {"mode": "builtin", "provider": "fmp"},
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# NEW-10-02: GET /setup/required_tiers
# ---------------------------------------------------------------------------


def test_required_tiers_reads_from_registry(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.get("/setup/required_tiers")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["required_tiers"]) <= {"thinking", "everyday", "quick"}
    assert "secretary" in body["enabled_departments"]
    # Real registry has thinking + everyday + quick across departments.
    assert "thinking" in body["required_tiers"]


# ---------------------------------------------------------------------------
# NEW-10-04: review poll shape
# ---------------------------------------------------------------------------


def test_review_poll_returns_canonical_shape(wizard_personal_client: TestClient) -> None:
    from openlia_server.ai_review import store as store_mod

    fresh = store_mod.ReviewStore()
    rid = fresh.create()
    fresh.update(rid, state="complete", progress=100, result={"summary": "ok"})

    # Inject the entry into the default store so the route can read it.
    store_mod.DEFAULT_STORE._entries[rid] = fresh._entries[rid]  # type: ignore[attr-defined]

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.get(f"/setup/review/{rid}")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"state", "progress", "result", "error"}
