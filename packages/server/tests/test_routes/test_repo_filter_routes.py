"""Route tests for extended /repo/items filter/sort/pagination + /repo/facets."""

from __future__ import annotations


def _save(client, report_id: str) -> None:
    resp = client.post("/repo/items", json={"report_id": report_id})
    assert resp.status_code == 201


def test_filtered_list_returns_enriched_rows(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r1 = report_factory(user_id=u.id, department="equity_research", title="AAPL-init")
    r2 = report_factory(user_id=u.id, department="secretary", title="brief-notes")
    _save(client, r1.id)
    _save(client, r2.id)

    resp = client.get("/repo/items", params={"filtered": "true"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["has_more"] is False
    assert len(body["items"]) == 2
    # Every row carries the enriched shape.
    first = body["items"][0]
    assert set(first.keys()) == {
        "id",
        "report_id",
        "department",
        "title",
        "filename",
        "generated_at",
        "saved_at",
    }
    assert first["filename"].endswith(".pdf")


def test_filtered_list_q_filter(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r1 = report_factory(user_id=u.id, title="AAPL-earnings")
    r2 = report_factory(user_id=u.id, title="MSFT-update")
    _save(client, r1.id)
    _save(client, r2.id)

    resp = client.get("/repo/items", params={"q": "aapl"})
    assert resp.status_code == 200
    titles = [row["title"] for row in resp.json()["items"]]
    assert titles == ["AAPL-earnings"]


def test_filtered_list_department_filter_csv(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r1 = report_factory(user_id=u.id, department="equity_research", title="A")
    r2 = report_factory(user_id=u.id, department="secretary", title="B")
    r3 = report_factory(user_id=u.id, department="earnings_update", title="C")
    _save(client, r1.id)
    _save(client, r2.id)
    _save(client, r3.id)

    resp = client.get("/repo/items?department=equity_research,secretary")
    titles = sorted(row["title"] for row in resp.json()["items"])
    assert titles == ["A", "B"]


def test_filtered_list_invalid_sort_returns_422(client, user_factory, login_as):
    login_as(user_factory())
    resp = client.get("/repo/items", params={"sort": "bogus"})
    assert resp.status_code == 422


def test_filtered_list_pagination_has_more_flag(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    for i in range(3):
        r = report_factory(user_id=u.id, title=f"r-{i}")
        _save(client, r.id)

    resp = client.get("/repo/items", params={"page_size": 2, "page": 1})
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["has_more"] is True

    resp2 = client.get("/repo/items", params={"page_size": 2, "page": 2})
    body2 = resp2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False


def test_facets_endpoint(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r1 = report_factory(user_id=u.id, department="equity_research", title="A")
    r2 = report_factory(user_id=u.id, department="equity_research", title="B")
    r3 = report_factory(user_id=u.id, department="secretary", title="C")
    _save(client, r1.id)
    _save(client, r2.id)
    _save(client, r3.id)

    resp = client.get("/repo/facets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    counts = {d["slug"]: d["count"] for d in body["departments"]}
    assert counts == {"equity_research": 2, "secretary": 1}


def test_facets_empty_for_new_user(client, user_factory, login_as):
    login_as(user_factory())
    resp = client.get("/repo/facets")
    assert resp.status_code == 200
    assert resp.json() == {"departments": [], "total": 0}


def test_legacy_list_shape_preserved_when_unfiltered(
    client, user_factory, login_as, report_factory
):
    u = user_factory()
    login_as(u)
    r = report_factory(user_id=u.id)
    _save(client, r.id)
    # No query args → legacy flat shape (items[].id/report_id/created_at only).
    body = client.get("/repo/items").json()
    assert "page" not in body
    assert body["items"][0]["report_id"] == r.id
