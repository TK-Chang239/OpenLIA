"""Tests for Secretary chat market-side partials.

Covers fix-chats commit 2:
  - shared/market_conventions.yaml.j2 — risk-on/off, sector ETFs, duration,
    credit, dollar, vol regime — desk vocabulary Lia carries every chat.
  - shared/snapshot_format.yaml.j2 — locked structure for market-snapshot
    answers (Tape / Risk / Macro / Crypto / Top movers / Read-through /
    Watch next).
  - shared/autonomous_defaults.yaml.j2 — "decide, do not ask" rule for
    general market questions (issue #2).

Targeted at the Secretary desk because it's the freeform chat surface.
Other chat desks are spot-checked in commit 7.
"""

from __future__ import annotations

from openlia.llm.runtime.prompts import PromptLoader


def _render_secretary() -> str:
    return PromptLoader().render("secretary", "chat.system")


def test_secretary_includes_market_conventions_partial() -> None:
    """market_conventions: risk-on/off, sectors, duration, credit, dollar, vol."""
    out = _render_secretary()
    # Risk regime taxonomy
    assert "risk-on" in out.lower()
    assert "risk-off" in out.lower()
    # SPDR sectors — every sector by ticker
    for ticker in ("XLK", "XLF", "XLE", "XLV", "XLP", "XLY", "XLU", "XLI", "XLB", "XLRE", "XLC"):
        assert ticker in out, f"market_conventions missing sector ticker {ticker}"
    # Duration
    assert "TLT" in out
    assert "duration" in out.lower()
    # Credit
    assert "HYG" in out
    # Dollar
    assert "DXY" in out
    # Vol regime
    assert "VIX" in out


def test_secretary_includes_snapshot_format_partial() -> None:
    """snapshot_format: all 7 section headers present in the rendered prompt."""
    out = _render_secretary()
    for header in (
        "**Tape**",
        "**Risk**",
        "**Macro**",
        "**Crypto**",
        "**Top movers**",
        "**Read-through**",
        "**Watch next**",
    ):
        assert header in out, f"snapshot_format missing header {header}"


def test_secretary_snapshot_default_basket_listed() -> None:
    """The default basket is hardcoded in this commit (user-pref ships later)."""
    out = _render_secretary()
    for ticker in ("SPY", "QQQ", "DIA", "IWM", "VIX", "HYG", "TLT", "DXY", "GLD", "USO", "BTC"):
        assert ticker in out, f"snapshot default basket missing {ticker}"


def test_secretary_includes_autonomous_defaults_partial() -> None:
    """autonomous_defaults: decide, do not ask. Anchored to triggers."""
    out = _render_secretary()
    lower = out.lower()
    # Anchor phrase
    assert "decide, do not ask" in lower or "decide, don't ask" in lower
    # Snapshot trigger words must be enumerated so the model recognizes them
    for trigger in ("snapshot", "tape", "movers"):
        assert trigger in lower
    # Explicit "never ask" / "don't ask" instruction
    assert "never ask" in lower or "do not ask" in lower
