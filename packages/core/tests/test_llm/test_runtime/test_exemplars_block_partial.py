"""Tests for the conditional exemplars_block partial (fix-chats).

Render-time injection of the snapshot / single_stock / continuation
exemplars based on the server-side selector's output. The general
exemplar is rendered unconditionally and is NOT controlled by this
partial.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia.llm.runtime.chat import build_chat_system_prompt
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry


@pytest.fixture
def empty_skill_store(tmp_path: Path) -> SkillRegistry:
    (tmp_path / "user").mkdir(parents=True, exist_ok=True)
    fs = FilesystemSkillStore(root=tmp_path)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


def _render(registry: SkillRegistry, selected: list[str] | None) -> str:
    return build_chat_system_prompt(
        department_id="secretary",
        user_id=None,
        registry=registry,
        selected_exemplars=selected,
    )


def test_no_exemplars_selected_renders_general_only(
    empty_skill_store: SkillRegistry,
) -> None:
    """With None / [], only the always-on general exemplar appears."""
    out = _render(empty_skill_store, None)
    # general exemplar (always-on)
    assert "what's the dollar doing this week" in out.lower()
    # conditional exemplars must NOT render
    assert "Market Snapshot — Wednesday" not in out  # snapshot exemplar title
    assert "thoughts on NVDA here?" not in out  # single_stock exemplar
    assert "QQQ-SPY spread at the open" not in out  # continuation


def test_snapshot_only_renders_snapshot_exemplar(
    empty_skill_store: SkillRegistry,
) -> None:
    out = _render(empty_skill_store, ["snapshot"])
    assert "Market Snapshot — Wednesday" in out, "snapshot exemplar must render"
    assert "thoughts on NVDA here?" not in out
    assert "QQQ-SPY spread at the open" not in out


def test_single_stock_only_renders_single_stock_exemplar(
    empty_skill_store: SkillRegistry,
) -> None:
    out = _render(empty_skill_store, ["single_stock"])
    assert "thoughts on NVDA here?" in out
    assert "Market Snapshot — Wednesday" not in out
    assert "QQQ-SPY spread at the open" not in out


def test_continuation_only_renders_continuation_exemplar(
    empty_skill_store: SkillRegistry,
) -> None:
    out = _render(empty_skill_store, ["continuation"])
    assert "QQQ-SPY spread at the open" in out
    assert "Market Snapshot — Wednesday" not in out
    assert "thoughts on NVDA here?" not in out


def test_multiple_exemplars_all_render(
    empty_skill_store: SkillRegistry,
) -> None:
    out = _render(empty_skill_store, ["snapshot", "continuation"])
    assert "Market Snapshot — Wednesday" in out
    assert "QQQ-SPY spread at the open" in out
    assert "thoughts on NVDA here?" not in out


@pytest.mark.parametrize(
    "selected",
    [None, [], ["snapshot"], ["snapshot", "single_stock", "continuation"]],
)
def test_general_exemplar_always_renders(
    empty_skill_store: SkillRegistry, selected: list[str] | None
) -> None:
    """The general exemplar is always-on regardless of selected_exemplars."""
    out = _render(empty_skill_store, selected)
    assert "what's the dollar doing this week" in out.lower()
