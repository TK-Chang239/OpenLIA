"""Tests for the single_stock exemplar (fix-chats, conditional injection).

The exemplar lives at shared/exemplars/single_stock.yaml.j2 and gets
injected by the deterministic exemplar_selector when the user's message
matches a single-stock trigger (ticker regex, "thoughts on $X",
"read on X").
"""

from __future__ import annotations

from pathlib import Path

import openlia


def _exemplar_path() -> Path:
    pkg_root = Path(openlia.__file__).resolve().parent
    return pkg_root / "prompts" / "shared" / "exemplars" / "single_stock.yaml.j2"


def test_single_stock_exemplar_file_exists() -> None:
    assert _exemplar_path().is_file(), "single_stock.yaml.j2 exemplar must exist"


def test_single_stock_exemplar_uses_user_assistant_framing() -> None:
    body = _exemplar_path().read_text(encoding="utf-8")
    assert "**User:**" in body
    assert "**You:**" in body


def test_single_stock_exemplar_demonstrates_all_locked_sections() -> None:
    """Five-beat structure: Bottom line / Setup / The story / Risk / reward / Watch next."""
    body = _exemplar_path().read_text(encoding="utf-8")
    for anchor in (
        "Bottom line",
        "Setup",
        "The story",
        "Risk / reward",
        "Watch next",
    ):
        assert anchor in body, f"single_stock exemplar missing section: {anchor}"


def test_single_stock_exemplar_demonstrates_bull_and_bear() -> None:
    """Risk/reward must spell out bull case AND bear case in dollar terms."""
    body = _exemplar_path().read_text(encoding="utf-8")
    assert "Bull case" in body
    assert "Bear case" in body


def test_single_stock_exemplar_uses_concrete_ticker_anchors() -> None:
    """The example uses NVDA — anchored so a future swap doesn't silently break."""
    body = _exemplar_path().read_text(encoding="utf-8")
    assert "NVDA" in body
    # Multiple-vs-history reference (the '32x' / '10Y median' comparison)
    assert "10Y median" in body or "10-year median" in body
