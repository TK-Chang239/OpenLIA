"""Phase 2: GET/PUT /portfolio/prefs — per-user refresh cadence preference."""

from __future__ import annotations


def test_get_returns_default_cadence(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.get("/portfolio/prefs")
    assert r.status_code == 200
    body = r.json()
    assert body["refresh_cadence"] == "daily"


def test_put_updates_cadence(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.put("/portfolio/prefs", json={"refresh_cadence": "hourly"})
    assert r.status_code == 200
    assert r.json()["refresh_cadence"] == "hourly"

    r = client.get("/portfolio/prefs")
    assert r.json()["refresh_cadence"] == "hourly"


def test_put_rejects_invalid_cadence(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.put("/portfolio/prefs", json={"refresh_cadence": "continuous"})
    assert r.status_code == 422 or r.status_code == 400


def test_prefs_endpoints_require_auth(client) -> None:
    r = client.get("/portfolio/prefs")
    assert r.status_code in (401, 403)
    r = client.put("/portfolio/prefs", json={"refresh_cadence": "hourly"})
    assert r.status_code in (401, 403)


def test_per_user_isolation(client, user_factory, login_as) -> None:
    u1 = user_factory()
    u2 = user_factory()
    login_as(u1)
    client.put("/portfolio/prefs", json={"refresh_cadence": "weekly"})

    login_as(u2)
    r = client.get("/portfolio/prefs")
    assert r.json()["refresh_cadence"] == "daily"
