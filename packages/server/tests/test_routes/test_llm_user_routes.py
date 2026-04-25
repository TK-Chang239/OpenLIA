"""NEW-4-11 / P2-12: user-facing /settings/models routes."""

from __future__ import annotations

from openlia_server.db.models.config import LLMModel, LLMProvider, UserLLMPreference


def _login(client, email="user@example.com", password="pw-12345678"):
    client.post("/auth/login", json={"email": email, "password": password})


def _seed_provider_and_models(db_session, *, with_user_pref_for: str | None = None):
    """Seed two providers and one model in each tier."""
    p1 = LLMProvider(id="p-1", kind="openai", label="OpenAI", is_enabled=True)
    p2 = LLMProvider(id="p-2", kind="anthropic", label="Anthropic", is_enabled=True)
    db_session.add_all([p1, p2])

    m_thinking = LLMModel(
        id="m-thinking",
        provider_id="p-2",
        tier="thinking",
        model_ref="claude-sonnet-4",
        display_name="Claude Sonnet 4",
        is_tier_default=True,
        is_enabled=True,
    )
    m_everyday = LLMModel(
        id="m-everyday",
        provider_id="p-1",
        tier="everyday",
        model_ref="gpt-5.4",
        display_name="GPT 5.4",
        is_tier_default=True,
        is_enabled=True,
    )
    m_quick = LLMModel(
        id="m-quick",
        provider_id="p-1",
        tier="quick",
        model_ref="gpt-5.4-mini",
        display_name="GPT 5.4 mini",
        is_tier_default=True,
        is_enabled=True,
    )
    db_session.add_all([m_thinking, m_everyday, m_quick])

    if with_user_pref_for is not None:
        db_session.add(
            UserLLMPreference(
                user_id=with_user_pref_for, tier="everyday", model_id="m-everyday"
            )
        )

    db_session.commit()


def test_roster_requires_auth(company_client) -> None:
    resp = company_client.get("/settings/models")
    assert resp.status_code in (401, 403)


def test_roster_returns_three_tier_payload(company_client, make_user, db_session) -> None:
    make_user(email="user@example.com", password="pw-12345678")
    _login(company_client)
    _seed_provider_and_models(db_session)

    resp = company_client.get("/settings/models")
    assert resp.status_code == 200
    body = resp.json()
    assert {entry["model_ref"] for entry in body["thinking"]} == {"claude-sonnet-4"}
    assert {entry["model_ref"] for entry in body["everyday"]} == {"gpt-5.4"}
    assert {entry["model_ref"] for entry in body["quick"]} == {"gpt-5.4-mini"}
    assert body["everyday"][0]["provider_kind"] == "openai"
    assert body["everyday"][0]["is_tier_default"] is True


def test_put_preference_404_for_unknown_model(
    company_client, make_user, db_session
) -> None:
    make_user(email="user@example.com", password="pw-12345678")
    _login(company_client)
    _seed_provider_and_models(db_session)

    resp = company_client.put(
        "/settings/models/preferences/quick",
        json={"model_id": "nope"},
    )
    assert resp.status_code == 404


def test_put_preference_422_for_tier_mismatch(
    company_client, make_user, db_session
) -> None:
    make_user(email="user@example.com", password="pw-12345678")
    _login(company_client)
    _seed_provider_and_models(db_session)

    resp = company_client.put(
        "/settings/models/preferences/thinking",
        json={"model_id": "m-quick"},
    )
    assert resp.status_code == 422


def test_put_and_delete_preference_round_trip(
    company_client, make_user, db_session
) -> None:
    user = make_user(email="user@example.com", password="pw-12345678")
    _login(company_client)
    _seed_provider_and_models(db_session)

    put_resp = company_client.put(
        "/settings/models/preferences/everyday",
        json={"model_id": "m-everyday"},
    )
    assert put_resp.status_code == 200

    listed = company_client.get("/settings/models/preferences").json()
    assert listed["preferences"]["everyday"] == "m-everyday"

    del_resp = company_client.delete("/settings/models/preferences/everyday")
    assert del_resp.status_code == 200
    after = company_client.get("/settings/models/preferences").json()
    assert "everyday" not in after["preferences"]

    db_session.expire_all()
    assert (
        db_session.query(UserLLMPreference)
        .filter_by(user_id=user.id, tier="everyday")
        .one_or_none()
        is None
    )


def test_effective_returns_resolved_model(
    company_client, make_user, db_session
) -> None:
    make_user(email="user@example.com", password="pw-12345678")
    _login(company_client)
    _seed_provider_and_models(db_session)

    resp = company_client.get("/settings/models/effective/equity_research")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "thinking"
    assert body["model_ref"] == "claude-sonnet-4"
    assert body["provider_kind"] == "anthropic"
