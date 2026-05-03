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
