"""Tests for the PR 7 lift: industry-mode selection is per-template opt-in.

`select_report_mode` now accepts an `available_modes` filter. When the active
template declares no industry modes, the runner skips mode selection entirely
and no overlay is applied. The default `stock_initiation` template declares
the legacy four modes (generic, saas, semis, distressed); custom templates
start without any modes.
"""

from __future__ import annotations


def test_default_template_declares_all_four_modes() -> None:
    from openlia.reports.frameworks.loaders.stock_initiation import (
        load_stock_initiation_template,
    )

    spec = load_stock_initiation_template()

    assert set(spec.industry_modes) == {"generic", "saas", "semis", "distressed"}


def test_select_report_mode_with_empty_available_modes_returns_none() -> None:
    from openlia.llm.runtime.report_v2.mode_selector import select_report_mode

    result = select_report_mode(
        facts={},
        material_events=[],
        available_modes=frozenset(),
    )

    assert result is None


def test_select_report_mode_with_available_modes_filters_legacy_result() -> None:
    # When the legacy logic would pick "generic" but the template only has
    # a single distressed mode, the selector returns None (no match).
    from openlia.llm.runtime.report_v2.mode_selector import select_report_mode

    result = select_report_mode(
        facts={},
        material_events=[],
        available_modes=frozenset({"distressed"}),
    )

    assert result is None


def test_select_report_mode_legacy_call_still_returns_a_mode() -> None:
    # No `available_modes` -> legacy hardcoded path; non-Technology subject
    # with no distress markers -> "generic".
    from openlia.llm.runtime.report_v2.mode_selector import select_report_mode

    result = select_report_mode(facts={}, material_events=[])

    assert result == "generic"
