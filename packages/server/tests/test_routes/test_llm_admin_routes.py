from __future__ import annotations

import respx
from openlia_server.services import llm_providers as svc


def _login(client, email="admin@example.com", password="pw-12345678"):
    client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )


def test_list_providers_requires_admin(company_client, make_user) -> None:
    # Non-admin user hits /settings/admin/llm/providers -> 403
    make_user(email="u@example.com", password="pw-12345678", is_admin=False)
    _login(company_client, email="u@example.com")
    resp = company_client.get("/settings/admin/llm/providers")
    assert resp.status_code == 403


def test_create_provider_requires_admin(company_client, make_user) -> None:
    make_user(email="u@example.com", password="pw-12345678", is_admin=False)
    _login(company_client, email="u@example.com")
    resp = company_client.post(
        "/settings/admin/llm/providers",
        json={"kind": "openai", "label": "x", "api_key": "k"},
    )
    assert resp.status_code == 403


def test_create_provider_happy_path_encrypts_api_key(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "openai",
                "label": "Main OpenAI",
                "api_key": "sk-plain",
                "run_test": True,
                "test_model": "gpt-5.4",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "openai"
    assert body["has_api_key"] is True
    assert "api_key" not in body  # never echoed back
    assert body["test"]["ok"] is True


def test_create_provider_rejects_failing_connection(company_client, make_user, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            401, json={"error": {"message": "bad key"}}
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "openai",
                "label": "Main OpenAI",
                "api_key": "sk-wrong",
                "run_test": True,
                "test_model": "gpt-5.4",
            },
        )
    assert resp.status_code == 400
    # Provider should NOT have been persisted.
    # (rely on db_session fixture below)


