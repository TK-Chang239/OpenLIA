"""Route tests for /report-templates CRUD (PR 9)."""

from __future__ import annotations

_MINIMAL_SPEC = {
    "name": "my_template",
    "global_preface": "",
    "body_sections": [],
    "synthesis_sections": [],
}


def test_create_template_returns_id(client, user_factory, login_as) -> None:
    login_as(user_factory())

    r = client.post(
        "/report-templates",
        json={"name": "Test Template", "template_spec": _MINIMAL_SPEC},
    )

    assert r.status_code == 201
    body = r.json()
    assert body["id"]
    assert body["name"] == "Test Template"
    assert body["template_spec"] == _MINIMAL_SPEC


def test_list_returns_only_users_templates(client, user_factory, login_as) -> None:
    a = user_factory()
    b = user_factory()
    login_as(a)
    client.post("/report-templates", json={"name": "A", "template_spec": _MINIMAL_SPEC})
    login_as(b)

    assert client.get("/report-templates").json()["items"] == []


def test_get_template_404_for_other_users_row(client, user_factory, login_as) -> None:
    a = user_factory()
    b = user_factory()
    login_as(a)
    tid = client.post(
        "/report-templates",
        json={"name": "A", "template_spec": _MINIMAL_SPEC},
    ).json()["id"]
    login_as(b)

    assert client.get(f"/report-templates/{tid}").status_code == 404


def test_update_template_overwrites_spec(client, user_factory, login_as) -> None:
    login_as(user_factory())
    tid = client.post(
        "/report-templates",
        json={"name": "A", "template_spec": _MINIMAL_SPEC},
    ).json()["id"]

    new_spec = dict(_MINIMAL_SPEC, name="renamed_template")
    r = client.put(
        f"/report-templates/{tid}",
        json={"name": "B", "template_spec": new_spec},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "B"
    assert body["template_spec"]["name"] == "renamed_template"


def test_delete_template_removes_row(client, user_factory, login_as) -> None:
    login_as(user_factory())
    tid = client.post(
        "/report-templates",
        json={"name": "A", "template_spec": _MINIMAL_SPEC},
    ).json()["id"]

    r = client.delete(f"/report-templates/{tid}")

    assert r.status_code == 204
    assert client.get(f"/report-templates/{tid}").status_code == 404
