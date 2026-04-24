"""HTTP tests for /departments/morning-briefing/config."""

from __future__ import annotations


def test_get_config_returns_defaults(company_client, auth_user):
    r = company_client.get("/departments/morning-briefing/config")
    assert r.status_code == 200
    body = r.json()
    assert body["report_length"] == "normal"
    assert len(body["enabled_section_ids"]) == 7
    assert body["reference_portfolio"] is False
    assert body["section_topics"] == {}
    assert body["custom_sections"] == []


def test_put_config_persists(company_client, auth_user):
    payload = {
        "report_length": "concise",
        "enabled_section_ids": ["executive_summary", "global_macro"],
        "section_topics": {"global_macro": [{"topic": "War", "notes": "Ukraine"}]},
        "custom_sections": [
            {"id": "c1", "title": "My Focus", "description": "FX desk"}
        ],
        "reference_portfolio": True,
    }
    r = company_client.put("/departments/morning-briefing/config", json=payload)
    assert r.status_code == 200
    assert r.json()["report_length"] == "concise"

    r2 = company_client.get("/departments/morning-briefing/config")
    body = r2.json()
    assert body["enabled_section_ids"] == ["executive_summary", "global_macro"]
    assert body["reference_portfolio"] is True
    assert body["section_topics"]["global_macro"][0]["topic"] == "War"


def test_put_config_rejects_invalid_length(company_client, auth_user):
    payload = {
        "report_length": "tiny",
        "enabled_section_ids": [],
        "section_topics": {},
        "custom_sections": [],
        "reference_portfolio": False,
    }
    r = company_client.put("/departments/morning-briefing/config", json=payload)
    assert r.status_code == 422


def test_put_config_rejects_unknown_section(company_client, auth_user):
    payload = {
        "report_length": "normal",
        "enabled_section_ids": ["not_a_section"],
        "section_topics": {},
        "custom_sections": [],
        "reference_portfolio": False,
    }
    r = company_client.put("/departments/morning-briefing/config", json=payload)
    assert r.status_code == 422


def test_config_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/morning-briefing/config")
    assert r.status_code == 401
