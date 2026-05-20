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


def test_ingest_passthrough_markdown(client, user_factory, login_as) -> None:
    login_as(user_factory())
    md = "# Heading\n\nbody text\n"
    r = client.post(
        "/report-templates/ingest",
        files={"file": ("template.md", md.encode("utf-8"), "text/markdown")},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"markdown": md}


def test_ingest_falls_back_on_filename_when_mime_is_generic(client, user_factory, login_as) -> None:
    login_as(user_factory())
    md = "# Heading\n"
    r = client.post(
        "/report-templates/ingest",
        files={"file": ("template.md", md.encode("utf-8"), "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["markdown"] == md


def test_ingest_rejects_unsupported_mime(client, user_factory, login_as) -> None:
    login_as(user_factory())
    r = client.post(
        "/report-templates/ingest",
        files={"file": ("logo.png", b"\x89PNG", "image/png")},
    )
    assert r.status_code == 415


def test_parse_returns_sections_and_compiled_spec(client, user_factory, login_as) -> None:
    login_as(user_factory())
    md = (
        "Top-level preamble.\n\n"
        "# Section One\nfirst section body\n\n"
        "# Section Two\nsecond section body\n"
    )
    r = client.post(
        "/report-templates/parse",
        json={"markdown": md, "name": "My Template"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["global_preface"] == "Top-level preamble."
    titles = [s["title"] for s in body["sections"]]
    assert titles == ["Section One", "Section Two"]
    spec = body["template_spec"]
    assert spec["name"] == "My Template"
    assert len(spec["body_sections"]) == 2
    assert spec["body_sections"][0]["id"] == "section_one"


def test_parse_routes_synthesis_and_meta_via_frontmatter(client, user_factory, login_as) -> None:
    login_as(user_factory())
    md = (
        "# Body One\nbody text\n\n"
        "# Synthesis Section\n<!-- openlia\ndispatch_tier: synthesis\n-->\nfindings\n\n"
        "# Self Audit\n<!-- openlia\ndispatch_tier: meta\n-->\nreview prose\n"
    )
    r = client.post(
        "/report-templates/parse",
        json={"markdown": md, "name": "T"},
    )
    assert r.status_code == 200, r.text
    spec = r.json()["template_spec"]
    assert len(spec["body_sections"]) == 1
    assert spec["body_sections"][0]["id"] == "body_one"
    assert len(spec["synthesis_sections"]) == 2
    tiers = {s["id"]: s.get("dispatch_tier", "synthesis") for s in spec["synthesis_sections"]}
    assert tiers["self_audit"] == "meta"


def test_delete_template_removes_row(client, user_factory, login_as) -> None:
    login_as(user_factory())
    tid = client.post(
        "/report-templates",
        json={"name": "A", "template_spec": _MINIMAL_SPEC},
    ).json()["id"]

    r = client.delete(f"/report-templates/{tid}")

    assert r.status_code == 204
    assert client.get(f"/report-templates/{tid}").status_code == 404
