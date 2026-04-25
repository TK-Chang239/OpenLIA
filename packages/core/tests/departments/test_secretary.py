from openlia.departments.secretary import SecretaryDepartment


def test_secretary_identifies_itself():
    d = SecretaryDepartment()
    assert d.name == "secretary"
    assert d.display_name == "Secretary"
    assert d.prompt_name == "secretary"


def test_secretary_uses_everyday_tier():
    assert SecretaryDepartment().tier == "everyday"


def test_secretary_declares_basic_data_requirements():
    reqs = SecretaryDepartment().data_requirement_types
    assert "stock_quote" in reqs
    assert "company_profile" in reqs


def test_secretary_advanced_requirements_are_soft():
    soft = SecretaryDepartment().optional_requirement_types
    assert "company_news" in soft
    assert "historical_prices" in soft
    assert "economic_events" in soft


def test_secretary_exposes_suggest_redirect_tool():
    tools = SecretaryDepartment().extra_tools
    names = {t["name"] for t in tools}
    assert "suggest_redirect" in names
    schema = next(t for t in tools if t["name"] == "suggest_redirect")
    required = set(schema["parameters"]["required"])
    assert {"department", "reason"}.issubset(required)
    props = schema["parameters"]["properties"]
    enum = set(props["department"]["enum"])
    assert {
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "retail_sentiment",
        "macro_research",
        "portfolio",
    }.issubset(enum)


def test_prompt_file_loads_chat_section():
    """P2-10: orphan top-level `system`/`user` keys removed; only nested
    `chat.*` slots are valid per the runtime spec."""
    from pathlib import Path

    import yaml

    path = Path(__file__).resolve().parents[2] / "src/openlia/prompts/secretary.yaml"
    content = yaml.safe_load(path.read_text())
    assert "chat" in content
    assert "system" in content["chat"]
    assert "welcome" in content["chat"]
    # Top-level orphan keys must be gone.
    assert "user" not in content
    assert content.get("system") is None or "chat" in content