def test_test_provider_endpoint_does_not_persist(
    company_client, make_user, db_session, monkeypatch
) -> None:
    from openlia_server.db.models.config import LLMProvider

    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock() as mock:
        mock.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        resp = company_client.post(
            "/settings/admin/llm/providers/test",
            json={"kind": "openai", "api_key": "sk-x", "model": "gpt-5.4"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert db_session.query(LLMProvider).count() == 0


# ---------------------------------------------------------------------------
# respx-driven create-provider coverage for the other real provider contracts.
# The openai path is already covered above; these add the three other shipped
# kinds so a schema or auth-header change in one provider can't silently ship.
# ---------------------------------------------------------------------------


def test_create_provider_anthropic_run_test_happy_path(
    company_client, make_user, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock() as mock:
        route = mock.post("https://api.anthropic.com/v1/messages").respond(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "anthropic",
                "label": "Main Anthropic",
                "api_key": "sk-ant-test",
                "run_test": True,
                "test_model": "claude-sonnet-4-6",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "anthropic"
    assert body["test"]["ok"] is True
    # Adapter sends x-api-key + anthropic-version on the probe call.
    sent = route.calls[0].request
    assert sent.headers["x-api-key"] == "sk-ant-test"
    assert sent.headers["anthropic-version"] == "2023-06-01"


def test_create_provider_anthropic_rejects_401(company_client, make_user, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock() as mock:
        mock.post("https://api.anthropic.com/v1/messages").respond(
            401, json={"error": {"message": "invalid api key"}}
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "anthropic",
                "label": "Bad Anthropic",
                "api_key": "sk-ant-bad",
                "run_test": True,
                "test_model": "claude-sonnet-4-6",
            },
        )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"] == "connection_test_failed"
    assert detail["test"]["ok"] is False
    assert detail["test"]["error_class"] == "AuthError"


def test_create_provider_openrouter_run_test_happy_path(
    company_client, make_user, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock() as mock:
        route = mock.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "openrouter",
                "label": "Main OpenRouter",
                "api_key": "or-test",
                "run_test": True,
                "test_model": "anthropic/claude-sonnet-4-6",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "openrouter"
    assert body["test"]["ok"] is True
    # OpenRouter expects a Bearer token on the probe call.
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer or-test"


def test_create_provider_gemini_run_test_happy_path(company_client, make_user, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock() as mock:
        mock.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).respond(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "x"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "gemini",
                "label": "Main Gemini",
                "api_key": "g-test",
                "run_test": True,
                "test_model": "gemini-3-flash",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "gemini"
    assert body["test"]["ok"] is True


def test_create_model_rejects_without_provider(company_client, make_user, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    resp = company_client.post(
        "/settings/admin/llm/models",
        json={
            "provider_id": "no-such",
            "tier": "thinking",
            "model_ref": "gpt-5.4-pro",
            "display_name": "Pro",
        },
    )
    assert resp.status_code == 404


def test_delete_provider_blocks_with_models(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=p.id,
        tier="thinking",
        model_ref="x",
        display_name="x",
        is_tier_default=True,
    )
    db_session.commit()
    resp = company_client.delete(f"/settings/admin/llm/providers/{p.id}")
    assert resp.status_code == 409


def test_department_tier_override_roundtrip(company_client, make_user, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    resp = company_client.post(
        "/settings/admin/llm/department/equity_research", json={"tier": "quick"}
    )
    assert resp.status_code == 200
    resp = company_client.post(
        "/settings/admin/llm/department/equity_research", json={"tier": None}
    )
    assert resp.status_code == 200


def test_capability_override_roundtrip(company_client, make_user, monkeypatch) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)
    resp = company_client.post(
        "/settings/admin/llm/capability_override/openai/gpt-5.4",
        json={"tool_calling": False},
    )
    assert resp.status_code == 200
    resp = company_client.post("/settings/admin/llm/capability_override/openai/gpt-5.4", json=None)
    assert resp.status_code == 200


# -- NEW-4-10 / NEW-4-24 / NEW-4-25 / NEW-4-27 fix-plan additions ---------------


def test_update_model_persists_tier_and_model_ref(
    company_client, make_user, monkeypatch, db_session
) -> None:
    """NEW-4-10: PUT /models/{id} persists tier + model_ref + provider_id."""
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)

    p = svc.create_provider(db_session, kind="openai", label="OAI")
    db_session.commit()
    m = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="gpt-5.4-mini",
        display_name="GPT 5.4 mini",
        is_tier_default=True,
    )
    db_session.commit()

    resp = company_client.put(
        f"/settings/admin/llm/models/{m.id}",
        json={
            "provider_id": p.id,
            "tier": "everyday",
            "model_ref": "gpt-5.4",
            "display_name": "GPT 5.4",
            "is_tier_default": True,
            "is_enabled": True,
            "overrides": None,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "everyday"
    assert body["model_ref"] == "gpt-5.4"


def test_remote_models_skipped_for_openrouter(
    company_client, make_user, monkeypatch, db_session
) -> None:
    """NEW-4-24: openrouter -> {skipped:true}."""
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)

    p = svc.create_provider(db_session, kind="openrouter", label="OpenRouter")
    db_session.commit()

    resp = company_client.get(f"/settings/admin/llm/providers/{p.id}/remote-models")
    assert resp.status_code == 200
    assert resp.json() == {"skipped": True, "reason": "manual entry"}


def test_remote_models_skipped_for_ollama(
    company_client, make_user, monkeypatch, db_session
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)

    p = svc.create_provider(db_session, kind="ollama", label="Local Ollama")
    db_session.commit()

    resp = company_client.get(f"/settings/admin/llm/providers/{p.id}/remote-models")
    assert resp.status_code == 200
    assert resp.json() == {"skipped": True, "reason": "manual entry"}


def test_create_openai_compat_model_persists_capability_override(
    company_client, make_user, monkeypatch, db_session
) -> None:
    """NEW-4-25: openai_compat capability checkboxes persisted."""
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)

    p = svc.create_provider(
        db_session, kind="openai_compat", label="Grok", base_url="https://example.com"
    )
    db_session.commit()

    resp = company_client.post(
        "/settings/admin/llm/models",
        json={
            "provider_id": p.id,
            "tier": "everyday",
            "model_ref": "grok-pro",
            "display_name": "Grok Pro",
            "is_tier_default": True,
            "is_enabled": True,
            "advertised_capabilities": {
                "tool_calling": True,
                "structured_output": False,
            },
        },
    )
    assert resp.status_code == 201, resp.text

    db_session.expire_all()
    override = svc.get_capability_override(
        db_session, provider_kind="openai_compat", model="grok-pro"
    )
    assert override == {"tool_calling": True, "structured_output": False}


def test_create_provider_runs_test_by_default(
    company_client, make_user, monkeypatch
) -> None:
    """NEW-4-27: omitting run_test triggers connection test (no test_model -> 400)."""
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)

    resp = company_client.post(
        "/settings/admin/llm/providers",
        json={"kind": "openai", "label": "OAI", "api_key": "sk-x"},
    )
    assert resp.status_code == 400
    assert "test_model required" in resp.text


def test_create_provider_run_test_false_requires_skip_reason(
    company_client, make_user, monkeypatch
) -> None:
    """NEW-4-27: explicit run_test=False without skip_reason rejected."""
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@example.com", password="pw-12345678", is_admin=True)
    _login(company_client)

    resp = company_client.post(
        "/settings/admin/llm/providers",
        json={"kind": "openai", "label": "OAI", "api_key": "sk-x", "run_test": False},
    )
    assert resp.status_code == 400
    assert "skip_reason" in resp.text
