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


def test_v23_parse_returns_valid_template_spec(client, user_factory, login_as) -> None:
    login_as(user_factory())
    md = (
        "<!-- openlia\nname: Lithium primer\nticker_anchored: false\n-->\n"
        "# Industry primer\nSet up the sector.\n\n"
        "# Drivers\nName the drivers.\n"
    )
    r = client.post(
        "/report-templates/v23/parse",
        json={"markdown": md, "name": "Untitled"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["validation_errors"] == []
    spec = payload["template_spec"]
    assert spec["name"] == "Lithium primer"
    assert spec["ticker_anchored"] is False
    assert [s["id"] for s in spec["sections"]] == ["industry_primer", "drivers"]


def test_v23_parse_surfaces_compile_errors_as_validation_errors(
    client, user_factory, login_as
) -> None:
    """When the markdown produces a TemplateSpec that fails Pydantic
    validation (e.g. zero sections), the endpoint returns 200 with
    `validation_errors` populated — the UI can show them inline rather
    than rendering a 4xx error."""
    login_as(user_factory())
    r = client.post(
        "/report-templates/v23/parse",
        json={"markdown": "Just prose, no headings.", "name": "Empty"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["validation_errors"]
    assert "at least one section" in payload["validation_errors"][0].lower()


def test_v23_parse_requires_auth(client) -> None:
    r = client.post(
        "/report-templates/v23/parse",
        json={"markdown": "# H1\nbody", "name": "X"},
    )
    assert r.status_code in (401, 403)


def test_v23_builtins_returns_three_templates(client, user_factory, login_as) -> None:
    """Settings pill renders these as flat siblings of user uploads. The
    three report_type built-ins mirror v2.2's mode triad (Stock
    Initiation / Stock Update / Sector Research)."""
    login_as(user_factory())
    r = client.get("/report-templates/v23/builtins")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    report_types = [it["report_type"] for it in items]
    assert sorted(report_types) == sorted(["initiation", "update", "sector_research"])
    names = {it["report_type"]: it["template_spec"]["name"] for it in items}
    assert names["initiation"] == "Stock Initiation"
    assert names["update"] == "Stock Update"
    assert names["sector_research"] == "Sector Research"
    # Each carries a fully-shaped TemplateSpec dict the frontend can
    # render without an extra fetch.
    for it in items:
        spec = it["template_spec"]
        assert spec["name"]
        assert spec["sections"]
        assert "shape_description" in spec
        assert "ticker_anchored" in spec


def test_v23_builtins_requires_auth(client) -> None:
    r = client.get("/report-templates/v23/builtins")
    assert r.status_code in (401, 403)


def test_v23_validate_accepts_well_formed_spec(client, user_factory, login_as) -> None:
    """The /v23/validate path is the JSON-upload sibling of /v23/parse:
    user supplies a TemplateSpec-shaped dict, server confirms it satisfies
    the engine's schema."""
    login_as(user_factory())
    spec = {
        "template_id": "user_initiation_abcd1234",
        "name": "User Initiation",
        "shape_description": "Custom initiation shape.",
        "ticker_anchored": True,
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "intent": "Set up the company.",
                "methodology_hints": [],
            },
        ],
    }
    r = client.post(
        "/report-templates/v23/validate",
        json={"template_spec": spec},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["validation_errors"] == []
    assert body["template_spec"]["name"] == "User Initiation"


def test_v23_validate_surfaces_pydantic_errors_inline(client, user_factory, login_as) -> None:
    """Bad JSON shape returns 200 with validation_errors populated so the
    upload UI can render them next to the file picker rather than as an
    HTTP error."""
    login_as(user_factory())
    bad = {
        "template_id": "Bad ID!",  # fails slug regex
        "name": "X",
        "shape_description": "x",
        "sections": [],  # min_length=1
    }
    r = client.post(
        "/report-templates/v23/validate",
        json={"template_spec": bad},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["validation_errors"]
    assert body["template_spec"] == {}


def test_v23_validate_requires_auth(client) -> None:
    r = client.post(
        "/report-templates/v23/validate",
        json={"template_spec": {}},
    )
    assert r.status_code in (401, 403)


def test_delete_template_removes_row(client, user_factory, login_as) -> None:
    login_as(user_factory())
    tid = client.post(
        "/report-templates",
        json={"name": "A", "template_spec": _MINIMAL_SPEC},
    ).json()["id"]

    r = client.delete(f"/report-templates/{tid}")

    assert r.status_code == 204
    assert client.get(f"/report-templates/{tid}").status_code == 404
