"""Per-report web-search budget resolution.

The runner picks the search budget from a three-level chain:
  1. ``ReportRequest.web_search_budget_override`` (user pref)
  2. The framework JSON's ``web_search_budget_default``
  3. Global fallback of 8

The resolved value flows into two places:
  - ``build_report_system_prompt(search_budget=...)`` so the prompt
    tells the model how many searches it has left
  - ``LLMRequest.web_search_max_uses`` so Anthropic enforces the cap
    server-side and the runtime dispatcher tracks budget consumed.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report import _resolve_search_budget


@pytest.mark.parametrize(
    "framework,override,expected",
    [
        # User override wins over everything.
        ({"web_search_budget_default": 10}, 3, 3),
        # No override → framework default.
        ({"web_search_budget_default": 10}, None, 10),
        ({"web_search_budget_default": 5}, None, 5),
        # Neither set → global fallback 8.
        ({}, None, 8),
        ({"unrelated": 1}, None, 8),
        # Non-int / zero / negative framework values fall through to 8.
        ({"web_search_budget_default": 0}, None, 8),
        ({"web_search_budget_default": -1}, None, 8),
        ({"web_search_budget_default": "10"}, None, 8),
        ({"web_search_budget_default": True}, None, 8),
        # Zero / negative overrides do NOT bypass to framework (intentional:
        # `0` from a user means "disable" but we don't support disabled
        # search yet; treat as invalid, fall through).
        ({"web_search_budget_default": 10}, 0, 10),
        ({"web_search_budget_default": 10}, -1, 10),
    ],
)
def test_resolve_search_budget(
    framework: dict, override: int | None, expected: int
) -> None:
    assert _resolve_search_budget(framework=framework, override=override) == expected


def test_resolve_search_budget_handles_none_framework() -> None:
    """Defensive: callers may pass None for frameworks with no JSON
    (e.g. user_template path)."""
    assert _resolve_search_budget(framework=None, override=None) == 8
    assert _resolve_search_budget(framework=None, override=4) == 4


# ---------- Integration: ReportRequest.web_search_budget_override field ----------


def test_report_request_accepts_web_search_budget_override() -> None:
    """The override field on ReportRequest is the carrier for user
    per-mode budget customization. Default is None (use framework)."""
    from openlia.llm.runtime.messages import ReportRequest

    r1 = ReportRequest(mode="stock_initiation", user_input="AAPL")
    assert r1.web_search_budget_override is None

    r2 = ReportRequest(
        mode="stock_initiation", user_input="AAPL", web_search_budget_override=3
    )
    assert r2.web_search_budget_override == 3
