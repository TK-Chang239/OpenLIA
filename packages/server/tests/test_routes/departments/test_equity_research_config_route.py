"""HTTP tests for /departments/equity-research/config."""


def test_get_config_returns_defaults(company_client, auth_user):
    r = company_client.get("/departments/equity-research/config")
    assert r.status_code == 200
    body = r.json()
    assert body["report_mode"] == "stock_initiation"
    assert body["report_length"] == "normal"
    assert "stock_initiation" in body["sections_by_mode"]
    assert len(body["sections_by_mode"]["stock_initiation"]) == 13


def test_put_config_partial_update_length_only(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"report_length": "elaborative"},
    )
    assert r.status_code == 200
    assert r.json()["report_length"] == "elaborative"


def test_put_config_updates_sections_for_mode(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"sections_by_mode": {"stock_update": ["investment_thesis", "event_analysis"]}},
    )
    assert r.status_code == 200
    assert r.json()["sections_by_mode"]["stock_update"] == [
        "investment_thesis",
        "event_analysis",
    ]


def test_put_config_rejects_unknown_section_id(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"sections_by_mode": {"stock_update": ["bogus"]}},
    )
    assert r.status_code == 400
    assert "unknown" in r.json()["detail"].lower()


def test_put_config_adds_custom_section(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={
            "custom_sections_by_mode": {
                "stock_update": [
                    {
                        "id": "custom_esg_x1",
                        "title": "ESG Footnote",
                        "description": "Short note.",
                    }
                ]
            }
        },
    )
    assert r.status_code == 200
    customs = r.json()["custom_sections_by_mode"]["stock_update"]
    assert customs[0]["title"] == "ESG Footnote"


def test_config_requires_auth(company_client_anon):
    r = company_client_anon.get("/departments/equity-research/config")
    assert r.status_code == 401
