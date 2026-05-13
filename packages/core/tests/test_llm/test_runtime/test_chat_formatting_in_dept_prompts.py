import pytest
from openlia.llm.runtime.prompts import PromptLoader

CHAT_DEPTS = [
    "secretary",
    "equity_research",
    "earnings_update",
    "morning_briefing",
    "macro_research",
    "retail_sentiment",
    "panic_thermometer",
]


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_chat_system_includes_markdown_formatting_partial(dept: str) -> None:
    loader = PromptLoader()
    rendered = loader.render(dept, "chat.system")
    assert "Markdown formatting:" in rendered, (
        f"{dept} chat.system is missing the chat_formatting partial"
    )
    assert "Do not use:" in rendered
    assert "### " in rendered
