"""HTTP tests for /departments/equity-research/config."""


def test_get_config_returns_defaults(company_client, auth_user):
    r = company_client.get("/departments/equity-research/config")
    assert r.status_code == 200
    body = r.json()
    assert body["report_mode"] == "stock_initiation"
    assert body["report_length"] == "normal"
    assert "stock_initiation" in body["sections_by_mode"]
    assert len(body["sections_by_mode"]["stock_initiation"]) == 14


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


def test_put_config_rejects_unknown_mode(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"report_mode": "bogus_mode"},
    )
    assert r.status_code == 400
    assert "unknown" in r.json()["detail"].lower()


def test_put_config_then_get_roundtrips(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    company_client.put(
        "/departments/equity-research/config",
        json={
            "report_mode": "stock_update",
            "report_length": "concise",
            "sections_by_mode": {"stock_update": ["investment_thesis", "event_analysis"]},
            "custom_sections_by_mode": {
                "stock_update": [{"id": "custom_q1", "title": "Q1 commentary", "description": "x"}]
            },
        },
    )
    body = company_client.get("/departments/equity-research/config").json()
    assert body["report_mode"] == "stock_update"
    assert body["report_length"] == "concise"
    assert body["sections_by_mode"]["stock_update"] == [
        "investment_thesis",
        "event_analysis",
    ]
    assert body["custom_sections_by_mode"]["stock_update"][0]["id"] == "custom_q1"


# ---------- Phase 5f: per-mode web_search budget ----------


def test_get_config_includes_web_search_budgets_by_mode(company_client, auth_user):
    """The GET response always carries the budgets map — empty by default
    so the frontend can render placeholders (framework default) without
    a special case."""
    r = company_client.get("/departments/equity-research/config")
    assert r.status_code == 200
    body = r.json()
    assert body["web_search_budgets_by_mode"] == {}


def test_put_config_persists_per_mode_web_search_budgets(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={
            "web_search_budgets_by_mode": {
                "stock_initiation": 12,
                "stock_update": 3,
            }
        },
    )
    assert r.status_code == 200
    assert r.json()["web_search_budgets_by_mode"] == {
        "stock_initiation": 12,
        "stock_update": 3,
    }
    # Round-trip via fresh GET.
    body = company_client.get("/departments/equity-research/config").json()
    assert body["web_search_budgets_by_mode"]["stock_initiation"] == 12
    assert body["web_search_budgets_by_mode"]["stock_update"] == 3


def test_put_config_rejects_zero_or_negative_web_search_budget(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"web_search_budgets_by_mode": {"stock_initiation": 0}},
    )
    assert r.status_code == 400
    assert "positive" in r.json()["detail"].lower()


def test_put_config_rejects_unknown_mode_in_budget_map(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"web_search_budgets_by_mode": {"bogus_mode": 5}},
    )
    assert r.status_code == 400
    assert "unknown" in r.json()["detail"].lower()


# ---------- report_reasoning_effort (v2.3 extended thinking) ----------


def test_get_config_includes_reasoning_effort_default_medium(company_client, auth_user):
    """The default reasoning value flowing out of the API is 'medium' —
    the UI no longer offers 'off', and the runtime needs reasoning on
    for OpenAI gpt-5.x to invoke web_search as a real tool call."""
    r = company_client.get("/departments/equity-research/config")
    assert r.status_code == 200
    assert r.json()["report_reasoning_effort"] == "medium"


def test_put_config_persists_reasoning_effort_and_roundtrips(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"report_reasoning_effort": "high"},
    )
    assert r.status_code == 200
    assert r.json()["report_reasoning_effort"] == "high"
    body = company_client.get("/departments/equity-research/config").json()
    assert body["report_reasoning_effort"] == "high"


def test_put_config_rejects_invalid_reasoning_effort(company_client, auth_user):
    company_client.get("/departments/equity-research/config")
    r = company_client.put(
        "/departments/equity-research/config",
        json={"report_reasoning_effort": "extreme"},
    )
    assert r.status_code == 400
    assert "reasoning_effort" in r.json()["detail"].lower()
