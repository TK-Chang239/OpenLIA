"""Route tests for /graph proposals and constructs (slice 8)."""

from __future__ import annotations

from openlia_server.services import graph_extraction, user_constructs


def _seed_proposal(db_session, user_id: str, *, kind: str = "user_construct", **overrides):
    payload = overrides.pop(
        "payload",
        {
            "construct_kind": "position",
            "statement": "Long NVDA on services-margin thesis",
            "entity_kind": "ticker",
            "entity_value": "NVDA",
            "source_excerpt": "I'm long NVDA",
        },
    )
    row = graph_extraction.record_proposal(
        db_session,
        user_id=user_id,
        source_kind=overrides.pop("source_kind", "session"),
        source_id=overrides.pop("source_id", "s-1"),
        kind=kind,
        payload=payload,
        status=overrides.pop("status", "pending"),
    )
    db_session.commit()
    return row


def _seed_construct(db_session, user_id: str, **overrides):
    row = user_constructs.create_construct(
        db_session,
        user_id=user_id,
        kind=overrides.pop("kind", "position"),
        statement=overrides.pop("statement", "Long NVDA"),
        entity_kind=overrides.pop("entity_kind", "ticker"),
        entity_value=overrides.pop("entity_value", "NVDA"),
        status=overrides.pop("status", "confirmed"),
    )
    db_session.commit()
    return row


# ---------- GET /graph/proposals ----------


