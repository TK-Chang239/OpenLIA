"""Route tests for /chat/sessions CRUD and /messages list."""

from __future__ import annotations


def test_list_returns_sessions_for_user(client, user_factory, login_as):
    u = user_factory()
    login_as(u)
    client.post("/chat/sessions", json={"department": "secretary", "title": "first"})
    r = client.get("/chat/sessions")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "first"


def test_list_hides_other_users_sessions(client, user_factory, login_as):
    a = user_factory()
    b = user_factory()
    login_as(a)
    client.post("/chat/sessions", json={"department": "secretary", "title": "A"})
    login_as(b)
    assert client.get("/chat/sessions").json()["items"] == []


def test_create_session_returns_id(client, user_factory, login_as):
    login_as(user_factory())
    r = client.post("/chat/sessions", json={"department": "secretary", "title": "hi"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"]
    assert body["title"] == "hi"
    assert body["department"] == "secretary"


def test_rename_session(client, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    r = client.patch(f"/chat/sessions/{sid}", json={"title": "renamed"})
    assert r.status_code == 200
    assert client.get("/chat/sessions").json()["items"][0]["title"] == "renamed"


def test_pin_and_archive_via_patch(client, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    assert client.patch(f"/chat/sessions/{sid}", json={"pinned": True}).status_code == 200
    assert client.patch(f"/chat/sessions/{sid}", json={"archived": True}).status_code == 200
    archived = client.get("/chat/sessions?include_archived=true").json()["items"]
    assert archived[0]["is_archived"] is True


def test_delete_session(client, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    assert client.delete(f"/chat/sessions/{sid}").status_code == 204
    assert client.get("/chat/sessions").json()["items"] == []


def test_list_messages(client, user_factory, login_as, seed_message):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    seed_message(session_id=sid, role="user", content="hello")
    r = client.get(f"/chat/sessions/{sid}/messages")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["role"] == "user"
    assert items[0]["content"] == "hello"


def test_list_messages_rejects_other_users(client, user_factory, login_as):
    a = user_factory()
    login_as(a)
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    b = user_factory()
    login_as(b)
    assert client.get(f"/chat/sessions/{sid}/messages").status_code == 403


def test_patch_rejects_other_user(client, user_factory, login_as):
    a = user_factory()
    login_as(a)
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    b = user_factory()
    login_as(b)
    assert client.patch(f"/chat/sessions/{sid}", json={"title": "hacked"}).status_code == 403


def test_department_filter_scopes_list(client, user_factory, login_as):
    login_as(user_factory())
    client.post("/chat/sessions", json={"department": "secretary", "title": "S"})
    client.post(
        "/chat/sessions",
        json={"department": "morning_briefing", "title": "M"},
    )
    r = client.get("/chat/sessions?department=secretary")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "S"
    assert items[0]["department"] == "secretary"


def test_q_filter_matches_title_substring(client, user_factory, login_as):
    login_as(user_factory())
    client.post("/chat/sessions", json={"department": "secretary", "title": "alpha bravo"})
    client.post("/chat/sessions", json={"department": "secretary", "title": "charlie"})
    r = client.get("/chat/sessions?q=alpha")
    titles = [s["title"] for s in r.json()["items"]]
    assert titles == ["alpha bravo"]


def test_get_or_create_by_department_creates_when_none(client, user_factory, login_as):
    login_as(user_factory())
    r = client.get("/chat/sessions/by-department/secretary")
    assert r.status_code == 200
    body = r.json()
    assert body["id"]
    assert body["department"] == "secretary"
    assert body["title"] == "New chat"


def test_get_or_create_by_department_is_idempotent(client, user_factory, login_as):
    login_as(user_factory())
    first = client.get("/chat/sessions/by-department/secretary").json()
    second = client.get("/chat/sessions/by-department/secretary").json()
    assert first["id"] == second["id"]


def test_get_or_create_by_department_scopes_to_user(client, user_factory, login_as):
    a = user_factory()
    b = user_factory()
    login_as(a)
    a_id = client.get("/chat/sessions/by-department/secretary").json()["id"]
    login_as(b)
    b_id = client.get("/chat/sessions/by-department/secretary").json()["id"]
    assert a_id != b_id


def test_get_or_create_by_department_rejects_unknown_department(client, user_factory, login_as):
    login_as(user_factory())
    r = client.get("/chat/sessions/by-department/not_a_real_dept")
    assert r.status_code == 422


def test_create_session_accepts_all_seven_departments(client, user_factory, login_as):
    login_as(user_factory())
    for dep in (
        "secretary",
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "retail_sentiment",
        "macro_research",
        "panic_thermometer",
    ):
        r = client.post("/chat/sessions", json={"department": dep, "title": dep})
        assert r.status_code == 201, dep


def test_session_out_includes_response_length(client, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    r = client.get(f"/chat/sessions/{sid}")
    assert r.status_code == 200
    assert r.json().get("response_length") is None


def test_patch_response_length_persists(client, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    assert (
        client.patch(f"/chat/sessions/{sid}", json={"response_length": "concise"}).status_code
        == 200
    )
    assert client.get(f"/chat/sessions/{sid}").json()["response_length"] == "concise"


def test_patch_response_length_normal_clears_back_to_null(client, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    client.patch(f"/chat/sessions/{sid}", json={"response_length": "detailed"})
    client.patch(f"/chat/sessions/{sid}", json={"response_length": "normal"})
    assert client.get(f"/chat/sessions/{sid}").json()["response_length"] is None


def test_patch_response_length_rejects_unknown_value(client, user_factory, login_as):
    login_as(user_factory())
    sid = client.post("/chat/sessions", json={"department": "secretary", "title": "x"}).json()["id"]
    r = client.patch(f"/chat/sessions/{sid}", json={"response_length": "huge"})
    assert r.status_code == 422
