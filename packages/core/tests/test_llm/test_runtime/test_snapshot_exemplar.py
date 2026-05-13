"""Tests for the snapshot exemplar (fix-chats commit, conditional injection).

The exemplar lives at shared/exemplars/snapshot.yaml.j2 and is injected by
the deterministic exemplar_selector when the user's message matches a
snapshot trigger ("snapshot", "tape", "movers", "what's the market doing",
"what's leading", "premarket", "afterhours").

The selector + wiring ship in a later commit. This test validates the
exemplar file content directly so the worked example is locked before the
selector goes live.
"""

from __future__ import annotations

from pathlib import Path

import openlia


def _exemplar_path() -> Path:
    pkg_root = Path(openlia.__file__).resolve().parent
    return pkg_root / "prompts" / "shared" / "exemplars" / "snapshot.yaml.j2"


def test_snapshot_exemplar_file_exists() -> None:
    assert _exemplar_path().is_file(), "snapshot.yaml.j2 exemplar must exist"


def test_snapshot_exemplar_uses_user_assistant_framing() -> None:
    body = _exemplar_path().read_text(encoding="utf-8")
    assert "**User:**" in body
    assert "**You:**" in body


def test_snapshot_exemplar_demonstrates_all_locked_sections() -> None:
    """Exemplar must include every section anchor from snapshot_format."""
    body = _exemplar_path().read_text(encoding="utf-8")
    for anchor in (
        "Bottom line",
        "Index check",
        "Sector tape",
        "Cross-asset",
        "What's driving it",
        "Trading desk take",
    ):
        assert anchor in body, f"snapshot exemplar missing section: {anchor}"


def test_snapshot_exemplar_demonstrates_trading_desk_quadrant() -> None:
    body = _exemplar_path().read_text(encoding="utf-8")
    for label in ("Long bias", "Hedge", "Avoid", "Watch"):
        assert label in body, f"snapshot exemplar missing quadrant label: {label}"


def test_snapshot_exemplar_uses_default_basket_tickers() -> None:
    """Worked example demonstrates the default basket in use."""
    body = _exemplar_path().read_text(encoding="utf-8")
    # Index check ⇒ tape tickers
    for ticker in ("SPY", "QQQ", "DIA", "IWM"):
        assert ticker in body, f"index-check missing {ticker}"
    # Cross-asset
    for ticker in ("VIX", "TLT", "GLD", "USO", "BTC"):
        assert ticker in body, f"cross-asset missing {ticker}"