def test_list_proposals_defaults_to_pending(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p_pending = _seed_proposal(db_session, u.id, source_id="s-pending")
    p_accepted = _seed_proposal(
        db_session,
        u.id,
        status="accepted",
        source_id="s-accepted",
        payload={
            "construct_kind": "thesis",
            "statement": "AMD lagging",
            "entity_kind": "ticker",
            "entity_value": "AMD",
        },
    )

    r = client.get("/graph/proposals")
    assert r.status_code == 200
    items = r.json()["items"]
    ids = [item["id"] for item in items]
    assert p_pending.id in ids
    assert p_accepted.id not in ids


def test_list_proposals_filters_by_status(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p_dismissed = _seed_proposal(db_session, u.id, status="dismissed")
    r = client.get("/graph/proposals?status=dismissed")
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert p_dismissed.id in ids


def test_list_proposals_ordered_created_at_desc(client, db_session, user_factory, login_as):
    from datetime import UTC, datetime, timedelta

    u = user_factory()
    login_as(u)
    first = _seed_proposal(db_session, u.id, source_id="first")
    second = _seed_proposal(
        db_session,
        u.id,
        source_id="second",
        payload={
            "construct_kind": "concern",
            "statement": "concentration risk",
            "entity_kind": "ticker",
            "entity_value": "TSLA",
        },
    )
    # Force distinct timestamps; func.now() can collide within a transaction.
    base = datetime.now(UTC)
    first.created_at = base - timedelta(seconds=5)
    second.created_at = base
    db_session.commit()

    r = client.get("/graph/proposals")
    ids = [item["id"] for item in r.json()["items"]]
    assert ids.index(second.id) < ids.index(first.id)


def test_list_proposals_scoped_to_user(client, db_session, user_factory, login_as):
    a = user_factory()
    b = user_factory()
    _seed_proposal(db_session, a.id)
    login_as(b)
    assert client.get("/graph/proposals").json()["items"] == []


def test_list_proposals_returns_expected_fields(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p = _seed_proposal(db_session, u.id)
    item = client.get("/graph/proposals").json()["items"][0]
    assert item["id"] == p.id
    assert item["kind"] == "user_construct"
    assert item["status"] == "pending"
    assert item["payload"]["entity_value"] == "NVDA"
    assert "created_at" in item


def test_list_proposals_requires_auth(client):
    assert client.get("/graph/proposals").status_code == 401


# ---------- POST /graph/proposals/{id}/accept ----------


def test_accept_user_construct_returns_construct_row(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p = _seed_proposal(db_session, u.id)
    r = client.post(f"/graph/proposals/{p.id}/accept")
    assert r.status_code == 200
    body = r.json()
    assert body is not None
    assert body["kind"] == "position"
    assert body["status"] == "confirmed"
    assert body["statement"] == "Long NVDA on services-margin thesis"


def test_accept_mention_returns_null(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p = _seed_proposal(
        db_session,
        u.id,
        kind="mention",
        payload={
            "entity_kind": "ticker",
            "entity_value": "NVDA",
            "artifact_kind": "session",
            "artifact_id": "s-1",
        },
    )
    r = client.post(f"/graph/proposals/{p.id}/accept")
    assert r.status_code == 200
    assert r.json() is None


def test_accept_unknown_proposal_returns_404(client, user_factory, login_as):
    login_as(user_factory())
    r = client.post("/graph/proposals/does-not-exist/accept")
    assert r.status_code == 404


def test_accept_other_users_proposal_returns_404(client, db_session, user_factory, login_as):
    a = user_factory()
    b = user_factory()
    p = _seed_proposal(db_session, a.id)
    login_as(b)
    r = client.post(f"/graph/proposals/{p.id}/accept")
    assert r.status_code == 404


def test_accept_already_resolved_returns_409(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p = _seed_proposal(db_session, u.id, status="accepted")
    r = client.post(f"/graph/proposals/{p.id}/accept")
    assert r.status_code == 409


def test_accept_requires_auth(client, db_session, user_factory):
    u = user_factory()
    p = _seed_proposal(db_session, u.id)
    assert client.post(f"/graph/proposals/{p.id}/accept").status_code == 401


# ---------- POST /graph/proposals/{id}/dismiss ----------


def test_dismiss_pending_proposal(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p = _seed_proposal(db_session, u.id)
    r = client.post(f"/graph/proposals/{p.id}/dismiss")
    assert r.status_code == 200
    # Re-listing dismissed status should now include this proposal.
    listed = client.get("/graph/proposals?status=dismissed").json()["items"]
    assert any(item["id"] == p.id for item in listed)


def test_dismiss_unknown_proposal_returns_404(client, user_factory, login_as):
    login_as(user_factory())
    r = client.post("/graph/proposals/nope/dismiss")
    assert r.status_code == 404


def test_dismiss_other_users_proposal_returns_404(client, db_session, user_factory, login_as):
    a = user_factory()
    b = user_factory()
    p = _seed_proposal(db_session, a.id)
    login_as(b)
    r = client.post(f"/graph/proposals/{p.id}/dismiss")
    assert r.status_code == 404


def test_dismiss_already_resolved_returns_409(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    p = _seed_proposal(db_session, u.id, status="dismissed")
    r = client.post(f"/graph/proposals/{p.id}/dismiss")
    assert r.status_code == 409


# ---------- GET /graph/constructs ----------


def test_list_constructs_returns_confirmed_only(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    confirmed = _seed_construct(db_session, u.id)
    rejected = _seed_construct(
        db_session,
        u.id,
        entity_value="AMD",
        statement="short AMD",
        status="rejected",
    )
    items = client.get("/graph/constructs").json()["items"]
    ids = [item["id"] for item in items]
    assert confirmed.id in ids
    assert rejected.id not in ids


def test_list_constructs_filters_by_entity_id(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    nvda = _seed_construct(db_session, u.id)
    _seed_construct(db_session, u.id, entity_value="AMD", statement="long AMD")
    r = client.get("/graph/constructs?entity_id=ticker:NVDA")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == nvda.id


def test_list_constructs_ordered_updated_at_desc(client, db_session, user_factory, login_as):
    from datetime import UTC, datetime, timedelta

    u = user_factory()
    login_as(u)
    first = _seed_construct(db_session, u.id)
    second = _seed_construct(db_session, u.id, entity_value="AMD", statement="long AMD")
    base = datetime.now(UTC)
    first.updated_at = base - timedelta(seconds=5)
    second.updated_at = base
    db_session.commit()

    ids = [item["id"] for item in client.get("/graph/constructs").json()["items"]]
    assert ids.index(second.id) < ids.index(first.id)


def test_list_constructs_scoped_to_user(client, db_session, user_factory, login_as):
    a = user_factory()
    b = user_factory()
    _seed_construct(db_session, a.id)
    login_as(b)
    assert client.get("/graph/constructs").json()["items"] == []


def test_list_constructs_requires_auth(client):
    assert client.get("/graph/constructs").status_code == 401


# ---------- DELETE /graph/constructs/{id} ----------


def test_delete_soft_retires_construct(client, db_session, user_factory, login_as):
    u = user_factory()
    login_as(u)
    c = _seed_construct(db_session, u.id)
    r = client.delete(f"/graph/constructs/{c.id}")
    assert r.status_code == 204
    # Verify status is rejected, row still exists.
    db_session.expire_all()
    from openlia_server.db.models.graph import GraphUserConstruct

    refetched = db_session.get(GraphUserConstruct, c.id)
    assert refetched is not None
    assert refetched.status == "rejected"


def test_delete_unknown_construct_returns_404(client, user_factory, login_as):
    login_as(user_factory())
    r = client.delete("/graph/constructs/does-not-exist")
    assert r.status_code == 404


def test_delete_other_users_construct_returns_404(client, db_session, user_factory, login_as):
    a = user_factory()
    b = user_factory()
    c = _seed_construct(db_session, a.id)
    login_as(b)
    r = client.delete(f"/graph/constructs/{c.id}")
    assert r.status_code == 404


def test_delete_requires_auth(client, db_session, user_factory):
    u = user_factory()
    c = _seed_construct(db_session, u.id)
    assert client.delete(f"/graph/constructs/{c.id}").status_code == 401
