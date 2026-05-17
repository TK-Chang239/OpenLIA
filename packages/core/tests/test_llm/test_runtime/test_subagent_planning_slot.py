from __future__ import annotations

from openlia.llm.runtime.prompts import PromptLoader


def test_subagent_planning_slot_renders_for_equity_research() -> None:
    loader = PromptLoader()
    rendered = loader.render(
        "equity_research",
        "report.subagent_planning",
        style_guide="# Style\nProfessional.",
        framework_summary="Sections: company_overview, industry_overview, ... (14 total)",
        user_input="MSFT",
    )
    assert "plan_report" in rendered
    assert "key_questions" in rendered
    assert "word_budget" in rendered
    assert "cross_section_themes" in rendered
    assert "MSFT" in rendered
