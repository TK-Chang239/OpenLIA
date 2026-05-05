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


def test_secretary_optional_categories_cover_all_connector_kinds():
    # Secretary now answers questions end-to-end and must reach every
    # connector category any department uses, while staying zero-config
    # (no required categories — see the test above).
    optional = set(SecretaryDepartment.optional_categories)
    assert {
        Category.FINANCIAL,
        Category.NEWS,
        Category.SOCIAL,
        Category.WEB_SEARCH,
    } <= optional


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


def _render_secretary_chat_system() -> str:
    from openlia.llm.runtime.prompts import PromptLoader

    return PromptLoader().render("secretary", "chat.system", skills_menu=[])


def test_secretary_prompt_drops_old_handoff_paragraph():
    # Old prompt explicitly listed "Hand off to: Equity Research for ...".
    # Secretary now answers questions itself and only offers a handoff
    # when the user asks for one (see the "ask first" test below).
    rendered = _render_secretary_chat_system()
    assert "Hand off to" not in rendered


def test_secretary_prompt_requires_asking_before_redirect():
    # Behavioral contract: never call suggest_redirect until the user
    # has explicitly agreed in chat. We assert the contract phrase is
    # rendered into the system prompt so prompt edits can't silently
    # drop it.
    rendered = _render_secretary_chat_system()
    assert "suggest_redirect" in rendered
    assert "ask the user" in rendered.lower()


def test_secretary_welcome_drops_specialist_routing_invite():
    from openlia.llm.runtime.prompts import PromptLoader

    welcome = PromptLoader().render("secretary", "chat.welcome")
    assert "specialist desk" not in welcome.lower()


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
