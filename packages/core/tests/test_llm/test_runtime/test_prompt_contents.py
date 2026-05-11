"""Startup-time validation that every department declares its expected slots.

Keeps prompt typos loud: if someone renames `report.stock_initiation.user` to
`report.stock_initiation.user_prompt` without updating ReportRunner, this test
fails in CI instead of failing a user's report generation at runtime.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.prompts import PromptLoader, PromptSlotNotFound

EXPECTED: dict[str, list[str]] = {
    "secretary": ["chat.system"],
    "equity_research": [
        "chat.system",
        "report.system",
        "report.stock_initiation.user",
        "report.stock_update.user",
        "report.sector_research.user",
    ],
    "earnings_update": [
        "report.system",
        "report.earnings_update.user",
    ],
    "morning_briefing": [
        "report.system",
        "report.morning_briefing.user",
    ],
    "macro_research": [
        "batch.t4_assessment.system",
        "batch.t4_assessment.user",
        "batch.t5_assessment.system",
        "batch.t5_assessment.user",
    ],
    "retail_sentiment": [
        "batch.classify_sentiment.system",
        "batch.classify_sentiment.user",
    ],
}


@pytest.mark.parametrize("department_id,slots", list(EXPECTED.items()))
def test_every_department_declares_expected_slots(department_id: str, slots: list[str]) -> None:
    loader = PromptLoader()  # default root: openlia.prompts
    loader.validate_department_slots(department_id, expected=slots)


def test_shared_include_voice_is_rendered_into_secretary_system() -> None:
    """Secretary's chat.system pulls in the canonical Lia identity partial."""
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Secretary desk" in out


def test_shared_include_output_discipline_is_rendered_into_report_system() -> None:
    loader = PromptLoader()
    out = loader.render("equity_research", "report.system", style_guide="x")
    assert "Output discipline" in out


def test_missing_slot_surfaces_prompt_slot_not_found() -> None:
    loader = PromptLoader()
    with pytest.raises(PromptSlotNotFound):
        loader.render("secretary", "report.system")


# Issue #99: chat-mode system prompts must tell the model that user messages
# can carry inline attachment contents and must not be parsed via tools.

_ATTACHMENT_GUIDANCE_PHRASES = ("attached file", "inline", "do not call")


def _assert_inline_attachment_guidance(rendered: str) -> None:
    lowered = rendered.lower()
    for phrase in _ATTACHMENT_GUIDANCE_PHRASES:
        assert phrase in lowered, f"missing attachment guidance phrase {phrase!r}"


def test_secretary_chat_system_includes_attachment_guidance() -> None:
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system")
    _assert_inline_attachment_guidance(out)


def test_equity_research_chat_system_includes_attachment_guidance() -> None:
    loader = PromptLoader()
    out = loader.render("equity_research", "chat.system")
    _assert_inline_attachment_guidance(out)


# Composer response-length picker. The Secretary system prompt must inject
# an explicit length directive when the user has chosen "concise" or
# "detailed", and must omit the section entirely for the default ("normal"
# or unset) so the model uses its own discipline.


def test_secretary_chat_system_omits_response_length_section_by_default() -> None:
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system")
    assert "## Response length" not in out


def test_secretary_chat_system_omits_response_length_section_for_normal() -> None:
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system", response_length="normal")
    assert "## Response length" not in out


def test_secretary_chat_system_injects_concise_directive() -> None:
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system", response_length="concise")
    assert "## Response length" in out
    lowered = out.lower()
    assert "short" in lowered or "concise" in lowered or "sentences" in lowered


def test_secretary_chat_system_injects_detailed_directive() -> None:
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system", response_length="detailed")
    assert "## Response length" in out
    lowered = out.lower()
    assert "thorough" in lowered or "headings" in lowered


def test_secretary_chat_system_omits_memory_section_by_default() -> None:
    """Default ``memory_block=None`` keeps the system prompt clean on
    turns where the user didn't mention any tracked entity."""
    loader = PromptLoader()
    out = loader.render("secretary", "chat.system")
    assert "## Memory" not in out


def test_secretary_chat_system_injects_memory_block_verbatim() -> None:
    """When the route supplies a pre-rendered memory block (slice 11),
    the system prompt embeds it verbatim under the existing partials."""
    loader = PromptLoader()
    block = "## Memory\n- NVDA:\n  - (thesis) Services-margin expansion"
    out = loader.render("secretary", "chat.system", memory_block=block)
    assert "## Memory" in out
    assert "Services-margin expansion" in out


def test_memory_partial_renders_without_context_var() -> None:
    """Defense in depth, parallel to the response_length partial:
    bypassing PromptLoader.render with raw Jinja and no context var
    must not raise UndefinedError under StrictUndefined."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from openlia.llm.runtime.prompts import _default_prompts_root

    env = Environment(
        loader=FileSystemLoader(str(_default_prompts_root())),
        undefined=StrictUndefined,
    )
    tmpl = env.get_template("shared/memory.yaml.j2")
    out = tmpl.render()
    assert "## Memory" not in out


def test_response_length_partial_renders_without_context_var() -> None:
    """Defense in depth: even if a caller bypasses ``PromptLoader.render``
    and uses Jinja directly without supplying ``response_length`` in the
    context, the partial must not raise ``UndefinedError`` under
    ``StrictUndefined``. Models that hit this path otherwise see a runtime
    crash instead of a quiet fallback to 'no length directive'."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from openlia.llm.runtime.prompts import _default_prompts_root

    env = Environment(
        loader=FileSystemLoader(str(_default_prompts_root())),
        undefined=StrictUndefined,
    )
    tmpl = env.get_template("shared/response_length.yaml.j2")
    out = tmpl.render()  # no context at all
    assert "## Response length" not in out
