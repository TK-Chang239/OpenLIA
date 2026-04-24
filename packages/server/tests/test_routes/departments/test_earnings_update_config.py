"""HTTP tests for /departments/earnings-update/config."""

from __future__ import annotations


def test_get_config_returns_defaults(company_client, auth_user):
    r = company_client.get("/departments/earnings-update/config")
    assert r.status_code == 200
    body = r.json()
    assert body["report_length"] == "normal"
    assert len(body["enabled_section_ids"]) == 8
    assert "quick_take" in body["enabled_section_ids"]
    assert body["custom_sections"] == []


def test_put_config_persists(company_client, auth_user):
    r = company_client.put(
        "/departments/earnings-update/config",
        json={
            "report_length": "elaborative",
            "enabled_section_ids": ["quick_take", "key_financials"],
            "custom_sections": [{"id": "cs_1", "title": "My Notes", "description": "scratch"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["report_length"] == "elaborative"
    assert body["enabled_section_ids"] == ["quick_take", "key_financials"]
    assert body["custom_sections"][0]["title"] == "My Notes"

    r2 = company_client.get("/departments/earnings-update/config")
    assert r2.json()["report_length"] == "elaborative"


def test_put_config_rejects_invalid_length(company_client, auth_user):
    r = company_client.put(
        "/departments/earnings-update/config",
        json={
            "report_length": "bogus",
            "enabled_section_ids": [],
            "custom_sections": [],
        },
    )
    # Pydantic Literal rejection -> 422
    assert r.status_code == 422


def test_put_config_rejects_custom_section_without_title(company_client, auth_user):
    r = company_client.put(
        "/departments/earnings-update/config",
        json={
            "report_length": "normal",
            "enabled_section_ids": [],
            "custom_sections": [{"id": "cs_1", "title": "", "description": ""}],
        },
    )
    assert r.status_code == 422


def test_config_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/earnings-update/config")
    assert r.status_code == 401


def test_config_is_user_scoped(company_client, auth_user, client, user_factory, login_as):
    company_client.put(
        "/departments/earnings-update/config",
        json={
            "report_length": "concise",
            "enabled_section_ids": ["quick_take"],
            "custom_sections": [],
        },
    )
    other = user_factory()
    login_as(other)
    r = client.get("/departments/earnings-update/config")
    assert r.status_code == 200
    # Other user should still see defaults.
    assert r.json()["report_length"] == "normal"
