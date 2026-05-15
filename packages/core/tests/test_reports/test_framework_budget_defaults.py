"""Each report framework JSON declares a per-mode default web-search
budget that ReportRunner consumes when the user has no override.

The default is the spec's anchor: small modes (update, earnings, daily
briefings) get a tighter budget; broader modes (initiation, sector,
macro) get a larger one. Sized to keep worst-case cost well under a
dollar per report at $10/1000 native searches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from openlia.llm.runtime.report import _default_frameworks_root

EXPECTED: dict[str, int] = {
    "stock_initiation": 10,
    "stock_update": 5,
    "sector_research": 15,
    "earnings_update": 6,
    "morning_briefing": 6,
}


@pytest.mark.parametrize("mode,expected", list(EXPECTED.items()))
def test_framework_declares_web_search_budget_default(mode: str, expected: int) -> None:
    path = Path(str(_default_frameworks_root())) / f"{mode}.json"
    framework = json.loads(path.read_text())
    assert "web_search_budget_default" in framework, (
        f"{mode}.json is missing 'web_search_budget_default'"
    )
    assert framework["web_search_budget_default"] == expected


def test_web_search_budget_default_is_positive_int_in_all_frameworks() -> None:
    """No silent zeros or floats — the runner enforces this server-side
    but having a typo'd '0' in a framework file silently disables search
    for that mode, which is hard to debug."""
    root = Path(str(_default_frameworks_root()))
    for path in root.glob("*.json"):
        framework = json.loads(path.read_text())
        if "web_search_budget_default" not in framework:
            continue
        v = framework["web_search_budget_default"]
        assert isinstance(v, int) and not isinstance(v, bool), f"{path.name}: not int"
        assert v > 0, f"{path.name}: budget must be positive (got {v})"
