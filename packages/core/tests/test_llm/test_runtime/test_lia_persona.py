"""Tests for the Lia persona wiring: department labels and identity partial."""

from __future__ import annotations

from openlia.prompts import DEPARTMENT_LABELS


def test_department_labels_cover_all_seven_desks() -> None:
    expected = {
        "secretary": "Secretary",
        "equity_research": "Equity Research",
        "earnings_update": "Earnings Update",
        "morning_briefing": "Morning Briefing",
        "retail_sentiment": "Retail Sentiment",
        "macro_research": "Macro Research",
        "panic_thermometer": "Panic Thermometer",
    }
    assert DEPARTMENT_LABELS == expected


from pathlib import Path

import pytest

from openlia.llm.runtime.prompts import PromptLoader


@pytest.fixture
def desk_prompts_dir(tmp_path: Path) -> Path:
    """Minimal prompts root that renders {{ current_desk }}."""
    (tmp_path / "shared").mkdir()
    (tmp_path / "secretary.yaml").write_text(
        "chat:\n"
        "  system: |\n"
        "    Right now you are at the {{ current_desk }} desk.\n"
    )
    return tmp_path


def test_render_auto_injects_current_desk_from_labels(
    desk_prompts_dir: Path,
) -> None:
    loader = PromptLoader(root=desk_prompts_dir)
    out = loader.render("secretary", "chat.system")
    assert "Right now you are at the Secretary desk." in out


def test_render_caller_can_override_current_desk(
    desk_prompts_dir: Path,
) -> None:
    loader = PromptLoader(root=desk_prompts_dir)
    out = loader.render("secretary", "chat.system", current_desk="Custom")
    assert "Right now you are at the Custom desk." in out


def test_render_unknown_department_id_passes_label_through_as_id(
    tmp_path: Path,
) -> None:
    """An unknown department_id renders without crashing — the id falls
    through as the desk label so the prompt is still well-formed."""
    (tmp_path / "shared").mkdir()
    (tmp_path / "made_up.yaml").write_text(
        "chat:\n  system: |\n    Desk: {{ current_desk }}\n"
    )
    loader = PromptLoader(root=tmp_path)
    out = loader.render("made_up", "chat.system")
    assert "Desk: made_up" in out


def test_lia_identity_partial_renders_in_an_including_template(
    tmp_path: Path,
) -> None:
    """A department prompt that includes lia_identity must produce the
    canonical Lia self-introduction substring."""
    (tmp_path / "shared").mkdir()
    # Copy the real partial into the temp tree so the include resolves.
    real_partial = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "openlia"
        / "prompts"
        / "shared"
        / "lia_identity.yaml.j2"
    )
    (tmp_path / "shared" / "lia_identity.yaml.j2").write_text(
        real_partial.read_text()
    )
    (tmp_path / "secretary.yaml").write_text(
        "chat:\n"
        "  system: |\n"
        '    {% include "shared/lia_identity.yaml.j2" %}\n'
    )
    loader = PromptLoader(root=tmp_path)
    out = loader.render("secretary", "chat.system")
    # Identity claim
    assert "I'm Lia" in out
    assert "Little Investor Assistant" in out
    # Desk awareness (auto-injected)
    assert "Secretary desk" in out
    # Voice rules header present
    assert "voice rules" in out.lower()
    # Guardrail header present
    assert "won't do" in out.lower()


def _real_loader() -> PromptLoader:
    """A loader bound to the real packaged prompts root."""
    return PromptLoader()


def test_secretary_chat_system_includes_lia_identity() -> None:
    out = _real_loader().render("secretary", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Secretary desk" in out
    # Department brief must mention routing — Secretary's defining duty.
    assert "rout" in out.lower()


def test_equity_research_chat_system_includes_lia_identity() -> None:
    out = _real_loader().render("equity_research", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Equity Research desk" in out


def test_earnings_update_chat_system_includes_lia_identity() -> None:
    out = _real_loader().render("earnings_update", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Earnings Update desk" in out


def test_morning_briefing_chat_system_includes_lia_identity() -> None:
    out = _real_loader().render("morning_briefing", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Morning Briefing desk" in out


def test_macro_research_chat_system_includes_lia_identity() -> None:
    out = _real_loader().render("macro_research", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Macro Research desk" in out


def test_retail_sentiment_chat_system_includes_lia_identity() -> None:
    out = _real_loader().render("retail_sentiment", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Retail Sentiment desk" in out


def test_panic_thermometer_chat_system_includes_lia_identity() -> None:
    out = _real_loader().render("panic_thermometer", "chat.system")
    assert "I'm Lia — short for Little Investor Assistant" in out
    assert "Panic Thermometer desk" in out
