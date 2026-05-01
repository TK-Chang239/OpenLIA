from openlia.connectors.types import Category
from openlia.departments.secretary import SecretaryDepartment


def test_secretary_identifies_itself():
    d = SecretaryDepartment()
    assert d.name == "secretary"
    assert d.display_name == "Secretary"
    assert d.prompt_name == "secretary"


def test_secretary_uses_everyday_tier():
    assert SecretaryDepartment().tier == "everyday"


def test_secretary_has_no_required_categories():
    # Spec §10.1: Secretary is zero-config; it never disables.
    assert SecretaryDepartment.required_categories == ()


def test_secretary_optional_categories_include_web_search():
    assert Category.WEB_SEARCH in SecretaryDepartment.optional_categories


def test_secretary_does_not_require_runner():
    assert SecretaryDepartment.requires_runner is False
    assert SecretaryDepartment.disable_runtime_routing is False


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
