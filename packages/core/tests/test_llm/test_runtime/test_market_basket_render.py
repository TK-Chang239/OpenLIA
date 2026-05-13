"""Tests that the snapshot_format partial reflects the user's basket.

When ``market_basket`` is supplied as a render var, the snapshot format
shows the user's tickers in the Tape / Risk / Macro / Crypto sections.
When omitted/None, the hardcoded fallback (Basket B) renders.
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


def _render(registry: SkillRegistry, basket: dict | None) -> str:
    return build_chat_system_prompt(
        department_id="secretary",
        user_id=None,
        registry=registry,
        market_basket=basket,
    )


def test_default_basket_renders_when_basket_is_none(
    empty_skill_store: SkillRegistry,
) -> None:
    """Hardcoded Basket B falls back when the user pref isn't supplied."""
    out = _render(empty_skill_store, None)
    # Each default section ticker should appear under the "Default basket" header
    assert "SPY" in out and "QQQ" in out
    assert "VIX" in out and "TLT" in out
    assert "DXY" in out
    assert "BTC" in out


def test_user_basket_overrides_default(empty_skill_store: SkillRegistry) -> None:
    custom = {
        "tape": ["IVV", "VTI"],
        "risk": ["UVXY"],
        "macro": ["UUP"],
        "crypto": ["SOL"],
    }
    out = _render(empty_skill_store, custom)
    # User's tickers must appear
    assert "IVV" in out and "VTI" in out
    assert "UVXY" in out
    assert "UUP" in out
    assert "SOL" in out
    # The basket-listing line specifically uses user's tickers, not defaults.
    assert "**Tape:** IVV, VTI" in out
    assert "**Risk:** UVXY" in out
    assert "**Macro:** UUP" in out
    assert "**Crypto:** SOL" in out


def test_partial_basket_still_renders_known_sections(
    empty_skill_store: SkillRegistry,
) -> None:
    """If only some sections supplied, the present sections render those tickers."""
    partial = {
        "tape": ["IVV"],
        "risk": ["UVXY"],
        "macro": ["DXY"],
        "crypto": ["BTC"],
    }
    out = _render(empty_skill_store, partial)
    assert "IVV" in out
    assert "UVXY" in out
